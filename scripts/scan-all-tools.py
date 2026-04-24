#!/usr/bin/env python3
"""Scan for every single tool in the devkit and report installation status."""

import json
import shutil
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Import catalog
import sys

sys.path.insert(0, str(_REPO_ROOT))
from core.install_catalog import TOOL_DISK_MB, WINGET_CATALOG, get_detector


def _check_tool_via_detector(entry: Any) -> bool:
    """Use the same detector logic as the installer."""
    try:
        detector = get_detector(entry)
        return detector()
    except Exception:
        return False


def _check_python_package(pkg: str) -> bool:
    """Check if a Python package is installed."""
    try:
        __import__(pkg)
        return True
    except ImportError:
        return False


def scan_all_tools() -> None:
    """Scan every tool and print results."""
    print("="*80)
    print("AM-DevKit Tool Installation Scan")
    print("="*80)
    print()

    # First check foundation tools (non-catalog)
    print("FOUNDATION TOOLS (non-catalog):")
    print("-" * 80)
    foundation = {
        "python":      lambda: shutil.which("python.exe") or shutil.which("python3.exe"),
        "git":         lambda: shutil.which("git.exe"),
        "git-lfs":     lambda: shutil.which("git-lfs.exe"),
        "github-cli":  lambda: shutil.which("gh.exe"),
        "powershell":  lambda: shutil.which("pwsh.exe"),
        "scoop":       lambda: shutil.which("scoop.cmd"),
        "rustup":      lambda: shutil.which("rustup.exe"),
        "nvm":         lambda: shutil.which("nvm.exe"),
    }
    foundation_found = 0
    for tool, detector in foundation.items():
        found = bool(detector())
        icon = "[+]" if found else "[-]"
        print(f"  {icon} {tool:20s} {'FOUND' if found else 'NOT FOUND'}")
        if found:
            foundation_found += 1
    print(f"\nFoundation: {foundation_found}/{len(foundation)} found\n")

    # Catalog tools
    print("CATALOG TOOLS (winget):")
    print("-" * 80)

    # Group by layer
    layers = {}
    for entry in WINGET_CATALOG:
        layer = entry.layer
        if layer not in layers:
            layers[layer] = []
        layers[layer].append(entry)

    total_tools = len(WINGET_CATALOG)
    found_tools = 0
    failed_tools = []

    for layer in sorted(layers.keys()):
        print(f"\nLayer: {layer.upper()}")
        layer_found = 0
        for entry in sorted(layers[layer], key=lambda e: e.tool):
            detected = _check_tool_via_detector(entry)
            icon = "[+]" if detected else "[-]"
            size_mb = TOOL_DISK_MB.get(entry.tool, 100)
            profiles = ", ".join(sorted(entry.profiles)) if entry.profiles else "common"

            status = f"{icon} {entry.tool:25s} {size_mb:4d}MB  ({profiles:40s})"
            if detected:
                status += " [OK] INSTALLED"
                layer_found += 1
                found_tools += 1
            else:
                status += " [MISSING]"
                failed_tools.append(entry.tool)

            print(f"  {status}")

        print(f"  -> Layer {layer}: {layer_found}/{len(layers[layer])} found")

    # Python packages (feature items)
    print("\n\nFEATURE TOGGLES (pip packages):")
    print("-" * 80)
    ml_packages = {
        "numpy":       "numpy",
        "pandas":      "pandas",
        "matplotlib":  "matplotlib",
        "sklearn":     "scikit-learn",
        "jupyter":     "jupyter",
        "IPython":     "ipython",
        "torch":       "PyTorch",
    }
    ml_found = 0
    for import_name, display_name in ml_packages.items():
        found = _check_python_package(import_name)
        icon = "[+]" if found else "[-]"
        print(f"  {icon} {display_name:25s} {'INSTALLED' if found else 'NOT FOUND'}")
        if found:
            ml_found += 1
    print(f"\nML packages: {ml_found}/{len(ml_packages)} found\n")

    # Summary
    print("\n" + "="*80)
    print("SUMMARY")
    print("="*80)
    print(f"Foundation tools:  {foundation_found:2d}/{len(foundation):2d}")
    print(f"Catalog tools:     {found_tools:2d}/{total_tools:2d}")
    print(f"ML packages:       {ml_found:2d}/{len(ml_packages):2d}")
    print(f"{'='*80}")

    if failed_tools:
        print(f"\nMISSING TOOLS ({len(failed_tools)}):")
        for tool in sorted(failed_tools):
            print(f"  - {tool}")

    # Load manifest if it exists to cross-check
    manifest_path = _REPO_ROOT / "devkit-manifest.json"
    if manifest_path.is_file():
        try:
            with open(manifest_path) as f:
                manifest = json.load(f)
            print(f"\n\nLast run manifest ({manifest.get('generated_at', 'unknown')}):")
            print("-" * 80)
            status_counts = {}
            for tool in manifest.get("tools", []):
                status = tool.get("status", "unknown")
                status_counts[status] = status_counts.get(status, 0) + 1
            for status in ["installed", "planned", "failed", "skipped"]:
                count = status_counts.get(status, 0)
                if count > 0:
                    print(f"  {status:12s}: {count:3d} items")
        except Exception as e:
            print(f"\nError reading manifest: {e}")


if __name__ == "__main__":
    scan_all_tools()
