"""Unit tests for scripts/gpu_detect.py — no hardware required."""

from __future__ import annotations

from scripts.gpu_detect import (
    GpuDetectionReport,
    VideoAdapter,
    detect_gpu_for_pytorch,
    dominant_discrete_vendor,
    parse_nvidia_smi_cuda_version,
    pytorch_index_url_for_cuda_tag,
    select_pytorch_cuda_wheel_tag,
    vendor_from_pnp_device_id,
)

# ---------------------------------------------------------------------------
# vendor_from_pnp_device_id
# ---------------------------------------------------------------------------

class TestVendorFromPnp:
    def test_nvidia(self):
        assert vendor_from_pnp_device_id("PCI\\VEN_10DE&DEV_2684&...") == "nvidia"

    def test_amd_1002(self):
        assert vendor_from_pnp_device_id("PCI\\VEN_1002&DEV_73DF&...") == "amd"

    def test_amd_1022(self):
        assert vendor_from_pnp_device_id("PCI\\VEN_1022&DEV_1234") == "amd"

    def test_intel(self):
        assert vendor_from_pnp_device_id("PCI\\VEN_8086&DEV_9BC4") == "intel"

    def test_microsoft(self):
        assert vendor_from_pnp_device_id("PCI\\VEN_1414&DEV_0001") == "microsoft"

    def test_unknown_vendor(self):
        assert vendor_from_pnp_device_id("PCI\\VEN_DEAD&DEV_BEEF") == "unknown"

    def test_none(self):
        assert vendor_from_pnp_device_id(None) == "unknown"

    def test_empty_string(self):
        assert vendor_from_pnp_device_id("") == "unknown"

    def test_no_ven_token(self):
        assert vendor_from_pnp_device_id("USB\\VID_046D&PID_C31C") == "unknown"

    def test_case_insensitive(self):
        assert vendor_from_pnp_device_id("pci\\ven_10de&dev_1234") == "nvidia"


# ---------------------------------------------------------------------------
# parse_nvidia_smi_cuda_version
# ---------------------------------------------------------------------------

class TestParseNvidiaSmiCuda:
    _SMI_SAMPLE = (
        "+-----------------------------------------------------------------------------+\n"
        "| NVIDIA-SMI 550.54.15    Driver Version: 550.54.15    CUDA Version: 12.4     |\n"
        "+-----------------------------------------------------------------------------+\n"
    )

    def test_typical_output(self):
        assert parse_nvidia_smi_cuda_version(self._SMI_SAMPLE) == (12, 4)

    def test_cuda_12_8(self):
        text = "CUDA Version: 12.8"
        assert parse_nvidia_smi_cuda_version(text) == (12, 8)

    def test_cuda_11_8(self):
        assert parse_nvidia_smi_cuda_version("CUDA Version: 11.8") == (11, 8)

    def test_no_cuda_line(self):
        assert parse_nvidia_smi_cuda_version("Driver Version: 550.54.15") is None

    def test_empty_string(self):
        assert parse_nvidia_smi_cuda_version("") is None

    def test_case_insensitive(self):
        assert parse_nvidia_smi_cuda_version("cuda version: 12.1") == (12, 1)


# ---------------------------------------------------------------------------
# select_pytorch_cuda_wheel_tag
# ---------------------------------------------------------------------------

class TestSelectPytorchCudaWheelTag:
    def test_cuda_12_8_gets_cu128(self):
        assert select_pytorch_cuda_wheel_tag((12, 8)) == "cu128"

    def test_cuda_12_9_still_cu128(self):
        # Newer-than-tracked driver → capped at newest confirmed wheel
        assert select_pytorch_cuda_wheel_tag((12, 9)) == "cu128"

    def test_cuda_12_6_gets_cu126(self):
        assert select_pytorch_cuda_wheel_tag((12, 6)) == "cu126"

    def test_cuda_12_4_gets_cu124(self):
        assert select_pytorch_cuda_wheel_tag((12, 4)) == "cu124"

    def test_cuda_12_1_gets_cu121(self):
        assert select_pytorch_cuda_wheel_tag((12, 1)) == "cu121"

    def test_cuda_11_8_gets_cu118(self):
        assert select_pytorch_cuda_wheel_tag((11, 8)) == "cu118"

    def test_cuda_11_7_too_old(self):
        assert select_pytorch_cuda_wheel_tag((11, 7)) is None

    def test_cuda_10_2_too_old(self):
        assert select_pytorch_cuda_wheel_tag((10, 2)) is None


# ---------------------------------------------------------------------------
# pytorch_index_url_for_cuda_tag
# ---------------------------------------------------------------------------

class TestPytorchIndexUrl:
    def test_cu128(self):
        assert pytorch_index_url_for_cuda_tag("cu128") == "https://download.pytorch.org/whl/cu128"

    def test_cu118(self):
        assert pytorch_index_url_for_cuda_tag("cu118") == "https://download.pytorch.org/whl/cu118"


# ---------------------------------------------------------------------------
# dominant_discrete_vendor
# ---------------------------------------------------------------------------

class TestDominantDiscreteVendor:
    def _adapter(self, pnp: str) -> VideoAdapter:
        return VideoAdapter(name="Test", driver_version=None, pnp_device_id=pnp)

    def test_nvidia_wins_over_intel(self):
        adapters = [
            self._adapter("PCI\\VEN_8086&DEV_1234"),  # intel
            self._adapter("PCI\\VEN_10DE&DEV_2684"),  # nvidia
        ]
        assert dominant_discrete_vendor(adapters) == "nvidia"

    def test_amd_beats_intel(self):
        adapters = [
            self._adapter("PCI\\VEN_8086&DEV_ABCD"),
            self._adapter("PCI\\VEN_1002&DEV_73DF"),
        ]
        assert dominant_discrete_vendor(adapters) == "amd"

    def test_intel_only(self):
        adapters = [self._adapter("PCI\\VEN_8086&DEV_9BC4")]
        assert dominant_discrete_vendor(adapters) == "intel"

    def test_empty_list(self):
        assert dominant_discrete_vendor([]) == "unknown"

    def test_unknown_pnp(self):
        adapters = [self._adapter("USB\\GARBAGE")]
        assert dominant_discrete_vendor(adapters) == "unknown"


# ---------------------------------------------------------------------------
# detect_gpu_for_pytorch (integration-ish — no real hardware needed)
# ---------------------------------------------------------------------------

class TestDetectGpuForPytorch:
    """Smoke-test the full detection path without hitting real hardware."""

    def test_returns_report_instance(self, monkeypatch):
        monkeypatch.setattr("scripts.gpu_detect.list_video_adapters_windows", lambda: ([], []))
        monkeypatch.setattr("scripts.gpu_detect.run_nvidia_smi", lambda: (127, "", "not found"))
        report = detect_gpu_for_pytorch()
        assert isinstance(report, GpuDetectionReport)

    def test_no_gpu_uses_cpu_index(self, monkeypatch):
        monkeypatch.setattr("scripts.gpu_detect.list_video_adapters_windows", lambda: ([], []))
        monkeypatch.setattr("scripts.gpu_detect.run_nvidia_smi", lambda: (127, "", "not found"))
        report = detect_gpu_for_pytorch()
        assert report.torch_path_kind == "cpu"
        assert "cpu" in report.pytorch_index_url

    def test_nvidia_smi_cuda_12_8_selects_cu128(self, monkeypatch):
        smi_out = "| NVIDIA-SMI 560.00    Driver Version: 560.00    CUDA Version: 12.8 |"
        monkeypatch.setattr("scripts.gpu_detect.list_video_adapters_windows", lambda: ([], []))
        monkeypatch.setattr("scripts.gpu_detect.run_nvidia_smi", lambda: (0, smi_out, ""))
        report = detect_gpu_for_pytorch()
        assert report.torch_path_kind == "nvidia_cuda"
        assert report.pytorch_cuda_wheel_tag == "cu128"
        assert "cu128" in report.pytorch_index_url

    def test_amd_adapter_no_smi_uses_directml(self, monkeypatch):
        amd = VideoAdapter(name="AMD Radeon RX 7900 XTX", driver_version=None,
                           pnp_device_id="PCI\\VEN_1002&DEV_744C")
        monkeypatch.setattr("scripts.gpu_detect.list_video_adapters_windows", lambda: ([amd], []))
        monkeypatch.setattr("scripts.gpu_detect.run_nvidia_smi", lambda: (127, "", "not found"))
        report = detect_gpu_for_pytorch()
        assert report.torch_path_kind == "amd_directml"

    def test_to_json_dict_serializable(self, monkeypatch):
        import json
        monkeypatch.setattr("scripts.gpu_detect.list_video_adapters_windows", lambda: ([], []))
        monkeypatch.setattr("scripts.gpu_detect.run_nvidia_smi", lambda: (127, "", "not found"))
        report = detect_gpu_for_pytorch()
        dumped = json.dumps(report.to_json_dict())
        assert isinstance(dumped, str)
