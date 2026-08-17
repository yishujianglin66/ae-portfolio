@echo off
REM ============================================================
REM Deploy After Effects MCP Bridge Panel (from open-source project)
REM Right-click -> Run as administrator
REM ============================================================

echo.
echo ============================================================
echo   Deploy AE MCP Bridge Panel (Open Source Version)
echo ============================================================
echo.

set "SOURCE=C:\Users\Administrator\Desktop\after-effects-mcp-main\build\scripts\mcp-bridge-auto.jsx"
set "TARGET=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels\mcp-bridge-auto.jsx"

if not exist "%SOURCE%" (
    echo [ERROR] Source file not found: %SOURCE%
    echo.
    pause
    exit /b 1
)

echo [INFO] Source: %SOURCE%
echo [INFO] Target: %TARGET%
echo.

if not exist "%~dp0..\ScriptUI Panels" (
    mkdir "%~dp0..\ScriptUI Panels"
)

copy /Y "%SOURCE%" "%TARGET%"

if errorlevel 1 (
    echo.
    echo [ERROR] Copy failed!
    echo Please right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Panel deployed successfully!
echo.
echo Next steps:
echo   1. Open After Effects
echo   2. Go to: Edit ^> Preferences ^> Scripting & Expressions
echo   3. Enable: "Allow Scripts to Write Files and Access Network"
echo   4. Restart After Effects
echo   5. Open panel: Window ^> mcp-bridge-auto.jsx
echo   6. Dock the panel and make sure "Auto-run commands" is enabled
echo.
pause
