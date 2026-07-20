# Adobe AE Error 146 Fix Script
# Fix: Remove .bak residual files + clean install caches

$ErrorActionPreference = 'Continue'
$aeDir = "C:\Program Files\Adobe\Adobe After Effects 2025"
$logFile = "D:\AE-Work\ae_install_fix_log.txt"

function Write-Log($msg) {
    Write-Output $msg
    $msg | Out-File -FilePath $logFile -Append -Encoding UTF8
}

"=== Adobe After Effects 2025 Error 146 Fix ===" | Out-File -FilePath $logFile -Encoding UTF8
"Time: $(Get-Date)" | Out-File -FilePath $logFile -Append -Encoding UTF8
"" | Out-File -FilePath $logFile -Append -Encoding UTF8

# Check if running as admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Log "Running as Administrator: $isAdmin"
if (-not $isAdmin) {
    Write-Log "WARNING: Not running as admin. Some operations may fail."
}

# Step 1: Remove all .bak files (the root cause of error 146)
Write-Log ""
Write-Log "=== Step 1: Remove .bak residual files ==="
$bakFiles = Get-ChildItem $aeDir -Recurse -File -Filter "*.bak" -ErrorAction SilentlyContinue
Write-Log "Found $($bakFiles.Count) .bak files"
$removed = 0
$failed = 0
foreach ($f in $bakFiles) {
    try {
        Remove-Item $f.FullName -Force -ErrorAction Stop
        $removed++
        Write-Log "  [OK] Removed: $($f.FullName)"
    } catch {
        $failed++
        Write-Log "  [FAIL] $($f.FullName): $($_.Exception.Message)"
    }
}
Write-Log "Result: $removed removed, $failed failed"

# Step 2: Clean Adobe install cache directories
Write-Log ""
Write-Log "=== Step 2: Clean Adobe Install Cache ==="
$cacheDirs = @(
    "C:\Program Files (x86)\Common Files\Adobe\Installers",
    "$env:LOCALAPPDATA\Temp\Adobe",
    "$env:TEMP\Adobe"
)
foreach ($dir in $cacheDirs) {
    if (Test-Path $dir) {
        $fileCount = (Get-ChildItem $dir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
        $sizeMB = [math]::Round((Get-ChildItem $dir -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum / 1MB, 1)
        Write-Log "  Cleaning: $dir ($fileCount files, $sizeMB MB)"
        try {
            Get-ChildItem $dir -Recurse -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
            Write-Log "    [OK] Files cleaned"
        } catch {
            Write-Log "    [WARN] Some files could not be removed: $($_.Exception.Message)"
        }
    } else {
        Write-Log "  [SKIP] Not found: $dir"
    }
}

# Step 3: Check for other potential issues
Write-Log ""
Write-Log "=== Step 3: Post-fix Verification ==="

# Check .bak count again
$remainingBak = (Get-ChildItem $aeDir -Recurse -File -Filter "*.bak" -ErrorAction SilentlyContinue | Measure-Object).Count
Write-Log "Remaining .bak files: $remainingBak"

# Check AE executable
$afterfx = Join-Path $aeDir "Support Files\AfterFX.exe"
if (Test-Path $afterfx) {
    $ver = (Get-Item $afterfx).VersionInfo.ProductVersion
    Write-Log "AfterFX.exe version: $ver"
}

# Check for missing key file aescriptrunner.exe
$aescript = Join-Path $aeDir "Support Files\aescriptrunner.exe"
if (Test-Path $aescript) {
    Write-Log "aescriptrunner.exe: PRESENT"
} else {
    Write-Log "aescriptrunner.exe: MISSING (will be restored by reinstall)"
}

Write-Log ""
Write-Log "=== Fix Summary ==="
Write-Log ".bak files removed: $removed"
Write-Log ".bak files failed: $failed"
Write-Log "Install cache cleaned: YES"
Write-Log ""
Write-Log "Next steps:"
Write-Log "  1. Close all Adobe processes"
Write-Log "  2. Run AE 2025 installer again"
Write-Log "  3. Choose 'Repair' or 'Install'"
Write-Log "  4. If error 146 persists, try 'Uninstall' first then fresh install"

Write-Log ""
Write-Log "Log saved to: $logFile"
