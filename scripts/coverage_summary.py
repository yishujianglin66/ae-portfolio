"""coverage_summary.py — 覆盖率快照摘要（P1-B 配套，2026-09-20）。

背景
----
覆盖率采集已由 CI 强制执行（`.github/workflows/quality-hardening.yml`
的 full-suite-sharded 作业，`--cov --cov-fail-under=29`），但它只上传
`coverage.xml` 作为**临时产物**（artifact 有保留期），且 `coverage.json` 本身
6MB 级、不适合入仓。于是"ratchet 逐步上调"缺少可对照的历史快照，也缺少
"该补哪里"的施工单。

本脚本把原始报告压成小快照：
  · 总量（覆盖率/语句/覆盖数/分支）
  · 按一级包（core/ai/pipeline/...）汇总
  · **未覆盖行数最多的 N 个文件**（补测优先级）
  · god 文件专项（分解前必须先补 characterization 测试的那几个）

用法:
  python scripts/coverage_summary.py                     # 读 reports/coverage.json
  python scripts/coverage_summary.py --top 25 --json reports/coverage_summary.json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
DEFAULT_IN = PROJ / "reports" / "coverage.json"
DEFAULT_OUT = PROJ / "reports" / "coverage_summary.json"

# 已知低覆盖的"god 文件"：分解前必须先补 characterization 测试
GOD_FILES = ("filter_engine.py", "transition_engine.py",
             "text_animation_engine.py", "production_director.py")


def _norm(path: str) -> str:
    return path.replace("\\", "/")


def _top_package(path: str) -> str:
    parts = _norm(path).split("/")
    return parts[0] if len(parts) > 1 else "(根模块)"


def summarize(data: dict, top_n: int = 20) -> dict:
    files = data.get("files") or {}
    tot = data.get("totals") or {}
    by_pkg: dict[str, dict] = defaultdict(
        lambda: {"statements": 0, "covered": 0, "missed": 0, "files": 0})
    rows = []
    for path, info in files.items():
        s = info.get("summary") or {}
        st = int(s.get("num_statements", 0))
        cov = int(s.get("covered_lines", 0))
        miss = int(s.get("missing_lines", 0))
        pkg = _top_package(path)
        p = by_pkg[pkg]
        p["statements"] += st
        p["covered"] += cov
        p["missed"] += miss
        p["files"] += 1
        rows.append({
            "file": _norm(path),
            "package": pkg,
            "statements": st,
            "covered": cov,
            "missing": miss,
            "percent": round(float(s.get("percent_covered", 0.0)), 2),
        })

    rows.sort(key=lambda r: (-r["missing"], r["file"]))
    pkgs = {
        k: {**v, "percent": round(v["covered"] / v["statements"] * 100, 2)
            if v["statements"] else 0.0}
        for k, v in sorted(by_pkg.items(), key=lambda kv: -kv[1]["missed"])
    }
    god = [r for r in rows if Path(r["file"]).name in GOD_FILES]
    return {
        "totals": {
            "percent_covered": round(float(tot.get("percent_covered", 0.0)), 2),
            "num_statements": int(tot.get("num_statements", 0)),
            "covered_lines": int(tot.get("covered_lines", 0)),
            "missing_lines": int(tot.get("missing_lines", 0)),
            "num_branches": int(tot.get("num_branches", 0)),
            "covered_branches": int(tot.get("covered_branches", 0)),
        },
        "by_package": pkgs,
        "worst_files": rows[:top_n],
        "god_files": god,
        "file_count": len(rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=str(DEFAULT_IN))
    ap.add_argument("--json", dest="out", default=str(DEFAULT_OUT))
    ap.add_argument("--top", type=int, default=20)
    args = ap.parse_args()

    src = Path(args.inp)
    if not src.exists():
        print(f"找不到覆盖率原始报告: {src}\n先跑: python -m pytest --cov --cov-report=json:{src}")
        return 2
    data = json.loads(src.read_text(encoding="utf-8"))
    rep = summarize(data, top_n=args.top)

    t = rep["totals"]
    print(f"\n=== 覆盖率快照 ({t['covered_lines']}/{t['num_statements']} 行) ===")
    print(f"  总覆盖率 {t['percent_covered']}% | 分支 "
          f"{t['covered_branches']}/{t['num_branches']} | 文件 {rep['file_count']} 个")
    print("\n按包（未覆盖行数降序）:")
    for k, v in list(rep["by_package"].items())[:10]:
        print(f"  {k:16s} {v['percent']:6.2f}%  未覆盖 {v['missed']:6d} / {v['statements']}")
    print(f"\n补测优先级 Top {args.top}（未覆盖行最多）:")
    for r in rep["worst_files"]:
        print(f"  {r['missing']:5d} 行  {r['percent']:6.2f}%  {r['file']}")
    if rep["god_files"]:
        print("\ngod 文件（分解前必须先补 characterization 测试）:")
        for r in rep["god_files"]:
            print(f"  {r['file']:52s} {r['percent']:6.2f}%  未覆盖 {r['missing']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n→ {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
