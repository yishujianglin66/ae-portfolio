# Visual Effect Schema Guide (Prompt-as-Code)

This guide explains how to use the structured JSON Schema for AE visual effects to enable deterministic LLM generation of effect configurations with evidence chain support.

## Overview

The visual effect schema (`schemas/visual_effect_schema.json`) provides a machine-readable contract for defining AE effects with:

- **Type-safe parameter validation** via JSON Schema `oneOf` conditional patterns
- **Temporal envelopes** for dynamic modulation (拍点包络: peak value, decay duration, tail ratio)
- **Evidence chain integration** linking effects to validated grammar cards via `skill_id` and `reasoning_log`
- **11 effect types**: twixtor, zoom_pan, bloom, bokeh, badtv, glitch, motion_blur, radial_blur, burst_radial, burst_badtv, fmb_directional

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
- `effect_type` matches one of the 11 defined types.
- `parameters` conform to the type-specific definition (via `oneOf` schema).
- `time_range.start_sec < time_range.end_sec`.
- `envelope.decay_seconds > 0` if enabled.
- `evidence_chain.skill_id` is present (required for audit trail).

## Integration with build_master_polish.py

The `_apply_effects_to_video()` function writes effects to a temporary JSON file and calls `scripts/build_master_polish.py` with `--effects-json` parameter.

**Note:** As of 2026-09-07, `build_master_polish.py` does not yet accept `--effects-json`. To complete the integration:

1. Refactor `build_master_polish.py` to read effect configs from JSON instead of hardcoding RECIPES.
2. Map schema effect types to RECIPES matchNames (e.g., `"bloom"` → `"ADBE Glo2"`).
3. Apply envelope modulation via `setValueAtTime` for `env: True` effects.

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
A: Check that `build_master_polish.py` exists and accepts `--effects-json`. If not, implement the integration (see Integration section above).

**Q: LLM generates invalid configs**
A: Provide the full schema in the prompt context. Use few-shot examples from `effect_config_example.json`.
