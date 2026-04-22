"""Winget package catalog toward PROJECT.md Phase 2B (profile-gated where noted).

IDs are from ``winget search`` / winget-pkgs; a wrong id surfaces as a failed manifest row
on first real install so it can be corrected without guessing silently.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

# --- Profile sets (ids match ``--profile`` / Absentmind list) ---
P_WEB: Final[frozenset[str]] = frozenset({"web-fullstack"})
P_AI: Final[frozenset[str]] = frozenset({"ai-ml"})
P_WEB_AI: Final[frozenset[str]] = frozenset({"web-fullstack", "ai-ml"})
P_SYS: Final[frozenset[str]] = frozenset({"systems"})
P_GAME: Final[frozenset[str]] = frozenset({"game-dev"})
P_HW: Final[frozenset[str]] = frozenset({"hardware-robotics"})
P_SYS_GAME: Final[frozenset[str]] = frozenset({"systems", "game-dev"})
P_SYS_AI_WEB: Final[frozenset[str]] = frozenset({"systems", "web-fullstack", "ai-ml"})
P_WEB_AI_SYS: Final[frozenset[str]] = frozenset({"web-fullstack", "ai-ml", "systems"})
P_LANG_STACK: Final[frozenset[str]] = frozenset({"systems", "game-dev", "hardware-robotics", "ai-ml", "web-fullstack"})
P_EXTRAS: Final[frozenset[str]] = frozenset({"extras"})


@dataclass(frozen=True, slots=True)
class WingetCatalogEntry:
    """One winget-installable component."""

    tool: str
    winget_id: str
    layer: str
    # If set, at least one of these profiles must be selected.
    profiles: frozenset[str] | None
    detect_exe: str

    def applies_to(self, selected: set[str]) -> bool:
        if self.profiles is None:
            return True
        return bool(selected & self.profiles)


def _d(exe: str) -> Callable[[], bool]:
    return lambda: shutil.which(exe) is not None


# Order within a layer is install order (dependencies first where possible).
WINGET_CATALOG: tuple[WingetCatalogEntry, ...] = (
    # --- Layer 7: utilities (common) ---
    WingetCatalogEntry("7zip", "7zip.7zip", "utilities", None, "7z.exe"),
    WingetCatalogEntry("notepadplusplus", "Notepad++.Notepad++", "utilities", None, "notepad++.exe"),
    WingetCatalogEntry("everything", "voidtools.Everything", "utilities", None, "Everything.exe"),
    WingetCatalogEntry("devtoys", "DevToys-app.DevToys", "utilities", None, "DevToys.exe"),
    WingetCatalogEntry("winmerge", "WinMerge.WinMerge", "utilities", None, "WinMergeU.exe"),
    WingetCatalogEntry("dbeaver", "dbeaver.dbeaver", "utilities", P_WEB_AI, "dbeaver.exe"),
    WingetCatalogEntry("bruno", "Bruno.Bruno", "utilities", P_WEB_AI, "Bruno.exe"),
    WingetCatalogEntry("fork-git-client", "Fork.Fork", "utilities", P_WEB_AI, "Fork.exe"),
    WingetCatalogEntry("keepassxc", "KeePassXCTeam.KeePassXC", "utilities", P_WEB_AI, "KeePassXC.exe"),
    WingetCatalogEntry("sysinternals", "Microsoft.Sysinternals.Suite", "utilities", P_SYS, "procexp.exe"),
    WingetCatalogEntry("wireshark", "WiresharkFoundation.Wireshark", "utilities", P_SYS_GAME, "Wireshark.exe"),
    WingetCatalogEntry("nmap", "Insecure.Nmap", "utilities", P_SYS_GAME, "nmap.exe"),
    WingetCatalogEntry("arduino-ide", "ArduinoSA.IDE.stable", "utilities", P_HW, "arduino.exe"),
    # --- Layer 6: devops extras ---
    # Docker / Kubernetes are now catalog-driven so the GUI can exclude them.
    WingetCatalogEntry("docker-desktop", "Docker.DockerDesktop", "devops", P_WEB_AI, "docker.exe"),
    WingetCatalogEntry("kubectl", "Kubernetes.kubectl", "devops", P_WEB_AI_SYS, "kubectl.exe"),
    WingetCatalogEntry("helm", "Helm.Helm", "devops", P_WEB_AI_SYS, "helm.exe"),
    WingetCatalogEntry("postgresql-17", "PostgreSQL.PostgreSQL.17", "devops", P_WEB_AI, "psql.exe"),
    WingetCatalogEntry("redis", "Redis.Redis", "devops", P_WEB_AI, "redis-server.exe"),
    WingetCatalogEntry("mkcert", "FiloSottile.mkcert", "devops", P_WEB_AI, "mkcert.exe"),
    WingetCatalogEntry("ngrok", "Ngrok.Ngrok", "devops", P_WEB_AI, "ngrok.exe"),
    WingetCatalogEntry("aws-cli", "Amazon.AWSCLI", "devops", P_WEB_AI, "aws.exe"),
    WingetCatalogEntry("google-cloud-sdk", "Google.CloudSDK", "devops", P_WEB_AI, "gcloud.cmd"),
    WingetCatalogEntry("azure-cli", "Microsoft.AzureCLI", "devops", P_WEB_AI, "az.cmd"),
    WingetCatalogEntry("podman-desktop", "RedHat.Podman-Desktop", "devops", P_SYS_AI_WEB, "podman.exe"),
    # --- Layer 4: languages & build (profile-gated) ---
    WingetCatalogEntry("nvm-windows", "CoreyButler.NVMforWindows", "languages", P_WEB, "nvm.exe"),
    WingetCatalogEntry("golang", "GoLang.Go", "languages", P_LANG_STACK, "go.exe"),
    WingetCatalogEntry("temurin-jdk21", "EclipseAdoptium.Temurin.21.JDK", "languages", P_LANG_STACK, "java.exe"),
    WingetCatalogEntry("dotnet-sdk-8", "Microsoft.DotNet.SDK.8", "languages", P_SYS_GAME, "dotnet.exe"),
    WingetCatalogEntry("cmake", "Kitware.CMake", "languages", P_SYS_GAME, "cmake.exe"),
    WingetCatalogEntry("ninja", "NinjaBuild.Ninja", "languages", P_SYS_GAME, "ninja.exe"),
    WingetCatalogEntry("unity-hub", "Unity.UnityHub", "languages", P_GAME, "Unity Hub.exe"),
    WingetCatalogEntry("godot", "GodotEngine.GodotEngine", "languages", P_GAME, "godot.exe"),
    # --- AI/ML non-Python non-pip installs (catalog-driven for excludability) ---
    WingetCatalogEntry("ollama", "Ollama.Ollama", "ml_stack", P_AI, "ollama.exe"),
    # --- Layer 3: editors extras ---
    WingetCatalogEntry("jetbrains-toolbox", "JetBrains.Toolbox", "editors", P_WEB_AI, "jetbrains-toolbox.exe"),
    # --- Extras (opt-in profile; PROJECT.md personal-preference stack) ---
    WingetCatalogEntry("powertoys", "Microsoft.PowerToys", "extras", P_EXTRAS, "PowerToys.exe"),
    WingetCatalogEntry("obsidian", "Obsidian.Obsidian", "extras", P_EXTRAS, "Obsidian.exe"),
    WingetCatalogEntry("obs-studio", "OBSProject.OBSStudio", "extras", P_EXTRAS, "obs64.exe"),
    WingetCatalogEntry("sharex", "ShareX.ShareX", "extras", P_EXTRAS, "ShareX.exe"),
    WingetCatalogEntry("hwinfo", "REALiX.HWiNFO", "extras", P_EXTRAS, "HWiNFO64.exe"),
    WingetCatalogEntry("wiztree", "AntibodySoftware.WizTree", "extras", P_EXTRAS, "WizTree.exe"),
    WingetCatalogEntry("vlc", "VideoLAN.VLC", "extras", P_EXTRAS, "vlc.exe"),
    WingetCatalogEntry("bitwarden", "Bitwarden.Bitwarden", "extras", P_EXTRAS, "Bitwarden.exe"),
    WingetCatalogEntry("autohotkey", "AutoHotkey.AutoHotkey", "extras", P_EXTRAS, "AutoHotkey.exe"),
    WingetCatalogEntry("discord", "Discord.Discord", "extras", P_EXTRAS, "Discord.exe"),
    WingetCatalogEntry("ffmpeg", "Gyan.FFmpeg", "extras", P_EXTRAS, "ffmpeg.exe"),
)


def catalog_entries_for_layer(layer: str) -> Sequence[WingetCatalogEntry]:
    return tuple(e for e in WINGET_CATALOG if e.layer == layer)


def count_winget_actions(
    selected_profiles: Sequence[str],
    *,
    catalog_excludes: Sequence[str] | frozenset[str] | set[str] | None = None,
) -> int:
    """Count catalog winget rows that would run (profile match, minus user exclusions)."""
    sel = set(selected_profiles)
    ex = set(catalog_excludes or ())
    return sum(
        1 for e in WINGET_CATALOG if e.tool not in ex and e.applies_to(sel)
    )


# Approximate installed footprint in MB for catalog entries. These are rough
# order-of-magnitude numbers — fine for a ballpark summary, not disk planning.
# Missing entries default to 100 MB via ``estimate_tool_disk_mb``.
TOOL_DISK_MB: Final[dict[str, int]] = {
    # Layer 7 utilities
    "7zip": 10,
    "notepadplusplus": 30,
    "everything": 15,
    "devtoys": 120,
    "winmerge": 40,
    "dbeaver": 450,
    "bruno": 220,
    "fork-git-client": 200,
    "keepassxc": 110,
    "sysinternals": 100,
    "wireshark": 180,
    "nmap": 60,
    "arduino-ide": 500,
    # Layer 6 devops
    "docker-desktop": 1200,
    "kubectl": 10,
    "helm": 15,
    "postgresql-17": 550,
    "redis": 5,
    "mkcert": 10,
    "ngrok": 25,
    "aws-cli": 90,
    "google-cloud-sdk": 350,
    "azure-cli": 850,
    "podman-desktop": 450,
    # Layer 4 languages
    "nvm-windows": 10,
    "golang": 550,
    "temurin-jdk21": 430,
    "dotnet-sdk-8": 650,
    "cmake": 120,
    "ninja": 5,
    "unity-hub": 220,
    "godot": 120,
    # ML stack
    "ollama": 350,
    # Layer 3 editors
    "jetbrains-toolbox": 500,
    # Extras
    "powertoys": 320,
    "obsidian": 220,
    "obs-studio": 320,
    "sharex": 110,
    "hwinfo": 40,
    "wiztree": 5,
    "vlc": 110,
    "bitwarden": 180,
    "autohotkey": 20,
    "discord": 220,
    "ffmpeg": 250,
}


def estimate_tool_disk_mb(tool: str) -> int:
    """Approximate install footprint for a single catalog tool (MB)."""
    return TOOL_DISK_MB.get(tool, 100)


def estimate_catalog_disk_mb(
    selected_profiles: Sequence[str],
    *,
    catalog_excludes: Sequence[str] | frozenset[str] | set[str] | None = None,
) -> int:
    """Sum of approximate MB for every catalog entry this run would install."""
    sel = set(selected_profiles)
    ex = set(catalog_excludes or ())
    total = 0
    for e in WINGET_CATALOG:
        if e.tool in ex:
            continue
        if not e.applies_to(sel):
            continue
        total += estimate_tool_disk_mb(e.tool)
    return total


def _exe_found(name: str) -> bool:
    return shutil.which(name) is not None


def _path_if_file(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _extras_paths(tool: str) -> list[Path]:
    """Typical install locations when an app is not on PATH."""
    pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    pfx86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    loc = Path(os.environ.get("LOCALAPPDATA", ""))
    roaming = Path(os.environ.get("APPDATA", ""))
    maps: dict[str, list[Path]] = {
        "powertoys": [
            pf / "PowerToys" / "PowerToys.exe",
            pfx86 / "PowerToys" / "PowerToys.exe",
        ],
        "obsidian": [
            loc / "Programs" / "obsidian" / "Obsidian.exe",
            pf / "Obsidian" / "Obsidian.exe",
        ],
        "obs-studio": [
            pf / "obs-studio" / "bin" / "64bit" / "obs64.exe",
            pfx86 / "obs-studio" / "bin" / "64bit" / "obs64.exe",
        ],
        "sharex": [pf / "ShareX" / "ShareX.exe", pfx86 / "ShareX" / "ShareX.exe"],
        "hwinfo": [
            pf / "HWiNFO64" / "HWiNFO64.exe",
            pfx86 / "HWiNFO64" / "HWiNFO64.exe",
        ],
        "wiztree": [pf / "WizTree" / "WizTree.exe", pfx86 / "WizTree" / "WizTree.exe"],
        "vlc": [pf / "VideoLAN" / "VLC" / "vlc.exe", pfx86 / "VideoLAN" / "VLC" / "vlc.exe"],
        "bitwarden": [
            loc / "Programs" / "Bitwarden" / "Bitwarden.exe",
            pf / "Bitwarden" / "Bitwarden.exe",
        ],
        "autohotkey": [
            pf / "AutoHotkey" / "v2" / "AutoHotkey.exe",
            pfx86 / "AutoHotkey" / "v2" / "AutoHotkey.exe",
        ],
        "discord": [
            loc / "Discord" / "app-1.0.0" / "Discord.exe",
            roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Discord Inc" / "Discord.exe",
        ],
    }
    return maps.get(tool, [])


def get_detector(entry: WingetCatalogEntry) -> Callable[[], bool]:
    """Return presence detector for *entry* (exe on PATH or standard location)."""
    exe = entry.detect_exe
    if entry.layer == "extras":
        extras_check = _extras_paths(entry.tool)

        def _extras_detect() -> bool:
            if _exe_found(exe):
                return True
            return any(_path_if_file(p) for p in extras_check)

        if entry.tool == "discord":
            # Discord updates live under …/Discord/app-<version>/Discord.exe
            root = Path(os.environ.get("LOCALAPPDATA", "")) / "Discord"

            def _discord_detect() -> bool:
                if _exe_found("Discord.exe"):
                    return True
                if root.is_dir():
                    for child in sorted(root.iterdir(), reverse=True):
                        if child.is_dir() and child.name.startswith("app-"):
                            cand = child / "Discord.exe"
                            if _path_if_file(cand):
                                return True
                return False

            return _discord_detect

        if entry.tool == "ffmpeg":
            return lambda: _exe_found("ffmpeg.exe") or _exe_found("ffmpeg")

        return _extras_detect

    if entry.tool == "godot":
        return lambda: bool(
            shutil.which("godot.exe") or shutil.which("Godot.exe") or shutil.which("godot4_console.exe")
        )
    if entry.tool == "unity-hub":
        return lambda: bool(shutil.which("Unity Hub.exe") or shutil.which("Unity.exe"))
    if exe == "java.exe":
        return lambda: bool(shutil.which("java.exe") or shutil.which("javac.exe"))
    if exe == "az.cmd":
        return lambda: bool(shutil.which("az.cmd") or shutil.which("az.exe"))
    if exe == "gcloud.cmd":
        return lambda: bool(shutil.which("gcloud.cmd") or shutil.which("gcloud.exe"))
    if entry.tool == "redis":
        return lambda: bool(
            shutil.which("redis-server.exe")
            or shutil.which("redis-cli.exe")
            or shutil.which("redis-cli")
        )
    if entry.tool == "postgresql-17":
        return lambda: bool(shutil.which("psql.exe"))
    return _d(exe)
