"""OS detection and package manager selection for cross-platform support."""
from __future__ import annotations

import shutil
import sys


def current_os() -> str:
    """Returns 'windows', 'linux', or 'macos'."""
    if sys.platform == "win32":
        return "windows"
    elif sys.platform == "darwin":
        return "macos"
    return "linux"


def is_windows() -> bool:
    return sys.platform == "win32"


def is_macos() -> bool:
    return sys.platform == "darwin"


def is_linux() -> bool:
    return sys.platform not in ("win32", "darwin")


def primary_pkg_manager() -> str:
    """Returns the primary package manager for the current OS."""
    if is_windows():
        return "winget"
    if is_macos():
        return "brew"
    for mgr in ("apt", "dnf", "pacman", "zypper"):
        if shutil.which(mgr):
            return mgr
    return "apt"


def fallback_pkg_manager() -> str | None:
    """Returns the fallback package manager, or None if no fallback exists."""
    if is_windows():
        return "choco"
    return None


def terminal_launcher() -> list[str]:
    """Returns a command prefix to open a new terminal window on non-Windows platforms."""
    if is_macos():
        return ["open", "-a", "Terminal"]
    for term in ("gnome-terminal", "konsole", "xfce4-terminal", "xterm"):
        if shutil.which(term):
            return [term, "--"]
    return []


def open_file(path: str) -> None:
    """Open a file with the system default application, cross-platform."""
    import subprocess
    if is_windows():
        import os
        os.startfile(path)
    elif is_macos():
        subprocess.run(["open", path], check=False)
    else:
        subprocess.run(["xdg-open", path], check=False)
