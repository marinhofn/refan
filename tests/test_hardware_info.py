"""Snapshot de hardware e métricas de GPU (Fase E3, REP-3)."""

from unittest import mock

from src.utils.hardware_info import (
    get_hardware_info,
    sample_gpu_metrics,
)


class TestGetHardwareInfo:
    def test_required_keys_present(self):
        get_hardware_info.cache_clear()
        info = get_hardware_info()
        for key in ("os", "os_release", "machine", "python_version",
                    "cpu_count", "ram_gb", "num_gpu_layers", "gpu"):
            assert key in info

    def test_is_json_serializable(self):
        import json
        get_hardware_info.cache_clear()
        json.dumps(get_hardware_info())  # não pode levantar

    def test_cached_per_process(self):
        get_hardware_info.cache_clear()
        assert get_hardware_info() is get_hardware_info()


class TestSampleGpuMetrics:
    def test_without_nvidia_smi_returns_none_pair(self):
        with mock.patch(
            "src.utils.hardware_info.subprocess.run",
            side_effect=FileNotFoundError("nvidia-smi ausente"),
        ):
            assert sample_gpu_metrics() == (None, None)

    def test_parses_nvidia_smi_output(self):
        fake = mock.MagicMock(stdout="37, 8123\n")
        with mock.patch(
            "src.utils.hardware_info.subprocess.run", return_value=fake
        ):
            pct, mem = sample_gpu_metrics()
        assert pct == 37.0
        assert mem == 8123.0


class TestSettingsNumGpuLayers:
    def test_env_parsed_into_settings(self, monkeypatch):
        from src.core.settings import RefanSettings
        monkeypatch.setenv("REFAN_NUM_GPU_LAYERS", "60")
        assert RefanSettings().num_gpu_layers == 60
        monkeypatch.setenv("REFAN_NUM_GPU_LAYERS", "abc")
        assert RefanSettings().num_gpu_layers is None
        monkeypatch.delenv("REFAN_NUM_GPU_LAYERS")
        assert RefanSettings().num_gpu_layers is None

    def test_enters_config_snapshot(self, monkeypatch):
        from src.core.settings import RefanSettings
        monkeypatch.setenv("REFAN_NUM_GPU_LAYERS", "42")
        snapshot = RefanSettings().to_dict()
        assert snapshot["num_gpu_layers"] == 42


class TestHeartbeatGpuFields:
    def test_metrics_omitted_when_none_and_sent_when_present(self):
        import sys
        import pytest
        pytest.importorskip("supabase")
        from tests.test_supabase_client import make_client

        client, api = make_client()
        client.update_heartbeat(runner_id="r1")
        payload = api.table.return_value.upsert.call_args.args[0]
        assert "gpu_utilization_pct" not in payload
        assert "memory_used_mb" not in payload

        client.update_heartbeat(
            runner_id="r1", gpu_utilization_pct=55.0, memory_used_mb=9000.0
        )
        payload = api.table.return_value.upsert.call_args.args[0]
        assert payload["gpu_utilization_pct"] == 55.0
        assert payload["memory_used_mb"] == 9000.0
