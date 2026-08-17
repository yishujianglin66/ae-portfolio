@echo off
REM ============================================================
REM Deploy MCP Bridge Panel to AE ScriptUI Panels
REM 右键 -> 以管理员身份运行
REM ============================================================

echo.
echo ============================================================
echo   Deploy MCP Bridge Panel to After Effects 2025
echo ============================================================
echo.

set "SRC=%~dp0mcp_bridge_panel.jsx"
set "DST=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels\mcp_bridge_panel.jsx"

if not exist "%SRC%" (
    echo [ERROR] Source file not found: %SRC%
    echo.
    pause
    exit /b 1
)

echo [INFO] Source: %SRC%
echo [INFO] Dest:   %DST%
echo.

copy /Y "%SRC%" "%DST%"
if errorlevel 1 (
    echo.
    echo [ERROR] Copy failed! Make sure you run this as Administrator.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Panel deployed successfully!
echo.
echo Next steps:
echo   1. Restart After Effects (if running)
echo   2. In AE menu: Window ^> mcp_bridge_panel.jsx
echo   3. Dock the panel wherever you like
echo   4. Panel will auto-start Listener when opened
echo   5. After docking, AE remembers it on next launch
echo.
pause
