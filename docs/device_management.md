# RoostOS Device Management & State Engine

Device Management is a core parental control and security feature of RoostOS. It allows administrators to identify, classify, and apply time schedules, daily screen time allowances, and network isolation policies to network clients based on their MAC addresses.

This document describes the mechanics of device discovery, the SQLite state database cache, Family Controls integration (`roostos-timeguardd`), and the three-set `nftables` state engine logic.

---

## 1. Device Discovery & Lease Pipeline

```
  [ Client Connects ] 
          │
          ▼
  [ Kea DHCP Server ] ────(lease commit)────► [ Run Script Hook ]
                                                    │
                                                    ▼ (D-Bus Signal)
  [ SQLite Cache ] ◄──(store)─── [ Node Daemon (roostos-core) ]
                                                    │
                                                    ▼ (MQTT Publish)
                                         [ Central Engine (roostos-engine) ]
                                                    │
                                           (Registered in devices.yaml?)
                                           ┌────────┴────────┐
                                         (Yes)              (No)
                                           │                 │
                                    [ Assign Tags ]   [ Apply Unregistered Policy ]
                                           │                 │
                                           └────────┬────────┘
                                                    ▼
                                         [ Update nftables Sets ]
```

1. **Lease Commit**: When a client requests an IP, Kea commits a DHCP lease and executes `libdhcp_run_script.so` (`roost-dhcp-hook`).
2. **D-Bus & MQTT Event**: The hook script emits a local D-Bus signal (`org.roostos.DHCP.LeaseCommitted`). `roostos-core` catches this signal, stores it in its local SQLite cache (`/var/lib/roostos/state.db`), and publishes an MQTT event to `roostos/dhcp/lease/commit`.
3. **Engine Synchronization**: `roostos-engine` receives the MQTT lease event:
   - If the MAC address is registered in `devices.yaml`, the engine resolves its assigned owner, room, location, and tags.
   - If the MAC address is unknown, `roostos-engine` logs it to `discovered_devices` in the central repository and evaluates `unregistered_device_policy` from `system.yaml`.
4. **Policy Enforcement**:
   - If `unregistered_device_policy: deny`, `roostos-core` adds the unknown MAC to the `quarantined` nftables set (full forward drop).
   - If `unregistered_device_policy: allow`, the unknown device gets standard network forwarding access.

---

## 2. Transient State Cache (SQLite Schema)

All temporary and dynamic node values are cached in `/var/lib/roostos/state.db`. This database can be safely cleared at any time; it does not contain persistent configuration settings.

### Table: `active_leases`
Tracks active DHCP client leases on the local node.
```sql
CREATE TABLE active_leases (
    mac TEXT PRIMARY KEY,
    ip TEXT NOT NULL,
    hostname TEXT,
    quarantined INTEGER DEFAULT 1,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `pending_upnp_requests`
Queues incoming UPnP requests awaiting parent/admin staging review.
```sql
CREATE TABLE pending_upnp_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mac TEXT NOT NULL,
    internal_ip TEXT NOT NULL,
    external_port INTEGER NOT NULL,
    internal_port INTEGER NOT NULL,
    protocol TEXT NOT NULL,       -- 'tcp' or 'udp'
    description TEXT,
    requested_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. Family Controls Integration (`roostos-timeguardd`)

`roostos-timeguardd` handles OS-level screen time tracking on client workstations and mobile devices:

1. **Local Session Tracking**: On client machines, `roostos-timeguardd` queries `systemd-logind` over local D-Bus to track active human user sessions.
2. **Offline Resilience**: Time limits are cached locally in `/var/lib/roostos-timeguardd/state.json`. If a client device moves off the home network, session monitoring and automatic locking continue locally.
3. **MQTT Heartbeat & Central Sync**: When connected to the home network, `roostos-timeguardd` publishes periodic heartbeats over MQTT (`roostos/timeguard/heartbeat/{username}`). `roostos-engine` aggregates screen time accumulated across multiple client devices owned by the same `Person`.
4. **Global Lock Command**: When a user's total daily limit is reached (combining network activity and client session time), `roostos-engine` publishes a lock payload to `roostos/timeguard/limits/{username}`, causing `roostos-timeguardd` to issue `loginctl lock-sessions` instantly and block subsequent PAM logins.

---

## 4. UPnP Staging Gateway

To resolve the security risks of automated UPnP port forwarding:

```
[ Device ] ───(UPnP Request)───► [ miniupnpd ] ───► [ roostos-core ]
                                                          │
                                                ┌─────────┴─────────┐
                                      (Matches upnp_trusted?)   (Untrusted)
                                                ▼                   ▼
                                         [ Allow Access ]    [ Queue in SQLite ]
                                                                    │
                                                                    ▼ (MQTT Signal)
                                                           [ roostos-web ]
                                                                    │
                                                            (Parent Approves)
                                                                    ▼
                                                           [ Add nftables DNAT ]
```

1. **Request Interception**: `miniupnpd` passes incoming UPnP mapping requests to `roostos-core`.
2. **Trust Verification**: `roostos-core` checks `devices.yaml` for the requesting MAC:
   - **Trusted Device**: If `upnp_trusted: true` is configured, the request is immediately allowed.
   - **Pre-Approved Port**: If the request matches an entry in `upnp_allowed_ports`, it is immediately allowed.
3. **Staging Queue**: If untrusted, the request is queued in `pending_upnp_requests` and broadcast via MQTT (`roostos/upnp/request`). The parent can click **Approve Once**, **Approve & Remember**, or **Approve & Trust Device** in `roostos-web`.

---

## 5. The State Engine Logic (Three nftables Sets)

`roostos-core` evaluates network state every 60 seconds (or immediately upon receiving an MQTT configuration broadcast).

### A. Tag & Selector Resolution
Selectors in `schedules.yaml` are expanded into a flat set of target MAC addresses:
- `tag:<name>`: All devices carrying `<name>` in `tags`.
- `person:<id>`: All devices where `owner == <id>`.
- `location:<id>`: All devices assigned to a Room or recursively to a Building.
- `mac:<address>`: Specific hardware MAC address.

### B. Daily Allowance Accumulation
During each 60-second evaluation tick, `roostos-core` checks byte transfer counters in `nftables`. If a MAC transfers >50KB in a minute, usage counters increase. When `used_seconds` >= `daily_limit * 60`, the MAC is marked for internet blocking.

### C. Three-Set `nftables` Structure

Instead of constantly rebuilding complex rules, `roostos-core` manages membership in three dynamic `nftables` sets:

1. **`quarantined`**: Devices blocked by default when `unregistered_device_policy: deny`. Packets are dropped at the input and forward chains completely.
2. **`schedule_blocked`**: Devices currently restricted by active time-window schedules or exhausted daily screen time limits. Packets are dropped **only when forwarding to the WAN interface** (LAN subnets, local printers, and local media servers remain accessible).
3. **`admin_blocked`**: Devices permanently blocked from internet access by administrator policy. Packets are dropped when forwarding to the WAN interface.

```bash
# Delta updates executed by roostos-core
nft add element inet filter quarantined { a4:83:e7:12:34:56 }
nft add element inet filter schedule_blocked { 4c:32:75:98:76:54 }
nft add element inet filter admin_blocked { 00:09:b0:12:34:56 }
```
