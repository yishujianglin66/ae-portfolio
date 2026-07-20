# Deep scan AE 2025 installation status and plugins
$ErrorActionPreference = 'Continue'

$aeRoot = "C:\Program Files\Adobe\Adobe After Effects 2025"
$output = @()

$output += "=== Adobe After Effects 2025 - Installation Scan ==="
$output += "Scan Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$output += ""

# 1. Installation base check
$output += "=== 1. Installation Status ==="
if (Test-Path $aeRoot) {
    $totalSize = (Get-ChildItem $aeRoot -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
    $output += "  Status: INSTALLED"
    $output += "  Path: $aeRoot"
    $output += "  Total Size: $([math]::Round($totalSize / 1GB, 2)) GB"
    $output += "  Total Files: $((Get-ChildItem $aeRoot -Recurse -File -ErrorAction SilentlyContinue).Count)"
    $output += "  Total Folders: $((Get-ChildItem $aeRoot -Recurse -Directory -ErrorAction SilentlyContinue).Count)"
} else {
    $output += "  Status: NOT INSTALLED"
    exit
}
$output += ""

# 2. Plug-ins scan
$output += "=== 2. Plug-ins (Plug-ins folder) ==="
$pluginsDir = Join-Path $aeRoot "Support Files\Plug-ins"
if (Test-Path $pluginsDir) {
    $pluginFiles = Get-ChildItem $pluginsDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Extension -in '.aex', '.plugin'
    }
    $output += "  Plugin files found: $($pluginFiles.Count)"
    $output += ""
    $output += "  --- Top-level plugin folders ---"
    Get-ChildItem $pluginsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $count = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.aex', '.plugin' }).Count
        $size = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum
        $sizeMB = [math]::Round($size / 1MB, 2)
        $output += "    $($_.Name): $count plugins, $sizeMB MB"
    }
    $output += ""
    $output += "  --- All .aex files ---"
    $pluginFiles | ForEach-Object {
        $relPath = $_.FullName.Replace($pluginsDir, "")
        $sizeKB = [math]::Round($_.Length / 1KB, 2)
        $output += "    $relPath ($sizeKB KB)"
    }
} else {
    $output += "  Plug-ins directory not found"
}
$output += ""

# 3. Scripts scan
$output += "=== 3. Scripts ==="
$scriptsDir = Join-Path $aeRoot "Support Files\Scripts"
if (Test-Path $scriptsDir) {
    $scriptFiles = Get-ChildItem $scriptsDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Extension -in '.jsx', '.jsxbin', '.js'
    }
    $output += "  Script files: $($scriptFiles.Count)"
    $output += "  ScriptUI Panels:"
    $scriptUIPath = Join-Path $scriptsDir "ScriptUI Panels"
    if (Test-Path $scriptUIPath) {
        Get-ChildItem $scriptUIPath -File -ErrorAction SilentlyContinue | ForEach-Object {
            $sizeKB = [math]::Round($_.Length / 1KB, 2)
            $output += "    $($_.Name) ($sizeKB KB)"
        }
    }
    $output += ""
    $output += "  Startup Scripts:"
    $startupPath = Join-Path $scriptsDir "Startup"
    if (Test-Path $startupPath) {
        Get-ChildItem $startupPath -File -ErrorAction SilentlyContinue | ForEach-Object {
            $output += "    $($_.Name)"
        }
    }
} else {
    $output += "  Scripts directory not found"
}
$output += ""

# 4. Presets scan
$output += "=== 4. Presets & Animation Presets ==="
$presetsDir = Join-Path $aeRoot "Support Files\Presets"
if (Test-Path $presetsDir) {
    $presetFiles = Get-ChildItem $presetsDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Extension -in '.ffx'
    }
    $output += "  Preset files: $($presetFiles.Count)"
    $output += "  Categories:"
    Get-ChildItem $presetsDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $count = (Get-ChildItem $_.FullName -Recurse -Filter '*.ffx' -ErrorAction SilentlyContinue).Count
        $output += "    $($_.Name): $count presets"
    }
} else {
    $output += "  Presets directory not found"
}
$output += ""

# 5. Common Files / Plug-ins
$output += "=== 5. Common Plug-ins (Common Files) ==="
$commonPlugins = "C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore"
if (Test-Path $commonPlugins) {
    $commonPluginFiles = Get-ChildItem $commonPlugins -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
        $_.Extension -in '.aex', '.plugin', '.prm', '.8bf'
    }
    $output += "  Common Plugin files: $($commonPluginFiles.Count)"
    Get-ChildItem $commonPlugins -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $count = (Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Where-Object { $_.Extension -in '.aex', '.plugin', '.prm' }).Count
        if ($count -gt 0) {
            $output += "    $($_.Name): $count plugins"
        }
    }
    $output += ""
    $commonPluginFiles | ForEach-Object {
        $rel = $_.FullName.Replace($commonPlugins, "")
        $sizeKB = [math]::Round($_.Length / 1KB, 2)
        $output += "    $rel ($sizeKB KB)"
    }
} else {
    $output += "  Common Plug-ins directory not found: $commonPlugins"
}
$output += ""

# 6. User presets and scripts (AppData)
$output += "=== 6. User Scripts & Presets (AppData) ==="
$userAE = "$env:APPDATA\Adobe\After Effects"
if (Test-Path $userAE) {
    $output += "  User AE config path: $userAE"
    Get-ChildItem $userAE -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $output += "    Version: $($_.Name)"
    }
    # Check latest version
    $latestVersion = Get-ChildItem $userAE -Directory -ErrorAction SilentlyContinue | Sort-Object Name -Descending | Select-Object -First 1
    if ($latestVersion) {
        $userScripts = Join-Path $latestVersion.FullName "Scripts"
        $userPresets = Join-Path $latestVersion.FullName "User Presets"
        if (Test-Path $userScripts) {
            $output += "    User Scripts: $((Get-ChildItem $userScripts -Recurse -File -ErrorAction SilentlyContinue).Count) files"
        }
        if (Test-Path $userPresets) {
            $output += "    User Presets: $((Get-ChildItem $userPresets -Recurse -File -ErrorAction SilentlyContinue).Count) files"
        }
    }
} else {
    $output += "  No user AE config found (first run not completed)"
}
$output += ""

# 7. LUTs / Lumetri
$output += "=== 7. LUTs & Lumetri ==="
$lutPaths = @(
    "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Lumetri\LUTs",
    "C:\Program Files\Adobe\Common\LUTs",
    "C:\ProgramData\Adobe\LUTs"
)
foreach ($lutPath in $lutPaths) {
    if (Test-Path $lutPath) {
        $lutFiles = Get-ChildItem $lutPath -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Extension -in '.cube', '.3dl', '.look'
        }
        $output += "  $lutPath : $($lutFiles.Count) LUTs"
    }
}
$output += ""

# 8. Fonts check (already installed)
$output += "=== 8. Installed Fonts (sample count) ==="
$shell = New-Object -ComObject Shell.Application
$fontsFolder = $shell.Namespace(0x14)
$fontCount = ($fontsFolder.Items() | Measure-Object).Count
$output += "  Total installed fonts: $fontCount"
$output += ""

# Save output
$output | Out-File -FilePath "D:\AE-Work\ae25_plugin_scan.txt" -Encoding UTF8
Write-Output "Scan complete. Results saved to D:\AE-Work\ae25_plugin_scan.txt"
Write-Output "Total lines: $($output.Count)"
