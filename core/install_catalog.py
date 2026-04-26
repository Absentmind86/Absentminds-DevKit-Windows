"""Cross-platform package catalog toward PROJECT.md Phase 2B (profile-gated where noted).

win_id     — winget package ID (Windows)
choco_id   — Chocolatey package ID (Windows fallback when winget fails); None = skip
linux_id   — apt/dnf/pacman package name (Linux); None = not available / skip
linux_repo — key into linux_util._APT_REPO_SETUP; third-party repo to add before apt install
macos_id   — brew formula or cask name (macOS); None = not available / skip
macos_cask — True when macos_id is a brew cask (GUI app), False for formulas
brew_tap   — homebrew tap to run before brew install (e.g. "adoptium/adoptium")

A wrong id surfaces as a failed manifest row on first real install so it can be
corrected without guessing silently.
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
P_SYS_HW: Final[frozenset[str]] = frozenset({"systems", "hardware-robotics"})
P_SYS_GAME_HW: Final[frozenset[str]] = frozenset({"systems", "game-dev", "hardware-robotics"})
P_SYS_AI_WEB: Final[frozenset[str]] = frozenset({"systems", "web-fullstack", "ai-ml"})
P_WEB_AI_SYS: Final[frozenset[str]] = frozenset({"web-fullstack", "ai-ml", "systems"})
P_WEB_SYS_GAME: Final[frozenset[str]] = frozenset({"web-fullstack", "systems", "game-dev"})
P_LANG_STACK: Final[frozenset[str]] = frozenset({"systems", "game-dev", "hardware-robotics", "ai-ml", "web-fullstack"})
P_EXTRAS: Final[frozenset[str]] = frozenset({"extras"})


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    """One cross-platform installable component."""

    tool: str
    win_id: str
    layer: str
    # If set, at least one of these profiles must be selected.
    profiles: frozenset[str] | None
    detect_exe: str
    linux_id: str | None = None
    macos_id: str | None = None
    macos_cask: bool = False
    choco_id: str | None = None     # Chocolatey fallback (Windows only)
    brew_tap: str | None = None     # brew tap to run before brew install
    linux_repo: str | None = None   # key into linux_util._APT_REPO_SETUP

    def applies_to(self, selected: set[str]) -> bool:
        if self.profiles is None:
            return True
        return bool(selected & self.profiles)


# Backward-compat alias — existing imports of WingetCatalogEntry continue to work.
WingetCatalogEntry = CatalogEntry


def _d(exe: str) -> Callable[[], bool]:
    return lambda: shutil.which(exe) is not None


# Order within a layer is install order (dependencies first where possible).
# linux_id  = apt/dnf/pacman package name (None = not available via standard pkg manager)
# macos_id  = brew formula or cask name   (None = not available on macOS)
# macos_cask = True when macos_id is a brew --cask (GUI app); False = formula (CLI tool)
WINGET_CATALOG: tuple[CatalogEntry, ...] = (
    # --- Layer 2: infrastructure ---
    # Git, Git LFS, Scoop, OpenSSH are bootstrap prereqs — not in this catalog.
    CatalogEntry("github-cli",
        "GitHub.cli", "infrastructure", None, "gh.exe",
        linux_id="gh", macos_id="gh",
        choco_id="gh", linux_repo="gh"),
    CatalogEntry("windows-terminal",
        "Microsoft.WindowsTerminal", "infrastructure", None, "wt.exe",
        choco_id="microsoft-windows-terminal"),
    CatalogEntry("powershell-7",
        "Microsoft.PowerShell", "infrastructure", None, "pwsh.exe",
        linux_id="powershell", macos_id="powershell",
        choco_id="powershell-core", linux_repo="microsoft"),
    CatalogEntry("oh-my-posh",
        "JanDeDobbeleer.OhMyPosh", "infrastructure", None, "oh-my-posh.exe",
        macos_id="oh-my-posh",
        choco_id="oh-my-posh", brew_tap="jandedobbeleer/oh-my-posh"),
    CatalogEntry("tailscale",
        "Tailscale.Tailscale", "infrastructure", None, "tailscale.exe",
        linux_id="tailscale", macos_id="tailscale", macos_cask=True,
        choco_id="tailscale", linux_repo="tailscale"),

    # --- Layer 3: editors ---
    CatalogEntry("vscode",
        "Microsoft.VisualStudioCode", "editors", None, "code.cmd",
        linux_id="code", macos_id="visual-studio-code", macos_cask=True,
        choco_id="vscode", linux_repo="vscode"),
    CatalogEntry("cursor",
        "Anysphere.Cursor", "editors", None, "cursor.exe",
        macos_id="cursor", macos_cask=True),  # no official Linux apt pkg (AppImage only)

    # --- Layer 7: utilities ---
    CatalogEntry("7zip",
        "7zip.7zip", "utilities", None, "7z.exe",
        linux_id="p7zip-full", macos_id="sevenzip",
        choco_id="7zip"),
    CatalogEntry("notepadplusplus",
        "Notepad++.Notepad++", "utilities", None, "notepad++.exe",
        choco_id="notepadplusplus"),
    CatalogEntry("everything",
        "voidtools.Everything", "utilities", None, "Everything.exe",
        choco_id="everything"),
    CatalogEntry("devtoys",
        "DevToys-app.DevToys", "utilities", None, "DevToys.exe",
        choco_id="devtoys"),
    CatalogEntry("winmerge",
        "WinMerge.WinMerge", "utilities", None, "WinMergeU.exe",
        choco_id="winmerge"),
    CatalogEntry("dbeaver",
        "DBeaver.DBeaver.Community", "utilities", P_WEB_AI, "dbeaver.exe",
        linux_id="dbeaver-ce", macos_id="dbeaver-community", macos_cask=True,
        choco_id="dbeaver"),
    CatalogEntry("bruno",
        "Bruno.Bruno", "utilities", P_WEB_AI, "Bruno.exe",
        linux_id="bruno", macos_id="bruno", macos_cask=True,
        choco_id="bruno"),
    CatalogEntry("sysinternals",
        "Microsoft.Sysinternals.Suite", "utilities", P_SYS_HW, "procexp.exe",
        choco_id="sysinternals"),
    CatalogEntry("wireshark",
        "WiresharkFoundation.Wireshark", "utilities", P_SYS_GAME_HW, "Wireshark.exe",
        linux_id="wireshark", macos_id="wireshark", macos_cask=True,
        choco_id="wireshark"),
    CatalogEntry("nmap",
        "Insecure.Nmap", "utilities", P_SYS, "nmap.exe",
        linux_id="nmap", macos_id="nmap",
        choco_id="nmap"),
    CatalogEntry("arduino-ide",
        "ArduinoSA.IDE.stable", "utilities", P_HW, "arduino.exe",
        macos_id="arduino-ide", macos_cask=True,
        choco_id="arduino-ide"),
    CatalogEntry("putty",
        "PuTTY.PuTTY", "utilities", P_HW, "putty.exe",
        linux_id="putty", macos_id="putty",
        choco_id="putty"),

    # --- Layer 6: devops ---
    # Docker / Kubernetes are catalog-driven so the GUI can exclude them.
    CatalogEntry("docker-desktop",
        "Docker.DockerDesktop", "devops", P_WEB_AI_SYS, "docker.exe",
        macos_id="docker", macos_cask=True,
        choco_id="docker-desktop"),
    CatalogEntry("kubectl",
        "Kubernetes.kubectl", "devops", P_WEB_AI_SYS, "kubectl.exe",
        linux_id="kubectl", macos_id="kubectl",
        choco_id="kubernetes-cli", linux_repo="kubernetes"),
    CatalogEntry("helm",
        "Helm.Helm", "devops", P_WEB_AI_SYS, "helm.exe",
        linux_id="helm", macos_id="helm",
        choco_id="kubernetes-helm", linux_repo="helm"),
    CatalogEntry("postgresql-17",
        "PostgreSQL.PostgreSQL.17", "devops", P_WEB_AI, "psql.exe",
        linux_id="postgresql", macos_id="postgresql@17",
        choco_id="postgresql"),
    CatalogEntry("redis",
        "Redis.Redis", "devops", P_WEB_AI, "redis-server.exe",
        linux_id="redis-server", macos_id="redis",
        choco_id="redis-64"),
    CatalogEntry("mkcert",
        "FiloSottile.mkcert", "devops", P_WEB_AI, "mkcert.exe",
        linux_id="mkcert", macos_id="mkcert",
        choco_id="mkcert"),
    CatalogEntry("ngrok",
        "Ngrok.Ngrok", "devops", P_WEB_AI, "ngrok.exe",
        linux_id="ngrok", macos_id="ngrok", macos_cask=True,
        choco_id="ngrok", linux_repo="ngrok"),
    CatalogEntry("aws-cli",
        "Amazon.AWSCLI", "devops", P_WEB_AI_SYS, "aws.exe",
        linux_id="awscli", macos_id="awscli",
        choco_id="awscli"),
    CatalogEntry("google-cloud-sdk",
        "Google.CloudSDK", "devops", P_WEB_AI_SYS, "gcloud.cmd",
        linux_id="google-cloud-sdk", macos_id="google-cloud-sdk", macos_cask=True,
        choco_id="gcloudsdk", linux_repo="google-cloud"),
    CatalogEntry("azure-cli",
        "Microsoft.AzureCLI", "devops", P_WEB_AI_SYS, "az.cmd",
        linux_id="azure-cli", macos_id="azure-cli",
        choco_id="azure-cli", linux_repo="azure-cli"),
    CatalogEntry("podman-desktop",
        "RedHat.Podman-Desktop", "devops", P_SYS_AI_WEB, "podman.exe",
        macos_id="podman-desktop", macos_cask=True,
        choco_id="podman-desktop"),

    # --- Layer 4: languages & build ---
    CatalogEntry("uv",
        "astral-sh.uv", "languages", None, "uv.exe",
        linux_id="uv", macos_id="uv",
        choco_id="uv"),
    CatalogEntry("nvm-windows",
        "CoreyButler.NVMforWindows", "languages", P_WEB, "nvm.exe",
        macos_id="nvm",
        choco_id="nvm"),  # Linux handled via curl installer in languages.py
    CatalogEntry("golang",
        "GoLang.Go", "languages", P_WEB_AI_SYS, "go.exe",
        linux_id="golang-go", macos_id="go",
        choco_id="golang"),
    CatalogEntry("temurin-jdk21",
        "EclipseAdoptium.Temurin.21.JDK", "languages", P_WEB_SYS_GAME, "java.exe",
        linux_id="temurin-21", macos_id="temurin@21", macos_cask=True,
        choco_id="temurin21", brew_tap="adoptium/adoptium", linux_repo="adoptium"),
    CatalogEntry("dotnet-sdk-8",
        "Microsoft.DotNet.SDK.8", "languages", P_WEB_SYS_GAME, "dotnet.exe",
        linux_id="dotnet-sdk-8.0", macos_id="dotnet-sdk", macos_cask=True,
        choco_id="dotnet-sdk", linux_repo="microsoft"),
    CatalogEntry("cmake",
        "Kitware.CMake", "languages", P_SYS_GAME_HW, "cmake.exe",
        linux_id="cmake", macos_id="cmake",
        choco_id="cmake"),
    CatalogEntry("ninja",
        "Ninja-build.Ninja", "languages", P_SYS_GAME_HW, "ninja.exe",
        linux_id="ninja-build", macos_id="ninja",
        choco_id="ninja"),
    CatalogEntry("unity-hub",
        "Unity.UnityHub", "languages", P_GAME, "Unity Hub.exe",
        linux_id="unityhub", macos_id="unity-hub", macos_cask=True,
        choco_id="unity-hub", linux_repo="unity"),
    CatalogEntry("godot",
        "GodotEngine.GodotEngine", "languages", P_GAME, "godot.exe",
        macos_id="godot", macos_cask=True,
        choco_id="godot"),

    # --- AI/ML ---
    CatalogEntry("ollama",
        "Ollama.Ollama", "ml_stack", P_AI, "ollama.exe",
        macos_id="ollama", macos_cask=True,
        choco_id="ollama"),

    # --- Layer 3: editors extras ---
    CatalogEntry("jetbrains-toolbox",
        "JetBrains.Toolbox", "editors", P_LANG_STACK, "jetbrains-toolbox.exe",
        macos_id="jetbrains-toolbox", macos_cask=True,
        choco_id="jetbrains-toolbox"),

    # --- Extras ---
    CatalogEntry("powertoys",
        "Microsoft.PowerToys", "extras", P_EXTRAS, "PowerToys.exe",
        choco_id="powertoys"),
    CatalogEntry("obsidian",
        "Obsidian.Obsidian", "extras", P_EXTRAS, "Obsidian.exe",
        macos_id="obsidian", macos_cask=True,
        choco_id="obsidian"),
    CatalogEntry("obs-studio",
        "OBSProject.OBSStudio", "extras", P_EXTRAS, "obs64.exe",
        linux_id="obs-studio", macos_id="obs", macos_cask=True,
        choco_id="obs-studio"),
    CatalogEntry("sharex",
        "ShareX.ShareX", "extras", P_EXTRAS, "ShareX.exe",
        choco_id="sharex"),
    CatalogEntry("hwinfo",
        "REALiX.HWiNFO", "extras", P_EXTRAS, "HWiNFO64.exe",
        choco_id="hwinfo"),
    CatalogEntry("wiztree",
        "AntibodySoftware.WizTree", "extras", P_EXTRAS, "WizTree.exe",
        choco_id="wiztree"),
    CatalogEntry("vlc",
        "VideoLAN.VLC", "extras", P_EXTRAS, "vlc.exe",
        linux_id="vlc", macos_id="vlc", macos_cask=True,
        choco_id="vlc"),
    CatalogEntry("bitwarden",
        "Bitwarden.Bitwarden", "extras", P_EXTRAS, "Bitwarden.exe",
        macos_id="bitwarden", macos_cask=True,
        choco_id="bitwarden"),
    CatalogEntry("keepassxc",
        "KeePassXCTeam.KeePassXC", "extras", P_EXTRAS, "KeePassXC.exe",
        linux_id="keepassxc", macos_id="keepassxc", macos_cask=True,
        choco_id="keepassxc"),
    CatalogEntry("fork-git-client",
        "Fork.Fork", "extras", P_EXTRAS, "Fork.exe",
        macos_id="fork", macos_cask=True,
        choco_id="fork"),
    CatalogEntry("autohotkey",
        "AutoHotkey.AutoHotkey", "extras", P_EXTRAS, "AutoHotkey.exe",
        choco_id="autohotkey"),
    CatalogEntry("discord",
        "Discord.Discord", "extras", P_EXTRAS, "Discord.exe",
        macos_id="discord", macos_cask=True,
        choco_id="discord"),
    CatalogEntry("ffmpeg",
        "Gyan.FFmpeg", "extras", P_EXTRAS, "ffmpeg.exe",
        linux_id="ffmpeg", macos_id="ffmpeg",
        choco_id="ffmpeg"),
)


def catalog_entries_for_layer(layer: str) -> Sequence[CatalogEntry]:
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
    # Layer 2 infrastructure
    "github-cli":       60,
    "windows-terminal": 150,
    "powershell-7":     220,
    "oh-my-posh":       30,
    "tailscale":        80,
    # Layer 4 languages (always-on)
    "uv":               20,
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
    "putty": 5,
    # Layer 3 editors (common)
    "vscode":  400,
    "cursor":  350,
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
        "keepassxc": [
            pf / "KeePassXC" / "KeePassXC.exe",
            pfx86 / "KeePassXC" / "KeePassXC.exe",
        ],
        "fork-git-client": [
            loc / "Fork" / "Fork.exe",
            pf / "Fork" / "Fork.exe",
        ],
        "autohotkey": [
            pf / "AutoHotkey" / "AutoHotkey.exe",        # winget v2 launcher
            pf / "AutoHotkey" / "v2" / "AutoHotkey64.exe",  # v2 native exe
            pf / "AutoHotkey" / "v2" / "AutoHotkey.exe",
            pfx86 / "AutoHotkey" / "AutoHotkey.exe",
        ],
        "discord": [
            loc / "Discord" / "app-1.0.0" / "Discord.exe",
            roaming / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Discord Inc" / "Discord.exe",
        ],
    }
    return maps.get(tool, [])


def get_detector(entry: CatalogEntry) -> Callable[[], bool]:
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

    if entry.tool == "cursor":
        _cursor_path = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "cursor" / "Cursor.exe"
        return lambda: _exe_found("cursor.exe") or _path_if_file(_cursor_path)

    # GUI apps that do not reliably register on PATH after winget install
    _loc = Path(os.environ.get("LOCALAPPDATA", ""))
    _pf  = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    _pfx = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))

    if entry.tool == "jetbrains-toolbox":
        _jb = _loc / "JetBrains" / "Toolbox" / "bin" / "jetbrains-toolbox.exe"
        return lambda: _exe_found("jetbrains-toolbox.exe") or _path_if_file(_jb)

    if entry.tool == "arduino-ide":
        _ard = _loc / "Arduino IDE" / "Arduino IDE.exe"
        return lambda: _exe_found("arduino.exe") or _path_if_file(_ard)

    if entry.tool == "bruno":
        _bruno = _loc / "Programs" / "Bruno" / "Bruno.exe"
        return lambda: _exe_found("Bruno.exe") or _exe_found("bruno.exe") or _path_if_file(_bruno)

    if entry.tool == "notepadplusplus":
        _npp = _pf / "Notepad++" / "notepad++.exe"
        _nppx = _pfx / "Notepad++" / "notepad++.exe"
        return lambda: _exe_found("notepad++.exe") or _path_if_file(_npp) or _path_if_file(_nppx)

    if entry.tool == "dbeaver":
        _db = _pf / "DBeaver" / "dbeaver.exe"
        return lambda: _exe_found("dbeaver.exe") or _path_if_file(_db)

    if entry.tool == "winmerge":
        _wm = _pf / "WinMerge" / "WinMergeU.exe"
        _wmx = _pfx / "WinMerge" / "WinMergeU.exe"
        return lambda: _exe_found("WinMergeU.exe") or _path_if_file(_wm) or _path_if_file(_wmx)

    if entry.tool == "godot":
        return lambda: bool(
            shutil.which("godot.exe") or shutil.which("Godot.exe") or shutil.which("godot4_console.exe")
        )
    if entry.tool == "unity-hub":
        _uh_pf  = Path(os.environ.get("PROGRAMFILES",      "C:\\Program Files"))          / "Unity Hub" / "Unity Hub.exe"
        _uh_pf86 = Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"))   / "Unity Hub" / "Unity Hub.exe"
        _uh_local = Path(os.environ.get("LOCALAPPDATA",    "")) / "Programs" / "Unity Hub" / "Unity Hub.exe"
        return lambda: bool(_uh_pf.is_file() or _uh_pf86.is_file() or _uh_local.is_file() or shutil.which("unityhub"))
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
