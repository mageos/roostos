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
    
    # 1. Assert filter table and dynamic MAC blocking sets exist
    assert "table inet filter {" in rules
    assert "set quarantined {" in rules
    assert "set schedule_blocked {" in rules
    assert "set admin_blocked {" in rules
    assert "set blocked_clients {" in rules
    assert 'ether saddr @quarantined log prefix "FIREWALL:BLOCKED:Quarantined " drop' in rules
    assert 'ether saddr @schedule_blocked oifname "eth0" log prefix "FIREWALL:BLOCKED:Schedule_Block " drop' in rules
    assert 'ether saddr @admin_blocked oifname "eth0" log prefix "FIREWALL:BLOCKED:Admin_Block " drop' in rules
    assert 'ether saddr @blocked_clients log prefix "FIREWALL:BLOCKED:Blocked_Client " drop' in rules

    # 2. Assert DNS Hijacking and DoT blocking exist
    assert "tcp dport 53 redirect to :53" in rules
    assert "udp dport 53 redirect to :53" in rules
    assert "tcp dport 853 drop" in rules

    # 3. Assert WAN interface masquerading exists (eth0 from conftest network)
    assert "oifname \"eth0\" masquerade" in rules

    # 4. Assert enabled user-defined input rule appears in the input chain
    assert 'iifname "eth0" tcp dport 22 accept' in rules

    # 5. Assert disabled rule does NOT appear
    assert 'tcp dport 80 drop' not in rules


def test_firewall_input_rule_wildcard_interface(temp_config_dir):
    """Verifies that a wildcard interface rule omits the iifname qualifier."""
    config = load_config_directory(temp_config_dir)

    # Add a wildcard interface rule
    from roostos_engine.config import InputRuleConfig
    config.firewall.rules.append(InputRuleConfig(
        name="Allow DNS globally",
        interface="*",
        protocol="tcp/udp",
        port=53,
        action="accept",
        enabled=True
    ))

    manager = FirewallManager(config)
    rules = manager.compile_ruleset()

    # Wildcard interface should NOT have iifname
    assert 'tcp dport 53 accept' in rules
    assert 'udp dport 53 accept' in rules


def test_firewall_input_rule_source_cidr(temp_config_dir):
    """Verifies source CIDR filtering appears in compiled nftables rule."""
    config = load_config_directory(temp_config_dir)

    from roostos_engine.config import InputRuleConfig
    config.firewall.rules.append(InputRuleConfig(
        name="Allow SSH from private",
        interface="eth0",
        protocol="tcp",
        port=22,
        source="10.0.0.0/8",
        action="accept",
        enabled=True
    ))

    manager = FirewallManager(config)
    rules = manager.compile_ruleset()

    assert 'iifname "eth0" ip saddr 10.0.0.0/8 tcp dport 22 accept' in rules


def test_firewall_input_rule_tcp_udp_dual(temp_config_dir):
    """Verifies tcp/udp protocol generates two separate nftables lines."""
    config = load_config_directory(temp_config_dir)

    from roostos_engine.config import InputRuleConfig
    config.firewall.rules.append(InputRuleConfig(
        name="Allow WireGuard",
        interface="eth0",
        protocol="tcp/udp",
        port=51820,
        action="accept",
        enabled=True
    ))

    manager = FirewallManager(config)
    rules = manager.compile_ruleset()

    assert 'iifname "eth0" tcp dport 51820 accept' in rules
    assert 'iifname "eth0" udp dport 51820 accept' in rules


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


def test_parse_ports_single():
    """Verifies parsing a single port."""
    from roostos_engine.cli import parse_ports
    assert parse_ports("22") == [22]

def test_parse_ports_multiple():
    """Verifies parsing comma-separated ports."""
    from roostos_engine.cli import parse_ports
    assert parse_ports("22,80,443") == [22, 80, 443]

def test_parse_ports_with_spaces():
    """Verifies parsing ports with whitespace around commas."""
    from roostos_engine.cli import parse_ports
    assert parse_ports("22 , 80 , 443") == [22, 80, 443]

def test_parse_ports_invalid():
    """Verifies that non-integer port values raise BadParameter."""
    import click
    from roostos_engine.cli import parse_ports
    with pytest.raises(click.exceptions.BadParameter):
        parse_ports("abc")

def test_parse_ports_out_of_range():
    """Verifies that out-of-range ports raise BadParameter."""
    import click
    from roostos_engine.cli import parse_ports
    with pytest.raises(click.exceptions.BadParameter):
        parse_ports("99999")

def test_resolve_zone_to_interface_wan(temp_config_dir):
    """Verifies that 'wan' resolves to the WAN interface name from config."""
    from roostos_engine.cli import resolve_zone_to_interface
    result = resolve_zone_to_interface("wan", str(temp_config_dir))
    assert result == "eth0"

def test_resolve_zone_to_interface_lan(temp_config_dir):
    """Verifies that 'lan' resolves to the LAN bridge name from config."""
    from roostos_engine.cli import resolve_zone_to_interface
    result = resolve_zone_to_interface("lan", str(temp_config_dir))
    assert result == "br0"

def test_resolve_zone_to_interface_literal(temp_config_dir):
    """Verifies that a literal interface name passes through unchanged."""
    from roostos_engine.cli import resolve_zone_to_interface
    result = resolve_zone_to_interface("enp0s3", str(temp_config_dir))
    assert result == "enp0s3"

def test_resolve_zone_to_interface_wildcard(temp_config_dir):
    """Verifies that '*' passes through unchanged."""
    from roostos_engine.cli import resolve_zone_to_interface
    result = resolve_zone_to_interface("*", str(temp_config_dir))
    assert result == "*"


def test_firewall_anti_doh_disabled_by_default(temp_config_dir):
    """Verifies that Anti-DoH and Anti-VPN drop rules are NOT added by default."""
    config = load_config_directory(temp_config_dir)
    manager = FirewallManager(config)
    rules = manager.compile_ruleset()

    # Sets exist
    assert "set doh_server_ips {" in rules
    assert "set vpn_server_ips {" in rules

    # Forward drops should NOT be present by default
    assert "FIREWALL:BLOCKED:DoH_Direct_IP" not in rules
    assert "FIREWALL:BLOCKED:VPN_Protocol" not in rules
    assert "FIREWALL:BLOCKED:QUIC_Drop" not in rules


def test_firewall_anti_doh_enabled(temp_config_dir):
    """Verifies that enabling block_doh inserts DoH drop rules into forward chain."""
    config = load_config_directory(temp_config_dir)
    config.firewall.block_doh = True
    manager = FirewallManager(config)
    rules = manager.compile_ruleset()

    assert 'ip daddr @doh_server_ips tcp dport 443 log prefix "FIREWALL:BLOCKED:DoH_Direct_IP " drop' in rules
    assert 'ip daddr @doh_server_ips udp dport 443 log prefix "FIREWALL:BLOCKED:DoH_Direct_IP " drop' in rules


def test_firewall_anti_vpn_enabled(temp_config_dir):
    """Verifies that enabling block_vpns inserts VPN protocol drop rules."""
    config = load_config_directory(temp_config_dir)
    config.firewall.block_vpns = True
    config.firewall.custom_vpn_ips = ["198.51.100.0/24"]
    manager = FirewallManager(config)
    rules = manager.compile_ruleset()

    assert 'udp dport { 500, 1194, 1701, 4500, 51820 } log prefix "FIREWALL:BLOCKED:VPN_Protocol " drop' in rules
    assert 'tcp dport { 1194, 1723 } log prefix "FIREWALL:BLOCKED:VPN_Protocol " drop' in rules
    assert 'ip protocol { esp, ah } log prefix "FIREWALL:BLOCKED:VPN_Protocol " drop' in rules
    assert 'ip daddr @vpn_server_ips log prefix "FIREWALL:BLOCKED:VPN_Endpoint " drop' in rules
    assert "198.51.100.0/24" in rules


def test_firewall_anti_quic_enabled(temp_config_dir):
    """Verifies that enabling block_quic drops UDP port 443."""
    config = load_config_directory(temp_config_dir)
    config.firewall.block_quic = True
    manager = FirewallManager(config)
    rules = manager.compile_ruleset()

    assert 'udp dport 443 log prefix "FIREWALL:BLOCKED:QUIC_Drop " drop' in rules


def test_firewall_anti_evasion_cli_helpers(temp_config_dir):
    """Verifies CLI helper methods for adding and deleting elements from anti-evasion sets."""
    config = load_config_directory(temp_config_dir)
    manager = FirewallManager(config)

    assert manager.get_add_doh_ip_cmd("1.2.3.4") == ["nft", "add", "element", "inet", "filter", "doh_server_ips", "{ 1.2.3.4 }"]
    assert manager.get_delete_doh_ip_cmd("1.2.3.4") == ["nft", "delete", "element", "inet", "filter", "doh_server_ips", "{ 1.2.3.4 }"]
    assert manager.get_add_vpn_ip_cmd("5.6.7.8") == ["nft", "add", "element", "inet", "filter", "vpn_server_ips", "{ 5.6.7.8 }"]
    assert manager.get_delete_vpn_ip_cmd("5.6.7.8") == ["nft", "delete", "element", "inet", "filter", "vpn_server_ips", "{ 5.6.7.8 }"]

