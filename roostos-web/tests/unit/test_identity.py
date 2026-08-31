"""Unit tests for Central Identity Router and LDAP AuthProvider."""

import json
import pytest
from fastapi.testclient import TestClient
from roostos_web.main import app
from roostos_web.interfaces.auth import (
    LDAPAuthProvider,
    MultiAuthorityAuthProvider,
    MockAuthProvider,
)
from roostos_engine.models import RoostConfig


def test_ldap_auth_provider(tmp_path):
    """Verifies LDAPAuthProvider authentication against domain store and fallback Administrator."""
    state_file = str(tmp_path / "ldap_users.json")
    with open(state_file, "w") as f:
        json.dump({
            "users": [
                {
                    "username": "john",
                    "password": "DomainPassword123!",
                    "role": "parent",
                    "person": "person_john",
                    "enabled": True
                },
                {
                    "username": "disabled_user",
                    "password": "pass",
                    "role": "member",
                    "enabled": False
                }
            ]
        }, f)

    provider = LDAPAuthProvider(state_file=state_file)

    # Valid authentication
    assert provider.authenticate("john", "DomainPassword123!") is True
    # Invalid password
    assert provider.authenticate("john", "wrongpassword") is False
    # Disabled account
    assert provider.authenticate("disabled_user", "pass") is False
    # Administrator fallback
    assert provider.authenticate("Administrator", "RoostOS!Admin2026") is True


def test_multi_authority_auth_provider(tmp_path):
    """Verifies MultiAuthorityAuthProvider properly routes local vs domain prefix notation."""
    local_p = MockAuthProvider(mock_users={"localadmin": "localpass"})
    central_p = MockAuthProvider(central_mock_users={"centraluser": "centralpass"})

    multi_p = MultiAuthorityAuthProvider(
        local_provider=local_p,
        central_provider=central_p,
        default_authority="local"
    )

    # 1. Local user
    assert multi_p.authenticate(".\\localadmin", "localpass") is True
    assert multi_p.authenticate("local\\localadmin", "localpass") is True
    assert multi_p.authenticate("localadmin@local", "localpass") is True

    # 2. Central / Domain user
    assert multi_p.authenticate("ROOSTOS\\centraluser", "centralpass") is True
    assert multi_p.authenticate("centraluser", "centralpass", authority="central") is True


def test_identity_router_endpoints(tmp_path):
    """Verifies identity REST API endpoints."""
    client = TestClient(app)

    # 1. Status
    res = client.get("/api/v1/identity/status")
    assert res.status_code == 200
    status_data = res.json()
    assert "realm" in status_data
    assert "status" in status_data

    # 2. List users
    res = client.get("/api/v1/identity/users")
    assert res.status_code == 200
    users = res.json()
    assert isinstance(users, list)

    # 3. Create user
    new_user_payload = {
        "username": "testuser1",
        "password": "UserPass123!",
        "first_name": "Test",
        "last_name": "User",
        "role": "member"
    }
    res = client.post("/api/v1/identity/users", json=new_user_payload)
    assert res.status_code == 201
    created = res.json()
    assert created["username"] == "testuser1"

    # 4. Update user
    res = client.put("/api/v1/identity/users/testuser1", json={"role": "parent"})
    assert res.status_code == 200
    assert res.json()["role"] == "parent"

    # 5. Reset password
    res = client.post("/api/v1/identity/users/testuser1/password", json={"new_password": "NewSecretPass!"})
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    # 6. Delete user
    res = client.delete("/api/v1/identity/users/testuser1")
    assert res.status_code == 200
    assert res.json()["deleted"] == "testuser1"

    # 7. Enrollment info
    res = client.get("/api/v1/identity/enrollment-info")
    assert res.status_code == 200
    assert "enrollment_command" in res.json()

    # 8. Join script
    res = client.get("/api/v1/identity/join.sh")
    assert res.status_code == 200
    assert "#!/usr/bin/env bash" in res.text
    assert "realm join" in res.text
