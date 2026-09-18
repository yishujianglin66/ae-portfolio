# -*- coding: utf-8 -*-
"""bridge_failure.py — 桥接失败结构化 (2026-09-07, 工程分析报告 #3)

把 ae_render_channel 的 on_fail_reason 字符串回调升级为结构化 BridgeFailure，
复用 pipeline_fault_policy 的八类分类关键词，供审计索引消费。

设计约束:
  - classify() / from_reason() 为纯函数，无 IO，可单测
  - BridgeFailure.to_dict() 可 JSON 序列化
  - 不改 on_fail_reason 回调签名（向后兼容）
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List

CATEGORIES = (
    "BRIDGE_DOWN",
    "LICENSE_MISSING",
    "OUTPUT_CORRUPT",
    "SCRIPT_SYNTAX",
    "TIMEOUT",
    "USER_CANCELLED",
    "DISK_FULL",
    "LICENCE_POPUP_BLOCKING",
)

RECOVERABLE = {"TIMEOUT", "BRIDGE_DOWN", "LICENCE_POPUP_BLOCKING"}


def classify(reason: str) -> str:
    """把自由文本失败原因归类到八类之一（关键词启发式，默认 BRIDGE_DOWN）。"""
    t = reason.lower()
    if "no space" in t or "enospc" in t or ("disk" in t and "full" in t):
        return "DISK_FULL"
    if "licen" in t and ("popup" in t or "弹窗" in t):
        return "LICENCE_POPUP_BLOCKING"
    if "弹窗" in t and ("blocking" in t or "block" in t or "阻塞" in t):
        return "LICENCE_POPUP_BLOCKING"
    if "licen" in t and ("missing" in t or "not found" in t or "失效" in t):
        return "LICENSE_MISSING"
    if "timeout" in t or "超时" in t or "无响应" in t:
        return "TIMEOUT"
    if "syntax" in t or ("jsx" in t and "error" in t) or "extendscript" in t:
        return "SCRIPT_SYNTAX"
    if "cancel" in t or "用户" in t:
        return "USER_CANCELLED"
    if "corrupt" in t or "损坏" in t or "截断" in t:
        return "OUTPUT_CORRUPT"
    if any(k in t for k in ("bridge", "ae未", "aerender", "计划为空",
                            "合成构建", "规范化", "构建失败")):
        return "BRIDGE_DOWN"
    return "BRIDGE_DOWN"


@dataclass(frozen=True)
class BridgeFailure:
    category: str
    stage: str
    detail: str
    recoverable: bool
    ts: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def from_reason(reason: str, stage: str) -> BridgeFailure:
    """从 (reason_text, stage) 构造结构化失败记录。"""
    cat = classify(reason)
    return BridgeFailure(
        category=cat,
        stage=stage,
        detail=reason,
        recoverable=cat in RECOVERABLE,
        ts=time.strftime("%Y-%m-%d %H:%M:%S"),
    )


def failures_summary(failures: list[BridgeFailure]) -> dict[str, Any]:
    """聚合失败列表：总数 + 按类别分组 + 是否有可恢复项。"""
    if not failures:
        return {"count": 0, "by_category": {}, "recoverable": False}
    by_cat: dict[str, int] = {}
    for f in failures:
        by_cat[f.category] = by_cat.get(f.category, 0) + 1
    return {
        "count": len(failures),
        "by_category": by_cat,
        "recoverable": any(f.recoverable for f in failures),
    }
