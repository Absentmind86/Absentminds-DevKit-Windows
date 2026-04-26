"""Layer 4: Python, runtimes, build tools.

Bootstrap: Python 3 is installed directly (must exist before catalog).
Catalog-driven: uv, nvm-windows (web), golang, temurin, dotnet, cmake, ninja,
                unity-hub, godot (all profile-gated in install_catalog.py).
Rustup is non-catalog (rustup-init.exe) — profile-gated via _wants_rust().
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

from core.catalog_install import install_catalog_layer
from core.platform_util import is_macos, is_windows, primary_pkg_manager
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


def _ensure_python(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Ensure Python 3.11+ is available — platform-aware."""
    py = (which("python.exe") or which("python3.exe")
          if is_windows() else shutil.which("python3") or shutil.which("python"))
    if py:
        manifest.record_tool(tool="python", layer="languages", status="skipped",
                             install_method="existing",
                             notes=f"Already present on PATH. ({py})")
        console.print(f"  [skipped] python — already installed ({py})")
        return

    if is_windows():
        ensure_winget_package(ctx, manifest, console, tool="python", layer="languages",
                              winget_id="Python.Python.3.12", detect=lambda: False)
    elif is_macos():
        from core.brew_util import ensure_brew_package
        ensure_brew_package(ctx, manifest, console, tool="python", layer="languages",
                            pkg_id="python@3.12",
                            detect=lambda: shutil.which("python3") is not None)
    else:
        from core.linux_util import ensure_linux_package
        ensure_linux_package(ctx, manifest, console, tool="python", layer="languages",
                             pkg_id="python3", manager=primary_pkg_manager(),
                             detect=lambda: shutil.which("python3") is not None)


def _ensure_nvm_linux(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Install nvm on Linux via the official curl installer (no apt package exists)."""
    if not ctx.profile_selected("web-fullstack"):
        return

    detect = lambda: shutil.which("nvm") is not None or (  # noqa: E731
        (Path.home() / ".nvm" / "nvm.sh").is_file()
    )
    if detect():
        manifest.record_tool(tool="nvm", layer="languages", status="skipped",
                             install_method="curl-installer",
                             notes="~/.nvm/nvm.sh already present.")
        console.print("  [skipped] nvm — already installed")
        return

    if ctx.dry_run:
        manifest.record_tool(tool="nvm", layer="languages", status="planned",
                             install_method="curl-installer",
                             notes="Would run: curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash")
        console.print("  [planned] nvm — dry-run")
        return

    console.print("  [installing] nvm via curl installer…")
    try:
        proc = subprocess.run(
            ["bash", "-c",
             "curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300.0,
        )
        combined = (proc.stdout + "\n" + proc.stderr).strip()
        if proc.returncode == 0:
            manifest.record_tool(tool="nvm", layer="languages", status="installed",
                                 install_method="curl-installer",
                                 notes=combined[-2000:] if combined else None)
            console.print("  [done] nvm (restart shell to activate)")
        else:
            manifest.record_tool(tool="nvm", layer="languages", status="failed",
                                 install_method="curl-installer",
                                 notes=f"exit {proc.returncode}: {combined[-2000:]}")
            console.print(f"  [failed] nvm (exit {proc.returncode})")
    except (OSError, subprocess.TimeoutExpired) as exc:
        manifest.record_tool(tool="nvm", layer="languages", status="failed",
                             install_method="curl-installer", notes=str(exc))
        console.print(f"  [failed] nvm — {exc}")


def run_languages(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    console.print("[bold]Layer 4 — Languages & runtimes[/bold]")

    _ensure_python(ctx, manifest, console)

    # pyenv-win is Windows-only (uses Scoop); on Linux/macOS pyenv needs its own
    # installer (curl script) — out of scope for v1, skipped with a note.
    if is_windows():
        from core.pyenv_scoop import ensure_pyenv_scoop
        ensure_pyenv_scoop(ctx, manifest, console)
    else:
        manifest.record_tool(tool="pyenv", layer="languages", status="skipped",
                             install_method="platform",
                             notes="pyenv-win is Windows-only. Install pyenv manually on Linux/macOS.")
        console.print("  [skipped] pyenv — Windows only (install pyenv manually)")

    if _wants_rust(ctx):
        ensure_rustup_default(ctx, manifest, console)
    elif ctx.skip_rust:
        manifest.record_tool(tool="rustup-stable", layer="languages", status="skipped",
                             install_method="user-opt-out",
                             notes="Skipped via --skip-rust (GUI: Skip Rust toolchain).")
        console.print("  [skipped] rustup — --skip-rust set")
    else:
        manifest.record_tool(tool="rustup-stable", layer="languages", status="skipped",
                             install_method="profile-gate",
                             notes="Rust not requested for selected profiles.")
        console.print("  [skipped] rustup — no systems/game-dev/hardware-robotics/ai-ml")

    install_catalog_layer(ctx, manifest, console, "languages")

    # nvm: Windows uses nvm-windows (catalog), macOS uses brew (catalog via macos_id="nvm").
    # Linux has no apt package — run the official curl installer.
    if not is_windows() and not is_macos():
        _ensure_nvm_linux(ctx, manifest, console)
