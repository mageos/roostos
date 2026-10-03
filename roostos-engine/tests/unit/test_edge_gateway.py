import time
import pytest
from roostos_engine.edge_manager import EdgeManager
from roostos_engine.models.edge import IngressRoute, EdgeGatewayConfig


def test_edge_manager_wireguard_keypair():
    """Verifies WireGuard keypair generation returns valid base64 strings."""
    mgr = EdgeManager(mock=True)
    priv, pub = mgr.generate_wireguard_keypair()
    assert isinstance(priv, str) and len(priv) > 20
    assert isinstance(pub, str) and len(pub) > 20
    assert priv != pub


def test_edge_manager_bootstrap_token_lifecycle():
    """Verifies bootstrap token creation, validation, and single-use consumption."""
    mgr = EdgeManager(secret_key="test-secret-key-12345-secure-32bytes-min!", mock=False)
    bootstrap = mgr.create_bootstrap_token(vps_public_ip="198.51.100.10", listen_port=8000, ttl_minutes=5)

    assert bootstrap.public_ip == "198.51.100.10"
    assert bootstrap.endpoint_url == "http://198.51.100.10:8000"
    assert bootstrap.expires_at > time.time()

    # 1. First validation succeeds and consumes the token
    claims = mgr.validate_and_consume_token(bootstrap.token)
    assert claims["vps_ip"] == "198.51.100.10"
    assert claims["sub"] == "edge_enrollment"

    # 2. Second validation must fail (single-use burned)
    with pytest.raises(ValueError, match="already been consumed"):
        mgr.validate_and_consume_token(bootstrap.token)


def test_edge_manager_networkd_config_generation():
    """Verifies systemd-networkd netdev and network files for both gateway and client."""
    mgr = EdgeManager(mock=True)

    # Server / Gateway config
    gw_files = mgr.generate_networkd_config(
        role="gateway",
        private_key="priv_key_server",
        peer_public_key="pub_key_home",
        listen_port=51820,
        tunnel_ip="10.42.0.1/24",
        allowed_ips="10.42.0.2/32",
    )
    assert "50-wg-edge.netdev" in gw_files
    assert "50-wg-edge.network" in gw_files
    assert "ListenPort=51820" in gw_files["50-wg-edge.netdev"]
    assert "PublicKey=pub_key_home" in gw_files["50-wg-edge.netdev"]
    assert "Address=10.42.0.1/24" in gw_files["50-wg-edge.network"]

    # Client / Home config
    cli_files = mgr.generate_networkd_config(
        role="client",
        private_key="priv_key_client",
        peer_public_key="pub_key_vps",
        endpoint="198.51.100.10:51820",
        tunnel_ip="10.42.0.2/24",
        allowed_ips="10.42.0.0/24",
        persistent_keepalive=25,
    )
    assert "Endpoint=198.51.100.10:51820" in cli_files["50-wg-edge.netdev"]
    assert "PersistentKeepalive=25" in cli_files["50-wg-edge.netdev"]
    assert "Address=10.42.0.2/24" in cli_files["50-wg-edge.network"]


def test_edge_manager_nginx_ingress_generation():
    """Verifies generation of Nginx reverse proxy server blocks."""
    mgr = EdgeManager(mock=True)

    routes = [
        IngressRoute(
            id="r1",
            domain="ha.example.com",
            target_ip="192.168.1.10",
            target_port=8123,
            ssl_enabled=True,
        ),
        IngressRoute(
            id="r2",
            domain="files.example.com",
            target_ip="10.42.0.2",
            target_port=8080,
            ssl_enabled=False,
        ),
    ]

    conf = mgr.generate_nginx_config(routes)
    assert "server_name ha.example.com;" in conf
    assert "proxy_pass http://192.168.1.10:8123;" in conf
    assert "ssl_certificate" in conf

    assert "server_name files.example.com;" in conf
    assert "proxy_pass http://10.42.0.2:8080;" in conf


def test_edge_manager_lockdown_rules():
    """Verifies firewall rules for port 8000 WAN attack surface reduction."""
    mgr = EdgeManager(mock=True)
    rules = mgr.compile_lockdown_rules("eth0")
    assert any("tcp dport 8000 drop" in r for r in rules)
