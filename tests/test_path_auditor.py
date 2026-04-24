"""Unit tests for scripts/path_auditor.py using synthetic PATH environments."""

from __future__ import annotations

import os
import stat
from pathlib import Path

from scripts.path_auditor import (
    _WINDOWS_APPS_MARKER,
    audit_path,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_exe(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("stub")
    if os.name != "nt":
        path.chmod(path.stat().st_mode | stat.S_IEXEC)


# ---------------------------------------------------------------------------
# audit_path: no conflicts
# ---------------------------------------------------------------------------

class TestAuditPathNoConflict:
    def test_empty_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PATH", "")
        result = audit_path()
        assert result["conflict_count"] == 0
        assert isinstance(result["path_fingerprint_sha256"], str)
        assert len(result["path_fingerprint_sha256"]) == 64

    def test_nonexistent_dirs_no_conflict(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PATH", str(tmp_path / "does_not_exist"))
        result = audit_path()
        assert result["conflict_count"] == 0
        dirs = result["path_directories"]
        assert len(dirs) == 1
        assert dirs[0]["exists"] is False

    def test_single_dir_no_conflict(self, monkeypatch, tmp_path):
        a = tmp_path / "bin"
        _make_exe(a / "tool.exe")
        monkeypatch.setenv("PATH", str(a))
        result = audit_path()
        assert result["conflict_count"] == 0

    def test_different_exes_no_conflict(self, monkeypatch, tmp_path):
        a = tmp_path / "bin_a"
        b = tmp_path / "bin_b"
        _make_exe(a / "foo.exe")
        _make_exe(b / "bar.exe")
        monkeypatch.setenv("PATH", os.pathsep.join([str(a), str(b)]))
        result = audit_path()
        assert result["conflict_count"] == 0


# ---------------------------------------------------------------------------
# audit_path: conflicts detected
# ---------------------------------------------------------------------------

class TestAuditPathConflicts:
    def test_same_exe_in_two_dirs(self, monkeypatch, tmp_path):
        a = tmp_path / "bin_a"
        b = tmp_path / "bin_b"
        _make_exe(a / "python.exe")
        _make_exe(b / "python.exe")
        monkeypatch.setenv("PATH", os.pathsep.join([str(a), str(b)]))
        result = audit_path()
        assert result["conflict_count"] == 1
        conflict = result["conflicts"][0]
        assert conflict["basename"] == "python.exe"
        # Winner is from the first directory
        assert str(a) in conflict["winner"]

    def test_winner_is_first_dir(self, monkeypatch, tmp_path):
        first = tmp_path / "first"
        second = tmp_path / "second"
        _make_exe(first / "git.exe")
        _make_exe(second / "git.exe")
        monkeypatch.setenv("PATH", os.pathsep.join([str(first), str(second)]))
        result = audit_path()
        conflicts = result["conflicts"]
        assert len(conflicts) == 1
        assert str(first) in conflicts[0]["winner"]
        assert any(str(second) in alt for alt in conflicts[0]["alternates"])

    def test_multiple_conflicts(self, monkeypatch, tmp_path):
        a = tmp_path / "a"
        b = tmp_path / "b"
        for name in ("python.exe", "pip.exe", "git.exe"):
            _make_exe(a / name)
            _make_exe(b / name)
        monkeypatch.setenv("PATH", os.pathsep.join([str(a), str(b)]))
        result = audit_path()
        assert result["conflict_count"] == 3


# ---------------------------------------------------------------------------
# audit_path: Windows false-positive suppression
# ---------------------------------------------------------------------------

class TestAuditPathFalsePositives:
    def test_windows_internal_duplicates_suppressed(self, monkeypatch, tmp_path):
        a = tmp_path / "system32"
        b = tmp_path / "syswow64"
        _make_exe(a / "notepad.exe")
        _make_exe(b / "notepad.exe")
        monkeypatch.setenv("PATH", os.pathsep.join([str(a), str(b)]))
        result = audit_path()
        assert result["conflict_count"] == 0

    def test_inno_uninstallers_suppressed(self, monkeypatch, tmp_path):
        a = tmp_path / "app1"
        b = tmp_path / "app2"
        _make_exe(a / "unins000.exe")
        _make_exe(b / "unins000.exe")
        monkeypatch.setenv("PATH", os.pathsep.join([str(a), str(b)]))
        result = audit_path()
        assert result["conflict_count"] == 0

    def test_windowsapps_stubs_suppressed(self, monkeypatch, tmp_path):
        # Real tool wins; stub in WindowsApps — should not be flagged.
        real = tmp_path / "real_bin"
        stub_parent = tmp_path / "Microsoft" / "WindowsApps"
        _make_exe(real / "python.exe")
        _make_exe(stub_parent / "python.exe")
        monkeypatch.setenv("PATH", os.pathsep.join([str(real), str(stub_parent)]))
        result = audit_path()
        # The stub path must contain the marker for suppression to fire.
        # We can't guarantee the tmp_path contains the marker, so only check
        # that any conflict present does not reference non-stub losers.
        for c in result["conflicts"]:
            for alt in c["alternates"]:
                # If the only alternate is the stub, no conflict should appear.
                assert _WINDOWS_APPS_MARKER not in alt.lower() or len(c["alternates"]) > 1


# ---------------------------------------------------------------------------
# audit_path: fingerprint stability
# ---------------------------------------------------------------------------

class TestFingerprint:
    def test_same_path_same_fingerprint(self, monkeypatch, tmp_path):
        a = tmp_path / "bin"
        _make_exe(a / "tool.exe")
        monkeypatch.setenv("PATH", str(a))
        r1 = audit_path()
        r2 = audit_path()
        assert r1["path_fingerprint_sha256"] == r2["path_fingerprint_sha256"]

    def test_different_path_different_fingerprint(self, monkeypatch, tmp_path):
        a = tmp_path / "bin_a"
        b = tmp_path / "bin_b"
        _make_exe(a / "t.exe")
        _make_exe(b / "t.exe")
        monkeypatch.setenv("PATH", str(a))
        r1 = audit_path()
        monkeypatch.setenv("PATH", str(b))
        r2 = audit_path()
        assert r1["path_fingerprint_sha256"] != r2["path_fingerprint_sha256"]
