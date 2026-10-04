from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Body
from pydantic import BaseModel

from roostos_engine.models.node import (
    NodeJoinRequest,
    NodeJoinResponse,
    NodeHeartbeatRequest,
    NodeHeartbeatResponse,
    NodeConfigSlice,
)
from roostos_web.auth import get_current_user, get_current_admin, UserSession
from roostos_web.services.cluster import ClusterService
from roostos_web.di import Injected


router = APIRouter(prefix="/api/cluster", tags=["cluster"])


class NodeInterfaceSchema(BaseModel):
    name: str
    mac_address: Optional[str] = None
    type: str = "ethernet"
    network_id: Optional[str] = None
    mode: str = "unassigned"
    vlan_tag: Optional[int] = None
    bridge: Optional[str] = None


class NodeManagementSchema(BaseModel):
    id: str
    name: str
    roles: List[str] = ["gateway_router"]
    management_ip: Optional[str] = None
    mac_address: Optional[str] = None
    location_id: Optional[str] = None
    interfaces: List[NodeInterfaceSchema] = []


@router.get("/status")
async def get_cluster_status(
    current_user: UserSession = Depends(get_current_user),
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Returns the current node's cluster role, connectivity, and registered nodes."""
    return await cluster_service.get_cluster_status()


@router.get("/nodes")
async def get_nodes(
    current_user: UserSession = Depends(get_current_user),
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Returns list of registered cluster nodes."""
    nodes = await cluster_service.get_nodes()
    return {"nodes": nodes}


@router.post("/nodes")
async def save_node(
    node_data: NodeManagementSchema,
    current_user: UserSession = Depends(get_current_admin),
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Creates or updates a node configuration in nodes.yaml."""
    await cluster_service.save_node(node_data.model_dump())
    return {"status": "success", "message": f"Node '{node_data.name}' saved successfully."}


@router.delete("/nodes/{node_id}")
async def remove_node(
    node_id: str,
    current_user: UserSession = Depends(get_current_admin),
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Decommissions a node from the cluster."""
    await cluster_service.remove_node(node_id)
    return {"status": "success", "message": f"Node '{node_id}' removed successfully."}


@router.post("/token")
async def generate_join_token(
    current_user: UserSession = Depends(get_current_admin),
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Generates a temporary pairing join token."""
    token = await cluster_service.generate_join_token()
    return {"status": "success", "token": token, "expires_in_seconds": 600}


@router.post("/discover")
async def discover_controllers(
    current_user: UserSession = Depends(get_current_user),
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Scans the local network for existing RoostOS controllers via mDNS."""
    controllers = await cluster_service.discover_controllers()
    return {"controllers": controllers}


@router.get("/hardware")
async def get_detected_hardware(
    current_user: UserSession = Depends(get_current_admin),
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Returns detected physical network hardware adapters on the host."""
    hardware = await cluster_service.get_detected_hardware()
    return {"hardware": hardware}


@router.post("/join", response_model=NodeJoinResponse)
async def join_cluster(
    request: NodeJoinRequest,
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Enrolls and registers a worker node into the cluster via pre-shared token."""
    try:
        res = await cluster_service.join_cluster(request.model_dump())
        return NodeJoinResponse(**res)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/nodes/{node_id}/heartbeat", response_model=NodeHeartbeatResponse)
async def record_node_heartbeat(
    node_id: str,
    request: NodeHeartbeatRequest,
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Ingests periodic telemetry and health reports from a cluster node."""
    res = await cluster_service.record_heartbeat(node_id, request.model_dump())
    return NodeHeartbeatResponse(**res)


@router.get("/nodes/{node_id}/heartbeat")
async def get_node_heartbeat(
    node_id: str,
    current_user: UserSession = Depends(get_current_user),
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Returns the most recent recorded heartbeat telemetry for a node."""
    hb = await cluster_service.get_node_heartbeat(node_id)
    if not hb:
        raise HTTPException(status_code=404, detail=f"No heartbeat recorded for node '{node_id}'.")
    return hb


@router.get("/nodes/{node_id}/config", response_model=NodeConfigSlice)
async def get_node_config_slice(
    node_id: str,
    cluster_service: ClusterService = Injected(ClusterService)
):
    """Fetches the tailored configuration slice for a specific cluster node."""
    config_slice = await cluster_service.get_node_config_slice(node_id)
    return NodeConfigSlice(**config_slice)

