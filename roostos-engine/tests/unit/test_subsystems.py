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
