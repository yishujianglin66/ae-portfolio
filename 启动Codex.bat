@echo off
chcp 65001 >nul
cd /d "C:\Users\Administrator\Desktop\AE-Knowledge-Vault"
powershell -NoExit -Command "& 'C:\Users\Administrator\AppData\Roaming\npm\codex.cmd' --skip-git-repo-check"
