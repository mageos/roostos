import os
import sys
import subprocess
from roostos_engine.subsystems.base import Subsystem

class FirewallServicesSubsystem(Subsystem):
    name = "firewall"
    dependencies = ["network"]

    def update(self) -> None:
        """Generates nftables configuration and applies it using nft command line."""
        nft_conf = os.environ.get("ROOSTOS_NFTABLES_CONF")
        if not nft_conf:
            if self.mock:
                return
            nft_conf = "/etc/nftables.conf"

        try:
            os.makedirs(os.path.dirname(nft_conf), exist_ok=True)
            firewall_manager = getattr(self.daemon, "firewall_manager", None)
            if firewall_manager:
                firewall_manager.write_ruleset(nft_conf)
                print(f"nftables firewall ruleset written to {nft_conf}")
            
            if self.mock:
                return

            # Apply configuration directly via nft command line for better visibility on errors
            res = subprocess.run(["nft", "-f", nft_conf], capture_output=True, text=True)
            if res.returncode != 0:
                raise Exception(res.stderr.strip())
            print("nftables firewall ruleset applied successfully")
        except Exception as e:
            print(f"Error applying firewall/nftables configuration: {e}", file=sys.stderr)
