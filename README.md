<div align="center">

# Absentmind's DevKit

### *You just got a new machine. Run one thing. Walk away.*
### *Come back to a fully configured, GPU-intelligent development environment.*

[![Status](https://img.shields.io/badge/status-pre--release-orange)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
[![Made by](https://img.shields.io/badge/made%20by-Absentmind-purple)]()

</div>

---

## What Is This?

AM-DevKit is a **Windows developer toolkit installer**. It is not a package manager. It is not a dotfile manager. It is not a debloater.

It is an **opinionated orchestration layer** that ties all of those things together — detects your hardware, makes smart decisions, installs the right stack for your work, and leaves you with a documented, reproducible environment you can restore on any future machine.

Optional Windows sanitation (via CTT WinUtil) is available but off by default — the installer works perfectly without it.

No other installer does all of this. Most handle apps *or* the OS — never both. None detect your GPU and install the correct ML stack automatically. Nobody ships a recoverable manifest.

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
[Optional] Windows sanitation via CTT WinUtil — off by default, fully toggleable
       │
       ▼
Your selected profiles install in order
       │
       ▼
GPU detected → correct PyTorch build installed automatically
       │
       ▼
Post-install: Path Auditor, HTML report, dotfiles, restore script
```

---

## Profile System

Select one or more. They stack. Each has an info button that shows exactly what installs before you commit.

| Profile | What It's For |
|---|---|
| 🤖 **AI / ML** | PyTorch (GPU-matched automatically), HuggingFace stack, Ollama, Jupyter, Open WebUI |
| 🌐 **Web / Full-Stack** | Node, Docker, PostgreSQL, Redis, Bruno, Playwright, cloud CLIs |
| 🎮 **Game Dev** | Unity Hub, Godot, Visual Studio Community, DirectX, CMake |
| ⚙️ **Systems / Low-Level** | Rust, C/C++, MSVC, Visual Studio Community, Wireshark |
| 🔌 **Hardware / Robotics** | Arduino, PlatformIO, pyserial, Zadig, PuTTY, Sigrok |
| ⚡ **Absentmind Mode** | All of the above. No questions. |
| 🎛️ **Custom** | Pick individual tools from any profile. |

---

## What Makes This Different

| Feature | CTT WinUtil | Winget | Dev Home | **AM-DevKit** |
|---|---|---|---|---|
| GPU detection | ❌ | ❌ | ❌ | ✅ |
| Correct PyTorch auto-install | ❌ | ❌ | ❌ | ✅ |
| App installs | ❌ | ✅ | ✅ | ✅ |
| Multi-select profile system | ❌ | ❌ | Partial | ✅ |
| Granular custom checkboxes | ❌ | ❌ | ❌ | ✅ |
| Hardware / Robotics profile | ❌ | ❌ | ❌ | ✅ |
| Install manifest | ❌ | ❌ | ❌ | ✅ |
| One-command restore on new machine | ❌ | ❌ | ❌ | ✅ |
| Post-install HTML report | ❌ | ❌ | ❌ | ✅ |
| Path conflict auditor | ❌ | ❌ | ❌ | ✅ |
| Dotfile seeding | ❌ | ❌ | ❌ | ✅ |
| System Restore Point | ❌ | ❌ | ❌ | ✅ |
| Optional Windows sanitation (CTT WinUtil) | ✅ core | ❌ | ❌ | ✅ opt-in |

---

## The GPU Magic

This is AM-DevKit's most significant differentiator. No other Windows installer does this.

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
- **Sanitation is preset-level toggleable** — choose between Minimal (light privacy cleanup) or Standard (full privacy + performance tuning) before anything runs. The preset can be disabled entirely. *(This runs Chris Titus Tech's WinUtil with our curated preset. Nothing in sanitation is required for AM-DevKit to work.)*
- **Pre-Install Summary** shows tool count, estimated time, and estimated disk usage before you commit.
- **Layer 8.5: Disposable Workspace** (opt-in) — configure Windows Sandbox or a Dev Container for testing experimental code without touching your host OS.

---

## Requirements

- Windows 10 (build 1903+) or Windows 11
- PowerShell 5.1+ (built-in — no pre-install required)
- Internet connection
- ~20GB free disk space for a full Absentmind Mode install

Administrator privileges required for sanitation and system-level installs.

---

## Installation

**Repository:** [github.com/Absentmind86/Absentminds-DevKit-Windows](https://github.com/Absentmind86/Absentminds-DevKit-Windows)

> ⚠️ **Pre-release.** Review `bootstrap/install.ps1` before you run it. The default action is a Layer 0 system scan only; use `-Gui` or `-FullInstall` for more (see script comment help).

**Fresh-machine one-liner** (installs git if missing, clones the repo, opens the GUI):

```powershell
irm https://raw.githubusercontent.com/Absentmind86/Absentminds-DevKit-Windows/main/bootstrap/fresh.ps1 | iex
```

This is the recommended entry point for a brand-new Windows install. It clones the repo to `%USERPROFILE%\Absentminds-DevKit-Windows` and launches the Phase 3 GUI. Re-running it updates the local clone and re-opens the GUI.

**Clone then run** (recommended if you want to read everything first):

```powershell
git clone https://github.com/Absentmind86/Absentminds-DevKit-Windows.git
cd Absentminds-DevKit-Windows
.\bootstrap\install.ps1          # Layer 0 scan → system-profile.json
# .\bootstrap\install.ps1 -Gui   # Flet launcher
# .\bootstrap\install.ps1 -FullInstall -DryRun
```

Watch [the GitHub repository](https://github.com/Absentmind86/Absentminds-DevKit-Windows) for updates.

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
- **Phase 2** ✅ — Full layer stack (CLI), CTT integration, manifest + HTML report
- **Phase 3** ✅ — Flet GUI, catalog exclusions, dotfile / vault / restore wiring
- **Phase 4** 🔄 — Release: VM testing ([docs/RELEASE_TESTING.md](docs/RELEASE_TESTING.md)), signed installer TBD, docs, launch

---

## About

AM-DevKit is a project under the **Absentmind** brand — built by someone who got tired of spending the first two days on a new machine reinstalling everything from memory.

---

## License and third-party software

This project is released under the **[MIT License](LICENSE)**.

AM-DevKit **does not bundle** Chris Titus Tech WinUtil or Winget-packaged apps in the repository; it **downloads or invokes** them at install time. Python UI/runtime dependencies (**rich**, **flet**) come from PyPI under their own licenses.

See **[docs/THIRD_PARTY_NOTICES.md](docs/THIRD_PARTY_NOTICES.md)** for attribution, WinUtil (MIT), Microsoft Winget expectations, ML/CUDA disclaimers, and contributor guidance when adding dependencies.

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
