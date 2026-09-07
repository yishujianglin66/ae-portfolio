#!/usr/bin/env python3
"""CI 质量门卫 CLI — 对管线产物执行 QualityGate 判定，供 CI/CD 自动运行。

把「pipeline_result.json / 产物 mp4 → QualityContext → QualityGate.evaluate()」
链路封装为一条命令，输出结构化报告 JSON 并以退出码表达判定：

    退出码:  0 = PASS  1 = WARN  2 = FAIL(阻断)

用法:
    python scripts/ci_quality_gate.py \\
        --result data/pipeline_runs/run_xxx/pipeline_result.json \\
        [--video output/final.mp4] \\
        [--thresholds config/quality_gate_thresholds.json] \\
        [--vmaf 80.0] [--report output/ci/quality_gate_report.json]

设计要点:
- result json 的 quality_score → OverallQualityRule 的 overall_score（统一口径）
- 产物 mp4 存在时用 ffprobe 实测时长/分辨率/大小，缺失时跳过对应规则
- 阈值默认取规则内置值，可通过 --thresholds JSON 覆盖
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.quality_gate import (  # noqa: E402
    QualityContext,
    VmafThresholdRule,
    get_quality_gate,
)


def load_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:
        print(f"[QGATE-CI] 读取 {path} 失败: {e}", file=sys.stderr)
        return None


def probe_media(video: Path) -> Dict[str, Any]:
    """用 ffprobe 探测产物：时长 / 分辨率 / 文件大小 / 音轨。找不到 ffprobe 则跳过。"""
    empty = {"available": False, "duration_sec": 0.0, "resolution": None,
             "size_mb": 0.0, "has_audio": False}
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None or not video.exists():
        return empty
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json",
             "-show_format", "-show_streams", str(video)],
            capture_output=True, text=True, timeout=60,
        )
        info = json.loads(proc.stdout or "{}")
    except Exception as e:
        print(f"[QGATE-CI] ffprobe 失败: {e}", file=sys.stderr)
        return empty
    streams = info.get("streams", [])
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = info.get("format", {})
    return {
        "available": True,
        "duration_sec": float(fmt.get("duration", 0.0) or 0.0),
        "resolution": (int(video_stream["width"]), int(video_stream["height"]))
                      if video_stream else None,
        "size_mb": round(float(fmt.get("size", 0.0)) / (1024 * 1024), 2),
        "has_audio": audio_stream is not None,
    }


def build_context(result: Dict[str, Any], probe: Dict[str, Any],
                  thresholds: Dict[str, Any]) -> QualityContext:
    """组装 QualityContext（阈值可从 --thresholds 覆盖，缺失用规则默认值）"""
    overall = result.get("quality_score", 0.0)
    try:
        overall = float(overall)
    except (TypeError, ValueError):
        overall = 0.0
    overall_min = float(thresholds.get("overall_min", 60.0))

    dur = probe.get("duration_sec", 0.0) if probe.get("available") else 0.0
    res = probe.get("resolution") if probe.get("available") else None
    size_mb = probe.get("size_mb", 0.0) if probe.get("available") else 0.0

    tgt = thresholds.get("target_resolution")
    target_res = tuple(tgt) if isinstance(tgt, list) and len(tgt) == 2 else None

    min_dur = float(thresholds.get("min_duration_sec", 5.0))
    max_dur = float(thresholds.get("max_duration_sec", 600.0))

    return QualityContext(
        output_path=result.get("output_path", ""),
        vmaf_score=None,  # CI 静态门默认无 VMAF，跳过该规则；可用 --vmaf 注入
        duration_sec=dur,
        resolution=res,
        target_resolution=target_res,
        audio_peak_db=None,
        file_size_mb=size_mb,
        stages_success=(result.get("status") == "success"),
        min_duration_sec=min_dur,
        max_duration_sec=max_dur,
        extra={"overall_score": overall, "min_score": overall_min},
    )


def apply_vmaf_threshold(gate, vmaf_min: Optional[float]):
    """--vmaf-min 与规则默认不同时，重建 VmafThresholdRule。"""
    if vmaf_min is None:
        return
    gate.remove_rule("vmaf_threshold")
    gate.add_rule(VmafThresholdRule(threshold=vmaf_min))


def main() -> int:
    ap = argparse.ArgumentParser(description="CI 质量门卫")
    ap.add_argument("--result", required=True, help="pipeline_result.json 路径")
    ap.add_argument("--video", default="", help="产物 mp4（缺省用 result.output_path）")
    ap.add_argument("--thresholds", default="", help="阈值 JSON（config/quality_gate_thresholds.json）")
    ap.add_argument("--vmaf", type=float, default=None, help="注入实测 VMAF 分")
    ap.add_argument("--vmaf-min", type=float, default=None, help="VMAF 阈值（覆盖默认 70）")
    ap.add_argument("--report", default="output/ci/quality_gate_report.json", help="报告输出路径")
    args = ap.parse_args()

    result_path = Path(args.result)
    result = load_json(result_path)
    if result is None:
        print("[QGATE-CI] FAIL: 无法读取 pipeline_result.json", file=sys.stderr)
        return 2

    thresholds: Dict[str, Any] = {}
    if args.thresholds:
        thresholds = load_json(Path(args.thresholds)) or {}

    video = Path(args.video) if args.video else Path(str(result.get("output_path", "")))
    probe = probe_media(video) if str(video) else {"available": False, "duration_sec": 0.0,
                                                   "resolution": None, "size_mb": 0.0,
                                                   "has_audio": False}
    # --vmaf 注入探测结果（若未给，保持 None 跳过规则）
    if args.vmaf is not None:
        probe["vmaf"] = float(args.vmaf)

    gate = get_quality_gate()
    apply_vmaf_threshold(gate, args.vmaf_min)

    context = build_context(result, probe, thresholds)
    gate_result = gate.evaluate(context)
    mitigations = gate.suggest_mitigations(gate_result)

    report = {
        "run_id": result.get("run_id", ""),
        "result_source": str(result_path),
        "video": str(video),
        "video_probe": {k: v for k, v in probe.items() if k != "vmaf"},
        "vmaf_injected": probe.get("vmaf"),
        "thresholds": thresholds,
        "context": {
            "overall_score_100": result.get("quality_score"),
            "duration_sec": context.duration_sec,
            "resolution": context.resolution,
            "file_size_mb": context.file_size_mb,
            "stages_success": context.stages_success,
            "overall_min": float(thresholds.get("overall_min", 60.0)),
        },
        "quality_gate": {
            "status": gate_result.status,
            "overall_score": round(gate_result.overall_score, 4),
            "overall_100": round(gate_result.overall_score * 100.0, 1),
            "rules": [
                {
                    "rule_id": r.rule_id,
                    "passed": r.passed,
                    "score": round(r.score, 3),
                    "severity": r.severity,
                    "reason": r.reason,
                }
                for r in gate_result.rule_results
            ],
            "issues": [
                {"rule_id": i.rule_id, "severity": i.severity,
                 "message": i.message, "actual": i.actual, "expected": str(i.expected)}
                for i in gate_result.issues
            ],
            "blocking_issues": [
                i.rule_id for i in gate.get_blocking_issues(gate_result)
            ],
            "mitigations": [
                {"issue_id": m.issue_id, "action": m.action,
                 "priority": m.priority, "estimated_effort": m.estimated_effort}
                for m in mitigations
            ],
        },
    }

    report_path = Path(args.report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2),
                           encoding="utf-8")

    # 控制台摘要
    qg = report["quality_gate"]
    print("\n========== CI 质量门 (QualityGate) ==========")
    print(f"  run_id : {report['run_id']}")
    print(f"  video  : {report['video']}")
    print(f"  status : {qg['status']}  overall={qg['overall_100']} (0-100)")
    for r in qg["rules"]:
        tag = "PASS" if r["passed"] else "FAIL"
        print(f"    [{tag}] {r['rule_id']}: score={r['score']} | {r['reason']}")
    if qg["issues"]:
        print("  issues:")
        for i in qg["issues"]:
            print(f"    - [{i['severity']}] {i['message']}")
    print(f"  报告 : {report_path}")
    print("=============================================")

    code = {"PASS": 0, "WARN": 1, "FAIL": 2}.get(qg["status"], 2)
    print(f"[QGATE-CI] exit={code} ({qg['status']})")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
