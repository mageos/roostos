import os
import tempfile
import shutil
import pytest
from roostos_engine.config import load_config_directory
from roostos_engine.git_engine import GitEngine
from roostos_engine.qos_manager import QoSManager

def test_git_engine_operations():
    """Tests the GitEngine repository operations."""
    temp_dir = tempfile.mkdtemp()
    try:
        # Initialize
        git_engine = GitEngine(temp_dir)
        git_dir = os.path.join(temp_dir, ".git")
        assert os.path.exists(git_dir)

        # Create dummy configuration file
        test_file = os.path.join(temp_dir, "system.yaml")
        with open(test_file, "w") as f:
            f.write("system: {}\n")

        # Commit changes
        success = git_engine.commit_changes("Initial commit")
        assert success

        # Commit again (no changes should be a no-op / return True)
        success_noop = git_engine.commit_changes("Second commit (no changes)")
        assert success_noop

        # Modify config file
        with open(test_file, "w") as f:
            f.write("system:\n  hostname: changed-host\n")

        success_modify = git_engine.commit_changes("Update hostname")
        assert success_modify

        # Verify history log contains our commits
        history = git_engine.get_commit_history()
        assert len(history) >= 2
        assert history[0]["description"] == "Update hostname"
        assert history[1]["description"] == "Initial commit"

        # Check rollback
        rollback_hash = history[1]["commit"]
        success_rollback = git_engine.rollback_to_commit(rollback_hash)
        assert success_rollback

        # Check content rolled back
        with open(test_file, "r") as f:
            content = f.read()
        assert "changed-host" not in content

    finally:
        shutil.rmtree(temp_dir)


def test_qos_manager_ruleset(temp_config_dir):
    """Tests QoSManager traffic control command generation."""
    config = load_config_directory(temp_config_dir)
    
    # Enable QoS settings in config
    config.network.qos.enabled = True
    config.network.qos.wan_upload_kbps = 50000
    config.network.qos.wan_download_kbps = 100000
    config.network.qos.prioritize_tags = ["gaming"]

    # Setup a device with priority tags and limit settings
    config.devices[0].tags.append("gaming")
    config.devices[0].max_upload_kbps = 10000
    config.devices[0].max_download_kbps = 20000
    config.devices[0].static_ip = "192.168.1.50"

    # Capture outputs by passing mock=True
    captured_commands = []
    manager = QoSManager(config, mock=True)
    
    # Override print function to collect commands
    def collect_cmd(args):
        captured_commands.append(" ".join(args))
    
    manager.execute_cmd = collect_cmd
    manager.update_qos()

    # Verify root qdisc deletion commands are called first
    assert any("qdisc del dev eth0 root" in cmd for cmd in captured_commands)
    assert any("qdisc del dev br0 root" in cmd for cmd in captured_commands)

    # Verify HTB add root classes
    assert any("qdisc add dev eth0 root handle 1: htb default 12" in cmd for cmd in captured_commands)
    assert any("class add dev eth0 parent 1: classid 1:1 htb rate 50000kbit" in cmd for cmd in captured_commands)

    # Verify priority tagging filter
    assert any("filter add dev eth0 protocol ip parent 1: prio 1 u32 match ip src 192.168.1.50 flowid 1:10" in cmd for cmd in captured_commands)

    # Verify device rate class and filter
    assert any("class add dev eth0 parent 1:1 classid 1:100 htb rate 10000kbit" in cmd for cmd in captured_commands)
    assert any("filter add dev eth0 protocol ip parent 1: prio 2 u32 match ip src 192.168.1.50 flowid 1:100" in cmd for cmd in captured_commands)
