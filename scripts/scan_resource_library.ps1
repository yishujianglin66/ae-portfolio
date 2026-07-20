# Scan resource library for AE plugins, presets, scripts, LUTs, etc.
$ErrorActionPreference = 'Continue'

$resourceRoot = "D:\AE-Work\resources"
$output = @()

$output += "=== AE Resource Library Scan ==="
$output += "Scan Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$output += "Root: $resourceRoot"
$output += ""

# Check resource categories
$categories = @{
    "plugins" = @("plugins_dir", @(".aex", ".plugin", ".prm", ".8bf", ".zxp"))
    "presets" = @("presets_dir", @(".ffx"))
    "scripts" = @("scripts_dir", @(".jsx", ".jsxbin", ".js"))
    "luts" = @("luts_dir", @(".cube", ".3dl", ".look", ".cms"))
    "fonts" = @("fonts_dir", @(".ttf", ".otf", ".ttc"))
    "templates" = @("templates_dir", @(".aep", ".aet"))
    "effects" = @("effects_dir", @(".aep", ".ffx", ".aex"))
    "videos" = @("videos_dir", @(".mp4", ".mov", ".avi", ".mkv"))
    "images" = @("images_dir", @(".png", ".jpg", ".jpeg", ".tiff", ".psd", ".ai"))
    "audio" = @("audio_dir", @(".mp3", ".wav", ".aac", ".flac"))
}

foreach ($cat in $categories.Keys) {
    $dirName = $categories[$cat][0]
    $exts = $categories[$cat][1]

    $output += "=== Category: $cat ==="
    $catDir = Join-Path $resourceRoot $cat
    if (Test-Path $catDir) {
        $files = Get-ChildItem $catDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Extension.ToLower() -in $exts
        }
        $output += "  Directory: $catDir"
        $output += "  File count: $($files.Count)"
        $totalSize = ($files | Measure-Object Length -Sum).Sum
        $output += "  Total size: $([math]::Round($totalSize / 1MB, 2)) MB"
        $output += ""

        # List top-level folders
        $topFolders = Get-ChildItem $catDir -Directory -ErrorAction SilentlyContinue
        if ($topFolders) {
            $output += "  Top-level folders:"
            $topFolders | Select-Object -First 20 | ForEach-Object {
                $subCount = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension.ToLower() -in $exts }).Count
                $output += "    $($_.Name): $subCount files"
            }
            if ($topFolders.Count -gt 20) {
                $output += "    ... and $($topFolders.Count - 20) more folders"
            }
        }
        $output += ""

        # List unique file extensions
        $extCounts = $files | Group-Object Extension | Sort-Object Count -Descending
        $output += "  Extensions:"
        $extCounts | ForEach-Object {
            $output += "    $($_.Name): $($_.Count) files"
        }
    } else {
        $output += "  Directory not found: $catDir"
    }
    $output += ""
}

# Also check for installation packages / zxp installers
$output += "=== Installation Packages & ZXP ==="
$allZxp = Get-ChildItem $resourceRoot -Recurse -Filter "*.zxp" -ErrorAction SilentlyContinue
$allZip = Get-ChildItem $resourceRoot -Recurse -Filter "*.zip" -ErrorAction SilentlyContinue
$allRar = Get-ChildItem $resourceRoot -Recurse -Filter "*.rar" -ErrorAction SilentlyContinue
$output += "  ZXP installers: $($allZxp.Count)"
$output += "  ZIP archives: $($allZip.Count)"
$output += "  RAR archives: $($allRar.Count)"
if ($allZxp.Count -gt 0) {
    $output += "  ZXP files:"
    $allZxp | Select-Object -First 20 | ForEach-Object {
        $output += "    $($_.Name) ($([math]::Round($_.Length / 1MB, 2)) MB)"
    }
}
$output += ""

# Save output
$output | Out-File -FilePath "D:\AE-Work\resource_library_scan.txt" -Encoding UTF8
Write-Output "Scan complete. Results saved to D:\AE-Work\resource_library_scan.txt"
Write-Output "Total lines: $($output.Count)"
