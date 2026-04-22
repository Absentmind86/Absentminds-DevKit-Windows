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
    "ai-ml":             "GPU-aware PyTorch, Ollama, ML stack, Jupyter. Also installs Docker Desktop, kubectl, Helm.",
    "web-fullstack":     "Docker Desktop, kubectl, Helm, DBs, Bruno, cloud CLIs, Node (nvm), web toolchain.",
    "systems":           "kubectl, Helm, Rust (rustup), MSVC / C++, CMake, Wireshark, low-level infra.",
    "game-dev":          "Unity Hub, Godot, Rust (rustup), VS Build Tools, game-focused runtimes.",
    "hardware-robotics": "Arduino IDE, Rust (rustup), pyserial, serial/USB tooling, embedded workflow.",
    "custom":            "View-mode toggle — exposes every stack's tools so you can cherry-pick anything.",
}

PROFILE_DISPLAY: dict[str, str] = {pid: label for pid, label in PROFILE_DEFS}

# Non-catalog, non-winget features that map to installer flags.
# Rendered as real checkboxes under their profile section.
# format: (display_name, description, installer_flag, ui_key)
PROFILE_FEATURE_ITEMS: dict[str, tuple[tuple[str, str, str, str], ...]] = {
    "ai-ml": (
        ("PyTorch wheels", "GPU-matched CUDA or CPU fallback via pip", "--install-ml-wheels", "install_ml_wheels"),
        ("ML pip base",    "numpy, pandas, matplotlib, scikit-learn, jupyter, ipython", "--install-ml-base", "install_ml_base"),
    ),
}

# Always-installed core items (Layer 0-3 boot + common catalog + Scoop suite).
# True must-haves get the REQUIRED flag; everything else is HARDWIRED (installer
# layers don't have skip flags yet — future work).
CORE_ITEMS: tuple[tuple[str, str, str], ...] = (
    # (display_name, description, state)  state: "required" | "hardwired" | "optional"
    ("Python 3",              "runtime — already running the GUI",     "required"),
    ("flet, rich",            "GUI/CLI deps (pip) — already installed", "required"),
    ("Git",                   "version control (winget)",               "hardwired"),
    ("Git LFS",               "large-file support (winget)",            "hardwired"),
    ("GitHub CLI",            "gh command (winget)",                    "hardwired"),
    ("Windows Terminal",      "modern terminal (winget)",               "hardwired"),
    ("PowerShell 7",          "modern pwsh (winget)",                   "hardwired"),
    ("OpenSSH Client",        "ssh/scp (Windows capability)",           "hardwired"),
    ("VS Code",               "editor (winget)",                        "hardwired"),
    ("Cursor",                "AI-native editor (winget)",              "hardwired"),
    ("VS Code extensions",    "from config/vscode/extensions.json",     "hardwired"),
    ("uv",                    "fast Python package manager (winget)",   "hardwired"),
    ("pyenv-win",             "Python version manager (scoop)",         "hardwired"),
    ("Scoop",                 "CLI package manager",                    "hardwired"),
    ("Scoop CLI suite",       "bat, ripgrep, fd, fzf, jq, lazygit, delta", "hardwired"),
    ("Oh My Posh",            "prompt theming (winget)",                "hardwired"),
    ("Tailscale",             "zero-config VPN (winget)",               "hardwired"),
    ("Nerd Fonts",            "icons/glyphs for terminals",             "hardwired"),
    ("7-Zip",                 "archiver (common catalog, always)",       "hardwired"),
    ("Notepad++",             "editor (common catalog, always)",        "hardwired"),
    ("Everything",            "file search (common catalog, always)",   "hardwired"),
    ("DevToys",               "developer utilities (common catalog)",   "hardwired"),
    ("WinMerge",              "diff/merge (common catalog)",            "hardwired"),
    ("System restore point",  "pre-install safety (toggle: skip-restore-point)", "hardwired"),
    ("Dotfiles seed",         ".gitconfig / pwsh profile (toggle: skip-dotfiles)", "hardwired"),
)

# Rust toolchain is non-catalog (rustup) and non-toggleable today.
# Shown as info row under profiles that trigger it.
PROFILE_RUSTUP_PROFILES: frozenset[str] = frozenset(
    {"ai-ml", "web-fullstack", "systems", "game-dev", "hardware-robotics"}
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
    sel = set(needed_profiles)
    return [
        e.tool for e in WINGET_CATALOG
        if e.profiles is not None and e.tool not in desired and e.applies_to(sel)
    ]


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
    sp = str(getattr(ui.get("sanitation_preset"), "value", "minimal") or "minimal").strip().lower()
    if sp not in ("minimal", "standard"):
        sp = "minimal"
    return InstallContext(
        repo_root=_REPO_ROOT,
        system_profile_path=_REPO_ROOT / "system-profile.json",
        system_profile=dict(system_profile),
        profiles=list(needed),
        dry_run=bool(ui["dry_run"].value),
        run_sanitation=bool(ui["run_sanitation"].value),
        sanitation_preset=sp,
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
        sp = str(getattr(ui.get("sanitation_preset"), "value", "minimal") or "minimal").strip().lower()
        argv.extend(["--sanitation-preset", sp if sp in ("minimal", "standard") else "minimal"])
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
        sanitation_preset_dd = ft.Dropdown(
            label="WinUtil tweak preset",
            options=[ft.dropdown.Option("minimal"), ft.dropdown.Option("standard")],
            value="minimal", width=400, disabled=True,
            hint_text="minimal = 4 tweaks · standard = CTT preset.json Standard (13)",
        )
        skip_rp       = ft.Switch(label="Skip system restore point", value=False)
        skip_dotfiles = ft.Switch(label="Skip dotfile seeding", value=False)
        assume_yes    = ft.Switch(label="Assume yes / non-interactive (-y)", value=True)
        skip_summary  = ft.Switch(label="Skip pre-install summary panel", value=False)
        ml_wheels     = ft.Switch(label="Install PyTorch wheels (when AI/ML applies)", value=False)
        ml_base       = ft.Switch(label="Install core ML pip stack (numpy, pandas, … when AI/ML applies)", value=False)
        enable_wsl    = ft.Switch(label="Enable WSL (DISM; may require reboot)", value=False)
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
            "dry_run":           dry_run,
            "run_sanitation":    run_sanitation,
            "sanitation_preset": sanitation_preset_dd,
            "skip_restore_point": skip_rp,
            "skip_dotfiles":     skip_dotfiles,
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
            picked   = len(desired_tools) + _count_feature_picks()
            core_n   = len(CORE_ITEMS)
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
                if "rustup" in PROFILE_RUSTUP_PROFILES and pid in PROFILE_RUSTUP_PROFILES:
                    dlg_body.controls.append(ft.Divider())
                    dlg_body.controls.append(ft.Text(
                        "Rust toolchain (rustup) — always installs with dev profiles "
                        "(skip toggle is future work).",
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

        def _sync_profile_header_state(pid: str) -> None:
            """Uncheck the profile 'select all' header if not all its tools are chosen."""
            hdr = profile_checks.get(pid)
            if hdr is None:
                return
            all_tools = set(_tools_for_profile(pid))
            feat_keys = {k for _n, _d, _f, k in PROFILE_FEATURE_ITEMS.get(pid, ())}
            fully_selected = all_tools.issubset(desired_tools) and all(
                bool(ui[k].value) for k in feat_keys
            )
            if hdr.value and not fully_selected:
                hdr.value = False
                try:
                    hdr.update()
                except Exception:
                    pass
                # Auto-check Custom when a profile becomes partial
                custom_cb = profile_checks.get("custom")
                if custom_cb and not custom_cb.value:
                    custom_cb.value = True
                    try:
                        custom_cb.update()
                    except Exception:
                        pass

        def on_tool_toggle(tool: str, is_checked: bool, source_pid: str | None = None) -> None:
            if is_checked:
                desired_tools.add(tool)
            else:
                desired_tools.discard(tool)
            # Sync every other Checkbox instance for this tool
            for cb in tool_cb_instances.get(tool, []):
                try:
                    if cb.value != is_checked:
                        cb.value = is_checked
                        cb.update()
                except Exception:
                    pass
            # Update profile header states for every profile this tool belongs to
            from core.install_catalog import WINGET_CATALOG
            for entry in WINGET_CATALOG:
                if entry.tool == tool and entry.profiles:
                    for pid in entry.profiles & set(STANDARD_PROFILE_IDS):
                        _sync_profile_header_state(pid)
            update_count()
            sync_previews()

        def make_tool_checkbox(entry: Any, pid_context: str) -> ft.Checkbox:
            cb = ft.Checkbox(
                label=_make_tool_label(entry),
                value=entry.tool in desired_tools,
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
            cb = ft.Checkbox(label=f"{name}  —  {desc}", value=bool(src.value))

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
                            "Rust toolchain (via rustup) — always installs with this profile. "
                            "Skip toggle is future work.",
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

            custom_mode = bool(profile_checks.get("custom", ft.Checkbox()).value)
            active_pids = {pid for pid in STANDARD_PROFILE_IDS if profile_checks.get(pid, ft.Checkbox()).value}
            visible_pids = STANDARD_PROFILE_IDS if custom_mode else tuple(
                p for p in STANDARD_PROFILE_IDS if p in active_pids
            )

            for pid, label in PROFILE_DEFS:
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
                "Always installed (core)", weight=ft.FontWeight.BOLD, size=15
            ))
            profiles_col.controls.append(ft.Text(
                "Python and flet/rich are required to run this GUI. Everything else is "
                "hardwired in the current installer layers (skip toggles are future work).",
                size=12, italic=True,
            ))
            for name, desc, state in CORE_ITEMS:
                if state == "required":
                    row = ft.Row([
                        ft.Checkbox(label=f"{name}  (required — already installed)",
                                    value=True, disabled=True),
                    ], spacing=4)
                else:
                    row = ft.Row([
                        ft.Icon(ft.Icons.LOCK_OUTLINE, size=14,
                                 color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text(f"{name}", size=13),
                        ft.Text(f"— {desc}", size=12, italic=True,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                        ft.Text("(always installs)", size=11,
                                color=ft.Colors.ON_SURFACE_VARIANT),
                    ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER)
                profiles_col.controls.append(row)

            profiles_col.controls.append(ft.Divider())

            # Extras section
            extras = _all_extras_entries()
            if extras:
                profiles_col.controls.append(ft.Row(
                    [
                        ft.Text("Extras (personal-preference apps)",
                                weight=ft.FontWeight.BOLD, size=15),
                        ft.OutlinedButton("Select all extras", on_click=select_all_extras),
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
                        cb.update()
                    except Exception:
                        pass
            update_count()
            sync_previews()

        def clear_all(_: ft.ControlEvent | None = None) -> None:
            desired_tools.clear()
            for cbs in tool_cb_instances.values():
                for cb in cbs:
                    try:
                        cb.value = False
                        cb.update()
                    except Exception:
                        pass
            for pid in STANDARD_PROFILE_IDS:
                profile_checks[pid].value = False
                try:
                    profile_checks[pid].update()
                except Exception:
                    pass
            ml_wheels.value = False
            ml_base.value   = False
            try:
                ml_wheels.update()
                ml_base.update()
            except Exception:
                pass
            update_count()
            sync_previews()

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
            sanitation_preset_dd.disabled = not bool(e.control.value)
            sanitation_preset_dd.update()
            sync_previews()

        run_sanitation.on_change = on_sanitation_change
        for sw in (dry_run, skip_rp, skip_dotfiles, assume_yes, skip_summary, enable_wsl, wsl_skip):
            sw.on_change = bind_switch
        sanitation_preset_dd.on_change = bind_switch
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
                for cb in tool_cb_instances.get(entry.tool, []):
                    try:
                        cb.label = _make_tool_label(entry)
                        cb.update()
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
            if not desired_tools and not ml_wheels.value and not ml_base.value:
                show_snack("No tools selected. Tick a profile or cherry-pick tools before installing.")
                return
            args = _argv_for_installer(ui)
            creation = 0
            if sys.platform == "win32":
                creation = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
            try:
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
                    dry_run, run_sanitation, sanitation_preset_dd,
                    skip_rp, skip_dotfiles, assume_yes, skip_summary,
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

        tabs = ft.Tabs(
            selected_index=1,
            expand=1,
            tabs=[
                ft.Tab(text="Summary",          content=summary_tab_content),
                ft.Tab(text="Profiles & Tools", content=profiles_tools_tab_content),
                ft.Tab(text="Install Options",  content=options_tab_content),
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
        rebuild_profiles_col()
        update_count()
        sync_previews()

        # Auto-run the system scan in the background so tool detection
        # and disk/time estimates are ready as soon as possible.
        threading.Thread(target=_auto_scan_thread, daemon=True).start()

    ft.app(target=main)


if __name__ == "__main__":
    main_gui()
