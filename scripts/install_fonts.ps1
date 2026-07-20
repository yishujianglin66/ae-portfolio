# Font Auto-Installer - Silent install all fonts
# Usage: Right-click -> Run with PowerShell (as admin)

$ErrorActionPreference = "Continue"

# Font library path
$fontRoot = "D:\AE-Work\resources\fonts"
$windowsFontsDir = "$env:WINDIR\Fonts"
$regPath = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Font Auto-Installer" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check admin
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
Write-Host "Admin: $isAdmin" -ForegroundColor $(if($isAdmin){'Green'}else{'Red'})

if (-not $isAdmin) {
    Write-Host "ERROR: Run as administrator!" -ForegroundColor Red
    Start-Sleep 3
    exit 1
}

# Get installed fonts from registry
Write-Host "`nScanning installed fonts..." -ForegroundColor Yellow
$installedFonts = @{}
$regFonts = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
if ($regFonts) {
    $regFonts.PSObject.Properties | ForEach-Object {
        if ($_.Name -notmatch "^PS" -and $_.Value) {
            $fileName = [System.IO.Path]::GetFileName($_.Value)
            $installedFonts[$fileName.ToLower()] = $_.Name
        }
    }
}
Write-Host "  Installed: $($installedFonts.Count)" -ForegroundColor Green

# Scan all fonts in library
Write-Host "`nScanning font library..." -ForegroundColor Yellow
$fontExts = @(".ttf", ".otf", ".ttc", ".fon")
$allFonts = Get-ChildItem -Path $fontRoot -Recurse -File |
            Where-Object { $fontExts -contains $_.Extension.ToLower() -and $_.Directory.Name -match "^\d+-" }
Write-Host "  Found: $($allFonts.Count) fonts" -ForegroundColor Green

# Filter to install
$toInstall = @()
$alreadyInstalled = 0
foreach ($font in $allFonts) {
    if ($installedFonts.ContainsKey($font.Name.ToLower())) {
        $alreadyInstalled++
    } else {
        $toInstall += $font
    }
}
Write-Host "  Already installed: $alreadyInstalled" -ForegroundColor Green
Write-Host "  To install: $($toInstall.Count)" -ForegroundColor Yellow

if ($toInstall.Count -eq 0) {
    Write-Host "`nAll fonts already installed!" -ForegroundColor Green
    Start-Sleep 2
    exit 0
}

# Install fonts
Write-Host "`nInstalling fonts..." -ForegroundColor Yellow
$success = 0
$failed = 0
$i = 0

foreach ($font in $toInstall) {
    $i++
    try {
        $destPath = Join-Path $windowsFontsDir $font.Name

        # Copy font file
        Copy-Item -Path $font.FullName -Destination $destPath -Force -ErrorAction Stop

        # Register in registry
        $baseName = [System.IO.Path]::GetFileNameWithoutExtension($font.Name)
        $ext = $font.Extension.ToLower()
        $fontType = switch ($ext) {
            ".ttf" { " (TrueType)" }
            ".otf" { " (OpenType)" }
            ".ttc" { " (TrueType)" }
            ".fon" { "" }
            default { " (TrueType)" }
        }
        $displayName = $baseName + $fontType

        New-ItemProperty -Path $regPath -Name $displayName -Value $font.Name -PropertyType String -Force | Out-Null

        $success++
        # Progress every 100 fonts
        if ($i % 100 -eq 0) {
            Write-Host "  Progress: $i / $($toInstall.Count) (OK: $success, FAIL: $failed)" -ForegroundColor Cyan
        }
    } catch {
        $failed++
    }
}

# Notify system about font change
Write-Host "`nNotifying system..." -ForegroundColor Yellow
Add-Type -Namespace Win32 -Name Native -MemberDefinition @"
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern int SendMessageTimeout(IntPtr hWnd, int Msg, IntPtr wParam, IntPtr lParam, int fuFlags, int uTimeout, out IntPtr lpdwResult);
"@
$HWND_BROADCAST = [IntPtr]0xffff
$WM_FONTCHANGE = 0x001D
$result = [IntPtr]::Zero
[Win32.Native]::SendMessageTimeout($HWND_BROADCAST, $WM_FONTCHANGE, [IntPtr]::Zero, [IntPtr]::Zero, 0, 1000, [ref]$result) | Out-Null

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "  Installation Complete!" -ForegroundColor Green
Write-Host "  Installed: $success" -ForegroundColor Green
Write-Host "  Failed: $failed" -ForegroundColor $(if($failed -eq 0){'Green'}else{'Yellow'})
Write-Host "  Was installed: $alreadyInstalled" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nRestart your applications to use the new fonts."
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
