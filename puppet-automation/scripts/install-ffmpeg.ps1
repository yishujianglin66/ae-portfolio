# ============================================================
# FFmpeg Full Install Script
# Downloads ffmpeg to C:\tools\ffmpeg
# ============================================================

$ErrorActionPreference = 'Stop'

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  FFmpeg Full Install Script" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$installDir = "C:\tools\ffmpeg"
$zipPath = "$env:TEMP\ffmpeg.zip"

Write-Host ""
Write-Host "[1/4] Creating install directory: $installDir" -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

Write-Host ""
Write-Host "[2/4] Downloading FFmpeg release essentials..." -ForegroundColor Yellow
$ProgressPreference = 'SilentlyContinue'
$url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
try {
    Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing -TimeoutSec 300
    $size = (Get-Item $zipPath).Length / 1MB
    Write-Host "  Download complete: $([math]::Round($size, 2)) MB"
} catch {
    Write-Host "  [FALLBACK] gyan.dev failed, trying BtbN GitHub..." -ForegroundColor Yellow
    $url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
    Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing -TimeoutSec 300
    $size = (Get-Item $zipPath).Length / 1MB
    Write-Host "  Download complete: $([math]::Round($size, 2)) MB"
}

Write-Host ""
Write-Host "[3/4] Extracting to: $installDir" -ForegroundColor Yellow
Expand-Archive -Path $zipPath -DestinationPath $installDir -Force

# Find ffmpeg.exe and move to bin directory
$ffmpegExe = Get-ChildItem $installDir -Recurse -Filter "ffmpeg.exe" | Select-Object -First 1
if ($ffmpegExe) {
    $binDir = Join-Path $installDir "bin"
    if (-not (Test-Path $binDir)) {
        New-Item -ItemType Directory -Force -Path $binDir | Out-Null
    }
    $targetExe = Join-Path $binDir "ffmpeg.exe"
    if ($ffmpegExe.FullName -ne $targetExe) {
        Copy-Item $ffmpegExe.FullName $targetExe -Force
        $ffprobe = Join-Path $ffmpegExe.DirectoryName "ffprobe.exe"
        if (Test-Path $ffprobe) {
            Copy-Item $ffprobe (Join-Path $binDir "ffprobe.exe") -Force
        }
    }
    Write-Host "  [OK] ffmpeg.exe: $targetExe" -ForegroundColor Green
}

Write-Host ""
Write-Host "[4/4] Adding to user PATH..." -ForegroundColor Yellow
$pathBin = "$installDir\bin"
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($userPath -notlike "*$pathBin*") {
    [Environment]::SetEnvironmentVariable("Path", "$userPath;$pathBin", "User")
    Write-Host "  [OK] Added to user PATH" -ForegroundColor Green
} else {
    Write-Host "  [SKIP] PATH already contains $pathBin" -ForegroundColor Yellow
}

# Cleanup
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  FFmpeg installation complete" -ForegroundColor Green
Write-Host "  Please reopen PowerShell for PATH to take effect" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Cyan
