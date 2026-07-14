from typing import List
from fastapi import Depends

from roostos_engine.config import NetworkConfig, VPNConfig, NetworkSettings, WifiSettings
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient
from roostos_web.services.base import get_repository, get_dbus_client

class NetworkService:
    def __init__(self, repo: ConfigRepository = Depends(get_repository), dbus: RoostClient = Depends(get_dbus_client)):
        self.repo = repo
        self.dbus = dbus

    def get_network_config(self) -> NetworkConfig:
        config = self.repo.get_config()
        return config.network

    async def save_network_config(self, network: NetworkSettings, wifi: WifiSettings, vpns: List[VPNConfig]):
        network_config_obj = NetworkConfig(
            network=network,
            wifi=wifi,
            vpns=vpns
        )
        self.repo.save_network_config(network_config_obj)
        await self.dbus.get_config()

    def get_vpns(self) -> List[VPNConfig]:
        config = self.repo.get_config()
        return config.vpns
