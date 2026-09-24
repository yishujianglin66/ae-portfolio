# -*- coding: utf-8 -*-
"""成本记账单测 (2026-09-19 接入生产)。

背景: 集成计划评审 §五发现 cost_report 报表早已就绪, 但 `data/cost_log.jsonl`
只有 7 行、最后一笔停在 8-30 —— 写入方是 OpenMontage 集成模块, **主生产链路
(V4Agent) 根本没接**。于是"平均成本 ≤ $0.05/条"这条验收指标既算不出也无人守。

本测试锁定四件事:
  1. 写入 schema 与既有 jsonl 一致 (cost_report 可无改动消费)
  2. usage 字段三种命名 (prompt/completion、input/output、total) 都能记账
  3. **记账失败绝不抛异常** (出片不能因为记账挂掉)
  4. 上下文 pipeline/stage 能标注到行, 供报表做"单条视频平均成本"分组
"""
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core import cost_logger  # noqa: E402


@pytest.fixture()
def logfile(tmp_path, monkeypatch):
    p = tmp_path / "cost_log.jsonl"
    monkeypatch.setenv("AEKV_COST_LOG", str(p))
    cost_logger.clear_context()
    yield p
    cost_logger.clear_context()


def _rows(p: Path) -> list[dict]:
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_writes_report_compatible_schema(logfile):
    """字段必须与 cost_report.summarize 读取的键一致。"""
    assert cost_logger.log_cost("deepseek", "ask", 0.0212, 3023, 500)
    r = _rows(logfile)[0]
    for k in ("timestamp", "provider", "action", "cost_cny", "cost_usd",
              "tokens_input", "tokens_output", "pipeline", "stage", "metadata"):
        assert k in r, k
    assert r["provider"] == "deepseek" and r["action"] == "ask"
    assert r["tokens_input"] == 3023 and r["tokens_output"] == 500
    assert r["cost_usd"] == pytest.approx(0.0212 / 7.1, rel=1e-3)


def test_report_consumes_rows(logfile):
    """写出的行能被既有报表脚本直接汇总 (不要求改报表)。"""
    cost_logger.set_context(pipeline="tag_x")
    cost_logger.log_cost("deepseek", "ask", 0.02, 100, 50)
    cost_logger.log_cost("comfyui", "r5_gen", 0.0)
    spec = importlib.util.spec_from_file_location(
        "cost_report", PROJECT / "scripts" / "cost_report.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    rep = m.summarize(_rows(logfile))
    assert rep["n_records"] == 2
    assert rep["by_pipeline"]["tag_x"]["calls"] == 2
    assert rep["local_calls"] == 1 and rep["cloud_calls"] == 1   # 本地优先可度量


@pytest.mark.parametrize("usage,tin,tout", [
    ({"prompt_tokens": 10, "completion_tokens": 5}, 10, 5),      # OpenAI/DeepSeek
    ({"input_tokens": 7, "output_tokens": 3}, 7, 3),             # Anthropic 风格
    ({"total_tokens": 42}, 42, 0),                               # 只有总数
    ({}, 0, 0),
])
def test_usage_field_variants(logfile, usage, tin, tout):
    """三种 usage 命名都要能记进 tokens 字段。"""
    cost_logger.log_usage("p", "a", usage, 0.0)
    r = _rows(logfile)[0]
    assert (r["tokens_input"], r["tokens_output"]) == (tin, tout)


def test_extra_kwargs_go_to_metadata(logfile):
    """model/duration_s 等随手上下文进 metadata, 不污染顶层 schema。"""
    cost_logger.log_usage("deepseek", "ask", {"total_tokens": 1}, 0.01,
                          model="deepseek-v4-pro", duration_s=32.7)
    r = _rows(logfile)[0]
    assert r["metadata"]["model"] == "deepseek-v4-pro"
    assert r["metadata"]["duration_s"] == 32.7
    assert "model" not in r


def test_context_annotates_and_clears(logfile):
    cost_logger.set_context(pipeline="vid_1", stage="stage3_render")
    cost_logger.log_cost("x", "y", 0.0)
    r = _rows(logfile)[0]
    assert (r["pipeline"], r["stage"]) == ("vid_1", "stage3_render")
    cost_logger.clear_context()
    cost_logger.log_cost("x", "y", 0.0)
    r2 = _rows(logfile)[1]
    assert r2["pipeline"] is None and r2["stage"] is None


def test_explicit_args_override_context(logfile):
    cost_logger.set_context(pipeline="ctx_pipe")
    cost_logger.log_cost("x", "y", 0.0, pipeline="explicit")
    assert _rows(logfile)[0]["pipeline"] == "explicit"


def test_failure_is_silent(tmp_path, monkeypatch):
    """路径不可写时必须静默返回 False —— 记账失败不得中断出片。"""
    monkeypatch.setenv("AEKV_COST_LOG", str(tmp_path / "nonexistent_dir_deeper" / "x" / "log.jsonl"))
    # 人为让 mkdir 失败
    monkeypatch.setattr(Path, "mkdir",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("denied")))
    assert cost_logger.log_cost("p", "a", 0.0) is False


def test_cny_rate_is_configurable(logfile, monkeypatch):
    monkeypatch.setenv("AEKV_CNY_PER_USD", "10")
    cost_logger.log_cost("p", "a", 10.0)
    assert _rows(logfile)[0]["cost_usd"] == pytest.approx(1.0, rel=1e-6)


def test_ai_agent_helper_is_wired():
    """生产链路 (V4Agent) 必须真的调用记账 —— 这是本轮接入的核心。"""
    src = (PROJECT / "ai" / "ai_agent.py").read_text(encoding="utf-8")
    assert "def _log_llm_cost" in src
    assert src.count("_log_llm_cost(") >= 4     # 定义 1 处 + 至少 3 个调用点
    for action in ("ask", "chat_tools", "ark_chat", "gateway_chat"):
        assert f'"{action}"' in src, action
