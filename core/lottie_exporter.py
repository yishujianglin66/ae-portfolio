"""
core/lottie_exporter.py — Lottie JSON 导出模块
================================================

将 AE 动画/程序化动画导出为 Lottie JSON 格式:
  - 支持 AE 动画 → Lottie (通过 bodymovin 插件)
  - 支持程序化 MG 动画 → Lottie
  - 支持跨平台交付: Web/iOS/Android

Lottie 格式规范:
  - v: Lottie 版本
  - fr: 帧率
  - ip/out: 入点/出点
  - w/h: 宽高
  - layers: 图层数组 (shape/text/image/null)
  - assets: 资源 (图片/预合成)

用法:
    from core.lottie_exporter import LottieExporter
    exporter = LottieExporter()
    result = exporter.create_animation(
        layers=[
            {"type": "text", "text": "Hello", "animation": "fade_in"},
            {"type": "shape", "shape": "circle", "animation": "scale_up"},
        ],
        output_path="animation.json",
        duration_sec=3,
    )
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class LottieExporter:
    """Lottie JSON 动画导出器

    支持:
    1. 程序化创建 Lottie 动画
    2. AE 项目 → Lottie (通过 bodymovin/nexrender)
    3. MG 模板引擎 → Lottie
    """

    LOTTIE_VERSION = "5.7.1"

    # 支持的动画类型
    ANIMATIONS = [
        "fade_in", "fade_out", "scale_up", "scale_down",
        "slide_left", "slide_right", "slide_up", "slide_down",
        "rotate", "bounce", "typewriter", "path_draw",
    ]

    def create_animation(
        self,
        layers: list[dict[str, Any]],
        output_path: str = "lottie_output.json",
        duration_sec: float = 3.0,
        fps: int = 30,
        width: int = 800,
        height: int = 600,
        bg_color: str = "#ffffff",
    ) -> dict[str, Any]:
        """创建 Lottie 动画

        Args:
            layers: 图层定义列表
            output_path: 输出 JSON 路径
            duration_sec: 动画时长
            fps: 帧率
            width/height: 画布尺寸
            bg_color: 背景色

        Returns:
            {"status": "success", "lottie": {...}, "file_path": "..."}
        """
        total_frames = int(duration_sec * fps)

        lottie = {
            "v": self.LOTTIE_VERSION,
            "fr": fps,
            "ip": 0,
            "op": total_frames,
            "w": width,
            "h": height,
            "nm": "exported_animation",
            "ddd": 0,
            "assets": [],
            "layers": [],
        }

        # 构建图层
        for i, layer_def in enumerate(layers):
            layer_type = layer_def.get("type", "shape")
            animation = layer_def.get("animation", "fade_in")
            delay = layer_def.get("delay", 0.0)  # 延迟秒数

            delay_frames = int(delay * fps)

            if layer_type == "text":
                layer = self._build_text_layer(
                    layer_def, i, total_frames, fps, width, height, delay_frames
                )
            elif layer_type == "shape":
                layer = self._build_shape_layer(
                    layer_def, i, total_frames, fps, width, height, delay_frames
                )
            elif layer_type == "image":
                layer = self._build_image_layer(
                    layer_def, i, total_frames, fps, width, height, delay_frames, lottie
                )
            else:
                layer = self._build_null_layer(layer_def, i, total_frames)

            lottie["layers"].append(layer)

        # 输出
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(lottie, f, indent=2, ensure_ascii=False)

        return {
            "status": "success",
            "lottie": lottie,
            "file_path": output_path,
            "layer_count": len(layers),
            "total_frames": total_frames,
        }

    def _build_text_layer(self, defn, idx, total_frames, fps, w, h, delay):
        """构建文字图层"""
        text = defn.get("text", "Text")
        font_size = defn.get("font_size", 48)
        color = defn.get("color", "#333333")
        animation = defn.get("animation", "fade_in")
        x = defn.get("x", w // 2)
        y = defn.get("y", h // 2)

        # 关键帧
        opacity_kf = self._animation_keyframes(animation, "opacity", total_frames, delay)
        scale_kf = self._animation_keyframes(animation, "scale", total_frames, delay)

        return {
            "ddd": 0,
            "ind": idx,
            "ty": 5,
            "nm": f"text_{idx}",
            "sr": 1,
            "ks": {
                "o": opacity_kf,
                "r": {"a": 0, "k": 0},
                "p": {"a": 0, "k": [x, y, 0]},
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": scale_kf,
            },
            "ao": 0,
            "t": {
                "d": {"k": [{"s": {
                    "s": font_size,
                    "f": defn.get("font_family", "Arial"),
                    "t": text,
                    "fc": self._hex_to_lottie_color(color),
                    "j": 2,  # center
                }, "t": 0}]},
                "p": {},
                "m": {"g": 1, "a": {"a": 0, "k": [0, 0]}},
            },
            "ip": 0,
            "op": total_frames,
        }

    def _build_shape_layer(self, defn, idx, total_frames, fps, w, h, delay):
        """构建形状图层"""
        shape = defn.get("shape", "circle")
        color = defn.get("color", "#4fc3f7")
        size = defn.get("size", 100)
        animation = defn.get("animation", "scale_up")
        x = defn.get("x", w // 2)
        y = defn.get("y", h // 2)

        opacity_kf = self._animation_keyframes(animation, "opacity", total_frames, delay)
        scale_kf = self._animation_keyframes(animation, "scale", total_frames, delay)
        position_kf = self._animation_keyframes(animation, "position", total_frames, delay,
                                                  center=[x, y, 0])

        shape_data = {
            "ty": "el" if shape == "circle" else "rc",
            "d": 1,
            "s": {"a": 0, "k": [size, size]},
            "p": {"a": 0, "k": [0, 0]},
        }
        if shape == "rect":
            shape_data["ty"] = "rc"
            shape_data["r"] = {"a": 0, "k": defn.get("corner_radius", 0)}

        return {
            "ddd": 0,
            "ind": idx,
            "ty": 4,
            "nm": f"shape_{idx}",
            "sr": 1,
            "ks": {
                "o": opacity_kf,
                "r": {"a": 0, "k": defn.get("rotation", 0)},
                "p": position_kf,
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": scale_kf,
            },
            "ao": 0,
            "shapes": [
                shape_data,
                {
                    "ty": "fl",
                    "c": {"a": 0, "k": self._hex_to_lottie_color(color)},
                    "o": {"a": 0, "k": 100},
                    "r": 1,
                },
            ],
            "ip": 0,
            "op": total_frames,
        }

    def _build_image_layer(self, defn, idx, total_frames, fps, w, h, delay, lottie):
        """构建图片图层"""
        image_path = defn.get("image_path", "")
        image_id = f"img_{idx}"

        # 添加到 assets
        lottie["assets"].append({
            "id": image_id,
            "w": defn.get("width", 200),
            "h": defn.get("height", 200),
            "u": "",
            "p": image_path,
        })

        return {
            "ddd": 0,
            "ind": idx,
            "ty": 2,
            "nm": f"image_{idx}",
            "sr": 1,
            "ks": {
                "o": self._animation_keyframes(
                    defn.get("animation", "fade_in"), "opacity", total_frames, delay
                ),
                "r": {"a": 0, "k": 0},
                "p": {"a": 0, "k": [w // 2, h // 2, 0]},
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": self._animation_keyframes(
                    defn.get("animation", "fade_in"), "scale", total_frames, delay
                ),
            },
            "ao": 0,
            "refId": image_id,
            "ip": 0,
            "op": total_frames,
        }

    def _build_null_layer(self, defn, idx, total_frames):
        """构建空图层"""
        return {
            "ddd": 0, "ind": idx, "ty": 3,
            "nm": f"null_{idx}", "sr": 1,
            "ks": {
                "o": {"a": 0, "k": 100},
                "r": {"a": 0, "k": 0},
                "p": {"a": 0, "k": [0, 0, 0]},
                "a": {"a": 0, "k": [0, 0, 0]},
                "s": {"a": 0, "k": [100, 100, 100]},
            },
            "ao": 0, "ip": 0, "op": total_frames,
        }

    def _animation_keyframes(self, animation, prop, total_frames, delay, center=None):
        """根据动画类型生成关键帧"""
        delay_f = delay

        if prop == "opacity":
            if animation in ("fade_in", "scale_up", "slide_left", "slide_right"):
                return {"a": 1, "k": [
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]},
                     "t": delay_f, "s": [0]},
                    {"t": delay_f + total_frames // 3, "s": [100]},
                ]}
            elif animation == "fade_out":
                return {"a": 1, "k": [
                    {"i": {"x": [0.833], "y": [0.833]}, "o": {"x": [0.167], "y": [0.167]},
                     "t": delay_f + total_frames * 2 // 3, "s": [100]},
                    {"t": delay_f + total_frames, "s": [0]},
                ]}
            return {"a": 0, "k": 100}

        elif prop == "scale":
            if animation == "scale_up":
                return {"a": 1, "k": [
                    {"i": {"x": [0.833, 0.833, 0.833], "y": [0.833, 0.833, 0.833]},
                     "o": {"x": [0.167, 0.167, 0.167], "y": [0.167, 0.167, 0.167]},
                     "t": delay_f, "s": [0, 0, 100]},
                    {"t": delay_f + total_frames // 2, "s": [100, 100, 100]},
                ]}
            elif animation == "bounce":
                mid = delay_f + total_frames // 2
                return {"a": 1, "k": [
                    {"i": {"x": [0.833]*3, "y": [0.833]*3}, "o": {"x": [0.167]*3, "y": [0.167]*3},
                     "t": delay_f, "s": [0, 0, 100]},
                    {"i": {"x": [0.833]*3, "y": [0.833]*3}, "o": {"x": [0.167]*3, "y": [0.167]*3},
                     "t": mid, "s": [120, 120, 100]},
                    {"t": delay_f + total_frames // 2 + 5, "s": [100, 100, 100]},
                ]}
            return {"a": 0, "k": [100, 100, 100]}

        elif prop == "position":
            if center is None:
                center = [0, 0, 0]
            if animation == "slide_left":
                return {"a": 1, "k": [
                    {"i": {"x": [0.833]*3, "y": [0.833]*3}, "o": {"x": [0.167]*3, "y": [0.167]*3},
                     "t": delay_f, "s": [center[0] + 500, center[1], center[2]]},
                    {"t": delay_f + total_frames // 2, "s": center},
                ]}
            elif animation == "slide_right":
                return {"a": 1, "k": [
                    {"i": {"x": [0.833]*3, "y": [0.833]*3}, "o": {"x": [0.167]*3, "y": [0.167]*3},
                     "t": delay_f, "s": [center[0] - 500, center[1], center[2]]},
                    {"t": delay_f + total_frames // 2, "s": center},
                ]}
            return {"a": 0, "k": center}

        return {"a": 0, "k": 0}

    @staticmethod
    def _hex_to_lottie_color(hex_color: str) -> list[float]:
        hex_color = hex_color.lstrip("#")
        if len(hex_color) < 6:
            return [0.2, 0.2, 0.2]
        r = int(hex_color[0:2], 16) / 255.0
        g = int(hex_color[2:4], 16) / 255.0
        b = int(hex_color[4:6], 16) / 255.0
        return [r, g, b]

    def validate_lottie(self, lottie_path: str) -> dict[str, Any]:
        """验证 Lottie JSON 文件"""
        try:
            with open(lottie_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            return {"valid": False, "error": str(e)}

        errors = []
        warnings = []

        # 必要字段检查
        for key in ["v", "fr", "ip", "op", "w", "h", "layers"]:
            if key not in data:
                errors.append(f"Missing required field: {key}")

        # 图层检查
        layers = data.get("layers", [])
        for i, layer in enumerate(layers):
            if "ty" not in layer:
                errors.append(f"Layer {i}: missing 'ty' (type)")
            if "ks" not in layer:
                errors.append(f"Layer {i}: missing 'ks' (keyframes)")

        # 帧范围检查
        if data.get("ip", 0) >= data.get("op", 0):
            errors.append("ip must be less than op")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "layer_count": len(layers),
            "frame_range": f"{data.get('ip', '?')}-{data.get('op', '?')}",
            "resolution": f"{data.get('w', '?')}x{data.get('h', '?')}",
        }
