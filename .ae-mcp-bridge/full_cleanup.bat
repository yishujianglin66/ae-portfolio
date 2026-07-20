@echo off
set "AE_PREF=C:\Users\Administrator\AppData\Roaming\Adobe\After Effects"
set "LOG=C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\cleanup_status.log"

echo [%date% %time%] Full cleanup started > "%LOG%"

REM Kill AE if running
taskkill /f /im AfterFX.exe 2>nul
echo Killed AfterFX >> "%LOG%"

timeout /t 3 /nobreak >nul

REM Rename 25.3 folder (corrupted by force-kill)
if exist "%AE_PREF%\25.3" (
    set "suffix=%random%"
    ren "%AE_PREF%\25.3" "25.3_corrupted_%random%"
    if exist "%AE_PREF%\25.3" (
        echo ERROR: Failed to rename 25.3 >> "%LOG%"
    ) else (
        echo Renamed 25.3 to 25.3_corrupted >> "%LOG%"
    )
) else (
    echo 25.3 folder not found >> "%LOG%"
)

REM Re-enable BCC folder
set "BCC_DIR=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Plug-ins\Continuum Plug-ins"
set "DISABLED_DIR=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Plug-ins\Continuum Plug-ins_disabled"
if exist "%DISABLED_DIR%" (
    ren "%DISABLED_DIR%" "Continuum Plug-ins"
    if exist "%BCC_DIR%" (
        echo BCC re-enabled >> "%LOG%"
    ) else (
        echo ERROR: Failed to re-enable BCC >> "%LOG%"
    )
) else (
    echo BCC folder already in normal state >> "%LOG%"
)

echo. >> "%LOG%"
echo Cleanup completed at %time% >> "%LOG%"
echo. >> "%LOG%"
echo Current AE preference folders: >> "%LOG%"
dir "%AE_PREF%" /b /ad >> "%LOG%" 2>&1
echo. >> "%LOG%"
echo Current BCC state: >> "%LOG%"
dir "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Plug-ins" /b /ad | findstr /i "Continuum" >> "%LOG%" 2>&1
