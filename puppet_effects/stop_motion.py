"""
stop_motion.py
木偶风格化系统 - 定格动画效果生成器

生成定格动画效果，包括降帧、逐帧抖动、曝光闪烁、镜头抖动等。

降帧处理通过表达式控制时间重映射（posterizeTime）实现。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


__all__ = [
    "StopMotionConfig",
    "StopMotionEffect",
]


@dataclass
class StopMotionConfig:
    """定格动画配置

    Attributes:
        fps: 定格帧率 (如 8, 12, 15)
        jitter_amount: 逐帧抖动幅度 (像素)
        flicker_amount: 曝光闪烁幅度 (0.0 - 1.0)
        camera_shake: 镜头抖动强度 (0.0 - 1.0)
    """
    fps: int = 12
    jitter_amount: float = 2.0
    flicker_amount: float = 0.1
    camera_shake: float = 0.3


class StopMotionEffect:
    """定格动画效果生成器

    生成定格动画所需的效果、关键帧和表达式。
    """

    def __init__(self) -> None:
        """初始化定格动画效果生成器"""
        pass

    @staticmethod
    def get_presets() -> Dict[str, StopMotionConfig]:
        """获取定格动画预设配置

        Returns:
            预设名称到配置的映射
        """
        return {
            "8fps_classic": StopMotionConfig(
                fps=8,
                jitter_amount=3.0,
                flicker_amount=0.15,
                camera_shake=0.2,
            ),
            "12fps_smooth": StopMotionConfig(
                fps=12,
                jitter_amount=1.5,
                flicker_amount=0.08,
                camera_shake=0.1,
            ),
            "15fps_modern": StopMotionConfig(
                fps=15,
                jitter_amount=1.0,
                flicker_amount=0.05,
                camera_shake=0.05,
            ),
            "handheld_shaky": StopMotionConfig(
                fps=10,
                jitter_amount=5.0,
                flicker_amount=0.2,
                camera_shake=0.6,
            ),
        }

    @staticmethod
    def generate_effects(config: StopMotionConfig,
                         layer_name: str = "layer_001",
                         duration: float = 5.0) -> Dict[str, Any]:
        """生成定格动画效果和关键帧

        包含：
        - 降帧处理：通过表达式控制时间重映射（posterizeTime）
        - 逐帧抖动：Transform Position + Wiggle 表达式
        - 曝光闪烁：Opacity 随机波动
        - 镜头抖动：整体位移 + 旋转微抖动

        Args:
            config: 定格动画配置
            layer_name: 图层名称
            duration: 动画持续时间（秒）

        Returns:
            包含 effects, keyframes, expressions 的字典
        """
        effects = StopMotionEffect._build_effects(config, layer_name)
        keyframes = StopMotionEffect._build_keyframes(config, layer_name, duration)
        expressions = StopMotionEffect._build_expressions(config, layer_name)
        layers = StopMotionEffect._build_layer_structure(config, layer_name)

        return {
            "config": {
                "fps": config.fps,
                "jitter_amount": config.jitter_amount,
                "flicker_amount": config.flicker_amount,
                "camera_shake": config.camera_shake,
            },
            "effects": effects,
            "keyframes": keyframes,
            "expressions": expressions,
            "layers": layers,
            "duration": duration,
        }

    @staticmethod
    def _build_effects(config: StopMotionConfig,
                       layer_name: str) -> List[Dict[str, Any]]:
        """构建定格动画相关的效果列表

        Args:
            config: 定格动画配置
            layer_name: 图层名称

        Returns:
            AE 效果列表
        """
        effects = []

        if config.flicker_amount > 0:
            flicker_strength = config.flicker_amount * 100
            effects.append({
                "effectName": "ADBE Brightness & Contrast 2",
                "matchName": "ADBE Brightness & Contrast 2",
                "settings": {
                    "Brightness": 0.0,
                    "Contrast": 0.0,
                    "Use Legacy": False,
                },
                "intensity_param": "Brightness",
                "intensity_factor": flicker_strength,
                "layer_name": layer_name,
                "animation": "flicker",
            })

        return effects

    @staticmethod
    def _build_keyframes(config: StopMotionConfig,
                         layer_name: str,
                         duration: float) -> List[Dict[str, Any]]:
        """构建关键帧数据

        Args:
            config: 定格动画配置
            layer_name: 图层名称
            duration: 持续时间

        Returns:
            关键帧列表
        """
        keyframes = []
        frame_interval = 1.0 / config.fps
        num_frames = int(duration * config.fps) + 1

        if config.jitter_amount > 0:
            import random
            random.seed(42)
            for i in range(num_frames):
                t = i * frame_interval
                jitter_x = random.uniform(-config.jitter_amount, config.jitter_amount)
                jitter_y = random.uniform(-config.jitter_amount, config.jitter_amount)
                keyframes.append({
                    "layer": layer_name,
                    "property": "Transform/Position",
                    "time": t,
                    "value": [jitter_x, jitter_y],
                    "interpolation": "hold",
                })

        if config.flicker_amount > 0:
            import random
            random.seed(123)
            for i in range(num_frames):
                t = i * frame_interval
                opacity = 100 - random.uniform(0, config.flicker_amount * 100)
                keyframes.append({
                    "layer": layer_name,
                    "property": "Transform/Opacity",
                    "time": t,
                    "value": opacity,
                    "interpolation": "hold",
                })

        if config.camera_shake > 0:
            import random
            random.seed(456)
            shake_amt = config.camera_shake * 10
            for i in range(num_frames):
                t = i * frame_interval
                rot_jitter = random.uniform(-shake_amt * 0.1, shake_amt * 0.1)
                keyframes.append({
                    "layer": layer_name,
                    "property": "Transform/Rotation",
                    "time": t,
                    "value": rot_jitter,
                    "interpolation": "hold",
                })

        return keyframes

    @staticmethod
    def _build_expressions(config: StopMotionConfig,
                           layer_name: str) -> List[Dict[str, Any]]:
        """构建表达式列表

        Args:
            config: 定格动画配置
            layer_name: 图层名称

        Returns:
            表达式列表
        """
        expressions = []

        expressions.append({
            "layer": layer_name,
            "property": "timeRemap",
            "expression": StopMotionEffect._posterize_time_expression(config.fps),
            "description": "降帧处理 - posterizeTime",
        })

        if config.jitter_amount > 0:
            expressions.append({
                "layer": layer_name,
                "property": "Transform/Position",
                "expression": StopMotionEffect._jitter_expression(
                    config.fps, config.jitter_amount
                ),
                "description": "逐帧位置抖动",
            })

        if config.flicker_amount > 0:
            expressions.append({
                "layer": layer_name,
                "property": "Transform/Opacity",
                "expression": StopMotionEffect._flicker_expression(
                    config.fps, config.flicker_amount
                ),
                "description": "曝光闪烁",
            })

        if config.camera_shake > 0:
            expressions.append({
                "layer": layer_name,
                "property": "Transform/Rotation",
                "expression": StopMotionEffect._camera_shake_expression(
                    config.fps, config.camera_shake
                ),
                "description": "镜头旋转抖动",
            })

        return expressions

    @staticmethod
    def _build_layer_structure(config: StopMotionConfig,
                               layer_name: str) -> List[Dict[str, Any]]:
        """构建推荐的图层结构

        Args:
            config: 定格动画配置
            layer_name: 主图层名称

        Returns:
            图层结构列表
        """
        layers = [
            {
                "name": layer_name,
                "type": "adjustment",
                "purpose": "定格动画主控层",
                "effects": ["time_remap", "jitter", "flicker"],
                "enabled": True,
            }
        ]

        if config.camera_shake > 0:
            layers.insert(0, {
                "name": f"{layer_name}_camera_shake",
                "type": "null",
                "purpose": "镜头抖动控制层",
                "parent": None,
                "enabled": True,
            })

        return layers

    @staticmethod
    def _posterize_time_expression(fps: int) -> str:
        """生成降帧表达式

        Args:
            fps: 目标帧率

        Returns:
            AE 表达式字符串
        """
        return f"""posterizeTime({fps});
time"""

    @staticmethod
    def _jitter_expression(fps: int, amount: float) -> str:
        """生成逐帧抖动表达式

        Args:
            fps: 帧率
            amount: 抖动幅度

        Returns:
            AE 表达式字符串
        """
        return f"""posterizeTime({fps});
wiggle({fps}, {amount})"""

    @staticmethod
    def _flicker_expression(fps: int, amount: float) -> str:
        """生成曝光闪烁表达式

        Args:
            fps: 帧率
            amount: 闪烁幅度 (0.0 - 1.0)

        Returns:
            AE 表达式字符串
        """
        flicker_range = amount * 100
        return f"""posterizeTime({fps});
100 - random(0, {flicker_range})"""

    @staticmethod
    def _camera_shake_expression(fps: int, amount: float) -> str:
        """生成镜头抖动表达式

        Args:
            fps: 帧率
            amount: 抖动强度 (0.0 - 1.0)

        Returns:
            AE 表达式字符串
        """
        shake_freq = fps
        shake_amp = amount * 2
        return f"""posterizeTime({fps});
wiggle({shake_freq}, {shake_amp})"""


# ----------------------------------------------------------------------
# 模块自测
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("StopMotionEffect 模块自测")
    print("=" * 60)

    sme = StopMotionEffect()

    presets = sme.get_presets()
    print(f"\n可用预设 ({len(presets)} 种):")
    for name, cfg in presets.items():
        print(f"  - {name}: fps={cfg.fps}, jitter={cfg.jitter_amount}, "
              f"flicker={cfg.flicker_amount}, shake={cfg.camera_shake}")

    test_presets = ["8fps_classic", "12fps_smooth", "handheld_shaky"]

    for preset_name in test_presets:
        print(f"\n{'─' * 50}")
        print(f"测试预设: {preset_name}")
        print(f"{'─' * 50}")
        config = presets[preset_name]
        result = sme.generate_effects(
            config, layer_name="test_layer", duration=3.0
        )
        print(f"  效果数量: {len(result['effects'])}")
        print(f"  关键帧数量: {len(result['keyframes'])}")
        print(f"  表达式数量: {len(result['expressions'])}")
        print(f"  图层数量: {len(result['layers'])}")

        if result["expressions"]:
            print(f"\n  表达式示例:")
            for expr in result["expressions"][:2]:
                print(f"    [{expr['property']}]")
                expr_lines = expr['expression'].strip().split('\n')
                for line in expr_lines:
                    print(f"      {line}")

    print(f"\n{'=' * 60}")
    print("测试自定义配置:")
    print(f"{'=' * 60}")
    custom_config = StopMotionConfig(
        fps=6,
        jitter_amount=5.0,
        flicker_amount=0.25,
        camera_shake=0.5,
    )
    result = sme.generate_effects(
        custom_config, layer_name="custom_layer", duration=2.0
    )
    print(f"  自定义配置 fps={custom_config.fps}")
    print(f"  关键帧数量: {len(result['keyframes'])}")
    print(f"  表达式数量: {len(result['expressions'])}")

    print("\n自测完成 ✓")
