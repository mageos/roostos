"""Subsystem for Central Identity and Samba Active Directory services."""

import sys
from roostos_engine.subsystems.base import Subsystem


class IdentityServicesSubsystem(Subsystem):
    """Initializes and synchronizes centralized identity and directory discovery."""
    name = "identity"
    dependencies = ["system_settings"]

    def update(self) -> None:
        """Applies identity and domain discovery configurations."""
        identity_cfg = getattr(self.config.system, "identity_server", None)
        realm = getattr(self.config.system, "realm", "ROOSTOS.LOCAL")

        if not identity_cfg or not identity_cfg.enabled:
            print(f"Identity service is disabled. Realm: {realm}")
            return

        print(f"Applying Central Identity configuration: realm='{realm}', provider='{identity_cfg.provider}'")

        # If running on the host or in mock mode, ensure identity manager instance is refreshed
        if hasattr(self.daemon, "identity_manager") and self.daemon.identity_manager:
            self.daemon.identity_manager.realm = realm.upper()
            if identity_cfg.workgroup:
                self.daemon.identity_manager.workgroup = identity_cfg.workgroup.upper()
