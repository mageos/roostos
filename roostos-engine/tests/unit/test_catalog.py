"""Unit tests for RoostOS CatalogManager and decentralized catalog security."""

import os
import json
import base64
import tempfile
import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519

from roostos_engine.catalog_manager import CatalogManager
from roostos_engine.models.catalog import (
    CatalogSourceConfig,
    CatalogIndex,
    CatalogAppEntry,
    CatalogContainerSpec,
    InstallAppRequest,
)


@pytest.fixture
def temp_catalog_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_catalog_manager_default_sources(temp_catalog_dir):
    mgr = CatalogManager(config_dir=temp_catalog_dir)
    sources = mgr.list_sources()
    assert len(sources) >= 1
    assert sources[0].id == "official"


def test_catalog_manager_add_and_remove_source(temp_catalog_dir):
    mgr = CatalogManager(config_dir=temp_catalog_dir)
    custom_source = CatalogSourceConfig(
        id="community",
        name="Community Catalog",
        url="https://example.com/catalog.json",
        enabled=True,
    )
    mgr.add_source(custom_source)

    sources = mgr.list_sources()
    assert any(s.id == "community" for s in sources)

    removed = mgr.remove_source("community")
    assert removed is True
    assert not any(s.id == "community" for s in mgr.list_sources())


def test_ed25519_signature_verification(temp_catalog_dir):
    mgr = CatalogManager(config_dir=temp_catalog_dir)
    priv_key = ed25519.Ed25519PrivateKey.generate()
    pub_key = priv_key.public_key()

    pub_bytes = pub_key.public_bytes_raw()
    pub_str = f"ed25519:{pub_bytes.hex()}"

    content = b'{"catalog_id": "test", "name": "Signed Catalog", "applications": []}'
    sig = priv_key.sign(content)
    sig_b64 = base64.b64encode(sig).decode("ascii")

    # Valid signature
    assert mgr.verify_ed25519_signature(content, sig_b64, pub_str) is True

    # Tampered content
    tampered = b'{"catalog_id": "test", "name": "TAMPERED", "applications": []}'
    assert mgr.verify_ed25519_signature(tampered, sig_b64, pub_str) is False

    # Corrupt signature
    assert mgr.verify_ed25519_signature(content, "bad-signature", pub_str) is False


def test_fetch_local_file_catalog(temp_catalog_dir):
    mgr = CatalogManager(config_dir=temp_catalog_dir)
    catalog_path = os.path.join(temp_catalog_dir, "test_catalog.json")
    catalog_data = {
        "catalog_id": "local_test",
        "name": "Local Test Catalog",
        "version": "1.0.0",
        "applications": [
            {
                "id": "my-local-app",
                "name": "My Local App",
                "version": "1.0.0",
                "category": "tools",
                "description": "Custom local microservice",
                "container": {
                    "image": "local/my-app:latest",
                    "pull_policy": "never",
                    "ports": [{"host_port": 9000, "container_port": 80, "protocol": "tcp"}],
                }
            }
        ]
    }
    with open(catalog_path, "w") as f:
        json.dump(catalog_data, f)

    source = CatalogSourceConfig(
        id="local_file",
        name="Local File",
        url=f"file://{catalog_path}",
        enabled=True,
    )
    cat = mgr.fetch_catalog(source)
    assert cat is not None
    assert cat.name == "Local Test Catalog"
    assert len(cat.applications) == 1
    assert cat.applications[0].id == "my-local-app"
    assert cat.applications[0].container.pull_policy == "never"


def test_get_available_apps_fallback_builtins(temp_catalog_dir):
    mgr = CatalogManager(config_dir=temp_catalog_dir)
    # With unreachable or empty default, fallback built-ins populate
    apps = mgr.get_available_apps(installed_plugin_ids=["homeassistant"])
    assert len(apps) >= 4
    ha = next(a for a in apps if a.id == "homeassistant")
    assert ha.installed is True
    immich = next(a for a in apps if a.id == "immich")
    assert immich.installed is False


def test_create_plugin_from_app(temp_catalog_dir):
    mgr = CatalogManager(config_dir=temp_catalog_dir)
    apps = mgr.get_available_apps()
    ha = next(a for a in apps if a.id == "homeassistant")

    req = InstallAppRequest(
        app_id="homeassistant",
        custom_ports={8123: 8124},
        custom_environment={"CUSTOM_VAR": "true"},
    )
    plugin = mgr.create_plugin_from_app(ha, req)
    assert plugin.id == "homeassistant"
    assert plugin.enabled is True
    assert len(plugin.containers) == 1
    assert plugin.containers[0].ports[0].host_port == 8124
    assert plugin.containers[0].environment["CUSTOM_VAR"] == "true"
