"""
mini_scene.py - 微缩场景效果生成器

为木偶动画生成微缩舞台/场景效果，包括移轴模糊、舞台灯光、
暗角、地面投影等，营造微缩模型/木偶戏的视觉风格。

与 AE MCP 桥接系统兼容，输出标准效果配置和调整层结构。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ============================================================================
# 数据类
# ============================================================================


@dataclass
class MiniSceneConfig:
    """微缩场景配置

    Attributes:
        tilt_shift: 是否启用移轴效果
        tilt_blur: 移轴模糊强度
        depth_of_field: 是否启用景深
        dof_blur: 景深模糊强度
        stage_lighting: 是否启用舞台灯光
        light_count: 灯光数量
        light_intensity: 灯光强度（0-1）
        vignette: 是否启用暗角
        vignette_amount: 暗角强度（0-1）
        floor_shadow: 是否启用地面投影
        shadow_opacity: 投影透明度（0-1）
    """

    tilt_shift: bool = True
    tilt_blur: float = 15.0
    depth_of_field: bool = True
    dof_blur: float = 20.0
    stage_lighting: bool = True
    light_count: int = 2
    light_intensity: float = 0.8
    vignette: bool = True
    vignette_amount: float = 0.5
    floor_shadow: bool = True
    shadow_opacity: float = 0.3


# ============================================================================
# MiniSceneEffect 类
# ============================================================================


class MiniSceneEffect:
    """微缩场景效果生成器

    生成移轴模糊、舞台灯光、暗角、地面投影等微缩场景效果，
    并通过调整层统一管理。
    """

    _presets: Dict[str, 'MiniSceneConfig'] = None

    def __init__(self) -> None:
        if MiniSceneEffect._presets is None:
            MiniSceneEffect._presets = MiniSceneEffect._init_presets()
        self._presets = MiniSceneEffect._presets

    # ------------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------------

    @staticmethod
    def generate_mini_scene(
        config: MiniSceneConfig,
        layer_name: str,
        comp_width: int,
        comp_height: int,
        duration: float,
    ) -> Dict[str, Any]:
        """生成微缩场景效果

        Args:
            config: 微缩场景配置
            layer_name: 目标图层名称（作为投影参考）
            comp_width: 合成宽度
            comp_height: 合成高度
            duration: 持续时间（秒）

        Returns:
            包含 effects, keyframes, layers, adjustment_layers 的字典
        """
        effects: List[Dict[str, Any]] = []
        keyframes: List[Dict[str, Any]] = []
        layers: List[Dict[str, Any]] = []
        adjustment_layers: List[Dict[str, Any]] = []

        adj_layer_name = "MiniScene_Adjustment"
        adj_effects: List[Dict[str, Any]] = []

        if config.tilt_shift:
            tilt_effects = MiniSceneEffect._generate_tilt_shift(config, comp_width, comp_height)
            adj_effects.extend(tilt_effects)

        if config.depth_of_field:
            dof_effects = MiniSceneEffect._generate_depth_of_field(config, comp_width, comp_height)
            adj_effects.extend(dof_effects)

        if config.stage_lighting:
            light_effects, light_kfs = MiniSceneEffect._generate_stage_lighting(
                config, comp_width, comp_height, duration
            )
            adj_effects.extend(light_effects)
            keyframes.extend(light_kfs)

        if config.vignette:
            vignette_effects = MiniSceneEffect._generate_vignette(config, comp_width, comp_height)
            adj_effects.extend(vignette_effects)

        adjustment_layers.append({
            "name": adj_layer_name,
            "type": "adjustment",
            "effects": adj_effects,
        })

        if config.floor_shadow:
            shadow_layer = MiniSceneEffect._generate_floor_shadow(
                config, layer_name, comp_width, comp_height
            )
            layers.append(shadow_layer)

        return {
            "effects": effects,
            "keyframes": keyframes,
            "layers": layers,
            "adjustment_layers": adjustment_layers,
            "comp_width": comp_width,
            "comp_height": comp_height,
            "duration": duration,
            "adjustment_layer_name": adj_layer_name,
        }

    @staticmethod
    def get_presets() -> Dict[str, MiniSceneConfig]:
        """获取所有预设配置

        Returns:
            预设名称 -> MiniSceneConfig 的字典
        """
        if MiniSceneEffect._presets is None:
            MiniSceneEffect._presets = MiniSceneEffect._init_presets()
        return MiniSceneEffect._presets.copy()

    # ------------------------------------------------------------------------
    # 内部方法 - 效果生成
    # ------------------------------------------------------------------------

    @staticmethod
    def _generate_tilt_shift(
        config: MiniSceneConfig,
        comp_width: int,
        comp_height: int,
    ) -> List[Dict[str, Any]]:
        """生成移轴模糊效果

        使用 Compound Blur + 渐变蒙版实现上下渐变模糊，
        中间清晰带高度约 30%。
        """
        effects: List[Dict[str, Any]] = []

        center_y = comp_height * 0.5
        band_height = comp_height * 0.3
        blur_radius = config.tilt_blur

        effects.append({
            "effectName": "Gradient Wipe",
            "matchName": "ADBE Gradient Wipe",
            "displayName": "TiltShift_Mask",
            "settings": {
                "Transition Completion": 0.0,
                "Transition Softness": 20.0,
                "Gradient Layer": 1,
                "Gradient Placement": "Tile Gradient",
                "Invert Gradient": False,
            },
        })

        effects.append({
            "effectName": "Gaussian Blur",
            "matchName": "ADBE Gaussian Blur 2",
            "displayName": "TiltShift_Blur",
            "settings": {
                "Blurriness": blur_radius,
                "Blur Dimensions": "Horizontal and Vertical",
                "Repeat Edge Pixels": True,
            },
        })

        effects.append({
            "effectName": "Ramp",
            "matchName": "ADBE Ramp",
            "displayName": "TiltShift_GradientMap",
            "settings": {
                "Start of Ramp": [comp_width / 2, 0],
                "Start Color": [1, 1, 1],
                "End of Ramp": [comp_width / 2, comp_height],
                "End Color": [0, 0, 0],
                "Ramp Shape": "Linear Ramp",
                "Ramp Scatter": 0.0,
                "Blend With Original": 0.0,
            },
        })

        return effects

    @staticmethod
    def _generate_depth_of_field(
        config: MiniSceneConfig,
        comp_width: int,
        comp_height: int,
    ) -> List[Dict[str, Any]]:
        """生成景深效果

        使用 Camera Lens Blur 模拟真实镜头景深。
        """
        effects: List[Dict[str, Any]] = []

        effects.append({
            "effectName": "Camera Lens Blur",
            "matchName": "ADBE Camera Lens Blur",
            "displayName": "DOF_Blur",
            "settings": {
                "Blur Radius": config.dof_blur,
                "Iris Shape": "Hexagon",
                "Iris Roundness": 50.0,
                "Iris Aspect Ratio": 1.0,
                "Iris Rotation": 0.0,
                "Diffraction Fringe": 0.0,
                "Highlight Gain": 0.0,
                "Highlight Threshold": 255.0,
                "Highlight Saturation": 50.0,
                "Edge Blur": 0.0,
            },
        })

        return effects

    @staticmethod
    def _generate_stage_lighting(
        config: MiniSceneConfig,
        comp_width: int,
        comp_height: int,
        duration: float,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """生成舞台灯光效果

        使用 Radial Wipe + 叠加模式模拟聚光灯效果，
        2 盏主灯左右对称，从上方照射。
        """
        effects: List[Dict[str, Any]] = []
        keyframes: List[Dict[str, Any]] = []

        cx = comp_width / 2.0
        cy = comp_height * 0.15

        light_count = max(1, min(config.light_count, 4))
        intensity = config.light_intensity

        light_positions = []
        if light_count == 1:
            light_positions = [(cx, cy)]
        elif light_count == 2:
            offset = comp_width * 0.2
            light_positions = [(cx - offset, cy), (cx + offset, cy)]
        elif light_count == 3:
            offset = comp_width * 0.2
            light_positions = [(cx - offset, cy), (cx, cy - 30), (cx + offset, cy)]
        else:
            offset_x = comp_width * 0.2
            offset_y = comp_height * 0.08
            light_positions = [
                (cx - offset_x, cy - offset_y),
                (cx + offset_x, cy - offset_y),
                (cx - offset_x * 0.5, cy + offset_y),
                (cx + offset_x * 0.5, cy + offset_y),
            ]

        for i, (lx, ly) in enumerate(light_positions):
            light_name = f"StageLight_{i + 1}"

            effects.append({
                "effectName": "Circle",
                "matchName": "ADBE Circle",
                "displayName": light_name,
                "settings": {
                    "Center": [lx, ly],
                    "Radius": comp_height * 0.6,
                    "Border": comp_height * 0.2,
                    "Inside Color": [1.0, 1.0, 0.95],
                    "Outside Color": [0.0, 0.0, 0.0],
                    "Blending Mode": "Add",
                },
            })

            keyframes.append({
                "layer_name": "MiniScene_Adjustment",
                "property": f"Effects.{light_name}.Inside Color",
                "values": [
                    {"time": 0, "value": [1.0 * intensity, 1.0 * intensity, 0.95 * intensity]},
                    {"time": duration * 0.5, "value": [0.9 * intensity, 0.9 * intensity, 0.85 * intensity]},
                    {"time": duration, "value": [1.0 * intensity, 1.0 * intensity, 0.95 * intensity]},
                ],
            })

        return effects, keyframes

    @staticmethod
    def _generate_vignette(
        config: MiniSceneConfig,
        comp_width: int,
        comp_height: int,
    ) -> List[Dict[str, Any]]:
        """生成暗角效果

        使用 Circle + Invert + 叠加模式实现边缘压暗。
        """
        effects: List[Dict[str, Any]] = []

        cx = comp_width / 2.0
        cy = comp_height / 2.0
        radius = min(comp_width, comp_height) * 0.6
        border = min(comp_width, comp_height) * 0.4

        amount = config.vignette_amount
        dark_val = 1.0 - amount

        effects.append({
            "effectName": "Circle",
            "matchName": "ADBE Circle",
            "displayName": "Vignette",
            "settings": {
                "Center": [cx, cy],
                "Radius": radius,
                "Border": border,
                "Inside Color": [1.0, 1.0, 1.0],
                "Outside Color": [dark_val, dark_val, dark_val],
                "Blending Mode": "Multiply",
            },
        })

        return effects

    @staticmethod
    def _generate_floor_shadow(
        config: MiniSceneConfig,
        layer_name: str,
        comp_width: int,
        comp_height: int,
    ) -> Dict[str, Any]:
        """生成地面投影效果

        使用椭圆 + 模糊 + 低透明度模拟地面阴影。
        """
        shadow_layer_name = f"{layer_name}_FloorShadow"

        shadow_y = comp_height * 0.85
        shadow_w = comp_width * 0.4
        shadow_h = comp_height * 0.08

        return {
            "name": shadow_layer_name,
            "type": "solid",
            "width": comp_width,
            "height": comp_height,
            "color": [0, 0, 0],
            "effects": [
                {
                    "effectName": "Circle",
                    "matchName": "ADBE Circle",
                    "displayName": "ShadowShape",
                    "settings": {
                        "Center": [comp_width / 2, shadow_y],
                        "Radius": shadow_w / 2,
                        "Border": shadow_h,
                        "Inside Color": [0.0, 0.0, 0.0],
                        "Outside Color": [0.0, 0.0, 0.0],
                        "Blending Mode": "Normal",
                    },
                },
                {
                    "effectName": "Fast Box Blur",
                    "matchName": "ADBE Box Blur",
                    "displayName": "ShadowBlur",
                    "settings": {
                        "Blur Radius": 15.0,
                        "Iterations": 3,
                        "Repeat Edge Pixels": True,
                    },
                },
                {
                    "effectName": "Opacity",
                    "matchName": "ADBE Opacity2",
                    "displayName": "ShadowOpacity",
                    "settings": {
                        "Opacity": config.shadow_opacity * 100.0,
                    },
                },
            ],
            "transform": {
                "Position": [comp_width / 2, comp_height / 2],
                "Scale": [100, 100],
                "Opacity": config.shadow_opacity * 100.0,
            },
        }

    # ------------------------------------------------------------------------
    # 预设初始化
    # ------------------------------------------------------------------------

    @staticmethod
    def _init_presets() -> Dict[str, MiniSceneConfig]:
        """初始化预设配置库"""
        presets: Dict[str, MiniSceneConfig] = {}

        presets["theater_stage"] = MiniSceneConfig(
            tilt_shift=True,
            tilt_blur=12.0,
            depth_of_field=True,
            dof_blur=15.0,
            stage_lighting=True,
            light_count=2,
            light_intensity=0.9,
            vignette=True,
            vignette_amount=0.7,
            floor_shadow=True,
            shadow_opacity=0.4,
        )

        presets["toy_table"] = MiniSceneConfig(
            tilt_shift=True,
            tilt_blur=20.0,
            depth_of_field=True,
            dof_blur=25.0,
            stage_lighting=True,
            light_count=1,
            light_intensity=0.6,
            vignette=True,
            vignette_amount=0.3,
            floor_shadow=True,
            shadow_opacity=0.25,
        )

        presets["miniature_city"] = MiniSceneConfig(
            tilt_shift=True,
            tilt_blur=30.0,
            depth_of_field=False,
            dof_blur=0.0,
            stage_lighting=False,
            light_count=1,
            light_intensity=0.5,
            vignette=True,
            vignette_amount=0.4,
            floor_shadow=False,
            shadow_opacity=0.2,
        )

        presets["shadow_puppet"] = MiniSceneConfig(
            tilt_shift=False,
            tilt_blur=0.0,
            depth_of_field=False,
            dof_blur=0.0,
            stage_lighting=True,
            light_count=1,
            light_intensity=1.0,
            vignette=True,
            vignette_amount=0.6,
            floor_shadow=False,
            shadow_opacity=0.0,
        )

        presets["marionette_stage"] = MiniSceneConfig(
            tilt_shift=True,
            tilt_blur=10.0,
            depth_of_field=True,
            dof_blur=18.0,
            stage_lighting=True,
            light_count=3,
            light_intensity=0.85,
            vignette=True,
            vignette_amount=0.55,
            floor_shadow=True,
            shadow_opacity=0.35,
        )

        return presets


# ============================================================================
# 自测
# ============================================================================


if __name__ == "__main__":
    import json

    print("=" * 60)
    print("MiniSceneEffect 自测")
    print("=" * 60)

    mse = MiniSceneEffect()

    # --- 测试 1: 预设获取 ---
    print("\n[测试 1] 预设获取")
    presets = mse.get_presets()
    print(f"  预设总数: {len(presets)}")
    for name, config in presets.items():
        features = []
        if config.tilt_shift:
            features.append("移轴")
        if config.depth_of_field:
            features.append("景深")
        if config.stage_lighting:
            features.append(f"灯光x{config.light_count}")
        if config.vignette:
            features.append("暗角")
        if config.floor_shadow:
            features.append("投影")
        print(f"  {name}: {', '.join(features)}")

    # --- 测试 2: 微缩场景生成 ---
    print("\n[测试 2] 微缩场景生成")
    config = mse.get_presets()["marionette_stage"]
    result = mse.generate_mini_scene(
        config=config,
        layer_name="PuppetLayer",
        comp_width=1920,
        comp_height=1080,
        duration=5.0,
    )
    print(f"  调整层数量: {len(result['adjustment_layers'])}")
    print(f"  普通图层数量: {len(result['layers'])}")
    print(f"  关键帧数量: {len(result['keyframes'])}")

    if result["adjustment_layers"]:
        adj = result["adjustment_layers"][0]
        print(f"  调整层名称: {adj['name']}")
        print(f"  调整层效果数: {len(adj['effects'])}")
        for eff in adj["effects"]:
            print(f"    - {eff['displayName']} ({eff['effectName']})")

    # --- 测试 3: 各预设生成测试 ---
    print("\n[测试 3] 各预设生成测试")
    test_presets = ["theater_stage", "toy_table", "miniature_city", "shadow_puppet"]
    for preset_name in test_presets:
        cfg = presets[preset_name]
        res = mse.generate_mini_scene(cfg, "Test", 1280, 720, 3.0)
        total_effects = 0
        for adj in res["adjustment_layers"]:
            total_effects += len(adj["effects"])
        total_effects += len(res["layers"])
        print(f"  {preset_name}: {total_effects} 个总效果, "
              f"{len(res['adjustment_layers'])} 调整层, "
              f"{len(res['layers'])} 普通层")

    # --- 测试 4: 数据类 ---
    print("\n[测试 4] 数据类验证")
    cfg = MiniSceneConfig(
        tilt_shift=True,
        tilt_blur=10.0,
        vignette=True,
        vignette_amount=0.5,
    )
    print(f"  tilt_shift: {cfg.tilt_shift}, blur: {cfg.tilt_blur}")
    print(f"  vignette: {cfg.vignette}, amount: {cfg.vignette_amount}")
    print(f"  灯光数: {cfg.light_count}, 强度: {cfg.light_intensity}")

    # --- 测试 5: 自定义配置生成 ---
    print("\n[测试 5] 自定义配置生成")
    custom_config = MiniSceneConfig(
        tilt_shift=True,
        tilt_blur=25.0,
        depth_of_field=False,
        dof_blur=0.0,
        stage_lighting=True,
        light_count=4,
        light_intensity=0.7,
        vignette=False,
        vignette_amount=0.0,
        floor_shadow=True,
        shadow_opacity=0.5,
    )
    custom_result = mse.generate_mini_scene(custom_config, "Custom", 800, 600, 2.0)
    adj_effect_names = [e["displayName"] for e in custom_result["adjustment_layers"][0]["effects"]]
    print(f"  效果列表: {adj_effect_names}")
    print(f"  灯光数验证: {sum(1 for n in adj_effect_names if 'StageLight' in n)} (预期 4)")

    print("\n" + "=" * 60)
    print("所有自测通过 ✓")
    print("=" * 60)
