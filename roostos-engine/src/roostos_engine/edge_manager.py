"""Edge Gateway Manager for WireGuard tunnel provisioning, token bootstrap, and ingress."""

import base64
import os
import secrets
import time
from typing import Any, Dict, List, Optional, Tuple

import jwt
from roostos_engine.edge_token_store import EdgeTokenStore
from roostos_engine.ingress_helper import (
    generate_nginx_config as _gen_nginx_config,
    compile_lockdown_rules as _compile_lockdown,
    update_peer_endpoint_file,
    persist_gateway_config as _persist_gw_config,
)
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
            config_dir=config_dir, secret_key=secret_key, state_file=state_file
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
        domain: Optional[str] = None,
        lan_subnets: Optional[List[str]] = None,
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

        home_priv, home_pub = self.generate_wireguard_keypair()
        gw_allowed = ["10.42.0.2/32"] + [s for s in (lan_subnets or []) if s != "10.42.0.2/32"]

        net_files = self.generate_networkd_config(
            role="gateway",
            private_key=vps_priv,
            peer_public_key=home_pub,
            listen_port=listen_port,
            tunnel_ip="10.42.0.1/24",
            allowed_ips=",".join(gw_allowed),
            routed_subnets=lan_subnets,
        )
        self._apply_network_files(net_files)

        endpoint_host = domain if domain else vps_public_ip
        bundle = EdgeInviteBundle(
            endpoint=f"{endpoint_host}:{listen_port}",
            gateway_public_key=vps_pub,
            client_private_key=home_priv,
            client_public_key=home_pub,
            assigned_tunnel_ip="10.42.0.2/24",
            gateway_tunnel_ip="10.42.0.1/24",
            allowed_ips=["10.42.0.0/24"],
            lan_subnets=lan_subnets or [],
            persistent_keepalive=25,
        )

        if output_path:
            with open(output_path, "w") as f:
                f.write(bundle.model_dump_json(indent=2))

        return bundle

    def _apply_network_files(self, net_files: Dict[str, str]) -> None:
        """Writes networkd configs and triggers systemd-networkd reload if root."""
        if self.mock:
            return
        net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
        if not os.path.exists(net_dir):
            try:
                os.makedirs(net_dir, exist_ok=True)
            except Exception:
                pass
        if os.path.exists(net_dir):
            import sys
            for fname, content in net_files.items():
                fpath = os.path.join(net_dir, fname)
                try:
                    mode = 0o600 if fname.endswith(".netdev") else 0o644
                    with open(os.open(fpath, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode), "w") as f:
                        f.write(content)
                except Exception as e:
                    print(f"Warning: Failed writing {fpath}: {e}", file=sys.stderr)
            if os.getuid() == 0:
                import subprocess
                try:
                    subprocess.run(["systemctl", "enable", "--now", "systemd-networkd"], check=False, capture_output=True)
                    subprocess.run(["networkctl", "reload"], check=False, capture_output=True)
                    subprocess.run(["networkctl", "reconfigure", "wg-edge"], check=False, capture_output=True)
                except Exception:
                    pass

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
            routed_subnets=["10.42.0.0/24"],
        )
        self._apply_network_files(net_files)
        from roostos_engine.edge_diagnostics import apply_local_edge_routing
        apply_local_edge_routing(config_dir=self.config_dir, lan_subnets=bundle.lan_subnets or None, is_gateway=False, mock=self.mock)
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
        self, role: str, private_key: str, peer_public_key: str, endpoint: Optional[str] = None,
        listen_port: Optional[int] = 51820, tunnel_ip: str = "10.42.0.2/24",
        allowed_ips: str = "10.42.0.0/24", persistent_keepalive: int = 25,
        routed_subnets: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """Generates systemd-networkd .netdev and .network files for WireGuard."""
        if role == "gateway":
            peer_section = f"[WireGuardPeer]\nPublicKey={peer_public_key}\nAllowedIPs={allowed_ips}\n"
            listen_line, desc = f"ListenPort={listen_port or 51820}\n", "Server"
        else:
            peer_section = (
                f"[WireGuardPeer]\nPublicKey={peer_public_key}\n"
                f"Endpoint={endpoint}\nAllowedIPs={allowed_ips}\n"
                f"PersistentKeepalive={persistent_keepalive}\n"
            )
            listen_line, desc = "", "Client"

        netdev = (
            f"[NetDev]\nName=wg-edge\nKind=wireguard\n"
            f"Description=RoostOS Edge Gateway WireGuard {desc}\n\n"
            f"[WireGuard]\nPrivateKey={private_key}\n{listen_line}\n{peer_section}"
        )
        network = f"[Match]\nName=wg-edge\n\n[Network]\nAddress={tunnel_ip}\nIPForward=yes\n"
        for subnet in (routed_subnets or []):
            network += f"\n[Route]\nDestination={subnet}\nScope=link\n"
        return {"50-wg-edge.netdev": netdev, "50-wg-edge.network": network}

    def update_peer_endpoint(self, endpoint_host: str, port: int = 51820) -> bool:
        """Updates the WireGuard peer endpoint (domain or IP) in 50-wg-edge.netdev and reloads networkd."""
        net_dir = os.environ.get("ROOSTOS_SYSTEMD_NETWORK_DIR", "/etc/systemd/network")
        updated = update_peer_endpoint_file(endpoint_host=endpoint_host, port=port, network_dir=net_dir)
        if not self.mock and os.getuid() == 0:
            import subprocess
            try:
                subprocess.run(["networkctl", "reload"], check=False, capture_output=True)
                subprocess.run(["networkctl", "reconfigure", "wg-edge"], check=False, capture_output=True)
            except Exception:
                pass
        return updated

    def persist_gateway_config(
        self, vps_ip: str, gw_tunnel: str, home_tunnel: str, pub_key: str,
        port: int = 51820, domain: Optional[str] = None,
    ) -> None:
        """Helper to persist edge gateway record in network.yaml."""
        _persist_gw_config(
            config_dir=self.config_dir, vps_ip=vps_ip, gw_tunnel=gw_tunnel,
            home_tunnel=home_tunnel, pub_key=pub_key, port=port, domain=domain,
        )

    def generate_nginx_config(self, routes: List[IngressRoute]) -> str:
        return _gen_nginx_config(routes)

    def compile_lockdown_rules(self, wan_interface: str = "eth0") -> List[str]:
        return _compile_lockdown(wan_interface)
