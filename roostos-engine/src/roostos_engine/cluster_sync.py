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
)


class ClusterSyncAgent:
    """Background agent running on worker nodes to sync state, telemetry, and configs with the controller."""

    def __init__(
        self,
        node_id: str,
        controller_url: str,
        sync_interval_seconds: int = 30,
        config_dir: str = "/etc/roostos",
        mock: bool = False,
    ):
        self.node_id = node_id
        self.controller_url = controller_url.rstrip("/")
        self.sync_interval_seconds = sync_interval_seconds
        self.config_dir = config_dir
        self.mock = mock
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
        """Periodic loop that sends heartbeats and pulls node configuration."""
        while self._running:
            try:
                await self.send_heartbeat()
                slice_data = await self.fetch_config_slice()
                if slice_data:
                    await self.apply_config_slice(slice_data)
            except Exception as e:
                print(f"ClusterSyncAgent error for node {self.node_id}: {e}", file=sys.stderr)
            await asyncio.sleep(self.sync_interval_seconds)

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
