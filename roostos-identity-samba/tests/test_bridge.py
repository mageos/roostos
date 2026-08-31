"""Unit tests for SambaIdentityBridge."""

import json
import pytest
from roostos_identity_samba.bridge import SambaIdentityBridge


@pytest.mark.asyncio
async def test_identity_bridge_operations(tmp_path):
    """Verifies bridge user operations and status payload generation."""
    state_file = str(tmp_path / "bridge_users.json")
    bridge = SambaIdentityBridge()
    bridge.state_file = state_file

    # Status
    status_str = await bridge.get_status()
    status_data = json.loads(status_str)
    assert status_data["provider"] == "samba_ad"
    assert status_data["status"] == "running"

    # Initial users list (includes Administrator)
    users_str = await bridge.list_users()
    users = json.loads(users_str)
    assert any(u["username"] == "Administrator" for u in users)

    # Create user
    created = await bridge.create_user("bob", "Pass123!", "parent", "alice_profile")
    assert created is True

    # User in list
    users_str = await bridge.list_users()
    users = json.loads(users_str)
    assert any(u["username"] == "bob" for u in users)

    # Password reset
    reset = await bridge.reset_password("bob", "NewPass456!")
    assert reset is True

    # Delete user
    deleted = await bridge.delete_user("bob")
    assert deleted is True

    # Cannot delete Administrator
    assert await bridge.delete_user("Administrator") is False
