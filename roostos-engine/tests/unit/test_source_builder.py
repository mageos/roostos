"""Unit tests for RoostOS SourceBuilder and roost-app.yaml package manifests."""

import os
import tempfile
from unittest.mock import patch, MagicMock
import pytest
import yaml

from roostos_engine.source_builder import SourceBuilder, provision_ingress_route
from roostos_engine.models.catalog import (
    PackageManifest,
    SourceBuildSpec,
    CatalogContainerSpec,
    InstallFromSourceRequest,
)
from roostos_engine.models.plugins import PortMapping, VolumeMount


@pytest.fixture
def temp_workspace():
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


def test_package_manifest_to_app_entry():
    manifest = PackageManifest(
        id="custom-sensor",
        name="Custom IoT Sensor",
        version="1.2.0",
        category="automation",
        build=SourceBuildSpec(dockerfile="Dockerfile.custom", context_path="."),
        container=CatalogContainerSpec(
            image="roostos-local/custom-sensor:1.2.0",
            pull_policy="never",
            ports=[PortMapping(host_port=9000, container_port=8080)],
            volumes=[VolumeMount(host_path="/tmp/data", container_path="/data", mode="rw")],
        ),
    )
    entry = manifest.to_app_entry()
    assert entry.id == "custom-sensor"
    assert entry.name == "Custom IoT Sensor"
    assert entry.version == "1.2.0"
    assert entry.source_build.dockerfile == "Dockerfile.custom"
    assert entry.container.ports[0].host_port == 9000


def test_load_manifest_from_yaml(temp_workspace):
    builder = SourceBuilder(sources_dir=temp_workspace)
    app_dir = os.path.join(temp_workspace, "my-app")
    os.makedirs(app_dir, exist_ok=True)

    manifest_data = {
        "schema_version": "1.0",
        "id": "solar-monitor",
        "name": "Solar Power Monitor",
        "version": "2.0.1",
        "category": "tools",
        "build": {
            "dockerfile": "Dockerfile",
            "context_path": ".",
            "build_args": {"APP_ENV": "production"},
        },
        "container": {
            "image": "solar-monitor:latest",
            "ports": [{"host_port": 3000, "container_port": 3000, "protocol": "tcp"}],
            "volumes": [{"host_path": "/var/lib/solar", "container_path": "/app/data", "mode": "rw"}],
            "environment": {"LOG_LEVEL": "info"},
        },
    }
    with open(os.path.join(app_dir, "roost-app.yaml"), "w") as f:
        yaml.safe_dump(manifest_data, f)

    manifest = builder.load_manifest(app_dir)
    assert manifest is not None
    assert manifest.id == "solar-monitor"
    assert manifest.name == "Solar Power Monitor"
    assert manifest.build.build_args["APP_ENV"] == "production"
    assert manifest.container.ports[0].host_port == 3000


def test_load_manifest_fallback_dockerfile(temp_workspace):
    builder = SourceBuilder(sources_dir=temp_workspace)
    repo_dir = os.path.join(temp_workspace, "weather_station")
    os.makedirs(repo_dir, exist_ok=True)

    with open(os.path.join(repo_dir, "Dockerfile"), "w") as f:
        f.write("FROM alpine:latest\nCMD echo 'Weather'\n")

    manifest = builder.load_manifest(repo_dir)
    assert manifest is not None
    assert manifest.id == "weather-station"
    assert manifest.build.dockerfile == "Dockerfile"


def test_clone_or_resolve_local_directory(temp_workspace):
    builder = SourceBuilder(sources_dir=temp_workspace)
    local_dir = os.path.join(temp_workspace, "local_test_repo")
    os.makedirs(local_dir, exist_ok=True)

    resolved = builder.clone_or_resolve_source(local_dir)
    assert resolved == os.path.abspath(local_dir)


def test_build_and_prepare_plugin_full(temp_workspace):
    builder = SourceBuilder(sources_dir=temp_workspace)
    repo_dir = os.path.join(temp_workspace, "mock-service")
    os.makedirs(repo_dir, exist_ok=True)

    with open(os.path.join(repo_dir, "roost-app.yaml"), "w") as f:
        yaml.safe_dump({
            "id": "mock-service",
            "name": "Mock Service",
            "version": "1.0.0",
            "container": {
                "image": "mock-service:custom",
                "ports": [{"host_port": 5000, "container_port": 5000, "protocol": "tcp"}],
                "volumes": [{"host_path": "/data/mock", "container_path": "/data", "mode": "rw"}],
                "environment": {"PORT": "5000"},
            },
        }, f)

    with open(os.path.join(repo_dir, "Dockerfile"), "w") as f:
        f.write("FROM scratch\n")

    with patch.object(builder, "build_docker_image", return_value=(True, "Mock build output")):
        req = InstallFromSourceRequest(
            source_url_or_path=repo_dir,
            custom_environment={"CUSTOM_KEY": "custom_val"},
            custom_ports={5000: 5050},
        )
        plugin, manifest, logs = builder.build_and_prepare_plugin(req)

        assert plugin.id == "mock-service"
        assert plugin.name == "Mock Service"
        assert plugin.containers[0].pull_policy == "never"
        assert plugin.containers[0].ports[0].host_port == 5050
        assert plugin.containers[0].environment["CUSTOM_KEY"] == "custom_val"
        assert plugin.settings["built_from_source"] is True
        assert "Mock build output" in logs


def test_import_to_catalog(temp_workspace):
    from roostos_engine.catalog_manager import CatalogManager
    from roostos_engine.models.catalog import ImportFromSourceRequest

    builder = SourceBuilder(sources_dir=temp_workspace)
    catalog_mgr = CatalogManager(config_dir=temp_workspace)
    repo_dir = os.path.join(temp_workspace, "my-imported-tool")
    os.makedirs(repo_dir, exist_ok=True)

    with open(os.path.join(repo_dir, "roost-app.yaml"), "w") as f:
        yaml.safe_dump({
            "id": "my-imported-tool",
            "name": "My Imported Tool",
            "version": "1.0.0",
            "container": {"image": "roostos-local/my-imported-tool:1.0.0"}
        }, f)

    with open(os.path.join(repo_dir, "Dockerfile"), "w") as f:
        f.write("FROM alpine:3.19\nCMD echo ok\n")

    with patch.object(builder, "build_docker_image", return_value=(True, "Build OK")):
        req = ImportFromSourceRequest(source_url_or_path=repo_dir)
        app_entry, logs = builder.import_to_catalog(req, catalog_mgr)

        assert app_entry.id == "my-imported-tool"
        assert app_entry.imported is True
        assert app_entry.catalog_id == "local"
        assert "Build OK" in logs

        # Verify it now appears in catalog manager available apps
        apps = catalog_mgr.get_available_apps()
        found = next((a for a in apps if a.id == "my-imported-tool"), None)
        assert found is not None
        assert found.imported is True


def test_check_app_updates(temp_workspace):
    from roostos_engine.models.catalog import CatalogAppEntry, CatalogContainerSpec
    builder = SourceBuilder(sources_dir=temp_workspace)

    app = CatalogAppEntry(
        id="tracked-tool",
        name="Tracked Tool",
        version="1.0.0",
        description="Tracked app",
        container=CatalogContainerSpec(image="roostos-local/tracked:1.0"),
        source_repo="https://github.com/example/repo.git",
        source_ref="main",
        last_commit_built="11111111",
    )

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="22222222 refs/heads/main\n")
        has_update, remote_sha = builder.check_app_updates(app)
        assert has_update is True
        assert remote_sha == "22222222"

        # When remote matches last commit
        mock_run.return_value = MagicMock(returncode=0, stdout="11111111 refs/heads/main\n")
        has_update2, remote_sha2 = builder.check_app_updates(app)
        assert has_update2 is False

