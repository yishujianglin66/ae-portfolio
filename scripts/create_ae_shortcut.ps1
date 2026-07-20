# Create desktop shortcut for Adobe After Effects 2025
$ErrorActionPreference = 'Stop'

$aePath = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "Adobe After Effects 2025.lnk"

# Remove existing shortcut if any
if (Test-Path $shortcutPath) {
    Remove-Item $shortcutPath -Force
    Write-Output "Removed existing shortcut"
}

# Create new shortcut
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $aePath
$shortcut.WorkingDirectory = Split-Path $aePath
$shortcut.Description = "Adobe After Effects 2025 v25.3"
$shortcut.WindowStyle = 1

# Try to set icon (use AE's own icon)
$shortcut.IconLocation = "$aePath,0"

$shortcut.Save()

Write-Output ""
Write-Output "=== Shortcut Created Successfully ==="
Write-Output "  Path: $shortcutPath"
Write-Output "  Target: $aePath"
Write-Output "  Size: $([math]::Round((Get-Item $shortcutPath).Length / 1KB, 2)) KB"
