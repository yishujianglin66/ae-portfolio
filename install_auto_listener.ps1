#Requires -Version 5.1
<#
.SYNOPSIS
    Installs ae_mcp_auto_listener.jsx into After Effects Startup folder.
.DESCRIPTION
    Detects AE installation, copies the listener script to Scripts/Startup,
    and verifies installation. Supports both machine-wide and user-level
    installation.
#>

[CmdletBinding()]
param(
    [string]$SourceScript = "",
    [switch]$UserLevel,
    [switch]$Force
)

$ErrorActionPreference = "Stop"

# ===== Helper functions =====
function Write-Header($text) {
    Write-Host "`n========================================" -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Ok($text) {
    Write-Host "[OK]   $text" -ForegroundColor Green
}

function Write-Warn($text) {
    Write-Host "[WARN] $text" -ForegroundColor Yellow
}

function Write-Err($text) {
    Write-Host "[ERR]  $text" -ForegroundColor Red
}

function Write-Info($text) {
    Write-Host "[INFO] $text" -ForegroundColor White
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole(
        [Security.Principal.WindowsBuiltInRole]::Administrator
    )
}

function Get-AEInstallPath {
    param([string]$Version = "2026")

    $candidates = @(
        "C:\Program Files\Adobe\Adobe After Effects $Version",
        "C:\Program Files\Adobe\Adobe After Effects 2025",
        "C:\Program Files\Adobe\Adobe After Effects 2024",
        "D:\Program Files\Adobe\Adobe After Effects $Version",
        "D:\Program Files\Adobe\Adobe After Effects 2025",
        "D:\Program Files\Adobe\Adobe After Effects 2024",
        "E:\Program Files\Adobe\Adobe After Effects $Version",
        "E:\Program Files\Adobe\Adobe After Effects 2025",
        "E:\Program Files\Adobe\Adobe After Effects 2024"
    )

    # Convert version (2026 -> 26.0)
    if ($Version -match "^20(\d{2})$") {
        $majorVer = $matches[1] + ".0"
    } else {
        $majorVer = $Version
    }

    # Search registry for AE installation
    $regPaths = @(
        "HKLM:\SOFTWARE\Adobe\After Effects\$majorVer",
        "HKLM:\SOFTWARE\WOW6432Node\Adobe\After Effects\$majorVer",
        "HKLM:\SOFTWARE\Adobe\After Effects\26.0",
        "HKLM:\SOFTWARE\WOW6432Node\Adobe\After Effects\26.0",
        "HKLM:\SOFTWARE\Adobe\After Effects\25.0",
        "HKLM:\SOFTWARE\WOW6432Node\Adobe\After Effects\25.0",
        "HKLM:\SOFTWARE\Adobe\After Effects\24.0",
        "HKLM:\SOFTWARE\WOW6432Node\Adobe\After Effects\24.0"
    )

    foreach ($rp in $regPaths) {
        if (Test-Path $rp) {
            try {
                $regVal = Get-ItemProperty -Path $rp -Name "InstallPath" -ErrorAction SilentlyContinue
                if ($regVal -and $regVal.InstallPath) {
                    $path = $regVal.InstallPath.TrimEnd('\')
                    if (Test-Path $path) {
                        return $path
                    }
                }
            } catch {}
        }
    }

    # Search filesystem
    foreach ($cand in $candidates) {
        if (Test-Path $cand) {
            return $cand
        }
    }

    # Broad search on C: and D:
    $searchRoots = @("C:\Program Files\Adobe", "D:\Program Files\Adobe")
    foreach ($root in $searchRoots) {
        if (Test-Path $root) {
            $dirs = Get-ChildItem -Path $root -Directory -Filter "Adobe After Effects*" -ErrorAction SilentlyContinue
            foreach ($d in $dirs) {
                return $d.FullName
            }
        }
    }

    return $null
}

function Get-UserStartupPath {
    # Try to detect AE version from AppData
    $aeAppData = "$env:APPDATA\Adobe\After Effects"
    if (Test-Path $aeAppData) {
        $versions = Get-ChildItem -Path $aeAppData -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending
        if ($versions) {
            $latest = $versions[0].FullName
            $startup = Join-Path $latest "Scripts\Startup"
            return $startup
        }
    }
    # Fallback to 24.0
    return "$env:APPDATA\Adobe\After Effects\24.0\Scripts\Startup"
}

function Test-AERunning {
    $procs = Get-Process -Name "AfterFX" -ErrorAction SilentlyContinue
    return ($null -ne $procs -and $procs.Count -gt 0)
}

# ===== Main =====
Write-Header "AE MCP Auto Listener Installer"

# Resolve source script path
if ([string]::IsNullOrWhiteSpace($SourceScript)) {
    $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
    if ([string]::IsNullOrWhiteSpace($scriptDir)) {
        $scriptDir = Get-Location
    }
    $SourceScript = Join-Path $scriptDir "ae_mcp_auto_listener.jsx"
}

# 1. Check source script
if (-not (Test-Path $SourceScript)) {
    Write-Err "Source script not found: $SourceScript"
    exit 1
}
Write-Ok "Source script found: $SourceScript"

# 2. Detect AE installation
Write-Info "Detecting After Effects installation..."
$aePath = Get-AEInstallPath
if (-not $aePath) {
    Write-Err "After Effects installation not found."
    Write-Info "Searched common locations and registry."
    exit 1
}
Write-Ok "AE installation found: $aePath"

# 3. Determine target path
$startupDir = $null
$installType = ""

if ($UserLevel) {
    $startupDir = Get-UserStartupPath
    $installType = "User-Level"
    Write-Info "User-level install selected"
} else {
    $startupDir = Join-Path $aePath "Support Files\Scripts\Startup"
    $installType = "Machine-Wide"
    Write-Info "Machine-wide install selected"
}

# 4. Check admin rights for machine-wide
if (-not $UserLevel) {
    $programFiles = "$env:ProgramFiles"
    if ($aePath.StartsWith($programFiles, [StringComparison]::OrdinalIgnoreCase)) {
        if (-not (Test-Admin)) {
            Write-Warn "Administrator rights required for machine-wide install."
            Write-Info "Please run PowerShell as Administrator,"
            Write-Info "or use -UserLevel switch for user-level install."
            $response = Read-Host "Attempt user-level install instead? (Y/n)"
            if ($response -ne "n" -and $response -ne "N") {
                $UserLevel = $true
                $startupDir = Get-UserStartupPath
                $installType = "User-Level (fallback)"
                Write-Info "Switching to user-level install"
            } else {
                exit 1
            }
        } else {
            Write-Ok "Running with administrator rights"
        }
    }
}

# 5. Create startup directory
Write-Info "Target directory: $startupDir"
if (-not (Test-Path $startupDir)) {
    try {
        New-Item -ItemType Directory -Path $startupDir -Force | Out-Null
        Write-Ok "Created startup directory"
    } catch {
        Write-Err "Failed to create directory: $_"
        exit 1
    }
} else {
    Write-Ok "Startup directory already exists"
}

# 6. Check if AE is running
if (Test-AERunning) {
    Write-Warn "After Effects is currently running."
    Write-Info "The script will only take effect after AE restarts."
    if (-not $Force) {
        $response = Read-Host "Continue installation? (Y/n)"
        if ($response -eq "n" -or $response -eq "N") {
            Write-Info "Installation cancelled by user"
            exit 0
        }
    }
} else {
    Write-Ok "After Effects is not running"
}

# 7. Copy script
$destFile = Join-Path $startupDir "ae_mcp_auto_listener.jsx"
try {
    Copy-Item -Path $SourceScript -Destination $destFile -Force
    Write-Ok "Script copied to: $destFile"
} catch {
    Write-Err "Failed to copy script: $_"
    exit 1
}

# 8. Verify installation
Write-Info "Verifying installation..."
$verified = $false
if (Test-Path $destFile) {
    $srcHash = (Get-FileHash -Path $SourceScript -Algorithm SHA256).Hash
    $dstHash = (Get-FileHash -Path $destFile -Algorithm SHA256).Hash
    if ($srcHash -eq $dstHash) {
        $verified = $true
        Write-Ok "File hash verified (SHA256)"
    } else {
        Write-Err "File hash mismatch!"
    }
} else {
    Write-Err "Destination file missing after copy"
}

# 9. Also offer user-level copy if machine-wide
if (-not $UserLevel) {
    $userStartup = Get-UserStartupPath
    if ($userStartup -ne $startupDir) {
        Write-Info "Also installing to user startup for redundancy..."
        if (-not (Test-Path $userStartup)) {
            New-Item -ItemType Directory -Path $userStartup -Force | Out-Null
        }
        $userDest = Join-Path $userStartup "ae_mcp_auto_listener.jsx"
        try {
            Copy-Item -Path $SourceScript -Destination $userDest -Force
            Write-Ok "Also copied to user startup: $userDest"
        } catch {
            Write-Warn "Could not copy to user startup: $_"
        }
    }
}

# 10. Installation report
Write-Header "Installation Report"
Write-Info "Install Type : $installType"
Write-Info "AE Path      : $aePath"
Write-Info "Target Dir   : $startupDir"
Write-Info "Script File  : $destFile"
Write-Info "Verified     : $verified"
Write-Info "AE Running   : $(Test-AERunning)"

if ($verified) {
    Write-Ok "Installation completed successfully!"
    Write-Info "After Effects will auto-run the listener on next startup."
} else {
    Write-Warn "Installation completed but verification failed."
}

Write-Host ""
