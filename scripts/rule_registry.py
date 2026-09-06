"""rule_registry.py — E1-1 规则蒸馏引擎 v1（seed/list/vote/retire + 管线消费 API）"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
RULESET = ROOT / "data" / "rules" / "ruleset.jsonl"
RULE_ID_RE = re.compile(r"^R-\d{4}-\d{4}$")
FORMS = ("constraint", "mapping", "dosage", "curve")
INJECT_POINTS = ("cut_anchor", "effect_map", "transition", "speed_curve",
                 "sfx_gain", "narrative")
STATUSES = ("active", "standby", "retired")
VOTE_RETIRE_THRESHOLD = 2  # down 比 up 多出该数量 → 自动降级 standby

# 首条规则：来自 2026-09-05 E0-1 二轮 A/B（闸门 2 合规）
SEED_RULE: Dict[str, Any] = {
    "rule_id": "R-2026-0001",
    "statement": "切点必须锚定 stem 真实鼓点：kick/snare（strength≥0.5 为强锚），"
                 "笼统 onset（含 hihat/人声瞬态）退出切点候选池",
    "form": "constraint",
    "inject_point": "cut_anchor",
    "applicability": {
        "duration_range": [15, 45],
        "bgm_structure": ["intro", "build", "drop"],
        "style": ["amv_highenergy", "燃向"],
        "exceptions": "low 能量段保持长镜头呼吸，不强制快切（沿用 2026-08-13 口径）",
    },
    "confidence": 0.9,
    "evidence": {
        "source_runs": ["run54anchor", "run54ctrl"],
        "gate_score_delta": "kick|snare 踩拍 +0.1478；笼统踩拍 +0.0624（run53 基线 0.7712→0.8077）",
        "artifacts": ["ab_result.json", "plan_diag_round2.txt", "anchors.json",
                      "smoke_summary.json"],
    },
    "votes": {"up": 1, "down": 0},
    "created": "2026-09-05",
    "last_confirmed": "2026-09-05",
    "status": "active",
}


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _today() -> str:
    return time.strftime("%Y-%m-%d")


def load_ruleset() -> List[Dict[str, Any]]:
    if not RULESET.exists():
        return []
    rules = []
    for line in RULESET.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rules.append(json.loads(line))
        except ValueError as e:
            print("[ruleset] 存在坏行(非 JSON)，已跳过")
    return rules


def save_ruleset(rules: List[Dict[str, Any]]) -> None:
    RULESET.parent.mkdir(parents=True, exist_ok=True)
    RULESET.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rules) + "\n",
        encoding="utf-8")


def validate_schema(rule: Dict[str, Any]) -> List[str]:
    """闸门 3 风格的三对齐：rule_id 白名单 + 枚举字段 + 必填证据。"""
    errs = []
    rid = str(rule.get("rule_id", ""))
    if not RULE_ID_RE.match(rid):
        errs.append(f"rule_id 非法(需 R-####-####): {rid}")
    for k in ("statement", "form", "inject_point", "status"):
        if not rule.get(k):
            errs.append(f"缺必填字段 {k}")
    if rule.get("form") not in FORMS:
        errs.append(f"form 非法: {rule.get('form')}")
    if rule.get("inject_point") not in INJECT_POINTS:
        errs.append(f"inject_point 非法: {rule.get('inject_point')}")
    if rule.get("status") not in STATUSES:
        errs.append(f"status 非法: {rule.get('status')}")
    if not (rule.get("evidence") or {}).get("gate_score_delta"):
        errs.append("evidence.gate_score_delta 缺失（无量化证据的规则不得 active）")
    return errs


def cmd_seed() -> int:
    rules = load_ruleset()
    if any(r.get("rule_id") == SEED_RULE["rule_id"] for r in rules):
        print("R-2026-0001 已存在，跳过播种")
        return 0
    errs = validate_schema(SEED_RULE)
    if errs:
        print("种子规则 schema 校验失败:", errs)
        return 1
    rules.append(SEED_RULE)
    save_ruleset(rules)
    print(f"已播种 {SEED_RULE['rule_id']} → {RULESET}")
    return 0


def cmd_list() -> int:
    rules = load_ruleset()
    if not rules:
        print("规则库为空（先运行 seed）")
        return 0
    print(f"{'rule_id':<13}{'status':<9}{'form':<12}{'inject_point':<13}{'up/down':<8}陈述")
    for r in rules:
        v = r.get("votes", {})
        print(f"{r['rule_id']:<13}{r['status']:<9}{r['form']:<12}"
              f"{r['inject_point']:<13}{v.get('up', 0)}/{v.get('down', 0):<5}"
              f"{r['statement'][:48]}")
    return 0


def cut_anchor_allowed() -> Optional[bool]:
    """锚点模式裁决：规则库未建立 → None（管线自便）；已建立 → 查 active 规则。

    退役/翻负的规则使本函数返回 False，production_director 自动回退启发式——
    "规则即契约"的消费端。
    """
    if not RULESET.exists():
        return None
    return bool(active_rules("cut_anchor"))


def active_rules(inject_point: Optional[str] = None) -> List[Dict[str, Any]]:
    """管线消费 API：返回可注入的 active 规则（schema 全过才放行，闸门 5）。

    消费方示例（production_director 锚点块）:
        rules = active_rules("cut_anchor")
        use_anchor_mode = bool(rules)  # 规则退役/翻负 → 自动回退启发式
    """
    out = []
    for r in load_ruleset():
        if r.get("status") != "active":
            continue
        if validate_schema(r):
            continue
        if inject_point and r.get("inject_point") != inject_point:
            continue
        out.append(r)
    return out


def cmd_vote(rule_id: str, up: bool, run_tag: str = "") -> int:
    rules = load_ruleset()
    for r in rules:
        if r["rule_id"] != rule_id:
            continue
        key = "up" if up else "down"
        r["votes"][key] = r["votes"].get(key, 0) + 1
        r["last_confirmed"] = _today()
        # 退役条款 §7.3-5: 反对票显著领先 → 自动 standby
        if r["votes"].get("down", 0) - r["votes"].get("up", 0) >= VOTE_RETIRE_THRESHOLD:
            r["status"] = "standby"
            print(f"[vote] {rule_id} 反对票领先 → 自动降级 standby")
        if run_tag:
            r.setdefault("vote_runs", []).append(
                {"run": run_tag, "vote": key, "ts": _now()})
        save_ruleset(rules)
        print(f"[vote] {rule_id} {key} 落库: {r['votes']}")
        return 0
    print(f"未找到规则 {rule_id}")
    return 1


def cmd_retire(rule_id: str, reason: str = "") -> int:
    rules = load_ruleset()
    for r in rules:
        if r["rule_id"] == rule_id:
            r["status"] = "retired"
            r["retire_reason"] = reason
            r["retired_at"] = _now()
            save_ruleset(rules)
            print(f"[retire] {rule_id} 已退役（{reason}）——管线自动回退启发式")
            return 0
    print(f"未找到规则 {rule_id}")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="规则蒸馏引擎 v1")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    sub.add_parser("list")
    v = sub.add_parser("vote")
    v.add_argument("--rule", required=True)
    v.add_argument("--up", action="store_true")
    v.add_argument("--down", dest="up", action="store_false")
    v.add_argument("--run", default="")
    r = sub.add_parser("retire")
    r.add_argument("--rule", required=True)
    r.add_argument("--reason", default="")
    args = ap.parse_args()
    if args.cmd == "seed":
        return cmd_seed()
    if args.cmd == "list":
        return cmd_list()
    if args.cmd == "vote":
        return cmd_vote(args.rule, args.up, args.run)
    if args.cmd == "retire":
        return cmd_retire(args.rule, args.reason)
    return 1


if __name__ == "__main__":
    sys.exit(main())
