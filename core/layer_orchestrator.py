"""
layer_orchestrator.py
Phase 3 - 多图层复杂编排智能

用途：自动处理图层间的复杂关系，包括：
  - 轨道遮罩（Track Matte）：Silhouette roto 输出 → 自动创建 Track Matte
  - 混合模式（Blend Mode）：根据效果类型自动选择 Screen/Add/Multiply 等
  - 父子关系（Parenting）：摄像机 → 多图层的父子链接
  - 调整图层（Adjustment Layer）：批量效果应用到调整层

设计对齐：scene_orchestrator.py / effect_composer.py 的模块结构
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

__all__ = [
    "TrackMateConfig",
    "BlendModeRule",
    "AdjustmentLayerConfig",
    "LayerOrchestrator",
    "apply_track_matte",
    "suggest_blend_mode",
    "create_adjustment_layer",
]


# ---------------------------------------------------------------------------
# 数据类
# ---------------------------------------------------------------------------

@dataclass
class TrackMateConfig:
    """轨道遮罩配置"""
    matte_layer: str
    target_layer: str
    matte_type: str = "alpha"  # alpha / alpha_inverted / luma / luma_inverted


@dataclass
class BlendModeRule:
    """混合模式规则"""
    effect_match_name: str = ""
    style: str = ""
    blend_mode: str = "normal"  # normal / screen / add / multiply / overlay / soft_light


@dataclass
class AdjustmentLayerConfig:
    """调整图层配置"""
    name: str
    effects: list[dict[str, Any]] = field(default_factory=list)
    startTime: float = 0.0
    duration: float = 0.0


# ---------------------------------------------------------------------------
# 主编排器
# ---------------------------------------------------------------------------

class LayerOrchestrator:
    """多图层编排器"""

    # 效果 → 混合模式映射
    EFFECT_BLEND_MODE_MAP: dict[str, str] = {
        "ADBE Glo2": "screen",
        "ADBE Glo": "screen",
        "ADBE Lens Flare": "screen",
        "ADBE Light Burst 2": "screen",
        "ADBE Light Sweep": "screen",
        "ADBE Inner Glow": "screen",
        "ADBE Drop Shadow": "multiply",
        "ADBE Color Balance": "soft_light",
        "ADBE Photo Filter": "soft_light",
        "ADBE Gradient Ramp": "overlay",
        "ADBE Ramp": "overlay",
        "ADBE Noise": "overlay",
        "ADBE Colorama": "color",
        "ADBE Tint": "tint",
    }

    # 风格 → 调整图层效果映射
    STYLE_ADJUSTMENT_EFFECTS: dict[str, list[str]] = {
        "cinematic": ["ADBE Color Balance", "ADBE Photo Filter", "ADBE Sharpen"],
        "vibrant": ["ADBE Hue/Saturation", "ADBE Glo2", "ADBE Color Balance"],
        "dreamy": ["ADBE Gaussian Blur 2", "ADBE Glo2", "ADBE Photo Filter"],
        "dark_moody": ["ADBE Color Balance", "ADBE Curves", "ADBE Photo Filter"],
        "minimalist": ["ADBE Sharpn"],
        "fast_cut": [],
        "slow_motion": ["ADBE Pixel Motion Blur", "ADBE Sharpen"],
        "soft_dreamy": ["ADBE Gaussian Blur 2", "ADBE Glo2"],
    }

    def __init__(self) -> None:
        self.track_mattes: list[TrackMateConfig] = []
        self.parent_relationships: list[tuple[str, str]] = []
        self.adjustment_layers: list[AdjustmentLayerConfig] = []
        self.blend_mode_assignments: dict[str, str] = {}

    # ------------------------------------------------------------------
    # 公共 API
    # ------------------------------------------------------------------

    def orchestrate(
        self,
        layers: list[dict],
        effects: list[dict],
        style: str = "cinematic",
        silhouette_artifacts: list[dict] | None = None,
    ) -> dict[str, Any]:
        """完整编排多图层关系

        Args:
            layers: 图层列表
            effects: 效果列表
            style: 风格
            silhouette_artifacts: Silhouette 产出（用于自动轨道遮罩）

        Returns:
            {
                "track_mattes": [...],
                "parent_relationships": [...],
                "adjustment_layers": [...],
                "blend_modes": {layer_name: blend_mode},
                "layer_operations": [...],  # 可注入 plan 的操作列表
            }
        """
        # 1. 轨道遮罩：Silhouette 产出 → Track Matte
        if silhouette_artifacts:
            self._create_track_mattes_from_silhouette(silhouette_artifacts, layers)

        # 2. 混合模式：根据效果自动分配
        self._assign_blend_modes(effects, style)

        # 3. 父子关系：3D 摄像机 → 3D 图层
        self._create_parent_relationships(layers)

        # 4. 调整图层：批量全局效果
        self._create_adjustment_layers(layers, effects, style)

        # 5. 生成操作列表
        operations = self._generate_operations()

        return {
            "track_mattes": [
                {"matte_layer": t.matte_layer, "target_layer": t.target_layer, "matte_type": t.matte_type}
                for t in self.track_mattes
            ],
            "parent_relationships": [
                {"child": child, "parent": parent}
                for child, parent in self.parent_relationships
            ],
            "adjustment_layers": [
                {
                    "name": a.name,
                    "effects": a.effects,
                    "startTime": a.startTime,
                    "duration": a.duration,
                }
                for a in self.adjustment_layers
            ],
            "blend_modes": dict(self.blend_mode_assignments),
            "layer_operations": operations,
        }

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _create_track_mattes_from_silhouette(
        self, artifacts: list[dict], layers: list[dict],
    ) -> None:
        """从 Silhouette 产出创建轨道遮罩"""
        footage_layers = [l for l in layers if l["type"] == "footage"]

        for art in artifacts:
            if art.get("status") != "success":
                continue
            ae_data = art.get("ae_integration_data", {})
            if not ae_data:
                continue

            # roto 类型 → 创建 alpha track matte
            if ae_data.get("type") == "matte" and footage_layers:
                matte_layer_name = f"Matte_{art.get('command', 'roto')}"
                target_layer = footage_layers[0]["name"]
                self.track_mattes.append(TrackMateConfig(
                    matte_layer=matte_layer_name,
                    target_layer=target_layer,
                    matte_type="alpha",
                ))

    def _assign_blend_modes(self, effects: list[dict], style: str) -> None:
        """根据效果类型分配混合模式"""
        style_blend_overrides = {
            "vibrant": "overlay",
            "dreamy": "screen",
            "dark_moody": "multiply",
            "soft_dreamy": "soft_light",
        }
        default_blend = style_blend_overrides.get(style, "normal")

        for effect in effects:
            layer_name = effect.get("layerName", "")
            match_name = effect.get("matchName", "")
            if not layer_name:
                continue

            # 效果级别的混合模式优先
            if match_name in self.EFFECT_BLEND_MODE_MAP:
                self.blend_mode_assignments[layer_name] = self.EFFECT_BLEND_MODE_MAP[match_name]
            elif style in style_blend_overrides and layer_name not in self.blend_mode_assignments:
                self.blend_mode_assignments[layer_name] = default_blend

    def _create_parent_relationships(self, layers: list[dict]) -> None:
        """创建父子关系：3D 摄像机作为 3D 图层的父级"""
        cameras = [l for l in layers if l.get("type") == "camera"]
        three_d_layers = [l for l in layers if l.get("threeD") and l.get("type") == "footage"]

        if cameras and three_d_layers:
            main_camera = cameras[0]
            for layer in three_d_layers:
                self.parent_relationships.append((layer["name"], main_camera["name"]))

    def _create_adjustment_layers(
        self, layers: list[dict], effects: list[dict], style: str,
    ) -> None:
        """创建调整图层（全局效果）"""
        adj_effects = self.STYLE_ADJUSTMENT_EFFECTS.get(style, [])
        if not adj_effects:
            return

        # 计算合成时长
        max_duration = max((l.get("duration", 0) for l in layers), default=5.0)

        adj_effect_list = [
            {"effectName": name, "matchName": name, "settings": {}}
            for name in adj_effects
        ]

        self.adjustment_layers.append(AdjustmentLayerConfig(
            name=f"Adjustment_{style}",
            effects=adj_effect_list,
            startTime=0.0,
            duration=max_duration,
        ))

    def _generate_operations(self) -> list[dict]:
        """生成可注入 plan 的操作列表"""
        ops = []

        # 轨道遮罩操作
        for tm in self.track_mattes:
            ops.append({
                "op": "setTrackMatte",
                "layerName": tm.target_layer,
                "matteLayerName": tm.matte_layer,
                "matteType": tm.matte_type,
                "_track_matte": True,
            })

        # 父子关系操作
        for child, parent in self.parent_relationships:
            ops.append({
                "op": "setParent",
                "childLayerName": child,
                "parentLayerName": parent,
                "_parenting": True,
            })

        # 混合模式操作
        for layer_name, blend_mode in self.blend_mode_assignments.items():
            ops.append({
                "op": "setBlendMode",
                "layerName": layer_name,
                "blendMode": blend_mode,
                "_blend_mode": True,
            })

        # 调整图层操作
        for adj in self.adjustment_layers:
            ops.append({
                "op": "addLayer",
                "layerType": "adjustment",
                "name": adj.name,
                "startTime": adj.startTime,
                "duration": adj.duration,
                "effects": adj.effects,
                "_adjustment_layer": True,
            })

        return ops


# ---------------------------------------------------------------------------
# 快捷函数
# ---------------------------------------------------------------------------

def apply_track_matte(
    target_layer: str,
    matte_layer: str,
    matte_type: str = "alpha",
) -> dict[str, Any]:
    """快捷函数：创建轨道遮罩操作"""
    return {
        "op": "setTrackMatte",
        "layerName": target_layer,
        "matteLayerName": matte_layer,
        "matteType": matte_type,
    }


def suggest_blend_mode(effect_match_name: str, style: str = "cinematic") -> str:
    """快捷函数：推荐混合模式"""
    orch = LayerOrchestrator()
    if effect_match_name in orch.EFFECT_BLEND_MODE_MAP:
        return orch.EFFECT_BLEND_MODE_MAP[effect_match_name]
    style_overrides = {
        "vibrant": "overlay",
        "dreamy": "screen",
        "dark_moody": "multiply",
    }
    return style_overrides.get(style, "normal")


def create_adjustment_layer(
    name: str,
    effects: list[dict],
    duration: float = 5.0,
) -> dict[str, Any]:
    """快捷函数：创建调整图层"""
    return {
        "op": "addLayer",
        "layerType": "adjustment",
        "name": name,
        "startTime": 0.0,
        "duration": duration,
        "effects": effects,
    }
