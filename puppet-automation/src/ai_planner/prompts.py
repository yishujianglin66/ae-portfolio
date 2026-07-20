"""AI Planner prompts - 提示词模板集合.

本模块提供两类内容：

1. **静态提示词模板常量**（``SYSTEM_PROMPT`` / ``INTENT_PARSING_PROMPT`` 等）
   供 ``planner.py`` 中的同步代码使用 ``.format()`` 填充后调用 LLM。
2. **异步资源上下文构建器**（``build_resource_context``）及对应的
   ``build_*_prompt_with_resources`` 异步包装函数：调用
   ``resource_index_service`` 拉取资源库实际可用资源，注入到提示词中，
   让 LLM 在生成视频制作方案时感知字体/LUT/特效/PSD/DaVinci/PR/AE 工程等
   实际资源，避免推荐资源库中不存在的资源。

资源索引服务位于 ``puppet_automation.src.services.resource_index_service``，
模块级单例 ``resource_index_service``。本模块仅生成提示词文本，不直接调用 LLM，
LLM 调用统一由 ``core/llm_gateway.py`` 网关负责。
"""
from __future__ import annotations

from typing import Any, Dict, List

from loguru import logger


# ============================================================
# 资源清单注入配置
# ============================================================

# 资源类别 → 中文标签映射（用于资源清单展示）
_RESOURCE_CATEGORY_LABELS: Dict[str, str] = {
    "fonts": "字体",
    "luts": "LUT 调色预设",
    "effects": "特效贴图",
    "psd": "PSD 素材",
    "audio": "音频素材",
    "video": "视频素材",
    "models": "3D 模型",
    "davinci": "DaVinci 预设",
    "premiere": "Premiere 预设",
    "projects": "AE 工程",
}

# 注入到提示词中的资源清单类别顺序（聚焦视频制作常用资源）
_RESOURCE_CONTEXT_CATEGORIES: tuple[str, ...] = (
    "fonts",
    "luts",
    "effects",
    "psd",
    "davinci",
    "premiere",
    "projects",
)


SYSTEM_PROMPT = """你是木偶视频自动化流水线的AI规划师。你的任务是将用户的自然语言需求解析为结构化的流水线配置。

## 可用的木偶风格（PuppetStyle）：
- wooden: 木质木偶，温暖棕色调，关节分明
- stop_motion: 定格动画风格，低帧率，黏土质感
- miniature: 微缩模型风格，浅景深，工作室打光
- clay: 黏土风格，次表面散射，柔和色彩
- shadow: 皮影风格，剪影效果，背光打亮
- paper: 纸艺剪纸风格，分层效果，扁平化打光
- voxel: 体素风格，像素化方块感，有限调色板
- handle: 提线木偶风格，可见控制杆和线

## 四阶段流水线（PipelinePhases）：
- phase1_preprocess: 视频预处理（场景检测、人脸/姿态分析、音频分析）
- phase2_keying: 自动抠像（rembg + Silhouette roto）
- phase3_stylize: 风格化（木偶风格转换 + 3D舞台）
- phase4_render: 最终渲染输出（合成 + 调色 + 编码）

## 质量预设（quality_preset）：
- low: 快速预览，720p, 24fps
- medium: 平衡质量，1080p, 30fps
- high: 高质量，1080p, 30fps, Topaz增强
- ultra: 最高质量，4K, 60fps

请根据用户需求输出JSON格式的流水线配置。"""


INTENT_PARSING_PROMPT = """
请分析以下用户需求，提取关键信息并生成流水线配置。

用户需求: "{user_query}"

视频文件路径: "{video_path}"

## 请输出JSON格式，包含以下字段：
```json
{{
  "style": "选择的木偶风格（从可用风格中选一个）",
  "target_resolution": [宽度, 高度],
  "target_fps": 帧率,
  "enable_face_puppet": 是否启用人脸木偶化（布尔值）,
  "enable_body_puppet": 是否启用身体木偶化（布尔值）,
  "enable_3d_stage": 是否使用3D舞台（布尔值）,
  "enable_audio": 是否保留并处理音频（布尔值）,
  "quality_preset": "质量预设（low/medium/high/ultra）",
  "phases": ["要执行的阶段列表"],
  "style_reasoning": "选择此风格的简短理由（一句话）",
  "estimated_duration_minutes": 预计处理时长（分钟，整数估计）
}}
```

只输出JSON，不要有其他文字。
"""


STYLE_RECOMMENDATION_PROMPT = """
你是木偶风格推荐专家。根据以下视频分析结果和用户偏好，推荐最合适的木偶风格。

## 视频分析结果：
- 视频时长: {duration}秒
- 分辨率: {width}x{height}
- 场景数量: {scene_count}
- 人脸数量: {face_count}
- 主要内容类型: {content_type}
- 运动强度: {motion_level}

## 用户偏好：
{user_preferences}

## 可用风格及适用场景：
1. wooden（木质木偶）：经典童话、儿童故事、复古感
2. stop_motion（定格动画）：创意短片、艺术表达、实验性内容
3. miniature（微缩模型）：城市景观、旅行vlog、美食节目
4. clay（黏土风格）：儿童教育、可爱风格、轻松搞笑
5. shadow（皮影风格）：传统故事、神话传说、剪影艺术
6. paper（纸艺剪纸）：清新文艺、手绘感、节日主题
7. voxel（体素风格）：游戏风格、科技感、复古像素
8. handle（提线木偶）：舞台剧感、经典戏剧、复古马戏

## 请按JSON格式输出推荐结果：
```json
{{
  "primary_style": "首选风格",
  "alternatives": ["备选风格1", "备选风格2"],
  "confidence": 0.0-1.0的置信度,
  "reasoning": "推荐理由（2-3句话）",
  "style_tips": {{
    "建议的参数调整": "说明"
  }}
}}
```

只输出JSON。
"""


PARAM_OPTIMIZATION_PROMPT = """
你是视频处理参数优化专家。根据视频特征自动调整流水线参数以获得最佳效果。

## 视频特征：
- 时长: {duration}秒
- 分辨率: {width}x{height}
- 帧率: {fps}
- 码率: {bitrate} bps
- 场景数量: {scene_count}
- 运动强度: {motion_level}（low/medium/high）
- 人脸数量: {face_count}
- 有人物: {has_people}

## 当前配置：
- 风格: {style}
- 质量预设: {quality_preset}

## 请输出优化后的参数（JSON格式）：
```json
{{
  "recommended_resolution": [宽, 高],
  "recommended_fps": 帧率,
  "recommended_quality": "质量预设",
  "enable_topaz": 是否启用Topaz增强（布尔值）,
  "enable_silhouette_roto": 是否启用Silhouette精细抠像（布尔值）,
  "enable_3d_stage": 是否启用3D舞台（布尔值）,
  "enable_color_grade": 是否启用DaVinci调色（布尔值）,
  "estimated_processing_time_minutes": 预计处理时间（分钟）,
  "optimization_notes": "优化说明（几句话）"
}}
```

只输出JSON。
"""


PIPELINE_EXPLANATION_PROMPT = """
用户发起了一个木偶视频流水线任务，请用通俗易懂的语言解释这个任务将如何执行。

## 任务配置：
{job_config}

## 请输出：
1. 一个简短的执行摘要（2-3句话）
2. 四个阶段分别会做什么
3. 预计耗时和最终产出

用友好、专业的口吻，不超过300字。
"""


# ============================================================
# 资源清单构建器（异步，调用 resource_index_service）
# ============================================================

async def build_resource_context(limit_per_category: int = 30) -> str:
    """构建资源库可用资源清单的文本块（供注入到 LLM 提示词中）。

    调用 ``resource_index_service`` 拉取各类资源的前 ``limit_per_category`` 个名称，
    拼接为结构化 Markdown 文本，包含：

    1. 顶部索引摘要（各类别资源数量统计）
    2. 各类别资源名称列表（前 N 个）

    任何异常都会被捕获并降级返回简短说明，保证不阻塞主流程。

    Args:
        limit_per_category: 每个类别返回的资源数量上限，默认 30

    Returns:
        结构化的资源清单文本块；若资源服务不可用则返回降级说明
    """
    try:
        from ..services.resource_index_service import resource_index_service
    except ImportError as exc:
        logger.debug(f"resource_index_service 不可用，资源清单注入跳过: {exc}")
        return "（资源索引服务未就绪，无法提供可用资源清单）"

    # 触发索引初始化（若未初始化）。refresh_index() 是公开方法，
    # 内部会调用 _build_index_internal() 并设置 _initialized 标志。
    if not resource_index_service.is_initialized():
        try:
            await resource_index_service.refresh_index()
        except Exception as exc:  # noqa: BLE001 — 索引初始化失败不应阻塞主流程
            logger.warning(f"资源索引初始化失败，资源清单降级: {exc}")
            return f"（资源索引初始化失败: {exc}）"

    # 顶部摘要
    try:
        summary: Dict[str, int] = resource_index_service.get_index_summary()
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"获取资源索引摘要失败: {exc}")
        summary = {}

    lines: List[str] = ["## 资源库可用资源清单"]

    if summary:
        lines.append("")
        lines.append("### 索引统计")
        total = 0
        for category in _RESOURCE_CONTEXT_CATEGORIES:
            count = int(summary.get(category, 0))
            label = _RESOURCE_CATEGORY_LABELS.get(category, category)
            lines.append(f"- {label}: {count}")
            total += count
        lines.append(f"- **资源总数（含未列出类别）**: {sum(summary.values())}")
        lines.append("")

    # 各类别资源名称列表
    has_any_category = False
    for category in _RESOURCE_CONTEXT_CATEGORIES:
        label = _RESOURCE_CATEGORY_LABELS.get(category, category)
        try:
            entries: List[Dict[str, Any]] = await resource_index_service.list_resources_by_type(
                category, limit=limit_per_category, offset=0
            )
        except Exception as exc:  # noqa: BLE001 — 单类别失败不应影响其他类别
            logger.debug(f"列出 {category} 资源失败: {exc}")
            entries = []

        if not entries:
            continue
        has_any_category = True

        lines.append(f"### 可用{label}（前 {len(entries)} 个）")
        for entry in entries:
            name = entry.get("name") or entry.get("file_path") or "未命名"
            ext = entry.get("extension") or ""
            if ext:
                lines.append(f"- {name}{ext}")
            else:
                lines.append(f"- {name}")
        lines.append("")

    if not has_any_category:
        return "（资源库当前为空或索引未就绪）"

    return "\n".join(lines)


# ============================================================
# 异步包装版本：在原提示词基础上注入资源清单
# ============================================================
#
# 设计原则：不破坏现有同步接口（``INTENT_PARSING_PROMPT.format()`` 等仍可用），
# 新增 ``build_*_prompt_with_resources`` 异步函数供 planner 或上层按需调用。
# 资源清单作为附加段落注入到原提示词尾部，并追加一段使用指引。
# ============================================================

_RESOURCE_USAGE_HINT = (
    "请在生成方案时优先使用上述可用资源；若需使用未列出的资源，"
    "请明确标注为「需用户准备」并给出建议名称或替代品。"
)


async def build_intent_parsing_prompt_with_resources(
    user_query: str,
    video_path: str,
    limit_per_category: int = 30,
) -> str:
    """构建意图解析提示词（带资源清单注入）。

    在 ``INTENT_PARSING_PROMPT`` 基础上追加可用资源清单，
    让 LLM 在生成流水线配置时感知资源库实际可用资源。

    Args:
        user_query: 用户的自然语言需求
        video_path: 视频文件路径
        limit_per_category: 每个资源类别注入的最大数量，默认 30

    Returns:
        注入了资源清单的完整提示词
    """
    base_prompt = INTENT_PARSING_PROMPT.format(
        user_query=user_query,
        video_path=video_path,
    )
    resource_block = await build_resource_context(limit_per_category=limit_per_category)
    return f"{base_prompt}\n\n{resource_block}\n\n{_RESOURCE_USAGE_HINT}"


async def build_style_recommendation_prompt_with_resources(
    duration: int | float,
    width: int,
    height: int,
    scene_count: int,
    face_count: int,
    content_type: str,
    motion_level: str,
    user_preferences: str,
    limit_per_category: int = 30,
) -> str:
    """构建风格推荐提示词（带资源清单注入）。

    在 ``STYLE_RECOMMENDATION_PROMPT`` 基础上追加可用资源清单。

    Args:
        duration: 视频时长（秒）
        width: 视频宽度
        height: 视频高度
        scene_count: 场景数量
        face_count: 人脸数量
        content_type: 内容类型
        motion_level: 运动强度（low/medium/high）
        user_preferences: 用户偏好描述
        limit_per_category: 每个资源类别注入的最大数量，默认 30

    Returns:
        注入了资源清单的完整提示词
    """
    base_prompt = STYLE_RECOMMENDATION_PROMPT.format(
        duration=duration,
        width=width,
        height=height,
        scene_count=scene_count,
        face_count=face_count,
        content_type=content_type,
        motion_level=motion_level,
        user_preferences=user_preferences or "无特殊偏好",
    )
    resource_block = await build_resource_context(limit_per_category=limit_per_category)
    style_hint = (
        "请基于上述可用资源推荐风格，并在 ``style_tips`` 中给出资源使用建议"
        "（如推荐字体、LUT、特效贴图等）。"
    )
    return f"{base_prompt}\n\n{resource_block}\n\n{style_hint}"


async def build_param_optimization_prompt_with_resources(
    duration: int | float,
    width: int,
    height: int,
    fps: float,
    bitrate: int,
    scene_count: int,
    motion_level: str,
    face_count: int,
    has_people: bool,
    style: str,
    quality_preset: str,
    limit_per_category: int = 30,
) -> str:
    """构建参数优化提示词（带资源清单注入）。

    Args:
        duration: 视频时长（秒）
        width: 视频宽度
        height: 视频高度
        fps: 帧率
        bitrate: 码率（bps）
        scene_count: 场景数量
        motion_level: 运动强度（low/medium/high）
        face_count: 人脸数量
        has_people: 是否有人物
        style: 目标风格
        quality_preset: 质量预设（low/medium/high/ultra）
        limit_per_category: 每个资源类别注入的最大数量，默认 30

    Returns:
        注入了资源清单的完整提示词
    """
    base_prompt = PARAM_OPTIMIZATION_PROMPT.format(
        duration=duration,
        width=width,
        height=height,
        fps=fps,
        bitrate=bitrate,
        scene_count=scene_count,
        motion_level=motion_level,
        face_count=face_count,
        has_people=has_people,
        style=style,
        quality_preset=quality_preset,
    )
    resource_block = await build_resource_context(limit_per_category=limit_per_category)
    opt_hint = (
        "请在 ``optimization_notes`` 中说明如何使用上述可用资源以达到最佳效果"
        "（如启用哪些 LUT、特效贴图、DaVinci 预设等）。"
    )
    return f"{base_prompt}\n\n{resource_block}\n\n{opt_hint}"


async def build_pipeline_explanation_prompt_with_resources(
    job_config: str,
    limit_per_category: int = 30,
) -> str:
    """构建流水线解释提示词（带资源清单注入）。

    Args:
        job_config: 任务配置 JSON 字符串
        limit_per_category: 每个资源类别注入的最大数量，默认 30

    Returns:
        注入了资源清单的完整提示词
    """
    base_prompt = PIPELINE_EXPLANATION_PROMPT.format(job_config=job_config)
    resource_block = await build_resource_context(limit_per_category=limit_per_category)
    explain_hint = "请在解释中提及将使用哪些可用资源（字体/LUT/特效/预设等）。"
    return f"{base_prompt}\n\n{resource_block}\n\n{explain_hint}"


__all__ = [
    # 静态提示词常量
    "SYSTEM_PROMPT",
    "INTENT_PARSING_PROMPT",
    "STYLE_RECOMMENDATION_PROMPT",
    "PARAM_OPTIMIZATION_PROMPT",
    "PIPELINE_EXPLANATION_PROMPT",
    # 资源清单构建器
    "build_resource_context",
    # 异步包装版本（带资源注入）
    "build_intent_parsing_prompt_with_resources",
    "build_style_recommendation_prompt_with_resources",
    "build_param_optimization_prompt_with_resources",
    "build_pipeline_explanation_prompt_with_resources",
]
