@echo off
rem AEKV-Daily-Disk-Cleanup task registration (2026-08-15)
rem Usage: right-click this file -> "Run as administrator"
rem Effect: auto disk cleanup every day at 03:00

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Please right-click and choose "Run as administrator"
    pause
    exit /b 1
)

schtasks /create /tn "AEKV-Daily-Disk-Cleanup" /tr "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts\run_daily_cleanup.bat" /sc daily /st 03:00 /f

if %errorlevel% equ 0 (
    echo [OK] Task registered: daily cleanup at 03:00
    echo [OK] Triggering one run now to verify...
    schtasks /run /tn "AEKV-Daily-Disk-Cleanup"
) else (
    echo [ERROR] Registration failed, check permissions
)
pause