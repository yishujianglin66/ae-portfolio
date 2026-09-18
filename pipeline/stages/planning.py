"""
pipeline/stages/planning.py - 规划阶段
========================================
生成剪辑剧本：调用 AI Director + 知识库 + Frontier System
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PlanningStage:
    """规划阶段：生成结构化剪辑剧本"""

    def __init__(self, config):
        self.config = config

    def run(self, previous_data: dict) -> dict:
        """执行规划阶段"""
        perceive = previous_data.get("perceive", {})
        analysis = previous_data.get("analyze", {})

        result = {
            "script": None,
            "style_params": {},
            "shot_list": [],
            "transition_plan": [],
            "effect_stack": [],
        }

        # 1. 获取知识库风格上下文
        if self.config.use_knowledge:
            kb_context = self._get_knowledge_context()
            result["style_params"] = kb_context

        # 2. 风格匹配（如果有参考）
        if self.config.style_reference:
            style = self._match_style(self.config.style_reference)
            result["style_params"].update(style)

        # 3. 生成剪辑剧本
        script = self._generate_script(perceive, analysis, result["style_params"])
        if script:
            result["script"] = script
            result["shot_list"] = script.get("shots", [])
            result["transition_plan"] = script.get("transitions", [])
            result["effect_stack"] = script.get("effects", [])

        return result

    def _get_knowledge_context(self) -> dict:
        """从知识库获取风格上下文"""
        try:
            from knowledge_base.kb_loader import KnowledgeBaseLoader
            loader = KnowledgeBaseLoader.get_instance()
            # 基于主题关键词检索相关知识
            context = loader.get_style_context_for_prompt(self.config.input_topic)
            return {"knowledge_context": context}
        except Exception as e:
            logger.debug(f"Knowledge context failed: {e}")
            return {}

    def _match_style(self, style_ref: str) -> dict:
        """风格匹配"""
        try:
            from knowledge_base.style_matcher import StyleMatcher
            matcher = StyleMatcher()
            return matcher.match(style_ref)
        except Exception as e:
            logger.debug(f"Style matching failed: {e}")
            return {}

    def _generate_script(self, perceive: dict, analysis: dict, style: dict) -> dict:
        """生成剪辑剧本"""
        # 构建素材分析列表 (供 AIDirector 使用)
        materials = perceive.get("videos", [])
        material_analyses = []
        for v in materials:
            material_analyses.append({
                "width": v.get("width", 1920),
                "height": v.get("height", 1080),
                "duration": v.get("duration_sec", 30),
                "mood": "dynamic",
                "avg_brightness": 0.5,
                "cut_rate": len(analysis.get("scenes", [])) / max(v.get("duration_sec", 1), 1),
            })

        # 确定风格
        style_name = "cinematic"
        kb_ctx = style.get("knowledge_context", "")
        if kb_ctx:
            style_name = "cinematic"  # KB 上下文已通过 style dict 传递

        # 尝试用 AI Director 生成
        try:
            from ai.ai_director import AIDirector
            director = AIDirector()
            prompt = self.config.input_topic or "Pipeline auto-generated video"
            return director.generate_script(
                user_prompt=prompt,
                material_analyses=material_analyses,
                style=style_name,
            )
        except Exception as e:
            logger.debug(f"AI Director failed: {e}")

        # 降级：用 Frontier System（标准化输出）
        try:
            from frontier_system import FrontierSystem
            fs = FrontierSystem()
            if self.config.reference_video:
                return fs.to_script(
                    f"复刻这个视频: {self.config.input_topic}",
                    video=self.config.reference_video,
                )
            elif self.config.input_topic:
                return fs.to_script(self.config.input_topic)
        except Exception as e:
            logger.debug(f"Frontier System failed: {e}")

        # 最终降级：基于分析数据生成基础剧本
        context = {
            "topic": self.config.input_topic,
            "materials": materials,
            "scenes": analysis.get("scenes", []),
            "beats": analysis.get("beats", []),
            "mood_curve": analysis.get("mood_curve", []),
            "style": style,
        }
        return self._fallback_script(context)

    def _fallback_script(self, context: dict) -> dict:
        """降级剧本生成（无LLM）— 基于场景检测+节拍分析+情绪曲线生成有意义的剧本"""
        scenes = context.get("scenes", [])
        beats = context.get("beats", [])
        materials = context.get("materials", [])
        mood_curve = context.get("mood_curve", [])

        shots = []

        # 策略 1: 如果有场景检测结果，按场景拆分
        if scenes:
            for i, scene in enumerate(scenes[:30]):
                # 基于情绪曲线决定转场类型
                t = scene.get("start_time", scene.get("start", 0))
                mood_at_t = self._get_mood_at_time(mood_curve, t)
                transition = self._mood_to_transition(mood_at_t)

                shots.append({
                    "index": i,
                    "type": "video",
                    "source": scene.get("source", ""),
                    "start": scene.get("start_time", scene.get("start", 0)),
                    "end": scene.get("end_time", scene.get("end", 0)),
                    "duration": scene.get("duration", 3),
                    "transition": transition,
                    "mood": mood_at_t,
                    "beat_synced": False,
                })

        # 策略 2: 如果没有场景但有素材视频，按节拍点拆分
        elif materials and beats:
            # 获取视频时长
            for mat_idx, mat in enumerate(materials[:5]):
                dur = mat.get("duration_sec", 10)
                source = mat.get("path", "")
                # 找到这个素材范围内的节拍点
                mat_beats = [b for b in beats
                             if b.get("time", 0) < dur]
                if mat_beats:
                    # 按节拍点切分
                    prev_t = 0
                    for b_idx, beat in enumerate(mat_beats[:20]):
                        beat_t = beat.get("time", 0)
                        seg_dur = beat_t - prev_t
                        if seg_dur >= 0.5:  # 至少 0.5 秒
                            mood_at_t = self._get_mood_at_time(mood_curve, beat_t)
                            shots.append({
                                "index": len(shots),
                                "type": "video",
                                "source": source,
                                "start": prev_t,
                                "end": beat_t,
                                "duration": round(seg_dur, 2),
                                "transition": "cut",  # 节拍点用硬切
                                "mood": mood_at_t,
                                "beat_synced": True,
                                "beat_time": beat_t,
                            })
                            prev_t = beat_t
                    # 最后一段
                    if dur - prev_t >= 0.5:
                        shots.append({
                            "index": len(shots),
                            "type": "video",
                            "source": source,
                            "start": prev_t,
                            "end": dur,
                            "duration": round(dur - prev_t, 2),
                            "transition": "dissolve",
                            "mood": "outro",
                            "beat_synced": False,
                        })
                else:
                    # 没有节拍点，整段使用
                    shots.append({
                        "index": len(shots),
                        "type": "video",
                        "source": source,
                        "start": 0,
                        "end": dur,
                        "duration": round(dur, 2),
                        "transition": "cut",
                        "mood": "neutral",
                        "beat_synced": False,
                    })

        # 策略 3: 没有任何分析数据，用素材整段
        elif materials:
            for mat_idx, mat in enumerate(materials[:5]):
                dur = mat.get("duration_sec", 10)
                shots.append({
                    "index": mat_idx,
                    "type": "video",
                    "source": mat.get("path", ""),
                    "start": 0,
                    "end": dur,
                    "duration": round(dur, 2),
                    "transition": "cut" if mat_idx < len(materials) - 1 else "dissolve",
                    "mood": "neutral",
                    "beat_synced": False,
                })

        # 构建转场计划
        transitions = []
        for i, shot in enumerate(shots[:-1]):
            transitions.append({
                "from": i,
                "to": i + 1,
                "type": shot.get("transition", "cut"),
                "start_time": shot.get("end", 0),
                "duration": 0.5 if shot.get("transition") != "cut" else 0,
            })

        # 构建效果建议 (基于情绪)
        effects = self._suggest_effects(mood_curve, beats)

        total_dur = sum(s["duration"] for s in shots)
        beat_count = sum(1 for s in shots if s.get("beat_synced"))

        logger.info(f"[Fallback Script] {len(shots)} shots, "
                    f"{beat_count} beat-synced, {total_dur:.1f}s total")

        return {
            "title": context.get("topic", "Untitled"),
            "total_duration": total_dur,
            "shots": shots,
            "transitions": transitions,
            "effects": effects,
            "generated_by": "fallback",
            "beat_synced_count": beat_count,
            "scene_count": len(scenes),
            "beat_count": len(beats),
        }

    def _get_mood_at_time(self, mood_curve: list, t: float) -> str:
        """从情绪曲线获取指定时间点的情绪"""
        if not mood_curve:
            return "neutral"
        # 找最接近的时间点
        closest = min(mood_curve, key=lambda p: abs(p.get("time", 0) - t))
        intensity = closest.get("intensity", 0.5)
        if intensity >= 0.7:
            return "high_energy"
        elif intensity >= 0.4:
            return "medium"
        else:
            return "low_energy"

    def _mood_to_transition(self, mood: str) -> str:
        """根据情绪选择转场类型"""
        return {
            "high_energy": "cut",
            "medium": "dissolve",
            "low_energy": "crossfade",
            "neutral": "cut",
            "intro": "fade_in",
            "outro": "fade_out",
        }.get(mood, "cut")

    def _suggest_effects(self, mood_curve: list, beats: list) -> list[dict]:
        """基于情绪和节拍建议效果"""
        effects = []
        if beats:
            bpm = beats[0].get("bpm", 120)
            if bpm >= 140:
                effects.append({
                    "name": "flash_on_be",
                    "description": "节拍闪光",
                    "apply_at": "beat_points",
                    "intensity": 0.3,
                })
            if bpm >= 120:
                effects.append({
                    "name": "zoom_pulse",
                    "description": "节拍缩放脉冲",
                    "apply_at": "downbeat",
                    "scale": 1.05,
                })
        # 如果有高能量段，加动态模糊
        high_energy_periods = [p for p in mood_curve if p.get("intensity", 0) >= 0.7]
        if high_energy_periods:
            effects.append({
                "name": "motion_blur",
                "description": "高能量段动态模糊",
                "apply_at": "high_energy_periods",
                "samples": 16,
            })
        return effects
