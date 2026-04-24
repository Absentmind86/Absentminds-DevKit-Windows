# Absentmind's DevKit
### Master Project Document — v0.3
**Brand:** Absentmind (Umbrella)
**Short Name:** AM-DevKit
**Status:** Pre-Development / Scoping
**Last Updated:** 2026-04-21

---

## Changelog

| Version | Date | Notes |
|---|---|---|
| v0.1 | 2025-04-21 | Initial document — full architecture, layers, profiles, roadmap |
| v0.2 | 2025-04-21 | Frontier LLM review pass: PowerToys, Scoop, Nerd Fonts, modern CLI suite, local DBs, JetBrains Toolbox, VS Community, DevToys, Sysinternals, Continue.dev, Gradio/Streamlit/FastAPI, Open WebUI, Playwright, sops/age, Docker GPU passthrough, git-delta dotfile config |
| v0.3 | 2026-04-21 | Architecture overhaul: Core/Profile/Extras split, multi-select profiles, Hardware/Robotics profile added, Absentmind Mode redefined as all-profiles, Custom Mode granular, Python moved to Core, Pre-Flight layer added (Restore Point + Absentmind toggle), Path Auditor in Layer 8, Layer 8.5 Disposable Workspace added, Tailscale added Layer 2, Extras section, info tooltip UI decision, Flet as GUI recommendation, Content Creator profile folded into Extras |
| v0.3.1 | 2026-04-21 | UX gaps addressed: Windows Sanitation toggle added to Pre-Flight UI (category-level, not all-or-nothing), Pre-Install Summary Screen added (tool count, time/disk estimate), Post-Install Launchpad added to HTML report (profile-aware, one-click actions) |
| v0.3.2 | 2026-04-21 | Final polish: sanitation reassurance note added, Absentmind Mode pre-install summary variant, GPU verification output humanized (✅/⚠️ language instead of True/False) |

---

## Vision Statement

> *"You just got a new machine. Run one thing. Walk away. Come back to a fully configured, GPU-intelligent, bloat-free development environment — personalized to your stack, documented, and reproducible."*

No tool currently does this completely. Most installers either handle apps OR the OS — never both. None detect GPU hardware and install the correct ML stack automatically. Nobody ships a recoverable manifest. Absentmind's DevKit fills that gap.

---

## Brand Context

```
Absentmind (Brand Umbrella)
├── Absentmind's DevKit        ← This project (AM-DevKit)
├── AM Studio                  ← Separate product umbrella
│   └── AM Pixel               ← SNES-era AI sprite generator
├── Kyle's Quest               ← Text RPG
├── GaussBow Mk.1              ← Gauss cannon project
├── Nerf AI Turret             ← CV/robotics starter
└── RV EZ FIX LLC              ← Active repair business
```

AM-DevKit is a standalone product under the Absentmind brand — not under AM Studio. The "AM-DevKit" shorthand is expected to emerge organically. The full name **Absentmind's DevKit** is the canonical name and should be used in all official contexts to build brand recognition.

---

## What Makes This Different

| Feature | CTT WinUtil | Winget | Dev Home | **AM-DevKit** |
|---|---|---|---|---|
| Bloat removal | ✅ | ❌ | ❌ | ✅ (via CTT) |
| App installs | ❌ | ✅ | ✅ | ✅ |
| GPU detection | ❌ | ❌ | ❌ | ✅ |
| Correct PyTorch | ❌ | ❌ | ❌ | ✅ |
| Install manifest | ❌ | ❌ | ❌ | ✅ |
| Restore point | ❌ | ❌ | ❌ | ✅ |
| Profile system | ❌ | ❌ | Partial | ✅ multi-select |
| Custom checkboxes | ❌ | ❌ | ❌ | ✅ |
| Post-install report | ❌ | ❌ | ❌ | ✅ |
| Dotfile seeding | ❌ | ❌ | ❌ | ✅ |
| Path Auditor | ❌ | ❌ | ❌ | ✅ |
| Disposable Workspace | ❌ | ❌ | ❌ | ✅ (opt-in) |
| WSL seeding | ❌ | ❌ | ❌ | ✅ (toggle) |
| Hardware/Robotics profile | ❌ | ❌ | ❌ | ✅ |

---

## Architecture Overview

### Execution Flow

```
[Launch Bootstrap]
       │
       ▼
[Pre-Flight]
  → Force System Restore Point
  → Absentmind Mode toggle (skip all prompts, install everything?)
       │
       ▼
[Layer 0: System Scan]
  CPU / GPU / RAM / Disk / OS / Existing Installs
       │
       ▼
[Profile Selection UI]
  ┌─────────────────────────────────────────────┐
  │  Select one or more (or Absentmind Mode):   │
  │  ☐ AI/ML  ☐ Web  ☐ Game Dev                │
  │  ☐ Systems  ☐ Hardware/Robotics             │
  │  [⚡ Absentmind Mode — All of the above]    │
  │  [⚙️  Custom — pick individual tools]        │
  └─────────────────────────────────────────────┘
       │
       ▼
[CORE — Always Installs]
  Git + Git LFS, Python, Scoop, GitHub CLI, Windows Terminal, PowerShell 7,
  VS Code, Cursor, Oh My Posh, Tailscale, uv, 7-Zip + Scoop CLI suite
       │
       ▼
[Layer 1: Windows Sanitation]
  → Invoke CTT WinUtil (unattended, AM config)
       │
       ▼
[Layer 2: Core Infrastructure]
  Git, Terminal, SSH, PowerShell 7, Tailscale
       │
       ▼
[Layer 3: Editors & IDEs]
  VS Code, Cursor, extensions pack
       │
       ▼
[Layer 4: Languages & Runtimes]
  Python version mgmt (pyenv-win), Node (nvm-windows), Rust, optional others
       │
       ▼
[Layer 5: AI/ML Stack]
  GPU branch logic → correct PyTorch wheel
       │
       ▼
[Layer 6: DevOps & Containers]
  Docker, WSL2, WSL seeding toggle, kubectl, cloud CLIs
       │
       ▼
[Layer 7: Profile-Specific Tools]
  Installs selected profile stacks only
       │
       ▼
[Layer 8: Configuration & State]
  Dotfiles, Path Auditor, manifest, restore script, post-install report
       │
       ▼
[Layer 8.5: Disposable Workspace — opt-in]
  Windows Sandbox config OR Dev Container setup
```

### Technology Stack

| Component | Technology | Rationale |
|---|---|---|
| Bootstrap entry point | PowerShell `.ps1` | Native to Windows, zero dependencies, single file |
| Main runtime | Python (after install) | Logic flexibility, rich CLI output, GPU query libraries |
| GUI (Profile selector) | Flet (Python/Flutter) | Async-native, modern look, zero JS/CSS headache, unified Python codebase |
| Manifest format | JSON | Human-readable, diffable |
| Config format | TOML | Cleaner than JSON for user-facing config |
| Package manager | Winget (primary), Chocolatey (fallback) | Winget is Microsoft-native, Choco fills gaps |

**Bootstrap logic:** PowerShell installs Python first → hands off to Python for all subsequent logic. Best of both worlds — no dependency on Python to start, full Python flexibility for the hard parts.

---

## Pre-Flight

Runs before anything else touches the system. Non-negotiable safety layer.

### System Restore Point
Forced automatically before Layer 1 (Sanitation) begins. No prompt, no opt-out. Labeled with timestamp and DevKit version so you can find it easily in Windows Recovery.

```powershell
Checkpoint-Computer -Description "AM-DevKit v0.3 — Pre-Install $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -RestorePointType MODIFY_SETTINGS
```

### Absentmind Mode Toggle
Presented as the first UI decision. If enabled:
- All profiles are selected automatically
- No further prompts during install
- Full curated stack installs and gets out of your way
- Extras are still opt-in (they're personal preference, not dev stack)

> *For the person whose answer to "which profile?" is genuinely "yes."*

### Windows Sanitation Toggle

Sanitation is on by default but **explicitly surfaced in the UI** — not silent. Before the install begins, the user sees what CTT WinUtil will do, organized by category, with the ability to toggle any category off.

**Presented as:**
```
Windows Sanitation  [ON ▼]
  ✅ Bloatware removal     (Xbox, Cortana, Candy Crush, etc.)
  ✅ Privacy hardening     (telemetry, advertising ID)
  ✅ Explorer fixes        (show extensions, show hidden files)
  ✅ Performance tweaks    (power plan, disable fast startup)
  ☐ OneDrive removal      (optional — you decide)
```

Toggling a category off removes it from the CTT config passed to WinUtil. The user isn't editing JSON — they're clicking checkboxes. The underlying config handles it.

**Why this matters:** Without this, Layer 1 is a blind leap. The user hits Install, then watches things disappear from their machine with no prior agreement. That erodes trust at exactly the wrong moment — right before the impressive parts.

> *This runs Chris Titus Tech's WinUtil with our curated settings. Nothing here is required for AM-DevKit to work — you can turn it all off and still get a fully configured dev environment.*

### Pre-Install Summary Screen

The final screen before anything touches the machine. Shown after profile selection, after sanitation toggle, before first execution.

```
You are about to:

  🧹 Modify Windows  →  Bloatware removal, privacy tweaks, Explorer fixes
  📦 Install Core    →  Git, VS Code, Python, Terminal, Scoop (8 tools)
  🤖 AI/ML Profile   →  PyTorch (CUDA), Ollama, HuggingFace stack (14 tools)
  🌐 Web Profile     →  Node, Docker, PostgreSQL, Bruno (11 tools)
  ⏱  Est. time       →  ~25 minutes on your connection
  💾 Est. disk use   →  ~12GB

  [View full tool list]     [Back]     [Start Install]
```

Time and disk estimates are generated from `system-profile.json` (connection speed + storage detected in Layer 0). "View full tool list" expands every tool that will be installed, version where known. No surprises.

**Absentmind Mode variant** — if Absentmind Mode was selected, the summary screen uses a different tone:
```
⚡ Absentmind Mode — Full Stack Install

  You're about to install the complete curated stack.
  (~47 tools, ~18–35 min depending on your connection)

  [View full tool list]     [Back]     [Let's go →]
```
No itemized breakdown — they already said "all of it." Just confirm the commitment and get moving.

---

## Layer 0: System Intelligence

Runs silently before anything else. Generates a `system-profile.json` used by all subsequent layers.

**Detects:**
- CPU: vendor, model, core/thread count
- GPU: vendor (NVIDIA/AMD/Intel/None), model, VRAM
- RAM: total, available
- Storage: type (NVMe/SATA/HDD), available space
- OS: Windows version, build number, architecture
- **System / virtualization** (`system` block): manufacturer, model, `is_vm`, `vm_hint`
  (matches VMware, VirtualBox, Hyper-V, KVM, QEMU, Xen, Parallels, bhyve)
- Existing installs: scans for already-installed tools (skip, don't reinstall)
- Driver status: GPU driver version, date
- Internet: speed check (queue large downloads intelligently)

**Outputs:** `system-profile.json` (schema `1.1`) + human-readable summary shown during profile selection

**Warnings generated:**
- Low disk space (< 20GB free)
- Outdated GPU driver
- GPU detected but no CUDA toolkit
- Virtualized host detected (warns that GPU passthrough is uncommon and WSL2 nesting may be unsupported)

---

## Core — Always Installs

**Regardless of profile selection, these install on every run. No exceptions.**

The litmus test for Core: *if you'd have to explain what it is to a developer, it doesn't belong here.*

| Tool | Why Core | Notes |
|---|---|---|
| **Git + GitHub CLI + Git LFS** | Universal. No developer doesn't need this. | Git Bash not included |
| **Windows Terminal** | The shell you'll live in | |
| **PowerShell 7** | Replaces the ancient built-in. Required for bootstrap itself | |
| **VS Code + Cursor** | Universal editor baseline | Excludable via `--exclude-catalog-tool` |
| **Scoop** | User-scoped package manager. Required for many Layer 2+ tools | |
| **Python 3 (latest stable)** | Near-universal dependency | |
| **uv** | Fast Python package manager | |
| **7-Zip** | Everyone needs it eventually | |
| **Oh My Posh** | Practical prompt theming | |
| **Tailscale** | Zero-config mesh VPN | |
| **System Restore Point** | Pre-flight safety net | Orchestration step, not an installed package |
| **Path Auditor** | Runs post-install, flags conflicts | Orchestration step, not an installed package |

> **Bloat removal (CTT WinUtil)** is opt-in, not Core. It runs as Layer 1 only when sanitation is enabled.
> **Nerd Fonts** is not currently automated — Oh My Posh works without them (prompt degrades gracefully).

*Python version management (pyenv-win), package tooling (uv, pipx), and virtual environments remain in Layer 4 — Core installs the runtime, Layer 4 installs the ecosystem.*

---

## Layer 1: Windows Sanitation

**Method:** Invoke CTT WinUtil in unattended mode with a curated `am-devkit-winutil.json` config. We own the opinionated config — CTT handles the execution.

```powershell
# Invocation (internal, not user-facing)
irm christitus.com/win | iex -Config "$PSScriptRoot\config\am-devkit-winutil.json" -Silent
```

**Our CTT config covers:**

*Bloatware Removal*
- Xbox Game Bar (unless Gaming profile)
- Cortana
- Teams (consumer)
- OneDrive (optional — user prompted)
- All preinstalled Store garbage (Candy Crush, etc.)
- Tips, Get Started, Weather widget
- All "suggested" apps

*Registry & Privacy Hardening*
- Disable telemetry
- Disable advertising ID
- Disable feedback prompts
- Disable background app data for non-essentials
- Long path support enabled
- Developer Mode enabled

*Explorer & Shell Sanity*
- Show file extensions by default
- Show hidden files
- Right-click → Open Terminal here
- Disable Quick Access clutter

*Performance Tweaks*
- High performance power plan
- Disable hibernation (SSD systems)
- Disable fast startup
- Disable mouse acceleration
- Virtual memory tuning (based on detected RAM)

---

## Layer 2: Core Developer Infrastructure

### Package Managers
- [ ] Winget (primary — Microsoft native)
- [ ] **Scoop** — user-scoped, portable, no admin required. Complements Winget perfectly. Huge dev CLI bucket ecosystem. Install early in bootstrap — many Layer 2 tools come via Scoop.
- [ ] Chocolatey (fallback for gaps neither Winget nor Scoop cover)

### Version Control
- [ ] Git (latest stable)
- [ ] Git Bash
- [ ] GitHub CLI (`gh`)
- [ ] Git LFS
- [ ] Global `.gitconfig` seeded with sane defaults:
  - `core.autocrlf = true` (Windows)
  - `core.editor = code --wait`
  - `init.defaultBranch = main`
  - `credential.helper = manager`

### Terminals
- [ ] Windows Terminal (with curated default profile)
- [ ] PowerShell 7 (replaces ancient built-in)
- [ ] Oh My Posh (prompt theming — practical, not just cosmetic)
- [ ] **Nerd Fonts** — required for Oh My Posh icons/ligatures. Without this, the prompt looks broken on fresh installs. Auto-installed via `oh-my-posh font install`. Recommended: CaskaydiaCove NF or JetBrainsMono NF. Auto-set as default font in seeded Terminal + VS Code settings.
- [ ] Terminal profile seeded with AM-DevKit default settings

### Modern CLI Suite (via Scoop)

These "modern Unix replacements" dramatically improve terminal life and pair perfectly with Oh My Posh + Git Bash. Aliases and configs seeded into dotfiles automatically.

| Tool | Replaces | Purpose |
|---|---|---|
| `bat` | `cat` | Syntax-highlighted file viewer |
| `git-delta` | git diff | Beautiful, readable diffs — auto-set as git pager in `.gitconfig` |
| `ripgrep` (`rg`) | `grep` | Insanely fast recursive search |
| `fd` | `find` | Simple, fast file finder |
| `eza` | `ls` | Modern ls with icons, git status |
| `zoxide` | `cd` | Smart directory jumper (learns your habits) |
| `fzf` | — | Fuzzy finder — transforms history, file search, etc. |
| `lazygit` | git CLI | TUI for git — visual staging, branching, stashing |
| `btop` | Task Manager | Beautiful resource monitor (CPU/GPU/RAM/disk/network) |
| `jq` | — | JSON processor — essential for API work |
| `yq` | — | YAML processor — same as jq but for YAML/TOML |
| `tldr` | `man` | Practical command examples, not wall-of-text manpages |
| `just` | `make` | Modern command runner — project task automation |
| `hyperfine` | — | CLI benchmarking tool |
| `dust` | `du` | Intuitive disk usage visualizer |

All aliases pre-configured in seeded `.bashrc` / PowerShell profile (e.g. `ls` → `eza --icons`, `cat` → `bat`).

### SSH & Keys
- [ ] OpenSSH client enabled (Windows feature)
- [ ] Generate ED25519 SSH key pair on first run (if none exists)
- [ ] Auto-add to `ssh-agent`
- [ ] Optional: push public key to GitHub via `gh auth`

---

## Layer 3: Editors & IDEs

### Core Editors
- [ ] VS Code (stable)
- [ ] Cursor (AI-native editor)

### VS Code Extensions — AM-DevKit Base Pack

*Essential*
- [ ] GitLens
- [ ] Prettier — Code formatter
- [ ] ESLint
- [ ] Error Lens (inline error display)
- [ ] Path Intellisense

*Python*
- [ ] Python (Microsoft)
- [ ] Pylance
- [ ] Ruff (linter/formatter — replaces flake8 + black)
- [ ] Jupyter

*Web*
- [ ] Auto Rename Tag
- [ ] CSS Peek
- [ ] REST Client or Thunder Client

*DevOps*
- [ ] Docker
- [ ] Remote - SSH
- [ ] Remote - WSL

*Utilities*
- [ ] Material Icon Theme
- [ ] One Dark Pro (default theme — overrideable)
- [ ] CodeSnap (screenshot code)
- [ ] TODO Highlight

*AI (if applicable)*
- [ ] GitHub Copilot (only if user has license — not forced)

### VS Code Settings
- `config/vscode/settings.json` is currently a stub (`{}`) — populate before this is implemented
- Extension seeding via `config/vscode/extensions.json` is implemented

---

## Layer 4: Languages & Runtimes

### Python
> **Note:** Python 3 (latest stable) is now installed in Core. Layer 4 installs the version management ecosystem on top of it.

- [ ] `pyenv-win` — version management (critical for multi-project work)
- [ ] `pip` upgraded immediately post-install
- [ ] `pipx` — isolated global CLI tools
- [ ] `virtualenv`
- [ ] `uv` — Rust-based package manager (10-100x faster than pip, emerging standard)
- [ ] `ruff` — Rust-based linter/formatter (replaces flake8 + black)

### Node.js
- [ ] `nvm-windows` — version manager (NEVER install Node directly)
- [ ] Node.js LTS via nvm
- [ ] `npm`, `pnpm`, `yarn` all available

### Rust
- [ ] `rustup` — official Rust toolchain installer
- [ ] Stable toolchain as default
- [ ] PATH configured correctly
- [ ] Required for: Ruff, uv, Tauri, and increasing number of modern tooling

### Build Tools (Required for many packages)
- [ ] Microsoft C++ Build Tools (MSVC) — required for many Python packages, Rust crates
- [ ] CMake (Systems / Game Dev / Low-Level profiles)
- [ ] Ninja build system — pairs with CMake, faster than MSBuild
- [ ] vcpkg — Microsoft's C++ package manager (Systems / Game Dev profiles)
- [ ] MinGW / GCC (optional, Custom mode)

### Optional IDEs (Profile-Gated)
- [ ] **Visual Studio Community** — Systems / Game Dev / .NET profiles. Best full IDE for C# / C++ / DirectX on Windows. Heavy but irreplaceable for those stacks.
- [ ] **JetBrains Toolbox** — optional in Custom / Full Stack / AI/ML. One installer that manages PyCharm, IntelliJ, Rider, WebStorm, DataGrip. Install the Toolbox only — user picks individual IDEs from there.

### Optional Language Profiles
- [ ] Go (CLI tooling, infra work)
- [ ] Java / JDK (Android dev, Minecraft, enterprise)
- [ ] .NET SDK (Windows ecosystem work)

---

## Layer 5: AI / ML Stack

**This is AM-DevKit's most significant differentiator. No other installer does this.**

### GPU Detection Logic

```
┌─────────────────────────────────────────┐
│         nvidia-smi detectable?          │
│              (NVIDIA GPU)               │
└─────────────────┬───────────────────────┘
                  │ YES
                  ▼
        Query CUDA version from nvidia-smi
                  │
                  ▼
        Select correct PyTorch wheel index URL
        for detected CUDA version automatically
        (pip install torch from download.pytorch.org/whl/cuXXX)

┌─────────────────────────────────────────┐
│         NVIDIA not found.               │
│         AMD GPU detected?               │
│         (WMI query for AMD/ATI)         │
└─────────────────┬───────────────────────┘
                  │ YES
                  ▼
        Install PyTorch via DirectML
        (torch-directml — stable Windows AMD path)

┌─────────────────────────────────────────┐
│   No discrete GPU / Intel integrated    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
        Install CPU-only PyTorch
        (torch, torchvision, torchaudio)
```

### PyTorch Install Command (NVIDIA Path Example)
```bash
# Auto-generated based on detected CUDA version
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### Core ML Stack (All Paths)
- [ ] `numpy`
- [ ] `pandas`
- [ ] `matplotlib`
- [ ] `scikit-learn`
- [ ] `jupyter` + `jupyterlab`
- [ ] `ipywidgets`
- [ ] `transformers` (HuggingFace)
- [ ] `diffusers`
- [ ] `accelerate`
- [ ] `datasets`
- [ ] `tokenizers`
- [ ] `peft`
- [ ] `bitsandbytes` (quantization — NVIDIA path)
- [ ] `einops`

### Local LLM Stack
- [ ] Ollama (local LLM runner — the standard. Gets same GPU detection logic as PyTorch)
- [ ] `llama-cpp-python` (with correct CUDA/CPU backend flags — same GPU branch logic)
- [ ] **Open WebUI** — web frontend for Ollama (optional but excellent; gives a ChatGPT-like UI for local models)
- [ ] `openai` SDK (works with local endpoints too)
- [ ] `anthropic` SDK
- [ ] `langchain` (optional — checkbox)
- [ ] `litellm` (universal LLM interface)

### AI Dev Tooling
- [ ] **Continue.dev** — VS Code/Cursor extension for local Ollama integration. Pairs perfectly with the local LLM stack. Code completion + chat using your own models.
- [ ] **Gradio** — instant web UI for ML demos. One decorator turns a Python function into a shareable app.
- [ ] **Streamlit** — data app framework. Standard for model dashboards, quick demos.
- [ ] **FastAPI** — async Python web framework. Standard for model serving APIs.
- [ ] `uvicorn` — ASGI server (pairs with FastAPI)

---

## Layer 6: DevOps & Containers

### Containers & Orchestration
- [ ] Docker Desktop (with WSL2 backend configured)
- [ ] ~~Docker GPU passthrough configured~~ — **not implemented**; future work
- [x] WSL2 enabled (DISM enables `Microsoft-Windows-Subsystem-Linux` + `VirtualMachinePlatform`).
      First-time enable returns exit 3010 → installer prints a prominent **REBOOT REQUIRED**
      notice, sets `ctx.wsl_reboot_required`, and defers `wsl --install -d <distro>` with a
      clear "reboot then re-run" message instead of failing silently. No auto-resume — the
      user re-launches the installer post-reboot and idempotent steps skip.
- [x] WSL distro install (`wsl --install -d <distro>`) — opt-in via `--enable-wsl`/`--wsl-distro`;
      auto-enabled when Docker Desktop or Podman Desktop is selected
- [x] Pre-install summary warns when `--enable-wsl` is set on a host where `wsl.exe` is not
      yet on PATH (first-time enable → reboot likely), and when the host is detected as a VM
      (nested-virt caveat).
- [ ] ~~WSL Seeding Toggle~~ — **not implemented**; future work
- [ ] `kubectl`
- [ ] `helm`
- [ ] `k9s` — TUI Kubernetes cluster manager (optional — cleaner than raw kubectl)
- [ ] Terraform (optional)

### Cloud CLIs (optional — individual checkboxes)
- [ ] AWS CLI
- [ ] Google Cloud CLI
- [ ] Azure CLI

### Local Database Servers (Full Stack / Web / AI profiles)
- [ ] **PostgreSQL** — standard relational DB. Installed as Windows service or Docker container (user choice).
- [ ] **Redis** — in-memory store. Essential for queuing, caching, session management.
- [ ] **MongoDB** (optional) — document store for flexible schema work.
- [ ] DBeaver already included in Layer 7 — connects to all of the above.

### Networking Utilities
- [ ] `ngrok` — expose localhost (webhook dev, demos)
- [ ] `mkcert` — local HTTPS certificates (eliminates constant headache)
- [ ] **Tailscale** — zero-config mesh VPN. Assigns a stable `100.x.x.x` address that follows you across networks. Essential for accessing a dev machine remotely, across hotspots, or from the road. Install in Layer 2 because it's infrastructure, not productivity.

---

## Layer 7: Productivity & Utilities

> **Note:** Obsidian, OBS, ShareX, Discord, HWiNFO64, and PowerToys have moved to the **Extras** section — they're genuinely useful but personal preference, not dev stack. Layer 7 now covers tools with clear dev workflow purpose.

### File & Text
- [ ] Notepad++ (emergency plain text, no dependencies)
- [ ] Everything (instant system-wide file search — life changing)
- [ ] WizTree (disk usage visualizer)
- [ ] **DevToys** — Swiss-army dev toolkit. JSON formatter, base64 encoder/decoder, hash generator, regex tester, diff viewer, UUID generator. Portable, fast, no bloat.
- [ ] **WinMerge** — visual file/folder diff and merge tool. Complements git-delta for non-terminal diff work.

### Network & API
- [ ] Bruno — open source Postman alternative (collections as plain files in repo)
- [ ] Wireshark (optional — Custom mode)
- [ ] nmap (optional — Custom mode)

### Database
- [ ] DBeaver — universal DB GUI (PostgreSQL, MySQL, SQLite, Redis, MongoDB, everything)
- [ ] SQLite Browser (lightweight, portable)

### Security
- [ ] KeePassXC — local password manager
- [ ] GPG4Win
- [ ] **sops** — secret file encryption (optional / Advanced Custom mode only)
- [ ] **age** — simple, modern encryption tool. Pairs with sops for `.env` file encryption in repos. (Advanced Custom mode only)

### System Monitoring & Diagnostics
- [ ] **Sysinternals Suite** — the definitive Windows power-user diagnostic toolkit (Process Explorer, Process Monitor, Autoruns, TCPView, etc.)
- [ ] Process Hacker / System Informer (better Task Manager)
- [ ] CrystalDiskInfo (drive health)
- [ ] CPU-Z
- [ ] GPU-Z

### Git GUI (Visual operations)
- [ ] Fork (free, fast, excellent branch visualization)
- [ ] GitKraken (optional — paid, more features)

---

## Layer 8: Configuration & State

**This layer is what separates AM-DevKit from everything else.**

### Outputs Generated After Install

| File | Purpose |
|---|---|
| `devkit-manifest.json` | Full record: every tool installed, version, timestamp, decisions made |
| `restore-devkit.ps1` | Run on a new machine to reproduce environment exactly |
| `dotfiles/` folder | `.gitconfig`, `.bashrc`, VS Code `settings.json`, PowerShell profile |
| `post-install-report.html` | Human-readable summary. **Path Auditor results appear first** — red banner if conflicts exist, green if clean. Followed by: what installed, what was skipped, what needs manual attention |
| `system-profile.json` | Hardware snapshot taken at install time |
| `powertoys-settings.json` | PowerToys config export — restores FancyZones layouts, PowerToys Run settings, key remaps |

### Post-Install Launchpad

**The last section of the HTML report.** Addresses the "okay now what?" gap — the user has a fully configured machine and no immediate direction.

Profile-aware: the launchpad shows actions relevant to what was actually installed.

```
🚀 You're set up. Here's where to start:

  [Run your first local AI model]   → Opens terminal: ollama run llama3
  [Open Web UI]                     → Opens http://localhost:3000 in browser
  [Start a new Python project]      → Opens VS Code with uv venv instructions
  [Test your GPU setup]             → Runs torch CUDA verification script
  [Open VS Code]                    → Launches with your seeded config
```

Rules for launchpad entries:
- **One click = one concrete outcome.** Not a link to docs. Not "learn more." An action.
- Only show entries for tools that were actually installed — no phantom options.
- GPU verification entry only appears if NVIDIA path was taken in Layer 5. Output is human-readable, not raw Python:
  - `✅ Your GPU is ready for AI workloads` (CUDA available)
  - `⚠️ CUDA not detected — running on CPU only` (CPU fallback path)
- Ordered by most likely first action for the selected profiles.

### Key Dotfile Configurations Seeded

`.gitconfig` additions:
```ini
[core]
    pager = delta          # git-delta as default diff pager

[interactive]
    diffFilter = delta --color-only

[delta]
    navigate = true
    light = false
    side-by-side = true
```

`.bashrc` / PowerShell profile aliases:
```bash
alias ls='eza --icons --group-directories-first'
alias ll='eza -la --icons --group-directories-first'
alias cat='bat'
alias find='fd'
alias grep='rg'
alias top='btop'
```

### Obsidian Vault Template (Seeded on Install)

```
/AM-DevKit-Vault/
  ├── 00 - Inbox/
  ├── 01 - Projects/
  ├── 02 - Learning/
  ├── 03 - Code Snippets/
  ├── 04 - Daily Notes/
  ├── 05 - Reference/
  ├── 06 - Archive/
  └── README.md
```

Vault is created at `~/Documents/AM-DevKit-Vault/` by default. Location configurable in `am-devkit.toml`.

### Path Auditor

Runs automatically at the end of every install. **Path Auditor output is the first section of the HTML report, above everything else.** If there are conflicts, the user sees them before they see anything else.

**Checks:**
- Lists every entry in `PATH` by precedence order
- Flags duplicate binaries (e.g. two `python.exe` entries) and shows *which one wins* and why
- Detects shim conflicts — where pyenv/Scoop is supposed to intercept but a system entry is ahead of it (e.g. old Python rotting in `AppData\Local` sitting above Scoop in PATH)
- Writes a `path-fingerprint.json` at install time so future runs can diff and detect drift from other installers

**Report presentation:**
- ✅ No conflicts — green banner, collapsed by default, full PATH list available on expand
- ⚠️ Conflicts found — **red banner at the top of the report, expanded and impossible to miss.** Each conflict shows: what the conflict is, which entry wins, what the fix is, and the exact command to resolve it if manual action is needed.

---

## Layer 8.5: Disposable Workspace *(opt-in)*

**Presented as an optional post-install step. Not part of any profile. Available to everyone.**

Gives you an isolated, throwaway environment for experimenting with unfamiliar tools, running code you don't fully trust, or testing things without touching your host OS.

### Option A — Windows Sandbox
- Lightweight, built into Windows 10/11 Pro
- Completely stateless — resets on close, no traces left
- Best for: testing tool behavior, running sketchy installers to inspect them, quick isolation
- AM-DevKit configures a `.wsb` sandbox config file with sensible defaults (networking enabled, clipboard sharing optional)

### Option B — Dev Container (Docker)
- Stateful — your work persists in a volume
- VS Code Dev Containers extension hooks in natively
- Best for: iterating on experimental code in isolation, testing reproducible environments
- AM-DevKit seeds a base `devcontainer.json` you can customize per-project

```
Layer 8.5 outputs:
  ├── sandbox-config.wsb          ← Windows Sandbox ready-to-launch config
  └── .devcontainer/
      └── devcontainer.json       ← Base Dev Container config
```

---

## Profile System

### How It Works

- **Select one or more profiles.** They're additive — each one layers on top of Core.
- **Each profile has an info button (ℹ️)** that shows the full tool list before you commit. No surprises, no walls of text in the UI.
- **Absentmind Mode** selects all profiles automatically. One button, full stack, no prompts.
- **Custom Mode** opens a granular per-tool checkbox list for surgical control.

---

### Core (Always Installs — No Selection Required)

> See the **Core** section above for the full list. Installs regardless of profile selection.

---

### Profile: AI / ML Developer

> *ℹ️ PyTorch (GPU-matched automatically), numpy, pandas, scikit-learn, Jupyter, HuggingFace stack (transformers, diffusers, accelerate, datasets, peft), Ollama, llama-cpp-python, Open WebUI, LangChain, LiteLLM, Gradio, Streamlit, FastAPI, Continue.dev, DBeaver, Docker + GPU passthrough*

GPU detection logic runs automatically. Installs the correct PyTorch wheel for your hardware. No manual `--index-url` hunting.

---

### Profile: Web / Full-Stack Developer

> *ℹ️ Node.js via nvm-windows, npm/pnpm/yarn, React tooling, Bruno (API client), mkcert (local HTTPS), Docker, PostgreSQL, Redis, MongoDB (optional), DBeaver, Playwright (E2E testing), ngrok, kubectl, helm, k9s, cloud CLIs (AWS/GCP/Azure — individual checkboxes)*

---

### Profile: Game Developer

> *ℹ️ Unity Hub, Godot, Visual Studio Community, CMake, Ninja, vcpkg, DirectX SDK, OBS Studio (capture/streaming), ShareX*

---

### Profile: Systems / Low-Level

> *ℹ️ Rust (rustup), C/C++ (MSVC Build Tools), Visual Studio Community, CMake, Ninja, vcpkg, MinGW/GCC (optional), Wireshark, nmap, .NET SDK (optional), Go (optional)*

---

### Profile: Hardware / Embedded / Robotics

> *ℹ️ Arduino IDE + Arduino CLI, PlatformIO (VS Code extension + CLI), pyserial, python-can, hidapi, Zadig (WinUSB driver tool), PuTTY (serial terminal), TeraTerm (serial logging/capture), Sigrok + PulseView (open source logic analyzer)*

For developers working with microcontrollers, sensors, serial protocols, and physical hardware. Pairs naturally with the AI/ML profile for bridging embedded work with Python inference.

Arduino CLI is included alongside the IDE for scripted/CI builds. Zadig is quietly essential — without it, half of USB device flashing workflows break silently on Windows.

---

### ⚡ Absentmind Mode

**All profiles. No questions asked.**

Equivalent to checking every profile box simultaneously. Installs the complete curated stack across all categories. For the person whose answer to "which profile?" is genuinely "yes."

Extras are still presented as a separate opt-in after install — they're personal preference, not dev stack.

---

### ⚙️ Custom Mode

Opens a full checkbox interface organized by layer. Every individual tool is selectable or deselectable. Users can:

- Select/deselect individual tools within any profile
- Mix tools from multiple profiles without taking entire stacks
- Save their selection as a named profile (e.g. `my-stack.toml`)
- Load saved profiles on future installs

**Checkbox categories:**
- [ ] Windows Sanitation (sub-checkboxes per tweak category)
- [ ] Core Infrastructure (Git, SSH, Terminal — mostly locked, extras optional)
- [ ] Editors (VS Code, Cursor, extension packs)
- [ ] Python ecosystem (pyenv-win, uv, pipx, virtualenv)
- [ ] Node/JS stack
- [ ] Rust
- [ ] Other languages (Go, Java, .NET)
- [ ] AI/ML stack (GPU detection still runs if anything ML is selected)
- [ ] Local LLM tools
- [ ] DevOps / Containers
- [ ] Cloud CLIs (AWS, GCP, Azure — individual)
- [ ] Hardware / Embedded tools (individual)
- [ ] Utilities (each tool individually)
- [ ] Security tools

---

## Extras *(Optional — Personal Preference, Not Dev Stack)*

Presented after profile selection, always. The test: *useful to a human, not specific to a developer workflow.*

| Tool | Category | Notes |
|---|---|---|
| **Microsoft PowerToys** | Windows Power User | FancyZones, PowerToys Run (`Alt+Space`), PowerRename, Keyboard Manager, Peek. Settings JSON exported for restore. |
| **Obsidian** | Notes / PKM | Local-first markdown knowledge base. AM-DevKit Vault template seeded if selected. |
| **OBS Studio** | Recording / Streaming | Full featured, industry standard |
| **ShareX** | Screenshots | What devs actually use for screenshots and screen recording |
| **HWiNFO64** | Hardware Monitoring | Sensors, thermals, detailed hardware readout |
| **Everything** | File Search | Instant system-wide file search. Life-changing on large drives. |
| **WizTree** | Disk Usage | Visual disk space analyzer |
| **VLC** | Media | Everyone needs it eventually |
| **Bitwarden** | Password Manager | Cloud-based. KeePassXC (local) is in Layer 7 Security. |
| **AutoHotkey** | Automation | Scripted keyboard/mouse automation for power users |
| **Discord** | Communication | Where every dev community lives |
| **ffmpeg** | Media CLI | Quietly essential. Powers half of media tooling. |

---

## Repository Structure (Proposed)

```
absentmind-devkit/
├── README.md
├── CHANGELOG.md
├── LICENSE
├── am-devkit.toml              ← User-facing config file
│
├── bootstrap/
│   └── install.ps1             ← Entry point — PowerShell bootstrap
│
├── core/
│   ├── preflight.py            ← Pre-flight: restore point + Absentmind Mode toggle
│   ├── system_scan.py          ← Layer 0: hardware detection
│   ├── sanitize.py             ← Layer 1: calls CTT WinUtil
│   ├── infrastructure.py       ← Layer 2: git, terminal, ssh, tailscale
│   ├── editors.py              ← Layer 3: VS Code, Cursor, extensions
│   ├── languages.py            ← Layer 4: Python ecosystem, Node, Rust
│   ├── ml_stack.py             ← Layer 5: GPU logic + PyTorch
│   ├── devops.py               ← Layer 6: Docker, WSL2, WSL seeding, CLIs
│   ├── utilities.py            ← Layer 7: dev tools, security, monitoring
│   ├── finalize.py             ← Layer 8: manifest, path auditor, report, dotfiles
│   └── sandbox.py              ← Layer 8.5: Disposable Workspace config
│
├── config/
│   ├── am-devkit-winutil.json  ← Our CTT WinUtil opinionated config
│   ├── profiles/
│   │   ├── ai-ml.toml
│   │   ├── web-fullstack.toml
│   │   ├── systems.toml
│   │   ├── game-dev.toml
│   │   ├── hardware-robotics.toml
│   │   ├── absentmind-mode.toml
│   │   └── extras.toml
│   └── vscode/
│       ├── settings.json       ← Seeded VS Code settings
│       └── extensions.json     ← Extension ID list
│
├── templates/
│   ├── dotfiles/
│   │   ├── .gitconfig
│   │   ├── .bashrc
│   │   └── powershell-profile.ps1
│   ├── obsidian-vault/         ← Starter vault template (seeded if Obsidian selected in Extras)
│   └── sandbox/
│       ├── sandbox-config.wsb  ← Windows Sandbox config
│       └── devcontainer.json   ← Base Dev Container config
│
├── scripts/
│   ├── gpu_detect.py           ← Standalone GPU + PyTorch logic
│   ├── path_auditor.py         ← PATH conflict detection + fingerprinting
│   └── restore-devkit.ps1      ← Restore point template
│
└── docs/
    ├── PROJECT.md              ← This document
    ├── ARCHITECTURE.md
    └── CONTRIBUTING.md
```

---

## Development Roadmap

### Phase 0 — Foundation
- [x] Vision and scope defined
- [x] Layer architecture mapped
- [x] Profile system designed
- [x] Finalize component list (frontier LLM input) ✅
- [x] Core/Profile/Extras architecture decided ✅
- [x] Hardware/Robotics profile scoped ✅
- [x] Absentmind Mode definition locked ✅
- [x] Name locked: **Absentmind's DevKit**
- [x] Create GitHub repo — [Absentmind86/Absentminds-DevKit-Windows](https://github.com/Absentmind86/Absentminds-DevKit-Windows)

### Phase 1 — Proof of Concept ✅
- [x] Layer 0: System scan script (Python + WMI)
- [x] Layer 5: GPU detection + correct PyTorch install (the core differentiator)
- [x] Bootstrap PowerShell → Python handoff
- [x] Basic profile selection (CLI, no GUI yet)

### Phase 2 — Core Installer ✅
- [x] All layers functional (CLI mode)
- [x] CTT WinUtil integration with AM config
- [x] Manifest generation
- [x] Post-install report (HTML)

### Phase 3 — Polish
- [x] GUI profile selector (Flet — Python/Flutter based)
- [x] Custom Mode with catalog exclusion checkboxes (`core/gui.py`)
- [x] Extras selector post-profile (CLI `--profile extras` + GUI checkbox)
- [x] Restore script generation (`scripts/restore-winget-from-manifest.ps1` + manifest replay)
- [x] Dotfile seeding (`core/finalize.py`)
- [x] Obsidian vault template seeding (Extras + finalize when Obsidian not excluded)
- [x] Layer 8.5 Disposable Workspace config generation (`core/sandbox.py`)

### Phase 4 — Release (current)
- [x] Unit test suite (90 tests, 0 failures):
      `tests/test_gpu_detect.py` (36), `test_path_auditor.py` (12),
      `test_install_catalog.py` (20), `test_winutil_presets.py` (22)
- [x] GitHub Actions CI (`.github/workflows/ci.yml`):
      windows-latest, Python 3.11 / 3.12 / 3.13 — py_compile + ruff + pytest
- [x] `pyproject.toml` — pytest + ruff lint config
- [ ] Testing on clean Windows installs — see `docs/RELEASE_TESTING.md`
- [x] README install / clone URLs — [Absentmind86/Absentminds-DevKit-Windows](https://github.com/Absentmind86/Absentminds-DevKit-Windows)
- [ ] Documentation polish (ongoing)
- [ ] GitHub release with signed `.exe` or `.ps1`

---

## Open Questions / Decisions Pending

| Question | Options | Status |
|---|---|---|
| GUI framework for profile selector | Tauri, PowerShell dialog, Python rich TUI, Flet | **Leaning Flet** — async-native, Python codebase stays unified, modern Flutter-based look without JS/CSS. Rich TUI for during-install output, Flet for the profile selector UI. |
| ROCm Windows — include or just warn? | **Resolved: DirectML** (`torch-directml`) — stable Windows AMD path, no ROCm | Closed |
| Signed executable? | Yes (code signing cert) / Trust-on-first-run PS1 | Open |
| Dotfile storage | Local only / Optional GitHub Gist sync | Open |
| Winget vs Chocolatey fallback strategy | Winget primary, Choco for gaps | Tentative |
| macOS/Linux support? | Windows only v1, cross-platform v2 | Tentative |

---

## Notes / Scratchpad

- Run full component list past other frontier LLMs ✅ — integrated in v0.2
- Architecture overhaul (Core/Profile/Extras split) ✅ — integrated in v0.3
- PowerToys is genuinely table-stakes for power users but not universal enough for Core — moved to Extras ✅
- Obsidian moved to Extras — personal preference, not dev stack ✅
- Python moved to Core — nearly every profile touched it anyway, makes no sense as profile-only ✅
- Investigate whether CTT WinUtil has a stable unattended API or if we need to pin a specific release
- `uv` is moving fast — may partially replace `pyenv-win` + `pipx` + `pip` by release time. Monitor
- Consider a `--dry-run` flag that shows what would be installed without doing it (great for demos)
- The post-install HTML report could be genuinely shareable / impressive. Make it look good.
- Absentmind Mode name is locked. ✅ It's character, not a feature.
- Docker GPU passthrough is easy to miss and breaks ML workflows silently — good catch
- sops + age flagged as Advanced Custom only — don't scare normal users ✅
- git-delta dotfile seeding documented in Layer 8 — small thing that makes a big impression
- Local DB servers (Postgres, Redis) — Docker fallback is fine but native Windows service option is cleaner for most web devs
- Flet chosen as GUI direction — async-native, Python codebase stays unified ✅
- Hardware/Robotics profile added — Zadig is the non-obvious essential here, don't drop it ✅
- Tailscale placed in Layer 2 (infrastructure), not Layer 7 (productivity) — correct framing ✅
- Layer 8.5 Disposable Workspace is opt-in, quiet, available to everyone regardless of profile ✅
- Path Auditor writes a fingerprint JSON — diff on future runs to catch installer drift ✅
- WSL Seeding toggle: SSH keys symlinked (shared), not duplicated — document this clearly for users
- Content Creator profile dissolved — OBS/ShareX/Discord live in Extras where they belong ✅
- Web Dev and Full-Stack profiles are similar — worth reviewing for possible merge in v0.4
- The "if you'd have to explain what it is, it's not Core" rule should be documented in CONTRIBUTING.md for future contributors
- Sanitation toggle is preset-level (Minimal / Standard radio), not all-or-nothing ✅
- Pre-Install Summary time/disk estimates depend on Layer 0 connection speed detection being accurate — test this early in Phase 1
- Post-Install Launchpad: "one click = one concrete outcome" is the rule. Do not let this become a links page.
- GPU verification script for Launchpad: raw `torch.cuda.is_available()` returning True/False is not user-friendly — wrap it in a readable output ("✅ CUDA available — your GPU is ready for AI workloads")
- **Donations:** Add Ko-fi or GitHub Sponsors link to README footer, post-install HTML report footer, and Launchpad. Framing: "AM-DevKit is free. If it saved you an afternoon, you know where to find me." No guilt, no begging. Add after repo goes live.

---

*Document maintained by Kyle / Absentmind Studio*
