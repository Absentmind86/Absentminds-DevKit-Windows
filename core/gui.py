"""Phase 3 — Flet launcher for AM-DevKit (profile picker + options + catalog exclusions).

Run from the repository root::

    python -m core.gui

Launches ``core.installer`` in a new console on Windows so Rich output stays readable.
Mirrors CLI flags including ``--reuse-system-profile`` when Layer 0 JSON reuse is enabled.
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

PROFILE_DEFS: tuple[tuple[str, str], ...] = (
    ("ai-ml", "AI / ML"),
    ("web-fullstack", "Web / Full-Stack"),
    ("systems", "Systems / Low-Level"),
    ("game-dev", "Game Dev"),
    ("hardware-robotics", "Hardware / Robotics"),
    ("extras", "Extras — PowerToys, Obsidian, Discord, …"),
)

PROFILE_HINTS: dict[str, str] = {
    "ai-ml": "GPU-aware PyTorch, Ollama, HF stack, Jupyter, ML tooling.",
    "web-fullstack": "Node via nvm, Docker, DBs, Bruno, cloud CLIs, web toolchain.",
    "systems": "Rust, MSVC/shovel-ready C++, CMake, Wireshark — low-level & infra.",
    "game-dev": "Unity Hub, Godot, VS Build Tools, game-focused runtimes.",
    "hardware-robotics": "Arduino, PlatformIO, serial/USB tooling, embedded workflow.",
    "extras": "Optional desktop apps: PowerToys, Obsidian, OBS, Discord, … (not in Absentmind).",
}


def _preview_context(ui: dict[str, Any], system_profile: dict[str, Any]) -> Any:
    """Build ``InstallContext`` matching GUI state (for summary text only)."""
    from core.install_context import InstallContext

    profiles = _selected_profile_ids(bool(ui["absentmind"].value), ui["profile_checks"])
    ex = frozenset(ui["excluded_tools"])
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
        catalog_exclude_tools=ex,
    )


def _selected_profile_ids(
    absentmind: bool,
    profile_checks: dict[str, Any],
) -> list[str]:
    from core.install_context import merge_profile_args

    if absentmind:
        return merge_profile_args(absentmind=True, profiles=[])
    active = [pid for pid, ob in profile_checks.items() if ob.value]
    merged = merge_profile_args(absentmind=False, profiles=active)
    return merged if merged else ["systems"]


def _argv_for_installer(ui: dict[str, Any]) -> list[str]:
    """Build argv for ``python -m core.installer`` (only flags and args)."""
    argv: list[str] = []

    if ui["dry_run"].value:
        argv.append("--dry-run")
    if ui["absentmind"].value:
        argv.append("--absentmind")
    else:
        for pid, ob in ui["profile_checks"].items():
            if ob.value:
                argv.extend(["--profile", pid])

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

    sel = set(
        _selected_profile_ids(
            bool(ui["absentmind"].value),
            ui["profile_checks"],
        )
    )
    excluded: set[str] = ui["excluded_tools"]
    from core.install_catalog import WINGET_CATALOG

    for entry in WINGET_CATALOG:
        if entry.applies_to(sel) and entry.tool in excluded:
            argv.extend(["--exclude-catalog-tool", entry.tool])

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

    excluded_tools: set[str] = set()
    profile_checks: dict[str, ft.Checkbox] = {}

    def build_exclusion_column(
        absentmind_cb: ft.Checkbox,
        prof_checks: dict[str, ft.Checkbox],
    ) -> ft.Column:
        from core.install_catalog import WINGET_CATALOG

        sel = set(_selected_profile_ids(absentmind_cb.value, prof_checks))
        controls: list[ft.Control] = [
            ft.Text(
                "Uncheck to exclude a winget catalog package for this profile selection.",
                size=13,
            ),
        ]
        for entry in WINGET_CATALOG:
            applies = entry.applies_to(sel)
            should_install = applies and entry.tool not in excluded_tools
            cb = ft.Checkbox(
                label=f"{entry.tool}  ({entry.layer})",
                value=should_install,
                disabled=not applies,
                tooltip=entry.winget_id,
            )

            def make_handler(tool: str, checkbox: ft.Checkbox):
                def _on_change(e: ft.ControlEvent) -> None:
                    if checkbox.disabled:
                        return
                    if e.control.value:
                        excluded_tools.discard(tool)
                    else:
                        excluded_tools.add(tool)

                return _on_change

            cb.on_change = make_handler(entry.tool, cb)
            controls.append(cb)
        return ft.Column(
            controls,
            spacing=4,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        )

    def main(page: ft.Page) -> None:
        page.title = "Absentmind's DevKit"
        page.theme_mode = ft.ThemeMode.DARK
        page.padding = 16
        page.window.width = 760
        page.window.height = 880

        absentmind_cb = ft.Checkbox(
            label="Absentmind Mode — all core profiles (AI, Web, Systems, Game, Hardware; not Extras)",
            value=False,
        )

        for pid, title in PROFILE_DEFS:
            profile_checks[pid] = ft.Checkbox(
                label=title,
                value=(pid == "systems"),
                tooltip=PROFILE_HINTS.get(pid),
            )

        dry_run = ft.Switch(label="Dry run (no destructive writes)", value=True)
        run_sanitation = ft.Switch(
            label="Run Windows sanitation (CTT WinUtil — disruptive)",
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
            "absentmind": absentmind_cb,
            "profile_checks": profile_checks,
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
            "excluded_tools": excluded_tools,
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

        exclusion_host = ft.Column(
            controls=[build_exclusion_column(absentmind_cb, profile_checks)],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        def sync_all_previews() -> None:
            from core.pre_install_summary import format_pre_install_summary_text

            preview_field.value = _format_cli_line(_argv_for_installer(ui))
            summary_field.value = format_pre_install_summary_text(_preview_context(ui, layer0_profile))
            preview_field.update()
            summary_field.update()

        def refresh_exclusions() -> None:
            exclusion_host.controls.clear()
            exclusion_host.controls.append(
                build_exclusion_column(absentmind_cb, profile_checks)
            )
            exclusion_host.update()
            sync_all_previews()

        def sync_profile_disabled() -> None:
            for cb in profile_checks.values():
                cb.disabled = absentmind_cb.value

        def on_absentmind_change(_: ft.ControlEvent | None = None) -> None:
            sync_profile_disabled()
            refresh_exclusions()
            page.update()

        absentmind_cb.on_change = on_absentmind_change

        def on_profile_change(_: ft.ControlEvent) -> None:
            refresh_exclusions()

        for cb in profile_checks.values():
            cb.on_change = on_profile_change

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
            ml_wheels,
            ml_base,
            enable_wsl,
            wsl_skip,
        ):
            sw.on_change = bind_switch
        sanitation_preset_dd.on_change = bind_switch
        wsl_distro.on_change = bind_switch

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

        profiles_card = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Profiles", weight=ft.FontWeight.BOLD, size=18),
                    absentmind_cb,
                    ft.Text("Profiles (multi-select)", size=13),
                    ft.Row(
                        wrap=True,
                        spacing=12,
                        controls=list(profile_checks.values()),
                    ),
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

        custom_tab = ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Custom — catalog exclusions",
                        weight=ft.FontWeight.BOLD,
                        size=18,
                    ),
                    exclusion_host,
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
                            ft.Text(
                                "Hover profile checkboxes on the next tab for short descriptions.",
                                size=12,
                                italic=True,
                            ),
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
            selected_index=0,
            expand=True,
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
                    text="Custom exclusions",
                    content=custom_tab,
                ),
            ],
        )

        page.add(
            ft.Text("Absentmind's DevKit", size=22, weight=ft.FontWeight.BOLD),
            ft.Text(
                "Developer toolkit installer — choose your profiles, then run the installer in a new console.",
                size=13,
            ),
            ft.Text(
                "Licensing: MIT (this repo). WinUtil / Winget / pip packages have separate terms — see docs/THIRD_PARTY_NOTICES.md",
                size=11,
                color=ft.Colors.ON_SURFACE_VARIANT,
            ),
            tabs,
            preview_field,
            ft.Row(
                [
                    ft.FilledButton(
                        "Run installer (new console)",
                        on_click=run_installer_new_console,
                    ),
                    ft.OutlinedButton("Copy command", on_click=copy_command),
                ],
                spacing=12,
            ),
            snack,
        )

        load_layer0_from_disk()
        sync_profile_disabled()
        sync_all_previews()

    ft.app(target=main)


if __name__ == "__main__":
    main_gui()
