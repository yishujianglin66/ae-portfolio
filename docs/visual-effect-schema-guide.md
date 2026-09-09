# Visual Effect Schema Guide (Prompt-as-Code)

This guide explains how to use the structured JSON Schema for AE visual effects to enable deterministic LLM generation of effect configurations with evidence chain support.

## Overview

The visual effect schema (`schemas/visual_effect_schema.json`) provides a machine-readable contract for defining AE effects with:

- **Type-safe parameter validation** via root-level `allOf` with `if`/`then` clauses
  (not `oneOf` —— `oneOf` 会让空 `parameters` 同时匹配多个类型而产生歧义)
- **Temporal envelopes** for dynamic modulation (拍点包络: peak value, decay duration, tail ratio)
- **Evidence chain integration** linking effects to validated grammar cards via `skill_id` and `reasoning_log`
- **18 effect types** (`effect_type` enum in `schemas/visual_effect_schema.json`, `version: 1.0.0`):
  `twixtor`, `zoom_pan`, `bloom`, `sapphire_glow`, `optical_flares`, `bokeh`,
  `badtv`, `glitch`, `delirium`, `motion_blur`, `radial_blur`, `radial`, `burst_radial`,
  `burst_badtv`, `fmb_directional`, `particular`, `magic_bullet_looks`, `film_stocks`

  ⚠️ 其中只有 **10 种在 `build_master_polish.RECIPES` 中有实现** 可真正渲染
  （`bloom`, `bokeh`, `badtv`, `glitch`, `radial_blur`/`radial`, `motion_blur`,
  `burst_radial`, `burst_badtv`, `fmb_directional`, `particular`）。
  `twixtor` / `zoom_pan` 由内部规划通道驱动，不可外部注入；
  5 种 premium 插件类型无 RECIPES 条目（matchName 未经 AE 枚举实证）。
  详见 `docs/visual-effect-schema-verification-2026-09-08.md`。

## Schema Structure

Each effect configuration follows this structure:

```json
{
  "effect_id": "unique_identifier",
  "effect_type": "twixtor | zoom_pan | bloom | ...",
  "time_range": {
    "start_sec": 5.0,
    "end_sec": 8.0
  },
  "parameters": {
    // Type-specific parameters (validated via oneOf schema)
  },
  "envelope": {
    "enabled": true,
    "peak_value": 0.9,
    "decay_seconds": 0.16,
    "tail_ratio": 0.45,
    "anchor_mode": "cut | mid | end"
  },
  "evidence_chain": {
    "skill_id": "run50-validated-2026-09-04",
    "reasoning": "closeup face → slow-mo with mid-freeze",
    "music_alignment": {
      "aligned_to_onset": true,
      "onset_time": 6.5,
      "beat_strength": 0.85
    }
  }
}
```

## Effect Types Reference

### 1. Twixtor (Speed Ramping)

Continuous velocity curves for slow-motion sequences.

```json
{
  "effect_type": "twixtor",
  "parameters": {
    "speed_profile": [
      [0.0, 0.35],   // (progress, relative_speed) at start
      [0.55, 0.50],  // slowest point (freeze-like)
      [1.0, 1.05]    // acceleration release
    ],
    "freeze_anchor": "mid"  // "cut" | "mid" | "end"
  }
}
```

**Key fields:**
- `speed_profile`: Array of (progress, speed) pairs. Progress is normalized [0,1] within time_range. Speed is relative (1.0 = normal, <1.0 = slow).
- `freeze_anchor`: Where to anchor the freeze point relative to onsets.

**Envelope behavior:** When enabled, modulates the speed curve intensity based on beat strength.

### 2. Bloom (Glow)

Ethereal glow on highlights using ADBE Glo2.

```json
{
  "effect_type": "bloom",
  "parameters": {
    "threshold": 0.80,   // luminance threshold [0.5, 1.0]
    "radius": 6,         // blur radius [3, 12]
    "intensity": 0.38    // glow intensity [0.2, 0.6]
  }
}
```

**Envelope:** Not applicable (`envelope.enabled: false`). Bloom is static.

### 3. BadTV (Glitch Distortion)

VHS-style distortion bursts aligned to kick onsets.

```json
{
  "effect_type": "badtv",
  "parameters": {
    "distortion": 9.0  // distortion amount [4.0, 13.0]
  },
  "envelope": {
    "enabled": true,
    "peak_value": 1.0,
    "decay_seconds": 0.16,  // ~3 frames @24fps
    "tail_ratio": 0.45,
    "anchor_mode": "cut"
  }
}
```

**Envelope behavior:** Full distortion at cut point, decays to 45% over 0.16s (~3 frames).

### 4. Radial Blur (Burst Impact)

CC Radial Fast Blur for tension release bursts.

```json
{
  "effect_type": "burst_radial",
  "parameters": {
    "blur_amount": 90  // blur amount [35, 90]
  },
  "duration_frames": 3,  // short impact layer (2-4 frames)
  "envelope": {
    "enabled": true,
    "peak_value": 1.0,
    "decay_seconds": 0.08,
    "tail_ratio": 0.3,
    "anchor_mode": "cut"
  }
}
```

**Use case:** Pre-drop build sections (12 strong beats ahead) or drop impacts.

### 5. Directional Motion Blur (FMB)

CC Force Motion Blur with flow angle injection.

```json
{
  "effect_type": "fmb_directional",
  "parameters": {
    "motion_blur_amount": 24,  // [14, 28] depending on light/hard
    "flow_magnitude": 2.5,      // auto-injected by pipeline
    "flow_angle": 45.0          // auto-injected by pipeline (degrees)
  }
}
```

**Auto-injected fields:** `flow_magnitude` and `flow_angle` are computed from shot motion analysis (tmp/shot_motion.json).

## Envelope System

The temporal envelope system implements the **拍点包络** (beat-point envelope) pattern:

```
peak_value (1.0)
    |\
    | \
    |  \ decay (0.16s)
    |   \
    |    \___ tail (0.45 * peak)
    |        |
    +--------+----------> time
   cut      0.16s
```

**Parameters:**
- `peak_value`: Maximum effect intensity at the anchor point (typically 1.0 for full dose).
- `decay_seconds`: Time to decay from peak to tail (0.16s ≈ 3 frames @24fps).
- `tail_ratio`: Sustained intensity after decay (0.45 = 45% of peak).
- `anchor_mode`:
  - `"cut"`: Anchor at cut point (most common).
  - `"mid"`: Anchor at strongest onset within shot (for mid-freeze twixtor).
  - `"end"`: Anchor at shot end (for冲入减速 patterns).

## Evidence Chain Integration

Every effect should include an `evidence_chain` object linking it to validated rules:

```json
"evidence_chain": {
  "skill_id": "run50-validated-2026-09-04",
  "reasoning": "closeup face → bokeh to avoid distortion",
  "music_alignment": {
    "aligned_to_onset": true,
    "onset_time": 6.5,
    "beat_strength": 0.85,
    "section_level": "drop"
  }
}
```

**Fields:**
- `skill_id`: References a validated grammar card (e.g., from run50精修收官).
- `reasoning`: Natural language explanation of why this effect was chosen.
- `music_alignment`: Optional music alignment data (onset time, beat strength, section level).

## Usage with MasterCut Agent

### Method 1: Direct Tool Call

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

print(result.output["effects_applied"])  # 1
print(result.output["effects_validation"])  # {"valid": True, ...}
```

### Method 2: Load from JSON File

```python
import json
from pathlib import Path

effects_json = Path("schemas/examples/effect_config_example.json")
effects = json.loads(effects_json.read_text(encoding="utf-8"))

result = agent.execute(
    "render_cut",
    sources=["video1.mp4", "video2.mp4"],
    bgm_path="bgm.mp3",
    output_dir="./output",
    tag="run62",
    enable_ae=True,
    effects=effects,
)
```

### Method 3: LLM Generation (Prompt-as-Code)

When using an LLM to generate effect configs, provide the schema as context:

```
You are generating AE effect configurations. Use the visual_effect_schema.json contract.

Available effect types: twixtor, zoom_pan, bloom, bokeh, badtv, glitch, motion_blur, radial_blur, burst_radial, burst_badtv, fmb_directional

Rules:
1. Each effect must have a unique effect_id.
2. Parameters must match the effect_type's definition (see schema).
3. Include evidence_chain with skill_id and reasoning.
4. Use envelope.enabled=true for punch effects (badtv, radial, burst_*).

Generate effects for a 30-second AMV with:
- BGM: 24fps, strong kicks at [5.0, 12.0, 18.0, 24.0]
- Sections: intro (0-5s), build (5-12s), drop (12-18s), climax (18-24s), outro (24-30s)
- Sources: closeup face (5-8s), wide shot action (12-15s), horizontal pan (20-23s)

Output JSON array of effect configs.
```

The LLM will produce schema-compliant JSON that can be validated and applied directly.

## Validation

Effects are automatically validated when passed to `render_cut`. You can also validate manually:

```python
from agents.mastercut_agent import _validate_effect_configs

validation = _validate_effect_configs(effects)
if not validation["valid"]:
    for error in validation["errors"]:
        print(f"Effect {error['effect_index']}: {error['error']}")
```

Validation checks:
- `effect_type` matches one of the 18 defined types.
- `parameters` conform to the type-specific definition (via root-level `allOf`
  with `if`/`then` clauses —— 不是 `oneOf`；`oneOf` 会让空参数对象同时匹配多个类型）。
- `time_range.start_sec < time_range.end_sec` —— ⚠️ **当前并未被 schema 强制**。
  实测 `start_sec=9, end_sec=1` 仍通过校验；`schema_effects_to_plan()`
  会把它归入 `skipped` 并给出原因，所以不会造成错误渲染，但约束应补到 schema 层。
- `envelope.decay_seconds > 0` if enabled.
- `evidence_chain.skill_id` is present (required for audit trail).

## Integration with build_master_polish.py

**已于 2026-09-08 完成。** 实证记录见
`docs/visual-effect-schema-verification-2026-09-08.md`。

链路分两步（`build_master_polish.py` **只建 comp 存 aep，不产 mp4**）：

```
python scripts/build_master_polish.py <run_dir> <tag> --effects-json <配置.json>
        → output/<run_dir>/polish/master.aep
python scripts/render_master.py <run_dir> <tag>
        → output/<run_dir>/polish/<tag>_master.mp4
```

`agents/mastercut_agent.py::_apply_effects_to_video()` 会自动跑完这两步。

已落地：

1. `build_master_polish.py` 改用 argparse，并新增 `--effects-json` 与 `--dry-run`；
   位置参数 `<run_dir> <tag>` 契约保持不变（旧形式调用仍可用）。
2. `schema_effects_to_plan()` 将 schema 配置翻译为内部 `plan` / `bursts`；
   类型映射见 `SCHEMA_TO_RECIPE` / `SCHEMA_DYN_RECIPE` / `SCHEMA_UNMAPPED`。
3. 包络：`envelope.enabled` 时取 `peak_value` 作 dose，由 `_fx_js` 的 `r.env`
   走 `setValueAtTime(t0, v)` + `setValueAtTime(t0+DECAY, v*TAIL)`。
4. 对账记账：`tmp/effects_injection_report.json` 输出
   `applied + unmapped + skipped == input`，**禁止静默丢弃**。

⚠️ **未覆盖的类型**：`sapphire_glow` / `optical_flares` / `delirium` /
`particular` / `magic_bullet_looks` / `film_stocks` 在 `RECIPES` 中无条目
（matchName 未经 AE 枚举实证，不得编造）；`twixtor` 由 `plan_effects` 的 twx
通道按真实 onset 生成，`zoom_pan` 由 `segments.zoompan_effect` 驱动 —— 三者均
不可外部注入。因此 `run53v43_effects_premium_v2.json` 139 条中实际仅 33 条可渲染。

另有命名分裂待清：`RECIPES` 用 `radial` 作键，而 schema enum 只有 `radial_blur`；
部分历史产物（如 `run53v43_effects_dense.json`）直接写了 `radial`，会被归入 skipped。

See `schemas/visual_effect_schema.json` definitions for parameter ranges matching production RECIPES.

## Example Configurations

See `schemas/examples/effect_config_example.json` for a complete example with 5 effects:
- Twixtor slow-mo with mid-freeze
- Bloom glow on drop section
- BadTV glitch burst at kick onset
- Radial blur pre-drop impact
- Directional motion blur on horizontal pan

## Troubleshooting

**Q: Validation fails with "Additional properties are not allowed"**
A: Check that `parameters` only includes fields defined for that `effect_type`. For example, `twixtor` expects `speed_profile`, not `distortion`.

**Q: Envelope has no effect**
A: Ensure `envelope.enabled: true` and `anchor_mode` is set. Also verify that `enable_ae=True` when calling `render_cut`.

**Q: Effects not applied to video**
A: 查 `tmp/effects_injection_report.json` 的 `unmapped_types` 与 `skipped` ——
类型在 `RECIPES` 中无实现时会被**如实计入 unmapped 而不是静默丢弃**。
再看 `effects_applied` 是否等于 `effects_requested`；不等就是部分交付。
渲染产物低于 100KB 会被 `_apply_effects_to_video` 直接判为失败（黑屏/空合成）。

**Q: 报的数能不能信？**
A: 2026-09-08 后能。之前 `_stage_render_cut` 无条件返回 `len(effects)`，
即使链路 `exit(1)` 也报“全部已应用”。现在报告数与 `build_jsx` 产物内的
效果条目数逐条一致，并由 `tests/test_visual_effect_schema.py` 钉住。

**Q: LLM generates invalid configs**
A: Provide the full schema in the prompt context. Use few-shot examples from `effect_config_example.json`.
