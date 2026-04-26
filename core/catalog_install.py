"""Install catalog rows with profile gates, manifest skips, and cross-platform dispatch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.install_catalog import CatalogEntry, catalog_entries_for_layer, get_detector
from core.platform_util import is_macos, is_windows, primary_pkg_manager
from core.winget_util import ensure_winget_package

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def _get_pkg_id(entry: CatalogEntry) -> str | None:
    """Return the package ID for the current OS, or None if unsupported."""
    if is_windows():
        return entry.win_id
    if is_macos():
        return entry.macos_id
    return entry.linux_id


def _install_entry(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
    entry: CatalogEntry,
    layer: str,
) -> None:
    pkg_id = _get_pkg_id(entry)

    if pkg_id is None:
        manifest.record_tool(
            tool=entry.tool,
            layer=layer,
            status="skipped",
            install_method="platform",
            notes=f"Not available on this platform ({primary_pkg_manager()}).",
        )
        console.print(f"  [skipped] {entry.tool} — not available on this platform")
        return

    if is_windows():
        ensure_winget_package(
            ctx, manifest, console,
            tool=entry.tool, layer=layer,
            winget_id=pkg_id,
            detect=get_detector(entry),
        )
    elif is_macos():
        from core.brew_util import ensure_brew_package
        ensure_brew_package(
            ctx, manifest, console,
            tool=entry.tool, layer=layer,
            pkg_id=pkg_id,
            is_cask=entry.macos_cask,
            detect=get_detector(entry),
        )
    else:
        from core.linux_util import ensure_linux_package
        ensure_linux_package(
            ctx, manifest, console,
            tool=entry.tool, layer=layer,
            pkg_id=pkg_id,
            manager=primary_pkg_manager(),
            detect=get_detector(entry),
        )


def install_catalog_layer(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
    layer: str,
    *,
    skip_tools: frozenset[str] | None = None,
) -> None:
    """Apply all CatalogEntry rows for *layer*."""
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
        _install_entry(ctx, manifest, console, entry, layer)
