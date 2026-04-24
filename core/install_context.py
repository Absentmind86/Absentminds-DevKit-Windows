"""Shared install context passed through Phase 2 layer modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    devkit_version: str = "0.8.0-phase4"
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
    # Opt into the live (unpinned) CTT WinUtil script. Default is the hash-verified pinned release.
    winutil_latest: bool = False
    # Skip rustup + rust toolchain install even when a profile would request it.
    skip_rust: bool = False

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
    """JSON file passed to CTT WinUtil ``-Config`` for the chosen sanitation preset."""
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
