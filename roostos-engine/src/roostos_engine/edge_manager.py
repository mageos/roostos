"""Edge Gateway Manager for WireGuard tunnel provisioning, token bootstrap, and ingress."""

import base64
import os
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

import jwt
from roostos_engine.edge_token_store import EdgeTokenStore
from roostos_engine.models.edge import (
    EdgeBootstrapToken,
    EdgeGatewayConfig,
    EdgeEnrollmentPayload,
    EdgeEnrollmentResponse,
    EdgeInviteBundle,
    IngressRoute,
)

ALGORITHM = "HS256"


class EdgeManager:
    """Manages Edge Gateway pairing, WireGuard tunnels, Nginx ingress, and security lockdown."""

    def __init__(
        self,
        config_dir: str = "/etc/roostos",
        secret_key: Optional[str] = None,
        mock: bool = False,
        state_file: Optional[str] = None,
        token_store: Optional[EdgeTokenStore] = None,
    ):
        self.config_dir = config_dir
        self.mock = mock
        self.token_store = token_store or EdgeTokenStore(
            config_dir=config_dir,
            secret_key=secret_key,
            state_file=state_file,
        )
        self.secret_key = self.token_store.secret_key
        self.state_file = self.token_store.state_file

    @property
    def _active_tokens(self) -> Dict[str, float]:
        """Provides in-memory compatibility for active tokens."""
        return self.token_store.load_tokens()

    def generate_wireguard_keypair(self) -> Tuple[str, str]:
        """Generates a WireGuard Curve25519 private and public keypair."""
        try:
            from cryptography.hazmat.primitives.asymmetric import x25519
            from cryptography.hazmat.primitives import serialization

            priv = x25519.X25519PrivateKey.generate()
            pub = priv.public_key()
            priv_bytes = priv.private_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PrivateFormat.Raw,
                encryption_algorithm=serialization.NoEncryption(),
            )
            pub_bytes = pub.public_bytes(
                encoding=serialization.Encoding.Raw,
                format=serialization.PublicFormat.Raw,
            )
            return (base64.b64encode(priv_bytes).decode("ascii"), base64.b64encode(pub_bytes).decode("ascii"))
        except Exception:
            return (base64.b64encode(secrets.token_bytes(32)).decode("ascii"), base64.b64encode(secrets.token_bytes(32)).decode("ascii"))


    def create_bootstrap_token(
        self,
        vps_public_ip: str,
        listen_port: int = 8000,
        ttl_minutes: int = 15,
        use_https: bool = False,
    ) -> EdgeBootstrapToken:
        """Generates a short-lived single-use bootstrap JWT token for enrollment."""
        jti = secrets.token_hex(16)
        expires_at = int(time.time()) + (ttl_minutes * 60)
        protocol = "https" if use_https else "http"
        endpoint_url = f"{protocol}://{vps_public_ip}:{listen_port}"

        payload = {
            "sub": "edge_enrollment",
            "role": "edge_bootstrap",
            "jti": jti,
            "vps_ip": vps_public_ip,
            "endpoint_url": endpoint_url,
            "exp": expires_at,
        }
        encoded_token = jwt.encode(payload, self.secret_key, algorithm=ALGORITHM)
        self.token_store.record_token(jti, float(expires_at))

        return EdgeBootstrapToken(
            token=encoded_token,
            endpoint_url=endpoint_url,
            expires_at=expires_at,
            public_ip=vps_public_ip,
        )

    def create_wireguard_invite(
        self,
        vps_public_ip: str,
        listen_port: int = 51820,
        output_path: Optional[str] = None,
    ) -> EdgeInviteBundle:
        """Generates a zero-web WireGuard invitation bundle and provisions the server peer."""
        state_dir = self.config_dir
        key_file = os.path.join(state_dir, "edge_server.key")
        if os.path.exists(key_file):
            with open(key_file, "r") as f:
                vps_priv, vps_pub = f.read().strip().split(":")
        else:
            vps_priv, vps_pub = self.generate_wireguard_keypair()
            try:
                os.makedirs(state_dir, exist_ok=True)
                with open(key_file, "w") as f:
                    f.write(f"{vps_priv}:{vps_pub}")
            except Exception:
                pass

        # Generate unique keypair for the client peer
        home_priv, home_pub = self.generate_wireguard_keypair()

        # Provision server networkd config on VPS
        net_files = self.generate_networkd_config(
            role="gateway",
            private_key=vps_priv,
            peer_public_key=home_pub,
            listen_port=listen_port,
            tunnel_ip="10.42.0.1/24",
            allowed_ips="10.42.0.2/32",
        )
        if not self.mock:
            net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
            if os.path.exists(net_dir):
                for fname, content in net_files.items():
                    try:
                        with open(os.path.join(net_dir, fname), "w") as f:
                            f.write(content)
                    except Exception:
                        pass

        bundle = EdgeInviteBundle(
            endpoint=f"{vps_public_ip}:{listen_port}",
            gateway_public_key=vps_pub,
            client_private_key=home_priv,
            client_public_key=home_pub,
            assigned_tunnel_ip="10.42.0.2/24",
            gateway_tunnel_ip="10.42.0.1/24",
            allowed_ips=["10.42.0.0/24"],
            persistent_keepalive=25,
        )

        if output_path:
            with open(output_path, "w") as f:
                f.write(bundle.model_dump_json(indent=2))

        return bundle

    def apply_wireguard_invite(self, bundle: EdgeInviteBundle) -> Dict[str, str]:
        """Applies a WireGuard invitation bundle on the home client router."""
        net_files = self.generate_networkd_config(
            role="client",
            private_key=bundle.client_private_key,
            peer_public_key=bundle.gateway_public_key,
            endpoint=bundle.endpoint,
            tunnel_ip=bundle.assigned_tunnel_ip,
            allowed_ips=",".join(bundle.allowed_ips),
            persistent_keepalive=bundle.persistent_keepalive,
        )

        if not self.mock:
            net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
            if os.path.exists(net_dir):
                for fname, content in net_files.items():
                    try:
                        with open(os.path.join(net_dir, fname), "w") as f:
                            f.write(content)
                    except Exception:
                        pass

        return net_files

    def validate_and_consume_token(self, token_str: str) -> Dict[str, Any]:
        """Validates and single-use consumes a bootstrap enrollment token."""
        try:
            payload = jwt.decode(token_str, self.secret_key, algorithms=[ALGORITHM])
        except Exception as e:
            raise ValueError(f"Invalid or expired bootstrap token: {e}")

        jti = payload.get("jti")
        if not jti:
            raise ValueError("Token missing unique token identifier (jti).")

        exp = payload.get("exp", 0)
        if exp < time.time():
            self.token_store.consume_token(jti)
            raise ValueError("Bootstrap token has expired.")

        active = self.token_store.load_tokens()
        if not self.mock and jti not in active:
            raise ValueError("Bootstrap token has already been consumed or is invalid.")

        self.token_store.consume_token(jti)
        return payload

    def generate_networkd_config(
        self,
        role: str,
        private_key: str,
        peer_public_key: str,
        endpoint: Optional[str] = None,
        listen_port: Optional[int] = 51820,
        tunnel_ip: str = "10.42.0.2/24",
        allowed_ips: str = "10.42.0.0/24",
        persistent_keepalive: int = 25,
    ) -> Dict[str, str]:
        """Generates systemd-networkd .netdev and .network files for WireGuard."""
        if role == "gateway":
            peer_section = f"[WireGuardPeer]\nPublicKey={peer_public_key}\nAllowedIPs={allowed_ips}\n"
            listen_line = f"ListenPort={listen_port or 51820}\n"
            desc = "Server"
        else:
            peer_section = (
                f"[WireGuardPeer]\nPublicKey={peer_public_key}\n"
                f"Endpoint={endpoint}\nAllowedIPs={allowed_ips}\n"
                f"PersistentKeepalive={persistent_keepalive}\n"
            )
            listen_line = ""
            desc = "Client"

        netdev = (
            f"[NetDev]\nName=wg-edge\nKind=wireguard\n"
            f"Description=RoostOS Edge Gateway WireGuard {desc}\n\n"
            f"[WireGuard]\nPrivateKey={private_key}\n{listen_line}\n"
            f"{peer_section}"
        )
        network = f"[Match]\nName=wg-edge\n\n[Network]\nAddress={tunnel_ip}\n"
        return {"50-wg-edge.netdev": netdev, "50-wg-edge.network": network}

    def generate_nginx_config(self, routes: List[IngressRoute]) -> str:
        """Generates Nginx reverse-proxy server blocks for active ingress routes."""
        if not routes:
            return (
                "# RoostOS Edge Ingress Proxy\n"
                "# No active routes configured.\n"
                "server {\n"
                "    listen 80 default_server;\n"
                "    server_name _;\n"
                "    return 404 'RoostOS Edge Gateway: No routes configured\\n';\n"
                "}\n"
            )

        blocks: List[str] = ["# RoostOS Ingress Reverse Proxy Configuration\n"]
        for r in routes:
            ssl_block = ""
            if r.ssl_enabled:
                ssl_block = (
                    f"    # SSL / TLS Termination\n"
                    f"    ssl_certificate /etc/roostos/certs/{r.domain}/fullchain.pem;\n"
                    f"    ssl_certificate_key /etc/roostos/certs/{r.domain}/privkey.pem;\n"
                )

            server_block = (
                f"server {{\n"
                f"    listen 80;\n"
                f"    {'listen 443 ssl http2;' if r.ssl_enabled else ''}\n"
                f"    server_name {r.domain};\n"
                f"{ssl_block}\n"
                f"    location / {{\n"
                f"        proxy_pass http://{r.target_ip}:{r.target_port};\n"
                f"        proxy_set_header Host $host;\n"
                f"        proxy_set_header X-Real-IP $remote_addr;\n"
                f"        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n"
                f"        proxy_set_header X-Forwarded-Proto $scheme;\n"
                f"        proxy_http_version 1.1;\n"
                f"        proxy_set_header Upgrade $http_upgrade;\n"
                f"        proxy_set_header Connection \"upgrade\";\n"
                f"    }}\n"
                f"}}\n"
            )
            blocks.append(server_block)

        return "\n".join(blocks)

    def compile_lockdown_rules(self, wan_interface: str = "eth0") -> List[str]:
        """Generates nftables rules to restrict port 8000 to internal tunnel/localhost."""
        return [
            f"# RoostOS Attack Surface Hardening: Drop public port 8000 on {wan_interface}",
            f'add rule inet filter input iifname "{wan_interface}" tcp dport 8000 drop',
        ]
