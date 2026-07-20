$ErrorActionPreference = 'Continue'

# Read the truly uninstalled list (FilePath|FamilyName per line)
$srcFile = 'D:\AE-Work\truly_uninstalled_fonts.txt'
if (-not (Test-Path $srcFile)) {
    Write-Error "Source list not found: $srcFile"
    exit 1
}

# Dedup by FamilyName (case-insensitive)
$familyMap = @{}  # familyName_lower -> first file path
$total = 0
Get-Content -Path $srcFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if (-not $line) { return }
    $parts = $line -split '\|', 2
    if ($parts.Count -lt 2) { return }
    $filePath = $parts[0]
    $familyName = $parts[1]
    $total++
    $key = $familyName.ToLower()
    if (-not $familyMap.ContainsKey($key)) {
        $familyMap[$key] = @{ FilePath = $filePath; FamilyName = $familyName }
    }
}

Write-Output "=== Dedup Result ==="
Write-Output "Total entries: $total"
Write-Output "Unique families: $($familyMap.Count)"

# Save deduped install list (FilePath only, for Shell.Application CopyHere)
$installList = 'D:\AE-Work\fonts_to_install_dedup.txt'
$familyMap.Values | ForEach-Object { $_.FilePath } | Out-File -FilePath $installList -Encoding UTF8
Write-Output "Deduped install list saved: $installList"

# Sample
Write-Output ""
Write-Output "---First 20 unique families to install---"
$familyMap.Values | Select-Object -First 20 | ForEach-Object {
    $fname = Split-Path -Leaf $_.FilePath
    Write-Output "  [$($_.FamilyName)]  $fname"
}
