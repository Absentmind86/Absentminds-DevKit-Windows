"""Layer 6: WSL, Docker, Kubernetes, databases, cloud CLIs (Phase 2B).

Docker Desktop, kubectl, and Helm are now driven through WINGET_CATALOG
(install_catalog.py) so the GUI can exclude them via --exclude-catalog-tool.
The old _wants_docker / _wants_kubernetes_cli helpers are removed; profile
gating and user exclusions are handled by install_catalog_layer automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.catalog_install import install_catalog_layer
from core.pwsh_util import ensure_wsl_default_distro, ensure_wsl_prereq

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def run_devops(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    console.print("[bold]Layer 6 — DevOps & containers[/bold]")

    ensure_wsl_prereq(ctx, manifest, console)
    if ctx.wsl_default_distro:
        ensure_wsl_default_distro(ctx, manifest, console, ctx.wsl_default_distro)

    # Docker Desktop, kubectl, Helm, PostgreSQL, Redis, cloud CLIs, etc. are all
    # catalog-driven — profile gates and user excludes are applied automatically.
    install_catalog_layer(ctx, manifest, console, "devops")
