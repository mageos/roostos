import json
from dbus_next.service import method, signal as dbus_signal
from roostos_engine.config import (
    DevicesConfig,
    DeviceConfig,
    InputRuleConfig,
    FirewallSettings,
    FirewallConfig,
)


class ConfigDBusMixin:
    """D-Bus methods for declarative configuration and domain entity CRUD."""

    @method()
    def GetConfig(self) -> 's':
        self.reload_config()
        return json.dumps(self._config.model_dump(exclude_none=True))

    @method()
    def GetUsers(self) -> 's':
        self.reload_config()
        return json.dumps([u.model_dump() for u in self._config.users])

    @method()
    def GetPeople(self) -> 's':
        self.reload_config()
        return json.dumps([p.model_dump() for p in self._config.people])

    @method()
    def GetBuildings(self) -> 's':
        self.reload_config()
        return json.dumps([b.model_dump() for b in self._config.buildings])

    @method()
    def GetRooms(self) -> 's':
        self.reload_config()
        return json.dumps([r.model_dump() for r in self._config.rooms])

    @method()
    def GetDevices(self) -> 's':
        self.reload_config()
        return json.dumps([d.model_dump() for d in self._config.devices])

    @method()
    def GetActiveLeases(self) -> 's':
        return json.dumps(self.state_db.get_active_leases())

    @method()
    def RegisterLease(self, mac: 's', ip: 's', hostname: 's') -> 'b':
        try:
            self.reload_config()
            norm_mac = DeviceConfig.normalize_mac(mac)
            registered = any(d.mac == norm_mac for d in self._config.devices)
            success = self.state_db.register_lease(norm_mac, ip, hostname, quarantined=not registered)
            if not success:
                return False
            if registered:
                self.DeviceConnected(norm_mac, ip, hostname)
            else:
                self.UnknownDeviceDiscovered(norm_mac, ip, hostname)
            return True
        except Exception:
            return False

    @method()
    def ReleaseLease(self, mac: 's') -> 'b':
        try:
            return self.state_db.release_lease(DeviceConfig.normalize_mac(mac))
        except Exception:
            return False

    @method()
    def GetSchedules(self) -> 's':
        self.reload_config()
        return json.dumps([s.model_dump() for s in self._config.schedules])

    @method()
    def GetFirewallRules(self) -> 's':
        self.reload_config()
        return json.dumps([r.model_dump() for r in self._config.firewall.rules])

    @method()
    def UpdateFirewallRule(self, name: 's', interface: 's', protocol: 's', port: 'i', source: 's', action: 's', enabled: 'b') -> 'b':
        try:
            self.reload_config()
            new_rule = InputRuleConfig(
                name=name, interface=interface or "*", protocol=protocol or "tcp",
                port=port, source=source or None, action=action or "accept", enabled=enabled
            )
            rules_list = [r.model_dump() for r in self._config.firewall.rules]
            rule_idx = next((i for i, r in enumerate(rules_list) if r["name"] == name), -1)
            if rule_idx >= 0:
                rules_list[rule_idx] = new_rule.model_dump()
            else:
                rules_list.append(new_rule.model_dump())
            self.repository.save_firewall_config(FirewallConfig(firewall=FirewallSettings(port_forwards=self._config.firewall.port_forwards, rules=rules_list)))
            self.reload_config()
            self.SchedulesUpdated()
            return True
        except Exception:
            return False

    @method()
    def DeleteFirewallRule(self, name: 's') -> 'b':
        try:
            self.reload_config()
            rules_list = [r.model_dump() for r in self._config.firewall.rules if r.name != name]
            self.repository.save_firewall_config(FirewallConfig(firewall=FirewallSettings(port_forwards=self._config.firewall.port_forwards, rules=rules_list)))
            self.reload_config()
            self.SchedulesUpdated()
            return True
        except Exception:
            return False

    @method()
    def UpdateDevice(self, mac: 's', name: 's', owner_id: 's', location_id: 's', tags: 'as', static_ip: 's', upnp_trusted: 'b', upnp_allowed_ports_json: 's') -> 'b':
        try:
            self.reload_config()
            norm_mac = DeviceConfig.normalize_mac(mac)
            allowed_ports = json.loads(upnp_allowed_ports_json) if upnp_allowed_ports_json else []
            devices_list = [d.model_dump() for d in self._config.devices if d.mac != norm_mac]
            devices_list.append({
                "mac": norm_mac, "name": name, "owner": owner_id or None, "location": location_id or None,
                "tags": tags, "static_ip": static_ip or None, "upnp_trusted": upnp_trusted, "upnp_allowed_ports": allowed_ports
            })
            self.repository.save_devices_config(DevicesConfig(people=self._config.people, buildings=self._config.buildings, rooms=self._config.rooms, devices=devices_list))
            self.reload_config()
            self.DevicesUpdated()
            return True
        except Exception:
            return False

    @method()
    def DeleteDevice(self, mac: 's') -> 'b':
        try:
            self.reload_config()
            norm_mac = DeviceConfig.normalize_mac(mac)
            devices_list = [d.model_dump() for d in self._config.devices if d.mac != norm_mac]
            self.repository.save_devices_config(DevicesConfig(people=self._config.people, buildings=self._config.buildings, rooms=self._config.rooms, devices=devices_list))
            self.reload_config()
            self.DevicesUpdated()
            return True
        except Exception:
            return False
