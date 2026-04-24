"""Incremental ``devkit-manifest.json`` writer (Phase 2)."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

Status = Literal["pending", "skipped", "installed", "failed", "planned"]


@dataclass
class ManifestEntry:
    """One row in the install manifest (AGENTS.md schema)."""

    tool: str
    layer: str
    status: Status
    timestamp: str
    install_method: str
    version: str | None = None
    notes: str | None = None
    winget_id: str | None = None

    def to_json_object(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "tool": self.tool,
            "layer": self.layer,
            "status": self.status,
            "timestamp": self.timestamp,
            "install_method": self.install_method,
        }
        if self.version is not None:
            d["version"] = self.version
        if self.notes is not None:
            d["notes"] = self.notes
        if self.winget_id is not None:
            d["winget_id"] = self.winget_id
        return d


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Manifest:
    """Thread-safe manifest buffer flushed to disk after each layer."""

    def __init__(self, path: Path, *, devkit_version: str) -> None:
        self._path = path
        self._devkit_version = devkit_version
        self._entries: list[ManifestEntry] = []
        self._lock = threading.Lock()

    def append(self, entry: ManifestEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    def record_tool(
        self,
        *,
        tool: str,
        layer: str,
        status: Status,
        install_method: str,
        version: str | None = None,
        notes: str | None = None,
        winget_id: str | None = None,
    ) -> None:
        self.append(
            ManifestEntry(
                tool=tool,
                layer=layer,
                status=status,
                timestamp=_utc_now(),
                install_method=install_method,
                version=version,
                notes=notes,
                winget_id=winget_id,
            )
        )

    def entries_snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [e.to_json_object() for e in self._entries]

    def flush(self) -> None:
        """Write full manifest document atomically."""
        payload = {
            "schema": "am-devkit-manifest-1.1",
            "devkit_version": self._devkit_version,
            "generated_at": _utc_now(),
            "tools": self.entries_snapshot(),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self._path)
