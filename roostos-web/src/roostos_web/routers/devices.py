from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body

from roostos_engine.config import (
    DevicesConfig, DeviceConfig, PersonConfig, BuildingConfig, RoomConfig
)
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_user, get_current_parent, UserSession
from roostos_web.services import DeviceService
from roostos_web.di import Injected

router = APIRouter(tags=["devices"])

@router.get("/api/devices")
async def get_devices(
    current_user: UserSession = Depends(get_current_user),
    device_service: DeviceService = Injected(DeviceService)
):
    """Returns registered device list along with active DHCP leases and active ARP table entries."""
    config = device_service.get_devices_config()
    active_leases = await device_service.get_active_leases()
    active_arp = device_service.get_active_arp()
    return {
        "devices": [d.model_dump() for d in config.devices],
        "active_leases": active_leases,
        "active_arp": active_arp
    }

@router.post("/api/devices")
async def register_device(
    mac: str = Body(...),
    name: str = Body(...),
    owner: str = Body(""),
    location: str = Body(""),
    tags: List[str] = Body([]),
    static_ip: str = Body(""),
    upnp_trusted: bool = Body(False),
    max_upload_kbps: Optional[int] = Body(None),
    max_download_kbps: Optional[int] = Body(None),
    current_user: UserSession = Depends(get_current_parent),
    device_service: DeviceService = Injected(DeviceService)
):
    """Registers or updates a device profile by saving configuration and triggering daemon reload."""
    config = device_service.get_devices_config()
    
    try:
        norm_mac = DeviceConfig.normalize_mac(mac)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid MAC address: {e}")

    if owner and not any(p.id == owner for p in config.people):
        raise HTTPException(status_code=400, detail=f"Owner '{owner}' does not exist.")
    if location and not any(r.id == location for r in config.rooms):
        raise HTTPException(status_code=400, detail=f"Location '{location}' does not exist.")

    device = next((d for d in config.devices if d.mac == norm_mac), None)
    if device:
        device.name = name
        device.owner = owner if owner else None
        device.location = location if location else None
        device.tags = tags
        device.static_ip = static_ip if static_ip else None
        device.upnp_trusted = upnp_trusted
        device.max_upload_kbps = max_upload_kbps
        device.max_download_kbps = max_download_kbps
    else:
        new_device = DeviceConfig(
            mac=norm_mac,
            name=name,
            owner=owner if owner else None,
            location=location if location else None,
            tags=tags,
            static_ip=static_ip if static_ip else None,
            upnp_trusted=upnp_trusted,
            max_upload_kbps=max_upload_kbps,
            max_download_kbps=max_download_kbps
        )
        config.devices.append(new_device)

    device_service.save_devices_config(config)
    await device_service.trigger_config_reload()
    return {"status": "success"}

@router.delete("/api/devices/{mac}")
async def delete_device(
    mac: str,
    current_user: UserSession = Depends(get_current_parent),
    dbus: RoostClient = Injected(RoostClient)
):
    """Removes a registered device profile by MAC address."""
    success = await dbus.delete_device(mac)
    if not success:
        raise HTTPException(status_code=400, detail="Failed to delete device.")
    return {"status": "success"}

@router.get("/api/people")
async def get_people(
    current_user: UserSession = Depends(get_current_user),
    device_service: DeviceService = Injected(DeviceService)
):
    """Returns the list of registered family profile people."""
    config = device_service.get_devices_config()
    return {"people": [p.model_dump() for p in config.people]}

@router.post("/api/people")
async def save_person(
    id: str = Body(...),
    name: str = Body(...),
    dns_profile: Optional[str] = Body(None),
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Creates or updates a family member profile."""
    config = repo.get_config()
    people = config.people
    person_idx = next((i for i, p in enumerate(people) if p.id == id), None)
    new_person = PersonConfig(id=id, name=name, dns_profile=dns_profile)
    if person_idx is not None:
        people[person_idx] = new_person
    else:
        people.append(new_person)
    
    devices_config_obj = DevicesConfig(
        people=people,
        buildings=config.buildings,
        rooms=config.rooms,
        devices=config.devices
    )
    repo.save_devices_config(devices_config_obj)
    await dbus.get_config()
    return {"status": "success"}

@router.delete("/api/people/{person_id}")
async def delete_person(
    person_id: str,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Removes a family member profile."""
    config = repo.get_config()
    people = config.people
    person_idx = next((i for i, p in enumerate(people) if p.id == person_id), None)
    if person_idx is None:
        raise HTTPException(status_code=404, detail="Person not found")
    people.pop(person_idx)
    
    devices_config_obj = DevicesConfig(
        people=people,
        buildings=config.buildings,
        rooms=config.rooms,
        devices=config.devices
    )
    repo.save_devices_config(devices_config_obj)
    await dbus.get_config()
    return {"status": "success"}

@router.get("/api/buildings")
async def get_buildings(
    current_user: UserSession = Depends(get_current_user),
    device_service: DeviceService = Injected(DeviceService)
):
    """Returns the list of configured physical buildings/structures."""
    config = device_service.get_devices_config()
    return {"buildings": [b.model_dump() for b in config.buildings]}

@router.post("/api/buildings")
async def save_building(
    id: str = Body(...),
    name: str = Body(...),
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Creates or updates a building profile."""
    config = repo.get_config()
    buildings = config.buildings
    b_idx = next((i for i, b in enumerate(buildings) if b.id == id), None)
    new_b = BuildingConfig(id=id, name=name)
    if b_idx is not None:
        buildings[b_idx] = new_b
    else:
        buildings.append(new_b)
        
    devices_config_obj = DevicesConfig(
        people=config.people,
        buildings=buildings,
        rooms=config.rooms,
        devices=config.devices
    )
    repo.save_devices_config(devices_config_obj)
    await dbus.get_config()
    return {"status": "success"}

@router.delete("/api/buildings/{building_id}")
async def delete_building(
    building_id: str,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Removes a building profile."""
    config = repo.get_config()
    buildings = config.buildings
    b_idx = next((i for i, b in enumerate(buildings) if b.id == building_id), None)
    if b_idx is None:
        raise HTTPException(status_code=404, detail="Building not found")
    buildings.pop(b_idx)
    
    devices_config_obj = DevicesConfig(
        people=config.people,
        buildings=buildings,
        rooms=config.rooms,
        devices=config.devices
    )
    repo.save_devices_config(devices_config_obj)
    await dbus.get_config()
    return {"status": "success"}

@router.get("/api/rooms")
async def get_rooms(
    current_user: UserSession = Depends(get_current_user),
    device_service: DeviceService = Injected(DeviceService)
):
    """Returns the list of rooms/locations inside buildings."""
    config = device_service.get_devices_config()
    return {"rooms": [r.model_dump() for r in config.rooms]}

@router.post("/api/rooms")
async def save_room(
    id: str = Body(...),
    name: str = Body(...),
    building: str = Body(...),
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Creates or updates a room configuration."""
    config = repo.get_config()
    rooms = config.rooms
    r_idx = next((i for i, r in enumerate(rooms) if r.id == id), None)
    new_r = RoomConfig(id=id, name=name, building=building)
    if r_idx is not None:
        rooms[r_idx] = new_r
    else:
        rooms.append(new_r)
        
    devices_config_obj = DevicesConfig(
        people=config.people,
        buildings=config.buildings,
        rooms=rooms,
        devices=config.devices
    )
    repo.save_devices_config(devices_config_obj)
    await dbus.get_config()
    return {"status": "success"}

@router.delete("/api/rooms/{room_id}")
async def delete_room(
    room_id: str,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient)
):
    """Removes a room configuration."""
    config = repo.get_config()
    rooms = config.rooms
    r_idx = next((i for i, r in enumerate(rooms) if r.id == room_id), None)
    if r_idx is None:
        raise HTTPException(status_code=404, detail="Room not found")
    rooms.pop(r_idx)
    
    devices_config_obj = DevicesConfig(
        people=config.people,
        buildings=config.buildings,
        rooms=rooms,
        devices=config.devices
    )
    repo.save_devices_config(devices_config_obj)
    await dbus.get_config()
    return {"status": "success"}
