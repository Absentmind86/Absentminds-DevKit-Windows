"""Cross-platform routing smoke tests.

Tests assert that _get_pkg_id returns the right field for each OS, that choco
fallback is attempted only on Windows, and that brew_tap / linux_repo metadata
is present for tools that need it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from core.install_catalog import WINGET_CATALOG, CatalogEntry, catalog_entries_for_layer


# ---------------------------------------------------------------------------
# Helper: look up an entry by tool name
# ---------------------------------------------------------------------------

def _entry(name: str) -> CatalogEntry:
    for e in WINGET_CATALOG:
        if e.tool == name:
            return e
    raise KeyError(f"No catalog entry for tool {name!r}")


# ---------------------------------------------------------------------------
# _get_pkg_id dispatch
# ---------------------------------------------------------------------------

class TestGetPkgId:
    """Verify catalog_install._get_pkg_id returns the correct field per OS."""

    def _get(self, entry: CatalogEntry, *, os_fn: str) -> str | None:
        """Call _get_pkg_id with the named OS active."""
        import core.catalog_install as ci
        with (
            patch("core.catalog_install.is_windows", return_value=(os_fn == "windows")),
            patch("core.catalog_install.is_macos",   return_value=(os_fn == "macos")),
        ):
            return ci._get_pkg_id(entry)

    def test_windows_returns_win_id(self):
        entry = _entry("github-cli")
        assert self._get(entry, os_fn="windows") == entry.win_id

    def test_macos_returns_macos_id(self):
        entry = _entry("github-cli")
        assert self._get(entry, os_fn="macos") == entry.macos_id

    def test_linux_returns_linux_id(self):
        entry = _entry("github-cli")
        assert self._get(entry, os_fn="linux") == entry.linux_id

    def test_windows_only_tool_returns_none_on_macos(self):
        entry = _entry("windows-terminal")
        assert self._get(entry, os_fn="macos") is None

    def test_windows_only_tool_returns_none_on_linux(self):
        entry = _entry("windows-terminal")
        assert self._get(entry, os_fn="linux") is None

    def test_tool_with_no_linux_id_returns_none_on_linux(self):
        entry = _entry("nvm-windows")
        assert self._get(entry, os_fn="linux") is None

    def test_nvm_has_macos_id(self):
        entry = _entry("nvm-windows")
        assert entry.macos_id == "nvm"


# ---------------------------------------------------------------------------
# Choco metadata
# ---------------------------------------------------------------------------

class TestChocoMetadata:
    def test_common_tools_have_choco_id(self):
        must_have = ("github-cli", "powershell-7", "vscode", "golang", "cmake", "docker-desktop")
        for name in must_have:
            entry = _entry(name)
            assert entry.choco_id, f"{name} is missing choco_id"

    def test_windows_only_tools_have_choco_id(self):
        windows_only = ("windows-terminal", "notepadplusplus", "sysinternals", "powertoys")
        for name in windows_only:
            entry = _entry(name)
            assert entry.choco_id, f"Windows-only tool {name} should have choco_id"

    def test_choco_ids_are_nonempty_strings(self):
        for e in WINGET_CATALOG:
            if e.choco_id is not None:
                assert isinstance(e.choco_id, str) and e.choco_id.strip(), (
                    f"{e.tool}: choco_id is set but empty"
                )


# ---------------------------------------------------------------------------
# Brew tap metadata
# ---------------------------------------------------------------------------

class TestBrewTapMetadata:
    def test_oh_my_posh_has_brew_tap(self):
        entry = _entry("oh-my-posh")
        assert entry.brew_tap == "jandedobbeleer/oh-my-posh"

    def test_temurin_has_brew_tap(self):
        entry = _entry("temurin-jdk21")
        assert entry.brew_tap == "adoptium/adoptium"

    def test_brew_tap_values_are_nonempty(self):
        for e in WINGET_CATALOG:
            if e.brew_tap is not None:
                assert isinstance(e.brew_tap, str) and e.brew_tap.strip(), (
                    f"{e.tool}: brew_tap is set but empty"
                )


# ---------------------------------------------------------------------------
# Linux repo metadata
# ---------------------------------------------------------------------------

class TestLinuxRepoMetadata:
    def test_gh_has_linux_repo(self):
        entry = _entry("github-cli")
        assert entry.linux_repo == "gh"

    def test_kubectl_has_linux_repo(self):
        entry = _entry("kubectl")
        assert entry.linux_repo == "kubernetes"

    def test_vscode_has_linux_repo(self):
        entry = _entry("vscode")
        assert entry.linux_repo == "vscode"

    def test_temurin_has_linux_repo(self):
        entry = _entry("temurin-jdk21")
        assert entry.linux_repo == "adoptium"

    def test_linux_repo_keys_exist_in_apt_setup_dict(self):
        from core.linux_util import _APT_REPO_SETUP
        for e in WINGET_CATALOG:
            if e.linux_repo is not None:
                assert e.linux_repo in _APT_REPO_SETUP, (
                    f"{e.tool}: linux_repo={e.linux_repo!r} has no entry in _APT_REPO_SETUP"
                )

    def test_linux_repo_values_are_nonempty(self):
        for e in WINGET_CATALOG:
            if e.linux_repo is not None:
                assert isinstance(e.linux_repo, str) and e.linux_repo.strip(), (
                    f"{e.tool}: linux_repo is set but empty"
                )


# ---------------------------------------------------------------------------
# Layer coverage: every layer has entries
# ---------------------------------------------------------------------------

class TestLayerCoverage:
    @pytest.mark.parametrize("layer", [
        "infrastructure", "editors", "utilities", "devops", "languages", "ml_stack", "extras",
    ])
    def test_layer_nonempty(self, layer: str):
        assert len(catalog_entries_for_layer(layer)) > 0, f"Layer {layer!r} is empty"
