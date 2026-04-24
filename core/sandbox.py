"""Layer 9: disposable workspace templates (Phase 2)."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def run_sandbox(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Copy sandbox templates into ``<repo>/am-devkit-out/sandbox/``."""
    console.print("[bold]Layer 9 — Sandbox templates[/bold]")
    src = ctx.repo_root / "templates" / "sandbox"
    dst = ctx.repo_root / "am-devkit-out" / "sandbox"
    if not src.is_dir():
        manifest.record_tool(
            tool="sandbox-templates",
            layer="sandbox",
            status="skipped",
            install_method="copy",
            notes=f"Missing template directory: {src}",
        )
        console.print("  [skipped] Sandbox templates — directory missing")
        return

    if ctx.dry_run:
        manifest.record_tool(
            tool="sandbox-templates",
            layer="sandbox",
            status="planned",
            install_method="copy",
            notes=f"Would copy {src} -> {dst}",
        )
        console.print("  [planned] Sandbox templates — dry-run")
        return

    try:
        shutil.copytree(src, dst, dirs_exist_ok=True)
    except OSError as exc:
        manifest.record_tool(
            tool="sandbox-templates",
            layer="sandbox",
            status="failed",
            install_method="copy",
            notes=str(exc),
        )
        console.print(f"  [failed] Sandbox templates — {exc}")
        return

    manifest.record_tool(
        tool="sandbox-templates",
        layer="sandbox",
        status="installed",
        install_method="copy",
        notes=str(dst),
    )
    console.print(f"  [done] Sandbox templates -> {dst}")
