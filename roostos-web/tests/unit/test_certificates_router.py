import pytest
from fastapi.testclient import TestClient
from roostos_engine.cert_manager import CertificateManager
from roostos_web.main import app
from roostos_web.routers.certificates import get_cert_manager
from roostos_web.auth import create_access_token

@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True)
def mock_cert_manager(tmp_path):
    cert_dir = str(tmp_path / "certs")
    cm = CertificateManager(cert_dir=cert_dir)
    app.dependency_overrides[get_cert_manager] = lambda: cm
    yield cm
    app.dependency_overrides.pop(get_cert_manager, None)

def test_get_certificates_status(auth_headers):
    client = TestClient(app)
    response = client.get("/api/v1/system/certificates", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "root_ca" in data
    assert data["root_ca"]["valid"] is True

def test_renew_server_certificate(auth_headers):
    client = TestClient(app)
    response = client.post("/api/v1/system/certificates/renew", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

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

