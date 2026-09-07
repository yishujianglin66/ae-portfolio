"""
core/handdrawn_styler.py — 手绘风格化处理器
=============================================

将普通图像/视频帧转化为手绘风格:
  - 线条提取 (Canny/自适应阈值)
  - 铅笔笔触模拟 (噪声纹理叠加)
  - 纸张纹理叠加
  - 墨水扩散效果
  - 水彩晕染效果
  - 线条抖动模拟 (贝塞尔曲线扰动)

支持的后端:
  1. Pillow + OpenCV (CPU, 无需 GPU)
  2. ComfyUI 工作流 (GPU, 高质量)
  3. 预训练风格迁移模型 (Anime2Sketch, White-box Cartoonization)

用法:
    from core.handdrawn_styler import HanddrawnStyler
    styler = HanddrawnStyler()
    result = styler.stylize_image(
        input_path="photo.png",
        output_path="handdrawn.png",
        style="pencil_sketch",
    )
"""

from __future__ import annotations

import logging
import math
import os
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class HanddrawnStyler:
    """手绘风格化处理器

    提供多种手绘风格:
    - pencil_sketch: 铅笔素描
    - ink_drawing: 墨水画
    - watercolor: 水彩
    - crayon: 蜡笔
    - comic: 漫画
    - doodle: 涂鸦
    """

    STYLES = [
        "pencil_sketch",
        "ink_drawing",
        "watercolor",
        "crayon",
        "comic",
        "doodle",
    ]

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._cv2_available = self._check_cv2()
        self._pil_available = self._check_pil()

    @staticmethod
    def _check_cv2() -> bool:
        try:
            import cv2
            return True
        except ImportError:
            return False

    @staticmethod
    def _check_pil() -> bool:
        try:
            from PIL import Image
            return True
        except ImportError:
            return False

    def check_available(self) -> bool:
        return self._pil_available

    def stylize_image(
        self,
        input_path: str,
        output_path: str = "handdrawn_output.png",
        style: str = "pencil_sketch",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """将图像转化为手绘风格

        Args:
            input_path: 输入图像路径
            output_path: 输出路径
            style: 手绘风格
            params: 额外参数 {intensity, line_width, paper_texture, ...}

        Returns:
            处理结果字典
        """
        if not self._pil_available:
            return {"status": "error", "message": "Pillow not installed"}

        params = params or {}

        if self._cv2_available:
            return self._stylize_cv2(input_path, output_path, style, params)
        else:
            return self._stylize_pil_only(input_path, output_path, style, params)

    def stylize_frame(
        self,
        frame_data,  # numpy array or PIL Image
        style: str = "pencil_sketch",
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        """处理单帧 (用于视频管线)

        Args:
            frame_data: numpy array (H,W,3) 或 PIL Image
            style: 手绘风格
            params: 额外参数

        Returns:
            处理后的帧 (同类型输入)
        """
        import numpy as np
        from PIL import Image

        params = params or {}
        is_numpy = isinstance(frame_data, np.ndarray)

        if is_numpy:
            img = Image.fromarray(frame_data)
        else:
            img = frame_data

        # 应用风格化处理
        result_img = self._apply_style(img, style, params)

        if is_numpy:
            return np.array(result_img)
        return result_img

    def _stylize_cv2(self, input_path, output_path, style, params) -> Dict[str, Any]:
        """使用 OpenCV + Pillow 进行风格化"""
        import cv2
        import numpy as np
        from PIL import Image

        img = cv2.imread(input_path)
        if img is None:
            return {"status": "error", "message": f"Cannot read: {input_path}"}

        intensity = params.get("intensity", 1.0)
        line_width = params.get("line_width", 1)

        if style == "pencil_sketch":
            result = self._pencil_sketch_cv2(img, intensity, line_width)
        elif style == "ink_drawing":
            result = self._ink_drawing_cv2(img, intensity, line_width)
        elif style == "watercolor":
            result = self._watercolor_cv2(img, intensity)
        elif style == "comic":
            result = self._comic_cv2(img, intensity)
        elif style == "crayon":
            result = self._crayon_cv2(img, intensity)
        elif style == "doodle":
            result = self._doodle_cv2(img, intensity, line_width)
        else:
            result = self._pencil_sketch_cv2(img, intensity, line_width)

        # 纸张纹理叠加
        if params.get("paper_texture", True):
            result = self._apply_paper_texture(result, params.get("texture_intensity", 0.3))

        cv2.imwrite(output_path, result)
        return {
            "status": "success",
            "style": style,
            "output_path": output_path,
            "backend": "opencv",
        }

    def _stylize_pil_only(self, input_path, output_path, style, params) -> Dict[str, Any]:
        """仅使用 Pillow 的风格化 (无 OpenCV 降级)"""
        from PIL import Image, ImageFilter, ImageOps

        img = Image.open(input_path).convert("RGB")

        if style in ("pencil_sketch", "doodle"):
            # 灰度 + 边缘检测模拟
            gray = ImageOps.grayscale(img)
            edges = gray.filter(ImageFilter.FIND_EDGES)
            result = ImageOps.invert(edges)
        elif style == "ink_drawing":
            gray = ImageOps.grayscale(img)
            result = ImageOps.posterize(gray, 2)
        else:
            result = img.filter(ImageFilter.SMOOTH)

        result.save(output_path)
        return {
            "status": "success",
            "style": style,
            "output_path": output_path,
            "backend": "pillow_only",
            "note": "Limited quality without OpenCV",
        }

    def _apply_style(self, img, style, params):
        """对 PIL Image 应用风格"""
        from PIL import Image, ImageFilter, ImageOps

        if style in ("pencil_sketch", "doodle"):
            gray = ImageOps.grayscale(img)
            edges = gray.filter(ImageFilter.FIND_EDGES)
            result = ImageOps.invert(edges)
            return result.convert("RGB")
        elif style == "ink_drawing":
            gray = ImageOps.grayscale(img)
            result = ImageOps.posterize(gray, 2)
            return result.convert("RGB")
        else:
            return img.filter(ImageFilter.SMOOTH)

    # ── OpenCV 风格化方法 ──────────────────────────────────────────

    def _pencil_sketch_cv2(self, img, intensity, line_width):
        import cv2
        import numpy as np

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray_blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # 边缘检测
        edges = cv2.Canny(gray_blur, 50 * intensity, 150 * intensity)

        # 反转得到白底黑线
        lines = cv2.bitwise_not(edges)

        # 线条加粗
        if line_width > 1:
            kernel = np.ones((line_width, line_width), np.uint8)
            lines = cv2.erode(lines, kernel, iterations=1)

        # 添加铅笔纹理效果
        sketch = cv2.cvtColor(lines, cv2.COLOR_GRAY2BGR)
        noise = np.random.normal(0, 10, sketch.shape).astype(np.int16)
        sketch = np.clip(sketch.astype(np.int16) + noise, 0, 255).astype(np.uint8)

        return sketch

    def _ink_drawing_cv2(self, img, intensity, line_width):
        import cv2
        import numpy as np

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 自适应阈值 → 墨水效果
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, int(11 * intensity), 2,
        )

        # 墨水扩散
        kernel = np.ones((2, 2), np.uint8)
        binary = cv2.dilate(binary, kernel, iterations=1)

        return cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)

    def _watercolor_cv2(self, img, intensity):
        import cv2

        # 双边滤波 → 水彩平滑
        smooth = cv2.bilateralFilter(img, 9, 75 * intensity, 75 * intensity)

        # 边缘叠加
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 9, 2,
        )
        edges_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        # 混合
        result = cv2.addWeighted(smooth, 0.8, edges_color, 0.2, 0)
        return result

    def _comic_cv2(self, img, intensity):
        import cv2
        import numpy as np

        # 颜色量化
        Z = img.reshape((-1, 3))
        Z = np.float32(Z)
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
        K = int(8 * intensity)
        _, label, center = cv2.kmeans(Z, K, None, criteria, 3, cv2.KMEANS_RANDOM_CENTERS)
        quantized = np.uint8(center[label.flatten()]).reshape(img.shape)

        # 边缘
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 100, 200)
        edge_color = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

        # 叠加
        result = cv2.addWeighted(quantized, 0.7, edge_color, 0.3, 0)
        return result

    def _crayon_cv2(self, img, intensity, line_width):
        import cv2
        import numpy as np

        # 铅笔画效果 + 颜色保留
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        inv = cv2.bitwise_not(gray)
        blur = cv2.GaussianBlur(inv, (0, 0), 3)
        sketch = cv2.addWeighted(gray, 0.7, cv2.bitwise_not(blur), 0.3, 0)

        # 叠加原色
        color_layer = cv2.addWeighted(img, 0.4, img, 0.6, 0)
        sketch_3ch = cv2.cvtColor(sketch, cv2.COLOR_GRAY2BGR)
        result = cv2.addWeighted(sketch_3ch, 0.5, color_layer, 0.5, 0)
        return result

    def _doodle_cv2(self, img, intensity, line_width):
        import cv2
        import numpy as np

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # 强边缘检测
        edges = cv2.Canny(gray, 30 * intensity, 100 * intensity)

        # 线条抖动 (模拟手绘不稳定感)
        rows, cols = edges.shape
        jitter = np.random.randint(-2, 3, (rows, cols), dtype=np.int16)
        jittered = np.clip(edges.astype(np.int16) + jitter * 20, 0, 255).astype(np.uint8)

        return cv2.cvtColor(jittered, cv2.COLOR_GRAY2BGR)

    def _apply_paper_texture(self, img, intensity):
        import cv2
        import numpy as np

        h, w = img.shape[:2]
        # 生成纸张噪声纹理
        noise = np.random.normal(128, 30 * intensity, (h, w, 3)).astype(np.int16)
        # 混合
        result = np.clip(img.astype(np.int16) * 0.9 + noise * 0.1, 0, 255)
        return result.astype(np.uint8)


# ── 视频帧序列风格化 ──────────────────────────────────────────

    def stylize_video_frames(
        self,
        input_dir: str,
        output_dir: str,
        style: str = "pencil_sketch",
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """批量风格化视频帧序列

        Args:
            input_dir: 帧图像目录
            output_dir: 输出目录
            style: 手绘风格
            params: 额外参数

        Returns:
            处理结果
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        frames = sorted(input_path.glob("*.png")) + sorted(input_path.glob("*.jpg"))
        if not frames:
            return {"status": "error", "message": f"No frames found in {input_dir}"}

        processed = 0
        for frame in frames:
            out_frame = output_path / frame.name
            result = self.stylize_image(str(frame), str(out_frame), style, params)
            if result.get("status") == "success":
                processed += 1

        return {
            "status": "success",
            "total_frames": len(frames),
            "processed_frames": processed,
            "style": style,
            "output_dir": str(output_dir),
        }
