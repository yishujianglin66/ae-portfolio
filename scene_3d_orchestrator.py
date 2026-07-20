"""
scene_3d_orchestrator.py
Phase 3 - 3D 场景与摄像机系统编排器

用途：生成 3D 图层开关、摄像机图层、灯光图层、3D 关键帧等操作。

功能：
  - 3D 图层开关：根据风格决定是否开启图层 3D 属性
  - 摄像机图层：创建摄像机并生成推拉摇移动画
  - 灯光系统：创建点光/平行光/环境光
  - 3D 关键帧：Z 轴位移 / 朝向 / 旋转

设计对齐：scene_orchestrator.py 的模块结构
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


__all__ = [
    "CameraMove",
    "LightConfig",
    "Scene3DOrchestrator",
]


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class CameraMove:
    """摄像机运动"""
    type: str = "push"  # push / pull / pan_left / pan_right / tilt_up / tilt_down / orbit / handheld
    duration: float = 2.0
    start_position: List[float] = field(default_factory=lambda: [960, 540, -1000])
    end_position: List[float] = field(default_factory=lambda: [960, 540, -500])
    start_point_of_interest: Optional[List[float]] = None
    end_point_of_interest: Optional[List[float]] = None


@dataclass
class LightConfig:
    """灯光配置"""
    name: str
    light_type: str = "point"  # point / parallel / ambient / spot
    position: List[float] = field(default_factory=lambda: [960, 540, -500])
    intensity: float = 100.0
    color: List[int] = field(default_factory=lambda: [255, 255, 255])
    casts_shadows: bool = False


@dataclass
class Layer3DConfig:
    """3D 图层配置"""
    layer_name: str
    three_d_enabled: bool = False
    z_position: float = 0.0
    orientation: List[float] = field(default_factory=lambda: [0, 0, 0])
    accepts_shadows: bool = False
    casts_shadows: bool = False


# ---------------------------------------------------------------------------
# 主编排器
# ---------------------------------------------------------------------------

class Scene3DOrchestrator:
    """3D 场景编排器"""

    STYLE_3D_MAP: Dict[str, Dict[str, Any]] = {
        "cinematic": {
            "enable_3d": True,
            "camera_type": "cinematic",
            "camera_move": "push",
            "lights": ["key_light", "fill_light"],
            "depth": 300.0,
        },
        "epic": {
            "enable_3d": True,
            "camera_type": "dynamic",
            "camera_move": "orbit",
            "lights": ["key_light", "rim_light", "ambient"],
            "depth": 500.0,
        },
        "dreamy": {
            "enable_3d": True,
            "camera_type": "soft",
            "camera_move": "float",
            "lights": ["soft_key", "ambient"],
            "depth": 200.0,
        },
        "vibrant": {
            "enable_3d": True,
            "camera_type": "energetic",
            "camera_move": "handheld",
            "lights": ["multi_color"],
            "depth": 400.0,
        },
        "minimalist": {
            "enable_3d": False,
            "camera_type": "none",
            "camera_move": "none",
            "lights": [],
            "depth": 0.0,
        },
        "fast_cut": {
            "enable_3d": False,
            "camera_type": "none",
            "camera_move": "none",
            "lights": [],
            "depth": 0.0,
        },
        "dark_moody": {
            "enable_3d": True,
            "camera_type": "moody",
            "camera_move": "slow_push",
            "lights": ["single_rim", "low_ambient"],
            "depth": 250.0,
        },
    }

    def __init__(self, style: str = "cinematic", comp_width: int = 1920, comp_height: int = 1080):
        self.style = style
        self.comp_width = comp_width
        self.comp_height = comp_height
        config = self.STYLE_3D_MAP.get(style, self.STYLE_3D_MAP["cinematic"])
        self.enable_3d = config.get("enable_3d", False)
        self.depth = config.get("depth", 300.0)
        self._camera_config = config
        self.cameras: List[Dict[str, Any]] = []
        self.lights: List[LightConfig] = []
        self.layers_3d: List[Layer3DConfig] = []

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def generate_scene(self, layers: List[Dict], duration: float) -> Dict[str, Any]:
        """生成完整 3D 场景配置

        Args:
            layers: 图层列表
            duration: 合成时长（秒）

        Returns:
            {
                "enable_3d": bool,
                "cameras": [...],
                "lights": [...],
                "layer_3d_configs": [...],
                "keyframe_operations": [...],
            }
        """
        if not self.enable_3d:
            return {
                "enable_3d": False,
                "cameras": [],
                "lights": [],
                "layer_3d_configs": [],
                "keyframe_operations": [],
            }

        # 1. 为每个 footage 图层开启 3D
        self._setup_layers_3d(layers)

        # 2. 创建摄像机
        self._create_camera(duration)

        # 3. 创建灯光
        self._create_lights()

        # 4. 生成关键帧操作
        keyframe_ops = self._generate_keyframe_ops(duration)

        return {
            "enable_3d": True,
            "cameras": [
                {
                    "name": cam.get("name", ""),
                    "type": cam.get("type", "camera"),
                    "position": cam.get("position", [960, 540, -1000]),
                    "pointOfInterest": cam.get("pointOfInterest", [960, 540, 0]),
                }
                for cam in self.cameras
            ],
            "lights": [
                {
                    "name": l.name,
                    "light_type": l.light_type,
                    "position": l.position,
                    "intensity": l.intensity,
                    "color": l.color,
                    "casts_shadows": l.casts_shadows,
                }
                for l in self.lights
            ],
            "layer_3d_configs": [
                {
                    "layer_name": l.layer_name,
                    "three_d_enabled": l.three_d_enabled,
                    "z_position": l.z_position,
                }
                for l in self.layers_3d
            ],
            "keyframe_operations": keyframe_ops,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _setup_layers_3d(self, layers: List[Dict]) -> None:
        """为 footage 图层开启 3D，按顺序分配 Z 轴深度"""
        footage_layers = [l for l in layers if l["type"] == "footage"]
        count = max(len(footage_layers), 1)
        for i, layer in enumerate(footage_layers):
            # 每层错开 depth/count 的距离，从前到后排列
            z_pos = (i - count / 2) * (self.depth / count)
            cfg = Layer3DConfig(
                layer_name=layer["name"],
                three_d_enabled=True,
                z_position=z_pos,
            )
            self.layers_3d.append(cfg)

    def _create_camera(self, duration: float) -> None:
        """创建摄像机"""
        cam_type = self._camera_config.get("camera_type", "cinematic")
        move_type = self._camera_config.get("camera_move", "push")

        start_z = -1500
        end_z = -800

        if move_type == "push":
            start_pos = [self.comp_width / 2, self.comp_height / 2, start_z]
            end_pos = [self.comp_width / 2, self.comp_height / 2, end_z]
        elif move_type == "pull":
            start_pos = [self.comp_width / 2, self.comp_height / 2, end_z]
            end_pos = [self.comp_width / 2, self.comp_height / 2, start_z]
        elif move_type == "handheld":
            start_pos = [self.comp_width / 2 + 10, self.comp_height / 2 - 5, start_z]
            end_pos = [self.comp_width / 2 - 8, self.comp_height / 2 + 7, end_z + 50]
        else:
            start_pos = [self.comp_width / 2, self.comp_height / 2, start_z]
            end_pos = [self.comp_width / 2, self.comp_height / 2, end_z]

        camera = {
            "name": f"Camera_{cam_type}",
            "type": "camera",
            "start_time": 0.0,
            "duration": duration,
            "position": start_pos,
            "pointOfInterest": [self.comp_width / 2, self.comp_height / 2, 0],
            "move": CameraMove(
                type=move_type,
                duration=duration,
                start_position=start_pos,
                end_position=end_pos,
            ),
        }
        self.cameras.append(camera)

    def _create_lights(self) -> None:
        """根据风格创建灯光"""
        light_names = self._camera_config.get("lights", [])
        center = [self.comp_width / 2, self.comp_height / 2, -500]

        light_templates = {
            "key_light": LightConfig(
                name="Key Light", light_type="point",
                position=[center[0] - 200, center[1] - 200, -1000],
                intensity=100, color=[255, 255, 240],
            ),
            "fill_light": LightConfig(
                name="Fill Light", light_type="point",
                position=[center[0] + 300, center[1] + 100, -800],
                intensity=50, color=[200, 220, 255],
            ),
            "rim_light": LightConfig(
                name="Rim Light", light_type="point",
                position=[center[0], center[1] - 300, 200],
                intensity=80, color=[255, 255, 255],
            ),
            "ambient": LightConfig(
                name="Ambient", light_type="ambient",
                position=center,
                intensity=30, color=[255, 255, 255],
            ),
            "soft_key": LightConfig(
                name="Soft Key", light_type="point",
                position=[center[0] - 150, center[1] - 100, -800],
                intensity=70, color=[255, 240, 230],
            ),
            "multi_color": LightConfig(
                name="Color Light", light_type="point",
                position=[center[0] + 200, center[1] - 200, -600],
                intensity=100, color=[255, 100, 200],
            ),
            "single_rim": LightConfig(
                name="Rim", light_type="point",
                position=[center[0], center[1] - 250, 300],
                intensity=60, color=[180, 200, 255],
            ),
            "low_ambient": LightConfig(
                name="Low Ambient", light_type="ambient",
                position=center,
                intensity=15, color=[100, 120, 150],
            ),
        }

        for name in light_names:
            if name in light_templates:
                self.lights.append(light_templates[name])

    def _generate_keyframe_ops(self, duration: float) -> List[Dict]:
        """生成 3D 关键帧操作列表"""
        ops = []

        for cam in self.cameras:
            move = cam.get("move")
            if not move:
                continue
            ops.append({
                "op": "setKeyframe",
                "layerName": cam["name"],
                "propertyPath": "Transform/Position",
                "keyframes": [
                    {"time": 0.0, "value": move.start_position, "ease": "ease_in_out"},
                    {"time": duration, "value": move.end_position, "ease": "ease_in_out"},
                ],
                "_3d": True,
                "_camera": True,
            })

        return ops


# ---------------------------------------------------------------------------
# 快捷函数
# ---------------------------------------------------------------------------

def generate_3d_scene(
    style: str,
    layers: List[Dict],
    duration: float,
    comp_width: int = 1920,
    comp_height: int = 1080,
) -> Dict[str, Any]:
    """快捷函数：生成 3D 场景"""
    orch = Scene3DOrchestrator(style, comp_width, comp_height)
    return orch.generate_scene(layers, duration)
