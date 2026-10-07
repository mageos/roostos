import os
import hashlib
import datetime
import shutil
from typing import Dict, List, Optional
import httpx

from roostos_engine.models.node import ClusterStateManifest, ClusterStateBundle


CONFIG_FILES: List[str] = [
    "system.yaml",
    "network.yaml",
    "devices.yaml",
    "schedules.yaml",
    "plugins.yaml",
    "nodes.yaml",
]


class ClusterReplicator:
    """Manages hash manifests, state bundling, and anti-entropy replication across cluster nodes."""

    def __init__(self, config_dir: str = "/etc/roostos", mock: bool = False) -> None:
        self.config_dir = config_dir
        self.mock = mock
        self._mock_files: Dict[str, str] = {}

    def compute_file_hash(self, filename: str) -> str:
        """Computes SHA-256 hash for a specific configuration file."""
        if self.mock and filename in self._mock_files:
            content = self._mock_files[filename].encode("utf-8")
            return f"sha256:{hashlib.sha256(content).hexdigest()}"

        filepath = os.path.join(self.config_dir, filename)
        if not os.path.isfile(filepath):
            return ""

        hasher = hashlib.sha256()
        try:
            with open(filepath, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            return f"sha256:{hasher.hexdigest()}"
        except OSError:
            return ""

    def compute_hashes(self) -> Dict[str, str]:
        """Computes SHA-256 hashes for all managed cluster configuration files."""
        result: Dict[str, str] = {}
        for filename in CONFIG_FILES:
            file_hash = self.compute_file_hash(filename)
            if file_hash:
                result[filename] = file_hash
        return result

    def generate_manifest(
        self,
        epoch: int = 1,
        master_node_id: str = "node-01",
        controller_url: Optional[str] = None
    ) -> ClusterStateManifest:
        """Generates a signed cluster state manifest with current configuration hashes."""
        hashes = self.compute_hashes()
        now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return ClusterStateManifest(
            epoch=epoch,
            master_node_id=master_node_id,
            controller_url=controller_url,
            generated_at=now_iso,
            hashes=hashes,
        )

    def export_bundle(
        self,
        epoch: int = 1,
        master_node_id: str = "node-01"
    ) -> ClusterStateBundle:
        """Exports raw content of all managed configuration files as a state bundle."""
        bundle_files: Dict[str, str] = {}
        for filename in CONFIG_FILES:
            if self.mock and filename in self._mock_files:
                bundle_files[filename] = self._mock_files[filename]
                continue

            filepath = os.path.join(self.config_dir, filename)
            if os.path.isfile(filepath):
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        bundle_files[filename] = f.read()
                except OSError:
                    pass

        return ClusterStateBundle(
            epoch=epoch,
            master_node_id=master_node_id,
            files=bundle_files,
        )

    def apply_bundle(self, bundle: ClusterStateBundle, backup: bool = True) -> bool:
        """Applies a cluster state bundle to the local replica configuration directory."""
        if self.mock:
            self._mock_files.update(bundle.files)
            return True

        os.makedirs(self.config_dir, exist_ok=True)
        for filename, content in bundle.files.items():
            if filename not in CONFIG_FILES:
                continue

            target_path = os.path.join(self.config_dir, filename)
            if backup and os.path.isfile(target_path):
                bak_path = f"{target_path}.bak"
                try:
                    shutil.copy2(target_path, bak_path)
                except OSError:
                    pass

            tmp_path = f"{target_path}.tmp"
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    f.write(content)
                os.replace(tmp_path, target_path)
            except OSError as e:
                print(f"Failed to write replicated config '{filename}': {e}")
                return False

        return True

    def compare_manifest(self, remote_manifest: ClusterStateManifest) -> List[str]:
        """Compares local configuration hashes against a remote manifest and returns mismatches."""
        local_hashes = self.compute_hashes()
        mismatched: List[str] = []

        for filename, remote_hash in remote_manifest.hashes.items():
            local_hash = local_hashes.get(filename, "")
            if local_hash != remote_hash:
                mismatched.append(filename)

        return mismatched

    async def sync_from_controller(self, controller_url: str) -> bool:
        """Fetches the state bundle from the controller and applies it to local replica."""
        url = f"{controller_url.rstrip('/')}/api/cluster/sync/bundle"
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(url)
                res.raise_for_status()
                data = res.json()
                bundle = ClusterStateBundle.model_validate(data)
                return self.apply_bundle(bundle)
        except Exception as e:
            print(f"Failed to sync state from controller at {controller_url}: {e}")
            return False
