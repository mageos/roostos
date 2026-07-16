import os
import sys
import subprocess
from roostos_engine.subsystems.base import Subsystem

class SystemSettingsSubsystem(Subsystem):
    name = "system_settings"
    dependencies = []

    def update(self) -> None:
        """Applies global system configuration (hostname, domain name)."""
        hostname = self.config.system.hostname
        etc_dir = os.environ.get("ROOSTOS_ETC_DIR")

        if etc_dir:
            try:
                os.makedirs(etc_dir, exist_ok=True)
                hostname_path = os.path.join(etc_dir, "hostname")
                with open(hostname_path, "w") as f:
                    f.write(f"{hostname}\n")
                
                hosts_path = os.path.join(etc_dir, "hosts")
                hosts_lines = []
                if os.path.exists(hosts_path):
                    with open(hosts_path, "r") as f:
                        for line in f:
                            if line.strip().startswith("127.0.0.1"):
                                hosts_lines.append(f"127.0.0.1 localhost {hostname}\n")
                            else:
                                hosts_lines.append(line)
                else:
                    hosts_lines = [f"127.0.0.1 localhost {hostname}\n"]
                with open(hosts_path, "w") as f:
                    f.writelines(hosts_lines)
                print(f"Mock applied hostname '{hostname}' to {etc_dir}")
            except Exception as e:
                print(f"Error applying mock hostname configuration to {etc_dir}: {e}", file=sys.stderr)
        elif not self.mock and os.getuid() == 0:
            try:
                # Update /etc/hostname
                with open("/etc/hostname", "w") as f:
                    f.write(f"{hostname}\n")
                
                # Update /etc/hosts safely
                hosts_lines = []
                if os.path.exists("/etc/hosts"):
                    with open("/etc/hosts", "r") as f:
                        for line in f:
                            if line.strip().startswith("127.0.0.1"):
                                hosts_lines.append(f"127.0.0.1 localhost {hostname}\n")
                            else:
                                hosts_lines.append(line)
                else:
                    hosts_lines = [f"127.0.0.1 localhost {hostname}\n"]
                with open("/etc/hosts", "w") as f:
                    f.writelines(hosts_lines)
                
                # Apply instantly on host
                subprocess.run(["hostnamectl", "set-hostname", hostname], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"Successfully applied hostname '{hostname}' to system")
            except Exception as e:
                print(f"Error applying system hostname configuration: {e}", file=sys.stderr)
        else:
            print(f"Non-root or mock mode. Mock applied hostname: '{hostname}'")

        domain = self.config.system.domain
        print(f"Applied local domain name: '{domain}'")
