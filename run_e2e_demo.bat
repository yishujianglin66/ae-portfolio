@echo off
chcp 65001 >nul
title 端到端演示 (MCP模式)：音乐+视频 -> AE合成

echo ============================================
echo   端到端演示 (MCP模式)：音乐+视频 -> AE合成
echo ============================================
echo.
echo   架构：Python (音乐分析) + MCP Bridge (AE执行)
echo.
echo   前置条件：
echo     1. Adobe After Effects 2025 已启动
echo     2. 在 AE 中运行了 ae_mcp_listener.jsx
echo        (文件 -> 脚本 -> 运行脚本文件 -> ae_mcp_listener.jsx)
echo.
echo ============================================
echo.

set PYTHON=C:\Users\Administrator\AppData\Local\Programs\Python\Python311\python.exe
set SCRIPT=c:\Users\Administrator\Desktop\AE-Knowledge-Vault\e2e_demo_v26.py

echo [1/1] 运行端到端演示 (BGM分析 + MCP创建合成)...
"%PYTHON%" "%SCRIPT%"

echo.
pause
