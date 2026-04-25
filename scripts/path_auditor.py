"""PATH conflict detection and fingerprinting (Phase 2).

Scans ``PATH`` in precedence order. For each directory, collects executable
filenames (``.exe``, ``.bat``, ``.cmd``, ``.ps1``). The first occurrence of a
basename wins; later directories that expose the same name are conflicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

_WIN_EXECUTABLE_SUFFIXES: Final[frozenset[str]] = frozenset({".exe", ".bat", ".cmd", ".ps1"})

# Basenames that Windows itself ships in multiple locations by design.
# Reporting these as conflicts is pure noise.
_WINDOWS_INTERNAL_DUPLICATES: Final[frozenset[str]] = frozenset({
    "notepad.exe",
    "write.exe",
    "winver.exe",
    "calc.exe",
    "mspaint.exe",
    "snippingtool.exe",
})

# WindowsApps stubs redirect to the Microsoft Store when the real app is absent.
# When a real tool wins over a stub, that is the intended and desirable outcome.
_WINDOWS_APPS_MARKER = "\\microsoft\\windowsapps\\"

# Known benign conflicts that occur when a full dev stack is installed.
# These are expected shadows with no functional impact; explain rather than alarm.
_KNOWN_BENIGN_CONFLICTS: Final[dict[str, str]] = {
    "klist.exe": (
        "Expected: JDK ships its own klist.exe (Kerberos ticket tool) which shadows "
        "the copy in C:\\Windows\\System32. Both do the same job; no action needed."
    ),
    "kubectl.exe": (
        "Expected: Docker Desktop bundles kubectl alongside the winget-installed copy. "
        "Both binaries are equivalent; Docker's copy wins by PATH order. No action needed."
    ),
    "code-tunnel.exe": (
        "Expected: VS Code and Cursor both ship code-tunnel.exe. VS Code's copy takes "
        "precedence but both editors work correctly. No action needed."
    ),
}

# Inno Setup places a generic uninstaller in every app's private directory.
# These are never run from PATH; "conflicts" between them are false positives.
def _is_inno_uninstaller(basename: str) -> bool:
    import re
    return bool(re.fullmatch(r"unins\d+\.exe", basename.lower()))


def _iter_path_directories() -> list[Path]:
    raw = os.environ.get("PATH", "")
    parts = [p.strip() for p in raw.split(os.pathsep) if p.strip()]
    return [Path(p) for p in parts]


def _executables_in_dir(directory: Path) -> Iterator[tuple[str, Path]]:
    """Yield ``(lowercase_basename, path)`` for each executable-looking file."""
    if not directory.is_dir():
        return
    try:
        for entry in directory.iterdir():
            if not entry.is_file():
                continue
            suf = entry.suffix.lower()
            if suf not in _WIN_EXECUTABLE_SUFFIXES:
                continue
            yield entry.name.lower(), entry
    except OSError:
        return


def audit_path() -> dict[str, Any]:
    """Return structured audit: ordered entries, conflicts, fingerprint."""
    dirs = _iter_path_directories()
    winner: dict[str, str] = {}
    ordered_entries: list[dict[str, Any]] = []
    basename_locations: defaultdict[str, list[str]] = defaultdict(list)

    for d in dirs:
        display = str(d)
        ordered_entries.append({"directory": display, "exists": d.is_dir()})
        if not d.is_dir():
            continue
        for base, entry in _executables_in_dir(d):
            try:
                full = str(entry.resolve())
            except OSError:
                full = str(entry)
            basename_locations[base].append(full)
            if base not in winner:
                winner[base] = full

    conflicts: list[dict[str, Any]] = []
    for base, paths in basename_locations.items():
        unique = list(dict.fromkeys(paths))
        if len(unique) <= 1:
            continue

        # Suppress known false positives
        if base in _WINDOWS_INTERNAL_DUPLICATES:
            continue
        if _is_inno_uninstaller(base):
            continue
        w = winner.get(base, unique[0])
        losers = [p for p in unique if p != w]
        # Suppress when every losing path is a WindowsApps stub — winner is correct.
        if all(_WINDOWS_APPS_MARKER in p.lower() for p in losers):
            continue

        hint = _KNOWN_BENIGN_CONFLICTS.get(
            base,
            "Earlier PATH entry shadows this name. Remove duplicates or "
            "reorder PATH so the intended toolchain (Scoop/pyenv) wins.",
        )
        conflicts.append(
            {
                "basename": base,
                "winner": w,
                "alternates": losers,
                "hint": hint,
            }
        )

    fingerprint_source = json.dumps(
        {"path": [e["directory"] for e in ordered_entries]},
        separators=(",", ":"),
    )
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()

    return {
        "path_directories": ordered_entries,
        "conflicts": conflicts,
        "conflict_count": len(conflicts),
        "path_fingerprint_sha256": fingerprint,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit PATH for duplicate basenames.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON to stdout instead of a short summary.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write full audit JSON to this file.",
    )
    args = parser.parse_args()
    data = audit_path()
    if args.output is not None:
        args.output.write_text(json.dumps(data, indent=2), encoding="utf-8")
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    print(f"PATH directories: {len(data['path_directories'])}")
    print(f"Conflicts: {data['conflict_count']}")
    print(f"Fingerprint SHA256: {data['path_fingerprint_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
