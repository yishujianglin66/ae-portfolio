"""
core/evolution/protocol.py — 自进化消息协议与数据结构
======================================================

借鉴 PenguinHarness 的 PenguinMessage 设计：统一且轻量的消息协议，
在评测器(Evaluator)、优化器(Optimizer)、版本管理(VersionManager)之间交换。

核心原则:
1. 文件即真相 — 所有消息/结果都持久化为 JSON 文件
2. 可复现、可审计、可回滚
3. 成本观测 — 每条消息可携带 token 成本
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class EvolutionMsgType(str, Enum):
    """自进化消息类型"""
    EVALUATE = "evaluate"          # 评测请求/结果
    OPTIMIZE = "optimize"          # 优化动作
    ACCEPT = "accept"              # 接受候选版本
    ROLLBACK = "rollback"          # 回退到上一版本
    BENCHMARK = "benchmark"        # 评测基准更新


@dataclass
class EvolutionMessage:
    """自进化消息协议 — 类比 PenguinMessage

    像网络数据报文一样在 Evaluator / Optimizer / VersionManager 之间交换。
    """
    msg_type: str                              # EvolutionMsgType 值
    run_id: str
    version_id: str = ""
    scope: str = ""                            # 版本作用域（同一任务类型才可比）
    payload: Dict[str, Any] = field(default_factory=dict)
    score: Optional[float] = None
    trajectory_ref: str = ""                   # 轨迹文件引用
    tokens_used: int = 0                       # 成本观测
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "EvolutionMessage":
        valid_keys = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in valid_keys})


@dataclass
class BenchmarkTask:
    """评测基准题目（P0 手动编写，P1 由 BenchmarkBuilder 自动生成）"""
    id: str
    task_type: str                             # style_transfer / effect_apply / color_grade ...
    input: str                                 # 任务描述
    expected_output: Dict[str, Any] = field(default_factory=dict)
    rubrics: str = ""                          # 隐藏评分标准（仅 Evaluator 可见）
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvaluationResult:
    """一次评测的完整结果"""
    run_id: str
    scope: str
    score: float                               # 综合评分 0-100
    deterministic_score: float = 0.0           # 确定性指标分（VMAF/SSIM/VQA）
    rubric_score: Optional[float] = None       # LLM 语义评分（Rubrics）
    passed: bool = False
    checks: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    tokens_used: int = 0
    cost_usd: float = 0.0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
#  成本上限策略（风险控制）
# ============================================================================

COST_LIMITS: Dict[str, int] = {
    "single_evaluation": 100_000,     # 单次评测 ≤ 10万 token
    "single_optimization": 200_000,   # 单次优化 ≤ 20万 token
    "evolution_cycle": 500_000,       # 单轮进化 ≤ 50万 token
    "daily_budget": 2_000_000,        # 日预算 ≤ 200万 token
}


def within_cost_limit(kind: str, tokens_used: int) -> bool:
    """检查 token 用量是否在上限内"""
    limit = COST_LIMITS.get(kind)
    if limit is None:
        return True
    return tokens_used <= limit


# ============================================================================
#  文件持久化工具 — 文件即真相
# ============================================================================

def append_jsonl(path: Path, record: Dict[str, Any]) -> None:
    """追加一条 JSON 记录到 JSONL 文件（原子性：先写临时文件再替换不适用于追加，直接追加）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def write_json(path: Path, data: Any) -> None:
    """写 JSON 文件（带目录创建）"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)


def read_json(path: Path, default: Any = None) -> Any:
    """读 JSON 文件，失败返回 default"""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default
