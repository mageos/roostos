"""Unit tests for the RoostOS Environment and Hardware Inspector."""

from roostos_cli.models import InterfaceInfo, SystemEnvironment, NodeRole
from roostos_cli.inspector import EnvironmentInspector


def test_inspect_real_or_fallback():
    env = EnvironmentInspector.inspect()
    assert env.arch != ""
    assert env.cpu_cores >= 1
    assert env.memory_total_mb > 0
    assert env.recommended_role in list(NodeRole)


def test_recommend_gateway_for_sbc():
    # 2 physical ethernet ports and 1GB RAM -> should recommend GATEWAY
    mock_env = SystemEnvironment(
        arch="arm64",
        cpu_cores=4,
        memory_total_mb=1024,
        memory_free_mb=600,
        is_laptop=False,
        interfaces=[
            InterfaceInfo(name="eth0", operstate="up", speed_mbps=1000),
            InterfaceInfo(name="eth1", operstate="down", speed_mbps=1000),
        ]
    )
    role, reason = EnvironmentInspector.recommend_role(mock_env)
    assert role == NodeRole.GATEWAY
    assert "Gateway" in reason


def test_recommend_workstation_for_laptop():
    mock_env = SystemEnvironment(
        arch="x86_64",
        cpu_cores=8,
        memory_total_mb=16384,
        is_laptop=True,
        interfaces=[
            InterfaceInfo(name="wlan0", is_wireless=True, operstate="up")
        ]
    )
    role, reason = EnvironmentInspector.recommend_role(mock_env)
    assert role == NodeRole.WORKSTATION
    assert "laptop" in reason.lower()


def test_recommend_controller_for_high_memory_server():
    mock_env = SystemEnvironment(
        arch="x86_64",
        cpu_cores=12,
        memory_total_mb=32768,
        is_laptop=False,
        interfaces=[
            InterfaceInfo(name="eth0", operstate="up", speed_mbps=10000)
        ]
    )
    role, reason = EnvironmentInspector.recommend_role(mock_env)
    assert role == NodeRole.CONTROLLER
