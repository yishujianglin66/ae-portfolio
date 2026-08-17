@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set VLM_WORKERS=16

:restart
echo [%date% %time%] T26c VLM并发标注启动 (16线程)...
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ai\t26c_vlm_concurrent.py"
set EXITCODE=%errorlevel%

if %EXITCODE% neq 0 (
    echo [%date% %time%] 进程异常退出 (code=%EXITCODE%)，5秒后自动重启...
    timeout /t 5 /nobreak >nul
    goto restart
)

echo [%date% %time%] 标注全部完成！
pause
