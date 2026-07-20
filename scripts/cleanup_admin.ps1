Write-Host "=== 管理员模式清理开始 ==="
Write-Host "时间: $(Get-Date)"

Write-Host ""
Write-Host "1. 删除 Windows.old..."
try {
    takeown /F "C:\Windows.old" /R /A /D Y
    icacls "C:\Windows.old" /grant administrators:F /T
    Remove-Item -Path "C:\Windows.old" -Recurse -Force -ErrorAction Stop
    Write-Host "SUCCESS: Windows.old 已删除"
} catch {
    Write-Host "ERROR: Windows.old 删除失败 - $_"
}

Write-Host ""
Write-Host "2. 删除 Cinema 4D 2025..."
try {
    Remove-Item -Path "C:\Program Files\Maxon Cinema 4D 2025" -Recurse -Force -ErrorAction Stop
    Write-Host "SUCCESS: Cinema 4D 2025 已删除"
} catch {
    Write-Host "ERROR: Cinema 4D 2025 删除失败 - $_"
}

Write-Host ""
Write-Host "3. 删除 Silhouette 安装残留..."
$silhouetteDirs = @(
    "C:\Program Files\BorisFX\Silhouette*",
    "C:\ProgramData\BorisFX\*"
)
foreach ($dir in $silhouetteDirs) {
    if (Test-Path $dir) {
        try {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction Stop
            Write-Host "SUCCESS: 已删除 $dir"
        } catch {
            Write-Host "ERROR: 删除 $dir 失败 - $_"
        }
    } else {
        Write-Host "INFO: $dir 不存在"
    }
}

Write-Host ""
Write-Host "4. 清理注册表残留..."
try {
    Get-ItemProperty "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*" | 
        Where-Object { $_.DisplayName -match "Silhouette" } | 
        ForEach-Object { Remove-Item -Path $_.PSPath -Force }
    Write-Host "SUCCESS: 注册表清理完成"
} catch {
    Write-Host "ERROR: 注册表清理失败 - $_"
}

Write-Host ""
Write-Host "=== 清理完成 ==="
$drive = Get-PSDrive C
Write-Host "C盘剩余空间: $([math]::Round($drive.Free / 1GB, 2)) GB"
Write-Host "按任意键退出..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")