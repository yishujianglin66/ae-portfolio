"""Evolution API 路由 - 自进化闭环观测 (P2)

为 ae-dashboard Evolution 页面提供只读数据:
- GET /api/v1/evolution/summary   综合概览（分数趋势/决策统计/成本/知识库）
- GET /api/v1/evolution/decisions 最近版本决策记录
- GET /api/v1/evolution/cost      成本观测（每轮进化 token/费用）

数据源全部为文件（文件即真相），无数据库依赖；文件缺失时返回空结构。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query
from loguru import logger

router = APIRouter(prefix="/api/v1", tags=["evolution"])

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_VERSIONS_DIR = _PROJECT_ROOT / "data" / "versions"
_BENCHMARK_DIR = _PROJECT_ROOT / "data" / "benchmark"
_EVOLUTION_DIR = _PROJECT_ROOT / "data" / "evolution"
# self_evolution 数据目录收口到 core.paths（运行时产物已移出代码仓库）
try:
    import sys as _sys
    if str(_PROJECT_ROOT) not in _sys.path:
        _sys.path.insert(0, str(_PROJECT_ROOT))
    from core.paths import self_evolution_dir as _paths_evo_dir
    _SELF_EVOLUTION_DIR = Path(_paths_evo_dir())
except ImportError:
    _SELF_EVOLUTION_DIR = _PROJECT_ROOT / "data" / "self_evolution"


def _read_jsonl(path: Path, limit: int = 0) -> list[dict[str, Any]]:
    """读 JSONL（尾部 limit 条；limit=0 全部）"""
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except Exception:
                    continue
    except Exception as e:
        logger.warning(f"[EvolutionAPI] read {path} failed: {e}")
        return []
    return records[-limit:] if limit > 0 else records


def _read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


@router.get("/evolution/summary")
async def evolution_summary() -> dict[str, Any]:
    """进化闭环综合概览"""
    decisions = _read_jsonl(_VERSIONS_DIR / "decision_log.jsonl")
    eval_history = _read_jsonl(_BENCHMARK_DIR / "results" / "evaluation_history.jsonl")
    cycles = _read_jsonl(_EVOLUTION_DIR / "cycle_history.jsonl")
    messages = _read_jsonl(_EVOLUTION_DIR / "messages.jsonl")

    # 分数趋势（最近 50 次评测）
    score_trend = [
        {
            "run_id": r.get("run_id", ""),
            "scope": r.get("scope", ""),
            "score": r.get("score", 0),
            "timestamp": r.get("timestamp", 0),
        }
        for r in eval_history[-50:]
    ]

    # 决策统计
    accept = sum(1 for d in decisions if d.get("decision") == "accept")
    rollback = sum(1 for d in decisions if d.get("decision") == "rollback")
    total_decisions = len(decisions)

    # 成本观测（P2 验收: token 可追踪）
    total_tokens = sum(int(c.get("cycle_tokens_used", 0) or 0) for c in cycles)
    total_cost = sum(float(c.get("cycle_cost_usd", 0.0) or 0.0) for c in cycles)
    msg_tokens = sum(int(m.get("tokens_used", 0) or 0) for m in messages)
    msg_cost = sum(float(m.get("cost_usd", 0.0) or 0.0) for m in messages)

    # 版本列表
    versions: list[dict[str, Any]] = []
    if _VERSIONS_DIR.exists():
        for vdir in sorted(_VERSIONS_DIR.iterdir()):
            if vdir.is_dir() and vdir.name.startswith("v"):
                meta = _read_json(vdir / "meta.json", {}) or {}
                versions.append({
                    "version_id": meta.get("version_id", vdir.name),
                    "scope": meta.get("scope", ""),
                    "status": meta.get("status", "unknown"),
                    "source_run_id": meta.get("source_run_id", ""),
                    "created_at": meta.get("created_at", 0),
                })

    # 知识库统计
    knowledge_stats = _read_json(_SELF_EVOLUTION_DIR / "knowledge_stats.json", {}) or {}

    return {
        "score_trend": score_trend,
        "decisions": {
            "total": total_decisions,
            "accept": accept,
            "rollback": rollback,
            "rollback_rate": round(rollback / total_decisions, 3) if total_decisions else 0.0,
        },
        "cost": {
            "total_tokens": total_tokens + msg_tokens,
            "total_cost_usd": round(total_cost + msg_cost, 6),
            "evolution_cycles": len(cycles),
        },
        "versions": versions[-20:],
        "knowledge": knowledge_stats,
        "avg_score": (
            round(sum(r.get("score", 0) for r in eval_history) / len(eval_history), 2)
            if eval_history else 0.0
        ),
    }


@router.get("/evolution/decisions")
async def evolution_decisions(
    limit: int = Query(default=50, ge=1, le=500),
    scope: str = Query(default=""),
) -> dict[str, Any]:
    """最近版本决策记录（审计）"""
    decisions = _read_jsonl(_VERSIONS_DIR / "decision_log.jsonl")
    if scope:
        decisions = [d for d in decisions if d.get("scope") == scope]
    return {"decisions": decisions[-limit:], "total": len(decisions)}


@router.get("/evolution/cost")
async def evolution_cost(
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    """成本观测 — 每轮进化的 token/费用（验收: 单次进化成本可追踪）"""
    cycles = _read_jsonl(_EVOLUTION_DIR / "cycle_history.jsonl")
    recent = cycles[-limit:]
    return {
        "cycles": recent,
        "total_tokens": sum(int(c.get("cycle_tokens_used", 0) or 0) for c in cycles),
        "total_cost_usd": round(
            sum(float(c.get("cycle_cost_usd", 0.0) or 0.0) for c in cycles), 6
        ),
        "cycle_count": len(cycles),
    }


@router.get("/evolution/knowledge")
async def evolution_knowledge(
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    """知识沉淀条目（data/self_evolution/）"""
    lessons = _read_jsonl(_SELF_EVOLUTION_DIR / "evolution_knowledge.jsonl")
    return {
        "lessons": lessons[-limit:],
        "total": len(lessons),
        "stats": _read_json(_SELF_EVOLUTION_DIR / "knowledge_stats.json", {}) or {},
    }
