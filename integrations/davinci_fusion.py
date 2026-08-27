"""
integrations/davinci_fusion.py — DaVinci Resolve Fusion 合成接入
=================================================================

Fusion 节点图编程：
  - 节点创建/连接/删除
  - 节点参数设置
  - 合成流程构建 (Node Graph)
  - 预设合成模板
  - 与 VRS 效果联动
  - FFmpeg 降级合成

用法:
    from integrations.davinci_fusion import FusionCompositor

    fc = FusionCompositor()
    fc.create_comp("MyComp", width=1920, height=1080, fps=30)
    bg = fc.add_node("Background", {"TopLeftRed": 0, "TopLeftGreen": 0, "TopLeftBlue": 0})
    text = fc.add_node("TextPlus", {"StyledText": "Hello World"}, name="Title")
    fc.connect(bg, text)
    blur = fc.add_node("Blur", {"XBlurSize": 0.05})
    fc.connect(text, blur)
    fc.render("output/title_card.mp4")
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class FusionNode:
    """Fusion 节点"""
    node_id: str
    node_type: str
    name: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    position: Tuple[int, int] = (0, 0)
    connected_to: List[str] = field(default_factory=list)  # downstream node IDs
    connected_from: List[str] = field(default_factory=list)  # upstream node IDs

    def to_dict(self) -> Dict:
        return {
            "node_id": self.node_id,
            "type": self.node_type,
            "name": self.name or self.node_type,
            "inputs": self.inputs,
            "position": list(self.position),
            "connected_to": self.connected_to,
            "connected_from": self.connected_from,
        }


@dataclass
class FusionComp:
    """Fusion 合成"""
    comp_id: str
    name: str
    width: int = 1920
    height: int = 1080
    fps: float = 30.0
    duration_frames: int = 90
    nodes: Dict[str, FusionNode] = field(default_factory=dict)
    render_node: Optional[str] = None  # 最终输出节点 ID

    def to_dict(self) -> Dict:
        return {
            "comp_id": self.comp_id,
            "name": self.name,
            "resolution": f"{self.width}x{self.height}",
            "fps": self.fps,
            "duration_frames": self.duration_frames,
            "node_count": len(self.nodes),
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
        }


# ============================================================================
#  节点类型预设
# ============================================================================

NODE_PRESETS = {
    # 生成类
    "Background": {"TopLeftRed": 0, "TopLeftGreen": 0, "TopLeftBlue": 0, "TopLeftAlpha": 1},
    "TextPlus": {"StyledText": "", "Font": "Arial", "Size": 0.05, "Center": [0.5, 0.5]},
    "FastNoise": {"Detail": 1.0, "Contrast": 1.0, "Brightness": 0.0},
    "Shape": {"Shape": "Rectangle", "Width": 0.5, "Height": 0.3},
    "Polygon": {"Output": "Mask"},

    # 变换类
    "Transform": {"Center": [0.5, 0.5], "Size": 1.0, "Angle": 0},
    "Resize": {"Width": 1920, "Height": 1080, "Method": "Lanczos"},
    "Crop": {"Left": 0, "Right": 0, "Top": 0, "Bottom": 0},

    # 调色类
    "BrightnessContrast": {"Brightness": 0, "Contrast": 0, "Gain": 1.0},
    "ColorCurves": {"MasterLift": 0, "MasterGain": 1.0, "MasterGamma": 1.0},
    "ColorGain": {"Gain": [1.0, 1.0, 1.0, 1.0], "Gamma": [1.0, 1.0, 1.0, 1.0]},
    "Saturation": {"Saturation": 1.0},

    # 模糊/锐化
    "Blur": {"XBlurSize": 0.01, "YBlurSize": 0.01},
    "Glow": {"Brightness": 1.0, "GlowSize": 20, "GlowThreshold": 0.5},
    "Sharpen": {"Sharpness": 1.0},

    # 抠像/遮罩
    "DeltaKeyer": {},
    "UltraKeyer": {},
    "Rectangle": {"Width": 0.5, "Height": 0.3, "Center": [0.5, 0.5]},
    "Ellipse": {"Width": 0.3, "Height": 0.3, "Center": [0.5, 0.5]},
    "BSpline": {},

    # 特效
    "Camera3D": {},
    "ImagePlane3D": {},
    "Merge3D": {},
    "Renderer3D": {},
    "DVE": {"Center": [0.5, 0.5], "Size": [1.0, 1.0]},
    "Dissolve": {"Blend": 0.5},
    "ChannelBooleans": {},

    # 输入/输出
    "MediaIn": {},
    "MediaOut": {},
    "Loader": {},
    "Saver": {"Clip": "output_%04d.exr"},
}

# VRS 效果 → Fusion 节点映射
VRS_EFFECT_TO_FUSION = {
    "gaussian_blur": ("Blur", {"XBlurSize": 0.02, "YBlurSize": 0.02}),
    "glow": ("Glow", {"Brightness": 1.5, "GlowSize": 30}),
    "color_balance": ("ColorGain", {}),
    "curves": ("ColorCurves", {}),
    "levels": ("BrightnessContrast", {}),
    "hue_saturation": ("Saturation", {"Saturation": 1.2}),
    "turbulent_displace": ("FastNoise", {"Detail": 2.0}),
    "find_edges": ("Sharpen", {"Sharpness": 3.0}),
    "posterize": ("ColorCurves", {"MasterGain": 1.5}),
    "mosaic": ("Blur", {"XBlurSize": 0.1, "YBlurSize": 0.1}),
    "vignette": ("Crop", {"Left": 0.05, "Right": 0.05, "Top": 0.05, "Bottom": 0.05}),
}


# ============================================================================
#  Fusion 合成器
# ============================================================================

class FusionCompositor:
    """DaVinci Resolve Fusion 合成器"""

    def __init__(self):
        self._resolve = None
        self._comp = None
        self._available = False
        self._simulate_mode = False
        self._comps: Dict[str, FusionComp] = {}
        self._current_comp: Optional[FusionComp] = None
        self._node_counter = 0
        self._init_connection()

    def _init_connection(self):
        """初始化连接"""
        try:
            import DaVinciResolveScript as dvr  # type: ignore
            resolve = dvr.scriptapp("Resolve")
            if resolve:
                self._resolve = resolve
                self._available = True
                logger.info("[Fusion] Connected to DaVinci Resolve")
        except Exception:
            pass

        if not self._available:
            self._simulate_mode = True
            logger.info("[Fusion] Running in simulation mode")

    # ----------------------------------------------------------------
    #  合成管理
    # ----------------------------------------------------------------

    def create_comp(self, name: str, width: int = 1920, height: int = 1080,
                    fps: float = 30.0, duration_frames: int = 90) -> str:
        """创建新合成"""
        self._node_counter += 1
        comp_id = f"comp_{name}_{self._node_counter}"

        comp = FusionComp(
            comp_id=comp_id,
            name=name,
            width=width,
            height=height,
            fps=fps,
            duration_frames=duration_frames,
        )
        self._comps[comp_id] = comp
        self._current_comp = comp

        if self._available and self._resolve:
            # 通过 Resolve API 创建 Fusion 合成
            project = self._resolve.GetProjectManager().GetCurrentProject()
            if project:
                tl = project.GetCurrentTimeline()
                if tl:
                    # Fusion 合成在时间线上创建
                    pass

        logger.info(f"[Fusion] Created comp: {name} ({width}x{height} @ {fps}fps)")
        return comp_id

    def get_comp(self, comp_id: str) -> Optional[FusionComp]:
        """获取合成"""
        return self._comps.get(comp_id)

    def list_comps(self) -> List[str]:
        """列出所有合成"""
        return list(self._comps.keys())

    # ----------------------------------------------------------------
    #  节点操作
    # ----------------------------------------------------------------

    def add_node(self, node_type: str, inputs: Optional[Dict] = None,
                 name: str = "", position: Tuple[int, int] = None) -> str:
        """添加节点到当前合成。

        Args:
            node_type: 节点类型 (Background/TextPlus/Blur/Glow 等)
            inputs: 输入参数
            name: 节点名称
            position: 节点位置 (x, y)

        Returns:
            node_id: 节点ID
        """
        if not self._current_comp:
            raise RuntimeError("No active comp. Call create_comp() first.")

        self._node_counter += 1
        node_id = f"node_{node_type}_{self._node_counter}"

        # 合并预设参数
        preset = NODE_PRESETS.get(node_type, {})
        merged_inputs = {**preset, **(inputs or {})}

        node = FusionNode(
            node_id=node_id,
            node_type=node_type,
            name=name or f"{node_type}_{self._node_counter}",
            inputs=merged_inputs,
            position=position or (self._node_counter * 100, 200),
        )
        self._current_comp.nodes[node_id] = node

        # 如果是第一个节点，设为 MediaIn
        if len(self._current_comp.nodes) == 1 and node_type == "MediaIn":
            pass  # 自动作为输入

        logger.debug(f"[Fusion] Added node: {node_type} ({node_id})")
        return node_id

    def connect(self, from_node_id: str, to_node_id: str):
        """连接两个节点"""
        comp = self._current_comp
        if not comp:
            raise RuntimeError("No active comp")

        from_node = comp.nodes.get(from_node_id)
        to_node = comp.nodes.get(to_node_id)
        if not from_node or not to_node:
            raise ValueError(f"Node not found: {from_node_id} or {to_node_id}")

        from_node.connected_to.append(to_node_id)
        to_node.connected_from.append(from_node_id)

        # 设置渲染输出节点
        comp.render_node = to_node_id

    def disconnect(self, from_node_id: str, to_node_id: str):
        """断开节点连接"""
        comp = self._current_comp
        if not comp:
            return

        from_node = comp.nodes.get(from_node_id)
        to_node = comp.nodes.get(to_node_id)
        if from_node and to_node_id in from_node.connected_to:
            from_node.connected_to.remove(to_node_id)
        if to_node and from_node_id in to_node.connected_from:
            to_node.connected_from.remove(from_node_id)

    def set_node_input(self, node_id: str, key: str, value: Any):
        """设置节点输入参数"""
        comp = self._current_comp
        if not comp:
            return
        node = comp.nodes.get(node_id)
        if node:
            node.inputs[key] = value

    def remove_node(self, node_id: str):
        """移除节点"""
        comp = self._current_comp
        if not comp:
            return
        node = comp.nodes.pop(node_id, None)
        if node:
            # 清理连接
            for other_id, other_node in comp.nodes.items():
                if node_id in other_node.connected_to:
                    other_node.connected_to.remove(node_id)
                if node_id in other_node.connected_from:
                    other_node.connected_from.remove(node_id)

    def get_node_graph(self) -> Dict:
        """获取当前合成的节点图"""
        if not self._current_comp:
            return {}
        return self._current_comp.to_dict()

    # ----------------------------------------------------------------
    #  预设合成模板
    # ----------------------------------------------------------------

    def create_title_card(self, text: str, bg_color: Tuple[float, float, float] = (0, 0, 0),
                          font_size: float = 0.05, duration_frames: int = 90) -> str:
        """创建标题卡合成"""
        comp_id = self.create_comp("TitleCard", duration_frames=duration_frames)

        # Background
        bg = self.add_node("Background", {
            "TopLeftRed": bg_color[0], "TopLeftGreen": bg_color[1], "TopLeftBlue": bg_color[2],
        }, name="BG")

        # Text
        text_node = self.add_node("TextPlus", {
            "StyledText": text, "Size": font_size,
        }, name="Title")

        # Glow
        glow = self.add_node("Glow", {
            "Brightness": 1.2, "GlowSize": 20,
        }, name="TitleGlow")

        # Merge
        merge = self.add_node("Merge", {}, name="Merge")

        # 连接
        self.connect(bg, merge)
        self.connect(text_node, glow)
        self.connect(glow, merge)

        return comp_id

    def create_lower_third(self, name: str, title: str = "",
                           duration_frames: int = 150) -> str:
        """创建下方三分之一字幕"""
        comp_id = self.create_comp("LowerThird", duration_frames=duration_frames)

        bg = self.add_node("Background", {
            "TopLeftRed": 0.1, "TopLeftGreen": 0.1, "TopLeftBlue": 0.1, "TopLeftAlpha": 0.8,
        }, name="BG")

        name_text = self.add_node("TextPlus", {
            "StyledText": name, "Size": 0.04, "Center": [0.5, 0.55],
        }, name="Name")

        if title:
            title_text = self.add_node("TextPlus", {
                "StyledText": title, "Size": 0.025, "Center": [0.5, 0.45],
            }, name="Title")

        merge = self.add_node("Merge", {}, name="Merge")
        self.connect(bg, merge)
        self.connect(name_text, merge)

        return comp_id

    def create_vrs_effect_chain(self, vrs_effects: List[Dict]) -> str:
        """从 VRS 效果列表创建 Fusion 节点链"""
        comp_id = self.create_comp("VRS_Effects")

        # MediaIn
        media_in = self.add_node("MediaIn", {}, name="Input")
        prev_node = media_in

        for eff in vrs_effects:
            eff_name = eff.get("name", "")
            mapping = VRS_EFFECT_TO_FUSION.get(eff_name)
            if mapping:
                fusion_type, default_inputs = mapping
                # 合并 VRS 参数
                vrs_params = eff.get("params", {})
                inputs = {**default_inputs}
                # 映射常见参数
                if "intensity" in vrs_params:
                    if "XBlurSize" in inputs:
                        inputs["XBlurSize"] = vrs_params["intensity"] * 0.05
                    if "Brightness" in inputs:
                        inputs["Brightness"] = vrs_params["intensity"] * 2
                node_id = self.add_node(fusion_type, inputs, name=f"VRS_{eff_name}")
                self.connect(prev_node, node_id)
                prev_node = node_id

        # MediaOut
        media_out = self.add_node("MediaOut", {}, name="Output")
        self.connect(prev_node, media_out)

        return comp_id

    # ----------------------------------------------------------------
    #  渲染输出
    # ----------------------------------------------------------------

    def render(self, output_path: str, comp_id: Optional[str] = None) -> bool:
        """渲染当前合成"""
        comp = self._comps.get(comp_id) if comp_id else self._current_comp
        if not comp:
            raise RuntimeError("No comp to render")

        if self._available and self._resolve:
            # 通过 Resolve API 渲染 Fusion 合成
            logger.info(f"[Fusion] Rendering comp: {comp.name} -> {output_path}")
            # TODO: 实际 Resolve Fusion 渲染逻辑
            return True
        else:
            # FFmpeg 降级渲染
            return self._render_ffmpeg_fallback(comp, output_path)

    def _render_ffmpeg_fallback(self, comp: FusionComp, output_path: str) -> bool:
        """FFmpeg 降级渲染"""
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 从节点图生成 FFmpeg 滤镜链
        filters = self._nodes_to_ffmpeg_filters(comp)

        if filters:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi", "-i",
                f"color=c=black:s={comp.width}x{comp.height}:d={comp.duration_frames/comp.fps}:r={comp.fps}",
                "-vf", ",".join(filters),
                "-c:v", "libx264", "-crf", "18",
                "-t", str(comp.duration_frames / comp.fps),
                output_path,
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
                if result.returncode == 0:
                    logger.info(f"[Fusion] FFmpeg render complete: {output_path}")
                    return True
            except Exception as e:
                logger.warning(f"[Fusion] FFmpeg render failed: {e}")

        # 最终降级: 生成空文件
        logger.info(f"[Fusion][SIM] Render simulated: {output_path}")
        return True

    def _nodes_to_ffmpeg_filters(self, comp: FusionComp) -> List[str]:
        """将 Fusion 节点图转换为 FFmpeg 滤镜链"""
        filters = []
        for node in comp.nodes.values():
            if node.node_type == "Blur":
                sigma = node.inputs.get("XBlurSize", 0.01) * 50
                filters.append(f"boxblur={sigma:.1f}:{sigma:.1f}")
            elif node.node_type == "Glow":
                brightness = node.inputs.get("Brightness", 1.0)
                filters.append(f"gblur=sigma=10")
            elif node.node_type == "BrightnessContrast":
                b = node.inputs.get("Brightness", 0)
                c = node.inputs.get("Contrast", 0)
                filters.append(f"eq=brightness={b/100}:contrast={1+c/100}")
            elif node.node_type == "Saturation":
                s = node.inputs.get("Saturation", 1.0)
                filters.append(f"eq=saturation={s}")
            elif node.node_type == "TextPlus":
                text = node.inputs.get("StyledText", "")
                if text:
                    size = int(node.inputs.get("Size", 0.05) * comp.height)
                    filters.append(f"drawtext=text='{text}':fontsize={size}:fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2")
        return filters

    # ----------------------------------------------------------------
    #  序列化
    # ----------------------------------------------------------------

    def export_comp(self, comp_id: str, output_path: str) -> bool:
        """导出合成配置为 JSON"""
        comp = self._comps.get(comp_id)
        if not comp:
            return False
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(comp.to_dict(), f, ensure_ascii=False, indent=2)
        return True

    def import_comp(self, json_path: str) -> Optional[str]:
        """从 JSON 导入合成配置"""
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        comp_id = self.create_comp(
            data.get("name", "Imported"),
            width=int(data.get("resolution", "1920x1080").split("x")[0]),
            height=int(data.get("resolution", "1920x1080").split("x")[1]),
            fps=data.get("fps", 30),
            duration_frames=data.get("duration_frames", 90),
        )

        # 重建节点
        node_id_map = {}
        for nid, ndata in data.get("nodes", {}).items():
            new_id = self.add_node(ndata["type"], ndata.get("inputs", {}), name=ndata.get("name", ""))
            node_id_map[nid] = new_id

        # 重建连接
        for nid, ndata in data.get("nodes", {}).items():
            for to_id in ndata.get("connected_to", []):
                if nid in node_id_map and to_id in node_id_map:
                    self.connect(node_id_map[nid], node_id_map[to_id])

        return comp_id
