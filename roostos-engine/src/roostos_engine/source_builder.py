"""SourceBuilder for cloning repositories, parsing manifests, and building Docker images."""

import os
import sys
import subprocess
from typing import Optional, Dict, Tuple, Any
import yaml

from roostos_engine.models.catalog import (
    PackageManifest,
    SourceBuildSpec,
    ImportFromSourceRequest,
    InstallFromSourceRequest,
    CatalogContainerSpec,
    CatalogAppEntry,
    BuildManifest,
    SandboxConfig,
)
from roostos_engine.build_sandbox import execute_sandboxed_build
from roostos_engine.models.plugins import (
    PluginConfig,
    ContainerConfig,
    PortMapping,
    VolumeMount,
)
from roostos_engine.ingress_helper import provision_ingress_route


class SourceBuilder:
    """Handles git cloning, manifest discovery, and building local Docker images from source."""

    def __init__(self, sources_dir: Optional[str] = None):
        self.sources_dir = sources_dir or os.environ.get(
            "ROOSTOS_SOURCES_DIR", "/var/lib/roostos/sources"
        )
        try:
            os.makedirs(self.sources_dir, exist_ok=True)
        except PermissionError:
            self.sources_dir = f"/tmp/roostos_sources_{os.getuid()}"
            os.makedirs(self.sources_dir, exist_ok=True)

    def clone_or_resolve_source(
        self, source_url_or_path: str, git_ref: str = "main", dir_name_override: Optional[str] = None
    ) -> str:
        """Clones a remote git repository or returns absolute local directory path."""
        if os.path.isdir(source_url_or_path):
            return os.path.abspath(source_url_or_path)

        clean_name = dir_name_override or os.path.splitext(
            os.path.basename(source_url_or_path.rstrip("/"))
        )[0]
        dest_path = os.path.join(self.sources_dir, clean_name)

        if os.path.exists(os.path.join(dest_path, ".git")):
            try:
                subprocess.run(["git", "fetch", "--depth", "1", "origin", git_ref], cwd=dest_path, check=True, capture_output=True, text=True)
                subprocess.run(["git", "checkout", git_ref], cwd=dest_path, check=True, capture_output=True, text=True)
            except Exception as e:
                print(f"Warning: Git fetch/checkout in {dest_path} had issue: {e}", file=sys.stderr)
        else:
            os.makedirs(dest_path, exist_ok=True)
            cmd = ["git", "clone", "--depth", "1", "-b", git_ref, source_url_or_path, dest_path]
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode != 0:
                cmd_fallback = ["git", "clone", "--depth", "1", source_url_or_path, dest_path]
                res2 = subprocess.run(cmd_fallback, capture_output=True, text=True)
                if res2.returncode != 0:
                    raise RuntimeError(f"Git clone failed for {source_url_or_path}: {res.stderr}\n{res2.stderr}")

        return dest_path

    def get_head_commit(self, repo_dir: str) -> str:
        """Returns the current HEAD commit hash of the git repository."""
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=repo_dir, capture_output=True, text=True
            )
            if res.returncode == 0:
                return res.stdout.strip()[:8]
        except Exception:
            pass
        return ""

    def load_manifest(self, repo_dir: str) -> Optional[PackageManifest]:
        """Loads and parses roost-build.yaml and roost-app.yaml from directory if present."""
        build_manifest: Optional[BuildManifest] = None
        for bname in ["roost-build.yaml", "roost-build.yml"]:
            bcandidate = os.path.join(repo_dir, bname)
            if os.path.isfile(bcandidate):
                try:
                    with open(bcandidate, "r") as f:
                        bdata = yaml.safe_load(f) or {}
                    build_manifest = BuildManifest.model_validate(bdata)
                    break
                except Exception as e:
                    raise ValueError(f"Failed to parse build manifest at {bcandidate}: {e}")

        manifest_filenames = ["roost-app.yaml", "roost-app.yml", "roost-manifest.yaml", "roost-manifest.yml"]
        for name in manifest_filenames:
            candidate = os.path.join(repo_dir, name)
            if os.path.isfile(candidate):
                try:
                    with open(candidate, "r") as f:
                        data = yaml.safe_load(f) or {}
                    pkg_manifest = PackageManifest.model_validate(data)
                    if build_manifest:
                        pkg_manifest.build = build_manifest.to_source_build_spec()
                    return pkg_manifest
                except Exception as e:
                    raise ValueError(f"Failed to parse manifest at {candidate}: {e}")

        if build_manifest:
            app_id = build_manifest.app_id or os.path.basename(repo_dir.rstrip("/")).lower().replace("_", "-")
            return PackageManifest(
                id=app_id,
                name=app_id.replace("-", " ").title(),
                version="0.1.0",
                description="Application built from source via roost-build.yaml",
                build=build_manifest.to_source_build_spec(),
                container=CatalogContainerSpec(image=f"roostos-local/{app_id}:0.1.0", pull_policy="never"),
            )

        dockerfile = os.path.join(repo_dir, "Dockerfile")
        if os.path.isfile(dockerfile):
            app_id = os.path.basename(repo_dir.rstrip("/")).lower().replace("_", "-")
            return PackageManifest(
                id=app_id,
                name=app_id.replace("-", " ").title(),
                version="0.1.0",
                description="Application built from source",
                build=SourceBuildSpec(dockerfile="Dockerfile", context_path=".", sandbox=SandboxConfig()),
                container=CatalogContainerSpec(image=f"roostos-local/{app_id}:0.1.0", pull_policy="never"),
            )
        return None

    def build_docker_image(
        self, context_path: str, dockerfile: str, image_tag: str,
        build_args: Dict[str, str], target_stage: Optional[str] = None,
        sandbox_config: Optional[SandboxConfig] = None, builder: str = "dockerfile",
    ) -> Tuple[bool, str]:
        """Builds a Docker image within a secure sandbox enforcing resource limits and safety."""
        return execute_sandboxed_build(
            context_path=context_path, dockerfile=dockerfile, image_tag=image_tag,
            build_args=build_args, sandbox_config=sandbox_config,
            target_stage=target_stage, builder=builder,
        )

    def import_to_catalog(
        self, req: ImportFromSourceRequest, catalog_mgr: Any
    ) -> Tuple[CatalogAppEntry, str]:
        """Clones source, verifies safety, builds container, and registers in local catalog."""
        repo_dir = self.clone_or_resolve_source(req.source_url_or_path, req.git_ref, req.app_id_override)
        commit_sha = self.get_head_commit(repo_dir)

        manifest = self.load_manifest(repo_dir)
        if not manifest:
            raise ValueError(f"No roost-app.yaml manifest or Dockerfile found at '{req.source_url_or_path}'.")

        if req.app_id_override:
            manifest.id = req.app_id_override

        build_spec = manifest.build or SourceBuildSpec(
            dockerfile=req.dockerfile, context_path=req.context_path,
            build_args=req.build_args, sandbox=req.sandbox or SandboxConfig(),
        )
        if req.build_args:
            build_spec.build_args.update(req.build_args)
        if req.sandbox:
            build_spec.sandbox = req.sandbox
        if req.approve_network:
            build_spec.sandbox.user_approved = True
            if req.approved_endpoints:
                build_spec.sandbox.approved_endpoints = req.approved_endpoints

        if build_spec.sandbox.network_required and not build_spec.sandbox.user_approved:
            raise PermissionError(
                f"Build requires network access to {build_spec.sandbox.allowed_endpoints} "
                f"('{build_spec.sandbox.network_justification}'), but network access has not been approved."
            )

        context_abs = os.path.abspath(os.path.join(repo_dir, build_spec.context_path))
        dockerfile_abs = build_spec.dockerfile if os.path.isabs(build_spec.dockerfile) else os.path.join(repo_dir, build_spec.dockerfile)
        image_tag = manifest.container.image if manifest.container and manifest.container.image and not manifest.container.image.startswith("roostos-local/") else f"roostos-local/{manifest.id}:{manifest.version}"

        success, logs = self.build_docker_image(
            context_path=context_abs, dockerfile=dockerfile_abs, image_tag=image_tag,
            build_args=build_spec.build_args, target_stage=build_spec.target_stage,
            sandbox_config=build_spec.sandbox,
        )
        if not success:
            raise RuntimeError(f"Failed to build image {image_tag}:\n{logs}")

        app_entry = manifest.to_app_entry(catalog_id="local")
        app_entry.source_repo = req.source_url_or_path
        app_entry.source_ref = req.git_ref
        app_entry.last_commit_built = commit_sha
        app_entry.container.image = image_tag
        app_entry.container.pull_policy = "never"
        catalog_mgr.add_local_app(app_entry)

        return app_entry, logs

    def check_app_updates(self, app: CatalogAppEntry) -> Tuple[bool, Optional[str]]:
        """Checks if a newer commit exists for an imported application in remote git."""
        if not app.source_repo:
            return False, None
        try:
            cmd = ["git", "ls-remote", app.source_repo, f"refs/heads/{app.source_ref}"]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if res.returncode == 0 and res.stdout.strip():
                remote_sha = res.stdout.strip().split()[0][:8]
                has_update = bool(app.last_commit_built and remote_sha != app.last_commit_built)
                return has_update, remote_sha
        except Exception:
            pass
        return False, None

    def build_and_prepare_plugin(
        self, req: InstallFromSourceRequest
    ) -> Tuple[PluginConfig, Optional[PackageManifest], str]:
        """Resolves source, discovers/synthesizes manifest, builds container, and outputs PluginConfig."""
        repo_dir = self.clone_or_resolve_source(req.source_url_or_path, req.git_ref, req.app_id_override)
        manifest = self.load_manifest(repo_dir)
        if not manifest:
            raise ValueError(f"No roost-app.yaml manifest or Dockerfile found at '{req.source_url_or_path}'.")

        if req.app_id_override:
            manifest.id = req.app_id_override

        build_spec = manifest.build or SourceBuildSpec(
            dockerfile=req.dockerfile, context_path=req.context_path,
            build_args=req.build_args, sandbox=req.sandbox or SandboxConfig(),
        )
        if req.build_args:
            build_spec.build_args.update(req.build_args)
        if req.sandbox:
            build_spec.sandbox = req.sandbox
        if req.approve_network:
            build_spec.sandbox.user_approved = True
            if req.approved_endpoints:
                build_spec.sandbox.approved_endpoints = req.approved_endpoints

        if build_spec.sandbox.network_required and not build_spec.sandbox.user_approved:
            raise PermissionError(
                f"Build requires network access to {build_spec.sandbox.allowed_endpoints} "
                f"('{build_spec.sandbox.network_justification}'), but network access has not been approved."
            )

        context_abs = os.path.abspath(os.path.join(repo_dir, build_spec.context_path))
        dockerfile_abs = build_spec.dockerfile if os.path.isabs(build_spec.dockerfile) else os.path.join(repo_dir, build_spec.dockerfile)
        image_tag = manifest.container.image if manifest.container and manifest.container.image and not manifest.container.image.startswith("roostos-local/") else f"roostos-local/{manifest.id}:{manifest.version}"

        success, logs = self.build_docker_image(
            context_path=context_abs, dockerfile=dockerfile_abs, image_tag=image_tag,
            build_args=build_spec.build_args, target_stage=build_spec.target_stage,
            sandbox_config=build_spec.sandbox,
        )
        if not success:
            raise RuntimeError(f"Failed to build image {image_tag}:\n{logs}")

        base_container = manifest.container or CatalogContainerSpec(image=image_tag, pull_policy="never")
        container_ports = [
            PortMapping(host_port=req.custom_ports.get(p.container_port, p.host_port), container_port=p.container_port, protocol=p.protocol)
            for p in base_container.ports
        ]
        env = base_container.environment.copy()
        env.update(req.custom_environment)

        container_config = ContainerConfig(
            name=f"app-{manifest.id}", image=image_tag, pull_policy="never",
            ports=container_ports, volumes=base_container.volumes, environment=env,
        )
        plugin = PluginConfig(
            id=manifest.id, name=manifest.name, type="application", enabled=True,
            network_mode=base_container.network_mode, requested_scopes=manifest.requested_scopes,
            containers=[container_config],
            settings={"source": req.source_url_or_path, "ref": req.git_ref, "version": manifest.version, "built_from_source": True},
        )
        return plugin, manifest, logs
