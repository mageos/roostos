import os
import pytest
from roostos_engine.cert_manager import CertificateManager

def test_root_ca_generation(tmp_path):
    cert_dir = str(tmp_path / "certs")
    manager = CertificateManager(cert_dir=cert_dir)
    
    ca_cert, ca_key = manager.ensure_root_ca()
    assert ca_cert is not None
    assert ca_key is not None
    assert os.path.exists(os.path.join(cert_dir, "ca.crt"))
    assert os.path.exists(os.path.join(cert_dir, "ca.key"))

    # Re-loading existing Root CA
    ca_cert_2, _ = manager.ensure_root_ca()
    assert ca_cert_2.serial_number == ca_cert.serial_number

def test_plugin_mtls_cert_issuance(tmp_path):
    cert_dir = str(tmp_path / "certs")
    manager = CertificateManager(cert_dir=cert_dir)

    plugin_id = "test-dns-filter"
    requested_scopes = ["admin", "network:read"]

    res = manager.issue_plugin_cert(plugin_id, requested_scopes)
    assert "cert_pem" in res
    assert "key_pem" in res
    assert "ca_pem" in res

    verification = manager.verify_client_cert(res["cert_pem"])
    assert verification["valid"] is True
    assert verification["subject_cn"] == f"plugin-{plugin_id}"
    assert "admin" in verification["scopes"]
    assert "network:read" in verification["scopes"]

def test_server_cert_issuance_and_status(tmp_path):
    cert_dir = str(tmp_path / "certs")
    manager = CertificateManager(cert_dir=cert_dir)

    server_res = manager.issue_server_cert(hostname="roost-router", domain="lan")
    assert "cert_pem" in server_res
    assert "key_pem" in server_res

    status = manager.get_cert_status()
    assert status["root_ca"]["valid"] is True
    assert status["server_cert"] is not None
    assert status["server_cert"]["cn"] == "roost-router.lan"

def test_service_cert_issuance_and_verification(tmp_path):
    cert_dir = str(tmp_path / "certs")
    manager = CertificateManager(cert_dir=cert_dir)

    service_name = "timeguardd"
    requested_scopes = ["timeguard:sync", "devices:read"]

    res = manager.issue_service_cert(service_name, requested_scopes)
    assert "cert_pem" in res
    assert "key_pem" in res

    verification = manager.verify_client_cert(res["cert_pem"])
    assert verification["valid"] is True
    assert verification["subject_cn"] == f"service-{service_name}"
    assert "timeguard:sync" in verification["scopes"]
    assert "devices:read" in verification["scopes"]

    status = manager.get_cert_status()
    assert len(status["services"]) == 1
    assert status["services"][0]["service_id"] == "timeguardd"
    assert status["services"][0]["subject_cn"] == "service-timeguardd"

def test_untrusted_cert_verification_fails(tmp_path):
    # Manager A (Root CA A)
    dir_a = str(tmp_path / "certs_a")
    mgr_a = CertificateManager(cert_dir=dir_a)
    cert_a = mgr_a.issue_service_cert("service-a", ["admin"])

    # Manager B (Root CA B)
    dir_b = str(tmp_path / "certs_b")
    mgr_b = CertificateManager(cert_dir=dir_b)

    # Verifying cert issued by A against B must fail
    res = mgr_b.verify_client_cert(cert_a["cert_pem"])
    assert res["valid"] is False
    assert "error" in res

