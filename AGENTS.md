# AGENTS.md — AM-DevKit AI Agent Ground Rules

> This file is the source of truth for any AI agent (Cursor, Claude, Copilot, etc.) working on this project.
> Read this before touching any file. When in doubt, re-read this.

---

## What This Project Is

**Absentmind's DevKit (AM-DevKit)** is a Windows developer environment bootstrapper.

One command. Walk away. Come back to a fully configured, GPU-intelligent dev environment.

It is **not**:
- A package manager (Winget/Scoop/Choco handle that)
- A dotfile manager (though it seeds dotfiles)
- A general-purpose Windows tweaker (CTT WinUtil handles sanitation)

It **is**:
- An opinionated orchestration layer that ties all of the above together
- A profile-based installer that detects hardware and makes smart decisions
- A reproducibility tool (manifest + restore script on every run)

---

## Current Phase

**Phase 4 — Release readiness**

Focus:
1. **Clean VM validation** — follow `docs/RELEASE_TESTING.md` (smoke + regression paths)
2. **Documentation** — README accuracy, `docs/THIRD_PARTY_NOTICES.md` when deps or integrations change
3. **Distribution** — signed `.exe` or trust-on-first-run `bootstrap/install.ps1` (decision TBD); GitHub release assets

**Phase 3 (GUI + polish) — baseline complete**

Delivered:
- `core/gui.py` — Flet launcher: Summary tab (`format_pre_install_summary_text`, **Run system scan**), Profiles & options (incl. `--reuse-system-profile` when JSON exists), Custom exclusions, new-console installer launch
- `core/extras.py` + `finalize.py` — Extras catalog; Obsidian vault + PowerToys backup when profile/excludes allow

CLI-only usage remains supported (`python -m core.installer`). Do not skip manifest writes.

**Phase 2 (complete baseline)** — `installer.py` orchestration, layer modules, WinUtil (`--run-sanitation`), manifest + HTML report, PATH auditor.

---

## Source of Truth

**`docs/PROJECT.md`** is the master document. It contains:
- Full architecture and layer definitions
- Profile system specification
- Component lists per layer
- UX decisions (Pre-Flight, Sanitation toggle, Pre-Install Summary, Launchpad)
- Repo structure
- Open questions

If there is any conflict between this file and `docs/PROJECT.md`, **PROJECT.md wins**.
If there is any conflict between PROJECT.md and a user instruction in the current session, **the user instruction wins**.

---

## Project Structure

```
absentmind-devkit/
├── AGENTS.md                   ← You are here
├── README.md
├── CHANGELOG.md
├── LICENSE                     ← MIT
├── am-devkit.toml              ← User-facing config (do not auto-generate values here)
│
├── bootstrap/
│   └── install.ps1             ← Entry point. PowerShell only. Installs Python, hands off.
│
├── core/
│   ├── installer.py            ← CLI orchestrator (python -m core.installer)
│   ├── gui.py                  ← Phase 3: Flet launcher (python -m core.gui)
│   ├── install_context.py      ← Shared InstallContext + profile merge helpers
│   ├── manifest.py             ← devkit-manifest.json incremental writer
│   ├── winget_util.py          ← Winget installs with skip-if-present logic
│   ├── pwsh_util.py            ← Scoop, OpenSSH client, rustup-init, optional WSL DISM
│   ├── pyenv_scoop.py          ← pyenv-win via Scoop (no winget package)
│   ├── install_catalog.py      ← PROJECT.md-aligned winget matrix (Phase 2B)
│   ├── catalog_install.py      ← Apply catalog rows per layer (profile gates)
│   ├── pre_install_summary.py  ← CLI pre-install summary + optional confirm (after Layer 0)
│   ├── preflight.py            ← Restore point + Absentmind Mode toggle
│   ├── system_scan.py          ← Layer 0: hardware detection → system-profile.json
│   ├── sanitize.py             ← Layer 1: invokes CTT WinUtil with AM config
│   ├── infrastructure.py       ← Layer 2: Git, Terminal, SSH, Tailscale
│   ├── editors.py              ← Layer 3: VS Code, Cursor, extensions
│   ├── languages.py            ← Layer 4: Python ecosystem, Node, Rust
│   ├── ml_stack.py             ← Layer 5: GPU branch logic + PyTorch
│   ├── devops.py               ← Layer 6: Docker, WSL2, WSL seeding, CLIs
│   ├── utilities.py            ← Layer 7: dev tools, security, monitoring
│   ├── extras.py               ← Extras profile: optional personal winget stack
│   ├── finalize.py             ← Layer 8: manifest, path auditor, HTML report, dotfiles
│   └── sandbox.py              ← Layer 8.5: Disposable Workspace config
│
├── config/
│   ├── am-devkit-winutil.json        ← WinUtil tweaks: conservative (minimal)
│   ├── am-devkit-winutil-standard.json  ← WinUtil tweaks: CTT preset.json Standard set
│   ├── profiles/
│   │   ├── ai-ml.toml
│   │   ├── web-fullstack.toml
│   │   ├── systems.toml
│   │   ├── game-dev.toml
│   │   ├── hardware-robotics.toml
│   │   ├── absentmind-mode.toml
│   │   └── extras.toml
│   └── vscode/
│       ├── settings.json
│       └── extensions.json
│
├── scripts/
│   ├── gpu_detect.py           ← Standalone. Must run independently of full bootstrap.
│   ├── path_auditor.py         ← PATH conflict detection + fingerprinting
│   └── restore-devkit.ps1
│
├── templates/
│   ├── dotfiles/
│   │   ├── .gitconfig
│   │   ├── .bashrc
│   │   └── powershell-profile.ps1
│   └── sandbox/
│       ├── sandbox-config.wsb
│       └── devcontainer.json
│
└── docs/
    ├── PROJECT.md              ← Master document. Read this.
    ├── ARCHITECTURE.md
    └── CONTRIBUTING.md
```

---

## Coding Conventions

### Language
- **Bootstrap entry point:** PowerShell (`.ps1`) only. Zero dependencies. Single file. No modules.
- **Everything else:** Python 3.11+
- **Config files:** TOML for user-facing, JSON for machine-generated output
- **No JavaScript. No Node. No Electron.** GUI is Flet (Python/Flutter) — Phase 3 only.

### Python Style
- Type hints on all function signatures
- Docstrings on all public functions
- No global state — pass `system_profile` dict through functions explicitly
- Prefer `subprocess.run()` with explicit args list over shell strings
- All file paths via `pathlib.Path`, never string concatenation

### Error Handling
- Every install step must be wrapped — a single tool failing must **never** crash the whole run
- On failure: log the error, mark the tool as `failed` in the manifest, continue
- Surface failures in the HTML report, not as exceptions during install

### Output During Install
- Use `rich` library for terminal output — progress bars, colored status, clean panels
- Every layer announces itself with a header
- Every tool install shows: `[installing]` → `[✅ done]` or `[⚠️ failed]`
- No raw `print()` statements in production code

### Licensing

- Repository license: **MIT** (`LICENSE`). Third-party attribution and runtime tools (WinUtil, Winget, pip deps): **`docs/THIRD_PARTY_NOTICES.md`**. Update that document when adding **direct** `requirements.txt` dependencies or materially changing external integrations.

### The Manifest
- Every decision made during install must be written to `devkit-manifest.json`
- Schema: `{ tool, version, layer, status, timestamp, install_method, notes, winget_id? }` — ``winget_id`` is set for winget rows (schema `am-devkit-manifest-1.1`) so ``scripts/restore-winget-from-manifest.ps1`` can replay installs.
- Written incrementally (append per tool), not in one shot at the end
- If the install crashes mid-run, the manifest reflects what actually completed

---

## Hard Rules — Do Not Violate

1. **Do not install anything without checking if it already exists first.** Layer 0 scans for existing installs. Respect that data.
2. **Do not modify the user's PATH directly** — use Winget/Scoop/installers and let them handle PATH registration. Log what changed.
3. **Do not hard-code paths.** Everything relative to detected user home or install root.
4. **`config/am-devkit-winutil.json` is the CTT WinUtil export (``WPFTweaks`` ids).** The repo ships a **conservative** preset (Chris Titus “Minimal”-style tweak set). Do not expand to aggressive bloat removal without review and VM testing; user requests to change sanitation are explicit permission to edit.
5. **Do not skip the manifest write.** Even for tools that were already installed (mark them `skipped`, not absent).
6. **`gpu_detect.py` must be runnable standalone** — it will be validated on real hardware before the rest of the stack is built. Keep it importable and independently testable.
7. **GUI is Flet (`core/gui.py`).** Profile selection remains available via CLI flags (`--profile`, `--absentmind`).

---

## Key Design Decisions (Already Made — Do Not Reopen)

| Decision | Choice | Reason |
|---|---|---|
| GUI framework | Flet | Async-native, Python codebase unified, Phase 3 |
| Package manager | Winget primary, Scoop for CLI tools, Choco as fallback | Documented in PROJECT.md |
| Python in Core | Yes — always installs | Near-universal dependency |
| Profile system | Multi-select, additive | Users often need more than one stack |
| Absentmind Mode | All *core* profiles (no Extras), no prompts | Extras stay opt-in (`config/profiles/extras.toml`) |
| Sanitation | CTT WinUtil, category-level toggle in UI | We own the config, CTT owns the execution |
| Path Auditor output | First section of HTML report, red banner on conflicts | Highest-value diagnostic, must be impossible to miss |
| Post-install Launchpad | Profile-aware, one-click concrete outcomes only | No links pages, no "learn more" |

---

## What "Done" Looks Like for Phase 2

- [ ] `python -m core.installer --dry-run --profile systems` completes and writes manifest + HTML + PATH fingerprint
- [ ] `python -m core.installer` (non-dry) runs layers without a single uncaught exception aborting the run
- [ ] `--run-sanitation` invokes WinUtil with the AM JSON config (validated on a throwaway VM first)
- [ ] `bootstrap/install.ps1 -FullInstall` runs the Phase 2 installer from repo root

### Phase 1 exit criteria (baseline)

- [ ] `system_scan.py` returns a valid `system-profile.json` on a real Windows machine
- [ ] `gpu_detect.py` correctly identifies NVIDIA/AMD/CPU-only and selects the right PyTorch index URL
- [ ] `install.ps1` bootstraps Python and hands off to Python without errors on a clean machine

---

*Maintained by Kyle / Absentmind Studio*
*See docs/PROJECT.md for full specification*
