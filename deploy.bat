@echo off
setlocal enabledelayedexpansion

:: ============================================================
:: AE-Knowledge-Vault 一键部署脚本
:: ============================================================
:: 使用方式：
::   1. 确保已安装 Python 3.11+ 和 Adobe 全家桶
::   2. 在项目根目录运行此脚本
::   3. 根据提示选择要启动的服务
:: ============================================================

set "PROJECT_ROOT=%~dp0"
set "VENV_DIR=%PROJECT_ROOT%puppet-automation\venv"
set "PYTHON=%VENV_DIR%\Scripts\python.exe"
set "UVICORN=%VENV_DIR%\Scripts\uvicorn.exe"

echo.
echo ============================================================
echo     AE-Knowledge-Vault 一键部署脚本
echo ============================================================
echo.

:: 检查 Python 虚拟环境
if not exist "%VENV_DIR%" (
    echo [ERROR] 虚拟环境不存在，请先安装依赖：
    echo.
    echo   cd puppet-automation
    echo   python -m venv venv
    echo   venv\Scripts\pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    echo.
    pause
    exit /b 1
)

echo [OK] 虚拟环境已就绪：%VENV_DIR%
echo.

:: 菜单
:MENU
echo ==================== 服务管理菜单 ====================
echo.
echo   1. 启动 API 服务（FastAPI + 16引擎）
echo   2. 启动 AE MCP Bridge（需先打开 AE）
echo   3. 启动 Premiere MCP Bridge（需先打开 PR）
echo   4. 启动 Photoshop MCP Bridge（需先打开 PS）
echo   5. 启动 Audition MCP Bridge（需先打开 AU）
echo   6. 启动全部服务（API + 所有 Bridge）
echo   7. 运行端到端测试
echo   8. 检查环境配置
echo   0. 退出
echo.
set /p "choice=请输入选择 [0-8]: "

if "%choice%"=="1" goto START_API
if "%choice%"=="2" goto START_AE_BRIDGE
if "%choice%"=="3" goto START_PR_BRIDGE
if "%choice%"=="4" goto START_PS_BRIDGE
if "%choice%"=="5" goto START_AU_BRIDGE
if "%choice%"=="6" goto START_ALL
if "%choice%"=="7" goto RUN_TEST
if "%choice%"=="8" goto CHECK_ENV
if "%choice%"=="0" goto EXIT

echo [ERROR] 无效选择，请重新输入
echo.
goto MENU

:: ------------------------------------------------------------
:: 启动 API 服务
:: ------------------------------------------------------------
:START_API
echo.
echo [INFO] 启动 API 服务（端口 8765）...
echo.

cd /d "%PROJECT_ROOT%puppet-automation"
start "AEKV API Server" "%UVICORN%" src.api.main:app --host 127.0.0.1 --port 8765 --log-level info

echo [OK] API 服务已启动，请访问 http://localhost:8765
echo      可用端点：
echo      - GET  /api/health          健康检查
echo      - GET  /api/engines          引擎列表
echo      - GET  /api/engine/{name}    引擎详情
echo      - POST /api/engine/{name}/execute  执行引擎命令
echo.
pause
goto MENU

:: ------------------------------------------------------------
:: 启动 AE MCP Bridge
:: ------------------------------------------------------------
:START_AE_BRIDGE
echo.
echo [INFO] 启动 AE MCP Bridge...
echo [INFO] 请确保 Adobe After Effects 2025 已打开
echo.
echo [INFO] 打开 AE 后，请手动运行脚本：
echo        File > Scripts > Run Script File...
echo        选择：%PROJECT_ROOT%ae_mcp_bridge_v26.jsx
echo.
pause
goto MENU

:: ------------------------------------------------------------
:: 启动 Premiere MCP Bridge
:: ------------------------------------------------------------
:START_PR_BRIDGE
echo.
echo [INFO] 启动 Premiere MCP Bridge...
echo [INFO] 请确保 Adobe Premiere Pro 2025 已打开
echo.
echo [INFO] 打开 PR 后，请手动运行脚本：
echo        File > Scripts > Run Script File...
echo        选择：%PROJECT_ROOT%pr_mcp_bridge.jsx
echo.
pause
goto MENU

:: ------------------------------------------------------------
:: 启动 Photoshop MCP Bridge
:: ------------------------------------------------------------
:START_PS_BRIDGE
echo.
echo [INFO] 启动 Photoshop MCP Bridge...
echo [INFO] 请确保 Adobe Photoshop 2025 已打开
echo.
echo [INFO] 打开 PS 后，请手动运行脚本：
echo        File > Scripts > Browse...
echo        选择：%PROJECT_ROOT%ps_mcp_bridge.jsx
echo.
pause
goto MENU

:: ------------------------------------------------------------
:: 启动 Audition MCP Bridge
:: ------------------------------------------------------------
:START_AU_BRIDGE
echo.
echo [INFO] 启动 Audition MCP Bridge...
echo [INFO] 请确保 Adobe Audition 2025 已打开
echo.
echo [INFO] 打开 AU 后，请手动运行脚本：
echo        File > Scripts > Run Script File...
echo        选择：%PROJECT_ROOT%au_mcp_bridge.jsx
echo.
pause
goto MENU

:: ------------------------------------------------------------
:: 启动全部服务
:: ------------------------------------------------------------
:START_ALL
echo.
echo [INFO] 启动全部服务...
echo.

:: 启动 API 服务
cd /d "%PROJECT_ROOT%puppet-automation"
start "AEKV API Server" "%UVICORN%" src.api.main:app --host 127.0.0.1 --port 8765 --log-level info

echo [OK] API 服务已启动
echo.

:: 提示用户启动 Bridge
echo [INFO] 请手动启动各软件的 MCP Bridge：
echo.
echo   1. Adobe After Effects 2025
echo      运行：ae_mcp_bridge_v26.jsx
echo.
echo   2. Adobe Premiere Pro 2025
echo      运行：pr_mcp_bridge.jsx
echo.
echo   3. Adobe Photoshop 2025
echo      运行：ps_mcp_bridge.jsx
echo.
echo   4. Adobe Audition 2025
echo      运行：au_mcp_bridge.jsx
echo.
echo [INFO] 全部 Bridge 启动后，运行"7. 运行端到端测试"验证
echo.
pause
goto MENU

:: ------------------------------------------------------------
:: 运行端到端测试
:: ------------------------------------------------------------
:RUN_TEST
echo.
echo [INFO] 运行端到端测试...
echo.

cd /d "%PROJECT_ROOT%puppet-automation"
"%PYTHON%" ..\test_deploy.py

echo.
pause
goto MENU

:: ------------------------------------------------------------
:: 检查环境配置
:: ------------------------------------------------------------
:CHECK_ENV
echo.
echo ==================== 环境配置检查 ====================
echo.

echo [检查] Python 虚拟环境...
if exist "%VENV_DIR%" (
    echo [OK] 虚拟环境已就绪
) else (
    echo [FAIL] 虚拟环境不存在
)

echo.
echo [检查] 引擎路径...
"%PYTHON%" -c "
import sys
sys.path.insert(0, '.')
from src.config.settings import get_settings
s = get_settings()
print(f'AE: {s.aerender_path}')
print(f'ME: {s.media_encoder_path}')
print(f'PR: {s.premiere_path}')
print(f'PS: {s.photoshop_path}')
print(f'AU: {s.audition_path}')
print(f'FFmpeg: {s.ffmpeg_path}')
"

echo.
pause
goto MENU

:: ------------------------------------------------------------
:: 退出
:: ------------------------------------------------------------
:EXIT
echo.
echo [INFO] 感谢使用 AE-Knowledge-Vault！
echo.
exit /b 0
