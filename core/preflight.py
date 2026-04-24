"""Layer pre-flight: restore point (Phase 2)."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def run_preflight(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Create a system restore point when possible (requires elevation on many systems)."""
    if ctx.skip_restore_point:
        manifest.record_tool(
            tool="system-restore-point",
            layer="preflight",
            status="skipped",
            install_method="Checkpoint-Computer",
            notes="Skipped by flag.",
        )
        console.print("  [skipped] System restore point — disabled by flag")
        return

    desc = f"AM-DevKit {ctx.devkit_version} — Pre-Install"
    if ctx.dry_run:
        manifest.record_tool(
            tool="system-restore-point",
            layer="preflight",
            status="planned",
            install_method="Checkpoint-Computer",
            notes=f"Would run Checkpoint-Computer -Description {desc!r}",
        )
        console.print("  [planned] System restore point — dry-run")
        return

    ps = rf"""
$ErrorActionPreference = 'Stop'
# Enable System Protection on the system drive if disabled.
Enable-ComputerRestore -Drive "$env:SystemDrive\" -ErrorAction SilentlyContinue
# Bypass the 24-hour throttle Windows imposes by default (value in minutes; 0 = always allow).
$regPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SystemRestore'
Set-ItemProperty -Path $regPath -Name SystemRestorePointCreationFrequency -Value 0 -Type DWord -ErrorAction SilentlyContinue
Checkpoint-Computer -Description '{desc.replace("'", "''")}' -RestorePointType MODIFY_SETTINGS
"""
    console.print("  [installing] System restore point …")
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        manifest.record_tool(
            tool="system-restore-point",
            layer="preflight",
            status="failed",
            install_method="Checkpoint-Computer",
            notes=f"{type(exc).__name__}: {exc}",
        )
        console.print(f"  [failed] System restore point — {exc}")
        return

    if proc.returncode == 0:
        manifest.record_tool(
            tool="system-restore-point",
            layer="preflight",
            status="installed",
            install_method="Checkpoint-Computer",
            notes="Restore point created (or no-op if policy blocks).",
        )
        console.print("  [done] System restore point")
        return

    err = (proc.stderr or proc.stdout or "").strip()
    manifest.record_tool(
        tool="system-restore-point",
        layer="preflight",
        status="failed",
        install_method="Checkpoint-Computer",
        notes=f"exit {proc.returncode}: {err[-1500:]}",
    )
    console.print(
        f"  [failed] System restore point (exit {proc.returncode}) — "
        "try an elevated shell or use --skip-restore-point"
    )
