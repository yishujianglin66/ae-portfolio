@echo off
chcp 65001 >nul
REM ============================================================
REM 包2 - 任务A: ToriiGate 全库氛围标注 (全量)
REM 用途: 对 18235 镜头全量标注 mood/time/atmosphere 三维度
REM 预计耗时: 1-2 小时 (5090 单卡, ~3-5 镜头/秒)
REM 支持断点续跑: 中断后再跑会自动跳过已标注
REM ============================================================

setlocal
cd /d "%~dp0"

echo === 包2 任务A 全量: ToriiGate 氛围标注 ===
echo 预计 1-2 小时, 支持断点续跑
echo.

py -3.12 scripts/torii_annotate_atmosphere.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] 全量标注失败, 检查日志
    pause
    exit /b 1
)

echo.
echo === 全量标注完成 ===
echo 输出: data\torii_atmosphere_labels.jsonl
echo 下一步: 双击 RUN_V5_TRAIN.bat 跑 v5 运镜重训
pause
