# Cleanup executor - deletes paths from manifest JSON to Recycle Bin in chunks of 10
# Usage: powershell -File scripts/cleanup_recycle.ps1 -Category C1_work
param(
    [Parameter(Mandatory=$true)][string]$Category
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName Microsoft.VisualBasic

$manifestPath = "output/_cleanup_manifest_20260908.json"
$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$paths = $manifest.paths.$Category

if (-not $paths -or $paths.Count -eq 0) {
    Write-Output "NO_PATHS for category $Category"
    exit 1
}

Write-Output "Category: $Category  total items: $($paths.Count)"
$chunkSize = 10
$failed = @()
for ($i = 0; $i -lt $paths.Count; $i += $chunkSize) {
    $chunk = $paths[$i..([Math]::Min($i + $chunkSize - 1, $paths.Count - 1))]
    foreach ($p in $chunk) {
        if (-not (Test-Path $p)) {
            Write-Output "SKIP (missing): $p"
            continue
        }
        try {
            if (Test-Path $p -PathType Container) {
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteDirectory($p, 'OnlyErrorDialogs', 'SendToRecycleBin')
            } else {
                [Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile($p, 'OnlyErrorDialogs', 'SendToRecycleBin')
            }
        } catch {
            Write-Output "FAIL: $p -> $($_.Exception.Message)"
            $failed += $p
        }
    }
    Write-Output ("PROGRESS: {0}/{1}" -f ([Math]::Min($i + $chunkSize, $paths.Count)), $paths.Count)
}

if ($failed.Count -gt 0) {
    Write-Output "FAILED_ITEMS: $($failed.Count)"
    $failed | ForEach-Object { Write-Output "  $_" }
    exit 2
}
Write-Output "DONE_OK"
