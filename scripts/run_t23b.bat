@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo [T23b] 训练启动...
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ai\t23b_lora_retrain_vitl14.py" > "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\logs\t23b_train.log" 2>&1
echo [T23b] 训练完成，退出码: %errorlevel%
pause
