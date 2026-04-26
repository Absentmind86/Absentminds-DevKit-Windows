<div align="center">

# Absentmind DevKit

### *You just got a new machine. Run one thing. Walk away.*
### *Come back to a fully configured, GPU-intelligent development environment.*

[![CI](https://github.com/Absentmind86/am-devkit/actions/workflows/ci.yml/badge.svg)](https://github.com/Absentmind86/am-devkit/actions/workflows/ci.yml)
[![Checksums](https://github.com/Absentmind86/am-devkit/actions/workflows/update-checksums.yml/badge.svg)](https://github.com/Absentmind86/am-devkit/actions/workflows/update-checksums.yml)
[![Status](https://img.shields.io/badge/status-pre--release-orange)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![Made by](https://img.shields.io/badge/made%20by-Absentmind-purple)]()

</div>

---

## Platform Support

| Platform | Status |
| --- | --- |
| Windows 10/11 | ✅ Live |
| Linux | ⚠️ In Development |
| macOS | ⚠️ In Development |

---

## What Is This?

AM-DevKit is a **developer toolkit installer** — currently Windows-only, with cross-platform support planned. It is not a package manager. It is not a dotfile manager. It is not a debloater.

Think of it as **Norton Ghost for your dev stack** — one run produces a documented, reproducible environment and a restore script you can replay on any future machine. It detects your hardware, makes smart decisions, and leaves a manifest of everything it did.

Optional Windows sanitation (native PowerShell — curated registry and service tweaks for privacy and performance) is available but off by default — the installer works perfectly without it.

No other installer combines all of this in one run. Tools like WinUtil handle OS tweaks well but aren't focused on developer stacks. Winget and Scoop handle apps but not GPU intelligence or reproducibility. Few ship a clean, replayable restore script + manifest out of the box.

---

## How It Works

```
Run install.ps1
       │
       ▼
Pre-Flight: System Restore Point created automatically
       │
       ▼
Choose your profiles (or hit Absentmind Mode and walk away)
       │
       ▼
Core installs: Git, VS Code, Python, Terminal, Scoop, 7-Zip + modern CLI suite
       │
       ▼
[Optional] Windows sanitization (native PS — privacy + performance tweaks) — off by default, fully toggleable
       │
       ▼
Your selected profiles install in order
       │
       ▼
GPU detected → correct PyTorch build selected automatically (opt-in toggle)
       │
       ▼
Post-install: Path Auditor, HTML report, dotfiles, restore script
```

---

## Profile System

Select one or more. They stack. Each has an info button that shows exactly what installs before you commit.

| Profile | What It's For |
|---|---|
| 🤖 **AI / ML** | Ollama (local LLM runtime), Docker/Podman Desktop, cloud CLIs (AWS / Azure / GCP), Kubernetes (kubectl / helm), PostgreSQL, Redis, DBeaver, Bruno, JetBrains Toolbox. Opt-in toggle: PyTorch GPU-matched (CUDA / DirectML / CPU-only) + pip ML base (numpy / pandas / matplotlib / scikit-learn / jupyter) |
| 🌐 **Web / Full-Stack** | Node.js via NVM, .NET SDK 8, Java (Temurin JDK 21), Docker/Podman Desktop, PostgreSQL, Redis, cloud CLIs (AWS / Azure / GCP), Bruno (API client), DBeaver, JetBrains Toolbox |
| 🎮 **Game Dev** | Unity Hub, Godot, CMake, Ninja, .NET SDK 8, JetBrains Toolbox |
| ⚙️ **Systems / Low-Level** | Rust toolchain (via rustup), Wireshark, Nmap, Sysinternals Suite, CMake, Ninja, cloud CLIs, JetBrains Toolbox |
| 🔌 **Hardware / Robotics** | Arduino IDE, PuTTY, CMake, Ninja, Sysinternals Suite, Wireshark; Rust toolchain (via rustup) |
| ⚡ **Absentmind Mode** | All of the above. No questions. |
| 🎛️ **Custom** | Pick individual tools from any profile. |

---

## What Makes This Different

| Feature | Winget / Scoop | Dev Home | Hand-rolled `.ps1` | **AM-DevKit** |
|---|---|---|---|---|
| GPU detection + ML stack selection | ❌ | ❌ | ⚠️ DIY | ✅ |
| Correct PyTorch build auto-selected | ❌ | ❌ | ⚠️ DIY | ✅ |
| App installs | ✅ | ✅ | ✅ | ✅ |
| Developer profile system (ai-ml / web / systems / game / hw) | ❌ | Partial | ⚠️ DIY | ✅ |
| Granular per-tool exclusions | ❌ | ❌ | ⚠️ DIY | ✅ |
| Hardware / Robotics profile | ❌ | ❌ | ❌ | ✅ |
| Install manifest (every tool, version, timestamp) | ❌ | ❌ | ❌ | ✅ |
| One-command restore on any future machine | ❌ | ❌ | ❌ | ✅ |
| Post-install HTML report | ❌ | ❌ | ❌ | ✅ |
| PATH conflict auditor | ❌ | ❌ | ❌ | ✅ |
| Dotfile seeding (.gitconfig, .bashrc, PS profile) | ❌ | ❌ | ⚠️ DIY | ✅ |
| System Restore Point (automatic, before anything runs) | ❌ | ❌ | ❌ | ✅ |
| Windows sanitation (bundled, auditable, no downloads) | ❌ | ❌ | ⚠️ DIY | ✅ opt-in |

> **On Windows sanitization:** The optional sanitation step runs a bundled PowerShell script (`scripts/sanitize.ps1`) that applies a curated set of privacy and performance registry/service tweaks — no external downloads, no GUI, fully auditable in the repo. Tweak selection was researched against [Chris Titus Tech's WinUtil](https://github.com/ChrisTitusTech/winutil) (MIT) and verified current as of April 2026. AM-DevKit's implementation is independent native PowerShell — no WinUtil code executes at runtime. See [`docs/THIRD_PARTY_NOTICES.md`](docs/THIRD_PARTY_NOTICES.md) for full attribution.

---

## The GPU Magic

This is AM-DevKit's most significant differentiator. Very few Windows installers attempt this level of GPU intelligence.

```
NVIDIA detected?
  → Query CUDA version from nvidia-smi
  → Select the correct PyTorch wheel index URL for that CUDA version automatically

AMD detected?
  → Install PyTorch via DirectML (torch-directml) — the stable Windows GPU path

No discrete GPU / VM?
  → Install CPU-only PyTorch
  → No wasted disk space on CUDA packages
```

PyTorch installation is opt-in (`--install-ml-wheels` / GUI toggle). You never touch `--index-url`. You never Google "which PyTorch version for CUDA 12.1." The right index URL is selected automatically — you just confirm and walk away.

---

## What You Get After Install

- **`devkit-manifest.json`** — every tool installed, version, timestamp, method
- **`restore-devkit.ps1`** — run this on any future machine to reproduce this exact environment
- **`post-install-report.html`** — opens in your browser. Path Auditor results first (red banner if conflicts, green if clean). Full install summary. Post-install Launchpad with one-click next steps.
- **Seeded dotfiles** — `.gitconfig` with sane defaults, `.bashrc`, PowerShell profile with modern CLI aliases

---

## Core Stack

**Bootstrap foundation** (always installs, required for everything else to function):

`Git` · `Git LFS` · `Python 3` · `Scoop`

**Always installs** (every run, excludable individually):

`GitHub CLI` · `Windows Terminal` · `PowerShell 7` · `VS Code` · `Cursor` · `Oh My Posh` · `Tailscale` · `uv` · `7-Zip`

**Scoop CLI suite** (always installs via Scoop):

`bat` · `ripgrep` · `fd` · `fzf` · `jq` · `lazygit` · `delta`

**Profile-dependent** (only with relevant profile selected):

`Rust` (systems / game-dev / hardware-robotics / ai-ml) · `Node via NVM` (web-fullstack)

---

## Extras (Optional — Personal Preference)

Not dev stack. Presented separately after profile selection.

`PowerToys` · `Obsidian` · `OBS Studio` · `ShareX` · `HWiNFO64` · `WizTree` · `VLC` · `Bitwarden` · `KeePassXC` · `Fork` · `Discord` · `AutoHotkey` · `ffmpeg`

---

## Safety First

- **System Restore Point** is forced before anything touches your machine. No opt-out.
- **Sanitation is preset-level toggleable** — choose between Minimal (light privacy cleanup) or Standard (full privacy + performance tuning) before anything runs. The preset can be disabled entirely. *(Native PowerShell — no external downloads. Nothing in sanitation is required for AM-DevKit to work.)*
- **Pre-Install Summary** shows tool count, estimated time, and estimated disk usage before you commit.
- **Layer 8.5: Disposable Workspace** (opt-in) — configure Windows Sandbox or a Dev Container for testing experimental code without touching your host OS.

---

## Requirements

- Windows 10 (build 1903+) or Windows 11
- PowerShell 5.1+ (built-in — no pre-install required)
- Internet connection
- ~30–40GB free disk space for a full Absentmind Mode install (CUDA wheels, multiple IDEs, Docker, cloud CLIs — plan for more, not less)

Administrator privileges required for sanitation and system-level installs.

---

## Installation

**Repository:** [github.com/Absentmind86/am-devkit](https://github.com/Absentmind86/am-devkit)

> ⚠️ **Pre-release.** Review `bootstrap/install.ps1` before you run it. The default action is a Layer 0 system scan only; use `-Gui` or `-FullInstall` for more (see script comment help).

**Fresh-machine one-liner** (installs git if missing, clones the repo, opens the GUI):

```powershell
irm https://raw.githubusercontent.com/Absentmind86/am-devkit/main/bootstrap/fresh.ps1 | iex
```

This is the quickest entry point. It clones the repo to `%USERPROFILE%\am-devkit` and launches the Phase 3 GUI. Re-running it updates the local clone and re-opens the GUI.

**Verified install** (downloads to file, shows SHA256, asks before running — recommended if you want proof of integrity):

```powershell
irm https://raw.githubusercontent.com/Absentmind86/am-devkit/main/bootstrap/Verify-Bootstrap.ps1 | iex
```

This fetches `fresh.ps1` to a temp file, computes its SHA256, compares it against the published hash in [`bootstrap/CHECKSUMS.sha256`](bootstrap/CHECKSUMS.sha256), and only proceeds with your explicit `Y`. The checksum file is automatically updated by CI on every push that changes `fresh.ps1`.

**Clone then run** (recommended if you want to read everything first):

```powershell
git clone https://github.com/Absentmind86/am-devkit.git
cd am-devkit
.\bootstrap\install.ps1          # Layer 0 scan → system-profile.json
# .\bootstrap\install.ps1 -Gui   # Flet launcher
# .\bootstrap\install.ps1 -FullInstall -DryRun
```

Watch [the GitHub repository](https://github.com/Absentmind86/am-devkit) for updates.

### SmartScreen / execution policy notes

**`irm | iex` (the one-liner):** PowerShell pipes the script directly into memory — no file is saved, so Windows never attaches a Mark-of-the-Web zone tag. SmartScreen does not block it. HTTPS provides transport integrity (TLS). If you additionally want content integrity (SHA256 verification), use the **Verified install** command above.

**Downloaded `.ps1` (clone-then-run):** If you download the files via a browser instead of `git clone`, Windows marks them as "from the internet." PowerShell will refuse to run them until you unblock them:

```powershell
# Run once from the repo root after a browser download:
Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File
```

`git clone` does not attach a zone tag, so cloning from the command line (as shown above) does not require this step.

**Scripts are not code-signed.** The `.ps1` files can be read in full at [github.com/Absentmind86/am-devkit](https://github.com/Absentmind86/am-devkit) before you run them.

---

## Known caveats

- **First-time WSL enable requires a reboot.** When you select **Enable WSL** (or pick a
  profile that pulls in Docker Desktop / Podman Desktop), the installer runs DISM to enable
  `Microsoft-Windows-Subsystem-Linux` + `VirtualMachinePlatform`. On a clean Windows install
  this returns exit `3010`: the installer prints a prominent **REBOOT REQUIRED** notice,
  defers `wsl --install -d <distro>` to avoid a half-enabled feature, and exits cleanly.
  **Reboot Windows, then re-launch the installer with the same flags** — idempotent steps
  skip and WSL distro install resumes.
- **Running on a VM?** Layer 0 detects virtualized hosts (VMware, VirtualBox, Hyper-V, KVM,
  QEMU, Xen, Parallels) and surfaces this in `system-profile.json` (`system.is_vm`). The
  pre-install summary warns when **AI/ML + `--install-ml-wheels`** is selected on a VM
  without GPU passthrough (PyTorch will install but won't see a GPU), and when **WSL** is
  enabled on a guest where nested virtualization isn't exposed by the host hypervisor.

---

## Roadmap

- **Phase 0** ✅ — Vision, architecture, full specification
- **Phase 1** ✅ — Proof of concept: system scan, GPU detection, PowerShell bootstrap
- **Phase 2** ✅ — Full layer stack (CLI), native sanitization, manifest + HTML report
- **Phase 3** ✅ — Flet GUI, catalog exclusions, dotfile / vault / restore wiring
- **Phase 4** 🔄 — Release: VM testing ([docs/RELEASE_TESTING.md](docs/RELEASE_TESTING.md)), SmartScreen docs, distribution (Azure Trusted Signing planned for v1.0), launch

---

## About

AM-DevKit is a project under the **Absentmind** brand — built by someone who got tired of spending the first two days on a new machine reinstalling everything from memory.

---

## License and third-party software

This project is released under the **[MIT License](LICENSE)**.

AM-DevKit **does not bundle** Winget-packaged apps in the repository; it invokes Winget/Scoop/rustup at install time. Python UI/runtime dependencies (**rich**, **flet**) come from PyPI under their own licenses.

See **[docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md)** for attribution, Microsoft Winget expectations, ML/CUDA disclaimers, and contributor guidance when adding dependencies.

---

## Troubleshooting

**`winget` fails mid-install with a source error**
Run `winget source reset --force` to refresh the msstore/winget source index, then re-run the installer — idempotent steps will skip already-installed tools.

**A tool shows `[failed]` in the HTML report but the rest completed**
Each layer is fault-isolated: one failure never aborts the run. Re-run with `--dry-run` first to confirm the tool is still missing, then run again without `--dry-run` — the tool will be retried while everything else skips.

**`winget install` hangs interactively**
AM-DevKit passes `--accept-package-agreements --accept-source-agreements` to all winget calls. If a package still prompts, it may have changed its installer type. Pin or exclude it via the GUI Custom Mode or `--exclude-catalog-tool <id>` and file an issue.

**WSL install fails after enabling (exit 3010 or 50)**
This is a first-time WSL enable that requires a reboot. The installer detects exit 3010 and prints a REBOOT REQUIRED notice. Reboot Windows, then re-run the installer with the same flags — idempotent steps skip and WSL distro install resumes. See `Known caveats` above.

**Python not found after install**
Run `Update-ProcessPathFromMachine` in a new PowerShell window (this function is in `bootstrap/install.ps1`) or simply open a fresh terminal — Python's installer registers its PATH entry in the Machine scope, which the current session may not yet see.

**Sanitization fails or applies unexpected tweaks**
The tweak list for each preset is documented in `config/am-devkit-winutil.json` (Minimal) and `config/am-devkit-winutil-standard.json` (Standard). The implementation is in `scripts/sanitize.ps1`. To adjust what runs, edit the PS1 directly — no external download or hash update required.

---

## Contributing

This project is pre-release. The architecture is locked and documented in [`docs/PROJECT.md`](docs/PROJECT.md).

If you want to contribute, read `docs/CONTRIBUTING.md` first. The short version: if you'd have to explain what a tool is to a working developer, it probably doesn't belong in Core.

---

## Support

AM-DevKit is free. If it saved you an afternoon, you know where to find me.

[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20the%20project-ff5e5b?logo=ko-fi)](https://ko-fi.com/absentmind)
[![GitHub Sponsors](https://img.shields.io/badge/GitHub%20Sponsors-♥-ea4aaa?logo=github)](https://github.com/sponsors/absentmind)

---

<div align="center">
<sub>Built by Absentmind · MIT License · <a href="docs/THIRD_PARTY_NOTICES.md">Third-party notices</a> · Windows only (for now)</sub>
</div>
