@echo off
REM ============================================================
REM Switch After Effects 2025 language to English
REM 右键 -> 以管理员身份运行
REM ============================================================

echo.
echo ============================================================
echo   Switch After Effects 2025 to English
echo ============================================================
echo.

set "AMT_FILE=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AMT\application.xml"

if not exist "%AMT_FILE%" (
    echo [ERROR] File not found: %AMT_FILE%
    echo.
    pause
    exit /b 1
)

echo [INFO] Backing up original file...
copy "%AMT_FILE%" "%AMT_FILE%.backup"

echo [INFO] Changing language to en_GB...

REM Use PowerShell to do the replacement
powershell -Command "$content = Get-Content '%AMT_FILE%' -Raw; $content = $content -replace 'installedLanguages[^>]*>[^<]*<', 'installedLanguages>en_GB<'; Set-Content -Path '%AMT_FILE%' -Value $content -NoNewline"

if errorlevel 1 (
    echo [ERROR] Failed to modify file.
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] Language changed to English!
echo.
echo Restart After Effects for changes to take effect.
echo.
pause
