# Deep analysis of missing AE resources
$ErrorActionPreference = 'Continue'

$output = @()
$aeRoot = "C:\Program Files\Adobe\Adobe After Effects 2025"
$resRoot = "D:\AE-Work\resources"

$output += "=== AE 2025 Deep Resource Analysis ==="
$output += ""

# 1. Empty plugin folders (no .aex files)
$output += "=== 1. Empty / Near-Empty Plugin Folders ==="
$pluginsDir = Join-Path $aeRoot "Support Files\Plug-ins"
if (Test-Path $pluginsDir) {
    Get-ChildItem $pluginsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $aexCount = (Get-ChildItem $_.FullName -Recurse -Filter '*.aex' -ErrorAction SilentlyContinue).Count
        $totalSize = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $sizeMB = [math]::Round($totalSize / 1MB, 2)
        if ($aexCount -le 2) {
            $output += "  $($_.Name): $aexCount .aex files, $sizeMB MB"
            Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 5 | ForEach-Object {
                $output += "    - $($_.Name) ($([math]::Round($_.Length / 1KB, 2)) KB)"
            }
        }
    }
}
$output += ""

# 2. Check for must-have plugins
$output += "=== 2. Must-Have Plugin Sets Check ==="
$mustHaves = @{
    "Trapcode Suite" = @("Particular", "Form", "Trapcode")
    "Magic Bullet Suite" = @("Magic Bullet", "Looks", "Colorista")
    "Red Giant Universe" = @("Universe")
    "Boris Continuum" = @("Continuum", "BCC")
    "Boris Sapphire" = @("Sapphire")
    "Video Copilot Element 3D" = @("Element.aex")
    "FXConsole" = @("FXConsole")
    "Duik Bassel" = @("Duik")
    "AfterCodecs" = @("AfterCodecs")
    "BG Renderer" = @("BG Renderer")
    "Pastiche" = @("Pastiche")
    "Deep Glow" = @("Deep Glow")
    "Shadow Studio" = @("Shadow Studio")
}

$allPluginFiles = Get-ChildItem $pluginsDir -Recurse -Filter '*.aex' -ErrorAction SilentlyContinue
$scriptsDir = Join-Path $aeRoot "Support Files\Scripts"
$allScripts = if (Test-Path $scriptsDir) { Get-ChildItem $scriptsDir -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.jsx', '.jsxbin' } } else { @() }

foreach ($setName in $mustHaves.Keys) {
    $keywords = $mustHaves[$setName]
    $found = $false
    $foundItems = @()
    
    foreach ($kw in $keywords) {
        $matches = $allPluginFiles | Where-Object { $_.Name -like "*$kw*" }
        if ($matches) {
            $found = $true
            $foundItems += $kw
        }
    }
    
    foreach ($kw in $keywords) {
        $sMatches = $allScripts | Where-Object { $_.Name -like "*$kw*" }
        if ($sMatches -and $kw -notin $foundItems) {
            $found = $true
            $foundItems += "$kw(script)"
        }
    }
    
    $status = if ($found) { "OK" } else { "MISSING" }
    $detail = if ($foundItems.Count -gt 0) { "$($foundItems -join ', ')" } else { "none" }
    $output += "  $status - $setName`: $detail"
}
$output += ""

# 3. Missing resource library categories
$output += "=== 3. Resource Library Category Status ==="
$requiredCats = @(
    @("plugins", "AE 插件安装包与 ZXP"),
    @("scripts", "AE 脚本"),
    @("presets", "动画预设 FFX"),
    @("effects", "特效素材"),
    @("videos", "视频素材"),
    @("images", "图片素材"),
    @("templates", "AE 工程模板"),
    @("fonts", "字体"),
    @("luts", "调色 LUT"),
    @("audio", "音频音效"),
    @("models", "3D 模型"),
    @("tutorials", "教程"),
    @("software", "软件安装包")
)

foreach ($cat in $requiredCats) {
    $catName = $cat[0]
    $catDesc = $cat[1]
    $catDir = Join-Path $resRoot $catName
    if (Test-Path $catDir) {
        $files = Get-ChildItem $catDir -Recurse -File -ErrorAction SilentlyContinue
        $status = "EXISTS"
        $count = $files.Count
        $output += "  $status - $catName ($count files): $catDesc"
    } else {
        $output += "  MISSING - $catName`: $catDesc"
    }
}
$output += ""

# 4. AE version info
$output += "=== 4. AE 2025 Version Info ==="
$aeExe = Join-Path $aeRoot "Support Files\AfterFX.exe"
if (Test-Path $aeExe) {
    $ver = [System.Diagnostics.FileVersionInfo]::GetVersionInfo($aeExe)
    $output += "  File: $aeExe"
    $output += "  Product Version: $($ver.ProductVersion)"
    $output += "  File Version: $($ver.FileVersion)"
    $output += "  Product Name: $($ver.ProductName)"
}
$output += ""

# 5. Script categories
$output += "=== 5. Script Categories ==="
if (Test-Path $scriptsDir) {
    $output += "  Total scripts: $($allScripts.Count)"
    
    $scriptUIPath = Join-Path $scriptsDir "ScriptUI Panels"
    if (Test-Path $scriptUIPath) {
        $uiScripts = Get-ChildItem $scriptUIPath -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.jsx', '.jsxbin' }
        $output += "  ScriptUI Panels: $($uiScripts.Count)"
    }
}
$output += ""

# 6. Presets
$output += "=== 6. Presets Analysis ==="
$presetsDir = Join-Path $aeRoot "Support Files\Presets"
if (Test-Path $presetsDir) {
    $presets = Get-ChildItem $presetsDir -Recurse -Filter '*.ffx' -ErrorAction SilentlyContinue
    $output += "  Total .ffx presets: $($presets.Count)"
    Get-ChildItem $presetsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $count = (Get-ChildItem $_.FullName -Recurse -Filter '*.ffx' -ErrorAction SilentlyContinue).Count
        if ($count -gt 0) {
            $output += "    $($_.Name): $count presets"
        }
    }
}
$output += ""

# Save
$output | Out-File -FilePath "D:\AE-Work\ae_resource_gap_analysis.txt" -Encoding UTF8
Write-Output "Analysis complete. Saved to D:\AE-Work\ae_resource_gap_analysis.txt"
Write-Output "Total lines: $($output.Count)"
