@echo off
rem DSH Web service registration (2026-08-15)
rem Usage: right-click -> "Run as administrator"
rem Effect: DSH Web GUI auto-starts at login + watchdog restarts if crashed

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Please right-click and choose "Run as administrator"
    pause
    exit /b 1
)

set PS_CMD=C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe
set SCRIPT=C:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts\dsh_service.ps1

rem 1. Auto-start at user login (correct user env for npm)
schtasks /create /tn "DSH-Web-AutoStart" /tr "%PS_CMD% -ExecutionPolicy Bypass -WindowStyle Hidden -File %SCRIPT%" /sc onlogon /f
if %errorlevel% equ 0 (echo [OK] DSH-Web-AutoStart registered) else (echo [WARN] AutoStart register failed)

rem 2. Watchdog every 5 min (restart if port 3080 down)
schtasks /create /tn "DSH-Web-Watchdog" /tr "%PS_CMD% -ExecutionPolicy Bypass -WindowStyle Hidden -File %SCRIPT%" /sc minute /mo 5 /f
if %errorlevel% equ 0 (echo [OK] DSH-Web-Watchdog registered) else (echo [WARN] Watchdog register failed)

echo.
echo Done. DSH Web will auto-start at login and self-heal every 5 minutes.
pause