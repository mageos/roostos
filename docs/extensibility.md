# RoostOS Extensibility & Unified Plugin Architecture

To prevent core system bloat and foster community-driven additions, RoostOS provides a secure, containerized extension system. This architecture ensures third-party extensions (e.g. ad blockers, dynamic network visualizers, parental portals, media servers) run in isolated containers while integrating securely with the host OS, REST API, MQTT bus, and Web Console UI.

---

## 1. Unified Plugin Model & Categories

Plugins are packaged extensions categorized into two types via a `type` field:

1. **`core_service`**:
   - Implements system-level infrastructure capabilities (e.g. DNS resolution, DHCP, OAuth2 identity, LDAP, Certificate Authority).
   - Runs directly on the router hardware node.
   - May expose local D-Bus interfaces (e.g. `org.roostos.DNSResolver`) or interface directly with `roostos-core`.
   - Engine automatically proxies its REST endpoints under `/api/v1/plugins/{id}/*`.

2. **`application`**:
   - General-purpose containerized software (e.g. Home Assistant, Plex, Nextcloud).
   - Designed to run across compute nodes in the RoostOS cluster.
   - Subject to strict sandbox permissions and scope controls.

---

## 2. Security, Authentication & Scope Permissions

RoostOS plugins operate under a zero-trust security model:

```
[ Plugin Installation Request ]
             │
             ▼
[ Review Requested Scopes in UI/CLI ] ───(Admin Grants Consent)───► [ Certificate Manager ]
                                                                             │
                                                                             ▼ (Issue mTLS Cert)
                                                                    [ Container Provisioning ]
                                                                             │
                                              ┌──────────────────────────────┴──────────────────────────────┐
                                              ▼                                                             ▼
                                [ REST API Auth (mTLS -> JWT) ]                              [ MQTT Broker ACL (mTLS OID) ]
```

1. **Scope Declaration & Consent**: Every plugin declares `requested_scopes` in its `manifest.json` (e.g. `devices:read`, `dns:manage`, `firewall:write`). During installation, the Web UI / CLI prompts the administrator to explicitly grant consent.
2. **mTLS Certificate Provisioning**: Upon approval, the Certificate Manager issues a unique client TLS certificate to the plugin container. The certificate embeds the granted scopes into custom X.509 extensions.
3. **REST Authentication**: The plugin uses its client certificate to authenticate with `roostos-engine` and exchange it for a scoped JWT bearer token.
4. **MQTT Topic ACLs**: When publishing or subscribing to the central MQTT broker, the broker enforces topic access rules directly against the client certificate's embedded X.509 scopes.

---

## 3. Containerized Plugin & Sidecar Architecture

Plugins run as **Docker / Podman containers** managed by `roostos-engine`.

### A. Sidecar Pattern
For standard software (like Technitium DNS or AdGuard Home) running existing web containers:

```
                               ┌─── Docker Network Namespace ──────────┐
                               │                                       │
  ┌─────────────────┐          │   ┌───────────────┐                   │
  │  roostos-core   │◄─D-Bus──►│   │ D-Bus Bridge  │                   │
  │     Daemon      │          │   │   (Sidecar)   │                   │
  └────────┬────────┘          │   └───────┬───────┘                   │
           │ MQTT              │           │ Localhost REST API        │
           ▼                   │           ▼                           │
  ┌─────────────────┐          │   ┌───────────────┐                   │
  │ roostos-engine  │          │   │  DNS Engine   │                   │
  │   (Central)     │          │   │ (Technitium)  │                   │
  └─────────────────┘          │   └───────────────┘                   │
                               │                                       │
                               └───────────────────────────────────────┘
```

1. **Main Service Container**: Runs official off-the-shelf software (e.g. `technitium/dns-server:latest`).
2. **Sidecar Bridge Container**: Runs helper code implementing RoostOS interfaces (e.g. `org.roostos.DNSResolver`), sharing the main container's network namespace (`network_mode: "service:dns-server"`).
3. **Isolation**: Namespace sharing allows sidecars to communicate via `localhost` (e.g., `http://127.0.0.1:5380/api`) without exposing internal ports to the LAN.

---

## 4. Web UI Extensions & REST Proxying

### A. UI Module Extraction
Plugins can extend `roostos-web` with custom Web Component / ES Module tabs:
1. **Packaging**: The plugin container image includes UI static assets (JS/CSS/Web Components) in `/var/www/ui/`.
2. **Extraction**: During installation/startup, `roostos-engine` copies these static assets into `roostos-web` static assets at `/usr/share/roostos/web/plugins/<plugin_id>/`.
3. **Dynamic Loading**: `roostos-web` dynamically imports `<plugin_id>/ui.js` at runtime and registers new navigation views.

### B. REST API Proxying
`roostos-engine` automatically proxies incoming REST API requests from `roostos-web` or external clients:
- Endpoint: `GET/POST/PUT/DELETE /api/v1/plugins/{plugin_id}/{path:path}`
- Routing: Proxies request directly to the container's designated REST port, injecting the plugin's authenticated mTLS/JWT headers.

---

## 5. Plugin Manifest Specification (`manifest.json`)

```json
{
  "id": "local-dns-resolver",
  "name": "Technitium DNS Resolver",
  "version": "1.0.2",
  "type": "core_service",
  "description": "Standard DNS resolution and blocklists powered by Technitium.",
  "author": "RoostOS Core Team",
  "update_url": "https://plugins.roostos.org/api/v1/plugins/local-dns-resolver",
  
  "requested_scopes": [
    "dns:manage",
    "network:read"
  ],

  "web_ui": {
    "container": "dbus-bridge",
    "src_dir": "/var/www/ui",
    "entrypoint": "ui.js"
  },

  "known_services": [
    "dns"
  ],

  "services": {
    "dns-server": {
      "image": "technitium/dns-server:latest",
      "ports": [
        "${dns_port:-53}:53/udp",
        "${dns_port:-53}:53/tcp",
        "${web_console_port:-5380}:5380/tcp"
      ],
      "volumes": [
        "/var/lib/roostos/plugins/dns/config:/etc/dns"
      ]
    },
    "dbus-bridge": {
      "image": "roostos/technitium-dbus-bridge:latest",
      "network_mode": "service:dns-server",
      "volumes": [
        "/var/run/dbus/system_bus_socket:/var/run/dbus/system_bus_socket"
      ],
      "environment": {
        "DBUS_SYSTEM_BUS_ADDRESS": "unix:path=/var/run/dbus/system_bus_socket",
        "TECHNITIUM_API_URL": "http://127.0.0.1:5380/api"
      }
    }
  }
}
```

---

## 6. Multi-Architecture Distribution & Custom Registries

- **OCI Image Pulls**: Plugin images are distributed via standard OCI registries (Docker Hub, GitHub Container Registry `ghcr.io`, or custom private registries configured in `system.yaml`).
- **Multi-Arch Support**: Plugin images must be built as multi-architecture manifests (`amd64` and `arm64`). The host container engine automatically pulls the architecture matching the host's hardware architecture.

---

## 7. Python SDK (`roostos-sdk`)

Plugins written in Python can import `roostos-sdk` to interact with D-Bus and MQTT:

```python
from roostos_sdk import DNSResolverServer

# Implement local D-Bus bridge for Technitium
server = DNSResolverServer()

@server.method()
async def set_client_dns_profile(mac: str, profile_name: str) -> bool:
    # Query Technitium REST API on localhost
    return True

server.run()
```
