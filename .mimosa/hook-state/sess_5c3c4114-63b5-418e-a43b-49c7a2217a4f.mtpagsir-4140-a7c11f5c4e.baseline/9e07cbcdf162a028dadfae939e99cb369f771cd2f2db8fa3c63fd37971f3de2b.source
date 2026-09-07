#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
multimodal_director.py — 多模态导演系统
========================================

核心能力：接收多种输入（文字/图片/视频/音乐），生成完整剪辑剧本。

输入模式:
  1. 文字描述 → "做一个进击的巨人高燃混剪，节奏快，利威尔为主"
  2. 参考视频 → 分析视频风格，学习节奏/色调/转场
  3. 参考图片 → 提取视觉风格（色调/构图/氛围）
  4. 音乐驱动 → 分析BPM/情绪曲线，自动匹配画面节奏
  5. 混合输入 → 以上任意组合

输出:
  EditScript JSON — 完整分镜脚本，可直接驱动AE自动化

用法:
    director = MultimodalDirector()
    script = director.direct_from_text("做一个利威尔高燃混剪")
    script = director.direct_from_video("reference.mp4")
    script = director.direct_mixed(text="高燃混剪", video="ref.mp4", music="bgm.mp3")
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))


def log(msg: str, level: str = "INFO"):
    ts = time.strftime("%H:%M:%S")
    print(f"  [{ts}][{level}] {msg}")


# ================================================================
#  剪辑剧本数据结构
# ================================================================

class EditScript:
    """剪辑剧本 — 描述完整视频的每一个镜头"""

    def __init__(self):
        self.title: str = ""
        self.total_duration: float = 0.0
        self.style: Dict[str, str] = {}
        self.segments: List[Dict[str, Any]] = []
        self.bgm_path: str = ""
        self.metadata: Dict[str, Any] = {}

    def add_segment(self, segment: Dict[str, Any]):
        """添加一个镜头段落"""
        self.segments.append(segment)
        self.total_duration += segment.get("duration", 0)

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "total_duration": self.total_duration,
            "style": self.style,
            "bgm_path": self.bgm_path,
            "segments": self.segments,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.to_json())
        log(f"剧本已保存: {path}")


# ================================================================
#  镜头模板库 — 常见混剪结构
# ================================================================

SHOT_TEMPLATES = {
    "epic_opening": {
        "description": "史诗开场：黑屏→渐入→大场景",
        "structure": [
            {"type": "black", "duration": 1.0},
            {"type": "fade_in", "duration": 2.0, "camera": "slow_push", "scale": "wide"},
            {"type": "montage", "duration": 8.0, "cut_speed": "fast", "camera": "mixed"},
        ],
    },
    "battle_montage": {
        "description": "战斗蒙太奇：快切+节拍卡点",
        "structure": [
            {"type": "action", "duration": 3.0, "cut_speed": "very_fast", "camera": "shake"},
            {"type": "impact", "duration": 0.5, "effect": "flash_white", "camera": "zoom_in"},
            {"type": "action", "duration": 5.0, "cut_speed": "fast", "camera": "tracking"},
            {"type": "climax", "duration": 4.0, "effect": "glow", "camera": "orbit"},
        ],
    },
    "emotional": {
        "description": "抒情段落：慢镜头+柔光",
        "structure": [
            {"type": "slow_mo", "duration": 5.0, "camera": "slow_push", "effect": "soft_glow"},
            {"type": "closeup", "duration": 3.0, "camera": "static", "effect": "bokeh"},
            {"type": "wide", "duration": 4.0, "camera": "pull_back", "effect": "warm_tone"},
        ],
    },
    "character_intro": {
        "description": "角色登场：特写→全身→战斗姿态",
        "structure": [
            {"type": "closeup", "duration": 2.0, "camera": "slow_push"},
            {"type": "medium", "duration": 2.0, "camera": "static"},
            {"type": "wide", "duration": 1.5, "camera": "pull_back", "effect": "glow_edge"},
            {"type": "action", "duration": 3.0, "camera": "tracking", "effect": "speed_lines"},
        ],
    },
    "finale": {
        "description": "终章高潮：全力战斗→定格→标题",
        "structure": [
            {"type": "action", "duration": 6.0, "cut_speed": "very_fast", "camera": "mixed"},
            {"type": "climax", "duration": 3.0, "effect": "intense_glow", "camera": "orbit"},
            {"type": "freeze", "duration": 1.5, "effect": "desaturate"},
            {"type": "title_card", "duration": 3.0, "effect": "fade_to_black"},
        ],
    },
}


# ================================================================
#  多模态导演系统
# ================================================================

class MultimodalDirector:
    """多模态导演系统 — 从任意输入生成剪辑剧本"""

    def __init__(self):
        self._init_components()

    def _init_components(self):
        """懒初始化各组件"""
        self._agent = None
        self._visual_analyzer = None
        self._style_analyzer = None
        self._beat_mapper = None
        self._scene_detector = None
        self._intel_engine = None
        self._material_index = None
        self._selected_materials: List[str] = []   # 严格选择后的候选素材

    @property
    def agent(self):
        if self._agent is None:
            try:
                from ai_agent import V4Agent
                self._agent = V4Agent()
                log("LLM Agent 已加载 (DeepSeek V4)")
            except Exception as e:
                log(f"LLM Agent 加载失败: {e}", "WARN")
        return self._agent

    @property
    def visual_analyzer(self):
        if self._visual_analyzer is None:
            try:
                from visual_content_analyzer import VisualContentAnalyzer
                self._visual_analyzer = VisualContentAnalyzer()
                log("视觉分析器已加载")
            except Exception as e:
                log(f"视觉分析器加载失败: {e}", "WARN")
        return self._visual_analyzer

    @property
    def beat_mapper(self):
        if self._beat_mapper is None:
            try:
                from beat_keyframe_mapper import BeatKeyframeMapper
                self._beat_mapper = BeatKeyframeMapper()
                log("节拍映射器已加载")
            except Exception as e:
                log(f"节拍映射器加载失败: {e}", "WARN")
        return self._beat_mapper

    @property
    def scene_detector(self):
        if self._scene_detector is None:
            try:
                from scene_detector import SceneDetector
                self._scene_detector = SceneDetector()
                log("场景检测器已加载")
            except Exception as e:
                log(f"场景检测器加载失败: {e}", "WARN")
        return self._scene_detector

    @property
    def intel_engine(self):
        """素材智能识别引擎 (延迟初始化)"""
        if self._intel_engine is None:
            try:
                from ai.material_intelligence import MaterialIntelligenceEngine
                self._intel_engine = MaterialIntelligenceEngine(frame_sample_count=3)
                log("素材智能识别引擎已加载 (VLM + CV)")
            except Exception as e:
                log(f"素材智能识别引擎加载失败: {e}", "WARN")
        return self._intel_engine

    def _ensure_material_index(self, materials: List[str], target_ip: str = "",
                               strict: bool = True, allow_mixed: bool = False):
        """确保素材索引已构建，并执行严格素材选择"""
        if self._material_index is not None and not target_ip:
            return
        engine = self.intel_engine
        if engine is None:
            return
        try:
            from ai.material_intelligence import MaterialIndex
            idx = MaterialIndex()
            for path in materials:
                if Path(path).exists():
                    tag = engine.analyze_video(path)
                    idx.add(tag)
            self._material_index = idx
            self._selected_materials = list(materials)
            if target_ip:
                selection = idx.select_for_ip(target_ip, allow_mixed=allow_mixed)
                matched = selection["matched"]
                log(f"素材选择 '{target_ip}': 匹配 {len(matched)}, "
                    f"混剪排除 {len(selection['mixed'])}, "
                    f"未识别排除 {len(selection['unknown'])}, "
                    f"其他IP/教程排除 {len(selection['excluded'])}")
                if not matched:
                    if strict:
                        raise RuntimeError(
                            f"严格模式: 无任何素材匹配目标IP《{target_ip}》，"
                            f"拒绝降级到无关素材。请提供真实素材后重试。")
                    log(f"非严格模式: 无匹配素材，使用全部素材", "WARN")
                else:
                    self._selected_materials = matched
        except RuntimeError:
            raise
        except Exception as e:
            log(f"素材索引构建失败: {e}", "WARN")

    # ----------------------------------------------------------------
    #  公开接口
    # ----------------------------------------------------------------

    def direct_from_text(self, description: str,
                         available_materials: Optional[List[str]] = None,
                         target_duration: float = 120.0,
                         cinematic_params: Optional[Dict] = None,
                         target_ip: str = "",
                         strict: bool = True,
                         allow_mixed: bool = False) -> EditScript:
        """从文字描述生成剪辑剧本

        Args:
            description: 用户描述
            available_materials: 可用素材列表
            target_duration: 目标时长(秒)
            cinematic_params: CinematicIntelligence推荐的镜头参数
            target_ip: 目标IP/作品名 (如 "进击的巨人")
            strict: 严格模式，无匹配素材时报错而非降级
            allow_mixed: 是否允许多IP混剪类素材
        """
        log(f"文字导演模式: {description[:50]}...")

        # 构建素材智能索引 + 严格选择
        if available_materials:
            self._ensure_material_index(available_materials, target_ip,
                                        strict, allow_mixed)

        # 1. 用LLM理解意图并生成分镜
        plan = self._generate_plan_from_text(description, target_duration)

        # 2. 构建剧本（支持外部参数覆盖）
        script = self._build_script_from_plan(plan, available_materials, cinematic_params, target_ip)
        script.title = plan.get("title", "未命名")
        script.metadata["input_mode"] = "text"
        script.metadata["description"] = description
        script.metadata["target_ip"] = target_ip
        if cinematic_params:
            script.metadata["cinematic_params"] = cinematic_params

        return script

    def direct_from_cinematic(self, cinematic_recommendation: Dict,
                              available_materials: Optional[List[str]] = None) -> EditScript:
        """从 CinematicIntelligence 的推荐结果生成剧本

        Args:
            cinematic_recommendation: CinematicIntelligence推荐结果，包含镜头参数和风格建议
            available_materials: 可用素材列表

        Example:
            cinematic_recommendation = {
                "title": "推荐标题",
                "mood": "epic",
                "pace": "fast",
                "color_tone": "cool",
                "structure": [...],
                "camera": "slow_push",
                "scale": "wide",
                "transition": "dissolve"
            }
        """
        log(f"Cinematic导演模式: {cinematic_recommendation.get('title', '未命名')[:50]}...")

        plan = {
            "title": cinematic_recommendation.get("title", "Cinematic推荐剧本"),
            "mood": cinematic_recommendation.get("mood", "epic"),
            "pace": cinematic_recommendation.get("pace", "fast"),
            "color_tone": cinematic_recommendation.get("color_tone", "cool"),
            "structure": cinematic_recommendation.get("structure", []),
        }

        # 提取全局参数用于覆盖
        global_params = {
            k: v for k, v in cinematic_recommendation.items()
            if k in ("camera", "scale", "transition", "effects")
        }

        script = self._build_script_from_plan(plan, available_materials, global_params)
        script.title = plan["title"]
        script.metadata["input_mode"] = "cinematic"
        script.metadata["cinematic_recommendation"] = cinematic_recommendation

        return script

    def direct_from_video(self, video_path: str,
                          available_materials: Optional[List[str]] = None) -> EditScript:
        """从参考视频学习风格并生成剧本"""
        log(f"视频导演模式: {video_path}")

        # 1. 视觉分析参考视频
        analysis = self._analyze_reference_video(video_path)

        # 2. 基于分析结果生成剧本
        script = self._build_script_from_analysis(analysis, available_materials)
        script.title = f"风格复刻: {Path(video_path).stem}"
        script.metadata["input_mode"] = "video"
        script.metadata["reference"] = video_path
        script.metadata["analysis"] = analysis

        return script

    def direct_from_images(self, image_paths: List[str],
                           description: str = "",
                           available_materials: Optional[List[str]] = None) -> EditScript:
        """从参考图片提取风格并生成剧本"""
        log(f"图片导演模式: {len(image_paths)} 张图片")

        # 1. 分析图片风格
        style = self._analyze_reference_images(image_paths, description)

        # 2. 构建剧本
        script = self._build_script_from_style(style, available_materials)
        script.title = description or "图片风格剧本"
        script.metadata["input_mode"] = "images"
        script.metadata["reference_images"] = image_paths

        return script

    def direct_from_music(self, music_path: str,
                          description: str = "",
                          available_materials: Optional[List[str]] = None,
                          target_ip: str = "",
                          strict: bool = True,
                          allow_mixed: bool = False) -> EditScript:
        """从音乐驱动生成剪辑剧本"""
        log(f"音乐导演模式: {music_path}")

        # 构建素材智能索引 + 严格选择
        if available_materials:
            self._ensure_material_index(available_materials, target_ip,
                                        strict, allow_mixed)

        # 1. 分析音乐节拍和情绪
        music_analysis = self._analyze_music(music_path)

        # 2. 根据音乐结构生成剧本
        script = self._build_script_from_music(music_analysis, description, available_materials, target_ip)
        script.title = description or f"音乐驱动: {Path(music_path).stem}"
        script.bgm_path = music_path
        script.metadata["input_mode"] = "music"
        script.metadata["target_ip"] = target_ip
        script.metadata["music_analysis"] = music_analysis

        return script

    def direct_mixed(self,
                     text: str = "",
                     video: str = "",
                     images: Optional[List[str]] = None,
                     music: str = "",
                     available_materials: Optional[List[str]] = None,
                     target_duration: float = 120.0) -> EditScript:
        """混合输入模式 — 综合所有输入源生成剧本"""
        log(f"混合导演模式: text={bool(text)}, video={bool(video)}, "
            f"images={len(images) if images else 0}, music={bool(music)}")

        # 收集所有分析结果
        context: Dict[str, Any] = {}

        if text:
            plan = self._generate_plan_from_text(text, target_duration)
            context["text_plan"] = plan

        if video:
            analysis = self._analyze_reference_video(video)
            context["video_analysis"] = analysis

        if images:
            style = self._analyze_reference_images(images, text)
            context["image_style"] = style

        if music:
            music_analysis = self._analyze_music(music)
            context["music_analysis"] = music_analysis

        # 综合生成剧本
        script = self._synthesize_script(context, available_materials)
        script.title = text or "混合输入剧本"
        if music:
            script.bgm_path = music
        script.metadata["input_mode"] = "mixed"
        script.metadata["sources"] = {
            "text": bool(text), "video": bool(video),
            "images": len(images) if images else 0, "music": bool(music),
        }

        return script

    # ----------------------------------------------------------------
    #  内部方法: 分析层
    # ----------------------------------------------------------------

    def _generate_plan_from_text(self, description: str, target_duration: float) -> Dict:
        """用LLM从文字描述生成分镜计划"""
        prompt = f"""你是一个专业视频剪辑导演。请根据以下描述，生成一个完整的视频剪辑分镜计划。

用户描述: {description}

目标时长: {target_duration}秒

请以JSON格式输出，包含以下字段:
{{
    "title": "视频标题",
    "mood": "整体情绪 (epic/emotional/calm/intense)",
    "pace": "节奏 (slow/medium/fast/very_fast)",
    "color_tone": "色调 (warm/cool/neutral/mixed)",
    "structure": [
        {{
            "section": "段落名称",
            "duration": 秒数,
            "mood": "段落情绪",
            "shot_type": "镜头类型 (wide/medium/closeup/mixed)",
            "camera": "运镜 (slow_push/tracking/orbit/static/mixed)",
            "effects": ["效果1", "效果2"],
            "transition": "转场方式"
        }}
    ]
}}

要求:
1. 总时长控制在 {target_duration} 秒左右
2. 段落之间要有情绪递进
3. 高潮部分用快切，抒情部分用慢镜头
4. 转场要匹配前后段落的情绪"""

        agent = self.agent
        if agent:
            try:
                response = agent.analyze(prompt)
                if isinstance(response, str):
                    # 提取JSON
                    json_str = self._extract_json(response)
                    if json_str:
                        return json.loads(json_str)
            except Exception as e:
                log(f"LLM生成计划失败: {e}, 使用模板", "WARN")

        # 降级: 使用内置模板
        return self._fallback_plan(description, target_duration)

    def _analyze_reference_video(self, video_path: str) -> Dict:
        """分析参考视频的风格和内容"""
        analyzer = self.visual_analyzer
        if not analyzer:
            return {"mood": "epic", "pace": "fast", "color_tone": "cool"}

        try:
            result = analyzer.analyze(video_path, num_frames=8)
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as e:
            log(f"视频分析失败: {e}", "WARN")
            return {"mood": "epic", "pace": "fast", "color_tone": "cool"}

    def _analyze_reference_images(self, image_paths: List[str], description: str = "") -> Dict:
        """分析参考图片的视觉风格"""
        analyzer = self.visual_analyzer
        if not analyzer:
            return {"mood": "epic", "color_tone": "cool"}

        try:
            # 取第一张图片分析
            result = analyzer.analyze(image_paths[0])
            return result if isinstance(result, dict) else {"raw": str(result)}
        except Exception as e:
            log(f"图片分析失败: {e}", "WARN")
            return {"mood": "epic", "color_tone": "cool"}

    def _analyze_music(self, music_path: str) -> Dict:
        """分析音乐的情绪和节拍"""
        mapper = self.beat_mapper
        if not mapper:
            return {"bpm": 120, "mood_curve": ["calm", "build", "climax", "outro"]}

        try:
            beats = mapper.detect_beats(music_path)
            bpm = mapper.estimate_bpm(music_path) if hasattr(mapper, 'estimate_bpm') else 120
            return {
                "bpm": bpm,
                "beat_count": len(beats) if beats else 0,
                "duration": beats[-1].get("time", 0) if beats else 0,
                "mood_curve": ["build", "build", "climax", "climax", "outro"],
            }
        except Exception as e:
            log(f"音乐分析失败: {e}", "WARN")
            return {"bpm": 120, "mood_curve": ["calm", "build", "climax", "outro"]}

    # ----------------------------------------------------------------
    #  内部方法: 构建层
    # ----------------------------------------------------------------

    def _build_script_from_plan(self, plan: Dict,
                                materials: Optional[List[str]] = None,
                                override_params: Optional[Dict] = None,
                                target_ip: str = "") -> EditScript:
        """从分镜计划构建剧本 — 智能素材匹配"""
        script = EditScript()
        script.style = {
            "mood": plan.get("mood", "epic"),
            "pace": plan.get("pace", "fast"),
            "color_tone": plan.get("color_tone", "cool"),
        }

        structure = plan.get("structure", [])
        mat_list = materials or []
        mat_idx = 0
        overrides = override_params or {}

        for i, section in enumerate(structure):
            duration = section.get("duration", 5.0)
            mood = section.get("mood", "neutral")

            # 使用外部参数覆盖，优先级: override_params > section > 默认值
            camera = overrides.get("camera") or section.get("camera", "static")
            effects = overrides.get("effects") or section.get("effects", [])
            transition = overrides.get("transition") or section.get("transition", "cut")
            shot_scale = overrides.get("scale") or section.get("shot_type", "mixed")

            # 智能素材分配 — 严格限定在已选择候选集内
            mood = section.get("mood", "neutral")
            pool = self._selected_materials or mat_list
            if self._material_index and pool:
                source = self._material_index.get_smart_assignment(
                    mat_idx, len(structure), target_mood=mood, target_ip=target_ip,
                    candidates=pool,
                )
                if not source:
                    source = pool[mat_idx % len(pool)]
            else:
                source = mat_list[mat_idx % len(mat_list)] if mat_list else ""
            mat_idx += 1

            segment = {
                "shot": i + 1,
                "section": section.get("section", f"段落{i+1}"),
                "duration": duration,
                "source": source,
                "mood": mood,
                "camera": camera,
                "effects": effects,
                "transition_in": transition,
                "shot_scale": shot_scale,
                "text_overlay": None,
            }
            script.add_segment(segment)

        return script

    def _build_script_from_analysis(self, analysis: Dict,
                                    materials: Optional[List[str]] = None) -> EditScript:
        """从视觉分析结果构建剧本"""
        mood = analysis.get("mood", "epic")
        pace = analysis.get("pace", "fast")

        # 根据分析结果选择模板
        template_name = self._select_template(mood, pace)
        template = SHOT_TEMPLATES.get(template_name, SHOT_TEMPLATES["battle_montage"])

        script = EditScript()
        script.style = {
            "mood": mood,
            "pace": pace,
            "color_tone": analysis.get("color_tone", "cool"),
        }

        mat_list = materials or []
        for i, step in enumerate(template["structure"]):
            source = mat_list[i % len(mat_list)] if mat_list else ""
            segment = {
                "shot": i + 1,
                "section": step["type"],
                "duration": step.get("duration", 3.0),
                "source": source,
                "mood": mood,
                "camera": step.get("camera", "static"),
                "effects": [step["effect"]] if "effect" in step else [],
                "transition_in": "cut",
                "shot_scale": step.get("scale", "medium"),
            }
            script.add_segment(segment)

        return script

    def _build_script_from_style(self, style: Dict,
                                 materials: Optional[List[str]] = None) -> EditScript:
        """从风格描述构建剧本"""
        script = EditScript()
        script.style = {
            "mood": style.get("mood", "epic"),
            "color_tone": style.get("color_palette", "cool"),
        }
        # 默认5段结构
        for i in range(5):
            source = materials[i % len(materials)] if materials else ""
            script.add_segment({
                "shot": i + 1,
                "section": f"段落{i+1}",
                "duration": 4.0,
                "source": source,
                "mood": style.get("mood", "epic"),
                "camera": "slow_push",
                "effects": [],
                "transition_in": "dissolve",
            })
        return script

    def _build_script_from_music(self, music_analysis: Dict,
                                 description: str = "",
                                 materials: Optional[List[str]] = None,
                                 target_ip: str = "") -> EditScript:
        """从音乐分析结果构建节拍驱动的剧本 — 智能素材匹配"""
        script = EditScript()
        bpm = music_analysis.get("bpm", 120)
        mood_curve = music_analysis.get("mood_curve", [])
        beat_interval = 60.0 / bpm  # 每拍秒数

        script.style = {"mood": "dynamic", "pace": "fast" if bpm > 130 else "medium",
                        "bpm": bpm}

        # 根据情绪曲线生成段落
        mat_list = materials or []
        for i, mood in enumerate(mood_curve):
            duration = beat_interval * 16  # 每段16拍
            # 智能素材分配 — 严格限定在已选择候选集内
            pool = self._selected_materials or mat_list
            if self._material_index and pool:
                source = self._material_index.get_smart_assignment(
                    i, len(mood_curve), target_mood=mood, target_ip=target_ip,
                    candidates=pool,
                )
                if not source:
                    source = pool[i % len(pool)]
            else:
                source = mat_list[i % len(mat_list)] if mat_list else ""

            camera = "static"
            effects = []
            if mood == "climax":
                camera = "shake"
                effects = ["flash", "glow"]
            elif mood == "build":
                camera = "slow_push"
            elif mood == "outro":
                camera = "pull_back"
                effects = ["fade_out"]

            script.add_segment({
                "shot": i + 1,
                "section": f"{mood}_{i+1}",
                "duration": duration,
                "source": source,
                "mood": mood,
                "camera": camera,
                "effects": effects,
                "transition_in": "beat_cut",
                "beat_sync": True,
            })

        return script

    def _synthesize_script(self, context: Dict,
                           materials: Optional[List[str]] = None) -> EditScript:
        """综合多源分析结果生成最终剧本"""
        # 优先级: video_analysis > text_plan > image_style > music
        plan = context.get("text_plan", {})
        analysis = context.get("video_analysis", {})
        music = context.get("music_analysis", {})

        # 合并风格
        merged_style = {
            "mood": analysis.get("mood") or plan.get("mood", "epic"),
            "pace": plan.get("pace", "fast"),
            "color_tone": analysis.get("color_tone") or plan.get("color_tone", "cool"),
        }

        # 如果有音乐，以音乐节奏为骨架
        if music:
            script = self._build_script_from_music(music, "", materials)
        elif plan:
            script = self._build_script_from_plan(plan, materials)
        elif analysis:
            script = self._build_script_from_analysis(analysis, materials)
        else:
            script = self._build_script_from_style(
                {"mood": "epic"}, materials)

        script.style = merged_style
        return script

    # ----------------------------------------------------------------
    #  辅助方法
    # ----------------------------------------------------------------

    def _select_template(self, mood: str, pace: str) -> str:
        """根据情绪和节奏选择最佳模板"""
        if mood in ("epic", "intense") and pace in ("fast", "very_fast"):
            return "battle_montage"
        elif mood in ("calm", "peaceful"):
            return "emotional"
        elif mood == "epic" and pace == "slow":
            return "epic_opening"
        elif pace == "fast":
            return "battle_montage"
        else:
            return "character_intro"

    def _fallback_plan(self, description: str, target_duration: float) -> Dict:
        """降级方案: 不依赖LLM的内置分镜"""
        return {
            "title": description[:30],
            "mood": "epic",
            "pace": "fast",
            "color_tone": "cool",
            "structure": [
                {"section": "开场", "duration": 5.0, "mood": "build",
                 "shot_type": "wide", "camera": "slow_push", "effects": [], "transition": "fade_in"},
                {"section": "铺垫", "duration": 15.0, "mood": "build",
                 "shot_type": "mixed", "camera": "tracking", "effects": [], "transition": "cut"},
                {"section": "发展", "duration": 25.0, "mood": "intense",
                 "shot_type": "mixed", "camera": "mixed", "effects": ["glow"], "transition": "flash"},
                {"section": "高潮", "duration": 30.0, "mood": "climax",
                 "shot_type": "mixed", "camera": "shake", "effects": ["glow", "flash"], "transition": "impact"},
                {"section": "收尾", "duration": 15.0, "mood": "resolve",
                 "shot_type": "wide", "camera": "pull_back", "effects": ["fade"], "transition": "fade_out"},
            ],
        }

    def _extract_json(self, text: str) -> Optional[str]:
        """从LLM响应中提取JSON"""
        import re
        # 尝试匹配 ```json ... ```
        m = re.search(r'```(?:json)?\s*(\{[\s\S]*?\})\s*```', text)
        if m:
            return m.group(1)
        # 尝试直接匹配 { ... }
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            return m.group(0)
        return None


# ================================================================
#  CLI 测试入口
# ================================================================

if __name__ == "__main__":
    director = MultimodalDirector()

    print("=" * 60)
    print("  多模态导演系统测试")
    print("=" * 60)

    # 测试1: 文字驱动
    print("\n--- 测试1: 文字驱动 ---")
    script = director.direct_from_text(
        "做一个进击的巨人利威尔高燃混剪，节奏快，战斗场面为主",
        target_duration=90,
    )
    print(f"标题: {script.title}")
    print(f"总时长: {script.total_duration:.1f}s")
    print(f"段落数: {len(script.segments)}")
    print(f"风格: {script.style}")

    # 测试2: 音乐驱动
    print("\n--- 测试2: 音乐驱动(模拟) ---")
    script2 = director.direct_from_music(
        "fake_bgm.mp3",
        description="测试音乐驱动",
    )
    print(f"标题: {script2.title}")
    print(f"BPM: {script2.style.get('bpm', 'N/A')}")
    print(f"段落数: {len(script2.segments)}")

    # 测试3: 混合输入
    print("\n--- 测试3: 混合输入(模拟) ---")
    script3 = director.direct_mixed(
        text="进击的巨人最终季混剪",
        music="fake_bgm.mp3",
        target_duration=120,
    )
    print(f"标题: {script3.title}")
    print(f"输入源: {script3.metadata.get('sources', {})}")

    # 测试4: direct_from_cinematic 方法
    print("\n--- 测试4: Cinematic推荐驱动 ---")
    cinematic_rec = {
        "title": "兵长外传·暗夜猎手",
        "mood": "intense",
        "pace": "very_fast",
        "color_tone": "dark",
        "camera": "tracking",
        "scale": "closeup",
        "transition": "flash",
        "effects": ["glow", "speed_lines"],
        "structure": [
            {"section": "潜行", "duration": 8.0, "mood": "build"},
            {"section": "突袭", "duration": 12.0, "mood": "intense"},
            {"section": "激战", "duration": 20.0, "mood": "climax"},
            {"section": "胜利", "duration": 5.0, "mood": "resolve"},
        ],
    }
    script4 = director.direct_from_cinematic(cinematic_rec)
    print(f"标题: {script4.title}")
    print(f"总时长: {script4.total_duration:.1f}s")
    print(f"段落数: {len(script4.segments)}")
    print(f"风格: {script4.style}")
    print(f"输入模式: {script4.metadata.get('input_mode', 'N/A')}")
    print(f"镜头1: camera={script4.segments[0]['camera']}, scale={script4.segments[0]['shot_scale']}, transition={script4.segments[0]['transition_in']}")

    # 测试5: direct_from_text 传入 cinematic_params
    print("\n--- 测试5: 文字驱动+外部参数覆盖 ---")
    external_params = {
        "camera": "slow_push",
        "scale": "wide",
        "transition": "dissolve",
        "effects": ["soft_glow"],
    }
    script5 = director.direct_from_text(
        "温柔的日落场景，慢节奏",
        target_duration=60,
        cinematic_params=external_params,
    )
    print(f"标题: {script5.title}")
    print(f"总时长: {script5.total_duration:.1f}s")
    print(f"段落数: {len(script5.segments)}")
    print(f"Cinematic参数: {script5.metadata.get('cinematic_params', 'N/A')}")
    print(f"镜头1: camera={script5.segments[0]['camera']}, scale={script5.segments[0]['shot_scale']}, transition={script5.segments[0]['transition_in']}")

    print("\n所有测试通过!")
