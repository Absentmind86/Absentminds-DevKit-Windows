"""AM-DevKit — full layer orchestration (CLI; invoked by Phase 3 GUI or directly).

Run from repository root::

    python -m core.installer --dry-run --profile systems
    python -m core.installer --absentmind --dry-run

``sys.path`` is adjusted so ``core.*`` and ``scripts.*`` imports resolve.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from rich.console import Console
from rich.theme import Theme

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from core import devops, editors, extras, finalize, infrastructure, languages, ml_stack, preflight, sanitize, sandbox, utilities  # noqa: E402
from core.install_context import InstallContext, merge_profile_args  # noqa: E402
from core.manifest import Manifest  # noqa: E402
from core.system_scan import build_system_profile, write_system_profile  # noqa: E402

LayerFn = Callable[[InstallContext, Manifest, Console], None]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_layer0_scan(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    console.print("[bold]Layer 0 — System scan[/bold]")
    if ctx.dry_run:
        profile = build_system_profile()
        manifest.record_tool(
            tool="system-scan",
            layer="layer0",
            status="planned",
            install_method="internal",
            notes="Dry-run: WMI scan executed; system-profile.json not written.",
        )
        console.print("  [planned] system-profile.json — dry-run")
        ctx.system_profile.clear()
        ctx.system_profile.update(profile)
        return

    profile = build_system_profile()
    write_system_profile(profile, ctx.system_profile_path)
    manifest.record_tool(
        tool="system-scan",
        layer="layer0",
        status="installed",
        install_method="internal",
        notes=str(ctx.system_profile_path),
    )
    console.print(f"  [done] system-profile.json -> {ctx.system_profile_path}")
    ctx.system_profile.clear()
    ctx.system_profile.update(profile)


def _run_layer0_from_file(ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    console.print("[bold]Layer 0 — System scan[/bold]")
    data = _load_json(ctx.system_profile_path)
    ctx.system_profile.clear()
    ctx.system_profile.update(data)
    manifest.record_tool(
        tool="system-scan",
        layer="layer0",
        status="skipped",
        install_method="file",
        notes=f"Loaded {ctx.system_profile_path}",
    )
    console.print(f"  [skipped] Loaded profile from {ctx.system_profile_path}")


def _safe_layer(name: str, fn: LayerFn, ctx: InstallContext, manifest: Manifest, console: Console) -> None:
    try:
        fn(ctx, manifest, console)
    except Exception as exc:  # noqa: BLE001 — install must never abort whole run
        manifest.record_tool(
            tool=f"{name}-uncaught",
            layer=name,
            status="failed",
            install_method="internal",
            notes=f"{type(exc).__name__}: {exc}",
        )
        console.print(f"[red]Layer {name} raised {type(exc).__name__}: {exc}[/red]")


def run_install(ctx: InstallContext, console: Console, *, layer0_fn: LayerFn | None = None) -> int:
    layer0: LayerFn = layer0_fn or _run_layer0_scan
    manifest = Manifest(ctx.manifest_path, devkit_version=ctx.devkit_version)
    manifest.record_tool(
        tool="install-start",
        layer="meta",
        status="installed",
        install_method="cli",
        notes=(
            f"profiles={ctx.profiles!r} dry_run={ctx.dry_run} "
            f"assume_yes={ctx.assume_yes} skip_summary={ctx.skip_summary} "
            f"sanitation_preset={getattr(ctx, 'sanitation_preset', 'minimal')!r}"
        ),
    )

    early_steps: list[tuple[str, LayerFn]] = [
        ("preflight", preflight.run_preflight),
        ("layer0", layer0),
    ]
    for title, fn in early_steps:
        console.rule(f"[bold cyan]{title}[/bold cyan]")
        _safe_layer(title, fn, ctx, manifest, console)
        manifest.flush()

    from core.pre_install_summary import show_pre_install_summary

    show_pre_install_summary(ctx, console)

    rest_steps: list[tuple[str, LayerFn]] = [
        ("sanitize", sanitize.run_sanitize),
        ("infrastructure", infrastructure.run_infrastructure),
        ("editors", editors.run_editors),
        ("languages", languages.run_languages),
        ("ml_stack", ml_stack.run_ml_stack),
        ("devops", devops.run_devops),
        ("utilities", utilities.run_utilities),
        ("extras", extras.run_extras),
        ("sandbox", sandbox.run_sandbox),
    ]
    for title, fn in rest_steps:
        console.rule(f"[bold cyan]{title}[/bold cyan]")
        _safe_layer(title, fn, ctx, manifest, console)
        manifest.flush()

    console.rule("[bold cyan]finalize[/bold cyan]")
    _safe_layer("finalize", finalize.run_finalize, ctx, manifest, console)
    return 0


def _configure_stdio_utf8() -> None:
    """Avoid ``UnicodeEncodeError`` on legacy Windows code pages (cp1252)."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def main(argv: list[str] | None = None) -> int:
    _configure_stdio_utf8()
    parser = argparse.ArgumentParser(description="AM-DevKit installer (CLI).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip destructive writes where possible; winget/WinUtil/pip become planned/skipped.",
    )
    parser.add_argument(
        "--absentmind",
        action="store_true",
        help="Select all curated profiles (equivalent to checking every profile box).",
    )
    parser.add_argument(
        "--profile",
        action="append",
        default=[],
        metavar="NAME",
        help="Profile id (repeatable): ai-ml, web-fullstack, systems, game-dev, hardware-robotics, extras.",
    )
    parser.add_argument(
        "--run-sanitation",
        action="store_true",
        help="Invoke CTT WinUtil (potentially disruptive). Config chosen via --sanitation-preset.",
    )
    parser.add_argument(
        "--sanitation-preset",
        choices=("minimal", "standard"),
        default="minimal",
        help="WinUtil JSON: minimal (4 tweaks) or standard (CTT preset.json 'Standard' set, 13 tweaks).",
    )
    parser.add_argument(
        "--skip-restore-point",
        action="store_true",
        help="Skip Checkpoint-Computer preflight step.",
    )
    parser.add_argument(
        "--install-ml-wheels",
        action="store_true",
        help="When ai-ml is selected, also pip install torch/torchvision/torchaudio.",
    )
    parser.add_argument(
        "--install-ml-base",
        action="store_true",
        help="When ai-ml is selected, pip install numpy pandas matplotlib scikit-learn jupyter ipython.",
    )
    parser.add_argument(
        "--enable-wsl",
        action="store_true",
        help="Run DISM to enable WSL + VirtualMachinePlatform (may require reboot; run elevated).",
    )
    parser.add_argument(
        "--wsl-distro",
        default="Ubuntu",
        metavar="NAME",
        help="With --enable-wsl, distro name for `wsl --install -d` (default: Ubuntu).",
    )
    parser.add_argument(
        "--wsl-skip-default-distro",
        action="store_true",
        help="With --enable-wsl, skip `wsl --install` (DISM only).",
    )
    parser.add_argument(
        "--skip-dotfiles",
        action="store_true",
        help="Do not copy templates/dotfiles into the user profile.",
    )
    parser.add_argument(
        "--skip-rust",
        action="store_true",
        help="Skip rustup + Rust toolchain install even when a profile would request it.",
    )
    parser.add_argument(
        "--reuse-system-profile",
        type=Path,
        default=None,
        help="Skip WMI scan; load existing system-profile.json from this path.",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="Do not prompt after the pre-install summary (non-dry-run).",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip the pre-install summary panel and confirmation.",
    )
    parser.add_argument(
        "--exclude-catalog-tool",
        action="append",
        default=[],
        metavar="TOOL",
        help="Skip this catalog tool id even if a profile would install it (repeatable).",
    )
    args = parser.parse_args(argv)

    profiles = merge_profile_args(absentmind=args.absentmind, profiles=list(args.profile))
    if not profiles:
        profiles = ["systems"]

    console = Console(theme=Theme({"repr.str": "green"}), legacy_windows=False)

    system_profile_path = (_REPO_ROOT / "system-profile.json").resolve()
    system_profile: dict[str, Any] = {}
    if args.reuse_system_profile is not None:
        system_profile_path = args.reuse_system_profile.resolve()
        system_profile = _load_json(system_profile_path)

    wsl_default: str | None = None
    if args.enable_wsl and not args.wsl_skip_default_distro:
        wsl_default = (args.wsl_distro or "Ubuntu").strip() or "Ubuntu"

    catalog_excludes = frozenset(
        str(x).strip() for x in (args.exclude_catalog_tool or []) if str(x).strip()
    )

    spreset: str = (args.sanitation_preset or "minimal").strip().lower()
    if spreset not in ("minimal", "standard"):
        spreset = "minimal"

    ctx = InstallContext(
        repo_root=_REPO_ROOT,
        system_profile_path=system_profile_path,
        system_profile=system_profile,
        profiles=profiles,
        dry_run=args.dry_run,
        run_sanitation=args.run_sanitation,
        sanitation_preset=spreset,
        skip_restore_point=args.skip_restore_point,
        install_ml_wheels=args.install_ml_wheels,
        manifest_path=_REPO_ROOT / "devkit-manifest.json",
        report_path=_REPO_ROOT / "post-install-report.html",
        enable_wsl=args.enable_wsl,
        wsl_default_distro=wsl_default,
        install_ml_base=args.install_ml_base,
        seed_dotfiles=not args.skip_dotfiles,
        assume_yes=args.yes,
        skip_summary=args.skip_summary,
        catalog_exclude_tools=catalog_excludes,
        skip_rust=args.skip_rust,
    )

    console.print(
        f"[bold]AM-DevKit installer[/bold] - profiles: [cyan]{', '.join(profiles)}[/cyan]"
        + (" [yellow](dry-run)[/yellow]" if args.dry_run else "")
    )

    layer0_fn: LayerFn | None = _run_layer0_from_file if args.reuse_system_profile else None
    run_install(ctx, console, layer0_fn=layer0_fn)
    console.print(f"\n[green]Report:[/green] {ctx.report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
