# RoostOS Multi-Node Test Harness & Automation Framework

RoostOS modifies low-level kernel networking, routing tables, and dynamic `nftables` firewall rulesets (NAT masquerading, port forwarding, DNS hijacking, bedtime MAC blocks, VLAN/Guest isolation). Testing these changes directly on a host machine is risky and can break local network connectivity.

The RoostOS Multi-Node Test Harness provides an isolated, containerized virtual network environment using Docker Compose and Pytest. It allows spinning up a virtual router along with client nodes and an upstream internet simulator to safely validate network behaviors and firewall policies.

---

## 1. Network Topology & Roles

```
+---------------------------------------------------------------------------------------------------+
|                                     TEST HARNESS ENVIRONMENT                                      |
|                                                                                                   |
|  +---------------------+                                                                          |
|  |     upstream-wan    |  172.30.1.100 (Simulates Internet / External Web & DNS)                 |
|  +----------+----------+                                                                          |
|             |                                                                                     |
|             | [ wan_net : 172.30.1.0/24 ]                                                         |
|             |                                                                                     |
|  +----------+----------+       [ mgmt_net : 172.30.0.0/24 ]       +---------------+               |
|  |    roostos-router   +==========================================+  test-runner  |               |
|  |     (DUT Node)      |  (Management API, D-Bus, Engine daemon)  |    (Pytest)   |               |
|  +----+------+-------+-+                                          +-------+-------+               |
|       |      |       |                                                    |                       |
|       |      |       | [ guest_net : 172.30.3.0/24 ]                      |                       |
|       |      |       +-----------------------------+                      | (exec/api)            |
|       |      |                                     |                      |                       |
|       |      | [ lan_net : 172.30.2.0/24 ]  +-------+--------+             |                       |
|       |      |                              |  client-guest  |<------------+                       |
|       |      |                              |  172.30.3.50   |                                     |
|       | +----+---------+                    +----------------+                                     |
|       | |  client-lan  |<--------------------------------------------------+                       |
|       | |  172.30.2.50 |                                                                           |
|       | +--------------+                                                                           |
|       |                                                                                           |
|       +=== Port 8080:8000 exposed to Host ====================> [ Host Browser: http://localhost:8080 ]
+---------------------------------------------------------------------------------------------------+
```

### Node Descriptions
* **`roostos-router` (Device Under Test)**:
  - Linux container with `NET_ADMIN` and `NET_RAW` capabilities and `net.ipv4.ip_forward=1`.
  - Built using a multi-stage Dockerfile that builds and installs our native **Debian packages (`.deb`)** (`roostos-sdk`, `roostos-engine`, `roostos-core`, `roostos-web`, `roostos-timeguardd`, `roostos-router`), verifying package creation, dependency trees, and standard Linux filesystem locations.
  - Runs `roostos-engine` and `roostos-web` with real `nftables` loaded in its network namespace.
  - Attached to all test networks and exposes Web Admin on port `8080` to the host.
* **`upstream-wan` (Internet Simulator)**:
  - Attached to `wan_net` at `172.30.1.100`.
  - Runs test HTTP (port 80), DNS (port 53), and echo services to simulate the broader Internet.
* **`client-lan` (LAN Client)**:
  - Attached to `lan_net` at `172.30.2.50` with MAC `02:42:ac:1e:02:32` and default gateway pointing to `172.30.2.1`.
* **`client-guest` (Guest Client)**:
  - Attached to `guest_net` at `172.30.3.50` with default gateway pointing to `172.30.3.1`.
* **`test-runner` (Automation Controller)**:
  - Pytest container attached to `mgmt_net` (`172.30.0.10`).
  - Executes socket and packet probes from client nodes and coordinates config updates via the RoostOS API.

---

## 2. Test Organization: Unit vs Automation

The repository separates tests into two primary tiers:

| Tier | Directory | Purpose | How to Run |
|---|---|---|---|
| **Unit Tests** | `roostos-engine/tests/`<br>`roostos-web/tests/unit/`<br>`tests/harness/` | Fast, mock-based unit tests testing business logic, schemas, and parsers without Docker or root. | `make test` |
| **Automation Tests** | `tests/automation/` | Real network socket probes, NAT checks, firewall rule enforcement, and zone isolation inside container namespaces. | `make test-harness` |

---

## 3. Running Automation Tests

### Execute the Full Automated Suite
```bash
make test-harness
```
Or via python CLI:
```bash
python3 scripts/run_test_harness.py
```

### Filter by Test Expression
```bash
python3 scripts/run_test_harness.py -k firewall
python3 scripts/run_test_harness.py -k nat
```

### Keep Containers Alive After Test Run (for Debugging)
```bash
python3 scripts/run_test_harness.py --keep-alive
```

---

## 4. Manual Web UI Testing & Interactive Sandbox

You can spin up the full multi-node network in interactive mode to test the Web UI in your host browser:

```bash
make test-harness-up
```

1. Open **`http://localhost:8080`** in your host web browser.
2. Log in with:
   - **Username**: `admin`
   - **Password**: `password`
3. You can interactively create firewall rules, update device schedules, or change network settings.
4. Because the router is connected to the real simulated client nodes (`client-lan` and `client-guest`), rule changes immediately affect live network traffic.
5. Press `Ctrl+C` in your terminal to safely tear down the containers.

---

## 5. Deployment Scenarios

The harness supports different topology and config scenarios located in `test-harness/scenarios/`:

* **`default`**: Standard single-router deployment (WAN + LAN bridge + Guest VLAN).
* **`multi-wan`**: Dual-WAN configuration with primary and failover gateway interfaces.
* **`mesh-satellite`**: Secondary RoostOS satellite access point operating in 802.11s bridged backhaul mode.
* **`vpn-gateway`**: Policy-routed Wireguard VPN gateway.

To run a specific scenario:
```bash
make test-harness-scenario SCENARIO=multi-wan
```
Or:
```bash
python3 scripts/run_test_harness.py --scenario vpn-gateway --interactive
```

---

## 6. Writing Live Socket Automation Tests

Automation tests use `NodeExecutor` to perform real socket actions from client containers:

```python
from tests.harness.client import NodeExecutor
from tests.harness.router_api import RoostOSRouterAPI


def test_firewall_rule_live(
    router_api: RoostOSRouterAPI,
    lan_client: NodeExecutor,
    wan_host: str,
) -> None:
    # 1. Probe socket connection from client container -> should succeed
    probe = lan_client.probe_tcp_socket(host=wan_host, port=80)
    assert probe.connected is True

    # 2. Block client dynamically via RoostOS API
    router_api.block_mac_address("02:42:ac:1e:02:32")

    # 3. Probe socket connection again -> assert socket timeout / error
    blocked_probe = lan_client.probe_tcp_socket(host=wan_host, port=80, timeout=2.0)
    assert blocked_probe.connected is False

    # 4. Unblock client via API
    router_api.unblock_mac_address("02:42:ac:1e:02:32")

    # 5. Connection succeeds again
    restored = lan_client.probe_tcp_socket(host=wan_host, port=80)
    assert restored.connected is True
```
