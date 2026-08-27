"""
pipeline/mg_orchestrator.py — MG 动画编排器
============================================

将 StyleSpec 转化为 MG 动画序列:
  1. 解析 StyleSpec → 确定 MG 动画类型/风格/时长
  2. 拆分为多个 MG 片段 (标题/图表/转场/结尾)
  3. 路由到合适的渲染后端 (Remotion/Motion Canvas/Pillow+FFmpeg)
  4. 拼接片段 → 最终 MG 动画输出
  5. 可选: 导出 Lottie JSON 用于跨平台交付

管线流程:
    StyleSpec → MGOrchestrator.plan() → [MGSegment, ...]
    → MGOrchestrator.render() → 逐段渲染 → 拼接 → 输出

用法:
    from pipeline.mg_orchestrator import MGOrchestrator
    orch = MGOrchestrator()
    result = orch.produce(
        style_spec={"type": "corporate", "duration": 30},
        content={"title": "Q4 Report", "data": [...]},
        output_path="output/mg_report.mp4",
    )
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class MGSegment:
    """MG 动画片段"""
    index: int
    segment_type: str           # title/data_chart/transition/ending/typography
    subtype: str = ""
    duration_sec: float = 3.0
    content: Dict[str, Any] = field(default_factory=dict)
    style_override: Optional[Dict[str, Any]] = None
    render_backend: str = "pillow_ffmpeg"
    transition_in: str = "fade"
    transition_out: str = "fade"


@dataclass
class MGPlan:
    """MG 动画编排计划"""
    title: str = ""
    total_duration_sec: float = 30.0
    segments: List[MGSegment] = field(default_factory=list)
    global_style: Dict[str, Any] = field(default_factory=dict)
    resolution: List[int] = field(default_factory=lambda: [1920, 1080])
    fps: int = 30
    output_format: str = "mp4"  # mp4/lottie/gif


# ============================================================================
#  MG 动画编排器
# ============================================================================

class MGOrchestrator:
    """MG 动画编排器

    职责:
    1. 将高层 StyleSpec + 内容 → 结构化 MG 计划
    2. 路由每段到最优渲染后端
    3. 协调多段渲染 + 拼接
    """

    # StyleSpec 类型 → 默认 MG 模板映射
    STYLE_TEMPLATES = {
        "corporate": {
            "segments": ["title", "data_chart", "data_chart", "transition", "ending"],
            "style": {"bg": "#1a1a2e", "accent": "#4fc3f7", "text": "#ffffff"},
            "default_duration": 30.0,
        },
        "playful": {
            "segments": ["title", "typography", "data_chart", "ending"],
            "style": {"bg": "#fff3e0", "accent": "#ff6d00", "text": "#333333"},
            "default_duration": 20.0,
        },
        "minimal": {
            "segments": ["title", "typography", "ending"],
            "style": {"bg": "#ffffff", "accent": "#333333", "text": "#000000"},
            "default_duration": 15.0,
        },
        "dark": {
            "segments": ["title", "data_chart", "typography", "transition", "ending"],
            "style": {"bg": "#0d0d0d", "accent": "#00e5ff", "text": "#ffffff"},
            "default_duration": 25.0,
        },
    }

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        from core.mg_template_engine import MGTemplateEngine
        self._engine = MGTemplateEngine(config)

    def plan(
        self,
        style_spec: Dict[str, Any],
        content: Dict[str, Any],
    ) -> MGPlan:
        """将 StyleSpec + 内容 → MG 编排计划

        Args:
            style_spec: 风格规格书 (来自 production_director)
            content: 内容数据 {title, data, text, ...}

        Returns:
            MGPlan 编排计划
        """
        # 确定风格模板
        style_type = style_spec.get("type", "corporate")
        template = self.STYLE_TEMPLATES.get(style_type, self.STYLE_TEMPLATES["corporate"])

        total_duration = style_spec.get("duration", template["default_duration"])
        resolution = style_spec.get("resolution", [1920, 1080])

        # 生成片段列表
        segment_types = template["segments"]
        per_segment_duration = total_duration / len(segment_types)

        segments = []
        for i, seg_type in enumerate(segment_types):
            seg = MGSegment(
                index=i,
                segment_type=seg_type,
                duration_sec=per_segment_duration,
                content=self._build_segment_content(seg_type, content, i),
                style_override=template["style"],
            )
            segments.append(seg)

        return MGPlan(
            title=content.get("title", ""),
            total_duration_sec=total_duration,
            segments=segments,
            global_style=template["style"],
            resolution=resolution,
            fps=style_spec.get("fps", 30),
            output_format=style_spec.get("output_format", "mp4"),
        )

    def produce(
        self,
        style_spec: Dict[str, Any],
        content: Dict[str, Any],
        output_path: str = "output_mg.mp4",
    ) -> Dict[str, Any]:
        """端到端 MG 动画生产

        Args:
            style_spec: 风格规格书
            content: 内容数据
            output_path: 输出路径

        Returns:
            生产结果字典
        """
        # 1. 编排计划
        mg_plan = self.plan(style_spec, content)
        logger.info("[MGOrchestrator] Plan: %d segments, %.1fs total",
                     len(mg_plan.segments), mg_plan.total_duration_sec)

        # 2. 逐段渲染
        rendered_segments = []
        with tempfile.TemporaryDirectory(prefix="mg_orch_") as tmpdir:
            for seg in mg_plan.segments:
                seg_output = os.path.join(tmpdir, f"seg_{seg.index:02d}_{seg.segment_type}.mp4")
                result = self._render_segment(seg, seg_output, mg_plan)
                if result.get("status") == "success":
                    rendered_segments.append(seg_output)
                else:
                    logger.warning("[MGOrchestrator] Segment %d failed: %s",
                                    seg.index, result.get("message", "unknown"))

            if not rendered_segments:
                return {"status": "error", "message": "No segments rendered successfully"}

            # 3. 拼接
            if len(rendered_segments) == 1:
                # 只有一段，直接复制
                import shutil
                shutil.copy2(rendered_segments[0], output_path)
            else:
                concat_result = self._concat_segments(rendered_segments, output_path, mg_plan.fps)
                if concat_result.get("status") != "success":
                    return concat_result

        # 4. 可选: Lottie 导出
        lottie_result = None
        if mg_plan.output_format == "lottie":
            lottie_result = self._engine.export_lottie({
                "type": mg_plan.segments[0].segment_type if mg_plan.segments else "typography",
                "style": mg_plan.global_style,
                "duration": mg_plan.total_duration_sec,
                "resolution": mg_plan.resolution,
                "lottie_output": output_path.replace(".mp4", ".json"),
            })

        return {
            "status": "success",
            "output_path": output_path,
            "segments_rendered": len(rendered_segments),
            "total_segments": len(mg_plan.segments),
            "total_duration_sec": mg_plan.total_duration_sec,
            "resolution": mg_plan.resolution,
            "lottie": lottie_result,
        }

    def _build_segment_content(self, seg_type: str, content: Dict[str, Any], idx: int) -> Dict[str, Any]:
        """为每种片段类型构建内容"""
        data_list = content.get("data", [])

        if seg_type == "title":
            return {"text": content.get("title", "Title")}
        elif seg_type == "data_chart":
            # 轮询数据列表
            chunk_size = max(len(data_list) // 3, 1)
            start = (idx * chunk_size) % max(len(data_list), 1)
            chunk = data_list[start:start + chunk_size] if data_list else [{"label": "A", "value": 50}]
            return {"data": chunk, "subtype": content.get("chart_type", "bar")}
        elif seg_type == "typography":
            texts = content.get("texts", [])
            text = texts[idx % len(texts)] if texts else f"Point {idx + 1}"
            return {"text": text}
        elif seg_type == "transition":
            return {"subtype": content.get("transition_type", "wipe")}
        elif seg_type == "ending":
            return {"text": content.get("ending_text", content.get("title", "Thank You"))}
        return {}

    def _render_segment(self, seg: MGSegment, output_path: str, plan: MGPlan) -> Dict[str, Any]:
        """渲染单个 MG 片段"""
        spec = {
            "type": seg.segment_type,
            "subtype": seg.subtype or seg.content.get("subtype", ""),
            "text": seg.content.get("text", ""),
            "data": seg.content.get("data", []),
            "style": seg.style_override or plan.global_style,
            "duration": seg.duration_sec,
            "resolution": plan.resolution,
            "fps": plan.fps,
            "easing": "ease_out",
        }
        return self._engine.render(spec, output_path, backend=seg.render_backend)

    def _concat_segments(self, segments: List[str], output_path: str, fps: int) -> Dict[str, Any]:
        """使用 FFmpeg 拼接片段"""
        # 创建 concat 文件列表
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, prefix="mg_concat_") as f:
            for seg_path in segments:
                f.write(f"file '{seg_path}'\n")
            concat_file = f.name

        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat", "-safe", "0",
                "-i", concat_file,
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "medium",
                "-crf", "18",
                "-r", str(fps),
                output_path,
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if proc.returncode == 0:
                return {"status": "success", "output_path": output_path}
            else:
                return {"status": "error", "message": f"FFmpeg concat failed: {proc.stderr[-200:]}"}
        finally:
            os.unlink(concat_file)
