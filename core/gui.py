"""Phase 3 — Flet launcher for AM-DevKit (opt-in per-tool selection).

Run from the repository root::

    python -m core.gui

Launches ``core.installer`` in a new console on Windows.

State model
-----------
``desired_tools: set[str]``  — catalog tool-ids the user has opted in to.
``active_features: set[str]`` — non-catalog feature keys (``pytorch-wheels``,
  ``ml-base``) that map to --install-* installer flags.

Profile checkboxes act as "select all" conveniences.  Unchecking any individual
tool under a profile unchecks the profile header (partial selection) and
auto-checks the "Custom" view mode so the user can see their picks.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# Profile metadata
# ---------------------------------------------------------------------------

STANDARD_PROFILE_IDS: tuple[str, ...] = (
    "ai-ml",
    "web-fullstack",
    "systems",
    "game-dev",
    "hardware-robotics",
)

PROFILE_PREFERENCE: tuple[str, ...] = (
    "web-fullstack",
    "systems",
    "hardware-robotics",
    "game-dev",
    "ai-ml",
    "extras",
)

PROFILE_DEFS: tuple[tuple[str, str], ...] = (
    ("ai-ml",             "AI / ML"),
    ("web-fullstack",     "Web / Full-Stack"),
    ("systems",           "Systems / Low-Level"),
    ("game-dev",          "Game Dev"),
    ("hardware-robotics", "Hardware / Robotics"),
    ("custom",            "Custom — cherry-pick from all stacks"),
)

PROFILE_HINTS: dict[str, str] = {
    "ai-ml":             "Ollama, GPU-aware PyTorch, ML pip stack, Jupyter, DBeaver, PostgreSQL, Redis, Docker, kubectl, Helm, cloud CLIs, Rust (rustup).",
    "web-fullstack":     "Node via NVM, Go, JDK 21, .NET 8, Bruno, DBeaver, PostgreSQL, Redis, mkcert, ngrok, Docker, kubectl, Helm, cloud CLIs, JetBrains Toolbox.",
    "systems":           "Rust (rustup), Go, .NET 8, JDK 21, CMake, Ninja, Docker, kubectl, Helm, Podman, Wireshark, Nmap, Sysinternals, cloud CLIs.",
    "game-dev":          "Unity Hub, Godot, .NET 8, JDK 21, Rust (rustup), CMake, Ninja, Wireshark, JetBrains Toolbox.",
    "hardware-robotics": "Arduino IDE, PuTTY, Rust (rustup), CMake, Ninja, Wireshark, Sysinternals, pyserial / USB tooling.",
    "custom":            "View-mode toggle — exposes every stack's tools so you can cherry-pick anything.",
}

PROFILE_DISPLAY: dict[str, str] = dict(PROFILE_DEFS)

# Non-catalog, non-winget features that map to installer flags.
# Rendered as real checkboxes under their profile section.
# format: (display_name, description, installer_flag, ui_key)
PROFILE_FEATURE_ITEMS: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "ai-ml": (
        ("PyTorch wheels", "GPU-matched CUDA or CPU fallback via pip", "--install-ml-wheels", "install_ml_wheels"),
        ("ML pip base",    "numpy, pandas, matplotlib, scikit-learn, jupyter, ipython", "--install-ml-base", "install_ml_base"),
    ),
}

# Only truly locked items — Python + flet/rich are required to run this GUI.
CORE_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("Python 3",   "runtime — already running the GUI",      "required"),
    ("flet, rich", "GUI/CLI deps (pip) — already installed", "required"),
)

# Approximate count of non-catalog foundation tools that always install:
# Git, Git LFS, GitHub CLI, Windows Terminal, PowerShell 7, OpenSSH, uv,
# pyenv-win, Scoop, Scoop CLI suite, Oh My Posh, Tailscale,
# restore-point, dotfiles.
# Note: Nerd Fonts is NOT currently automated (Oh My Posh degrades gracefully without it).
FOUNDATION_ALWAYS_COUNT: int = 14

# Hover tooltips shown on every catalog tool checkbox and feature toggle.
TOOL_TOOLTIPS: dict[str, str] = {
    # Layer 2 infrastructure (common — excludable) -------------------------
    "github-cli":        "GitHub CLI (gh) — manage repos, PRs, issues, and Actions from the terminal. Pairs with Git for a complete GitHub workflow.",
    "windows-terminal":  "Windows Terminal — modern multi-tab terminal with GPU-accelerated text rendering, profiles, and Unicode support.",
    "powershell-7":      "PowerShell 7 — cross-platform shell replacing the built-in Windows PowerShell 5.1. Required for modern scripting and AM-DevKit's own tools.",
    "oh-my-posh":        "Oh My Posh — prompt theme engine. Adds git status, active venv, execution time, and more to your PowerShell/bash prompt.",
    "tailscale":         "Tailscale — zero-config mesh VPN. Securely connects your machines across networks without port-forwarding or static IPs.",
    # Layer 4 languages (common — excludable) ------------------------------
    "uv":                "uv — extremely fast Python package and project manager (Rust-backed). Replaces pip/pip-tools/venv for day-to-day Python work.",
    # Common tools (profiles=None) ----------------------------------------
    "vscode":            "Visual Studio Code — lightweight, extensible editor by Microsoft. Extensions installed from config/vscode/extensions.json.",
    "cursor":            "Cursor — AI-native code editor built on VS Code with Claude / Copilot integration baked in.",
    "7zip":              "7-Zip — open-source file archiver supporting ZIP, 7z, TAR, GZ, RAR and more.",
    "notepadplusplus":   "Notepad++ — fast text and code editor with syntax highlighting, multi-tab editing, and macro recording.",
    "everything":        "Everything — instant file search across your entire drive. Finds files by name in milliseconds.",
    "devtoys":           "DevToys — developer Swiss-army knife: JSON formatter, base64, hash generator, regex tester, diff viewer, and more.",
    "winmerge":          "WinMerge — visual diff and merge tool for files and folders. Great for comparing configs and code.",
    # Utilities (profile-gated) -------------------------------------------
    "dbeaver":           "DBeaver — universal database GUI client supporting PostgreSQL, MySQL, SQLite, and 100+ other databases.",
    "bruno":             "Bruno — open-source API client (Postman/Insomnia alternative). Collections stored as plain text files — Git-friendly.",
    "fork-git-client":   "Fork — fast, friendly Git GUI with visual branching, merge conflict resolution, and a built-in diff viewer.",
    "keepassxc":         "KeePassXC — open-source offline password manager. Credentials stored in a local encrypted database.",
    "sysinternals":      "Sysinternals Suite — Microsoft's advanced Windows utilities: Process Explorer, Autoruns, TCPView, ProcMon, and more.",
    "wireshark":         "Wireshark — network protocol analyzer. Capture and inspect live packets for debugging and security analysis.",
    "nmap":              "Nmap — network discovery and security scanner. Maps open ports and services on reachable hosts.",
    "arduino-ide":       "Arduino IDE — official IDE for programming Arduino boards and compatible microcontrollers.",
    "putty":             "PuTTY — SSH, Telnet, and serial console client. Essential for talking to embedded devices over UART/USB-serial.",
    # DevOps --------------------------------------------------------------
    "docker-desktop":    "Docker Desktop — containerization platform with GUI, CLI, and Compose for running Linux containers on Windows.",
    "kubectl":           "kubectl — Kubernetes CLI. Deploy, inspect, and manage containerized workloads in any K8s cluster.",
    "helm":              "Helm — Kubernetes package manager. Install and upgrade pre-configured application charts.",
    "postgresql-17":     "PostgreSQL 17 — powerful open-source relational database, widely used for web apps and data pipelines.",
    "redis":             "Redis — in-memory key-value store used for caching, sessions, pub/sub messaging, and fast data structures.",
    "mkcert":            "mkcert — create locally trusted TLS certificates with zero config. Enables HTTPS on localhost for dev.",
    "ngrok":             "ngrok — expose local servers to the internet via secure tunnels. Useful for webhooks, demos, and API testing.",
    "aws-cli":           "AWS CLI — command-line interface for Amazon Web Services: S3, EC2, Lambda, and all other AWS services.",
    "google-cloud-sdk":  "Google Cloud SDK — gcloud, gsutil, and bq CLI tools for all Google Cloud Platform services.",
    "azure-cli":         "Azure CLI — command-line tool for creating and managing Microsoft Azure resources.",
    "podman-desktop":    "Podman Desktop — daemonless, rootless container engine (Docker-compatible) with a GUI. No background daemon required.",
    # Languages & build ---------------------------------------------------
    "nvm-windows":       "NVM for Windows — Node Version Manager. Install and switch between Node.js versions per project.",
    "golang":            "Go (golang) — fast, statically typed language by Google. Great for CLIs, cloud services, embedded tooling, and microservices.",
    "temurin-jdk21":     "Eclipse Temurin JDK 21 — open-source Java 21 LTS runtime and SDK by the Adoptium project.",
    "dotnet-sdk-8":      ".NET SDK 8 — Microsoft's cross-platform SDK for C# and F#. Required for Unity scripting, WinForms, and ASP.NET.",
    "cmake":             "CMake — cross-platform build system generator. The de-facto standard for C/C++ projects and embedded firmware.",
    "ninja":             "Ninja — ultra-fast build system, typically used as CMake's backend generator for C/C++ and embedded builds.",
    "unity-hub":         "Unity Hub — launcher and license manager for Unity Editor versions. Required to start Unity game development.",
    "godot":             "Godot Engine — open-source 2D/3D game engine with GDScript (Python-like) and C# support. No royalties.",
    # ML stack ------------------------------------------------------------
    "ollama":            "Ollama — run large language models locally (Llama, Mistral, Gemma, Phi, and more) via a simple CLI and REST API.",
    # Editors extras ------------------------------------------------------
    "jetbrains-toolbox": "JetBrains Toolbox — launcher for all JetBrains IDEs: IntelliJ IDEA, PyCharm, WebStorm, Rider, GoLand, and more.",
    # Extras (opt-in) -----------------------------------------------------
    "powertoys":         "Microsoft PowerToys — power-user utilities: FancyZones, PowerRename, Color Picker, Run launcher, and more.",
    "obsidian":          "Obsidian — markdown knowledge base and note-taking with a graph view, backlinks, and a rich plugin ecosystem.",
    "obs-studio":        "OBS Studio — free, open-source screen recording and live streaming software.",
    "sharex":            "ShareX — advanced screenshot and screen recording with annotations, workflows, and upload support.",
    "hwinfo":            "HWiNFO — detailed hardware information and real-time sensor monitoring: temps, voltages, fan speeds.",
    "wiztree":           "WizTree — the fastest disk space analyzer. Visualizes what is consuming your drive in seconds.",
    "vlc":               "VLC — universal media player supporting virtually every audio and video format, including network streams.",
    "bitwarden":         "Bitwarden — open-source password manager with cloud sync, browser extensions, and mobile apps.",
    "autohotkey":        "AutoHotkey — Windows automation scripting. Remap keys, automate repetitive tasks, and build simple GUIs.",
    "discord":           "Discord — voice, video, and text chat platform. Popular in dev communities, gaming, and open-source projects.",
    "ffmpeg":            "FFmpeg — command-line multimedia framework for converting, encoding, streaming, and processing audio/video files.",
    # Feature toggles (map to ui_key, not tool id) -----------------------
    "install_ml_wheels": "Installs GPU-matched PyTorch via pip. Auto-detects NVIDIA CUDA and selects the right wheel index; uses DirectML (torch-directml) for AMD GPUs; falls back to CPU-only wheels.",
    "install_ml_base":   "Installs the core scientific Python stack via pip: numpy, pandas, matplotlib, scikit-learn, jupyter, ipython.",
}

# Rust toolchain is non-catalog (rustup); keep this in lockstep with
# ``core.languages._wants_rust`` so the GUI info row matches installer behaviour.
# Toggleable via the "Skip Rust toolchain" switch (Install Options → --skip-rust).
PROFILE_RUSTUP_PROFILES: frozenset[str] = frozenset(
    {"ai-ml", "systems", "game-dev", "hardware-robotics"}
)


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------

def _entries_for_profile(profile_id: str) -> list[Any]:
    from core.install_catalog import WINGET_CATALOG
    return [e for e in WINGET_CATALOG if e.profiles and profile_id in e.profiles]


def _all_extras_entries() -> list[Any]:
    from core.install_catalog import WINGET_CATALOG
    return [e for e in WINGET_CATALOG if e.profiles and "extras" in e.profiles]


def _tools_for_profile(profile_id: str) -> list[str]:
    return [e.tool for e in _entries_for_profile(profile_id)]


def _needed_profiles_for(ui: dict[str, Any]) -> list[str]:
    from core.install_catalog import WINGET_CATALOG
    checked = {pid for pid in STANDARD_PROFILE_IDS if ui["profile_checks"][pid].value}
    desired = set(ui["desired_tools"])
    derived: set[str] = set()
    for entry in WINGET_CATALOG:
        if entry.tool not in desired or not entry.profiles:
            continue
        if entry.profiles & checked:
            continue
        for pref in PROFILE_PREFERENCE:
            if pref in entry.profiles:
                derived.add(pref)
                break
    return sorted(checked | derived)


def _exclusions_for(ui: dict[str, Any], needed_profiles: list[str]) -> list[str]:
    from core.install_catalog import WINGET_CATALOG
    desired = set(ui["desired_tools"])
    common_out = set(ui.get("common_opt_out") or ())
    sel = set(needed_profiles)
    excl: list[str] = []
    for e in WINGET_CATALOG:
        if e.profiles is None:
            # Common tool: excluded only if user explicitly opted out
            if e.tool in common_out:
                excl.append(e.tool)
        elif e.tool not in desired and e.applies_to(sel):
            excl.append(e.tool)
    return excl


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------

def _preview_context(ui: dict[str, Any], system_profile: dict[str, Any]) -> Any:
    from core.install_context import InstallContext
    needed = _needed_profiles_for(ui)
    exclusions = frozenset(_exclusions_for(ui, needed))
    wsl_default = None
    if ui["enable_wsl"].value and not ui["wsl_skip_distro"].value:
        wsl_default = (ui["wsl_distro"].value or "Ubuntu").strip() or "Ubuntu"
    sp = str(getattr(ui.get("sanitation_preset"), "value", "Minimal") or "Minimal").strip() or "Minimal"
    return InstallContext(
        repo_root=_REPO_ROOT,
        system_profile_path=_REPO_ROOT / "system-profile.json",
        system_profile=dict(system_profile),
        profiles=list(needed),
        dry_run=bool(ui["dry_run"].value),
        run_sanitation=bool(ui["run_sanitation"].value),
        sanitation_preset=sp,
        winutil_latest=bool(getattr(ui.get("winutil_latest"), "value", False)),
        skip_restore_point=bool(ui["skip_restore_point"].value),
        install_ml_wheels=bool(ui["install_ml_wheels"].value),
        manifest_path=_REPO_ROOT / "devkit-manifest.json",
        report_path=_REPO_ROOT / "post-install-report.html",
        enable_wsl=bool(ui["enable_wsl"].value),
        wsl_default_distro=wsl_default,
        install_ml_base=bool(ui["install_ml_base"].value),
        seed_dotfiles=not bool(ui["skip_dotfiles"].value),
        assume_yes=bool(ui["assume_yes"].value),
        skip_summary=bool(ui["skip_summary"].value),
        catalog_exclude_tools=exclusions,
        skip_rust=bool(ui["skip_rust"].value),
    )


def _argv_for_installer(ui: dict[str, Any]) -> list[str]:
    argv: list[str] = []
    if ui["dry_run"].value:
        argv.append("--dry-run")
    needed = _needed_profiles_for(ui)
    for pid in needed:
        argv.extend(["--profile", pid])
    for tool in sorted(_exclusions_for(ui, needed)):
        argv.extend(["--exclude-catalog-tool", tool])
    if ui["run_sanitation"].value:
        argv.append("--run-sanitation")
        sp = str(getattr(ui.get("sanitation_preset"), "value", "Minimal") or "Minimal").strip() or "Minimal"
        argv.extend(["--sanitation-preset", sp])
        if bool(getattr(ui.get("winutil_latest"), "value", False)):
            argv.append("--winutil-latest")
    if ui["skip_restore_point"].value:
        argv.append("--skip-restore-point")
    if ui["install_ml_wheels"].value:
        argv.append("--install-ml-wheels")
    if ui["install_ml_base"].value:
        argv.append("--install-ml-base")
    if ui["enable_wsl"].value:
        argv.append("--enable-wsl")
        if ui["wsl_skip_distro"].value:
            argv.append("--wsl-skip-default-distro")
        else:
            argv.extend(["--wsl-distro", (ui["wsl_distro"].value or "Ubuntu").strip() or "Ubuntu"])
    if ui["skip_dotfiles"].value:
        argv.append("--skip-dotfiles")
    if ui["skip_rust"].value:
        argv.append("--skip-rust")
    if ui["assume_yes"].value:
        argv.append("--yes")
    if ui["skip_summary"].value:
        argv.append("--skip-summary")
    return argv


def _quote_ps_arg(s: str) -> str:
    if not s:
        return "''"
    if all(c.isalnum() or c in "-_./:" for c in s):
        return s
    return "'" + s.replace("'", "''") + "'"


def _format_cli_line(argv: list[str]) -> str:
    return "python -m core.installer " + " ".join(_quote_ps_arg(a) for a in argv)


# ---------------------------------------------------------------------------
# Main GUI
# ---------------------------------------------------------------------------

def main_gui() -> None:
    import flet as ft

    desired_tools: set[str] = set()
    profile_checks: dict[str, ft.Checkbox] = {}
    # All rendered Checkbox instances for each tool (shared across profile sections)
    tool_cb_instances: dict[str, list[ft.Checkbox]] = {}
    # Common catalog tools (profiles=None) the user has opted OUT of
    common_opt_out: set[str] = set()
    common_cb_instances: dict[str, list[ft.Checkbox]] = {}
    # Detected installed state (populated by background scan)
    installed_state: dict[str, bool] = {}

    def main(page: ft.Page) -> None:
        page.title = "Absentmind's DevKit"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 16
        page.window.width = 960
        page.window.height = 960

        # ------------------------------------------------------------------
        # Switches / dropdowns for Install Options (defined early so other
        # handlers can read / write .value before the tab is rendered).
        # ------------------------------------------------------------------
        dry_run         = ft.Switch(label="Dry run (no destructive writes)", value=True)
        run_sanitation  = ft.Switch(label="Run Windows sanitation (CTT WinUtil — optional, disruptive)", value=False)
        sanitation_radios_col = ft.Column([], spacing=0)
        sanitation_preset_rg = ft.RadioGroup(value="Minimal", content=sanitation_radios_col)
        sanitation_load_text = ft.Text(
            "Loading WinUtil presets…",
            size=12, italic=True, color=ft.Colors.ON_SURFACE_VARIANT,
        )
        sanitation_source_text = ft.Text(
            "CTT WinUtil — pinned release, hash-verified.",
            size=11, italic=True, color=ft.Colors.ON_SURFACE_VARIANT,
        )
        winutil_latest_sw = ft.Switch(
            label="Use latest WinUtil (unpinned — no integrity check)",
            value=False,
        )
        winutil_latest_warning = ft.Container(
            content=ft.Text(
                "Caution: unpinned mode downloads and executes the live CTT script "
                "from christitus.com without a SHA256 check. Default (pinned, hash-verified) is safer.",
                size=11, italic=True, color=ft.Colors.AMBER,
            ),
            visible=False,
            padding=ft.padding.only(left=8, top=2, bottom=2),
        )
        sanitation_presets_section = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text("WinUtil tweak preset", weight=ft.FontWeight.W_500, size=13),
                    sanitation_load_text,
                ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                sanitation_preset_rg,
                sanitation_source_text,
                winutil_latest_sw,
                winutil_latest_warning,
            ], spacing=6),
            visible=False,
            padding=ft.padding.only(left=8, top=6, bottom=4),
        )
        skip_rp       = ft.Switch(label="Skip system restore point", value=False)
        skip_dotfiles = ft.Switch(label="Skip dotfile seeding", value=False)
        skip_rust     = ft.Switch(
            label="Skip Rust toolchain (rustup) install",
            value=False,
            tooltip="Do not install rustup or the stable Rust toolchain, even for systems / game-dev / hardware / AI-ML profiles.",
        )
        assume_yes    = ft.Switch(label="Assume yes / non-interactive (-y)", value=True)
        skip_summary  = ft.Switch(label="Skip pre-install summary panel", value=False)
        ml_wheels     = ft.Switch(label="Install PyTorch wheels (when AI/ML applies)", value=True)
        ml_base       = ft.Switch(label="Install core ML pip stack (numpy, pandas, … when AI/ML applies)", value=True)
        enable_wsl    = ft.Switch(
            label="Enable WSL (DISM; may require reboot)",
            value=False,
            tooltip=(
                "Runs DISM to enable Microsoft-Windows-Subsystem-Linux + VirtualMachinePlatform. "
                "First-time enable on a fresh machine almost always returns exit 3010 (REBOOT REQUIRED). "
                "If that happens, the installer skips `wsl --install -d <distro>` with a clear message — "
                "reboot Windows, then re-run this installer with the same flags to resume."
            ),
        )
        wsl_distro    = ft.TextField(label="WSL distro name", value="Ubuntu", width=280)
        wsl_skip      = ft.Switch(label="Skip default distro install (DISM only)", value=False)
        reuse_layer0  = ft.Switch(label="Reuse system profile from file (skip WMI scan)", value=False)
        reuse_layer0_path = ft.TextField(
            label="Path to system-profile.json",
            value=str((_REPO_ROOT / "system-profile.json").resolve()),
            expand=True,
        )

        ui: dict[str, Any] = {
            "profile_checks":    profile_checks,
            "desired_tools":     desired_tools,
            "common_opt_out":    common_opt_out,
            "dry_run":           dry_run,
            "run_sanitation":    run_sanitation,
            "sanitation_preset": sanitation_preset_rg,
            "winutil_latest":    winutil_latest_sw,
            "skip_restore_point": skip_rp,
            "skip_dotfiles":     skip_dotfiles,
            "skip_rust":         skip_rust,
            "assume_yes":        assume_yes,
            "skip_summary":      skip_summary,
            "install_ml_wheels": ml_wheels,
            "install_ml_base":   ml_base,
            "enable_wsl":        enable_wsl,
            "wsl_distro":        wsl_distro,
            "wsl_skip_distro":   wsl_skip,
            "reuse_layer0":      reuse_layer0,
            "reuse_layer0_path": reuse_layer0_path,
        }

        # ------------------------------------------------------------------
        # Layer 0 profile (disk)
        # ------------------------------------------------------------------
        layer0_profile: dict[str, Any] = {}

        def load_layer0_from_disk() -> None:
            layer0_profile.clear()
            path = _REPO_ROOT / "system-profile.json"
            if path.is_file():
                try:
                    layer0_profile.update(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    pass

        # ------------------------------------------------------------------
        # Scan status indicator
        # ------------------------------------------------------------------
        scan_status = ft.Text("", size=12, italic=True, color=ft.Colors.ON_SURFACE_VARIANT)

        # ------------------------------------------------------------------
        # Preview / summary fields
        # ------------------------------------------------------------------
        preview_field = ft.TextField(
            label="Equivalent command (run from repo root)",
            read_only=True, multiline=True, min_lines=2, max_lines=6, text_size=12,
        )
        summary_field = ft.TextField(
            label="Pre-install summary", read_only=True,
            multiline=True, min_lines=14, max_lines=24, text_size=12,
        )

        # ------------------------------------------------------------------
        # Count display
        # ------------------------------------------------------------------
        count_text      = ft.Text("", size=13, italic=True)
        bar_count_text  = ft.Text("", size=13, weight=ft.FontWeight.W_500)

        def _count_feature_picks() -> int:
            n = 0
            if ml_wheels.value:
                n += 1
            if ml_base.value:
                n += 1
            return n

        def update_count() -> None:
            from core.install_catalog import WINGET_CATALOG as _CAT
            common_selected = sum(
                1 for e in _CAT if e.profiles is None and e.tool not in common_opt_out
            )
            picked   = len(desired_tools) + _count_feature_picks() + common_selected
            core_n   = len(CORE_ITEMS) + FOUNDATION_ALWAYS_COUNT
            total    = picked + core_n
            tword    = "tool" if picked == 1 else "tools"
            bar_count_text.value  = f"{picked} {tword} selected · ~{total} total installs this run"
            count_text.value      = (
                f"{picked} {tword} selected  (+{core_n} core always install)  ·  ~{total} total."
            )
            try:
                bar_count_text.update()
                count_text.update()
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Sync preview / summary
        # ------------------------------------------------------------------
        def sync_previews() -> None:
            try:
                from core.pre_install_summary import format_pre_install_summary_text
                preview_field.value  = _format_cli_line(_argv_for_installer(ui))
                summary_field.value  = format_pre_install_summary_text(_preview_context(ui, layer0_profile))
                preview_field.update()
                summary_field.update()
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Info dialog (shared, reused)
        # ------------------------------------------------------------------
        dlg_title   = ft.Text("", weight=ft.FontWeight.BOLD, size=16)
        dlg_body    = ft.Column([], tight=True, spacing=4, scroll=ft.ScrollMode.AUTO)

        def close_dlg(_: ft.ControlEvent | None = None) -> None:
            info_dlg.open = False
            page.update()

        info_dlg = ft.AlertDialog(
            modal=True,
            title=dlg_title,
            content=ft.Container(content=dlg_body, width=540, height=440),
            actions=[ft.TextButton("Close", on_click=close_dlg)],
        )

        def open_profile_info(pid: str) -> None:
            dlg_title.value = f"{PROFILE_DISPLAY.get(pid, pid)} — what installs"
            dlg_body.controls.clear()
            if pid == "custom":
                dlg_body.controls.append(ft.Text(
                    "Custom is a view toggle — it exposes every stack's tools so you can "
                    "cherry-pick without enabling a whole profile.",
                    size=12,
                ))
            else:
                entries = _entries_for_profile(pid)
                dlg_body.controls.append(ft.Text(
                    PROFILE_HINTS.get(pid, ""), size=12, italic=True
                ))
                if entries:
                    dlg_body.controls.append(ft.Divider())
                    dlg_body.controls.append(ft.Text(
                        f"Catalog tools ({len(entries)}):", weight=ft.FontWeight.BOLD, size=13
                    ))
                    for e in entries:
                        dlg_body.controls.append(ft.Text(
                            f"  • {e.tool}  ({e.layer})  —  {e.winget_id}", size=12
                        ))
                feats = PROFILE_FEATURE_ITEMS.get(pid, ())
                if feats:
                    dlg_body.controls.append(ft.Divider())
                    dlg_body.controls.append(ft.Text("Optional extras (checkboxes):", size=13))
                    for name, desc, _flag, _key in feats:
                        dlg_body.controls.append(ft.Text(f"  • {name} — {desc}", size=12))
                if pid in PROFILE_RUSTUP_PROFILES:
                    dlg_body.controls.append(ft.Divider())
                    dlg_body.controls.append(ft.Text(
                        "Rust toolchain (rustup) — installs with this profile by default. "
                        "Toggle 'Skip Rust toolchain' under Install Options to opt out.",
                        size=12,
                    ))
            if info_dlg not in page.overlay:
                page.overlay.append(info_dlg)
            info_dlg.open = True
            page.update()

        def make_info_btn(pid: str) -> ft.IconButton:
            return ft.IconButton(
                icon=ft.Icons.INFO_OUTLINE,
                tooltip=f"What installs with {PROFILE_DISPLAY.get(pid, pid)}",
                icon_size=18,
                on_click=lambda _e, p=pid: open_profile_info(p),
            )

        # ------------------------------------------------------------------
        # Tool checkbox helpers
        # ------------------------------------------------------------------

        def _installed_suffix(tool: str) -> str:
            if installed_state.get(tool):
                return "  ✓ already installed"
            return ""

        def _make_tool_label(entry: Any) -> str:
            return f"{entry.tool}  ({entry.layer}){_installed_suffix(entry.tool)}"

        def _sync_all_header_states() -> None:
            """Sync all profile headers and absentmind_cb after any tool toggle."""
            for pid in STANDARD_PROFILE_IDS:
                hdr = profile_checks.get(pid)
                if hdr is None or not hdr.value:
                    continue
                all_tools = set(_tools_for_profile(pid))
                feat_keys = {k for _n, _d, _f, k in PROFILE_FEATURE_ITEMS.get(pid, ())}
                fully_selected = all_tools.issubset(desired_tools) and all(
                    bool(ui[k].value) for k in feat_keys
                )
                if not fully_selected:
                    hdr.value = False
                    # Auto-check Custom when a profile becomes partial
                    custom_cb = profile_checks.get("custom")
                    if custom_cb and not custom_cb.value:
                        custom_cb.value = True
            # Uncheck absentmind_cb if any standard profile is no longer fully checked
            if absentmind_cb.value:
                all_profiles_on = all(
                    pid in profile_checks and bool(profile_checks[pid].value)
                    for pid in STANDARD_PROFILE_IDS
                )
                if not all_profiles_on:
                    absentmind_cb.value = False

        def on_tool_toggle(tool: str, is_checked: bool, source_pid: str | None = None) -> None:
            if is_checked:
                desired_tools.add(tool)
            else:
                desired_tools.discard(tool)
            # Sync every other Checkbox instance for this tool (no individual .update())
            for cb in tool_cb_instances.get(tool, []):
                try:
                    if cb.value != is_checked:
                        cb.value = is_checked
                except Exception:
                    pass
            # Sync all profile headers and absentmind checkbox, then batch-redraw
            _sync_all_header_states()
            update_count()
            sync_previews()
            page.update()

        def make_tool_checkbox(entry: Any, pid_context: str) -> ft.Checkbox:
            cb = ft.Checkbox(
                label=_make_tool_label(entry),
                value=entry.tool in desired_tools,
                tooltip=TOOL_TOOLTIPS.get(entry.tool, ""),
            )

            def _handler(e: ft.ControlEvent) -> None:
                on_tool_toggle(entry.tool, bool(e.control.value), pid_context)

            cb.on_change = _handler
            tool_cb_instances.setdefault(entry.tool, []).append(cb)
            return cb

        # Feature checkboxes (PyTorch wheels, ML pip base) — wired to Switches.
        feature_cb_instances: dict[str, list[ft.Checkbox]] = {}

        def make_feature_checkbox(name: str, desc: str, ui_key: str) -> ft.Checkbox:
            src = ui[ui_key]
            cb = ft.Checkbox(
                label=f"{name}  —  {desc}",
                value=bool(src.value),
                tooltip=TOOL_TOOLTIPS.get(ui_key, desc),
            )

            def _handler(e: ft.ControlEvent) -> None:
                val = bool(e.control.value)
                src.value = val
                try:
                    src.update()
                except Exception:
                    pass
                for other in feature_cb_instances.get(ui_key, []):
                    try:
                        if other is not cb and other.value != val:
                            other.value = val
                            other.update()
                    except Exception:
                        pass
                update_count()
                sync_previews()

            cb.on_change = _handler
            feature_cb_instances.setdefault(ui_key, []).append(cb)
            return cb

        def make_common_tool_checkbox(entry: Any) -> ft.Checkbox:
            """Checkbox for a common catalog tool (profiles=None) — pre-checked, opt-out."""
            cb = ft.Checkbox(
                label=_make_tool_label(entry),
                value=entry.tool not in common_opt_out,
                tooltip=TOOL_TOOLTIPS.get(entry.tool, ""),
            )

            def _handler(e: ft.ControlEvent) -> None:
                val = bool(e.control.value)
                if val:
                    common_opt_out.discard(entry.tool)
                else:
                    common_opt_out.add(entry.tool)
                for other in common_cb_instances.get(entry.tool, []):
                    try:
                        if other is not e.control and other.value != val:
                            other.value = val
                    except Exception:
                        pass
                update_count()
                sync_previews()
                page.update()

            cb.on_change = _handler
            common_cb_instances.setdefault(entry.tool, []).append(cb)
            return cb

        # ------------------------------------------------------------------
        # Profile section builder
        # ------------------------------------------------------------------

        def build_profile_section(pid: str) -> list[ft.Control]:
            """Return the list of controls for one profile block."""
            controls: list[ft.Control] = []
            entries = _entries_for_profile(pid)
            feats   = PROFILE_FEATURE_ITEMS.get(pid, ())

            for entry in entries:
                cb = make_tool_checkbox(entry, pid)
                controls.append(ft.Container(content=cb, padding=ft.padding.only(left=24)))

            if feats:
                controls.append(ft.Container(
                    content=ft.Text("Also runs with this profile:", size=12, italic=True,
                                    color=ft.Colors.ON_SURFACE_VARIANT),
                    padding=ft.padding.only(left=24, top=4),
                ))
                for name, desc, _flag, ui_key in feats:
                    feat_cb = make_feature_checkbox(name, desc, ui_key)
                    controls.append(ft.Container(content=feat_cb, padding=ft.padding.only(left=24)))

            if pid in PROFILE_RUSTUP_PROFILES:
                controls.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.INFO_OUTLINE, size=14,
                                 color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(
                            "Rust toolchain (via rustup) — installs with this profile unless "
                            "'Skip Rust toolchain' is enabled under Install Options.",
                            size=12, italic=True, color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                    ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=ft.padding.only(left=24, top=2),
                ))

            return controls

        # ------------------------------------------------------------------
        # Main profiles column (rebuilt when profile selections change)
        # ------------------------------------------------------------------
        profiles_col = ft.Column(controls=[], spacing=0, scroll=ft.ScrollMode.AUTO, expand=True)
        # Per-profile expandable sub-columns: pid -> Column
        profile_sub_cols: dict[str, ft.Column] = {}

        def rebuild_profiles_col() -> None:
            profiles_col.controls.clear()
            tool_cb_instances.clear()
            feature_cb_instances.clear()
            common_cb_instances.clear()

            custom_mode = bool(profile_checks.get("custom", ft.Checkbox()).value)
            active_pids = {pid for pid in STANDARD_PROFILE_IDS if profile_checks.get(pid, ft.Checkbox()).value}
            for pid, _label in PROFILE_DEFS:
                cb = profile_checks[pid]
                # Header row: checkbox (acts as select-all) + info button
                header = ft.Row(
                    [
                        cb,
                        make_info_btn(pid),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
                profiles_col.controls.append(header)

                # Tool sub-list (only for non-custom profiles that are visible)
                if pid != "custom":
                    sub_controls = (
                        build_profile_section(pid)
                        if (custom_mode or pid in active_pids)
                        else []
                    )
                    sub_col = ft.Column(controls=sub_controls, spacing=2)
                    profile_sub_cols[pid] = sub_col
                    profiles_col.controls.append(sub_col)

            profiles_col.controls.append(ft.Divider())

            # Core section
            profiles_col.controls.append(ft.Text(
                "Core (always installed)", weight=ft.FontWeight.BOLD, size=15
            ))
            # Required items — truly locked (Python 3 + flet/rich)
            for name, _desc, _state in CORE_ITEMS:
                profiles_col.controls.append(
                    ft.Checkbox(
                        label=f"{name}  (required — already installed)",
                        value=True, disabled=True,
                    )
                )
            # Foundation note — collapsed to one info line
            profiles_col.controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.INFO_OUTLINE, size=14, color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(
                        "Foundation (always installs): Git, Git LFS, GitHub CLI, "
                        "Windows Terminal, PowerShell 7, OpenSSH, uv, pyenv-win, "
                        "Scoop + CLI suite, Oh My Posh, Tailscale, "
                        "restore point, dotfiles — no skip toggles yet.",
                        size=12, italic=True, color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ], spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.padding.only(top=4, bottom=4),
            ))
            # Common catalog tools — pre-selected, user can uncheck to skip
            profiles_col.controls.append(ft.Container(
                content=ft.Text(
                    "Common tools (pre-selected — uncheck any to skip):",
                    size=13, weight=ft.FontWeight.W_500,
                ),
                padding=ft.padding.only(top=6, bottom=2),
            ))
            from core.install_catalog import WINGET_CATALOG as _WC
            for _entry in (e for e in _WC if e.profiles is None):
                _cb = make_common_tool_checkbox(_entry)
                profiles_col.controls.append(
                    ft.Container(content=_cb, padding=ft.padding.only(left=8))
                )

            profiles_col.controls.append(ft.Divider())

            # Extras section
            extras = _all_extras_entries()
            if extras:
                profiles_col.controls.append(ft.Row(
                    [
                        ft.Text("Extras (personal-preference apps)",
                                weight=ft.FontWeight.BOLD, size=15),
                        ft.Row([
                            ft.OutlinedButton("Select all extras", on_click=select_all_extras),
                            ft.OutlinedButton("Clear all extras", on_click=clear_all_extras),
                        ], spacing=8),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ))
                profiles_col.controls.append(ft.Text(
                    "All opt-in. Nothing here pre-checked.", size=12, italic=True
                ))
                for entry in extras:
                    cb2 = make_tool_checkbox(entry, "extras")
                    profiles_col.controls.append(cb2)

            try:
                profiles_col.update()
            except Exception:
                pass

        # ------------------------------------------------------------------
        # Profile checkbox wiring
        # ------------------------------------------------------------------
        for pid, title in PROFILE_DEFS:
            profile_checks[pid] = ft.Checkbox(label=f"{title}  (select all)", value=False)

        def wire_profile_cb(pid: str) -> None:
            def _handler(e: ft.ControlEvent) -> None:
                checked = bool(e.control.value)
                if pid == "custom":
                    # Custom is a view toggle only — rebuild to show/hide sections
                    rebuild_profiles_col()
                    update_count()
                    sync_previews()
                    return
                # Bulk-select / deselect all catalog tools for this profile
                for tool in _tools_for_profile(pid):
                    if checked:
                        desired_tools.add(tool)
                    else:
                        desired_tools.discard(tool)
                # Bulk-toggle feature items
                for _name, _desc, _flag, ui_key in PROFILE_FEATURE_ITEMS.get(pid, ()):
                    ui[ui_key].value = checked
                    try:
                        ui[ui_key].update()
                    except Exception:
                        pass
                rebuild_profiles_col()
                update_count()
                sync_previews()

            profile_checks[pid].on_change = _handler

        for pid, _ in PROFILE_DEFS:
            wire_profile_cb(pid)

        # Absentmind Mode
        absentmind_cb = ft.Checkbox(
            label="Absentmind Mode — select all profiles (AI, Web, Systems, Game, Hardware).",
            value=False,
        )

        def on_absentmind(_e: ft.ControlEvent | None = None) -> None:
            if absentmind_cb.value:
                for pid in STANDARD_PROFILE_IDS:
                    if not profile_checks[pid].value:
                        profile_checks[pid].value = True
                        for tool in _tools_for_profile(pid):
                            desired_tools.add(tool)
                    # Also activate every feature item for this profile
                    # (PyTorch wheels, ML pip base, etc.)  — Absentmind = everything.
                    for _name, _desc, _flag, ui_key in PROFILE_FEATURE_ITEMS.get(pid, ()):
                        if ui_key in ui:
                            ui[ui_key].value = True
                rebuild_profiles_col()
                update_count()
                sync_previews()

        absentmind_cb.on_change = on_absentmind

        # Extras helpers
        def select_all_extras(_: ft.ControlEvent | None = None) -> None:
            for entry in _all_extras_entries():
                desired_tools.add(entry.tool)
                for cb in tool_cb_instances.get(entry.tool, []):
                    try:
                        cb.value = True
                    except Exception:
                        pass
            update_count()
            sync_previews()
            page.update()

        def clear_all_extras(_: ft.ControlEvent | None = None) -> None:
            for entry in _all_extras_entries():
                desired_tools.discard(entry.tool)
                for cb in tool_cb_instances.get(entry.tool, []):
                    try:
                        cb.value = False
                    except Exception:
                        pass
            update_count()
            sync_previews()
            page.update()

        def clear_all(_: ft.ControlEvent | None = None) -> None:
            desired_tools.clear()
            for cbs in tool_cb_instances.values():
                for cb in cbs:
                    try:
                        cb.value = False
                    except Exception:
                        pass
            for pid in STANDARD_PROFILE_IDS:
                profile_checks[pid].value = False
            absentmind_cb.value = False
            ml_wheels.value = False
            ml_base.value   = False
            update_count()
            sync_previews()
            page.update()

        # ------------------------------------------------------------------
        # ML switch sync: flipping Install Options switch updates feature cbs
        # ------------------------------------------------------------------
        def make_ml_switch_handler(ui_key: str):
            def _h(e: ft.ControlEvent) -> None:
                val = bool(e.control.value)
                for cb in feature_cb_instances.get(ui_key, []):
                    try:
                        cb.value = val
                        cb.update()
                    except Exception:
                        pass
                update_count()
                sync_previews()
            return _h

        ml_wheels.on_change = make_ml_switch_handler("install_ml_wheels")
        ml_base.on_change   = make_ml_switch_handler("install_ml_base")

        # ------------------------------------------------------------------
        # Other switch handlers
        # ------------------------------------------------------------------
        def bind_switch(_: ft.ControlEvent | None = None) -> None:
            sync_previews()

        def on_sanitation_change(e: ft.ControlEvent) -> None:
            sanitation_presets_section.visible = bool(e.control.value)
            sanitation_presets_section.update()
            sync_previews()

        run_sanitation.on_change = on_sanitation_change
        for sw in (dry_run, skip_rp, skip_dotfiles, skip_rust, assume_yes, skip_summary, enable_wsl, wsl_skip):
            sw.on_change = bind_switch
        sanitation_preset_rg.on_change = bind_switch

        def on_winutil_latest_change(e: ft.ControlEvent) -> None:
            winutil_latest_warning.visible = bool(e.control.value)
            try:
                winutil_latest_warning.update()
            except Exception:
                pass
            threading.Thread(target=_load_presets_thread, daemon=True).start()
            sync_previews()

        winutil_latest_sw.on_change = on_winutil_latest_change
        wsl_distro.on_change = bind_switch

        def on_reuse_change(e: ft.ControlEvent) -> None:
            reuse_layer0_path.disabled = not bool(e.control.value)
            if e.control.value:
                load_layer0_from_disk()
            reuse_layer0_path.update()
            sync_previews()

        reuse_layer0.on_change = on_reuse_change
        reuse_layer0_path.disabled = not reuse_layer0.value
        reuse_layer0_path.on_change = bind_switch

        # ------------------------------------------------------------------
        # SnackBar
        # ------------------------------------------------------------------
        snack = ft.SnackBar(content=ft.Text(""), open=False)

        def show_snack(msg: str) -> None:
            snack.content = ft.Text(msg)
            snack.open = True
            page.update()

        # ------------------------------------------------------------------
        # System scan (manual + auto on startup)
        # ------------------------------------------------------------------
        def _run_scan_subprocess() -> bool:
            scan_script = _REPO_ROOT / "core" / "system_scan.py"
            out_path    = _REPO_ROOT / "system-profile.json"
            try:
                proc = subprocess.run(
                    [sys.executable, str(scan_script), "--output", str(out_path)],
                    cwd=str(_REPO_ROOT), capture_output=True, text=True,
                    encoding="utf-8", errors="replace", timeout=300.0,
                )
                return proc.returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                return False

        def _detect_installed_tools() -> None:
            """Run detectors for every catalog entry; store in installed_state."""
            from core.install_catalog import WINGET_CATALOG, get_detector
            for entry in WINGET_CATALOG:
                try:
                    installed_state[entry.tool] = get_detector(entry)()
                except Exception:
                    installed_state[entry.tool] = False

        def _refresh_tool_labels() -> None:
            """Update checkbox labels to show '✓ already installed' where detected."""
            from core.install_catalog import WINGET_CATALOG
            for entry in WINGET_CATALOG:
                label = _make_tool_label(entry)
                for cb in tool_cb_instances.get(entry.tool, []):
                    try:
                        cb.label = label
                    except Exception:
                        pass
                for cb in common_cb_instances.get(entry.tool, []):
                    try:
                        cb.label = label
                    except Exception:
                        pass

        def _auto_scan_thread() -> None:
            scan_status.value = "Scanning system… (this may take a moment)"
            try:
                scan_status.update()
            except Exception:
                pass
            ok = _run_scan_subprocess()
            _detect_installed_tools()
            load_layer0_from_disk()
            _refresh_tool_labels()
            update_count()
            sync_previews()
            scan_status.value = (
                "System scan complete." if ok else "System scan had errors — disk/time estimates may be approximate."
            )
            try:
                scan_status.update()
                page.update()
            except Exception:
                pass

        def _load_presets_thread() -> None:
            try:
                from core.winutil_pin import WINUTIL_TAG
                from core.winutil_presets import fallback_presets, fetch_presets
                latest = bool(winutil_latest_sw.value)
                sanitation_load_text.value = "Loading WinUtil presets…"
                try:
                    sanitation_load_text.update()
                except Exception:
                    pass
                try:
                    presets = fetch_presets(latest=latest, timeout=30.0)
                    source_note = (
                        "CTT WinUtil — live main branch (unpinned, no integrity check)."
                        if latest
                        else f"CTT WinUtil — pinned release {WINUTIL_TAG}, hash-verified."
                    )
                except Exception:
                    presets = fallback_presets()
                    source_note = (
                        "CTT WinUtil — offline fallback (network unavailable). "
                        "Install may fail if still offline at run time."
                    )
                controls: list[ft.Control] = []
                for p in presets:
                    controls.append(ft.Radio(value=p.key, label=p.key))
                    controls.append(ft.Container(
                        content=ft.Text(
                            p.description, size=11, italic=True,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        ),
                        padding=ft.padding.only(left=32, bottom=6),
                    ))
                sanitation_radios_col.controls = controls
                keys = {p.key for p in presets}
                if sanitation_preset_rg.value not in keys:
                    sanitation_preset_rg.value = presets[0].key if presets else "Minimal"
                sanitation_load_text.value = ""
                sanitation_source_text.value = source_note
                try:
                    sanitation_presets_section.update()
                except Exception:
                    pass
            except Exception as exc:
                sanitation_load_text.value = f"Could not load presets: {exc}"
                try:
                    sanitation_load_text.update()
                except Exception:
                    pass

        def run_system_scan_manual(_: ft.ControlEvent) -> None:
            scan_status.value = "Running scan…"
            try:
                scan_status.update()
            except Exception:
                pass
            threading.Thread(target=_auto_scan_thread, daemon=True).start()

        # ------------------------------------------------------------------
        # Start installer
        # ------------------------------------------------------------------
        def run_installer(_: ft.ControlEvent) -> None:
            sync_previews()
            # Block only if truly nothing would install (common tools count as selected)
            from core.install_catalog import WINGET_CATALOG as _gc
            _common_n = sum(1 for e in _gc if e.profiles is None and e.tool not in common_opt_out)
            if not desired_tools and _common_n == 0 and not ml_wheels.value and not ml_base.value:
                show_snack("No tools selected. Tick a profile or cherry-pick tools before installing.")
                return
            args = _argv_for_installer(ui)
            creation = 0
            if sys.platform == "win32":
                creation = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
            try:
                if sys.platform == "win32":
                    # Wrap in PowerShell so the console stays open after the
                    # installer finishes and the user can read the full output.
                    py = sys.executable.replace("'", "''")
                    installer_cmd = " ".join(
                        [f"& '{py}'", "-m", "core.installer"] +
                        [f'"{a}"' if " " in a else a for a in args]
                    )
                    ps_cmd = (
                        f"{installer_cmd}; "
                        f"Write-Host ''; "
                        f"Write-Host ('=' * 70) -ForegroundColor DarkGray; "
                        f"Write-Host 'Install finished. Review output above, then close this window.' "
                        f"-ForegroundColor Green; "
                        f"Read-Host 'Press Enter to close'"
                    )
                    subprocess.Popen(
                        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
                        cwd=str(_REPO_ROOT), creationflags=creation,
                    )
                else:
                    subprocess.Popen(
                        [sys.executable, "-m", "core.installer", *args],
                        cwd=str(_REPO_ROOT), creationflags=creation,
                    )
                show_snack("Installer started in a new console window.")
            except OSError as exc:
                show_snack(f"Could not start installer: {exc}")

        def copy_command(_: ft.ControlEvent) -> None:
            sync_previews()
            page.set_clipboard(preview_field.value or "")
            show_snack("Copied installer command to clipboard.")

        def copy_summary(_: ft.ControlEvent) -> None:
            sync_previews()
            page.set_clipboard(summary_field.value or "")
            show_snack("Copied pre-install summary to clipboard.")

        # ------------------------------------------------------------------
        # Start button + bar
        # ------------------------------------------------------------------
        start_btn = ft.FilledButton(
            "▶  START INSTALL",
            on_click=run_installer,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=24, vertical=16),
                bgcolor=ft.Colors.GREEN_700,
                color=ft.Colors.WHITE,
            ),
        )
        start_bar = ft.Container(
            content=ft.Row(
                [bar_count_text, start_btn],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=10),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.GREEN),
        )

        # ------------------------------------------------------------------
        # Build tabs
        # ------------------------------------------------------------------
        summary_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Pre-install summary", weight=ft.FontWeight.BOLD, size=18),
                    scan_status,
                    ft.Row([
                        ft.FilledButton("Run system scan", on_click=run_system_scan_manual),
                        ft.OutlinedButton("Copy summary", on_click=copy_summary),
                    ], spacing=16, wrap=True),
                    summary_field,
                ],
                spacing=12, expand=True, scroll=ft.ScrollMode.AUTO,
            ),
            padding=16, expand=True,
        )

        profiles_tools_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    ft.Text("Profiles & Tools", weight=ft.FontWeight.BOLD, size=18),
                                    ft.Text(
                                        "Check a profile to select all its tools. "
                                        "Uncheck individual tools to customize. "
                                        "Enable 'Custom' to see every stack.",
                                        size=12, italic=True,
                                    ),
                                ],
                                spacing=2, expand=True,
                            ),
                            ft.OutlinedButton("Clear all", on_click=clear_all),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    absentmind_cb,
                    count_text,
                    profiles_col,
                ],
                spacing=8, expand=True,
            ),
            padding=16, expand=True,
        )

        options_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Install options", weight=ft.FontWeight.BOLD, size=18),
                    dry_run, run_sanitation, sanitation_presets_section,
                    skip_rp, skip_dotfiles, skip_rust, assume_yes, skip_summary,
                    ft.Divider(),
                    ml_wheels, ml_base,
                    ft.Divider(),
                    enable_wsl, wsl_distro, wsl_skip,
                    ft.Divider(),
                    reuse_layer0, reuse_layer0_path,
                ],
                spacing=4, scroll=ft.ScrollMode.AUTO, expand=True,
            ),
            padding=16, expand=True,
        )

        # ------------------------------------------------------------------
        # Results tab: display the most recent dry-run / post-install manifest
        # ------------------------------------------------------------------
        results_display_col = ft.Column([], expand=True, scroll=ft.ScrollMode.AUTO)

        def _format_results_text() -> str:
            """Load and format the devkit-manifest.json if it exists."""
            manifest_path = _REPO_ROOT / "devkit-manifest.json"
            if not manifest_path.is_file():
                return "(No manifest found yet. Run --dry-run or START INSTALL to generate results.)"
            try:
                import json
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                lines = []
                lines.append(f"Generated: {data.get('generated_at', 'unknown')}")
                lines.append(f"DevKit version: {data.get('devkit_version', 'unknown')}")
                lines.append("")
                lines.append("Install status summary:")
                lines.append("-" * 70)

                _ALREADY_PRESENT_NOTES = (
                    "Already present on PATH or detector.",
                    "already on PATH.",
                    "already available.",
                    "Target exists:",
                )

                def _display_status(t: dict) -> str:
                    """Reclassify 'skipped' entries that are actually pre-installed."""
                    if t.get("status") == "skipped" and any(
                        marker in (t.get("notes") or "") for marker in _ALREADY_PRESENT_NOTES
                    ):
                        return "already_installed"
                    return t.get("status", "unknown")

                # Group by display status
                status_groups: dict[str, list] = {}
                for tool in data.get("tools", []):
                    ds = _display_status(tool)
                    status_groups.setdefault(ds, []).append(tool)

                _STATUS_META = [
                    ("installed",        "I", "INSTALLED"),
                    ("already_installed","A", "ALREADY INSTALLED"),
                    ("planned",          "P", "PLANNED (dry-run)"),
                    ("failed",           "F", "FAILED"),
                    ("skipped",          "S", "SKIPPED"),
                ]
                for status, letter, label in _STATUS_META:
                    if status not in status_groups:
                        continue
                    tools = status_groups[status]
                    lines.append(f"\n{label} ({len(tools)}):")
                    for tool in tools:
                        layer = tool.get("layer", "?")
                        method = tool.get("install_method", "?")
                        lines.append(f"  [{letter}] {tool['tool']:25s} ({layer:15s}) via {method}")

                lines.append("")
                lines.append("=" * 70)
                lines.append("For detailed results, see:")
                lines.append(f"  - {manifest_path}")
                lines.append(f"  - {_REPO_ROOT / 'post-install-report.html'}")
                lines.append("")
                lines.append("(Click 'Refresh results' after running --dry-run or START INSTALL)")

                return "\n".join(lines)
            except Exception as e:
                return f"Error loading manifest: {e}"

        def _load_results_from_disk() -> None:
            """Load results and repopulate the display."""
            results_display_col.controls.clear()
            text = _format_results_text()
            results_display_col.controls.append(
                ft.TextField(
                    value=text,
                    read_only=True,
                    multiline=True,
                    min_lines=20,
                    max_lines=40,
                    text_size=11,
                    expand=True,
                )
            )

        def _refresh_results(_: ft.ControlEvent | None = None) -> None:
            try:
                _load_results_from_disk()
                page.update()
            except Exception as e:
                snack.content.value = f"Error refreshing results: {e}"
                snack.open = True
                try:
                    page.update()
                except Exception:
                    pass

        def _open_html_report(_: ft.ControlEvent | None = None) -> None:
            """Open the HTML report in the default browser."""
            import os
            report_path = _REPO_ROOT / "post-install-report.html"
            if not report_path.is_file():
                snack.content.value = f"Report not found: {report_path}"
                snack.open = True
                page.update()
                return
            try:
                os.startfile(str(report_path))
            except Exception as e:
                snack.content.value = f"Error opening report: {e}"
                snack.open = True
                page.update()

        def _copy_results(_: ft.ControlEvent) -> None:
            page.set_clipboard(_format_results_text())
            show_snack("Results copied to clipboard.")

        results_tab_content = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Results", weight=ft.FontWeight.BOLD, size=18),
                    ft.Text(
                        "Most recent dry-run or post-install results. Refresh to reload.",
                        size=12, italic=True,
                    ),
                    ft.Row([
                        ft.OutlinedButton("Refresh results", on_click=_refresh_results),
                        ft.OutlinedButton("Copy results", on_click=_copy_results),
                    ], spacing=8),
                    results_display_col,
                    ft.OutlinedButton(
                        "Open full HTML report",
                        on_click=_open_html_report,
                    ),
                ],
                spacing=8, expand=True,
            ),
            padding=16, expand=True,
        )

        tabs = ft.Tabs(
            selected_index=1,
            expand=1,
            tabs=[
                ft.Tab(text="Summary",          content=summary_tab_content),
                ft.Tab(text="Profiles & Tools", content=profiles_tools_tab_content),
                ft.Tab(text="Install Options",  content=options_tab_content),
                ft.Tab(text="Results",          content=results_tab_content),
            ],
        )

        # ------------------------------------------------------------------
        # Page layout
        # ------------------------------------------------------------------
        page.add(
            ft.Column([
                ft.Text("Absentmind's DevKit", size=22, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "Developer toolkit installer — pick profiles, customize tools, then START INSTALL.",
                    size=13,
                ),
            ], spacing=2),
            ft.Text(
                "MIT license (this repo). WinUtil / Winget / pip packages have separate terms — "
                "see docs/THIRD_PARTY_NOTICES.md",
                size=11, color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            tabs,
            start_bar,
            preview_field,
            ft.Row([ft.OutlinedButton("Copy command", on_click=copy_command)], spacing=12),
            snack,
        )

        # ------------------------------------------------------------------
        # Initial state
        # ------------------------------------------------------------------
        load_layer0_from_disk()
        _load_results_from_disk()
        rebuild_profiles_col()
        update_count()
        sync_previews()

        # Auto-run the system scan in the background so tool detection
        # and disk/time estimates are ready as soon as possible.
        threading.Thread(target=_auto_scan_thread, daemon=True).start()
        threading.Thread(target=_load_presets_thread, daemon=True).start()

    ft.app(target=main)


if __name__ == "__main__":
    main_gui()
