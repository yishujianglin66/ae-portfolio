# MasterCut Agent Interface Guide

## Overview

The MasterCut Agent provides a tool-use interface for autonomous orchestration of the AE video editing pipeline. It bridges the existing Python scripts with an agent architecture inspired by OpenAI Codex CLI's tool loop pattern.

## Architecture

```
agents/mastercut_agent.py
├── ToolRegistry          # Maps tool names to callable functions
├── MasterCutAgent        # Main agent class with execute() method
└── Tool Functions        # Stateless wrappers for each pipeline stage

scripts/unified_edit.py
├── stage1_beat_analysis()      # BGM beat/dynamics detection
├── stage2_motion_labels()      # Source footage motion labeling (CNN+VLM)
├── stage3_render_cut()         # ProductionDirector V23 orchestration
├── stage4a_apply_lut()         # LUT color grading
├── stage4b_apply_sfx()         # Musical SFX enhancement
├── stage5_score_video()        # CNN + SiliconFlow scoring
├── stage6_run_gate()           # 7-metric quality gate
└── stage7_harvest_experience() # Auto-save to render_history.jsonl
```

## Usage Examples

### Individual Tool Execution

```python
from agents.mastercut_agent import MasterCutAgent

agent = MasterCutAgent()

# List available tools
tools = agent.list_tools()
for tool in tools:
    print(f"{tool['name']}: {tool['description']}")

# Execute individual stages
beat_result = agent.execute("analyze_beat", bgm_path="bgm.mp3")
motion_result = agent.execute("analyze_motion", sources=["vid1.mp4", "vid2.mp4"])
cut_result = agent.execute(
    "render_cut",
    sources=["vid1.mp4"],
    bgm_path="bgm.mp3",
    output_dir="./output",
    duration=30.0,
)
```

### Full Pipeline Execution

```python
result = agent.run_full_pipeline(
    sources=["video1.mp4", "video2.mp4"],
    bgm_path="background_music.mp3",
    output_dir="./output/run54",
    tag="run54",
    duration=30.0,
    theme="燃向混剪: 铺垫→蓄力→爆发→收尾",
    style="amv_highenergy",
    enable_ae=False,  # Set True for AE channel rendering
)

print(f"Final video: {result['final_video']}")
print(f"Elapsed: {result['elapsed_s']}s")
print(f"Quality gate: {'PASS' if result['stages']['quality_gate']['output']['accepted'] else 'FAIL'}")
```

### Evidence Chain Integration

Each tool supports optional `skill_id` parameter for evidence-based decision tracking:

```python
result = agent.execute(
    "render_cut",
    sources=sources,
    bgm_path=bgm,
    output_dir=output_dir,
    skill_id="run50-validated-2026-09-04",  # Link to validated grammar card
)
```

The result includes a `reasoning_log` field that captures the decision rationale for audit purposes.

## Tool Reference

| Tool Name | Description | Key Parameters |
|-----------|-------------|----------------|
| `analyze_beat` | Detect BGM beats and dynamic sections | `bgm_path: str` |
| `analyze_motion` | Label source footage motion (zoom/static/tilt-orbit) | `sources: List[str]`, `cache_dir: Optional[str]` |
| `render_cut` | Orchestrate cut using ProductionDirector V23 | `sources`, `bgm_path`, `output_dir`, `duration`, `theme`, `style`, `enable_ae`, `skill_id` |
| `apply_lut` | Apply style-themed LUT color grading | `input_video`, `output_dir`, `style`, `tag` |
| `apply_sfx` | Add musical SFX layers aligned to cuts | `input_video`, `bgm_path`, `output_dir`, `production_report_path`, `tag` |
| `score_video` | Score final video quality (CNN + SiliconFlow) | `video_path`, `mode` |
| `run_gate` | Run 7-metric quality gate validation | `output_dir`, `tag`, `bgm_path` |
| `harvest_experience` | Save execution experience to history | `output_dir`, `tag`, `bgm_path` |

## ToolResult Structure

All tool executions return a `ToolResult` object:

```python
@dataclass
class ToolResult:
    tool_name: str          # Name of executed tool
    success: bool           # Execution status
    output: Dict[str, Any]  # Structured output data
    error: Optional[str]    # Error message if failed
    reasoning_log: str      # Evidence chain rationale
    elapsed_ms: float       # Execution time in milliseconds
```

## Backward Compatibility

The original CLI interface remains fully functional:

```bash
python scripts/unified_edit.py --bgm bgm.mp3 --sources vid1.mp4 vid2.mp4 --tag run54 --duration 30
```

The refactored `main()` function now calls the same stage functions internally, ensuring consistent behavior between CLI and agent-driven execution.

## Integration with Evidence-Based Skills

The agent interface is designed to work with the evidence skill schema defined in `schemas/evidence_skill_schema.json`. Each tool can accept a `skill_id` parameter that links the execution to a validated rule or grammar card, enabling:

1. **Reproducible Decisions**: Every cut/render decision is traceable to a specific validated rule
2. **Audit Trails**: The `reasoning_log` field captures why a particular action was taken
3. **Continuous Improvement**: Failed executions can be analyzed against their associated skill to refine the rule

Example workflow:
```python
# Execute with evidence chain
result = agent.execute(
    "render_cut",
    sources=sources,
    bgm_path=bgm,
    output_dir=output_dir,
    skill_id="run50-validated-2026-09-04",
)

# If quality gate fails, analyze reasoning_log against skill definition
if not result["stages"]["quality_gate"]["output"]["accepted"]:
    reasoning = result["stages"]["render_cut"]["reasoning_log"]
    # Use reasoning to diagnose why the validated rule didn't produce acceptable results
```

## Next Steps

- **Task 3**: Develop Visual Schema (Prompt-as-Code) for Effects — Create `schemas/visual_effect_schema.json` to structure effect parameters (Twixtor, Zoom, Glow, etc.) as JSON schemas for deterministic LLM generation.
- **AE Channel Integration**: Optionally enable `enable_ae=True` in `render_cut` to trigger AE bridge for lens-level polish passes.
