@echo off
title Font Auto-Installer
echo ========================================
echo   Font Auto-Installer
echo   Click Yes on UAC prompt
echo ========================================
echo.

:: Check admin
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo Requesting admin rights...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

echo Admin confirmed.
echo.

:: Run the font installer
powershell -ExecutionPolicy Bypass -NoProfile -File "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\install_fonts.ps1"

echo.
echo Done.
pause
