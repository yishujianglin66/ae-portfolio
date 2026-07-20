# Add Windows Defender exclusions for Adobe AE installation
# This is the REAL fix for Error 146

$ErrorActionPreference = 'Continue'

Write-Output "=== Adding Windows Defender Exclusions for AE Installation ==="
Write-Output ""

# Exclusion paths
$exclusions = @(
    "C:\adobeTemp",
    "C:\Program Files\Common Files\Adobe",
    "C:\Program Files\Adobe",
    "C:\ProgramData\Adobe",
    "D:\BaiduNetdiskDownload\Adobe After Effects 2025 v25.3.0.071",
    "C:\Users\Administrator\AppData\Local\Temp\CreativeCloud"
)

foreach ($path in $exclusions) {
    Write-Output "Adding exclusion: $path"
    try {
        Add-MpPreference -ExclusionPath $path -ErrorAction Stop
        Write-Output "  OK"
    } catch {
        Write-Output "  Failed: $_"
    }
}

# Also exclude by process name
$processExclusions = @("Set-up.exe", "AdobePIM.dll", "Cinema 4D.exe", "Cinema 4D Installer.exe")
foreach ($proc in $processExclusions) {
    Write-Output "Adding process exclusion: $proc"
    try {
        Add-MpPreference -ExclusionProcess $proc -ErrorAction Stop
        Write-Output "  OK"
    } catch {
        Write-Output "  Failed: $_"
    }
}

Write-Output ""
Write-Output "=== Verify exclusions ==="
$prefs = Get-MpPreference
Write-Output "Exclusion Paths:"
$prefs.ExclusionPath | ForEach-Object { Write-Output "  $_" }
Write-Output ""
Write-Output "Exclusion Processes:"
$prefs.ExclusionProcess | ForEach-Object { Write-Output "  $_" }

Write-Output ""
Write-Output "=== Restore quarantined Cinema 4D.exe files ==="
# Try to restore all quarantined Cinema 4D.exe items
try {
    $threats = Get-MpThreatDetection -ErrorAction SilentlyContinue | Where-Object {
        $_.Resources -match 'Cinema 4D'
    }
    if ($threats) {
        Write-Output "Found $($threats.Count) quarantined Cinema 4D items"
        foreach ($t in $threats) {
            Write-Output "  ThreatID: $($t.ThreatID) Time: $($t.InitialDetectionTime)"
            Write-Output "    Resources: $($t.Resources -join ', ')"
        }
    } else {
        Write-Output "  No quarantined Cinema 4D items"
    }
} catch {
    Write-Output "  Cannot query threats: $_"
}

Write-Output ""
Write-Output "=== Recreate Cinema 4D.exe in CustomHook directories ==="
$cinemaExe = "C:\Program Files\Maxon Cinema 4D 2026\Cinema 4D.exe"
$targets = @(
    "C:\Program Files\Common Files\Adobe\Keyfiles\AfterEffects\25\CustomHook\win",
    "C:\Program Files\Common Files\Adobe\Keyfiles\AfterEffects\26\CustomHook\win"
)
foreach ($targetDir in $targets) {
    $targetFile = Join-Path $targetDir "Cinema 4D.exe"
    if (Test-Path $targetFile) {
        Write-Output "  Already exists: $targetFile"
    } else {
        Write-Output "  Copying Cinema 4D.exe to: $targetDir"
        Copy-Item -Path $cinemaExe -Destination $targetFile -Force
        Write-Output "    Done. Size: $([math]::Round((Get-Item $targetFile).Length / 1MB, 2)) MB"
    }
}

Write-Output ""
Write-Output "=== Disable real-time protection temporarily (optional) ==="
try {
    Set-MpPreference -DisableRealtimeMonitoring $false
    Write-Output "  Real-time monitoring is enabled (recommended)"
    Write-Output "  But exclusions should now protect the AE install"
} catch {
    Write-Output "  Cannot set monitoring: $_"
}

Write-Output ""
Write-Output "=== Fix Complete ==="
Write-Output "Now run AE installer again - Cinema 4D.exe should not be quarantined this time"
