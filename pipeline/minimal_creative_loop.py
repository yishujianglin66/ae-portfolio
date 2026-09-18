"""AE Knowledge Vault — 最小端到端创意闭环（Minimal Creative Loop）。

====================================================================

为项目提供从自然语言描述到最终 mp4 视频的**最小可用端到端链路**：

```
用户文字描述
   ↓
[1] LLM 创意规划（生成 CreativePlan JSON）
   ↓
[2] AE 合成创建 + 图层/关键帧/效果
   ↓
[3] AE → DaVinci 链路（专业调色）
   ↓
[4] 渲染输出 mp4
```

为什么需要这个模块
==================

- 项目已有 UnifiedAEClient、AEToDavinciPipeline、LLMGateway 等组件，
  但**没有一条端到端链路**把它们串起来。
- 本模块是**最小可行版本**：聚焦 "10 秒文字动画" 这一典型场景，
  保证从输入到输出的完整链路可运行、可降级、可观测。

设计原则
========

1. **依赖注入**：所有外部依赖（AE、LLM、AE→DaVinci）都接受注入，
   便于单元测试。
2. **降级优先**：LLM 失败 → fallback 规划；AE 失败 → 警告但不中断；
   调色失败 → 仍输出未调色视频。
3. **进度可观测**：通过 ``progress_callback`` 实时上报阶段进度。
4. **同步优先**：默认提供同步 ``run()``，内部 ``asyncio.run`` 调度
   LLM 异步调用，便于脚本化使用。

示例
====

    >>> from pipeline.minimal_creative_loop import (
    ...     MinimalCreativeLoop, CreativeRequest,
    ...     ContentType, StylePreset,
    ... )
    >>> loop = MinimalCreativeLoop()
    >>> result = loop.run(CreativeRequest(
    ...     description="做一个 10 秒的电影感木偶风格文字动画，文字是'探索未来'",
    ...     content_type=ContentType.TEXT_ANIMATION,
    ...     style=StylePreset.CINEMATIC,
    ...     duration=10.0,
    ...     output_path="output/future_exploration.mp4",
    ... ))
    >>> print(result.success, result.output_path)
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

# 枚举从 prompts 子包导出（避免循环导入）
from pipeline.prompts.creative_planning import (
    STYLE_PRESET_MAP,
    ContentType,
    StylePreset,
    build_system_prompt,
    build_user_prompt,
)

# 仅类型检查时导入，避免运行时循环依赖
if TYPE_CHECKING:
    from ae.unified_ae_client import UnifiedAEClient
    from core.llm_gateway import LLMGateway, LLMResponse
    from integrations.ae_to_davinci_pipeline import AEToDavinciPipeline


logger = logging.getLogger(__name__)


# ============================================================================
# 数据模型
# ============================================================================

@dataclass
class CreativeRequest:
    """创意请求。

    Attributes:
        description: 用户输入的自然语言描述。
        content_type: 内容类型。
        style: 视觉风格。
        duration: 视频时长（秒）。
        output_path: 最终输出 mp4 路径。
        resolution: 分辨率 ``(width, height)``。
        frame_rate: 帧率。
        additional_params: 附加参数（透传到 AE/DaVinci）。
        progress_callback: 进度回调 ``(stage: str, percent: float) -> None``。
    """

    description: str
    content_type: ContentType = ContentType.TEXT_ANIMATION
    style: StylePreset = StylePreset.CINEMATIC
    duration: float = 10.0
    output_path: str = "output/auto_generated.mp4"
    resolution: tuple[int, int] = (1920, 1080)
    frame_rate: float = 30.0
    additional_params: dict[str, Any] = field(default_factory=dict)
    progress_callback: Callable[[str, float], None] | None = None


@dataclass
class CreativePlan:
    """创意规划（LLM 生成或 fallback 构造）。

    Attributes:
        comp_name: 合成名称。
        duration: 时长（秒）。
        fps: 帧率。
        resolution: 分辨率。
        background: 背景设计 dict。
        layers: 图层规格列表。
        keyframes: 关键帧规格列表。
        effects: 效果规格列表。
        text_content: 主要文字内容。
        text_style: 文字主样式。
        color_grading: 调色方案。
        estimated_complexity: 复杂度 0-1。
    """

    comp_name: str
    duration: float
    fps: float
    resolution: tuple[int, int]
    background: dict[str, Any]
    layers: list[dict[str, Any]] = field(default_factory=list)
    keyframes: list[dict[str, Any]] = field(default_factory=list)
    effects: list[dict[str, Any]] = field(default_factory=list)
    text_content: str | None = None
    text_style: dict[str, Any] | None = None
    color_grading: dict[str, Any] | None = None
    estimated_complexity: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """序列化为 dict（方便持久化、调试）。"""
        return {
            "comp_name": self.comp_name,
            "duration": self.duration,
            "fps": self.fps,
            "resolution": list(self.resolution),
            "background": dict(self.background),
            "layers": list(self.layers),
            "keyframes": list(self.keyframes),
            "effects": list(self.effects),
            "text_content": self.text_content,
            "text_style": dict(self.text_style) if self.text_style else None,
            "color_grading": dict(self.color_grading) if self.color_grading else None,
            "estimated_complexity": self.estimated_complexity,
        }


@dataclass
class CreativeResult:
    """创意执行结果。

    Attributes:
        success: 是否整体成功。
        output_path: 最终输出文件路径。
        plan: 使用的创意规划。
        execution_log: 执行步骤日志（每步一个 dict）。
        errors: 错误列表。
        warnings: 警告列表。
        metrics: 性能指标（阶段耗时）。
        total_duration_sec: 总耗时。
    """

    success: bool
    output_path: str | None = None
    plan: CreativePlan | None = None
    execution_log: list[dict[str, Any]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    total_duration_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output_path": self.output_path,
            "plan": self.plan.to_dict() if self.plan else None,
            "execution_log": list(self.execution_log),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "metrics": dict(self.metrics),
            "total_duration_sec": self.total_duration_sec,
        }


# ============================================================================
# 主类 MinimalCreativeLoop
# ============================================================================

class MinimalCreativeLoop:
    """最小端到端创意闭环。

    把"自然语言描述 → mp4 视频"的全流程串成一条可监控、可降级的链路：

    1. **LLM 规划**（0% - 20%）：调用 :class:`core.llm_gateway.LLMGateway`
       生成结构化 :class:`CreativePlan`；失败时使用 :meth:`_fallback_plan`。
    2. **AE 执行**（20% - 70%）：通过 :class:`ae.unified_ae_client.UnifiedAEClient`
       创建合成、图层、关键帧、效果。
    3. **专业调色**（70% - 90%）：通过 AE → DaVinci 链路
       （:class:`integrations.ae_to_davinci_pipeline.AEToDavinciPipeline`）
       套用调色预设。
    4. **渲染输出**（90% - 100%）：mp4 文件生成。

    Attributes:
        ae: UnifiedAEClient 实例（可注入）。
        ae_to_davinci: AE→DaVinci 链路实例（可注入）。
        llm: LLMGateway 实例（可注入）。
    """

    def __init__(
        self,
        ae_client: Any | None = None,
        ae_to_davinci: Any | None = None,
        llm_gateway: Any | None = None,
    ) -> None:
        """初始化最小创意闭环。

        所有依赖都可注入，方便测试。未注入时按需懒加载。
        """
        # 注入优先，懒加载兜底
        if ae_client is not None:
            self.ae = ae_client
        else:
            from ae.unified_ae_client import UnifiedAEClient
            self.ae = UnifiedAEClient()

        if ae_to_davinci is not None:
            self.ae_to_davinci = ae_to_davinci
        else:
            from integrations.ae_to_davinci_pipeline import AEToDavinciPipeline
            self.ae_to_davinci = AEToDavinciPipeline(ae_client=self.ae)

        if llm_gateway is not None:
            self.llm = llm_gateway
        else:
            from core.llm_gateway import LLMGateway
            self.llm = LLMGateway()

        # 图层名 → 索引缓存（一次合成内复用）
        self._layer_index_cache: dict[tuple[str, str], int] = {}

    # -----------------------------------------------------------------
    # 主入口
    # -----------------------------------------------------------------

    def run(self, request: CreativeRequest) -> CreativeResult:
        """执行端到端创意生成（同步入口）。

        Args:
            request: :class:`CreativeRequest` 创意请求。

        Returns:
            :class:`CreativeResult` 执行结果。
        """
        result = CreativeResult(success=False)
        start = time.time()

        # 清空缓存
        self._layer_index_cache.clear()

        try:
            # ---------- 阶段 1：LLM 规划（0% - 20%） ----------
            self._report(request, "分析需求", 0.0)
            plan = self._plan_with_llm(request, result)
            result.plan = plan
            result.execution_log.append({
                "stage": "planning",
                "comp_name": plan.comp_name,
                "complexity": plan.estimated_complexity,
            })
            self._report(request, "规划完成", 0.2)

            # ---------- 阶段 2：AE 创建（20% - 70%） ----------
            self._report(request, "AE 创建合成", 0.2)
            self._execute_in_ae(plan, request, result)
            self._report(request, "AE 创建完成", 0.7)

            # ---------- 阶段 3：调色（70% - 90%） ----------
            self._report(request, "专业调色", 0.7)
            self._apply_color_grading(plan, request, result)
            self._report(request, "调色完成", 0.9)

            # ---------- 阶段 4：渲染（90% - 100%） ----------
            self._report(request, "渲染输出", 0.9)
            self._finalize_output(plan, request, result)
            self._report(request, "完成", 1.0)

            result.success = True
            result.output_path = request.output_path

        except Exception as exc:  # noqa: BLE001
            logger.exception("MinimalCreativeLoop 执行失败: %s", exc)
            result.errors.append(f"{type(exc).__name__}: {exc}")
            result.execution_log.append({
                "stage": "fatal_error",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            })

        result.total_duration_sec = time.time() - start
        result.metrics["total_sec"] = result.total_duration_sec
        return result

    # -----------------------------------------------------------------
    # 便捷方法
    # -----------------------------------------------------------------

    def text_animation(
        self,
        text: str,
        style: str = "cinematic",
        duration: float = 10.0,
        output_path: str = "output/text_anim.mp4",
    ) -> CreativeResult:
        """生成文字动画（一键便捷方法）。"""
        return self.run(CreativeRequest(
            description=f"做一个{duration}秒的{style}风格文字动画，文字是'{text}'",
            content_type=ContentType.TEXT_ANIMATION,
            style=StylePreset(style),
            duration=duration,
            output_path=output_path,
        ))

    def motion_graphics(
        self,
        description: str,
        duration: float = 10.0,
        output_path: str = "output/mg.mp4",
        style: str = "minimal",
    ) -> CreativeResult:
        """生成动态图形。"""
        return self.run(CreativeRequest(
            description=f"做一个{duration}秒的{style}风格动态图形：{description}",
            content_type=ContentType.MOTION_GRAPHICS,
            style=StylePreset(style),
            duration=duration,
            output_path=output_path,
        ))

    def lyric_video(
        self,
        lyrics: str,
        style: str = "neon",
        duration: float = 10.0,
        output_path: str = "output/lyric.mp4",
    ) -> CreativeResult:
        """生成歌词视频。

        Args:
            lyrics: 歌词文本（多行用换行分隔）。
            style: 风格。
            duration: 时长。
            output_path: 输出路径。
        """
        return self.run(CreativeRequest(
            description=(
                f"做一个{duration}秒的{style}风格歌词视频，歌词如下：\n{lyrics}\n"
                "每句逐行高亮，节奏感强。"
            ),
            content_type=ContentType.LYRIC_VIDEO,
            style=StylePreset(style),
            duration=duration,
            output_path=output_path,
            additional_params={"lyrics": lyrics},
        ))

    def product_showcase(
        self,
        product_name: str,
        tagline: str,
        style: str = "minimal",
        duration: float = 10.0,
        output_path: str = "output/product.mp4",
    ) -> CreativeResult:
        """生成产品展示。"""
        return self.run(CreativeRequest(
            description=(
                f"做一个{duration}秒的{style}风格产品展示视频，"
                f"产品名：{product_name}，副标题：{tagline}。"
                "产品居中，光照精致，文字呼吸感缩放。"
            ),
            content_type=ContentType.PRODUCT_SHOWCASE,
            style=StylePreset(style),
            duration=duration,
            output_path=output_path,
        ))

    def transition(
        self,
        theme: str = "cinematic",
        duration: float = 2.0,
        output_path: str = "output/transition.mp4",
    ) -> CreativeResult:
        """生成转场效果。"""
        return self.run(CreativeRequest(
            description=f"做一个{duration}秒的{theme}风格转场，主题：{theme}",
            content_type=ContentType.TRANSITION_EFFECT,
            style=StylePreset(theme),
            duration=duration,
            output_path=output_path,
        ))

    # -----------------------------------------------------------------
    # 阶段 1：LLM 规划
    # -----------------------------------------------------------------

    def _plan_with_llm(
        self,
        request: CreativeRequest,
        result: CreativeResult,
    ) -> CreativePlan:
        """用 LLM 分析需求并生成创意规划。

        调用 LLMGateway.chat 异步接口，包装在 ``asyncio.run`` 中。
        失败时使用 :meth:`_fallback_plan` 兜底，保证链路不中断。
        """
        system_prompt = build_system_prompt(request.content_type, request.style)
        user_prompt = build_user_prompt(
            description=request.description,
            content_type=request.content_type,
            style=request.style,
            duration=request.duration,
            resolution=request.resolution,
            frame_rate=request.frame_rate,
            additional_context=request.additional_params or None,
        )

        t0 = time.time()
        try:
            # chat 是 async；同步入口包一层
            llm_response: LLMResponse = self._call_llm_sync(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            result.metrics["llm_sec"] = time.time() - t0

            if not llm_response or not getattr(llm_response, "success", False):
                err = getattr(llm_response, "error", "unknown") if llm_response else "no response"
                result.warnings.append(f"LLM 规划失败（{err}），使用 fallback 规划")
                return self._fallback_plan(request)

            content = getattr(llm_response, "content", "") or ""
            plan = self._parse_llm_plan(content, request, result)
            return plan

        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"LLM 规划异常: {exc}，使用 fallback 规划")
            return self._fallback_plan(request)

    def _call_llm_sync(self, system_prompt: str, user_prompt: str) -> Any:
        """同步调用 LLM 网关。

        优先使用 ``chat_with_routing`` 路由到合适的模型；如果当前线程
        已经在 event loop 中（例如 pytest-asyncio），则降级为 ``chat``。
        """
        from core.llm_gateway import TaskType
        try:
            # 优先尝试 chat_with_routing
            coro = self.llm.chat_with_routing(
                message=user_prompt,
                task_type=TaskType.EFFECT_PLANNING,
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=2048,
            )
            return self._run_async_safely(coro)
        except Exception as exc:  # noqa: BLE001
            logger.debug("chat_with_routing 失败，尝试 chat: %s", exc)
            coro = self.llm.chat(
                message=user_prompt,
                system_prompt=system_prompt,
                temperature=0.5,
                max_tokens=2048,
            )
            return self._run_async_safely(coro)

    def _run_async_safely(self, coro: Any) -> Any:
        """在同步上下文中安全运行 async 协程。

        如果当前线程已有 event loop（例如 pytest-asyncio），
        则使用 ``run_coroutine_threadsafe`` 或在 thread 中跑。
        否则使用 ``asyncio.run``。
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            # 没有运行中的 loop，直接 asyncio.run
            return asyncio.run(coro)

        # 已有 loop：在新线程中跑（避免 RuntimeError: cannot reuse）
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(asyncio.run, coro)
            return future.result(timeout=60)

    def _parse_llm_plan(
        self,
        llm_response: str,
        request: CreativeRequest,
        result: CreativeResult,
    ) -> CreativePlan:
        """解析 LLM 输出为 CreativePlan。

        兼容：
        - 纯 JSON 输出
        - Markdown code block 包裹的 JSON
        - 输出文字前后带解释
        """
        if not llm_response:
            result.warnings.append("LLM 返回为空，使用 fallback 规划")
            return self._fallback_plan(request)

        # 尝试提取 JSON 块
        json_str = self._extract_json(llm_response)
        if not json_str:
            result.warnings.append("LLM 输出中未找到 JSON，使用 fallback 规划")
            return self._fallback_plan(request)

        try:
            plan_dict = json.loads(json_str)
        except json.JSONDecodeError as exc:
            result.warnings.append(f"LLM JSON 解析失败（{exc}），使用 fallback 规划")
            return self._fallback_plan(request)

        # 构造 CreativePlan（健壮性 + 字段补全）
        try:
            comp_name = self._sanitize_comp_name(
                plan_dict.get("comp_name", f"Auto_{int(time.time())}")
            )
            resolution_raw = plan_dict.get("resolution", list(request.resolution))
            if not isinstance(resolution_raw, (list, tuple)) or len(resolution_raw) < 2:
                resolution_raw = list(request.resolution)

            return CreativePlan(
                comp_name=comp_name,
                duration=float(plan_dict.get("duration", request.duration)),
                fps=float(plan_dict.get("fps", request.frame_rate)),
                resolution=(int(resolution_raw[0]), int(resolution_raw[1])),
                background=self._normalize_background(
                    plan_dict.get("background"),
                    request,
                ),
                layers=list(plan_dict.get("layers", [])),
                keyframes=list(plan_dict.get("keyframes", [])),
                effects=list(plan_dict.get("effects", [])),
                text_content=plan_dict.get("text_content"),
                text_style=plan_dict.get("text_style"),
                color_grading=self._normalize_color_grading(
                    plan_dict.get("color_grading"),
                    request,
                ),
                estimated_complexity=float(plan_dict.get("estimated_complexity", 0.5)),
            )
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"规划字段不合法（{exc}），使用 fallback 规划")
            return self._fallback_plan(request)

    @staticmethod
    def _extract_json(text: str) -> str | None:
        """从 LLM 响应中提取 JSON 字符串。"""
        if not text:
            return None

        # 1) Markdown code block
        m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(1).strip()

        # 2) 找首个 { 到末尾最后一个 } 的子串
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last != -1 and last > first:
            candidate = text[first:last + 1].strip()
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                pass

        # 3) 整段尝试
        try:
            json.loads(text.strip())
            return text.strip()
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _sanitize_comp_name(name: str) -> str:
        """清理合成名（移除空格、特殊字符）。"""
        if not name:
            return f"Auto_{int(time.time())}"
        # 替换空格为下划线
        name = re.sub(r"\s+", "_", name)
        # 仅保留字母数字下划线
        name = re.sub(r"[^A-Za-z0-9_\-]", "", name)
        if not name:
            return f"Auto_{int(time.time())}"
        return name[:60]  # AE 合成名长度限制

    def _normalize_background(
        self,
        bg: dict[str, Any] | None,
        request: CreativeRequest,
    ) -> dict[str, Any]:
        """规范化背景字段。"""
        if not isinstance(bg, dict):
            return {"type": "solid", "color": [0.0, 0.0, 0.0]}

        bg_type = bg.get("type", "solid")
        if bg_type not in ("solid", "gradient"):
            bg_type = "solid"

        if bg_type == "solid":
            color = bg.get("color", [0.0, 0.0, 0.0])
            if not isinstance(color, (list, tuple)) or len(color) < 3:
                color = [0.0, 0.0, 0.0]
            return {
                "type": "solid",
                "color": [float(color[0]), float(color[1]), float(color[2])],
            }
        else:  # gradient
            grad = bg.get("gradient", {}) or {}
            frm = grad.get("from", [0.0, 0.0, 0.0])
            to = grad.get("to", [1.0, 1.0, 1.0])
            if not isinstance(frm, (list, tuple)) or len(frm) < 3:
                frm = [0.0, 0.0, 0.0]
            if not isinstance(to, (list, tuple)) or len(to) < 3:
                to = [1.0, 1.0, 1.0]
            return {
                "type": "gradient",
                "gradient": {
                    "from": [float(frm[0]), float(frm[1]), float(frm[2])],
                    "to": [float(to[0]), float(to[1]), float(to[2])],
                    "angle": float(grad.get("angle", 0.0)),
                },
            }

    def _normalize_color_grading(
        self,
        cg: dict[str, Any] | None,
        request: CreativeRequest,
    ) -> dict[str, Any] | None:
        """规范化调色字段，确保 preset_name 一定存在。"""
        if not isinstance(cg, dict):
            return {
                "preset_name": self._map_style_to_preset(request.style),
                "style_description": "由风格自动选择",
            }
        preset_name = cg.get("preset_name")
        if not preset_name:
            preset_name = self._map_style_to_preset(request.style)
        return {
            "preset_name": preset_name,
            "style_description": cg.get("style_description", ""),
        }

    # -----------------------------------------------------------------
    # Fallback 规划
    # -----------------------------------------------------------------

    def _fallback_plan(self, request: CreativeRequest) -> CreativePlan:
        """LLM 失败时的回退规划。

        基于请求参数按规则生成一个最小可用的文字动画规划，
        保证链路不中断、仍能输出视频。
        """
        # 默认文字
        text = request.description or "Hello"
        # 截短过长文字
        if len(text) > 30:
            text = text[:30] + "..."

        # 风格 → 背景色
        bg_color_map = {
            StylePreset.CARTOON: [0.95, 0.85, 0.50],
            StylePreset.CINEMATIC: [0.05, 0.05, 0.10],
            StylePreset.NEON: [0.05, 0.0, 0.10],
            StylePreset.VINTAGE: [0.20, 0.15, 0.10],
            StylePreset.MINIMAL: [0.95, 0.95, 0.95],
            StylePreset.ENERGETIC: [0.90, 0.30, 0.20],
            StylePreset.ROMANTIC: [1.0, 0.85, 0.90],
            StylePreset.DARK_MOOD: [0.05, 0.05, 0.08],
        }
        # 文字色：深色背景用白，浅色背景用黑
        bg_color = bg_color_map.get(request.style, [0.0, 0.0, 0.0])
        is_dark_bg = sum(bg_color) < 0.5
        text_color = [1.0, 1.0, 1.0] if is_dark_bg else [0.0, 0.0, 0.0]

        # 字体大小（基于分辨率）
        font_size = max(60.0, min(120.0, request.resolution[1] * 0.08))

        comp_name = self._sanitize_comp_name(
            f"Auto_{request.style.value}_{int(time.time()) % 100000}"
        )

        layers: list[dict[str, Any]] = [
            {
                "type": "text",
                "name": "MainText",
                "properties": {
                    "text": text,
                    "font_size": float(font_size),
                    "color": text_color,
                    "font_family": "Arial",
                    "position": [
                        request.resolution[0] / 2.0,
                        request.resolution[1] / 2.0,
                    ],
                },
            }
        ]

        # 关键帧：简单的淡入 + 缩放入场
        keyframes: list[dict[str, Any]] = [
            {
                "layer_name": "MainText",
                "property": "Opacity",
                "time": 0.0,
                "value": [0.0],
            },
            {
                "layer_name": "MainText",
                "property": "Opacity",
                "time": min(1.0, request.duration * 0.2),
                "value": [100.0],
            },
            {
                "layer_name": "MainText",
                "property": "Scale",
                "time": 0.0,
                "value": [80.0, 80.0],
            },
            {
                "layer_name": "MainText",
                "property": "Scale",
                "time": min(1.5, request.duration * 0.3),
                "value": [100.0, 100.0],
            },
        ]

        return CreativePlan(
            comp_name=comp_name,
            duration=request.duration,
            fps=request.frame_rate,
            resolution=request.resolution,
            background={"type": "solid", "color": bg_color},
            layers=layers,
            keyframes=keyframes,
            effects=[],
            text_content=text,
            text_style={
                "font_size": float(font_size),
                "color": text_color,
                "font_family": "Arial",
                "alignment": "center",
            },
            color_grading={
                "preset_name": self._map_style_to_preset(request.style),
                "style_description": f"Fallback plan for {request.style.value} style",
            },
            estimated_complexity=0.3,
        )

    # -----------------------------------------------------------------
    # 阶段 2：AE 执行
    # -----------------------------------------------------------------

    def _execute_in_ae(
        self,
        plan: CreativePlan,
        request: CreativeRequest,
        result: CreativeResult,
    ) -> None:
        """在 AE 中执行规划：创建合成 → 背景 → 图层 → 关键帧 → 效果。"""
        # 1. 创建合成
        t0 = time.time()
        comp_resp = self.ae.create_composition(
            name=plan.comp_name,
            width=plan.resolution[0],
            height=plan.resolution[1],
            fps=plan.fps,
            duration=plan.duration,
        )
        result.metrics["ae_create_comp_sec"] = time.time() - t0
        result.execution_log.append({
            "stage": "ae_create_comp",
            "comp_name": plan.comp_name,
            "response": comp_resp,
        })
        if not self._is_success(comp_resp):
            raise RuntimeError(f"AE 创建合成失败: {comp_resp.get('error', comp_resp)}")

        # 2. 创建背景
        self._create_background(plan, result)

        # 3. 创建图层
        for layer_spec in plan.layers:
            try:
                self._create_layer(plan.comp_name, layer_spec, result)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"创建图层失败（{layer_spec.get('name')}）: {exc}")

        # 4. 关键帧
        for kf_spec in plan.keyframes:
            try:
                self._create_keyframe(plan.comp_name, kf_spec, result)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"关键帧失败（{kf_spec.get('layer_name')}）: {exc}")

        # 5. 效果
        for eff_spec in plan.effects:
            try:
                self._apply_effect(plan.comp_name, eff_spec, result)
            except Exception as exc:  # noqa: BLE001
                result.warnings.append(f"应用效果失败（{eff_spec.get('layer_name')}）: {exc}")

    def _create_background(
        self,
        plan: CreativePlan,
        result: CreativeResult,
    ) -> None:
        """创建背景。"""
        bg = plan.background
        bg_type = bg.get("type", "solid")

        if bg_type == "solid":
            color = bg.get("color", [0.0, 0.0, 0.0])
            resp = self.ae.create_solid_layer(
                comp_name=plan.comp_name,
                color=color,
                name="BG",
            )
            result.execution_log.append({"stage": "ae_bg_solid", "response": resp})

        elif bg_type == "gradient":
            # 用 shape layer + gradient fill 模拟渐变
            grad = bg.get("gradient", {})
            resp = self.ae.create_shape_layer(
                comp_name=plan.comp_name,
                shape_type="rect",
                name="BG_Gradient",
            )
            result.execution_log.append({"stage": "ae_bg_gradient", "response": resp})
            # 渐变通过调整 shape layer 的 fill color 模拟（简化）

        else:
            # 未知类型 → 默认黑底
            self.ae.create_solid_layer(
                comp_name=plan.comp_name,
                color=[0.0, 0.0, 0.0],
                name="BG",
            )

    def _create_layer(
        self,
        comp_name: str,
        layer_spec: dict[str, Any],
        result: CreativeResult,
    ) -> None:
        """创建单个图层。"""
        layer_type = layer_spec.get("type", "solid")
        layer_name = layer_spec.get("name", "Layer")
        props = layer_spec.get("properties", {}) or {}

        if layer_type == "text":
            text = props.get("text") or props.get("text_content") or "Text"
            font_size = float(props.get("font_size", 72))
            color = props.get("color", [1.0, 1.0, 1.0])
            if not isinstance(color, (list, tuple)) or len(color) < 3:
                color = [1.0, 1.0, 1.0]

            resp = self.ae.create_text_layer(
                comp_name=comp_name,
                text=str(text),
                name=layer_name,
                font_size=font_size,
                color=[float(color[0]), float(color[1]), float(color[2])],
                font_family=props.get("font_family", "Arial"),
            )
            # 缓存图层名 → 索引
            self._cache_layer_index(comp_name, layer_name, resp)
            result.execution_log.append({
                "stage": "ae_text_layer",
                "layer_name": layer_name,
                "response": resp,
            })

        elif layer_type == "solid":
            color = props.get("color", [0.5, 0.5, 0.5])
            if not isinstance(color, (list, tuple)) or len(color) < 3:
                color = [0.5, 0.5, 0.5]
            resp = self.ae.create_solid_layer(
                comp_name=comp_name,
                color=[float(color[0]), float(color[1]), float(color[2])],
                name=layer_name,
            )
            self._cache_layer_index(comp_name, layer_name, resp)
            result.execution_log.append({
                "stage": "ae_solid_layer",
                "layer_name": layer_name,
                "response": resp,
            })

        elif layer_type == "shape":
            shape_type = props.get("shape", "rect")
            resp = self.ae.create_shape_layer(
                comp_name=comp_name,
                shape_type=shape_type,
                name=layer_name,
            )
            self._cache_layer_index(comp_name, layer_name, resp)
            result.execution_log.append({
                "stage": "ae_shape_layer",
                "layer_name": layer_name,
                "response": resp,
            })

        elif layer_type == "adjustment":
            resp = self.ae.add_adjustment_layer(
                comp_name=comp_name,
                name=layer_name,
            )
            self._cache_layer_index(comp_name, layer_name, resp)
            result.execution_log.append({
                "stage": "ae_adjustment_layer",
                "layer_name": layer_name,
                "response": resp,
            })

        else:
            result.warnings.append(f"未知图层类型: {layer_type}，已跳过")

    def _create_keyframe(
        self,
        comp_name: str,
        kf_spec: dict[str, Any],
        result: CreativeResult,
    ) -> None:
        """创建关键帧。"""
        layer_name = kf_spec.get("layer_name", "")
        layer_idx = self._find_layer_index(comp_name, layer_name)
        if layer_idx is None:
            result.warnings.append(f"关键帧找不到图层: {layer_name}")
            return

        property_name = kf_spec.get("property", "Position")
        time = float(kf_spec.get("time", 0.0))
        value = kf_spec.get("value", [0.0, 0.0])

        resp = self.ae.set_layer_keyframe(
            comp_name=comp_name,
            layer_index=layer_idx,
            property_name=property_name,
            time=time,
            value=value,
        )
        result.execution_log.append({
            "stage": "ae_keyframe",
            "layer_name": layer_name,
            "property": property_name,
            "time": time,
            "response": resp,
        })

    def _apply_effect(
        self,
        comp_name: str,
        eff_spec: dict[str, Any],
        result: CreativeResult,
    ) -> None:
        """应用效果。"""
        layer_name = eff_spec.get("layer_name", "")
        layer_idx = self._find_layer_index(comp_name, layer_name)
        if layer_idx is None:
            result.warnings.append(f"效果找不到图层: {layer_name}")
            return

        effect_name = eff_spec.get("effect_name")
        if not effect_name:
            result.warnings.append("效果缺少 effect_name，已跳过")
            return

        settings = eff_spec.get("settings", {}) or {}
        resp = self.ae.apply_effect(
            comp_name=comp_name,
            layer_index=layer_idx,
            effect_name=effect_name,
            settings=settings,
        )
        result.execution_log.append({
            "stage": "ae_effect",
            "layer_name": layer_name,
            "effect_name": effect_name,
            "response": resp,
        })

    def _cache_layer_index(
        self,
        comp_name: str,
        layer_name: str,
        create_resp: Any,
    ) -> None:
        """从创建响应中提取 layer_index 并缓存。"""
        idx = self._extract_layer_index(create_resp)
        if idx is not None:
            self._layer_index_cache[(comp_name, layer_name)] = idx

    @staticmethod
    def _extract_layer_index(create_resp: Any) -> int | None:
        """从 UnifiedAEClient 的创建响应中提取 layer_index。

        响应格式约定：
        - {"success": True, "data": {"layer_index": 1}}
        - {"success": True, "layer_index": 1}
        - {"success": True, "data": {"index": 1}}
        """
        if not isinstance(create_resp, dict):
            return None
        # 优先 data.layer_index
        data = create_resp.get("data")
        if isinstance(data, dict):
            for key in ("layer_index", "index", "layerId"):
                if key in data:
                    try:
                        return int(data[key])
                    except (TypeError, ValueError):
                        pass
        # 顶层
        for key in ("layer_index", "index", "layerId"):
            if key in create_resp:
                try:
                    return int(create_resp[key])
                except (TypeError, ValueError):
                    pass
        return None

    def _find_layer_index(
        self,
        comp_name: str,
        layer_name: str,
    ) -> int | None:
        """查找图层索引（优先缓存，否则通过 AE 客户端查询）。"""
        cached = self._layer_index_cache.get((comp_name, layer_name))
        if cached is not None:
            return cached

        # 尝试通过 get_layer_info 查询
        try:
            info = self.ae.get_layer_info(comp_name=comp_name, layer_name=layer_name)
        except Exception:  # noqa: BLE001
            info = None
        if isinstance(info, dict):
            for key in ("layer_index", "index"):
                if key in info:
                    try:
                        idx = int(info[key])
                        self._layer_index_cache[(comp_name, layer_name)] = idx
                        return idx
                    except (TypeError, ValueError):
                        pass
            data = info.get("data")
            if isinstance(data, dict):
                for key in ("layer_index", "index"):
                    if key in data:
                        try:
                            idx = int(data[key])
                            self._layer_index_cache[(comp_name, layer_name)] = idx
                            return idx
                        except (TypeError, ValueError):
                            pass
        return None

    # -----------------------------------------------------------------
    # 阶段 3：调色（AE → DaVinci 链路）
    # -----------------------------------------------------------------

    def _apply_color_grading(
        self,
        plan: CreativePlan,
        request: CreativeRequest,
        result: CreativeResult,
    ) -> None:
        """应用专业调色（通过 AE → DaVinci 协作链路）。

        如果调色链路不可用或失败，记录 warning 但不中断主流程。
        """
        if not plan.color_grading:
            return

        preset_name = plan.color_grading.get("preset_name")
        if not preset_name:
            preset_name = self._map_style_to_preset(request.style)

        if not preset_name:
            result.warnings.append("无调色预设，跳过调色阶段")
            return

        t0 = time.time()
        try:
            pipeline_result = self.ae_to_davinci.run_with_preset(
                comp_name=plan.comp_name,
                output_path=request.output_path,
                preset_name=preset_name,
                duration=plan.duration,
            )
            result.metrics["color_grading_sec"] = time.time() - t0
            result.execution_log.append({
                "stage": "color_grading",
                "preset_name": preset_name,
                "pipeline_success": pipeline_result.success,
            })

            if not pipeline_result.success:
                result.warnings.append(
                    f"调色失败（{pipeline_result.errors}），输出未调色视频"
                )
            else:
                if pipeline_result.final_output_path:
                    result.output_path = pipeline_result.final_output_path
        except Exception as exc:  # noqa: BLE001
            result.metrics["color_grading_sec"] = time.time() - t0
            result.warnings.append(f"调色阶段异常: {exc}")

    @staticmethod
    def _map_style_to_preset(style: StylePreset) -> str:
        """将风格映射到 DaVinci 调色预设。"""
        return STYLE_PRESET_MAP.get(style, "cinematic_teal_orange")

    # -----------------------------------------------------------------
    # 阶段 4：渲染输出
    # -----------------------------------------------------------------

    def _finalize_output(
        self,
        plan: CreativePlan,
        request: CreativeRequest,
        result: CreativeResult,
    ) -> None:
        """渲染输出。

        注意：实际渲染在 :meth:`_apply_color_grading` 内部由
        :class:`AEToDavinciPipeline` 完成（含 AE export + DaVinci render）。
        本方法负责：
        1. 如果未走调色链路（如调色被跳过），直接调用 AE render
        2. 确保输出目录存在
        """
        output_path = Path(request.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # 如果 result.output_path 已经被调色阶段设置为最终路径，跳过 AE render
        if result.output_path and result.output_path != request.output_path:
            return

        # 否则直接调用 AE 渲染
        try:
            t0 = time.time()
            render_resp = self.ae.render(
                comp_name=plan.comp_name,
                output_path=request.output_path,
                format="h264",
            )
            result.metrics["render_sec"] = time.time() - t0
            result.execution_log.append({
                "stage": "ae_render",
                "response": render_resp,
            })
            if not self._is_success(render_resp):
                result.warnings.append(f"AE 渲染返回失败: {render_resp.get('error')}")
        except Exception as exc:  # noqa: BLE001
            result.warnings.append(f"AE 渲染异常: {exc}")

    # -----------------------------------------------------------------
    # 工具方法
    # -----------------------------------------------------------------

    @staticmethod
    def _is_success(resp: Any) -> bool:
        """判断 AE 响应是否成功。"""
        if not isinstance(resp, dict):
            return False
        return bool(resp.get("success"))

    def _report(
        self,
        request: CreativeRequest,
        stage: str,
        percent: float,
    ) -> None:
        """触发进度回调（如果提供）。"""
        cb = request.progress_callback
        if cb is not None:
            try:
                cb(stage, percent)
            except Exception as exc:  # noqa: BLE001
                logger.warning("progress_callback 异常: %s", exc)
        logger.debug("[%5.1f%%] %s", percent * 100, stage)


# ============================================================================
# 便捷函数（顶层包装）
# ============================================================================

def quick_generate(
    description: str,
    output_path: str = "output/auto_generated.mp4",
    style: str = "cinematic",
    duration: float = 10.0,
) -> CreativeResult:
    """一行式端到端生成（最简 API）。

    示例::

        >>> result = quick_generate("做一个 10 秒电影感文字动画，内容是'探索未来'")

    Args:
        description: 用户文字描述。
        output_path: 输出 mp4 路径。
        style: 风格键名。
        duration: 时长（秒）。

    Returns:
        :class:`CreativeResult`。
    """
    loop = MinimalCreativeLoop()
    return loop.run(CreativeRequest(
        description=description,
        content_type=ContentType.TEXT_ANIMATION,
        style=StylePreset(style),
        duration=duration,
        output_path=output_path,
    ))


__all__ = [
    "ContentType",
    "StylePreset",
    "CreativeRequest",
    "CreativePlan",
    "CreativeResult",
    "MinimalCreativeLoop",
    "quick_generate",
]
