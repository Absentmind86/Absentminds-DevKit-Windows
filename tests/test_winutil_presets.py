"""Unit tests for core/winutil_presets.py — fetch/fallback/ordering logic."""

from __future__ import annotations

import json

from core.winutil_presets import (
    CURATED_DESCRIPTIONS,
    PresetInfo,
    _parse_preset_json,
    fallback_presets,
    get_tweaks_for_preset,
)

# ---------------------------------------------------------------------------
# _parse_preset_json
# ---------------------------------------------------------------------------

class TestParsePresetJson:
    def test_parses_known_presets(self):
        data = {
            "Minimal": ["WPFTweak1", "WPFTweak2"],
            "Standard": ["WPFTweak1", "WPFTweak2", "WPFTweak3"],
        }
        presets = _parse_preset_json(data)
        assert len(presets) == 2
        keys = [p.key for p in presets]
        assert "Minimal" in keys
        assert "Standard" in keys

    def test_known_presets_ordered_first(self):
        data = {
            "Standard": ["T1"],
            "Custom": ["T2"],
            "Minimal": ["T3"],
        }
        presets = _parse_preset_json(data)
        assert presets[0].key == "Minimal"
        assert presets[1].key == "Standard"
        assert presets[2].key == "Custom"

    def test_curated_description_applied(self):
        data = {"Minimal": ["T1"]}
        presets = _parse_preset_json(data)
        assert presets[0].description == CURATED_DESCRIPTIONS["Minimal"]

    def test_unknown_preset_gets_fallback_description(self):
        data = {"ExoticPreset": ["T1", "T2"]}
        presets = _parse_preset_json(data)
        assert presets[0].description != ""
        assert presets[0].key == "ExoticPreset"

    def test_tweak_count(self):
        data = {"Minimal": ["A", "B", "C"]}
        presets = _parse_preset_json(data)
        assert presets[0].tweak_count == 3

    def test_non_list_tweaks_become_empty(self):
        data = {"Minimal": "not-a-list"}
        presets = _parse_preset_json(data)
        assert presets[0].tweaks == []

    def test_empty_dict(self):
        presets = _parse_preset_json({})
        assert presets == []


# ---------------------------------------------------------------------------
# PresetInfo
# ---------------------------------------------------------------------------

class TestPresetInfo:
    def test_tweak_count_property(self):
        p = PresetInfo(key="Test", description="desc", tweaks=["A", "B"])
        assert p.tweak_count == 2

    def test_tweak_count_empty(self):
        p = PresetInfo(key="Test", description="desc")
        assert p.tweak_count == 0


# ---------------------------------------------------------------------------
# fallback_presets
# ---------------------------------------------------------------------------

class TestFallbackPresets:
    def test_returns_minimal_and_standard(self):
        presets = fallback_presets()
        keys = [p.key for p in presets]
        assert "Minimal" in keys
        assert "Standard" in keys

    def test_descriptions_nonempty(self):
        for p in fallback_presets():
            assert p.description

    def test_returns_preset_info_instances(self):
        for p in fallback_presets():
            assert isinstance(p, PresetInfo)


# ---------------------------------------------------------------------------
# get_tweaks_for_preset (mocked network)
# ---------------------------------------------------------------------------

class TestGetTweaksForPreset:
    def _mock_fetch(self, monkeypatch, data: dict) -> None:
        """Patch fetch_presets to return parsed presets from *data*."""
        presets = _parse_preset_json(data)
        monkeypatch.setattr("core.winutil_presets.fetch_presets", lambda **kw: presets)

    def test_returns_tweaks_for_known_key(self, monkeypatch):
        self._mock_fetch(monkeypatch, {"Minimal": ["T1", "T2"]})
        result = get_tweaks_for_preset("Minimal")
        assert result == ["T1", "T2"]

    def test_case_insensitive_key_lookup(self, monkeypatch):
        self._mock_fetch(monkeypatch, {"Minimal": ["T1"]})
        assert get_tweaks_for_preset("minimal") == ["T1"]
        assert get_tweaks_for_preset("MINIMAL") == ["T1"]

    def test_missing_key_returns_empty(self, monkeypatch):
        self._mock_fetch(monkeypatch, {"Minimal": ["T1"]})
        assert get_tweaks_for_preset("NonExistent") == []

    def test_network_failure_returns_empty(self, monkeypatch):
        def _fail(**kw):
            raise OSError("network down")
        monkeypatch.setattr("core.winutil_presets.fetch_presets", _fail)
        assert get_tweaks_for_preset("Minimal") == []

    def test_returns_list(self, monkeypatch):
        self._mock_fetch(monkeypatch, {"Standard": ["WPFTweakA", "WPFTweakB"]})
        result = get_tweaks_for_preset("Standard")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# fetch_presets (mocked network — pinned path)
# ---------------------------------------------------------------------------

class TestFetchPresets:
    def test_pinned_path_verifies_and_parses(self, monkeypatch, tmp_path):
        """Stub download_verified to return a tmp JSON file; no real network."""
        preset_data = {"Minimal": ["T1"], "Standard": ["T1", "T2"]}
        tmp_json = tmp_path / "preset.json"
        tmp_json.write_text(json.dumps(preset_data), encoding="utf-8")

        import core.winutil_pin as pin_module

        monkeypatch.setattr(
            pin_module, "download_verified",
            lambda url, sha, *, timeout=30.0, suffix=".json": tmp_json,
        )
        from core.winutil_presets import fetch_presets
        presets = fetch_presets(latest=False)
        keys = [p.key for p in presets]
        assert "Minimal" in keys
        assert "Standard" in keys

    def test_latest_path_fetches_live(self, monkeypatch, tmp_path):
        """Stub urllib.request.urlopen to return a BytesIO of preset JSON."""
        preset_data = {"Minimal": ["T1"]}
        encoded = json.dumps(preset_data).encode()

        class _FakeResp:
            def read(self): return encoded
            def __enter__(self): return self
            def __exit__(self, *a): pass

        import urllib.request
        monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=30: _FakeResp())

        from core.winutil_presets import fetch_presets
        presets = fetch_presets(latest=True)
        assert any(p.key == "Minimal" for p in presets)
