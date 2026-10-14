"""Pydantic schemas and DTOs for Household Hub and quick actions."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field


class HouseholdPulseDTO(BaseModel):
    """Aggregated real-time metrics for Household Hub hero banner."""
    hostname: str = Field(default="roost-home-router", description="Router hostname")
    version: str = Field(default="0.3.0", description="RoostOS software version")
    uptime: str = Field(default="6d 14h 22m", description="Human-readable uptime")
    wan_ip: str = Field(..., description="External WAN IPv4 address")
    gateway_ip: str = Field(..., description="Local LAN gateway IP")
    isp_name: str = Field(default="Residential ISP", description="ISP provider name")
    cgnat_detected: bool = Field(default=False, description="Whether WAN IP is behind RFC6598 CGNAT")
    ping_ms: int = Field(default=12, description="Uplink latency in milliseconds")
    download_mbps: float = Field(default=0.0, description="Measured or active download speed in Mbps")
    upload_mbps: float = Field(default=0.0, description="Measured or active upload speed in Mbps")
    status: str = Field(default="online", description="Overall connection health status")
    all_kids_paused: bool = Field(default=False, description="Whether all kid profiles are currently paused")
    active_kids_count: int = Field(default=0, description="Total number of registered kid profiles")
    total_devices_count: int = Field(default=0, description="Total registered devices")
    online_devices_count: int = Field(default=0, description="Total currently online devices")
    unassigned_device_alert: bool = Field(default=False, description="Alert flag if unassigned devices are detected")
    unassigned_device: Optional[Dict[str, Any]] = Field(default=None, description="Details of latest quarantined device")


class GuestWifiDTO(BaseModel):
    """Guest Wi-Fi network configuration and QR payload."""
    ssid: str = Field(..., description="Guest network SSID")
    passphrase: str = Field(..., description="WPA2/WPA3 pre-shared key")
    enabled: bool = Field(default=True, description="Whether guest AP is currently broadcasting")
    band: str = Field(default="5GHz", description="Radio band")
    security: str = Field(default="WPA2-Personal", description="Security mode")
    clients_count: int = Field(default=0, description="Active guest clients count")
    qr_payload: str = Field(..., description="Standard WIFI:S:... URI for camera scanning")


class ToggleGuestWifiRequestDTO(BaseModel):
    """Request payload to enable or disable the Guest Wi-Fi access point."""
    enabled: bool = Field(..., description="Desired Guest Wi-Fi broadcast state")


class QuickActionResponseDTO(BaseModel):
    """Response returned by one-touch quick actions."""
    action: str = Field(..., description="Identifier of action performed")
    status: str = Field(default="success", description="Action execution status")
    message: str = Field(..., description="User-facing confirmation message")
    timestamp: str = Field(..., description="ISO 8601 execution timestamp")


class SpeedTestResultDTO(BaseModel):
    """Result of an on-demand speed test cycle."""
    download_mbps: float = Field(..., description="Download throughput in Mbps")
    upload_mbps: float = Field(..., description="Upload throughput in Mbps")
    ping_ms: int = Field(..., description="Ping latency in ms")
    server_location: str = Field(default="Local ISP Edge", description="Testing server location")
    timestamp: str = Field(..., description="ISO timestamp of test execution")
