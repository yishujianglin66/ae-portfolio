"""旗舰管线故障策略（Plan B / P1 一致性收口）。

本模块把「降级」从「静默默认行为」改为「显式 opt-in」，并把失败归类到旗舰规格
§0.4 的八类错误，自动产出带修复建议的 postmortem.md。

设计约束（稳定性优先，绝不影响主流程）：
- 纯新增模块，只被 pipeline.flagship_runner 调用。
- 所有函数包裹 try/except；本模块自身故障绝不能拖垮主流程。
- 默认严格模式（AEKV_ENGINE_FALLBACK=0）：原生引擎不可用即中止，
  不降级到 ffmpeg_equiv（符合规格 §0.1 零 mock / §0.3 全链路可失败 / §1.2 无回退）。
- 仅当用户显式设置 env AEKV_ENGINE_FALLBACK=1 时，才允许降级到 ffmpeg_equiv，
  且仍须显式打标 execution_mode=ffmpeg_equiv 并记录降级根因。
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger("pipeline_fault_policy")

# 旗舰规格 §0.4 八类错误
FAILURE_CATEGORIES = (
    "BRIDGE_DOWN",
    "LICENSE_MISSING",
    "OUTPUT_CORRUPT",
    "SCRIPT_SYNTAX",
    "TIMEOUT",
    "USER_CANCELLED",
    "DISK_FULL",
    "LICENCE_POPUP_BLOCKING",
)

# 八类错误对应的修复建议（写入 postmortem.md）
FIX_SUGGESTIONS = {
    "BRIDGE_DOWN": "确认 AE / PR / DaVinci / AME 已启动且 Bridge 已连接；S0 健康检查应先行。"
                   "可启用看门狗（AEKV_WATCHDOG=1）自动杀树重启假死引擎。",
    "LICENSE_MISSING": "检查 Adobe 许可是否激活；确认 ae_presets/、color_lut.cube 等素材存在且路径正确。",
    "OUTPUT_CORRUPT": "检查输出文件是否被截断/损坏；清理 run 目录后重试；确认磁盘可写且未达配额。",
    "SCRIPT_SYNTAX": "检查 JSX / JS 脚本语法；确认 AE / DaVinci 版本与脚本兼容（必要时手动执行定位报错行）。",
    "TIMEOUT": "增大超时阈值或检查引擎是否卡死；确认素材规模匹配；必要时手动重启引擎。"
               "AME 队列死锁可清空旧队列后重试。",
    "USER_CANCELLED": "用户主动取消，无需自动修复；重新触发即可。",
    "DISK_FULL": "清理磁盘空间（S0 预检要求 ≥50GB，S6 前 ≥10GB）；释放后重试。",
    "LICENCE_POPUP_BLOCKING": "检测并关闭许可弹窗（close_dialog.ps1）；失败则手动关闭后重试。",
}


class FlagshipStageError(Exception):
    """阶段级失败：携带规格 §0.4 八类错误分类，供顶层统一生成 postmortem。"""

    def __init__(self, stage: str, category: str, error: str, completed: dict | None = None):
        super().__init__(error)
        self.stage = stage
        self.category = category if category in FAILURE_CATEGORIES else "BRIDGE_DOWN"
        self.error = error
        self.completed = completed or {}


def engine_fallback_enabled() -> bool:
    """ffmpeg_equiv 降级是否允许（默认 False = 严格 / 规格合规）。

    仅当用户显式设置 env AEKV_ENGINE_FALLBACK=1 时返回 True。
    """
    return os.environ.get("AEKV_ENGINE_FALLBACK", "0") == "1"


def classify_failure(stage: str, exc: BaseException | None = None, logs: str = "") -> str:
    """将一次失败归类到规格 §0.4 八类之一（关键词启发式，引擎不可用默认 BRIDGE_DOWN）。"""
    text = f"{stage} {exc} {logs}".lower()
    # 注意：具体类别须排在泛化类别(BRIDGE_DOWN)之前，否则会被提前命中
    if "no space" in text or "enospc" in text or ("disk" in text and "full" in text):
        return "DISK_FULL"
    if "licen" in text and ("popup" in text or "blocking" in text or "弹窗" in text):
        return "LICENCE_POPUP_BLOCKING"
    if "licen" in text and ("missing" in text or "not found" in text or "失效" in text):
        return "LICENSE_MISSING"
    if "timeout" in text or "timed out" in text or "超时" in text:
        return "TIMEOUT"
    if "syntax" in text or ("jsx" in text and "error" in text) or "脚本" in text:
        return "SCRIPT_SYNTAX"
    if "cancel" in text or ("user" in text and "abort" in text) or "用户" in text:
        return "USER_CANCELLED"
    if "corrupt" in text or "损坏" in text or "截断" in text:
        return "OUTPUT_CORRUPT"
    if "bridge" in text or "unavailable" in text or "not available" in text or "不可用" in text or "连接" in text:
        return "BRIDGE_DOWN"
    # 引擎/原生路径失败且无法细分时，默认归为 Bridge 不可达（最常见根因）
    return "BRIDGE_DOWN"


def write_postmortem(
    run_dir: Path,
    category: str,
    stage: str,
    error: str,
    completed: dict | None = None,
) -> Path:
    """生成规格 §0.4 合规的 postmortem.md（含八类分类 + 修复建议）。"""
    category = category if category in FAILURE_CATEGORIES else "BRIDGE_DOWN"
    completed = completed or {}
    fix = FIX_SUGGESTIONS.get(category, "见错误详情。")
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    path = Path(run_dir) / "postmortem.md"
    try:
        path.write_text(
            f"# 旗舰管线失败报告（规格 §0.4）\n\n"
            f"- Run ID: {Path(run_dir).name}\n"
            f"- 时间: {ts}\n"
            f"- 失败阶段: **{stage}**\n"
            f"- 错误分类: **{category}**\n"
            f"- 错误详情: {error}\n\n"
            f"## 修复建议\n\n{fix}\n\n"
            f"## 已完成阶段\n\n"
            f"```json\n{__import__('json').dumps(completed, indent=2, ensure_ascii=False)}\n```\n",
            encoding="utf-8",
        )
    except Exception as e:
        logger.warning(f"[postmortem] 写入失败: {e}")
    return path
