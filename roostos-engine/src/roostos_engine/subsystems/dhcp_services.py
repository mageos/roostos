import os
import sys
import tempfile
import subprocess
from roostos_engine.subsystems.base import Subsystem

class DhcpServicesSubsystem(Subsystem):
    name = "dhcp"
    dependencies = ["network"]

    def update(self) -> None:
        """Compiles the Kea DHCP4 configuration and restarts the kea-dhcp4-server service."""
        try:
            from roostos_engine.dhcp_manager import DHCPManager
            
            kea_conf_dir = os.environ.get("ROOSTOS_KEA_CONF_DIR")
            if kea_conf_dir:
                target_path = os.path.join(kea_conf_dir, "kea-dhcp4.conf")
            else:
                target_path = "/etc/kea/kea-dhcp4.conf"
            
            # If in mock mode, write to custom overridden path or temp dir
            if self.mock:
                if not kea_conf_dir:
                    target_path = os.path.join(tempfile.gettempdir(), "kea-dhcp4.conf")
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                manager = DHCPManager(self.config, target_path)
                manager.write_config()
                return

            # Attempt writing to standard /etc/kea/kea-dhcp4.conf path
            try:
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                manager = DHCPManager(self.config, target_path)
                manager.write_config()
            except OSError as e:
                print(f"Warning: Failed to write to {target_path} ({e}), falling back to temp file.", file=sys.stderr)
                target_path = os.path.join(tempfile.gettempdir(), "kea-dhcp4.conf")
                manager = DHCPManager(self.config, target_path)
                manager.write_config()
                return
            
            # Restart kea-dhcp4-server using systemctl if running as root
            if os.getuid() == 0:
                # Remove stale socket/lock files to prevent permission issues for the _kea user
                for stale_file in ["/run/kea/kea-dhcp4-ctrl.sock", "/run/kea/kea-dhcp4-ctrl.sock.lock"]:
                    try:
                        if os.path.exists(stale_file):
                            os.remove(stale_file)
                    except Exception as ex:
                        print(f"Warning: Could not remove stale file {stale_file}: {ex}", file=sys.stderr)

                print("Restarting kea-dhcp4-server service...")
                subprocess.run(["systemctl", "restart", "kea-dhcp4-server"], check=True)
        except Exception as e:
            print(f"Error updating DHCP services: {e}", file=sys.stderr)
