"""FastAPI router for ISC Kea 2.4 Multi-Network DHCP Scopes, Leases, and Reservations."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status

from roostos_web.auth import get_current_parent, get_current_admin, UserSession
from roostos_web.di import Injected
from roostos_web.schemas.dhcp import (
    DhcpScopeDTO,
    DhcpLeaseDTO,
    DhcpReservationDTO,
    ConvertLeaseRequestDTO,
)
from roostos_web.services.kea_service import KeaService

router = APIRouter(prefix="/api/v1/dhcp", tags=["DHCP"])


@router.get("/scopes", response_model=List[DhcpScopeDTO])
async def list_dhcp_scopes(
    current_user: UserSession = Depends(get_current_parent),
    kea_service: KeaService = Injected(KeaService),
) -> List[DhcpScopeDTO]:
    """Returns all configured multi-subnet DHCP scopes with live lease counts."""
    return await kea_service.get_scopes()


@router.post("/scopes", response_model=DhcpScopeDTO, status_code=status.HTTP_201_CREATED)
async def create_dhcp_scope(
    scope_data: DhcpScopeDTO,
    current_user: UserSession = Depends(get_current_admin),
    kea_service: KeaService = Injected(KeaService),
) -> DhcpScopeDTO:
    """Creates a new subnet scope and enables DHCP service."""
    return await kea_service.create_scope(scope_data)


@router.put("/scopes/{scope_id}", response_model=DhcpScopeDTO)
async def update_dhcp_scope(
    scope_id: str,
    scope_data: DhcpScopeDTO,
    current_user: UserSession = Depends(get_current_admin),
    kea_service: KeaService = Injected(KeaService),
) -> DhcpScopeDTO:
    """Updates an existing DHCP scope configuration (in-place row edit)."""
    if scope_id != scope_data.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Scope ID mismatch")
    return await kea_service.update_scope(scope_data)


@router.get("/leases", response_model=List[DhcpLeaseDTO])
async def get_active_leases(
    node_id: Optional[str] = None,
    current_user: UserSession = Depends(get_current_parent),
    kea_service: KeaService = Injected(KeaService),
) -> List[DhcpLeaseDTO]:
    """Returns currently allocated dynamic DHCP client leases."""
    return await kea_service.get_leases(node_id=node_id)


@router.post("/reservations/from-lease", response_model=DhcpReservationDTO)
async def convert_lease_to_static(
    payload: ConvertLeaseRequestDTO,
    current_user: UserSession = Depends(get_current_admin),
    kea_service: KeaService = Injected(KeaService),
) -> DhcpReservationDTO:
    """1-Click action: Converts an active dynamic lease into a permanent static MAC reservation."""
    reservation = await kea_service.convert_lease_to_static(
        mac=payload.mac,
        hostname=payload.hostname,
        description=payload.description,
    )
    if not reservation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No active dynamic lease found matching MAC address {payload.mac}",
        )
    return reservation


@router.get("/reservations", response_model=List[DhcpReservationDTO])
async def list_reservations(
    current_user: UserSession = Depends(get_current_parent),
    kea_service: KeaService = Injected(KeaService),
) -> List[DhcpReservationDTO]:
    """Returns all static IP reservations defined across devices."""
    return await kea_service.get_reservations()


@router.post("/reservations", response_model=DhcpReservationDTO, status_code=status.HTTP_201_CREATED)
async def create_reservation(
    payload: DhcpReservationDTO,
    current_user: UserSession = Depends(get_current_admin),
    kea_service: KeaService = Injected(KeaService),
) -> DhcpReservationDTO:
    """Creates a new static reservation binding a MAC to a fixed IP."""
    res = await kea_service.convert_lease_to_static(
        mac=payload.mac,
        hostname=payload.hostname,
        description=payload.description,
    )
    if not res:
        # If no dynamic lease exists, save directly
        config = kea_service.repo.get_config()
        from roostos_engine.config import DeviceConfig, DevicesConfig
        norm_mac = payload.mac.strip().lower()
        dev = next((d for d in config.devices if d.mac.lower() == norm_mac), None)
        if dev:
            dev.static_ip = payload.reserved_ip
            if payload.hostname:
                dev.name = payload.hostname
        else:
            config.devices.append(DeviceConfig(
                mac=norm_mac,
                name=payload.hostname or f"Device-{norm_mac[-4:]}",
                static_ip=payload.reserved_ip,
                tags=["reservation"],
            ))
        kea_service.repo.save_devices_config(DevicesConfig(
            people=config.people,
            buildings=config.buildings,
            rooms=config.rooms,
            devices=config.devices
        ))
        await kea_service._trigger_reload()
        return payload
    return res


@router.delete("/reservations/{mac}")
async def delete_reservation(
    mac: str,
    current_user: UserSession = Depends(get_current_admin),
    kea_service: KeaService = Injected(KeaService),
) -> Dict[str, str]:
    """Removes a static reservation by MAC address."""
    config = kea_service.repo.get_config()
    from roostos_engine.config import DevicesConfig
    norm_mac = mac.strip().lower()
    dev = next((d for d in config.devices if d.mac.lower() == norm_mac), None)
    if not dev or not dev.static_ip:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Reservation for MAC {mac} not found")
    
    dev.static_ip = None
    kea_service.repo.save_devices_config(DevicesConfig(
        people=config.people,
        buildings=config.buildings,
        rooms=config.rooms,
        devices=config.devices
    ))
    await kea_service._trigger_reload()
    return {"status": "success", "message": f"Reservation for MAC {mac} removed"}
