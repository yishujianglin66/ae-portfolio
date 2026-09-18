"""
puppet_style_engine.py
木偶风格化系统 - 主引擎入口

整合材质质感效果、定格动画效果、关节系统和微缩场景，
提供统一的木偶风格化接口。

内置8种风格预设：
1. wooden_puppet（木质木偶）
2. ceramic_puppet（陶瓷木偶）
3. cloth_puppet（布偶/毛绒）
4. clay_puppet（黏土/橡皮泥）
5. metal_puppet（金属木偶）
6. stop_motion_basic（基础定格动画）
7. marionette（提线木偶）
8. shadow_puppet（皮影）
"""

import json
import os
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional

from puppet_effects.joint_system import JointConfig, JointPoint, JointSystem
from puppet_effects.material_effects import MaterialEffects
from puppet_effects.mini_scene import MiniSceneConfig, MiniSceneEffect
from puppet_effects.stop_motion import StopMotionConfig, StopMotionEffect

try:
    from puppet_effects.face_puppet import FacePuppetConfig, FacePuppetEffect
    _FACE_PUPPET_AVAILABLE = True
except ImportError:
    FacePuppetEffect = None
    FacePuppetConfig = None
    _FACE_PUPPET_AVAILABLE = False


__all__ = [
    "PuppetStyleConfig",
    "PuppetStyleResult",
    "PuppetStyleEngine",
]


@dataclass
class PuppetStyleConfig:
    """木偶风格配置

    Attributes:
        style_type: 风格类型名称
        intensity: 整体强度 (0.0 - 2.0)
        material: 材质类型名称
        stop_motion: 定格动画配置字典
        joint_system: 关节系统配置字典
        mini_scene: 微缩场景配置字典
        comp_width: 合成宽度（用于微缩场景计算）
        comp_height: 合成高度（用于微缩场景计算）
        bbox: 人物边界框（用于关节估算）{"x", "y", "width", "height"}
        enable_face_puppet: 是否启鼈面部木偶化
        face_preset: 面部木偶化预设
        face_data: 面部特征点数据（可选，有则用，无则估算）
        joint_data: 关节跟踪数据（来自 MediaPipe 等），用于生成关键帧动画
                    格式: [{"time": 0.0, "joints": [{"name": "...", "x": ..., "y": ...}, ...]}, ...]
        auto_detect_pose: 是否自动检测人物姿态（需要 MediaPipe）
    """
    style_type: str = "wooden_puppet"
    intensity: float = 1.0
    material: str = "wood"
    stop_motion: dict[str, Any] = field(default_factory=dict)
    joint_system: dict[str, Any] = field(default_factory=dict)
    mini_scene: dict[str, Any] = field(default_factory=dict)
    comp_width: int = 1920
    comp_height: int = 1080
    bbox: dict[str, float] | None = None
    enable_face_puppet: bool = False
    face_preset: str = "classic_button"
    face_data: dict[str, Any] | None = None
    joint_data: list[dict[str, Any]] | None = None
    auto_detect_pose: bool = False


@dataclass
class PuppetStyleResult:
    """木偶风格化结果

    Attributes:
        effects: AE 效果列表
        keyframes: 关键帧列表
        layers: 图层结构列表
        expressions: 表达式列表
        adjustment_layers: 调整层列表
        face_effects: 面部效果列表
        face_expressions: 面部表达式列表
    """
    effects: list[dict[str, Any]] = field(default_factory=list)
    keyframes: list[dict[str, Any]] = field(default_factory=list)
    layers: list[dict[str, Any]] = field(default_factory=list)
    expressions: list[dict[str, Any]] = field(default_factory=list)
    adjustment_layers: list[dict[str, Any]] = field(default_factory=list)
    face_effects: list[dict[str, Any]] = field(default_factory=list)
    face_expressions: list[dict[str, Any]] = field(default_factory=list)


class PuppetStyleEngine:
    """木偶风格化引擎 - 主入口类

    整合材质效果、定格动画效果、关节系统和微缩场景，
    根据配置生成完整的木偶风格化方案。
    """

    _PRESETS_FILE = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "config", "style_presets.json",
    )

    def __init__(self) -> None:
        """初始化木偶风格化引擎，注册所有子风格生成器"""
        self.material_effects = MaterialEffects()
        self.stop_motion_effect = StopMotionEffect()
        self.joint_system = JointSystem()
        self.mini_scene_effect = MiniSceneEffect()
        self.face_puppet_effect = FacePuppetEffect if _FACE_PUPPET_AVAILABLE else None
        self._style_presets = self._load_presets()

    def _load_presets(self) -> dict[str, dict[str, Any]]:
        """从外部 JSON 加载风格预设，失败时回退到内置默认

        Returns:
            预设名称到配置的映射
        """
        try:
            if os.path.exists(self._PRESETS_FILE):
                with open(self._PRESETS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                presets = data.get("presets", {})
                if presets:
                    return presets
        except (json.JSONDecodeError, OSError) as e:
            print(f"⚠️ 风格预设加载失败，使用内置默认: {e}")
        return self._build_builtin_presets()

    def _build_builtin_presets(self) -> dict[str, dict[str, Any]]:
        """构建内置风格预设（作为外部 JSON 的 fallback）

        Returns:
            预设名称到配置的映射
        """
        return {
            "wooden_puppet": {
                "name": "wooden_puppet",
                "display_name": "木质木偶",
                "category": "材质风格",
                "description": "经典木质木偶效果，木纹纹理、暖棕色调、硬边描边",
                "keywords": ["木质", "木偶", "木纹", "暖色调", "传统"],
                "intensity_range": [0.3, 1.8],
                "material": "wooden_puppet",
                "stop_motion": None,
                "joint_preset": "simple_puppet",
                "joint_config": {
                    "show_joint_seams": True,
                    "seam_radius": 10.0,
                    "show_strings": False,
                    "joint_gap": 3.0,
                },
                "mini_scene_preset": "theater_stage",
                "face_puppet_enabled": True,
                "face_preset": "classic_button",
            },
            "ceramic_puppet": {
                "name": "ceramic_puppet",
                "display_name": "陶瓷木偶",
                "category": "材质风格",
                "description": "精致陶瓷木偶效果，瓷釉高光、冷色调、光滑质感",
                "keywords": ["陶瓷", "瓷釉", "光滑", "冷色调", "精致"],
                "intensity_range": [0.3, 2.0],
                "material": "ceramic_puppet",
                "stop_motion": None,
                "joint_preset": "simple_puppet",
                "joint_config": {
                    "show_joint_seams": False,
                    "show_strings": False,
                    "joint_gap": 0.0,
                },
                "mini_scene_preset": "toy_table",
                "face_puppet_enabled": True,
                "face_preset": "porcelain_doll",
            },
            "cloth_puppet": {
                "name": "cloth_puppet",
                "display_name": "布偶/毛绒",
                "category": "材质风格",
                "description": "柔软布偶效果，毛绒纹理、粗糙边缘、柔和色彩",
                "keywords": ["布偶", "毛绒", "柔软", "温暖", "可爱"],
                "intensity_range": [0.2, 1.5],
                "material": "cloth_puppet",
                "stop_motion": None,
                "joint_preset": "simple_puppet",
                "joint_config": {
                    "show_joint_seams": True,
                    "seam_radius": 12.0,
                    "show_strings": False,
                    "joint_gap": 2.0,
                },
                "mini_scene_preset": "toy_table",
                "face_puppet_enabled": True,
                "face_preset": "rag_doll",
            },
            "clay_puppet": {
                "name": "clay_puppet",
                "display_name": "黏土/橡皮泥",
                "category": "材质风格",
                "description": "黏土动画效果，指纹纹理、圆润边缘、柔和对比",
                "keywords": ["黏土", "橡皮泥", "圆润", "手工", "童趣"],
                "intensity_range": [0.3, 1.8],
                "material": "clay_puppet",
                "stop_motion": "12fps_smooth",
                "joint_preset": "simple_puppet",
                "joint_config": {
                    "show_joint_seams": False,
                    "show_strings": False,
                    "joint_gap": 1.0,
                },
                "mini_scene_preset": "toy_table",
                "face_puppet_enabled": False,
                "face_preset": "classic_button",
            },
            "metal_puppet": {
                "name": "metal_puppet",
                "display_name": "金属木偶",
                "category": "材质风格",
                "description": "机械金属木偶效果，冷钢色调、高对比度、金属高光",
                "keywords": ["金属", "机械", "冷色调", "工业", "朋克"],
                "intensity_range": [0.4, 2.0],
                "material": "metal_puppet",
                "stop_motion": None,
                "joint_preset": "human_upper_body",
                "joint_config": {
                    "show_joint_seams": True,
                    "seam_radius": 8.0,
                    "show_strings": False,
                    "joint_gap": 4.0,
                },
                "mini_scene_preset": "miniature_city",
                "face_puppet_enabled": False,
                "face_preset": "classic_button",
            },
            "stop_motion_basic": {
                "name": "stop_motion_basic",
                "display_name": "基础定格动画",
                "category": "动画风格",
                "description": "经典定格动画效果，12fps、轻微抖动和闪烁",
                "keywords": ["定格", "逐帧", "定格动画", "经典", "复古"],
                "intensity_range": [0.2, 1.5],
                "material": None,
                "stop_motion": "12fps_smooth",
                "joint_preset": None,
                "joint_config": {},
                "mini_scene_preset": None,
                "face_puppet_enabled": False,
                "face_preset": "classic_button",
            },
            "marionette": {
                "name": "marionette",
                "display_name": "提线木偶",
                "category": "动画风格",
                "description": "提线木偶效果，木质材质+悬挂线+摆动动画",
                "keywords": ["提线", "悬挂", "木偶", "摆动", "传统"],
                "intensity_range": [0.3, 1.8],
                "material": "wooden_puppet",
                "stop_motion": "8fps_classic",
                "joint_preset": "marionette_basic",
                "joint_config": {
                    "show_joint_seams": True,
                    "seam_radius": 12.0,
                    "show_strings": True,
                    "string_count": 4,
                    "string_opacity": 0.65,
                    "joint_gap": 4.0,
                },
                "mini_scene_preset": "marionette_stage",
                "face_puppet_enabled": True,
                "face_preset": "classic_button",
            },
            "shadow_puppet": {
                "name": "shadow_puppet",
                "display_name": "皮影",
                "category": "动画风格",
                "description": "中国皮影戏效果，剪影风格、关节可动、暖光投影",
                "keywords": ["皮影", "剪影", "投影", "中国风", "传统"],
                "intensity_range": [0.4, 2.0],
                "material": None,
                "stop_motion": "15fps_modern",
                "joint_preset": "simple_puppet",
                "joint_config": {
                    "show_joint_seams": True,
                    "seam_radius": 6.0,
                    "show_strings": False,
                    "joint_gap": 2.0,
                },
                "mini_scene_preset": "shadow_puppet",
                "face_puppet_enabled": True,
                "face_preset": "stitched",
            },
        }

    def get_available_styles(self) -> list[dict[str, Any]]:
        """返回所有可用风格列表

        Returns:
            风格信息列表，每项包含 name, display_name, category, description, keywords
        """
        styles = []
        for name, preset in self._style_presets.items():
            styles.append({
                "name": preset["name"],
                "display_name": preset["display_name"],
                "category": preset["category"],
                "description": preset["description"],
                "keywords": preset["keywords"],
                "intensity_range": preset["intensity_range"],
            })
        return styles

    def get_style_preset(self, style_name: str) -> dict[str, Any] | None:
        """获取指定风格的预设配置

        Args:
            style_name: 风格名称

        Returns:
            预设配置字典，不存在则返回 None
        """
        return self._style_presets.get(style_name)

    def register_preset(self, name: str, preset: dict[str, Any]) -> None:
        """注册自定义风格预设（运行时动态扩展）

        Args:
            name: 预设名称（唯一键）
            preset: 预设配置字典，需包含 name, display_name, category,
                    description, keywords, intensity_range 等字段
        """
        required = ["name", "display_name", "intensity_range"]
        missing = [k for k in required if k not in preset]
        if missing:
            raise ValueError(f"预设缺少必需字段: {missing}")
        self._style_presets[name] = preset

    def reload_presets(self) -> int:
        """重新从 JSON 文件加载预设（热重载）

        Returns:
            加载的预设数量
        """
        self._style_presets = self._load_presets()
        return len(self._style_presets)

    def generate_style(self, config: PuppetStyleConfig,
                       layer_name: str = "layer_001",
                       duration: float = 5.0) -> PuppetStyleResult:
        """主入口，根据配置生成完整风格化效果

        Args:
            config: 风格配置
            layer_name: 图层名称
            duration: 动画持续时间（秒）

        Returns:
            风格化结果，包含 effects, keyframes, layers, expressions, adjustment_layers

        Raises:
            ValueError: 当风格类型不存在时
        """
        preset = self._style_presets.get(config.style_type)
        if not preset:
            raise ValueError(
                f"Unknown style type: {config.style_type}. "
                f"Available: {list(self._style_presets.keys())}"
            )

        intensity = self._clamp_intensity(
            config.intensity, preset["intensity_range"]
        )

        result = PuppetStyleResult()

        if preset["material"]:
            material_effects = self.material_effects.generate(
                preset["material"], intensity=intensity, layer_name=layer_name
            )
            result.effects.extend(material_effects)

        if preset["stop_motion"]:
            sm_presets = self.stop_motion_effect.get_presets()
            sm_config = sm_presets.get(preset["stop_motion"])
            if sm_config:
                if config.stop_motion:
                    for key, value in config.stop_motion.items():
                        if hasattr(sm_config, key):
                            setattr(sm_config, key, value)
                sm_result = self.stop_motion_effect.generate_effects(
                    sm_config, layer_name=layer_name, duration=duration
                )
                result.effects.extend(sm_result.get("effects", []))
                result.keyframes.extend(sm_result.get("keyframes", []))
                result.layers.extend(sm_result.get("layers", []))
                result.expressions.extend(sm_result.get("expressions", []))

        if preset.get("joint_preset"):
            joint_config = self._build_joint_config(
                preset, config, layer_name
            )
            if joint_config:
                joint_result = self.joint_system.generate_joint_effects(
                    joint_config, layer_name, duration
                )
                result.effects.extend(joint_result.get("effects", []))
                result.keyframes.extend(joint_result.get("keyframes", []))
                result.layers.extend(joint_result.get("layers", []))
                result.expressions.extend(joint_result.get("expressions", []))

                if config.joint_data:
                    joint_kfs = self.joint_system.generate_joint_keyframes(
                        joint_config, layer_name, config.joint_data
                    )
                    result.keyframes.extend(joint_kfs)

        if preset.get("mini_scene_preset"):
            scene_config = self._build_mini_scene_config(
                preset, config, intensity
            )
            if scene_config:
                scene_result = self.mini_scene_effect.generate_mini_scene(
                    config=scene_config,
                    layer_name=layer_name,
                    comp_width=config.comp_width,
                    comp_height=config.comp_height,
                    duration=duration,
                )
                result.effects.extend(scene_result.get("effects", []))
                result.keyframes.extend(scene_result.get("keyframes", []))
                result.layers.extend(scene_result.get("layers", []))
                result.adjustment_layers.extend(
                    scene_result.get("adjustment_layers", [])
                )

        if self._should_enable_face_puppet(preset, config):
            face_result = self._generate_face_puppet_effects(
                preset, config, layer_name, duration
            )
            if face_result:
                result.effects.extend(face_result.get("effects", []))
                result.keyframes.extend(face_result.get("keyframes", []))
                result.layers.extend(face_result.get("layers", []))
                result.expressions.extend(face_result.get("expressions", []))
                result.face_effects.extend(face_result.get("effects", []))
                result.face_expressions.extend(face_result.get("expressions", []))

        return result

    def _clamp_intensity(self, intensity: float,
                         intensity_range: list[float]) -> float:
        """限制强度在有效范围内

        Args:
            intensity: 输入强度
            intensity_range: [min, max] 范围

        Returns:
            限制后的强度值
        """
        min_val, max_val = intensity_range
        return max(min_val, min(max_val, intensity))

    def _build_joint_config(self, preset: dict[str, Any],
                            config: PuppetStyleConfig,
                            layer_name: str) -> JointConfig | None:
        """构建关节系统配置

        Args:
            preset: 风格预设
            config: 引擎配置
            layer_name: 图层名称

        Returns:
            JointConfig 实例或 None
        """
        joint_preset_name = preset.get("joint_preset")
        if not joint_preset_name:
            return None

        try:
            joint_config = self.joint_system.get_standard_joint_preset(
                joint_preset_name
            )
        except ValueError:
            return None

        joint_config = replace(joint_config)

        preset_joint_config = preset.get("joint_config", {})
        override_fields = {}
        for key, value in preset_joint_config.items():
            if hasattr(joint_config, key):
                override_fields[key] = value
        if override_fields:
            joint_config = replace(joint_config, **override_fields)

        if config.joint_system:
            override_fields = {}
            for key, value in config.joint_system.items():
                if hasattr(joint_config, key):
                    override_fields[key] = value
            if override_fields:
                joint_config = replace(joint_config, **override_fields)

        if config.bbox and not joint_config.joint_points:
            joint_points = self.joint_system.estimate_joints_from_bbox(
                config.bbox, "simple"
            )
            joint_config = replace(joint_config, joint_points=joint_points)

        return joint_config

    def _build_mini_scene_config(self, preset: dict[str, Any],
                                 config: PuppetStyleConfig,
                                 intensity: float) -> MiniSceneConfig | None:
        """构建微缩场景配置

        Args:
            preset: 风格预设
            config: 引擎配置
            intensity: 强度系数

        Returns:
            MiniSceneConfig 实例或 None
        """
        scene_preset_name = preset.get("mini_scene_preset")
        if not scene_preset_name:
            return None

        scene_presets = self.mini_scene_effect.get_presets()
        scene_config = scene_presets.get(scene_preset_name)
        if not scene_config:
            return None

        scene_config = replace(
            scene_config,
            tilt_blur=scene_config.tilt_blur * intensity,
            dof_blur=scene_config.dof_blur * intensity,
            light_intensity=scene_config.light_intensity * intensity,
            vignette_amount=scene_config.vignette_amount * intensity,
            shadow_opacity=scene_config.shadow_opacity * intensity,
        )

        if config.mini_scene:
            override_fields = {}
            for key, value in config.mini_scene.items():
                if hasattr(scene_config, key):
                    override_fields[key] = value
            if override_fields:
                scene_config = replace(scene_config, **override_fields)

        return scene_config

    def _should_enable_face_puppet(self, preset: dict[str, Any],
                                   config: PuppetStyleConfig) -> bool:
        """判断是否应该启鼈面部木偶化

        Args:
            preset: 风格预设
            config: 引擎配置

        Returns:
            是否启鼈面部木偶化
        """
        if not _FACE_PUPPET_AVAILABLE or self.face_puppet_effect is None:
            return False

        if config.enable_face_puppet:
            return True

        if preset.get("face_puppet_enabled", False):
            return True

        return False

    def _generate_face_puppet_effects(self, preset: dict[str, Any],
                                    config: PuppetStyleConfig,
                                    layer_name: str,
                                    duration: float) -> dict[str, Any] | None:
        """生成面部木偶化效果

        Args:
            preset: 风格预设
            config: 引擎配置
            layer_name: 图层名称
            duration: 持续时间（秒）

        Returns:
            包含 effects, keyframes, layers, expressions 的字典或 None
        """
        if not _FACE_PUPPET_AVAILABLE or self.face_puppet_effect is None:
            return None

        if config.enable_face_puppet:
            face_preset_name = config.face_preset
        else:
            face_preset_name = preset.get("face_preset", "classic_button")

        try:
            face_config = self.face_puppet_effect.get_preset(face_preset_name)
        except ValueError:
            face_config = self.face_puppet_effect.get_preset("classic_button")

        face_data = config.face_data
        if face_data is None and config.bbox:
            face_data = self.face_puppet_effect.estimate_face_from_bbox(
                config.bbox
            )

        try:
            result = self.face_puppet_effect.generate_face_puppet(
                config=face_config,
                layer_name=layer_name,
                face_data=face_data,
                duration=duration,
            )
            return result
        except Exception:
            return None


# ----------------------------------------------------------------------
# 模块自测
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("PuppetStyleEngine 模块自测")
    print("=" * 60)

    engine = PuppetStyleEngine()

    print(f"\n可用风格列表 ({len(engine.get_available_styles())} 种):")
    for style in engine.get_available_styles():
        print(f"  - {style['name']} ({style['display_name']})")
        print(f"    类别: {style['category']}")
        print(f"    描述: {style['description'][:50]}...")

    test_styles = [
        "wooden_puppet",
        "ceramic_puppet",
        "cloth_puppet",
        "clay_puppet",
        "metal_puppet",
        "stop_motion_basic",
        "marionette",
        "shadow_puppet",
    ]

    for style_name in test_styles:
        print(f"\n{'─' * 50}")
        print(f"测试风格: {style_name}")
        print(f"{'─' * 50}")

        preset = engine.get_style_preset(style_name)
        if preset:
            print(f"  显示名称: {preset['display_name']}")
            print(f"  材质: {preset['material']}")
            print(f"  定格动画: {preset['stop_motion']}")
            print(f"  关节预设: {preset.get('joint_preset')}")
            print(f"  场景预设: {preset.get('mini_scene_preset')}")
            print(f"  面部木偶化: {preset.get('face_puppet_enabled', False)}")
            print(f"  面部预设: {preset.get('face_preset', 'N/A')}")

        config = PuppetStyleConfig(
            style_type=style_name,
            intensity=1.0,
            comp_width=1280,
            comp_height=720,
        )
        try:
            result = engine.generate_style(
                config, layer_name="test_layer", duration=3.0
            )
            print(f"  效果数量: {len(result.effects)}")
            print(f"  关键帧数量: {len(result.keyframes)}")
            print(f"  图层数量: {len(result.layers)}")
            print(f"  表达式数量: {len(result.expressions)}")
            print(f"  调整层数量: {len(result.adjustment_layers)}")
            print(f"  面部效果数量: {len(result.face_effects)}")
            print(f"  面部表达式数量: {len(result.face_expressions)}")
        except Exception as e:
            print(f"  错误: {e}")
            import traceback
            traceback.print_exc()

    print(f"\n{'=' * 60}")
    print("测试强度变化 (intensity=0.5 vs 1.5):")
    print(f"{'=' * 60}")
    config_low = PuppetStyleConfig(
        style_type="wooden_puppet", intensity=0.5,
        comp_width=1280, comp_height=720,
    )
    config_high = PuppetStyleConfig(
        style_type="wooden_puppet", intensity=1.5,
        comp_width=1280, comp_height=720,
    )
    result_low = engine.generate_style(config_low, "test", 2.0)
    result_high = engine.generate_style(config_high, "test", 2.0)
    print(f"  低强度效果数: {len(result_low.effects)}")
    print(f"  高强度效果数: {len(result_high.effects)}")
    if result_low.effects and result_high.effects:
        eff_low = result_low.effects[0]
        eff_high = result_high.effects[0]
        param = eff_low.get("intensity_param")
        if param and param in eff_low["settings"] and isinstance(eff_low["settings"][param], (int, float)):
            print(f"  第一个效果 {param}: {eff_low['settings'][param]:.2f} -> {eff_high['settings'][param]:.2f}")

    print(f"\n{'=' * 60}")
    print("测试自定义配置覆盖:")
    print(f"{'=' * 60}")
    custom_config = PuppetStyleConfig(
        style_type="marionette",
        intensity=1.2,
        stop_motion={
            "fps": 10,
            "jitter_amount": 4.0,
        },
        comp_width=1920,
        comp_height=1080,
    )
    result = engine.generate_style(custom_config, "custom_layer", 2.0)
    print(f"  效果数量: {len(result.effects)}")
    print(f"  表达式数量: {len(result.expressions)}")
    for expr in result.expressions[:3]:
        print(f"    - {expr.get('property', 'N/A')}: {expr.get('description', 'N/A')}")

    print(f"\n{'=' * 60}")
    print("测试带边界框的关节估算:")
    print(f"{'=' * 60}")
    bbox_config = PuppetStyleConfig(
        style_type="marionette",
        intensity=1.0,
        comp_width=1280,
        comp_height=720,
        bbox={"x": 400, "y": 100, "width": 300, "height": 500},
    )
    result = engine.generate_style(bbox_config, "bbox_layer", 2.0)
    print(f"  效果数量: {len(result.effects)}")
    print(f"  图层数量: {len(result.layers)}")

    print(f"\n{'=' * 60}")
    print("测试面部木偶化效果:")
    print(f"{'=' * 60}")

    print("\n[测试 1] 默认风格自带面部木偶化 (wooden_puppet):")
    config_face1 = PuppetStyleConfig(
        style_type="wooden_puppet",
        intensity=1.0,
        comp_width=1280,
        comp_height=720,
        bbox={"x": 400, "y": 100, "width": 300, "height": 500},
    )
    result_face1 = engine.generate_style(config_face1, "face_layer", 3.0)
    print(f"  面部效果数量: {len(result_face1.face_effects)}")
    print(f"  面部表达式数量: {len(result_face1.face_expressions)}")
    if result_face1.face_effects:
        print("  前5个面部效果:")
        for eff in result_face1.face_effects[:5]:
            print(f"    - {eff.get('displayName', '?')}")

    print("\n[测试 2] 手动启鼈面部木偶化 (clay_puppet 默认关闭):")
    config_face2 = PuppetStyleConfig(
        style_type="clay_puppet",
        intensity=1.0,
        enable_face_puppet=True,
        face_preset="rag_doll",
        comp_width=1280,
        comp_height=720,
        bbox={"x": 400, "y": 100, "width": 300, "height": 500},
    )
    result_face2 = engine.generate_style(config_face2, "face_layer2", 3.0)
    print(f"  面部效果数量: {len(result_face2.face_effects)}")
    print(f"  面部表达式数量: {len(result_face2.face_expressions)}")

    print("\n[测试 3] 提供 face_data 面部特征点:")
    face_data = {
        "left_eye": {"x": 500, "y": 280},
        "right_eye": {"x": 620, "y": 280},
        "mouth": {"x": 560, "y": 400, "width": 80, "height": 25},
        "nose": {"x": 560, "y": 340},
        "jaw": {"x": 560, "y": 480},
        "face_bbox": {"x": 400, "y": 150, "width": 320, "height": 380},
    }
    config_face3 = PuppetStyleConfig(
        style_type="ceramic_puppet",
        intensity=1.0,
        face_data=face_data,
        comp_width=1280,
        comp_height=720,
    )
    result_face3 = engine.generate_style(config_face3, "face_layer3", 3.0)
    print(f"  面部效果数量: {len(result_face3.face_effects)}")
    print(f"  总效果数量: {len(result_face3.effects)}")

    print("\n[测试 4] 不同面部预设对比:")
    face_presets_to_test = ["classic_button", "porcelain_doll", "rag_doll", "stitched"]
    for preset_name in face_presets_to_test:
        config_test = PuppetStyleConfig(
            style_type="metal_puppet",
            intensity=1.0,
            enable_face_puppet=True,
            face_preset=preset_name,
            comp_width=1280,
            comp_height=720,
            bbox={"x": 400, "y": 100, "width": 300, "height": 500},
        )
        result_test = engine.generate_style(config_test, f"test_{preset_name}", 2.0)
        print(f"  {preset_name}: {len(result_test.face_effects)} 个面部效果")

    print("\n[测试 5] 面部木偶化模块可用性检测:")
    print(f"  FacePuppetEffect 可用: {_FACE_PUPPET_AVAILABLE}")
    print(f"  引擎 face_puppet_effect: {engine.face_puppet_effect is not None}")

    print("\n自测完成 ✓")
