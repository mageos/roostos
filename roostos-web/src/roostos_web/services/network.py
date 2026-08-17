from typing import List
from injector import inject

from roostos_engine.config import NetworkConfig, VPNConfig, NetworkSettings, WifiSettings
from roostos_engine.repository import ConfigRepository
from roostos_sdk.client import RoostClient


class NetworkService:
    @inject
    def __init__(self, repo: ConfigRepository, dbus: RoostClient):
        self.repo = repo
        self.dbus = dbus

    def get_network_config(self) -> NetworkConfig:
        config = self.repo.get_config()
        return NetworkConfig(
            network=config.network,
            wifi=config.wifi,
            vpns=config.vpns
        )

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
