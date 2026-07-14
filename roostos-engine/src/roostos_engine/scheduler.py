import datetime
from typing import List, Set
from roostos_engine.config import RoostConfig, ScheduleConfig, DeviceConfig

def is_schedule_active(sched: ScheduleConfig, current_dt: datetime.datetime) -> bool:
    """Returns True if current_dt falls within the schedule's defined time window and day constraints."""
    if not sched.start_time or not sched.end_time:
        return False
        
    now_hm = (current_dt.hour, current_dt.minute)
    
    try:
        sh, sm = map(int, sched.start_time.split(":"))
        eh, em = map(int, sched.end_time.split(":"))
    except ValueError:
        return False
        
    start_hm = (sh, sm)
    end_hm = (eh, em)
    
    day_today = current_dt.strftime("%A").lower()
    
    # Calculate yesterday's day name in case of overnight windows
    yesterday_dt = current_dt - datetime.timedelta(days=1)
    day_yesterday = yesterday_dt.strftime("%A").lower()
    
    is_overnight = (end_hm < start_hm)
    
    # Normalize days list to lowercase
    days = [d.lower() for d in sched.days]
    
    if not is_overnight:
        # Same day matching
        if day_today in days:
            return start_hm <= now_hm <= end_hm
        return False
    else:
        # Overnight matching
        # Latter half: midnight to end_time (started yesterday)
        if now_hm <= end_hm:
            return day_yesterday in days
        # Starting half: start_time to midnight (starts today)
        if now_hm >= start_hm:
            return day_today in days
        return False


def resolve_schedule_targets(sched: ScheduleConfig, config: RoostConfig) -> Set[str]:
    """Resolves all target MAC addresses affected by a schedule, expanding tags, owners, and locations."""
    target_macs: Set[str] = set()
    
    for target in sched.targets:
        if target.mac:
            target_macs.add(DeviceConfig.normalize_mac(target.mac))
            
        elif target.person:
            # Gather all devices owned by this person
            for dev in config.devices:
                if dev.owner == target.person:
                    target_macs.add(DeviceConfig.normalize_mac(dev.mac))
                    
        elif target.location:
            # Resolve recursive location targets
            for dev in config.devices:
                if dev.location == target.location:
                    target_macs.add(DeviceConfig.normalize_mac(dev.mac))
                    
        elif target.tag:
            # Gather all devices carrying this tag
            for dev in config.devices:
                if target.tag in dev.tags:
                    target_macs.add(DeviceConfig.normalize_mac(dev.mac))
                    
    return target_macs
