# AE Scripts Installer - Install to D drive
# Usage: powershell -ExecutionPolicy Bypass -File install_ae_scripts.ps1

$ErrorActionPreference = "Stop"

$SourceDir = "D:\迅雷云盘"
$InstallRoot = "D:\app\AE-Scripts"
$CEPDir = "C:\Program Files (x86)\Common Files\Adobe\CEP\extensions"
$AEScriptsDir = "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Scripts"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AE Scripts Installer - D Drive" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Find zip files by pattern
Write-Host "Scanning for zip files in $SourceDir ..." -ForegroundColor Yellow
$allZips = Get-ChildItem $SourceDir -Filter "*.zip" | Select-Object Name, FullName
Write-Host "  Found $($allZips.Count) zip files" -ForegroundColor Green
Write-Host ""

# Identify each zip
$beatEditZip = $allZips | Where-Object { $_.Name -like "*BeatEdit*" -and $_.Name -like "*AE*" } | Select-Object -First 1
$beatEditPRZip = $allZips | Where-Object { $_.Name -like "*BeatEdit*" -and $_.Name -like "*PR*" } | Select-Object -First 1
$motionToolsZip = $allZips | Where-Object { $_.Name -like "*Motion Tools*" } | Select-Object -First 1
$motionSpiceZip = $allZips | Where-Object { $_.Name -like "*MotionSpice*" -or $_.Name -like "*graphic*" -or ($_.Name -like "*MG*" -and $_.Name -like "*preset*") } | Select-Object -First 1
$motionStudioZip = $allZips | Where-Object { $_.Name -like "*Motion Studio*" } | Select-Object -First 1

if (-not $motionSpiceZip) {
    $motionSpiceZip = $allZips | Where-Object { $_.Name -like "*MG*" -and $_.Name -notlike "*Motion*" -and $_.Name -notlike "*BeatEdit*" } | Select-Object -First 1
}

Write-Host "Identified packages:" -ForegroundColor Yellow
if ($beatEditZip) { Write-Host "  BeatEdit AE: $($beatEditZip.Name)" -ForegroundColor White }
if ($motionToolsZip) { Write-Host "  Motion Tools Pro: $($motionToolsZip.Name)" -ForegroundColor White }
if ($motionSpiceZip) { Write-Host "  MotionSpice: $($motionSpiceZip.Name)" -ForegroundColor White }
if ($motionStudioZip) { Write-Host "  Motion Studio: $($motionStudioZip.Name)" -ForegroundColor White }
Write-Host ""

# Step 1: Create directories
Write-Host "[1/6] Creating directories..." -ForegroundColor Yellow
$dirs = @(
    "$InstallRoot\BeatEdit",
    "$InstallRoot\Motion Tools Pro",
    "$InstallRoot\MotionSpice",
    "$InstallRoot\Motion Studio",
    "$InstallRoot\ScriptUI Panels"
)
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Green
    }
}
Write-Host "  Done!" -ForegroundColor Green
Write-Host ""

# Step 2: Install BeatEdit AE (CEP extension)
Write-Host "[2/6] Installing BeatEdit AE..." -ForegroundColor Yellow
if ($beatEditZip) {
    $beatTemp = "$InstallRoot\_temp_beatedit"
    if (Test-Path $beatTemp) { Remove-Item $beatTemp -Recurse -Force }
    Expand-Archive -Path $beatEditZip.FullName -DestinationPath $beatTemp -Force
    $innerDir = Get-ChildItem $beatTemp -Directory | Select-Object -First 1
    $extDir = Get-ChildItem "$($innerDir.FullName)" -Directory -Filter "beatedit_*" | Select-Object -First 1
    if ($extDir) {
        $dest = "$InstallRoot\BeatEdit\$($extDir.Name)"
        if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
        Move-Item -Path $extDir.FullName -Destination "$InstallRoot\BeatEdit\" -Force
        Write-Host "  Ext dir: $($extDir.Name)" -ForegroundColor Green
        
        # Create symlink to CEP extensions dir
        $linkPath = "$CEPDir\$($extDir.Name)"
        if (Test-Path $linkPath) { Remove-Item $linkPath -Recurse -Force }
        New-Item -ItemType SymbolicLink -Path $linkPath -Target "$InstallRoot\BeatEdit\$($extDir.Name)" -Force | Out-Null
        Write-Host "  CEP link: $linkPath" -ForegroundColor Green
        
        # Import registry (PlayerDebugMode)
        $regFile = Get-ChildItem "$($innerDir.FullName)" -Filter "*.reg" | Select-Object -First 1
        if ($regFile) {
            reg import $($regFile.FullName) | Out-Null
            Write-Host "  Registry imported" -ForegroundColor Green
        }
    }
    Remove-Item $beatTemp -Recurse -Force
    Write-Host "  BeatEdit installed!" -ForegroundColor Green
} else {
    Write-Host "  BeatEdit zip not found, skipped" -ForegroundColor Red
}
Write-Host ""

# Step 3: Install Motion Tools Pro
Write-Host "[3/6] Installing Motion Tools Pro..." -ForegroundColor Yellow
if ($motionToolsZip) {
    $mtpTemp = "$InstallRoot\_temp_mtp"
    if (Test-Path $mtpTemp) { Remove-Item $mtpTemp -Recurse -Force }
    Expand-Archive -Path $motionToolsZip.FullName -DestinationPath $mtpTemp -Force
    $innerDir = Get-ChildItem $mtpTemp -Directory | Select-Object -First 1
    if ($innerDir) {
        $dest = "$InstallRoot\Motion Tools Pro"
        if ((Get-ChildItem $dest).Count -gt 0) {
            Get-ChildItem $dest | Remove-Item -Recurse -Force
        }
        Get-ChildItem "$($innerDir.FullName)" | ForEach-Object {
            Move-Item -Path $_.FullName -Destination "$dest\" -Force
        }
        Write-Host "  Installed to: $dest" -ForegroundColor Green
    }
    Remove-Item $mtpTemp -Recurse -Force
    Write-Host "  Motion Tools Pro installed!" -ForegroundColor Green
} else {
    Write-Host "  Motion Tools Pro zip not found, skipped" -ForegroundColor Red
}
Write-Host ""

# Step 4: Install MotionSpice
Write-Host "[4/6] Installing MotionSpice..." -ForegroundColor Yellow
if ($motionSpiceZip) {
    $msTemp = "$InstallRoot\_temp_ms"
    if (Test-Path $msTemp) { Remove-Item $msTemp -Recurse -Force }
    Expand-Archive -Path $motionSpiceZip.FullName -DestinationPath $msTemp -Force
    $innerDir = Get-ChildItem $msTemp -Directory | Select-Object -First 1
    if ($innerDir) {
        $dest = "$InstallRoot\MotionSpice"
        if ((Get-ChildItem $dest).Count -gt 0) {
            Get-ChildItem $dest | Remove-Item -Recurse -Force
        }
        Get-ChildItem "$($innerDir.FullName)" | ForEach-Object {
            Move-Item -Path $_.FullName -Destination "$dest\" -Force
        }
        Write-Host "  Installed to: $dest" -ForegroundColor Green
    }
    Remove-Item $msTemp -Recurse -Force
    Write-Host "  MotionSpice installed!" -ForegroundColor Green
} else {
    Write-Host "  MotionSpice zip not found, skipped" -ForegroundColor Red
}
Write-Host ""

# Step 5: Install Motion Studio
Write-Host "[5/6] Installing Motion Studio..." -ForegroundColor Yellow
if ($motionStudioZip) {
    $mstTemp = "$InstallRoot\_temp_mst"
    if (Test-Path $mstTemp) { Remove-Item $mstTemp -Recurse -Force }
    Expand-Archive -Path $motionStudioZip.FullName -DestinationPath $mstTemp -Force
    $innerDir = Get-ChildItem $mstTemp -Directory | Select-Object -First 1
    if ($innerDir) {
        $dest = "$InstallRoot\Motion Studio"
        if ((Get-ChildItem $dest).Count -gt 0) {
            Get-ChildItem $dest | Remove-Item -Recurse -Force
        }
        Get-ChildItem "$($innerDir.FullName)" | ForEach-Object {
            Move-Item -Path $_.FullName -Destination "$dest\" -Force
        }
        Write-Host "  Installed to: $dest" -ForegroundColor Green
    }
    Remove-Item $mstTemp -Recurse -Force
    Write-Host "  Motion Studio installed!" -ForegroundColor Green
} else {
    Write-Host "  Motion Studio zip not found, skipped" -ForegroundColor Red
}
Write-Host ""

# Step 6: Setup AE script links
Write-Host "[6/6] Configuring AE script links..." -ForegroundColor Yellow

# Create symlink for ScriptUI Panels
$scriptUILink = "$AEScriptsDir\ScriptUI Panels\CustomScripts"
if (-not (Test-Path $scriptUILink)) {
    New-Item -ItemType SymbolicLink -Path $scriptUILink -Target "$InstallRoot\ScriptUI Panels" -Force | Out-Null
    Write-Host "  ScriptUI link: $scriptUILink" -ForegroundColor Green
}

# Copy JSX files from each script to ScriptUI Panels
$jsxDirs = @(
    "$InstallRoot\Motion Tools Pro",
    "$InstallRoot\MotionSpice",
    "$InstallRoot\Motion Studio"
)
$jsxCount = 0
foreach ($dir in $jsxDirs) {
    if (Test-Path $dir) {
        Get-ChildItem $dir -Filter "*.jsx" -Recurse | ForEach-Object {
            $destPath = "$InstallRoot\ScriptUI Panels\$($_.Name)"
            if (-not (Test-Path $destPath)) {
                Copy-Item -Path $_.FullName -Destination $destPath -Force
                Write-Host "  Copied JSX: $($_.Name)" -ForegroundColor Green
                $jsxCount++
            }
        }
    }
}
if ($jsxCount -eq 0) {
    Write-Host "  No new JSX files to copy" -ForegroundColor Gray
}
Write-Host "  Script links configured!" -ForegroundColor Green
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  All installations complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Install directory: $InstallRoot" -ForegroundColor White
Write-Host ""
Write-Host "How to use:" -ForegroundColor Yellow
Write-Host "  1. BeatEdit: AE Menu -> Window -> Extensions -> BeatEdit" -ForegroundColor White
Write-Host "  2. Other scripts: AE Menu -> Window -> ScriptUI Panels -> CustomScripts" -ForegroundColor White
Write-Host "  3. Enable: Edit -> Preferences -> Scripting & Expressions" -ForegroundColor White
Write-Host "     -> Allow Scripts to Write Files and Access Network" -ForegroundColor White
Write-Host ""

# List installed files
Write-Host "Installed contents:" -ForegroundColor Yellow
Get-ChildItem $InstallRoot -Directory | Where-Object { $_.Name -notlike "_temp_*" } | ForEach-Object {
    $count = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object).Count
    Write-Host "  [$($_.Name)] - $count files" -ForegroundColor White
}
Write-Host ""
