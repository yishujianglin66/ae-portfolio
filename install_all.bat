@echo off
echo ============================================
echo AE脚本扩展安装程序 v1.0
echo 以管理员身份运行此脚本
echo ============================================

setlocal enabledelayedexpansion

set "CEPDIR=C:\Program Files (x86)\Common Files\Adobe\CEP\extensions"
set "SCRIPTDIR=C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels"
set "SOURCEDIR=D:\迅雷云盘"

echo.
echo [1/6] 创建目录结构...
if not exist "%CEPDIR%" mkdir "%CEPDIR%"
if not exist "%SCRIPTDIR%" mkdir "%SCRIPTDIR%"
if not exist "D:\app\AE-Scripts" mkdir "D:\app\AE-Scripts"
if not exist "D:\app\AE-Scripts\CEP" mkdir "D:\app\AE-Scripts\CEP"
if not exist "D:\app\AE-Scripts\ScriptUI" mkdir "D:\app\AE-Scripts\ScriptUI"

echo.
echo [2/6] 安装BeatEdit CEP扩展...
robocopy "%SOURCEDIR%\卡点脚本汉化AE版 BeatEdit V2.2.005\卡点脚本汉化AE版 BeatEdit V2.2.005\beatedit_Ae_2_2_005" "%CEPDIR%\beatedit_Ae_2_2_005" /E /COPYALL /R:3 /W:5 /NP
robocopy "%SOURCEDIR%\卡点脚本汉化AE版 BeatEdit V2.2.005\卡点脚本汉化AE版 BeatEdit V2.2.005\beatedit_Ae_2_2_005" "D:\app\AE-Scripts\CEP\beatedit_Ae_2_2_005" /E /COPYALL /R:3 /W:5 /NP

echo.
echo [3/6] 安装Motion Tools Pro CEP扩展...
robocopy "%SOURCEDIR%\AE脚本Motion Tools Pro 2.1.1 英文版\AE脚本Motion Tools Pro 2.1.1 英文版\motion tools pro" "%CEPDIR%\motion_tools_pro" /E /COPYALL /R:3 /W:5 /NP
robocopy "%SOURCEDIR%\AE脚本Motion Tools Pro 2.1.1 英文版\AE脚本Motion Tools Pro 2.1.1 英文版\motion tools pro" "D:\app\AE-Scripts\CEP\motion_tools_pro" /E /COPYALL /R:3 /W:5 /NP

echo.
echo [4/6] 安装MotionSpice脚本...
robocopy "%SOURCEDIR%\(英文版)AE脚本MG动画基本图形工具包预设库 MotionSpice V2.0.3\(英文版)AE脚本MG动画基本图形工具包预设库 MotionSpice V2.0.3\MotionSpice" "%SCRIPTDIR%\MotionSpice" /E /COPYALL /R:3 /W:5 /NP
robocopy "%SOURCEDIR%\(英文版)AE脚本MG动画基本图形工具包预设库 MotionSpice V2.0.3\(英文版)AE脚本MG动画基本图形工具包预设库 MotionSpice V2.0.3\MotionSpice" "D:\app\AE-Scripts\ScriptUI\MotionSpice" /E /COPYALL /R:3 /W:5 /NP

echo.
echo [5/6] 安装Motion Studio CEP扩展...
robocopy "%SOURCEDIR%\AE脚本英文MG动画关键帧多功能高级工具 Motion Studio V1.2.5\AE脚本英文MG动画关键帧多功能高级工具 Motion Studio V1.2.5\motion-studio-v1.2.5.5216" "%CEPDIR%\motion-studio-v1.2.5.5216" /E /COPYALL /R:3 /W:5 /NP
robocopy "%SOURCEDIR%\AE脚本英文MG动画关键帧多功能高级工具 Motion Studio V1.2.5\AE脚本英文MG动画关键帧多功能高级工具 Motion Studio V1.2.5\motion-studio-v1.2.5.5216" "D:\app\AE-Scripts\CEP\motion-studio-v1.2.5.5216" /E /COPYALL /R:3 /W:5 /NP

echo.
echo [6/6] 配置注册表 PlayerDebugMode...
reg add "HKEY_CURRENT_USER\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_SZ /d 1 /f
reg add "HKEY_LOCAL_MACHINE\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_SZ /d 1 /f

echo.
echo ============================================
echo 安装完成！
echo ============================================
echo.
echo 安装目录：
echo   CEP扩展: %CEPDIR%
echo   ScriptUI脚本: %SCRIPTDIR%
echo   D盘备份: D:\app\AE-Scripts
echo.
echo 请重启After Effects后使用脚本。
pause