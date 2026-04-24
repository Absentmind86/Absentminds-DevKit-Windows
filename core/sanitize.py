"""Layer 1: CTT WinUtil integration.

Two execution paths:

* **Default (pinned, hash-verified)** — downloads the WinUtil ``winutil.ps1``
  release artifact and its ``preset.json`` from the pinned tag in
  :mod:`core.winutil_pin`.  Both files are SHA256-verified before anything
  runs; a mismatch aborts the layer.  The script is invoked locally via
  ``powershell.exe -File`` with the preset passed as ``-Config``.

* **Opt-in (``--winutil-latest``)** — replicates the upstream one-liner
  ``iex "& { $(irm 'https://christitus.com/win') } -Config $config -Run"``
  with no integrity check.  A disclaimer is printed before it runs.  Use only
  when you need a tweak CTT just shipped.

Upstream license: MIT, Chris Titus Tech / CT Tech Group LLC — see
``docs/THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def _write_preset_config(tweaks: list[str]) -> Path:
    tmp = Path(tempfile.mktemp(suffix=".json", prefix="am-devkit-winutil-cfg-"))
    tmp.write_text(json.dumps({"WPFTweaks": tweaks}), encoding="utf-8")
    return tmp


def _run_winutil_pinned(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
    preset_name: str,
) -> None:
    from core.winutil_pin import (
        WINUTIL_SCRIPT_SHA256,
        WINUTIL_SCRIPT_URL,
        WINUTIL_TAG,
        WinUtilHashMismatch,
        download_verified,
    )
    from core.winutil_presets import get_tweaks_for_preset

    try:
        tweaks = get_tweaks_for_preset(preset_name, latest=False, timeout=60.0)
    except Exception as exc:
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="failed",
            install_method="winutil-pinned",
            notes=f"preset fetch failed: {type(exc).__name__}: {exc}",
        )
        console.print(f"  [failed] WinUtil — preset fetch failed: {exc}")
        return

    if not tweaks:
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="failed",
            install_method="winutil-pinned",
            notes=f"Unknown preset '{preset_name}' in pinned preset.json ({WINUTIL_TAG}).",
        )
        console.print(f"  [failed] WinUtil — unknown preset: {preset_name}")
        return

    config_path = _write_preset_config(tweaks)

    try:
        script_path = download_verified(
            WINUTIL_SCRIPT_URL,
            WINUTIL_SCRIPT_SHA256,
            timeout=180.0,
            suffix=".ps1",
        )
    except WinUtilHashMismatch as exc:
        config_path.unlink(missing_ok=True)
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="failed",
            install_method="winutil-pinned",
            notes=f"Hash verification failed: {exc}",
        )
        console.print(f"  [failed] WinUtil — hash verification failed (install aborted): {exc}")
        return
    except Exception as exc:
        config_path.unlink(missing_ok=True)
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="failed",
            install_method="winutil-pinned",
            notes=f"Script download failed: {type(exc).__name__}: {exc}",
        )
        console.print(f"  [failed] WinUtil — script download failed: {exc}")
        return

    console.print(
        f"  [installing] WinUtil (CTT {WINUTIL_TAG}, hash-verified) — "
        f"preset: {preset_name} — this may take several minutes …"
    )
    try:
        proc = subprocess.run(
            [
                "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-File", str(script_path),
                "-Config", str(config_path),
                "-Run",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="failed",
            install_method="winutil-pinned",
            notes=f"{type(exc).__name__}: {exc}",
        )
        console.print(f"  [failed] WinUtil — {exc}")
        return
    finally:
        script_path.unlink(missing_ok=True)
        config_path.unlink(missing_ok=True)

    tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-2000:]
    if proc.returncode == 0:
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="installed",
            install_method="winutil-pinned",
            notes=f"pinned={WINUTIL_TAG}\n{tail}"[:2000] if tail else f"pinned={WINUTIL_TAG}",
        )
        console.print(f"  [done] WinUtil ({WINUTIL_TAG})")
        return

    manifest.record_tool(
        tool="ctt-winutil", layer="sanitize", status="failed",
        install_method="winutil-pinned",
        notes=f"exit {proc.returncode}: {tail}",
    )
    console.print(f"  [failed] WinUtil (exit {proc.returncode})")


def _resolve_live_config(ctx: InstallContext) -> tuple[Path, bool]:
    """Return ``(config_path, is_temp)`` for the live path.

    Tries the live preset fetch first; falls back to the static local JSON
    when offline.  This is the ``--winutil-latest`` path, used only on
    explicit opt-in.
    """
    preset_key = getattr(ctx, "sanitation_preset", "Minimal") or "Minimal"
    try:
        from core.winutil_presets import get_tweaks_for_preset
        tweaks = get_tweaks_for_preset(preset_key, latest=True, timeout=6.0)
        if tweaks:
            return _write_preset_config(tweaks), True
    except Exception:
        pass
    from core.install_context import winutil_config_path_for_preset
    return winutil_config_path_for_preset(ctx.repo_root, preset_key), False


def _run_winutil_live(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
    preset_name: str,
) -> None:
    console.print(
        "  [caution] --winutil-latest: downloading and executing the live "
        "CTT WinUtil script from christitus.com with NO integrity check."
    )
    config_path, is_temp = _resolve_live_config(ctx)
    if not config_path.is_file():
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="failed",
            install_method="winutil-live",
            notes=f"Config not found: {config_path}",
        )
        console.print(f"  [failed] WinUtil — config not found: {config_path}")
        return

    cfg = str(config_path).replace("'", "''")
    ps = (
        "$ErrorActionPreference = 'Stop'; "
        f"$config = '{cfg}'; "
        "iex \"& { $(irm 'https://christitus.com/win') } -Config $config -Run\""
    )
    console.print(
        f"  [installing] WinUtil (CTT live, unpinned) — preset: {preset_name} — "
        "this may take several minutes …"
    )
    try:
        proc = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=7200.0,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="failed",
            install_method="winutil-live",
            notes=f"{type(exc).__name__}: {exc}",
        )
        console.print(f"  [failed] WinUtil — {exc}")
        return
    finally:
        if is_temp:
            config_path.unlink(missing_ok=True)

    tail = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()[-2000:]
    if proc.returncode == 0:
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="installed",
            install_method="winutil-live",
            notes=tail or "unpinned live run",
        )
        console.print("  [done] WinUtil (live)")
        return

    manifest.record_tool(
        tool="ctt-winutil", layer="sanitize", status="failed",
        install_method="winutil-live",
        notes=f"exit {proc.returncode}: {tail}",
    )
    console.print(f"  [failed] WinUtil (exit {proc.returncode})")


def run_sanitize(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    """Invoke Chris Titus WinUtil (opt-in: ``ctx.run_sanitation``)."""
    console.print("[bold]Layer 1 — Windows sanitization[/bold]")
    preset_name = getattr(ctx, "sanitation_preset", "Minimal") or "Minimal"
    latest = bool(getattr(ctx, "winutil_latest", False))
    method_label = "winutil-live" if latest else "winutil-pinned"

    if not ctx.run_sanitation:
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="skipped",
            install_method=method_label,
            notes="Sanitation not requested (pass --run-sanitation to enable).",
        )
        console.print("  [skipped] WinUtil — use --run-sanitation to enable (preset: none)")
        return

    if ctx.dry_run:
        planned_note = (
            f"Would invoke live CTT WinUtil with preset '{preset_name}' (unpinned, no integrity check)."
            if latest
            else f"Would invoke pinned CTT WinUtil with preset '{preset_name}' (hash-verified)."
        )
        manifest.record_tool(
            tool="ctt-winutil", layer="sanitize", status="planned",
            install_method=method_label,
            notes=planned_note,
        )
        mode = "live unpinned" if latest else "pinned"
        console.print(f"  [planned] WinUtil — dry-run (preset: {preset_name}, {mode})")
        return

    if latest:
        _run_winutil_live(ctx, manifest, console, preset_name)
    else:
        _run_winutil_pinned(ctx, manifest, console, preset_name)
