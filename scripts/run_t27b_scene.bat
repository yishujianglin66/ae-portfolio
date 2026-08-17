@echo off
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
echo [T27b] 场景分类器训练启动...
"C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe" "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ai\t27b_scene_classifier_train.py"
echo [T27b] 训练完成，退出码: %errorlevel%
pause
