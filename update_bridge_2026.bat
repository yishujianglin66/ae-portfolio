@echo off
chcp 65001 >nul
title AE 2025 MCP Bridge 更新工具
echo ==========================================
echo   AE 2025 MCP Bridge 更新工具 v1.0
echo ==========================================
echo.

set sourcePath=C:\Users\Administrator\Desktop\AE-Knowledge-Vault\mcp-bridge-auto.jsx
set targetPath=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels\mcp-bridge-auto.jsx
set backupPath=%targetPath%.bak

if not exist "%sourcePath%" (
    echo [错误] 源文件不存在: %sourcePath%
    echo 请确保 bridge 文件在正确位置
    pause
    exit /b 1
)

echo [信息] 准备更新 AE 2025 MCP Bridge...
echo [信息] 源文件: %sourcePath%
echo [信息] 目标文件: %targetPath%
echo.

echo [信息] 创建备份...
if exist "%targetPath%" (
    copy /Y "%targetPath%" "%backupPath%" >nul
    echo [成功] 备份已创建: %backupPath%
) else (
    echo [信息] 目标文件不存在，跳过备份
)

echo.
echo [信息] 复制更新文件...
copy /Y "%sourcePath%" "%targetPath%" >nul
if %errorlevel% == 0 (
    echo [成功] 更新完成!
    echo.
    echo ==========================================
    echo   更新成功! 请重启 AE 2025 使更改生效
    echo ==========================================
) else (
    echo [错误] 更新失败，请尝试以管理员身份运行此脚本
    echo.
    echo [提示] 或者手动复制:
    echo   从: %sourcePath%
    echo   到: %targetPath%
)

echo.
pause
