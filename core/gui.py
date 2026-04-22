"""Phase 3 — Flet launcher for AM-DevKit (opt-in per-tool selection).

Run from the repository root::

    python -m core.gui

Launches ``core.installer`` in a new console on Windows so Rich output stays readable.
State model: a single ``desired_tools: set[str]`` drives the CLI command we emit.
Profile checkboxes are bulk-select conveniences that add/remove their tools into that set.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[1]

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Standard dev-stack profiles (ordered for Tools-tab rendering).
STANDARD_PROFILE_IDS: tuple[str, ...] = (
    "ai-ml",
    "web-fullstack",
    "systems",
    "game-dev",
    "hardware-robotics",
)

# Preference order for deriving profile flags when a tool was picked in Custom
# mode without the user explicitly checking any profile. Lightweight profiles
# come first so cherry-picking a shared tool (e.g. dbeaver, which is in both
# ai-ml and web-fullstack) does not drag in the heavier ML layer by accident.
PROFILE_PREFERENCE: tuple[str, ...] = (
    "web-fullstack",
    "systems",
    "hardware-robotics",
    "game-dev",
    "ai-ml",
)

# Profile checkboxes shown in the left column. "custom" is a view-mode toggle —
# when on, the Tools tab exposes every stack's tools for cherry-picking.
PROFILE_DEFS: tuple[tuple[str, str], ...] = (
    ("ai-ml", "AI / ML"),
    ("web-fullstack", "Web / Full-Stack"),
    ("systems", "Systems / Low-Level"),
    ("game-dev", "Game Dev"),
    ("hardware-robotics", "Hardware / Robotics"),
    ("custom", "Custom — cherry-pick from all stacks"),
)

PROFILE_HINTS: dict[str, str] = {
    "ai-ml": "GPU-aware PyTorch, Ollama, HF stack, Jupyter, ML tooling.",
    "web-fullstack": "Node via nvm, Docker, DBs, Bruno, cloud CLIs, web toolchain.",
    "systems": "Rust, MSVC/shovel-ready C++, CMake, Wireshark — low-level & infra.",
    "game-dev": "Unity Hub, Godot, VS Build Tools, game-focused runtimes.",
    "hardware-robotics": "Arduino, PlatformIO, serial/USB tooling, embedded workflow.",
    "custom": "Exposes every stack's tools on the Tools tab. Pick exactly what you want.",
}

# Always-installed core items (Layer 0-3 boot + Scoop CLI suite + common catalog
# entries with profiles=None). Shown at the top of the Tools tab so the user
# can see exactly what runs on every install, not just their opt-in picks.
CORE_ALWAYS_INSTALLS: tuple[tuple[str, str], ...] = (
    ("Git", "version control (winget)"),
    ("Git LFS", "large-file support (winget)"),
    ("GitHub CLI", "gh command (winget)"),
    ("Windows Terminal", "modern terminal (winget)"),
    ("PowerShell 7", "modern pwsh (winget)"),
    ("OpenSSH Client", "ssh/scp (Windows capability)"),
    ("VS Code", "editor (winget)"),
    ("Cursor", "AI-native editor (winget)"),
    ("VS Code extensions", "from config/vscode/extensions.json"),
    ("Python 3.12", "runtime (winget)"),
    ("uv", "fast Python package manager (winget)"),
    ("pyenv-win", "Python version manager (scoop)"),
    ("Scoop", "CLI package manager"),
    ("Scoop CLI suite", "bat, ripgrep, fd, fzf, jq, lazygit, delta"),
    ("Oh My Posh", "prompt theming (winget)"),
    ("Tailscale", "zero-config VPN (winget)"),
    ("Nerd Fonts", "icons/glyphs for terminals"),
    ("7-Zip", "archiver (winget — common catalog)"),
    ("Notepad++", "editor (winget — common catalog)"),
    ("Everything", "file search (winget — common catalog)"),
    ("DevToys", "developer utilities (winget — common catalog)"),
    ("WinMerge", "diff/merge (winget — common catalog)"),
    ("System restore point", "pre-install safety (toggleable)"),
    ("Dotfiles seed", ".gitconfig / pwsh profile (toggleable)"),
)

# Non-catalog installs gated by profile. Each row is
# (display_name, description, toggle_ui_key | None).
# When toggle_ui_key is not None, we render a real checkbox wired to that
# ui dict entry (the Switch in Install options). Otherwise it renders as a
# read-only info row so the user can see what's running.
PROFILE_IMPLICIT_INSTALLS: dict[str, tuple[tuple[str, str, str | None], ...]] = {
    "ai-ml": (
        ("Ollama runtime", "winget — LLM serving; models not included", None),
        ("Docker Desktop", "winget — container runtime (shared with web)", None),
        ("kubectl", "winget — Kubernetes CLI (shared with web / systems)", None),
        ("Helm", "winget — K8s package manager (shared)", None),
        ("Rust toolchain", "rustup — shared across dev stacks", None),
        ("PyTorch wheels", "GPU-matched CUDA or CPU fallback via pip", "install_ml_wheels"),
        ("ML pip base", "numpy, pandas, matplotlib, scikit-learn, jupyter, ipython", "install_ml_base"),
    ),
    "web-fullstack": (
        ("Docker Desktop", "winget — container runtime", None),
        ("kubectl", "winget — Kubernetes CLI", None),
        ("Helm", "winget — K8s package manager", None),
    ),
    "systems": (
        ("kubectl", "winget — Kubernetes CLI (shared)", None),
        ("Helm", "winget — K8s package manager (shared)", None),
        ("Rust toolchain", "rustup", None),
    ),
    "game-dev": (
        ("Rust toolchain", "rustup (shared across dev stacks)", None),
    ),
    "hardware-robotics": (
        ("Rust toolchain", "rustup (shared across dev stacks)", None),
    ),
}

PROFILE_DISPLAY: dict[str, str] = {pid: label for pid, label in PROFILE_DEFS}


def _entries_for_profile(profile_id: str) -> list[Any]:
    """Catalog entries that list this profile (in catalog order)."""
    from core.install_catalog import WINGET_CATALOG

    return [e for e in WINGET_CATALOG if e.profiles and profile_id in e.profiles]


def _tools_for_profile(profile_id: str) -> list[str]:
    """Tool ids whose catalog entry lists this profile."""
    return [e.tool for e in _entries_for_profile(profile_id)]


def _checked_standard_profiles(ui: dict[str, Any]) -> set[str]:
    return {pid for pid in STANDARD_PROFILE_IDS if ui["profile_checks"][pid].value}


def _needed_profiles_for(ui: dict[str, Any]) -> list[str]:
    """Profiles to pass to the installer.

    Starts with the profiles the user explicitly checked on the Profiles tab.
    Any desired tool not already covered by that set adds its preferred profile
    (lightest of its allowed profiles, per PROFILE_PREFERENCE) so the installer
    will actually run it.
    """
    from core.install_catalog import WINGET_CATALOG

    checked = _checked_standard_profiles(ui)
    desired = set(ui["desired_tools"])

    derived: set[str] = set()
    for entry in WINGET_CATALOG:
        if entry.tool not in desired or not entry.profiles:
            continue
        if entry.profiles & checked:
            continue  # already covered by a user-checked profile
        for pref in PROFILE_PREFERENCE:
            if pref in entry.profiles:
                derived.add(pref)
                break

    return sorted(checked | derived)


def _exclusions_for(ui: dict[str, Any], needed_profiles: list[str]) -> list[str]:
    """Catalog tools the installer would otherwise install that the user did not pick."""
    from core.install_catalog import WINGET_CATALOG

    desired = set(ui["desired_tools"])
    sel = set(needed_profiles)
    excl: list[str] = []
    for entry in WINGET_CATALOG:
        if entry.profiles is None:
            continue  # common core — always install, never exclude
        if entry.tool in desired:
            continue
        if entry.applies_to(sel):
            excl.append(entry.tool)
    return excl


def _preview_context(ui: dict[str, Any], system_profile: dict[str, Any]) -> Any:
    """Build ``InstallContext`` matching GUI state (for summary text only)."""
    from core.install_context import InstallContext

    needed = _needed_profiles_for(ui)
    exclusions = frozenset(_exclusions_for(ui, needed))
    profiles = list(needed)

    wsl_default = None
    if ui["enable_wsl"].value and not ui["wsl_skip_distro"].value:
        wsl_default = (ui["wsl_distro"].value or "Ubuntu").strip() or "Ubuntu"
    sp_raw = getattr(ui.get("sanitation_preset"), "value", None) or "minimal"
    sp = str(sp_raw).strip().lower()
    if sp not in ("minimal", "standard"):
        sp = "minimal"
    return InstallContext(
        repo_root=_REPO_ROOT,
        system_profile_path=_REPO_ROOT / "system-profile.json",
        system_profile=dict(system_profile),
        profiles=profiles,
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
    """Build argv for ``python -m core.installer`` derived from desired_tools."""
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
        sp_raw = getattr(ui.get("sanitation_preset"), "value", None) or "minimal"
        sp = str(sp_raw).strip().lower()
        if sp not in ("minimal", "standard"):
            sp = "minimal"
        argv.extend(["--sanitation-preset", sp])
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
            d = (ui["wsl_distro"].value or "Ubuntu").strip() or "Ubuntu"
            argv.extend(["--wsl-distro", d])
    if ui["skip_dotfiles"].value:
        argv.append("--skip-dotfiles")
    if ui["assume_yes"].value:
        argv.append("--yes")
    if ui["skip_summary"].value:
        argv.append("--skip-summary")
    if ui.get("reuse_layer0") and ui["reuse_layer0"].value:
        raw = (ui.get("reuse_layer0_path") and ui["reuse_layer0_path"].value) or ""
        p = Path(str(raw).strip())
        if str(p):
            argv.extend(["--reuse-system-profile", str(p.resolve())])

    return argv


def _quote_ps_arg(s: str) -> str:
    if not s:
        return "''"
    if all(c.isalnum() or c in "-_./:" for c in s):
        return s
    return "'" + s.replace("'", "''") + "'"


def _format_cli_line(argv: list[str]) -> str:
    parts = [_quote_ps_arg(a) for a in argv]
    return "python -m core.installer " + " ".join(parts)


def main_gui() -> None:
    import flet as ft

    desired_tools: set[str] = set()
    profile_checks: dict[str, ft.Checkbox] = {}
    tool_checkboxes: dict[str, ft.Checkbox] = {}

    def main(page: ft.Page) -> None:
        page.title = "Absentmind's DevKit"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 16
        page.window.width = 900
        page.window.height = 900

        absentmind_cb = ft.Checkbox(
            label="Absentmind Mode — pre-select all core stacks (AI, Web, Systems, Game, Hardware).",
            value=False,
        )

        for pid, title in PROFILE_DEFS:
            profile_checks[pid] = ft.Checkbox(
                label=title,
                value=False,
            )

        # One dialog instance is reused for every profile info popup. Content
        # is swapped in before each open.
        info_dialog_title = ft.Text("", weight=ft.FontWeight.BOLD, size=16)
        info_dialog_body = ft.Column(
            [],
            tight=True,
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
        )

        def close_info_dialog(_: ft.ControlEvent | None = None) -> None:
            info_dialog.open = False
            page.update()

        info_dialog = ft.AlertDialog(
            modal=True,
            title=info_dialog_title,
            content=ft.Container(content=info_dialog_body, width=520, height=420),
            actions=[ft.TextButton("Close", on_click=close_info_dialog)],
        )

        def open_profile_info(profile_id: str) -> None:
            info_dialog_title.value = f"{PROFILE_DISPLAY.get(profile_id, profile_id)} — what installs"
            info_dialog_body.controls.clear()

            info_dialog_body.controls.append(
                ft.Text(PROFILE_HINTS.get(profile_id, ""), size=12, italic=True)
            )

            if profile_id == "custom":
                info_dialog_body.controls.append(
                    ft.Text(
                        "Custom is a view toggle. Turning it on exposes every stack's "
                        "tools on the Tools tab so you can cherry-pick. It does not add "
                        "any tools to the install on its own.",
                        size=12,
                    )
                )
            else:
                entries = _entries_for_profile(profile_id)
                if entries:
                    info_dialog_body.controls.append(ft.Divider())
                    info_dialog_body.controls.append(
                        ft.Text(
                            f"Catalog tools ({len(entries)}):",
                            weight=ft.FontWeight.BOLD,
                            size=13,
                        )
                    )
                    for e in entries:
                        info_dialog_body.controls.append(
                            ft.Text(f"  • {e.tool}  ({e.layer})  —  {e.winget_id}", size=12)
                        )
                note = PROFILE_EXTRAS_NOTES.get(profile_id)
                if note:
                    info_dialog_body.controls.append(ft.Divider())
                    info_dialog_body.controls.append(
                        ft.Text(note, size=12)
                    )

            if info_dialog not in page.overlay:
                page.overlay.append(info_dialog)
            info_dialog.open = True
            page.update()

        def make_info_button(profile_id: str) -> ft.IconButton:
            return ft.IconButton(
                icon=ft.Icons.INFO_OUTLINE,
                tooltip=f"Show what installs with {PROFILE_DISPLAY.get(profile_id, profile_id)}",
                icon_size=18,
                on_click=lambda e, pid=profile_id: open_profile_info(pid),
            )

        dry_run = ft.Switch(label="Dry run (no destructive writes)", value=True)
        run_sanitation = ft.Switch(
            label="Run Windows sanitation (CTT WinUtil — optional, disruptive)",
            value=False,
        )
        sanitation_preset_dd = ft.Dropdown(
            label="WinUtil tweak preset (when sanitation is on)",
            options=[
                ft.dropdown.Option("minimal"),
                ft.dropdown.Option("standard"),
            ],
            value="minimal",
            width=400,
            disabled=True,
            hint_text="minimal = 4 tweaks · standard = CTT preset.json Standard (13)",
        )
        skip_rp = ft.Switch(label="Skip system restore point", value=False)
        skip_dotfiles = ft.Switch(label="Skip dotfile seeding", value=False)
        assume_yes = ft.Switch(label="Assume yes / non-interactive (-y)", value=True)
        skip_summary = ft.Switch(label="Skip pre-install summary panel", value=False)
        ml_wheels = ft.Switch(label="Install PyTorch wheels (when AI/ML applies)", value=False)
        ml_base = ft.Switch(
            label="Install core ML pip stack (numpy, pandas, … when AI/ML applies)",
            value=False,
        )
        enable_wsl = ft.Switch(label="Enable WSL (DISM; may require reboot)", value=False)
        wsl_distro = ft.TextField(label="WSL distro name", value="Ubuntu", width=280)
        wsl_skip = ft.Switch(label="Skip default distro install (DISM only)", value=False)
        reuse_layer0 = ft.Switch(
            label="Reuse system profile from file (skip WMI scan during install)",
            value=False,
        )
        reuse_layer0_path = ft.TextField(
            label="Path to system-profile.json",
            value=str((_REPO_ROOT / "system-profile.json").resolve()),
            expand=True,
        )

        ui: dict[str, Any] = {
            "profile_checks": profile_checks,
            "desired_tools": desired_tools,
            "dry_run": dry_run,
            "run_sanitation": run_sanitation,
            "sanitation_preset": sanitation_preset_dd,
            "skip_restore_point": skip_rp,
            "skip_dotfiles": skip_dotfiles,
            "assume_yes": assume_yes,
            "skip_summary": skip_summary,
            "install_ml_wheels": ml_wheels,
            "install_ml_base": ml_base,
            "enable_wsl": enable_wsl,
            "wsl_distro": wsl_distro,
            "wsl_skip_distro": wsl_skip,
            "reuse_layer0": reuse_layer0,
            "reuse_layer0_path": reuse_layer0_path,
        }

        preview_field = ft.TextField(
            label="Equivalent command (run from repo root)",
            read_only=True,
            multiline=True,
            min_lines=2,
            max_lines=6,
            text_size=12,
        )

        layer0_profile: dict[str, Any] = {}

        def load_layer0_from_disk() -> None:
            layer0_profile.clear()
            path = _REPO_ROOT / "system-profile.json"
            if path.is_file():
                try:
                    layer0_profile.update(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    pass

        summary_field = ft.TextField(
            label="Pre-install summary (same heuristics as CLI)",
            read_only=True,
            multiline=True,
            min_lines=14,
            max_lines=22,
            text_size=12,
        )
        scan_hint = ft.Text(
            "Run a Layer 0 scan to improve time/disk estimates. Writes system-profile.json in the repo.",
            size=13,
        )

        selected_count_text = ft.Text("", size=13, italic=True)
        start_bar_count_text = ft.Text("", size=13, weight=ft.FontWeight.W_500)

        def _count_profile_implicit_installs() -> int:
            """Non-catalog add-ons that trigger for the user's selected profiles.

            Counts each unique add-on once across profiles. Toggleable ML items
            (PyTorch wheels, ML pip base) only count when their Switch is on.
            """
            checked = _checked_standard_profiles(ui)
            # Also count profiles implicitly activated by desired cherry-picks.
            needed = set(_needed_profiles_for(ui))
            active = checked | needed
            seen: set[str] = set()
            count = 0
            for pid in active:
                for name, _desc, toggle_key in PROFILE_IMPLICIT_INSTALLS.get(pid, ()):
                    if name in seen:
                        continue
                    if toggle_key:
                        src = ui.get(toggle_key)
                        if src is None or not bool(src.value):
                            continue
                    seen.add(name)
                    count += 1
            return count

        def update_selected_count() -> None:
            picked = len(desired_tools)
            core = len(CORE_ALWAYS_INSTALLS)
            implicit = _count_profile_implicit_installs()
            total = picked + core + implicit
            tools_word = "tool" if picked == 1 else "tools"
            short = (
                f"{picked} {tools_word} selected · "
                f"~{total} total installs this run"
            )
            long = (
                f"{picked} {tools_word} selected  (+ {core} core always install"
                f"{f' + {implicit} profile add-ons' if implicit else ''})  "
                f"·  ~{total} total."
            )
            start_bar_count_text.value = short
            selected_count_text.value = long
            try:
                start_bar_count_text.update()
                selected_count_text.update()
            except (AssertionError, AttributeError):
                pass

        def on_tool_toggle(tool: str, is_checked: bool) -> None:
            if is_checked:
                desired_tools.add(tool)
            else:
                desired_tools.discard(tool)
            update_selected_count()
            sync_all_previews()

        def make_tool_checkbox(entry: Any) -> ft.Checkbox:
            cb = ft.Checkbox(
                label=f"{entry.tool}  ({entry.layer})",
                value=entry.tool in desired_tools,
                tooltip=entry.winget_id,
            )

            def _handler(e: ft.ControlEvent) -> None:
                on_tool_toggle(entry.tool, bool(e.control.value))

            cb.on_change = _handler
            return cb

        tools_host = ft.Column(
            controls=[],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=6,
        )

        def select_all_extras(_: ft.ControlEvent | None = None) -> None:
            from core.install_catalog import WINGET_CATALOG

            for entry in WINGET_CATALOG:
                if entry.profiles and "extras" in entry.profiles:
                    desired_tools.add(entry.tool)
                    cb = tool_checkboxes.get(entry.tool)
                    if cb is not None:
                        cb.value = True
                        cb.update()
            update_selected_count()
            sync_all_previews()

        def clear_all_tools(_: ft.ControlEvent | None = None) -> None:
            desired_tools.clear()
            for cb in tool_checkboxes.values():
                cb.value = False
                cb.update()
            update_selected_count()
            sync_all_previews()

        # References to mirror-checkboxes for ml toggles, so flipping the
        # Switch in Install options also updates these rendered checkboxes.
        ml_linked_refs: dict[str, ft.Checkbox | None] = {
            "install_ml_wheels": None,
            "install_ml_base": None,
        }

        def make_core_row(name: str, desc: str) -> ft.Row:
            return ft.Row(
                [
                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=14, color=ft.Colors.GREEN_400),
                    ft.Text(name, size=13, weight=ft.FontWeight.W_500),
                    ft.Text(
                        f"— {desc}",
                        size=12,
                        italic=True,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        def make_implicit_row(name: str, desc: str) -> ft.Row:
            return ft.Row(
                [
                    ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=14, color=ft.Colors.BLUE_300),
                    ft.Text(name, size=13, weight=ft.FontWeight.W_500),
                    ft.Text(
                        f"— {desc}",
                        size=12,
                        italic=True,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    ),
                ],
                spacing=6,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )

        def make_ml_linked_checkbox(ui_key: str, label: str, desc: str) -> ft.Checkbox:
            src = ui[ui_key]  # the Switch in Install options
            cb = ft.Checkbox(
                label=f"{label} — {desc}",
                value=bool(src.value),
            )

            def _on_change(e: ft.ControlEvent) -> None:
                src.value = bool(e.control.value)
                src.update()
                update_selected_count()
                sync_all_previews()

            cb.on_change = _on_change
            ml_linked_refs[ui_key] = cb
            return cb

        def rebuild_tools_column() -> None:
            tools_host.controls.clear()
            tool_checkboxes.clear()
            for k in ml_linked_refs:
                ml_linked_refs[k] = None

            custom_mode = bool(profile_checks["custom"].value)
            active_standard_profiles = {
                pid for pid in STANDARD_PROFILE_IDS if profile_checks[pid].value
            }
            # When Custom is on, show every stack so the user can cherry-pick.
            visible_profiles = (
                STANDARD_PROFILE_IDS if custom_mode else tuple(
                    pid for pid in STANDARD_PROFILE_IDS if pid in active_standard_profiles
                )
            )

            # --- Core section (always installed) ---
            tools_host.controls.append(
                ft.Text("Always installed (core)", weight=ft.FontWeight.BOLD, size=15)
            )
            tools_host.controls.append(
                ft.Text(
                    "These install on every run and cannot be unchecked. Shown so you "
                    "can see the full install footprint, not just your opt-in picks.",
                    size=12,
                    italic=True,
                )
            )
            for name, desc in CORE_ALWAYS_INSTALLS:
                tools_host.controls.append(make_core_row(name, desc))

            tools_host.controls.append(ft.Divider())
            tools_host.controls.append(
                ft.Text(
                    "Profile tools (opt-in)",
                    weight=ft.FontWeight.BOLD,
                    size=15,
                )
            )
            tools_host.controls.append(
                ft.Text(
                    "Every tool below starts unchecked. Tick a profile on the Profiles tab "
                    "to bulk-select, or cherry-pick individual items.",
                    size=12,
                    italic=True,
                )
            )

            any_standard_section = False
            already_rendered: set[str] = set()
            already_rendered_implicit: set[str] = set()
            for profile_id in visible_profiles:
                entries = [
                    e for e in _entries_for_profile(profile_id)
                    if e.tool not in already_rendered
                ]
                implicit_rows = [
                    row for row in PROFILE_IMPLICIT_INSTALLS.get(profile_id, ())
                    if row[0] not in already_rendered_implicit
                ]
                if not entries and not implicit_rows:
                    continue
                any_standard_section = True
                tools_host.controls.append(ft.Divider())
                tools_host.controls.append(
                    ft.Text(
                        PROFILE_DISPLAY.get(profile_id, profile_id),
                        weight=ft.FontWeight.BOLD,
                        size=15,
                    )
                )
                # Catalog (checkable) tools
                for entry in entries:
                    cb = make_tool_checkbox(entry)
                    tool_checkboxes[entry.tool] = cb
                    tools_host.controls.append(cb)
                    already_rendered.add(entry.tool)

                # Non-catalog items: auto-installs + toggleable ML add-ons
                if implicit_rows:
                    tools_host.controls.append(
                        ft.Text(
                            "Also runs with this profile:",
                            size=12,
                            italic=True,
                            color=ft.Colors.ON_SURFACE_VARIANT,
                        )
                    )
                    for name, desc, toggle_key in implicit_rows:
                        if toggle_key and toggle_key in ui:
                            tools_host.controls.append(
                                make_ml_linked_checkbox(toggle_key, name, desc)
                            )
                        else:
                            tools_host.controls.append(make_implicit_row(name, desc))
                        already_rendered_implicit.add(name)

            if not any_standard_section:
                tools_host.controls.append(
                    ft.Text(
                        "No stacks selected yet. Tick a profile on the Profiles tab, or tick "
                        "'Custom — cherry-pick from all stacks' to see everything.",
                        size=12,
                        color=ft.Colors.ON_SURFACE_VARIANT,
                    )
                )

            # --- Extras section — always visible, individually selectable. ---
            extras = _entries_for_profile("extras")
            if extras:
                tools_host.controls.append(ft.Divider())
                tools_host.controls.append(
                    ft.Row(
                        [
                            ft.Text("Extras (personal-preference apps)", weight=ft.FontWeight.BOLD, size=15),
                            ft.OutlinedButton("Select all extras", on_click=select_all_extras),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    )
                )
                tools_host.controls.append(
                    ft.Text(
                        "Each extra is individually opt-in. Nothing here is pre-checked.",
                        size=12,
                        italic=True,
                    )
                )
                for entry in extras:
                    cb = make_tool_checkbox(entry)
                    tool_checkboxes[entry.tool] = cb
                    tools_host.controls.append(cb)

            tools_host.update()

        def sync_all_previews() -> None:
            from core.pre_install_summary import format_pre_install_summary_text

            preview_field.value = _format_cli_line(_argv_for_installer(ui))
            summary_field.value = format_pre_install_summary_text(
                _preview_context(ui, layer0_profile)
            )
            preview_field.update()
            summary_field.update()

        def on_profile_toggle(profile_id: str, is_checked: bool) -> None:
            # "custom" is a view toggle only; it does not add tools.
            if profile_id != "custom":
                tools = _tools_for_profile(profile_id)
                for t in tools:
                    if is_checked:
                        desired_tools.add(t)
                    else:
                        desired_tools.discard(t)
            rebuild_tools_column()
            update_selected_count()
            sync_all_previews()

        def wire_profile_checkbox(pid: str, cb: ft.Checkbox) -> None:
            def _handler(e: ft.ControlEvent) -> None:
                on_profile_toggle(pid, bool(e.control.value))

            cb.on_change = _handler

        for pid, cb in profile_checks.items():
            wire_profile_checkbox(pid, cb)

        def on_absentmind_change(_: ft.ControlEvent | None = None) -> None:
            if absentmind_cb.value:
                for pid in STANDARD_PROFILE_IDS:
                    cb = profile_checks[pid]
                    if not cb.value:
                        cb.value = True
                        cb.update()
                        on_profile_toggle(pid, True)
            # Absentmind does not unselect anything when unchecked — user manages manually.

        absentmind_cb.on_change = on_absentmind_change

        def bind_switch(_: ft.ControlEvent | None = None) -> None:
            sync_all_previews()

        def on_sanitation_change(e: ft.ControlEvent) -> None:
            sanitation_preset_dd.disabled = not bool(e.control.value)
            sanitation_preset_dd.update()
            bind_switch(e)

        run_sanitation.on_change = on_sanitation_change

        for sw in (
            dry_run,
            skip_rp,
            skip_dotfiles,
            assume_yes,
            skip_summary,
            enable_wsl,
            wsl_skip,
        ):
            sw.on_change = bind_switch
        sanitation_preset_dd.on_change = bind_switch
        wsl_distro.on_change = bind_switch

        def on_ml_switch_change(ui_key: str) -> Any:
            def _handler(e: ft.ControlEvent) -> None:
                # Mirror any linked checkbox currently rendered on the Tools tab
                # so the two stay in sync regardless of where the user toggled.
                linked = ml_linked_refs.get(ui_key)
                if linked is not None:
                    linked.value = bool(e.control.value)
                    try:
                        linked.update()
                    except (AssertionError, AttributeError):
                        pass
                update_selected_count()
                sync_all_previews()

            return _handler

        ml_wheels.on_change = on_ml_switch_change("install_ml_wheels")
        ml_base.on_change = on_ml_switch_change("install_ml_base")

        def on_reuse_layer0_change(e: ft.ControlEvent) -> None:
            reuse_layer0_path.disabled = not bool(e.control.value)
            if e.control.value:
                load_layer0_from_disk()
            reuse_layer0_path.update()
            bind_switch(e)

        reuse_layer0.on_change = on_reuse_layer0_change
        reuse_layer0_path.disabled = not reuse_layer0.value
        reuse_layer0_path.on_change = bind_switch

        snack = ft.SnackBar(content=ft.Text(""), open=False)

        def copy_summary_text(_: ft.ControlEvent) -> None:
            sync_all_previews()
            page.set_clipboard(summary_field.value or "")
            snack.content = ft.Text("Copied pre-install summary to clipboard.")
            snack.open = True
            page.update()

        def run_system_scan(_: ft.ControlEvent) -> None:
            scan_script = _REPO_ROOT / "core" / "system_scan.py"
            out_path = _REPO_ROOT / "system-profile.json"
            try:
                proc = subprocess.run(
                    [sys.executable, str(scan_script), "--output", str(out_path)],
                    cwd=str(_REPO_ROOT),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=300.0,
                )
                if proc.returncode != 0:
                    tail = ((proc.stderr or "") + "\n" + (proc.stdout or ""))[-400:]
                    snack.content = ft.Text(f"system_scan exited {proc.returncode}. {tail}")
                    snack.open = True
                    page.update()
                    return
                load_layer0_from_disk()
                sync_all_previews()
                snack.content = ft.Text(f"Updated {out_path.name}")
                snack.open = True
                page.update()
            except (OSError, subprocess.TimeoutExpired) as exc:
                snack.content = ft.Text(f"Scan failed: {exc}")
                snack.open = True
                page.update()

        def run_installer_new_console(_: ft.ControlEvent) -> None:
            sync_all_previews()
            if not desired_tools:
                snack.content = ft.Text(
                    "No tools selected. Tick a profile or cherry-pick individual tools "
                    "before starting the install."
                )
                snack.open = True
                page.update()
                return
            if reuse_layer0.value:
                rp = Path(str(reuse_layer0_path.value or "").strip())
                if not rp.is_file():
                    snack.content = ft.Text(
                        "Reuse Layer 0 is on, but that JSON file was not found. "
                        "Run system scan or fix the path."
                    )
                    snack.open = True
                    page.update()
                    return
            args = _argv_for_installer(ui)
            creation = 0
            if sys.platform == "win32":
                creation = subprocess.CREATE_NEW_CONSOLE  # type: ignore[attr-defined]
            try:
                subprocess.Popen(
                    [sys.executable, "-m", "core.installer", *args],
                    cwd=str(_REPO_ROOT),
                    creationflags=creation,
                )
                snack.content = ft.Text("Installer started in a new console window.")
                snack.open = True
                page.update()
            except OSError as exc:
                snack.content = ft.Text(f"Could not start installer: {exc}")
                snack.open = True
                page.update()

        def copy_command(_: ft.ControlEvent) -> None:
            sync_all_previews()
            page.set_clipboard(preview_field.value or "")
            snack.content = ft.Text("Copied installer command to clipboard.")
            snack.open = True
            page.update()

        profile_rows: list[ft.Control] = []
        for pid, _title in PROFILE_DEFS:
            profile_rows.append(
                ft.Row(
                    [
                        profile_checks[pid],
                        make_info_button(pid),
                    ],
                    spacing=4,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        profiles_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Profiles", weight=ft.FontWeight.BOLD, size=18),
                    ft.Text(
                        "Ticking a profile bulk-adds its tools to your install. Individual tools "
                        "are still editable on the Tools tab. Click the ⓘ button on any profile "
                        "to see exactly what it installs.",
                        size=12,
                        italic=True,
                    ),
                    absentmind_cb,
                    ft.Column(profile_rows, spacing=2),
                ],
                spacing=8,
            ),
            padding=16,
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
        )

        options_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Install options", weight=ft.FontWeight.BOLD, size=18),
                    dry_run,
                    run_sanitation,
                    sanitation_preset_dd,
                    skip_rp,
                    skip_dotfiles,
                    assume_yes,
                    skip_summary,
                    ft.Divider(),
                    ml_wheels,
                    ml_base,
                    ft.Divider(),
                    enable_wsl,
                    wsl_distro,
                    wsl_skip,
                    ft.Divider(),
                    reuse_layer0,
                    reuse_layer0_path,
                ],
                spacing=4,
            ),
            padding=16,
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
        )

        tools_tab = ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Text(
                                "Tools & extras — per-item selection",
                                weight=ft.FontWeight.BOLD,
                                size=18,
                            ),
                            ft.OutlinedButton("Clear all", on_click=clear_all_tools),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    selected_count_text,
                    tools_host,
                ],
                spacing=8,
                expand=True,
            ),
            padding=16,
            expand=True,
        )

        summary_tab = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Pre-install summary", weight=ft.FontWeight.BOLD, size=18),
                    scan_hint,
                    ft.Row(
                        [
                            ft.FilledButton("Run system scan", on_click=run_system_scan),
                            ft.OutlinedButton("Copy summary", on_click=copy_summary_text),
                        ],
                        spacing=16,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        wrap=True,
                    ),
                    summary_field,
                ],
                spacing=12,
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=16,
            expand=True,
        )

        tabs = ft.Tabs(
            selected_index=1,
            expand=1,
            tabs=[
                ft.Tab(
                    text="Summary",
                    content=summary_tab,
                ),
                ft.Tab(
                    text="Profiles & options",
                    content=ft.Container(
                        content=ft.Column(
                            [profiles_card, options_card],
                            spacing=16,
                            scroll=ft.ScrollMode.AUTO,
                            expand=True,
                        ),
                        padding=8,
                        expand=True,
                    ),
                ),
                ft.Tab(
                    text="Tools & extras",
                    content=tools_tab,
                ),
            ],
        )

        start_button = ft.FilledButton(
            "▶  START INSTALL",
            on_click=run_installer_new_console,
            style=ft.ButtonStyle(
                padding=ft.padding.symmetric(horizontal=24, vertical=16),
                bgcolor=ft.Colors.GREEN_700,
                color=ft.Colors.WHITE,
            ),
        )

        header = ft.Column(
            [
                ft.Text(
                    "Absentmind's DevKit",
                    size=22,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Developer toolkit installer — pick profiles or cherry-pick tools, "
                    "review the summary, then click START INSTALL at the bottom.",
                    size=13,
                ),
            ],
            spacing=2,
        )

        # Start bar sits just above the equivalent-command preview so it's visible
        # without scrolling, and close to the command the user is about to run.
        start_bar = ft.Container(
            content=ft.Row(
                [
                    start_bar_count_text,
                    start_button,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=8, vertical=10),
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.10, ft.Colors.GREEN),
        )

        page.add(
            header,
            ft.Text(
                "Licensing: MIT (this repo). WinUtil / Winget / pip packages have separate terms — see docs/THIRD_PARTY_NOTICES.md",
                size=11,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            tabs,
            start_bar,
            preview_field,
            ft.Row(
                [
                    ft.OutlinedButton("Copy command", on_click=copy_command),
                ],
                spacing=12,
            ),
            snack,
        )

        load_layer0_from_disk()
        rebuild_tools_column()
        update_selected_count()
        sync_all_previews()

    ft.app(target=main)


if __name__ == "__main__":
    main_gui()
