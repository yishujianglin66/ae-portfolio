Write-Host "=== 管理员模式清理 C盘 ===" -ForegroundColor Green
Write-Host "时间: $(Get-Date)"

Write-Host ""
Write-Host "1. 删除 Windows.old (~26 GB)..." -ForegroundColor Yellow
try {
    takeown /F "C:\Windows.old" /R /A /D Y | Out-Null
    icacls "C:\Windows.old" /grant administrators:F /T | Out-Null
    Remove-Item -Path "C:\Windows.old" -Recurse -Force -ErrorAction Stop
    Write-Host "✅ SUCCESS: Windows.old 已删除" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: Windows.old 删除失败 - $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "2. 删除 Cinema 4D 2025 (~0.84 GB)..." -ForegroundColor Yellow
try {
    Remove-Item -Path "C:\Program Files\Maxon Cinema 4D 2025" -Recurse -Force -ErrorAction Stop
    Write-Host "✅ SUCCESS: Cinema 4D 2025 已删除" -ForegroundColor Green
} catch {
    Write-Host "❌ ERROR: Cinema 4D 2025 删除失败 - $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "3. 删除用户级缓存..." -ForegroundColor Yellow
$cacheDirs = @(
    "C:\Users\Administrator\.trae-cn",
    "C:\Users\Administrator\.lingma",
    "C:\Users\Administrator\.nuget",
    "C:\Users\Administrator\pandoc",
    "C:\Users\Administrator\.EasyOCR",
    "C:\Users\Administrator\.openvino"
)
foreach ($dir in $cacheDirs) {
    if (Test-Path $dir) {
        try {
            Remove-Item -Path "$dir\*" -Recurse -Force -ErrorAction Stop
            Write-Host "✅ SUCCESS: 已清理 $dir" -ForegroundColor Green
        } catch {
            Write-Host "❌ ERROR: 清理 $dir 失败 - $_" -ForegroundColor Red
        }
    }
}

Write-Host ""
Write-Host "=== 清理完成 ===" -ForegroundColor Green
$drive = Get-PSDrive C
Write-Host "C盘剩余空间: $([math]::Round($drive.Free / 1GB, 2)) GB" -ForegroundColor Cyan
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")