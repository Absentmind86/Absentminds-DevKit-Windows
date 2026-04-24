#!/usr/bin/env python3
"""Verify every winget ID in WINGET_CATALOG resolves against the winget source.

Run weekly (or before a release) to catch IDs that have been renamed or removed
by the upstream publisher. Requires winget to be installed and online.

Usage:
    python scripts/smoke-test-winget-ids.py [--timeout SECS]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from core.install_catalog import WINGET_CATALOG  # noqa: E402


def _check_id(winget_id: str, timeout: int) -> tuple[bool, str]:
    """Return (ok, reason). Runs `winget show --id <id> --exact`."""
    try:
        result = subprocess.run(
            [
                "winget", "show",
                "--id", winget_id,
                "--exact",
                "--accept-source-agreements",
                "--disable-interactivity",
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return True, "ok"
        stderr = result.stderr.strip() or result.stdout.strip()
        first_line = stderr.splitlines()[0] if stderr else f"exit {result.returncode}"
        return False, first_line
    except subprocess.TimeoutExpired:
        return False, f"timeout after {timeout}s"
    except FileNotFoundError:
        return False, "winget not found — install App Installer from the Microsoft Store"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--timeout", type=int, default=20,
        metavar="SECS", help="Per-ID winget query timeout (default: 20s)"
    )
    parser.add_argument(
        "--layer", metavar="LAYER",
        help="Limit check to a specific catalog layer (e.g. utilities, editors)"
    )
    args = parser.parse_args()

    entries = list(WINGET_CATALOG)
    if args.layer:
        entries = [e for e in entries if e.layer == args.layer]
        if not entries:
            print(f"No catalog entries found for layer '{args.layer}'.")
            return 1

    print(f"AM-DevKit — winget ID smoke test ({len(entries)} IDs)")
    print(f"Timeout per ID: {args.timeout}s")
    print("=" * 70)

    passed: list[str] = []
    failed: list[tuple[str, str, str]] = []  # (tool, winget_id, reason)

    for entry in entries:
        ok, reason = _check_id(entry.winget_id, args.timeout)
        icon = "[OK]  " if ok else "[FAIL]"
        layer_tag = f"[{entry.layer}]"
        print(f"  {icon} {layer_tag:16s} {entry.winget_id:45s}  {reason if not ok else ''}")
        if ok:
            passed.append(entry.winget_id)
        else:
            failed.append((entry.tool, entry.winget_id, reason))

    print("=" * 70)
    print(f"Passed: {len(passed)}/{len(entries)}")

    if failed:
        print(f"\nFailed IDs ({len(failed)}) — update core/install_catalog.py:")
        for tool, winget_id, reason in failed:
            print(f"  tool={tool!r}  id={winget_id!r}")
            print(f"    reason: {reason}")
        return 1

    print("\nAll winget IDs resolved successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
