@echo off
chcp 65001 >nul
REM ============================================================
REM 包2 - 任务B: v5 运镜分类重训 冒烟测试
REM 用途: 验证数据加载 + 模型初始化 + 训练循环
REM 闸门: 200 样本能跑完 2 个 epoch, val_acc 输出非 NaN
REM 预计耗时: 5-10 分钟
REM ============================================================

setlocal
cd /d "%~dp0"

echo === 包2 任务B 冒烟: v5 训练管线 (200 样本, 2 epochs) ===
echo.

py -3.12 scripts/train_anime_camera_v5.py --limit 200 --epochs 2 --amp --batch-size 8

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] 冒烟失败, 检查错误
    pause
    exit /b 1
)

echo.
echo === 冒烟通过 ===
echo 下一步: 双击 RUN_V5_TRAIN.bat 跑全量训练
pause
