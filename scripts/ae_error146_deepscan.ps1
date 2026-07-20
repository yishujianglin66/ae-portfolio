# Deep scan for Adobe install logs and error 146 root cause

$ErrorActionPreference = 'Continue'
$logFile = "D:\AE-Work\ae_error146_deepscan.txt"

function Write-Log($msg) {
    Write-Output $msg
    $msg | Out-File -FilePath $logFile -Append -Encoding UTF8
}

"=== Adobe AE Error 146 Deep Diagnosis v2 ===" | Out-File -FilePath $logFile -Encoding UTF8
"Time: $(Get-Date)" | Out-File -FilePath $logFile -Append -Encoding UTF8
"" | Out-File -FilePath $logFile -Append -Encoding UTF8

# Step 1: Find all Adobe install log files
Write-Log "=== Step 1: Search for Adobe Installer Log Files ==="
$logLocations = @(
    "$env:TEMP",
    "$env:LOCALAPPDATA\Temp",
    "C:\Windows\Temp",
    "C:\Program Files (x86)\Common Files\Adobe\Installers",
    "C:\ProgramData\Adobe\Installers",
    "$env:LOCALAPPDATA\Adobe",
    "C:\Users\$env:USERNAME\AppData\Local\Adobe"
)

$allLogs = @()
foreach ($loc in $logLocations) {
    if (Test-Path $loc) {
        Get-ChildItem $loc -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -match '\.log$|\.log\.gz$|install|installer|Setup\.log|PDApp|oobelib' -and
            $_.LastWriteTime -gt (Get-Date).AddDays(-7)
        } | ForEach-Object { $allLogs += $_ }
    }
}
Write-Log "Found $($allLogs.Count) recent log files"
$allLogs | Sort-Object Length -Descending | Select-Object -First 15 | ForEach-Object {
    $sizeKB = [math]::Round($_.Length / 1KB, 1)
    Write-Log "  $($_.FullName) ($sizeKB KB, $($_.LastWriteTime))"
}

# Step 2: Check for read-only / system / hidden files
Write-Log ""
Write-Log "=== Step 2: Files with ReadOnly / System / Hidden attributes ==="
$aeDir = "C:\Program Files\Adobe\Adobe After Effects 2025"
$problemFiles = Get-ChildItem $aeDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Attributes -match 'ReadOnly' -or $_.Attributes -match 'System'
}
if ($problemFiles) {
    Write-Log "Found $($problemFiles.Count) files with ReadOnly/System attributes"
    $problemFiles | Select-Object -First 20 | ForEach-Object {
        Write-Log "  [$($_.Attributes)] $($_.FullName)"
    }
} else {
    Write-Log "  No ReadOnly/System files found"
}

# Step 3: Check for junction points / symbolic links
Write-Log ""
Write-Log "=== Step 3: Junction Points / Symbolic Links ==="
$junctions = Get-ChildItem $aeDir -Recurse -Directory -ErrorAction SilentlyContinue | Where-Object {
    $_.LinkType -ne $null -and $_.LinkType -ne ''
}
if ($junctions) {
    Write-Log "Found $($junctions.Count) junction/symlink directories"
    $junctions | ForEach-Object {
        Write-Log "  [$($_.LinkType)] $($_.FullName) -> $($_.Target)"
    }
} else {
    Write-Log "  No junction points found"
}

# Step 4: Check Common Files version conflicts
Write-Log ""
Write-Log "=== Step 4: Common Files After Effects Versions ==="
$commonAEDir = "C:\Program Files\Common Files\Adobe\After Effects"
if (Test-Path $commonAEDir) {
    Get-ChildItem $commonAEDir -Directory | ForEach-Object {
        Write-Log "  Version folder: $($_.Name)"
        $subFiles = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        $subSize = [math]::Round((Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB, 1)
        Write-Log "    Files: $subFiles, Size: $subSize MB"
    }
}

# Step 5: Check for OneDrive sync status on AE directory
Write-Log ""
Write-Log "=== Step 5: OneDrive / Sync Status ==="
$aeDirItem = Get-Item $aeDir
$aeParent = Split-Path $aeDir -Parent
Write-Log "AE dir: $aeDir"
Write-Log "Parent: $aeParent"
# Check if OneDrive syncs Program Files (unlikely but worth checking)
$oneDrivePaths = @("$env:OneDrive", "$env:OneDriveConsumer", "$env:OneDriveCommercial")
foreach ($od in $oneDrivePaths) {
    if ($od -and (Test-Path $od)) {
        Write-Log "OneDrive path: $od"
    }
}

# Step 6: Check for antivirus/security locks
Write-Log ""
Write-Log "=== Step 6: Security Software ==="
try {
    $av = Get-CimInstance -Namespace root/SecurityCenter2 -ClassName AntivirusProduct -ErrorAction Stop
    if ($av) {
        $av | ForEach-Object {
            Write-Log "  AV Product: $($_.displayName)"
            Write-Log "  State: $($_.productState)"
        }
    } else {
        Write-Log "  No AV product found via WMI"
    }
} catch {
    Write-Log "  AV check failed: $($_.Exception.Message)"
}

# Step 7: Check Installer registry entries and pending renames
Write-Log ""
Write-Log "=== Step 7: Pending File Rename Operations (RunOnce) ==="
$runOncePaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\RunOnce"
)
foreach ($rp in $runOncePaths) {
    if (Test-Path $rp) {
        Write-Log "  $rp"
        $props = Get-ItemProperty $rp -ErrorAction SilentlyContinue
        $props.PSObject.Properties | Where-Object { $_.Name -notlike 'PS*' } | ForEach-Object {
            Write-Log "    $($_.Name) = $($_.Value)"
        }
    }
}

# Check PendingFileRenameOperations
$pfr = "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager"
if (Test-Path $pfr) {
    $pfrValue = (Get-ItemProperty $pfr -Name "PendingFileRenameOperations" -ErrorAction SilentlyContinue)."PendingFileRenameOperations"
    if ($pfrValue) {
        Write-Log ""
        Write-Log "  PendingFileRenameOperations entries (reboot needed):"
        $pfrValue | Select-Object -First 20 | ForEach-Object {
            Write-Log "    $_"
        }
    } else {
        Write-Log "  No pending file rename operations"
    }
}

# Step 8: Permissions check on AE directory
Write-Log ""
Write-Log "=== Step 8: AE Directory Permissions ==="
try {
    $acl = Get-Acl $aeDir -ErrorAction Stop
    $owner = $acl.Owner
    Write-Log "  Owner: $owner"
    Write-Log "  Access rules:"
    $acl.Access | Select-Object -First 10 | ForEach-Object {
        Write-Log "    $($_.IdentityReference): $($_.FileSystemRights) ($($_.AccessControlType))"
    }
} catch {
    Write-Log "  Permission check failed: $($_.Exception.Message)"
}

# Step 9: Check for files in use by other processes
Write-Log ""
Write-Log "=== Step 9: Files Locked by Other Processes (handle check) ==="
# Check if handle.exe or openfiles is available
$handleFound = $false
if (Get-Command handle.exe -ErrorAction SilentlyContinue) {
    $handleFound = $true
    Write-Log "  handle.exe available"
} else {
    Write-Log "  handle.exe not found (Sysinternals not installed)"
}

# Alternative: use openfiles
try {
    $openFilesTest = openfiles /query /s localhost /fo csv 2>$null
    Write-Log "  openfiles command available"
} catch {
    Write-Log "  openfiles not available or openfiles global flag not set"
}

Write-Log ""
Write-Log "=== Diagnosis Complete ==="
Write-Log "Log saved to: $logFile"
