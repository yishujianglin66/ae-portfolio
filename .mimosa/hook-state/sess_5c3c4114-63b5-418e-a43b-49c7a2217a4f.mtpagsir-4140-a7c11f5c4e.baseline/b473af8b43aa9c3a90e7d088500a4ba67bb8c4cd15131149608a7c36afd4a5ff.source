"""图片分析器 - 分析图片亮度、颜色等特征，为自适应调色提供依据

功能：
1. 亮度分析（平均亮度、直方图分布）
2. 颜色分析（主色调、饱和度、色温）
3. 对比度分析
4. 生成自适应调色建议
"""
import os
import json
import math
from typing import Dict, List, Tuple, Any


class ImageAnalyzer:
    """图片分析器 - 使用 Pillow 分析图片特征"""
    
    def __init__(self):
        self._pil_available = False
        self._cv2_available = False
        try:
            from PIL import Image, ImageStat
            self._Image = Image
            self._ImageStat = ImageStat
            self._pil_available = True
        except ImportError:
            pass
        
        try:
            import cv2
            import numpy as np
            self._cv2 = cv2
            self._np = np
            self._cv2_available = True
        except ImportError:
            pass
    
    def analyze(self, image_path: str) -> Dict[str, Any]:
        """分析图片，返回完整的特征数据
        
        Args:
            image_path: 图片路径
            
        Returns:
            包含亮度、颜色、对比度等特征的字典
        """
        if not os.path.exists(image_path):
            return {"error": f"Image not found: {image_path}"}
        
        # 优先使用 Pillow（对中文路径支持更好）
        if self._pil_available:
            return self._analyze_with_pil(image_path)
        elif self._cv2_available:
            return self._analyze_with_cv2(image_path)
        else:
            return self._analyze_fallback(image_path)
    
    def _analyze_with_cv2(self, image_path: str) -> Dict[str, Any]:
        """使用 OpenCV 分析图片"""
        cv2 = self._cv2
        np = self._np
        
        img = cv2.imread(image_path)
        if img is None:
            return {"error": f"Cannot read image: {image_path}"}
        
        h, w = img.shape[:2]
        
        # 转换为不同颜色空间
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img_hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        img_lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        
        # 亮度分析 (L channel in LAB)
        l_channel = img_lab[:, :, 0]
        brightness_mean = float(np.mean(l_channel))
        brightness_std = float(np.std(l_channel))
        brightness_min = float(np.min(l_channel))
        brightness_max = float(np.max(l_channel))
        
        # 亮度分布百分比
        dark_pixels = float(np.sum(l_channel < 50)) / (h * w) * 100
        mid_pixels = float(np.sum((l_channel >= 50) & (l_channel < 200))) / (h * w) * 100
        bright_pixels = float(np.sum(l_channel >= 200)) / (h * w) * 100
        
        # 颜色分析
        h_channel = img_hsv[:, :, 0]
        s_channel = img_hsv[:, :, 1]
        v_channel = img_hsv[:, :, 2]
        
        saturation_mean = float(np.mean(s_channel))
        value_mean = float(np.mean(v_channel))
        
        # 主色调分析（计算色相直方图）
        hist_hue = cv2.calcHist([img_hsv], [0], None, [180], [0, 180])
        dominant_hue = int(np.argmax(hist_hue))
        
        # 色温估计（基于R/B比例）
        r_mean = float(np.mean(img_rgb[:, :, 0]))
        g_mean = float(np.mean(img_rgb[:, :, 1]))
        b_mean = float(np.mean(img_rgb[:, :, 2]))
        rb_ratio = r_mean / (b_mean + 1)
        
        # 对比度分析
        contrast = (brightness_max - brightness_min) / (brightness_max + brightness_min + 1)
        
        # 生成自适应调色建议
        suggestions = self._generate_suggestions(
            brightness_mean=brightness_mean,
            brightness_std=brightness_std,
            saturation_mean=saturation_mean,
            contrast=contrast,
            rb_ratio=rb_ratio,
            dark_pixels=dark_pixels,
            bright_pixels=bright_pixels
        )
        
        return {
            "image_path": image_path,
            "size": {"width": w, "height": h},
            "brightness": {
                "mean": round(brightness_mean, 2),
                "std": round(brightness_std, 2),
                "min": round(brightness_min, 2),
                "max": round(brightness_max, 2),
                "dark_percent": round(dark_pixels, 1),
                "mid_percent": round(mid_pixels, 1),
                "bright_percent": round(bright_pixels, 1),
            },
            "color": {
                "dominant_hue": dominant_hue,
                "saturation_mean": round(saturation_mean, 2),
                "value_mean": round(value_mean, 2),
                "r_mean": round(r_mean, 2),
                "g_mean": round(g_mean, 2),
                "b_mean": round(b_mean, 2),
                "rb_ratio": round(rb_ratio, 3),
            },
            "contrast": round(contrast, 3),
            "suggestions": suggestions,
        }
    
    def _analyze_with_pil(self, image_path: str) -> Dict[str, Any]:
        """使用 Pillow 分析图片"""
        Image = self._Image
        ImageStat = self._ImageStat
        
        img = Image.open(image_path)
        w, h = img.size
        
        img_rgb = img.convert("RGB")
        img_hsv = img.convert("HSV")
        img_gray = img.convert("L")
        
        stat_rgb = ImageStat.Stat(img_rgb)
        stat_hsv = ImageStat.Stat(img_hsv)
        stat_gray = ImageStat.Stat(img_gray)
        
        # 亮度分析
        brightness_mean = stat_gray.mean[0]
        brightness_std = stat_gray.stddev[0]
        extrema = stat_gray.extrema[0]
        brightness_min = extrema[0]
        brightness_max = extrema[1]
        
        # 颜色分析
        r_mean, g_mean, b_mean = stat_rgb.mean
        h_mean, s_mean, v_mean = stat_hsv.mean
        
        rb_ratio = r_mean / (b_mean + 1)
        
        # 对比度
        contrast = (brightness_max - brightness_min) / (brightness_max + brightness_min + 1)
        
        suggestions = self._generate_suggestions(
            brightness_mean=brightness_mean,
            brightness_std=brightness_std,
            saturation_mean=s_mean,
            contrast=contrast,
            rb_ratio=rb_ratio,
            dark_pixels=0,
            bright_pixels=0
        )
        
        return {
            "image_path": image_path,
            "size": {"width": w, "height": h},
            "brightness": {
                "mean": round(brightness_mean, 2),
                "std": round(brightness_std, 2),
                "min": brightness_min,
                "max": brightness_max,
            },
            "color": {
                "r_mean": round(r_mean, 2),
                "g_mean": round(g_mean, 2),
                "b_mean": round(b_mean, 2),
                "saturation_mean": round(s_mean, 2),
                "rb_ratio": round(rb_ratio, 3),
            },
            "contrast": round(contrast, 3),
            "suggestions": suggestions,
        }
    
    def _analyze_fallback(self, image_path: str) -> Dict[str, Any]:
        """无图像处理库时的降级分析（仅基于文件大小估算）"""
        file_size = os.path.getsize(image_path)
        
        return {
            "image_path": image_path,
            "file_size": file_size,
            "brightness": {"mean": 128, "note": "estimated"},
            "suggestions": {
                "brightness_adjust": 10,
                "contrast_adjust": 10,
                "saturation_adjust": 5,
                "vignette_intensity": 0.3,
            }
        }
    
    def _generate_suggestions(self, **kwargs) -> Dict[str, Any]:
        """根据分析结果生成自适应调色建议
        
        Returns:
            包含各种调色参数调整建议的字典
        """
        brightness_mean = kwargs.get("brightness_mean", 128)
        brightness_std = kwargs.get("brightness_std", 50)
        saturation_mean = kwargs.get("saturation_mean", 128)
        contrast = kwargs.get("contrast", 0.5)
        rb_ratio = kwargs.get("rb_ratio", 1.0)
        dark_pixels = kwargs.get("dark_pixels", 20)
        bright_pixels = kwargs.get("bright_pixels", 10)
        
        # 亮度调整：图片越暗，需要提亮越多
        # 理想平均亮度约为 128 (0-255)
        brightness_diff = 128 - brightness_mean
        brightness_adjust = max(-30, min(30, brightness_diff * 0.3))
        
        # 对比度调整：对比越低，提升越多
        # 理想对比度约为 0.6-0.8
        contrast_adjust = 0
        if contrast < 0.5:
            contrast_adjust = (0.6 - contrast) * 50
        elif contrast > 0.85:
            contrast_adjust = -(contrast - 0.85) * 30
        
        # 饱和度调整
        saturation_adjust = 0
        if saturation_mean < 50:
            saturation_adjust = 15
        elif saturation_mean > 180:
            saturation_adjust = -10
        
        # 暗角强度：图片越亮，暗角可以稍强
        vignette_intensity = 0.3
        if brightness_mean > 150:
            vignette_intensity = 0.4
        elif brightness_mean < 80:
            vignette_intensity = 0.2
        
        # 色温调整：rb_ratio > 1 偏暖，< 1 偏冷
        warmth_adjust = 0
        if rb_ratio < 0.9:
            warmth_adjust = 5  # 偏冷，加暖
        elif rb_ratio > 1.1:
            warmth_adjust = -3  # 偏暖，稍减
        
        # 光效强度
        flare_intensity = 0.6
        if brightness_mean > 160:
            flare_intensity = 0.4  # 亮图减弱光效
        elif brightness_mean < 80:
            flare_intensity = 0.8  # 暗图增强光效
        
        return {
            "brightness_adjust": round(brightness_adjust, 1),
            "contrast_adjust": round(contrast_adjust, 1),
            "saturation_adjust": round(saturation_adjust, 1),
            "vignette_intensity": round(vignette_intensity, 2),
            "warmth_adjust": round(warmth_adjust, 1),
            "flare_intensity": round(flare_intensity, 2),
            "brightness_level": "dark" if brightness_mean < 80 else ("bright" if brightness_mean > 160 else "normal"),
            "contrast_level": "low" if contrast < 0.4 else ("high" if contrast > 0.8 else "normal"),
            "saturation_level": "low" if saturation_mean < 50 else ("high" if saturation_mean > 180 else "normal"),
            "temperature": "warm" if rb_ratio > 1.05 else ("cool" if rb_ratio < 0.95 else "neutral"),
        }
    
    def analyze_batch(self, image_paths: List[str]) -> List[Dict[str, Any]]:
        """批量分析图片
        
        Args:
            image_paths: 图片路径列表
            
        Returns:
            每张图片的分析结果列表
        """
        results = []
        for path in image_paths:
            results.append(self.analyze(path))
        return results
    
    def get_average_suggestions(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算多张图片的平均调色建议
        
        Args:
            results: 多张图片的分析结果
            
        Returns:
            平均调色建议
        """
        valid_results = [r for r in results if "suggestions" in r and "error" not in r]
        if not valid_results:
            return {
                "brightness_adjust": 10,
                "contrast_adjust": 10,
                "saturation_adjust": 5,
                "vignette_intensity": 0.3,
                "flare_intensity": 0.6,
            }
        
        def avg(key):
            vals = [r["suggestions"][key] for r in valid_results if key in r["suggestions"]]
            return sum(vals) / len(vals) if vals else 0
        
        return {
            "brightness_adjust": round(avg("brightness_adjust"), 1),
            "contrast_adjust": round(avg("contrast_adjust"), 1),
            "saturation_adjust": round(avg("saturation_adjust"), 1),
            "vignette_intensity": round(avg("vignette_intensity"), 2),
            "flare_intensity": round(avg("flare_intensity"), 2),
            "num_images_analyzed": len(valid_results),
        }


def main():
    """测试图片分析器"""
    analyzer = ImageAnalyzer()
    
    test_dir = r"D:\AE-Work\视频素材库\frames"
    if os.path.exists(test_dir):
        import glob
        frames = sorted(glob.glob(os.path.join(test_dir, "frame_*.png")))
        if frames:
            print(f"分析 {len(frames)} 张图片...")
            
            # 分析前3张
            for i, frame in enumerate(frames[:3]):
                result = analyzer.analyze(frame)
                print(f"\n[{i+1}] {os.path.basename(frame)}:")
                if "error" in result:
                    print(f"  错误: {result['error']}")
                else:
                    print(f"  尺寸: {result['size']['width']}x{result['size']['height']}")
                    print(f"  亮度: mean={result['brightness']['mean']:.1f}, min={result['brightness']['min']}, max={result['brightness']['max']}")
                    print(f"  对比度: {result['contrast']}")
                    sug = result["suggestions"]
                    print(f"  调色建议:")
                    print(f"    亮度调整: {sug['brightness_adjust']}")
                    print(f"    对比度调整: {sug['contrast_adjust']}")
                    print(f"    饱和度调整: {sug['saturation_adjust']}")
                    print(f"    暗角强度: {sug['vignette_intensity']}")
                    print(f"    光效强度: {sug['flare_intensity']}")
                    print(f"    亮度等级: {sug['brightness_level']}")
            
            # 批量分析并计算平均
            print("\n" + "="*50)
            print("批量分析平均建议:")
            all_results = analyzer.analyze_batch(frames)
            avg_sug = analyzer.get_average_suggestions(all_results)
            print(json.dumps(avg_sug, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
