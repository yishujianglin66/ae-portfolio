# -*- coding: utf-8 -*-
"""MasterCut Agent — Terminal Tool-Use Interface

Bridges the MasterCut pipeline with an autonomous agent architecture inspired by
OpenAI Codex CLI's tool loop. Exposes discrete, stateless functions for each
pipeline stage so the agent can compose workflows dynamically.

Architecture:
  - ToolRegistry: Maps command names (e.g., "analyze_motion", "render_cut") to
    Python callables with typed input/output contracts.
  - Stateless Functions: Each tool function accepts explicit parameters and returns
    structured results (dict/JSON), enabling reproducible execution and audit trails.
  - Evidence Chain Integration: Tools accept optional `skill_id` and return
    `reasoning_log` fields to support evidence-based decision tracking.

Usage:
  from agents.mastercut_agent import MasterCutAgent
  
  agent = MasterCutAgent()
  result = agent.execute("analyze_motion", sources=["video1.mp4"])
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

logger = logging.getLogger("mastercut_agent")


@dataclass
class ToolResult:
    """Structured result from a tool execution."""
    tool_name: str
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    reasoning_log: str = ""
    elapsed_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool": self.tool_name,
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "reasoning_log": self.reasoning_log,
            "elapsed_ms": round(self.elapsed_ms, 2),
        }


class ToolRegistry:
    """Registry mapping tool names to callable functions with metadata."""

    def __init__(self):
        self._tools: Dict[str, Dict[str, Any]] = {}

    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        input_schema: Optional[Dict[str, Any]] = None,
    ):
        """Register a tool with its metadata."""
        self._tools[name] = {
            "func": func,
            "description": description,
            "input_schema": input_schema or {},
        }

    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieve tool metadata by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[Dict[str, str]]:
        """List all registered tools with descriptions."""
        return [
            {"name": name, "description": meta["description"]}
            for name, meta in self._tools.items()
        ]

    def execute(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name with given arguments."""
        if name not in self._tools:
            return ToolResult(
                tool_name=name,
                success=False,
                error=f"Unknown tool: {name}",
            )

        tool_meta = self._tools[name]
        func = tool_meta["func"]

        t0 = time.time()
        try:
            result = func(**kwargs)
            elapsed = (time.time() - t0) * 1000
            return ToolResult(
                tool_name=name,
                success=True,
                output=result if isinstance(result, dict) else {"result": result},
                elapsed_ms=elapsed,
            )
        except Exception as e:
            elapsed = (time.time() - t0) * 1000
            logger.exception(f"Tool {name} failed: {e}")
            return ToolResult(
                tool_name=name,
                success=False,
                error=str(e),
                elapsed_ms=elapsed,
            )


def _stage_analyze_beat(bgm_path: str, **kwargs) -> Dict[str, Any]:
    """① BGM beat/dynamics analysis.

    数据流（2026-09-14 修复：旧 `BeatStrengthEngine.detect(path)` / `analyze(path)`
    已不存在，调用即 AttributeError）：
      ae.beat_detector.BeatDetector   路径 → 拍点(time/strength/is_downbeat) + onset
      core.beat_strength_engine       拍点 → 强/中/弱分级(统计)
      core.music_dynamics             逐帧 RMS → high/mid/low 动态分段
    """
    import librosa
    import numpy as np

    from ae.beat_detector import BeatDetector
    from core.beat_strength_engine import BeatStrengthEngine
    from core.music_dynamics import MusicDynamicsAnalyzer

    detector = BeatDetector()
    beat_infos = detector.detect_beats(bgm_path)
    onset_sec = np.asarray(detector.detect_onsets(bgm_path), dtype=float)

    # 逐帧 RMS 与时间轴：分级与分段共用同一采样
    hop_length = 512
    y, sr = librosa.load(bgm_path, sr=22050, mono=True)
    sr = int(sr)
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    total_duration = float(len(y)) / float(sr)

    beats_sec = np.asarray([b.time for b in beat_infos], dtype=float)
    downbeats_sec = np.asarray([b.time for b in beat_infos if b.is_downbeat], dtype=float)

    strength_stats: Dict[str, Any] = {}
    if beats_sec.size:
        strength_stats = BeatStrengthEngine().classify_beats(
            beats_sec, downbeats_sec,
            rms_energy=rms, times=times, sr=sr, hop_length=hop_length,
        ).statistics()

    sections = MusicDynamicsAnalyzer().analyze(
        rms, times, total_duration, beats_sec=beats_sec, onsets_sec=onset_sec,
    )

    return {
        "beat_count": len(beat_infos),
        "beats": [{"time": b.time, "strength": b.strength} for b in beat_infos[:50]],  # first 50
        "sections": [
            {"start": s.start, "end": s.end, "level": s.level, "energy": s.energy_mean}
            for s in sections
        ],
        "beat_strength": strength_stats,
    }


def _stage_analyze_motion(sources: List[str], cache_dir: Optional[str] = None, **kwargs) -> Dict[str, Any]:
    """② Source footage motion labeling (CNN+VLM layered classifier)."""
    from ai.camera_decision import SourceCameraInventory

    cache_path = Path(cache_dir) if cache_dir else PROJECT / "tmp" / "motion_cache"
    cache_path.mkdir(parents=True, exist_ok=True)

    inv = SourceCameraInventory()
    results = {}
    for src in sources:
        r = inv.analyze(src)
        results[Path(src).name] = {
            "motion_label": r.get("coarse") or r.get("label"),
            "confidence": r.get("confidence"),
            "source_type": r.get("source"),
        }
    inv.unload()  # Release VLM/VideoMAE memory after analysis

    return {"sources": results}


def _validate_effect_configs(effects: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Validate effect configurations against visual_effect_schema.json."""
    import jsonschema
    
    schema_path = PROJECT / "schemas" / "visual_effect_schema.json"
    if not schema_path.exists():
        return {"valid": False, "error": "Schema file not found"}
    
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    
    errors = []
    for i, effect in enumerate(effects):
        try:
            jsonschema.validate(instance=effect, schema=schema)
        except jsonschema.ValidationError as e:
            errors.append({"effect_index": i, "error": e.message})
    
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "effect_count": len(effects),
    }


# 渲染产物最小体积 (项目铁律: 输出文件 >100KB 才算渲染成功)
MIN_RENDER_BYTES = 100 * 1024


def _apply_effects_to_video(
    effects: List[Dict[str, Any]],
    output_dir: str,
    run_dir_name: Optional[str] = None,
    tag: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """经 build_master_polish.py + render_master.py 应用已校验的特效配置。

    2026-09-07 修复三个致命缺陷:
      1. 原实现用 --input-video/--effects-json/--output-dir/--tag 调用, 而当时
         build_master_polish.py 裸读位置参数 sys.argv[1]/[2] 并施加白名单
         (unified_run\\d+ / run\\d+) → sys.argv[1]="--input-video" 必然 exit(1)。
         实测证据: returncode=1, "[ERR] 非法 run 目录名: --input-video"。
      2. 原实现等待 <tag>_polished.mp4, 但没有任何代码会产出该文件 —
         build 只建 comp 存 polish/master.aep, 真正渲染由 render_master.py
         负责 (aerender -comp MASTER)。现补齐这一步。
      3. 原实现 text=True 解码中文版 AE 的 GBK 输出会抛 UnicodeDecodeError
         并拖垮 subprocess reader 线程。改为 bytes + errors="replace"。

    不再接受 input_video: 底片由 build_master_polish.py 内部推导为
    run_dir/<tag>_lut.mp4, 外部传入无作用。

    dry_run=True 时只验证 schema→plan→JSX 链路, 不调用 AE (AE 被其他会话占用时可用)。
    """
    import re as _re
    import subprocess as sp

    out_dir = Path(output_dir)

    # run_dir / tag 推导 — 先过白名单, 否则子进程只会回一句含糊的 ERR
    if run_dir_name is None:
        run_dir_name = out_dir.name
    from scripts.build_master_polish import RUN_DIR_PATTERN   # 单一真源(Step1.5), 避免三处白名单漂移
    if not _re.fullmatch(RUN_DIR_PATTERN, str(run_dir_name)):
        return {
            "success": False,
            "error": (f"output_dir 目录名 '{run_dir_name}' 不符合白名单 "
                      f"unified_run<N> | unified_r1_fixed_v<N> — 无法定位 run 目录"),
            "effects_applied": 0,
            "effects_requested": len(effects),
        }
    if tag is None:
        _derived = str(run_dir_name).removeprefix("unified_")   # unified_run53 → run53
        if not _re.fullmatch(r"run\d+", _derived):
            return {"success": False, "effects_applied": 0, "effects_requested": len(effects),
                    "error": (f"run '{run_dir_name}' 无法自动派生合法 tag(得 '{_derived}'); "
                              f"r1_fixed 类须显式传 tag=runN")}
        tag = _derived
    if not _re.fullmatch(r"run\d+", str(tag)):
        return {
            "success": False,
            "error": f"推导出的 tag '{tag}' 不符合白名单 run\\d+",
            "effects_applied": 0,
            "effects_requested": len(effects),
        }

    lut = out_dir / f"{tag}_lut.mp4"
    if not lut.exists():
        return {
            "success": False,
            "error": f"缺底片 {lut.name} — build_master_polish.py 以此为输入, 需先跑 LUT 阶段",
            "effects_applied": 0,
            "effects_requested": len(effects),
        }

    out_dir.mkdir(parents=True, exist_ok=True)
    effects_json = out_dir / f"{tag}_schema_effects.json"
    effects_json.write_text(
        json.dumps(effects, ensure_ascii=False, indent=2), encoding="utf-8")

    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    cmd = [sys.executable, str(PROJECT / "scripts" / "build_master_polish.py"),
           str(run_dir_name), str(tag), "--effects-json", str(effects_json)]
    if dry_run:
        cmd.append("--dry-run")

    logger.info(f"[effects] build: {' '.join(cmd[1:])}")
    build = sp.run(cmd, capture_output=True, timeout=1800, cwd=str(PROJECT), env=env)
    build_out = build.stdout.decode("utf-8", "replace")
    build_err = build.stderr.decode("utf-8", "replace")

    # 注入记账 — 由 build_master_polish.py 落盘, 是"实际上了多少"的唯一可信来源
    report_p = PROJECT / "tmp" / "effects_injection_report.json"
    inj: Dict[str, Any] = {}
    if report_p.exists():
        try:
            inj = json.loads(report_p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            inj = {}

    applied = int(inj.get("applied_count", 0))
    unmapped = int(inj.get("unmapped_count", 0))
    skipped = int(inj.get("skipped_count", 0))

    result: Dict[str, Any] = {
        "success": False,
        "stage": "build",
        "returncode": build.returncode,
        "stdout": build_out[-4000:],
        "stderr": build_err[-4000:],
        "effects_requested": len(effects),
        "effects_applied": applied,
        "effects_unmapped": unmapped,
        "effects_skipped": skipped,
        "unmapped_types": inj.get("unmapped_types", {}),
        "carried_from_base": inj.get("carried_from_base", 0),
        "output_video": None,
        "dry_run": dry_run,
    }

    if build.returncode != 0:
        result["error"] = (
            f"build_master_polish.py 退出码 {build.returncode} "
            f"(2=参数/前置缺失, 3=无可执行特效, 4=Bridge 无响应)")
        return result

    if dry_run:
        # 离线模式到 JSX 生成为止; 不声称产出了视频
        result["success"] = True
        result["stage"] = "dry_run"
        result["note"] = "schema→plan→JSX 链路已验证; 未调用 AE, 无渲染产物"
        return result

    # Step2 §4: 特效已由 build_master_polish 应用到 AE → 事后回填 EDL 轨道(非侵入)
    # 失败只记日志绝不阻断主流程(同 unified_edit EDL 块口径)。effects_file 无歧义(本函数自写)。
    try:
        from scripts.inject_edl_tracks import inject_edl_tracks
        _inj = inject_edl_tracks(out_dir, effects_file=str(effects_json))
        result["edl_inject"] = {"effects": _inj["effects_injected"],
                                "text_events": _inj["text_events_injected"],
                                "lint_errors": _inj["lint_errors"]}
        logger.info(f"[edl-inject] effects={_inj['effects_injected']} "
                    f"text_events={_inj['text_events_injected']} lint={len(_inj['lint_errors'])}")
    except Exception as _ie:  # noqa: BLE001
        logger.warning(f"[edl-inject 跳过] {_ie}")

    aep = out_dir / "polish" / "master.aep"
    if not aep.exists():
        result["error"] = f"build 声称成功但未产出 {aep} — AE 未真正建合成"
        return result

    # 第二步: 真实 aerender 渲染 (build 只存 aep, 不出 mp4)
    render_cmd = [sys.executable, str(PROJECT / "scripts" / "render_master.py"),
                  str(run_dir_name), str(tag)]
    logger.info(f"[effects] render: {' '.join(render_cmd[1:])}")
    rend = sp.run(render_cmd, capture_output=True, timeout=1800, cwd=str(PROJECT), env=env)
    result["stage"] = "render"
    result["render_returncode"] = rend.returncode
    result["render_stdout"] = rend.stdout.decode("utf-8", "replace")[-4000:]
    result["render_stderr"] = rend.stderr.decode("utf-8", "replace")[-4000:]

    out_mp4 = out_dir / "polish" / f"{tag}_master.mp4"
    if rend.returncode != 0 or not out_mp4.exists():
        result["error"] = f"render_master.py 失败或未产出 {out_mp4.name}"
        return result

    size = out_mp4.stat().st_size
    result["output_video"] = str(out_mp4)
    result["output_bytes"] = size
    if size < MIN_RENDER_BYTES:
        # 铁律: <100KB 判定为黑屏/空渲染, 不得当作成功
        result["error"] = (f"渲染产物仅 {size:,} B < {MIN_RENDER_BYTES:,} B "
                           f"— 判定为异常输出(黑屏/空合成), 不算成功")
        return result

    result["success"] = True
    result["note"] = (f"已渲染 {size / 1024 / 1024:.1f} MB; 实际生效特效 {applied} 条"
                      + (f", 另有 {unmapped} 条因类型无 RECIPES 实现未生效" if unmapped else ""))
    return result


def _stage_render_cut(
    sources: List[str],
    bgm_path: str,
    output_dir: str,
    output_name: str = "cut.mp4",
    duration: float = 30.0,
    theme: str = "燃向混剪: 铺垫→蓄力→爆发→收尾",
    style: str = "amv_highenergy",
    enable_ae: bool = False,
    skill_id: Optional[str] = None,
    effects: Optional[List[Dict[str, Any]]] = None,
    effects_dry_run: bool = False,
    **kwargs,
) -> Dict[str, Any]:
    """③ Orchestration rendering (ProductionDirector V23 engine).

    Supports optional effect configurations via visual_effect_schema.json.
    When effects are provided, validates them against the schema and applies
    them in a post-processing pass if enable_ae=True.

    effects_dry_run=True 时特效链路只跑到 JSX 生成, 不占 AE —— 供 AE 被其他
    会话占用时做离线链路验证。
    """
    from ai.production_director import ProductionDirector

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Validate effects if provided
    effects_validation = None
    if effects:
        effects_validation = _validate_effect_configs(effects)
        if not effects_validation["valid"]:
            return {
                "video_path": None,
                "error": "Effect validation failed",
                "validation_errors": effects_validation["errors"],
            }

    # Load taste profile if available
    taste_path = PROJECT / "data" / "style_cards" / f"{style}.json"
    taste = None
    if taste_path.exists():
        taste = json.loads(taste_path.read_text(encoding="utf-8"))

    director = ProductionDirector(
        work_dir=str(out_dir / "work"),
        taste_profile=taste,
    )

    base_video = director.render(
        video_sources=sources,
        bgm_path=bgm_path,
        output_dir=str(out_dir),
        output_name=output_name,
        target_duration=duration,
        resolution=(1920, 1080),
        fps=24,
        use_speed_ramp=True,
        verify_content=False,
        theme=theme,
        enable_ae_channel=enable_ae,
        clean_bgm_sfx=False,
        beat_lock_hard_cuts=True,
    )

    # Apply effects if provided and AE channel enabled
    final_video = str(base_video)
    effect_result: Optional[Dict[str, Any]] = None
    if effects and enable_ae:
        logger.info(f"Applying {len(effects)} effects...")
        # 不传 tag: 旧实现传 f"{stem}_fx" 违反 build_master_polish.py 的 run\\d+
        # 白名单; run_dir/tag 现由 _apply_effects_to_video 从 output_dir 推导。
        effect_result = _apply_effects_to_video(
            effects=effects,
            output_dir=str(out_dir),
            dry_run=effects_dry_run,
        )
        if effect_result["success"] and effect_result.get("output_video"):
            final_video = effect_result["output_video"]
        elif not effect_result["success"]:
            # 失败不静默降级回 base_video 却不告知 —— 调用方必须能区分
            # "特效已上" 与 "特效失败只拿到底片"
            logger.warning(
                f"Effect application FAILED (stage={effect_result.get('stage')}): "
                f"{effect_result.get('error')}")

    # Extract internal state for evidence chain
    dyn_sections = getattr(director, "_dyn_sections", []) or []
    onsets = getattr(director, "_onsets", []) or []

    # 如实上报: 只统计真正生效的条数。旧实现无条件返回 len(effects),
    # 即使 _apply_effects_to_video 己失败也报"全部已应用" —— 假绿灯。
    applied = int((effect_result or {}).get("effects_applied", 0))
    return {
        "video_path": final_video,
        "base_video": str(base_video),
        "duration": duration,
        "sections_count": len(dyn_sections),
        "onset_count": len(onsets),
        "ae_enabled": enable_ae,
        "skill_id": skill_id,
        "effects_requested": len(effects) if effects else 0,
        "effects_applied": applied,
        "effects_unmapped": int((effect_result or {}).get("effects_unmapped", 0)),
        "effects_skipped": int((effect_result or {}).get("effects_skipped", 0)),
        "effects_success": (bool(effect_result["success"]) if effect_result else None),
        "effects_stage": (effect_result or {}).get("stage"),
        "effects_error": (effect_result or {}).get("error"),
        "effects_output": (effect_result or {}).get("output_video"),
        "effects_note": (effect_result or {}).get("note"),
        "effects_validation": effects_validation,
    }


def _stage_apply_lut(
    input_video: str,
    output_dir: str,
    style: str = "amv_highenergy",
    tag: str = "lut",
    **kwargs,
) -> Dict[str, Any]:
    """④-a LUT color grading (style-themed Hollywood/Vintage Film)."""
    import subprocess as sp

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    lut_map = {
        "amv_highenergy": "好莱坞 _ Hollywood",
        "cinematic_film": "好莱坞 _ Hollywood",
        "vintage_film": "复古电影 _ Vintage Film",
    }
    theme_lut = lut_map.get(style, "好莱坞 _ Hollywood")

    from core.lut_pipeline import load_sampling

    cube = load_sampling().get(theme_lut, [None])[0]
    if not cube:
        return {"success": False, "error": f"LUT not found for {theme_lut}"}

    output_video = str(out_dir / f"{tag}_lut.mp4")
    cube_path = cube.replace("\\", "/").replace(":", "\\:")

    # Compress large files first, then apply LUT while preserving audio
    input_path = input_video
    if Path(input_video).stat().st_size > 50e6:
        small_path = str(out_dir / f"{tag}_small.mp4")
        sp.run(
            ["ffmpeg", "-y", "-i", input_video, "-c:v", "libx264", "-preset", "fast",
             "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "copy", small_path],
            capture_output=True, timeout=1200,
        )
        input_path = small_path

    result = sp.run(
        ["ffmpeg", "-y", "-i", input_path, "-vf", f"lut3d='{cube_path}'",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18",
         "-pix_fmt", "yuv420p", "-c:a", "copy", output_video],
        capture_output=True, timeout=1200,
    )

    return {
        "success": result.returncode == 0,
        "output_video": output_video if result.returncode == 0 else None,
        "lut_applied": theme_lut,
    }


def _stage_apply_sfx(
    input_video: str,
    bgm_path: str,
    output_dir: str,
    production_report_path: Optional[str] = None,
    tag: str = "sfx",
    **kwargs,
) -> Dict[str, Any]:
    """④-b SFX v2.1 musical enhancement (impact/whoosh/glitch layers)."""
    import random
    import subprocess as sp

    from core.sfx_layer import _load_index as sfx_index, shorten_sfx, SFX_TAIL_S

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load production report for cut times
    pr_path = Path(production_report_path) if production_report_path else out_dir / "production_report.json"
    if not pr_path.exists():
        return {"success": False, "error": "Production report not found"}

    pr = json.loads(pr_path.read_text(encoding="utf-8"))
    segments = pr.get("script", {}).get("segments", [])

    pools = {k: sfx_index().get(k, []) for k in ("impact", "whoosh", "riser", "glitch")}
    lvl_mult = {"low": 0.65, "mid": 0.85, "high": 1.0}

    rng = random.Random(2027)
    plan = []
    cut_times = []

    for seg in segments:
        t = round(seg.get("start_time", 0), 2)
        if t < 0.05:
            continue
        cut_times.append(t)

        mood = seg.get("mood", "build")
        if mood in ("drop", "climax"):
            pool, base_gain, pre_delay = "impact", 0.65, 0.040
        elif mood == "intro":
            pool, base_gain, pre_delay = "whoosh", 0.32, 0.080
        else:
            pool, base_gain, pre_delay = "whoosh", 0.38, 0.080

        files = pools[pool]
        if not files:
            continue

        f = rng.choice(files)
        gain = base_gain * lvl_mult.get("mid", 0.85)
        plan.append((shorten_sfx(f, SFX_TAIL_S[pool], pool=pool) or f,
                     max(0, int((t - pre_delay) * 1000)), round(gain, 2)))

    # Mix SFX batch
    output_video = str(out_dir / f"{tag}_final.mp4")
    frame_ms = 1000.0 / 24.0

    def qframe(t):
        return int(round((t - 0.006) * 24) * frame_ms)

    parts, labels = [], []
    for i, (f, ms, g) in enumerate(plan, start=1):
        qms = int(round(ms / frame_ms) * frame_ms)
        parts.append(f"[{i}:a]adelay={qms}|{qms},volume={g:.2f}[s{i}]")
        labels.append(f"[s{i}]")

    parts.append(
        "[0:a]" + "".join(labels) +
        f"amix=inputs={len(plan)+1}:duration=first:normalize=0[am];"
        f"[am]alimiter=attack=1:release=50:limit=0.88:level=0[outa]"
    )

    cmd = ["ffmpeg", "-y", "-i", input_video]
    for f, _, _ in plan:
        cmd += ["-i", f]
    cmd += ["-filter_complex", ";".join(parts), "-map", "0:v", "-map", "[outa]",
            "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", output_video]

    result = sp.run(cmd, capture_output=True, timeout=600)

    return {
        "success": result.returncode == 0,
        "output_video": output_video if result.returncode == 0 else None,
        "sfx_count": len(plan),
    }


def _stage_score_video(video_path: str, mode: str = "local", **kwargs) -> Dict[str, Any]:
    """⑤ Final video scoring (CNN + SiliconFlow hybrid chain)."""
    from core.cnn_scorer import score_video_mode

    result = score_video_mode(video_path, mode)
    return {
        "scores": result.get("scores", {}),
        "video_path": video_path,
    }


def _stage_run_gate(output_dir: str, tag: str, bgm_path: str, **kwargs) -> Dict[str, Any]:
    """⑥ Quality gate validation (7-metric acceptance criteria)."""
    import subprocess as sp

    result = sp.run(
        [sys.executable, str(PROJECT / "scripts" / "render_gate.py"),
         output_dir, tag, "--bgm", bgm_path],
        capture_output=True, text=True, timeout=900, encoding="utf-8", errors="replace",
    )

    accepted = "ACCEPT" in result.stdout
    return {
        "accepted": accepted,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _stage_harvest_experience(output_dir: str, tag: str, bgm_path: str, **kwargs) -> Dict[str, Any]:
    """⑦ Experience harvesting (auto-save to render_history.jsonl)."""
    import subprocess as sp

    result = sp.run(
        [sys.executable, str(PROJECT / "scripts" / "harvest_experience.py"),
         output_dir, tag, "--bgm", bgm_path],
        capture_output=True, text=True, timeout=900,
    )

    return {
        "success": result.returncode == 0,
        "stdout": result.stdout,
    }


class MasterCutAgent:
    """Autonomous agent for MasterCut pipeline orchestration.

    Exposes a tool-use interface where each pipeline stage is a callable tool.
    The agent can execute tools sequentially or compose them based on user intent.

    Example:
        agent = MasterCutAgent()
        
        # Execute individual tools
        beat_result = agent.execute("analyze_beat", bgm_path="bgm.mp3")
        motion_result = agent.execute("analyze_motion", sources=["vid1.mp4"])
        
        # Full pipeline execution
        result = agent.run_full_pipeline(
            sources=["vid1.mp4", "vid2.mp4"],
            bgm_path="bgm.mp3",
            output_dir="./output",
        )
    """

    def __init__(self):
        self.registry = ToolRegistry()
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all default pipeline stage tools."""
        self.registry.register(
            name="analyze_beat",
            func=_stage_analyze_beat,
            description="Analyze BGM beat strength and dynamic sections",
            input_schema={"bgm_path": "str"},
        )
        self.registry.register(
            name="analyze_motion",
            func=_stage_analyze_motion,
            description="Label source footage with motion categories (zoom/static/tilt-orbit)",
            input_schema={"sources": "List[str]", "cache_dir": "Optional[str]"},
        )
        self.registry.register(
            name="render_cut",
            func=_stage_render_cut,
            description="Orchestrate video cut using ProductionDirector V23 engine with optional effect configurations",
            input_schema={
                "sources": "List[str]",
                "bgm_path": "str",
                "output_dir": "str",
                "duration": "float",
                "theme": "str",
                "style": "str",
                "enable_ae": "bool",
                "skill_id": "Optional[str]",
                "effects": "Optional[List[Dict]] - visual_effect_schema.json compliant effect configs",
                "effects_dry_run": "bool - 只验证 schema→plan→JSX 链路, 不调用 AE",
            },
        )
        self.registry.register(
            name="apply_lut",
            func=_stage_apply_lut,
            description="Apply style-themed LUT color grading",
            input_schema={
                "input_video": "str",
                "output_dir": "str",
                "style": "str",
                "tag": "str",
            },
        )
        self.registry.register(
            name="apply_sfx",
            func=_stage_apply_sfx,
            description="Add musical SFX layers (impact/whoosh/glitch) aligned to cuts",
            input_schema={
                "input_video": "str",
                "bgm_path": "str",
                "output_dir": "str",
                "production_report_path": "Optional[str]",
                "tag": "str",
            },
        )
        self.registry.register(
            name="score_video",
            func=_stage_score_video,
            description="Score final video quality using CNN + SiliconFlow hybrid",
            input_schema={"video_path": "str", "mode": "str"},
        )
        self.registry.register(
            name="run_gate",
            func=_stage_run_gate,
            description="Run 7-metric quality gate validation",
            input_schema={"output_dir": "str", "tag": "str", "bgm_path": "str"},
        )
        self.registry.register(
            name="harvest_experience",
            func=_stage_harvest_experience,
            description="Harvest execution experience to render_history.jsonl",
            input_schema={"output_dir": "str", "tag": "str", "bgm_path": "str"},
        )

    def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """Execute a registered tool by name."""
        return self.registry.execute(tool_name, **kwargs)

    def list_tools(self) -> List[Dict[str, str]]:
        """List all available tools."""
        return self.registry.list_tools()

    def run_full_pipeline(
        self,
        sources: List[str],
        bgm_path: str,
        output_dir: str,
        tag: str = "run",
        duration: float = 30.0,
        theme: str = "燃向混剪: 铺垫→蓄力→爆发→收尾",
        style: str = "amv_highenergy",
        enable_ae: bool = False,
    ) -> Dict[str, Any]:
        """Execute the full MasterCut pipeline end-to-end.

        This is a convenience method that chains all stages in sequence.
        For fine-grained control, use `execute()` for individual tools.
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        report: Dict[str, Any] = {
            "sources": sources,
            "bgm": bgm_path,
            "theme": theme,
            "capabilities_used": {},
            "stages": {},
        }

        t0 = time.time()

        # Stage 1: Beat analysis
        logger.info("Stage 1: Analyzing BGM beats...")
        beat_result = self.execute("analyze_beat", bgm_path=bgm_path)
        report["stages"]["beat_analysis"] = beat_result.to_dict()
        report["capabilities_used"]["beat_analysis"] = beat_result.success

        # Stage 2: Motion labeling
        logger.info("Stage 2: Analyzing source motion...")
        motion_result = self.execute("analyze_motion", sources=sources, cache_dir=str(out_dir / "cache"))
        report["stages"]["motion_analysis"] = motion_result.to_dict()
        report["capabilities_used"]["motion_labels"] = motion_result.success

        # Stage 3: Render cut
        logger.info("Stage 3: Rendering cut...")
        cut_result = self.execute(
            "render_cut",
            sources=sources,
            bgm_path=bgm_path,
            output_dir=str(out_dir),
            output_name=f"{tag}_cut.mp4",
            duration=duration,
            theme=theme,
            style=style,
            enable_ae=enable_ae,
        )
        report["stages"]["render_cut"] = cut_result.to_dict()
        report["capabilities_used"]["v23_engine"] = cut_result.success

        if not cut_result.success:
            report["error"] = "Render cut failed"
            return report

        video_path = cut_result.output.get("video_path")

        # Stage 4a: Apply LUT
        logger.info("Stage 4a: Applying LUT...")
        lut_result = self.execute(
            "apply_lut",
            input_video=video_path,
            output_dir=str(out_dir),
            style=style,
            tag=tag,
        )
        report["stages"]["apply_lut"] = lut_result.to_dict()
        report["capabilities_used"]["lut"] = lut_result.success

        video_path = lut_result.output.get("output_video") or video_path

        # Stage 4b: Apply SFX
        logger.info("Stage 4b: Applying SFX...")
        pr_path = out_dir / "production_report.json"
        sfx_result = self.execute(
            "apply_sfx",
            input_video=video_path,
            bgm_path=bgm_path,
            output_dir=str(out_dir),
            production_report_path=str(pr_path) if pr_path.exists() else None,
            tag=tag,
        )
        report["stages"]["apply_sfx"] = sfx_result.to_dict()
        report["capabilities_used"]["sfx"] = sfx_result.success

        final_video = sfx_result.output.get("output_video") or video_path

        # Stage 5: Score video
        logger.info("Stage 5: Scoring video...")
        score_result = self.execute("score_video", video_path=final_video)
        report["stages"]["scoring"] = score_result.to_dict()
        report["capabilities_used"]["scoring"] = score_result.success

        # Stage 6: Quality gate
        logger.info("Stage 6: Running quality gate...")
        gate_result = self.execute("run_gate", output_dir=str(out_dir), tag=tag, bgm_path=bgm_path)
        report["stages"]["quality_gate"] = gate_result.to_dict()
        report["capabilities_used"]["gate"] = gate_result.success

        # Stage 7: Harvest experience
        logger.info("Stage 7: Harvesting experience...")
        harvest_result = self.execute(
            "harvest_experience", output_dir=str(out_dir), tag=tag, bgm_path=bgm_path
        )
        report["stages"]["harvest"] = harvest_result.to_dict()
        report["capabilities_used"]["harvest"] = harvest_result.success

        report["elapsed_s"] = round(time.time() - t0, 2)
        report["final_video"] = final_video

        # Save report
        report_path = out_dir / f"{tag}_agent_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        return report
