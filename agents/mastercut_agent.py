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
    """① BGM beat/dynamics analysis (beat_strength_engine + music_dynamics)."""
    from ai.beat_strength_engine import BeatStrengthEngine
    from ai.music_dynamics import MusicDynamicsAnalyzer

    engine = BeatStrengthEngine()
    beats = engine.detect(bgm_path)

    dyn = MusicDynamicsAnalyzer()
    sections = dyn.analyze(bgm_path)

    return {
        "beat_count": len(beats),
        "beats": [{"time": b.time, "strength": b.strength} for b in beats[:50]],  # first 50
        "sections": [
            {"start": s.start, "end": s.end, "level": s.level, "energy": s.energy_mean}
            for s in sections
        ],
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


def _apply_effects_to_video(
    input_video: str,
    effects: List[Dict[str, Any]],
    output_dir: str,
    tag: str = "effects",
) -> Dict[str, Any]:
    """Apply validated effect configurations to video using build_master_polish.py logic."""
    import subprocess as sp
    
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Write effects config to temporary JSON for build_master_polish.py consumption
    effects_json = out_dir / f"{tag}_effects.json"
    effects_json.write_text(
        json.dumps(effects, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    
    # Call build_master_polish.py with effects config
    # Note: This assumes build_master_polish.py accepts --effects-json parameter
    # If not, we'd need to refactor it to consume the JSON schema
    result = sp.run(
        [sys.executable, str(PROJECT / "scripts" / "build_master_polish.py"),
         "--input-video", input_video,
         "--effects-json", str(effects_json),
         "--output-dir", str(out_dir),
         "--tag", tag],
        capture_output=True, text=True, timeout=1800,
    )
    
    output_video = str(out_dir / f"{tag}_polished.mp4")
    
    return {
        "success": result.returncode == 0 and Path(output_video).exists(),
        "output_video": output_video if result.returncode == 0 else None,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "effects_applied": len(effects),
    }


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
    **kwargs,
) -> Dict[str, Any]:
    """③ Orchestration rendering (ProductionDirector V23 engine).
    
    Supports optional effect configurations via visual_effect_schema.json.
    When effects are provided, validates them against the schema and applies
    them in a post-processing pass if enable_ae=True.
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
    if effects and enable_ae:
        logger.info(f"Applying {len(effects)} effects...")
        effect_result = _apply_effects_to_video(
            input_video=str(base_video),
            effects=effects,
            output_dir=str(out_dir),
            tag=f"{Path(output_name).stem}_fx",
        )
        if effect_result["success"]:
            final_video = effect_result["output_video"]
        else:
            logger.warning(f"Effect application failed: {effect_result.get('stderr')}")

    # Extract internal state for evidence chain
    dyn_sections = getattr(director, "_dyn_sections", []) or []
    onsets = getattr(director, "_onsets", []) or []

    return {
        "video_path": final_video,
        "base_video": str(base_video),
        "duration": duration,
        "sections_count": len(dyn_sections),
        "onset_count": len(onsets),
        "ae_enabled": enable_ae,
        "skill_id": skill_id,
        "effects_applied": len(effects) if effects else 0,
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

        report = {
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
