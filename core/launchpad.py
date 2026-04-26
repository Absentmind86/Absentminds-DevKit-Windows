"""Post-install launchpad: helper scripts + HTML fragment (Phase 2)."""

from __future__ import annotations

import html
import textwrap
from pathlib import Path
from typing import Any

from core.platform_util import is_windows


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _tool_row(tools: list[dict[str, Any]], name: str) -> dict[str, Any] | None:
    for t in tools:
        if isinstance(t, dict) and t.get("tool") == name:
            return t
    return None


def _tool_usable(row: dict[str, Any] | None) -> bool:
    if row is None:
        return False
    return row.get("status") in ("installed", "skipped", "planned")


def write_launchpad_scripts(
    *,
    repo_root: Path,
    profiles: list[str],
    tools: list[dict[str, Any]],
    pytorch: dict[str, Any] | None,
) -> Path:
    """Write ``am-devkit-out/launchpad/*.cmd`` and ``verify-torch-cuda.py``."""
    out = repo_root / "am-devkit-out" / "launchpad"
    out.mkdir(parents=True, exist_ok=True)

    if is_windows():
        (out / "open-vscode.cmd").write_text(
            textwrap.dedent(
                r"""
                @echo off
                start "" "%LocalAppData%\Programs\Microsoft VS Code\Code.exe"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        (out / "open-cursor.cmd").write_text(
            textwrap.dedent(
                r"""
                @echo off
                start "" "%LocalAppData%\Programs\cursor\Cursor.exe"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        (out / "open-docker-desktop.cmd").write_text(
            textwrap.dedent(
                r"""
                @echo off
                start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

        (out / "ollama-run-small.cmd").write_text(
            textwrap.dedent(
                r"""
                @echo off
                ollama run llama3.2
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    verify_py = textwrap.dedent(
        '''
        """Verify PyTorch CUDA (AM-DevKit launchpad). Run: python verify-torch-cuda.py"""
        from __future__ import annotations

        def main() -> int:
            try:
                import torch
            except ImportError:
                print("PyTorch is not installed in this interpreter. Install torch first.")
                return 1
            ok = bool(torch.cuda.is_available())
            if ok:
                print("CUDA is available - GPU path looks good.")
                print("Device:", torch.cuda.get_device_name(0))
            else:
                print("CUDA not available - CPU-only or driver/toolkit issue.")
            return 0 if ok else 2

        if __name__ == "__main__":
            raise SystemExit(main())
        '''
    ).strip()
    (out / "verify-torch-cuda.py").write_text(verify_py + "\n", encoding="utf-8")

    if is_windows() and "extras" in profiles:
        (out / "open-am-devkit-vault.cmd").write_text(
            textwrap.dedent(
                r"""
                @echo off
                explorer "%USERPROFILE%\Documents\AM-DevKit-Vault"
                """
            ).strip()
            + "\n",
            encoding="utf-8",
        )

    return out


def build_launchpad_html(*, rel_dir: str, profiles: list[str], tools: list[dict[str, Any]], pytorch: dict[str, Any]) -> str:
    """Return HTML fragment for the report (scripts live under *rel_dir*)."""
    rows: list[str] = []
    prof = set(profiles)

    def add(title: str, file: str, blurb: str) -> None:
        rows.append(
            "<li class='lp-item'>"
            f"<p><strong>{_esc(title)}</strong></p>"
            f"<p class='hint'>{_esc(blurb)}</p>"
            f"<p><code>{_esc(rel_dir + '/' + file)}</code></p>"
            "</li>"
        )

    if is_windows():
        add(
            "Open VS Code",
            "open-vscode.cmd",
            "Double-click in Explorer, or run from this folder in cmd.",
        )

        if _tool_usable(_tool_row(tools, "cursor")) or "ai-ml" in prof or "web-fullstack" in prof:
            add(
                "Open Cursor",
                "open-cursor.cmd",
                "If install path differs, edit the .cmd or launch Cursor from Start.",
            )

        if _tool_usable(_tool_row(tools, "docker-desktop")) or "ai-ml" in prof or "web-fullstack" in prof:
            add(
                "Open Docker Desktop",
                "open-docker-desktop.cmd",
                "Edit this file if Docker is installed to a non-default path.",
            )

        if "ai-ml" in prof and _tool_usable(_tool_row(tools, "ollama")):
            add(
                "Run a small local model (Ollama)",
                "ollama-run-small.cmd",
                "Requires ollama on PATH; pulls/runs llama3.2 on first use.",
            )

    if "ai-ml" in prof:
        kind = str(pytorch.get("torch_path_kind") or "")
        if kind == "nvidia_cuda" or _tool_usable(_tool_row(tools, "pytorch-pip")):
            add(
                "Verify PyTorch CUDA",
                "verify-torch-cuda.py",
                "In a terminal: cd to this folder, then run your Python against verify-torch-cuda.py.",
            )

    if is_windows() and "extras" in prof and (
        _tool_usable(_tool_row(tools, "obsidian-vault"))
        or _tool_usable(_tool_row(tools, "obsidian"))
    ):
        add(
            "Open AM-DevKit vault folder",
            "open-am-devkit-vault.cmd",
            "Opens Documents\\AM-DevKit-Vault in Explorer; use Obsidian → Open folder as vault.",
        )

    if not rows:
        return ""

    items = "\n".join(rows)
    return f"""
  <h2>Launchpad</h2>
  <p class='hint'>Concrete next steps. Scripts live under <code>{_esc(rel_dir)}</code> (double-click in Explorer).</p>
  <ul class='launchpad'>
  {items}
  </ul>
"""


def build_launchpad_section(
    *,
    repo_root: Path,
    profiles: list[str],
    tools: list[dict[str, Any]],
    system_profile: dict[str, Any],
) -> str:
    pytorch = system_profile.get("pytorch") if isinstance(system_profile.get("pytorch"), dict) else {}
    rel = "am-devkit-out/launchpad"
    write_launchpad_scripts(
        repo_root=repo_root,
        profiles=profiles,
        tools=tools,
        pytorch=pytorch,
    )
    return build_launchpad_html(rel_dir=rel, profiles=profiles, tools=tools, pytorch=pytorch)
