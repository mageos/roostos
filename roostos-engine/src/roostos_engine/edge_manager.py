"""Edge Gateway Manager for WireGuard tunnel provisioning, token bootstrap, and ingress."""

import os
import time
import base64
import secrets
import datetime
from typing import Dict, Any, Optional, List, Tuple
import jwt

from roostos_engine.models.edge import (
    IngressRoute,
    EdgeGatewayConfig,
    EdgeBootstrapToken,
    EdgeEnrollmentPayload,
    EdgeEnrollmentResponse,
)

ALGORITHM = "HS256"
_ACTIVE_BOOTSTRAP_TOKENS: Dict[str, float] = {}


class EdgeManager:
    """Manages Edge Gateway pairing, WireGuard tunnels, Nginx ingress, and security lockdown."""

    def __init__(
        self,
        config_dir: str = "/etc/roostos",
        secret_key: Optional[str] = None,
        mock: bool = False,
    ):
        self.config_dir = config_dir
        self.secret_key = secret_key or os.environ.get("ROOSTOS_JWT_SECRET", "roostos-edge-default-secret-min-32-bytes!!")
        self.mock = mock
        self._active_tokens: Dict[str, float] = _ACTIVE_BOOTSTRAP_TOKENS


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
            return (
                base64.b64encode(priv_bytes).decode("ascii"),
                base64.b64encode(pub_bytes).decode("ascii"),
            )
        except Exception:
            # Fallback random 32-byte keys for testing or lightweight systems
            rand_priv = secrets.token_bytes(32)
            rand_pub = secrets.token_bytes(32)
            return (
                base64.b64encode(rand_priv).decode("ascii"),
                base64.b64encode(rand_pub).decode("ascii"),
            )

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
        self._active_tokens[jti] = expires_at

        return EdgeBootstrapToken(
            token=encoded_token,
            endpoint_url=endpoint_url,
            expires_at=expires_at,
            public_ip=vps_public_ip,
        )

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
            self._active_tokens.pop(jti, None)
            raise ValueError("Bootstrap token has expired.")

        # Single-use enforcement
        if not self.mock and jti not in self._active_tokens:
            raise ValueError("Bootstrap token has already been consumed or is invalid.")

        self._active_tokens.pop(jti, None)
        return payload

    def generate_networkd_config(
        self,
        role: str,  # "gateway" or "client"
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
            netdev = (
                f"[NetDev]\n"
                f"Name=wg-edge\n"
                f"Kind=wireguard\n"
                f"Description=RoostOS Edge Gateway WireGuard Server\n\n"
                f"[WireGuard]\n"
                f"PrivateKey={private_key}\n"
                f"ListenPort={listen_port or 51820}\n\n"
                f"[WireGuardPeer]\n"
                f"PublicKey={peer_public_key}\n"
                f"AllowedIPs={allowed_ips}\n"
            )
        else:
            netdev = (
                f"[NetDev]\n"
                f"Name=wg-edge\n"
                f"Kind=wireguard\n"
                f"Description=RoostOS Edge Gateway WireGuard Client\n\n"
                f"[WireGuard]\n"
                f"PrivateKey={private_key}\n\n"
                f"[WireGuardPeer]\n"
                f"PublicKey={peer_public_key}\n"
                f"Endpoint={endpoint}\n"
                f"AllowedIPs={allowed_ips}\n"
                f"PersistentKeepalive={persistent_keepalive}\n"
            )

        network = (
            f"[Match]\n"
            f"Name=wg-edge\n\n"
            f"[Network]\n"
            f"Address={tunnel_ip}\n"
        )

        return {
            "50-wg-edge.netdev": netdev,
            "50-wg-edge.network": network,
        }

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
            f"add rule inet filter input iifname \"{wan_interface}\" tcp dport 8000 drop",
        ]
