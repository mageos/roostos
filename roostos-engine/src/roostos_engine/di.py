"""RoostOS Engine Dependency Injection Module and Provider Loader."""

import os
import yaml
from typing import Optional, Dict, Any
from injector import Module, Binder, singleton, provider, Injector

from roostos_engine.models.providers import ProvidersSettings, ProvidersConfigFile
from roostos_engine.repository import (
    ConfigRepository,
    StagingConfigRepository,
    YAMLConfigRepository,
    InMemoryConfigRepository,
)
from roostos_engine.cert_manager import CertificateManager


def load_providers_settings(
    config_dir: str = "/etc/roostos",
    providers_config_path: Optional[str] = None,
    overrides: Optional[Dict[str, Any]] = None
) -> ProvidersSettings:
    """Loads ProvidersSettings from container.yaml/providers.yaml, applying environment and CLI overrides."""
    settings_dict: Dict[str, Any] = {}
    target_file = None

    # Check for preset shortcuts like 'mock' or 'prod'
    if providers_config_path in ("mock", "mock_container"):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        candidate = os.path.join(repo_root, "config", "mock_container.yaml")
        if os.path.exists(candidate):
            target_file = candidate
        else:
            settings_dict.update({
                "auth_provider": "mock",
                "config_repository": "memory",
                "system_client": "mock",
                "cert_manager": "mock",
                "firewall_manager": "mock",
                "data_seeder": "concept1",
                "auto_auth": True,
            })
    elif providers_config_path in ("prod", "production"):
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        candidate = os.path.join(repo_root, "config", "container.yaml")
        if os.path.exists(candidate):
            target_file = candidate
    else:
        target_file = providers_config_path or os.environ.get(
            "ROOSTOS_CONTAINER_CONFIG",
            os.environ.get(
                "ROOSTOS_PROVIDERS_CONFIG",
                os.path.join(config_dir, "container.yaml")
                if os.path.exists(os.path.join(config_dir, "container.yaml"))
                else os.path.join(config_dir, "providers.yaml")
            )
        )

    # 1. Load from file if present
    if target_file and os.path.exists(target_file):
        try:
            with open(target_file, "r") as f:
                content = yaml.safe_load(f) or {}
                if "container" in content and isinstance(content["container"], dict):
                    settings_dict.update(content["container"])
                elif "providers" in content and isinstance(content["providers"], dict):
                    settings_dict.update(content["providers"])
                elif isinstance(content, dict):
                    settings_dict.update(content)
        except Exception as e:
            print(f"Warning: Failed to parse container config file '{target_file}': {e}")

    # 2. Apply environment variable overrides
    env_mappings = {
        "ROOSTOS_AUTH_PROVIDER": "auth_provider",
        "ROOSTOS_CONFIG_REPO": "config_repository",
        "ROOSTOS_SYSTEM_CLIENT": "system_client",
        "ROOSTOS_CERT_MANAGER": "cert_manager",
        "ROOSTOS_FIREWALL_MANAGER": "firewall_manager",
        "ROOSTOS_DATA_SEEDER": "data_seeder",
    }
    for env_key, setting_key in env_mappings.items():
        val = os.environ.get(env_key)
        if val:
            settings_dict[setting_key] = val

    # 3. Apply explicit CLI / caller overrides
    if overrides:
        for k, v in overrides.items():
            if v is not None:
                settings_dict[k] = v

    # Mock auth shortcut fallback
    if os.environ.get("ROOSTOS_MOCK_AUTH") == "1" and "auth_provider" not in settings_dict:
        settings_dict["auth_provider"] = "mock"

    return ProvidersSettings(**settings_dict)


class EngineDIModule(Module):
    """Injector Module configuring core roostos-engine provider bindings."""

    def __init__(
        self,
        config_dir: str = "/etc/roostos",
        staged_dir: Optional[str] = None,
        cert_dir: Optional[str] = None,
        providers_settings: Optional[ProvidersSettings] = None
    ):
        self.config_dir = config_dir
        self.staged_dir = staged_dir or os.environ.get(
            "ROOSTOS_STAGED_CONFIG_DIR",
            os.path.join(os.path.dirname(config_dir.rstrip("/")), "staged_config")
            if config_dir != "/etc/roostos"
            else "/var/lib/roostos/staged_config"
        )
        self.cert_dir = cert_dir or os.environ.get(
            "ROOSTOS_CERT_DIR",
            os.path.join(config_dir, "certs")
        )
        self.providers_settings = providers_settings or load_providers_settings(config_dir)

    def configure(self, binder: Binder) -> None:
        # Bind ProvidersSettings instance as singleton
        binder.bind(ProvidersSettings, to=self.providers_settings, scope=singleton)

        # Bind ConfigRepository implementation
        repo_impl = self.providers_settings.config_repository.lower()
        if repo_impl in ("staging", "staged"):
            repo_instance = StagingConfigRepository(self.config_dir, self.staged_dir)
        elif repo_impl in ("yaml", "file", "direct"):
            repo_instance = YAMLConfigRepository(self.config_dir)
        elif repo_impl in ("memory", "inmemory", "mock"):
            seeder = getattr(self.providers_settings, "data_seeder", "concept1").lower()
            if seeder in ("empty", "none", "clean"):
                repo_instance = InMemoryConfigRepository()
            elif os.path.exists(seeder):
                from roostos_engine.config import load_config_directory
                repo_instance = InMemoryConfigRepository(initial_config=load_config_directory(seeder))
            else:
                from roostos_engine.mock_data import create_mock_config
                repo_instance = InMemoryConfigRepository(initial_config=create_mock_config())
        else:
            repo_instance = StagingConfigRepository(self.config_dir, self.staged_dir)

        binder.bind(ConfigRepository, to=repo_instance, scope=singleton)

        # Bind CertificateManager
        cert_impl = self.providers_settings.cert_manager.lower()
        if cert_impl in ("mock", "memory"):
            from roostos_engine.mock_cert_manager import MockCertificateManager
            cert_mgr = MockCertificateManager()
        else:
            cert_mgr = CertificateManager(cert_dir=self.cert_dir)
        binder.bind(CertificateManager, to=cert_mgr, scope=singleton)


def create_engine_injector(
    config_dir: str = "/etc/roostos",
    staged_dir: Optional[str] = None,
    cert_dir: Optional[str] = None,
    providers_settings: Optional[ProvidersSettings] = None,
    overrides: Optional[Dict[str, Any]] = None
) -> Injector:
    """Factory creating an Injector configured with EngineDIModule."""
    settings = providers_settings or load_providers_settings(config_dir, overrides=overrides)
    return Injector([EngineDIModule(config_dir, staged_dir, cert_dir, settings)])
