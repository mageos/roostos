import json
from dbus_next.service import method
from roostos_engine.config import NodesConfigFile, NodeConfig
from roostos_engine.hardware_inspector import HardwareInspector


class ClusterDBusMixin:
    """D-Bus methods for cluster topology, health checking, and controller discovery."""

    @method()
    def GetClusterStatus(self) -> 's':
        self.reload_config()
        return json.dumps(self.cluster_manager.get_cluster_status(self._config.system, self._config.nodes).model_dump())

    @method()
    def GetNodeHealth(self, check_mqtt: 'b') -> 's':
        self.reload_config()
        node_id = getattr(self._config.system.cluster, "node_id", "node-01") if self._config.system.cluster else "node-01"
        current_node = next((n for n in self._config.nodes if n.id == node_id), None)
        roles = [r.value if hasattr(r, "value") else str(r) for r in current_node.roles] if current_node else ["gateway_router"]
        return json.dumps(self.health_checker.collect_health_report(
            node_id=node_id,
            node_name=current_node.name if current_node else self._config.system.hostname,
            roles=roles,
            dbus_connected=True,
            check_mqtt=check_mqtt,
        ).model_dump())

    @method()
    def GetDetectedHardware(self) -> 's':
        return json.dumps([d.model_dump() for d in HardwareInspector.inspect_network_interfaces(mock=self.mock)])

    @method()
    def GetNodes(self) -> 's':
        self.reload_config()
        return json.dumps([n.model_dump() for n in self._config.nodes])

    @method()
    def SaveNodes(self, nodes_json: 's') -> 'b':
        try:
            self.repository.save_nodes_config(NodesConfigFile(nodes=[NodeConfig.model_validate(n) for n in json.loads(nodes_json)]))
            self.reload_config()
            self.NodesUpdated()
            return True
        except Exception:
            return False

    @method()
    def GenerateJoinToken(self) -> 's':
        return self.cluster_manager.generate_join_token()

    @method()
    async def DiscoverControllers(self) -> 's':
        return json.dumps([c.model_dump() for c in await self.mdns_service.discover_controllers()])
