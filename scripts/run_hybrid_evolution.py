# -*- coding: utf-8 -*-
"""
混合管线 × 自进化闭环（可复现自动化）
======================================

流程（闭环）：
    执行  ResolveAeResolvePipeline.run()（真实 Stage A/B/C）
      ↓
    检测  ffprobe/signalstats/scene 客观测量 + measure_sync_quality 切点-节拍偏差
      ↓
    评估  core.evolution.evaluator 确定性分项评分（quality 30% / style 30% /
          pipeline_success 25% / output_exists 15%）+ 黑屏一票否决
      ↓
    决策  VersionManager 严格对比（仅严格更高才接受新版本，否则回滚）
      ↓
    回写  knowledge_sink + self_evolution_engine 评审历史 + messages.jsonl 轨迹

用法：
    python scripts/run_hybrid_evolution.py [--skip-run]
    （--skip-run: 复用最近一次成片只做评测闭环，用于离线回归）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "integrations"))
sys.path.insert(0, os.path.join(ROOT, "vrs"))

BGM = r"D:\AE-Work\音频素材库\BGM\ae实战音乐.mp3"
CLIPS_DIR = r"C:\VinlandClips"
# 【第三轮修复】输出路径迁移到 D 盘，C 盘空间不足
OUT_DIR = r"D:\AE-Work\文档\hybrid_pipeline"
FINAL = os.path.join(OUT_DIR, "hybrid_final.mp4")
LUT = os.path.join(ROOT, "output", "phase3_showcase", "teal_orange.cube")

CONFIG = {
    "title": "冰海战记",
    "subtitle": "VINLAND SAGA · AMV",
    "beat_group": 2,  # 每2拍切一个镜头（原4拍切点太少仅7个）
    # 【A2 闪白转场优化】移除 flash，均衡分配 whip_pan/glitch/zoom
    "transitions": ["whip_pan", "glitch", "zoom", "whip_pan", "glitch", "zoom"],
    "lut": LUT if os.path.exists(LUT) else None,
    "clips_dir": CLIPS_DIR,
    "bgm": BGM,
}


def measure_yavg(path: str) -> float | None:
    r = subprocess.run(
        [r"C:\ffmpeg\bin\ffmpeg.exe", "-i", path,
         "-vf", "signalstats,metadata=print", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="ignore", timeout=600)
    vals = [float(v) for v in re.findall(r"signalstats\.YAVG=(\d+(?:\.\d+)?)", r.stderr)]
    return sum(vals) / len(vals) if vals else None


def pick_clips() -> list[str]:
    exts = {".mp4", ".mov", ".mkv"}
    durs = []
    for f in os.listdir(CLIPS_DIR):
        if os.path.splitext(f)[1].lower() not in exts:
            continue
        p = os.path.join(CLIPS_DIR, f)
        rr = subprocess.run(
            [r"C:\ffmpeg\bin\ffprobe.exe", "-v", "error",
             "-show_entries", "format=duration", "-of", "csv=p=0", p],
            capture_output=True, text=True, timeout=60)
        try:
            durs.append((float(rr.stdout.strip()), p))
        except ValueError:
            continue
    durs.sort(reverse=True)
    return [p for _, p in durs[:6]]


def build_pipeline_result(run_meta: dict, sync: dict, yavg: float | None) -> dict:
    """把客观测量转换为 PipelineResult 字典（evaluator 契约）。"""
    cuts = int(sync.get("cuts", 0))
    on_beat = float(sync.get("on_beat_rate", 0.0))
    avg_dev = float(sync.get("avg_dev_ms", 999.0))

    # 质检分（确定性、可复现）：踩拍同步 50% + 偏差余量 30% + 内容有效性 20%
    sync_part = 100.0 * on_beat
    dev_part = 100.0 * max(0.0, 1.0 - avg_dev / 200.0)
    valid_part = 100.0 if (yavg is not None and yavg >= 20.0 and cuts >= 2) else 0.0
    quality_score = round(0.5 * sync_part + 0.3 * dev_part + 0.2 * valid_part, 1)

    return {
        "run_id": run_meta["run_id"],
        "mode": "mixed",  # Resolve→AE→Resolve 混合工作流
        "status": "success" if run_meta["ok"] else "failed",
        "output_path": FINAL,
        "quality_score": quality_score,
        "total_duration_sec": run_meta.get("duration", 0.0),
        "iterations": 1,
        "project_path": "",
        # P3-C 风格断言（第四轮更新：匹配新智能导演效果链）
        "_expected_output": {
            "saturation": "high",
            "contrast": "high",
            "effects_contain": ["glow", "glitch", "teal_orange"],
        },
        "stages": {
            "stage_a": {"data": {"duration": run_meta.get("stage_a_duration")}},
            "stage_b": {"data": {"ae_used": run_meta.get("ae_used"),
                                 "engine": "AE" if run_meta.get("ae_used") else "ffmpeg_drawtext"}},
            "stage_c": {"data": {"lut": bool(CONFIG["lut"])}},
            "verify": {"data": {
                "score": quality_score,
                "yavg": yavg, "cuts": cuts,
                "avg_dev_ms": avg_dev, "on_beat_rate": on_beat,
                "elapsed_s": run_meta.get("elapsed_s"),
                "transitions": CONFIG["transitions"],
                "teal_orange": bool(CONFIG["lut"]),
            }},
        },
    }


def _calibrate_beat_offset(pipe, clips: list, beat_group: int) -> float:
    """B4 节拍对齐微调：快速探测切点-节拍系统性偏移，返回补偿值（秒）。

    原理：用默认参数（无偏移）跑一次 Stage A 的剪辑逻辑，
    检测实际切点与目标节拍的偏差中位数作为系统性偏移。
    """
    try:
        analysis = pipe.vrs.analyze(BGM)
        beats = analysis.get("beats", [])
        if not beats:
            return 0.0
        # 模拟切点位置（每 beat_group 拍一个镜头）
        cut_beats = beats[::beat_group]
        boundaries = [0.0] + list(cut_beats)
        shot_bounds = [(boundaries[i], boundaries[i + 1])
                       for i in range(len(boundaries) - 1)
                       if boundaries[i + 1] - boundaries[i] >= 0.3]
        # 切点 = 每个镜头的起始时间
        actual_cuts = [b for a, b in shot_bounds[1:]]  # 跳过第一个 0.0
        if not actual_cuts:
            return 0.0
        # 计算每个切点到最近节拍的偏差
        devs = []
        for ct in actual_cuts:
            nearest = min(beats, key=lambda b: abs(b - ct))
            devs.append(ct - nearest)
        if not devs:
            return 0.0
        # 中位数偏差作为系统性偏移（截断到 ±50ms 安全范围）
        devs.sort()
        median_dev = devs[len(devs) // 2]
        # 偏移补偿 = -偏差（把切点推回节拍上）
        offset = max(-0.05, min(0.05, -median_dev))
        return round(offset, 4)
    except Exception:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-run", action="store_true",
                    help="复用最近成片只做评测闭环")
    args = ap.parse_args()

    run_id = f"hybrid_{time.strftime('%Y%m%d_%H%M%S')}"
    run_meta: dict = {"run_id": run_id, "ok": False, "ae_used": False}

    if not args.skip_run:
        from resolve_ae_resolve_pipeline import ResolveAeResolvePipeline
        pipe = ResolveAeResolvePipeline()
        os.makedirs(OUT_DIR, exist_ok=True)
        clips = pick_clips()

        # 【B4 修复】禁用 beat_offset 校准（xfade 预补偿已处理漂移，额外偏移反而恶化对齐）
        beat_offset = 0.0

        out = pipe.run(clips, BGM, FINAL,
                       title=CONFIG["title"], subtitle=CONFIG["subtitle"],
                       beat_group=CONFIG["beat_group"],
                       transitions=CONFIG["transitions"],
                       lut_path=CONFIG["lut"],
                       beat_offset=beat_offset,
                       output_dir=OUT_DIR)
        rep = pipe.last_report
        run_meta.update(ok=os.path.exists(out), ae_used=rep["ae_used"],
                        duration=rep["duration"], elapsed_s=rep["elapsed_s"],
                        stage_a_duration=rep["stage_a_duration"])
        beats = pipe.vrs.last_analysis["beats"]
        sync = pipe.vrs.measure_sync_quality(FINAL, beats)
    else:
        if not os.path.exists(FINAL):
            print("无既成成片，去掉 --skip-run 重跑")
            return 1
        from resolve_ae_resolve_pipeline import ResolveAeResolvePipeline
        pipe = ResolveAeResolvePipeline()
        # 复用最近一次分析的节拍不可行（进程已换），用 BGM 重新分析
        analysis = pipe.vrs.analyze(BGM)
        beats = analysis["beats"]
        sync = pipe.vrs.measure_sync_quality(FINAL, beats)
        run_meta.update(ok=True, duration=19.2)

    yavg = measure_yavg(FINAL)
    pr = build_pipeline_result(run_meta, sync, yavg)

    print("========== 客观测量 ==========")
    print(json.dumps({"run_id": run_id, "ae_used": run_meta.get("ae_used"),
                      "yavg": round(yavg, 1) if yavg else None,
                      "sync": sync, "quality_score": pr["quality_score"]},
                     ensure_ascii=False, indent=1))

    # ---- 进化闭环：评测 → 候选版本 → 严格对比决策 → 知识沉淀 ----
    from core.evolution.runner import get_evolution_runner
    runner = get_evolution_runner(enable_rubrics=True)
    decision = runner.record_pipeline_run(
        pr, scope="mixed",
        config_snapshot={**CONFIG, "ae_used": run_meta.get("ae_used")})

    print("========== 进化决策 ==========")
    if decision is None:
        print("decision: None (闭环内部异常，已隔离不影响管线)")
        return 1
    print(f"decision={decision.decision}  reason={decision.reason}")
    print("messages_log: data/evolution/messages.jsonl")

    # ---- 能力注册表反馈闭环 ----
    try:
        from core.evolution.capability_feedback import CapabilityFeedbackLoop
        from integrations.smart_director import get_last_run_stats

        fb = CapabilityFeedbackLoop()
        stats = get_last_run_stats()
        presets_used = stats.get("presets_used", [])
        fonts_used = stats.get("fonts_used", [])
        # 获取调色风格（从管线对象中读取）
        grading_styles = getattr(pipe, '_grading_styles_used', [])

        # 将 quality_score 归一化到 0~1 范围
        norm_score = min(1.0, pr["quality_score"] / 100.0)

        fb.record_run(
            presets_used=presets_used,
            fonts_used=fonts_used,
            grading_styles=grading_styles,
            eval_score=norm_score,
        )
        fb.save()

        cov = fb.get_coverage_stats()
        print("========== 能力反馈闭环 ==========")
        print(f"预设覆盖率: {cov['used']}/{cov['total']} = {cov['coverage_rate']:.0%}")
        if cov["unused"]:
            print(f"未使用预设: {', '.join(cov['unused'])}")
    except Exception as e:
        print(f"反馈闭环异常（已隔离）: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
