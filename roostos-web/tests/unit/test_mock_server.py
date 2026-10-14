"""Unit tests for RoostOS mock API, mock client, and mock DI test server."""

import os
import pytest
from fastapi.testclient import TestClient

from roostos_engine.repository import ConfigRepository, InMemoryConfigRepository
from roostos_engine.cert_manager import CertificateManager
from roostos_engine.mock_cert_manager import MockCertificateManager
from roostos_sdk.client import RoostClient
from roostos_sdk.mock_client import MockRoostClient
from roostos_web.interfaces.auth import AuthProvider, MockAuthProvider
from roostos_web.di import create_mock_web_injector, set_injector
from roostos_web.main import create_app


@pytest.fixture
def mock_environment():
    """Sets up the isolated mock DI injector and environment variables."""
    old_mock = os.environ.get("ROOSTOS_MOCK")
    old_dev = os.environ.get("ROOSTOS_DEV_MOCK")
    os.environ["ROOSTOS_MOCK"] = "1"
    os.environ["ROOSTOS_DEV_MOCK"] = "1"

    injector = create_mock_web_injector()
    set_injector(injector)

    yield injector

    if old_mock is not None:
        os.environ["ROOSTOS_MOCK"] = old_mock
    else:
        os.environ.pop("ROOSTOS_MOCK", None)

    if old_dev is not None:
        os.environ["ROOSTOS_DEV_MOCK"] = old_dev
    else:
        os.environ.pop("ROOSTOS_DEV_MOCK", None)


def test_mock_di_container_bindings(mock_environment):
    injector = mock_environment
    repo = injector.get(ConfigRepository)
    assert isinstance(repo, InMemoryConfigRepository)

    cfg = repo.get_config()
    assert cfg.system.hostname == "roost-home-router"
    assert len(cfg.people) >= 4
    person_ids = [p.id for p in cfg.people]
    assert "dad" in person_ids and "alice" in person_ids

    assert len(cfg.devices) >= 3
    assert len(cfg.wifi.access_points) >= 2

    client = injector.get(RoostClient)
    assert isinstance(client, MockRoostClient)

    cm = injector.get(CertificateManager)
    assert isinstance(cm, MockCertificateManager)

    auth = injector.get(AuthProvider)
    assert isinstance(auth, MockAuthProvider)


@pytest.mark.asyncio
async def test_mock_roost_client_operations():
    client = MockRoostClient()
    await client.connect()
    assert client.disconnect() is None

    leases = await client.get_active_leases()
    assert len(leases) >= 3
    assert any(l["hostname"] == "Dads-MacBook-Pro" for l in leases)

    # Test lease registration & release
    ok = await client.register_lease("aa:bb:cc:dd:ee:11", "192.168.1.199", "Test-Device")
    assert ok is True
    updated = await client.get_active_leases()
    assert any(l["hostname"] == "Test-Device" for l in updated)

    ok_del = await client.release_lease("aa:bb:cc:dd:ee:11")
    assert ok_del is True

    # Test time extension
    ext_ok = await client.grant_time_extension("f4:d4:88:44:55:66", 1800)
    assert ext_ok is True
    assert "f4:d4:88:44:55:66" in client.time_extensions
    rem_ok = await client.remove_time_extension("f4:d4:88:44:55:66")
    assert rem_ok is True

    # Test cluster & health
    cluster = await client.get_cluster_status()
    assert cluster["status"] == "healthy"
    assert cluster["ha_enabled"] is True


def test_mock_endpoints_with_auto_mock_auth(mock_environment):
    app = create_app(mode="full", no_ui=False)
    client = TestClient(app)

    # 1. UI root index
    resp_ui = client.get("/")
    assert resp_ui.status_code == 200
    assert "RoostOS" in resp_ui.text

    # 2. Household pulse without any auth token (auto admin session)
    resp_pulse = client.get("/api/v1/household/pulse")
    assert resp_pulse.status_code == 200
    assert resp_pulse.json()["hostname"] == "roost-home-router"

    # 3. Devices list
    resp_devs = client.get("/api/devices")
    assert resp_devs.status_code == 200
    data = resp_devs.json()
    assert len(data["devices"]) >= 3
    assert len(data["active_leases"]) >= 3

    # 4. Family members
    resp_people = client.get("/api/v1/family/people")
    assert resp_people.status_code == 200
    people = resp_people.json()
    assert any(p["id"] == "alice" for p in people)

    # 5. DHCP scopes
    resp_scopes = client.get("/api/v1/dhcp/scopes")
    assert resp_scopes.status_code == 200
    scopes = resp_scopes.json()
    assert len(scopes) >= 1

    # 6. Security Shields
    resp_shields = client.get("/api/v1/protection/shields")
    assert resp_shields.status_code == 200
    assert resp_shields.json()["ad_blocking_enabled"] is True


def test_load_container_config_file_direct():
    from roostos_engine.di import load_providers_settings
    settings = load_providers_settings(providers_config_path="config/mock_container.yaml")
    assert settings.auth_provider == "mock"
    assert settings.config_repository == "memory"
    assert settings.system_client == "mock"
    assert settings.cert_manager == "mock"
    assert settings.firewall_manager == "mock"
    assert settings.data_seeder == "concept1"
    assert settings.auto_auth is True
    assert "exploratory UI" in (settings.description or "")


def test_load_container_config_presets():
    from roostos_engine.di import load_providers_settings
    mock_settings = load_providers_settings(providers_config_path="mock")
    assert mock_settings.config_repository == "memory"
    assert mock_settings.system_client == "mock"
    assert mock_settings.data_seeder == "concept1"

    prod_settings = load_providers_settings(providers_config_path="prod")
    assert prod_settings.config_repository == "staging"
    assert prod_settings.system_client == "dbus"
    assert prod_settings.auto_auth is False


def test_data_seeder_empty_vs_concept1():
    from roostos_engine.models.providers import ProvidersSettings
    # Empty seeder produces no preloaded people or devices
    empty_injector = create_mock_web_injector(
        providers_settings=ProvidersSettings(
            config_repository="memory",
            system_client="mock",
            cert_manager="mock",
            data_seeder="empty",
        )
    )
    repo_empty = empty_injector.get(ConfigRepository)
    cfg_empty = repo_empty.get_config()
    assert len(cfg_empty.people) == 0
    assert len(cfg_empty.devices) == 0

    # Concept1 seeder populates household personas and devices
    concept1_injector = create_mock_web_injector(
        providers_settings=ProvidersSettings(
            config_repository="memory",
            system_client="mock",
            cert_manager="mock",
            data_seeder="concept1",
        )
    )
    repo_concept1 = concept1_injector.get(ConfigRepository)
    cfg_concept1 = repo_concept1.get_config()
    assert len(cfg_concept1.people) >= 4
    assert len(cfg_concept1.devices) >= 3


def test_mock_server_and_main_cli_parsers():
    from roostos_web.mock_server import build_parser as build_mock_parser
    from roostos_web.main import build_parser as build_main_parser

    mock_parser = build_mock_parser()
    mock_args = mock_parser.parse_args([
        "--container-config", "config/mock_container.yaml",
        "--port", "8888",
        "--reload"
    ])
    assert mock_args.container_config == "config/mock_container.yaml"
    assert mock_args.port == 8888
    assert mock_args.reload is True

    main_parser = build_main_parser()
    main_args = main_parser.parse_args([
        "--container-config", "mock",
        "--mock",
        "--port", "8000"
    ])
    assert main_args.container_config == "mock"
    assert main_args.mock is True
    assert main_args.port == 8000

