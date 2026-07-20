# Adobe AE Error 146 Deep Scan Script

$ErrorActionPreference = 'Continue'
$aeDir = "C:\Program Files\Adobe\Adobe After Effects 2025"
$logFile = "D:\AE-Work\ae_install_diagnosis.txt"

function Write-Log($msg) {
    Write-Output $msg
    $msg | Out-File -FilePath $logFile -Append -Encoding UTF8
}

"=== Adobe After Effects 2025 Installation Diagnosis ===" | Out-File -FilePath $logFile -Encoding UTF8
"Time: $(Get-Date)" | Out-File -FilePath $logFile -Append -Encoding UTF8
"" | Out-File -FilePath $logFile -Append -Encoding UTF8

# 1. Check AE directory structure
Write-Log "=== 1. AE 2025 Installation Directory ==="
if (Test-Path $aeDir) {
    $totalSize = (Get-ChildItem $aeDir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1GB
    Write-Log "Directory: $aeDir"
    Write-Log "Total size: $([math]::Round($totalSize, 2)) GB"
    Write-Log "Top-level folders:"
    Get-ChildItem $aeDir -Directory | ForEach-Object {
        $subSize = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB
        Write-Log "  $($_.Name) - $([math]::Round($subSize, 1)) MB"
    }

    # Check for critical files
    Write-Log ""
    Write-Log "=== 2. Critical File Checks ==="
    $criticalFiles = @(
        "Support Files\AfterFX.exe",
        "Support Files\aescriptrunner.exe",
        "Support Files\afterfx.com",
        "Support Files\aerender.exe"
    )
    foreach ($f in $criticalFiles) {
        $fullPath = Join-Path $aeDir $f
        if (Test-Path $fullPath) {
            $ver = (Get-Item $fullPath).VersionInfo.ProductVersion
            Write-Log "  [OK] $f (v$ver)"
        } else {
            Write-Log "  [MISSING] $f"
        }
    }
} else {
    Write-Log "AE 2025 directory NOT FOUND"
}

# 3. Check for .tmp / .partial / leftover files
Write-Log ""
Write-Log "=== 3. Suspicious / Temporary Files (error 146 cause) ==="
$suspicious = Get-ChildItem $aeDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Extension -match '\.tmp|\.bak|\.old|\.partial|_bak|_old|_new' -or
    $_.Name -match '^\._' -or
    $_.Name -match '\.download' -or
    $_.Name.StartsWith('~$') -or
    $_.Name -match '^__MACOSX'
}
if ($suspicious) {
    Write-Log "Found $($suspicious.Count) suspicious files:"
    $suspicious | Select-Object -First 20 | ForEach-Object {
        Write-Log "  $($_.FullName) ($([math]::Round($_.Length / 1KB, 2)) KB)"
    }
    if ($suspicious.Count -gt 20) {
        Write-Log "  ... and $($suspicious.Count - 20) more"
    }
} else {
    Write-Log "  No suspicious temp files found"
}

# 4. Check for files that can't be renamed (locked/permissions)
Write-Log ""
Write-Log "=== 4. Locked / Permission-denied Files ==="
$lockedCount = 0
$lockedFiles = @()
Get-ChildItem $aeDir -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 500 | ForEach-Object {
    try {
        $stream = [System.IO.File]::Open($_.FullName, 'Open', 'ReadWrite', 'None')
        $stream.Close()
    } catch {
        $lockedCount++
        if ($lockedCount -le 10) {
            $lockedFiles += "$($_.FullName) - $($_.Exception.Message)"
        }
    }
}
if ($lockedCount -gt 0) {
    Write-Log "Found $lockedCount locked/undeletable files:"
    $lockedFiles | ForEach-Object { Write-Log "  $_" }
} else {
    Write-Log "  All files are accessible (no locks)"
}

# 5. Check for duplicate / same-name folders
Write-Log ""
Write-Log "=== 5. Duplicate Name Pattern (146 often caused by renamed dirs) ==="
$dupPatterns = Get-ChildItem $aeDir -Directory | Where-Object {
    $_.Name -match '_\d+$| copy| - | copy \(\d+\)'
}
if ($dupPatterns) {
    Write-Log "Potential duplicate folders:"
    $dupPatterns | ForEach-Object { Write-Log "  $($_.Name)" }
} else {
    Write-Log "  No obvious duplicate folders"
}

# 6. Check ProgramData / AppData for install cache
Write-Log ""
Write-Log "=== 6. Install Cache / Temp Directories ==="
$cachePaths = @(
    "C:\ProgramData\Adobe\Installers",
    "C:\Program Files (x86)\Common Files\Adobe\Installers",
    "$env:TEMP\Adobe",
    "$env:LOCALAPPDATA\Temp\Adobe",
    "C:\Windows\Temp\Adobe"
)
foreach ($p in $cachePaths) {
    if (Test-Path $p) {
        $itemCount = (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        $size = (Get-ChildItem $p -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB
        Write-Log "  [EXISTS] $p ($itemCount files, $([math]::Round($size, 1)) MB)"
    } else {
        Write-Log "  [MISSING] $p"
    }
}

# 7. Check Common Files After Effects dir
Write-Log ""
Write-Log "=== 7. Common Files After Effects ==="
$commonAEDir = "C:\Program Files\Common Files\Adobe\After Effects"
if (Test-Path $commonAEDir) {
    Get-ChildItem $commonAEDir -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 15 | ForEach-Object {
        Write-Log "  $($_.FullName)"
    }
} else {
    Write-Log "  Directory not found"
}

# 8. Registry install entries
Write-Log ""
Write-Log "=== 8. Registry Install Entries ==="
$regPaths = @(
    "HKLM:\SOFTWARE\Adobe\After Effects",
    "HKLM:\SOFTWARE\WOW6432Node\Adobe\After Effects",
    "HKCU:\SOFTWARE\Adobe\After Effects"
)
foreach ($rp in $regPaths) {
    if (Test-Path $rp) {
        Write-Log "  [FOUND] $rp"
        Get-Item $rp | Select-Object -ExpandProperty Property | ForEach-Object {
            $val = Get-ItemProperty $rp -Name $_ -ErrorAction SilentlyContinue
            Write-Log "    $_ = $($val.$_)"
        }
    }
}

Write-Log ""
Write-Log "=== Diagnosis Complete ==="
Write-Log "Log saved to: $logFile"
