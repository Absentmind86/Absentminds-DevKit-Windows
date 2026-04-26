"""Linux package manager installs — apt / dnf / pacman / zypper (mirrors winget_util.py pattern)."""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest

_SUPPORTED_MANAGERS = ("apt", "apt-get", "dnf", "pacman", "zypper")


def linux_manager_available(manager: str) -> bool:
    return shutil.which(manager) is not None


def _build_install_argv(manager: str, pkg_id: str) -> list[str]:
    if manager in ("apt", "apt-get"):
        return ["sudo", manager, "install", "-y", pkg_id]
    if manager == "dnf":
        return ["sudo", "dnf", "install", "-y", pkg_id]
    if manager == "pacman":
        return ["sudo", "pacman", "-Sy", "--noconfirm", pkg_id]
    if manager == "zypper":
        return ["sudo", "zypper", "--non-interactive", "install", pkg_id]
    raise ValueError(f"Unsupported package manager: {manager!r}")


def run_linux_install(
    manager: str,
    pkg_id: str,
    *,
    dry_run: bool,
    timeout_s: float = 3600.0,
) -> tuple[int, str, str]:
    if dry_run:
        return 0, "", ""
    argv = _build_install_argv(manager, pkg_id)
    try:
        proc = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"


def ensure_linux_package(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
    *,
    tool: str,
    layer: str,
    pkg_id: str,
    manager: str,
    detect: Callable[[], bool],
    version_hint: str | None = None,
) -> None:
    """Install pkg_id via the given Linux package manager unless already present."""
    if detect():
        manifest.record_tool(
            tool=tool, layer=layer, status="skipped",
            install_method=manager, version=version_hint,
            notes="Already present on PATH or detector.",
        )
        console.print(f"  [skipped] {tool} — already installed")
        return

    if ctx.dry_run:
        argv_str = " ".join(_build_install_argv(manager, pkg_id))
        manifest.record_tool(
            tool=tool, layer=layer, status="planned",
            install_method=manager, version=version_hint,
            notes=f"Would run: {argv_str}",
        )
        console.print(f"  [planned] {tool} — dry-run")
        return

    if not linux_manager_available(manager):
        manifest.record_tool(
            tool=tool, layer=layer, status="failed",
            install_method=manager,
            notes=f"{manager} not found on PATH.",
        )
        console.print(f"  [failed] {tool} — {manager} not available")
        return

    console.print(f"  [installing] {tool} via {manager}…")
    code, out, err = run_linux_install(manager, pkg_id, dry_run=False)
    combined = (out + "\n" + err).strip()

    if code == 0:
        manifest.record_tool(
            tool=tool, layer=layer, status="installed",
            install_method=manager, version=version_hint,
            notes=combined[-2000:] if combined else None,
        )
        console.print(f"  [done] {tool}")
        return

    manifest.record_tool(
        tool=tool, layer=layer, status="failed",
        install_method=manager,
        notes=f"exit {code}: {combined[-2000:]}",
    )
    console.print(f"  [failed] {tool} (exit {code})")
