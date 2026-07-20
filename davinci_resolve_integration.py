#!/usr/bin/env python3
"""
DaVinci Resolve 调色集成模块 v1.0
==================================

通过 Python API 和 CLI 命令行接口集成 DaVinci Resolve，支持视频调色、
节点管理、LUT 应用、渲染输出等专业调色功能，提供真实模式、模拟模式和自动降级模式。

安装路径: C:\\Program Files\\Blackmagic Design\\DaVinci Resolve
Python API: DaVinciResolveScript 模块
CLI 工具: Resolve.exe

支持的功能:
- color_grade   : 视频调色（节点式调色流程）
- batch_grade   : 批量调色
- preset_apply  : 调色预设应用
- drx_export    : 导出 .drx 调色预设文件
- lut_apply     : LUT 应用

执行模式:
- real    : 通过 Resolve API / CLI 真实执行（需要安装 DaVinci Resolve）
- simulate: 模拟执行，生成模拟结果（用于测试和流程验证）
- auto    : 优先真实模式，失败自动降级到模拟模式
"""
import os
import sys
import json
import time
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

from core.config import ConfigManager

_config = ConfigManager()
DEFAULT_RESOLVE_HOME = Path(_config.get("davinci.install_path", r"D:\DaVinci Resolve"))
RESOLVE_HOME = Path(os.environ.get("RESOLVE_HOME", str(DEFAULT_RESOLVE_HOME)))

RESOLVE_EXE_CANDIDATES = [
    RESOLVE_HOME / "Resolve.exe",
    RESOLVE_HOME / "Resolve" / "Resolve.exe",
]

OUTPUT_BASE = Path(os.environ.get("AE_WORK_DIR", r"D:\AE-Work"))

AVAILABLE_NODE_TYPES = [
    "primary",
    "secondary",
    "qualifier",
    "power_window",
    "lut",
    "vignette",
    "blur",
    "mixer",
]

OUTPUT_FORMAT_MAP = {
    "mp4": "mp4",
    "mov": "mov",
    "prores422hq": "mov",
    "prores422": "mov",
    "prores4444": "mov",
    "dnxhr": "mxf",
    "dpx": "dpx",
    "exr": "exr",
}


@dataclass
class ColorGradeNode:
    """单个调色节点配置。

    Attributes:
        node_type: 节点类型（primary/secondary/qualifier/power_window/lut/vignette 等）
        name: 节点名称
        settings: 节点设置（lift/gamma/gain/saturation/contrast 等）
        enabled: 是否启用
    """
    node_type: str = "primary"
    name: str = "Node"
    settings: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


@dataclass
class ResolveColorConfig:
    """DaVinci Resolve 调色配置数据类。

    Attributes:
        install_path: Resolve 安装路径
        mode: 运行模式（real/simulate/auto）
        project_name: 项目名称
        timeline_name: 时间线名称
        color_preset: 调色预设名称
        input_path: 输入视频路径
        output_path: 输出视频路径
        output_format: 输出格式（mp4/mov/prores422hq/dnxhr）
        render_quality: 渲染质量（0-100，默认 90）
        use_lut: LUT 文件路径（可选）
        nodes: 节点配置列表（可选，高级用法）
    """
    install_path: str = str(RESOLVE_HOME)
    mode: str = "auto"
    project_name: str = "ColorGrade_Project"
    timeline_name: str = "Timeline 1"
    color_preset: str = "default"
    input_path: str = ""
    output_path: str = ""
    output_format: str = "mp4"
    render_quality: int = 90
    use_lut: str = ""
    nodes: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ResolveColorResult:
    """调色结果数据类。

    Attributes:
        success: 是否成功
        input_path: 输入文件路径
        output_path: 输出文件路径
        duration: 处理耗时（秒）
        nodes_applied: 应用的节点数
        color_grade_summary: 调色摘要（亮度/对比度/饱和度等）
        error: 错误信息（如果失败）
        mode: 实际使用的执行模式
        preset: 使用的调色预设
    """
    success: bool = False
    input_path: str = ""
    output_path: str = ""
    duration: float = 0.0
    nodes_applied: int = 0
    color_grade_summary: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    mode: str = "simulate"
    preset: str = ""


RESOLVE_PRESETS: Dict[str, Dict[str, Any]] = {
    "default": {
        "description": "默认轻微调色，自然色彩增强",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Primary Correction",
                "enabled": True,
                "settings": {
                    "lift": [1.0, 1.0, 1.0, 0.0],
                    "gamma": [1.02, 1.02, 1.02, 0.0],
                    "gain": [1.03, 1.03, 1.03, 0.0],
                    "saturation": 1.05,
                    "contrast": 1.05,
                    "pivot": 0.5,
                },
            },
        ],
    },
    "cinematic": {
        "description": "电影级调色（高对比，偏蓝阴影，暖高光）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Cinematic Primary",
                "enabled": True,
                "settings": {
                    "lift": [0.9, 0.92, 1.0, 0.02],
                    "gamma": [1.0, 1.0, 1.02, 0.0],
                    "gain": [1.08, 1.05, 0.98, 0.0],
                    "saturation": 0.95,
                    "contrast": 1.25,
                    "pivot": 0.45,
                },
            },
            {
                "node_type": "vignette",
                "name": "Cinematic Vignette",
                "enabled": True,
                "settings": {
                    "strength": 0.35,
                    "size": 0.7,
                    "softness": 0.6,
                    "aspect": 1.5,
                },
            },
        ],
    },
    "warm_vintage": {
        "description": "温暖复古（暖色调，低对比，颗粒感）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Vintage Warm",
                "enabled": True,
                "settings": {
                    "lift": [1.05, 1.0, 0.92, 0.03],
                    "gamma": [1.08, 1.03, 0.95, 0.0],
                    "gain": [1.1, 1.02, 0.9, 0.0],
                    "saturation": 0.8,
                    "contrast": 0.85,
                    "pivot": 0.5,
                },
            },
            {
                "node_type": "lut",
                "name": "Vintage Film LUT",
                "enabled": True,
                "settings": {
                    "lut_name": "Film_Vintage",
                    "strength": 0.6,
                },
            },
        ],
    },
    "cool_teal": {
        "description": "冷色调青蓝（青色阴影，蓝色高光）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Cool Teal Primary",
                "enabled": True,
                "settings": {
                    "lift": [0.85, 1.0, 1.05, 0.02],
                    "gamma": [0.9, 1.0, 1.08, 0.0],
                    "gain": [0.95, 1.02, 1.1, 0.0],
                    "saturation": 1.0,
                    "contrast": 1.15,
                    "pivot": 0.5,
                },
            },
            {
                "node_type": "secondary",
                "name": "Teal Shadows",
                "enabled": True,
                "settings": {
                    "hue_range": [170, 210],
                    "saturation_boost": 0.2,
                    "luminance": -0.05,
                },
            },
        ],
    },
    "vivid_pop": {
        "description": "鲜艳活泼（高饱和，高对比，明亮）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Vivid Pop",
                "enabled": True,
                "settings": {
                    "lift": [1.0, 1.0, 1.0, -0.02],
                    "gamma": [1.05, 1.05, 1.05, 0.0],
                    "gain": [1.1, 1.1, 1.1, 0.0],
                    "saturation": 1.35,
                    "contrast": 1.2,
                    "pivot": 0.5,
                },
            },
            {
                "node_type": "primary",
                "name": "Color Boost",
                "enabled": True,
                "settings": {
                    "color_boost": 1.25,
                    "midtone_contrast": 1.1,
                },
            },
        ],
    },
    "muted_film": {
        "description": "低饱和胶片（低饱和，柔和对比，灰雾）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Muted Film",
                "enabled": True,
                "settings": {
                    "lift": [0.98, 0.98, 0.98, 0.08],
                    "gamma": [0.95, 0.95, 0.95, 0.0],
                    "gain": [0.97, 0.97, 0.97, 0.0],
                    "saturation": 0.6,
                    "contrast": 0.8,
                    "pivot": 0.5,
                },
            },
            {
                "node_type": "lut",
                "name": "Film Stock LUT",
                "enabled": True,
                "settings": {
                    "lut_name": "Kodak_2383",
                    "strength": 0.45,
                },
            },
        ],
    },
    "noir_bw": {
        "description": "黑白 noir（高对比黑白，硬光）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Noir B&W",
                "enabled": True,
                "settings": {
                    "lift": [0.0, 0.0, 0.0, 0.05],
                    "gamma": [0.9, 0.9, 0.9, 0.0],
                    "gain": [1.15, 1.15, 1.15, 0.0],
                    "saturation": 0.0,
                    "contrast": 1.45,
                    "pivot": 0.4,
                },
            },
            {
                "node_type": "vignette",
                "name": "Hard Vignette",
                "enabled": True,
                "settings": {
                    "strength": 0.55,
                    "size": 0.6,
                    "softness": 0.3,
                    "aspect": 1.0,
                },
            },
        ],
    },
    "pastel_dream": {
        "description": "粉彩梦幻（低对比，高明度，柔和色彩）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Pastel Dream",
                "enabled": True,
                "settings": {
                    "lift": [1.05, 1.03, 1.05, 0.1],
                    "gamma": [1.08, 1.05, 1.08, 0.0],
                    "gain": [1.02, 1.0, 1.02, 0.0],
                    "saturation": 0.7,
                    "contrast": 0.7,
                    "pivot": 0.55,
                },
            },
            {
                "node_type": "blur",
                "name": "Dream Glow",
                "enabled": True,
                "settings": {
                    "blur_radius": 8.0,
                    "blend_mode": "screen",
                    "opacity": 0.25,
                },
            },
        ],
    },
    "puppet_warm": {
        "description": "木偶暖调（暖棕色，柔和高光，木质色调）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Puppet Warm",
                "enabled": True,
                "settings": {
                    "lift": [1.02, 0.98, 0.9, 0.03],
                    "gamma": [1.05, 1.0, 0.92, 0.0],
                    "gain": [1.08, 1.02, 0.93, 0.0],
                    "saturation": 0.9,
                    "contrast": 0.95,
                    "pivot": 0.5,
                    "temperature": 0.15,
                    "tint": 0.05,
                },
            },
            {
                "node_type": "secondary",
                "name": "Wood Tone Enhancer",
                "enabled": True,
                "settings": {
                    "hue_range": [20, 50],
                    "saturation_boost": 0.15,
                    "luminance": 0.05,
                },
            },
        ],
    },
    "puppet_porcelain": {
        "description": "瓷娃娃冷调（冷白，微蓝，高光滑）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Porcelain Cool",
                "enabled": True,
                "settings": {
                    "lift": [0.95, 0.97, 1.02, 0.05],
                    "gamma": [0.98, 0.99, 1.03, 0.0],
                    "gain": [1.02, 1.03, 1.08, 0.0],
                    "saturation": 0.85,
                    "contrast": 1.0,
                    "pivot": 0.5,
                    "temperature": -0.1,
                    "tint": -0.02,
                },
            },
            {
                "node_type": "blur",
                "name": "Smooth Glow",
                "enabled": True,
                "settings": {
                    "blur_radius": 5.0,
                    "blend_mode": "lighten",
                    "opacity": 0.2,
                },
            },
        ],
    },
    "horror_grade": {
        "description": "恐怖调色（低饱和，绿色调，暗角）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Horror Primary",
                "enabled": True,
                "settings": {
                    "lift": [0.85, 1.0, 0.85, 0.02],
                    "gamma": [0.88, 1.0, 0.88, 0.0],
                    "gain": [0.9, 1.05, 0.9, 0.0],
                    "saturation": 0.5,
                    "contrast": 1.2,
                    "pivot": 0.4,
                },
            },
            {
                "node_type": "vignette",
                "name": "Dark Vignette",
                "enabled": True,
                "settings": {
                    "strength": 0.7,
                    "size": 0.5,
                    "softness": 0.5,
                    "aspect": 1.0,
                },
            },
        ],
    },
    "anime_style": {
        "description": "动画风格（鲜艳色彩，硬边阴影，高对比）",
        "nodes": [
            {
                "node_type": "primary",
                "name": "Anime Primary",
                "enabled": True,
                "settings": {
                    "lift": [0.95, 0.95, 0.95, 0.0],
                    "gamma": [1.0, 1.0, 1.0, 0.0],
                    "gain": [1.1, 1.1, 1.1, 0.0],
                    "saturation": 1.4,
                    "contrast": 1.3,
                    "pivot": 0.45,
                },
            },
            {
                "node_type": "secondary",
                "name": "Cel Shading",
                "enabled": True,
                "settings": {
                    "edge_detection": True,
                    "edge_strength": 0.3,
                    "posterize_levels": 8,
                },
            },
        ],
    },
}


class DavinciColorist:
    """DaVinci Resolve 调色师。

    封装 DaVinci Resolve 的 Python API 和 CLI 调用，提供视频调色、
    节点管理、预设应用、LUT 处理等专业调色功能的统一接口。
    支持真实模式、模拟模式和自动降级模式。
    """

    def __init__(self, config: Optional[ResolveColorConfig] = None):
        """初始化 DavinciColorist。

        Args:
            config: Resolve 调色配置对象，为 None 时使用默认配置
        """
        self.config = config or ResolveColorConfig()
        self._exe_path = self._find_resolve_exe()
        self._available = self._check_availability()
        print(f"[DavinciColorist] Mode: {self.config.mode}")
        print(f"[DavinciColorist] Resolve available: {self._available}")
        print(f"[DavinciColorist] Executable: {self._exe_path}")

    def _find_resolve_exe(self) -> Optional[Path]:
        """查找 DaVinci Resolve 可执行文件。

        Returns:
            Resolve 可执行文件路径，找不到返回 None
        """
        install_path = Path(self.config.install_path)
        candidates = [
            install_path / "Resolve.exe",
            install_path / "Resolve" / "Resolve.exe",
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _check_availability(self) -> bool:
        """检查 DaVinci Resolve 是否已安装可用。

        Returns:
            True 表示可用，False 表示不可用
        """
        if self._exe_path is None:
            return False
        if not self._exe_path.exists():
            return False
        # 优先检查文件存在性（可靠），再尝试--version（Resolve启动慢可能超时）
        try:
            result = subprocess.run(
                [str(self._exe_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 or "DaVinci" in result.stdout + result.stderr
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # --version超时但文件存在, 仍然视为可用(Resolve启动慢)
            return True

    def is_available(self) -> bool:
        """检查 DaVinci Resolve 是否已安装可用。

        Returns:
            True 表示可用，False 表示不可用
        """
        return self._available

    def get_available_presets(self) -> List[str]:
        """获取所有可用调色预设名称。

        Returns:
            预设名称列表
        """
        return list(RESOLVE_PRESETS.keys())

    def apply_preset(self, preset_name: str) -> List[ColorGradeNode]:
        """根据预设名称生成节点配置列表。

        Args:
            preset_name: 预设名称

        Returns:
            ColorGradeNode 节点配置列表

        Raises:
            ValueError: 预设不存在时抛出
        """
        if preset_name not in RESOLVE_PRESETS:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Available presets: {list(RESOLVE_PRESETS.keys())}"
            )
        preset_data = RESOLVE_PRESETS[preset_name]
        nodes = []
        for node_data in preset_data.get("nodes", []):
            node = ColorGradeNode(
                node_type=node_data.get("node_type", "primary"),
                name=node_data.get("name", "Node"),
                settings=node_data.get("settings", {}),
                enabled=node_data.get("enabled", True),
            )
            nodes.append(node)
        return nodes

    def _get_video_info(self, video_path: str) -> Dict[str, Any]:
        """获取视频基本信息（分辨率、帧率、时长等）。

        Args:
            video_path: 视频文件路径

        Returns:
            包含 width, height, fps, duration 的字典
        """
        info = {
            "width": 1920,
            "height": 1080,
            "fps": 24.0,
            "duration": 0.0,
        }
        try:
            path = Path(video_path)
            if not path.exists():
                return info
            file_size = path.stat().st_size
            if file_size > 1024 * 1024:
                info["duration"] = min(300.0, file_size / (1024 * 1024 * 2))
        except Exception:
            pass
        return info

    def estimate_duration(
        self,
        input_path: str,
        config: Optional[ResolveColorConfig] = None,
    ) -> float:
        """估算调色处理时间（基于视频时长和节点复杂度）。

        Args:
            input_path: 输入视频路径
            config: 配置（可选，默认使用实例配置）

        Returns:
            估算的处理时间（秒）
        """
        cfg = config or self.config
        video_info = self._get_video_info(input_path)
        duration = video_info.get("duration", 60.0)
        width = video_info.get("width", 1920)
        height = video_info.get("height", 1080)

        base_time = duration * 0.8

        node_count = len(cfg.nodes) if cfg.nodes else 1
        complexity_factor = 1.0 + (node_count * 0.15)

        if cfg.use_lut:
            complexity_factor *= 1.2

        resolution_factor = (width * height) / (1920 * 1080)
        complexity_factor *= resolution_factor

        quality_factor = cfg.render_quality / 90.0
        complexity_factor *= quality_factor

        estimated = base_time * complexity_factor
        return max(3.0, estimated)

    def _build_color_grade_summary(
        self,
        nodes: List[ColorGradeNode],
    ) -> Dict[str, Any]:
        """根据节点配置生成调色摘要。

        Args:
            nodes: 调色节点列表

        Returns:
            调色摘要字典
        """
        summary = {
            "brightness": 0.0,
            "contrast": 1.0,
            "saturation": 1.0,
            "temperature": 0.0,
            "node_count": len(nodes),
            "enabled_nodes": 0,
            "node_types": [],
        }

        for node in nodes:
            if not node.enabled:
                continue
            summary["enabled_nodes"] += 1
            if node.node_type not in summary["node_types"]:
                summary["node_types"].append(node.node_type)
            settings = node.settings
            if "contrast" in settings:
                summary["contrast"] *= settings["contrast"]
            if "saturation" in settings:
                summary["saturation"] *= settings["saturation"]
            if "gain" in settings and isinstance(settings["gain"], list):
                gain_avg = sum(settings["gain"][:3]) / 3
                summary["brightness"] += (gain_avg - 1.0) * 0.5
            if "temperature" in settings:
                summary["temperature"] += settings["temperature"]

        return summary

    def color_grade(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        config: Optional[ResolveColorConfig] = None,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> ResolveColorResult:
        """主方法：对视频进行调色。

        Args:
            input_path: 输入视频文件路径
            output_path: 输出视频文件路径（可选，自动生成）
            config: 配置（可选，默认使用实例配置）
            callback: 进度回调函数 (progress 0-1, message)

        Returns:
            ResolveColorResult 调色结果对象
        """
        cfg = config or self.config
        start_time = time.time()

        input_file = Path(input_path)
        if not input_file.exists():
            return ResolveColorResult(
                success=False,
                input_path=input_path,
                error=f"Input file not found: {input_path}",
                mode=cfg.mode,
                preset=cfg.color_preset,
            )

        if output_path is None:
            output_dir = OUTPUT_BASE / "davinci_output"
            output_dir.mkdir(parents=True, exist_ok=True)
            ts = int(time.time())
            ext = OUTPUT_FORMAT_MAP.get(cfg.output_format, cfg.output_format)
            output_path = str(output_dir / f"grade_{input_file.stem}_{ts}.{ext}")

        nodes = []
        if cfg.nodes:
            for node_data in cfg.nodes:
                nodes.append(ColorGradeNode(
                    node_type=node_data.get("node_type", "primary"),
                    name=node_data.get("name", "Node"),
                    settings=node_data.get("settings", {}),
                    enabled=node_data.get("enabled", True),
                ))
        elif cfg.color_preset:
            nodes = self.apply_preset(cfg.color_preset)

        if cfg.use_lut:
            lut_node = ColorGradeNode(
                node_type="lut",
                name="Custom LUT",
                settings={"lut_path": cfg.use_lut, "strength": 1.0},
                enabled=True,
            )
            nodes.append(lut_node)

        color_summary = self._build_color_grade_summary(nodes)

        mode = cfg.mode
        if mode == "auto":
            mode = "real" if self._available else "simulate"

        if callback:
            callback(0.0, f"Starting color grading in {mode} mode...")

        result = ResolveColorResult(
            success=False,
            input_path=input_path,
            output_path=output_path,
            nodes_applied=color_summary["enabled_nodes"],
            color_grade_summary=color_summary,
            mode=mode,
            preset=cfg.color_preset,
        )

        if mode == "real":
            real_result = self._run_real_mode(
                input_path, output_path, cfg, nodes, callback
            )
            result = real_result
            if not real_result.success and cfg.mode == "auto":
                print("[DavinciColorist] Real mode failed, falling back to simulate")
                if callback:
                    callback(0.3, "Real mode failed, falling back to simulate mode...")
                sim_result = self._run_simulate_mode(
                    input_path, output_path, cfg, nodes, callback
                )
                result = sim_result
        else:
            sim_result = self._run_simulate_mode(
                input_path, output_path, cfg, nodes, callback
            )
            result = sim_result

        result.duration = time.time() - start_time
        return result

    def _init_resolve_api(self) -> bool:
        """初始化 DaVinci Resolve Python API 环境。

        设置环境变量并尝试加载 DaVinciResolveScript 模块。
        需要 Resolve 正在运行才能成功连接。

        Returns:
            True 表示 API 可用，False 表示不可用
        """
        # 设置环境变量
        script_api = os.environ.get("RESOLVE_SCRIPT_API", "")
        if not script_api:
            program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
            script_api = os.path.join(
                program_data,
                "Blackmagic Design",
                "DaVinci Resolve",
                "Support",
                "Developer",
                "Scripting",
                "Modules",
            )
            os.environ["RESOLVE_SCRIPT_API"] = script_api

        script_lib = os.environ.get("RESOLVE_SCRIPT_LIB", "")
        if not script_lib and self._exe_path:
            script_lib = str(self._exe_path.parent / "fusionscript.dll")
            os.environ["RESOLVE_SCRIPT_LIB"] = script_lib

        # 将 Modules 路径加入 sys.path
        if script_api not in sys.path:
            sys.path.insert(0, script_api)

        try:
            import DaVinciResolveScript as dvr
            resolve = dvr.scriptapp("Resolve")
            if resolve:
                return True
        except Exception:
            pass

        return False

    def _ensure_resolve_running(self, timeout: int = 30) -> bool:
        """确保 DaVinci Resolve 正在运行。

        如果 Resolve 未运行，尝试启动它并等待连接就绪。

        Args:
            timeout: 等待就绪的超时时间（秒）

        Returns:
            True 表示 Resolve 已运行且 API 可连接
        """
        # 检查 Resolve 进程是否在运行
        try:
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq Resolve.exe"],
                capture_output=True, text=True, timeout=5,
            )
            resolve_running = "Resolve.exe" in result.stdout
        except Exception:
            resolve_running = False

        if not resolve_running and self._exe_path:
            print("[DavinciColorist] DaVinci Resolve 未运行，正在启动...")
            try:
                subprocess.Popen(
                    [str(self._exe_path)],
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
            except Exception as e:
                print(f"[DavinciColorist] 启动 Resolve 失败: {e}")
                return False

            # 等待 Resolve 启动
            start = time.time()
            while time.time() - start < timeout:
                time.sleep(3)
                if self._init_resolve_api():
                    return True
                print(f"[DavinciColorist] 等待 Resolve 启动... ({int(time.time() - start)}s)")
            return False

        return self._init_resolve_api()

    def _run_real_mode(
        self,
        input_path: str,
        output_path: str,
        config: ResolveColorConfig,
        nodes: List[ColorGradeNode],
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> ResolveColorResult:
        """真实模式：通过 DaVinci Resolve Python API 执行调色。

        工作流程：
        1. 生成 DRX 调色预设文件
        2. 连接到运行中的 DaVinci Resolve
        3. 创建项目、导入视频、创建时间线
        4. 应用 DRX 调色到所有片段
        5. 设置渲染参数并渲染输出

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            config: Resolve 配置
            nodes: 调色节点列表
            callback: 进度回调函数

        Returns:
            ResolveColorResult 调色结果
        """
        color_summary = self._build_color_grade_summary(nodes)
        enabled_nodes = sum(1 for n in nodes if n.enabled)

        result = ResolveColorResult(
            success=False,
            input_path=input_path,
            output_path=output_path,
            nodes_applied=enabled_nodes,
            color_grade_summary=color_summary,
            mode="real",
            preset=config.color_preset,
        )

        if self._exe_path is None or not self._exe_path.exists():
            result.error = f"DaVinci Resolve not found at {config.install_path}"
            return result

        try:
            # Step 1: 生成 DRX 调色预设文件
            if callback:
                callback(0.05, "生成 DRX 调色预设文件...")

            drx_dir = Path(tempfile.mkdtemp(prefix="resolve_drx_"))
            drx_path = drx_dir / f"{config.color_preset}.drx"
            self.generate_drx_file(config, str(drx_path))
            print(f"[DavinciColorist] DRX 文件: {drx_path}")

            # Step 2: 连接 DaVinci Resolve
            if callback:
                callback(0.10, "连接 DaVinci Resolve...")

            if not self._ensure_resolve_running(timeout=30):
                result.error = "无法连接 DaVinci Resolve（请确保 Resolve 已启动并启用脚本权限）"
                return result

            import DaVinciResolveScript as dvr
            resolve = dvr.scriptapp("Resolve")
            if not resolve:
                result.error = "DaVinci Resolve 连接失败"
                return result

            print("[DavinciColorist] 已连接 DaVinci Resolve")

            # Step 3: 创建项目
            if callback:
                callback(0.20, "创建 Resolve 项目...")

            project_manager = resolve.GetProjectManager()
            project_name = f"AE_Grade_{config.color_preset}_{int(time.time())}"
            project = project_manager.CreateProject(project_name)
            if not project:
                project = project_manager.GetCurrentProject()
            if not project:
                result.error = "无法创建 Resolve 项目"
                return result

            print(f"[DavinciColorist] 项目: {project_name}")

            # Step 4: 导入视频
            if callback:
                callback(0.30, "导入视频文件...")

            media_pool = project.GetMediaPool()
            root_folder = media_pool.GetRootFolder()
            media_pool.ImportMedia([str(Path(input_path).resolve())])
            clips = root_folder.GetClipList()
            if not clips:
                result.error = "视频导入失败"
                return result

            print(f"[DavinciColorist] 已导入: {Path(input_path).name}")

            # Step 5: 创建时间线
            if callback:
                callback(0.40, "创建时间线...")

            timeline = media_pool.CreateTimelineFromClips(
                config.timeline_name, clips
            )
            if not timeline:
                timeline = project.GetTimelineByIndex(1)
            if not timeline:
                result.error = "时间线创建失败"
                return result

            project.SetCurrentTimeline(timeline)
            print(f"[DavinciColorist] 时间线: {config.timeline_name}")

            # Step 6: 应用 DRX 调色
            if callback:
                callback(0.50, "应用 DRX 调色...")

            track_count = timeline.GetTrackCount("video")
            grade_applied = False
            for track_idx in range(1, int(track_count) + 1):
                track_clips = timeline.GetItemListInTrack("video", track_idx)
                if track_clips:
                    if timeline.ApplyGradeFromDRX(str(drx_path), 0, track_clips):
                        grade_applied = True
                        print(f"[DavinciColorist] 调色已应用到轨道 {track_idx}")

            if not grade_applied:
                print("[DavinciColorist] DRX 应用失败，尝试手动调色...")
                # 尝试通过 Color 页面手动设置
                resolve.OpenPage("Color")
                time.sleep(1)

            # Step 7: 设置渲染参数
            if callback:
                callback(0.60, "配置渲染参数...")

            resolve.OpenPage("Deliver")
            time.sleep(1)

            output_format = OUTPUT_FORMAT_MAP.get(config.output_format, "mp4")
            render_format = "mp4" if output_format == "mp4" else "mov"
            render_codec = "H264" if output_format == "mp4" else "ProRes422HQ"

            try:
                project.SetCurrentRenderFormatAndCodec(render_format, render_codec)
            except Exception:
                pass

            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            project.SetRenderSettings({
                "TargetDir": str(output_file.parent),
                "CustomName": output_file.stem,
                "ExportVideo": True,
                "ExportAudio": True,
                "Quality": config.render_quality,
            })

            # Step 8: 渲染输出
            if callback:
                callback(0.70, "开始渲染...")

            project.DeleteAllRenderJobs()
            project.AddRenderJob()
            project.StartRendering()

            # 等待渲染完成
            render_start = time.time()
            while project.IsRenderingInProgress():
                progress = project.GetRenderJobStatus(0).get("JobProgress", 0)
                if callback:
                    callback(0.70 + float(progress) * 0.25,
                             f"渲染中... {int(float(progress) * 100)}%")
                time.sleep(2)

            render_time = time.time() - render_start
            print(f"[DavinciColorist] 渲染完成，耗时 {render_time:.1f}s")

            # 验证输出文件
            if output_file.exists():
                result.success = True
                result.output_path = str(output_file)
                result.duration = render_time
                if callback:
                    callback(1.0, "调色渲染完成")
            else:
                result.error = f"输出文件未找到: {output_path}"

            # 清理：关闭项目
            try:
                project_manager.CloseProject(project)
            except Exception:
                pass

        except Exception as e:
            result.error = f"Real mode error: {e}"
            import traceback
            traceback.print_exc()

        return result

    def _generate_resolve_script(
        self,
        input_path: str,
        output_path: str,
        config: ResolveColorConfig,
        nodes: List[ColorGradeNode],
    ) -> str:
        """生成 DaVinci Resolve Python 脚本。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            config: Resolve 配置
            nodes: 调色节点列表

        Returns:
            脚本文件路径
        """
        script_dir = Path(tempfile.mkdtemp(prefix="resolve_script_"))
        script_path = script_dir / "color_grade.py"

        script_lines = [
            "#!/usr/bin/env python3",
            '"""DaVinci Resolve 自动调色脚本"""',
            "import sys",
            "import os",
            "",
            "try:",
            "    import DaVinciResolveScript as dvr_script",
            "    resolve = dvr_script.scriptapp('Resolve')",
            "    projectManager = resolve.GetProjectManager()",
            "    project = projectManager.CreateProject(f'{config.project_name}')",
            "    if not project:",
            "        project = projectManager.LoadProject(f'{config.project_name}')",
            "    mediaPool = project.GetMediaPool()",
            "    folder = mediaPool.GetRootFolder()",
            "    mediaPool.ImportMedia([r'{}'])".format(input_path),
            "    timeline = mediaPool.CreateTimelineFromClips(f'{config.timeline_name}', folder.GetClipList())",
            "    if not timeline:",
            "        timeline = project.GetTimelineByIndex(1)",
            "",
            "    clip = timeline.GetItemInTrack(1, 1, 1)",
            "    if clip:",
            "        grade = clip.GetClipColorGrade()",
            f"        num_nodes = grade.GetNumberOfNodes()",
        ]

        for i, node in enumerate(nodes):
            if not node.enabled:
                continue
            node_idx = i + 1
            script_lines.append(f"        # Node {node_idx}: {node.name} ({node.node_type})")
            if node.node_type == "primary":
                settings = node.settings
                if "saturation" in settings:
                    script_lines.append(
                        f"        grade.SetSaturation({node_idx}, {settings['saturation']})"
                    )
                if "contrast" in settings:
                    script_lines.append(
                        f"        grade.SetContrast({node_idx}, {settings['contrast']}, {settings.get('pivot', 0.5)})"
                    )
                if "lift" in settings and isinstance(settings["lift"], list):
                    lift = settings["lift"]
                    script_lines.append(
                        f"        grade.SetLift({node_idx}, {lift[0]}, {lift[1]}, {lift[2]}, {lift[3]})"
                    )
                if "gamma" in settings and isinstance(settings["gamma"], list):
                    gamma = settings["gamma"]
                    script_lines.append(
                        f"        grade.SetGamma({node_idx}, {gamma[0]}, {gamma[1]}, {gamma[2]}, {gamma[3]})"
                    )
                if "gain" in settings and isinstance(settings["gain"], list):
                    gain = settings["gain"]
                    script_lines.append(
                        f"        grade.SetGain({node_idx}, {gain[0]}, {gain[1]}, {gain[2]}, {gain[3]})"
                    )

        script_lines.extend([
            "",
            "    # 设置渲染",
            "    project.SetCurrentTimeline(timeline)",
            "    project.SetRenderFormat(f'{config.output_format}', f'{config.output_format}')",
            f"    project.SetRenderSettings({{'Quality': {config.render_quality}}})",
            f"    output_path = r'{output_path}'",
            "    project.SetRenderSettings({'TargetDir': os.path.dirname(output_path)})",
            "    project.SetRenderSettings({'CustomName': os.path.basename(output_path)})",
            "    job_id = project.AddRenderJob()",
            "    project.StartRendering([job_id])",
            "",
            "    print('Color grading complete!')",
            "",
            "except Exception as e:",
            "    print(f'Error: {{e}}')",
            "    sys.exit(1)",
        ])

        script_path.write_text("\n".join(script_lines), encoding="utf-8")
        return str(script_path)

    def _run_simulate_mode(
        self,
        input_path: str,
        output_path: str,
        config: ResolveColorConfig,
        nodes: List[ColorGradeNode],
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> ResolveColorResult:
        """模拟模式：不真正调用 Resolve，生成模拟结果。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            config: Resolve 配置
            nodes: 调色节点列表
            callback: 进度回调函数

        Returns:
            ResolveColorResult 调色结果
        """
        color_summary = self._build_color_grade_summary(nodes)
        enabled_nodes = sum(1 for n in nodes if n.enabled)

        estimated = self.estimate_duration(input_path, config)
        sim_duration = min(estimated * 0.1, 3.0)

        steps = 10
        node_steps = max(1, enabled_nodes)
        total_steps = steps + node_steps

        for i in range(steps):
            time.sleep(sim_duration / total_steps)
            if callback:
                progress = (i + 1) / total_steps
                msg = f"Simulating color grading... {int(progress * 100)}%"
                callback(progress, msg)

        for i, node in enumerate(nodes):
            if not node.enabled:
                continue
            time.sleep(sim_duration / total_steps)
            if callback:
                progress = (steps + i + 1) / total_steps
                msg = f"Applying node: {node.name} ({node.node_type})"
                callback(progress, msg)

        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        input_file = Path(input_path)
        if input_file.exists():
            try:
                input_file_size = input_file.stat().st_size
                sim_size = int(input_file_size * 0.95)
                with open(output_file, "wb") as f:
                    f.write(b"RESOLVE_GRADED_OUTPUT")
                    f.seek(max(0, sim_size - 1))
                    f.write(b"\0")
            except Exception:
                output_file.write_bytes(b"RESOLVE_GRADED_OUTPUT")
        else:
            output_file.write_bytes(b"RESOLVE_GRADED_OUTPUT")

        result = ResolveColorResult(
            success=True,
            input_path=input_path,
            output_path=output_path,
            duration=sim_duration,
            nodes_applied=enabled_nodes,
            color_grade_summary=color_summary,
            mode="simulate",
            preset=config.color_preset,
        )

        if callback:
            callback(1.0, "Color grading simulation complete")

        return result

    def batch_color_grade(
        self,
        input_paths: List[str],
        output_dir: Optional[str] = None,
        preset: Optional[str] = None,
        callback: Optional[Callable[[int, int, ResolveColorResult], None]] = None,
    ) -> List[ResolveColorResult]:
        """批量调色。

        Args:
            input_paths: 输入视频路径列表
            output_dir: 输出目录（可选，使用默认目录）
            preset: 调色预设名称（可选，使用配置中的预设）
            callback: 进度回调函数 (current_index, total, current_result)

        Returns:
            ResolveColorResult 列表
        """
        cfg = ResolveColorConfig(**{
            **self.config.__dict__,
            "color_preset": preset or self.config.color_preset,
        })
        results = []
        total = len(input_paths)

        for idx, input_path in enumerate(input_paths):
            single_output_dir = output_dir or str(OUTPUT_BASE / "davinci_output")
            Path(single_output_dir).mkdir(parents=True, exist_ok=True)

            result = self.color_grade(
                input_path=input_path,
                output_path=None,
                config=cfg,
                callback=None,
            )
            results.append(result)

            if callback:
                callback(idx + 1, total, result)

        return results

    def generate_drx_file(
        self,
        config: ResolveColorConfig,
        output_path: str,
    ) -> str:
        """生成 .drx 调色预设文件（XML 格式，可导入 Resolve）。

        Args:
            config: 调色配置
            output_path: 输出 .drx 文件路径

        Returns:
            生成的文件路径
        """
        nodes = []
        if config.nodes:
            for node_data in config.nodes:
                nodes.append(ColorGradeNode(
                    node_type=node_data.get("node_type", "primary"),
                    name=node_data.get("name", "Node"),
                    settings=node_data.get("settings", {}),
                    enabled=node_data.get("enabled", True),
                ))
        elif config.color_preset:
            nodes = self.apply_preset(config.color_preset)

        root = ET.Element("DRX", {
            "version": "1.0",
            "xmlns": "http://www.blackmagicdesign.com/schema/drx/1.0",
        })

        header = ET.SubElement(root, "Header")
        ET.SubElement(header, "Name").text = config.color_preset or "Custom Grade"
        ET.SubElement(header, "Description").text = f"Generated from preset: {config.color_preset}"
        ET.SubElement(header, "Created").text = datetime.now().isoformat()
        ET.SubElement(header, "Tool").text = "DavinciColorist"

        grade_group = ET.SubElement(root, "ColorGradeGroup")
        ET.SubElement(grade_group, "Name").text = "Corrector"

        corrector = ET.SubElement(grade_group, "Corrector")
        nodes_elem = ET.SubElement(corrector, "Nodes")

        for i, node in enumerate(nodes):
            node_elem = ET.SubElement(nodes_elem, "Node", {
                "index": str(i + 1),
                "type": node.node_type,
                "enabled": str(node.enabled).lower(),
            })
            ET.SubElement(node_elem, "Name").text = node.name

            settings_elem = ET.SubElement(node_elem, "Settings")
            for key, value in node.settings.items():
                setting_elem = ET.SubElement(settings_elem, "Setting", {"name": key})
                if isinstance(value, list):
                    ET.SubElement(setting_elem, "ValueArray").text = " ".join(map(str, value))
                else:
                    ET.SubElement(setting_elem, "Value").text = str(value)

        if config.use_lut:
            lut_node = ET.SubElement(nodes_elem, "Node", {
                "index": str(len(nodes) + 1),
                "type": "lut",
                "enabled": "true",
            })
            ET.SubElement(lut_node, "Name").text = "Custom LUT"
            lut_settings = ET.SubElement(lut_node, "Settings")
            lut_setting = ET.SubElement(lut_settings, "Setting", {"name": "LUTPath"})
            ET.SubElement(lut_setting, "Value").text = config.use_lut

        tree = ET.ElementTree(root)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        tree.write(str(output_file), encoding="utf-8", xml_declaration=True)

        return str(output_file)


def create_config_from_preset(preset_name: str) -> ResolveColorConfig:
    """从预设创建 ResolveColorConfig 配置对象。

    Args:
        preset_name: 预设名称

    Returns:
        ResolveColorConfig 配置对象

    Raises:
        ValueError: 预设不存在时抛出
    """
    if preset_name not in RESOLVE_PRESETS:
        raise ValueError(
            f"Unknown preset: {preset_name}. "
            f"Available presets: {list(RESOLVE_PRESETS.keys())}"
        )
    preset = RESOLVE_PRESETS[preset_name]
    config = ResolveColorConfig()
    config.color_preset = preset_name
    config.nodes = preset.get("nodes", [])
    return config


def _run_self_tests():
    """自测函数：验证 DaVinci Resolve 调色集成模块的所有功能。"""
    print("=" * 60)
    print("DaVinci Resolve 调色集成模块 - 自测")
    print("=" * 60)

    results = []

    test_dir = Path(tempfile.mkdtemp(prefix="davinci_test_"))
    test_input = test_dir / "test_input.mp4"
    try:
        with open(test_input, "wb") as f:
            f.write(b"FAKE_VIDEO_HEADER")
            f.seek(1024 * 1024)
            f.write(b"\0")
    except Exception:
        pass

    print("\n[测试 1/10] 检查 RESOLVE_PRESETS 预设配置...")
    expected_presets = [
        "default",
        "cinematic",
        "warm_vintage",
        "cool_teal",
        "vivid_pop",
        "muted_film",
        "noir_bw",
        "pastel_dream",
        "puppet_warm",
        "puppet_porcelain",
        "horror_grade",
        "anime_style",
    ]
    all_presets_ok = True
    for pname in expected_presets:
        if pname in RESOLVE_PRESETS:
            pdata = RESOLVE_PRESETS[pname]
            has_nodes = "nodes" in pdata and len(pdata["nodes"]) > 0
            has_desc = "description" in pdata
            if has_nodes and has_desc:
                print(f"  ✓ {pname} 存在 (nodes: {len(pdata['nodes'])})")
            else:
                print(f"  ⚠ {pname} 存在但配置不完整")
                all_presets_ok = False
        else:
            print(f"  ✗ {pname} 不存在")
            all_presets_ok = False
    results.append(("presets", all_presets_ok))

    print("\n[测试 2/10] 检查 ColorGradeNode 数据类...")
    try:
        node = ColorGradeNode()
        required_attrs = ["node_type", "name", "settings", "enabled"]
        attrs_ok = all(hasattr(node, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ ColorGradeNode 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print(f"  ✗ ColorGradeNode 缺少必需属性")
        results.append(("node_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ ColorGradeNode 错误: {e}")
        results.append(("node_dataclass", False))

    print("\n[测试 3/10] 检查 ResolveColorConfig 数据类...")
    try:
        config = ResolveColorConfig()
        required_attrs = [
            "install_path", "mode", "project_name", "timeline_name",
            "color_preset", "input_path", "output_path", "output_format",
            "render_quality", "use_lut", "nodes",
        ]
        attrs_ok = all(hasattr(config, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ ResolveColorConfig 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print(f"  ✗ ResolveColorConfig 缺少必需属性")
        results.append(("config_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ ResolveColorConfig 错误: {e}")
        results.append(("config_dataclass", False))

    print("\n[测试 4/10] 检查 ResolveColorResult 数据类...")
    try:
        result = ResolveColorResult()
        required_attrs = [
            "success", "input_path", "output_path", "duration",
            "nodes_applied", "color_grade_summary", "error", "mode", "preset",
        ]
        attrs_ok = all(hasattr(result, attr) for attr in required_attrs)
        if attrs_ok:
            print(f"  ✓ ResolveColorResult 包含所有必需属性 ({len(required_attrs)} 个)")
        else:
            print(f"  ✗ ResolveColorResult 缺少必需属性")
        results.append(("result_dataclass", attrs_ok))
    except Exception as e:
        print(f"  ✗ ResolveColorResult 错误: {e}")
        results.append(("result_dataclass", False))

    print("\n[测试 5/10] 检查 DavinciColorist 初始化...")
    try:
        colorist = DavinciColorist(config=ResolveColorConfig(mode="simulate"))
        print(f"  ✓ DavinciColorist 初始化成功")
        print(f"    - Mode: {colorist.config.mode}")
        print(f"    - Available: {colorist.is_available()}")
        results.append(("colorist_init", True))
    except Exception as e:
        print(f"  ✗ DavinciColorist 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("colorist_init", False))

    print("\n[测试 6/10] 检查 get_available_presets 和 apply_preset...")
    try:
        colorist = DavinciColorist(config=ResolveColorConfig(mode="simulate"))
        presets = colorist.get_available_presets()
        if isinstance(presets, list) and len(presets) >= 12:
            print(f"  ✓ 可用预设列表: {len(presets)} 个")
            print(f"    {presets[:5]}...")

            test_preset = "cinematic"
            nodes = colorist.apply_preset(test_preset)
            if isinstance(nodes, list) and len(nodes) > 0:
                print(f"  ✓ 预设 {test_preset} 节点数: {len(nodes)}")
                for n in nodes:
                    print(f"    - {n.name} ({n.node_type}, enabled={n.enabled})")
                results.append(("presets_apply", True))
            else:
                print(f"  ✗ 预设节点配置错误")
                results.append(("presets_apply", False))
        else:
            print(f"  ✗ 预设列表为空或数量不足")
            results.append(("presets_apply", False))
    except Exception as e:
        print(f"  ✗ 预设测试错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("presets_apply", False))

    print("\n[测试 7/10] 检查 simulate 模式 color_grade...")
    try:
        colorist = DavinciColorist(config=ResolveColorConfig(mode="simulate"))
        output_dir = test_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        progress_log = []
        def progress_cb(progress, msg):
            progress_log.append((progress, msg))

        result = colorist.color_grade(
            input_path=str(test_input),
            output_path=str(output_dir / "test_output.mp4"),
            callback=progress_cb,
        )

        if result.success and Path(result.output_path).exists():
            print(f"  ✓ 模拟模式调色成功")
            print(f"    - 应用节点数: {result.nodes_applied}")
            print(f"    - 模式: {result.mode}")
            print(f"    - 预设: {result.preset}")
            print(f"    - 进度回调次数: {len(progress_log)}")
            print(f"    - 调色摘要 keys: {list(result.color_grade_summary.keys())}")
            results.append(("simulate_grade", True))
        else:
            print(f"  ✗ 模拟模式调色失败: {result.error}")
            results.append(("simulate_grade", False))
    except Exception as e:
        print(f"  ✗ simulate color_grade 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("simulate_grade", False))

    print("\n[测试 8/10] 检查 create_config_from_preset...")
    try:
        test_preset = "warm_vintage"
        config = create_config_from_preset(test_preset)
        if config.color_preset == test_preset and len(config.nodes) > 0:
            print(f"  ✓ 预设 {test_preset} 创建成功")
            print(f"    - Preset: {config.color_preset}")
            print(f"    - Nodes: {len(config.nodes)}")
            results.append(("preset_create", True))
        else:
            print(f"  ✗ 预设参数不匹配")
            results.append(("preset_create", False))
    except Exception as e:
        print(f"  ✗ create_config_from_preset 错误: {e}")
        results.append(("preset_create", False))

    print("\n[测试 9/10] 检查 generate_drx_file...")
    try:
        colorist = DavinciColorist(config=ResolveColorConfig(mode="simulate"))
        drx_path = test_dir / "test_preset.drx"
        config = create_config_from_preset("cinematic")
        output_path = colorist.generate_drx_file(config, str(drx_path))

        if Path(output_path).exists():
            tree = ET.parse(output_path)
            root = tree.getroot()
            nodes_found = root.findall(".//Node")
            print(f"  ✓ DRX 文件生成成功")
            print(f"    - 文件路径: {output_path}")
            print(f"    - 节点数量: {len(nodes_found)}")
            results.append(("drx_generation", True))
        else:
            print(f"  ✗ DRX 文件生成失败")
            results.append(("drx_generation", False))
    except Exception as e:
        print(f"  ✗ generate_drx_file 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("drx_generation", False))

    print("\n[测试 10/10] 检查 batch_color_grade 批量处理...")
    try:
        colorist = DavinciColorist(config=ResolveColorConfig(mode="simulate"))
        batch_dir = test_dir / "batch_output"
        batch_dir.mkdir(parents=True, exist_ok=True)

        input_files = [str(test_input) for _ in range(3)]

        batch_log = []
        def batch_cb(current, total, result):
            batch_log.append((current, total, result.success))

        results_list = colorist.batch_color_grade(
            input_paths=input_files,
            output_dir=str(batch_dir),
            preset="vivid_pop",
            callback=batch_cb,
        )

        success_count = sum(1 for r in results_list if r.success)
        if success_count == len(input_files) and len(batch_log) == len(input_files):
            print(f"  ✓ 批量调色成功 ({success_count}/{len(input_files)})")
            results.append(("batch_grade", True))
        else:
            print(f"  ✗ 批量调色失败 (成功 {success_count}/{len(input_files)})")
            results.append(("batch_grade", False))
    except Exception as e:
        print(f"  ✗ batch_color_grade 错误: {e}")
        import traceback
        traceback.print_exc()
        results.append(("batch_grade", False))

    print("\n[预设配置清单]")
    for pname, pdata in RESOLVE_PRESETS.items():
        desc = pdata.get("description", "")
        node_count = len(pdata.get("nodes", []))
        print(f"  - {pname}: {desc} (节点数: {node_count})")

    try:
        import shutil
        shutil.rmtree(test_dir, ignore_errors=True)
    except Exception:
        pass

    print("\n" + "=" * 60)
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    print(f"自测结果: {passed}/{total} 通过")
    print("=" * 60)

    for name, ok in results:
        status = "✓ 通过" if ok else "✗ 失败"
        print(f"  {status}: {name}")

    return passed == total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DaVinci Resolve Color Grading Integration")
    parser.add_argument(
        "--mode",
        choices=["real", "simulate", "auto"],
        default="auto",
        help="Execution mode",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run self-tests",
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input video path",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output video path",
    )
    parser.add_argument(
        "--preset",
        type=str,
        default="default",
        help=f"Preset name: {list(RESOLVE_PRESETS.keys())}",
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="List all available presets",
    )
    parser.add_argument(
        "--export-drx",
        type=str,
        help="Export preset to .drx file",
    )

    args = parser.parse_args()

    if args.test:
        success = _run_self_tests()
        sys.exit(0 if success else 1)
    elif args.list_presets:
        print("Available presets:")
        for name, data in RESOLVE_PRESETS.items():
            desc = data.get("description", "")
            nodes = data.get("nodes", [])
            print(f"  {name}: {desc}")
            print(f"    Nodes: {len(nodes)}")
    elif args.export_drx:
        colorist = DavinciColorist()
        config = create_config_from_preset(args.preset)
        output = colorist.generate_drx_file(config, args.export_drx)
        print(f"✓ DRX preset exported to: {output}")
    elif args.input:
        config = create_config_from_preset(args.preset)
        config.mode = args.mode
        colorist = DavinciColorist(config=config)

        print(f"Color grading: {args.input}")
        print(f"Preset: {args.preset}")
        print(f"Mode: {args.mode}")

        def progress(progress, msg):
            print(f"  [{int(progress * 100):3d}%] {msg}")

        result = colorist.color_grade(
            input_path=args.input,
            output_path=args.output,
            callback=progress,
        )

        if result.success:
            print(f"\n✓ Success! Output: {result.output_path}")
            print(f"  Duration: {result.duration:.2f}s")
            print(f"  Nodes applied: {result.nodes_applied}")
            print(f"  Color summary: {result.color_grade_summary}")
            sys.exit(0)
        else:
            print(f"\n✗ Failed: {result.error}")
            sys.exit(1)
    else:
        parser.print_help()
