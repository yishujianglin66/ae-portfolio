# -*- coding: utf-8 -*-
"""r4_applicability_probe.py — R4 适用域校验诊断（2026-09-09）

R4 目标是"第二母版泛化验证"：换异风格（叙事向/慢节奏）跑全链，
检验 R-2026-0002 的 applicability 域是否真的约束了规则注入。

本脚本先做**纯逻辑诊断**（不起管线、不渲染），回答一个问题：
    active_rules() 是否会按 applicability 的 style / duration / bgm_structure 过滤？

结论直接决定 R4 的走向：
  - 若会过滤 → 换异风格后规则自动退场，属"适用域收窄"正常运作；
  - 若不过滤 → 规则会跨风格误注入，是真实缺陷，需先修 applicability 校验。

用法: python scripts/r4_applicability_probe.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

from scripts.rule_registry import active_rules, load_ruleset  # noqa: E402

EVIDENCE = PROJ / "output" / "evidence" / "r4_applicability_20260909"


def main() -> int:
    rules = load_ruleset()
    print(f"规则库共 {len(rules)} 条")
    print()

    # 1. 列出每条 active 规则的 applicability 声明
    for r in rules:
        if r.get("status") != "active":
            continue
        ap = r.get("applicability") or {}
        print(f"[{r['rule_id']}] {r['status']}")
        print(f"  inject_point : {r.get('inject_point')}")
        print(f"  style 域     : {ap.get('style')}")
        print(f"  duration 域  : {ap.get('duration_range')}")
        print(f"  structure 域 : {ap.get('bgm_structure')}")
    print()

    # 2. 关键诊断：active_rules 的签名是否接收适用域上下文
    import inspect
    sig = inspect.signature(active_rules)
    params = list(sig.parameters)
    print(f"active_rules 形参: {params}")
    has_context = any(p in params for p in ("context", "style", "duration", "bgm_structure"))
    print(f"是否接收适用域上下文: {has_context}")
    print()

    # 3. 实证：同一调用在不同"意图风格"下返回是否相同
    #    由于接口无 style 入参，这里用"接口能力"作为证据：
    #    一次调用无法区分 amv_highenergy 与 emotional_lyric。
    got = active_rules("cut_anchor")
    print(f"active_rules('cut_anchor') 返回 {len(got)} 条:")
    for r in got:
        print(f"  - {r['rule_id']} (style 声明={r.get('applicability', {}).get('style')})")
    print()

    verdict = "NOT_ENFORCED" if not has_context else "ENFORCED"
    print("=" * 60)
    if verdict == "NOT_ENFORCED":
        print("判定: applicability 未被校验（纸面声明）")
        print("  影响: 换异风格后规则仍会注入 → 跨风格污染风险")
        print("  处置: 需为 active_rules 增加 context 过滤（R8② 前置）")
    else:
        print("判定: applicability 已被校验")
    print("=" * 60)

    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / "probe.json").write_text(json.dumps({
        "n_rules": len(rules),
        "active_rules_signature": params,
        "has_context_param": has_context,
        "verdict": verdict,
        "active_returned": [{"rule_id": r["rule_id"],
                             "declared_style": r.get("applicability", {}).get("style")}
                            for r in got],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n证据 → {EVIDENCE / 'probe.json'}")
    return 0 if verdict == "ENFORCED" else 2


if __name__ == "__main__":
    sys.exit(main())
