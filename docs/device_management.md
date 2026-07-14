# RoostOS Device Management & State Engine

Device Management is the core parental control and security feature of RoostOS. It allows administrators to identify, classify, and apply schedules and firewall policies to network clients based on their MAC addresses. 

This document describes the mechanics of device discovery, the SQLite state database, and the logic of the time-schedule and override engine.

---

## 1. Device Discovery Pipeline

```
  [ Client Connects ] 
          │
          ▼
  [ Kea DHCP Server ] ────(lease commit)────► [ Run Script Hook ]
                                                    │
                                                    ▼ (dbus-send)
  [ SQLite Cache ] ◄──(store)─── [ Roost Engine (roostd) ]
                                                    │
                                                    ├────► [ Cockpit Web UI (Signal) ]
                                                    ▼
                                            [ nftables Sets ]
```

1.  **Lease Commit**: When a client requests an IP, Kea commits a DHCP lease and executes the hook library `libdhcp_run_script.so`.
2.  **D-Bus Signal**: The hook script runs a lightweight shell wrapper that fires a D-Bus signal on the system bus:
    *   **Interface**: `org.roostos.DHCP`
    *   **Signal**: `LeaseCommitted(string mac, string ip, string hostname)`
3.  **Daemon Update**: The Roost Engine daemon (`roostd`) catches the signal and:
    *   Queries its SQLite transient cache to check if this MAC has been seen before.
    *   Checks `/etc/roostos/devices.yaml` to see if the MAC is a registered device.
    *   Updates the client's last-seen IP and hostname.
4.  **Tag Assignment & Isolation**:
    *   If the MAC is registered in `/etc/roostos/devices.yaml`, the engine resolves its user-defined tags, room/location, and owner (which implicitly act as tags).
    *   If the MAC is **unregistered / randomized**, the engine automatically logs it to `discovered_devices` in the SQLite cache and tags it as `system:unregistered`.
    *   The firewall then evaluates rules matching the client's resolved tags. For example, if a rule in `schedules.yaml` blocks `system:unregistered`, the client's MAC is immediately added to the `blocked_macs` or `quarantined_macs` nftables set.

---

## 2. Transient State Cache (SQLite Schema)

All temporary and dynamic values are stored in `/var/lib/roostos/state.db`. This database can be safely wiped at any time; it does not contain persistent configuration settings.

### Table: `discovered_devices`
Tracks all MAC addresses that have ever connected to DHCP but are not yet registered in the YAML configuration.
```sql
CREATE TABLE discovered_devices (
    mac TEXT PRIMARY KEY,
    last_ip TEXT NOT NULL,
    hostname TEXT,
    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
    quarantined INTEGER DEFAULT 1
);
```

### Table: `temporary_bypasses`
Tracks dynamic time extensions (e.g. "allow child's tablet online for 30 minutes").
```sql
CREATE TABLE temporary_bypasses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mac TEXT NOT NULL,
    bypass_type TEXT NOT NULL,  -- 'time_extension' (e.g., +30m) or 'unblock' (ignore schedule)
    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL
);
CREATE INDEX idx_bypasses_expires ON temporary_bypasses(expires_at);
```

### Table: `accumulated_usage`
Tracks screen-time usage (active minutes) accumulated per target/MAC today.
```sql
CREATE TABLE accumulated_usage (
    target_id TEXT NOT NULL,      -- Can be a MAC address or Person ID
    date TEXT NOT NULL,           -- Format: 'YYYY-MM-DD'
    used_seconds INTEGER DEFAULT 0,
    PRIMARY KEY (target_id, date)
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

## 3. UPnP Staging Gateway

To resolve the security risks associated with standard Universal Plug and Play (UPnP)—where compromised internal devices or IoT devices can open ports automatically—RoostOS implements a **UPnP Staging Gateway**:

```
[ Game Console / Device ] ───(UPnP Request)───► [ miniupnpd (Router Daemon) ]
                                                       │
                                                       ▼ (Custom verification script)
                                                [ Roost Engine (roostd) ]
                                                       │
                                            ┌──────────┴──────────┐
                                   (Matches upnp_trusted?)  (No trust / unknown)
                                            ▼                     ▼
                                     [ Allow Access ]      [ Queue in SQLite ]
                                                                  │
                                                                  ▼ (Emit Signal)
                                                           [ Cockpit Web UI ]
                                                                  │
                                                            (Parent clicks)
                                                       ┌──────────┴──────────┐
                                                   (Approve)             (Reject)
                                                       ▼                     ▼
                                                [ Add nftables ]       [ Block port ]
```

1.  **Request Interception**: RoostOS runs `miniupnpd` configured to pass incoming UPnP port mapping requests to a custom verification script hook before applying them to the firewall.
2.  **Trust Verification**: The script checks `devices.yaml` for the requesting client's MAC address:
    *   **Trusted Device**: If `upnp_trusted: true` is configured for the MAC, the request is immediately allowed.
    *   **Pre-Approved Port**: If the request matches a port-protocol entry in the client's `upnp_allowed_ports` array, it is immediately allowed.
3.  **Parent Staging Queue**: If the device is not trusted or the port is not pre-approved:
    *   The request is logged to the `pending_upnp_requests` SQLite cache.
    *   `roostd` broadcasts the D-Bus signal `UPnPRequestReceived(mac, external_port, protocol, description)`.
    *   The request is held in a pending state, returning a temporary rejection to the client.
4.  **Admin Review**: The parent/admin receives a notification in the Cockpit Web interface showing the device details and the requested port. The parent can select:
    *   **Approve Once**: Temporarily applies the port forward in nftables.
    *   **Approve & Remember**: Appends the port/protocol rule to `upnp_allowed_ports` in `devices.yaml`. Future requests for this mapping are auto-approved.
    *   **Approve & Trust Device**: Sets `upnp_trusted: true` in `devices.yaml`, allowing all future UPnP requests from this hardware.
    *   **Deny**: Rejects the mapping and logs the block.

---

## 4. The State Engine Logic

The firewall's state is evaluated by a background thread inside `roostd` that runs every 60 seconds (a "tick"), or immediately upon a configuration update or D-Bus request.

### A. Tag-Based Target Resolution & Location Hierarchy
Schedules and firewall blocks target selectors rather than raw MAC addresses:
*   `tag:<name>`
*   `person:<id>`
*   `location:<id>`
*   `mac:<address>`

During the evaluation loop, the daemon compiles these selectors into a flat list of active MAC addresses:
1.  **Direct Resolution**: If a schedule in `schedules.yaml` targets `person:alice_profile`, `roostd` scans `/etc/roostos/devices.yaml` to find all devices where `owner` is `alice_profile`.
2.  **Tag Expansion**: If a schedule targets `tag:kids`, `roostd` maps it to all devices containing `kids` in their `tags` list inside `devices.yaml`.
3.  **Recursive Location Resolution**: If a schedule targets `location:<id>`, the daemon checks `devices.yaml`:
    *   If `<id>` corresponds to a **Room**: Map to all devices where `location` is the Room ID.
    *   If `<id>` corresponds to a **Building**:
        1. Find all Rooms that belong to this Building ID.
        2. Map to all devices assigned directly to the Building ID.
        3. Map to all devices assigned to any of those child Rooms.
4.  **Built-in tags**: If a schedule targets `tag:system:unregistered`, `roostd` maps it to all active MAC addresses logged in `discovered_devices` that have not been registered in `devices.yaml`.

### B. Daily Usage Tracking (Accumulation Limits)
To enforce limits like "2 hours of screen time per day," RoostOS monitors device activity:
1.  **Activity Sensing**: During the 60-second tick, `roostd` queries `nftables` byte counters for each active client MAC address.
2.  **Threshold Check**: If a MAC address has transferred more than **50 Kilobytes** of data during the last minute, the client is marked as active.
3.  **Database Logging**: One minute (60 seconds) is added to the `used_seconds` counter in the `accumulated_usage` table for that MAC, and also for its associated `Person` ID.
4.  **Enforcement**: Once `used_seconds` exceeds the configured daily limit (defined in `schedules.yaml`), the client's MAC addresses are added to the `blocked_macs` nftables set.
5.  **Reset**: A cron job resets all entries in `accumulated_usage` at midnight local time.

### C. Applying Firewall Changes (nftables Integration)
Instead of reloading the entire nftables engine (which is disruptive and slow), the state engine manages memberships in named nftables sets:
*   **`quarantined_macs`**: Packets from these MAC addresses are dropped completely.
*   **`blocked_macs`**: Packets from these MAC addresses are dropped only when attempting to route to the WAN interface.

During each engine tick, `roostd` determines the list of MACs that should be blocked. It then runs:
1.  `nft flush set inet filter quarantined_macs`
2.  `nft add element inet filter quarantined_macs { mac1, mac2, ... }`
3.  `nft flush set inet filter blocked_macs`
4.  `nft add element inet filter blocked_macs { mac3, mac4, ... }`
