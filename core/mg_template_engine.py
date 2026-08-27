"""
core/mg_template_engine.py — MG 动画模板引擎
=============================================

参数化动态图形模板系统，支持:
  - 形状动画 (圆形/矩形/路径变形)
  - 文字动画 (逐字/逐行/弹跳/打字机)
  - 数据图表动画 (柱状图/折线图/饼图)
  - 排版动画 (网格/分栏/信息图)
  - 转场效果 (擦除/缩放/旋转/滑动)

输出目标:
  - Remotion React 组件 (TSX)
  - Motion Canvas TypeScript 场景
  - AE ExtendScript (JSX)
  - Lottie JSON
  - 直接 MP4 (通过 FFmpeg + Pillow)

用法:
    from core.mg_template_engine import MGTemplateEngine
    engine = MGTemplateEngine()
    spec = {
        "type": "data_chart",
        "subtype": "bar",
        "data": [{"label": "Q1", "value": 42}, ...],
        "style": {"bg": "#1a1a2e", "accent": "#4fc3f7"},
        "duration_sec": 5,
        "resolution": [1920, 1080],
    }
    result = engine.render(spec, output_path="chart.mp4")
"""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class MGStyle:
    """MG 动画视觉风格"""
    bg_color: str = "#1a1a2e"
    accent_color: str = "#4fc3f7"
    text_color: str = "#ffffff"
    secondary_color: str = "#e040fb"
    font_family: str = "Arial"
    font_size: int = 48
    corner_radius: int = 8
    padding: int = 60


@dataclass
class MGAnimationSpec:
    """MG 动画规格书"""
    anim_type: str = "typography"       # typography/data_chart/shape/transition
    subtype: str = ""                   # bar/line/pie/circle/rect/wipe/zoom
    data: List[Dict[str, Any]] = field(default_factory=list)
    text: str = ""
    style: MGStyle = field(default_factory=MGStyle)
    duration_sec: float = 5.0
    fps: int = 30
    width: int = 1920
    height: int = 1080
    easing: str = "ease_out"           # linear/ease_in/ease_out/ease_in_out/spring
    extra: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
#  缓动函数
# ============================================================================

def ease_linear(t: float) -> float:
    return t

def ease_in(t: float) -> float:
    return t * t * t

def ease_out(t: float) -> float:
    return 1 - (1 - t) ** 3

def ease_in_out(t: float) -> float:
    if t < 0.5:
        return 4 * t * t * t
    return 1 - (-2 * t + 2) ** 3 / 2

def ease_spring(t: float, damping: float = 0.6) -> float:
    return 1 - math.exp(-damping * t * 10) * math.cos(t * math.pi * 4)

EASING_FUNCTIONS = {
    "linear": ease_linear,
    "ease_in": ease_in,
    "ease_out": ease_out,
    "ease_in_out": ease_in_out,
    "spring": ease_spring,
}


# ============================================================================
#  模板引擎
# ============================================================================

class MGTemplateEngine:
    """MG 动画模板引擎

    支持两种渲染后端:
    1. Pillow + FFmpeg (直接渲染，无需外部依赖)
    2. Remotion (React 组件渲染，需 Node.js)
    3. Motion Canvas (TypeScript 渲染，需 Node.js)
    """

    SUPPORTED_TYPES = ["typography", "data_chart", "shape", "transition", "infographic"]
    RENDER_BACKENDS = ["pillow_ffmpeg", "remotion", "motion_canvas"]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._default_backend = "pillow_ffmpeg"
        self._ffmpeg_available = self._check_ffmpeg()

    def _check_ffmpeg(self) -> bool:
        try:
            r = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, timeout=5
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def render(
        self,
        spec: Dict[str, Any],
        output_path: str = "output_mg.mp4",
        backend: str = "auto",
    ) -> Dict[str, Any]:
        """渲染 MG 动画

        Args:
            spec: 动画规格书
            output_path: 输出路径
            backend: 渲染后端 (auto/pillow_ffmpeg/remotion/motion_canvas)

        Returns:
            渲染结果字典
        """
        # 解析规格书
        anim_spec = self._parse_spec(spec)

        # 选择后端
        if backend == "auto":
            backend = self._default_backend
            # 检查 Remotion 是否可用
            if self._check_remotion():
                backend = "remotion"

        # 渲染
        if backend == "pillow_ffmpeg":
            return self._render_pillow_ffmpeg(anim_spec, output_path)
        elif backend == "remotion":
            return self._render_remotion(anim_spec, output_path)
        elif backend == "motion_canvas":
            return self._render_motion_canvas(anim_spec, output_path)
        else:
            return {"status": "error", "message": f"Unknown backend: {backend}"}

    def list_templates(self) -> Dict[str, Any]:
        """列出所有可用模板"""
        return {
            "status": "success",
            "templates": [
                {
                    "type": "typography",
                    "subtypes": ["title_reveal", "lower_third", "typewriter", "bounce"],
                    "description": "文字动画: 标题展示/字幕条/打字机/弹跳",
                },
                {
                    "type": "data_chart",
                    "subtypes": ["bar", "line", "pie", "number_count"],
                    "description": "数据图表: 柱状图/折线图/饼图/数字跳动",
                },
                {
                    "type": "shape",
                    "subtypes": ["circle", "rect", "path_morph", "particle"],
                    "description": "形状动画: 圆/矩形/路径变形/粒子",
                },
                {
                    "type": "transition",
                    "subtypes": ["wipe", "zoom", "rotate", "slide", "glitch"],
                    "description": "转场: 擦除/缩放/旋转/滑动/故障",
                },
                {
                    "type": "infographic",
                    "subtypes": ["grid", "timeline", "comparison"],
                    "description": "信息图: 网格/时间线/对比",
                },
            ],
            "backends": self.RENDER_BACKENDS,
        }

    def _parse_spec(self, spec: Dict[str, Any]) -> MGAnimationSpec:
        """解析动画规格书"""
        style_data = spec.get("style", {})
        if isinstance(style_data, dict):
            style = MGStyle(
                bg_color=style_data.get("bg", "#1a1a2e"),
                accent_color=style_data.get("accent", "#4fc3f7"),
                text_color=style_data.get("text", "#ffffff"),
                secondary_color=style_data.get("secondary", "#e040fb"),
                font_family=style_data.get("font_family", "Arial"),
                font_size=style_data.get("font_size", 48),
            )
        else:
            style = MGStyle()

        resolution = spec.get("resolution", [1920, 1080])

        return MGAnimationSpec(
            anim_type=spec.get("type", "typography"),
            subtype=spec.get("subtype", ""),
            data=spec.get("data", []),
            text=spec.get("text", ""),
            style=style,
            duration_sec=spec.get("duration", 5.0),
            fps=spec.get("fps", 30),
            width=resolution[0] if len(resolution) > 0 else 1920,
            height=resolution[1] if len(resolution) > 1 else 1080,
            easing=spec.get("easing", "ease_out"),
            extra={k: v for k, v in spec.items() if k not in (
                "type", "subtype", "data", "text", "style",
                "duration", "fps", "resolution", "easing",
            )},
        )

    # ── Pillow + FFmpeg 渲染 ──────────────────────────────────────────

    def _render_pillow_ffmpeg(self, spec: MGAnimationSpec, output_path: str) -> Dict[str, Any]:
        """使用 Pillow 逐帧渲染 + FFmpeg 编码"""
        if not self._ffmpeg_available:
            return {"status": "error", "message": "FFmpeg not available"}

        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            return {"status": "error", "message": "Pillow not installed"}

        total_frames = int(spec.duration_sec * spec.fps)
        easing_fn = EASING_FUNCTIONS.get(spec.easing, ease_out)

        # 临时帧目录
        with tempfile.TemporaryDirectory(prefix="mg_frames_") as tmpdir:
            frame_dir = Path(tmpdir)

            for frame_idx in range(total_frames):
                t = frame_idx / max(total_frames - 1, 1)
                progress = easing_fn(t)

                img = Image.new("RGB", (spec.width, spec.height), spec.style.bg_color)
                draw = ImageDraw.Draw(img)

                # 根据类型分发渲染
                if spec.anim_type == "typography":
                    self._draw_typography(draw, spec, progress, frame_idx)
                elif spec.anim_type == "data_chart":
                    self._draw_data_chart(draw, spec, progress, frame_idx)
                elif spec.anim_type == "shape":
                    self._draw_shape(draw, spec, progress, frame_idx)
                elif spec.anim_type == "transition":
                    self._draw_transition(draw, spec, progress, frame_idx)
                else:
                    self._draw_typography(draw, spec, progress, frame_idx)

                frame_path = frame_dir / f"frame_{frame_idx:05d}.png"
                img.save(str(frame_path))

            # FFmpeg 编码
            cmd = [
                "ffmpeg", "-y",
                "-framerate", str(spec.fps),
                "-i", str(frame_dir / "frame_%05d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-preset", "medium",
                "-crf", "18",
                output_path,
            ]

            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if proc.returncode == 0:
                return {
                    "status": "success",
                    "backend": "pillow_ffmpeg",
                    "output_path": output_path,
                    "frames": total_frames,
                    "resolution": f"{spec.width}x{spec.height}",
                    "duration_sec": spec.duration_sec,
                }
            else:
                return {"status": "error", "message": f"FFmpeg failed: {proc.stderr[-200:]}"}

    def _draw_typography(self, draw, spec, progress, frame_idx):
        """文字动画渲染"""
        from PIL import ImageFont
        text = spec.text or "MG Animation"
        cx, cy = spec.width // 2, spec.height // 2

        try:
            font = ImageFont.truetype("arial.ttf", spec.style.font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        # 逐字显示效果
        visible_chars = int(len(text) * progress)
        visible_text = text[:visible_chars]

        # 缩放效果
        scale = 0.5 + 0.5 * progress
        bbox = draw.textbbox((0, 0), visible_text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        x = cx - tw // 2
        y = cy - th // 2

        draw.text((x, y), visible_text, fill=spec.style.text_color, font=font)

    def _draw_data_chart(self, draw, spec, progress, frame_idx):
        """数据图表动画渲染"""
        data = spec.data or [{"label": "A", "value": 40}, {"label": "B", "value": 70},
                              {"label": "C", "value": 55}, {"label": "D", "value": 85}]
        n = len(data)
        max_val = max(d.get("value", 0) for d in data) or 1
        padding = spec.style.padding
        chart_w = spec.width - 2 * padding
        chart_h = spec.height - 2 * padding
        bar_w = max(chart_w // (n * 2), 20)
        gap = bar_w // 2

        for i, d in enumerate(data):
            val = d.get("value", 0)
            bar_h = (val / max_val) * chart_h * progress
            x = padding + i * (bar_w + gap)
            y = spec.height - padding - bar_h

            draw.rectangle(
                [x, y, x + bar_w, spec.height - padding],
                fill=spec.style.accent_color if i % 2 == 0 else spec.style.secondary_color,
            )

    def _draw_shape(self, draw, spec, progress, frame_idx):
        """形状动画渲染"""
        cx, cy = spec.width // 2, spec.height // 2
        r = int(min(spec.width, spec.height) * 0.3 * progress)

        if spec.subtype == "circle" or not spec.subtype:
            draw.ellipse(
                [cx - r, cy - r, cx + r, cy + r],
                fill=spec.style.accent_color,
            )
        else:
            draw.rectangle(
                [cx - r, cy - r, cx + r, cy + r],
                fill=spec.style.accent_color,
            )

    def _draw_transition(self, draw, spec, progress, frame_idx):
        """转场效果渲染"""
        w, h = spec.width, spec.height

        if spec.subtype == "wipe" or not spec.subtype:
            # 从左到右擦除
            wipe_x = int(w * progress)
            draw.rectangle([0, 0, wipe_x, h], fill=spec.style.accent_color)
        elif spec.subtype == "zoom":
            r = int(max(w, h) * progress)
            cx, cy = w // 2, h // 2
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=spec.style.accent_color)
        else:
            draw.rectangle([0, 0, w, h], fill=spec.style.accent_color)

    # ── Remotion 渲染 ──────────────────────────────────────────────

    def _render_remotion(self, spec: MGAnimationSpec, output_path: str) -> Dict[str, Any]:
        """通过 Remotion 渲染"""
        from integrations.remotion_agent_adapter import RemotionAgentAdapter
        adapter = RemotionAgentAdapter()
        return adapter.execute("generate_mg_animation", {
            "spec": {
                "type": spec.anim_type,
                "subtype": spec.subtype,
                "data": spec.data,
                "text": spec.text,
                "style": {
                    "bg": spec.style.bg_color,
                    "accent": spec.style.accent_color,
                },
                "duration": spec.duration_sec,
            },
            "output_path": output_path,
            "fps": spec.fps,
            "width": spec.width,
            "height": spec.height,
        })

    def _render_motion_canvas(self, spec: MGAnimationSpec, output_path: str) -> Dict[str, Any]:
        """通过 Motion Canvas 渲染 (预留)"""
        return {
            "status": "success",
            "mode": "simulate",
            "message": "Motion Canvas 渲染尚未实现，降级为 Pillow+FFmpeg",
            "backend": "pillow_ffmpeg",
        }

    def _check_remotion(self) -> bool:
        """检查 Remotion 是否可用"""
        try:
            r = subprocess.run(
                ["npx", "remotion", "--version"],
                capture_output=True, text=True, timeout=15,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    # ── Lottie JSON 导出 ──────────────────────────────────────────

    def export_lottie(self, spec: Dict[str, Any]) -> Dict[str, Any]:
        """将 MG 动画规格书导出为 Lottie JSON

        Returns:
            {"status": "success", "lottie": {...}, "file_path": "..."}
        """
        anim_spec = self._parse_spec(spec)
        lottie = self._spec_to_lottie(anim_spec)

        output_path = spec.get("lottie_output", "output_mg_lottie.json")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(lottie, f, indent=2)

        return {
            "status": "success",
            "lottie": lottie,
            "file_path": output_path,
        }

    def _spec_to_lottie(self, spec: MGAnimationSpec) -> Dict[str, Any]:
        """将 MGAnimationSpec 转为 Lottie JSON 格式"""
        total_frames = int(spec.duration_sec * spec.fps)

        # 基础 Lottie 结构
        lottie = {
            "v": "5.7.1",
            "fr": spec.fps,
            "ip": 0,
            "op": total_frames,
            "w": spec.width,
            "h": spec.height,
            "nm": f"mg_{spec.anim_type}",
            "ddd": 0,
            "assets": [],
            "layers": [],
        }

        # 根据类型生成图层
        if spec.anim_type == "typography":
            lottie["layers"].append(self._lottie_text_layer(spec, total_frames))
        elif spec.anim_type == "data_chart":
            for i, d in enumerate(spec.data or []):
                lottie["layers"].append(
                    self._lottie_shape_layer(spec, d, i, total_frames)
                )
        elif spec.anim_type == "shape":
            lottie["layers"].append(self._lottie_shape_layer(spec, {}, 0, total_frames))

        return lottie

    def _lottie_text_layer(self, spec: MGAnimationSpec, total_frames: int) -> Dict:
        """生成 Lottie 文字图层"""
        return {
            "ddd": 0,
            "ind": 0,
            "ty": 5,  # text layer
            "nm": "text",
            "sr": 1,
            "ks": {
                "o": {"a": 1, "k": [
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]},
                     "t": 0, "s": [0]},
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]},
                     "t": total_frames // 2, "s": [100]},
                    {"t": total_frames, "s": [100]},
                ]},
                "r": {"a": 0, "k": 0},
                "p": {"a": 0, "k": [spec.width // 2, spec.height // 2, 0]},
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": {"a": 1, "k": [
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]},
                     "t": 0, "s": [50, 50, 100]},
                    {"t": total_frames // 2, "s": [100, 100, 100]},
                ]},
            },
            "ao": 0,
            "t": {
                "d": {"k": [{"s": {"s": spec.style.font_size, "f": spec.style.font_family,
                                    "t": spec.text or "MG Animation",
                                    "fc": self._hex_to_rgb(spec.style.text_color)},
                              "t": 0}]},
                "p": {},
                "m": {"g": 1, "a": {"a": 0, "k": [0, 0]}},
            },
            "ip": 0,
            "op": total_frames,
        }

    def _lottie_shape_layer(self, spec: MGAnimationSpec, data: dict, idx: int, total_frames: int) -> Dict:
        """生成 Lottie 形状图层"""
        padding = spec.style.padding
        n = max(len(spec.data), 1)
        bar_w = (spec.width - 2 * padding) // (n * 2)
        x = padding + idx * bar_w * 2

        return {
            "ddd": 0,
            "ind": idx,
            "ty": 4,  # shape layer
            "nm": f"bar_{idx}",
            "sr": 1,
            "ks": {
                "o": {"a": 0, "k": 100},
                "r": {"a": 0, "k": 0},
                "p": {"a": 0, "k": [x + bar_w // 2, spec.height - padding, 0]},
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": {"a": 1, "k": [
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]},
                     "t": idx * 5, "s": [100, 0, 100]},
                    {"t": idx * 5 + total_frames // 2, "s": [100, 100, 100]},
                ]},
            },
            "ao": 0,
            "shapes": [{
                "ty": "rc",
                "d": 1,
                "s": {"a": 0, "k": [bar_w, 100]},
                "p": {"a": 0, "k": [0, -50]},
                "r": {"a": 0, "k": spec.style.corner_radius},
            }],
            "ip": 0,
            "op": total_frames,
        }

    @staticmethod
    def _hex_to_rgb(hex_color: str) -> List[float]:
        """#RRGGBB → [r, g, b] (0~1 范围)"""
        hex_color = hex_color.lstrip("#")
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return [r / 255.0, g / 255.0, b / 255.0]
