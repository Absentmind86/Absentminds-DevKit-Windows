"""Standalone GPU detection and PyTorch wheel index selection for Windows (Phase 1).

Run from anywhere::

    python scripts/gpu_detect.py
    python scripts/gpu_detect.py --json

This module is importable without executing ``main()`` — use
:class:`GpuDetectionReport` and :func:`detect_gpu_for_pytorch`.
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

VendorKind = Literal["nvidia", "amd", "intel", "microsoft", "unknown"]
TorchPathKind = Literal["nvidia_cuda", "cpu", "amd_directml"]

# Driver-reported maximum CUDA (from nvidia-smi) must be >= tuple to use that wheel line.
# Ordered highest-first. Capped at the newest CUDA wheel line that appears on PyTorch's
# stable "Start Locally" installer (https://pytorch.org/get-started/locally/) — do not add
# speculative cu* indexes above this without verifying the index exists on download.pytorch.org.
_NEWEST_CONFIRMED_PYTORCH_CUDA_WHEEL: tuple[str, tuple[int, int]] = ("cu128", (12, 8))
_PYTORCH_CUDA_WHEELS: list[tuple[str, tuple[int, int]]] = [
    _NEWEST_CONFIRMED_PYTORCH_CUDA_WHEEL,
    ("cu126", (12, 6)),
    ("cu124", (12, 4)),
    ("cu121", (12, 1)),
    ("cu118", (11, 8)),
]

_CPU_INDEX = "https://download.pytorch.org/whl/cpu"
_DIRECTML_NOTE = (
    "AMD GPU detected — torch-directml will be installed for DirectX 12 GPU acceleration. "
    "DirectML works on all AMD Radeon/RX GPUs on Windows and is faster than CPU for any "
    "real model workload. Note: torch-directml bundles its own PyTorch version."
)


def _which(executable: str) -> Path | None:
    """Return absolute path to *executable* on PATH, if found."""
    found = shutil.which(executable)
    return Path(found) if found else None


def _run_subprocess(
    argv: list[str],
    *,
    timeout_s: float = 45.0,
) -> tuple[int, str, str]:
    """Run a subprocess and return ``(returncode, stdout, stderr)`` as text."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def parse_nvidia_smi_cuda_version(nvidia_smi_text: str) -> tuple[int, int] | None:
    """Parse the *CUDA Version* reported by ``nvidia-smi`` (driver capability, not toolkit).

    Example line::

        | NVIDIA-SMI 550.54.15    Driver Version: 550.54.15    CUDA Version: 12.4 |
    """
    match = re.search(r"CUDA\s+Version:\s*(\d+)\.(\d+)", nvidia_smi_text, re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def select_pytorch_cuda_wheel_tag(driver_cuda: tuple[int, int]) -> str | None:
    """Pick the newest **published** ``cuXXX`` wheel line supported by *driver_cuda*.

    Selection is capped at the newest ``cu*`` entry in ``_PYTORCH_CUDA_WHEELS`` (currently
    matching PyTorch stable) so we never suggest a ``--index-url`` that has not been
    published yet.

    Returns ``None`` if the driver is too old for any bundled CUDA wheel we track
    (caller should fall back to CPU wheels).
    """
    for tag, minimum in _PYTORCH_CUDA_WHEELS:
        if driver_cuda >= minimum:
            return tag
    return None


def pytorch_index_url_for_cuda_tag(cuda_tag: str) -> str:
    """Return the PyTorch download index URL for a ``cuXXX`` tag."""
    return f"https://download.pytorch.org/whl/{cuda_tag}"


@dataclass(frozen=True)
class VideoAdapter:
    """One Windows display adapter from ``Win32_VideoController``."""

    name: str
    driver_version: str | None
    pnp_device_id: str | None


def vendor_from_pnp_device_id(pnp: str | None) -> VendorKind:
    """Infer hardware vendor from PCI ID in the PNP device string."""
    if not pnp:
        return "unknown"
    match = re.search(r"VEN_([0-9A-Fa-f]{4})", pnp, re.IGNORECASE)
    if not match:
        return "unknown"
    vid = match.group(1).upper()
    if vid == "10DE":
        return "nvidia"
    if vid in {"1002", "1022"}:
        return "amd"
    if vid == "8086":
        return "intel"
    if vid == "1414":
        return "microsoft"
    return "unknown"


def _powershell_json_array() -> str:
    """Return a PowerShell expression that emits JSON for all video controllers."""
    return (
        "Get-CimInstance -ClassName Win32_VideoController | "
        "Select-Object Name,DriverVersion,PNPDeviceID | "
        "ConvertTo-Json -Depth 4 -Compress"
    )


def list_video_adapters_windows() -> tuple[list[VideoAdapter], list[str]]:
    """Query display adapters via CIM (PowerShell). Returns ``(adapters, warnings)``."""
    warnings: list[str] = []
    ps = _which("powershell.exe")
    if ps is None:
        warnings.append("powershell.exe not found — cannot query Win32_VideoController.")
        return [], warnings

    code, out, err = _run_subprocess(
        [
            str(ps),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _powershell_json_array(),
        ]
    )
    if code != 0:
        warnings.append(f"Video adapter query failed (exit {code}): {err.strip() or out.strip()}")
        return [], warnings

    try:
        raw: Any = json.loads(out)
    except json.JSONDecodeError as exc:
        warnings.append(f"Could not parse adapter JSON: {exc}")
        return [], warnings

    items: list[dict[str, Any]]
    if isinstance(raw, dict):
        items = [raw]
    elif isinstance(raw, list):
        items = [x for x in raw if isinstance(x, dict)]
    else:
        warnings.append("Unexpected adapter JSON shape.")
        return [], warnings

    adapters: list[VideoAdapter] = []
    for row in items:
        name = str(row.get("Name") or "").strip()
        if not name:
            continue
        dv = row.get("DriverVersion")
        pnp = row.get("PNPDeviceID")
        adapters.append(
            VideoAdapter(
                name=name,
                driver_version=str(dv).strip() if dv is not None else None,
                pnp_device_id=str(pnp).strip() if pnp is not None else None,
            )
        )
    return adapters, warnings


def run_nvidia_smi() -> tuple[int, str, str]:
    """Run ``nvidia-smi`` if present. Returns ``(code, stdout, stderr)``."""
    exe = _which("nvidia-smi")
    if exe is None:
        return 127, "", "nvidia-smi not found on PATH"
    return _run_subprocess([str(exe)])


def dominant_discrete_vendor(adapters: list[VideoAdapter]) -> VendorKind:
    """Pick the best-effort discrete GPU vendor from adapter list (NVIDIA over AMD over Intel)."""
    vendors = [vendor_from_pnp_device_id(a.pnp_device_id) for a in adapters]
    if "nvidia" in vendors:
        return "nvidia"
    if "amd" in vendors:
        return "amd"
    if "intel" in vendors:
        return "intel"
    if "microsoft" in vendors:
        return "microsoft"
    return "unknown"


@dataclass
class GpuDetectionReport:
    """Structured result for PyTorch install planning."""

    platform_system: str
    torch_path_kind: TorchPathKind
    pytorch_index_url: str
    pytorch_cuda_wheel_tag: str | None
    nvidia_smi_ok: bool
    nvidia_driver_cuda: tuple[int, int] | None
    discrete_vendor: VendorKind
    adapters: list[VideoAdapter] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pip_command_example: list[str] = field(default_factory=list)
    human_summary: str = ""

    def to_json_dict(self) -> dict[str, Any]:
        """JSON-serializable dict (tuples become strings)."""
        data: dict[str, Any] = {
            "platform_system": self.platform_system,
            "torch_path_kind": self.torch_path_kind,
            "pytorch_index_url": self.pytorch_index_url,
            "pytorch_cuda_wheel_tag": self.pytorch_cuda_wheel_tag,
            "nvidia_smi_ok": self.nvidia_smi_ok,
            "nvidia_driver_cuda": (
                f"{self.nvidia_driver_cuda[0]}.{self.nvidia_driver_cuda[1]}"
                if self.nvidia_driver_cuda
                else None
            ),
            "discrete_vendor": self.discrete_vendor,
            "warnings": list(self.warnings),
            "pip_command_example": list(self.pip_command_example),
            "human_summary": self.human_summary,
            "adapters": [asdict(a) for a in self.adapters],
        }
        return data


def _build_pip_command(index_url: str) -> list[str]:
    return [
        "pip",
        "install",
        "torch",
        "torchvision",
        "torchaudio",
        "--index-url",
        index_url,
    ]


def detect_gpu_for_pytorch() -> GpuDetectionReport:
    """Detect GPUs on Windows and select a PyTorch ``pip --index-url`` line.

    Safe to call without elevated privileges. Does not install packages.
    """
    warnings: list[str] = []
    if platform.system() == "Windows":
        adapters, w_adapters = list_video_adapters_windows()
        warnings.extend(w_adapters)
    else:
        adapters = []
        warnings.append("Win32_VideoController scan skipped (non-Windows); nvidia-smi may still run.")

    smi_code, smi_out, smi_err = run_nvidia_smi()
    nvidia_smi_ok = smi_code == 0 and bool(smi_out.strip())
    driver_cuda = parse_nvidia_smi_cuda_version(smi_out) if nvidia_smi_ok else None
    if _which("nvidia-smi") is not None and smi_code not in (0, 127):
        warnings.append(
            f"nvidia-smi returned exit code {smi_code}: {smi_err.strip() or smi_out.strip()}"
        )
    if nvidia_smi_ok and driver_cuda is None:
        warnings.append("nvidia-smi ran but a CUDA Version line could not be parsed.")

    discrete = dominant_discrete_vendor(adapters)

    # Default path
    torch_path: TorchPathKind = "cpu"
    index_url = _CPU_INDEX
    cuda_tag: str | None = None

    if nvidia_smi_ok and driver_cuda is not None:
        tag = select_pytorch_cuda_wheel_tag(driver_cuda)
        if tag is not None:
            torch_path = "nvidia_cuda"
            cuda_tag = tag
            index_url = pytorch_index_url_for_cuda_tag(tag)
            cap_tag, cap_need = _NEWEST_CONFIRMED_PYTORCH_CUDA_WHEEL
            if tag == cap_tag and driver_cuda > cap_need:
                warnings.append(
                    f"Driver reports CUDA {driver_cuda[0]}.{driver_cuda[1]} (newer than {cap_tag}); "
                    f"capped to newest confirmed stable wheel line ({cap_tag})."
                )
        else:
            warnings.append(
                f"Driver reports CUDA {driver_cuda[0]}.{driver_cuda[1]}, "
                "below tracked PyTorch CUDA wheels — using CPU index."
            )
    elif discrete == "nvidia":
        warnings.append(
            "NVIDIA hardware reported by WMI but nvidia-smi did not run successfully — "
            "verify driver installation; using CPU PyTorch index until then."
        )
    elif discrete == "amd":
        torch_path = "amd_directml"
        index_url = _CPU_INDEX  # DirectML is pip-installed from PyPI, not the torch CDN
        warnings.append(_DIRECTML_NOTE)
    elif discrete in {"intel", "microsoft"}:
        warnings.append(
            "No NVIDIA path selected — PyTorch GPU on this configuration typically "
            "uses CPU wheels unless you add vendor-specific runtimes manually."
        )

    pip_cmd = _build_pip_command(index_url)

    if torch_path == "nvidia_cuda" and driver_cuda is not None and cuda_tag is not None:
        summary = (
            "✅ NVIDIA path: nvidia-smi reports driver CUDA "
            f"{driver_cuda[0]}.{driver_cuda[1]} — use PyTorch wheels from {index_url} "
            f"({cuda_tag})."
        )
    elif nvidia_smi_ok and driver_cuda is not None and torch_path == "cpu":
        summary = (
            f"⚠️ NVIDIA driver reports CUDA {driver_cuda[0]}.{driver_cuda[1]}, "
            "below tracked PyTorch CUDA wheel lines — using CPU index."
        )
    elif torch_path == "amd_directml":
        summary = "✅ AMD GPU detected — torch-directml (DirectX 12 GPU acceleration) will be installed."
    else:
        summary = "⚠️ CPU-only PyTorch index recommended (no working NVIDIA CUDA path detected)."

    return GpuDetectionReport(
        platform_system=platform.system(),
        torch_path_kind=torch_path,
        pytorch_index_url=index_url,
        pytorch_cuda_wheel_tag=cuda_tag,
        nvidia_smi_ok=nvidia_smi_ok,
        nvidia_driver_cuda=driver_cuda,
        discrete_vendor=discrete,
        adapters=adapters,
        warnings=warnings,
        pip_command_example=pip_cmd,
        human_summary=summary,
    )


def format_human_report(report: GpuDetectionReport) -> str:
    """Multi-line human-readable report (PROJECT.md style hints)."""
    lines: list[str] = [
        "AM-DevKit — GPU / PyTorch index detection",
        "",
        report.human_summary,
        "",
        f"Discrete vendor (WMI / PnP): {report.discrete_vendor}",
        f"PyTorch index URL: {report.pytorch_index_url}",
        "Suggested pip command:",
        "  " + " ".join(report.pip_command_example),
        "",
    ]
    if report.adapters:
        lines.append("Video adapters:")
        for a in report.adapters:
            lines.append(f"  - {a.name} [{vendor_from_pnp_device_id(a.pnp_device_id)}]")
        lines.append("")
    if report.warnings:
        lines.append("Warnings / notes:")
        for w in report.warnings:
            lines.append(f"  ⚠️ {w}")
    return "\n".join(lines).rstrip() + "\n"


def _configure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    _configure_stdout_utf8()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit a JSON object suitable for tooling / manifest fields.",
    )
    args = parser.parse_args(argv)

    if platform.system() != "Windows":
        sys.stderr.write("gpu_detect.py: intended for Windows; detection may be incomplete.\n")

    report = detect_gpu_for_pytorch()
    if args.json:
        sys.stdout.write(json.dumps(report.to_json_dict(), indent=2) + "\n")
    else:
        sys.stdout.write(format_human_report(report))
    return 0


__all__ = [
    "GpuDetectionReport",
    "VideoAdapter",
    "detect_gpu_for_pytorch",
    "format_human_report",
    "main",
    "parse_nvidia_smi_cuda_version",
    "pytorch_index_url_for_cuda_tag",
    "run_nvidia_smi",
    "select_pytorch_cuda_wheel_tag",
    "vendor_from_pnp_device_id",
    "list_video_adapters_windows",
]

if __name__ == "__main__":
    raise SystemExit(main())
