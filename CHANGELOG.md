# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Version numbers follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.8.0-phase4] — 2026-04-25

### Breaking changes
- **`--winutil-latest` CLI flag removed.** Sanitization is now native PowerShell;
  no CTT WinUtil download at any time.
- **`core/winutil_pin.py` deleted.** Any code that imported from it will need
  updating (no external consumers expected).

### Added
- **`scripts/sanitize.ps1`** — self-contained native PowerShell sanitization.
  Applies privacy/performance registry and service tweaks directly with no
  network access, no GUI, no external download. Presets: `Minimal` (4 tweaks)
  and `Standard` (13 tweaks). Streams output live to the terminal.
- **`scripts/smoke-test-winget-ids.py`** — validates every `WINGET_CATALOG`
  entry via `winget show --id --exact`. Accepts `--layer` and `--timeout` flags.
  Run before release or when catalog IDs change.
- **`scripts/test_gpu_pytorch_matrix.py`** — 51-scenario GPU/PyTorch path
  selection matrix. Covers NVIDIA (CUDA 10.1–13.0), AMD discrete/iGPU,
  Intel, VM adapters, headless, Optimus, broken smi, and more. Exit 0 = all
  expected paths matched. Outputs plain text (default), `--markdown`, or
  `--json`. Added to static check list in `docs/RELEASE_TESTING.md`.
- **`scripts/sanitize.ps1`** added to `scripts/` alongside existing
  `gpu_detect.py`, `path_auditor.py`, `scan-all-tools.py`, `verify-install.py`.
- **`VERSION` file** at repo root — single-source version string. Read by
  `install_context._read_version()` at module load with hard-coded fallback.
- **`pyproject.toml`** — pytest config (`testpaths`, `-v --tb=short`) and ruff
  lint config (`target-version = "py311"`, `line-length = 100`).
- **`.github/workflows/ci.yml`** — CI on `windows-latest` for Python 3.11,
  3.12, and 3.13: `py_compile` (all non-GUI core modules + scripts), ruff, pytest.
- **GUI failure reporter** — Results tab gains "Report failures on GitHub" button
  (hidden unless manifest has `failed` tools). Opens a pre-filled GitHub new-issue
  URL with version, profiles, and failed tool list. Built via `_build_issue_url()`
  and `page.launch_url()`.
- **Pre-install summary tweak list** — when `--run-sanitation` is set, the
  summary panel lists the actual tweak names for the chosen preset (reads local
  JSON config; strips `WPFTweaks` prefix; truncates at 10 with `(+N more)`).
- **`docs/RELEASE_TESTING.md`** — comprehensive 12-section VM validation
  checklist: static checks, winget ID smoke-test, Layer 0, all CLI dry-run
  flags, GUI tab-by-tab, pre-install summary accuracy, destructive smoke
  (systems / extras / AI-ML / sanitation), bootstrap paths, SmartScreen, sign-off
  template.
- **SmartScreen / execution policy notes** in README — explains MOTW behaviour
  for `irm | iex`, `git clone`, and browser-downloaded `.ps1`; includes
  `Unblock-File` snippet.
- **README Troubleshooting section** — winget source reset, fault-isolated
  retry, winget hang workaround, WSL reboot/resume flow, Python PATH,
  sanitization WinUtil note removed.
- **`core/__init__.py`** — `REPO_ROOT` constant and `ensure_repo_on_sys_path()`
  canonical helper (replaced 3 identical local implementations in `finalize.py`,
  `ml_stack.py`, `system_scan.py`).
- **WSL reboot handling** — `ensure_wsl_prereq` sets `ctx.wsl_reboot_required`
  on DISM exit `3010`; `ensure_wsl_default_distro` defers with a clear
  REBOOT REQUIRED message; pre-install summary warns on first-time WSL enable.
- **VM detection** — `system-profile.json` schema bumped to `1.1`; new `system`
  block with `manufacturer`, `model`, `is_vm`, `vm_hint` (covers VMware,
  VirtualBox, Hyper-V, KVM/QEMU, Xen, Parallels). Pre-install summary warns on
  VM + AI-ML + `--install-ml-wheels` (no GPU passthrough) and VM + WSL (nested
  virt caveat). Layer 0 prints a warning when `is_vm` is true.
- **Unit test suite** — 83 tests across 4 modules (gpu_detect: 36,
  install_catalog: 20, path_auditor: 12, winutil_presets: 12, winget_util / others:
  3). All pass on Windows, Python 3.11–3.13.

### Changed
- **Sanitization completely rewritten** — `core/sanitize.py` previously
  downloaded and executed `winutil.ps1` (CTT's full GUI application), which
  opened the CTT interface regardless of flags. Replaced with a call to the
  bundled `scripts/sanitize.ps1`. No network access, no GUI, no SHA256 pinning
  ceremony. Output streams live to the terminal.
- **README comparison table** — removed CTT WinUtil column (comparing against
  your own runtime dependency is incoherent). Replaced with Winget/Scoop,
  Dev Home, and hand-rolled `.ps1` scripts. Added honest note explaining AM-DevKit
  no longer uses CTT at all.
- **WSL DISM + `wsl --install -d`** now use `stream=True` so output appears live
  in the terminal. `wsl.exe` is invoked directly (not via `Start-Process`) to
  avoid output capture.
- **Profile table in README** rewritten row-by-row to match actual
  `WINGET_CATALOG` entries. Removed tools that were never implemented
  (HuggingFace, Open WebUI, Playwright, Visual Studio Community, PlatformIO,
  Zadig, Sigrok). Added accurate per-profile tool lists.
- **`core/winutil_presets.py`** — stripped to preset descriptions and
  `fallback_presets()`. Network-fetching functions (`fetch_presets`,
  `get_tweaks_for_preset`) removed along with `winutil_pin` dependency.
- **GUI sanitation section** — replaced the "fetch presets from CTT" background
  thread with hardcoded Minimal/Standard radio buttons with descriptions. No
  network call on GUI open.
- **`config/am-devkit-winutil-standard.json`** — corrected `WPFTweaksDVR`
  (which does not exist in CTT) to `WPFTweaksGameDVR`.
- **Pre-install summary "Norton Ghost" framing** — installer pitch changed from
  generic "opinionated orchestration layer" to "Norton Ghost for your dev stack"
  (reproducibility/portability focus).
- **`docs/project.md` profile tooltips** annotated with `[Implemented]` /
  `[Planned]` split to reflect actual vs. aspirational feature coverage.
- **GPU diagram note** — "installed automatically" qualified to
  "selected automatically (opt-in toggle)" to accurately reflect that PyTorch
  installation is opt-in.
- **`am-devkit.toml`** header comment clarified: "NOT currently read by
  installer — authoritative version in VERSION file."

### Added
- **`scripts/sanitize-restore.ps1`** — reverses all sanitization tweaks and
  restores Windows registry/service defaults. Self-elevates via UAC. Irreversible
  steps (temp file deletion, DISM cleanup) are noted in output.
- **GUI "Restore Windows defaults" button** — always-visible button in the
  Sanitization section of the Options tab; launches `sanitize-restore.ps1` in a
  new console with UAC elevation.
- **Already-sanitized skip** — `core/sanitize.py` reads `devkit-manifest.json`
  before running; if a prior `am-sanitize installed` entry exists, the layer is
  skipped with a clear message instead of re-applying all tweaks.
- **Pre-install detection pre-checks** — skip tools that are already installed
  without invoking the underlying tool:
  - `scoop-cli-bundle`: checks scoop shims dir for all 7 tools (bat, rg, fd,
    fzf, jq, lazygit, delta) — shims are not on the elevated-process PATH so
    `shutil.which` would always miss them
  - `pyenv-win`: also probes scoop shims alongside PATH
  - `wsl-prereq`: queries DISM feature state before enabling; skips the 2-5 min
    DISM run if both features are already enabled
  - `pip-ml-base`: `pip show` pre-check; skips if all 6 packages present
  - `pytorch / torch-directml`: `pip show` pre-check; skips if torch pkg present
  - `docker permissions fix`: skips `takeown`/`icacls` if `docker.exe` on PATH
- **Known-benign PATH conflict notes** — `scripts/path_auditor.py` now maps
  `klist.exe`, `kubectl.exe`, and `code-tunnel.exe` to specific explanations
  instead of the generic "reorder PATH" hint. These shadows are expected when a
  full dev stack is installed; the HTML report now says so clearly.

### Fixed
- **`bootstrap/install.ps1` pip noise** — added `-q` flag to `pip install
  -r requirements.txt`; suppresses "Requirement already satisfied" output when
  dependencies are already present.
- **`scripts/sanitize.ps1` encoding crash** — em dash `—` in the completion
  message caused a PowerShell 5.1 parse error (`MissingEndCurlyBrace`) because
  PS 5.1 reads scripts as Windows-1252 and choked on the UTF-8 multibyte
  character. Replaced with an ASCII hyphen.
- **`unity-hub` detector** — `shutil.which("Unity Hub.exe")` never resolves
  (spaces in name; not on PATH). Replaced with direct `Program Files` path checks.
- **Flet version check false positive** — `bootstrap/install.ps1` incorrectly
  flagged `flet-core` / `flet-desktop` at `0.25.2` as needing a downgrade
  because the check compared the package *name* (not `flet`) rather than just
  the version. Fixed to a version-only comparison.
- **`core/winutil_presets.py`** `_FALLBACK_DESCRIPTION` replaced with an
  inline `"Custom preset."` string; unknown presets still get a non-empty
  description.

### Removed
- **`core/winutil_pin.py`** — deleted. Managed CTT WinUtil SHA256 pinning and
  download. No longer needed.
- **`--winutil-latest` CLI flag** and `winutil_latest` field on `InstallContext`.
- **CTT preset-loader background thread** from GUI (`_load_presets_thread`).
- **`winutil_latest_sw`** and **`winutil_latest_warning`** controls from GUI.
- **Stale profile hints** — removed `"pyserial / USB tooling"` from
  hardware-robotics `PROFILE_HINTS` (not implemented in catalog).
- **22 → 12 tests in `test_winutil_presets.py`** — removed `TestFetchPresets`
  and `TestGetTweaksForPreset` classes (tested CTT network paths that no longer
  exist).

---

## Pre-history (before structured changelog)

The following features were developed before this changelog was established.
Captured from git history for completeness.

### Phase 3 — GUI (Flet)
- `core/gui.py` — Flet launcher with four tabs: Summary (system scan + pre-install
  preview), Profiles & Options (checkboxes, switches, exclusions), Custom Exclusions
  (per-tool opt-out), Results (manifest viewer + failure reporter)
- `--reuse-system-profile` — skip Layer 0 re-scan in GUI mode when JSON exists
- Absentmind Mode in GUI — selects all core profiles, no Extras
- Sanitation preset radio group (Minimal / Standard)
- GUI "Run installer (new console)" launches a second PowerShell window so the
  Flet window stays responsive during long installs

### Phase 2 — CLI baseline
- `core/installer.py` — CLI orchestrator with full layer stack
- Layer 1: Windows sanitation (originally CTT WinUtil, now native PS)
- Layer 2: infrastructure (Git, Scoop, GitHub CLI, Windows Terminal, PS7, Oh My Posh, uv)
- Layer 3: editors (VS Code, Cursor, extensions)
- Layer 4: languages (Python ecosystem, Node via NVM, Rust via rustup)
- Layer 5: ML stack (GPU detection + PyTorch CUDA/DirectML/CPU branch)
- Layer 6: DevOps (Docker, WSL2, cloud CLIs: AWS/Azure/GCP)
- Layer 7: utilities (catalog-driven — profiles gate which tools install)
- Layer 8: finalize (manifest, PATH auditor, HTML report, dotfiles, restore bundle)
- Layer 8.5: sandbox (Windows Sandbox + Dev Container config)
- `devkit-manifest.json` — incremental manifest written tool-by-tool
- `post-install-report.html` — PATH auditor first (red/green banner), then install summary
- `scripts/restore-devkit.ps1` — restore script generated per run
- `--dry-run` — full walkthrough with no destructive writes
- `--profile` / `--absentmind` / `--exclude-catalog-tool`
- `--install-ml-wheels` / `--install-ml-base` (opt-in PyTorch + pip base stack)
- `--enable-wsl` + `--wsl-default-distro`
- `--run-sanitation` + `--sanitation-preset`
- Extras profile — personal apps (PowerToys, Obsidian, OBS, ShareX, etc.)

### Phase 1 — Proof of concept
- `core/system_scan.py` + Layer 0 — hardware scan → `system-profile.json`
- `scripts/gpu_detect.py` — NVIDIA CUDA version detection, AMD DirectML path,
  CPU-only fallback; selects correct PyTorch `--index-url` automatically
- `bootstrap/install.ps1` — PowerShell entry point, bootstraps Python + deps,
  hands off to Python installer
- `bootstrap/fresh.ps1` — fresh-machine one-liner (installs git if missing,
  clones repo, opens GUI)
- `scripts/path_auditor.py` — PATH conflict detection with false-positive
  suppression (Windows internals, Inno Setup stubs, WindowsApps stubs)

### Phase 0 — Vision + architecture
- `docs/PROJECT.md` — master specification document
- `AGENTS.md` — AI agent ground rules
- Repository scaffold, profile system design, catalog architecture
