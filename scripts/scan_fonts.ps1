$ErrorActionPreference = 'SilentlyContinue'
$fontsRoot = 'D:\AE-Work\resources\fonts'
$installedFile = 'D:\AE-Work\installed_fonts.txt'

Write-Output "=== Font Resource Scan ==="
Write-Output "Source: $fontsRoot"

$fontFiles = Get-ChildItem -Path $fontsRoot -Recurse -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -in @('.ttf','.otf','.ttc') }

Write-Output ("Total font files: {0}" -f $fontFiles.Count)
Write-Output ""

$byCategory = @{}
foreach ($f in $fontFiles) {
    $rel = $f.DirectoryName.Replace($fontsRoot, '').Trim('\', '/')
    if (-not $rel) { $rel = '(root)' }
    if (-not $byCategory.ContainsKey($rel)) { $byCategory[$rel] = @() }
    $byCategory[$rel] += $f
}

Write-Output "=== Categories ==="
foreach ($key in ($byCategory.Keys | Sort-Object)) {
    $count = $byCategory[$key].Count
    Write-Output ("[{0}]  {1} files" -f $key, $count)
    $byCategory[$key] | Select-Object -First 30 | ForEach-Object {
        $size = [math]::Round($_.Length / 1024, 0)
        Write-Output ("  {0,-55}  {1}KB" -f $_.Name, $size)
    }
    if ($byCategory[$key].Count -gt 30) {
        Write-Output ("  ... more {0} files" -f ($byCategory[$key].Count - 30))
    }
    Write-Output ""
}

if (Test-Path $installedFile) {
    Write-Output "=== Installed Fonts (first 30) ==="
    Get-Content $installedFile -Encoding UTF8 | Select-Object -First 30 | ForEach-Object {
        Write-Output ("  $_")
    }
    $totalInstalled = (Get-Content $installedFile -Encoding UTF8 | Measure-Object).Count
    Write-Output ("Total installed: {0}" -f $totalInstalled)
} else {
    Write-Output ("[Installed fonts list not found: {0}]" -f $installedFile)
}
