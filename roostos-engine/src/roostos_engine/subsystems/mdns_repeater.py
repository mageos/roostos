import os
import sys
import subprocess
from roostos_engine.subsystems.base import Subsystem

class MdnsRepeaterSubsystem(Subsystem):
    name = "mdns"
    dependencies = ["network"]

    def update(self) -> None:
        """Generates and restarts systemd service for mdns-repeater dynamically based on active local interfaces."""
        interfaces = []
        if hasattr(self.config, "network") and self.config.network:
            for bridge in self.config.network.bridges:
                interfaces.append(bridge.name)
            for vlan in self.config.network.vlans:
                interfaces.append(vlan.name)

        service_path = os.environ.get("ROOSTOS_MDNS_REPEATER_SERVICE")
        if not service_path:
            if self.mock or os.getuid() != 0:
                import tempfile
                temp_dir = os.path.join(tempfile.gettempdir(), "systemd", "system")
                os.makedirs(temp_dir, exist_ok=True)
                service_path = os.path.join(temp_dir, "mdns-repeater.service")
            else:
                service_path = "/etc/systemd/system/mdns-repeater.service"

        if len(interfaces) >= 2:
            cmd = f"/usr/sbin/mdns-repeater {' '.join(interfaces)}"
            service_content = f"""[Unit]
Description=mDNS Repeater between local interfaces
After=network.target

[Service]
Type=simple
ExecStart={cmd}
Restart=always

[Install]
WantedBy=multi-user.target
"""
            try:
                with open(service_path, "w") as f:
                    f.write(service_content)
                print(f"mdns-repeater service generated at {service_path} with command: {cmd}")

                if os.getuid() == 0 and not self.mock:
                    subprocess.run(["systemctl", "daemon-reload"], check=True)
                    subprocess.run(["systemctl", "enable", "mdns-repeater"], check=True)
                    subprocess.run(["systemctl", "restart", "mdns-repeater"], check=True)
            except Exception as e:
                print(f"Warning: Failed to configure mdns-repeater: {e}", file=sys.stderr)
        else:
            if os.path.exists(service_path):
                try:
                    os.remove(service_path)
                except Exception:
                    pass
            if os.getuid() == 0 and not self.mock:
                try:
                    subprocess.run(["systemctl", "stop", "mdns-repeater"], check=False)
                    subprocess.run(["systemctl", "disable", "mdns-repeater"], check=False)
                    subprocess.run(["systemctl", "daemon-reload"], check=False)
                except Exception:
                    pass
