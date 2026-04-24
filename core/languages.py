"""Layer 4: Python, runtimes, build tools.

Bootstrap: Python 3 is installed directly (must exist before catalog).
Catalog-driven: uv, nvm-windows (web), golang, temurin, dotnet, cmake, ninja,
                unity-hub, godot (all profile-gated in install_catalog.py).
Rustup is non-catalog (rustup-init.exe) — profile-gated via _wants_rust().
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.catalog_install import install_catalog_layer
from core.pwsh_util import ensure_rustup_default
from core.pyenv_scoop import ensure_pyenv_scoop
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
            notes=f"Already present on PATH or detector. ({py})",
        )
        console.print(f"  [skipped] python — already installed (found at {py})")
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

    ensure_pyenv_scoop(ctx, manifest, console)

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
