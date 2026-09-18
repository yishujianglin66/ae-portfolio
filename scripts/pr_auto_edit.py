"""
PR 自动剪辑工作流 — 真正的端到端 PR 自动化

功能：
  1. 检测 Premiere Pro 运行状态
  2. 自动检测桥接协议（CEP 插件优先，Standalone JSX 降级）
  3. 导入素材 → 创建序列 → 上轨 → 转场 → 输出
  4. 完整错误处理和日志

使用方式：
    python scripts/pr_auto_edit.py

首次使用：
  1. 启动 Premiere Pro 并打开/创建一个项目
  2. 运行 pr_mcp_bridge.jsx (File > Scripts > Run Script File...)
     选择: puppet-automation/src/engines/premiere/pr_mcp_bridge.jsx
     点击"确定"启动监听器
  3. 运行本脚本

流程：
  1. 检测 PR 是否运行 → 未运行则启动
  2. 等待桥接就绪（尝试 CEP 协议，降级 standalone）
  3. 导入所有素材到项目
  4. 创建序列（多策略：预设名/无预设/克隆）
  5. 逐个添加素材到时间线（间隔 5 秒）
  6. 在片段衔接处添加 Cross Dissolve 转场
  7. 导出为 H.264 MP4
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# 添加路径
_PROJECT_ROOT = Path(__file__).parent.parent.resolve()
_PUPPET_AUTOMATION = _PROJECT_ROOT / "puppet-automation"
sys.path.insert(0, str(_PROJECT_ROOT))
sys.path.insert(0, str(_PUPPET_AUTOMATION))

from loguru import logger

# 配置日志
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:7}</level> | {message}",
    level="DEBUG",
    colorize=True,
)
logger.add(
    _PROJECT_ROOT / "output" / "pr_auto_edit_{time:YYYY-MM-DD}.log",
    rotation="10 MB",
    level="DEBUG",
    encoding="utf-8",
)

# 路径配置
PR_EXECUTABLE = Path(r"D:\Pr25\Adobe Premiere Pro 2025\Adobe Premiere Pro.exe")
BRIDGE_DIR = _PROJECT_ROOT / ".premiere-mcp-bridge"
STOCK_FOOTAGE = _PROJECT_ROOT / "data" / "stock_footage"
OUTPUT_DIR = _PROJECT_ROOT / "output"
PROJECT_FILE = _PROJECT_ROOT / "output" / "pr_auto_edit.prproj"

# 桥接就绪等待时间
BRIDGE_WAIT_TIMEOUT = 30  # 秒
BRIDGE_POLL_INTERVAL = 1  # 秒


def is_pr_running() -> bool:
    """检测 Premiere Pro 是否在运行。"""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Adobe Premiere Pro.exe", "/FO", "CSV"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "Adobe Premiere Pro.exe" in result.stdout
    except Exception:
        return False


def start_premiere_pro() -> subprocess.Popen | None:
    """启动 Premiere Pro。"""
    if not PR_EXECUTABLE.exists():
        logger.error(f"PR 可执行文件不存在: {PR_EXECUTABLE}")
        return None

    logger.info(f"启动 Premiere Pro: {PR_EXECUTABLE}")
    try:
        proc = subprocess.Popen(
            [str(PR_EXECUTABLE)],
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0,
        )
        logger.info(f"PR 启动中 (PID: {proc.pid})...")
        return proc
    except Exception as e:
        logger.error(f"启动 PR 失败: {e}")
        return None


async def wait_for_bridge(timeout: int = BRIDGE_WAIT_TIMEOUT) -> bool:
    """等待 PR Bridge 就绪（尝试 CEP 协议，然后 standalone）。"""
    from src.engines.premiere.pr_bridge_client import PRBridgeClient, PRBridgeError

    client = PRBridgeClient()
    logger.info(f"等待桥接就绪（超时 {timeout} 秒）...")
    start = time.monotonic()

    while time.monotonic() - start < timeout:
        try:
            info = await client.ping()
            logger.info(f"✅ 桥接就绪! PR 版本: {info.get('data', {}).get('appVersion', 'unknown')}")
            return True
        except PRBridgeError:
            elapsed = int(time.monotonic() - start)
            if elapsed % 5 == 0:
                logger.info(f"  等待桥接中... ({elapsed}s)")
            await asyncio.sleep(BRIDGE_POLL_INTERVAL)

    logger.error(f"❌ 桥接未就绪（超时 {timeout} 秒）")
    print()
    print("=" * 60)
    print("  桥接连接失败 - 请按以下步骤操作:")
    print("=" * 60)
    print()
    print("  步骤1: 检查 CEP 面板状态")
    print("    在 PR 中: Window > Extensions > MCP Bridge")
    print("    如果面板显示 'Stopped' 或空白，请关闭并重新打开")
    print()
    print("  步骤2: 运行桥接监听器（备用方案）")
    print("    在 PR 中: File > Scripts > Run Script File...")
    jsx_path = _PUPPET_AUTOMATION / "src" / "engines" / "premiere" / "pr_mcp_bridge.jsx"
    print(f"     选择: {jsx_path}")
    print('     在弹出的对话框中点击"确定"启动监听器')
    print()
    print("  步骤3: 重新运行本脚本")
    print()
    return False


async def get_media_files() -> list[str]:
    """获取素材文件列表。"""
    video_exts = {".mp4", ".mov", ".avi", ".mxf", ".mts", ".m2ts", ".wmv", ".flv", ".mkv"}
    files = sorted(
        [str(f) for f in STOCK_FOOTAGE.iterdir() if f.suffix.lower() in video_exts]
    )

    if not files:
        json_file = STOCK_FOOTAGE / "download_result.json"
        if json_file.exists():
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                files = [
                    str(_PROJECT_ROOT / v) for v in data.get("videos", [])
                    if (_PROJECT_ROOT / v).exists()
                ]
            except Exception:
                pass

    if not files:
        logger.error("没有可用素材，请先下载素材")
        return []

    logger.info(f"找到 {len(files)} 个素材文件:")
    for f in files:
        f_size = Path(f).stat().st_size / (1024 * 1024)
        logger.info(f"  - {Path(f).name} ({f_size:.1f} MB)")

    return files


async def run_auto_edit_workflow() -> None:
    """执行完整的 PR 自动剪辑工作流。"""
    print()
    print("=" * 70)
    print("  PR 自动剪辑工作流 v1.0")
    print("=" * 70)
    print()

    # 1. 检查 PR 运行状态
    if is_pr_running():
        logger.info("✅ Premiere Pro 已在运行")
    else:
        logger.info("Premiere Pro 未运行，正在启动...")
        proc = start_premiere_pro()
        if not proc:
            logger.error("无法启动 Premiere Pro，请手动启动后重试")
            return
        logger.info("等待 PR 启动完成（约 20 秒）...")
        await asyncio.sleep(20)

    # 2. 等待桥接就绪
    bridge_ready = await wait_for_bridge()
    if not bridge_ready:
        return

    # 3. 获取素材
    media_files = await get_media_files()
    if not media_files:
        return

    # 4. 确保输出目录
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 5. 执行工作流
    output_path = str(OUTPUT_DIR / "pr_auto_edit_output.mp4")
    project_path = str(PROJECT_FILE)

    from src.engines.premiere.pr_bridge_client import (
        PRBridgeClient,
        PRBridgeError,
        SequenceCreationError,
        auto_edit_workflow,
    )

    logger.info("开始执行自动剪辑工作流...")
    print()
    logger.info(f"  素材: {len(media_files)} 个文件")
    logger.info("  序列: AutoEdit")
    logger.info("  转场: Cross Dissolve (0.5s)")
    logger.info(f"  输出: {output_path}")
    print()

    result = await auto_edit_workflow(
        media_files=media_files,
        output_path=output_path,
        sequence_name="AutoEdit",
        transition_name="Cross Dissolve",
        transition_duration=0.5,
        project_path=project_path,
    )

    # 6. 报告结果
    print()
    print("=" * 70)
    print("  工作流执行结果")
    print("=" * 70)
    print()

    if result["success"]:
        logger.info("✅ 自动剪辑工作流执行成功!")
        print()
        logger.info(f"输出文件: {output_path}")
        if Path(output_path).exists():
            size_mb = Path(output_path).stat().st_size / (1024 * 1024)
            logger.info(f"文件大小: {size_mb:.1f} MB")
        print()
        logger.info("步骤明细:")
        for step in result["steps"]:
            icon = "✅" if step["status"] == "ok" else "❌"
            logger.info(f"  {icon} {step['step']}")
    else:
        logger.error(f"❌ 工作流执行失败: {result['error']}")
        print()
        logger.info("已完成步骤:")
        for step in result["steps"]:
            icon = "✅" if step["status"] == "ok" else "❌"
            logger.info(f"  {icon} {step['step']}")
        print()
        logger.info("提示: 请确保:")
        logger.info("  1. PR 中已运行了 pr_mcp_bridge.jsx")
        logger.info("  2. PR 中打开了项目（1.prproj）")
        logger.info("  3. 素材已成功导入到项目面板")

    print()


def main():
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    try:
        asyncio.run(run_auto_edit_workflow())
    except KeyboardInterrupt:
        print()
        logger.info("用户中断")
    except Exception as e:
        logger.error(f"未预期错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()