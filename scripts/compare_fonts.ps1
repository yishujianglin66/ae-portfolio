$ErrorActionPreference = 'Stop'

# Load installed fonts list
$installedFile = 'D:\AE-Work\installed_fonts.txt'
if (-not (Test-Path $installedFile)) {
    Write-Error "Installed fonts list not found: $installedFile"
    exit 1
}
$installedNames = @{}
Get-Content -Path $installedFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line) {
        $installedNames[$line.ToLower()] = $true
    }
}
Write-Output "Installed fonts count: $($installedNames.Count)"

# Scan resource library fonts
$fontsRoot = 'D:\AE-Work\resources\fonts'
if (-not (Test-Path $fontsRoot)) {
    Write-Error "Resource fonts directory not found: $fontsRoot"
    exit 1
}

$fontExtensions = @('.ttf', '.otf', '.ttc', '.fon')
$resourceFonts = @()
$uninstalled = @()

Get-ChildItem -Path $fontsRoot -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $fontExtensions -contains $_.Extension.ToLower()
} | ForEach-Object {
    $resourceFonts += $_
    $key = $_.Name.ToLower()
    if (-not $installedNames.ContainsKey($key)) {
        $uninstalled += $_
    }
}

Write-Output "Resource fonts count: $($resourceFonts.Count)"
Write-Output "Uninstalled fonts count: $($uninstalled.Count)"

# Save uninstalled list
$uninstalledList = 'D:\AE-Work\uninstalled_fonts.txt'
$uninstalled | ForEach-Object { $_.FullName } | Out-File -FilePath $uninstalledList -Encoding UTF8
Write-Output "Uninstalled list saved: $uninstalledList"

if ($uninstalled.Count -gt 0) {
    Write-Output "---First 20 uninstalled fonts---"
    $uninstalled | Select-Object -First 20 | ForEach-Object {
        Write-Output "  $($_.Name)  <-  $($_.DirectoryName)"
    }
}
