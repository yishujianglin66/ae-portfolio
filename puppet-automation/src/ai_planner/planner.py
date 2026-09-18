"""AI Planner - 智能规划层。

将自然语言需求转换为结构化的流水线配置，包括：
- 需求解析 (IntentParser)
- 风格推荐 (StyleRecommender)
- 参数调优 (ParamOptimizer)
- 规划器主类 (AIPlanner)

LLM 调用规范：
- 所有 LLM 调用必须通过 ``core/llm_gateway.py`` 统一网关
- 业务代码禁止直连 Provider HTTP API（已移除 ``providers/`` 直连实现）
- 网关不可用时自动降级到规则匹配回退
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from loguru import logger

from ..config import settings
from ..models.pipeline import (
    PipelineJob,
    PipelinePhase,
    PuppetStyle,
    VideoMetadata,
)
from .prompts import (
    INTENT_PARSING_PROMPT,
    PARAM_OPTIMIZATION_PROMPT,
    PIPELINE_EXPLANATION_PROMPT,
    STYLE_RECOMMENDATION_PROMPT,
    SYSTEM_PROMPT,
    # 资源清单注入版本（异步，调用 resource_index_service）
    build_intent_parsing_prompt_with_resources,
    build_param_optimization_prompt_with_resources,
    build_pipeline_explanation_prompt_with_resources,
    build_style_recommendation_prompt_with_resources,
)

# ============================================================
# Data Models
# ============================================================

@dataclass
class StyleRecommendation:
    """风格推荐结果。"""
    primary_style: PuppetStyle
    alternatives: list[PuppetStyle]
    confidence: float
    reasoning: str
    style_tips: dict[str, Any]


@dataclass
class OptimizedParams:
    """优化后的参数配置。"""
    recommended_resolution: tuple[int, int]
    recommended_fps: float
    recommended_quality: str
    enable_topaz: bool
    enable_silhouette_roto: bool
    enable_3d_stage: bool
    enable_color_grade: bool
    estimated_processing_time_minutes: int
    optimization_notes: str


@dataclass
class PlanningResult:
    """AI规划结果。"""
    job: PipelineJob
    style_recommendation: StyleRecommendation | None = None
    optimized_params: OptimizedParams | None = None
    explanation: str = ""
    reasoning: str = ""


# ============================================================
# LLM Helper (统一通过 core/llm_gateway.py 网关)
# ============================================================

def _get_llm():
    """获取统一 LLM 网关实例，未配置时返回 None 以触发规则匹配回退。

    Returns:
        ``core.llm_gateway.LLMGateway`` 实例（已从 settings 配置）或 ``None``
    """
    try:
        from core.llm_gateway import llm_gateway
    except ImportError:
        logger.debug("core.llm_gateway 不可用，AI Planner 将使用规则匹配回退")
        return None

    # 若网关未配置，尝试从 settings 注入配置
    if not llm_gateway.is_available():
        try:
            cfg = settings.get_llm_gateway_config()
            if cfg.base_url and cfg.api_key:
                llm_gateway.configure(cfg)
        except Exception as exc:  # noqa: BLE001 — 配置注入失败不应阻断流程
            logger.debug(f"LLM 网关配置注入失败: {exc}")

    return llm_gateway if llm_gateway.is_available() else None


def _extract_json(text: str) -> dict[str, Any]:
    """从LLM响应中提取JSON。"""
    try:
        # Try direct parse
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in markdown code block
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find first { and last }
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass

    logger.warning(f"Failed to extract JSON from: {text[:200]}")
    return {}


# ============================================================
# Intent Parser
# ============================================================

class IntentParser:
    """自然语言需求解析器。

    将用户的自然语言需求解析为结构化的PipelineJob配置。
    优先使用LLM，无LLM时使用规则匹配回退。
    """

    def __init__(self) -> None:
        self.llm = _get_llm()
        self._style_keywords = self._build_style_keywords()

    def _build_style_keywords(self) -> dict[PuppetStyle, list[str]]:
        """构建风格关键词映射（用于无LLM时的规则匹配）。"""
        return {
            PuppetStyle.WOODEN: ["木头", "木质", "木偶", "木制", "wooden", "wood", "marionette"],
            PuppetStyle.STOP_MOTION: ["定格", "逐帧", "stop motion", "stop-motion", "粘土动画"],
            PuppetStyle.MINIATURE: ["微缩", "模型", "小人国", "miniature", "tilt-shift", "移轴"],
            PuppetStyle.CLAY: ["黏土", "粘土", "橡皮泥", "clay", "claymation"],
            PuppetStyle.SHADOW: ["皮影", "影子", "剪影", "shadow", "silhouette"],
            PuppetStyle.PAPER: ["纸艺", "剪纸", "纸剪", "paper", "paper cut", "origami"],
            PuppetStyle.VOXEL: ["体素", "方块", "像素", "voxel", "minecraft", "mc"],
            PuppetStyle.HANDLE: ["提线木偶", "提线", "操纵杆", "线控", "handle", "strings", "marionette strings", "marionette"],
        }

    async def parse(self, user_query: str, video_path: str = "") -> dict[str, Any]:
        """解析用户需求。

        Args:
            user_query: 用户的自然语言需求
            video_path: 视频文件路径

        Returns:
            解析后的配置字典
        """
        if self.llm:
            return await self._parse_with_llm(user_query, video_path)
        else:
            return self._parse_rule_based(user_query, video_path)

    async def _parse_with_llm(self, user_query: str, video_path: str) -> dict[str, Any]:
        """使用LLM解析需求。"""
        from core.llm_gateway import TaskType

        # 注入资源清单；若资源索引服务不可用则降级返回简短说明，
        # 仍继续调用 LLM（不因资源清单失败而放弃整个 LLM 调用）。
        try:
            prompt = await build_intent_parsing_prompt_with_resources(
                user_query=user_query,
                video_path=video_path,
            )
        except Exception as exc:  # noqa: BLE001 — 资源清单构建失败不应阻塞 LLM 调用
            logger.warning(f"[AI Planner] 意图解析资源清单注入失败，降级使用静态提示词: {exc}")
            prompt = INTENT_PARSING_PROMPT.format(
                user_query=user_query,
                video_path=video_path,
            )
        response = await self.llm.chat_with_routing(
            message=prompt,
            task_type=TaskType.INTENT_CLASSIFICATION,
            system_prompt=SYSTEM_PROMPT,
        )
        if not response.success:
            logger.warning(f"LLM 网关调用失败，回退规则匹配: {response.error}")
            return self._parse_rule_based(user_query, video_path)

        result = _extract_json(response.content)

        # Validate and sanitize
        return self._sanitize_parsed_result(result, user_query)

    def _parse_rule_based(self, user_query: str, video_path: str) -> dict[str, Any]:
        """基于规则的解析回退。"""
        query_lower = user_query.lower()

        # Detect style
        detected_style = PuppetStyle.WOODEN
        max_score = 0
        for style, keywords in self._style_keywords.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            if score > max_score:
                max_score = score
                detected_style = style

        # Detect quality
        quality = "medium"
        if any(w in query_lower for w in ["高清", "4k", "最高", "极致", "high quality", "4K"]):
            quality = "high"
        elif any(w in query_lower for w in ["快速", "预览", "快速", "preview", "fast"]):
            quality = "low"

        # Detect 3D stage
        enable_3d = any(w in query_lower for w in ["3d", "三维", "立体", "舞台", "3D舞台"])

        # Detect phases
        phases = [p.value for p in PipelinePhase]
        if "只抠像" in user_query or "only key" in query_lower:
            phases = [PipelinePhase.PHASE1_PREPROCESS.value, PipelinePhase.PHASE2_KEYING.value]

        return {
            "style": detected_style.value,
            "target_resolution": [1920, 1080],
            "target_fps": 30.0,
            "enable_face_puppet": True,
            "enable_body_puppet": True,
            "enable_3d_stage": enable_3d,
            "enable_audio": True,
            "quality_preset": quality,
            "phases": phases,
            "style_reasoning": f"基于关键词匹配检测到{detected_style.value}风格",
            "estimated_duration_minutes": 5,
        }

    def _sanitize_parsed_result(self, result: dict[str, Any], query: str) -> dict[str, Any]:
        """清理和验证解析结果。"""
        # Start with rule-based defaults, then overlay LLM result on top
        default = self._parse_rule_based(query, "")
        merged = dict(default)
        merged.update(result)

        # Validate style
        style_val = merged.get("style", default["style"])
        try:
            PuppetStyle(style_val)
        except ValueError:
            merged["style"] = default["style"]

        # Validate resolution
        res = merged.get("target_resolution")
        if not isinstance(res, list) or len(res) != 2:
            merged["target_resolution"] = default["target_resolution"]

        # Validate fps
        fps = merged.get("target_fps")
        if not isinstance(fps, (int, float)):
            merged["target_fps"] = default["target_fps"]

        # Ensure boolean fields
        field_defaults = {
            "enable_face_puppet": True,
            "enable_body_puppet": True,
            "enable_3d_stage": False,
            "enable_audio": True,
        }
        for field, def_val in field_defaults.items():
            if not isinstance(merged.get(field), bool):
                merged[field] = def_val

        # Quality preset
        quality = merged.get("quality_preset")
        if quality not in ("low", "medium", "high", "ultra"):
            merged["quality_preset"] = default["quality_preset"]

        # Phases
        phases = merged.get("phases")
        if not isinstance(phases, list):
            merged["phases"] = default["phases"]

        # Set defaults for missing fields
        merged.setdefault("style_reasoning", default["style_reasoning"])
        merged.setdefault("estimated_duration_minutes", 5)

        return merged


# ============================================================
# Style Recommender
# ============================================================

class StyleRecommender:
    """风格推荐引擎。

    根据视频特征和用户偏好推荐最佳木偶风格。
    """

    def __init__(self) -> None:
        self.llm = _get_llm()

    async def recommend(
        self,
        video_metadata: VideoMetadata | None = None,
        scene_count: int = 0,
        face_count: int = 0,
        content_type: str = "general",
        motion_level: str = "medium",
        user_preferences: str = "",
    ) -> StyleRecommendation:
        """推荐风格。

        Args:
            video_metadata: 视频元数据
            scene_count: 场景数量
            face_count: 人脸数量
            content_type: 内容类型
            motion_level: 运动强度
            user_preferences: 用户偏好描述

        Returns:
            风格推荐结果
        """
        if self.llm:
            return await self._recommend_with_llm(
                video_metadata, scene_count, face_count,
                content_type, motion_level, user_preferences,
            )
        else:
            return self._recommend_rule_based(
                video_metadata, scene_count, face_count,
                content_type, motion_level, user_preferences,
            )

    async def _recommend_with_llm(
        self,
        video_metadata: VideoMetadata | None,
        scene_count: int,
        face_count: int,
        content_type: str,
        motion_level: str,
        user_preferences: str,
    ) -> StyleRecommendation:
        """使用LLM推荐风格。"""
        from core.llm_gateway import TaskType

        duration = video_metadata.duration if video_metadata else 0
        width = video_metadata.width if video_metadata else 1920
        height = video_metadata.height if video_metadata else 1080

        # 注入资源清单；若资源索引服务不可用则降级返回简短说明，
        # 仍继续调用 LLM（不因资源清单失败而放弃整个 LLM 调用）。
        try:
            prompt = await build_style_recommendation_prompt_with_resources(
                duration=duration,
                width=width,
                height=height,
                scene_count=scene_count,
                face_count=face_count,
                content_type=content_type,
                motion_level=motion_level,
                user_preferences=user_preferences or "无特殊偏好",
            )
        except Exception as exc:  # noqa: BLE001 — 资源清单构建失败不应阻塞 LLM 调用
            logger.warning(f"[AI Planner] 风格推荐资源清单注入失败，降级使用静态提示词: {exc}")
            prompt = STYLE_RECOMMENDATION_PROMPT.format(
                duration=duration,
                width=width,
                height=height,
                scene_count=scene_count,
                face_count=face_count,
                content_type=content_type,
                motion_level=motion_level,
                user_preferences=user_preferences or "无特殊偏好",
            )
        response = await self.llm.chat_with_routing(
            message=prompt,
            task_type=TaskType.EFFECT_PLANNING,
            system_prompt=SYSTEM_PROMPT,
        )
        if not response.success:
            logger.warning(f"LLM 网关调用失败，回退规则推荐: {response.error}")
            return self._recommend_rule_based(
                video_metadata, scene_count, face_count,
                content_type, motion_level, user_preferences,
            )
        result = _extract_json(response.content)

        try:
            primary = PuppetStyle(result.get("primary_style", "wooden"))
        except ValueError:
            primary = PuppetStyle.WOODEN

        alternatives = []
        for alt in result.get("alternatives", []):
            try:
                alternatives.append(PuppetStyle(alt))
            except ValueError:
                pass

        return StyleRecommendation(
            primary_style=primary,
            alternatives=alternatives[:2],
            confidence=float(result.get("confidence", 0.7)),
            reasoning=result.get("reasoning", "基于规则推荐"),
            style_tips=result.get("style_tips", {}),
        )

    def _recommend_rule_based(
        self,
        video_metadata: VideoMetadata | None,
        scene_count: int,
        face_count: int,
        content_type: str,
        motion_level: str,
        user_preferences: str,
    ) -> StyleRecommendation:
        """基于规则的风格推荐。"""
        content_lower = content_type.lower()
        prefs_lower = user_preferences.lower()

        # Content type based recommendations
        style_scores = {s: 0.5 for s in PuppetStyle}

        # Content type matching
        if any(k in content_lower or k in prefs_lower for k in ["童话", "儿童", "故事", "fairy", "kids", "story"]):
            style_scores[PuppetStyle.WOODEN] += 0.3
            style_scores[PuppetStyle.CLAY] += 0.2
        if any(k in content_lower or k in prefs_lower for k in ["传统", "神话", "皮影", "tradition", "myth", "shadow"]):
            style_scores[PuppetStyle.SHADOW] += 0.4
        if any(k in content_lower or k in prefs_lower for k in ["旅行", "vlog", "美食", "travel", "food"]):
            style_scores[PuppetStyle.MINIATURE] += 0.3
        if any(k in content_lower or k in prefs_lower for k in ["游戏", "科技", "像素", "game", "tech", "pixel"]):
            style_scores[PuppetStyle.VOXEL] += 0.35
        if any(k in content_lower or k in prefs_lower for k in ["艺术", "创意", "实验", "art", "creative"]):
            style_scores[PuppetStyle.STOP_MOTION] += 0.3
        if any(k in content_lower or k in prefs_lower for k in ["纸艺", "清新", "文艺", "paper", "fresh"]):
            style_scores[PuppetStyle.PAPER] += 0.3

        # Face and people-based adjustment
        if face_count > 0:
            style_scores[PuppetStyle.HANDLE] += 0.15
            style_scores[PuppetStyle.WOODEN] += 0.1

        # Get top 3
        sorted_styles = sorted(style_scores.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_styles[0][0]
        alternatives = [s[0] for s in sorted_styles[1:3]]

        return StyleRecommendation(
            primary_style=primary,
            alternatives=alternatives,
            confidence=round(min(0.6 + sorted_styles[0][1] / 2, 0.95), 2),
            reasoning=f"基于内容类型为{content_type}，综合评分最高的是{primary.value}风格",
            style_tips={"建议": "可根据实际效果调整风格参数"},
        )


# ============================================================
# Parameter Optimizer
# ============================================================

class ParamOptimizer:
    """智能参数调优器。

    根据视频特征自动调整流水线参数。
    """

    def __init__(self) -> None:
        self.llm = _get_llm()

    async def optimize(
        self,
        video_metadata: VideoMetadata | None,
        style: PuppetStyle,
        quality_preset: str = "medium",
        scene_count: int = 0,
        face_count: int = 0,
        motion_level: str = "medium",
        has_people: bool = True,
    ) -> OptimizedParams:
        """优化参数。

        Args:
            video_metadata: 视频元数据
            style: 目标风格
            quality_preset: 质量预设
            scene_count: 场景数量
            face_count: 人脸数量
            motion_level: 运动强度
            has_people: 是否有人物

        Returns:
            优化后的参数
        """
        if self.llm:
            return await self._optimize_with_llm(
                video_metadata, style, quality_preset,
                scene_count, face_count, motion_level, has_people,
            )
        else:
            return self._optimize_rule_based(
                video_metadata, style, quality_preset,
                scene_count, face_count, motion_level, has_people,
            )

    async def _optimize_with_llm(
        self,
        video_metadata: VideoMetadata | None,
        style: PuppetStyle,
        quality_preset: str,
        scene_count: int,
        face_count: int,
        motion_level: str,
        has_people: bool,
    ) -> OptimizedParams:
        """使用LLM优化参数。"""
        from core.llm_gateway import TaskType

        duration = video_metadata.duration if video_metadata else 60
        width = video_metadata.width if video_metadata else 1920
        height = video_metadata.height if video_metadata else 1080
        fps = video_metadata.fps if video_metadata else 30
        bitrate = video_metadata.bitrate if video_metadata else 5000000

        # 注入资源清单；若资源索引服务不可用则降级返回简短说明，
        # 仍继续调用 LLM（不因资源清单失败而放弃整个 LLM 调用）。
        try:
            prompt = await build_param_optimization_prompt_with_resources(
                duration=duration,
                width=width,
                height=height,
                fps=fps,
                bitrate=bitrate,
                scene_count=scene_count,
                motion_level=motion_level,
                face_count=face_count,
                has_people=has_people,
                style=style.value,
                quality_preset=quality_preset,
            )
        except Exception as exc:  # noqa: BLE001 — 资源清单构建失败不应阻塞 LLM 调用
            logger.warning(f"[AI Planner] 参数优化资源清单注入失败，降级使用静态提示词: {exc}")
            prompt = PARAM_OPTIMIZATION_PROMPT.format(
                duration=duration,
                width=width,
                height=height,
                fps=fps,
                bitrate=bitrate,
                scene_count=scene_count,
                motion_level=motion_level,
                face_count=face_count,
                has_people=has_people,
                style=style.value,
                quality_preset=quality_preset,
            )
        response = await self.llm.chat_with_routing(
            message=prompt,
            task_type=TaskType.PARAMETER_OPTIMIZATION,
            system_prompt=SYSTEM_PROMPT,
        )
        if not response.success:
            logger.warning(f"LLM 网关调用失败，回退规则优化: {response.error}")
            return self._optimize_rule_based(
                video_metadata, style, quality_preset,
                scene_count, face_count, motion_level, has_people,
            )
        result = _extract_json(response.content)

        res = result.get("recommended_resolution", [width, height])
        if not isinstance(res, list) or len(res) != 2:
            res = [width, height]

        try:
            rec_fps = float(result.get("recommended_fps", fps))
        except (ValueError, TypeError):
            rec_fps = fps

        return OptimizedParams(
            recommended_resolution=(int(res[0]), int(res[1])),
            recommended_fps=rec_fps,
            recommended_quality=result.get("recommended_quality", quality_preset),
            enable_topaz=bool(result.get("enable_topaz", quality_preset in ["high", "ultra"])),
            enable_silhouette_roto=bool(result.get("enable_silhouette_roto", has_people)),
            enable_3d_stage=bool(result.get("enable_3d_stage", False)),
            enable_color_grade=bool(result.get("enable_color_grade", True)),
            estimated_processing_time_minutes=int(result.get("estimated_processing_time_minutes", 10)),
            optimization_notes=result.get("optimization_notes", "基于视频特征的参数优化"),
        )

    def _optimize_rule_based(
        self,
        video_metadata: VideoMetadata | None,
        style: PuppetStyle,
        quality_preset: str,
        scene_count: int,
        face_count: int,
        motion_level: str,
        has_people: bool,
    ) -> OptimizedParams:
        """基于规则的参数优化。"""
        width = video_metadata.width if video_metadata else 1920
        height = video_metadata.height if video_metadata else 1080
        fps = video_metadata.fps if video_metadata else 30
        duration = video_metadata.duration if video_metadata else 60

        # Quality preset mapping
        quality_map = {
            "low": {"res": (1280, 720), "fps": 24, "topaz": False},
            "medium": {"res": (1920, 1080), "fps": 30, "topaz": False},
            "high": {"res": (1920, 1080), "fps": 30, "topaz": True},
            "ultra": {"res": (3840, 2160), "fps": 60, "topaz": True},
        }
        q = quality_map.get(quality_preset, quality_map["medium"])

        # Style-specific adjustments
        if style == PuppetStyle.VOXEL:
            # Voxel styles can be lower res (stylized)
            fps = min(fps, q["fps"])
        elif style == PuppetStyle.STOP_MOTION:
            fps = min(12, 24)

        # Motion-based adjustments
        if motion_level == "high":
            estimated_time = max(3, int(duration / 30))  # Rough estimate
        else:
            estimated_time = max(2, int(duration / 60))

        if quality_preset in ["high", "ultra"]:
            estimated_time *= 2

        return OptimizedParams(
            recommended_resolution=q["res"],
            recommended_fps=q["fps"],
            recommended_quality=quality_preset,
            enable_topaz=q["topaz"],
            enable_silhouette_roto=has_people and face_count > 0,
            enable_3d_stage=False,
            enable_color_grade=True,
            estimated_processing_time_minutes=estimated_time,
            optimization_notes=f"基于{quality_preset}质量预设和{style.value}风格的参数优化",
        )


# ============================================================
# AI Planner (Main Class)
# ============================================================

class AIPlanner:
    """AI规划器主类。

    协调整个规划流程：需求解析 → 风格推荐 → 参数调优 → 生成PipelineJob
    """

    def __init__(self) -> None:
        self.intent_parser = IntentParser()
        self.style_recommender = StyleRecommender()
        self.param_optimizer = ParamOptimizer()

    async def plan_from_query(
        self,
        user_query: str,
        video_path: str,
        video_metadata: VideoMetadata | None = None,
    ) -> PlanningResult:
        """从自然语言需求生成流水线规划。

        Args:
            user_query: 用户的自然语言需求
            video_path: 视频文件路径
            video_metadata: 视频元数据（可选）

        Returns:
            规划结果，包含PipelineJob配置和推荐信息
        """
        logger.info(f"[AI Planner] Planning for: {user_query[:50]}...")

        # Step 1: Parse intent
        parsed = await self.intent_parser.parse(user_query, video_path)
        style = PuppetStyle(parsed["style"])

        # Step 2: Style recommendation (if we have metadata)
        style_rec = None
        if video_metadata:
            try:
                style_rec = await self.style_recommender.recommend(
                    video_metadata=video_metadata,
                    scene_count=0,
                    face_count=0,
                    user_preferences=user_query,
                )
                # Override with recommended style if confidence is high
                if style_rec.confidence > 0.8 and style != style_rec.primary_style:
                    logger.info(f"[AI Planner] Style recommendation: {style} → {style_rec.primary_style}")
            except Exception as e:
                logger.warning(f"[AI Planner] Style recommendation failed: {e}")

        # Step 3: Parameter optimization
        opt_params = None
        try:
            opt_params = await self.param_optimizer.optimize(
                video_metadata=video_metadata,
                style=style,
                quality_preset=parsed["quality_preset"],
                has_people=parsed.get("enable_face_puppet", True),
            )
        except Exception as e:
            logger.warning(f"[AI Planner] Parameter optimization failed: {e}")

        # Step 4: Build PipelineJob
        import uuid
        job_id = f"job_{uuid.uuid4().hex[:8]}"

        resolution = opt_params.recommended_resolution if opt_params else tuple(parsed["target_resolution"])
        fps = opt_params.recommended_fps if opt_params else parsed["target_fps"]

        job = PipelineJob(
            job_id=job_id,
            input_video=video_path,
            style=style,
            target_resolution=resolution,
            target_fps=fps,
            enable_audio=parsed.get("enable_audio", True),
            enable_face_puppet=parsed.get("enable_face_puppet", True),
            enable_body_puppet=parsed.get("enable_body_puppet", True),
            enable_3d_stage=parsed.get("enable_3d_stage", False),
            quality_preset=opt_params.recommended_quality if opt_params else parsed["quality_preset"],
            phases=[PipelinePhase(p) for p in parsed.get("phases", [p.value for p in PipelinePhase])],
        )

        # Step 5: Generate explanation
        explanation = await self._generate_explanation(job, style_rec, opt_params)

        logger.info(f"[AI Planner] Complete: style={style.value}, quality={job.quality_preset}")

        return PlanningResult(
            job=job,
            style_recommendation=style_rec,
            optimized_params=opt_params,
            explanation=explanation,
            reasoning=parsed.get("style_reasoning", ""),
        )

    async def recommend_style(
        self,
        video_path: str,
        video_metadata: VideoMetadata | None = None,
        user_preferences: str = "",
    ) -> StyleRecommendation:
        """仅做风格推荐。"""
        return await self.style_recommender.recommend(
            video_metadata=video_metadata,
            user_preferences=user_preferences,
        )

    async def _generate_explanation(
        self,
        job: PipelineJob,
        style_rec: StyleRecommendation | None,
        opt_params: OptimizedParams | None,
    ) -> str:
        """生成流水线解释。"""
        if self.intent_parser.llm:
            try:
                from core.llm_gateway import TaskType

                job_config = json.dumps({
                    "style": job.style.value,
                    "resolution": f"{job.target_resolution[0]}x{job.target_resolution[1]}",
                    "fps": job.target_fps,
                    "quality": job.quality_preset,
                    "phases": [p.value for p in job.phases],
                }, indent=2, ensure_ascii=False)

                # 注入资源清单；若资源索引服务不可用则降级返回简短说明，
                # 仍继续调用 LLM（不因资源清单失败而放弃整个 LLM 调用）。
                try:
                    prompt = await build_pipeline_explanation_prompt_with_resources(
                        job_config=job_config,
                    )
                except Exception as exc:  # noqa: BLE001 — 资源清单构建失败不应阻塞 LLM 调用
                    logger.warning(f"[AI Planner] 流水线解释资源清单注入失败，降级使用静态提示词: {exc}")
                    prompt = PIPELINE_EXPLANATION_PROMPT.format(job_config=job_config)

                response = await self.intent_parser.llm.chat_with_routing(
                    message=prompt,
                    task_type=TaskType.GENERAL,
                    system_prompt=SYSTEM_PROMPT,
                )
                if response.success and response.content:
                    return response.content
                logger.warning(f"[AI Planner] 解释生成 LLM 调用失败: {response.error}")
            except Exception as e:
                logger.warning(f"[AI Planner] Explanation generation failed: {e}")

        # Fallback explanation
        phases_cn = {
            PipelinePhase.PHASE1_PREPROCESS: "视频预处理（分析画面、检测人脸和场景）",
            PipelinePhase.PHASE2_KEYING: "自动抠像（生成透明背景）",
            PipelinePhase.PHASE3_STYLIZE: f"{job.style.value}风格化转换",
            PipelinePhase.PHASE4_RENDER: "最终渲染输出（合成、调色、导出）",
        }
        phases_desc = "\n".join([f"  • {phases_cn.get(p, p.value)}" for p in job.phases])

        return (
            f"这是一个{job.style.value}风格的木偶视频制作任务。\n\n"
            f"执行阶段：\n{phases_desc}\n\n"
            f"输出规格：{job.target_resolution[0]}x{job.target_resolution[1]} / {job.target_fps}fps，{job.quality_preset}质量。"
        )
