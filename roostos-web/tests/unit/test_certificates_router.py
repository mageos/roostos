import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from roostos_engine.cert_manager import CertificateManager
from roostos_engine.acme_service import HTTP_CHALLENGES
from roostos_web.main import app
from roostos_web.di import get_injector, set_injector, create_web_injector
from roostos_web.auth import create_access_token

@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
def mock_cert_manager(tmp_path):
    cert_dir = str(tmp_path / "certs")
    cm = CertificateManager(cert_dir=cert_dir)
    injector = create_web_injector(cert_dir=cert_dir)
    injector.binder.bind(CertificateManager, to=cm)
    set_injector(injector)
    yield cm

def test_get_certificates_status(auth_headers):
    client = TestClient(app)
    response = client.get("/api/v1/system/certificates", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "root_ca" in data
    assert data["root_ca"]["valid"] is True
    assert "domains" in data

def test_download_root_ca(auth_headers):
    client = TestClient(app)
    response = client.get("/api/v1/system/certificates/ca.crt", headers=auth_headers)
    assert response.status_code == 200
    assert "BEGIN CERTIFICATE" in response.text
    assert "roostos-root-ca.crt" in response.headers.get("Content-Disposition", "")

def test_renew_server_certificate(auth_headers):
    client = TestClient(app)
    response = client.post("/api/v1/system/certificates/renew", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

def test_acme_settings_lifecycle(auth_headers):
    client = TestClient(app)
    # 1. Fetch default settings
    res = client.get("/api/v1/system/certificates/acme/settings", headers=auth_headers)
    assert res.status_code == 200
    
    # 2. Update settings
    payload = {
        "email": "admin@myhome.lan",
        "staging": True,
        "default_challenge": "dns-01",
        "dns_providers": {
            "cloudflare": {"api_token": "cf-secret-token"}
        }
    }
    update_res = client.put("/api/v1/system/certificates/acme/settings", json=payload, headers=auth_headers)
    assert update_res.status_code == 200
    assert update_res.json()["status"] == "success"

    # 3. Verify updated
    res2 = client.get("/api/v1/system/certificates/acme/settings", headers=auth_headers)
    assert res2.json()["email"] == "admin@myhome.lan"
    assert res2.json()["staging"] is True

def test_domain_certificate_order_renew_delete(auth_headers):
    client = TestClient(app)
    mock_prov = MagicMock()

    with patch("roostos_engine.acme_service.get_dns_provider", return_value=mock_prov):
        # 1. Order domain certificate
        order_payload = {
            "domain": "home.example.com",
            "sans": ["*.home.example.com"],
            "challenge_type": "dns-01",
            "dns_provider": "cloudflare",
            "dns_credentials": {"api_token": "secret"},
            "auto_renew": True
        }
        order_res = client.post("/api/v1/system/certificates/domains", json=order_payload, headers=auth_headers)
        assert order_res.status_code == 200
        cert_data = order_res.json()
        assert cert_data["domain"] == "home.example.com"
        assert cert_data["status"] == "valid"

        # 2. List domain certificates
        list_res = client.get("/api/v1/system/certificates/domains", headers=auth_headers)
        assert list_res.status_code == 200
        assert len(list_res.json()) == 1

        # 3. Renew domain certificate
        renew_res = client.post("/api/v1/system/certificates/domains/home.example.com/renew", headers=auth_headers)
        assert renew_res.status_code == 200
        assert renew_res.json()["status"] == "success"

        # 4. Delete domain certificate
        del_res = client.delete("/api/v1/system/certificates/domains/home.example.com", headers=auth_headers)
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "success"

        # 5. List is now empty
        assert len(client.get("/api/v1/system/certificates/domains", headers=auth_headers).json()) == 0

def test_public_acme_http_challenge_responder():
    client = TestClient(app)
    HTTP_CHALLENGES["challenge-token-xyz"] = "challenge-token-xyz.account-thumbprint-123"

    try:
        # Public call without auth headers
        res = client.get("/.well-known/acme-challenge/challenge-token-xyz")
        assert res.status_code == 200
        assert res.text == "challenge-token-xyz.account-thumbprint-123"

        # Nonexistent token returns 404
        not_found = client.get("/.well-known/acme-challenge/nonexistent")
        assert not_found.status_code == 404
    finally:
        HTTP_CHALLENGES.pop("challenge-token-xyz", None)

def test_issue_and_verify_certificates(auth_headers):
    client = TestClient(app)
    
    # 1. Issue service cert
    issue_payload = {
        "entity_type": "service",
        "entity_id": "timeguardd",
        "scopes": ["timeguard:sync", "devices:read"]
    }
    issue_res = client.post("/api/v1/system/certificates/issue", json=issue_payload, headers=auth_headers)
    assert issue_res.status_code == 200
    cert_data = issue_res.json()
    assert "cert_pem" in cert_data

    # 2. Verify issued cert
    verify_payload = {"cert_pem": cert_data["cert_pem"]}
    verify_res = client.post("/api/v1/system/certificates/verify", json=verify_payload, headers=auth_headers)
    assert verify_res.status_code == 200
    verification = verify_res.json()
    assert verification["valid"] is True
    assert verification["subject_cn"] == "service-timeguardd"
    assert "timeguard:sync" in verification["scopes"]
    assert "devices:read" in verification["scopes"]
