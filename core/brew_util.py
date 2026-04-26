"""Homebrew-based installs for macOS (mirrors winget_util.py pattern)."""
from __future__ import annotations

import shutil
import subprocess
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def brew_available() -> bool:
    return shutil.which("brew") is not None


def run_brew_install(
    pkg_id: str,
    *,
    is_cask: bool,
    dry_run: bool,
    timeout_s: float = 3600.0,
) -> tuple[int, str, str]:
    if dry_run:
        return 0, "", ""
    argv = ["brew", "install"]
    if is_cask:
        argv.append("--cask")
    argv.append(pkg_id)
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


def ensure_brew_package(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
    *,
    tool: str,
    layer: str,
    pkg_id: str,
    is_cask: bool = False,
    detect: Callable[[], bool],
    version_hint: str | None = None,
) -> None:
    """Install pkg_id via brew unless already present or dry-run."""
    install_method = "brew-cask" if is_cask else "brew"

    if detect():
        manifest.record_tool(
            tool=tool, layer=layer, status="skipped",
            install_method=install_method, version=version_hint,
            notes="Already present on PATH or detector.",
        )
        console.print(f"  [skipped] {tool} — already installed")
        return

    if ctx.dry_run:
        cmd = f"brew install {'--cask ' if is_cask else ''}{pkg_id}"
        manifest.record_tool(
            tool=tool, layer=layer, status="planned",
            install_method=install_method, version=version_hint,
            notes=f"Would run: {cmd}",
        )
        console.print(f"  [planned] {tool} — dry-run")
        return

    if not brew_available():
        manifest.record_tool(
            tool=tool, layer=layer, status="failed",
            install_method=install_method,
            notes="brew not found on PATH.",
        )
        console.print(f"  [failed] {tool} — brew not available")
        return

    console.print(f"  [installing] {tool} via {install_method}…")
    code, out, err = run_brew_install(pkg_id, is_cask=is_cask, dry_run=False)
    combined = (out + "\n" + err).strip()

    if code == 0:
        manifest.record_tool(
            tool=tool, layer=layer, status="installed",
            install_method=install_method, version=version_hint,
            notes=combined[-2000:] if combined else None,
        )
        console.print(f"  [done] {tool}")
        return

    # brew exits 1 when the package is already installed at latest version
    if "already installed" in combined.lower():
        manifest.record_tool(
            tool=tool, layer=layer, status="skipped",
            install_method=install_method, version=version_hint,
            notes="Already installed (brew reported no upgrade needed).",
        )
        console.print(f"  [skipped] {tool} — already installed")
        return

    manifest.record_tool(
        tool=tool, layer=layer, status="failed",
        install_method=install_method,
        notes=f"exit {code}: {combined[-2000:]}",
    )
    console.print(f"  [failed] {tool} (exit {code})")
