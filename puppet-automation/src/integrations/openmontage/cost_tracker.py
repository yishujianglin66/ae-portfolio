"""OpenMontage 成本追踪器。

管理视频制作流程中的 API 调用成本，预算分配，告警。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from loguru import logger


class BudgetPolicy(str, Enum):
    """预算策略。"""

    OBSERVE = "observe"  # 仅观察
    WARN = "warn"  # 超阈值告警
    CAP = "cap"  # 强制上限


@dataclass
class CostEntry:
    """单次成本记录。"""

    timestamp: float
    provider: str
    action: str
    cost_usd: float
    tokens_input: int = 0
    tokens_output: int = 0
    pipeline: Optional[str] = None
    stage: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "provider": self.provider,
            "action": self.action,
            "cost_usd": self.cost_usd,
            "tokens_input": self.tokens_input,
            "tokens_output": self.tokens_output,
            "pipeline": self.pipeline,
            "stage": self.stage,
            "metadata": self.metadata,
        }


class CostTracker:
    """成本追踪器。

    支持预算分配、累计统计、告警、日志持久化。
    """

    def __init__(
        self,
        total_budget_usd: float = 10.0,
        reserve_pct: float = 0.10,
        policy: BudgetPolicy = BudgetPolicy.WARN,
        log_path: Optional[Path] = None,
    ):
        self.total_budget_usd = total_budget_usd
        self.reserve_pct = reserve_pct
        self.policy = policy
        self.log_path = log_path or Path(
            r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\data\cost_log.jsonl"
        )
        self._entries: List[CostEntry] = []
        self._alerts: List[str] = []
        logger.info(
            f"CostTracker 初始化: budget=${total_budget_usd}, "
            f"reserve={reserve_pct * 100}%, policy={policy.value}"
        )

    @property
    def total_spent(self) -> float:
        """总支出。"""
        return sum(e.cost_usd for e in self._entries)

    @property
    def reserve_budget(self) -> float:
        """保留预算。"""
        return self.total_budget_usd * self.reserve_pct

    @property
    def available_budget(self) -> float:
        """可用预算。"""
        return self.total_budget_usd - self.reserve_budget - self.total_spent

    def can_afford(self, estimated_cost: float) -> bool:
        """检查是否负担得起。"""
        return self.available_budget >= estimated_cost

    def record(
        self,
        provider: str,
        action: str,
        cost_usd: float,
        tokens_input: int = 0,
        tokens_output: int = 0,
        pipeline: Optional[str] = None,
        stage: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CostEntry:
        """记录一次成本。

        Args:
            provider: 提供方（openai/anthropic/...）
            action: 操作名
            cost_usd: 成本（美元）
            tokens_input: 输入 token 数
            tokens_output: 输出 token 数
            pipeline: 所属流水线
            stage: 所属阶段

        Returns:
            CostEntry
        """
        entry = CostEntry(
            timestamp=time.time(),
            provider=provider,
            action=action,
            cost_usd=cost_usd,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            pipeline=pipeline,
            stage=stage,
            metadata=metadata or {},
        )
        self._entries.append(entry)
        self._check_alerts()
        self._persist(entry)
        return entry

    def _check_alerts(self):
        """检查告警。"""
        if self.policy == BudgetPolicy.OBSERVE:
            return
        total = self.total_spent
        if total > self.total_budget_usd:
            alert = (
                f"超预算！支出 ${total:.2f} / 预算 ${self.total_budget_usd:.2f}"
            )
            self._alerts.append(alert)
            logger.error(alert)
        elif total > self.total_budget_usd * 0.8:
            alert = f"预算告警：已用 80% (${total:.2f}/${self.total_budget_usd:.2f})"
            self._alerts.append(alert)
            logger.warning(alert)

    def _persist(self, entry: CostEntry):
        """持久化到 JSONL 文件。"""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"成本日志写入失败: {e}")

    def get_report(self) -> Dict[str, Any]:
        """获取成本报告。"""
        by_provider: Dict[str, float] = {}
        by_action: Dict[str, float] = {}
        by_pipeline: Dict[str, float] = {}
        for e in self._entries:
            by_provider[e.provider] = by_provider.get(e.provider, 0) + e.cost_usd
            by_action[e.action] = by_action.get(e.action, 0) + e.cost_usd
            if e.pipeline:
                by_pipeline[e.pipeline] = by_pipeline.get(e.pipeline, 0) + e.cost_usd

        return {
            "total_budget_usd": self.total_budget_usd,
            "total_spent_usd": self.total_spent,
            "available_usd": self.available_budget,
            "reserve_budget_usd": self.reserve_budget,
            "policy": self.policy.value,
            "entry_count": len(self._entries),
            "by_provider": by_provider,
            "by_action": by_action,
            "by_pipeline": by_pipeline,
            "alerts": self._alerts[-10:],
            "utilization_pct": (self.total_spent / self.total_budget_usd) * 100
            if self.total_budget_usd > 0
            else 0,
        }

    def get_top_spenders(self, n: int = 5) -> List[CostEntry]:
        """获取支出最高的 n 个条目。"""
        return sorted(self._entries, key=lambda e: e.cost_usd, reverse=True)[:n]

    def reset(self):
        """重置（不删除持久化日志）。"""
        self._entries.clear()
        self._alerts.clear()
