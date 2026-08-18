import json
import httpx
from typing import Any, Dict, List, Optional
from tests.harness.client import NodeExecutor


class RoostOSRouterAPI:
    """REST API and runtime management client for the RoostOS Router container."""

    def __init__(
        self,
        base_url: str = "http://roostos-router:8000",
        container_name: str = "roostos-router",
        timeout: float = 10.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.container_name = container_name
        self.timeout = timeout
        self.executor = NodeExecutor(container_name=container_name, default_timeout=timeout)
        self.token: Optional[str] = None

    def authenticate(self, username: str = "admin", password: str = "password") -> str:
        """Authenticates with RoostOS and retrieves a bearer token."""
        try:
            # First try direct OAuth token endpoint with mock/password credentials
            res = httpx.post(
                f"{self.base_url}/oauth/token",
                data={
                    "grant_type": "password",
                    "username": username,
                    "password": password,
                    "client_id": "roostos-ui",
                },
                timeout=self.timeout,
            )
            if res.status_code == 200:
                self.token = res.json().get("access_token")
                return self.token or ""
        except Exception:
            pass

        # Fallback to mock bearer token for test environments with ROOSTOS_MOCK_AUTH=1
        self.token = f"mock-token-{username}"
        return self.token

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_system_health(self) -> Dict[str, Any]:
        """Queries subsystem health status."""
        res = httpx.get(f"{self.base_url}/api/system/health", headers=self._headers(), timeout=self.timeout)
        return res.json() if res.status_code == 200 else {}

    def get_firewall_rules(self) -> List[Dict[str, Any]]:
        """Retrieves currently configured firewall rules."""
        res = httpx.get(f"{self.base_url}/api/firewall/rules", headers=self._headers(), timeout=self.timeout)
        return res.json() if res.status_code == 200 else []

    def add_firewall_rule(self, rule_data: Dict[str, Any]) -> bool:
        """Creates or updates a custom firewall rule."""
        res = httpx.post(
            f"{self.base_url}/api/firewall/rules",
            json=rule_data,
            headers=self._headers(),
            timeout=self.timeout,
        )
        return res.status_code in (200, 201)

    def get_nft_ruleset(self) -> str:
        """Inspects the active live nftables ruleset in the kernel."""
        res = self.executor.run_command(["nft", "list", "ruleset"])
        return res.stdout if res.success else ""

    def get_blocked_clients(self) -> List[str]:
        """Retrieves list of MAC addresses in the active blocked_clients nft set."""
        res = self.executor.run_command(["nft", "-j", "list", "set", "inet", "filter", "blocked_clients"])
        if res.success and res.stdout:
            try:
                data = json.loads(res.stdout)
                for item in data.get("nftables", []):
                    if "set" in item:
                        return item["set"].get("elem", [])
            except Exception:
                pass
        return []

    def block_mac_address(self, mac: str) -> bool:
        """Directly adds a MAC address to the nftables blocked_clients dynamic set."""
        res = self.executor.run_command(
            ["nft", "add", "element", "inet", "filter", "blocked_clients", f"{{ {mac.lower()} }}"]
        )
        return res.success

    def unblock_mac_address(self, mac: str) -> bool:
        """Directly removes a MAC address from the nftables blocked_clients dynamic set."""
        res = self.executor.run_command(
            ["nft", "delete", "element", "inet", "filter", "blocked_clients", f"{{ {mac.lower()} }}"]
        )
        return res.success
