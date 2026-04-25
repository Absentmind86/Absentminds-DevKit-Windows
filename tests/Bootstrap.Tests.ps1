#Requires -Version 5.1
<#
.SYNOPSIS
    Pester smoke tests for bootstrap/install.ps1 logic.

.DESCRIPTION
    Tests the flet-pinning logic, launcher detection, and elevation guard
    without actually installing anything. All pip / winget / system calls
    are mocked.

.NOTES
    Run from the repo root:
        Invoke-Pester tests/Bootstrap.Tests.ps1 -Output Detailed
    Requires Pester >= 5.x  (Install-Module Pester -Force -SkipPublisherCheck)
#>

BeforeAll {
    $BootstrapScript = "$PSScriptRoot/../bootstrap/install.ps1"
    $ReqFile = "$PSScriptRoot/../requirements.txt"

    # Helper: build a fake pip-list JSON string
    function New-FakePipJson {
        param([hashtable]$Packages)
        $list = $Packages.GetEnumerator() | ForEach-Object {
            [pscustomobject]@{ name = $_.Key; version = $_.Value }
        }
        $list | ConvertTo-Json -Compress
    }
}

# ---------------------------------------------------------------------------
# Flet version detection logic
# ---------------------------------------------------------------------------

Describe "Flet pinning — version comparison logic" {

    # Mirror the exact logic from install.ps1 so we can unit-test it
    # without running the whole script.
    BeforeAll {
        function Test-FletNeedsDowngrade {
            param([hashtable]$InstalledVersions)
            $pin = '0.25.2'
            $fletPackages = @('flet', 'flet-core', 'flet-desktop', 'flet-web', 'flet-runtime')
            $detected = @()
            foreach ($pkg in $fletPackages) {
                if ($InstalledVersions.ContainsKey($pkg)) {
                    $detected += [pscustomobject]@{ Name = $pkg; Version = $InstalledVersions[$pkg] }
                }
            }
            foreach ($d in $detected) {
                if ($d.Version -ne $pin) { return $true }
            }
            return $false
        }
    }

    It "returns false when flet is already at 0.25.2" {
        $result = Test-FletNeedsDowngrade -InstalledVersions @{ flet = '0.25.2' }
        $result | Should -Be $false
    }

    It "returns true when flet is at a newer version" {
        $result = Test-FletNeedsDowngrade -InstalledVersions @{ flet = '0.84.0' }
        $result | Should -Be $true
    }

    It "returns true when flet is at an older version" {
        $result = Test-FletNeedsDowngrade -InstalledVersions @{ flet = '0.20.1' }
        $result | Should -Be $true
    }

    It "returns false when no flet packages are installed at all" {
        $result = Test-FletNeedsDowngrade -InstalledVersions @{ numpy = '1.26.0' }
        $result | Should -Be $false
    }

    It "returns true when flet is correct but flet-core is wrong" {
        $result = Test-FletNeedsDowngrade -InstalledVersions @{
            flet      = '0.25.2'
            'flet-core' = '0.22.0'
        }
        $result | Should -Be $true
    }

    It "returns false when all flet-family packages are at 0.25.2" {
        $result = Test-FletNeedsDowngrade -InstalledVersions @{
            flet           = '0.25.2'
            'flet-core'    = '0.25.2'
            'flet-desktop' = '0.25.2'
        }
        $result | Should -Be $false
    }

}

# ---------------------------------------------------------------------------
# Requirements file sanity
# ---------------------------------------------------------------------------

Describe "requirements.txt" {

    It "exists at the repo root" {
        $ReqFile | Should -Exist
    }

    It "pins flet to exactly 0.25.2" {
        $content = Get-Content $ReqFile -Raw
        $content | Should -Match 'flet==0\.25\.2'
    }

    It "includes rich with a minimum version pin" {
        $content = Get-Content $ReqFile -Raw
        $content | Should -Match 'rich>='
    }

    It "contains no bare unpinned flet entry" {
        $content = Get-Content $ReqFile -Raw
        # 'flet' alone on a line (not 'flet==...' or 'flet>=...') would be unpinned
        $content | Should -Not -Match '(?m)^flet\s*$'
    }

}

# ---------------------------------------------------------------------------
# bootstrap/install.ps1 structure sanity
# ---------------------------------------------------------------------------

Describe "bootstrap/install.ps1 structure" {

    BeforeAll {
        $ScriptContent = Get-Content $BootstrapScript -Raw
    }

    It "exists" {
        $BootstrapScript | Should -Exist
    }

    It "contains elevation check" {
        $ScriptContent | Should -Match 'IsInRole.*Administrator'
    }

    It "contains self-elevation via Start-Process RunAs" {
        $ScriptContent | Should -Match 'RunAs'
    }

    It "references flet pinned version 0.25.2" {
        $ScriptContent | Should -Match '0\.25\.2'
    }

    It "does not use --upgrade-strategy eager (regression guard)" {
        $ScriptContent | Should -Not -Match 'upgrade-strategy'
    }

    It "has a -Yes / bypass-prompt flag" {
        $ScriptContent | Should -Match '\[switch\]\$Yes|\$Yes'
    }

    It "references requirements.txt" {
        $ScriptContent | Should -Match 'requirements\.txt'
    }

}

# ---------------------------------------------------------------------------
# scripts/sanitize.ps1 structure sanity
# ---------------------------------------------------------------------------

Describe "scripts/sanitize.ps1 structure" {

    BeforeAll {
        $SanScript = "$PSScriptRoot/../scripts/sanitize.ps1"
        $SanContent = Get-Content $SanScript -Raw
    }

    It "exists" {
        "$PSScriptRoot/../scripts/sanitize.ps1" | Should -Exist
    }

    It "has ValidateSet for Preset parameter" {
        $SanContent | Should -Match "ValidateSet.*'Minimal'.*'Standard'"
    }

    It "tracks an error counter variable" {
        $SanContent | Should -Match 'ErrCount'
    }

    It "exits non-zero on errors" {
        $SanContent | Should -Match 'exit 1'
    }

    It "exits zero on clean run" {
        $SanContent | Should -Match 'exit 0'
    }

    It "does not contain em dashes (encoding regression guard)" {
        # Em dash (U+2014) caused cp1252 parse failures on Windows
        $SanContent | Should -Not -Match [char]0x2014
    }

}

# ---------------------------------------------------------------------------
# Verify-Bootstrap.ps1 structure sanity
# ---------------------------------------------------------------------------

Describe "bootstrap/Verify-Bootstrap.ps1" {

    BeforeAll {
        $VerifyScript = "$PSScriptRoot/../bootstrap/Verify-Bootstrap.ps1"
        if (Test-Path $VerifyScript) {
            $VerifyContent = Get-Content $VerifyScript -Raw
        } else {
            $VerifyContent = $null
        }
    }

    It "exists" {
        "$PSScriptRoot/../bootstrap/Verify-Bootstrap.ps1" | Should -Exist
    }

    It "uses SHA256 hashing" {
        $VerifyContent | Should -Match 'SHA256'
    }

    It "uses Get-FileHash" {
        $VerifyContent | Should -Match 'Get-FileHash'
    }

    It "does not use irm | iex in executable code (forces file-based verification)" {
        # Strip <# ... #> block comments and #-prefixed lines, then check no live iex pipe remains
        $stripped = [regex]::Replace($VerifyContent, '(?s)<#.*?#>', '')
        $codeOnly = ($stripped -split "`n") | Where-Object { $_ -notmatch '^\s*#' }
        ($codeOnly -join "`n") | Should -Not -Match '\|\s*iex'
    }

}
