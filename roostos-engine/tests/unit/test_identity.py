"""Unit tests for Centralized Identity & Domain Management in roostos-engine."""

import pytest
from roostos_engine.models.identity import (
    DomainUser,
    DomainUserCreate,
    DomainUserUpdate,
    DomainStatus,
)
from roostos_engine.identity_manager import IdentityManager
from roostos_engine.repository import YAMLConfigRepository


def test_domain_user_model_validation():
    """Verifies validation rules on DomainUser."""
    user = DomainUser(username="alice", role="parent", first_name="Alice", last_name="Smith")
    assert user.username == "alice"
    assert user.role == "parent"

    with pytest.raises(ValueError, match="must be 'admin', 'parent', or 'member'"):
        DomainUser(username="bob", role="superadmin")


def test_identity_manager_crud(temp_config_dir, tmp_path):
    """Verifies CRUD operations on domain accounts in IdentityManager."""
    repo = YAMLConfigRepository(config_dir=str(temp_config_dir))
    state_file = str(tmp_path / "domain_users.json")
    mgr = IdentityManager(
        repo=repo,
        realm="ROOSTOS.LOCAL",
        workgroup="ROOSTOS",
        state_file=state_file
    )

    # Check initial status
    status = mgr.get_status()
    assert isinstance(status, DomainStatus)
    assert status.realm == "ROOSTOS.LOCAL"
    assert status.workgroup == "ROOSTOS"
    assert status.user_count >= 1  # Administrator

    # Create new domain user
    new_user = mgr.create_user(DomainUserCreate(
        username="jdoe",
        password="SecretPassword123!",
        first_name="John",
        last_name="Doe",
        role="member",
        person="alice_profile"  # exists in temp_config_dir
    ))
    assert new_user.username == "jdoe"
    assert new_user.first_name == "John"
    assert new_user.person == "alice_profile"

    # Duplicate creation error
    with pytest.raises(ValueError, match="already exists"):
        mgr.create_user(DomainUserCreate(
            username="jdoe",
            password="pass",
            role="member"
        ))

    # Update user
    updated = mgr.update_user("jdoe", DomainUserUpdate(
        last_name="Smith",
        role="parent"
    ))
    assert updated.last_name == "Smith"
    assert updated.role == "parent"

    # Reset password
    assert mgr.reset_password("jdoe", "NewPassword456!") is True

    # Delete user
    assert mgr.delete_user("jdoe") is True
    assert mgr.get_user("jdoe") is None

    # Cannot delete built-in Administrator
    with pytest.raises(ValueError, match="built-in Domain Administrator cannot be deleted"):
        mgr.delete_user("Administrator")


def test_identity_manager_enrollment_and_dns(temp_config_dir, tmp_path):
    """Verifies workstation enrollment info and DNS SRV generation."""
    repo = YAMLConfigRepository(config_dir=str(temp_config_dir))
    state_file = str(tmp_path / "domain_users.json")
    mgr = IdentityManager(
        repo=repo,
        realm="ROOSTOS.LOCAL",
        workgroup="ROOSTOS",
        state_file=state_file
    )

    enroll = mgr.get_enrollment_info(router_ip="192.168.1.1")
    assert enroll.realm == "ROOSTOS.LOCAL"
    assert "192.168.1.1" in enroll.enrollment_command
    assert "Add-Computer" in enroll.powershell_command

    srv_records = mgr.get_dns_srv_records(dc_ip="192.168.1.1")
    assert len(srv_records) >= 4
    record_names = [r["name"] for r in srv_records]
    assert any("_ldap._tcp" in name for name in record_names)
    assert any("_kerberos._tcp" in name for name in record_names)
