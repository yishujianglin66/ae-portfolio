@echo off
chcp 65001 >nul
title AE 音频驱动自动化工具箱

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║       AE 音频驱动自动化 - 一键启动工具箱                  ║
echo ║       Phase 2 经验沉淀 + V4 深度优化                      ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: 检查前置条件
echo [前置检查]
echo.

:: 检查 Python
py -3.11 --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Python 3.11 未找到，请先安装
    pause
    exit /b 1
) else (
    echo ✓ Python 3.11 已就绪
)

:: 检查 librosa
py -3.11 -c "import librosa; print(librosa.__version__)" >nul 2>&1
if errorlevel 1 (
    echo ⚠ librosa 未安装，正在安装...
    py -3.11 -m pip install librosa numpy -q
)
echo ✓ librosa 已就绪

:: 检查音频文件
if not exist "input.wav" (
    if not exist "input.mp3" (
        echo.
        echo ⚠ 未找到 input.wav 或 input.mp3
        echo   请将音频文件放置在当前目录并命名为 input.wav
        echo.
    ) else (
        echo ✓ 音频文件: input.mp3
    )
) else (
    echo ✓ 音频文件: input.wav
)

echo.
echo ══════════════════════════════════════════════════════════
echo  使用说明
echo ══════════════════════════════════════════════════════════
echo.
echo  1. 确保 AE 已打开目标项目
echo  2. 确保 ae_mcp_auto_listener.jsx 已加载（AE会自动加载）
echo  3. 将音频文件命名为 input.wav 放在当前目录
echo.
echo  4. 执行步骤:
echo     - 步骤1: 音频分析（Python + librosa）
echo     - 步骤2: AE预检（在AE中运行脚本）
echo     - 步骤3: 生成关键帧（自动写入AE）
echo     - 步骤4: 渲染输出
echo.
echo ══════════════════════════════════════════════════════════
echo.

set /p choice="是否开始执行? (Y/N): "
if /i not "%choice%"=="Y" (
    echo 已取消
    pause
    exit /b 0
)

echo.
echo [步骤 1/4] 音频分析...
echo.

if exist "input.wav" (
    set AUDIO_FILE=input.wav
) else (
    set AUDIO_FILE=input.mp3
)

py -3.11 phase2_optimized.py --audio %AUDIO_FILE%

if errorlevel 1 (
    echo.
    echo ✗ 音频分析失败，请检查音频文件格式
    pause
    exit /b 1
)

echo.
echo ✓ 音频分析完成
echo.
echo [步骤 2/4] AE 预检...
echo.
echo 请在 AE 中手动运行以下脚本:
echo   10-风格化剪辑知识库\Phase3-音频驱动自动化\scripts\check_before_run.jsx
echo.
echo 或通过 Python 调用:
echo   py -3.11 -c "import sys; sys.path.insert(0, r'C:\Users\Administrator\Desktop\AE-Knowledge-Vault'); from ae_mcp_client import AECommandClient; c = AECommandClient(); print(c.send_command('executeAtomScript', {'script': open(r'10-风格化剪辑知识库\Phase3-音频驱动自动化\scripts\check_before_run.jsx').read()}))"
echo.

set /p continue="预检通过后继续? (Y/N): "
if /i not "%continue%"=="Y" (
    echo 已暂停
    pause
    exit /b 0
)

echo.
echo [步骤 3/4] 验证关键帧写入...
echo.

py -3.11 verify_phase2_run.py

echo.
echo [步骤 4/4] 渲染输出...
echo.
echo 请在 AE 中手动添加到渲染队列并渲染
echo 输出路径: D:\AE-Work\output\E2E_VinlandSaga_Phase2.mp4
echo.

echo ══════════════════════════════════════════════════════════
echo  完成
echo ══════════════════════════════════════════════════════════
echo.
echo  输出视频: D:\AE-Work\output\E2E_VinlandSaga_Phase2.mp4
echo  经验文档: 10-风格化剪辑知识库\Phase2实战经验总结.md
echo  配置模板: 10-风格化剪辑知识库\Phase3-音频驱动自动化\config\beat_config.json
echo.
echo  下次实战:
echo    1. 修改 beat_config.json 调整参数
echo    2. 准备音频文件 (建议 >30秒)
echo    3. 运行此脚本
echo.

pause