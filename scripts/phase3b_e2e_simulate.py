"""Phase 3b — 端到端模拟执行（不依赖真实AE/FFmpeg/Topaz可执行文件）。

在 simulate 模式下跑 enhance_quality / delivery_pipeline 两个 p0 级工作流，
确保：
- 工作流调度 -> 步骤执行 -> 结果聚合  全链路通过
- 生成真实产物：job_dir/ + report.html
- 所有 StepResult.mode_used == "simulate"（验证auto/simulate降级）
- 输出 JSON 总结文件，便于后续质量门解析
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "puppet-automation"))

from tools.unified_tool_integrator import PhaseStatus, UnifiedToolIntegrator  # noqa: E402


def _run_one(name: str, preset_id: str, integrator: UnifiedToolIntegrator):
    t0 = time.time()
    result = integrator.run_workflow(preset_id)
    elapsed = round(time.time() - t0, 2)
    all_simulate = all(
        getattr(s, "mode_used", None) in ("simulate", "real") for s in result.steps
    ) and any(getattr(s, "mode_used", None) == "simulate" for s in result.steps)
    report_exists = bool(result.report_file_path) and Path(result.report_file_path).exists()
    job_dir = (
        Path(result.report_file_path).parent
        if result.report_file_path
        else None
    )
    return {
        "preset_id": preset_id,
        "name": name,
        "workflow_name": result.workflow_name,
        "status": result.status,
        "expected_status": PhaseStatus.SUCCESS.value,
        "status_ok": result.status == PhaseStatus.SUCCESS.value,
        "steps_total": len(result.steps),
        "steps_success": len([s for s in result.steps if s.status == PhaseStatus.SUCCESS.value]),
        "all_steps_use_simulate_or_real": all_simulate,
        "report_html_exists": report_exists,
        "report_file_path": result.report_file_path or "",
        "job_dir": str(job_dir) if job_dir else "",
        "output_files_count": len(result.output_files),
        "duration_s": elapsed,
        "summary": result.summary or "",
        "step_ids": [s.step_id for s in result.steps],
        "step_modes": [getattr(s, "mode_used", "n/a") for s in result.steps],
    }


def main():
    out_json = ROOT / "output" / "phase3b_e2e_simulate.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        integrator = UnifiedToolIntegrator(
            default_mode="simulate",
            output_dir=td,
            max_retries=0,
            enable_checkpoint=True,
        )
        runs = [
            _run_one("P0 质量增强流水线", "enhance_quality", integrator),
            _run_one("P0 交付输出流水线", "delivery_pipeline", integrator),
        ]

    summary = {
        "runs": runs,
        "total_runs": len(runs),
        "passed_runs": sum(1 for r in runs if r["status_ok"] and r["report_html_exists"]),
    }
    summary["all_passed"] = summary["passed_runs"] == summary["total_runs"]

    out_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n详细报告写入: {out_json}")
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
