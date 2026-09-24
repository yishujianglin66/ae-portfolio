"""log_acceptance.py — 验收/听感事件的实时追加入口（2026-09-19）。

背景
----
`data/evolution/acceptance_log.jsonl` 是 R8③（GEPA 规则归纳）的数据前置，
要求 ≥30 条。但此前**只有一次性回填脚本**（`backfill_acceptance_log.py`），
没有"现场追加"的入口 —— 于是日志的实际形态是"某天回填 30 条，之后再无增长"，
GEPA 前置随时可能重新跌破。本脚本补上追加通道：

  · 严格沿用 acceptance_v1 schema（与既有 30 条同构，消费方无需改动）
  · kind 白名单（user_hearing / system_ab / milestone）——「听感」与
    「系统 A/B」「里程碑」必须分类，消费方要能按类别筛选，不能混为一谈
  · 去重（同 run_tag + verdict + notes 前 40 字视为重复）
  · 追加后回报累计条数与 GEPA 前置状态

用法:
  python scripts/log_acceptance.py --run-tag integration_27s_v6 \
      --verdict "不够" --notes "没跟小提琴节奏变换，视觉冲击力不到位" \
      --kind user_hearing --source "session:2026-09-19"

  python scripts/log_acceptance.py --run-tag run61 --verdict "A/B" \
      --notes "闪白覆盖 2/3→3/3" --kind system_ab --rating-a 0 --rating-b 1
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
LOG = PROJ / "data" / "evolution" / "acceptance_log.jsonl"
KINDS = ("user_hearing", "system_ab", "milestone")
GEPA_MIN = 30


def _rows() -> list[dict]:
    if not LOG.exists():
        return []
    out = []
    for ln in LOG.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out


def append_record(*, run_tag: str, verdict: str, notes: str, kind: str,
                  source: str = "session:manual",
                  versions: list[str] | None = None,
                  rating_a: int = 0, rating_b: int = 0,
                  ts: str | None = None, dry_run: bool = False) -> dict:
    """追加一条验收记录。返回 {'written': bool, 'reason': str, 'total': int}。"""
    if kind not in KINDS:
        return {"written": False, "reason": f"kind 非法(需 {'/'.join(KINDS)}): {kind}",
                "total": -1}
    if not (run_tag and verdict and notes):
        return {"written": False, "reason": "run_tag/verdict/notes 均不可为空",
                "total": -1}

    rec = {
        "schema": "acceptance_v1",
        "ts": ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "run_tag": run_tag,
        "versions": versions or [None],
        "ratings": {"a": int(rating_a), "b": int(rating_b)},
        "issues": [],
        "verdict": verdict,
        "notes": f"[{kind}] {notes}",
        "source": source,
    }

    rows = _rows()
    key = (rec["run_tag"], rec["verdict"], rec["notes"][:40])
    if any((r.get("run_tag"), r.get("verdict"),
            str(r.get("notes", ""))[:40]) == key for r in rows):
        return {"written": False, "reason": "重复记录（run_tag+verdict+notes 已存在）",
                "total": len(rows)}

    if not dry_run:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    total = len(rows) + (0 if dry_run else 1)
    return {"written": not dry_run, "reason": "ok", "total": total, "record": rec}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-tag", required=True)
    ap.add_argument("--verdict", required=True)
    ap.add_argument("--notes", required=True)
    ap.add_argument("--kind", required=True, choices=KINDS)
    ap.add_argument("--source", default="session:manual")
    ap.add_argument("--versions", default="", help="逗号分隔的版本列表")
    ap.add_argument("--rating-a", type=int, default=0)
    ap.add_argument("--rating-b", type=int, default=0)
    ap.add_argument("--ts", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    vers = [v.strip() for v in args.versions.split(",") if v.strip()] or [None]
    res = append_record(run_tag=args.run_tag, verdict=args.verdict,
                        notes=args.notes, kind=args.kind, source=args.source,
                        versions=vers, rating_a=args.rating_a,
                        rating_b=args.rating_b, ts=args.ts,
                        dry_run=args.dry_run)
    if not res["written"] and not args.dry_run:
        print(f"未写入: {res['reason']}")
        return 0 if res["total"] >= 0 else 1

    tag = "[dry-run] " if args.dry_run else ""
    print(f"{tag}已记录 [{args.kind}] {args.run_tag}: {args.verdict[:40]}")
    n = res["total"]
    print(f"累计 {n} 条 | GEPA 前置(≥{GEPA_MIN}): "
          f"{'达成' if n >= GEPA_MIN else f'未达({n}/{GEPA_MIN})'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
