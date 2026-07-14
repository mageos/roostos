import os
import json
import httpx
import asyncio
from typing import List
from roostos_sdk.server import DNSResolverServer

class TechnitiumBridge(DNSResolverServer):
    """Sidecar bridge translating RoostOS DNSResolver D-Bus requests to Technitium REST HTTP calls."""

    def __init__(self):
        super().__init__()
        self.api_url = os.getenv("TECHNITIUM_API_URL", "http://localhost:5380").rstrip("/")
        self.token = os.getenv("TECHNITIUM_API_TOKEN", "")

    # ==========================================
    # Helper method for HTTP requests
    # ==========================================

    async def _make_api_call(self, endpoint: str, params: dict) -> httpx.Response:
        """Helper to send authenticated GET requests to the Technitium REST API."""
        params["token"] = self.token
        url = f"{self.api_url}{endpoint}"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=5.0)
            resp.raise_for_status()
            return resp

    # ==========================================
    # DNSResolver D-Bus Hook Implementations
    # ==========================================

    async def set_client_dns_profile(self, mac: str, profile_name: str) -> bool:
        """Binds a client MAC address to a Technitium DNS group (profile)."""
        try:
            # Overwrite client configuration with the target group name
            params = {
                "client": mac.lower(),
                "group": profile_name,
                "overwrite": "true"
            }
            resp = await self._make_api_call("/api/dns/clients/add", params)
            data = resp.json()
            if data.get("status") != "ok":
                # If already exists, attempt to update group
                params = {
                    "client": mac.lower(),
                    "group": profile_name
                }
                resp = await self._make_api_call("/api/dns/clients/update", params)
                data = resp.json()
            return data.get("status") == "ok"
        except Exception as e:
            print(f"Error calling Technitium set_client_dns_profile: {e}")
            return False

    async def clear_client_dns_profile(self, mac: str) -> bool:
        """Removes a client entry from Technitium config list."""
        try:
            params = {"client": mac.lower()}
            resp = await self._make_api_call("/api/dns/clients/delete", params)
            data = resp.json()
            return data.get("status") == "ok"
        except Exception as e:
            print(f"Error calling Technitium clear_client_dns_profile: {e}")
            return False

    async def set_global_forwarders(self, forwarders: List[str]) -> bool:
        """Updates upstream DNS forwarders in Technitium config settings."""
        try:
            params = {"forwarders": ",".join(forwarders)}
            resp = await self._make_api_call("/api/dns/config/set", params)
            data = resp.json()
            return data.get("status") == "ok"
        except Exception as e:
            print(f"Error calling Technitium set_global_forwarders: {e}")
            return False

    async def get_dns_profiles(self) -> str:
        """Returns JSON list of active filtering profile names (Technitium Groups)."""
        try:
            params = {}
            resp = await self._make_api_call("/api/dns/groups/list", params)
            data = resp.json()
            if data.get("status") == "ok":
                # Extract group names from the response list
                groups = [g["name"] for g in data.get("response", {}).get("groups", [])]
                return json.dumps(groups)
            return "[]"
        except Exception as e:
            print(f"Error calling Technitium get_dns_profiles: {e}")
            return "[]"

    async def set_ad_blocking_enabled(self, enabled: bool) -> bool:
        """Toggles ad-blocking blocklists globally on the Technitium server."""
        try:
            endpoint = "/api/dns/blocklists/enable" if enabled else "/api/dns/blocklists/disable"
            params = {"all": "true"}
            resp = await self._make_api_call(endpoint, params)
            data = resp.json()
            return data.get("status") == "ok"
        except Exception as e:
            print(f"Error calling Technitium set_ad_blocking_enabled: {e}")
            return False


if __name__ == "__main__":
    import sys
    
    session_mode = "--session" in sys.argv or os.getenv("ROOSTOS_SESSION_BUS") == "1"
    bridge = TechnitiumBridge()
    
    async def main():
        await bridge.start(session=session_mode)
        await asyncio.Event().wait()
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        bridge.stop()
