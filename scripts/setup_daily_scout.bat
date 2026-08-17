@echo off
:: 右键"以管理员身份运行"此文件
:: 创建 DSH 插件生态每日侦察定时任务 (每天 09:00)

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Please right-click and "Run as Administrator"
    pause
    exit /b 1
)

schtasks /create /tn "DSH-Plugin-Scout" /tr "py -3.12 c:\Users\Administrator\Desktop\AE-Knowledge-Vault\scripts\dsh_plugin_scout.py" /sc daily /st 09:00 /f /rl highest
if %errorlevel% equ 0 (
    echo [OK] Task "DSH-Plugin-Scout" created - runs daily at 09:00
) else (
    echo [FAIL] Could not create task
)
echo.
echo To remove: schtasks /delete /tn "DSH-Plugin-Scout" /f
echo To run now: schtasks /run /tn "DSH-Plugin-Scout"
pause