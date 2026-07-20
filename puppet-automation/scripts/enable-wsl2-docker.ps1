# ============================================================
# WSL2 + Docker Desktop Enable Script
# Run as Administrator (right-click -> Run as administrator)
# ============================================================

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Puppet Automation - WSL2 + Docker Enable Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# Check if running as administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "[ERROR] This script requires administrator privileges." -ForegroundColor Red
    Write-Host "        Right-click PowerShell -> Run as administrator."
    Write-Host "        Or run: Start-Process powershell -Verb RunAs -ArgumentList '-File `"$PSCommandPath`"'"
    exit 1
}

Write-Host ""
Write-Host "[1/5] Checking WSL2 feature status..." -ForegroundColor Yellow
$wslFeature = Get-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
$vmFeature = Get-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform
Write-Host "  WSL: $($wslFeature.State)"
Write-Host "  VM Platform: $($vmFeature.State)"

if ($wslFeature.State -ne 'Enabled') {
    Write-Host ""
    Write-Host "[2/5] Enabling WSL feature..." -ForegroundColor Yellow
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
} else {
    Write-Host ""
    Write-Host "[2/5] WSL already enabled, skipping" -ForegroundColor Green
}

if ($vmFeature.State -ne 'Enabled') {
    Write-Host ""
    Write-Host "[3/5] Enabling Virtual Machine Platform..." -ForegroundColor Yellow
    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
} else {
    Write-Host ""
    Write-Host "[3/5] Virtual Machine Platform already enabled, skipping" -ForegroundColor Green
}

Write-Host ""
Write-Host "[4/5] Setting WSL default version to 2..." -ForegroundColor Yellow
try {
    wsl --set-default-version 2 2>&1 | Out-Host
} catch {
    Write-Host "  WSL not installed, run: wsl --install" -ForegroundColor Red
}

Write-Host ""
Write-Host "[5/5] Checking Docker Desktop..." -ForegroundColor Yellow
$dockerPath = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
if (Test-Path $dockerPath) {
    Write-Host "  Docker Desktop installed: $dockerPath" -ForegroundColor Green
} else {
    Write-Host "  Docker Desktop not installed" -ForegroundColor Yellow
    Write-Host "  Download: https://desktop.docker.com/win/main/amd64/Docker%20Desktop%20Installer.exe"
    Write-Host "  Or run: winget install Docker.DockerDesktop"
    Write-Host "  Restart required after install"
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  WSL2 configuration complete. Please restart your PC." -ForegroundColor Green
Write-Host "  After restart, install Docker Desktop to use Docker." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan

$restart = Read-Host "Restart now? (y/N)"
if ($restart -eq 'y' -or $restart -eq 'Y') {
    Restart-Computer -Force
}
