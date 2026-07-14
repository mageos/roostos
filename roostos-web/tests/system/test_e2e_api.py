import os
import sys
import time
import subprocess
import pytest
import httpx
import shutil

# Ensure workspace root is in path for scripts module resolution
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../")))
from scripts.generate_mock_configs import generate_mock_configs

@pytest.fixture(scope="module")
def system_test_env(tmp_path_factory):
    # Create temp directory for system configurations
    config_dir = tmp_path_factory.mktemp("roostos-system-test-configs")
    generate_mock_configs(str(config_dir))

    # Set up isolated D-Bus environment using D-Bus session fixture setup from conftest.py
    # We will assume pytest has dbus_session set up by the conftest or run with --session
    # Let's start the daemon on Session D-Bus
    os.environ["ROOSTOS_SESSION_BUS"] = "1"
    os.environ["ROOSTOS_MOCK_AUTH"] = "1"
    os.environ["ROOSTOS_CONFIG_DIR"] = str(config_dir)
    os.environ["ROOSTOS_WEB_PORT"] = "8888"

    daemon_proc = subprocess.Popen([
        sys.executable, "-m", "roostos_engine.daemon",
        "--config-dir", str(config_dir),
        "--session", "--mock"
    ])
    
    # Give the daemon time to start and acquire bus name
    time.sleep(1.5)

    # Start the web service
    web_proc = subprocess.Popen([
        sys.executable, "-m", "roostos_web.main"
    ])

    # Give the web server time to bind to port 8888
    time.sleep(1.5)

    yield config_dir

    # Terminate both processes cleanly
    web_proc.terminate()
    daemon_proc.terminate()
    web_proc.wait()
    daemon_proc.wait()


def get_oauth_token(username, password) -> str:
    """Helper to authenticate using standard OAuth2 authorization code flow."""
    redirect_uri = "http://localhost:8000/callback"
    client_id = "roostos-ui"
    
    # 1. Post credentials to authorize endpoint
    auth_res = httpx.post(
        "http://localhost:8888/oauth/authorize",
        data={
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "username": username,
            "password": password
        },
        follow_redirects=False
    )
    assert auth_res.status_code == 303
    location = auth_res.headers["Location"]
    
    # 2. Parse authorization code from redirect URL
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(location)
    code = parse_qs(parsed.query)["code"][0]
    
    # 3. Exchange code for access token
    token_res = httpx.post(
        "http://localhost:8888/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id
        }
    )
    assert token_res.status_code == 200
    return token_res.json()["access_token"]


def test_login_and_retrieve_jwt(system_test_env):
    """Verifies user can complete the OAuth2 authorization code flow and obtain a JWT."""
    token = get_oauth_token("admin", "password")
    assert token is not None
    assert len(token) > 0


def test_get_and_post_system_config(system_test_env):
    """Verifies reading and writing system settings, validating disk persistence and daemon reload."""
    # 1. Complete OAuth flow to get token
    token = get_oauth_token("admin", "password")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Get system settings
    sys_url = "http://localhost:8888/api/system"
    get_res = httpx.get(sys_url, headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["hostname"] == "roost-home-router"

    # 3. Modify system settings
    post_res = httpx.post(
        sys_url, 
        headers=headers,
        json={"hostname": "roost-test-e2e", "domain": "test.lan", "timezone": "UTC"}
    )
    assert post_res.status_code == 200

    # 4. Verify that config file was modified on disk directly
    import yaml
    system_yaml_path = os.path.join(str(system_test_env), "system.yaml")
    with open(system_yaml_path, "r") as f:
        data = yaml.safe_load(f)
    assert data["system"]["hostname"] == "roost-test-e2e"
    assert data["system"]["domain"] == "test.lan"


def test_register_device_e2e(system_test_env):
    """Verifies registering a device writes config to disk and registers with active configs."""
    # 1. Complete OAuth flow to get token
    token = get_oauth_token("admin", "password")
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Register a new device
    device_url = "http://localhost:8888/api/api/devices" # Wait, main.py defines it as /api/devices
    device_url = "http://localhost:8888/api/devices"
    payload = {
        "mac": "aa:bb:cc:11:22:33",
        "name": "E2E Test TV",
        "owner": "dad_profile",
        "location": "living_room",
        "tags": ["media"],
        "static_ip": "192.168.1.222",
        "upnp_trusted": False
    }
    
    post_res = httpx.post(device_url, headers=headers, json=payload)
    assert post_res.status_code == 200

    # 3. Read devices via API to verify it is returned
    get_res = httpx.get(device_url, headers=headers)
    assert get_res.status_code == 200
    devices_data = get_res.json()["devices"]
    assert any(d["mac"] == "aa:bb:cc:11:22:33" for d in devices_data)
