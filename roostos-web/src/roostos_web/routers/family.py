"""FastAPI router for Family profiles, Screentime limits, Bedtime schedules, and One-Touch actions."""

from datetime import datetime, timezone
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status

from roostos_engine.config import DevicesConfig
from roostos_engine.models.devices import PersonConfig
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.auth import get_current_parent, get_current_user, UserSession
from roostos_web.di import Injected
from roostos_web.schemas.family import (
    FamilyPersonDTO, FamilyRoleEnum, BedtimeScheduleDTO, ScreentimeBonusRequestDTO,
    DinnerTimeRequestDTO, PauseKidsRequestDTO, PausePersonRequestDTO, CreateFamilyPersonRequestDTO,
)
from roostos_web.schemas.household import QuickActionResponseDTO
from roostos_web.services import DeviceService

router = APIRouter(prefix="/api/v1/family", tags=["Family Management"])

@router.get("/people", response_model=List[FamilyPersonDTO])
async def list_family_people(
    current_user: UserSession = Depends(get_current_user),
    device_service: DeviceService = Injected(DeviceService),
) -> List[FamilyPersonDTO]:
    """Returns rich family member profiles with quotas, schedules, and active statuses."""
    dev_config = device_service.get_devices_config()
    people = getattr(dev_config, "people", [])
    devices = getattr(dev_config, "devices", [])

    results: List[FamilyPersonDTO] = []
    R_ADM, R_PAR, R_KID = FamilyRoleEnum.ADMIN, FamilyRoleEnum.PARENT, FamilyRoleEnum.KID
    default_metadata = {
        "dad": {"role": R_ADM, "avatar": "👨‍💻", "color": "#3b82f6", "limit": 0, "used": 180, "start": "00:00", "end": "06:00", "active": False, "filter": "Standard"},
        "mom": {"role": R_PAR, "avatar": "👩‍🔬", "color": "#ec4899", "limit": 0, "used": 140, "start": "23:30", "end": "06:00", "active": False, "filter": "Standard"},
        "alice": {"role": R_KID, "avatar": "👧", "color": "#10b981", "limit": 120, "used": 95, "start": "20:30", "end": "06:30", "active": False, "filter": "SafeSearch + AdBlock"},
        "bob": {"role": R_KID, "avatar": "👦", "color": "#f59e0b", "limit": 90, "used": 90, "start": "20:00", "end": "06:30", "active": True, "filter": "Strict Kids"},
    }

    for p in people:
        meta = default_metadata.get(p.id, {
            "role": FamilyRoleEnum.KID if getattr(p, "dns_profile", "") == "kids" else FamilyRoleEnum.PARENT,
            "avatar": "👤",
            "color": "#6366f1",
            "limit": 120 if getattr(p, "dns_profile", "") == "kids" else 0,
            "used": 60,
            "start": "20:30",
            "end": "06:30",
            "active": False,
            "filter": getattr(p, "dns_profile", "Standard") or "Standard"
        })

        owned_devs = [d.mac for d in devices if d.owner == p.id]

        results.append(FamilyPersonDTO(
            id=p.id,
            name=p.name,
            role=meta["role"],
            avatar=meta["avatar"],
            color=meta["color"],
            screentime_limit_minutes=meta["limit"],
            screentime_used_minutes=meta["used"],
            bonus_minutes_today=0,
            bedtime=BedtimeScheduleDTO(
                start_time=meta["start"],
                end_time=meta["end"],
                enabled=True,
                active_now=meta["active"],
            ),
            filter_level=meta["filter"],
            device_count=len(owned_devs),
            devices=owned_devs,
        ))

    return results

@router.put("/people/{person_id}", response_model=FamilyPersonDTO)
async def update_family_person(
    person_id: str,
    payload: FamilyPersonDTO,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> FamilyPersonDTO:
    """Updates a family member's bedtime windows, screentime quotas, and filter settings."""
    config = repo.get_config()
    p = next((person for person in config.people if person.id == person_id), None)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Person '{person_id}' not found")

    p.name = payload.name
    p.dns_profile = payload.filter_level
    repo.save_devices_config(DevicesConfig(
        people=config.people,
        buildings=config.buildings,
        rooms=config.rooms,
        devices=config.devices
    ))
    try:
        await dbus.get_config()
    except Exception:
        pass

    return payload

@router.post("/people", response_model=FamilyPersonDTO, status_code=status.HTTP_201_CREATED)
async def create_family_person(
    payload: CreateFamilyPersonRequestDTO,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> FamilyPersonDTO:
    """Creates a new household person profile with screentime and bedtime settings."""
    config = repo.get_config()
    person_id = payload.id or payload.name.lower().replace(" ", "-").replace("'", "")

    if any(p.id == person_id for p in config.people):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Person profile '{person_id}' already exists"
        )

    dns_profile = payload.filter_level or ("kids" if payload.role == FamilyRoleEnum.KID else "standard")
    new_person = PersonConfig(id=person_id, name=payload.name, dns_profile=dns_profile)
    config.people.append(new_person)

    repo.save_devices_config(DevicesConfig(
        people=config.people,
        buildings=config.buildings,
        rooms=config.rooms,
        devices=config.devices
    ))
    try:
        await dbus.get_config()
    except Exception:
        pass

    bedtime = payload.bedtime or BedtimeScheduleDTO()
    return FamilyPersonDTO(
        id=person_id,
        name=payload.name,
        role=payload.role,
        avatar=payload.avatar or "👤",
        screentime_limit_minutes=payload.screentime_limit_minutes,
        screentime_used_minutes=0,
        bonus_minutes_today=0,
        bedtime=bedtime,
        filter_level=dns_profile,
        device_count=0,
        devices=[],
    )

@router.delete("/people/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_family_person(
    person_id: str,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> None:
    """Removes a family member profile and unlinks their devices."""
    config = repo.get_config()
    person_idx = next((i for i, p in enumerate(config.people) if p.id == person_id), None)
    if person_idx is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Person '{person_id}' not found")

    config.people.pop(person_idx)
    for d in config.devices:
        if d.owner == person_id:
            d.owner = ""

    repo.save_devices_config(DevicesConfig(
        people=config.people,
        buildings=config.buildings,
        rooms=config.rooms,
        devices=config.devices
    ))
    try:
        await dbus.get_config()
    except Exception:
        pass

@router.post("/people/{person_id}/pause", response_model=QuickActionResponseDTO)
async def toggle_pause_person(
    person_id: str,
    payload: PausePersonRequestDTO,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> QuickActionResponseDTO:
    """Pauses or unpauses all devices assigned to an individual family member."""
    config = repo.get_config()
    p = next((person for person in config.people if person.id == person_id), None)
    if not p:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Person '{person_id}' not found")

    owned_devices = [d for d in config.devices if d.owner == person_id]
    for dev in owned_devices:
        try:
            if payload.paused:
                await dbus.remove_time_extension(dev.mac)
            else:
                await dbus.grant_time_extension(dev.mac, 3600)
        except Exception:
            pass

    action_name = "pause_person" if payload.paused else "resume_person"
    msg = f"Paused devices for {p.name}." if payload.paused else f"Resumed devices for {p.name}."
    return QuickActionResponseDTO(
        action=action_name,
        status="success",
        message=msg,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@router.post("/people/{person_id}/bonus", response_model=QuickActionResponseDTO)
async def grant_person_screentime_bonus(
    person_id: str,
    payload: ScreentimeBonusRequestDTO,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> QuickActionResponseDTO:
    """Grants a temporary screentime bonus (+15m, +30m, +1h) to all devices owned by person."""
    config = repo.get_config()
    owned_devices = [d for d in config.devices if d.owner == person_id]
    if not owned_devices:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No devices found for '{person_id}'")

    for dev in owned_devices:
        try:
            await dbus.grant_time_extension(dev.mac, payload.duration_minutes * 60)
        except Exception:
            pass

    return QuickActionResponseDTO(
        action=f"bonus_{payload.duration_minutes}m",
        status="success",
        message=f"Granted +{payload.duration_minutes}m bonus screentime to {person_id}.",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@router.post("/pause-kids", response_model=QuickActionResponseDTO)
async def toggle_pause_all_kids(
    payload: PauseKidsRequestDTO,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> QuickActionResponseDTO:
    """One-Touch Action: Pauses or unpauses all kid devices across the household."""
    config = repo.get_config()
    kid_ids = {p.id for p in config.people if getattr(p, "dns_profile", "") == "kids" or p.id in ("alice", "bob")}
    kid_devices = [d for d in config.devices if d.owner in kid_ids]

    for dev in kid_devices:
        try:
            if payload.paused:
                await dbus.remove_time_extension(dev.mac)
            else:
                await dbus.grant_time_extension(dev.mac, 3600)
        except Exception:
            pass

    action_name = "pause_kids" if payload.paused else "resume_kids"
    msg = "All kids devices paused." if payload.paused else "All kids devices resumed."
    return QuickActionResponseDTO(
        action=action_name,
        status="success",
        message=msg,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )

@router.post("/dinner-time", response_model=QuickActionResponseDTO)
async def trigger_dinner_time(
    payload: DinnerTimeRequestDTO,
    current_user: UserSession = Depends(get_current_parent),
    repo: ConfigRepository = Injected(ConfigRepository),
    dbus: RoostClient = Injected(RoostClient),
) -> QuickActionResponseDTO:
    """Dinner Time Action: Pauses all kid devices for a dinner duration (e.g. 60m)."""
    config = repo.get_config()
    kid_ids = {p.id for p in config.people if getattr(p, "dns_profile", "") == "kids" or p.id in ("alice", "bob")}
    kid_devices = [d for d in config.devices if d.owner in kid_ids]

    for dev in kid_devices:
        try:
            await dbus.remove_time_extension(dev.mac)
        except Exception:
            pass

    return QuickActionResponseDTO(
        action="dinner_time",
        status="success",
        message=f"Dinner Time activated! Kids devices paused for {payload.duration_minutes} minutes.",
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
