import pytest
import os
import tempfile
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from roostos_engine.cluster_replicator import ClusterReplicator
from roostos_engine.cluster_sync import ClusterSyncAgent
from roostos_engine.models.node import ClusterStateManifest, ClusterStateBundle


def test_cluster_replicator_hashes_and_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        replicator = ClusterReplicator(config_dir=tmpdir)

        # Write sample configuration files
        sys_file = os.path.join(tmpdir, "system.yaml")
        with open(sys_file, "w") as f:
            f.write("system:\n  hostname: test-master\n")

        net_file = os.path.join(tmpdir, "network.yaml")
        with open(net_file, "w") as f:
            f.write("network:\n  interfaces: []\n")

        hashes = replicator.compute_hashes()
        assert "system.yaml" in hashes
        assert "network.yaml" in hashes
        assert hashes["system.yaml"].startswith("sha256:")

        manifest = replicator.generate_manifest(epoch=2, master_node_id="master-01", controller_url="http://192.168.1.1:8000")
        assert manifest.epoch == 2
        assert manifest.master_node_id == "master-01"
        assert manifest.controller_url == "http://192.168.1.1:8000"
        assert "system.yaml" in manifest.hashes


def test_cluster_replicator_bundle_export_and_apply():
    with tempfile.TemporaryDirectory() as src_dir, tempfile.TemporaryDirectory() as dst_dir:
        src_rep = ClusterReplicator(config_dir=src_dir)
        dst_rep = ClusterReplicator(config_dir=dst_dir)

        # Populate source
        with open(os.path.join(src_dir, "devices.yaml"), "w") as f:
            f.write("devices:\n  - id: dev-1\n")
        with open(os.path.join(src_dir, "schedules.yaml"), "w") as f:
            f.write("schedules: []\n")

        bundle = src_rep.export_bundle(epoch=3, master_node_id="master-01")
        assert bundle.epoch == 3
        assert "devices.yaml" in bundle.files
        assert "schedules.yaml" in bundle.files

        # Apply to destination replica
        success = dst_rep.apply_bundle(bundle)
        assert success is True

        dst_devices = os.path.join(dst_dir, "devices.yaml")
        assert os.path.isfile(dst_devices)
        with open(dst_devices, "r") as f:
            content = f.read()
        assert "dev-1" in content


def test_cluster_replicator_anti_entropy_compare():
    with tempfile.TemporaryDirectory() as tmpdir:
        replicator = ClusterReplicator(config_dir=tmpdir)
        with open(os.path.join(tmpdir, "network.yaml"), "w") as f:
            f.write("network:\n  interfaces: [eth0]\n")

        manifest = ClusterStateManifest(
            epoch=1,
            master_node_id="node-01",
            hashes={
                "network.yaml": "sha256:differenthash123",
                "devices.yaml": "sha256:somehash456",
            }
        )

        mismatches = replicator.compare_manifest(manifest)
        assert "network.yaml" in mismatches
        assert "devices.yaml" in mismatches


@pytest.mark.asyncio
async def test_cluster_sync_agent_automatic_failover():
    agent = ClusterSyncAgent(
        node_id="standby-02",
        controller_url="http://dead-master:8000",
        sync_interval_seconds=1,
        mock=True,
        failover_priority=90,
        auto_failover=True,
        failover_threshold=3,
    )

    assert agent.failover_priority == 90
    assert agent.is_promoted_master is False

    # Simulate 3 failures
    with patch.object(agent, "send_heartbeat", side_effect=Exception("Connection refused")):
        # Evaluate failover trigger directly
        agent.consecutive_heartbeat_failures = 3
        promoted = await agent.evaluate_and_trigger_failover()
        assert promoted is True
        assert agent.is_promoted_master is True
