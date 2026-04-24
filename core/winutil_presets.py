"""CTT WinUtil preset registry.

Default path is the **pinned** preset.json (SHA256-verified) from the release
AM-DevKit was tested against.  When the user opts into ``--winutil-latest``,
this module fetches the live ``main`` branch preset.json instead — no
integrity check, faithful to the GUI / CLI disclaimer.

Falls back to hardcoded Minimal / Standard when all network paths fail so the
GUI can still render a sensible radio list offline.

Adding a polished description for a new preset only requires adding an entry
to CURATED_DESCRIPTIONS — unknown presets get a generic fallback automatically.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

# Edit this dict to control what users see for known presets.
# Unknown/future presets automatically get _FALLBACK_DESCRIPTION.
CURATED_DESCRIPTIONS: dict[str, str] = {
    "Minimal": (
        "Light privacy cleanup — removes Microsoft's suggested app ads, disables "
        "unnecessary background services, and turns off basic telemetry. "
        "Safe for most users and fully reversible via System Restore."
    ),
    "Standard": (
        "Full privacy and performance tuning — everything in Minimal, plus: disables "
        "Activity History, GameDVR, location tracking, disk telemetry, and "
        "PowerShell 7 telemetry; clears temp files; and adds End Task to the taskbar. "
        "Recommended for most power users."
    ),
}

_FALLBACK_DESCRIPTION = "Additional preset from CTT WinUtil."


@dataclass
class PresetInfo:
    key: str
    description: str
    tweaks: list[str] = field(default_factory=list)

    @property
    def tweak_count(self) -> int:
        return len(self.tweaks)


def _parse_preset_json(data: dict[str, Any]) -> list[PresetInfo]:
    result: list[PresetInfo] = []
    for key, tweaks in data.items():
        result.append(PresetInfo(
            key=key,
            description=CURATED_DESCRIPTIONS.get(key, _FALLBACK_DESCRIPTION),
            tweaks=tweaks if isinstance(tweaks, list) else [],
        ))
    _order = list(CURATED_DESCRIPTIONS.keys())
    result.sort(key=lambda p: (
        _order.index(p.key) if p.key in _order else len(_order),
        p.key,
    ))
    return result


def fetch_presets(*, latest: bool = False, timeout: float = 30.0) -> list[PresetInfo]:
    """Fetch preset list. Default: pinned release (SHA256-verified).

    When *latest* is True, fetch the live ``main`` branch preset.json with no
    integrity check — this is the opt-in unpinned path surfaced through the
    ``--winutil-latest`` flag / GUI toggle.
    """
    import json

    if latest:
        import urllib.request
        from core.winutil_pin import WINUTIL_PRESET_LIVE_URL
        with urllib.request.urlopen(WINUTIL_PRESET_LIVE_URL, timeout=timeout) as resp:
            data: dict[str, Any] = json.loads(resp.read().decode())
        return _parse_preset_json(data)

    from core.winutil_pin import (
        WINUTIL_PRESET_SHA256,
        WINUTIL_PRESET_URL,
        download_verified,
    )
    path = download_verified(
        WINUTIL_PRESET_URL,
        WINUTIL_PRESET_SHA256,
        timeout=timeout,
        suffix=".json",
    )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    finally:
        path.unlink(missing_ok=True)
    return _parse_preset_json(data)


def fallback_presets() -> list[PresetInfo]:
    """Hardcoded Minimal + Standard for GUI display when all network paths fail."""
    return [
        PresetInfo(key="Minimal", description=CURATED_DESCRIPTIONS["Minimal"]),
        PresetInfo(key="Standard", description=CURATED_DESCRIPTIONS["Standard"]),
    ]


def get_tweaks_for_preset(
    preset_key: str,
    *,
    latest: bool = False,
    timeout: float = 30.0,
) -> list[str]:
    """Return the WPFTweaks list for *preset_key* (case-insensitive), or [] on failure."""
    try:
        presets = fetch_presets(latest=latest, timeout=timeout)
        key_lower = preset_key.strip().lower()
        for p in presets:
            if p.key.lower() == key_lower:
                return p.tweaks
    except Exception:
        pass
    return []
