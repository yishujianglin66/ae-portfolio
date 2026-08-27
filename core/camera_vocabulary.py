"""core/camera_vocabulary.py - 运镜词汇表校准 (CameraBench ↔ 项目 CAMERA_LABELS)

2026-08-14 A3: 用 CameraBench (syCen, 专业摄影师共建) 的运镜原语分类法
校准项目的运镜词汇表。关键发现:

  CameraBench = 多维多标签 (34 原语, 4 正交维度)
    1. 方向 motion (26 原语: static/no-motion/pan/truck/tilt/pedestal/
       dolly/zoom/arc/roll + 7 种 tracking)
    2. 速度 speed (3: regular/slow/fast)
    3. 稳定 stability (4: no-shaking/minimal-shaking/unsteady/very-unsteady)
    4. 复杂度 complexity (1: complex-motion)

  项目 CAMERA_LABELS = 单维扁平 13 类 (方向为主, 无速度/稳定维度)

校准结论:
  1. 方向维可 1:1 / 多:1 映射 (见 DIRECTION_TO_PROJECT), 且能补全项目
     现有标签的语义:
       - project 的 push/zoom_back 精确对应 CameraBench 的 dolly-in/dolly-out
         (物理推拉, 与 lens zoom 的 zoom-in/out 区分)
       - project 缺 roll(绕光轴旋转), CameraBench 有 roll-CW/roll-CCW → 归 orbit
  2. 速度/稳定/复杂度是项目当前丢失的维度 → Step 4 VLM 预标注应升级为
     多维 schema (见 ANNOTATION_LABEL_SCHEME), 而非单一扁平标签。

用途:
  1. 把 CameraBench 多标签 → 项目扁平标签 (map_camerabench_to_project)
  2. 给 Step 4 VLM 预标注 prompt 提供校准后的多维 schema
"""
from __future__ import annotations

from typing import Dict, List, Set

# ── CameraBench 34 原语 (按维度分组) ─────────────────────────────────────

# 方向 (含静态组, 26 个)
DIRECTION_TO_PROJECT: Dict[str, str] = {
    # 静态组
    "static": "static",
    "no-motion": "static",
    "minor-motion": "static",
    # 水平 pan/truck (2D 光流下 truck=横向轨道 ≈ pan)
    "pan-left": "pan_left",
    "pan-right": "pan_right",
    "truck-left": "pan_left",
    "truck-right": "pan_right",
    # 垂直 tilt/pedestal (pedestal=升降 ≈ tilt)
    "tilt-up": "tilt_up",
    "tilt-down": "tilt_down",
    "pedestal-up": "tilt_up",
    "pedestal-down": "tilt_down",
    # 变焦 zoom (lens) vs 推拉 dolly (物理, 透视变化)
    "zoom-in": "zoom_in",
    "zoom-out": "zoom_out",
    "dolly-in": "push",
    "dolly-out": "zoom_back",
    # 环绕/旋转
    "arc-CW": "orbit",
    "arc-CCW": "orbit",
    "roll-CW": "orbit",
    "roll-CCW": "orbit",
}

# 静态组 (多标签里可能并列出现, 如 ["no-motion", "static"])
STATIC_LABELS: Set[str] = {"static", "no-motion", "minor-motion"}

# 跟拍 tracking → 基准轴 (与显式方向合并; 无显式方向时的兜底轴)
#   side/pan-tracking → pan; tilt-tracking → tilt; arc-tracking → orbit
#   aerial/tail/lead-tracking 方向多义 → complex
TRACKING_TO_AXIS: Dict[str, str] = {
    "side-tracking": "pan",
    "pan-tracking": "pan",
    "tilt-tracking": "tilt",
    "arc-tracking": "orbit",
    "aerial-tracking": "complex",
    "tail-tracking": "complex",
    "lead-tracking": "complex",
}

# 项目标签 → 规范轴 (用于多标签合并判断: pan_left/pan_right 同属 pan 轴)
LABEL_TO_AXIS: Dict[str, str] = {
    "static": "static",
    "pan_left": "pan", "pan_right": "pan",
    "tilt_up": "tilt", "tilt_down": "tilt",
    "zoom_in": "zoom", "zoom_out": "zoom",
    "push": "zoom", "zoom_back": "zoom",   # dolly 推拉与 lens zoom 同属"纵深轴"
    "orbit": "orbit",
    "complex": "complex",
}

# 速度 / 稳定 / 复杂度 (独立维度, 不参与方向映射, 但保留给 Step 4)
SPEED_LABELS: Set[str] = {"regular-speed", "slow-speed", "fast-speed"}
STABILITY_LABELS: Set[str] = {"no-shaking", "minimal-shaking",
                              "unsteady", "very-unsteady"}
COMPLEXITY_LABELS: Set[str] = {"complex-motion"}

# 全部 34 原语
CAMERABENCH_LABELS: List[str] = (
    sorted(DIRECTION_TO_PROJECT) + sorted(TRACKING_TO_AXIS)
    + sorted(SPEED_LABELS | STABILITY_LABELS | COMPLEXITY_LABELS)
)

# ── Step 4 VLM 预标注 schema 建议 (多维) ────────────────────────────────

# 比单一扁平标签信息量更足: 方向 + 速度 + 稳定 三维, 直接沿用 CameraBench 原语名
ANNOTATION_LABEL_SCHEMA: Dict[str, List[str]] = {
    "direction": [
        "static", "pan_left", "pan_right", "tilt_up", "tilt_down",
        "zoom_in", "zoom_out", "push", "zoom_back", "orbit", "complex",
    ],
    "speed": ["regular-speed", "slow-speed", "fast-speed"],
    "stability": ["no-shaking", "minimal-shaking", "unsteady", "very-unsteady"],
}


def map_camerabench_to_project(labels: List[str]) -> str:
    """把 CameraBench 多标签映射为项目扁平标签 (方向为主)。

    规则 (优先级从高到低):
      1. 抽出方向类原语 (DIRECTION_TO_PROJECT ∪ TRACKING_TO_AXIS)。
      2. 静态组命中 (static/no-motion/minor-motion) 且无其它方向 → "static"。
      3. 唯一方向 → 查表映射。
      4. 跟拍 tracking 与其显式方向合并 (同轴则不冲突)。
      5. 多轴方向 / complex-motion → "complex"。
      6. 无方向信息 → "unknown"。
    """
    if not labels:
        return "unknown"

    specific_dirs: List[str] = []   # 显式方向 → 项目标签
    tracking_axes: List[str] = []   # 跟拍 → 规范轴

    for lb in labels:
        if lb in DIRECTION_TO_PROJECT:
            specific_dirs.append(DIRECTION_TO_PROJECT[lb])
        elif lb in TRACKING_TO_AXIS:
            tracking_axes.append(TRACKING_TO_AXIS[lb])
        # speed/stability/complexity 原语不参与方向映射

    # 静态组处理: 命中静态且无其它方向 → static
    if specific_dirs and all(x == "static" for x in specific_dirs):
        specific_dirs = ["static"]

    # 所有涉及到的规范轴 (方向 + 跟拍)
    axes: Set[str] = {LABEL_TO_AXIS[d] for d in specific_dirs}
    axes.update(a for a in tracking_axes if a != "complex")

    if not axes:
        # 无方向但有 complex-motion / 多义跟拍 → complex
        if any(l in COMPLEXITY_LABELS for l in labels):
            return "complex"
        if any(a == "complex" for a in tracking_axes):
            return "complex"
        return "unknown"

    # 单轴 → 唯一标签; 但同轴出现双向冲突 (pan_left + pan_right) 视为 complex
    if len(axes) == 1:
        if specific_dirs:
            if len(set(specific_dirs)) > 1:
                return "complex"
            return specific_dirs[0]
        # 仅跟拍轴无显式方向 → 方向多义 → complex
        return "complex"

    # 多轴 → complex
    return "complex"


def map_camerabench_multi(labels: List[str]) -> Dict[str, str]:
    """把 CameraBench 多标签拆为多维 schema (方向 + 速度 + 稳定)。"""
    direction = map_camerabench_to_project(labels)
    speed = next((l for l in labels if l in SPEED_LABELS), "regular-speed")
    stability = next((l for l in labels if l in STABILITY_LABELS), "no-shaking")
    return {"direction": direction, "speed": speed, "stability": stability}


if __name__ == "__main__":
    # 冒烟: 打印映射表 + 几个典型样本
    print("=== 方向映射表 (CameraBench → 项目) ===")
    for k, v in DIRECTION_TO_PROJECT.items():
        print(f"  {k:14s} -> {v}")
    print("\n=== 典型样本映射 ===")
    for labs in [
        ["no-motion", "static", "regular-speed", "no-shaking"],
        ["pan-left", "regular-speed", "minimal-shaking"],
        ["dolly-in", "regular-speed", "no-shaking"],
        ["zoom-in", "fast-speed", "unsteady"],
        ["arc-CW", "regular-speed", "no-shaking"],
        ["side-tracking", "truck-right", "regular-speed"],
        ["complex-motion", "tilt-down", "regular-speed", "minimal-shaking"],
    ]:
        print(f"  {labs!s:70s} -> {map_camerabench_to_project(labs)}")
