"""Finalize: dotfile seeding, PATH audit, manifest flush, HTML report (Phase 2)."""

from __future__ import annotations

import json
import os
import shutil
import sys
import html
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _ensure_repo_on_sys_path() -> None:
    root = str(_repo_root())
    if root not in sys.path:
        sys.path.insert(0, root)


def _html_escape(text: str) -> str:
    return html.escape(text, quote=True)


def _seed_dotfiles(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Copy template dotfiles into the user profile only when the target is missing."""
    if not ctx.seed_dotfiles:
        manifest.record_tool(
            tool="dotfiles-seed",
            layer="finalize",
            status="skipped",
            install_method="copy",
            notes="Disabled by --skip-dotfiles.",
        )
        console.print("  [skipped] dotfiles-seed — flag")
        return

    src_dir = ctx.repo_root / "templates" / "dotfiles"
    if not src_dir.is_dir():
        manifest.record_tool(
            tool="dotfiles-seed",
            layer="finalize",
            status="skipped",
            install_method="copy",
            notes=f"Missing {src_dir}",
        )
        console.print("  [skipped] dotfiles-seed — no templates directory")
        return

    home = Path.home()
    pwsh_dir = home / "Documents" / "PowerShell"
    mappings: list[tuple[str, Path, Path]] = [
        (".gitconfig", src_dir / ".gitconfig", home / ".gitconfig"),
        (".bashrc", src_dir / ".bashrc", home / ".bashrc"),
        (
            "powershell-profile",
            src_dir / "powershell-profile.ps1",
            pwsh_dir / "Microsoft.PowerShell_profile.ps1",
        ),
    ]

    if ctx.dry_run:
        manifest.record_tool(
            tool="dotfiles-seed",
            layer="finalize",
            status="planned",
            install_method="copy",
            notes="Would copy missing templates into user profile.",
        )
        console.print("  [planned] dotfiles-seed — dry-run")
        return

    copied = 0
    skipped = 0
    for label, src, dst in mappings:
        if not src.is_file():
            manifest.record_tool(
                tool=f"dotfile-{label}",
                layer="finalize",
                status="skipped",
                install_method="copy",
                notes=f"Missing template: {src}",
            )
            continue
        if dst.exists():
            manifest.record_tool(
                tool=f"dotfile-{label}",
                layer="finalize",
                status="skipped",
                install_method="copy",
                notes=f"Target exists: {dst}",
            )
            skipped += 1
            continue
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        except OSError as exc:
            manifest.record_tool(
                tool=f"dotfile-{label}",
                layer="finalize",
                status="failed",
                install_method="copy",
                notes=str(exc),
            )
            continue
        manifest.record_tool(
            tool=f"dotfile-{label}",
            layer="finalize",
            status="installed",
            install_method="copy",
            notes=str(dst),
        )
        copied += 1

    console.print(f"  [done] dotfiles-seed — copied {copied}, skipped {skipped}")


def _seed_obsidian_vault(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Create the starter Obsidian vault under Documents when Extras profile requests it."""
    if not ctx.profile_selected("extras"):
        return
    if "obsidian" in ctx.catalog_exclude_tools:
        manifest.record_tool(
            tool="obsidian-vault",
            layer="finalize",
            status="skipped",
            install_method="template",
            notes="Obsidian winget excluded; vault not seeded.",
        )
        console.print("  [skipped] obsidian-vault — Obsidian excluded from catalog")
        return

    vault_root = Path.home() / "Documents" / "AM-DevKit-Vault"
    subdirs = (
        "00 - Inbox",
        "01 - Projects",
        "02 - Learning",
        "03 - Code Snippets",
        "04 - Daily Notes",
        "05 - Reference",
        "06 - Archive",
    )
    readme = (
        "# AM-DevKit Vault\n\n"
        "Starter folders seeded by Absentmind's DevKit. "
        "In Obsidian: **Open folder as vault** and choose this directory.\n"
    )

    if ctx.dry_run:
        manifest.record_tool(
            tool="obsidian-vault",
            layer="finalize",
            status="planned",
            install_method="template",
            notes=f"Would create {vault_root}",
        )
        console.print("  [planned] obsidian-vault — dry-run")
        return

    try:
        vault_root.mkdir(parents=True, exist_ok=True)
        for name in subdirs:
            (vault_root / name).mkdir(parents=True, exist_ok=True)
        readme_path = vault_root / "README.md"
        if not readme_path.is_file():
            readme_path.write_text(readme, encoding="utf-8")
        manifest.record_tool(
            tool="obsidian-vault",
            layer="finalize",
            status="installed",
            install_method="template",
            notes=str(vault_root.resolve()),
        )
        console.print(f"  [done] obsidian-vault -> {vault_root}")
    except OSError as exc:
        manifest.record_tool(
            tool="obsidian-vault",
            layer="finalize",
            status="failed",
            install_method="template",
            notes=str(exc),
        )
        console.print(f"  [failed] obsidian-vault: {exc}")


def _powertoys_settings_source_dir() -> Path | None:
    """Return PowerToys user settings folder under LocalAppData, if present."""
    la = Path(os.environ.get("LOCALAPPDATA", ""))
    base = la / "Microsoft" / "PowerToys"
    if not base.is_dir():
        return None
    for sub in ("Settings", "settings"):
        d = base / sub
        if d.is_dir():
            return d
    return base


def _backup_powertoys_settings(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Copy PowerToys JSON settings into am-devkit-out for restore on a new PC (Extras profile)."""
    if not ctx.profile_selected("extras"):
        return
    if "powertoys" in ctx.catalog_exclude_tools:
        manifest.record_tool(
            tool="powertoys-settings-backup",
            layer="finalize",
            status="skipped",
            install_method="copy",
            notes="PowerToys excluded from catalog.",
        )
        console.print("  [skipped] powertoys-settings-backup — catalog exclude")
        return

    if ctx.dry_run:
        manifest.record_tool(
            tool="powertoys-settings-backup",
            layer="finalize",
            status="planned",
            install_method="copy",
            notes="Would copy LocalAppData Microsoft/PowerToys *.json into am-devkit-out.",
        )
        console.print("  [planned] powertoys-settings-backup — dry-run")
        return

    src = _powertoys_settings_source_dir()
    if src is None:
        manifest.record_tool(
            tool="powertoys-settings-backup",
            layer="finalize",
            status="skipped",
            install_method="copy",
            notes="PowerToys user data directory not found (install not finished or not installed).",
        )
        console.print("  [skipped] powertoys-settings-backup — PowerToys folder missing")
        return

    dst_root = ctx.repo_root / "am-devkit-out" / "powertoys-settings-backup"
    copied = 0
    try:
        for path in sorted(src.rglob("*.json")):
            if "Logs" in path.parts:
                continue
            try:
                rel = path.relative_to(src)
            except ValueError:
                continue
            dest = dst_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, dest)
            copied += 1
        manifest.record_tool(
            tool="powertoys-settings-backup",
            layer="finalize",
            status="installed" if copied else "skipped",
            install_method="copy",
            notes=str(dst_root.resolve()) if copied else "No JSON files under PowerToys settings.",
        )
        if copied:
            console.print(f"  [done] powertoys-settings-backup — {copied} files -> {dst_root}")
        else:
            console.print("  [skipped] powertoys-settings-backup — no JSON files found")
    except OSError as exc:
        manifest.record_tool(
            tool="powertoys-settings-backup",
            layer="finalize",
            status="failed",
            install_method="copy",
            notes=str(exc),
        )
        console.print(f"  [failed] powertoys-settings-backup: {exc}")


def build_post_install_html(
    *,
    ctx: InstallContext,
    audit: dict[str, Any],
    tools: list[dict[str, Any]],
    launchpad_html: str = "",
) -> str:
    conflicts = audit.get("conflicts") or []
    conflict_n = int(audit.get("conflict_count") or 0)
    banner_ok = conflict_n == 0

    _ALREADY_PRESENT_MARKERS = (
        "Already present on PATH or detector.",
        "already on PATH.",
        "already available.",
        "Target exists:",
    )

    def _is_already_present(notes: str) -> bool:
        return any(m in notes for m in _ALREADY_PRESENT_MARKERS)

    def _row_class(t: dict[str, Any]) -> str:
        status = t.get("status", "")
        notes = t.get("notes") or ""
        if status == "installed":
            return "row-installed"
        if status == "failed":
            return "row-failed"
        if status == "skipped" and _is_already_present(notes):
            return "row-already"
        return ""

    def rows() -> str:
        parts: list[str] = []
        for t in tools:
            status = t.get("status", "")
            notes = t.get("notes") or ""
            display_status = status
            if status == "skipped" and _is_already_present(notes):
                display_status = "already installed"
            parts.append(
                f"<tr class='{_row_class(t)}'>"
                f"<td>{_html_escape(str(t.get('tool', '')))}</td>"
                f"<td>{_html_escape(str(t.get('layer', '')))}</td>"
                f"<td>{_html_escape(display_status)}</td>"
                f"<td>{_html_escape(str(t.get('install_method', '')))}</td>"
                "</tr>"
            )
        return "\n".join(parts) if parts else "<tr><td colspan='4'>No entries.</td></tr>"

    def conflict_blocks() -> str:
        if not conflicts:
            return "<p>No duplicate executable names detected across PATH.</p>"
        blocks: list[str] = []
        for c in conflicts:
            alts = c.get("alternates") or []
            blocks.append(
                "<div class='conflict'>"
                f"<p><strong>{_html_escape(str(c.get('basename', '')))}</strong> — "
                f"winner: <code>{_html_escape(str(c.get('winner', '')))}</code></p>"
                "<ul>"
                + "".join(f"<li><code>{_html_escape(str(a))}</code></li>" for a in alts)
                + "</ul>"
                f"<p class='hint'>{_html_escape(str(c.get('hint', '')))}</p>"
                "</div>"
            )
        return "\n".join(blocks)

    banner_class = "ok" if banner_ok else "bad"
    banner_text = (
        "PATH looks clean — no basename conflicts detected."
        if banner_ok
        else f"PATH conflicts detected ({conflict_n}). Review the section below first."
    )

    profiles = ", ".join(ctx.profiles) if ctx.profiles else "(none)"
    restore_devkit = (ctx.repo_root / "scripts" / "restore-devkit.ps1").resolve()
    restore_winget = (ctx.repo_root / "scripts" / "restore-winget-from-manifest.ps1").resolve()
    third_party_doc = (ctx.repo_root / "docs" / "THIRD_PARTY_NOTICES.md").resolve()
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>AM-DevKit — Post-install report</title>
  <style>
    body {{ font-family: Segoe UI, system-ui, sans-serif; margin: 2rem; background: #0f1115; color: #e8eaed; }}
    h1 {{ font-weight: 600; }}
    .banner {{ padding: 1rem 1.25rem; border-radius: 8px; margin-bottom: 1.5rem; }}
    .banner.ok {{ background: #143c24; border: 1px solid #2fa36b; }}
    .banner.bad {{ background: #3c1414; border: 1px solid #e05555; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 1rem; }}
    th, td {{ border: 1px solid #333; padding: 0.45rem 0.6rem; text-align: left; }}
    th {{ background: #1a1d24; }}
    tr:nth-child(even) {{ background: #151821; }}
    tr.row-installed td:nth-child(3) {{ color: #2fa36b; font-weight: 600; }}
    tr.row-failed td:nth-child(3) {{ color: #e05555; font-weight: 600; }}
    tr.row-already td:nth-child(3) {{ color: #58a6ff; }}
    code {{ font-size: 0.9em; color: #c9d1d9; }}
    .conflict {{ margin: 1rem 0; padding: 1rem; background: #1a1518; border-radius: 8px; }}
    .hint {{ color: #9aa0a6; font-size: 0.95rem; }}
    footer {{ margin-top: 2rem; color: #9aa0a6; font-size: 0.9rem; }}
    ul.launchpad {{ list-style: none; padding-left: 0; }}
    li.lp-item {{ margin: 1rem 0; padding: 1rem; background: #151821; border-radius: 8px; border: 1px solid #2a2f3a; }}
    a.lp-link {{ color: #58a6ff; }}
  </style>
</head>
<body>
  <h1>Absentmind's DevKit — Post-install report</h1>
  <p>Version {_html_escape(ctx.devkit_version)} · Profiles: {_html_escape(profiles)}</p>
  <div class="banner {banner_class}">{_html_escape(banner_text)}</div>

  <h2>PATH auditor</h2>
  <p>Fingerprint SHA256: <code>{_html_escape(str(audit.get('path_fingerprint_sha256', '')))}</code></p>
  {conflict_blocks()}

  <h2>Install manifest</h2>
  <table>
    <thead><tr><th>Tool</th><th>Layer</th><th>Status</th><th>Method</th></tr></thead>
    <tbody>
      {rows()}
    </tbody>
  </table>

  {launchpad_html}

  <footer>
    Generated {_html_escape(datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"))}
    · Manifest: <code>{_html_escape(str(ctx.manifest_path))}</code>
    <p class="hint">AM-DevKit is MIT-licensed; WinUtil, Winget packages, pip libraries, and ML runtimes have separate terms.
    See <code>{_html_escape(str(third_party_doc))}</code></p>
    <p class="hint">Re-run winget installs from this manifest on another PC:</p>
    <p><code>{_html_escape(str(restore_devkit))}</code></p>
    <p><code>{_html_escape(str(restore_winget))}</code></p>
  </footer>
</body>
</html>
"""


def run_finalize(ctx: InstallContext, manifest: Manifest, console: Console) -> dict[str, Any]:
    """Run PATH audit, write fingerprint JSON, flush manifest, emit HTML report."""
    _ensure_repo_on_sys_path()
    from core.launchpad import build_launchpad_section
    from core.restore_bundle import refresh_restore_script_from_disk
    from scripts.path_auditor import audit_path

    console.print("[bold]Finalize[/bold]")
    _seed_dotfiles(ctx, manifest, console)
    _seed_obsidian_vault(ctx, manifest, console)
    _backup_powertoys_settings(ctx, manifest, console)
    audit = audit_path()
    fp_payload = {
        "path_fingerprint_sha256": audit.get("path_fingerprint_sha256"),
        "conflict_count": audit.get("conflict_count"),
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    fp_path = ctx.repo_root / "path-fingerprint.json"
    fp_path.write_text(json.dumps(fp_payload, indent=2), encoding="utf-8")
    console.print(f"  [done] PATH fingerprint -> {fp_path}")

    manifest.record_tool(
        tool="path-auditor",
        layer="finalize",
        status="installed",
        install_method="internal",
        notes=f"{audit.get('conflict_count', 0)} conflicts",
    )

    manifest.flush()
    console.print(f"  [done] Manifest -> {ctx.manifest_path}")

    try:
        rw = refresh_restore_script_from_disk(ctx.manifest_path, ctx.repo_root)
        console.print(f"  [done] Restore winget script -> {rw}")
    except OSError as exc:
        console.print(f"  [failed] Restore script generation: {exc}")

    snap = manifest.entries_snapshot()
    launchpad_fragment = build_launchpad_section(
        repo_root=ctx.repo_root,
        profiles=ctx.profiles,
        tools=snap,
        system_profile=ctx.system_profile,
    )
    html_doc = build_post_install_html(ctx=ctx, audit=audit, tools=snap, launchpad_html=launchpad_fragment)
    ctx.report_path.write_text(html_doc, encoding="utf-8")
    console.print(f"  [done] HTML report -> {ctx.report_path}")
    return audit
