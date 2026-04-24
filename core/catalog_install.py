"""Install winget rows from ``install_catalog`` with profile gates and manifest skips."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.install_catalog import catalog_entries_for_layer, get_detector
from core.winget_util import ensure_winget_package

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def install_catalog_layer(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
    layer: str,
    *,
    skip_tools: frozenset[str] | None = None,
) -> None:
    """Apply all ``WingetCatalogEntry`` rows for *layer*."""
    selected = set(ctx.profiles)
    for entry in catalog_entries_for_layer(layer):
        if skip_tools and entry.tool in skip_tools:
            continue
        if entry.tool in ctx.catalog_exclude_tools:
            manifest.record_tool(
                tool=entry.tool,
                layer=layer,
                status="skipped",
                install_method="user-exclude",
                notes="Excluded via Custom Mode / --exclude-catalog-tool.",
            )
            console.print(f"  [skipped] {entry.tool} — user exclude")
            continue
        if not entry.applies_to(selected):
            req = ", ".join(sorted(entry.profiles)) if entry.profiles else ""
            manifest.record_tool(
                tool=entry.tool,
                layer=layer,
                status="skipped",
                install_method="profile-gate",
                notes=f"Requires one of these profiles: {req}",
            )
            console.print(f"  [skipped] {entry.tool} — profile gate")
            continue
        ensure_winget_package(
            ctx,
            manifest,
            console,
            tool=entry.tool,
            layer=layer,
            winget_id=entry.winget_id,
            detect=get_detector(entry),
        )
