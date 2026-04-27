"""Layer 6: WSL, Docker, Kubernetes, databases, cloud CLIs (Phase 2B).

Docker Desktop, kubectl, and Helm are now driven through WINGET_CATALOG
(install_catalog.py) so the GUI can exclude them via --exclude-catalog-tool.
The old _wants_docker / _wants_kubernetes_cli helpers are removed; profile
gating and user exclusions are handled by install_catalog_layer automatically.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from core.catalog_install import install_catalog_layer
from core.install_catalog import catalog_entries_for_layer
from core.platform_util import is_windows

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


_CONTAINER_TOOLS: frozenset[str] = frozenset({"docker-desktop", "podman-desktop"})


def run_devops(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    console.print("[bold]Layer 6 — DevOps & containers[/bold]")

    if is_windows():
        from core.pwsh_util import ensure_wsl_default_distro, ensure_wsl_prereq

        # Docker Desktop and Podman Desktop require WSL2 to function on Windows 11 Home.
        # Auto-enable the WSL prereq whenever either container tool will be installed,
        # without forcing the user to pass --enable-wsl.
        if not ctx.enable_wsl:
            selected = set(ctx.profiles)
            needs_wsl = any(
                e.tool in _CONTAINER_TOOLS
                and e.applies_to(selected)
                and e.tool not in ctx.catalog_exclude_tools
                for e in catalog_entries_for_layer("devops")
            )
            if needs_wsl:
                ctx.enable_wsl = True

        ensure_wsl_prereq(ctx, manifest, console)
        if ctx.wsl_default_distro:
            ensure_wsl_default_distro(ctx, manifest, console, ctx.wsl_default_distro)

        # Docker Desktop fails with "C:\ProgramData\DockerDesktop must be owned by
        # an elevated account" when a prior partial install left that directory owned
        # by a non-admin process.  Fix ownership upfront so the installer can proceed.
        # Skip if docker.exe is already on PATH — docker is already installed and
        # the ownership was set correctly on the first install.
        if not ctx.dry_run:
            from core.winget_util import which as _which
            selected = set(ctx.profiles)
            docker_wanted = any(
                e.tool == "docker-desktop" and e.applies_to(selected) and e.tool not in ctx.catalog_exclude_tools
                for e in catalog_entries_for_layer("devops")
            )
            docker_installed = _which("docker.exe") is not None
            if docker_wanted and not docker_installed:
                from core.pwsh_util import run_powershell
                console.print("  [installing] docker-desktop permissions fix …")
                run_powershell(
                    r"""
$dir = 'C:\ProgramData\DockerDesktop'
if (Test-Path $dir) {
    # /A assigns ownership to the Administrators group (not just the current user).
    # Docker Desktop checks that the directory is owned by an elevated account.
    & takeown.exe /F $dir /R /D Y /A 2>&1 | Out-Null
    & icacls.exe $dir /grant "BUILTIN\Administrators:(OI)(CI)F" /T /Q 2>&1 | Out-Null
    & icacls.exe $dir /setowner "BUILTIN\Administrators" /T /Q 2>&1 | Out-Null
}
""",
                    timeout_s=60.0,
                )

    # Docker Desktop, kubectl, Helm, PostgreSQL, Redis, cloud CLIs, etc. are all
    # catalog-driven — profile gates and user excludes are applied automatically.
    install_catalog_layer(ctx, manifest, console, "devops")
