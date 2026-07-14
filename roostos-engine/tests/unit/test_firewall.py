import datetime
import pytest
from roostos_engine.config import load_config_directory, ScheduleConfig, ScheduleTarget
from roostos_engine.firewall_manager import FirewallManager
from roostos_engine.scheduler import is_schedule_active, resolve_schedule_targets

def test_firewall_ruleset_compilation(temp_config_dir):
    """Verifies that FirewallManager compiles correct nftables.conf strings."""
    config = load_config_directory(temp_config_dir)
    manager = FirewallManager(config)
    
    rules = manager.compile_ruleset()
    
    # 1. Assert filter table and dynamic MAC blocking set exist
    assert "table inet filter {" in rules
    assert "set blocked_clients {" in rules
    assert "ether saddr @blocked_clients drop" in rules

    # 2. Assert DNS Hijacking and DoT blocking exist
    assert "tcp dport 53 redirect to :53" in rules
    assert "udp dport 53 redirect to :53" in rules
    assert "tcp dport 853 drop" in rules

    # 3. Assert WAN interface masquerading exists (eth0 from conftest network)
    assert "oifname \"eth0\" masquerade" in rules


def test_schedule_overnight_time_evaluation():
    """Verifies is_schedule_active matches simple day ranges and overnight bedtime crossings."""
    # 1. Standard same-day schedule (e.g., Saturday & Sunday daytime, 08:00 - 20:00)
    sched_day = ScheduleConfig(
        name="Weekend limits",
        targets=[],
        days=["saturday", "sunday"],
        start_time="08:00",
        end_time="20:00",
        action="block_internet"
    )
    
    # Saturday noon -> Active
    dt_sat_noon = datetime.datetime(2026, 6, 27, 12, 0) # 2026-06-27 is Saturday
    assert is_schedule_active(sched_day, dt_sat_noon) is True

    # Saturday 9 PM -> Inactive
    dt_sat_night = datetime.datetime(2026, 6, 27, 21, 0)
    assert is_schedule_active(sched_day, dt_sat_night) is False

    # Monday noon -> Inactive
    dt_mon_noon = datetime.datetime(2026, 6, 29, 12, 0) # 2026-06-29 is Monday
    assert is_schedule_active(sched_day, dt_mon_noon) is False

    # 2. Overnight bedtime schedule (e.g., Monday Bedtime starting Monday 22:00 to Tuesday 06:00)
    sched_overnight = ScheduleConfig(
        name="Monday Bedtime",
        targets=[],
        days=["monday"],
        start_time="22:00",
        end_time="06:00",
        action="block_internet"
    )

    # Monday 23:00 -> Active (started today)
    dt_mon_bed = datetime.datetime(2026, 6, 29, 23, 0)
    assert is_schedule_active(sched_overnight, dt_mon_bed) is True

    # Tuesday 03:00 -> Active (started yesterday)
    dt_tue_early = datetime.datetime(2026, 6, 30, 3, 0) # Tuesday
    assert is_schedule_active(sched_overnight, dt_tue_early) is True

    # Tuesday 07:00 -> Inactive (ended at 06:00)
    dt_tue_morning = datetime.datetime(2026, 6, 30, 7, 0)
    assert is_schedule_active(sched_overnight, dt_tue_morning) is False

    # Wednesday 03:00 -> Inactive (only Monday overnight runs)
    dt_wed_early = datetime.datetime(2026, 7, 1, 3, 0)
    assert is_schedule_active(sched_overnight, dt_wed_early) is False


def test_resolve_schedule_targets(temp_config_dir):
    """Verifies that scheduler targets expand correctly to MAC address sets."""
    config = load_config_directory(temp_config_dir)
    
    # Target by Owner
    sched_person = ScheduleConfig(
        name="Kids Limits",
        targets=[ScheduleTarget(person="alice_profile")],
        days=[], start_time="", end_time=""
    )
    # Alice's iPad (owned by alice_profile, mac: 4c:32:75:98:76:54)
    macs = resolve_schedule_targets(sched_person, config)
    assert len(macs) == 1
    assert "4c:32:75:98:76:54" in macs

    # Target by Location
    sched_room = ScheduleConfig(
        name="Room block",
        targets=[ScheduleTarget(location="living_room")],
        days=[], start_time="", end_time=""
    )
    # Mom's Laptop (mac a4:83:e7:12:34:56) is in living_room
    macs = resolve_schedule_targets(sched_room, config)
    assert len(macs) == 1
    assert "a4:83:e7:12:34:56" in macs
