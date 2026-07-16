import importlib
import pkgutil
from roostos_engine.subsystems.base import Subsystem

def discover_subsystems(daemon) -> list[Subsystem]:
    discovered = []
    import roostos_engine.subsystems as subs_pkg
    for _, module_name, _ in pkgutil.iter_modules(subs_pkg.__path__):
        if module_name == "base":
            continue
        module = importlib.import_module(f"roostos_engine.subsystems.{module_name}")
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, type) and issubclass(attr, Subsystem) and attr is not Subsystem:
                discovered.append(attr(daemon))
                
    return resolve_execution_order(discovered)

def resolve_execution_order(subsystems: list[Subsystem]) -> list[Subsystem]:
    resolved = []
    visited = {}  # name -> state (0 = visiting, 1 = visited)
    by_name = {s.name: s for s in subsystems}

    def visit(name: str):
        if name in visited:
            if visited[name] == 0:
                raise ValueError(f"Circular dependency detected in subsystem: {name}")
            return
        
        if name not in by_name:
            raise ValueError(f"Subsystem '{name}' is missing but required as a dependency")

        visited[name] = 0  # Mark as currently visiting
        for dep in by_name[name].dependencies:
            visit(dep)
        visited[name] = 1  # Mark as fully visited
        resolved.append(by_name[name])

    for s in subsystems:
        if s.name not in visited:
            visit(s.name)

    return resolved
