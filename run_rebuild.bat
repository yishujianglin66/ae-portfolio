@echo off
chcp 65001 >nul
echo ============================================
echo 一拳超人项目重建一键运行脚本
echo ============================================
echo.
echo 正在启动AE并运行重建脚本...
echo.
echo 注意: 请确保Adobe After Effects 2025已安装
echo 并已打开一个AE项目文件
echo.

start "" "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"

echo 等待AE启动...
timeout /t 15 /nobreak >nul

echo 运行重建脚本: onepunch_rebuild_v6.jsx
echo.

echo 脚本已准备就绪，请在AE中通过"文件>运行脚本"
echo 运行以下文件:
echo.
echo   %~dp0onepunch_rebuild_v6.jsx
echo.
echo 运行完成后，运行验证脚本:
echo.
echo   %~dp0verify_project.jsx
echo.
echo 或者运行端到端测试:
echo.
echo   %~dp0full_pipeline_test.jsx
echo.

pause