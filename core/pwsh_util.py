"""PowerShell-driven setup steps (Scoop, optional Windows features, rustup)."""

from __future__ import annotations

import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from rich.console import Console

    from core.install_context import InstallContext
    from core.manifest import Manifest


def run_powershell(
    script: str,
    *,
    timeout_s: float,
    stream: bool = False,
) -> tuple[int, str, str]:
    """Run a PowerShell script string; return ``(code, stdout, stderr)``.

    When *stream* is True output is printed live to the terminal and the
    returned stdout/stderr strings will be empty.
    """
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                script,
            ],
            capture_output=not stream,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", f"{type(exc).__name__}: {exc}"
    if stream:
        return proc.returncode, "", ""
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def ensure_openssh_client(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
) -> None:
    """Enable OpenSSH Client optional Windows capability when absent."""
    tool = "openssh-client"
    ps = r"""
$ErrorActionPreference = 'Stop'
$cap = Get-WindowsCapability -Online | Where-Object { $_.Name -like 'OpenSSH.Client*' } | Select-Object -First 1
if ($null -eq $cap) { throw 'OpenSSH.Client capability not found on this image.' }
if ($cap.State -eq 'Installed') { exit 0 }
Add-WindowsCapability -Online -Name $cap.Name
"""
    if ctx.dry_run:
        manifest.record_tool(
            tool=tool,
            layer="infrastructure",
            status="planned",
            install_method="Add-WindowsCapability",
            notes="Would enable OpenSSH.Client optional capability.",
        )
        console.print(f"  [planned] {tool} — dry-run")
        return

    console.print(f"  [installing] {tool} (Windows optional capability) …")
    code, out, err = run_powershell(ps, timeout_s=300.0)
    tail = (out + "\n" + err).strip()[-2000:]
    if code == 0:
        manifest.record_tool(
            tool=tool,
            layer="infrastructure",
            status="installed",
            install_method="Add-WindowsCapability",
            notes=tail or None,
        )
        console.print(f"  [done] {tool}")
        return
    manifest.record_tool(
        tool=tool,
        layer="infrastructure",
        status="failed",
        install_method="Add-WindowsCapability",
        notes=f"exit {code}: {tail}",
    )
    console.print(f"  [failed] {tool} (exit {code}) — may need elevated PowerShell")


def ensure_scoop(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
) -> None:
    """Install Scoop (user scope) when ``scoop`` is not available."""
    tool = "scoop"
    # Detection: also look in the default Scoop shims dir in case it was just
    # installed but its shims are not yet in the machine/user PATH env var.
    detect_ps = r"""
$scoopShims = Join-Path $env:USERPROFILE 'scoop\shims'
if ((Test-Path $scoopShims) -and ($env:PATH -notlike "*$scoopShims*")) {
    $env:PATH = "$scoopShims;$env:PATH"
}
if (Get-Command scoop -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }
"""
    code_d, _, _ = run_powershell(detect_ps, timeout_s=30.0)
    if code_d == 0:
        manifest.record_tool(
            tool=tool,
            layer="infrastructure",
            status="skipped",
            install_method="irm-get.scoop.sh",
            notes="scoop already on PATH.",
        )
        console.print(f"  [skipped] {tool} — already installed")
        return

    if ctx.dry_run:
        manifest.record_tool(
            tool=tool,
            layer="infrastructure",
            status="planned",
            install_method="irm-get.scoop.sh",
            notes="Would run official Scoop installer.",
        )
        console.print(f"  [planned] {tool} — dry-run")
        return

    install_ps = r"""
$ErrorActionPreference = 'Continue'
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction SilentlyContinue
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
$scoopScript = Invoke-RestMethod -Uri https://get.scoop.sh
# -RunAsAdmin was added in later Scoop installer versions; fall back gracefully.
if ($isAdmin) {
    try {
        & ([scriptblock]::Create($scoopScript)) -RunAsAdmin
    } catch {
        if ($_.FullyQualifiedErrorId -like '*NamedParameterNotFound*' -or $_.Exception.Message -like '*RunAsAdmin*') {
            Write-Host 'Scoop installer does not support -RunAsAdmin; retrying without it.'
            & ([scriptblock]::Create($scoopScript))
        } else {
            throw
        }
    }
} else {
    & ([scriptblock]::Create($scoopScript))
}
# Verify installation — shims may not be on PATH yet in this session.
$scoopShims = Join-Path $env:USERPROFILE 'scoop\shims'
if (Test-Path (Join-Path $scoopShims 'scoop.ps1')) { exit 0 }
if (Get-Command scoop -ErrorAction SilentlyContinue) { exit 0 }
exit 1
"""
    console.print(f"  [installing] {tool} …")
    code, out, err = run_powershell(install_ps, timeout_s=600.0)
    tail = (out + "\n" + err).strip()[-2000:]
    if code == 0:
        manifest.record_tool(
            tool=tool,
            layer="infrastructure",
            status="installed",
            install_method="irm-get.scoop.sh",
            notes=tail or None,
        )
        console.print(f"  [done] {tool}")
        return
    manifest.record_tool(
        tool=tool,
        layer="infrastructure",
        status="failed",
        install_method="irm-get.scoop.sh",
        notes=f"exit {code}: {tail}",
    )
    console.print(f"  [failed] {tool} (exit {code})")


def ensure_scoop_cli_bundle(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
) -> None:
    """Install common CLI tools via Scoop (extras bucket for git-delta)."""
    tool = "scoop-cli-bundle"
    if ctx.dry_run:
        manifest.record_tool(
            tool=tool,
            layer="infrastructure",
            status="planned",
            install_method="scoop",
            notes="Would: scoop install bat ripgrep fd fzf jq lazygit delta",
        )
        console.print(f"  [planned] {tool} — dry-run")
        return

    ps = r"""
$ErrorActionPreference = 'Continue'
$scoopShims = Join-Path $env:USERPROFILE 'scoop\shims'
if ((Test-Path $scoopShims) -and ($env:PATH -notlike "*$scoopShims*")) {
    $env:PATH = "$scoopShims;$env:PATH"
}
if (-not (Get-Command scoop -ErrorAction SilentlyContinue)) { exit 2 }
scoop bucket add extras 2>&1 | Out-Null
scoop install bat ripgrep fd fzf jq lazygit delta
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
exit 0
"""
    console.print(f"  [installing] {tool} via scoop (streaming output below)…")
    code, _out, _err = run_powershell(ps, timeout_s=1800.0, stream=True)
    if code == 0:
        manifest.record_tool(
            tool=tool,
            layer="infrastructure",
            status="installed",
            install_method="scoop",
        )
        console.print(f"  [done] {tool}")
        return
    if code == 2:
        manifest.record_tool(
            tool=tool,
            layer="infrastructure",
            status="skipped",
            install_method="scoop",
            notes="scoop not available; install scoop first.",
        )
        console.print(f"  [skipped] {tool} — scoop not on PATH")
        return
    manifest.record_tool(
        tool=tool,
        layer="infrastructure",
        status="failed",
        install_method="scoop",
        notes=f"exit {code}: see terminal output above",
    )
    console.print(f"  [failed] {tool} (exit {code})")


def ensure_rustup_default(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
) -> None:
    """Install stable Rust via rustup-init when rustc is missing."""
    tool = "rustup-stable"
    detect = r"if (Get-Command rustc -ErrorAction SilentlyContinue) { exit 0 } else { exit 1 }"
    code_d, _, _ = run_powershell(detect, timeout_s=30.0)
    if code_d == 0:
        manifest.record_tool(
            tool=tool,
            layer="languages",
            status="skipped",
            install_method="rustup-init",
            notes="rustc already on PATH.",
        )
        console.print(f"  [skipped] {tool} — already installed")
        return

    if ctx.dry_run:
        manifest.record_tool(
            tool=tool,
            layer="languages",
            status="planned",
            install_method="rustup-init",
            notes="Would download rustup-init and run with -y.",
        )
        console.print(f"  [planned] {tool} — dry-run")
        return

    ps = r"""
$ErrorActionPreference = 'Stop'
$uri = 'https://static.rust-lang.org/rustup/dist/x86_64-pc-windows-msvc/rustup-init.exe'
$dst = Join-Path $env:TEMP 'rustup-init.exe'
Invoke-WebRequest -Uri $uri -OutFile $dst
$p = Start-Process -FilePath $dst -ArgumentList @('-y') -PassThru -Wait
exit $p.ExitCode
"""
    console.print(f"  [installing] {tool} …")
    code, out, err = run_powershell(ps, timeout_s=3600.0)
    tail = (out + "\n" + err).strip()[-2000:]
    if code == 0:
        manifest.record_tool(
            tool=tool,
            layer="languages",
            status="installed",
            install_method="rustup-init",
            notes=tail or None,
        )
        console.print(f"  [done] {tool}")
        return
    manifest.record_tool(
        tool=tool,
        layer="languages",
        status="failed",
        install_method="rustup-init",
        notes=f"exit {code}: {tail}",
    )
    console.print(f"  [failed] {tool} (exit {code})")


def ensure_wsl_prereq(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
) -> None:
    """Enable WSL + VirtualMachinePlatform optional features (requires admin reboot sometimes)."""
    tool = "wsl-prereq"
    if not ctx.enable_wsl:
        manifest.record_tool(
            tool=tool,
            layer="devops",
            status="skipped",
            install_method="Enable-WindowsOptionalFeature",
            notes="Pass --enable-wsl to enable Microsoft-Windows-Subsystem-Linux + VirtualMachinePlatform.",
        )
        console.print(f"  [skipped] {tool} — use --enable-wsl")
        return

    if ctx.dry_run:
        manifest.record_tool(
            tool=tool,
            layer="devops",
            status="planned",
            install_method="Enable-WindowsOptionalFeature",
            notes="Would enable WSL and VirtualMachinePlatform.",
        )
        console.print(f"  [planned] {tool} — dry-run")
        return

    ps = r"""
$ErrorActionPreference = 'Stop'
dism.exe /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
$c1 = $LASTEXITCODE
dism.exe /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
$c2 = $LASTEXITCODE
if ($c1 -eq 3010 -or $c2 -eq 3010) { exit 3010 }
if ($c1 -ne 0) { exit $c1 }
if ($c2 -ne 0) { exit $c2 }
exit 0
"""
    console.print(f"  [installing] {tool} via DISM …")
    code, out, err = run_powershell(ps, timeout_s=600.0)
    tail = (out + "\n" + err).strip()[-2000:]
    if code in (0, 3010):
        manifest.record_tool(
            tool=tool,
            layer="devops",
            status="installed",
            install_method="DISM",
            notes=tail or "Exit 3010 means reboot may be required before wsl --install.",
        )
        console.print(f"  [done] {tool}" + (" (reboot may be required)" if code == 3010 else ""))
        return
    manifest.record_tool(
        tool=tool,
        layer="devops",
        status="failed",
        install_method="DISM",
        notes=f"exit {code}: {tail}",
    )
    console.print(f"  [failed] {tool} (exit {code}) — run installer elevated")


def ensure_wsl_default_distro(
    ctx: InstallContext,
    manifest: Manifest,
    console: Console,
    distro: str,
) -> None:
    """Run ``wsl --install -d <distro>`` after optional features (may require prior reboot)."""
    tool = "wsl-default-distro"
    if not ctx.enable_wsl:
        return
    d = distro.strip()
    if not d:
        return

    if ctx.dry_run:
        manifest.record_tool(
            tool=tool,
            layer="devops",
            status="planned",
            install_method="wsl.exe",
            notes=f"Would run: wsl.exe --install -d {d}",
        )
        console.print(f"  [planned] {tool} ({d}) — dry-run")
        return

    ps = f"""
$ErrorActionPreference = 'Stop'
$distro = '{d.replace("'", "''")}'
$proc = Start-Process -FilePath 'wsl.exe' -ArgumentList @('--install', '-d', $distro) -PassThru -Wait -NoNewWindow
exit $proc.ExitCode
"""
    console.print(f"  [installing] {tool} ({d}) via wsl.exe …")
    code, out, err = run_powershell(ps, timeout_s=3600.0)
    tail = (out + "\n" + err).strip()[-2000:]
    if code == 0:
        manifest.record_tool(
            tool=tool,
            layer="devops",
            status="installed",
            install_method="wsl.exe",
            notes=tail or f"wsl --install -d {d} completed (reboot may still be required on first enable).",
        )
        console.print(f"  [done] {tool}")
        return

    manifest.record_tool(
        tool=tool,
        layer="devops",
        status="failed",
        install_method="wsl.exe",
        notes=f"exit {code}: {tail}",
    )
    console.print(
        f"  [failed] {tool} (exit {code}) — if DISM just ran, reboot then re-run installer or: wsl --install -d {d}"
    )
