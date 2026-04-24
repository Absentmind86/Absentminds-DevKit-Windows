"""Pinned CTT WinUtil release — default path for Layer 1 sanitization.

AM-DevKit ships with a SHA256-pinned reference to a specific CTT WinUtil
release.  Downloads are hash-verified before execution, so a compromised CDN
or DNS cannot substitute attacker-controlled code into the install flow.

To bump the pin
---------------
1. Check the latest release: https://github.com/ChrisTitusTech/winutil/releases/latest
2. Download ``winutil.ps1`` (the release asset) and
   ``config/preset.json`` from the source tree at that tag.
3. Compute SHA256 of each::

       Get-FileHash -Algorithm SHA256 <file>

4. Update ``WINUTIL_TAG``, ``WINUTIL_SCRIPT_SHA256``, and
   ``WINUTIL_PRESET_SHA256`` below.
5. Test the install flow end-to-end on a VM (dry-run + real run).
6. Open a PR titled "bump: WinUtil pin to <tag>".

Upstream license: MIT, Chris Titus Tech / CT Tech Group LLC — see
``docs/THIRD_PARTY_NOTICES.md``.
"""

from __future__ import annotations

import hashlib
import tempfile
import urllib.request
from pathlib import Path

WINUTIL_TAG = "26.04.14"

WINUTIL_SCRIPT_URL = (
    f"https://github.com/ChrisTitusTech/winutil/releases/download/{WINUTIL_TAG}/winutil.ps1"
)
WINUTIL_SCRIPT_SHA256 = (
    "31b67e92fe5375a976f728855a425ed4e129094a3c04b1b4de6fcf2fffb8d626"
)

WINUTIL_PRESET_URL = (
    f"https://raw.githubusercontent.com/ChrisTitusTech/winutil/{WINUTIL_TAG}/config/preset.json"
)
WINUTIL_PRESET_SHA256 = (
    "7544eb16ff6a859ddc892d7b167c63570d2f3450ebf1e0e990e3ba522951f725"
)

# Live (unpinned) endpoints used only when the user opts into --winutil-latest.
# NO integrity check — the GUI and CLI surface this explicitly.
WINUTIL_SCRIPT_LIVE_URL = "https://christitus.com/win"
WINUTIL_PRESET_LIVE_URL = (
    "https://raw.githubusercontent.com/ChrisTitusTech/winutil/main/config/preset.json"
)


class WinUtilHashMismatch(RuntimeError):
    """Raised when a downloaded WinUtil artifact fails SHA256 verification."""


def download_verified(
    url: str,
    expected_sha256: str,
    *,
    timeout: float = 30.0,
    suffix: str = "",
) -> Path:
    """Download *url* to a temp file and verify SHA256.

    Returns the temp file path on success.  Raises ``WinUtilHashMismatch`` if
    the digest does not match — callers MUST NOT execute the downloaded file
    in that case.  The temp file is deleted before raising so a tampered
    artifact never lingers on disk.
    """
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data = resp.read()
    actual = hashlib.sha256(data).hexdigest()
    if actual.lower() != expected_sha256.lower():
        raise WinUtilHashMismatch(
            f"SHA256 mismatch for {url}: expected {expected_sha256}, got {actual}"
        )
    tmp = Path(tempfile.mktemp(suffix=suffix, prefix="am-devkit-winutil-"))
    tmp.write_bytes(data)
    return tmp
