@echo off
chcp 65001 >nul
title OpenAI Codex CLI
cd /d "%~dp0"
echo ========================================
echo   OpenAI Codex CLI - 启动中
echo ========================================
echo.
echo 工作目录: %cd%
echo 默认模型: gpt-5.5 (duckmiss_gpt)
echo 生图模型: gpt-image-2 (CLI fallback 模式)
echo.
echo 提示:
echo   - 输入 codex 进入交互模式
echo   - 输入 codex exec "问题" 单次执行
echo   - 输入 exit 退出
echo ========================================
echo.
powershell -NoExit -Command "& 'C:\Users\Administrator\AppData\Roaming\npm\codex.cmd' --skip-git-repo-check"
