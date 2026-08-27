@echo off
chcp 65001 >nul
REM ============================================================
REM 包2 - 任务B: v5 运镜分类重训 (全量)
REM 用途: 用扩大的 vlm_labels_v3.jsonl 数据集重训 VideoMAE 全参
REM 预计耗时: 4-6 小时 (5090, 24k 样本, 25 epochs)
REM 闸门: meta.json val_acc >= 0.70 (保底) / >= 0.75 (达标)
REM ============================================================

setlocal
cd /d "%~dp0"

echo === 包2 任务B: v5 运镜重训 ===
echo 数据: data\vlm_labels_v3.jsonl (本地标注合并后)
echo 模式: 全参微调, label_smoothing=0.1, mixup=0.2
echo 预计 4-6 小时, 配合早停 (patience=5)
echo.

REM 底模重训 (推荐, 避免继承 v4 偏差)
py -3.12 scripts/train_anime_camera_v5.py ^
    --labels data\vlm_labels_v3.jsonl ^
    --out models\output\anime_camera_lora_v5 ^
    --epochs 25 --early-stop 5 --amp --batch-size 16

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] v5 训练失败, 检查日志
    pause
    exit /b 1
)

echo.
echo === v5 训练完成 ===
echo 检查 meta.json 的 val_acc 字段:
echo   >= 0.70 保底
echo   >= 0.75 达标
echo   >= 0.80 理想
echo.
echo 按 SOP 打包回传: model.safetensors + meta.json + config.json + train_history.json
pause
