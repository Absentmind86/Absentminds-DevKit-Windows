"""Shared install context passed through Phase 2 layer modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_VERSION_FILE = Path(__file__).resolve().parents[1] / "VERSION"


def _read_version() -> str:
    """Read version from repo-root VERSION file; fall back to hard-coded string."""
    try:
        return _VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "1.0.0"


@dataclass
class InstallContext:
    """Mutable state for one installer run."""

    repo_root: Path
    system_profile_path: Path
    system_profile: dict[str, Any]
    profiles: list[str]
    dry_run: bool
    run_sanitation: bool
    skip_restore_point: bool
    install_ml_wheels: bool
    manifest_path: Path
    report_path: Path
    devkit_version: str = field(default_factory=_read_version)
    enable_wsl: bool = False
    # If set (e.g. "Ubuntu"), run `wsl --install -d` after DISM when enable_wsl is true.
    wsl_default_distro: str | None = None
    install_ml_base: bool = False
    seed_dotfiles: bool = True
    assume_yes: bool = False
    skip_summary: bool = False
    # Tools to skip even when profile gates match (Custom Mode / GUI exclusions).
    catalog_exclude_tools: frozenset[str] = field(default_factory=frozenset)
    # WinUtil preset key (e.g. "Minimal", "Standard"). Matched case-insensitively against upstream preset.json.
    sanitation_preset: str = "Minimal"
    # Skip rustup + rust toolchain install even when a profile would request it.
    skip_rust: bool = False
    # Set by ensure_wsl_prereq when DISM returns 3010 (reboot required). When true,
    # downstream WSL steps (e.g. `wsl --install -d <distro>`) are deferred with a
    # clear message instead of attempting to run on a half-enabled feature.
    wsl_reboot_required: bool = False

    def profile_selected(self, name: str) -> bool:
        """Return True if *name* is in the resolved profile list."""
        return name in self.profiles


def default_profiles_from_absentmind() -> list[str]:
    """Profile ids equivalent to Absentmind Mode (all stacks)."""
    return [
        "ai-ml",
        "web-fullstack",
        "systems",
        "game-dev",
        "hardware-robotics",
    ]


def winutil_config_path_for_preset(repo_root: Path, sanitation_preset: str) -> Path:
    """JSON config file listing tweaks for the chosen sanitation preset (used by pre-install summary)."""
    p = (sanitation_preset or "minimal").strip().lower()
    if p == "standard":
        return (repo_root / "config" / "am-devkit-winutil-standard.json").resolve()
    return (repo_root / "config" / "am-devkit-winutil.json").resolve()


def merge_profile_args(
    *,
    absentmind: bool,
    profiles: list[str],
) -> list[str]:
    """Resolve CLI profile flags into a deduplicated ordered list."""
    if absentmind:
        base = default_profiles_from_absentmind()
    else:
        base = list(profiles)
    seen: set[str] = set()
    out: list[str] = []
    for p in base:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out
