"""CatalogManager for decentralized RoostOS application catalogs and local deployments."""

import os
import json
import base64
import urllib.request
from typing import List, Dict, Optional, Any
import yaml

from roostos_engine.models.catalog import (
    CatalogAppEntry,
    CatalogIndex,
    CatalogSourceConfig,
    CatalogContainerSpec,
    IngressPreset,
    InstallAppRequest,
)
from roostos_engine.models.plugins import (
    PluginConfig,
    ContainerConfig,
    PortMapping,
    VolumeMount,
)
from roostos_engine.catalog_defaults import DEFAULT_BUILTIN_APPS


class CatalogManager:
    """Orchestrates configurable catalog sources, local catalog, and app provisioning."""

    def __init__(self, config_dir: str = "/etc/roostos", cache_dir: Optional[str] = None):
        self.config_dir = config_dir
        self.cache_dir = cache_dir or os.path.join(config_dir, "cache", "catalogs")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.catalogs_file = os.path.join(self.config_dir, "catalogs.yaml")
        self.local_catalog_file = os.path.join(self.config_dir, "local_catalog.json")

    def get_local_catalog(self) -> CatalogIndex:
        """Returns the local imported applications catalog index."""
        if os.path.exists(self.local_catalog_file):
            try:
                with open(self.local_catalog_file, "r") as f:
                    data = json.load(f)
                return CatalogIndex.model_validate(data)
            except Exception:
                pass
        return CatalogIndex(
            catalog_id="local",
            name="Local / Imported Applications",
            description="Applications built locally or imported from source",
            applications=[],
        )

    def save_local_catalog(self, index: CatalogIndex) -> None:
        """Persists the local imported applications catalog to disk."""
        os.makedirs(self.config_dir, exist_ok=True)
        with open(self.local_catalog_file, "w") as f:
            json.dump(index.model_dump(mode="json"), f, indent=2)

    def add_local_app(self, entry: CatalogAppEntry) -> None:
        """Adds or updates an application entry in the local catalog."""
        entry.catalog_id = "local"
        entry.imported = True
        index = self.get_local_catalog()
        index.applications = [a for a in index.applications if a.id != entry.id]
        index.applications.append(entry)
        self.save_local_catalog(index)

    def remove_local_app(self, app_id: str) -> bool:
        """Removes an application from the local catalog."""
        index = self.get_local_catalog()
        initial_len = len(index.applications)
        index.applications = [a for a in index.applications if a.id != app_id]
        if len(index.applications) != initial_len:
            self.save_local_catalog(index)
            return True
        return False

    def list_sources(self) -> List[CatalogSourceConfig]:
        """Reads configured catalog sources from catalogs.yaml, falling back to default."""
        if os.path.exists(self.catalogs_file):
            try:
                with open(self.catalogs_file, "r") as f:
                    data = yaml.safe_load(f) or {}
                raw_sources = data.get("catalogs", [])
                return [CatalogSourceConfig.model_validate(s) for s in raw_sources]
            except Exception:
                pass
        return [
            CatalogSourceConfig(
                id="official",
                name="RoostOS Official Catalog",
                url="https://catalog.roostos.org/index.json",
                enabled=True,
                allow_insecure=True,
            )
        ]

    def save_sources(self, sources: List[CatalogSourceConfig]) -> None:
        """Persists catalog sources to catalogs.yaml."""
        os.makedirs(self.config_dir, exist_ok=True)
        data = {"catalogs": [s.model_dump(mode="json", exclude_none=True) for s in sources]}
        with open(self.catalogs_file, "w") as f:
            yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

    def add_source(self, source: CatalogSourceConfig) -> None:
        """Appends or updates a catalog source."""
        sources = [s for s in self.list_sources() if s.id != source.id]
        sources.append(source)
        self.save_sources(sources)

    def remove_source(self, source_id: str) -> bool:
        """Removes a catalog source by identifier."""
        sources = self.list_sources()
        new_sources = [s for s in sources if s.id != source_id]
        if len(new_sources) != len(sources):
            self.save_sources(new_sources)
            return True
        return False

    def verify_ed25519_signature(self, content_bytes: bytes, signature_b64: str, public_key_str: str) -> bool:
        """Verifies Ed25519 signature of catalog manifest bytes."""
        try:
            from cryptography.hazmat.primitives.asymmetric import ed25519
            if public_key_str.startswith("ed25519:"):
                public_key_str = public_key_str[8:]
            try:
                key_bytes = bytes.fromhex(public_key_str)
            except ValueError:
                key_bytes = base64.b64decode(public_key_str)
            sig_bytes = base64.b64decode(signature_b64)
            pub_key = ed25519.Ed25519PublicKey.from_public_bytes(key_bytes)
            pub_key.verify(sig_bytes, content_bytes)
            return True
        except Exception:
            return False

    def fetch_catalog(self, source: CatalogSourceConfig) -> Optional[CatalogIndex]:
        """Fetches catalog manifest from local file or HTTP(S) URL with signature verification."""
        try:
            content_bytes: bytes
            if source.url.startswith("file://"):
                local_path = source.url[7:]
                with open(local_path, "rb") as f:
                    content_bytes = f.read()
            elif os.path.isabs(source.url):
                with open(source.url, "rb") as f:
                    content_bytes = f.read()
            else:
                req = urllib.request.Request(source.url, headers={"User-Agent": "RoostOS-CatalogManager/1.0"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    content_bytes = resp.read()

            if source.public_key:
                sig_url = f"{source.url}.sig"
                sig_bytes = b""
                try:
                    if sig_url.startswith("file://") or os.path.isabs(sig_url):
                        path = sig_url[7:] if sig_url.startswith("file://") else sig_url
                        if os.path.exists(path):
                            with open(path, "rb") as sf:
                                sig_bytes = sf.read()
                    else:
                        with urllib.request.urlopen(sig_url, timeout=3) as sresp:
                            sig_bytes = sresp.read()
                except Exception:
                    pass

                if not sig_bytes or not self.verify_ed25519_signature(content_bytes, sig_bytes.decode("utf-8").strip(), source.public_key):
                    if not source.allow_insecure:
                        return None

            data = json.loads(content_bytes.decode("utf-8"))
            data["catalog_id"] = source.id
            index = CatalogIndex.model_validate(data)
            cache_file = os.path.join(self.cache_dir, f"{source.id}.json")
            with open(cache_file, "w") as cf:
                cf.write(content_bytes.decode("utf-8"))
            return index
        except Exception:
            cache_file = os.path.join(self.cache_dir, f"{source.id}.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r") as cf:
                        data = json.load(cf)
                    return CatalogIndex.model_validate(data)
                except Exception:
                    pass
            return None

    def get_available_apps(self, installed_plugin_ids: Optional[List[str]] = None) -> List[CatalogAppEntry]:
        """Returns aggregated apps from all enabled sources, local catalog, and built-ins."""
        installed = set(installed_plugin_ids or [])
        sources = [s for s in self.list_sources() if s.enabled]
        apps: Dict[str, CatalogAppEntry] = {}

        for source in sources:
            cat = self.fetch_catalog(source)
            if cat and cat.applications:
                for app in cat.applications:
                    app.catalog_id = source.id
                    app.installed = app.id in installed
                    apps[app.id] = app

        if not apps:
            for raw in DEFAULT_BUILTIN_APPS:
                app = CatalogAppEntry.model_validate(raw)
                app.installed = app.id in installed
                apps[app.id] = app

        # Merge local catalog applications
        local_index = self.get_local_catalog()
        for local_app in local_index.applications:
            local_app.catalog_id = "local"
            local_app.imported = True
            local_app.installed = local_app.id in installed
            apps[local_app.id] = local_app

        return list(apps.values())

    def create_plugin_from_app(self, app: CatalogAppEntry, req: InstallAppRequest) -> PluginConfig:
        """Converts a catalog application entry into an active RoostOS PluginConfig."""
        container_ports = []
        for p in app.container.ports:
            hp = req.custom_ports.get(p.container_port, p.host_port)
            container_ports.append(PortMapping(host_port=hp, container_port=p.container_port, protocol=p.protocol))

        env = app.container.environment.copy()
        env.update(req.custom_environment)

        container = ContainerConfig(
            name=f"app-{app.id}",
            image=app.container.image,
            pull_policy=app.container.pull_policy,
            ports=container_ports,
            volumes=app.container.volumes,
            environment=env,
        )

        return PluginConfig(
            id=app.id,
            name=app.name,
            type="application",
            enabled=True,
            network_mode=app.container.network_mode,
            requested_scopes=app.requested_scopes,
            containers=[container],
            settings={
                "catalog_id": req.catalog_id or app.catalog_id,
                "version": app.version,
                "imported": app.imported,
                "source_repo": app.source_repo or "",
                "last_commit_built": app.last_commit_built or "",
            },
        )
