import sys
from roostos_engine.subsystems.base import Subsystem

class QosServicesSubsystem(Subsystem):
    name = "qos"
    dependencies = ["network"]

    def update(self) -> None:
        """Re-compiles and applies traffic shaping rules (tc/fq_codel)."""
        try:
            from roostos_engine.qos_manager import QoSManager
            state_db = getattr(self.daemon, "state_db", None)
            active_leases = state_db.get_active_leases() if state_db else []
            manager = QoSManager(self.config, mock=self.mock, active_leases=active_leases)
            manager.update_qos()
        except Exception as e:
            print(f"Error updating QoS services: {e}", file=sys.stderr)
