#!/usr/bin/env python3
"""Comprehensive install verification: compare manifest against actual system state.

Checks:
- What the manifest says should be installed vs. what's actually on disk
- Deep version checks (PyTorch GPU support, pip package versions, etc.)
- Missing tools, failed installs, and unexpected state
- GPU detection for ML stack
"""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Import catalog
sys.path.insert(0, str(_REPO_ROOT))
from core.install_catalog import TOOL_DISK_MB, WINGET_CATALOG, get_detector


def _check_tool_via_detector(entry: Any) -> bool:
    """Use the same detector logic as the installer."""
    try:
        detector = get_detector(entry)
        return detector()
    except Exception:
        return False


def _get_python_package_version(pkg: str) -> str | None:
    """Get installed version of a Python package."""
    try:
        import importlib.metadata
        return importlib.metadata.version(pkg)
    except Exception:
        return None


def _detect_gpu() -> str:
    """Detect GPU type (NVIDIA, AMD, or CPU-only)."""
    try:
        # Check for NVIDIA
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return f"NVIDIA: {result.stdout.strip().split()[0]}"
    except Exception:
        pass

    try:
        # Check for AMD
        result = subprocess.run(
            ["rocm-smi", "--showid"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return "AMD ROCm detected"
    except Exception:
        pass

    return "CPU-only (no NVIDIA/AMD detected)"


def _check_pytorch_cuda() -> dict[str, Any]:
    """Check PyTorch GPU support."""
    try:
        import torch
        return {
            "installed": True,
            "version": torch.__version__,
            "cuda_available": torch.cuda.is_available(),
            "cuda_version": torch.version.cuda if torch.cuda.is_available() else None,
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        }
    except ImportError:
        return {"installed": False}
    except Exception as e:
        return {"installed": True, "error": str(e)}


def load_manifest() -> dict[str, Any] | None:
    """Load the devkit-manifest.json if it exists."""
    manifest_path = _REPO_ROOT / "devkit-manifest.json"
    if not manifest_path.is_file():
        return None
    try:
        with open(manifest_path) as f:
            return json.load(f)
    except Exception:
        return None


def verify_install() -> None:
    """Verify install against manifest."""
    print("=" * 90)
    print("AM-DevKit Install Verification")
    print("=" * 90)
    print()

    # Load manifest
    manifest = load_manifest()
    if not manifest:
        print("No manifest found. Run --dry-run or START INSTALL first.\n")
        return

    print(f"Manifest generated: {manifest.get('generated_at', 'unknown')}")
    print(f"DevKit version: {manifest.get('devkit_version', 'unknown')}\n")

    # Extract expected tools from manifest by status
    expected_tools = {}  # tool -> {status, layer, method, expected}
    for tool_entry in manifest.get("tools", []):
        tool_name = tool_entry.get("tool")
        status = tool_entry.get("status", "unknown")
        if tool_name and status in ("installed", "planned"):
            expected_tools[tool_name] = {
                "status": status,
                "layer": tool_entry.get("layer", "?"),
                "method": tool_entry.get("install_method", "?"),
                "notes": tool_entry.get("notes", ""),
            }

    print(f"Manifest expected {len(expected_tools)} tools to install\n")

    # Check each expected tool
    print("EXPECTED TOOLS VERIFICATION:")
    print("-" * 90)

    found_count = 0
    missing = []
    catalog_by_tool = {e.tool: e for e in WINGET_CATALOG}

    for tool_name in sorted(expected_tools.keys()):
        info = expected_tools[tool_name]
        layer = info["layer"]

        # Skip non-installable meta tools
        if layer in ("meta", "preflight", "layer0", "finalize", "sandbox"):
            continue

        detected = False
        if tool_name in catalog_by_tool:
            detected = _check_tool_via_detector(catalog_by_tool[tool_name])
        elif tool_name in ("system-restore-point", "system-scan", "ctt-winutil", "dotfiles-seed", "vscode-extensions", "rustup-stable", "gpu-detect", "wsl-prereq", "sandbox-templates"):
            # Non-catalog tools that are harder to detect
            # Mark as detected if they were marked installed/planned
            detected = info["status"] == "installed"

        icon = "[+]" if detected else "[-]"
        status_icon = "I" if info["status"] == "installed" else "P"  # I=installed, P=planned
        size = TOOL_DISK_MB.get(tool_name, 100)

        if detected:
            found_count += 1
            print(f"  {icon} [{status_icon}] {tool_name:30s} {size:5d}MB  ({layer:15s}) OK")
        else:
            missing.append(tool_name)
            print(f"  {icon} [{status_icon}] {tool_name:30s} {size:5d}MB  ({layer:15s}) MISSING")

    print(f"\nFound: {found_count}/{len([t for t in expected_tools if expected_tools[t]['layer'] not in ('meta', 'preflight', 'layer0', 'finalize', 'sandbox')])}")

    # GPU Detection
    print("\n" + "=" * 90)
    print("HARDWARE DETECTION:")
    print("-" * 90)
    gpu_info = _detect_gpu()
    print(f"GPU: {gpu_info}\n")

    # PyTorch Deep Check
    print("=" * 90)
    print("ML STACK DEEP CHECKS:")
    print("-" * 90)

    pytorch_info = _check_pytorch_cuda()
    if pytorch_info["installed"]:
        print("PyTorch installed: YES")
        print(f"  Version: {pytorch_info.get('version', 'unknown')}")
        if "error" in pytorch_info:
            print(f"  Error: {pytorch_info['error']}")
        else:
            print(f"  CUDA available: {pytorch_info.get('cuda_available', False)}")
            if pytorch_info.get("cuda_available"):
                print(f"  CUDA version: {pytorch_info.get('cuda_version', 'unknown')}")
                print(f"  GPU count: {pytorch_info.get('device_count', 0)}")
                print(f"  GPU name: {pytorch_info.get('device_name', 'unknown')}")
            else:
                print("  (Running CPU-only mode)")
    else:
        print("PyTorch installed: NO")

    print()

    # ML pip packages
    print("ML pip packages:")
    ml_pkgs = {
        "numpy": "numpy",
        "pandas": "pandas",
        "matplotlib": "matplotlib",
        "sklearn": "scikit-learn",
        "jupyter": "Jupyter",
        "IPython": "IPython",
    }
    ml_found = 0
    for import_name, display_name in ml_pkgs.items():
        version = _get_python_package_version(import_name)
        if version:
            print(f"  [+] {display_name:15s} v{version}")
            ml_found += 1
        else:
            print(f"  [-] {display_name:15s} NOT FOUND")

    print(f"\nML packages: {ml_found}/{len(ml_pkgs)}")

    # Summary
    print("\n" + "=" * 90)
    print("SUMMARY:")
    print("=" * 90)
    if missing:
        print(f"\nMISSING TOOLS ({len(missing)}):")
        for tool in sorted(missing):
            print(f"  - {tool}")
        print("\nRun `python scripts/scan-all-tools.py` for more details on all tools.")
    else:
        print("\nAll expected tools found!")

    # Manifest status breakdown
    print("\n" + "=" * 90)
    print("MANIFEST STATUS BREAKDOWN:")
    print("-" * 90)
    status_counts = {}
    for tool_entry in manifest.get("tools", []):
        status = tool_entry.get("status", "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1

    for status in ["installed", "planned", "failed", "skipped"]:
        count = status_counts.get(status, 0)
        if count > 0:
            print(f"  {status:12s}: {count:3d}")

    # Recommendations
    print("\n" + "=" * 90)
    print("RECOMMENDATIONS:")
    print("-" * 90)
    if pytorch_info["installed"] and not pytorch_info.get("cuda_available"):
        print("  * PyTorch is installed but CUDA is not available.")
        print("    Install NVIDIA CUDA Toolkit if you have an NVIDIA GPU.")
    if missing:
        if len(missing) < 10:
            print(f"  * {len(missing)} tools are missing. Check installation logs.")
        else:
            print(f"  * {len(missing)} tools are missing. Run full install again or")
            print("    manually install with: winget install <tool-id>")
    print()


if __name__ == "__main__":
    verify_install()
