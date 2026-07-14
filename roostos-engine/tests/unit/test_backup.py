import os
import pytest
import yaml
import tarfile
import tempfile
import shutil
import subprocess
from roostos_engine.daemon import RoostDaemonInterface

def test_backup_and_restore_success(temp_config_dir):
    """Test successful backup creation, encryption, decryption, manifest validation, and restore."""
    daemon = RoostDaemonInterface("org.roostos.Daemon", str(temp_config_dir))
    
    passphrase = "my-secret-passphrase"
    # Call the undecorated method directly using __wrapped__
    backup_path = daemon.CreateBackup.__wrapped__(daemon, passphrase)
    
    assert backup_path is not None
    assert os.path.exists(backup_path)
    assert backup_path.endswith(".tar.gz.gpg")

    # Modify the active configuration (change hostname and domain)
    system_file = os.path.join(temp_config_dir, "system.yaml")
    with open(system_file, "r") as f:
        sys_data = yaml.safe_load(f)
    sys_data["system"]["hostname"] = "modified-router"
    sys_data["system"]["domain"] = "modified.local"
    with open(system_file, "w") as f:
        yaml.safe_dump(sys_data, f)

    daemon.reload_config()
    assert daemon._config.system.hostname == "modified-router"
    assert daemon._config.system.domain == "modified.local"

    # Restore from the backup and verify configs revert back
    success = daemon.RestoreBackup.__wrapped__(daemon, backup_path, passphrase)
    assert success is True

    # Reload check
    assert daemon._config.system.hostname == "sandbox-router"
    assert daemon._config.system.domain == "lan"  # Default domain we added to config schema


def test_restore_incorrect_passphrase(temp_config_dir):
    """Test that restoring with a bad passphrase fails gracefully."""
    daemon = RoostDaemonInterface("org.roostos.Daemon", str(temp_config_dir))
    backup_path = daemon.CreateBackup.__wrapped__(daemon, "correct-passphrase")
    
    success = daemon.RestoreBackup.__wrapped__(daemon, backup_path, "wrong-passphrase")
    assert success is False


def test_restore_corrupt_manifest(temp_config_dir):
    """Test that restoring a backup with a corrupt manifest or mismatched file hashes fails."""
    daemon = RoostDaemonInterface("org.roostos.Daemon", str(temp_config_dir))
    passphrase = "test-passphrase"
    backup_path = daemon.CreateBackup.__wrapped__(daemon, passphrase)

    # Let's decrypt the backup, tamper with a file, re-encrypt it, and try restoring it
    with tempfile.TemporaryDirectory() as tmp_dir:
        decrypted_tar = os.path.join(tmp_dir, "backup.tar.gz")
        
        # Decrypt
        subprocess.run(
            ["gpg", "--decrypt", "--batch", "--yes", "--passphrase-fd", "0", "-o", decrypted_tar, backup_path],
            input=passphrase.encode(),
            check=True
        )
        
        # Extract
        extract_dir = os.path.join(tmp_dir, "extracted")
        with tarfile.open(decrypted_tar, "r:gz") as tar:
            tar.extractall(path=extract_dir)

        # Tamper with system.yaml (change a character to cause a checksum mismatch)
        system_file = os.path.join(extract_dir, "roostos", "system.yaml")
        with open(system_file, "a") as f:
            f.write("\ntampered: true\n")

        # Pack tar back up
        tampered_tar = os.path.join(tmp_dir, "tampered.tar.gz")
        with tarfile.open(tampered_tar, "w:gz") as tar:
            tar.add(os.path.join(extract_dir, "roostos"), arcname="roostos")

        # Encrypt back to backup_path
        subprocess.run(
            ["gpg", "--symmetric", "--cipher-algo", "AES256", "--batch", "--yes", "--passphrase-fd", "0", "-o", backup_path, tampered_tar],
            input=passphrase.encode(),
            check=True
        )

    # Restoring should fail because the SHA256 of system.yaml will not match manifest.json
    success = daemon.RestoreBackup.__wrapped__(daemon, backup_path, passphrase)
    assert success is False
