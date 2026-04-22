#Requires -Version 5.1
<#
.SYNOPSIS
  AM-DevKit fresh-machine bootstrap — designed to be run via `irm | iex` on a blank Windows install.

.DESCRIPTION
  Ensures git is available (installs via winget if missing), clones the AM-DevKit repository
  to a local path, then hands off to bootstrap/install.ps1 inside the clone.

  Intended use:
    irm https://raw.githubusercontent.com/Absentmind86/Absentminds-DevKit-Windows/main/bootstrap/fresh.ps1 | iex

  After running, you will have the repo cloned at $InstallPath and the Phase 3 GUI open.

.PARAMETER InstallPath
  Where to clone the repo. Defaults to "$env:USERPROFILE\Absentminds-DevKit-Windows".

.PARAMETER Branch
  Git branch to clone. Defaults to 'main'.

.PARAMETER Mode
  'Gui' (default) opens the Flet launcher. 'Scan' runs only the Layer 0 system scan.
  'Cli' runs the full installer non-interactively (pass extra args after a `--` separator).

.NOTES
  Requires Windows 10 build 1809+ or Windows 11 (for winget availability).
  Administrator is recommended but not strictly required for the clone step.
#>

[CmdletBinding()]
param(
    [string] $InstallPath = (Join-Path $env:USERPROFILE 'Absentminds-DevKit-Windows'),
    [string] $Branch = 'main',
    [ValidateSet('Gui', 'Scan', 'Cli')]
    [string] $Mode = 'Gui'
)

$ErrorActionPreference = 'Stop'
$RepoUrl = 'https://github.com/Absentmind86/Absentminds-DevKit-Windows.git'

function Write-Step {
    param([string] $Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-OK {
    param([string] $Message)
    Write-Host "    $Message" -ForegroundColor Green
}

function Update-ProcessPathFromMachine {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($machine -and $user) {
        $env:Path = "$machine;$user"
    } elseif ($machine) {
        $env:Path = $machine
    } elseif ($user) {
        $env:Path = $user
    }
}

Write-Host ''
Write-Host "Absentmind's DevKit — fresh machine bootstrap" -ForegroundColor Magenta
Write-Host "Target: $InstallPath (branch: $Branch, mode: $Mode)" -ForegroundColor DarkGray
Write-Host ''

# --- Step 1: ensure git is available ---------------------------------------
Write-Step 'Checking for git'
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'Neither git nor winget is available. Install App Installer from the Microsoft Store (provides winget), or install git manually from https://git-scm.com/download/win, then re-run this script.'
    }
    Write-Host '    git not found; installing Git.Git via winget...' -ForegroundColor Yellow
    winget install --id Git.Git -e --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        throw "winget failed to install git (exit $LASTEXITCODE). Install manually from https://git-scm.com/download/win and re-run."
    }
    Update-ProcessPathFromMachine
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        throw 'git was installed but is not on PATH in this session. Open a new PowerShell window and re-run this script.'
    }
    Write-OK 'git installed'
} else {
    Write-OK "git found: $((git --version) 2>&1)"
}

# --- Step 2: clone or update the repo --------------------------------------
$parent = Split-Path -Parent $InstallPath
if (-not (Test-Path -LiteralPath $parent)) {
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
}

if (Test-Path -LiteralPath (Join-Path $InstallPath '.git')) {
    Write-Step "Repository already present at $InstallPath — pulling latest"
    Push-Location $InstallPath
    try {
        git fetch origin $Branch
        if ($LASTEXITCODE -ne 0) { throw "git fetch failed (exit $LASTEXITCODE)" }
        git checkout $Branch
        if ($LASTEXITCODE -ne 0) { throw "git checkout failed (exit $LASTEXITCODE)" }
        git pull --ff-only origin $Branch
        if ($LASTEXITCODE -ne 0) {
            Write-Host '    git pull --ff-only failed (local diverges from remote). Leaving repo as-is.' -ForegroundColor Yellow
        } else {
            Write-OK 'repo updated'
        }
    } finally {
        Pop-Location
    }
} elseif (Test-Path -LiteralPath $InstallPath) {
    throw "$InstallPath exists but is not a git repository. Move or delete it, or pass a different -InstallPath."
} else {
    Write-Step "Cloning $RepoUrl into $InstallPath"
    git clone --branch $Branch --single-branch $RepoUrl $InstallPath
    if ($LASTEXITCODE -ne 0) {
        throw "git clone failed (exit $LASTEXITCODE)"
    }
    Write-OK 'clone complete'
}

# --- Step 3: hand off to install.ps1 ---------------------------------------
$InstallScript = Join-Path $InstallPath 'bootstrap\install.ps1'
if (-not (Test-Path -LiteralPath $InstallScript)) {
    throw "Missing $InstallScript — clone may be incomplete."
}

Write-Host ''
Write-Step "Launching bootstrap\install.ps1 (mode: $Mode)"
Write-Host ''

switch ($Mode) {
    'Gui'  { & $InstallScript -Gui }
    'Scan' { & $InstallScript }
    'Cli'  { & $InstallScript -FullInstall }
}

if ($LASTEXITCODE -ne 0) {
    throw "install.ps1 exited with code $LASTEXITCODE"
}

Write-Host ''
Write-Host "Repository is at: $InstallPath" -ForegroundColor DarkGray
Write-Host 'You can re-run from there with: .\bootstrap\install.ps1 -Gui' -ForegroundColor DarkGray
