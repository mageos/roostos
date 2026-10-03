"""Unit tests for roostos app CLI commands."""

import os
import yaml
from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from roostos_cli.main import cli
from roostos_engine.models.plugins import PluginConfig, ContainerConfig, PortMapping


def test_app_inspect_cli(tmp_path):
    runner = CliRunner()
    app_dir = tmp_path / "mock-pkg"
    app_dir.mkdir()
    manifest_file = app_dir / "roost-app.yaml"
    manifest_file.write_text(yaml.safe_dump({
        "id": "mesh-bridge",
        "name": "Mesh Network Bridge",
        "version": "1.0.0",
        "category": "networking",
        "container": {
            "ports": [{"host_port": 8888, "container_port": 8888, "protocol": "tcp"}],
            "volumes": [{"host_path": "/var/mesh", "container_path": "/data", "mode": "rw"}],
        }
    }))

    res = runner.invoke(cli, ["app", "inspect", str(app_dir)])
    assert res.exit_code == 0
    assert "Mesh Network Bridge" in res.output
    assert "8888➔8888" in res.output


def test_app_inspect_cli_with_sandbox(tmp_path):
    runner = CliRunner()
    app_dir = tmp_path / "hardened-pkg"
    app_dir.mkdir()
    manifest_file = app_dir / "roost-build.yaml"
    manifest_file.write_text(yaml.safe_dump({
        "app_id": "hardened-service",
        "sandbox": {
            "allow_network": False,
            "max_memory_mb": 1536,
            "max_cpu_cores": 1.0,
            "timeout_seconds": 300,
        }
    }))

    res = runner.invoke(cli, ["app", "inspect", str(app_dir)])
    assert res.exit_code == 0
    assert "Build Sandbox:" in res.output
    assert "No (offline)" in res.output
    assert "1536 MB" in res.output
    assert "1.0 cores" in res.output


def test_app_install_cli(tmp_path):
    runner = CliRunner()
    app_dir = tmp_path / "install-pkg"
    app_dir.mkdir()
    (app_dir / "roost-app.yaml").write_text(yaml.safe_dump({
        "id": "my-tool",
        "name": "My Tool",
        "version": "0.5.0",
        "container": {"ports": [{"host_port": 9090, "container_port": 9090}]}
    }))

    mock_plugin = PluginConfig(
        id="my-tool",
        name="My Tool",
        enabled=True,
        containers=[
            ContainerConfig(
                name="app-my-tool",
                image="roostos-local/my-tool:0.5.0",
                pull_policy="never",
                ports=[PortMapping(host_port=9090, container_port=9090)],
            )
        ],
    )

    with patch("roostos_engine.source_builder.SourceBuilder.build_and_prepare_plugin", return_value=(mock_plugin, None, "Success")):
        with patch("roostos_engine.repository.YAMLConfigRepository.save_plugins_config") as mock_save:
            res = runner.invoke(cli, ["app", "install", "--source", str(app_dir), "--config-dir", str(tmp_path)])
            assert res.exit_code == 0
            assert "Successfully installed 'My Tool'" in res.output
            assert mock_save.called


def test_app_import_cli(tmp_path):
    from roostos_engine.models.catalog import CatalogAppEntry, CatalogContainerSpec
    runner = CliRunner()
    app_dir = tmp_path / "import-pkg"
    app_dir.mkdir()
    (app_dir / "roost-app.yaml").write_text(yaml.safe_dump({
        "id": "imported-tool",
        "name": "Imported Tool",
        "version": "1.0.0",
        "container": {"image": "roostos-local/imported-tool:1.0.0"}
    }))

    mock_entry = CatalogAppEntry(
        id="imported-tool",
        name="Imported Tool",
        version="1.0.0",
        description="Imported desc",
        container=CatalogContainerSpec(image="roostos-local/imported-tool:1.0.0"),
        imported=True,
        last_commit_built="abc1234",
    )

    with patch("roostos_engine.source_builder.SourceBuilder.import_to_catalog", return_value=(mock_entry, "Build log")):
        res = runner.invoke(cli, ["app", "import", str(app_dir), "--config-dir", str(tmp_path)])
        assert res.exit_code == 0
        assert "Successfully imported 'Imported Tool' into local catalog!" in res.output
        assert "abc1234" in res.output

