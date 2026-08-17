# Verify key Adobe install paths based on first scan
$ErrorActionPreference = "SilentlyContinue"

Write-Host "========== Verifying Key Adobe Paths =========="

$paths = @(
    "D:\Me",
    "D:\Me\Adobe Media Encoder 2025",
    "D:\Me\Adobe Media Encoder 2025\Adobe Media Encoder.exe",
    "D:\Me\Adobe Media Encoder 2026",
    "D:\Me\Adobe Media Encoder 2026\Adobe Media Encoder.exe",
    "D:\Au",
    "D:\Au\Adobe Audition 2025",
    "D:\Au\Adobe Audition 2025\Adobe Audition.exe",
    "D:\Au\Adobe Audition 2026",
    "D:\Au\Adobe Audition 2026\Adobe Audition.exe",
    "D:\Brige\Adobe Bridge 2025",
    "D:\Brige\Adobe Bridge 2025\Adobe Bridge.exe",
    "D:\Ai25\Adobe Illustrator 2025",
    "D:\Ai\Adobe Illustrator 2026",
    "D:\Lr",
    "D:\An24\Adobe Animate 2024",
    "D:\Blender\Blender 5.1.0\blender.exe",
    "D:\top\Topaz Video AI Pro",
    "D:\top\Topaz Video AI Pro\Topaz Video AI BETA.exe",
    "C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe",
    "C:\Program Files\BorisFX\ContinuumAE",
    "C:\Program Files\BorisFX\Sapphire 2025 Adobe",
    "C:\Program Files\Maxon Cinema 4D 2025\Cinema 4D.exe",
    "C:\Program Files\Maxon Cinema 4D 2025\c4dpy.exe",
    "C:\Program Files\Maxon Cinema 4D 2026\Cinema 4D.exe",
    "C:\Program Files\Maxon Cinema 4D 2026\c4dpy.exe",
    "C:\Program Files\REVisionEffects\REFlex5AE",
    "D:\DaVinci Resolve\Resolve.exe",
    "C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore",
    "C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore\Boris FX MochaPro2025.5"
)

foreach ($p in $paths) {
    if (Test-Path $p) {
        $item = Get-Item $p
        if ($item.PSIsContainer) {
            $count = (Get-ChildItem $p | Measure-Object).Count
            Write-Host "[EXISTS-DIR] $p ($count items)" -ForegroundColor Green
            # Show top 8 items
            Get-ChildItem $p | Select-Object -First 8 | ForEach-Object {
                Write-Host "    - $($_.Name)"
            }
        } else {
            $ver = $item.VersionInfo.ProductVersion
            $size = [math]::Round($item.Length / 1MB, 1)
            Write-Host "[EXISTS-EXE] $p (Version: $ver, Size: $size MB)" -ForegroundColor Cyan
        }
    } else {
        Write-Host "[MISSING]    $p" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "========== Probing AME / Audition CLI =========="

# Test AME CLI
$ameExe = "D:\Me\Adobe Media Encoder 2025\Adobe Media Encoder.exe"
if (Test-Path $ameExe) {
    Write-Host "AME 2025 FOUND at: $ameExe" -ForegroundColor Green
    $ameDir = Split-Path $ameExe
    Get-ChildItem $ameDir -Filter "*.exe" | ForEach-Object {
        Write-Host "    Exe: $($_.Name) - $($_.VersionInfo.ProductVersion)"
    }
}

# Test Audition CLI
$auExe = "D:\Au\Adobe Audition 2025\Adobe Audition.exe"
if (Test-Path $auExe) {
    Write-Host "Audition 2025 FOUND at: $auExe" -ForegroundColor Green
    $auDir = Split-Path $auExe
    Get-ChildItem $auDir -Filter "*.exe" | ForEach-Object {
        Write-Host "    Exe: $($_.Name) - $($_.VersionInfo.ProductVersion)"
    }
}

# Test Blender CLI
$blenderExe = "D:\Blender\Blender 5.1.0\blender.exe"
if (Test-Path $blenderExe) {
    Write-Host "Blender FOUND at: $blenderExe" -ForegroundColor Green
    $blenderVer = & $blenderExe --version 2>&1 | Select-Object -First 2
    Write-Host "    Version: $blenderVer"
}

# Test Topaz CLI
$topazExe = "D:\top\Topaz Video AI Pro\Topaz Video AI BETA.exe"
if (Test-Path $topazExe) {
    Write-Host "Topaz Video AI Pro FOUND at: $topazExe" -ForegroundColor Green
    # Check for CLI variant
    $topazDir = Split-Path $topazExe
    Get-ChildItem $topazDir -Filter "*.exe" | ForEach-Object {
        Write-Host "    Exe: $($_.Name)"
    }
}

# Test Silhouette CLI
$silExe = "C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe"
if (Test-Path $silExe) {
    Write-Host "Silhouette 2026 FOUND at: $silExe" -ForegroundColor Green
    $silDir = Split-Path $silExe
    Get-ChildItem $silDir -Filter "*.exe" | ForEach-Object {
        Write-Host "    Exe: $($_.Name)"
    }
}

Write-Host ""
Write-Host "========== Probing C4D Python API =========="
$c4dPy = "C:\Program Files\Maxon Cinema 4D 2025\c4dpy.exe"
if (Test-Path $c4dPy) {
    Write-Host "C4D Python 2025 FOUND at: $c4dPy" -ForegroundColor Green
    $c4dVer = & $c4dPy --version 2>&1 | Select-Object -First 1
    Write-Host "    Python version: $c4dVer"
}

Write-Host ""
Write-Host "========== Summary =========="

$summary = @()
$summary += [PSCustomObject]@{ Software="After Effects 2025"; Path="C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"; Version="25.3"; CLI="aerender.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="Photoshop 2025"; Path="D:\ps\Adobe Photoshop 2025\Photoshop.exe"; Version="26.8"; CLI="Photoshop.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="Premiere Pro 2025"; Path="D:\Pr25\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe"; Version="25.3.0"; CLI="Adobe Premiere Pro.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="DaVinci Resolve"; Path="D:\DaVinci Resolve\Resolve.exe"; Version="21.0.0.20"; CLI="resolve.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="Blender 5.1"; Path="D:\Blender\Blender 5.1.0\blender.exe"; Version="5.1"; CLI="blender.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="Topaz Video AI Pro"; Path="D:\top\Topaz Video AI Pro\Topaz Video AI BETA.exe"; Version="7.2.0.0"; CLI="ffmpeg.exe (internal)"; Available=$true }
$summary += [PSCustomObject]@{ Software="Silhouette 2026"; Path="C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe"; Version="2021.5.0.0"; CLI="Silhouette.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="Cinema 4D 2025"; Path="C:\Program Files\Maxon Cinema 4D 2025\"; Version="2025.2.0"; CLI="c4dpy.exe / Commandline.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="Cinema 4D 2026"; Path="C:\Program Files\Maxon Cinema 4D 2026\"; Version="2026.2.0"; CLI="c4dpy.exe / Commandline.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="FFmpeg (gyan build)"; Path="C:\ffmpeg\bin\ffmpeg.exe"; Version="8.1.1-essentials"; CLI="ffmpeg.exe"; Available=$true }
$summary += [PSCustomObject]@{ Software="FFmpeg (alternate)"; Path="C:\Program Files\ffmpeg\bin\ffmpeg.exe"; Version="4.0.2"; CLI="ffkroma.exe"; Available=$true }

# Verify Media Encoder
$amePath = "D:\Me\Adobe Media Encoder 2025\Adobe Media Encoder.exe"
if (Test-Path $amePath) {
    $summary += [PSCustomObject]@{ Software="Media Encoder 2025"; Path=$amePath; Version="25.3"; CLI="Adobe Media Encoder.exe"; Available=$true }
} else {
    $summary += [PSCustomObject]@{ Software="Media Encoder 2025"; Path="(missing)"; Version="-"; CLI="-"; Available=$false }
}

# Verify Audition
$auPath = "D:\Au\Adobe Audition 2025\Adobe Audition.exe"
if (Test-Path $auPath) {
    $summary += [PSCustomObject]@{ Software="Audition 2025"; Path=$auPath; Version="25.3"; CLI="Adobe Audition.exe"; Available=$true }
} else {
    $summary += [PSCustomObject]@{ Software="Audition 2025"; Path="(missing)"; Version="-"; CLI="-"; Available=$false }
}

$summary | Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "========== Engine Mapping Summary =========="
Write-Host "✅ Engines to ACTIVATE (10 engines):"
Write-Host "    1. AE Engine (After Effects 2025 @ C:\Program Files\Adobe\Adobe After Effects 2025)"
Write-Host "    2. PS Engine (Photoshop 2025 @ D:\ps\Adobe Photoshop 2025)"
Write-Host "    3. PR Engine (Premiere Pro 2025 @ D:\Pr25\Adobe Premiere Pro 2025)"
Write-Host "    4. DaVinci Engine (Resolve 21 @ D:\DaVinci Resolve)"
Write-Host "    5. Blender Engine (Blender 5.1 @ D:\Blender\Blender 5.1.0)"
Write-Host "    6. Topaz Engine (Topaz Video AI Pro 7.2 @ D:\top\Topaz Video AI Pro)"
Write-Host "    7. Silhouette Engine (Silhouette 2026 @ C:\Program Files\BorisFX\Silhouette 2026.0)"
Write-Host "    8. Cinema4D Engine (C4D 2026 @ C:\Program Files\Maxon Cinema 4D 2026 + c4dpy)"
Write-Host "    9. FFmpeg Engine (8.1.1 @ C:\ffmpeg\bin)"
Write-Host "   10. Audition Engine (Audition 2025 @ D:\Au\Adobe Audition 2025)"
Write-Host ""
Write-Host "⚠️ User Excluded: AME (Media Encoder 2025/2026) - User said '除ame之外都已安装'"
Write-Host "    Even though AME IS installed at D:\Me, user does NOT want to use it"
Write-Host "    => PR export_final will need alternative: PR direct export via H.264 or FFmpeg concat"
