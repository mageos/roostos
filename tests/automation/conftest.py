import os
import pytest
from tests.harness.client import NodeExecutor
from tests.harness.router_api import RoostOSRouterAPI


@pytest.fixture(scope="session")
def router_url() -> str:
    """Returns the base URL for the RoostOS Router API."""
    return os.environ.get("ROOSTOS_ROUTER_URL", "http://roostos-router:8000")


@pytest.fixture(scope="session")
def wan_host() -> str:
    """Returns the IP address of the upstream WAN simulator."""
    return os.environ.get("WAN_HOST", "172.30.1.100")


@pytest.fixture(scope="session")
def router_api(router_url: str) -> RoostOSRouterAPI:
    """Initializes and authenticates a client against the RoostOS Router."""
    api = RoostOSRouterAPI(base_url=router_url, container_name="roostos-router")
    api.authenticate("admin", "password")
    return api


@pytest.fixture(scope="session")
def lan_client() -> NodeExecutor:
    """Returns executor for the primary LAN client node (172.30.2.50)."""
    return NodeExecutor(container_name="client-lan", default_timeout=8.0)


@pytest.fixture(scope="session")
def guest_client() -> NodeExecutor:
    """Returns executor for the Guest network client node (172.30.3.50)."""
    return NodeExecutor(container_name="client-guest", default_timeout=8.0)


@pytest.fixture(scope="session")
def wan_node() -> NodeExecutor:
    """Returns executor for the Upstream WAN node (172.30.1.100)."""
    return NodeExecutor(container_name="upstream-wan", default_timeout=8.0)
