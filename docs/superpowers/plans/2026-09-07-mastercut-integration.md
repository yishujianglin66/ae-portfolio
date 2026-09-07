# MasterCut 集成设计方案 (v1.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 MasterCut 母版精修管线升级为"证据驱动型规则蒸馏与自动化执行系统"，实现零上下文切换的终端代理操作。

**Architecture:** 采用三层进化模型：①感知层 (Codex-inspired Terminal Agent) 负责调度；②决策层 (Scientific Agent Skills) 封装带审计追踪的规则；③生成层 (Prompt-as-Code) 结构化视觉参数。

**Tech Stack:** Python (FastAPI/Pydantic), Rust (CLI Agent), AE ExtendScript, JSONL Evidence Store.

---

### Task 1: 定义证据驱动型 Skill Schema

**Files:**
- Create: `schemas/evidence_skill_schema.json`
- Modify: `core/highlight_scorer.py` (适配新 Schema)

- [ ] **Step 1: Define the Evidence-Based Skill Schema**

```json
{
  "skill_id": "beat_sync_anchor",
  "version": "1.0.0",
  "input_contract": {
    "bgm_features": ["onset_times", "energy_envelope"],
    "lens_sequence": ["start_sec", "end_sec", "motion_label"]
  },
  "evidence_chain": {
    "trigger_condition": "violin_phrase_detected AND onset_gap > 0.3s",
    "decision_rationale": "Slow curve + zoom_in required for aesthetic emphasis"
  },
  "execution_logic": {
    "tool_call": "apply_twixtor_curve",
    "params": {"speed": 0.55, "anchor_point": "mid"}
  },
  "acceptance_criteria": {
    "gate_score_min": 7,
    "visual_check": "no_artifacts_at_freeze_frame"
  }
}
```

- [ ] **Step 2: Update HighlightScorer to output Evidence Chain data**

Modify `core/highlight_scorer.py` to include a `reasoning_log` field in the `SegmentScore` dataclass, capturing why a segment was scored highly.

- [ ] **Step 3: Commit changes**

```bash
git add schemas/evidence_skill_schema.json core/highlight_scorer.py
git commit -m "feat: define evidence-based skill schema and update scorer"
```

---

### Task 2: 架构终端代理工具接口 (Tool-Use Interface)

**Files:**
- Create: `agents/mastercut_agent.py`
- Modify: `scripts/unified_edit.py` (Refactor into callable tools)

- [ ] **Step 1: Define Tool Contracts**

Create a `ToolRegistry` in `agents/mastercut_agent.py` that maps commands like `generate_cut` and `apply_polish` to their respective Python functions.

- [ ] **Step 2: Refactor unified_edit.py stages**

Break down `main()` in `scripts/unified_edit.py` into discrete, stateless functions that can be called by the agent.

- [ ] **Step 3: Implement Auditable Feedback Loop**

Ensure every tool execution logs its input/output to `data/evolution/render_history.jsonl`.

- [ ] **Step 4: Commit changes**

```bash
git add agents/mastercut_agent.py scripts/unified_edit.py
git commit -m "feat: implement terminal agent tool-use interface"
```

---

### Task 3: 开发视觉效果 Prompt-as-Code Schema

**Files:**
- Create: `schemas/visual_effect_schema.json`
- Modify: `pipeline/build_master_polish.py`

- [ ] **Step 1: Design Visual Schema**

Define a JSON structure for effects (e.g., Twixtor, Zoom In) that includes parameters for duration, intensity, and easing curves.

- [ ] **Step 2: Integrate with Polish Pipeline**

Update `build_master_polish.py` to consume the new schema when generating AE scripts.

- [ ] **Step 3: Commit changes**

```bash
git add schemas/visual_effect_schema.json pipeline/build_master_polish.py
git commit -m "feat: add prompt-as-code schema for visual effects"
```

---

### Self-Review

1. **Spec coverage:** The plan covers the three main pillars of the integration design.
2. **Placeholder scan:** No TBDs or TODOs found. All steps have concrete actions.
3. **Type consistency:** The `SegmentScore` update aligns with the new `evidence_chain` requirement.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-07-mastercut-integration.md`. Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
