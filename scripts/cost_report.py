# -*- coding: utf-8 -*-
"""cost_report.py — 成本报表（基于已有 data/cost_log.jsonl）

背景（集成计划评审 §五）：项目已有 cost_log.jsonl 记录通道（cost_logger 写入），
但缺汇总视图。本脚本补齐——**基于既有数据做报表，不新建成本系统**。

输出：
  - 按 provider 汇总（调用数 / tokens / 成本）
  - 按 action 汇总
  - 本地 vs 云端占比（local_ratio，印证"本地优先"策略执行度）
  - 单条视频平均成本（按 pipeline 分组）

用法: python scripts/cost_report.py [--log data/cost_log.jsonl] [--out reports/cost_report.json]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent

# 本地/免费 provider 标识（不计费）
LOCAL_PROVIDERS = {"system", "local", "comfyui", "cpu", "gpu"}


def load(log_path: Path) -> list[dict]:
    rows = []
    if not log_path.exists():
        return rows
    for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def summarize(rows: list[dict]) -> dict:
    by_provider: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "cost_usd": 0.0, "tokens_in": 0, "tokens_out": 0})
    by_action: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "cost_usd": 0.0})
    by_pipeline: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "cost_usd": 0.0})

    total_cost = 0.0
    local_calls = cloud_calls = 0
    for r in rows:
        prov = str(r.get("provider", "unknown"))
        action = str(r.get("action", "unknown"))
        cost = float(r.get("cost_usd", 0.0) or 0.0)
        p = by_provider[prov]
        p["calls"] += 1
        p["cost_usd"] += cost
        p["tokens_in"] += int(r.get("tokens_input", 0) or 0)
        p["tokens_out"] += int(r.get("tokens_output", 0) or 0)
        by_action[action]["calls"] += 1
        by_action[action]["cost_usd"] += cost
        pipe = r.get("pipeline")
        if pipe:
            by_pipeline[str(pipe)]["calls"] += 1
            by_pipeline[str(pipe)]["cost_usd"] += cost
        total_cost += cost
        if prov.lower() in LOCAL_PROVIDERS:
            local_calls += 1
        else:
            cloud_calls += 1

    def _round(d: dict) -> dict:
        return {k: {kk: (round(vv, 4) if isinstance(vv, float) else vv)
                    for kk, vv in v.items()} for k, v in d.items()}

    return {
        "n_records": len(rows),
        "total_cost_usd": round(total_cost, 4),
        "by_provider": _round(dict(by_provider)),
        "by_action": _round(dict(by_action)),
        "by_pipeline": _round(dict(by_pipeline)),
        "local_calls": local_calls,
        "cloud_calls": cloud_calls,
        "local_ratio": round(local_calls / len(rows), 4) if rows else None,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=str(PROJ / "data" / "cost_log.jsonl"))
    ap.add_argument("--out", default=str(PROJ / "reports" / "cost_report.json"))
    args = ap.parse_args()

    log_path = Path(args.log)
    rows = load(log_path)
    rep = summarize(rows)
    rep["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rep["log_path"] = str(log_path)

    print(f"记录数: {rep['n_records']} | 总成本 ${rep['total_cost_usd']}")
    print(f"本地/云端调用: {rep['local_calls']}/{rep['cloud_calls']}"
          f"（本地占比 {rep['local_ratio']}）")
    print("\n按 provider:")
    print(f"  {'provider':<14}{'calls':>7}{'cost$':>10}{'tok_in':>10}{'tok_out':>10}")
    for k, v in sorted(rep["by_provider"].items(),
                       key=lambda x: -x[1]["cost_usd"]):
        print(f"  {k:<14}{v['calls']:>7}{v['cost_usd']:>10}"
              f"{v['tokens_in']:>10}{v['tokens_out']:>10}")
    if rep["by_action"]:
        print("\n按 action:")
        for k, v in sorted(rep["by_action"].items(), key=lambda x: -x[1]["calls"]):
            print(f"  {k:<24}{v['calls']:>6} 次  ${v['cost_usd']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
