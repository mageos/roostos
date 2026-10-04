"""Unit tests for RoostOS VictoriaMetrics telemetry manager and collector."""

import io
import json
import urllib.request
from unittest.mock import patch, MagicMock
import pytest

from roostos_engine.models.system import TelemetryConfig, TelemetryExportConfig
from roostos_engine.telemetry_manager import TelemetryManager
from roostos_engine.telemetry_collector import (
    MetricSample,
    format_prometheus_line,
    TelemetryCollector,
)


def test_metric_sample_prometheus_formatting():
    sample1 = MetricSample(name="system_cpu_usage", value=42.5)
    assert format_prometheus_line(sample1) == "system_cpu_usage 42.5"

    sample2 = MetricSample(name="system_mem_used", value=1024.0, labels={"node": "node-01", "role": "gateway"})
    assert format_prometheus_line(sample2) == 'system_mem_used{node="node-01",role="gateway"} 1024.0'

    sample3 = MetricSample(name="dhcp_leases", value=5.0, labels={"node": "node-01"}, timestamp=1700000000000)
    assert format_prometheus_line(sample3) == 'dhcp_leases{node="node-01"} 5.0 1700000000000'


def test_telemetry_manager_base_url():
    mgr1 = TelemetryManager(TelemetryConfig(listen_addr="127.0.0.1:8428"))
    assert mgr1.base_url == "http://127.0.0.1:8428"

    mgr2 = TelemetryManager(TelemetryConfig(listen_addr="http://vm-server.local:8428"))
    assert mgr2.base_url == "http://vm-server.local:8428"


def test_telemetry_manager_health_check():
    mgr = TelemetryManager()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        assert mgr.is_healthy() is True

    with patch("urllib.request.urlopen", side_effect=Exception("Connection refused")):
        assert mgr.is_healthy() is False


def test_telemetry_manager_query_instant():
    mgr = TelemetryManager()
    fake_response = {
        "status": "success",
        "data": {
            "resultType": "vector",
            "result": [
                {"metric": {"__name__": "system_cpu_load_1m", "node": "node-01"}, "value": [1700000000, "1.25"]}
            ]
        }
    }
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        res = mgr.query_instant("system_cpu_load_1m")
        assert res["status"] == "success"
        assert len(res["data"]["result"]) == 1
        assert res["data"]["result"][0]["value"][1] == "1.25"


def test_telemetry_manager_import_prometheus():
    mgr = TelemetryManager()
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        assert mgr.import_prometheus_data("system_cpu_load 0.5\n") is True
        # Verify request parameters
        req: urllib.request.Request = mock_urlopen.call_args[0][0]
        assert req.get_method() == "POST"
        assert req.get_full_url() == "http://127.0.0.1:8428/api/v1/import/prometheus"
        assert req.data == b"system_cpu_load 0.5"


def test_telemetry_collector_system_and_subsystem_metrics():
    mgr = MagicMock(spec=TelemetryManager)
    collector = TelemetryCollector(node_id="gateway-01", telemetry_manager=mgr)

    samples = collector.collect_all_metrics(
        active_dhcp_leases=8,
        dns_queries_total=1500,
        dns_blocked_total=120,
        quarantined_devices=1,
        active_vpn_tunnels=2,
    )
    metric_names = {s.name for s in samples}

    assert "roostos_dhcp_active_leases" in metric_names
    assert "roostos_dns_queries_total" in metric_names
    assert "roostos_dns_blocked_queries_total" in metric_names
    assert "roostos_firewall_quarantined_devices" in metric_names
    assert "roostos_vpn_active_tunnels" in metric_names

    for s in samples:
        assert s.labels.get("node") == "gateway-01"


def test_telemetry_collector_push_and_external_export():
    mgr = MagicMock(spec=TelemetryManager)
    mgr.import_prometheus_data.return_value = True

    export_cfg = TelemetryExportConfig(
        enabled=True,
        endpoint="https://external-otel.example.com/v1/metrics",
        headers={"Authorization": "Bearer test-token"},
    )
    collector = TelemetryCollector(node_id="node-01", telemetry_manager=mgr, export_config=export_cfg)

    samples = [MetricSample(name="test_metric", value=100.0, labels={"node": "node-01"})]

    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        success = collector.push_metrics(samples)
        assert success is True

        mgr.import_prometheus_data.assert_called_once()
        # Verify external export was invoked with headers
        assert mock_urlopen.call_count == 1
        export_req: urllib.request.Request = mock_urlopen.call_args[0][0]
        assert export_req.get_full_url() == "https://external-otel.example.com/v1/metrics"
        assert export_req.headers.get("Authorization") == "Bearer test-token"
