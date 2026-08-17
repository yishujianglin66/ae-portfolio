@echo off
echo === Adding AE to Windows Defender Exclusions (Admin Required) ===
echo.

powershell -Command "Add-MpPreference -ExclusionPath 'C:\Program Files\Adobe\Adobe After Effects 2026'"
powershell -Command "Add-MpPreference -ExclusionPath 'C:\Program Files\Adobe\Adobe After Effects 2025'"
if %errorlevel% equ 0 (
    echo [OK] Added AE installation folder
) else (
    echo [FAIL] Could not add AE folder
)

powershell -Command "Add-MpPreference -ExclusionPath 'C:\Users\Administrator\AppData\Roaming\Adobe\After Effects'"
if %errorlevel% equ 0 (
    echo [OK] Added AE preferences folder
) else (
    echo [FAIL] Could not add preferences folder
)

powershell -Command "Add-MpPreference -ExclusionProcess 'AfterFX.exe'"
if %errorlevel% equ 0 (
    echo [OK] Added AfterFX.exe process exclusion
) else (
    echo [FAIL] Could not add process exclusion
)

echo.
echo === Verifying Exclusions ===
powershell -Command "Get-MpPreference | Select-Object -ExpandProperty ExclusionPath"

echo.
echo Done! You can close this window.
timeout /t 5
