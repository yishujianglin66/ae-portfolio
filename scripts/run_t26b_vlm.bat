@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo [T26b] VLM全量标注启动...
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ai\t26b_vlm_full_annotation.py"
echo [T26b] 标注完成，退出码: %errorlevel%
pause
