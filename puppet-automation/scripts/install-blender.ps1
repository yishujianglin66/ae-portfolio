# ============================================================
# Blender 4.x 静默安装脚本
# 需要以管理员身份运行
# ============================================================

$ErrorActionPreference = 'Stop'

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Blender 4.x 安装脚本" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

$blenderUrl = "https://download.blender.org/release/Blender4.2/blender-4.2.5-windows-x64.msi"
$installerPath = "$env:TEMP\blender-installer.msi"
$installPath = "C:\Program Files\Blender Foundation"

Write-Host "`n[1/4] 下载 Blender 4.2.5 MSI 安装包..." -ForegroundColor Yellow
$ProgressPreference = 'SilentlyContinue'
Invoke-WebRequest -Uri $blenderUrl -OutFile $installerPath -UseBasicParsing
$size = (Get-Item $installerPath).Length / 1MB
Write-Host "  下载完成: $([math]::Round($size, 2)) MB"

Write-Host "`n[2/4] 检查管理员权限..." -ForegroundColor Yellow
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "  [WARN] 未以管理员身份运行，尝试安装到用户目录..." -ForegroundColor Yellow
    $installPath = "$env:LOCALAPPDATA\Programs\Blender"
}

Write-Host "`n[3/4] 静默安装 Blender 到: $installPath" -ForegroundColor Yellow
$installArgs = "/i `"$installerPath`" /quiet /norestart INSTALLDIR=`"$installPath`""
$process = Start-Process msiexec.exe -ArgumentList $installArgs -Wait -PassThru
Write-Host "  安装退出码: $($process.ExitCode)"

Write-Host "`n[4/4] 验证安装..." -ForegroundColor Yellow
$blenderExe = Join-Path $installPath "blender.exe"
if (Test-Path $blenderExe) {
    Write-Host "  [OK] Blender 安装成功: $blenderExe" -ForegroundColor Green
} else {
    # 尝试在子目录查找
    $found = Get-ChildItem $installPath -Recurse -Filter "blender.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) {
        Write-Host "  [OK] Blender 安装成功: $($found.FullName)" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] Blender 可执行文件未找到" -ForegroundColor Red
    }
}

# 清理安装包
Remove-Item $installerPath -Force -ErrorAction SilentlyContinue

Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "  Blender 安装完成" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
