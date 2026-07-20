# Check Cinema 4D keyfile directory
$ErrorActionPreference = 'Continue'

Write-Output "=== Keyfiles Directory ==="
$keyfilePath = "C:\Program Files\Common Files\Adobe\Keyfiles"
if (Test-Path $keyfilePath) {
    Get-ChildItem $keyfilePath -Recurse -Directory -ErrorAction SilentlyContinue | Select-Object -First 30 | ForEach-Object {
        Write-Output $_.FullName
    }
    Write-Output ""
    Write-Output "=== AfterEffects\25\CustomHook\win ==="
    $cinemaDir = Join-Path $keyfilePath "AfterEffects\25\CustomHook\win"
    if (Test-Path $cinemaDir) {
        Get-ChildItem $cinemaDir -File -ErrorAction SilentlyContinue | ForEach-Object {
            $sizeKB = [math]::Round($_.Length / 1KB, 2)
            Write-Output "  $($_.Name) ($sizeKB KB)"
        }
    } else {
        Write-Output "  MISSING: $cinemaDir"
    }
    Write-Output ""
    Write-Output "=== All files under CustomHook ==="
    $customHook = Join-Path $keyfilePath "AfterEffects\25\CustomHook"
    if (Test-Path $customHook) {
        Get-ChildItem $customHook -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
            Write-Output "  $($_.FullName)"
        }
    }
} else {
    Write-Output "Keyfiles directory not found: $keyfilePath"
}

Write-Output ""
Write-Output "=== Search Cinema 4D in installer package ==="
$installerPath = "D:\BaiduNetdiskDownload\Adobe After Effects 2025 v25.3.0.071"
if (Test-Path $installerPath) {
    $cinemaFiles = Get-ChildItem $installerPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -match 'Cinema|cinema|C4D|c4d'
    }
    Write-Output "Found $($cinemaFiles.Count) Cinema 4D related files"
    $cinemaFiles | Select-Object -First 20 | ForEach-Object {
        Write-Output "  $($_.FullName)"
    }
} else {
    Write-Output "Installer path not found: $installerPath"
}

Write-Output ""
Write-Output "=== Search Cinema 4D.exe on entire C drive ==="
Get-ChildItem "C:\" -Recurse -File -Filter "Cinema 4D.exe" -ErrorAction SilentlyContinue -Depth 8 | Select-Object -First 5 | ForEach-Object {
    Write-Output "  $($_.FullName)"
}
