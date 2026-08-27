"""
core/evolution/version_manager.py — 进化版本管理 + 严格回退
============================================================

借鉴 PenguinHarness 的核心机制：
    只有在候选版本取得「严格更高」的分数时才被接受；
    如果得分持平或下降，回退到上一个版本。

设计原则:
1. 文件即真相 — 每个版本是一个目录（配置快照 + 得分记录）
2. 可审计 — 所有接受/回退决策写入 decision_log.jsonl
3. 作用域隔离 — 不同任务类型(scope)的版本分开比较，避免跨任务污染

目录结构:
    data/versions/
    ├── current.json            # 当前生效版本指针 {scope: version_id}
    ├── decision_log.jsonl      # 接受/回退决策日志（审计）
    ├── v001/
    │   ├── meta.json           # 版本元数据（scope、时间、来源run_id）
    │   ├── config.json         # Agent/Prompt/参数配置快照
    │   └── scores.jsonl        # 该版本历次评测得分
    └── ...

集成方式:
    from core.evolution.version_manager import get_version_manager

    vm = get_version_manager()
    vid = vm.create_version(scope="style_transfer", config_snapshot={...})
    decision = vm.record_and_decide(vid, score=72.5)
    # decision.decision ∈ {"accept", "rollback", "hold"}
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.protocol import (
    EvolutionMessage,
    EvolutionMsgType,
    append_jsonl,
    read_json,
    write_json,
)

# 项目根目录（core/evolution/version_manager.py → 上三级）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class VersionDecision:
    """版本决策结果"""
    version_id: str
    decision: str                     # accept / rollback / hold
    score: float
    best_score: float                 # 决策前的历史最佳分
    margin: float                     # score - best_score
    epsilon: float                    # 严格更高所需的边际
    consecutive_rollbacks: int = 0    # 连续回退次数（>=3 时应通知人工）
    reason: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
#  版本管理器
# ============================================================================

class VersionManager:
    """进化版本管理器

    职责:
    1. 创建版本（配置快照）
    2. 记录评测得分
    3. 严格对比决策：仅当 score > best + epsilon 时接受
    4. 回退：候选被拒绝时指向历史最佳版本
    """

    DEFAULT_DATA_DIR = str(PROJECT_ROOT / "data" / "versions")
    # 连续回退达到该次数时，决策日志中标记 need_human_review
    HUMAN_REVIEW_THRESHOLD = 3

    def __init__(self, data_dir: str = DEFAULT_DATA_DIR, epsilon: float = 0.5):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._epsilon = float(epsilon)
        self._current_path = self._data_dir / "current.json"
        self._decision_log = self._data_dir / "decision_log.jsonl"

    # ----------------------------------------------------------------
    #  版本生命周期
    # ----------------------------------------------------------------

    def create_version(
        self,
        scope: str,
        config_snapshot: Optional[Dict[str, Any]] = None,
        source_run_id: str = "",
        parent_version: str = "",
    ) -> str:
        """创建新版本（配置快照）

        Args:
            scope: 版本作用域（同一任务类型才可比，如 "style_transfer"）
            config_snapshot: 当前 Agent 配置/Prompt/参数快照
            source_run_id: 产生该版本的管线 run_id
            parent_version: 父版本 ID（回退后的再进化场景）

        Returns:
            新版本 ID（如 "v001"）
        """
        version_id = self._next_version_id()
        vdir = self._data_dir / version_id
        vdir.mkdir(parents=True, exist_ok=True)

        meta = {
            "version_id": version_id,
            "scope": scope,
            "created_at": time.time(),
            "source_run_id": source_run_id,
            "parent_version": parent_version,
            "status": "candidate",   # candidate → accepted / rejected
        }
        write_json(vdir / "meta.json", meta)
        write_json(vdir / "config.json", config_snapshot or {})
        logger.info("[VersionManager] created %s (scope=%s)", version_id, scope)
        return version_id

    def _next_version_id(self) -> str:
        existing = [
            p.name for p in self._data_dir.iterdir()
            if p.is_dir() and p.name.startswith("v") and p.name[1:].isdigit()
        ]
        next_num = max((int(n[1:]) for n in existing), default=0) + 1
        return f"v{next_num:03d}"

    # ----------------------------------------------------------------
    #  评分与决策
    # ----------------------------------------------------------------

    def record_score(
        self,
        version_id: str,
        score: float,
        breakdown: Optional[Dict[str, Any]] = None,
        run_id: str = "",
    ) -> None:
        """记录一次评测得分到版本目录"""
        scores_path = self._data_dir / version_id / "scores.jsonl"
        append_jsonl(scores_path, {
            "score": float(score),
            "breakdown": breakdown or {},
            "run_id": run_id,
            "timestamp": time.time(),
        })

    def get_best_score(self, version_id: str) -> float:
        """获取版本的历史最佳分"""
        scores_path = self._data_dir / version_id / "scores.jsonl"
        if not scores_path.exists():
            return 0.0
        best = 0.0
        try:
            import json
            with open(scores_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        s = float(rec.get("score", 0.0))
                        if s > best:
                            best = s
                    except (ValueError, TypeError):
                        continue
        except Exception:
            pass
        return best

    def get_current_version(self, scope: str) -> str:
        """获取某作用域当前生效的版本 ID（无则空串）"""
        current = read_json(self._current_path, {}) or {}
        return current.get(scope, "")

    def _set_current_version(self, scope: str, version_id: str) -> None:
        current = read_json(self._current_path, {}) or {}
        current[scope] = version_id
        write_json(self._current_path, current)

    def record_and_decide(
        self,
        version_id: str,
        score: float,
        run_id: str = "",
        breakdown: Optional[Dict[str, Any]] = None,
    ) -> VersionDecision:
        """记录得分并做出接受/回退决策（PenguinHarness 核心逻辑）

        规则:
            - 该 scope 尚无 accepted 版本 → 直接接受（建立基线）
            - score > best + epsilon → 接受（严格更高）
            - score <= best + epsilon → 回退（保持历史最佳）

        Args:
            version_id: 候选版本
            score: 本次评测综合分
            run_id: 关联的管线 run_id
            breakdown: 分项得分明细

        Returns:
            VersionDecision
        """
        meta = read_json(self._data_dir / version_id / "meta.json", {}) or {}
        scope = meta.get("scope", "default")

        self.record_score(version_id, score, breakdown, run_id)

        current_id = self.get_current_version(scope)
        best_score = self.get_best_score(current_id) if current_id else 0.0
        margin = float(score) - best_score

        if not current_id:
            decision = "accept"
            reason = "no_baseline_established"
        elif margin > self._epsilon:
            decision = "accept"
            reason = f"strictly_higher ({score:.1f} > {best_score:.1f} + {self._epsilon})"
        else:
            decision = "rollback"
            reason = f"not_strictly_higher ({score:.1f} <= {best_score:.1f} + {self._epsilon})"

        # 连续回退计数
        consecutive = self._count_consecutive_rollbacks(scope)
        if decision == "accept":
            self._set_current_version(scope, version_id)
            self._set_version_status(version_id, "accepted")
            consecutive = 0
        else:
            self._set_version_status(version_id, "rejected")
            consecutive += 1

        need_human = consecutive >= self.HUMAN_REVIEW_THRESHOLD
        vd = VersionDecision(
            version_id=version_id,
            decision=decision,
            score=float(score),
            best_score=best_score,
            margin=margin,
            epsilon=self._epsilon,
            consecutive_rollbacks=consecutive,
            reason=reason,
        )

        # 审计日志
        log_record = vd.to_dict()
        log_record.update({
            "scope": scope,
            "run_id": run_id,
            "need_human_review": need_human,
        })
        append_jsonl(self._decision_log, log_record)

        if need_human:
            logger.warning(
                "[VersionManager] scope=%s 连续 %d 次回退，建议人工介入",
                scope, consecutive,
            )

        logger.info(
            "[VersionManager] %s score=%.1f best=%.1f → %s (%s)",
            version_id, score, best_score, decision, reason,
        )
        return vd

    def _set_version_status(self, version_id: str, status: str) -> None:
        meta_path = self._data_dir / version_id / "meta.json"
        meta = read_json(meta_path, {}) or {}
        meta["status"] = status
        write_json(meta_path, meta)

    def _count_consecutive_rollbacks(self, scope: str) -> int:
        """统计该 scope 最近连续回退次数（从日志尾部往前数）"""
        if not self._decision_log.exists():
            return 0
        records: List[Dict[str, Any]] = []
        try:
            import json
            with open(self._decision_log, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                        if rec.get("scope") == scope:
                            records.append(rec)
                    except Exception:
                        continue
        except Exception:
            return 0
        count = 0
        for rec in reversed(records):
            if rec.get("decision") == "rollback":
                count += 1
            else:
                break
        return count

    # ----------------------------------------------------------------
    #  查询与审计
    # ----------------------------------------------------------------

    def history(self, scope: Optional[str] = None) -> List[Dict[str, Any]]:
        """获取所有版本的摘要历史"""
        result = []
        for vdir in sorted(self._data_dir.iterdir()):
            if not (vdir.is_dir() and vdir.name.startswith("v")):
                continue
            meta = read_json(vdir / "meta.json", {}) or {}
            if scope and meta.get("scope") != scope:
                continue
            result.append({
                "version_id": meta.get("version_id", vdir.name),
                "scope": meta.get("scope", ""),
                "status": meta.get("status", "unknown"),
                "best_score": self.get_best_score(vdir.name),
                "created_at": meta.get("created_at", 0),
                "source_run_id": meta.get("source_run_id", ""),
            })
        return result

    def get_config_snapshot(self, version_id: str) -> Dict[str, Any]:
        """读取版本配置快照（供回退后恢复）"""
        return read_json(self._data_dir / version_id / "config.json", {}) or {}

    def emit_message(self, decision: VersionDecision, scope: str, run_id: str) -> EvolutionMessage:
        """将决策转为 EvolutionMessage（供消息总线/日志消费）"""
        msg_type = (
            EvolutionMsgType.ACCEPT if decision.decision == "accept"
            else EvolutionMsgType.ROLLBACK
        )
        return EvolutionMessage(
            msg_type=msg_type.value,
            run_id=run_id,
            version_id=decision.version_id,
            scope=scope,
            score=decision.score,
            payload=decision.to_dict(),
        )


# ============================================================================
#  全局单例
# ============================================================================

_global_vm: Optional[VersionManager] = None


def get_version_manager(
    data_dir: str = VersionManager.DEFAULT_DATA_DIR,
    epsilon: float = 0.5,
) -> VersionManager:
    """获取全局版本管理器单例"""
    global _global_vm
    if _global_vm is None:
        _global_vm = VersionManager(data_dir=data_dir, epsilon=epsilon)
    return _global_vm
