#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Apply schema-validated visual effects (run53v43_effects.json, 8 条) to run53。

Usage:
    python scripts/apply_run53v43_effects.py [--dry-run]

本脚本现在只是 agents.mastercut_agent 特效链路的一层薄封装。

为什么重写 (2026-09-07): 旧实现有 6 处各自独立的致命缺陷, 任何一处都足以让它
永远产不出片子, 且彼此掩盖:
  1. 只传 1 个位置参数调 build_master_polish.py, 缺 tag → 旧版 IndexError /
     新版 argparse 直接报 "the following arguments are required: tag"。
  2. args["script"] 传的是 jsx_script.name (文件名字符串), 而监听器执行
     new Function(args.script) → 等于把 "apply_run53v43_effects.jsx" 当 JS 跑。
  3. 判定 jsx_result.get("success"), 但 Bridge 结果结构是 {"status":"success",
     "result":{...}} — 根本没有 success 键, 恒为 None → 永远报失败; 且超时
     返回 None 时 .get() 直接 AttributeError。
  4. 裸调 ["aerender", ...] 依赖 PATH, 项目为此专门提供 core.paths.aerender_exe()。
  5. 渲染 -comp POLISH 且找 run53v43_polish.aep, 但 build 建的合成叫 MASTER、
     落在 polish/master.aep — 名称与路径双重对不上。
  6. 只检查产物是否存在, 不校验体积 → 黑屏空片会被当成成功 (违反 >100KB 铁律)。

单一可信实现现在在 agents/mastercut_agent.py::_apply_effects_to_video,
渲染步骤在 scripts/render_master.py。要改行为请改那里, 不要在此复制逻辑。
"""
import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from agents.mastercut_agent import _apply_effects_to_video, _validate_effect_configs  # noqa: E402

RUN_DIR = PROJECT / "output" / "unified_run53"
EFFECTS_JSON = RUN_DIR / "run53v43_effects.json"


def apply_effects_to_video(dry_run: bool = False) -> bool:
    """把 run53v43_effects.json 灌进 schema 注入链路, 如实返回是否全部生效。"""
    if not EFFECTS_JSON.exists():
        print(f"[ERROR] Effects config not found: {EFFECTS_JSON}")
        return False

    effects = json.loads(EFFECTS_JSON.read_text(encoding="utf-8"))
    if isinstance(effects, dict):
        effects = effects.get("effects") or effects.get("effect_configs") or [effects]
    print(f"[INFO] Loaded {len(effects)} effects from {EFFECTS_JSON.name}")

    # 先做 schema 校验 — 不合法就没必要启动耗时的 build/render
    val = _validate_effect_configs(effects)
    if not val.get("valid"):
        print(f"[ERROR] schema 校验未通过 {len(val.get('errors', []))} 条:")
        for er in val.get("errors", [])[:10]:
            print(f"  #{er.get('effect_index')}: {er.get('error')}")
        return False
    print("[INFO] schema validation passed for all effects")

    result = _apply_effects_to_video(
        effects=effects,
        output_dir=str(RUN_DIR),
        dry_run=dry_run,
    )

    req = result.get("effects_requested", len(effects))
    applied = result.get("effects_applied", 0)
    unmapped = result.get("effects_unmapped", 0)
    skipped = result.get("effects_skipped", 0)

    print("\n" + "=" * 62)
    print("特效执行对账")
    print("=" * 62)
    print(f"  请求   : {req}")
    print(f"  已生效 : {applied}")
    print(f"  无实现 : {unmapped}")
    print(f"  己跳过 : {skipped}")
    if unmapped:
        print("  无实现明细:")
        for t, v in sorted((result.get("unmapped_types") or {}).items(),
                           key=lambda kv: -kv[1].get("count", 0)):
            print(f"    {t}: {v.get('count')} 条 — {v.get('reason')}")

    if not result.get("success"):
        print(f"\n[FAIL] stage={result.get('stage')}: {result.get('error')}")
        for key in ("stderr", "render_stderr"):
            body = (result.get(key) or "").strip()
            if body:
                print(f"  {key}: {body[-600:]}")
        return False

    if applied < req:
        print(f"\n[PARTIAL] {applied}/{req} 生效 — 补齐 RECIPES 映射前不算完整交付")
        print("  详见 tmp/effects_injection_report.json")
        return False

    print(f"\n[OK] {result.get('note') or '全部特效已生效'}")
    if not dry_run and result.get("output_video"):
        p = Path(result["output_video"])
        print(f"  产物: {p} ({p.stat().st_size / (1024 * 1024):.1f} MB)")
    return True


if __name__ == "__main__":
    sys.exit(0 if apply_effects_to_video("--dry-run" in sys.argv[1:]) else 1)
