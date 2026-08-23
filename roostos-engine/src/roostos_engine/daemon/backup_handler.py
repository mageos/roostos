import os
import sys
import json
import hashlib
import tempfile
import shutil
import tarfile
import subprocess
import datetime
from typing import Callable, Optional, Dict, Any, List


class BackupHandler:
    """Manages secure GPG AES-256 encrypted backups and manifest-verified restores."""

    def __init__(self, config_dir: str, get_hostname: Callable[[], str], on_restored: Callable[[], None]):
        self.config_dir = config_dir
        self.get_hostname = get_hostname
        self.on_restored = on_restored

    def create_backup(self, passphrase: str) -> str:
        """Creates an encrypted GPG backup of all config files under config_dir."""
        backup_dir = "/var/lib/roostos/backups"
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except PermissionError:
            # Fall back to user-writeable path inside config_dir for testing/sandbox envs
            backup_dir = os.path.join(self.config_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
        backup_path = os.path.join(backup_dir, "roostos-backup.tar.gz.gpg")

        with tempfile.TemporaryDirectory() as tmp_dir:
            staged_configs = os.path.join(tmp_dir, "roostos")
            os.makedirs(staged_configs, exist_ok=True)

            # Copy all files from config directory into staged_configs
            config_files: List[str] = []
            if os.path.exists(self.config_dir):
                for item in os.listdir(self.config_dir):
                    item_path = os.path.join(self.config_dir, item)
                    # Skip state.db or temporary/cache files
                    if item in ("state.db", "state.db-shm", "state.db-wal", "backups"):
                        continue
                    if os.path.isdir(item_path):
                        shutil.copytree(item_path, os.path.join(staged_configs, item))
                    else:
                        shutil.copy2(item_path, os.path.join(staged_configs, item))
                        config_files.append(item)

            # Calculate SHA-256 hashes of copied configuration files
            manifest_files: List[Dict[str, str]] = []
            for root, _, files in os.walk(staged_configs):
                for f in sorted(files):
                    file_abspath = os.path.join(root, f)
                    rel_path = os.path.relpath(file_abspath, staged_configs)
                    sha = hashlib.sha256()
                    with open(file_abspath, "rb") as file_bin:
                        while chunk := file_bin.read(4096):
                            sha.update(chunk)
                    manifest_files.append({
                        "path": rel_path,
                        "sha256": sha.hexdigest()
                    })

            # Create manifest.json
            manifest: Dict[str, Any] = {
                "roostos_backup_version": "1.0",
                "roostos_version": "0.1.0",
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "hostname": self.get_hostname(),
                "files": manifest_files
            }
            with open(os.path.join(staged_configs, "manifest.json"), "w") as f:
                json.dump(manifest, f, indent=2)

            # Tar the staging directory
            tar_path = os.path.join(tmp_dir, "backup.tar.gz")
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(staged_configs, arcname="roostos")

            # Encrypt tar.gz using GPG AES256
            try:
                subprocess.run(
                    ["gpg", "--symmetric", "--cipher-algo", "AES256", "--batch", "--yes", "--passphrase-fd", "0", "-o", backup_path, tar_path],
                    input=passphrase.encode(),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                print(f"Backup created successfully at {backup_path} using GPG encryption.")
                return backup_path
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode()
                print(f"Error encrypting backup: {err_msg}", file=sys.stderr)
                raise Exception(f"Encryption failed: {err_msg}")

    def restore_backup(self, backup_path: str, passphrase: str) -> bool:
        """Decrypts, validates manifest checksums, and restores config files."""
        if not os.path.exists(backup_path):
            print(f"Restore failed: Backup file {backup_path} not found.", file=sys.stderr)
            return False

        with tempfile.TemporaryDirectory() as tmp_dir:
            decrypted_tar = os.path.join(tmp_dir, "backup.tar.gz")
            
            # Decrypt the GPG backup
            try:
                subprocess.run(
                    ["gpg", "--decrypt", "--batch", "--yes", "--passphrase-fd", "0", "-o", decrypted_tar, backup_path],
                    input=passphrase.encode(),
                    check=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
            except subprocess.CalledProcessError as e:
                print(f"Restore failed: Decryption error: {e.stderr.decode()}", file=sys.stderr)
                return False

            # Extract tar
            restore_staged = os.path.join(tmp_dir, "restore_staged")
            try:
                with tarfile.open(decrypted_tar, "r:gz") as tar:
                    tar.extractall(path=restore_staged, filter="data")
            except Exception as e:
                print(f"Restore failed: Failed to extract archive: {e}", file=sys.stderr)
                return False

            roostos_dir = os.path.join(restore_staged, "roostos")
            manifest_path = os.path.join(roostos_dir, "manifest.json")
            if not os.path.exists(manifest_path):
                print("Restore failed: manifest.json missing from backup.", file=sys.stderr)
                return False

            # Read and parse manifest
            try:
                with open(manifest_path, "r") as f:
                    manifest = json.load(f)
            except Exception as e:
                print(f"Restore failed: Failed to parse manifest: {e}", file=sys.stderr)
                return False

            # Validate manifest structure and versions
            if manifest.get("roostos_backup_version") != "1.0":
                print(f"Restore failed: Incompatible backup version: {manifest.get('roostos_backup_version')}", file=sys.stderr)
                return False

            # Verify checksums of files
            for file_entry in manifest.get("files", []):
                rel_path = file_entry.get("path")
                expected_sha = file_entry.get("sha256")
                full_path = os.path.join(roostos_dir, rel_path)

                if not os.path.exists(full_path):
                    print(f"Restore failed: File {rel_path} in manifest is missing from backup.", file=sys.stderr)
                    return False

                sha = hashlib.sha256()
                with open(full_path, "rb") as file_bin:
                    while chunk := file_bin.read(4096):
                        sha.update(chunk)
                
                if sha.hexdigest() != expected_sha:
                    print(f"Restore failed: Checksum mismatch for file {rel_path}.", file=sys.stderr)
                    return False

            # If all checks pass, restore files to config directory
            try:
                os.remove(manifest_path)
                for item in os.listdir(roostos_dir):
                    src_item = os.path.join(roostos_dir, item)
                    dst_item = os.path.join(self.config_dir, item)
                    if os.path.isdir(src_item):
                        if os.path.exists(dst_item):
                            shutil.rmtree(dst_item)
                        shutil.copytree(src_item, dst_item)
                    else:
                        shutil.copy2(src_item, dst_item)
                
                print("Backup files successfully restored to configuration directory.")
                self.on_restored()
                return True
            except Exception as e:
                print(f"Restore failed: Failed to copy configurations: {e}", file=sys.stderr)
                return False
