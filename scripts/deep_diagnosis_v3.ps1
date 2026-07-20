# Deep diagnosis - check current state of CustomHook directory
$ErrorActionPreference = 'Continue'

Write-Output "=== Current state of AE 25 CustomHook\win ==="
$dir25 = "C:\Program Files\Common Files\Adobe\Keyfiles\AfterEffects\25\CustomHook\win"
if (Test-Path $dir25) {
    Get-ChildItem $dir25 -File -Force | ForEach-Object {
        $size = [math]::Round($_.Length / 1MB, 2)
        $attr = $_.Attributes
        Write-Output "  $($_.Name) ($size MB) Attr=$attr LastWrite=$($_.LastWriteTime)"
    }
} else {
    Write-Output "  Directory MISSING: $dir25"
}

Write-Output ""
Write-Output "=== Current state of AE 26 CustomHook\win ==="
$dir26 = "C:\Program Files\Common Files\Adobe\Keyfiles\AfterEffects\26\CustomHook\win"
if (Test-Path $dir26) {
    Get-ChildItem $dir26 -File -Force | ForEach-Object {
        $size = [math]::Round($_.Length / 1MB, 2)
        Write-Output "  $($_.Name) ($size MB) LastWrite=$($_.LastWriteTime)"
    }
} else {
    Write-Output "  Directory MISSING: $dir26"
}

Write-Output ""
Write-Output "=== Windows Defender Quarantine ==="
try {
    $q = Get-MpThreatDetection -ErrorAction SilentlyContinue | Sort-Object InitialDetectionTime -Descending | Select-Object -First 5
    if ($q) {
        $q | ForEach-Object {
            Write-Output "  Threat: $($_.ThreatID) Resources: $($_.Resources -join ',') Time: $($_.InitialDetectionTime)"
        }
    } else {
        Write-Output "  No recent threat detections"
    }
} catch {
    Write-Output "  Cannot query Defender: $_"
}

Write-Output ""
Write-Output "=== Installer package full structure ==="
$pkg = "D:\BaiduNetdiskDownload\Adobe After Effects 2025 v25.3.0.071\Adobe After Effects 2025 v25.3.0.071"
if (Test-Path $pkg) {
    Get-ChildItem $pkg -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match 'Cinema|cinema|C4D|c4d|Keyfile|CustomHook|crack|patch|amtlib|Paint|AdobePIM' -or
        $_.Extension -in '.txt','.nfo','.md','.rtf'
    } | Select-Object -First 30 | ForEach-Object {
        $rel = $_.FullName.Replace($pkg, "")
        $size = if ($_.Length -gt 1MB) { "$([math]::Round($_.Length / 1MB, 2)) MB" } else { "$([math]::Round($_.Length / 1KB, 2)) KB" }
        Write-Output "  $rel ($size)"
    }
}

Write-Output ""
Write-Output "=== Search for any Cinema 4D files on D drive installer ==="
Get-ChildItem "D:\BaiduNetdiskDownload" -Recurse -File -ErrorAction SilentlyContinue -Depth 6 | Where-Object {
    $_.Name -match 'Cinema 4D' -and $_.Extension -eq '.exe'
} | Select-Object -First 10 | ForEach-Object {
    Write-Output "  $($_.FullName) ($([math]::Round($_.Length / 1MB, 2)) MB)"
}

Write-Output ""
Write-Output "=== Adobe PIM dataXML content (from log) ==="
Write-Output "  Log says: Inside InstallThreadProc. Passing dataXML to PIM: <data><sourcePath></sourcePath></data>"
Write-Output "  Note: sourcePath is EMPTY - this may be the issue!"
