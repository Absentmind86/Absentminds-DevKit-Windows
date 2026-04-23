"""Layer 4: Python, Node via NVM, runtimes, build tools (Phase 2B — catalog + PROJECT.md)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.catalog_install import install_catalog_layer
from core.pyenv_scoop import ensure_pyenv_scoop
from core.pwsh_util import ensure_rustup_default
from core.winget_util import ensure_winget_package, which

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def _wants_rust(ctx: InstallContext) -> bool:
    if ctx.skip_rust:
        return False
    return any(
        ctx.profile_selected(p) for p in ("systems", "game-dev", "hardware-robotics", "ai-ml")
    )


def run_languages(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    console.print("[bold]Layer 4 — Languages & runtimes[/bold]")

    py = which("python.exe") or which("python3.exe")
    if py:
        manifest.record_tool(
            tool="python",
            layer="languages",
            status="skipped",
            install_method="existing",
            notes=str(py),
        )
        console.print(f"  [skipped] Python — found at {py}")
    else:
        ensure_winget_package(
            ctx,
            manifest,
            console,
            tool="python",
            layer="languages",
            winget_id="Python.Python.3.12",
            detect=lambda: False,
        )

    ensure_winget_package(
        ctx,
        manifest,
        console,
        tool="uv",
        layer="languages",
        winget_id="astral-sh.uv",
        detect=lambda: which("uv.exe") is not None,
    )

    ensure_pyenv_scoop(ctx, manifest, console)

    if ctx.profile_selected("web-fullstack"):
        console.print("  [info] Node — use NVM from catalog; after install run: nvm install lts")
    else:
        console.print("  [skipped] NVM / Node — web-fullstack not selected")

    if _wants_rust(ctx):
        ensure_rustup_default(ctx, manifest, console)
    elif ctx.skip_rust:
        manifest.record_tool(
            tool="rustup-stable",
            layer="languages",
            status="skipped",
            install_method="user-opt-out",
            notes="Skipped via --skip-rust (GUI: Skip Rust toolchain).",
        )
        console.print("  [skipped] rustup — --skip-rust set")
    else:
        manifest.record_tool(
            tool="rustup-stable",
            layer="languages",
            status="skipped",
            install_method="profile-gate",
            notes="Rust not requested for selected profiles.",
        )
        console.print("  [skipped] rustup — no systems/game-dev/hardware-robotics/ai-ml")

    install_catalog_layer(ctx, manifest, console, "languages")
