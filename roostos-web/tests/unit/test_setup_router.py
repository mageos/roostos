"""Unit tests for the roostos-web setup router."""

import pytest
from fastapi.testclient import TestClient

from roostos_web.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_get_setup_status(client, tmp_path):
    response = client.get(f"/api/setup/status?config_dir={tmp_path}")
    assert response.status_code == 200
    data = response.json()
    assert "is_configured" in data
    assert "environment" in data
    assert data["is_configured"] is False


def test_discover_services(client):
    response = client.post("/api/setup/discover")
    assert response.status_code == 200
    data = response.json()
    assert "services" in data
    assert "gateways" in data
    assert "controllers" in data


def test_apply_setup_gateway(client, tmp_path):
    payload = {
        "role": "gateway",
        "gateway_params": {
            "wan_interface": "eth0",
            "lan_interfaces": ["eth1"],
            "lan_network": "192.168.2.0/24",
            "lan_ip": "192.168.2.1",
            "dhcp_enabled": True,
            "dhcp_start": "192.168.2.100",
            "dhcp_end": "192.168.2.200",
            "dns_servers": ["1.1.1.1"]
        }
    }
    response = client.post(f"/api/setup/apply?config_dir={tmp_path}", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["role"] == "gateway"
    assert (tmp_path / "network.yaml").exists()


def test_enrollment_script(client):
    response = client.get("/api/setup/enroll-script?token=test-token-123")
    assert response.status_code == 200
    data = response.json()
    assert "--token=test-token-123" in data["command"]


def test_get_enroll_sh(client):
    response = client.get("/api/setup/enroll.sh")
    assert response.status_code == 200
    assert "#!/usr/bin/env bash" in response.text
