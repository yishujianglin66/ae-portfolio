@echo off
chcp 65001 >nul
REM ============================================================
REM 包2 - 任务A: ToriiGate 全库氛围标注 冒烟测试
REM 用途: 验证 ToriiGate 模型加载 + 抽帧 + JSON 解析链路
REM 闸门: 20 个镜头全部成功输出 mood/time/atmosphere 三维度
REM 预计耗时: 2-5 分钟 (首次加载模型 + 20 镜头推理)
REM ============================================================

setlocal
cd /d "%~dp0"

echo === 包2 任务A 冒烟: ToriiGate 氛围标注 (20 镜头) ===
echo.

REM Python 必须用 3.12 (默认 py 指向损坏的 3.14)
py -3.12 scripts/torii_annotate_atmosphere.py --limit 20

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] 冒烟失败, 检查上面的错误日志
    pause
    exit /b 1
)

echo.
echo === 冒烟通过 ===
echo 检查输出: data\torii_atmosphere_labels.jsonl (应至少 20 行)
echo 每行应有 mood/time/atmosphere/caption 四个字段
echo.
echo 下一步: 双击 RUN_TORII.bat 跑全量标注
pause
