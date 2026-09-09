# Visual Effect Schema Integration - Completion Summary

**Date:** 2026-09-07（2026-09-08 更正）
**Task:** 集成计划中的 Task 3（本文旧称 "Task 8"，与 `docs/superpowers/plans/2026-09-07-mastercut-integration.md` 的编号不一致）
**Status:** ⚠️ 部分完成 —— Schema 定义可用；执行链路于 2026-09-08 修复后才跑通

> **更正说明（2026-09-08）**
> 本文旧版声称 "Status: ✅ COMPLETED" 且 "可以投入使用了"，经实际验证不属实：
> `_apply_effects_to_video()` 用 `--input-video/--effects-json/--output-dir/--tag`
> 调用 `build_master_polish.py`，而该脚本当时只认位置参数且带
> `unified_run\d+` / `run\d+` 白名单，实测 `returncode=1`、
> `[ERR] 非法 run 目录名(白名单 unified_run\d+): --input-video`。
> 特效从建成起到 2026-09-08 **一次也没能真正落地**。
> 修复与实证记录见 `docs/visual-effect-schema-verification-2026-09-08.md`。

## Overview

Structured JSON Schema for AE visual effects integrated into the MasterCut pipeline, enabling deterministic LLM generation of effect configurations with evidence chain support.

## Deliverables Created

### 1. Core Schema (`schemas/visual_effect_schema.json`)

Comprehensive JSON Schema covering **18 effect types**（旧版文档误写为 11；premium 总结文档又误写为 19；2026-09-09 加 `radial` 别名后为 18）:
- `twixtor` - Time remapping with continuous velocity curves
- `zoom_pan` - Scale and position animation
- `bloom` - Glow/bloom effect (ADBE Glo2)
- `bokeh` - Depth-of-field simulation (RWB Fast Bokeh)
- `badtv` - TV glitch distortion (GUTS BadTV)
- `glitch` - General glitch presets (AESweetsGlitch7in1)
- `motion_blur` - CC Force Motion Blur
- `radial_blur` - CC Radial Fast Blur
- `burst_radial` - Burst impact layer (radial)
- `burst_badtv` - Burst impact layer (BadTV)
- `fmb_directional` - Directional motion blur with optical flow
- `sapphire_glow` / `optical_flares` / `delirium` /
  `magic_bullet_looks` / `film_stocks` —— 2026-09-07 新增的 5 种第三方插件类型，
  **均无 RECIPES 实现**（matchName 未经 AE 枚举实证，不得编造）
- `particular` —— 2026-09-09 加入 RECIPES（matchName `tc Particular` 经 AE Bridge 实证）
- `radial` —— 2026-09-09 加入 enum 作为 `radial_blur` 的别名（dense 数据用 RECIPES 键名）

**Key Features:**
- **Type-safe parameter validation** via top-level `allOf` conditional schemas
- **Temporal envelopes** for dynamic modulation (拍点包络: peak_value, decay_seconds=0.16s, tail_ratio=0.45)
- **Evidence chain integration** linking effects to validated grammar cards via `skill_id` and `reasoning`
- **Parameter ranges** matching production RECIPES in `scripts/build_master_polish.py`

### 2. Agent Integration (`agents/mastercut_agent.py`)

Enhanced `MasterCutAgent` with effect-based rendering capabilities:

**New Functions:**
- `_validate_effect_configs(effects)` - Validates effect list against schema using jsonschema
- `_apply_effects_to_video(input_video, effects, output_dir, tag)` - Applies validated effects via build_master_polish.py

**Updated Tool:**
- `render_cut` now accepts optional `effects` parameter (List[Dict])
  - Automatically validates effects before rendering
  - If `enable_ae=True` and effects provided, applies them in post-processing pass
  - Returns validation results in output dict

**Example Usage:**
```python
from agents.mastercut_agent import MasterCutAgent

agent = MasterCutAgent()

effects = [
    {
        "effect_id": "twx_001",
        "effect_type": "twixtor",
        "time_range": {"start_sec": 5.0, "end_sec": 8.0},
        "parameters": {
            "speed_profile": [[0.0, 0.35], [0.55, 0.50], [1.0, 1.05]],
            "freeze_anchor": "mid"
        },
        "envelope": {"enabled": True, "peak_value": 0.9, "decay_seconds": 0.16, "tail_ratio": 0.45, "anchor_mode": "mid"},
        "evidence_chain": {
            "skill_id": "run50-validated-2026-09-04",
            "reasoning": "closeup face → slow-mo with mid-freeze"
        }
    }
]

result = agent.execute(
    "render_cut",
    sources=["video1.mp4"],
    bgm_path="bgm.mp3",
    output_dir="./output",
    enable_ae=True,
    effects=effects,
)
```

### 3. Example Configuration (`schemas/examples/effect_config_example.json`)

Complete working example with **5 diverse effects**:
1. Twixtor slow-mo with mid-freeze at kick onset
2. Bloom glow on high-energy drop section
3. BadTV glitch burst at strong kick (cut anchor)
4. Radial blur pre-drop impact (3-frame burst)
5. Directional motion blur on horizontal pan

All examples validated successfully against schema.

### 4. Documentation (`docs/visual-effect-schema-guide.md`)

Comprehensive guide covering:
- Schema structure and effect type reference
- Envelope system explanation (拍点包络 pattern)
- Evidence chain integration
- Usage examples (direct tool call, JSON file load, LLM generation)
- Validation troubleshooting
- Integration notes for build_master_polish.py

## Technical Implementation Details

### Schema Design Pattern

Used `allOf` with conditional `if/then` clauses at root level instead of nested `oneOf`:

```json
{
  "allOf": [
    {
      "if": {"properties": {"effect_type": {"const": "twixtor"}}},
      "then": {"properties": {"parameters": {"$ref": "#/definitions/TwixtorParams"}}}
    },
    // ... one clause per effect type
  ]
}
```

This avoids the ambiguity issue where multiple effect types match empty parameter objects.

### Validation Logic

```python
def _validate_effect_configs(effects: List[Dict[str, Any]]) -> Dict[str, Any]:
    import jsonschema
    
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    
    errors = []
    for i, effect in enumerate(effects):
        try:
            jsonschema.validate(instance=effect, schema=schema)
        except jsonschema.ValidationError as e:
            errors.append({"effect_index": i, "error": e.message})
    
    return {"valid": len(errors) == 0, "errors": errors, "effect_count": len(effects)}
```

### Envelope System

Implements the **拍点包络** (beat-point envelope) temporal modulation:

```
peak_value (1.0)
    |\
    | \
    |  \ decay (0.16s ≈ 3 frames @24fps)
    |   \
    |    \___ tail (0.45 * peak)
    |        |
    +--------+----------> time
   cut      0.16s
```

**Parameters:**
- `peak_value`: Maximum intensity at anchor point (typically 1.0)
- `decay_seconds`: Decay duration (0.16s default)
- `tail_ratio`: Sustained ratio after decay (0.45 default)
- `anchor_mode`: "cut" | "mid" | "end"

Matches production constants in `build_master_polish.py`:
- `ENV_DECAY_S = 0.16`
- `ENV_TAIL = 0.45`

## Remaining Work (Future Integration)

### build_master_polish.py Enhancement —— ✅ 已于 2026-09-08 完成

旧状态（本文原版）：`_apply_effects_to_video()` 写 effects 到 JSON 并以
`--effects-json` 调用 build_master_polish.py，**但该脚本当时不接受该参数**。
下列 5 项已全部落地于 `build_master_polish.py`：

1. ✅ 加 `--effects-json` CLI 参数（argparse，保留 `<run_dir> <tag>` 位置参数契约）
2. ✅ `schema_effects_to_plan()` 从 JSON 读取配置并生成 plan/bursts
3. ✅ `SCHEMA_TO_RECIPE` / `SCHEMA_DYN_RECIPE` / `SCHEMA_UNMAPPED` 三张表完成类型映射
4. ✅ 包络：`envelope.enabled` 时取 `peak_value` 作 dose，由 `_fx_js` 的
   `r.env` 走 `setValueAtTime(t0, v)` + `setValueAtTime(t0+DECAY, v*TAIL)`
5. ✅ burst 层路由到 `bursts` 列表（`duration_frames` 映射为 `t1 - t0`）

**仍未完成**：上节 Known Gaps 第 1 项（5 种 premium 插件类型无 RECIPES 实现）。

**Mapping table:**
| Schema Type | RECIPES Key | Match Name | Env Flag |
|------------|-------------|------------|----------|
| bloom | bloom | ADBE Glo2 | False |
| bokeh | bokeh | RWB Fast Bokeh | False |
| badtv | badtv | GUTS BadTV | True |
| radial_blur / radial | radial | CC Radial Fast Blur | True |
| particular | particular | tc Particular | False |
| sapphire_glow | sapphire_glow | S_Glow | False |
| optical_flares | optical_flares | Optical Flares | False |
| magic_bullet_looks | magic_bullet_looks | Magic Bullet Looks | False |
| burst_radial | burst_radial | CC Radial Fast Blur | True |
| burst_badtv | burst_badtv | GUTS BadTV | True |
| motion_blur | fmb | CC Force Motion Blur | False |
| fmb_directional | fmb_dir | CC Force Motion Blur | False |

## Testing Results

2026-09-09 实测（`tests/test_visual_effect_schema.py`，21 passed / 9s）：

✅ 5 个示例配置通过 schema 校验（jsonschema 4.26.0）
✅ schema 正确拒绝非法配置：未知类型 / 越界 / 类型错 / 未知参数注入 / 缺必填 / id 正则
✅ 映射表与 schema enum 一一对应，18/18 无空洞
✅ 翻译对账闭合：applied + unmapped + skipped == input（无静默丢弃）
✅ build_jsx 产物内效果条目数 == 报告数，且 matchName 全部来自 RECIPES
✅ 真实 aerender 渲染：`run53_master.mp4` 59,238,698 B，h264 1920x1080@24fps，720 帧 = 30.0s

旧版本文列出的 "✅ Agent integration compiles without errors" 等四条并不能
证明链路可用 —— 它只跑了 import，从未跑过真实调用。

## Known Gaps（2026-09-09 更新）

1. **2 种 premium 插件类型无渲染实现** —— `delirium` / `film_stocks` 在 `RECIPES`
   中无条目（本机未安装 Digieffects Delirium 和 Tiffen Dfx，无法 AE 实证）。
   `sapphire_glow` / `optical_flares` / `magic_bullet_looks` 已于 2026-09-09 经 AE Bridge 实证加入 RECIPES。
2. ~~**`radial` vs `radial_blur` 命名分裂**~~ —— ✅ 2026-09-09 修复：`radial` 加入 schema enum 作为合法别名，`SCHEMA_TO_RECIPE` 加 `"radial": "radial"` 直接映射。dense 文件 20 条 skipped 降为 0。
3. ~~**`flow_angle` 上限写错**~~ —— ✅ 2026-09-09 修复：schema `maximum` 从 180 改为 360。dense 文件 10 条不通过降为 0。
4. **`time_range` 缺跨字段约束** —— `start_sec > end_sec` 仍过 schema（翻译器会
   归入 skipped，不会错渲染，但 schema 层应补）。已在测试中钉住此现状。
5. **`ai/production_director.py`（271KB，V23 真引擎）不认识 schema** ——
   提及 `visual_effect_schema` 0 次。特效注入仅发生在 build 阶段。
6. **全部交付物仍未入 git** —— `agents/`、`schemas/visual_effect_schema.json`、
   `schemas/examples/`、本文与指南文档均为 `??` 未跟踪状态。

## Files Modified/Created

- ✅ `schemas/visual_effect_schema.json` - Core schema definition (~570 lines)
- ✅ `schemas/examples/effect_config_example.json` - Working example (5 effects)
- ✅ `agents/mastercut_agent.py` - Agent integration (+~120 lines)
- ✅ `docs/visual-effect-schema-guide.md` - User documentation
- ✅ `docs/visual-effect-schema-summary.md` - This completion summary

## Conclusion

Schema 定义层可用且质量不错（18 类型约束严谨、`additionalProperties: false` 生效）。

但旧结论 "Task 8 is complete ... 可以投入使用了" **不成立**：它是纸面合同，
当时没人消费它，第一跳就 `exit(1)`。2026-09-08 已完成 P0 修复（见
`docs/visual-effect-schema-verification-2026-09-08.md`）：

- `build_master_polish.py` 改为 argparse（位置参数契约不变）+ `--effects-json` + `--dry-run`
- 新增 `schema_effects_to_plan()` 翻译器，带 unmapped/skipped 显式记账
- `_apply_effects_to_video()` 按真实契约调用，并补齐缺失的 `render_master.py` 渲染步骤
- 删除两层假绿灯（agent 无条件报 `len(effects)`、脚本 `.get(..., len(effects))` 兜底）
- 修正 `ToolResult.data` 不存在（实际是 `.output`）导致调用方恒走 FAIL 分支
- 新增 `tests/test_visual_effect_schema.py`（20 项）防回归

**2026-09-09 缺口修复**（见 `docs/visual-effect-schema-verification-2026-09-08.md` 第 5 节）：

- `flow_angle` 上限 180 → 360（光流方向 0-360°）
- `radial` 加入 schema enum 别名 + `SCHEMA_TO_RECIPE` 直接映射，消除 dense 文件 20 条 skipped
- `particular` 加入 RECIPES（matchName `tc Particular` 经 AE Bridge 实证），移出 `SCHEMA_UNMAPPED`
- 测试从 18 项增至 21 项（新增 radial alias、flow_angle 360 验证）

**距"完整可用"仍差**：5 种 premium 插件类型的 RECIPES 实现（需 AE 枚举实证 matchName）。
在那之前，`run53v43_effects_premium_v2.json` 只能渲染 33/139 条，属**部分交付**。
