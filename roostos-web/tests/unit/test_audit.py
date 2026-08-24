"""Unit tests for structured audit logging in RoostOS Web."""

import logging
from unittest.mock import MagicMock
from fastapi import Request
from roostos_web.audit import (
    extract_client_ip,
    log_auth_success,
    log_auth_failure,
    log_cert_auth,
    log_config_change,
    log_system_action,
    audit_logger
)


def create_mock_request(client_host="192.168.1.100", headers=None):
    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = client_host
    request.headers = headers or {}
    return request


def test_extract_client_ip():
    # Direct client IP
    req_direct = create_mock_request(client_host="10.0.0.5")
    assert extract_client_ip(req_direct) == "10.0.0.5"

    # Forwarded for header (e.g. reverse proxy)
    req_forwarded = create_mock_request(
        client_host="127.0.0.1",
        headers={"x-forwarded-for": "203.0.113.195, 10.0.0.1"}
    )
    assert extract_client_ip(req_forwarded) == "203.0.113.195"

    # Real IP header
    req_real = create_mock_request(
        client_host="127.0.0.1",
        headers={"x-real-ip": "198.51.100.42"}
    )
    assert extract_client_ip(req_real) == "198.51.100.42"

    # None request
    assert extract_client_ip(None) == "internal"


def test_log_auth_success(caplog):
    caplog.set_level(logging.INFO, logger="roostos.audit")
    req = create_mock_request(client_host="192.168.1.50")

    log_auth_success(username="admin", authority="local", role="admin", request=req, method="password")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    assert '[AUDIT:AUTH_SUCCESS] user="admin" authority="local" role="admin" method="password" ip="192.168.1.50"' in record.message


def test_log_auth_failure(caplog):
    caplog.set_level(logging.WARNING, logger="roostos.audit")
    req = create_mock_request(client_host="192.168.1.88")

    log_auth_failure(username="hacker", authority="central", reason="invalid_credentials", request=req, method="oauth_authorize")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.WARNING
    assert '[AUDIT:AUTH_FAILED] user="hacker" authority="central" reason="invalid_credentials" method="oauth_authorize" ip="192.168.1.88"' in record.message


def test_log_cert_auth(caplog):
    caplog.set_level(logging.INFO, logger="roostos.audit")
    req = create_mock_request(client_host="127.0.0.1")

    log_cert_auth(service_id="timeguardd", subject_cn="service-timeguardd", scopes=["timeguard:sync", "devices:read"], request=req)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    assert '[AUDIT:AUTH_CERT] service="timeguardd" subject="service-timeguardd" scopes="timeguard:sync,devices:read" ip="127.0.0.1"' in record.message


def test_log_config_change(caplog):
    caplog.set_level(logging.INFO, logger="roostos.audit")
    req = create_mock_request(client_host="192.168.1.50")

    log_config_change(username="admin", section="firewall", action="add_rule", request=req, details="port=8080")

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    assert '[AUDIT:CONFIG_CHANGE] user="admin" section="firewall" action="add_rule" ip="192.168.1.50" details="port=8080"' in record.message


def test_log_system_action(caplog):
    caplog.set_level(logging.INFO, logger="roostos.audit")
    req = create_mock_request(client_host="192.168.1.50")

    log_system_action(username="admin", action="reboot_router", request=req)

    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.levelno == logging.INFO
    assert '[AUDIT:SYSTEM_ACTION] user="admin" action="reboot_router" ip="192.168.1.50"' in record.message
