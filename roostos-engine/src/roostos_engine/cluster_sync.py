import os
import sys
import asyncio
import datetime
from typing import Dict, Any, List, Optional
import httpx

from roostos_engine.models.node import (
    NodeJoinRequest,
    NodeJoinResponse,
    NodeHeartbeatRequest,
    NodeHeartbeatResponse,
    NodeConfigSlice,
    NodeRole,
    NodeInterface,
    ClusterStateManifest,
)
from roostos_engine.cluster_replicator import ClusterReplicator


class ClusterSyncAgent:
    """Background agent running on worker nodes to sync state, telemetry, and configs with the controller."""

    def __init__(
        self,
        node_id: str,
        controller_url: str,
        sync_interval_seconds: int = 30,
        config_dir: str = "/etc/roostos",
        mock: bool = False,
        failover_priority: int = 0,
        auto_failover: bool = True,
        failover_threshold: int = 3,
    ):
        self.node_id = node_id
        self.controller_url = controller_url.rstrip("/")
        self.sync_interval_seconds = sync_interval_seconds
        self.config_dir = config_dir
        self.mock = mock
        self.failover_priority = failover_priority
        self.auto_failover = auto_failover
        self.failover_threshold = failover_threshold
        self.consecutive_heartbeat_failures = 0
        self.is_promoted_master = False
        self.replicator = ClusterReplicator(config_dir=config_dir, mock=mock)
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_heartbeat_time: Optional[str] = None
        self._last_heartbeat_status: Optional[str] = None
        self._last_config_slice: Optional[Dict[str, Any]] = None

    async def start(self) -> None:
        """Starts the periodic heartbeat and config sync background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._sync_loop())

    async def stop(self) -> None:
        """Stops the sync background loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _sync_loop(self) -> None:
        """Periodic loop that sends heartbeats, syncs state manifests, and monitors master health."""
        while self._running:
            try:
                hb_res = await self.send_heartbeat()
                self.consecutive_heartbeat_failures = 0
                for cmd in hb_res.get("commands", []):
                    await self.execute_command(cmd)

                slice_data = await self.fetch_config_slice()
                if slice_data:
                    await self.apply_config_slice(slice_data)

                # Anti-entropy state sync via hash manifest
                manifest = await self.fetch_manifest()
                if manifest and self.replicator.compare_manifest(manifest):
                    await self.replicator.sync_from_controller(self.controller_url)

            except Exception as e:
                self.consecutive_heartbeat_failures += 1
                print(f"ClusterSyncAgent failure ({self.consecutive_heartbeat_failures}) for {self.node_id}: {e}", file=sys.stderr)
                if self.auto_failover and self.consecutive_heartbeat_failures >= self.failover_threshold:
                    await self.evaluate_and_trigger_failover()

            await asyncio.sleep(self.sync_interval_seconds)

    async def fetch_manifest(self) -> Optional[ClusterStateManifest]:
        """Fetches the current cluster state manifest from the controller."""
        if self.mock and not self.controller_url.startswith("http"):
            return self.replicator.generate_manifest(epoch=1, master_node_id="master-01")

        url = f"{self.controller_url}/api/cluster/sync/manifest"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(url)
                if res.status_code == 200:
                    return ClusterStateManifest.model_validate(res.json())
        except Exception:
            pass
        return None

    async def evaluate_and_trigger_failover(self) -> bool:
        """Evaluates whether this node has eligible failover priority to assume master role."""
        if self.is_promoted_master or self.failover_priority <= 0:
            return False
        return await self.promote_to_master()

    async def promote_to_master(self) -> bool:
        """Promotes this node to cluster master and halts the subordinate sync agent."""
        self.is_promoted_master = True
        self._running = False
        print(f"Node '{self.node_id}' successfully promoted to cluster master!")
        return True

    async def execute_command(self, cmd: str) -> None:
        """Executes a remote command queued by the cluster controller."""
        if cmd in ("install_updates", "install_security_updates"):
            sec_only = (cmd == "install_security_updates")
            try:
                from roostos_engine.update_manager import UpdateManager
                mgr = UpdateManager(config_dir=self.config_dir, mock=self.mock)
                mgr.install_updates(security_only=sec_only)
            except Exception as e:
                print(f"Failed to execute command '{cmd}' on node {self.node_id}: {e}", file=sys.stderr)

    def _collect_local_telemetry(self) -> Dict[str, Any]:
        """Collects lightweight host telemetry for node heartbeat reporting."""
        if self.mock:
            return {
                "cpu_percent": 12.5,
                "memory_percent": 42.0,
                "disk_percent": 35.0,
                "uptime_seconds": 3600,
            }
        try:
            import psutil
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent,
                "uptime_seconds": int(psutil.boot_time()),
            }
        except ImportError:
            return {"cpu_percent": 0.0, "memory_percent": 0.0, "disk_percent": 0.0}

    async def send_heartbeat(
        self,
        status: str = "healthy",
        telemetry: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        updates_status: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Sends node heartbeat with health report to the central controller."""
        if updates_status is None:
            try:
                from roostos_engine.update_manager import UpdateManager
                mgr = UpdateManager(config_dir=self.config_dir, mock=self.mock)
                up_st = mgr.get_update_status()
                updates_status = up_st.model_dump()
            except Exception:
                pass

        payload = NodeHeartbeatRequest(
            status=status,
            telemetry=telemetry or self._collect_local_telemetry(),
            warnings=warnings or [],
            updates_status=updates_status,
        )

        if self.mock and not self.controller_url.startswith("http"):
            self._last_heartbeat_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._last_heartbeat_status = "acknowledged"
            return {"status": "acknowledged", "commands": []}

        url = f"{self.controller_url}/api/cluster/nodes/{self.node_id}/heartbeat"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload.model_dump())
            resp.raise_for_status()
            data = resp.json()
            self._last_heartbeat_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._last_heartbeat_status = data.get("status", "acknowledged")
            return data

    async def fetch_config_slice(self) -> Optional[Dict[str, Any]]:
        """Pulls the node-specific configuration slice from the controller."""
        if self.mock and not self.controller_url.startswith("http"):
            return {
                "node_id": self.node_id,
                "name": self.node_id,
                "roles": ["gateway_router"],
                "controller_url": self.controller_url,
                "dns_servers": ["1.1.1.1"],
                "interfaces": [],
                "bridges": [],
                "vlans": [],
                "wifi_access_points": [],
            }

        url = f"{self.controller_url}/api/cluster/nodes/{self.node_id}/config"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                self._last_config_slice = resp.json()
                return self._last_config_slice
            return None

    async def apply_config_slice(self, config_slice: Dict[str, Any]) -> bool:
        """Stores or applies the received config slice locally."""
        self._last_config_slice = config_slice
        return True

    async def join_cluster(
        self,
        token: str,
        name: str,
        roles: Optional[List[str]] = None,
        interfaces: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Submits pairing join request with token to register node with controller."""
        parsed_roles = [NodeRole(r) for r in (roles or ["gateway_router"])]
        parsed_ifaces = [NodeInterface.model_validate(i) for i in (interfaces or [])]

        join_req = NodeJoinRequest(
            token=token,
            node_id=self.node_id,
            name=name,
            roles=parsed_roles,
            interfaces=parsed_ifaces,
        )

        if self.mock and not self.controller_url.startswith("http"):
            return {
                "status": "success",
                "node_id": self.node_id,
                "controller_url": self.controller_url,
                "message": f"Node '{name}' joined cluster successfully.",
            }

        url = f"{self.controller_url}/api/cluster/join"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=join_req.model_dump())
            resp.raise_for_status()
            return resp.json()
