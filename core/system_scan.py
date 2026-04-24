"""Layer 0: hardware and environment scan producing ``system-profile.json`` (Phase 1).

Run::

    python core/system_scan.py
    python core/system_scan.py --output path/to/system-profile.json
    python core/system_scan.py --json

``--json`` writes the profile document to stdout (no default file write).
"""

from __future__ import annotations

import argparse
import json
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Final

_SCHEMA_VERSION: Final[str] = "1.1"

# Manufacturer / model substrings (lowercase) that indicate a virtual machine.
# Hit on Win32_ComputerSystem.Manufacturer or .Model.
_VM_HINTS: Final[tuple[tuple[str, str], ...]] = (
    ("vmware", "VMware"),
    ("virtualbox", "VirtualBox"),
    ("vbox", "VirtualBox"),
    ("kvm", "KVM"),
    ("qemu", "QEMU"),
    ("xen", "Xen"),
    ("microsoft corporation", "Hyper-V"),  # Hyper-V guests report this
    ("virtual machine", "Hyper-V"),
    ("parallels", "Parallels"),
    ("bhyve", "bhyve"),
    ("innotek", "VirtualBox"),
)
_LOW_DISK_BYTES: Final[int] = 20 * 1024 * 1024 * 1024
_DRIVER_STALE_DAYS: Final[int] = 540  # ~18 months
_WMI_QUERY_TIMEOUT_S: Final[float] = 60.0


def _repo_root() -> Path:
    """Return repository root (parent of ``core``)."""
    return Path(__file__).resolve().parents[1]


def _ensure_repo_on_sys_path() -> None:
    """Allow ``from scripts.gpu_detect import …`` when running as a script."""
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def _which(executable: str) -> Path | None:
    found = shutil.which(executable)
    return Path(found) if found else None


def _run_subprocess(
    argv: list[str],
    *,
    timeout_s: float = _WMI_QUERY_TIMEOUT_S,
) -> tuple[int, str, str]:
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


def _powershell_exe() -> Path | None:
    return _which("powershell.exe")


def _wmi_payload_json() -> str:
    """PowerShell that emits one JSON object with Layer 0 WMI facts."""
    return r"""
$ErrorActionPreference = 'Stop'
try {
function SafeString($x) {
  if ($null -eq $x) { return $null }
  return "$x"
}
$processors = @(Get-CimInstance Win32_Processor | ForEach-Object {
  [ordered]@{
    Manufacturer = SafeString $_.Manufacturer
    Name           = SafeString $_.Name
    NumberOfCores  = [int]$_.NumberOfCores
    NumberOfLogicalProcessors = [int]$_.NumberOfLogicalProcessors
  }
})
$os = Get-CimInstance Win32_OperatingSystem | Select-Object -First 1
$osObj = [ordered]@{
  Caption            = SafeString $os.Caption
  Version            = SafeString $os.Version
  BuildNumber        = SafeString $os.BuildNumber
  OSArchitecture     = SafeString $os.OSArchitecture
  SystemDrive        = SafeString $os.SystemDrive
  WindowsDirectory   = SafeString $os.WindowsDirectory
  FreePhysicalMemoryKB = if ($null -ne $os.FreePhysicalMemory) { [int64]$os.FreePhysicalMemory } else { $null }
  TotalVisibleMemoryKB = if ($null -ne $os.TotalVisibleMemorySize) { [int64]$os.TotalVisibleMemorySize } else { $null }
}
$cs = Get-CimInstance Win32_ComputerSystem | Select-Object -First 1
$csObj = [ordered]@{
  Manufacturer = SafeString $cs.Manufacturer
  Model          = SafeString $cs.Model
  TotalPhysicalMemoryBytes = if ($null -ne $cs.TotalPhysicalMemory) { [int64]$cs.TotalPhysicalMemory } else { $null }
}
$logicalDisks = @(Get-CimInstance Win32_LogicalDisk | Where-Object { $_.DriveType -eq 3 } | ForEach-Object {
  [ordered]@{
    DeviceID    = SafeString $_.DeviceID
    VolumeName  = SafeString $_.VolumeName
    FileSystem  = SafeString $_.FileSystem
    SizeBytes   = if ($null -ne $_.Size) { [int64]$_.Size } else { $null }
    FreeBytes   = if ($null -ne $_.FreeSpace) { [int64]$_.FreeSpace } else { $null }
  }
})
$physicalDisks = @(Get-CimInstance Win32_DiskDrive | ForEach-Object {
  [ordered]@{
    Model         = SafeString $_.Model
    InterfaceType = SafeString $_.InterfaceType
    MediaType     = SafeString $_.MediaType
    SizeBytes     = if ($null -ne $_.Size) { [int64]$_.Size } else { $null }
    SerialNumber  = SafeString $_.SerialNumber
  }
})
$videos = @(Get-CimInstance Win32_VideoController | ForEach-Object {
  $dd = $null
  if ($null -ne $_.DriverDate) {
    try { $dd = $_.DriverDate.ToString('o') } catch { $dd = SafeString $_.DriverDate }
  }
  [ordered]@{
    Name           = SafeString $_.Name
    AdapterRAM     = if ($null -ne $_.AdapterRAM) { [int64]$_.AdapterRAM } else { $null }
    DriverVersion  = SafeString $_.DriverVersion
    DriverDate     = $dd
    PNPDeviceID    = SafeString $_.PNPDeviceID
  }
})
[PSCustomObject]@{
  processors     = $processors
  operatingSystem = $osObj
  computerSystem = $csObj
  logicalDisks   = $logicalDisks
  physicalDisks  = $physicalDisks
  videoControllers = $videos
} | ConvertTo-Json -Depth 8 -Compress
} catch {
  @{ wmi_error = $_.Exception.Message } | ConvertTo-Json -Compress
}
"""


def query_wmi_layer0() -> tuple[dict[str, Any] | None, list[str]]:
    """Query WMI/CIM for hardware facts. Returns ``(payload, warnings)``."""
    warnings: list[str] = []
    if platform.system() != "Windows":
        warnings.append("WMI scan skipped: not Windows.")
        return None, warnings

    ps = _powershell_exe()
    if ps is None:
        warnings.append("powershell.exe not found — WMI scan unavailable.")
        return None, warnings

    code, out, err = _run_subprocess(
        [
            str(ps),
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _wmi_payload_json(),
        ],
        timeout_s=_WMI_QUERY_TIMEOUT_S,
    )
    if code != 0:
        warnings.append(f"WMI PowerShell failed (exit {code}): {err.strip() or out.strip()}")
        return None, warnings
    try:
        data = json.loads(out)
    except json.JSONDecodeError as exc:
        warnings.append(f"WMI JSON parse error: {exc}")
        return None, warnings
    if not isinstance(data, dict):
        warnings.append("WMI JSON root is not an object.")
        return None, warnings
    if data.get("wmi_error"):
        warnings.append(f"WMI query error: {data.get('wmi_error')}")
        return None, warnings
    return data, warnings


def _as_list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        return [value]
    return []


def _detect_vm(wmi: dict[str, Any]) -> tuple[bool, str | None]:
    """Best-effort virtualization detection from Win32_ComputerSystem.

    Returns ``(is_vm, hint)`` where *hint* is a short hypervisor name
    ("VMware", "Hyper-V", …) or ``None`` when nothing matched.
    """
    cs = wmi.get("computerSystem") if isinstance(wmi.get("computerSystem"), dict) else {}
    haystack = " ".join(
        str(cs.get(k) or "") for k in ("Manufacturer", "Model")
    ).lower()
    if not haystack.strip():
        return False, None
    for needle, label in _VM_HINTS:
        if needle in haystack:
            return True, label
    return False, None


def _cpu_from_wmi(wmi: dict[str, Any]) -> dict[str, Any]:
    rows = _as_list_of_dicts(wmi.get("processors"))
    if not rows:
        return {
            "vendor": None,
            "model": None,
            "physical_cores": 0,
            "logical_processors": 0,
            "socket_count": 0,
        }
    vendor = next((r.get("Manufacturer") for r in rows if r.get("Manufacturer")), None)
    models = [str(r.get("Name") or "").strip() for r in rows if r.get("Name")]
    model = "; ".join(models) if models else None
    cores = sum(int(r.get("NumberOfCores") or 0) for r in rows)
    threads = sum(int(r.get("NumberOfLogicalProcessors") or 0) for r in rows)
    return {
        "vendor": vendor,
        "model": model,
        "physical_cores": cores,
        "logical_processors": threads,
        "socket_count": len(rows),
    }


def _memory_from_wmi(wmi: dict[str, Any]) -> dict[str, Any]:
    cs = wmi.get("computerSystem") if isinstance(wmi.get("computerSystem"), dict) else {}
    os_ = wmi.get("operatingSystem") if isinstance(wmi.get("operatingSystem"), dict) else {}
    total = cs.get("TotalPhysicalMemoryBytes")
    free_kb = os_.get("FreePhysicalMemoryKB")
    total_bytes = int(total) if isinstance(total, int) else None
    free_bytes: int | None = None
    if isinstance(free_kb, int):
        free_bytes = free_kb * 1024
    return {
        "total_bytes": total_bytes,
        "free_bytes": free_bytes,
    }


def _os_from_wmi(wmi: dict[str, Any]) -> dict[str, Any]:
    os_ = wmi.get("operatingSystem") if isinstance(wmi.get("operatingSystem"), dict) else {}
    return {
        "caption": os_.get("Caption"),
        "version": os_.get("Version"),
        "build": os_.get("BuildNumber"),
        "architecture": os_.get("OSArchitecture"),
        "system_drive": os_.get("SystemDrive"),
        "windows_directory": os_.get("WindowsDirectory"),
    }


def _classify_disk_kind(interface_type: str | None, media_type: str | None) -> str:
    it = (interface_type or "").upper()
    mt = (media_type or "").upper()
    if "NVME" in it or "NVME" in mt:
        return "nvme"
    if "SSD" in mt or "SOLID STATE" in mt:
        return "ssd"
    if "USB" in it:
        return "usb"
    if "IDE" in it or "SATA" in it or "SCSI" in it:
        return "sata"
    if "FIXED" in mt:
        return "fixed"
    return "unknown"


def _storage_from_wmi(wmi: dict[str, Any]) -> dict[str, Any]:
    logical = _as_list_of_dicts(wmi.get("logicalDisks"))
    physical = _as_list_of_dicts(wmi.get("physicalDisks"))
    vols: list[dict[str, Any]] = []
    for row in logical:
        vols.append(
            {
                "device": row.get("DeviceID"),
                "label": row.get("VolumeName"),
                "filesystem": row.get("FileSystem"),
                "size_bytes": row.get("SizeBytes"),
                "free_bytes": row.get("FreeBytes"),
            }
        )
    disks: list[dict[str, Any]] = []
    for row in physical:
        disks.append(
            {
                "model": row.get("Model"),
                "interface_type": row.get("InterfaceType"),
                "media_type": row.get("MediaType"),
                "kind": _classify_disk_kind(
                    str(row.get("InterfaceType") or ""),
                    str(row.get("MediaType") or ""),
                ),
                "size_bytes": row.get("SizeBytes"),
                "serial": row.get("SerialNumber"),
            }
        )
    return {"volumes": vols, "physical_disks": disks}


def _parse_wmi_driver_date(raw: str | None) -> datetime | None:
    if not raw:
        return None
    raw = raw.strip()
    iso_try = re.match(r"^(\d{4})-(\d{2})-(\d{2})", raw)
    if iso_try:
        try:
            return datetime(
                int(iso_try.group(1)),
                int(iso_try.group(2)),
                int(iso_try.group(3)),
                tzinfo=timezone.utc,
            )
        except ValueError:
            return None
    m = re.match(r"/Date\((\d+)\)/", raw)
    if m:
        try:
            ms = int(m.group(1))
            return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        except (OSError, ValueError, OverflowError):
            return None
    if len(raw) >= 8 and raw[:8].isdigit():
        try:
            return datetime(int(raw[0:4]), int(raw[4:6]), int(raw[6:8]), tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _gpus_from_wmi(
    wmi: dict[str, Any],
    vendor_fn: Callable[[str | None], str],
) -> list[dict[str, Any]]:
    rows = _as_list_of_dicts(wmi.get("videoControllers"))
    out: list[dict[str, Any]] = []
    for row in rows:
        name = str(row.get("Name") or "").strip()
        if not name:
            continue
        pnp = row.get("PNPDeviceID")
        pnp_s = str(pnp).strip() if pnp else None
        vendor = vendor_fn(pnp_s)
        ram = row.get("AdapterRAM")
        vram: int | None = int(ram) if isinstance(ram, int) else None
        out.append(
            {
                "vendor": vendor,
                "model": name,
                "vram_bytes_wmi": vram,
                "driver_version": row.get("DriverVersion"),
                "driver_date_raw": row.get("DriverDate"),
                "pnp_device_id": pnp_s,
            }
        )
    return out


def probe_command_on_path(commands: list[str]) -> dict[str, Any]:
    """Return ``{"present": bool, "path": str | null}`` for the first found executable."""
    for cmd in commands:
        path = shutil.which(cmd)
        if path:
            return {"present": True, "path": path}
    return {"present": False, "path": None}


def probe_existing_installs() -> dict[str, Any]:
    """Lightweight PATH probes for common dev tools (no package installs)."""
    keys: dict[str, list[str]] = {
        "git": ["git"],
        "python": ["python", "python3"],
        "py_launcher": ["py"],
        "winget": ["winget"],
        "vscode": ["code"],
        "cursor": ["cursor"],
        "scoop": ["scoop"],
        "nvcc": ["nvcc"],
        "docker": ["docker"],
        "node": ["node"],
        "npm": ["npm"],
    }
    return {name: probe_command_on_path(cmds) for name, cmds in keys.items()}


def measure_http_head_latency_ms(url: str, timeout_s: float = 5.0) -> tuple[float | None, str | None]:
    """Return ``(latency_ms, error_message)`` for a small HTTPS GET (204/empty body preferred)."""
    t0 = time.perf_counter()
    try:
        req = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "AM-DevKit-system-scan/1.0"},
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            _ = resp.status
    except urllib.error.HTTPError as exc:
        if exc.code in (204, 404, 405):
            t1 = time.perf_counter()
            return (t1 - t0) * 1000.0, None
        return None, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, str(exc.reason if hasattr(exc, "reason") else exc)
    except TimeoutError:
        return None, "timeout"
    except OSError as exc:
        return None, str(exc)
    t1 = time.perf_counter()
    return (t1 - t0) * 1000.0, None


def collect_warnings(
    system_profile: dict[str, Any],
) -> list[str]:
    """Append scan warnings (disk, drivers, CUDA hints) into *system_profile*."""
    extra: list[str] = []
    storage = system_profile.get("storage") if isinstance(system_profile.get("storage"), dict) else {}
    volumes = storage.get("volumes") if isinstance(storage.get("volumes"), list) else []
    os_ = system_profile.get("os") if isinstance(system_profile.get("os"), dict) else {}
    boot = str(os_.get("system_drive") or "C:").rstrip("\\").upper()
    for v in volumes:
        if not isinstance(v, dict):
            continue
        dev = str(v.get("device") or "").rstrip("\\").upper()
        if dev != boot and not dev.startswith(boot):
            continue
        free = v.get("free_bytes")
        if isinstance(free, int) and free < _LOW_DISK_BYTES:
            extra.append(
                f"Low free space on {v.get('device')} ({free // (1024 * 1024 * 1024)} GiB free; "
                f"recommend at least {_LOW_DISK_BYTES // (1024 * 1024 * 1024)} GiB for full installs)."
            )
            break
    now = datetime.now(timezone.utc)
    gpus = system_profile.get("gpus") if isinstance(system_profile.get("gpus"), list) else []
    driver_warned = False
    for g in gpus:
        if not isinstance(g, dict):
            continue
        if g.get("vendor") != "nvidia" or driver_warned:
            continue
        raw = g.get("driver_date_raw")
        if not isinstance(raw, str):
            continue
        dt = _parse_wmi_driver_date(raw)
        if dt is None:
            continue
        age_days = (now - dt).days
        if age_days > _DRIVER_STALE_DAYS:
            extra.append(
                f"NVIDIA driver may be outdated (WMI driver date ~{age_days} days old) — "
                "consider updating for CUDA / PyTorch compatibility."
            )
            driver_warned = True
    pytorch = system_profile.get("pytorch") if isinstance(system_profile.get("pytorch"), dict) else {}
    existing = (
        system_profile.get("existing_installs")
        if isinstance(system_profile.get("existing_installs"), dict)
        else {}
    )
    nvcc = existing.get("nvcc") if isinstance(existing.get("nvcc"), dict) else {}
    if gpus and any(isinstance(g, dict) and g.get("vendor") == "nvidia" for g in gpus):
        if not nvcc.get("present") and pytorch.get("torch_path_kind") == "nvidia_cuda":
            extra.append(
                "NVIDIA GPU with CUDA-capable driver detected, but nvcc was not found on PATH — "
                "PyTorch wheels bundle their own CUDA runtime; toolkit optional unless you compile extensions."
            )
    sysblock = system_profile.get("system") if isinstance(system_profile.get("system"), dict) else {}
    if sysblock.get("is_vm"):
        hint = sysblock.get("vm_hint") or "virtual machine"
        extra.append(
            f"Virtualized host detected ({hint}). GPU passthrough is uncommon — "
            "CUDA / DirectML wheels may fall back to CPU and WSL2 nesting may be unsupported."
        )
    base = list(system_profile.get("warnings") or [])
    system_profile["warnings"] = list(dict.fromkeys([*base, *extra]))
    return system_profile["warnings"]


def build_system_profile(
    *,
    wmi_payload: dict[str, Any] | None = None,
    wmi_warnings: list[str] | None = None,
) -> dict[str, Any]:
    """Assemble the ``system-profile.json`` document.

    If *wmi_payload* is ``None`` and the host is Windows, WMI is queried automatically.
    Pass a pre-fetched payload in tests.
    """
    _ensure_repo_on_sys_path()
    from scripts.gpu_detect import detect_gpu_for_pytorch, vendor_from_pnp_device_id

    warnings: list[str] = list(wmi_warnings or [])
    if wmi_payload is not None:
        wmi: dict[str, Any] = wmi_payload
    elif platform.system() == "Windows":
        fetched, w_warn = query_wmi_layer0()
        warnings.extend(w_warn)
        wmi = fetched if fetched is not None else {}
    else:
        wmi = {}

    cpu = _cpu_from_wmi(wmi)
    memory = _memory_from_wmi(wmi)
    os_info = _os_from_wmi(wmi)
    storage = _storage_from_wmi(wmi)
    gpus = _gpus_from_wmi(wmi, vendor_from_pnp_device_id)
    is_vm, vm_hint = _detect_vm(wmi)
    cs = wmi.get("computerSystem") if isinstance(wmi.get("computerSystem"), dict) else {}
    system_block: dict[str, Any] = {
        "manufacturer": cs.get("Manufacturer"),
        "model": cs.get("Model"),
        "is_vm": is_vm,
        "vm_hint": vm_hint,
    }

    net_url = "https://connectivitycheck.gstatic.com/generate_204"
    net_ms, net_err = measure_http_head_latency_ms(net_url)
    network: dict[str, Any] = {
        "probe_latency_ms": net_ms,
        "probe_url": net_url,
        "error": net_err,
    }
    if net_err:
        warnings.append(f"Network latency probe failed: {net_err}")

    gpu_report = detect_gpu_for_pytorch()
    pytorch_block: dict[str, Any] = {
        **gpu_report.to_json_dict(),
    }

    profile: dict[str, Any] = {
        "schema_version": _SCHEMA_VERSION,
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "machine": platform.machine(),
            "python_version": platform.python_version(),
        },
        "system": system_block,
        "os": os_info,
        "cpu": cpu,
        "memory": memory,
        "storage": storage,
        "gpus": gpus,
        "network": network,
        "existing_installs": probe_existing_installs(),
        "pytorch": pytorch_block,
        "warnings": warnings + list(pytorch_block.get("warnings") or []),
    }
    profile["warnings"] = list(dict.fromkeys(profile["warnings"]))
    collect_warnings(profile)
    return profile


def write_system_profile(profile: dict[str, Any], output_path: Path) -> None:
    """Write *profile* as UTF-8 JSON with stable formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(profile, indent=2, sort_keys=False) + "\n"
    output_path.write_text(text, encoding="utf-8")


def format_human_summary(profile: dict[str, Any]) -> str:
    """Readable multi-line summary for CLI / bootstrap."""
    lines = [
        "AM-DevKit — Layer 0 system scan",
        "",
        f"Schema: {profile.get('schema_version')}",
        f"Generated (UTC): {profile.get('generated_at_utc')}",
        "",
        "OS:",
        f"  {profile.get('os', {}).get('caption')}",
        f"  Build {profile.get('os', {}).get('build')}  ({profile.get('os', {}).get('architecture')})",
        "",
        "CPU:",
        f"  {profile.get('cpu', {}).get('vendor')}  {profile.get('cpu', {}).get('model')}",
        f"  Cores / threads: {profile.get('cpu', {}).get('physical_cores')} / "
        f"{profile.get('cpu', {}).get('logical_processors')}",
        "",
        "Memory:",
        f"  Total bytes: {profile.get('memory', {}).get('total_bytes')}",
        f"  Free bytes (approx): {profile.get('memory', {}).get('free_bytes')}",
        "",
        "Primary PyTorch suggestion:",
        f"  {profile.get('pytorch', {}).get('human_summary', '').strip()}",
        f"  Index URL: {profile.get('pytorch', {}).get('pytorch_index_url')}",
        "",
    ]
    warns = profile.get("warnings") or []
    if warns:
        lines.append("Warnings:")
        for w in warns:
            lines.append(f"  ⚠️ {w}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _configure_stdout_utf8() -> None:
    """Avoid ``UnicodeEncodeError`` on cp1252 consoles when printing summaries."""
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
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write JSON to this path (default: system-profile.json in the current directory).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the profile JSON to stdout instead of writing a file.",
    )
    args = parser.parse_args(argv)

    profile = build_system_profile()

    if args.json:
        sys.stdout.write(json.dumps(profile, indent=2) + "\n")
        return 0

    out = args.output if args.output is not None else Path.cwd() / "system-profile.json"
    write_system_profile(profile, out)
    sys.stdout.write(format_human_summary(profile))
    sys.stdout.write(f"\nWrote: {out.resolve()}\n")
    return 0


__all__ = [
    "build_system_profile",
    "collect_warnings",
    "format_human_summary",
    "main",
    "measure_http_head_latency_ms",
    "probe_existing_installs",
    "query_wmi_layer0",
    "write_system_profile",
]

if __name__ == "__main__":
    raise SystemExit(main())
