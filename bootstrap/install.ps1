#Requires -Version 5.1
<#
.SYNOPSIS
  AM-DevKit bootstrap - ensures Python 3.11+ and runs Layer 0 scan, Phase 3 GUI, or full installer.

.DESCRIPTION
  Resolves the repository root from this script location, finds or installs Python,
  then either runs core/system_scan.py (default), core.gui when -Gui is specified,
  or core.installer when -FullInstall is specified.

.PARAMETER FullInstall
  Run python -m core.installer from the repo root. Combine with -DryRun, -Profile, etc.,
  or pass extra Python flags via remaining arguments (quoted), e.g. '-FullInstall' '--install-ml-wheels'.

.PARAMETER Gui
  Open the Phase 3 Flet launcher (python -m core.gui) instead of Layer 0 or the CLI installer.

.PARAMETER SanitationPreset
  With -FullInstall and -RunSanitation: WinUtil JSON preset — 'minimal' (default) or 'standard'.

.NOTES
  Single-file bootstrap per AGENTS.md (no dot-sourcing of other modules).
#>

[CmdletBinding()]
param(
    [switch] $FullInstall,
    [switch] $Gui,
    [switch] $DryRun,
    [switch] $Absentmind,
    [switch] $RunSanitation,
    [switch] $SkipRestorePoint,
    [switch] $InstallMlWheels,
    [switch] $InstallMlBase,
    [switch] $EnableWsl,
    [string] $WslDistro = '',
    [switch] $WslSkipDefaultDistro,
    [switch] $SkipDotfiles,
    [switch] $Yes,
    [switch] $SkipSummary,
    [ValidateSet('minimal', 'standard')]
    [string] $SanitationPreset = 'minimal',
    [string[]] $Profile,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]] $InstallerArgs
)

$ErrorActionPreference = 'Stop'

function Get-RepoRoot {
    return (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
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

function Test-PythonVersion {
    param(
        [Parameter(Mandatory = $true)][string] $Exe,
        [AllowEmptyCollection()]
        [string[]] $PrefixArgs = @()
    )
    try {
        $allArgs = @()
        if ($PrefixArgs.Count -gt 0) { $allArgs += $PrefixArgs }
        $allArgs += '-c'
        $allArgs += 'import sys; sys.exit(0 if sys.version_info[:2] >= (3, 11) else 1)'
        & $Exe @allArgs 1>$null 2>$null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

function Get-PythonLauncher {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        if (Test-PythonVersion -Exe 'py' -PrefixArgs @('-3')) {
            return @{ Exe = 'py'; Args = @('-3') }
        }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        if (Test-PythonVersion -Exe 'python' -PrefixArgs @()) {
            return @{ Exe = 'python'; Args = @() }
        }
    }
    return $null
}

function Install-PythonWithWinget {
    Write-Host 'Python 3.11+ not found. Installing Python 3.12 via winget...' -ForegroundColor Yellow
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw 'winget is not available. Install Python 3.11+ manually from https://www.python.org/downloads/windows/ then re-run bootstrap/install.ps1'
    }
    winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements
    if ($LASTEXITCODE -ne 0) {
        throw "winget install failed (exit $LASTEXITCODE). Install Python 3.11+ manually, then re-run."
    }
    Update-ProcessPathFromMachine
}

$RepoRoot = Get-RepoRoot
$launcher = Get-PythonLauncher
if (-not $launcher) {
    Install-PythonWithWinget
    $launcher = Get-PythonLauncher
}
if (-not $launcher) {
    throw 'Could not locate Python 3.11+ after winget install. Open a new terminal (refreshed PATH) and run bootstrap/install.ps1 again.'
}

function Install-PythonRequirements {
    param(
        [Parameter(Mandatory = $true)] $Launcher,
        [Parameter(Mandatory = $true)][string] $RepoRoot
    )
    $req = Join-Path $RepoRoot 'requirements.txt'
    if (-not (Test-Path -LiteralPath $req)) {
        Write-Host "AM-DevKit: no requirements.txt found at $req (skipping pip install)." -ForegroundColor Yellow
        return
    }
    Write-Host 'AM-DevKit: ensuring Python dependencies (rich, flet) ...' -ForegroundColor Cyan
    $pipArgs = @()
    if ($Launcher.Args.Count -gt 0) { $pipArgs += $Launcher.Args }
    $pipArgs += @('-m', 'pip', 'install', '--upgrade', 'pip')
    & $Launcher.Exe @pipArgs 1>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "    pip self-upgrade exited $LASTEXITCODE (continuing)." -ForegroundColor Yellow
    }

    # Detect any pre-existing flet-family packages via a single `pip list`.
    # We pin to flet 0.25.2 (see requirements.txt for rationale); any other
    # version must be removed first, and we ask the user before downgrading.
    # Using `pip list --format=json` avoids the per-package "not found"
    # warnings that `pip show` emits to stderr (which PowerShell 5.1 turns
    # into NativeCommandError records under ErrorActionPreference=Stop).
    $fletPackages = @('flet', 'flet-core', 'flet-desktop', 'flet-web', 'flet-runtime')
    $installed = @{}
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $listArgs = @()
        if ($Launcher.Args.Count -gt 0) { $listArgs += $Launcher.Args }
        $listArgs += @('-m', 'pip', 'list', '--format=json', '--disable-pip-version-check')
        $listJson = (& $Launcher.Exe @listArgs 2>$null) -join "`n"
        if ($listJson) {
            $pkgs = $listJson | ConvertFrom-Json
            foreach ($p in $pkgs) {
                $installed[$p.name.ToLower()] = $p.version
            }
        }
    } catch {
        Write-Host "    Could not enumerate pip packages: $_" -ForegroundColor Yellow
    } finally {
        $ErrorActionPreference = $prevEAP
    }

    $detected = @()
    foreach ($pkg in $fletPackages) {
        if ($installed.ContainsKey($pkg.ToLower())) {
            $detected += [pscustomobject]@{ Name = $pkg; Version = $installed[$pkg.ToLower()] }
        }
    }

    $needsDowngrade = $false
    foreach ($d in $detected) {
        if ($d.Version -ne '0.25.2') {
            $needsDowngrade = $true
            break
        }
    }

    if ($needsDowngrade) {
        Write-Host ''
        Write-Host 'Heads up: incompatible Flet packages are already installed on this Python:' -ForegroundColor Yellow
        foreach ($d in $detected) {
            Write-Host ("    {0} {1}" -f $d.Name, $d.Version) -ForegroundColor DarkGray
        }
        Write-Host ''
        Write-Host 'AM-DevKit pins flet to 0.25.2 (a stable version with a known-good GUI API).' -ForegroundColor White
        Write-Host 'To proceed, the installer will uninstall the above and install flet 0.25.2.' -ForegroundColor White
        Write-Host 'If you use flet for other projects, you may need to reinstall your preferred' -ForegroundColor White
        Write-Host 'version afterward (e.g., pip install flet==0.84.0).' -ForegroundColor White
        Write-Host ''

        if (-not $Yes) {
            $confirm = Read-Host 'Downgrade flet and continue? [Y/N]'
            if ($confirm -notmatch '^[Yy]') {
                throw 'Aborted by user. No Python packages were changed.'
            }
        } else {
            Write-Host '(-Yes passed — downgrading without prompt.)' -ForegroundColor DarkGray
        }

        $uninstallArgs = @()
        if ($Launcher.Args.Count -gt 0) { $uninstallArgs += $Launcher.Args }
        $uninstallArgs += @('-m', 'pip', 'uninstall', '-y') + $fletPackages
        $prevEAP2 = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            & $Launcher.Exe @uninstallArgs 1>$null 2>$null
            # Ignore exit code — some packages may not be installed, which is fine.
        } finally {
            $ErrorActionPreference = $prevEAP2
        }
    }

    $pipArgs = @()
    if ($Launcher.Args.Count -gt 0) { $pipArgs += $Launcher.Args }
    $pipArgs += @('-m', 'pip', 'install', '--upgrade', '--upgrade-strategy', 'eager', '-r', $req)
    & $Launcher.Exe @pipArgs
    if ($LASTEXITCODE -ne 0) {
        throw "pip install -r requirements.txt failed (exit $LASTEXITCODE). Fix networking/pip and re-run bootstrap/install.ps1."
    }
}

if ($Gui -or $FullInstall) {
    Install-PythonRequirements -Launcher $launcher -RepoRoot $RepoRoot
}

if ($Gui) {
    $GuiModule = Join-Path $RepoRoot 'core\gui.py'
    if (-not (Test-Path -LiteralPath $GuiModule)) {
        throw "Missing $GuiModule - repository layout may be incomplete."
    }
    Write-Host 'AM-DevKit: opening Phase 3 GUI (python -m core.gui) ...' -ForegroundColor Cyan
    $runArgs = [System.Collections.Generic.List[string]]::new()
    if ($launcher.Args.Count -gt 0) { foreach ($a in $launcher.Args) { $runArgs.Add($a) } }
    $runArgs.Add('-m')
    $runArgs.Add('core.gui')
    Push-Location $RepoRoot
    try {
        & $launcher.Exe @($runArgs.ToArray())
        if ($LASTEXITCODE -ne 0) {
            throw "core.gui exited with code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
    exit 0
}

if ($FullInstall) {
    $InstallerModule = Join-Path $RepoRoot 'core\installer.py'
    if (-not (Test-Path -LiteralPath $InstallerModule)) {
        throw "Missing $InstallerModule - repository layout may be incomplete."
    }
    Write-Host 'AM-DevKit: running Phase 2 installer (python -m core.installer) ...' -ForegroundColor Cyan
    $runArgs = [System.Collections.Generic.List[string]]::new()
    if ($launcher.Args.Count -gt 0) { foreach ($a in $launcher.Args) { $runArgs.Add($a) } }
    $runArgs.Add('-m')
    $runArgs.Add('core.installer')
    if ($DryRun) { $runArgs.Add('--dry-run') }
    if ($Absentmind) { $runArgs.Add('--absentmind') }
    if ($RunSanitation) {
        $runArgs.Add('--run-sanitation')
        $runArgs.Add('--sanitation-preset')
        $runArgs.Add($SanitationPreset)
    }
    if ($SkipRestorePoint) { $runArgs.Add('--skip-restore-point') }
    if ($InstallMlWheels) { $runArgs.Add('--install-ml-wheels') }
    if ($InstallMlBase) { $runArgs.Add('--install-ml-base') }
    if ($Yes) { $runArgs.Add('--yes') }
    if ($SkipSummary) { $runArgs.Add('--skip-summary') }
    if ($EnableWsl) {
        $runArgs.Add('--enable-wsl')
        if ($WslSkipDefaultDistro) { $runArgs.Add('--wsl-skip-default-distro') }
        elseif ($WslDistro) {
            $runArgs.Add('--wsl-distro')
            $runArgs.Add($WslDistro)
        }
    }
    if ($SkipDotfiles) { $runArgs.Add('--skip-dotfiles') }
    if ($Profile) {
        foreach ($p in $Profile) {
            $runArgs.Add('--profile')
            $runArgs.Add($p)
        }
    }
    if ($InstallerArgs -and $InstallerArgs.Count -gt 0) {
        foreach ($x in $InstallerArgs) { $runArgs.Add($x) }
    }
    Push-Location $RepoRoot
    try {
        & $launcher.Exe @($runArgs.ToArray())
        if ($LASTEXITCODE -ne 0) {
            throw "core.installer exited with code $LASTEXITCODE"
        }
    } finally {
        Pop-Location
    }
    Write-Host 'AM-DevKit: Phase 2 installer finished.' -ForegroundColor Green
    exit 0
}

$ScanScript = Join-Path $RepoRoot 'core\system_scan.py'
if (-not (Test-Path -LiteralPath $ScanScript)) {
    throw "Missing $ScanScript - repository layout may be incomplete."
}

$OutFile = Join-Path $RepoRoot 'system-profile.json'
Write-Host "AM-DevKit: running Layer 0 scan with $($launcher.Exe) ..." -ForegroundColor Cyan

$runArgs = @()
if ($launcher.Args.Count -gt 0) { $runArgs += $launcher.Args }
$runArgs += $ScanScript
$runArgs += @('--output', $OutFile)

& $launcher.Exe @runArgs
if ($LASTEXITCODE -ne 0) {
    throw "system_scan.py exited with code $LASTEXITCODE"
}

Write-Host "AM-DevKit: wrote $OutFile" -ForegroundColor Green
exit 0
