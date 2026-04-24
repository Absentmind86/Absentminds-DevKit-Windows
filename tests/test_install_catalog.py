"""Unit tests for core/install_catalog.py — profile matching, counts, disk estimates."""

from __future__ import annotations

from core.install_catalog import (
    P_EXTRAS,
    P_WEB,
    WINGET_CATALOG,
    WingetCatalogEntry,
    catalog_entries_for_layer,
    count_winget_actions,
    estimate_catalog_disk_mb,
    estimate_tool_disk_mb,
    get_detector,
)

# ---------------------------------------------------------------------------
# WingetCatalogEntry.applies_to
# ---------------------------------------------------------------------------

class TestAppliesTo:
    def test_profiles_none_always_applies(self):
        entry = WingetCatalogEntry(
            tool="t", winget_id="X.X", layer="infrastructure",
            profiles=None, detect_exe="t.exe",
        )
        assert entry.applies_to(set()) is True
        assert entry.applies_to({"ai-ml"}) is True

    def test_profile_match(self):
        entry = WingetCatalogEntry(
            tool="t", winget_id="X.X", layer="languages",
            profiles=P_WEB, detect_exe="t.exe",
        )
        assert entry.applies_to({"web-fullstack"}) is True
        assert entry.applies_to({"ai-ml"}) is False
        assert entry.applies_to(set()) is False

    def test_multi_profile_any_match(self):
        entry = WingetCatalogEntry(
            tool="t", winget_id="X.X", layer="devops",
            profiles=frozenset({"web-fullstack", "ai-ml"}), detect_exe="t.exe",
        )
        assert entry.applies_to({"ai-ml"}) is True
        assert entry.applies_to({"web-fullstack"}) is True
        assert entry.applies_to({"systems"}) is False


# ---------------------------------------------------------------------------
# catalog_entries_for_layer
# ---------------------------------------------------------------------------

class TestCatalogEntriesForLayer:
    def test_infrastructure_layer_nonempty(self):
        entries = catalog_entries_for_layer("infrastructure")
        assert len(entries) > 0
        assert all(e.layer == "infrastructure" for e in entries)

    def test_unknown_layer_empty(self):
        assert list(catalog_entries_for_layer("nonexistent")) == []

    def test_ml_stack_layer(self):
        entries = catalog_entries_for_layer("ml_stack")
        assert any(e.tool == "ollama" for e in entries)

    def test_extras_layer(self):
        entries = catalog_entries_for_layer("extras")
        assert all(e.profiles == P_EXTRAS for e in entries)


# ---------------------------------------------------------------------------
# count_winget_actions
# ---------------------------------------------------------------------------

class TestCountWingetActions:
    def test_no_profiles_counts_profiles_none_only(self):
        count = count_winget_actions([])
        # Only entries with profiles=None should match an empty selection.
        none_count = sum(1 for e in WINGET_CATALOG if e.profiles is None)
        assert count == none_count

    def test_ai_ml_profile_includes_extras(self):
        count_ai = count_winget_actions(["ai-ml"])
        count_none = count_winget_actions([])
        assert count_ai > count_none

    def test_all_profiles_gives_max(self):
        all_profiles = ["ai-ml", "web-fullstack", "systems", "game-dev", "hardware-robotics"]
        count_all = count_winget_actions(all_profiles)
        count_one = count_winget_actions(["ai-ml"])
        assert count_all >= count_one

    def test_catalog_excludes_reduce_count(self):
        base = count_winget_actions(["ai-ml"])
        with_excl = count_winget_actions(["ai-ml"], catalog_excludes=["ollama"])
        assert with_excl == base - 1

    def test_exclude_nonexistent_tool_no_change(self):
        base = count_winget_actions(["ai-ml"])
        with_excl = count_winget_actions(["ai-ml"], catalog_excludes=["does-not-exist"])
        assert with_excl == base

    def test_extras_not_included_without_extras_profile(self):
        all_core = ["ai-ml", "web-fullstack", "systems", "game-dev", "hardware-robotics"]
        count_without_extras = count_winget_actions(all_core)
        count_with_extras = count_winget_actions(all_core + ["extras"])
        assert count_with_extras > count_without_extras


# ---------------------------------------------------------------------------
# estimate_tool_disk_mb / estimate_catalog_disk_mb
# ---------------------------------------------------------------------------

class TestDiskEstimates:
    def test_known_tool_returns_defined_value(self):
        # docker-desktop is 1200 MB in TOOL_DISK_MB
        assert estimate_tool_disk_mb("docker-desktop") == 1200

    def test_unknown_tool_returns_default(self):
        assert estimate_tool_disk_mb("some-imaginary-tool") == 100

    def test_empty_profiles_positive_estimate(self):
        mb = estimate_catalog_disk_mb([])
        assert mb > 0

    def test_more_profiles_more_disk(self):
        ai_only = estimate_catalog_disk_mb(["ai-ml"])
        all_profiles = estimate_catalog_disk_mb(
            ["ai-ml", "web-fullstack", "systems", "game-dev", "hardware-robotics"]
        )
        assert all_profiles > ai_only

    def test_exclude_reduces_estimate(self):
        base = estimate_catalog_disk_mb(["web-fullstack", "ai-ml"])
        excl = estimate_catalog_disk_mb(
            ["web-fullstack", "ai-ml"], catalog_excludes=["docker-desktop"]
        )
        assert excl < base


# ---------------------------------------------------------------------------
# Catalog integrity: uniqueness and required fields
# ---------------------------------------------------------------------------

class TestCatalogIntegrity:
    def test_tool_names_unique(self):
        names = [e.tool for e in WINGET_CATALOG]
        assert len(names) == len(set(names)), "Duplicate tool names in WINGET_CATALOG"

    def test_winget_ids_unique(self):
        ids = [e.winget_id for e in WINGET_CATALOG]
        assert len(ids) == len(set(ids)), "Duplicate winget IDs in WINGET_CATALOG"

    def test_all_entries_have_nonempty_detect_exe(self):
        for e in WINGET_CATALOG:
            assert e.detect_exe, f"{e.tool} has empty detect_exe"

    def test_known_bootstrap_tools_absent_from_catalog(self):
        """Git/Scoop/OpenSSH are bootstrap prereqs — must not be in catalog."""
        catalog_tools = {e.tool for e in WINGET_CATALOG}
        for bootstrap in ("git", "scoop", "openssh"):
            assert bootstrap not in catalog_tools, (
                f"'{bootstrap}' should not be in WINGET_CATALOG (it is a bootstrap prereq)"
            )

    def test_get_detector_returns_callable(self):
        for entry in WINGET_CATALOG:
            detector = get_detector(entry)
            assert callable(detector), f"get_detector returned non-callable for {entry.tool}"
