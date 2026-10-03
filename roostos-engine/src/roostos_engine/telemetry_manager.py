"""VictoriaMetrics lifecycle management, health verification, and PromQL query service."""

import os
import shutil
import subprocess
import urllib.parse
import urllib.request
import urllib.error
import json
from typing import Dict, Any, Optional

from roostos_engine.models.system import TelemetryConfig


class TelemetryManager:
    """Manages VictoriaMetrics time-series database service and queries for RoostOS."""

    def __init__(
        self,
        config: Optional[TelemetryConfig] = None,
        config_dir: str = "/etc/roostos",
    ) -> None:
        self.config = config or TelemetryConfig()
        self.config_dir = config_dir
        self.listen_addr = self.config.listen_addr
        self.storage_path = self.config.storage_data_path
        self.retention = self.config.retention_period
        self._proc: Optional[subprocess.Popen] = None

    @property
    def base_url(self) -> str:
        """Returns the HTTP base URL for VictoriaMetrics."""
        host = self.listen_addr
        if ":" in host and not host.startswith("http"):
            return f"http://{host}"
        return f"http://{host}:8428" if not host.startswith("http") else host

    def is_binary_available(self) -> bool:
        """Checks if the VictoriaMetrics binary is installed on the host."""
        candidates = ["victoria-metrics-prod", "victoriametrics", "/usr/bin/victoria-metrics-prod"]
        return any(shutil.which(c) is not None or os.path.isfile(c) for c in candidates)

    def is_healthy(self) -> bool:
        """Pings the VictoriaMetrics /health HTTP endpoint."""
        url = f"{self.base_url}/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def query_instant(self, query: str, timestamp: Optional[float] = None) -> Dict[str, Any]:
        """Executes an instant PromQL expression against VictoriaMetrics."""
        params = {"query": query}
        if timestamp:
            params["time"] = str(timestamp)
        url = f"{self.base_url}/api/v1/query?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"status": "error", "errorType": "connection", "error": str(e), "data": {"result": []}}

    def query_range(
        self,
        query: str,
        start: float,
        end: float,
        step: str = "15s",
    ) -> Dict[str, Any]:
        """Executes a range PromQL expression over a time window."""
        params = {
            "query": query,
            "start": str(start),
            "end": str(end),
            "step": step,
        }
        url = f"{self.base_url}/api/v1/query_range?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            return {"status": "error", "errorType": "connection", "error": str(e), "data": {"result": []}}

    def import_prometheus_data(self, lines: str) -> bool:
        """Pushes raw Prometheus-formatted text metrics into VictoriaMetrics."""
        if not lines or not lines.strip():
            return True
        url = f"{self.base_url}/api/v1/import/prometheus"
        try:
            data = lines.strip().encode("utf-8")
            req = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "text/plain"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status in (200, 204)
        except Exception:
            return False

    def start_service(self) -> bool:
        """Attempts to start the victoriametrics systemd unit or binary."""
        if self.is_healthy():
            return True
        # Try systemctl first if systemd unit exists
        try:
            res = subprocess.run(["systemctl", "start", "victoriametrics"], capture_output=True, timeout=5)
            if res.returncode == 0 and self.is_healthy():
                return True
        except Exception:
            pass

        # Standalone binary fallback
        bin_path = shutil.which("victoria-metrics-prod") or shutil.which("victoriametrics")
        if bin_path:
            os.makedirs(self.storage_path, exist_ok=True)
            cmd = [
                bin_path,
                f"-storageDataPath={self.storage_path}",
                f"-httpListenAddr={self.listen_addr}",
                f"-retentionPeriod={self.retention}",
            ]
            try:
                self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                return False
        return False

    def stop_service(self) -> bool:
        """Stops the VictoriaMetrics service or standalone process."""
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2.0)
                self._proc = None
                return True
            except Exception:
                pass
        try:
            res = subprocess.run(["systemctl", "stop", "victoriametrics"], capture_output=True, timeout=5)
            return res.returncode == 0
        except Exception:
            return False
