@echo off
chcp 65001 >nul
title PR Bridge - Premiere Pro 自动化桥接
cd /d "%~dp0.."

echo ============================================================
echo   PR Bridge 启动器
echo ============================================================
echo.

:: 1. 检查 PR 是否运行
tasklist /FI "IMAGENAME eq Adobe Premiere Pro.exe" 2>nul | find /i "Adobe Premiere Pro.exe" >nul
if %errorlevel%==0 (
    echo [✅] Premiere Pro 已在运行
) else (
    echo [🔄] 正在启动 Premiere Pro...
    start "" "D:\Pr25\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe"
    echo [⏳] 等待 PR 启动 (20秒)...
    ping -n 21 127.0.0.1 >nul
)

:: 2. 检查桥接目录
if exist ".premiere-mcp-bridge" (
    echo [✅] 桥接目录已存在
) else (
    echo [📁] 创建桥接目录...
    mkdir .premiere-mcp-bridge
)

:: 3. 检查 CEP 插件
if exist "%APPDATA%\Adobe\CEP\extensions\MCPBridgeCEP\CSXS\manifest.xml" (
    echo [✅] CEP 插件已安装
) else (
    echo [⚠️] CEP 插件未安装
    echo     请运行: python setup_premiere_mcp.py
)

:: 4. 检查素材
set MEDIA_COUNT=0
for %%f in (data\stock_footage\*.mp4 data\stock_footage\*.mov data\stock_footage\*.avi) do (
    set /a MEDIA_COUNT+=1
)
if %MEDIA_COUNT% GTR 0 (
    echo [✅] 素材文件: %MEDIA_COUNT% 个
) else (
    echo [⚠️] 无素材文件
    echo     请将素材放入: data\stock_footage\
)

echo.
echo ------------------------------------------------------------
echo   准备就绪！请检查：
echo   1. Premiere Pro 已打开并创建/打开了一个项目
echo   2. MCP Bridge 插件已自动运行 (窗口 ^> 扩展 ^> MCP Bridge)
echo   3. 桥接目录: .premiere-mcp-bridge
echo.
echo   运行自动剪辑:
echo     python scripts\pr_auto_edit.py
echo.
echo   测试桥接连接:
echo     python -m puppet_automation.src.engines.premiere.pr_bridge_client
echo ------------------------------------------------------------
echo.

pause