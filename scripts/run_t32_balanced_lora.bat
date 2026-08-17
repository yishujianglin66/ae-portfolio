@echo off
cd /d C:\Users\Administrator\Desktop\AE-Knowledge-Vault
echo [%date% %time%] T32 balanced LoRA retrain started >> "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\logs\t32_balanced_lora.log"
C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe -m ai.t32_balanced_lora_retrain --train >> "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\logs\t32_balanced_lora.log" 2>&1
echo [%date% %time%] T32 exited with code %errorlevel% >> "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\logs\t32_balanced_lora.log"
