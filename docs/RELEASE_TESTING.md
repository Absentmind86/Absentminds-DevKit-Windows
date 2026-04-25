# Release testing (Phase 4)

Use this checklist before tagging a release. Sections 2–7 and 9 are non-destructive
and safe to run on any Windows machine. Section 8 (destructive smoke) installs real
software and section 8d applies system-level sanitization tweaks — a VM or spare machine
is convenient for those so you can reset quickly, but the tool has been validated on a
live daily-driver install and is designed to be safe and reversible.

---

## 1. Environment

- [ ] Windows 11 (or Windows 10 build 1903+), current patches, local admin
- [ ] Repo cloned to a short path — e.g. `C:\src\am-devkit`
      from [github.com/Absentmind86/am-devkit](https://github.com/Absentmind86/am-devkit)
- [ ] Python 3.11+ available, or run `bootstrap/install.ps1` to bootstrap it
- [ ] `pip install -r requirements.txt` (rich + flet) for GUI tests

---

## 2. Static checks (non-destructive, run on any machine)

From repo root:

- [ ] `python -m pytest tests/ -v` — all tests pass, 0 failures
      *(run `python -m pytest tests/ --co -q | tail -1` to confirm current count before tagging)*
- [ ] `python -m ruff check core/ scripts/ tests/` — no errors
- [ ] `python -m py_compile` passes for all non-flet modules:
      ```powershell
      Get-ChildItem core/*.py | Where-Object { $_.Name -ne 'gui.py' } |
        ForEach-Object { python -m py_compile $_.FullName }
      ```
- [ ] `cat VERSION` matches the expected release string (e.g. `0.8.0-phase4`)
- [ ] `python scripts/test_gpu_pytorch_matrix.py` — all GPU/PyTorch path scenarios pass (exit 0)
      *(confirm scenario count matches the "X/X matched" line in output)*

---

## 3. Winget ID smoke-test (requires winget + internet)

- [ ] `python scripts/smoke-test-winget-ids.py` — all IDs resolve (exit 0)
- [ ] If any fail, update `core/install_catalog.py` before tagging

---

## 4. Layer 0 + scan

- [ ] `python core/system_scan.py --output system-profile.json` — completes,
      produces valid JSON with `schema_version: "1.1"` and a `system` block
- [ ] `python scripts/gpu_detect.py` — runs without traceback
      (VM is typically CPU-only; expect CPU branch in output)
- [ ] `python scripts/scan-all-tools.py` — runs without traceback;
      most tools will show `[MISSING]` on a fresh VM — that's expected

---

## 5. CLI dry-run smoke (non-destructive)

- [ ] `python -m core.installer --dry-run --profile systems --skip-summary`
      exits 0, writes `devkit-manifest.json`, `post-install-report.html`,
      and `path-fingerprint.json`
- [ ] `python -m core.installer --dry-run --absentmind --skip-summary`
      exits 0; manifest contains all core profiles
- [ ] `python -m core.installer --dry-run --profile ai-ml --install-ml-wheels --skip-summary`
      exits 0; manifest shows PyTorch rows as `planned`
- [ ] `python -m core.installer --dry-run --profile systems --exclude-catalog-tool cursor --skip-summary`
      exits 0; `cursor` does not appear in manifest as `planned`
- [ ] `python -m core.installer --dry-run --reuse-system-profile system-profile.json --profile systems --skip-summary`
      exits 0 when `system-profile.json` exists from step 4
- [ ] `python -m core.installer --dry-run --run-sanitation --sanitation-preset minimal --profile systems --skip-summary`
      exits 0; pre-install summary shows tweak list (4 tweaks for Minimal preset)
- [ ] Re-run same command a second time after a real (non-dry) install has written a manifest —
      sanitize layer should print `[skipped] sanitization already applied in a prior run`

---

## 6. GUI smoke (non-destructive)

- [ ] `python -m core.gui` opens without traceback
- [ ] **Summary tab:** "Run system scan" completes; summary text populates;
      estimated disk and step count appear; WinUtil tweak line appears when
      sanitation is toggled on
- [ ] **Profiles & Options tab:** all 5 profile checkboxes toggle; Absentmind Mode
      selects all; PyTorch toggle only appears when AI/ML is checked;
      sanitation preset radio (Minimal / Standard) toggles correctly;
      WSL switch shows reboot caveat tooltip;
      "Restore Windows defaults" button is always visible and launches a new
      PowerShell console when clicked (approve UAC prompt)
- [ ] **Custom Exclusions tab:** typing a tool ID adds it to the exclusion list;
      preview field updates
- [ ] **Results tab:** "Refresh results" loads the dry-run manifest from step 5;
      status summary displays; "Open full HTML report" opens a browser tab;
      "Report failures on GitHub" button is hidden when no failures exist
- [ ] "Run installer (new console)" launches a second PowerShell/CMD window
      running `--dry-run` without Python tracebacks

---

## 7. Pre-install summary accuracy

Run interactively (without `--skip-summary`) and verify:

- [ ] `python -m core.installer --dry-run --profile systems`
      — summary panel shows correct profile list, step estimate, disk estimate
- [ ] `python -m core.installer --dry-run --run-sanitation --sanitation-preset standard --profile systems`
      — WinUtil tweak list shows all 13 standard preset tweaks (10 visible + "+3 more")
- [ ] `python -m core.installer --dry-run --enable-wsl --profile systems`
      — WSL first-time enable warning appears in summary

---

## 8. Destructive smoke (installs real software — snapshot or spare machine recommended)

> A VM or snapshot makes it easy to reset between sub-sections, but this is not required.

### 8a. Single profile — systems
- [ ] `python -m core.installer --profile systems --yes --skip-summary`
      completes without uncaught layer abort; no `[red]Layer * raised` lines
- [ ] `post-install-report.html` opens in browser; PATH banner is green (no conflicts)
      or shows a specific conflict with the affected binaries named
- [ ] `devkit-manifest.json` contains no `"status": "failed"` entries for catalog tools
- [ ] `scripts/restore-devkit.ps1` exists and is non-empty
- [ ] `scripts/restore-winget-from-manifest.ps1` exists

### 8b. Extras profile
- [ ] `python -m core.installer --profile extras --yes --skip-summary`
- [ ] With Obsidian not excluded: `Documents\AM-DevKit-Vault` directory seeded
- [ ] Extras tools (PowerToys, Obsidian, etc.) appear as `installed` or `skipped`
      (already present) in manifest

### 8c. AI / ML profile (opt-in wheels)
- [ ] `python -m core.installer --profile ai-ml --install-ml-wheels --install-ml-base --yes --skip-summary`
- [ ] Ollama appears as `installed` in manifest
- [ ] PyTorch: verify correct variant installed (`torch-directml` on AMD/CPU VM,
      `torch` with CPU index on CPU-only VM)
- [ ] `python -c "import torch; print(torch.__version__)"` runs without error

### 8d. Sanitation (modifies registry and services — reversible via sanitize-restore.ps1)
- [ ] `python -m core.installer --run-sanitation --sanitation-preset minimal --yes --skip-summary`
- [ ] Native `scripts/sanitize.ps1` runs (no external download); tweak steps stream to console; no uncaught exception
- [ ] Final line reads `Sanitization complete. (Minimal preset - no errors)` with exit 0
- [ ] VM remains usable after sanitation (can still open Start menu, Settings, Edge)
- [ ] Re-running the installer with `--run-sanitation` on the same VM prints `[skipped] sanitization already applied`
- [ ] `scripts/sanitize-restore.ps1` runs without error; services and registry keys restored

---

## 9. Bootstrap paths

### 9a. fresh.ps1 one-liner
- [ ] On a VM with no repo, no Python: open PowerShell as Administrator and run:
      ```powershell
      irm https://raw.githubusercontent.com/Absentmind86/am-devkit/main/bootstrap/fresh.ps1 | iex
      ```
- [ ] Git installs (if absent), repo clones to `%USERPROFILE%\am-devkit`,
      Python installs, GUI opens — no unhandled errors

### 9b. install.ps1 entry points
- [ ] `.\bootstrap\install.ps1` (no flags) — runs Layer 0 scan, writes `system-profile.json`
- [ ] `.\bootstrap\install.ps1 -Gui` — opens Flet GUI
- [ ] `.\bootstrap\install.ps1 -FullInstall -DryRun` — dry-run install, exits 0

---

## 10. SmartScreen / execution policy

Scripts are not code-signed in v0.8.

- [ ] **`irm | iex` path** — no SmartScreen block
      *(no Mark-of-the-Web on piped scripts)*
- [ ] **`git clone` then run** — no execution policy error
      *(git does not attach a zone tag)*
- [ ] **Browser download** — PowerShell refuses unsigned `.ps1`;
      `Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File` fixes it;
      re-run succeeds

If any of these fail unexpectedly, update the SmartScreen section in `README.md` before releasing.

---

## 11. Regression triggers

Re-run sections 4–6 (non-destructive) after any change to:

| Changed file | Re-run sections |
|---|---|
| `core/installer.py` layer order or `InstallContext` fields | 4, 5, 6 |
| `core/install_catalog.py` / `core/catalog_install.py` | 3, 5 |
| `core/sanitize.py` or `scripts/sanitize.ps1` / `sanitize-restore.ps1` | 5 (sanitation items), 7, 8d |
| `bootstrap/install.ps1` or `bootstrap/fresh.ps1` | 9 |
| `core/gui.py` | 6 |
| `core/pre_install_summary.py` | 7 |
| `core/system_scan.py` | 4 |
| `core/ml_stack.py` | 5 (ai-ml dry-run), 8c |
| `core/pwsh_util.py` (scoop/wsl helpers) | 5, 8a |
| `core/pyenv_scoop.py` or `core/install_catalog.py` detectors | 3, 5 |
| `core/devops.py` | 5, 8a |
| `VERSION` | verify `cat VERSION` in section 2 |

---

## 12. Sign-off template

Copy into the release issue or tag notes:

```
Release: v<VERSION>
Commit: <SHA>
Tester: <name>
Date: <YYYY-MM-DD>

VM environment:
  OS: Windows 11 <build> / Windows 10 <build>
  VM host: <VMware / Hyper-V / VirtualBox / bare metal>
  Python: <version>
  Winget: <version> (winget --version)

Sections completed:
  [ ] 1. Environment
  [ ] 2. Static checks
  [ ] 3. Winget ID smoke-test
  [ ] 4. Layer 0 + scan
  [ ] 5. CLI dry-run smoke
  [ ] 6. GUI smoke
  [ ] 7. Pre-install summary accuracy
  [ ] 8. Destructive smoke (a/b/c/d)
  [ ] 9. Bootstrap paths
  [ ] 10. SmartScreen
  [ ] 11. Regression triggers (if applicable)

Known issues / deviations:
  <none | describe>

Ready to tag: yes / no
```
