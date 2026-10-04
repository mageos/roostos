"""Telemetry metrics collector for RoostOS system and subsystem performance."""

import os
import shutil
import time
import urllib.request
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from roostos_engine.models.system import TelemetryExportConfig
from roostos_engine.telemetry_manager import TelemetryManager


class MetricSample(BaseModel):
    """Represents a single time-series metric point."""
    name: str
    value: float
    labels: Dict[str, str] = Field(default_factory=dict)
    timestamp: Optional[int] = None


def format_prometheus_line(sample: MetricSample) -> str:
    """Formats a MetricSample into a Prometheus exposition text line."""
    if sample.labels:
        lbls = ",".join(f'{k}="{v}"' for k, v in sorted(sample.labels.items()))
        metric_str = f"{sample.name}{{{lbls}}} {sample.value}"
    else:
        metric_str = f"{sample.name} {sample.value}"
    if sample.timestamp:
        return f"{metric_str} {sample.timestamp}"
    return metric_str


class TelemetryCollector:
    """Collects system performance and RoostOS subsystem metrics, pushing to VictoriaMetrics & export targets."""

    def __init__(
        self,
        node_id: str = "node-01",
        telemetry_manager: Optional[TelemetryManager] = None,
        export_config: Optional[TelemetryExportConfig] = None,
    ) -> None:
        self.node_id = node_id
        self.telemetry_manager = telemetry_manager or TelemetryManager()
        self.export_config = export_config

    def collect_system_metrics(self) -> List[MetricSample]:
        """Collects host CPU, memory, disk, and network interface metrics."""
        samples: List[MetricSample] = []
        node_lbl = {"node": self.node_id}

        # 1. CPU Load
        if os.path.exists("/proc/loadavg"):
            try:
                with open("/proc/loadavg", "r") as f:
                    loads = f.read().split()
                    samples.append(MetricSample(name="system_cpu_load_1m", value=float(loads[0]), labels=node_lbl))
                    samples.append(MetricSample(name="system_cpu_load_5m", value=float(loads[1]), labels=node_lbl))
            except Exception:
                pass

        # 2. Memory Usage
        if os.path.exists("/proc/meminfo"):
            try:
                mem_total = 0.0
                mem_avail = 0.0
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            mem_total = float(line.split()[1]) * 1024.0
                        elif line.startswith("MemAvailable:"):
                            mem_avail = float(line.split()[1]) * 1024.0
                if mem_total > 0:
                    mem_used = mem_total - mem_avail
                    mem_pct = round((mem_used / mem_total) * 100.0, 2)
                    samples.append(MetricSample(name="system_memory_total_bytes", value=mem_total, labels=node_lbl))
                    samples.append(MetricSample(name="system_memory_used_bytes", value=mem_used, labels=node_lbl))
                    samples.append(MetricSample(name="system_memory_usage_percent", value=mem_pct, labels=node_lbl))
            except Exception:
                pass

        # 3. Disk Usage
        try:
            total, used, free = shutil.disk_usage("/")
            disk_pct = round((used / total) * 100.0, 2)
            disk_lbl = {"node": self.node_id, "mount": "/"}
            samples.append(MetricSample(name="system_disk_total_bytes", value=float(total), labels=disk_lbl))
            samples.append(MetricSample(name="system_disk_used_bytes", value=float(used), labels=disk_lbl))
            samples.append(MetricSample(name="system_disk_usage_percent", value=disk_pct, labels=disk_lbl))
        except Exception:
            pass

        # 4. Network Interfaces
        if os.path.exists("/proc/net/dev"):
            try:
                with open("/proc/net/dev", "r") as f:
                    for line in f.readlines()[2:]:
                        parts = line.strip().split()
                        if not parts:
                            continue
                        iface = parts[0].rstrip(":")
                        if iface in ("lo", ""):
                            continue
                        rx_bytes = float(parts[1])
                        rx_drop = float(parts[4])
                        tx_bytes = float(parts[9])
                        tx_drop = float(parts[12])
                        iface_lbl = {"node": self.node_id, "interface": iface}
                        samples.append(MetricSample(name="system_network_receive_bytes_total", value=rx_bytes, labels=iface_lbl))
                        samples.append(MetricSample(name="system_network_transmit_bytes_total", value=tx_bytes, labels=iface_lbl))
                        samples.append(MetricSample(name="system_network_receive_drop_total", value=rx_drop, labels=iface_lbl))
                        samples.append(MetricSample(name="system_network_transmit_drop_total", value=tx_drop, labels=iface_lbl))
            except Exception:
                pass

        return samples

    def collect_subsystem_metrics(
        self,
        active_dhcp_leases: int = 0,
        dns_queries_total: int = 0,
        dns_blocked_total: int = 0,
        quarantined_devices: int = 0,
        active_vpn_tunnels: int = 0,
    ) -> List[MetricSample]:
        """Collects RoostOS specific domain & security metrics."""
        node_lbl = {"node": self.node_id}
        return [
            MetricSample(name="roostos_dhcp_active_leases", value=float(active_dhcp_leases), labels=node_lbl),
            MetricSample(name="roostos_dns_queries_total", value=float(dns_queries_total), labels=node_lbl),
            MetricSample(name="roostos_dns_blocked_queries_total", value=float(dns_blocked_total), labels=node_lbl),
            MetricSample(name="roostos_firewall_quarantined_devices", value=float(quarantined_devices), labels=node_lbl),
            MetricSample(name="roostos_vpn_active_tunnels", value=float(active_vpn_tunnels), labels=node_lbl),
        ]

    def collect_all_metrics(
        self,
        active_dhcp_leases: int = 0,
        dns_queries_total: int = 0,
        dns_blocked_total: int = 0,
        quarantined_devices: int = 0,
        active_vpn_tunnels: int = 0,
    ) -> List[MetricSample]:
        """Collects combined system and subsystem metrics."""
        sys_samples = self.collect_system_metrics()
        sub_samples = self.collect_subsystem_metrics(
            active_dhcp_leases=active_dhcp_leases,
            dns_queries_total=dns_queries_total,
            dns_blocked_total=dns_blocked_total,
            quarantined_devices=quarantined_devices,
            active_vpn_tunnels=active_vpn_tunnels,
        )
        return sys_samples + sub_samples

    def push_metrics(self, samples: List[MetricSample]) -> bool:
        """Serializes samples and imports into VictoriaMetrics and any external export target."""
        if not samples:
            return True

        text_payload = "\n".join(format_prometheus_line(s) for s in samples) + "\n"
        success = self.telemetry_manager.import_prometheus_data(text_payload)

        # Mirror/Export to external endpoint if configured
        if self.export_config and self.export_config.enabled and self.export_config.endpoint:
            try:
                headers = {"Content-Type": "text/plain"}
                if self.export_config.headers:
                    headers.update(self.export_config.headers)
                req = urllib.request.Request(
                    self.export_config.endpoint,
                    data=text_payload.encode("utf-8"),
                    method="POST",
                    headers=headers,
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    pass
            except Exception:
                pass

        return success

    def collect_and_push(self, **kwargs) -> Tuple[bool, int]:
        """Convenience method to collect and immediately push metrics."""
        samples = self.collect_all_metrics(**kwargs)
        res = self.push_metrics(samples)
        return res, len(samples)
