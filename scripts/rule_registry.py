"""rule_registry.py — E1-1 规则蒸馏引擎 v1（seed/list/vote/retire + 管线消费 API）"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
RULESET = ROOT / "data" / "rules" / "ruleset.jsonl"
RULE_ID_RE = re.compile(r"^R-\d{4}-\d{4}$")
FORMS = ("constraint", "mapping", "dosage", "curve")
# 2026-09-19 增补 material_assign: 素材选择是真实管线阶段 (单源占比/源数/
# 同源连续段都作用在这里), R8③ 首轮有两条候选指向它 —— 没有这个注入点它们无处安放。
INJECT_POINTS = ("cut_anchor", "effect_map", "transition", "speed_curve",
                 "sfx_gain", "narrative", "material_assign")
STATUSES = ("active", "standby", "retired")

# 规则晋升/降级/退役阈值（§7.3 治理机制，消除"何时转正"的人工解释空间）:
#   active  转正:  up - down >= PROMOTE_THRESHOLD 且 evidence 完整（schema 过闸）
#   standby 降级:  down - up >= DEMOTE_THRESHOLD（投票翻负）
#   retired 退役:  standby 后继续翻负至 down - up >= RETIRE_THRESHOLD，或显式 retire
PROMOTE_THRESHOLD = 2
DEMOTE_THRESHOLD = 2
RETIRE_THRESHOLD = 4

# 首条规则：来自 2026-09-05 E0-1 二轮 A/B（闸门 2 合规）
SEED_RULE: dict[str, Any] = {
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


def load_ruleset() -> list[dict[str, Any]]:
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


def save_ruleset(rules: list[dict[str, Any]]) -> None:
    RULESET.parent.mkdir(parents=True, exist_ok=True)
    RULESET.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rules) + "\n",
        encoding="utf-8")


def validate_schema(rule: dict[str, Any]) -> list[str]:
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


def evaluate_status(rule: dict[str, Any]) -> tuple[str, str | None]:
    """确定性状态机：按投票差 + 证据完整性判定目标状态（§7.3 治理机制）。

    纯函数，不落盘，由 cmd_vote 调用并把结果写回。语义：
      retired 为终态，不可逆；
      down-up >= RETIRE_THRESHOLD 且当前 standby → retired（连续翻负退役）;
      down-up >= DEMOTE_THRESHOLD → standby（投票翻负）;
      up-down >= PROMOTE_THRESHOLD 且 schema 过闸 → active（转正）;
      其余维持现状。
    """
    votes = rule.get("votes") or {}
    up = int(votes.get("up", 0))
    down = int(votes.get("down", 0))
    diff = down - up
    cur = rule.get("status", "standby")
    if cur == "retired":
        return "retired", "终态，不可逆"
    if diff >= RETIRE_THRESHOLD and cur == "standby":
        return "retired", f"standby 后继续翻负 down-up={diff} >= {RETIRE_THRESHOLD}"
    if diff >= DEMOTE_THRESHOLD:
        return "standby", f"投票翻负 down-up={diff} >= {DEMOTE_THRESHOLD}"
    if up - down >= PROMOTE_THRESHOLD and not validate_schema(rule):
        return "active", f"支持票领先 up-down={up-down} >= {PROMOTE_THRESHOLD} 且证据完整"
    return cur, None


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


def cut_anchor_allowed(context: dict[str, Any] | None = None) -> bool | None:
    """锚点模式裁决：规则库未建立 → None（管线自便）；已建立 → 查 active 规则。

    退役/翻负的规则使本函数返回 False，production_director 自动回退启发式——
    "规则即契约"的消费端。

    context（可选）: {"style":..., "duration":..., "bgm_structure":...}
    提供时按 applicability 过滤——异风格/超时长范围运行时，不适用的规则
    自动退场，管线回退启发式（这正是 R4 泛化验证期望的行为）。
    """
    if not RULESET.exists():
        return None
    return bool(active_rules("cut_anchor", context=context))


def rule_applies(rule: dict[str, Any], context: dict[str, Any] | None = None) -> bool:
    """判断规则是否适用于当前运行上下文（applicability 校验）。

    修复（2026-09-09, R4 诊断发现）：此前 active_rules 只按 inject_point 过滤，
    applicability 里的 style/duration_range/bgm_structure 从未被校验——
    "适用域"沦为纸面声明，跨风格运行会误注入。

    校验规则（缺省的维度不约束；context 未提供的维度跳过）：
      - style          : context["style"] 须在声明列表内（大小写不敏感）
      - duration_range : context["duration"] 须落在 [lo, hi]
      - bgm_structure  : context["bgm_structure"] 须与声明列表有交集

    context=None 时视为"无信息"，一律放行（保持向后兼容，避免误伤旧调用）。
    """
    if context is None:
        return True
    ap = rule.get("applicability") or {}
    if not ap:
        return True

    # style
    declared_styles = ap.get("style") or []
    ctx_style = context.get("style")
    if declared_styles and ctx_style:
        norm = {str(s).strip().lower() for s in declared_styles}
        if str(ctx_style).strip().lower() not in norm:
            return False

    # duration_range
    dr = ap.get("duration_range")
    ctx_dur = context.get("duration")
    if (isinstance(dr, (list, tuple)) and len(dr) == 2
            and ctx_dur is not None):
        try:
            lo, hi = float(dr[0]), float(dr[1])
            if not (lo <= float(ctx_dur) <= hi):
                return False
        except (TypeError, ValueError):
            pass  # 声明不可解析 → 不约束

    # bgm_structure
    declared_struct = ap.get("bgm_structure") or []
    ctx_struct = context.get("bgm_structure") or context.get("structure")
    if declared_struct and ctx_struct:
        if isinstance(ctx_struct, str):
            ctx_set = {ctx_struct.strip().lower()}
        else:
            ctx_set = {str(s).strip().lower() for s in ctx_struct}
        declared_set = {str(s).strip().lower() for s in declared_struct}
        if not (ctx_set & declared_set):
            return False

    return True


def active_rules(inject_point: str | None = None,
                 context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """管线消费 API：返回可注入的 active 规则（schema 全过才放行，闸门 5）。

    消费方示例（production_director 锚点块）:
        rules = active_rules("cut_anchor", context={"style": "amv_highenergy",
                                                    "duration": 30})
        use_anchor_mode = bool(rules)  # 规则退役/翻负/不适用 → 自动回退启发式

    context 提供 style/duration/bgm_structure 时按 applicability 过滤；
    不传 context 则只按 inject_point + status 过滤（向后兼容）。
    """
    out = []
    for r in load_ruleset():
        if r.get("status") != "active":
            continue
        if validate_schema(r):
            continue
        if inject_point and r.get("inject_point") != inject_point:
            continue
        if not rule_applies(r, context):
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
        if run_tag:
            r.setdefault("vote_runs", []).append(
                {"run": run_tag, "vote": key, "ts": _now()})
        # 确定性状态机（§7.3）：转正 / 投票翻负降级 / 连续翻负退役
        target, reason = evaluate_status(r)
        if target != r.get("status"):
            prev = r.get("status")
            r["status"] = target
            r.setdefault("status_log", []).append(
                {"from": prev, "to": target, "reason": reason, "ts": _now()})
            print(f"[vote] {rule_id} {prev} → {target}（{reason}）")
        save_ruleset(rules)
        print(f"[vote] {rule_id} {key} 落库: {r['votes']}")
        return 0
    print(f"未找到规则 {rule_id}")
    return 1


def cmd_retire(rule_id: str, reason: str = "") -> int:
    rules = load_ruleset()
    for r in rules:
        if r["rule_id"] == rule_id:
            prev = r.get("status")
            r["status"] = "retired"
            r["retire_reason"] = reason
            r["retired_at"] = _now()
            r.setdefault("status_log", []).append(
                {"from": prev, "to": "retired", "reason": reason or "显式退役",
                 "ts": _now()})
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