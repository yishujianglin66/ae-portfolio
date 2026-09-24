"""cost_logger.py — 生产链路 LLM 成本记账（2026-09-19 接入）。

背景
----
集成计划评审 §五发现：`scripts/cost_report.py` 报表已就绪，但 `data/cost_log.jsonl`
只有 7 行、最后一笔停在 8-30 —— 因为写入方是 `puppet-automation/.../cost_tracker.py`
（OpenMontage 集成模块），**主生产链路（V4Agent）根本没接**。于是"平均成本 ≤
$0.05/条"这条验收指标既算不出也无人守。

设计取舍
--------
- **只记账，不改调用行为**：任何异常一律吞掉（记账失败绝不能中断出片）。
- 与既有 jsonl 同 schema：`scripts/cost_report.py` 无需改动即可消费。
- 单位透明：管线单价表按人民币计价（¥/1k tokens），故同时写 `cost_cny`（原生）
  与 `cost_usd`（按 AEKV_CNY_PER_USD 折算，默认 7.1）。报表读 `cost_usd`，
  但人民币原值可追溯，避免"汇率假设"被当成事实。
- 上下文（pipeline/stage）：出片主链由 production_director 通过 set_context()
  注入，报表即可按 pipeline 分组算"单条视频平均成本"。
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

DEFAULT_LOG = "data/cost_log.jsonl"
CNY_PER_USD_DEFAULT = 7.1     # 近似汇率；跨币种折算须显式暴露假设

# 出片主链上下文 (pipeline, stage)；由 set_context() 注入
_CONTEXT: dict[str, str | None] = {"pipeline": None, "stage": None}


def set_context(pipeline: str | None = None, stage: str | None = None) -> None:
    """设置后续记账行的 pipeline/stage 标签（None = 保持不变）。"""
    if pipeline is not None:
        _CONTEXT["pipeline"] = pipeline
    if stage is not None:
        _CONTEXT["stage"] = stage


def clear_context() -> None:
    _CONTEXT["pipeline"] = None
    _CONTEXT["stage"] = None


def log_path() -> Path:
    return Path(os.environ.get("AEKV_COST_LOG", DEFAULT_LOG))


def cny_per_usd() -> float:
    try:
        return float(os.environ.get("AEKV_CNY_PER_USD", CNY_PER_USD_DEFAULT))
    except ValueError:
        return CNY_PER_USD_DEFAULT


def log_cost(provider: str, action: str, cost_cny: float = 0.0,
             tokens_input: int = 0, tokens_output: int = 0,
             *, pipeline: str | None = None, stage: str | None = None,
             metadata: dict | None = None) -> bool:
    """追加一行成本记录。返回是否写入成功；**绝不抛异常**。

    provider 为本地/免费通道时也记账（cost_cny=0），这样"本地优先策略执行度"
    （cost_report 的 local_ratio）才有分母。
    """
    try:
        rate = cny_per_usd() or CNY_PER_USD_DEFAULT
        row = {
            "timestamp": time.time(),
            "provider": str(provider or "unknown"),
            "action": str(action or "unknown"),
            "cost_cny": round(float(cost_cny or 0.0), 6),
            "cost_usd": round(float(cost_cny or 0.0) / rate, 6),
            "tokens_input": int(tokens_input or 0),
            "tokens_output": int(tokens_output or 0),
            "pipeline": pipeline if pipeline is not None else _CONTEXT["pipeline"],
            "stage": stage if stage is not None else _CONTEXT["stage"],
            "metadata": metadata or {},
        }
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return True
    except Exception:  # noqa: BLE001 — 记账失败不得影响出片
        return False


def log_usage(provider: str, action: str, usage: dict, cost_cny: float,
              **kwargs) -> bool:
    """从 API usage dict 记账的便捷入口。

    usage 兼容 OpenAI/DeepSeek/ARK 三种字段命名（prompt/completion 或 input/output）。
    除 `pipeline`/`stage`/`metadata` 外的关键字参数（model/duration_s/... ）
    一律并入 metadata —— 调用方可以随手带上下文而不必构造 dict。
    """
    tin = int((usage or {}).get("prompt_tokens")
              or (usage or {}).get("input_tokens") or 0)
    tout = int((usage or {}).get("completion_tokens")
               or (usage or {}).get("output_tokens") or 0)
    if not tin and not tout:
        tin = int((usage or {}).get("total_tokens") or 0)
    meta = dict(kwargs.pop("metadata", None) or {})
    meta.update(kwargs)                     # model / duration_s / ... 全进 metadata
    return log_cost(provider, action, cost_cny, tin, tout, metadata=meta)
