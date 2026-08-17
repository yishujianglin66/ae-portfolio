# Deep Software Scan Script for AE Knowledge Vault
# Scans registry, Start Menu shortcuts, and common directories

$ErrorActionPreference = "SilentlyContinue"

Write-Host "============================================================"
Write-Host "AE Knowledge Vault - Deep Software Scan"
Write-Host "Date: $(Get-Date)"
Write-Host "============================================================"
Write-Host ""

# 1. Registry Scan
Write-Host "========== [1] Registry Uninstall Keys =========="
$regPaths = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
)

$regResults = @()
foreach ($rp in $regPaths) {
    $keys = Get-ChildItem $rp -ErrorAction SilentlyContinue
    foreach ($k in $keys) {
        $p = Get-ItemProperty $k.PSPath -ErrorAction SilentlyContinue
        if ($p -and $p.DisplayName) {
            $regResults += [PSCustomObject]@{
                Name = $p.DisplayName
                Version = $p.DisplayVersion
                Location = $p.InstallLocation
                Uninstall = $p.UninstallString
            }
        }
    }
}

$targetKeywords = "Adobe|Blender|Topaz|Silhouette|DaVinci|Cinema|Autodesk|FFmpeg|Maxon|Boris|Resolve|Unreal|Substance|Houdini|Cinema 4D|Media Encoder|Audition|After Effects|Photoshop|Premiere|Illustrator|Lightroom|Bridge|InDesign"
$filtered = $regResults | Where-Object { $_.Name -match $targetKeywords } | Sort-Object Name
$filtered | Format-Table Name, Version, Location -AutoSize -Wrap

Write-Host ""
Write-Host "Total matching entries: $($filtered.Count)"
Write-Host ""

# 2. Start Menu shortcuts
Write-Host "========== [2] Start Menu Shortcuts =========="
$startMenus = @(
    "C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    "$env:APPDATA\Microsoft\Windows\Start Menu\Programs"
)

$shell = New-Object -ComObject WScript.Shell
$shortcuts = @()
foreach ($sm in $startMenus) {
    $lnks = Get-ChildItem $sm -Recurse -Include *.lnk -ErrorAction SilentlyContinue
    foreach ($l in $lnks) {
        try {
            $sc = $shell.CreateShortcut($l.FullName)
            $shortcuts += [PSCustomObject]@{
                Name = $l.BaseName
                Target = $sc.TargetPath
                Args = $sc.Arguments
            }
        } catch {}
    }
}

$filteredSc = $shortcuts | Where-Object { $_.Target -match $targetKeywords } | Sort-Object Name
$filteredSc | Format-Table Name, Target -AutoSize -Wrap

Write-Host ""
Write-Host "Total matching shortcuts: $($filteredSc.Count)"
Write-Host ""

# 3. Specific path probes for known possible install locations
Write-Host "========== [3] Path Probes =========="
$probePaths = @(
    "D:\Blender",
    "D:\top",
    "D:\top\Topaz Video AI Pro",
    "C:\Program Files\BorisFX\Silhouette 2026.0",
    "D:\Au\Adobe Audition 2025",
    "C:\Program Files\Maxon Cinema 4D 2025",
    "C:\Program Files\Maxon Cinema 4D 2026",
    "D:\DaVinci Resolve",
    "C:\Program Files\Adobe",
    "D:\ps\Adobe Photoshop 2025",
    "D:\Pr25\Adobe Premiere Pro 2025",
    "C:\Program Files\Adobe\Adobe After Effects 2025",
    "C:\ffmpeg\bin",
    "C:\Program Files\ffmpeg\bin",
    "D:\Blender Foundation",
    "C:\Program Files\Blender Foundation",
    "D:\Topaz Labs",
    "C:\Program Files\Topaz Labs LLC",
    "C:\Program Files\BorisFX",
    "D:\BorisFX",
    "D:\Maxon",
    "D:\Autodesk",
    "C:\Program Files\Autodesk",
    "D:\Substance",
    "C:\Program Files\Adobe\Adobe Audition 2025",
    "C:\Program Files\Adobe\Adobe Media Encoder 2025",
    "C:\Program Files\Adobe\Adobe Media Encoder 2026",
    "D:\Adobe Media Encoder",
    "C:\Program Files (x86)\Adobe"
)

foreach ($pp in $probePaths) {
    if (Test-Path $pp) {
        Write-Host "[EXISTS] $pp" -ForegroundColor Green
        # List top-level contents
        $items = Get-ChildItem $pp -ErrorAction SilentlyContinue | Select-Object -First 5
        foreach ($i in $items) {
            Write-Host "    - $($i.Name)"
        }
    } else {
        Write-Host "[MISSING] $pp" -ForegroundColor Gray
    }
}

Write-Host ""

# 4. Find all exe files in likely Adobe/BorisFX/Topaz/Blender directories
Write-Host "========== [4] Executable Probes =========="
$exeSearchPaths = @(
    "D:\Blender",
    "D:\top\Topaz Video AI Pro",
    "C:\Program Files\BorisFX\Silhouette 2026.0",
    "D:\Au\Adobe Audition 2025",
    "D:\DaVinci Resolve",
    "C:\Program Files\Adobe",
    "D:\ps\Adobe Photoshop 2025",
    "D:\Pr25\Adobe Premiere Pro 2025",
    "C:\Program Files\Maxon Cinema 4D 2025",
    "C:\Program Files\Maxon Cinema 4D 2026",
    "D:\Maxon"
)

foreach ($sp in $exeSearchPaths) {
    if (Test-Path $sp) {
        Write-Host ""
        Write-Host ">>> Scanning $sp" -ForegroundColor Cyan
        $exes = Get-ChildItem $sp -Filter "*.exe" -Recurse -Depth 2 -ErrorAction SilentlyContinue
        $filteredExe = $exes | Where-Object {
            $_.Name -match "^(blender|topaz|silhouette|resolve|photoshop|premiere|After.Effects|audition|media.encoder|aerender|c4d|cinema|Cinema 4D|ffx)" -and
            $_.Name -notmatch "unins|setup|crash|update|helper|report"
        }
        $filteredExe | ForEach-Object {
            Write-Host "    [EXE] $($_.FullName)"
            Write-Host "          Version: $($_.VersionInfo.ProductVersion)"
        }
    }
}

Write-Host ""
Write-Host "========== [5] PATH Environment Variable =========="
$envPath = $env:PATH -split ";"
$relevantPaths = $envPath | Where-Object { $_ -match "ffmpeg|blender|topaz|silhouette|davinci|adobe|cinema|maxon|boris" }
$relevantPaths | ForEach-Object { Write-Host "    $_" }

Write-Host ""
Write-Host "========== [6] Specific Engine Checks =========="

# Check DaVinci Resolve
Write-Host ""
Write-Host "--- DaVinci Resolve ---"
$resolveExe = "D:\DaVinci Resolve\Resolve.exe"
if (Test-Path $resolveExe) {
    $ver = (Get-Item $resolveExe).VersionInfo.ProductVersion
    Write-Host "Found: $resolveExe (Version: $ver)" -ForegroundColor Green
} else {
    Write-Host "Not found at expected path"
}

# Check Topaz
Write-Host ""
Write-Host "--- Topaz Video AI Pro ---"
$topazExe = "D:\top\Topaz Video AI Pro\Topaz Video AI BETA.exe"
if (Test-Path $topazExe) {
    $ver = (Get-Item $topazExe).VersionInfo.ProductVersion
    Write-Host "Found: $topazExe (Version: $ver)" -ForegroundColor Green
    # Check for CLI
    $topazCli = Get-ChildItem "D:\top\Topaz Video AI Pro" -Filter "*.exe" -ErrorAction SilentlyContinue
    $topazCli | ForEach-Object { Write-Host "    Exe: $($_.Name)" }
}

# Check Silhouette
Write-Host ""
Write-Host "--- Silhouette 2026 ---"
$silExe = "C:\Program Files\BorisFX\Silhouette 2026.0\Silhouette.exe"
if (Test-Path $silExe) {
    $ver = (Get-Item $silExe).VersionInfo.ProductVersion
    Write-Host "Found: $silExe (Version: $ver)" -ForegroundColor Green
}

# Check Blender
Write-Host ""
Write-Host "--- Blender ---"
$blenderCandidates = @(
    "D:\Blender\blender.exe",
    "D:\Blender Foundation\blender.exe",
    "C:\Program Files\Blender Foundation\Blender\blender.exe",
    "C:\Program Files\Blender Foundation\blender.exe"
)
$blenderFound = $false
foreach ($b in $blenderCandidates) {
    if (Test-Path $b) {
        $ver = (Get-Item $b).VersionInfo.ProductVersion
        Write-Host "Found: $b (Version: $ver)" -ForegroundColor Green
        $blenderFound = $true
        break
    }
}
if (-not $blenderFound) {
    Write-Host "Searching D:\ for blender.exe..."
    $found = Get-ChildItem "D:\" -Filter "blender.exe" -Recurse -Depth 4 -ErrorAction SilentlyContinue | Select-Object -First 3
    $found | ForEach-Object { Write-Host "    Found: $($_.FullName)" -ForegroundColor Yellow }
}

# Check Audition
Write-Host ""
Write-Host "--- Adobe Audition ---"
$auExe = "D:\Au\Adobe Audition 2025\Adobe Audition.exe"
if (Test-Path $auExe) {
    $ver = (Get-Item $auExe).VersionInfo.ProductVersion
    Write-Host "Found: $auExe (Version: $ver)" -ForegroundColor Green
} else {
    Write-Host "Not found at D:\Au\Adobe Audition 2025"
    $auSearch = Get-ChildItem "D:\Au" -Filter "*.exe" -ErrorAction SilentlyContinue
    $auSearch | ForEach-Object { Write-Host "    Exe: $($_.FullName)" }
}

# Check Cinema 4D
Write-Host ""
Write-Host "--- Cinema 4D ---"
$c4dCandidates = @(
    "C:\Program Files\Maxon Cinema 4D 2025\Cinema 4D.exe",
    "C:\Program Files\Maxon Cinema 4D 2026\Cinema 4D.exe",
    "C:\Program Files\Maxon\Cinema 4D 2025\Cinema 4D.exe",
    "C:\Program Files\Maxon\Cinema 4D 2026\Cinema 4D.exe"
)
$c4dFound = $false
foreach ($c in $c4dCandidates) {
    if (Test-Path $c) {
        $ver = (Get-Item $c).VersionInfo.ProductVersion
        Write-Host "Found: $c (Version: $ver)" -ForegroundColor Green
        $c4dFound = $true
    }
}
if (-not $c4dFound) {
    Write-Host "Searching C:\Program Files\Maxon* for Cinema 4D.exe..."
    $found = Get-ChildItem "C:\Program Files" -Directory -Filter "Maxon*" -ErrorAction SilentlyContinue
    foreach ($d in $found) {
        Write-Host "Dir: $($d.FullName)"
        Get-ChildItem $d.FullName -Filter "*.exe" -Recurse -Depth 2 -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Host "    Exe: $($_.FullName)"
        }
    }
}

# Check FFmpeg
Write-Host ""
Write-Host "--- FFmpeg ---"
$ffCandidates = @(
    "C:\ffmpeg\bin\ffmpeg.exe",
    "C:\Program Files\ffmpeg\bin\ffmpeg.exe"
)
foreach ($f in $ffCandidates) {
    if (Test-Path $f) {
        Write-Host "Found: $f" -ForegroundColor Green
        $ffVer = & $f -version 2>&1 | Select-Object -First 1
        Write-Host "    Version: $ffVer"
    }
}

# Check Adobe products
Write-Host ""
Write-Host "--- Adobe Products ---"
$adobeProducts = @{
    "After Effects 2025" = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
    "Photoshop 2025" = "D:\ps\Adobe Photoshop 2025\Photoshop.exe"
    "Premiere Pro 2025" = "D:\Pr25\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe"
    "Media Encoder 2025" = "C:\Program Files\Adobe\Adobe Media Encoder 2025\Adobe Media Encoder.exe"
    "Media Encoder 2026" = "C:\Program Files\Adobe\Adobe Media Encoder 2026\Adobe Media Encoder.exe"
    "Audition 2025" = "D:\Au\Adobe Audition 2025\Adobe Audition.exe"
    "Illustrator 2025" = "C:\Program Files\Adobe\Adobe Illustrator 2025\Support Files\Contents\Windows\Illustrator.exe"
}

foreach ($name in $adobeProducts.Keys) {
    $path = $adobeProducts[$name]
    if (Test-Path $path) {
        $ver = (Get-Item $path).VersionInfo.ProductVersion
        Write-Host "[INSTALLED] $name -> $path (Version: $ver)" -ForegroundColor Green
    } else {
        Write-Host "[MISSING]   $name -> $path" -ForegroundColor Red
    }
}

# Also search for all Adobe exes
Write-Host ""
Write-Host "--- All Adobe Installations ---"
$adobeRoot = "C:\Program Files\Adobe"
if (Test-Path $adobeRoot) {
    Get-ChildItem $adobeRoot -Directory | ForEach-Object {
        Write-Host "Adobe product dir: $($_.FullName)" -ForegroundColor Cyan
    }
}

Write-Host ""
Write-Host "========== Scan Complete =========="
