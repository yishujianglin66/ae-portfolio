# Complete Installation Script - Install ALL software to D drive
# Run: powershell -ExecutionPolicy Bypass -File full_install.ps1

$ErrorActionPreference = "Stop"

$SourceDir = "D:\迅雷云盘"
$InstallRoot = "D:\app"

# Adobe install locations
$AdobeDir = "$InstallRoot\Adobe"
$AEScriptsDir = "$InstallRoot\AE-Scripts"

# AE ScriptUI/CEP paths
$CEPDir = "C:\Program Files (x86)\Common Files\Adobe\CEP\extensions"
$AE2026Scripts = "C:\Program Files\Adobe\Adobe After Effects 2026\Support Files\Scripts"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  COMPLETE INSTALLATION TO D DRIVE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# =========================================
# Step 1: Create directory structure
# =========================================
Write-Host "[1/10] Creating directory structure..." -ForegroundColor Yellow
$dirs = @(
    "$InstallRoot",
    "$AdobeDir",
    "$AEScriptsDir",
    "$AEScriptsDir\BeatEdit",
    "$AEScriptsDir\Motion Tools Pro",
    "$AEScriptsDir\MotionSpice",
    "$AEScriptsDir\Motion Studio",
    "$AEScriptsDir\ScriptUI Panels",
    "$InstallRoot\DaVinci Resolve"
)
foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "  Created: $dir" -ForegroundColor Green
    }
}
Write-Host "  Done!" -ForegroundColor Green
Write-Host ""

# =========================================
# Step 2: Install BeatEdit AE (CEP extension)
# =========================================
Write-Host "[2/10] Installing BeatEdit AE..." -ForegroundColor Yellow
$beatAeDir = "$AEScriptsDir\BeatEdit\beatedit_Ae_2_2_005"
if (Test-Path $beatAeDir) {
    $linkPath = "$CEPDir\beatedit_Ae_2_2_005"
    if (Test-Path $linkPath) { Remove-Item $linkPath -Recurse -Force }
    cmd /c "mklink /J `"$linkPath`" `"$beatAeDir`"" | Out-Null
    Write-Host "  CEP link created: $linkPath" -ForegroundColor Green
    
    $regFile = Get-ChildItem "$AEScriptsDir\BeatEdit\卡点脚本汉化AE版 BeatEdit V2.2.005" -Filter "*.reg" | Select-Object -First 1
    if ($regFile) {
        reg import $regFile.FullName | Out-Null
        Write-Host "  Registry imported" -ForegroundColor Green
    }
} else {
    Write-Host "  BeatEdit AE directory not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Step 3: Install Motion Tools Pro
# =========================================
Write-Host "[3/10] Installing Motion Tools Pro..." -ForegroundColor Yellow
$mtpSrc = Get-ChildItem $SourceDir -Directory | Where-Object { $_.Name -like "*Motion Tools Pro*" } | Select-Object -First 1
if ($mtpSrc) {
    $mtpInner = Get-ChildItem $mtpSrc.FullName -Directory | Select-Object -First 1
    if ($mtpInner) {
        Get-ChildItem $mtpInner.FullName | ForEach-Object {
            $dest = "$AEScriptsDir\Motion Tools Pro\$($_.Name)"
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
            Move-Item $_.FullName -Destination "$AEScriptsDir\Motion Tools Pro\" -Force
        }
        Write-Host "  Installed to: $AEScriptsDir\Motion Tools Pro" -ForegroundColor Green
    }
} else {
    Write-Host "  Motion Tools Pro not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Step 4: Install MotionSpice
# =========================================
Write-Host "[4/10] Installing MotionSpice..." -ForegroundColor Yellow
$msSrc = Get-ChildItem $SourceDir -Directory | Where-Object { $_.Name -like "*MotionSpice*" } | Select-Object -First 1
if (-not $msSrc) {
    $msSrc = Get-ChildItem $SourceDir -Directory | Where-Object { $_.Name -like "*MG*" -and $_.Name -notlike "*Motion*" -and $_.Name -notlike "*BeatEdit*" } | Select-Object -First 1
}
if ($msSrc) {
    $msInner = Get-ChildItem $msSrc.FullName -Directory | Select-Object -First 1
    if ($msInner) {
        Get-ChildItem $msInner.FullName | ForEach-Object {
            $dest = "$AEScriptsDir\MotionSpice\$($_.Name)"
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
            Move-Item $_.FullName -Destination "$AEScriptsDir\MotionSpice\" -Force
        }
        Write-Host "  Installed to: $AEScriptsDir\MotionSpice" -ForegroundColor Green
    }
} else {
    Write-Host "  MotionSpice not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Step 5: Install Motion Studio
# =========================================
Write-Host "[5/10] Installing Motion Studio..." -ForegroundColor Yellow
$mstSrc = Get-ChildItem $SourceDir -Directory | Where-Object { $_.Name -like "*Motion Studio*" } | Select-Object -First 1
if ($mstSrc) {
    $mstInner = Get-ChildItem $mstSrc.FullName -Directory | Select-Object -First 1
    if ($mstInner) {
        Get-ChildItem $mstInner.FullName | ForEach-Object {
            $dest = "$AEScriptsDir\Motion Studio\$($_.Name)"
            if (Test-Path $dest) { Remove-Item $dest -Recurse -Force }
            Move-Item $_.FullName -Destination "$AEScriptsDir\Motion Studio\" -Force
        }
        Write-Host "  Installed to: $AEScriptsDir\Motion Studio" -ForegroundColor Green
    }
} else {
    Write-Host "  Motion Studio not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Step 6: Install Adobe Photoshop 2026
# =========================================
Write-Host "[6/10] Installing Adobe Photoshop 2026..." -ForegroundColor Yellow
$psSetup = Get-ChildItem $SourceDir -Recurse -Filter "Set-up.exe" | Where-Object { $_.FullName -like "*Photoshop*" } | Select-Object -First 1
if ($psSetup) {
    Write-Host "  Launching installer..." -ForegroundColor White
    $proc = Start-Process -FilePath $psSetup.FullName -ArgumentList "--installPath=`"$AdobeDir\Adobe Photoshop 2026`"" -PassThru -Wait
    if ($proc.ExitCode -eq 0) {
        Write-Host "  Photoshop 2026 installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "  Photoshop installation failed (code: $($proc.ExitCode))" -ForegroundColor Red
    }
} else {
    Write-Host "  Photoshop setup not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Step 7: Install Adobe Premiere Pro 2026
# =========================================
Write-Host "[7/10] Installing Adobe Premiere Pro 2026..." -ForegroundColor Yellow
$prSetup = Get-ChildItem $SourceDir -Recurse -Filter "Set-up.exe" | Where-Object { $_.FullName -like "*Premiere*" } | Select-Object -First 1
if ($prSetup) {
    Write-Host "  Launching installer..." -ForegroundColor White
    $proc = Start-Process -FilePath $prSetup.FullName -ArgumentList "--installPath=`"$AdobeDir\Adobe Premiere Pro 2026`"" -PassThru -Wait
    if ($proc.ExitCode -eq 0) {
        Write-Host "  Premiere Pro 2026 installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "  Premiere Pro installation failed (code: $($proc.ExitCode))" -ForegroundColor Red
    }
} else {
    Write-Host "  Premiere Pro setup not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Step 8: Install Adobe Illustrator 2026
# =========================================
Write-Host "[8/10] Installing Adobe Illustrator 2026..." -ForegroundColor Yellow
$aiSetup = Get-ChildItem $SourceDir -Recurse -Filter "Set-up.exe" | Where-Object { $_.FullName -like "*Illustrator*" } | Select-Object -First 1
if ($aiSetup) {
    Write-Host "  Launching installer..." -ForegroundColor White
    $proc = Start-Process -FilePath $aiSetup.FullName -ArgumentList "--installPath=`"$AdobeDir\Adobe Illustrator 2026`"" -PassThru -Wait
    if ($proc.ExitCode -eq 0) {
        Write-Host "  Illustrator 2026 installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "  Illustrator installation failed (code: $($proc.ExitCode))" -ForegroundColor Red
    }
} else {
    Write-Host "  Illustrator setup not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Step 9: Install Adobe Media Encoder 2026
# =========================================
Write-Host "[9/10] Installing Adobe Media Encoder 2026..." -ForegroundColor Yellow
$meSetup = Get-ChildItem $SourceDir -Recurse -Filter "Set-up.exe" | Where-Object { $_.FullName -like "*Media Encoder*" } | Select-Object -First 1
if ($meSetup) {
    Write-Host "  Launching installer..." -ForegroundColor White
    $proc = Start-Process -FilePath $meSetup.FullName -ArgumentList "--installPath=`"$AdobeDir\Adobe Media Encoder 2026`"" -PassThru -Wait
    if ($proc.ExitCode -eq 0) {
        Write-Host "  Media Encoder 2026 installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "  Media Encoder installation failed (code: $($proc.ExitCode))" -ForegroundColor Red
    }
} else {
    Write-Host "  Media Encoder setup not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Step 10: Install DaVinci Resolve Studio 21.0
# =========================================
Write-Host "[10/10] Installing DaVinci Resolve Studio 21.0..." -ForegroundColor Yellow
$drSetup = Get-ChildItem $SourceDir -Recurse -Filter "Install Resolve*.exe" | Select-Object -First 1
if ($drSetup) {
    Write-Host "  Launching installer..." -ForegroundColor White
    $proc = Start-Process -FilePath $drSetup.FullName -ArgumentList "/VERYSILENT /DIR=`"$InstallRoot\DaVinci Resolve`"" -PassThru -Wait
    if ($proc.ExitCode -eq 0) {
        Write-Host "  DaVinci Resolve installed successfully!" -ForegroundColor Green
    } else {
        Write-Host "  DaVinci Resolve installation failed (code: $($proc.ExitCode))" -ForegroundColor Red
    }
    
    # Install unlock tools
    $drUnlock = Get-ChildItem $SourceDir -Recurse -Directory | Where-Object { $_.Name -like "*解锁工具*" } | Select-Object -First 1
    if ($drUnlock) {
        Get-ChildItem $drUnlock.FullName | ForEach-Object {
            Copy-Item $_.FullName -Destination "$InstallRoot\DaVinci Resolve\" -Force
        }
        Write-Host "  Unlock tools copied" -ForegroundColor Green
    }
} else {
    Write-Host "  DaVinci Resolve setup not found" -ForegroundColor Red
}
Write-Host ""

# =========================================
# Final setup: ScriptUI links and PlayerDebugMode
# =========================================
Write-Host "[FINAL] Configuring AE script links..." -ForegroundColor Yellow

# Create symlink for ScriptUI Panels
$scriptUILink = "$AE2026Scripts\ScriptUI Panels\CustomScripts"
if (-not (Test-Path $scriptUILink)) {
    cmd /c "mklink /J `"$scriptUILink`" `"$AEScriptsDir\ScriptUI Panels`"" | Out-Null
    Write-Host "  ScriptUI link: $scriptUILink" -ForegroundColor Green
}

# Copy JSX files
$jsxDirs = @("$AEScriptsDir\Motion Tools Pro", "$AEScriptsDir\MotionSpice", "$AEScriptsDir\Motion Studio")
$jsxCount = 0
foreach ($dir in $jsxDirs) {
    if (Test-Path $dir) {
        Get-ChildItem $dir -Filter "*.jsx" -Recurse | ForEach-Object {
            $destPath = "$AEScriptsDir\ScriptUI Panels\$($_.Name)"
            if (-not (Test-Path $destPath)) {
                Copy-Item $_.FullName -Destination $destPath -Force
                $jsxCount++
            }
        }
    }
}
Write-Host "  Copied $jsxCount JSX files to ScriptUI Panels" -ForegroundColor Green

# Set PlayerDebugMode registry
reg add "HKCU\Software\Adobe\CSXS.12" /v "PlayerDebugMode" /t REG_SZ /d "1" /f | Out-Null
reg add "HKCU\Software\Adobe\CSXS.13" /v "PlayerDebugMode" /t REG_SZ /d "1" /f | Out-Null
reg add "HKCU\Software\Adobe\CSXS.14" /v "PlayerDebugMode" /t REG_SZ /d "1" /f | Out-Null
Write-Host "  PlayerDebugMode set for CEP extensions" -ForegroundColor Green
Write-Host ""

# =========================================
# Summary
# =========================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  INSTALLATION COMPLETE!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Installation Directory: $InstallRoot" -ForegroundColor White
Write-Host ""
Write-Host "Installed Software:" -ForegroundColor Yellow

# List AE scripts
Write-Host "[AE Scripts]" -ForegroundColor White
Get-ChildItem $AEScriptsDir -Directory | Where-Object { $_.Name -notlike "_temp_*" } | ForEach-Object {
    $count = (Get-ChildItem $_.FullName -Recurse -File | Measure-Object).Count
    Write-Host "  - $($_.Name): $count files" -ForegroundColor White
}

# List Adobe apps
Write-Host "[Adobe Apps]" -ForegroundColor White
Get-ChildItem $AdobeDir -Directory | ForEach-Object {
    Write-Host "  - $($_.Name)" -ForegroundColor White
}

# List DaVinci Resolve
if (Test-Path "$InstallRoot\DaVinci Resolve") {
    Write-Host "[DaVinci Resolve]" -ForegroundColor White
    Write-Host "  - DaVinci Resolve Studio 21.0" -ForegroundColor White
}

Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Open AE -> Window -> Extensions -> BeatEdit" -ForegroundColor White
Write-Host "  2. Enable Edit -> Preferences -> Scripting & Expressions" -ForegroundColor White
Write-Host "     -> Allow Scripts to Write Files and Access Network" -ForegroundColor White
Write-Host "  3. Run unlock tools for DaVinci Resolve" -ForegroundColor White
Write-Host ""
