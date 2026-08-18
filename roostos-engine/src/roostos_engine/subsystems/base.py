from abc import ABC, abstractmethod

class Subsystem(ABC):
    name: str = ""
    dependencies: list[str] = []
    run_on_init: bool = True
    run_on_reload: bool = True

    def __init__(self, daemon):
        self.daemon = daemon

    @property
    def config(self):
        return self.daemon._config

    @property
    def mock(self) -> bool:
        return self.daemon.mock

    @abstractmethod
    def update(self) -> None:
        """Subclasses implement their specific logic here."""
        pass
