import json
import pytest
from roostos_dns_technitium.bridge import TechnitiumBridge

@pytest.mark.asyncio
async def test_set_client_dns_profile_success(httpx_mock):
    """Verifies that set_client_dns_profile sends correct query parameters to Technitium API."""
    bridge = TechnitiumBridge()
    bridge.token = "test_token"
    
    # Mock successful add API response
    httpx_mock.add_response(
        url="http://localhost:5380/api/dns/clients/add?client=aa%3Abb%3Acc%3Add%3Aee%3Aff&group=Kids-Safe&overwrite=true&token=test_token",
        json={"status": "ok"}
    )

    success = await bridge.set_client_dns_profile("aa:bb:cc:dd:ee:ff", "Kids-Safe")
    assert success is True


@pytest.mark.asyncio
async def test_clear_client_dns_profile(httpx_mock):
    """Verifies clear_client_dns_profile hits the delete endpoint."""
    bridge = TechnitiumBridge()
    bridge.token = "test_token"

    httpx_mock.add_response(
        url="http://localhost:5380/api/dns/clients/delete?client=aa%3Abb%3Acc%3Add%3Aee%3Aff&token=test_token",
        json={"status": "ok"}
    )

    success = await bridge.clear_client_dns_profile("aa:bb:cc:dd:ee:ff")
    assert success is True


@pytest.mark.asyncio
async def test_set_global_forwarders(httpx_mock):
    """Verifies upstream forwarders are correctly serialized and submitted."""
    bridge = TechnitiumBridge()
    bridge.token = "test_token"

    httpx_mock.add_response(
        url="http://localhost:5380/api/dns/config/set?forwarders=1.1.1.1%2C8.8.8.8&token=test_token",
        json={"status": "ok"}
    )

    success = await bridge.set_global_forwarders(["1.1.1.1", "8.8.8.8"])
    assert success is True


@pytest.mark.asyncio
async def test_get_dns_profiles(httpx_mock):
    """Verifies Technitium group lists are loaded and parsed into a JSON list string."""
    bridge = TechnitiumBridge()
    bridge.token = "test_token"

    httpx_mock.add_response(
        url="http://localhost:5380/api/dns/groups/list?token=test_token",
        json={
            "status": "ok",
            "response": {
                "groups": [
                    {"name": "Default"},
                    {"name": "Kids-Safe"},
                    {"name": "Malware-Filter"}
                ]
            }
        }
    )

    profiles_json = await bridge.get_dns_profiles()
    profiles = json.loads(profiles_json)
    assert len(profiles) == 3
    assert "Kids-Safe" in profiles
    assert "Malware-Filter" in profiles


@pytest.mark.asyncio
async def test_set_ad_blocking_enabled(httpx_mock):
    """Verifies global blocklists toggle endpoint call logic."""
    bridge = TechnitiumBridge()
    bridge.token = "test_token"

    # Test enable
    httpx_mock.add_response(
        url="http://localhost:5380/api/dns/blocklists/enable?all=true&token=test_token",
        json={"status": "ok"}
    )
    success = await bridge.set_ad_blocking_enabled(True)
    assert success is True

    # Test disable
    httpx_mock.add_response(
        url="http://localhost:5380/api/dns/blocklists/disable?all=true&token=test_token",
        json={"status": "ok"}
    )
    success = await bridge.set_ad_blocking_enabled(False)
    assert success is True
