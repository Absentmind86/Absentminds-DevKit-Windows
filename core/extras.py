"""Optional Extras profile — personal tools (PROJECT.md), winget catalog layer ``extras``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.catalog_install import install_catalog_layer

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def run_extras(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Install winget rows gated on profile ``extras``."""
    if not ctx.profile_selected("extras"):
        console.print("[dim]Layer Extras — skipped (opt-in only; use 'Select all extras' in the GUI or pass --profile extras)[/dim]")
        return

    console.print("[bold]Layer Extras — optional personal tools[/bold]")
    install_catalog_layer(ctx, manifest, console, "extras")
