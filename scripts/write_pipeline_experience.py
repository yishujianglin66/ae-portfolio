#!/usr/bin/env python3
"""方向1: 将本次开发经验写入管线学习闭环
- 错误模式 → data/error_patterns/error_patterns.json
- 失败复盘 → data/pipeline_runs/run_showcase_bug/postmortem.json
- 验证回读
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ERROR_PATTERNS_FILE = ROOT / "data" / "error_patterns" / "error_patterns.json"
PIPELINE_RUNS_DIR = ROOT / "data" / "pipeline_runs"

# === 1. 写入错误模式 ===
print("[Step 1] Writing error patterns to pipeline learning system...")

new_patterns = [
    {
        "error_type": "JSXExecutionError",
        "error_msg": "app.project.activeItem is null/wrong after addComp() - template returns 'No active comp'",
        "error_keywords": ["activeItem", "addComp", "No active comp", "null"],
        "context_keys": ["stage", "preset_id"],
        "context_stage": "execute",
        "fix_applied": "replace_activeItem_with_comp_variable",
        "fix_code": "preset_code = jsx_inner.replace('app.project.activeItem', 'comp')",
        "root_cause": "AE addComp() does NOT set activeItem. Must use variable reference or set activeItem explicitly.",
        "prevention": "Never rely on app.project.activeItem in scripted comp creation. Pass comp as variable.",
        "success_count": 1,
        "occurrence_count": 109,
        "first_seen": "2026-07-29T10:00:00",
        "last_seen": "2026-07-29T14:00:00"
    },
    {
        "error_type": "JSXReferenceError",
        "error_msg": "COMP_REF is not defined - 3D title template placeholder not replaced",
        "error_keywords": ["COMP_REF", "ReferenceError", "3d_title", "placeholder"],
        "context_keys": ["stage", "category"],
        "context_stage": "execute",
        "fix_applied": "replace_COMP_REF_with_comp",
        "fix_code": "preset_code = jsx_inner.replace('COMP_REF', 'comp')",
        "root_cause": "3D title presets use COMP_REF as comp placeholder. Must be replaced before injection.",
        "prevention": "Check for COMP_REF placeholder in templates and replace with actual comp variable.",
        "success_count": 1,
        "occurrence_count": 4,
        "first_seen": "2026-07-29T12:00:00",
        "last_seen": "2026-07-29T12:30:00"
    },
    {
        "error_type": "SilentFailure",
        "error_msg": "catch(pe){} swallows all errors - animation code fails silently, output appears successful",
        "error_keywords": ["catch", "silent", "empty catch", "swallow", "no error reported"],
        "context_keys": ["stage"],
        "context_stage": "execute",
        "fix_applied": "remove_empty_catch_add_error_reporting",
        "fix_code": "Return JSON.stringify({status:'error', error:e.toString()}) instead of empty catch",
        "root_cause": "Empty catch blocks hide failures. Verification only checked file existence, not content.",
        "prevention": "Never use empty catch. Always log/return error details. Verify animation properties exist.",
        "success_count": 1,
        "occurrence_count": 109,
        "first_seen": "2026-07-29T10:00:00",
        "last_seen": "2026-07-29T14:00:00"
    },
    {
        "error_type": "RenderOutputError",
        "error_msg": "aerender CLI outputs 0-byte/empty files when project not saved or comp has no active camera",
        "error_keywords": ["aerender", "empty file", "0 bytes", "CLI render"],
        "context_keys": ["stage"],
        "context_stage": "render",
        "fix_applied": "use_ae_internal_render_queue",
        "fix_code": "app.project.renderQueue.render() instead of aerender CLI",
        "root_cause": "aerender CLI has issues with unsaved projects and certain comp configurations.",
        "prevention": "Prefer AE internal renderQueue.render() via Bridge. Verify output size > threshold.",
        "success_count": 1,
        "occurrence_count": 109,
        "first_seen": "2026-07-29T09:00:00",
        "last_seen": "2026-07-29T11:00:00"
    },
    {
        "error_type": "BridgeParseError",
        "error_msg": "Bridge result nested at r.result.data.result not r.result.result",
        "error_keywords": ["bridge", "parse", "nested", "result.data.result"],
        "context_keys": ["stage"],
        "context_stage": "execute",
        "fix_applied": "multi_level_nested_parsing",
        "fix_code": "inner = r.get('result',{}); if inner.get('success') and 'data' in inner: result_str = inner['data'].get('result','')",
        "root_cause": "AE Bridge wraps response in nested structure. Must check both paths.",
        "prevention": "Always parse Bridge response with multi-level fallback: result.data.result OR result.result.",
        "success_count": 1,
        "occurrence_count": 18,
        "first_seen": "2026-07-28T16:00:00",
        "last_seen": "2026-07-29T10:00:00"
    }
]

# 读取现有patterns
existing = []
if ERROR_PATTERNS_FILE.exists():
    existing = json.loads(ERROR_PATTERNS_FILE.read_text(encoding='utf-8'))

# 合并(去重)
existing_msgs = {p.get("error_msg", "") for p in existing}
added = 0
for p in new_patterns:
    if p["error_msg"] not in existing_msgs:
        existing.append(p)
        added += 1

ERROR_PATTERNS_FILE.parent.mkdir(parents=True, exist_ok=True)
ERROR_PATTERNS_FILE.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"  Added {added} new error patterns (total: {len(existing)})")

# === 2. 写入失败复盘记录 ===
print("\n[Step 2] Writing failure postmortem...")
run_dir = PIPELINE_RUNS_DIR / "run_20260729_showcase_static_bug"
run_dir.mkdir(parents=True, exist_ok=True)

postmortem = {
    "run_id": "run_20260729_showcase_static_bug",
    "timestamp": datetime.now().isoformat(),
    "task": "Render 109 presets to showcase video",
    "status": "failed_then_fixed",
    "failure_symptom": "ALL_PRESETS_SHOWCASE.mp4 contains only static text, no animation",
    "root_cause_analysis": {
        "primary": "app.project.activeItem not set after addComp() - template code returns 'No active comp' error",
        "secondary": "catch(pe){} empty catch silently swallows all template execution errors",
        "tertiary": "COMP_REF placeholder in 3D title templates not replaced with comp variable",
        "verification_gap": "Only checked file existence/size, not animation content (pixel diff)"
    },
    "fix_applied": {
        "script": "scripts/render_all_presets_v2.py",
        "changes": [
            "Replaced eval() with direct code injection",
            "Replace app.project.activeItem with comp variable reference",
            "Replace COMP_REF with comp for 3D title presets",
            "Added animation property verification (animators/keyframes/effects count)",
            "Added pixel diff verification (YAVG > 5 threshold)"
        ]
    },
    "verification_result": {
        "before": {"file_size_mb": 3.9, "pixel_diff_yavg": 0, "animation": False},
        "after": {"file_size_mb": 135.76, "pixel_diff_yavg": 92.79, "animation": True}
    },
    "lessons_learned": [
        "AE addComp() does NOT set activeItem - always use variable reference",
        "Never use empty catch blocks in JSX - always report errors",
        "Render verification must include content-level checks (pixel diff, property count)",
        "File size alone is insufficient verification - static content compresses to small files",
        "eval() in ExtendScript has escaping risks - prefer direct code injection"
    ],
    "prevention_rules": [
        "After creating comp via script, verify activeItem or use direct variable",
        "All JSX templates must be tested with actual Bridge execution, not just syntax check",
        "Render output verification: ffprobe duration + pixel diff YAVG > 5 + file size > 10MB/min",
        "Error patterns must be written to data/error_patterns/ for pipeline learning"
    ]
}

(run_dir / "postmortem.json").write_text(json.dumps(postmortem, ensure_ascii=False, indent=2), encoding='utf-8')
(run_dir / "pipeline_result.json").write_text(json.dumps({
    "run_id": "run_20260729_showcase_static_bug",
    "status": "failed",
    "quality_score": 0,
    "total_duration_sec": 7200,
    "mode": "batch_render",
    "stages": {
        "execute": {"status": "failed", "error": "activeItem not set - all animations silently failed"},
        "render": {"status": "success", "note": "Rendered successfully but content was static"},
        "verify": {"status": "failed", "error": "Verification gap: only checked file size, not content"}
    }
}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f"  Written to: {run_dir}")

# === 3. 验证回读 ===
print("\n[Step 3] Verifying experience can be read back by pipeline...")
# 模拟 experience_harvester 的 StructuredDataParser.parse_error_patterns()
patterns_read = json.loads(ERROR_PATTERNS_FILE.read_text(encoding='utf-8'))
our_patterns = [p for p in patterns_read if "activeItem" in p.get("error_msg", "") or "COMP_REF" in p.get("error_msg", "")]
print(f"  Error patterns readable: {len(patterns_read)} total, {len(our_patterns)} from this session")

# 模拟 pipeline_runs 回读
run_result = run_dir / "pipeline_result.json"
if run_result.exists():
    rr = json.loads(run_result.read_text(encoding='utf-8'))
    print(f"  Pipeline run readable: status={rr['status']}, mode={rr['mode']}")
    
postmortem_file = run_dir / "postmortem.json"
if postmortem_file.exists():
    pm = json.loads(postmortem_file.read_text(encoding='utf-8'))
    print(f"  Postmortem readable: {len(pm['lessons_learned'])} lessons, {len(pm['prevention_rules'])} rules")

print("\n[DONE] Experience successfully written to pipeline learning system")
print(f"  - Error patterns: {ERROR_PATTERNS_FILE}")
print(f"  - Postmortem: {run_dir / 'postmortem.json'}")
print(f"  - Pipeline result: {run_dir / 'pipeline_result.json'}")
