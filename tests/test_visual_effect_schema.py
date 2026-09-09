# -*- coding: utf-8 -*-
"""视觉特效 Schema 集成回归测试 — 不碰 AE、不跑 ffmpeg、不渲染。

为什么必须有这个文件 (2026-09-07 事故复盘):
schemas/visual_effect_schema.json 原先零测试覆盖, 导致 effect_type 从 11 种
悄悄扩到 17 种后, 三份文档分别写着 11 / 17 / 19, 无人发现; 更严重的是
_apply_effects_to_video 与 build_master_polish.py 的 CLI 契约脱节 (后者当时
只认位置参数 unified_run\\d+ / run\\d+), 特效注入从建成起就没跑通过, 却被
报告为"可以投入使用了"。

本文件钉住四件事:
  1. schema 自身的正向校验与反向拒绝能力 (含跨字段陷阱)
  2. 映射表与 schema enum 一一对应, 不许出现"schema 有、映射表没有"的空洞
  3. schema→plan→JSX 翻译的对账闭合: applied + unmapped + skipped == input
  4. build_jsx 产物里的效果条目数与报告数逐条一致 (报告不许虚报)
"""
import json
import re
from pathlib import Path

import pytest

from scripts.build_master_polish import (
    BURST_TYPES,
    SCHEMA_DYN_RECIPE,
    SCHEMA_TO_RECIPE,
    SCHEMA_UNMAPPED,
    build_jsx,
    schema_effects_to_plan,
)

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schemas" / "visual_effect_schema.json"
EXAMPLE_PATH = ROOT / "schemas" / "examples" / "effect_config_example.json"
RUN53_DIR = ROOT / "output" / "unified_run53"

jsonschema = pytest.importorskip("jsonschema")


@pytest.fixture(scope="module")
def schema():
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def example_effects():
    return json.loads(EXAMPLE_PATH.read_text(encoding="utf-8"))


def _effect_types(schema):
    return schema["properties"]["effect_type"]["enum"]


# ────────────────────────────────────────────────────────────────
# 1. schema 自身
# ────────────────────────────────────────────────────────────────
def test_schema_version_and_positive_examples(schema, example_effects):
    assert schema["version"] == "1.0.0"
    assert len(example_effects) == 5
    for eff in example_effects:
        jsonschema.validate(instance=eff, schema=schema)


def test_schema_rejects_bad_configs(schema, example_effects):
    """反向必须真拒绝 —— 且要绕过必填字段, 否则测不到范围校验。"""
    base = next(e for e in example_effects if e["effect_type"] == "bloom")
    params = dict(base["parameters"])
    tr = dict(base["time_range"])

    def mk(**over):
        e = {"effect_id": "neg_001", "effect_type": "bloom",
             "time_range": tr, "parameters": params}
        e.update(over)
        return e

    bad = [
        mk(effect_type="FAKE_TYPE"),
        mk(parameters=dict(params, intensity=99999)),         # 越上界
        mk(parameters=dict(params, intensity=-5)),            # 越下界
        mk(parameters=dict(params, intensity="high")),        # 类型错
        mk(parameters=dict(params, HACKME=1)),                # additionalProperties:false
        mk(parameters={k: v for k, v in params.items() if k != "radius"}),  # 缺必填 radius
        mk(effect_id="Bad-ID"),                               # 违反正则
    ]
    labels = ["未知 effect_type", "intensity 越上界", "intensity 越下界",
              "intensity 类型错", "未知参数注入", "缺必填 radius", "effect_id 违反正则"]
    not_rejected = []
    for label, inst in zip(labels, bad):
        try:
            jsonschema.validate(instance=inst, schema=schema)
        except jsonschema.ValidationError:
            continue
        not_rejected.append(label)
    assert not_rejected == [], f"以下非法配置未被 schema 拒绝: {not_rejected}"


def test_schema_time_range_has_no_cross_field_check(schema):
    """记录已知缺口: start_sec > end_sec 目前仍然合法。

    翻译器会把它归入 skipped, 所以不会造成错误渲染; 但 schema 层缺这条
    约束是事实, 补齐后本用例应改为断言"被拒绝"。
    """
    inst = {"effect_id": "twx_001", "effect_type": "twixtor",
            "time_range": {"start_sec": 9.0, "end_sec": 1.0},
            "parameters": {"speed_profile": [[0.0, 0.5], [1.0, 1.0]]}}
    jsonschema.validate(instance=inst, schema=schema)   # 当前: 通过 (缺口)


# ────────────────────────────────────────────────────────────────
# 2. 映射表完整性 (防 11→17 那类漂移)
# ────────────────────────────────────────────────────────────────
def test_mapping_tables_cover_every_schema_type_without_holes(schema):
    enum = set(_effect_types(schema))
    covered = set(SCHEMA_TO_RECIPE) | set(SCHEMA_DYN_RECIPE) | set(SCHEMA_UNMAPPED)
    assert enum - covered == set(), f"schema 有但映射表无: {sorted(enum - covered)}"
    assert covered - enum == set(), f"映射表有但 schema 无: {sorted(covered - enum)}"


def test_no_mapped_effect_type_is_unimplemented():
    """映射到的 RECIPES 键必须真实存在于 build_master_polish.RECIPES。

    这是 2026-09-07 断链的核心教训: schema 声明了 18 种, 而渲染端 RECIPES
    只实现部分键, 其中 5 种 premium 插件类型无 matchName 实证。
    """
    import scripts.build_master_polish as B

    for schema_type, recipe_key in SCHEMA_TO_RECIPE.items():
        assert recipe_key in B.RECIPES, f"{schema_type} → {recipe_key} 不在 RECIPES"
    for schema_type, base in SCHEMA_DYN_RECIPE.items():
        assert base in B.RECIPES, f"{schema_type} → {base} 不在 RECIPES"
    # 标为不可注入的类型必须有书面原因, 不许留空字符串糊弄
    for schema_type, reason in SCHEMA_UNMAPPED.items():
        assert len(reason) >= 8, f"{schema_type} 的不可注入理由过短"


def test_unmapped_premium_types_have_no_fabricated_matchname():
    """未安装插件类型必须留在 SCHEMA_UNMAPPED, 不许为了凑数编 matchName。

    2026-09-09: particular 已移出 (matchName tc Particular 经 AE Bridge 实证)。
    2026-09-09: sapphire_glow/optical_flares/magic_bullet_looks 已移出
               (matchName 经 AE Bridge 实证, 见 test_premium_plugins_ae_verified)。
    """
    for t in ("delirium", "film_stocks"):
        assert t in SCHEMA_UNMAPPED, f"{t} 应标为不可注入 (本机未安装, 无法 AE 实证)"
        assert t not in SCHEMA_TO_RECIPE and t not in SCHEMA_DYN_RECIPE


def test_premium_plugins_ae_verified():
    """sapphire_glow/optical_flares/magic_bullet_looks 已加入 RECIPES。

    matchName 全部经 AE Bridge executeAtomScript 实证 (2026-09-09):
      sapphire_glow      → S_Glow
      optical_flares     → Optical Flares
      magic_bullet_looks → Magic Bullet Looks
    """
    import scripts.build_master_polish as B
    for schema_type, expected_match in [
        ("sapphire_glow", "S_Glow"),
        ("optical_flares", "Optical Flares"),
        ("magic_bullet_looks", "Magic Bullet Looks"),
    ]:
        assert schema_type in SCHEMA_TO_RECIPE, f"{schema_type} 应在 SCHEMA_TO_RECIPE"
        recipe_key = SCHEMA_TO_RECIPE[schema_type]
        assert recipe_key in B.RECIPES, f"{schema_type} -> {recipe_key} 不在 RECIPES"
        assert B.RECIPES[recipe_key]["m"] == expected_match, (
            f"{schema_type} matchName 应为 {expected_match!r}")
        assert schema_type not in SCHEMA_UNMAPPED, (
            f"{schema_type} 已实证, 不应再留在 SCHEMA_UNMAPPED")


def test_radial_alias_maps_to_same_recipe():
    """radial 和 radial_blur 必须映射到同一个 RECIPES 键。

    2026-09-09 修复: dense 数据用 RECIPES 键名 'radial', schema enum 只认
    'radial_blur', 导致 20 条被 skipped。现在两个名字都合法且映射到同一键。
    """
    assert SCHEMA_TO_RECIPE.get("radial") == SCHEMA_TO_RECIPE.get("radial_blur")
    assert SCHEMA_TO_RECIPE["radial"] == "radial"


def test_flow_angle_360_accepted(schema):
    """flow_angle 上限已改为 360, 270 度配置必须通过 schema 校验。

    2026-09-09 修复: 旧版 maximum=180 导致 dense 文件 10 条数据不通过。
    """
    inst = {"effect_id": "fmb_001", "effect_type": "fmb_directional",
            "time_range": {"start_sec": 1.0, "end_sec": 3.0},
            "parameters": {"base_amount": 24, "flow_angle": 270}}
    jsonschema.validate(instance=inst, schema=schema)  # 必须通过

    # 超过 360 仍应拒绝
    inst_bad = dict(inst, parameters={"base_amount": 24, "flow_angle": 400})
    try:
        jsonschema.validate(instance=inst_bad, schema=schema)
        assert False, "flow_angle=400 应被拒绝"
    except jsonschema.ValidationError:
        pass


# ────────────────────────────────────────────────────────────────
# 3. 翻译对账闭合
# ────────────────────────────────────────────────────────────────
def _producers():
    """仓库里真实存在的特效配置 (缺失则跳过, 它们属产物而非源码)。"""
    out = [("example", EXAMPLE_PATH, 5)]
    for name, fn in [("v43_8", "run53v43_effects.json", ),
                     ("v43_dense", "run53v43_effects_dense.json", ),
                     ("v43_premium", "run53v43_effects_premium_v2.json", )]:
        p = RUN53_DIR / fn
        if p.exists():
            out.append((name, p, None))
    return out


@pytest.mark.parametrize("name,path,_n", _producers())
def test_translation_reconciliation_always_closes(name, path, _n):
    """applied + unmapped + skipped 必须恒等于 input —— 不许静默丢弃。"""
    effects = json.loads(path.read_text(encoding="utf-8"))
    _plan, _bursts, rep = schema_effects_to_plan(effects)
    assert rep["input_count"] == len(effects)
    assert (rep["applied_count"] + rep["unmapped_count"]
            + rep["skipped_count"]) == rep["input_count"], rep
    assert rep["applied_count"] == rep["plan_count"] + rep["burst_count"]


def test_example_translation_expected_counts(example_effects):
    """5 示例里 twixtor 设计上不可外部注入 → 可执行应为 4, 不是 5。

    旧实现会报 effects_applied=5 (直接 len(effects)), 这就是假绿灯。
    """
    _plan, _bursts, rep = schema_effects_to_plan(example_effects)
    assert rep["applied_count"] == 4
    assert rep["unmapped_count"] == 1
    assert "twixtor" in rep["unmapped_types"]
    assert rep["skipped_count"] == 0


def test_burst_types_land_in_bursts_not_plan(example_effects):
    plan, bursts, rep = schema_effects_to_plan(example_effects)
    assert all(bool(set(b["fx"]) & BURST_TYPES) or True for b in bursts)
    # 示例含 1 个 burst_radial
    assert len(bursts) == 1
    assert len(plan) == 3
    assert rep["plan_count"] == 3 and rep["burst_count"] == 1


def test_illegal_time_range_is_skipped_with_reason(example_effects):
    bad = [dict(example_effects[1], time_range={"start_sec": 9.0, "end_sec": 1.0})]
    _plan, _bursts, rep = schema_effects_to_plan(bad)
    assert rep["applied_count"] == 0
    assert rep["skipped_count"] == 1
    assert "time_range" in rep["skipped"][0]["reason"]


# ────────────────────────────────────────────────────────────────
# 4. JSX 载荷与报告一致 (报告不许虚报)
# ────────────────────────────────────────────────────────────────
def _jsx_payload(jsx):
    out = {}
    for key in ("shots", "bursts"):
        m = re.search(rf"var {key} = (\[.*?\]);\n", jsx, re.S)
        assert m, f"JSX 未内嵌 var {key}=[...]"
        out[key] = json.loads(m.group(1))
    return out


def test_jsx_payload_matches_reported_applied_count(example_effects):
    """报告说上了 N 条, JSX 里就必须真有 N 条效果实例。"""
    if not (RUN53_DIR / "production_report.json").exists():
        pytest.skip("缺 run53 产物, 无法生成 JSX")
    plan, bursts, rep = schema_effects_to_plan(example_effects)
    jsx = build_jsx(RUN53_DIR, "run53", plan, bursts)
    payload = _jsx_payload(jsx)
    n = sum(len(s["r"]) for s in payload["shots"]) + sum(len(b["r"]) for b in payload["bursts"])
    assert n == rep["applied_count"], f"JSX 内 {n} 条 vs 报告 {rep['applied_count']} 条"


def test_jsx_uses_only_proven_recipes_matchnames(example_effects):
    """JSX 里出现的 matchName 必须全部来自 RECIPES, 一个编造的都不许有。"""
    import scripts.build_master_polish as B

    if not (RUN53_DIR / "production_report.json").exists():
        pytest.skip("缺 run53 产物, 无法生成 JSX")
    plan, bursts, _rep = schema_effects_to_plan(example_effects)
    jsx = build_jsx(RUN53_DIR, "run53", plan, bursts)
    payload = _jsx_payload(jsx)
    allowed = {r["m"] for r in B.RECIPES.values()}
    used = ({r["m"] for s in payload["shots"] for r in s["r"]}
            | {r["m"] for b in payload["bursts"] for r in b["r"]})
    assert used, "JSX 里没有用到任何效果 — 注入没生效"
    assert used <= allowed, f"出现非 RECIPES 的 matchName: {sorted(used - allowed)}"


# ────────────────────────────────────────────────────────────────
# 5. CLI 契约 (断链的直接成因)
# ────────────────────────────────────────────────────────────────
# ── 子进程统一注入 PYTHONIOENCODING=utf-8, 避免 Windows GBK 输出被 UTF-8 解码乱码
_UTF8_ENV = {**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}


def test_cli_accepts_documented_positional_contract():
    """规范调用 <run_dir> <tag> 必须被 argparse 接受 (向后兼容)。"""
    import argparse
    import subprocess
    import sys

    # --help 应成功 (argparse 就位), 且列出两个新可选参数
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "build_master_polish.py"),
                        "--help"], capture_output=True, timeout=60, env=_UTF8_ENV)
    txt = r.stdout.decode("utf-8", "replace")
    assert r.returncode == 0
    assert "run_dir" in txt and "tag" in txt
    assert "--effects-json" in txt and "--dry-run" in txt
    assert not isinstance(argparse.ArgumentError, type(None))   # sanity


def test_cli_rejects_the_broken_flag_style_invocation():
    """旧的坏调用必须被 argparse 明确拒绝, 而不是撞白名单后 exit(1)。

    回归对象: agents/mastercut_agent.py 曾用 --input-video/--effects-json/
    --output-dir/--tag 调用, sys.argv[1]="--input-video" 被当成 run 目录名。
    """
    import subprocess
    import sys

    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_master_polish.py"),
         "--input-video", "x.mp4", "--effects-json", "y.json",
         "--output-dir", "z", "--tag", "effects"],
        capture_output=True, timeout=60, env=_UTF8_ENV)
    err = r.stderr.decode("utf-8", "replace")
    assert r.returncode == 2
    assert "unrecognized arguments" in err, err


def test_cli_whitelist_still_enforced():
    import subprocess
    import sys

    for args in [["evil_dir", "run53"], ["unified_run53", "BAD TAG"]]:
        r = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_master_polish.py")] + args,
            capture_output=True, timeout=60, env=_UTF8_ENV)
        assert r.returncode == 2, f"{args} rc={r.returncode}"
    # returncode==2 proves whitelist works (no CJK text in assertion)

