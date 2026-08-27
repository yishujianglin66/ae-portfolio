"""
core/evolution/knowledge_sink.py — 进化知识自动沉淀与消费 (P2)
=================================================================

借鉴 PenguinHarness「文件即真相」与计划中的知识沉淀目标:
1. 每次进化决策（accept/rollback）自动提炼经验教训 → data/self_evolution/
2. 后续运行（Optimizer/管线）可消费这些经验（load_relevant_experience）
3. 知识条目带去重与上限裁剪，防止无限膨胀

知识文件:
    data/self_evolution/evolution_knowledge.jsonl   # 经验条目（append-only + 定期压缩）
    data/self_evolution/knowledge_stats.json        # 统计摘要（供 Dashboard）

用法:
    from core.evolution.knowledge_sink import get_knowledge_sink

    sink = get_knowledge_sink()
    sink.record_lesson(scope="style_transfer", decision="accept", ...)
    lessons = sink.load_relevant_experience("style_transfer")
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.evolution.protocol import append_jsonl, read_json, write_json

logger = logging.getLogger(__name__)


# 知识库最大条目数（超出时保留最新 + 高价值条目）
MAX_LESSONS = 200


class KnowledgeSink:
    """进化知识沉淀池"""

    # 默认目录收口到 core.paths.self_evolution_dir()（运行时产物移出代码仓库）
    try:
        from core.paths import self_evolution_dir as _paths_evo_dir
        DEFAULT_DIR = _paths_evo_dir()
    except ImportError:
        DEFAULT_DIR = "data/self_evolution"

    def __init__(self, data_dir: str = DEFAULT_DIR):
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._lessons_path = self._dir / "evolution_knowledge.jsonl"
        self._stats_path = self._dir / "knowledge_stats.json"

    # ----------------------------------------------------------------
    #  写入: 从进化决策提炼经验
    # ----------------------------------------------------------------

    def record_lesson(
        self,
        scope: str,
        decision: str,
        score: float,
        adjustments: Optional[Dict[str, Any]] = None,
        notes: Optional[List[str]] = None,
        run_id: str = "",
    ) -> Dict[str, Any]:
        """将一次进化决策提炼为经验条目

        经验格式（供 Optimizer/管线消费）:
        - accept: 「调整 X 使 scope=Y 得分提升至 Z」
        - rollback: 「调整 X 未能提升 scope=Y 的得分（应回退）」
        """
        lesson_text = self._compose_lesson(scope, decision, score, adjustments)
        entry = {
            "lesson": lesson_text,
            "scope": scope,
            "decision": decision,
            "score": float(score),
            "adjustments": adjustments or {},
            "notes": notes or [],
            "run_id": run_id,
            "value": self._lesson_value(decision, adjustments),
            "timestamp": time.time(),
        }

        # 去重: 同 scope+adjustments 的经验只保留最新
        if not self._is_duplicate(entry):
            append_jsonl(self._lessons_path, entry)
            self._trim_if_needed()
            self._update_stats(entry)
            logger.info("[KnowledgeSink] lesson recorded: %s", lesson_text[:80])
        else:
            logger.debug("[KnowledgeSink] duplicate lesson skipped")
        return entry

    def _compose_lesson(
        self,
        scope: str,
        decision: str,
        score: float,
        adjustments: Optional[Dict[str, Any]],
    ) -> str:
        adj_desc = ", ".join(f"{k}={v}" for k, v in (adjustments or {}).items()) or "无配置调整"
        if decision == "accept":
            return f"[{scope}] 有效改进: {adj_desc} → 得分 {score:.1f}（被接受）"
        return f"[{scope}] 无效尝试: {adj_desc} → 得分 {score:.1f}（被回退，避免重复）"

    @staticmethod
    def _lesson_value(decision: str, adjustments: Optional[Dict[str, Any]]) -> int:
        """经验价值分（裁剪时保留高价值条目）"""
        value = 3 if decision == "rollback" else 2   # 失败教训更有价值
        if adjustments:
            value += 1
        return value

    def _is_duplicate(self, entry: Dict[str, Any]) -> bool:
        """同 scope + 同 adjustments 视为重复"""
        for existing in self._read_lessons()[-20:]:
            if (
                existing.get("scope") == entry["scope"]
                and existing.get("adjustments") == entry["adjustments"]
                and existing.get("decision") == entry["decision"]
            ):
                return True
        return False

    # ----------------------------------------------------------------
    #  读取: 供 Optimizer/管线消费
    # ----------------------------------------------------------------

    def load_relevant_experience(
        self,
        scope: str = "",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """加载相关经验（scope 精确匹配优先，其次全局高价值条目）"""
        lessons = self._read_lessons()
        if not lessons:
            return []
        scoped = [l for l in lessons if not scope or l.get("scope") == scope]
        scoped.sort(key=lambda l: (l.get("value", 0), l.get("timestamp", 0)), reverse=True)
        return scoped[:limit]

    def experience_text(self, scope: str = "", limit: int = 5) -> str:
        """将经验格式化为文本（注入 Optimizer Prompt 上下文）"""
        lessons = self.load_relevant_experience(scope, limit)
        if not lessons:
            return ""
        lines = ["【历史进化经验（来自知识库）】"]
        for l in lessons:
            lines.append(f"- {l.get('lesson', '')}")
        return "\n".join(lines)

    def _read_lessons(self) -> List[Dict[str, Any]]:
        if not self._lessons_path.exists():
            return []
        lessons: List[Dict[str, Any]] = []
        try:
            with open(self._lessons_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        lessons.append(json.loads(line))
                    except Exception:
                        continue
        except Exception:
            pass
        return lessons

    # ----------------------------------------------------------------
    #  维护
    # ----------------------------------------------------------------

    def _trim_if_needed(self) -> None:
        """超出上限时裁剪：保留高价值 + 最新条目"""
        lessons = self._read_lessons()
        if len(lessons) <= MAX_LESSONS:
            return
        lessons.sort(key=lambda l: (l.get("value", 0), l.get("timestamp", 0)), reverse=True)
        kept = lessons[:MAX_LESSONS]
        kept.sort(key=lambda l: l.get("timestamp", 0))
        try:
            with open(self._lessons_path, "w", encoding="utf-8") as f:
                for l in kept:
                    f.write(json.dumps(l, ensure_ascii=False, default=str) + "\n")
            logger.info("[KnowledgeSink] trimmed to %d lessons", len(kept))
        except Exception as e:
            logger.warning("[KnowledgeSink] trim failed: %s", e)

    def _update_stats(self, entry: Dict[str, Any]) -> None:
        stats = read_json(self._stats_path, {}) or {}
        stats["total_lessons"] = len(self._read_lessons())
        stats["last_updated"] = time.time()
        by_scope = stats.get("by_scope", {})
        by_scope[entry["scope"]] = by_scope.get(entry["scope"], 0) + 1
        stats["by_scope"] = by_scope
        write_json(self._stats_path, stats)

    def stats(self) -> Dict[str, Any]:
        """知识沉淀统计（供 Dashboard / 验收标准检查）"""
        lessons = self._read_lessons()
        return {
            "total_lessons": len(lessons),
            "by_decision": self._count_by(lessons, "decision"),
            "by_scope": self._count_by(lessons, "scope"),
            "lessons_path": str(self._lessons_path),
        }

    @staticmethod
    def _count_by(lessons: List[Dict[str, Any]], key: str) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for l in lessons:
            k = str(l.get(key, "unknown"))
            counts[k] = counts.get(k, 0) + 1
        return counts


# ============================================================================
#  全局单例
# ============================================================================

_global_sink: Optional[KnowledgeSink] = None


def get_knowledge_sink(data_dir: str = KnowledgeSink.DEFAULT_DIR) -> KnowledgeSink:
    """获取全局知识沉淀池单例"""
    global _global_sink
    if _global_sink is None:
        _global_sink = KnowledgeSink(data_dir=data_dir)
    return _global_sink
