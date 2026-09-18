"""
material_effects.py
木偶风格化系统 - 材质质感效果生成器

生成各种材质的 AE 效果组合，包括木质、陶瓷、布偶、黏土等。

每个效果项包含：
- effectName / matchName: AE 效果的匹配名
- settings: 效果参数设置
- intensity_param: 强度控制参数名
- intensity_factor: 强度因子
"""

from dataclasses import dataclass
from typing import Any, Dict, List

__all__ = [
    "MaterialEffects",
]


class MaterialEffects:
    """材质质感效果生成器

    生成各种木偶材质的 AE 效果组合，支持强度调节。
    """

    def __init__(self) -> None:
        """初始化材质效果生成器"""
        self._effect_catalog = {
            "wooden_puppet": self.wooden_puppet,
            "ceramic_puppet": self.ceramic_puppet,
            "cloth_puppet": self.cloth_puppet,
            "clay_puppet": self.clay_puppet,
            "metal_puppet": self.metal_puppet,
        }

    def get_available_materials(self) -> list[str]:
        """获取所有可用材质列表

        Returns:
            材质名称列表
        """
        return list(self._effect_catalog.keys())

    def generate(self, material_type: str, intensity: float = 1.0,
                 layer_name: str = "layer_001") -> list[dict[str, Any]]:
        """生成指定材质的效果列表

        Args:
            material_type: 材质类型名称
            intensity: 效果强度 (0.0 - 2.0)
            layer_name: 图层名称

        Returns:
            AE 效果列表

        Raises:
            ValueError: 当材质类型不存在时
        """
        if material_type not in self._effect_catalog:
            raise ValueError(
                f"Unknown material type: {material_type}. "
                f"Available: {self.get_available_materials()}"
            )
        generator = self._effect_catalog[material_type]
        return generator(intensity, layer_name)

    @staticmethod
    def _scale_intensity(base_value: float, intensity: float,
                         factor: float) -> float:
        """根据强度缩放参数值

        Args:
            base_value: 基准值
            intensity: 强度系数 (0.0 - 2.0)
            factor: 最大变化幅度

        Returns:
            缩放后的值
        """
        return base_value + (factor - base_value) * (intensity - 0.5) * 2

    # ------------------------------------------------------------------
    # 木质木偶效果
    # ------------------------------------------------------------------
    @staticmethod
    def wooden_puppet(intensity: float = 1.0,
                      layer_name: str = "layer_001") -> list[dict[str, Any]]:
        """木质木偶效果

        效果组合：
        - Find Edges（边缘检测）
        - Posterize（色调分离，8-16级）
        - Tint（着色，暖棕色系）
        - 木纹纹理叠加（Fractal Noise + 叠加模式）
        - 高光描边（Glow + 边缘强化）

        Args:
            intensity: 效果强度 (0.0 - 2.0)
            layer_name: 图层名称

        Returns:
            AE 效果列表
        """
        posterize_levels = int(
            MaterialEffects._scale_intensity(12, intensity, 8)
        )
        posterize_levels = max(4, min(32, posterize_levels))

        return [
            {
                "effectName": "ADBE Find Edges",
                "matchName": "ADBE Find Edges",
                "settings": {
                    "Invert": False,
                    "Blend With Original": MaterialEffects._scale_intensity(30, intensity, 10),
                },
                "intensity_param": "Blend With Original",
                "intensity_factor": 10.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Posterize",
                "matchName": "ADBE Posterize",
                "settings": {
                    "Level": float(posterize_levels),
                },
                "intensity_param": "Level",
                "intensity_factor": 8.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Tint 2",
                "matchName": "ADBE Tint 2",
                "settings": {
                    "Map Black To": [0.35, 0.2, 0.1, 1.0],
                    "Map White To": [0.9, 0.75, 0.5, 1.0],
                    "Amount To Tint": MaterialEffects._scale_intensity(80, intensity, 100),
                },
                "intensity_param": "Amount To Tint",
                "intensity_factor": 100.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Fractal Noise 2",
                "matchName": "ADBE Fractal Noise 2",
                "settings": {
                    "Fractal Type": "Wood",
                    "Noise Type": "Spline",
                    "Contrast": MaterialEffects._scale_intensity(150, intensity, 200),
                    "Brightness": 20.0,
                    "Scale": 800.0,
                    "Complexity": 5.0,
                    "Evolution": 0.0,
                    "Offset (Turbulence)": [0, 0],
                },
                "intensity_param": "Contrast",
                "intensity_factor": 200.0,
                "layer_name": layer_name,
                "blend_mode": "Multiply",
            },
            {
                "effectName": "ADBE Glo2",
                "matchName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 60.0,
                    "Glow Radius": MaterialEffects._scale_intensity(10, intensity, 20),
                    "Glow Intensity": MaterialEffects._scale_intensity(0.8, intensity, 1.5),
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Sawtooth B>A",
                    "Color A": [1.0, 0.85, 0.6, 1.0],
                    "Color B": [0.8, 0.5, 0.25, 1.0],
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 1.5,
                "layer_name": layer_name,
            },
        ]

    # ------------------------------------------------------------------
    # 陶瓷木偶效果
    # ------------------------------------------------------------------
    @staticmethod
    def ceramic_puppet(intensity: float = 1.0,
                       layer_name: str = "layer_001") -> list[dict[str, Any]]:
        """陶瓷木偶效果

        效果组合：
        - Gaussian Blur（轻微模糊）
        - Curves（S曲线增强对比）
        - Glow（瓷釉高光）
        - Color Balance（冷色调）

        Args:
            intensity: 效果强度 (0.0 - 2.0)
            layer_name: 图层名称

        Returns:
            AE 效果列表
        """
        return [
            {
                "effectName": "ADBE Gaussian Blur 2",
                "matchName": "ADBE Gaussian Blur 2",
                "settings": {
                    "Blurriness": MaterialEffects._scale_intensity(2, intensity, 5),
                    "Blur Dimensions": "Horizontal and Vertical",
                    "Repeat Edge Pixels": True,
                },
                "intensity_param": "Blurriness",
                "intensity_factor": 5.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE CurvesCustom",
                "matchName": "ADBE CurvesCustom",
                "settings": {
                    "Channel": "RGB",
                    "Curve": [
                        [0.0, 0.0],
                        [0.3, 0.25],
                        [0.5, 0.5],
                        [0.7, 0.75],
                        [1.0, 1.0],
                    ],
                },
                "intensity_param": "Curve",
                "intensity_factor": 1.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Glo2",
                "matchName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 70.0,
                    "Glow Radius": MaterialEffects._scale_intensity(20, intensity, 35),
                    "Glow Intensity": MaterialEffects._scale_intensity(1.0, intensity, 2.0),
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Triangle A>B",
                    "Color A": [0.9, 0.95, 1.0, 1.0],
                    "Color B": [0.7, 0.8, 0.95, 1.0],
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 2.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Color Balance",
                "matchName": "ADBE Color Balance",
                "settings": {
                    "Shadow Red Balance": MaterialEffects._scale_intensity(-5, intensity, -10),
                    "Shadow Green Balance": 2.0,
                    "Shadow Blue Balance": MaterialEffects._scale_intensity(8, intensity, 15),
                    "Midtone Red Balance": MaterialEffects._scale_intensity(-8, intensity, -15),
                    "Midtone Green Balance": 3.0,
                    "Midtone Blue Balance": MaterialEffects._scale_intensity(12, intensity, 20),
                    "Hilight Red Balance": MaterialEffects._scale_intensity(-3, intensity, -8),
                    "Hilight Green Balance": 1.0,
                    "Hilight Blue Balance": MaterialEffects._scale_intensity(5, intensity, 10),
                    "Preserve Luminosity": True,
                },
                "intensity_param": "Midtone Blue Balance",
                "intensity_factor": 20.0,
                "layer_name": layer_name,
            },
        ]

    # ------------------------------------------------------------------
    # 布偶/毛绒效果
    # ------------------------------------------------------------------
    @staticmethod
    def cloth_puppet(intensity: float = 1.0,
                     layer_name: str = "layer_001") -> list[dict[str, Any]]:
        """布偶/毛绒效果

        效果组合：
        - Roughen Edges（边缘粗糙）
        - Noise（杂色纹理）
        - Fast Blur（柔边）

        Args:
            intensity: 效果强度 (0.0 - 2.0)
            layer_name: 图层名称

        Returns:
            AE 效果列表
        """
        return [
            {
                "effectName": "ADBE Roughen Edges",
                "matchName": "ADBE Roughen Edges",
                "settings": {
                    "Edge Type": "Roughen",
                    "Border": MaterialEffects._scale_intensity(8, intensity, 15),
                    "Edge Sharpness": 0.5,
                    "Fractal Influence": MaterialEffects._scale_intensity(0.8, intensity, 1.0),
                    "Scale": 100.0,
                    "Stretch Width or Height": 0.0,
                    "Offset (Turbulence)": [0, 0],
                    "Complexity": 3.0,
                    "Evolution": 0.0,
                },
                "intensity_param": "Border",
                "intensity_factor": 15.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Noise HLS",
                "matchName": "ADBE Noise HLS",
                "settings": {
                    "Noise": "Uniform",
                    "Hue": MaterialEffects._scale_intensity(5, intensity, 10),
                    "Lightness": MaterialEffects._scale_intensity(8, intensity, 15),
                    "Saturation": 3.0,
                    "Grain Size": 3.0,
                },
                "intensity_param": "Lightness",
                "intensity_factor": 15.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Fast Blur",
                "matchName": "ADBE Fast Blur",
                "settings": {
                    "Blurriness": MaterialEffects._scale_intensity(2, intensity, 4),
                    "Blur Dimensions": "Horizontal and Vertical",
                    "Repeat Edge Pixels": True,
                },
                "intensity_param": "Blurriness",
                "intensity_factor": 4.0,
                "layer_name": layer_name,
            },
        ]

    # ------------------------------------------------------------------
    # 黏土/橡皮泥效果
    # ------------------------------------------------------------------
    @staticmethod
    def clay_puppet(intensity: float = 1.0,
                    layer_name: str = "layer_001") -> list[dict[str, Any]]:
        """黏土/橡皮泥效果

        效果组合：
        - Simple Choker（边缘圆润）
        - Noise（指纹杂色）
        - Curves（柔和对比）

        Args:
            intensity: 效果强度 (0.0 - 2.0)
            layer_name: 图层名称

        Returns:
            AE 效果列表
        """
        return [
            {
                "effectName": "ADBE Simple Choker",
                "matchName": "ADBE Simple Choker",
                "settings": {
                    "Choke Matte": MaterialEffects._scale_intensity(-3, intensity, -8),
                },
                "intensity_param": "Choke Matte",
                "intensity_factor": -8.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Noise HLS",
                "matchName": "ADBE Noise HLS",
                "settings": {
                    "Noise": "Grain",
                    "Hue": 2.0,
                    "Lightness": MaterialEffects._scale_intensity(6, intensity, 12),
                    "Saturation": 2.0,
                    "Grain Size": MaterialEffects._scale_intensity(2, intensity, 5),
                },
                "intensity_param": "Lightness",
                "intensity_factor": 12.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE CurvesCustom",
                "matchName": "ADBE CurvesCustom",
                "settings": {
                    "Channel": "RGB",
                    "Curve": [
                        [0.0, 0.05],
                        [0.25, 0.2],
                        [0.5, 0.45],
                        [0.75, 0.7],
                        [1.0, 0.95],
                    ],
                },
                "intensity_param": "Curve",
                "intensity_factor": 1.0,
                "layer_name": layer_name,
            },
        ]

    # ------------------------------------------------------------------
    # 金属木偶效果
    # ------------------------------------------------------------------
    @staticmethod
    def metal_puppet(intensity: float = 1.0,
                     layer_name: str = "layer_001") -> list[dict[str, Any]]:
        """金属木偶效果

        效果组合：
        - Find Edges（金属边缘线）
        - Curves（高对比度金属质感）
        - Glow（金属高光）
        - Color Balance（冷钢色调）

        Args:
            intensity: 效果强度 (0.0 - 2.0)
            layer_name: 图层名称

        Returns:
            AE 效果列表
        """
        return [
            {
                "effectName": "ADBE Find Edges",
                "matchName": "ADBE Find Edges",
                "settings": {
                    "Invert": True,
                    "Blend With Original": MaterialEffects._scale_intensity(50, intensity, 30),
                },
                "intensity_param": "Blend With Original",
                "intensity_factor": 30.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE CurvesCustom",
                "matchName": "ADBE CurvesCustom",
                "settings": {
                    "Channel": "RGB",
                    "Curve": [
                        [0.0, 0.0],
                        [0.2, 0.1],
                        [0.4, 0.35],
                        [0.6, 0.65],
                        [0.8, 0.9],
                        [1.0, 1.0],
                    ],
                },
                "intensity_param": "Curve",
                "intensity_factor": 1.0,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Glo2",
                "matchName": "ADBE Glo2",
                "settings": {
                    "Glow Threshold": 40.0,
                    "Glow Radius": MaterialEffects._scale_intensity(15, intensity, 25),
                    "Glow Intensity": MaterialEffects._scale_intensity(1.2, intensity, 2.5),
                    "Composite Original": "On Top",
                    "Glow Colors": "A & B Colors",
                    "Color Looping": "Triangle A>B",
                    "Color A": [0.9, 0.95, 1.0, 1.0],
                    "Color B": [0.5, 0.6, 0.7, 1.0],
                },
                "intensity_param": "Glow Intensity",
                "intensity_factor": 2.5,
                "layer_name": layer_name,
            },
            {
                "effectName": "ADBE Color Balance",
                "matchName": "ADBE Color Balance",
                "settings": {
                    "Shadow Red Balance": MaterialEffects._scale_intensity(-10, intensity, -18),
                    "Shadow Green Balance": MaterialEffects._scale_intensity(-5, intensity, -10),
                    "Shadow Blue Balance": MaterialEffects._scale_intensity(5, intensity, 12),
                    "Midtone Red Balance": MaterialEffects._scale_intensity(-8, intensity, -15),
                    "Midtone Green Balance": MaterialEffects._scale_intensity(-3, intensity, -8),
                    "Midtone Blue Balance": MaterialEffects._scale_intensity(8, intensity, 15),
                    "Hilight Red Balance": MaterialEffects._scale_intensity(-3, intensity, -6),
                    "Hilight Green Balance": 0.0,
                    "Hilight Blue Balance": MaterialEffects._scale_intensity(3, intensity, 8),
                    "Preserve Luminosity": True,
                },
                "intensity_param": "Midtone Blue Balance",
                "intensity_factor": 15.0,
                "layer_name": layer_name,
            },
        ]


# ----------------------------------------------------------------------
# 模块自测
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("MaterialEffects 模块自测")
    print("=" * 60)

    me = MaterialEffects()

    print(f"\n可用材质列表 ({len(me.get_available_materials())} 种):")
    for mat in me.get_available_materials():
        print(f"  - {mat}")

    test_materials = ["wooden_puppet", "ceramic_puppet", "cloth_puppet",
                      "clay_puppet", "metal_puppet"]

    for material in test_materials:
        print(f"\n{'─' * 50}")
        print(f"测试材质: {material}")
        print(f"{'─' * 50}")
        effects = me.generate(material, intensity=1.0, layer_name="test_layer")
        print(f"  效果数量: {len(effects)}")
        for i, eff in enumerate(effects, 1):
            print(f"  {i}. {eff.get('effectName', 'N/A')}")
            print(f"     matchName: {eff.get('matchName', 'N/A')}")
            print(f"     intensity_param: {eff.get('intensity_param', 'N/A')}")

    print(f"\n{'=' * 60}")
    print("测试强度缩放 (intensity=0.5 vs 1.5):")
    print(f"{'=' * 60}")
    wooden_low = me.wooden_puppet(intensity=0.5)
    wooden_high = me.wooden_puppet(intensity=1.5)
    for low, high in zip(wooden_low, wooden_high):
        param = low["intensity_param"]
        low_val = low["settings"][param]
        high_val = high["settings"][param]
        if isinstance(low_val, (int, float)):
            print(f"  {low['effectName']} - {param}: {low_val} -> {high_val}")

    print("\n自测完成 ✓")
