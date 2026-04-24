"""Layer 1: CTT WinUtil integration with AM config (Phase 2).

WinUtil is retrieved at runtime from ``https://christitus.com/win`` (not vendored here).
Upstream license: MIT, Chris Titus Tech / CT Tech Group LLC — see docs/THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def _winutil_config_path(ctx: InstallContext) -> Path:
    from core.install_context import winutil_config_path_for_preset

    return winutil_config_path_for_preset(
        ctx.repo_root,
        getattr(ctx, "sanitation_preset", "minimal"),
    )


def run_sanitize(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Invoke Chris Titus WinUtil with our JSON preset (opt-in: ``ctx.run_sanitation``)."""
    console.print("[bold]Layer 1 — Windows sanitization[/bold]")
    preset_name = getattr(ctx, "sanitation_preset", "minimal")
    config_path = _winutil_config_path(ctx)
    if not config_path.is_file():
        manifest.record_tool(
            tool="ctt-winutil",
            layer="sanitize",
            status="failed",
            install_method="winutil",
            notes=f"Missing config file: {config_path}",
        )
        console.print(f"  [failed] WinUtil — missing {config_path}")
        return

    if not ctx.run_sanitation:
        manifest.record_tool(
            tool="ctt-winutil",
            layer="sanitize",
            status="skipped",
            install_method="winutil",
            notes="Sanitation not requested (pass --run-sanitation to enable).",
        )
        console.print("  [skipped] WinUtil — use --run-sanitation to enable (preset: none)")
        return

    if ctx.dry_run:
        manifest.record_tool(
            tool="ctt-winutil",
            layer="sanitize",
            status="planned",
            install_method="winutil",
            notes=f"Would invoke WinUtil with config {config_path}",
        )
        console.print(f"  [planned] WinUtil — dry-run ({config_path.name})")
        return

    # Documented pattern: iex "& { $(irm 'https://christitus.com/win') } -Config <path> -Run"
    cfg = str(config_path).replace("'", "''")
    ps = (
        "$ErrorActionPreference = 'Stop'; "
        f"$config = '{cfg}'; "
        "iex \"& { $(irm 'https://christitus.com/win') } -Config $config -Run\""
    )
    console.print(
        f"  [installing] WinUtil (CTT) — {config_path.name} — this may take several minutes …"
    )
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        manifest.record_tool(
            tool="ctt-winutil",
            layer="sanitize",
            status="failed",
            install_method="winutil",
            notes=f"{type(exc).__name__}: {exc}",
        )
        console.print(f"  [failed] WinUtil — {exc}")
        return

    tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-2000:]
    if proc.returncode == 0:
        manifest.record_tool(
            tool="ctt-winutil",
            layer="sanitize",
            status="installed",
            install_method="winutil",
            notes=tail or None,
        )
        console.print("  [done] WinUtil")
        return

    manifest.record_tool(
        tool="ctt-winutil",
        layer="sanitize",
        status="failed",
        install_method="winutil",
        notes=f"exit {proc.returncode}: {tail}",
    )
    console.print(f"  [failed] WinUtil (exit {proc.returncode})")
