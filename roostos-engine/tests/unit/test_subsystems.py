import pytest
from roostos_engine.subsystems.base import Subsystem
from roostos_engine.subsystems import resolve_execution_order

class MockSubsystem(Subsystem):
    def __init__(self, name, dependencies=None):
        self._name = name
        self.dependencies = dependencies or []
        self.run_on_init = True
        self.run_on_reload = True

    @property
    def name(self):
        return self._name

    def update(self) -> None:
        pass

def test_resolve_execution_order_success():
    s1 = MockSubsystem("system_settings", dependencies=[])
    s2 = MockSubsystem("network", dependencies=["system_settings"])
    s3 = MockSubsystem("dhcp", dependencies=["network"])
    s4 = MockSubsystem("mdns", dependencies=["network"])
    
    # Pass in scrambled order
    ordered = resolve_execution_order([s4, s3, s2, s1])
    
    # Extract names
    names = [s.name for s in ordered]
    assert names.index("system_settings") < names.index("network")
    assert names.index("network") < names.index("dhcp")
    assert names.index("network") < names.index("mdns")

def test_resolve_execution_order_circular():
    s1 = MockSubsystem("A", dependencies=["B"])
    s2 = MockSubsystem("B", dependencies=["C"])
    s3 = MockSubsystem("C", dependencies=["A"])
    
    with pytest.raises(ValueError) as excinfo:
        resolve_execution_order([s1, s2, s3])
    assert "Circular dependency detected" in str(excinfo.value)

def test_resolve_execution_order_missing():
    s1 = MockSubsystem("A", dependencies=["B"])
    
    with pytest.raises(ValueError) as excinfo:
        resolve_execution_order([s1])
    assert "missing but required as a dependency" in str(excinfo.value)


def test_system_settings_resolv_conf(temp_config_dir, tmp_path, monkeypatch):
    """Verifies that SystemSettingsSubsystem writes resolv.conf with forwarders."""
    from roostos_engine.config import load_config_directory
    from roostos_engine.subsystems.system_settings import SystemSettingsSubsystem

    config = load_config_directory(temp_config_dir)
    config.system.dns.forwarders = ["1.1.1.1", "8.8.8.8"]
    config.system.domain = "roostos.home"

    mock_etc = tmp_path / "etc"
    monkeypatch.setenv("ROOSTOS_ETC_DIR", str(mock_etc))

    class DummyDaemon:
        def __init__(self, cfg):
            self._config = cfg
            self.mock = True

    subsystem = SystemSettingsSubsystem(DummyDaemon(config))
    subsystem.update()

    resolv_file = mock_etc / "resolv.conf"
    assert resolv_file.exists()
    content = resolv_file.read_text()
    assert "search roostos.home" in content
    assert "nameserver 1.1.1.1" in content
    assert "nameserver 8.8.8.8" in content

