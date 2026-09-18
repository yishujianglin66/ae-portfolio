"""创意生成 API 端点（P3/P4 级）。

包含：
- 风格迁移 API
- 多模态导演系统 API
- 智能镜头语言 API
- 自动复刻/视频生成 API
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger

router = APIRouter(prefix="/api/v1", tags=["creative"])

# ── 项目根目录（用于导入根目录下的模块） ──
PROJECT_ROOT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ============================================================
#  1. 智能镜头语言 API
# ============================================================

@router.get("/cinematic/shot/recommend")
async def recommend_shot(
    mood: str = Query(..., description="情绪标签: intense/calm/epic/tense/climax/..."),
    content: str = Query("", description="内容描述: battle/dialogue/landscape/..."),
    prev_scale: str | None = Query(None, description="前镜头景别"),
    beat_time: float | None = Query(None, description="节拍时间点"),
):
    """根据情绪和内容推荐最优镜头参数。"""
    try:
        from scene.cinematic_intelligence import CinematicIntelligence
        ci = CinematicIntelligence()
        prev_shot = None
        if prev_scale:
            prev_shot = {"scale": prev_scale}
        rec = ci.recommend_shot(mood, content, prev_shot, beat_time)
        return {"success": True, "recommendation": rec}
    except Exception as e:
        logger.error(f"镜头推荐失败: {e}")
        raise HTTPException(status_code=500, detail=f"镜头推荐失败: {e}")


@router.post("/cinematic/shot/optimize-script")
async def optimize_script(script: dict[str, Any]):
    """优化整个剧本的镜头语言。

    输入: {"segments": [{"mood": "...", "content": "..."}, ...]}
    输出: 优化后的剧本（含镜头/转场推荐）
    """
    try:
        from scene.cinematic_intelligence import CinematicIntelligence
        ci = CinematicIntelligence()
        optimized = ci.optimize_script(script)
        return {"success": True, "optimized": optimized}
    except Exception as e:
        logger.error(f"剧本优化失败: {e}")
        raise HTTPException(status_code=500, detail=f"剧本优化失败: {e}")


@router.get("/cinematic/transition/recommend")
async def recommend_transition(
    prev_mood: str = Query(..., description="前一段情绪"),
    curr_mood: str = Query(..., description="当前段情绪"),
    prev_content: str = Query("", description="前一段内容"),
    curr_content: str = Query("", description="当前段内容"),
):
    """推荐两段之间的最优转场。"""
    try:
        from scene.cinematic_intelligence import CinematicIntelligence
        ci = CinematicIntelligence()
        trans = ci.recommend_transition(prev_mood, curr_mood, prev_content, curr_content)
        return {"success": True, "transition": trans}
    except Exception as e:
        logger.error(f"转场推荐失败: {e}")
        raise HTTPException(status_code=500, detail=f"转场推荐失败: {e}")


@router.post("/cinematic/continuity/check")
async def check_continuity(segments: list[dict[str, Any]]):
    """检查镜头连续性，报告可能不自然的跳跃。"""
    try:
        from scene.cinematic_intelligence import CinematicIntelligence
        ci = CinematicIntelligence()
        issues = ci.analyze_continuity(segments)
        return {
            "success": True,
            "issues": issues,
            "issue_count": len(issues),
            "clean": len(issues) == 0,
        }
    except Exception as e:
        logger.error(f"连续性检查失败: {e}")
        raise HTTPException(status_code=500, detail=f"连续性检查失败: {e}")


@router.get("/cinematic/moods")
async def list_moods():
    """列出所有支持的情绪标签。"""
    try:
        from scene.cinematic_intelligence import EMOTION_CAMERA_MAP
        moods = list(EMOTION_CAMERA_MAP.keys())
        return {"success": True, "moods": moods, "count": len(moods)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取情绪列表失败: {e}")


# ============================================================
#  2. 多模态导演系统 API
# ============================================================

@router.post("/director/produce")
async def director_produce(params: dict[str, Any]):
    """完整导演生产流程。

    从一句话描述到成品视频的完整自动化创作链。

    请求体:
    {
        "prompt": "利威尔高燃混剪, 电影感, 30秒",
        "material_urls": [],
        "material_paths": [],
        "style": "cinematic",
        "auto_launch_ae": false,
        "enable_3d_stage": true,
        "enable_style_migration": true,
        "reference_video": null,
        "audio_path": null,
        "enable_audio_edit": true
    }
    """
    try:
        from ai.ai_director import AIDirector

        from ..engines.base import validate_path_safety
        output_dir = params.get("output_dir", str(PROJECT_ROOT / "output_director"))
        director = AIDirector(output_dir=output_dir)

        # 安全校验：验证所有素材路径在允许范围内
        material_paths = params.get("material_paths")
        if material_paths:
            validated_paths = []
            for p in material_paths:
                try:
                    safe_p = validate_path_safety(p, must_exist=True)
                    validated_paths.append(str(safe_p))
                except (ValueError, FileNotFoundError) as ve:
                    logger.warning(f"素材路径校验失败，已跳过: {p} -> {ve}")
            params["material_paths"] = validated_paths

        result = director.produce(
            user_prompt=params.get("prompt", ""),
            material_urls=params.get("material_urls"),
            material_paths=params.get("material_paths"),
            style=params.get("style", "cinematic"),
            auto_launch_ae=params.get("auto_launch_ae", False),
            enable_3d_stage=params.get("enable_3d_stage", True),
            enable_style_migration=params.get("enable_style_migration", True),
            reference_video=params.get("reference_video"),
            audio_path=params.get("audio_path"),
            enable_audio_edit=params.get("enable_audio_edit", True),
        )
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"导演生产失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"导演生产失败: {e}")


@router.post("/director/generate-script")
async def director_generate_script(params: dict[str, Any]):
    """仅生成 AI 剧本（不执行后续步骤）。"""
    try:
        from ai.ai_director import ScriptGenerator
        gen = ScriptGenerator()
        script = gen.generate_script(
            user_prompt=params.get("prompt", ""),
            material_analyses=params.get("material_analyses", []),
            style=params.get("style", "cinematic"),
        )
        return {"success": True, "script": script}
    except Exception as e:
        logger.error(f"剧本生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"剧本生成失败: {e}")


@router.post("/director/translate-jsx")
async def director_translate_jsx(params: dict[str, Any]):
    """将剧本翻译为 JSX 脚本。"""
    try:
        from ai.ai_director import ScriptToJSXTranslator
        translator = ScriptToJSXTranslator()
        jsx = translator.translate(
            script=params.get("script", {}),
            material_paths=params.get("material_paths", []),
        )
        return {"success": True, "jsx": jsx, "jsx_lines": len(jsx.splitlines())}
    except Exception as e:
        logger.error(f"JSX翻译失败: {e}")
        raise HTTPException(status_code=500, detail=f"JSX翻译失败: {e}")


@router.post("/director/analyze-materials")
async def director_analyze_materials(params: dict[str, Any]):
    """分析素材视频的视觉特征。"""
    try:
        from ai.ai_director import VisualAnalyzer

        from ..engines.base import validate_path_safety
        analyzer = VisualAnalyzer()
        results = []
        for path in params.get("paths", []):
            try:
                safe_path = validate_path_safety(path, must_exist=True)
                analysis = analyzer.analyze(str(safe_path))
                analysis["source"] = path
                results.append(analysis)
            except (ValueError, FileNotFoundError) as ve:
                results.append({"error": f"路径校验失败: {ve}", "source": path})
        return {"success": True, "analyses": results}
    except Exception as e:
        logger.error(f"素材分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"素材分析失败: {e}")


# ============================================================
#  3. 自动复刻 / 视频生成 API
# ============================================================

@router.post("/replica/analyze-music")
async def replica_analyze_music(params: dict[str, Any]):
    """分析音乐文件（BPM/节拍/能量曲线）。"""
    try:
        from video.video_generator import VideoGenerator
        gen = VideoGenerator()
        music_path = params.get("music_path", "")
        if not os.path.exists(music_path):
            raise HTTPException(status_code=400, detail=f"音乐文件不存在: {music_path}")
        analysis = gen.analyze_music(music_path)
        return {"success": True, "analysis": analysis}
    except Exception as e:
        logger.error(f"音乐分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"音乐分析失败: {e}")


@router.post("/replica/analyze-clips")
async def replica_analyze_clips(params: dict[str, Any]):
    """分析视频片段（色彩/运动/时长）。"""
    try:
        from video.video_generator import VideoGenerator
        gen = VideoGenerator()
        clip_paths = params.get("clip_paths", [])
        atoms = gen.analyze_clips(clip_paths)
        return {"success": True, "clip_atoms": atoms, "count": len(atoms)}
    except Exception as e:
        logger.error(f"片段分析失败: {e}")
        raise HTTPException(status_code=500, detail=f"片段分析失败: {e}")


@router.post("/replica/match-audio-video")
async def replica_match_audio_video(params: dict[str, Any]):
    """音画匹配 — 根据音乐节奏自动排列片段。"""
    try:
        from video.video_generator import VideoGenerator
        gen = VideoGenerator()
        music_analysis = params.get("music_analysis", {})
        clip_atoms = params.get("clip_atoms", [])
        match = gen.match_audio_video(music_analysis, clip_atoms)
        return {"success": True, "match": match}
    except Exception as e:
        logger.error(f"音画匹配失败: {e}")
        raise HTTPException(status_code=500, detail=f"音画匹配失败: {e}")


@router.post("/replica/generate-timeline")
async def replica_generate_timeline(params: dict[str, Any]):
    """生成完整时间轴计划（含图层/效果/关键帧）。"""
    try:
        from video.video_generator import VideoGenerator
        gen = VideoGenerator()
        match_result = params.get("match_result", {})
        music_analysis = params.get("music_analysis", {})
        timeline = gen.generate_timeline_plan(match_result, music_analysis)
        return {"success": True, "timeline": timeline}
    except Exception as e:
        logger.error(f"时间轴生成失败: {e}")
        raise HTTPException(status_code=500, detail=f"时间轴生成失败: {e}")


@router.post("/replica/run-pipeline")
async def replica_run_pipeline(params: dict[str, Any]):
    """运行完整复刻流水线（分析+匹配+时间轴+可选AE执行）。"""
    try:
        from video.video_generator import VideoGenerator
        gen = VideoGenerator()
        music_path = params.get("music_path", "")
        clip_paths = params.get("clip_paths", [])

        if not os.path.exists(music_path):
            raise HTTPException(status_code=400, detail=f"音乐文件不存在: {music_path}")

        result = gen.run_full_pipeline(music_path, clip_paths)
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"流水线执行失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"流水线执行失败: {e}")


@router.post("/replica/run-enhanced")
async def replica_run_enhanced(params: dict[str, Any]):
    """运行增强版复刻流水线（四引擎集成）。"""
    try:
        from video.video_generator import VideoGenerator
        gen = VideoGenerator()
        result = gen.run_enhanced_pipeline(
            music_path=params.get("music_path", ""),
            clip_paths=params.get("clip_paths", []),
            style=params.get("style", "cinematic"),
            include_text=params.get("include_text", True),
            include_transitions=params.get("include_transitions", True),
            include_filters=params.get("include_filters", True),
            text_overlays=params.get("text_overlays"),
        )
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"增强流水线失败: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"增强流水线失败: {e}")


# ============================================================
#  4. 风格迁移 API
# ============================================================

@router.post("/style/extract")
async def style_extract(params: dict[str, Any]):
    """从参考视频中提取风格指纹。

    请求体: {"video_path": "..."}
    返回: 风格标签/色彩情绪/节奏类型/能量等级
    """
    try:
        from video.style_migrator import StyleMigrator
        migrator = StyleMigrator()
        video_path = params.get("video_path", "")
        if not os.path.exists(video_path):
            raise HTTPException(status_code=400, detail=f"视频文件不存在: {video_path}")

        fingerprint = migrator.extractor.extract(video_path)
        match = migrator.matcher.match(fingerprint)
        return {
            "success": True,
            "fingerprint": {
                "style_tags": fingerprint.get("style_tags", []),
                "color_mood": fingerprint.get("color", {}).get("color_mood", "balanced"),
                "rhythm": fingerprint.get("rhythm", {}).get("rhythm_type", "moderate"),
                "energy": fingerprint.get("energy", {}).get("level", "medium"),
            },
            "match": match,
        }
    except Exception as e:
        logger.error(f"风格提取失败: {e}")
        raise HTTPException(status_code=500, detail=f"风格提取失败: {e}")


@router.post("/style/match")
async def style_match(params: dict[str, Any]):
    """将风格指纹匹配到预设风格。"""
    try:
        from video.style_migrator import StyleMigrator
        migrator = StyleMigrator()
        fingerprint = params.get("fingerprint", {})
        match = migrator.matcher.match(fingerprint)
        return {"success": True, "match": match}
    except Exception as e:
        logger.error(f"风格匹配失败: {e}")
        raise HTTPException(status_code=500, detail=f"风格匹配失败: {e}")


@router.get("/style/presets")
async def style_presets():
    """列出所有可用风格预设。"""
    try:
        from video.style_migrator import StylePresets
        presets = StylePresets()
        return {"success": True, "presets": presets.list_all()}
    except Exception as e:
        logger.error(f"获取风格预设失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取风格预设失败: {e}")


# ============================================================
#  5. 组合创意 API（一键全流程）
# ============================================================

@router.post("/creative/full-pipeline")
async def creative_full_pipeline(params: dict[str, Any]):
    """一键创意全流程 — 导演+镜头语言+风格迁移+复刻的组合。

    这是最强大的端点，整合所有创意模块。

    请求体:
    {
        "prompt": "利威尔高燃混剪, 电影感, 30秒",
        "material_paths": [...],
        "style": "cinematic",
        "reference_video": null,
        "audio_path": null,
        "enable_cinematic_optimization": true,
        "enable_style_migration": true,
        "enable_audio_sync": true
    }
    """
    start = time.time()
    report: dict[str, Any] = {"phases": {}}

    try:
        # ── Phase 1: 导演生产 ──
        from ai.ai_director import AIDirector
        output_dir = params.get("output_dir", str(PROJECT_ROOT / "output_creative"))
        director = AIDirector(output_dir=output_dir)

        director_result = director.produce(
            user_prompt=params.get("prompt", ""),
            material_paths=params.get("material_paths"),
            style=params.get("style", "cinematic"),
            auto_launch_ae=False,
            enable_3d_stage=True,
            enable_style_migration=params.get("enable_style_migration", True),
            reference_video=params.get("reference_video"),
            audio_path=params.get("audio_path"),
            enable_audio_edit=params.get("enable_audio_sync", True),
        )
        report["phases"]["director"] = {
            "status": "success",
            "script_title": director_result.get("phases", {}).get("script", {}).get("title"),
            "jsx_lines": director_result.get("phases", {}).get("translation", {}).get("jsx_lines"),
        }

        # ── Phase 2: 镜头语言优化（可选） ──
        if params.get("enable_cinematic_optimization", True):
            from scene.cinematic_intelligence import CinematicIntelligence
            ci = CinematicIntelligence()
            script_path = Path(output_dir) / "director_script.json"
            if script_path.exists():
                with open(script_path, "r", encoding="utf-8") as f:
                    script = json.load(f)
                optimized = ci.optimize_script(script)
                opt_path = Path(output_dir) / "director_script_optimized.json"
                with open(opt_path, "w", encoding="utf-8") as f:
                    json.dump(optimized, f, ensure_ascii=False, indent=2)
                report["phases"]["cinematic"] = {
                    "status": "success",
                    "optimized_segments": optimized.get("ci_metadata", {}).get("optimized_count"),
                }

        # ── 汇总 ──
        report["success"] = True
        report["elapsed_seconds"] = round(time.time() - start, 1)
        report["output_dir"] = output_dir
        return report

    except Exception as e:
        logger.error(f"创意全流程失败: {e}\n{traceback.format_exc()}")
        report["success"] = False
        report["error"] = str(e)
        report["elapsed_seconds"] = round(time.time() - start, 1)
        raise HTTPException(status_code=500, detail=report)
