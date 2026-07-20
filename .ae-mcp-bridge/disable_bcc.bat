@echo off
set "BCC_DIR=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Plug-ins\Continuum Plug-ins"
set "DISABLED_DIR=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Plug-ins\Continuum Plug-ins_disabled"
set "LOG=C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\bcc_status.log"

echo [%date% %time%] BCC toggle operation > "%LOG%"

if exist "%DISABLED_DIR%" (
    echo BCC already disabled, re-enabling... >> "%LOG%"
    rmdir /s /q "%BCC_DIR%" 2>nul
    rename "%DISABLED_DIR%" "Continuum Plug-ins"
    if exist "%BCC_DIR%" (
        echo BCC re-enabled successfully >> "%LOG%"
    ) else (
        echo ERROR: Failed to re-enable BCC >> "%LOG%"
    )
) else (
    if exist "%BCC_DIR%" (
        echo Disabling BCC folder... >> "%LOG%"
        rename "%BCC_DIR%" "Continuum Plug-ins_disabled"
        if exist "%DISABLED_DIR%" (
            echo BCC disabled successfully >> "%LOG%"
        ) else (
            echo ERROR: Failed to disable BCC >> "%LOG%"
        )
    ) else (
        echo BCC folder not found >> "%LOG%"
    )
)

echo. >> "%LOG%"
echo Current state: >> "%LOG%"
dir "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Plug-ins" /b /ad | findstr /i "Continuum" >> "%LOG%" 2>&1
