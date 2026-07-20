@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

set "SOURCE_DIR=D:\迅雷云盘"
set "INSTALL_ROOT=D:\app"
set "ADOBE_DIR=%INSTALL_ROOT%\Adobe"
set "AE_SCRIPTS_DIR=%INSTALL_ROOT%\AE-Scripts"
set "CEP_DIR=C:\Program Files (x86)\Common Files\Adobe\CEP\extensions"
set "AE2025_SCRIPTS=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts"

echo ========================================
echo   COMPLETE INSTALLATION TO D DRIVE
echo ========================================
echo.

:: Step 1: Create directories
echo [1/10] Creating directory structure...
if not exist "%INSTALL_ROOT%\Adobe" mkdir "%INSTALL_ROOT%\Adobe"
if not exist "%INSTALL_ROOT%\DaVinci Resolve" mkdir "%INSTALL_ROOT%\DaVinci Resolve"
echo   Done!
echo.

:: Step 2: Install BeatEdit AE (CEP extension)
echo [2/10] Installing BeatEdit AE...
if exist "%AE_SCRIPTS_DIR%\BeatEdit\beatedit_Ae_2_2_005" (
    if exist "%CEP_DIR%\beatedit_Ae_2_2_005" rmdir /s /q "%CEP_DIR%\beatedit_Ae_2_2_005"
    mklink /J "%CEP_DIR%\beatedit_Ae_2_2_005" "%AE_SCRIPTS_DIR%\BeatEdit\beatedit_Ae_2_2_005"
    echo   CEP link created
    for %%f in ("%AE_SCRIPTS_DIR%\BeatEdit\卡点脚本汉化AE版 BeatEdit V2.2.005\*.reg") do (
        reg import "%%f"
        echo   Registry imported
    )
) else (
    echo   BeatEdit AE directory not found
)
echo.

:: Step 3: Install Motion Tools Pro
echo [3/10] Installing Motion Tools Pro...
for /d %%d in ("%SOURCE_DIR%\AE脚本Motion Tools Pro*") do (
    for /d %%i in ("%%d\*") do (
        xcopy /s /e /y "%%i\*" "%AE_SCRIPTS_DIR%\Motion Tools Pro\"
        echo   Installed to: %AE_SCRIPTS_DIR%\Motion Tools Pro
        goto :mtp_done
    )
)
:mtp_done
echo.

:: Step 4: Install MotionSpice
echo [4/10] Installing MotionSpice...
for /d %%d in ("%SOURCE_DIR%\（英文版）AE脚本MG动画基本图形工具包*") do (
    for /d %%i in ("%%d\*") do (
        xcopy /s /e /y "%%i\*" "%AE_SCRIPTS_DIR%\MotionSpice\"
        echo   Installed to: %AE_SCRIPTS_DIR%\MotionSpice
        goto :ms_done
    )
)
:ms_done
echo.

:: Step 5: Install Motion Studio
echo [5/10] Installing Motion Studio...
for /d %%d in ("%SOURCE_DIR%\AE脚本英文MG动画关键帧多功能高级工具 Motion Studio*") do (
    for /d %%i in ("%%d\*") do (
        xcopy /s /e /y "%%i\*" "%AE_SCRIPTS_DIR%\Motion Studio\"
        echo   Installed to: %AE_SCRIPTS_DIR%\Motion Studio
        goto :mst_done
    )
)
:mst_done
echo.

:: Step 6: Install Adobe Photoshop 2025
echo [6/10] Installing Adobe Photoshop 2025...
for /r "%SOURCE_DIR%" %%f in ("*Photoshop*\Set-up.exe") do (
    echo   Launching installer...
    start /wait "Photoshop Install" "%%f" --installPath="%ADOBE_DIR%\Adobe Photoshop 2025"
    if !errorlevel! equ 0 (
        echo   Photoshop 2025 installed successfully!
    ) else (
        echo   Photoshop installation failed (code: !errorlevel!)
    )
    goto :ps_done
)
:ps_done
echo.

:: Step 7: Install Adobe Premiere Pro 2025
echo [7/10] Installing Adobe Premiere Pro 2025...
for /r "%SOURCE_DIR%" %%f in ("*Premiere*\Set-up.exe") do (
    echo   Launching installer...
    start /wait "Premiere Pro Install" "%%f" --installPath="%ADOBE_DIR%\Adobe Premiere Pro 2025"
    if !errorlevel! equ 0 (
        echo   Premiere Pro 2025 installed successfully!
    ) else (
        echo   Premiere Pro installation failed (code: !errorlevel!)
    )
    goto :pr_done
)
:pr_done
echo.

:: Step 8: Install Adobe Illustrator 2025
echo [8/10] Installing Adobe Illustrator 2025...
for /r "%SOURCE_DIR%" %%f in ("*Illustrator*\Set-up.exe") do (
    echo   Launching installer...
    start /wait "Illustrator Install" "%%f" --installPath="%ADOBE_DIR%\Adobe Illustrator 2025"
    if !errorlevel! equ 0 (
        echo   Illustrator 2025 installed successfully!
    ) else (
        echo   Illustrator installation failed (code: !errorlevel!)
    )
    goto :ai_done
)
:ai_done
echo.

:: Step 9: Install Adobe Media Encoder 2025
echo [9/10] Installing Adobe Media Encoder 2025...
for /r "%SOURCE_DIR%" %%f in ("*Media Encoder*\Set-up.exe") do (
    echo   Launching installer...
    start /wait "Media Encoder Install" "%%f" --installPath="%ADOBE_DIR%\Adobe Media Encoder 2025"
    if !errorlevel! equ 0 (
        echo   Media Encoder 2025 installed successfully!
    ) else (
        echo   Media Encoder installation failed (code: !errorlevel!)
    )
    goto :me_done
)
:me_done
echo.

:: Step 10: Install DaVinci Resolve Studio 21.0
echo [10/10] Installing DaVinci Resolve Studio 21.0...
for /r "%SOURCE_DIR%" %%f in ("Install Resolve*.exe") do (
    echo   Launching installer...
    start /wait "DaVinci Resolve Install" "%%f" /VERYSILENT /DIR="%INSTALL_ROOT%\DaVinci Resolve"
    if !errorlevel! equ 0 (
        echo   DaVinci Resolve installed successfully!
    ) else (
        echo   DaVinci Resolve installation failed (code: !errorlevel!)
    )
    
    :: Copy unlock tools
    for /d %%d in ("%SOURCE_DIR%\DaVinci Resolve*") do (
        for /d %%u in ("%%d\*解锁工具*") do (
            xcopy /s /e /y "%%u\*" "%INSTALL_ROOT%\DaVinci Resolve\"
            echo   Unlock tools copied
        )
    )
    goto :dr_done
)
:dr_done
echo.

:: Final setup
echo [FINAL] Configuring AE script links...
if not exist "%AE2026_SCRIPTS%\ScriptUI Panels\CustomScripts" (
    mklink /J "%AE2026_SCRIPTS%\ScriptUI Panels\CustomScripts" "%AE_SCRIPTS_DIR%\ScriptUI Panels"
    echo   ScriptUI link created
)

:: Copy JSX files
xcopy /s /e /y "%AE_SCRIPTS_DIR%\Motion Tools Pro\*.jsx" "%AE_SCRIPTS_DIR%\ScriptUI Panels\"
xcopy /s /e /y "%AE_SCRIPTS_DIR%\MotionSpice\*.jsx" "%AE_SCRIPTS_DIR%\ScriptUI Panels\"
xcopy /s /e /y "%AE_SCRIPTS_DIR%\Motion Studio\*.jsx" "%AE_SCRIPTS_DIR%\ScriptUI Panels\"
echo   JSX files copied

:: Set PlayerDebugMode
reg add "HKCU\Software\Adobe\CSXS.12" /v "PlayerDebugMode" /t REG_SZ /d "1" /f >nul
reg add "HKCU\Software\Adobe\CSXS.13" /v "PlayerDebugMode" /t REG_SZ /d "1" /f >nul
reg add "HKCU\Software\Adobe\CSXS.14" /v "PlayerDebugMode" /t REG_SZ /d "1" /f >nul
echo   PlayerDebugMode set
echo.

echo ========================================
echo   INSTALLATION COMPLETE!
echo ========================================
echo.
echo Installation Directory: %INSTALL_ROOT%
echo.
echo Installed Software:
echo [AE Scripts]
for /d %%d in ("%AE_SCRIPTS_DIR%\*") do (
    dir "%%d" /s /b | find /c /v "" > tmp_count.txt
    set /p count=<tmp_count.txt
    echo   - %%~nd: !count! files
)
del tmp_count.txt
echo [Adobe Apps]
for /d %%d in ("%ADOBE_DIR%\*") do (
    echo   - %%~nd
)
echo [DaVinci Resolve]
echo   - DaVinci Resolve Studio 21.0
echo.
echo Next Steps:
echo   1. Open AE -^> Window -^> Extensions -^> BeatEdit
echo   2. Enable Edit -^> Preferences -^> Scripting & Expressions
echo      -^> Allow Scripts to Write Files and Access Network
echo   3. Run unlock tools for DaVinci Resolve
echo.
pause
