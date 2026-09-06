@echo off
rem MasterCut E0-5b: DVC daily backup push (invoked by scheduled task 03:00)
rem Rationale: 2026-08-21 audit found "backup drive has no weight backups".
rem dvc push never happens automatically - this task institutionalizes it.
rem (ASCII-only comments: cmd default codepage GBK mis-parses UTF-8 Chinese)
cd /d C:\Users\Administrator\Desktop\AE-Knowledge-Vault
echo ====== %date% %time% DVC daily push ====== >> logs\dvc_push.log
dvc push >> logs\dvc_push.log 2>&1
dvc status >> logs\dvc_push.log 2>&1
echo exitcode=%errorlevel% >> logs\dvc_push.log
