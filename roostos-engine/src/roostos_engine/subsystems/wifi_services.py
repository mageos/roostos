import os
import sys
import subprocess
from roostos_engine.subsystems.base import Subsystem

class WifiServicesSubsystem(Subsystem):
    name = "wifi"
    dependencies = ["network"]

    def update(self) -> None:
        """Generates IWD Access Point configurations for wireless interfaces."""
        if not self.config.wifi:
            return

        iwd_dir = os.environ.get("ROOSTOS_IWD_DIR")
        if not iwd_dir:
            if self.mock:
                import tempfile
                iwd_dir = os.path.join(tempfile.gettempdir(), "iwd")
            else:
                iwd_dir = "/var/lib/iwd"

        try:
            os.makedirs(iwd_dir, exist_ok=True)
            print(f"Generating IWD AP configurations in {iwd_dir}...")
            
            # Map radios for quick lookup
            radios_map = {r.interface: r for r in self.config.wifi.radios}
            
            # Generate AP profile file for each access point
            for ap in self.config.wifi.access_points:
                if ap.interface:
                    iface_name = ap.interface
                elif ap.radio:
                    if ap.bridge == "br0":
                        iface_name = ap.radio
                    else:
                        iface_name = f"{ap.radio}_guest"
                else:
                    iface_name = "wlan0"

                ap_file = f"{iface_name}.ap"
                ap_path = os.path.join(iwd_dir, ap_file)
                
                radio_iface = ap.radio or ap.interface or "wlan0"
                radio = radios_map.get(radio_iface)
                
                with open(ap_path, "w") as f:
                    f.write("[General]\n")
                    f.write(f"Name={ap.ssid}\n")
                    f.write("Mode=ap\n")
                    
                    if radio:
                        if radio.channel != "auto":
                            f.write(f"Channel={radio.channel}\n")
                        if "5ghz" in radio.band.lower():
                            f.write("Band=5g\n")
                        elif "2.4ghz" in radio.band.lower():
                            f.write("Band=2.4g\n")
                    
                    f.write("\n[AP]\n")
                    if ap.security == "wpa3-sae":
                        f.write("Security=sae\n")
                    elif ap.security == "wpa2-psk":
                        f.write("Security=psk\n")
                    
                    f.write(f"Passphrase={ap.passphrase}\n")
                
                if os.getuid() == 0 and not self.mock:
                    if iface_name != radio_iface:
                        try:
                            subprocess.run(["ip", "link", "show", iface_name], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        except subprocess.CalledProcessError:
                            print(f"Creating virtual wireless AP interface {iface_name} on {radio_iface}...")
                            subprocess.run(["iw", "dev", radio_iface, "interface", "add", iface_name, "type", "__ap"], check=True)
                            subprocess.run(["ip", "link", "set", iface_name, "up"], check=True)

            if os.getuid() == 0 and not self.mock:
                print("Restarting IWD service...")
                subprocess.run(["systemctl", "restart", "iwd"], check=True)
                
        except Exception as e:
            print(f"Error updating Wi-Fi services: {e}", file=sys.stderr)
