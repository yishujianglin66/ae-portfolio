# -*- coding: utf-8 -*-
"""render_audit.py — 统一渲染审计索引 (2026-09-06, 工程分析报告 #5)

把一次渲染的「切点 / 运镜 / 评分 / 闸门 / 规则命中」聚合成一条可查询 jsonl
（落 data/evolution/render_audit.jsonl）。零主线侵入：只读既有产物，不改任何调用点。

产物源:
  production_report.json → 切点(start_time) / 变速(speed) / 运镜(zoompan_effect)
  unified_report.json   → 评分(scores) / 运镜标注(motion_labels)
  render_gate.py        → 七项闸门 PASS/FAIL + ACCEPT
  rule_registry         → active 规则命中

用法:
  python scripts/render_audit.py <run_dir> <tag> [--bgm xx.mp3] [--no-gate]
  python scripts/render_audit.py --list [-n 10]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJ = Path(__file__).resolve().parent.parent
AUDIT = PROJ / "data" / "evolution" / "render_audit.jsonl"
_GATE_RE = re.compile(r"\[(PASS|FAIL)\] ([^:]+): (.+)")


def _load_json(p: Path) -> dict[str, Any] | None:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cuts_stats(segs: list[dict]) -> dict[str, Any]:
    """切点统计：数量 + 间隔中位/极值（量化"卡点密度与呼吸"）。"""
    starts = sorted(s["start_time"] for s in segs
                    if s.get("start_time", 0) > 0.05)
    if not starts:
        return {"n": 0}
    gaps = [starts[i + 1] - starts[i] for i in range(len(starts) - 1)]
    return {
        "n": len(starts),
        "median_gap": round(sorted(gaps)[len(gaps) // 2], 3) if gaps else None,
        "min_gap": round(min(gaps), 3) if gaps else None,
        "max_gap": round(max(gaps), 3) if gaps else None,
    }


def speed_stats(segs: list[dict]) -> dict[str, Any]:
    sp = [round(float(s.get("speed", 1.0)), 2) for s in segs if s.get("speed")]
    jumps = sum(1 for i in range(len(sp) - 1) if abs(sp[i + 1] - sp[i]) >= 0.4)
    return {"dist": dict(Counter(str(x) for x in sp)), "jumps": jumps}


def camera_stats(segs: list[dict],
                 motion_labels: dict | None) -> dict[str, Any]:
    """运镜：编排端 technique 分布 + 感知端 motion 标注分布。"""
    tech = Counter(str(s.get("zoompan_effect")) for s in segs
                   if s.get("zoompan_effect"))
    ml = Counter(str(m.get("motion")) for m in (motion_labels or {}).values()
                 if isinstance(m, dict) and m.get("motion"))
    return {"technique_dist": dict(tech), "motion_label_dist": dict(ml)}


def parse_gate_stdout(text: str) -> dict[str, Any]:
    """解析 render_gate.py 的 [PASS|FAIL] name: detail 输出 + ACCEPT/REJECT。"""
    checks = re.findall(_GATE_RE, text)
    detail = {name.strip(): d.strip() for _, name, d in checks}
    return {
        "pass": sum(1 for c, _, _ in checks if c == "PASS"),
        "total": len(checks),
        "detail": detail,
        "accepted": "ACCEPT" in text,
    }


def gate_from(run_dir: Path, tag: str, bgm: str | None = None,
              timeout: int = 900) -> dict[str, Any]:
    cmd = [sys.executable, str(PROJ / "scripts" / "render_gate.py"),
           str(run_dir), tag]
    if bgm:
        cmd += ["--bgm", bgm]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        return parse_gate_stdout(r.stdout)
    except Exception as e:  # 闸门缺失/超时 → 审计不因闸门失败而中断
        return {"pass": None, "total": None, "detail": {},
                "accepted": None, "error": type(e).__name__}


def rules_snapshot() -> list[dict[str, str]]:
    try:
        from scripts.rule_registry import active_rules
        return [{"rule_id": r.get("rule_id"),
                 "inject_point": r.get("inject_point"),
                 "status": r.get("status")} for r in active_rules()]
    except Exception:
        return []


def ae_failures(run_dir: Path) -> list[dict[str, Any]]:
    """读取 ae_failures.json（桥接失败结构化 #3 产物）。"""
    p = run_dir / "ae_failures.json"
    if not p.exists():
        return []
    data = _load_json(p)
    return data if isinstance(data, list) else []


def build_audit(run_dir: Path, tag: str, bgm: str | None = None,
                run_gate: bool = True) -> dict[str, Any]:
    pr = _load_json(run_dir / "production_report.json") or {}
    unirep = _load_json(run_dir / "unified_report.json") or {}
    segs = pr.get("script", {}).get("segments") or pr.get("segments") or []
    rec: dict[str, Any] = {
        "schema": "render_audit_v1",
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "run_tag": tag,
        "run_dir": str(run_dir).replace("\\", "/"),
        "cuts": cuts_stats(segs),
        "speed": speed_stats(segs),
        "camera": camera_stats(segs, unirep.get("motion_labels")),
        "score": unirep.get("scores") or {},
        "rules": rules_snapshot(),
        "ae_failures": ae_failures(run_dir),
        "meta": {
            "render_success": pr.get("render_success"),
            "content_verified": pr.get("content_verified"),
            "elapsed_s": unirep.get("elapsed_s"),
        },
    }
    rec["gate"] = gate_from(run_dir, tag, bgm) if run_gate else \
        {"pass": None, "total": None, "detail": {}, "accepted": None}
    return rec


def append(rec: dict[str, Any]) -> None:
    AUDIT.parent.mkdir(parents=True, exist_ok=True)
    with open(AUDIT, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def cmd_audit(run_dir: str, tag: str, bgm: str | None, no_gate: bool) -> int:
    rec = build_audit(Path(run_dir), tag, bgm, run_gate=not no_gate)
    append(rec)
    g = rec["gate"]
    gate_str = (f"{g.get('pass')}/{g.get('total')} accepted={g.get('accepted')}"
                if g.get("pass") is not None else "跳过")
    print(f"[审计] {tag} 切点={rec['cuts'].get('n')} "
          f"运镜档={len(rec['camera']['technique_dist'])} "
          f"评分overall={rec['score'].get('score_overall')} "
          f"闸门={gate_str} 规则命中={len(rec['rules'])} "
          f"AE失败={len(rec['ae_failures'])}")
    print(f"[落盘] {AUDIT}")
    return 0


def cmd_list(n: int) -> int:
    if not AUDIT.exists():
        print("审计索引为空")
        return 0
    rows = []
    for line in AUDIT.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    print(f"共 {len(rows)} 条审计记录（最近 {min(n, len(rows))} 条）:")
    for r in reversed(rows[-n:]):
        g = r.get("gate", {})
        gs = (f"gate={g.get('pass')}/{g.get('total')}"
              if g.get("pass") is not None else "gate=skip")
        sc = r.get("score", {}).get("score_overall")
        print(f"  {r['run_tag']:<8} cuts={r['cuts'].get('n'):<4} "
              f"overall={sc} {gs} rules={len(r.get('rules', []))}  {r['ts']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="统一渲染审计索引")
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("tag", nargs="?")
    ap.add_argument("--bgm", default=None)
    ap.add_argument("--no-gate", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("-n", type=int, default=10)
    args = ap.parse_args()
    if args.list:
        return cmd_list(args.n)
    if not args.run_dir or not args.tag:
        ap.error("需 <run_dir> <tag> 或 --list")
    return cmd_audit(args.run_dir, args.tag, args.bgm, args.no_gate)


if __name__ == "__main__":
    sys.exit(main())