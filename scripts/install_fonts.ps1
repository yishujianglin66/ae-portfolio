# Batch Install Fonts Script - Current User Method
# Install fonts to user font directory (no admin required)
# Source: D:\AE-Work\resources\fonts

$ErrorActionPreference = "SilentlyContinue"
$fontSourceDir = "D:\AE-Work\resources\fonts"

# User font directory (no admin required)
$userFontsDir = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts"
$registryPath = "HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"

# Create user fonts directory if not exists
if (-not (Test-Path $userFontsDir)) {
    New-Item -ItemType Directory -Path $userFontsDir -Force | Out-Null
    Write-Host "Created user fonts directory: $userFontsDir" -ForegroundColor Cyan
}

# Ensure registry path exists
if (-not (Test-Path $registryPath)) {
    New-Item -Path $registryPath -Force | Out-Null
}

# Font extensions
$fontExts = @(".ttf", ".otf", ".ttc", ".fon")

# Get all font files
$fontFiles = Get-ChildItem -Path $fontSourceDir -Recurse -File | Where-Object { $fontExts -contains $_.Extension.ToLower() }

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Batch Font Installer (User Scope)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Total fonts to install: $($fontFiles.Count)" -ForegroundColor Yellow
Write-Host "Target directory: $userFontsDir" -ForegroundColor Cyan
Write-Host ""

# Get list of currently installed fonts from registry
$installedFonts = @()
try {
    $regKey = Get-ItemProperty -Path $registryPath
    $regKey.PSObject.Properties | Where-Object { $_.Name -notlike "PS*" } | ForEach-Object {
        $installedFonts += $_.Value
    }
} catch {
    Write-Host "Warning: Cannot read registry, will attempt all fonts" -ForegroundColor Yellow
}

Write-Host "Already installed: $($installedFonts.Count) fonts" -ForegroundColor Cyan
Write-Host ""

$successCount = 0
$skipCount = 0
$failCount = 0
$failList = @()

$counter = 0
foreach ($fontFile in $fontFiles) {
    $counter++
    $fontName = $fontFile.Name
    $fontPath = $fontFile.FullName
    $destPath = Join-Path $userFontsDir $fontName

    # Progress display
    if ($counter % 100 -eq 0 -or $counter -eq $fontFiles.Count) {
        Write-Host "[$counter/$($fontFiles.Count)] Success:$successCount Skipped:$skipCount Failed:$failCount" -ForegroundColor Green
    }

    # Check if font file already exists in target
    if (Test-Path $destPath) {
        $skipCount++
        continue
    }

    try {
        # Copy font file to user fonts directory
        Copy-Item -Path $fontPath -Destination $destPath -Force -ErrorAction Stop

        # Get font display name (without extension)
        $fontDisplayName = [System.IO.Path]::GetFileNameWithoutExtension($fontName)
        $ext = $fontFile.Extension.ToLower()

        # Determine registry value name suffix based on extension
        $regSuffix = switch ($ext) {
            ".ttf" { " (TrueType)" }
            ".otf" { " (OpenType)" }
            ".ttc" { " (TrueType)" }
            ".fon" { " (VGA res)" }
            default { " (TrueType)" }
        }

        $regName = $fontDisplayName + $regSuffix

        # Register in HKCU registry with full path
        New-ItemProperty -Path $registryPath -Name $regName -Value $destPath -PropertyType String -Force -ErrorAction Stop | Out-Null

        $successCount++
    } catch {
        $failCount++
        $failList += "$fontName : $($_.Exception.Message)"
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Installation Summary" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Successfully installed: $successCount" -ForegroundColor Green
Write-Host "Skipped (already exists): $skipCount" -ForegroundColor Yellow
Write-Host "Failed: $failCount" -ForegroundColor Red
Write-Host ""

if ($failList.Count -gt 0) {
    Write-Host "--- Failed list (first 20) ---" -ForegroundColor Red
    $failList | Select-Object -First 20 | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
}

# Notify system of font change
Write-Host ""
Write-Host "Notifying system to refresh font cache..." -ForegroundColor Cyan
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class FontHelper3 {
    [DllImport("user32.dll")]
    public static extern int SendMessageTimeout(IntPtr hWnd, int Msg, IntPtr wParam, IntPtr lParam, int fuFlags, int uTimeout, out IntPtr lpdwResult);
    
    public const int HWND_BROADCAST = 0xffff;
    public const int WM_FONTCHANGE = 0x001D;
}
"@

$result = [IntPtr]::Zero
[FontHelper3]::SendMessageTimeout([IntPtr][FontHelper3]::HWND_BROADCAST, [FontHelper3]::WM_FONTCHANGE, [IntPtr]::Zero, [IntPtr]::Zero, 0, 1000, [ref]$result) | Out-Null
Write-Host "Font cache refresh complete!" -ForegroundColor Green
Write-Host ""
Write-Host "Note: Fonts installed to user scope. All applications can use them." -ForegroundColor Cyan
