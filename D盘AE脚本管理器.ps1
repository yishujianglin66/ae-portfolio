#Requires -RunAsAdministrator
<#
.SYNOPSIS
    D盘AE脚本管理器 - 统一管理AE脚本安装到D盘
.DESCRIPTION
    本脚本用于将AE脚本（CEP扩展和ScriptUI脚本）安装到D盘指定目录，
    并自动创建符号链接让C盘的AE能够加载D盘脚本。
.NOTES
    必须以管理员身份运行
    适用AE版本: 2025
#>

# 配置路径
$Config = @{
    # D盘脚本根目录
    D_ScriptsRoot     = "D:\Adobe\Scripts"
    # CEP扩展D盘目录
    D_CEPDir          = "D:\Adobe\Scripts\CEP\extensions"
    # ScriptUI脚本D盘目录
    D_ScriptUIDir     = "D:\Adobe\Scripts\ScriptUI\ScriptUI Panels"
    # C盘CEP扩展目录（符号链接目标）
    C_CEPDir          = "C:\Program Files (x86)\Common Files\Adobe\CEP\extensions"
    # C盘ScriptUI目录（符号链接目标）
    C_ScriptUIDir     = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels"
    # AE 2025 ScriptUI路径（备用）
    C_ScriptUIDir2025 = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels"
}

# 确保D盘目录存在
function Initialize-Directories {
    $dirs = @(
        $Config.D_CEPDir,
        $Config.D_ScriptUIDir,
        "D:\Adobe\Scripts\Startup",
        "D:\Adobe\Scripts\Shutdown",
        "D:\Adobe\AE-Extensions",
        "D:\Adobe\AE-Scripts"
    )
    foreach ($dir in $dirs) {
        if (!(Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
            Write-Host "[创建] $dir" -ForegroundColor Green
        }
    }
}

# 安装CEP扩展到D盘
function Install-CEPExtension {
    param(
        [Parameter(Mandatory=$true)]
        [string]$SourcePath,
        
        [Parameter(Mandatory=$false)]
        [string]$ExtensionName = $null
    )
    
    if (!(Test-Path $SourcePath)) {
        Write-Error "源路径不存在: $SourcePath"
        return
    }
    
    # 自动获取扩展名
    if (!$ExtensionName) {
        $ExtensionName = Split-Path $SourcePath -Leaf
    }
    
    $destPath = Join-Path $Config.D_CEPDir $ExtensionName
    $cPath = Join-Path $Config.C_CEPDir $ExtensionName
    
    Write-Host "`n[安装CEP扩展] $ExtensionName" -ForegroundColor Cyan
    
    # 复制到D盘
    Write-Host "  复制到D盘..." -ForegroundColor Yellow
    Start-Process -FilePath "robocopy.exe" -ArgumentList "`"$SourcePath`" `"$destPath`" /E /COPY:DAT /R:3 /W:5 /NP /NFL /NDL" -Wait -NoNewWindow
    
    # 创建符号链接
    Write-Host "  创建符号链接..." -ForegroundColor Yellow
    if (Test-Path $cPath) {
        # 备份现有目录
        $bakPath = "$cPath.bak"
        if (Test-Path $bakPath) {
            Remove-Item $bakPath -Recurse -Force
        }
        Rename-Item $cPath "$ExtensionName.bak" -Force
    }
    
    $cmd = "mklink /J `"$cPath`" `"$destPath`""
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmd" -Wait -NoNewWindow
    
    Write-Host "  完成! $ExtensionName" -ForegroundColor Green
}

# 安装ScriptUI脚本到D盘
function Install-ScriptUI {
    param(
        [Parameter(Mandatory=$true)]
        [string]$SourcePath,
        
        [Parameter(Mandatory=$false)]
        [string]$ScriptName = $null
    )
    
    if (!(Test-Path $SourcePath)) {
        Write-Error "源路径不存在: $SourcePath"
        return
    }
    
    if (!$ScriptName) {
        $ScriptName = Split-Path $SourcePath -Leaf
    }
    
    $destPath = Join-Path $Config.D_ScriptUIDir $ScriptName
    
    Write-Host "`n[安装ScriptUI脚本] $ScriptName" -ForegroundColor Cyan
    
    if (Test-Path $SourcePath -PathType Container) {
        # 目录
        Start-Process -FilePath "robocopy.exe" -ArgumentList "`"$SourcePath`" `"$destPath`" /E /COPY:DAT /R:3 /W:5 /NP /NFL /NDL" -Wait -NoNewWindow
    } else {
        # 文件
        Copy-Item $SourcePath $destPath -Force
    }
    
    Write-Host "  完成! $ScriptName" -ForegroundColor Green
}

# 修复符号链接（如果链接损坏）
function Repair-SymbolicLinks {
    Write-Host "`n[修复符号链接]" -ForegroundColor Cyan
    
    # 检查CEP扩展
    $cepExtensions = Get-ChildItem $Config.D_CEPDir -Directory -ErrorAction SilentlyContinue
    foreach ($ext in $cepExtensions) {
        $cPath = Join-Path $Config.C_CEPDir $ext.Name
        if (!(Test-Path $cPath)) {
            Write-Host "  修复: $($ext.Name)" -ForegroundColor Yellow
            $cmd = "mklink /J `"$cPath`" `"$($ext.FullName)`""
            Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmd" -Wait -NoNewWindow
        }
    }
    
    # 检查ScriptUI Panels符号链接
    $scriptUIPath = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels"
    if (!(Test-Path $scriptUIPath) -or !((Get-Item $scriptUIPath -Force).Attributes -match "ReparsePoint")) {
        Write-Host "  修复: ScriptUI Panels" -ForegroundColor Yellow
        $scriptDir = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts"
        if (Test-Path "$scriptDir\ScriptUI Panels.bak") {
            Rename-Item "$scriptDir\ScriptUI Panels.bak" "ScriptUI Panels" -Force
        }
        $cmd = "cd /d `"$scriptDir`" && ren `"ScriptUI Panels`" `"ScriptUI Panels.bak`" && mklink /J `"ScriptUI Panels`" `"$($Config.D_ScriptUIDir)`""
        Start-Process -FilePath "cmd.exe" -ArgumentList "/c $cmd" -Wait -NoNewWindow
    }
    
    Write-Host "  修复完成!" -ForegroundColor Green
}

# 显示当前状态
function Show-Status {
    Write-Host "`n========== D盘AE脚本状态 ==========" -ForegroundColor Cyan
    
    Write-Host "`n[D盘CEP扩展]" -ForegroundColor Yellow
    Get-ChildItem $Config.D_CEPDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $size = (Get-ChildItem $_.FullName -Recurse -ErrorAction SilentlyContinue | Measure-Object -Property Length -Sum).Sum
        $sizeMB = [math]::Round($size / 1MB, 2)
        Write-Host "  $($_.Name) (${sizeMB} MB)"
    }
    
    Write-Host "`n[D盘ScriptUI脚本]" -ForegroundColor Yellow
    Get-ChildItem $Config.D_ScriptUIDir -ErrorAction SilentlyContinue | Group-Object Extension | ForEach-Object {
        Write-Host "  $($_.Name): $($_.Count) 个文件"
    }
    
    Write-Host "`n[C盘符号链接检查]" -ForegroundColor Yellow
    $cepItems = Get-ChildItem $Config.C_CEPDir -Force -ErrorAction SilentlyContinue | Where-Object { $_.Attributes -match "ReparsePoint" }
    Write-Host "  CEP Junction: $($cepItems.Count) 个"
    
    $scriptUIItem = Get-Item "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels" -Force -ErrorAction SilentlyContinue
    if ($scriptUIItem -and ($scriptUIItem.Attributes -match "ReparsePoint")) {
        Write-Host "  ScriptUI Panels: Junction 正常" -ForegroundColor Green
    } else {
        Write-Host "  ScriptUI Panels: 未链接" -ForegroundColor Red
    }
    
    Write-Host "`n==================================" -ForegroundColor Cyan
}

# 主菜单
function Show-Menu {
    Clear-Host
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "      D盘AE脚本管理器 v1.0" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  1. 安装CEP扩展到D盘"
    Write-Host "  2. 安装ScriptUI脚本到D盘"
    Write-Host "  3. 修复符号链接"
    Write-Host "  4. 查看当前状态"
    Write-Host "  5. 初始化目录结构"
    Write-Host "  0. 退出"
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
}

# 主程序
Initialize-Directories

# 如果带参数运行，直接执行对应功能
if ($args.Count -gt 0) {
    switch ($args[0]) {
        "install-cep" { Install-CEPExtension -SourcePath $args[1] -ExtensionName $args[2] }
        "install-ui"  { Install-ScriptUI -SourcePath $args[1] -ScriptName $args[2] }
        "repair"      { Repair-SymbolicLinks }
        "status"      { Show-Status }
        "init"        { Initialize-Directories }
        default       { Write-Host "未知命令: $($args[0])" -ForegroundColor Red }
    }
    exit
}

# 交互模式
while ($true) {
    Show-Menu
    $choice = Read-Host "请选择操作"
    
    switch ($choice) {
        "1" {
            $path = Read-Host "请输入CEP扩展源路径"
            $name = Read-Host "请输入扩展名称（留空自动获取）"
            if ($name -eq "") { $name = $null }
            Install-CEPExtension -SourcePath $path -ExtensionName $name
            Read-Host "`n按回车键继续"
        }
        "2" {
            $path = Read-Host "请输入ScriptUI脚本源路径"
            $name = Read-Host "请输入脚本名称（留空自动获取）"
            if ($name -eq "") { $name = $null }
            Install-ScriptUI -SourcePath $path -ScriptName $name
            Read-Host "`n按回车键继续"
        }
        "3" {
            Repair-SymbolicLinks
            Read-Host "`n按回车键继续"
        }
        "4" {
            Show-Status
            Read-Host "`n按回车键继续"
        }
        "5" {
            Initialize-Directories
            Read-Host "`n按回车键继续"
        }
        "0" { exit }
        default {
            Write-Host "无效选择!" -ForegroundColor Red
            Start-Sleep -Seconds 1
        }
    }
}
