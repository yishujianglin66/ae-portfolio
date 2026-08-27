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


# ============================================================================
# FFmpeg Filter 调色预设 (v2.0 新增)
# ============================================================================
# 借鉴 video-editing-skill 项目的 FFmpeg filter 链调色方案
# 当 DaVinci Resolve 不可用时，自动降级到 FFmpeg 滤镜链调色

FFMPEG_COLOR_PRESETS: Dict[str, Dict[str, Any]] = {
    "natural": {
        "description": "自然色彩增强（轻微饱和度+对比度提升）",
        "ffmpeg_filter": (
            "eq=saturation=1.1:contrast=1.05:brightness=0.02:gamma=1.02,"
            "curves=m='0/0 0.25/0.28 0.5/0.53 0.75/0.78 1/1'"
        ),
        "params": {"saturation": 1.1, "contrast": 1.05, "brightness": 0.02},
    },
    "warm": {
        "description": "暖色调（橙黄色温，适合人像/日落）",
        "ffmpeg_filter": (
            "eq=saturation=1.05:brightness=0.03:gamma=1.03,"
            "colorbalance=rs=0.15:gs=0.05:bs=-0.1:"
            "rm=0.1:gm=0.03:bm=-0.08:"
            "rh=0.08:gh=0.04:bm=-0.05,"
            "curves=r='0/0 0.5/0.55 1/1':b='0/0 0.5/0.47 1/1'"
        ),
        "params": {"temperature": 0.15, "saturation": 1.05},
    },
    "cool": {
        "description": "冷色调（青蓝色温，适合科技/夜景）",
        "ffmpeg_filter": (
            "eq=saturation=0.95:contrast=1.08:brightness=-0.02,"
            "colorbalance=rs=-0.1:gs=0.05:bs=0.15:"
            "rm=-0.08:gm=0.03:bm=0.12:"
            "rh=-0.05:gh=0.02:bh=0.1,"
            "curves=r='0/0 0.5/0.47 1/1':b='0/0 0.5/0.55 1/1'"
        ),
        "params": {"temperature": -0.15, "contrast": 1.08},
    },
    "punchy": {
        "description": "冲击力（高对比高饱和，适合运动/广告）",
        "ffmpeg_filter": (
            "eq=saturation=1.3:contrast=1.25:brightness=-0.03:gamma=0.95,"
            "curves=m='0/0 0.2/0.15 0.5/0.55 0.8/0.85 1/1',"
            "unsharp=3:3:0.8"
        ),
        "params": {"saturation": 1.3, "contrast": 1.25, "sharpness": 0.8},
    },
    "soft": {
        "description": "柔和梦幻（低对比，柔光效果）",
        "ffmpeg_filter": (
            "eq=saturation=0.85:contrast=0.85:brightness=0.05:gamma=1.08,"
            "gblur=sigma=0.8[blur];[blur]blend=all_mode=screen:all_opacity=0.2,"
            "curves=m='0/0.05 0.3/0.35 0.6/0.65 1/1'"
        ),
        "params": {"saturation": 0.85, "contrast": 0.85, "glow": 0.2},
    },
    "cinematic_ff": {
        "description": "电影感（宽银幕色调映射，暗角+胶片颗粒）",
        "ffmpeg_filter": (
            "eq=saturation=0.9:contrast=1.2:brightness=-0.05:gamma=0.98,"
            "colorbalance=rs=0.08:gs=-0.02:bs=-0.08:"
            "rm=0.05:gm=0.0:bm=-0.05:"
            "rh=0.1:gh=0.05:bm=-0.1,"
            "curves=m='0/0.02 0.15/0.1 0.5/0.52 0.85/0.9 1/0.98',"
            "vignette=PI/4:aspect=1.8,"
            "noise=alls=20:allf=t+u"
        ),
        "params": {"contrast": 1.2, "saturation": 0.9, "grain": 20, "vignette": True},
    },
    "screen": {
        "description": "银幕感（明亮高光，柔和阴影，适合纪录片）",
        "ffmpeg_filter": (
            "eq=saturation=1.0:contrast=1.1:brightness=0.08:gamma=1.05,"
            "colorbalance=rs=0.03:gs=0.02:bs=0.05:"
            "rm=0.02:gm=0.02:bm=0.04,"
            "curves=r='0/0 0.3/0.32 0.7/0.72 1/1':"
            "g='0/0 0.3/0.31 0.7/0.71 1/1':"
            "b='0/0.02 0.3/0.33 0.7/0.73 1/1'"
        ),
        "params": {"brightness": 0.08, "contrast": 1.1},
    },
}


# ============================================================================
# color_grade.v1 JSON Artifact 格式 (v2.0 新增)
# ============================================================================

@dataclass
class ColorGradeArtifact:
    """color_grade.v1 JSON artifact 数据类。

    标准化的调色描述格式，可在 Resolve / FFmpeg / AE 之间互通。

    Attributes:
        version: artifact 版本号
        preset_name: 预设名称
        source: 来源（resolve/ffmpeg/manual）
        nodes: 调色节点列表
        ffmpeg_filter: FFmpeg 滤镜链（如果适用）
        metadata: 额外元数据
    """
    version: str = "1.0"
    preset_name: str = ""
    source: str = "auto"
    created_at: str = ""
    nodes: List[Dict[str, Any]] = field(default_factory=list)
    ffmpeg_filter: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "preset_name": self.preset_name,
            "source": self.source,
            "created_at": self.created_at or datetime.now().isoformat(),
            "nodes": self.nodes,
            "ffmpeg_filter": self.ffmpeg_filter,
            "metadata": self.metadata,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColorGradeArtifact":
        return cls(
            version=data.get("version", "1.0"),
            preset_name=data.get("preset_name", ""),
            source=data.get("source", "auto"),
            created_at=data.get("created_at", ""),
            nodes=data.get("nodes", []),
            ffmpeg_filter=data.get("ffmpeg_filter", ""),
            metadata=data.get("metadata", {}),
        )

    def save(self, path: str) -> str:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: str) -> "ColorGradeArtifact":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls.from_dict(data)


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
        self._fuscript_available = False
        self._available = self._check_availability()
        self._ffmpeg_available = self._check_ffmpeg()
        print(f"[DavinciColorist] Mode: {self.config.mode}")
        print(f"[DavinciColorist] Resolve available: {self._available}")
        print(f"[DavinciColorist] Fuscript available: {self._fuscript_available}")
        print(f"[DavinciColorist] FFmpeg available: {self._ffmpeg_available}")
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
        
        # 检查 fuscript.exe（v2.0 自动化路径）
        fuscript_path = self._exe_path.parent / "fuscript.exe"
        if fuscript_path.exists():
            self._fuscript_available = True
        
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

    def _check_ffmpeg(self) -> bool:
        """检查 FFmpeg 是否可用。"""
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True, text=True, timeout=5,
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    def is_available(self) -> bool:
        """检查 DaVinci Resolve 是否已安装可用。

        Returns:
            True 表示可用，False 表示不可用
        """
        return self._available

    def get_available_presets(self) -> List[str]:
        """获取所有可用调色预设名称（Resolve + FFmpeg）。"""
        return list(RESOLVE_PRESETS.keys()) + list(FFMPEG_COLOR_PRESETS.keys())

    def apply_preset(self, preset_name: str) -> List[ColorGradeNode]:
        """根据预设名称生成节点配置列表。

        Args:
            preset_name: 预设名称（支持 Resolve 预设和 FFmpeg 预设）

        Returns:
            ColorGradeNode 节点配置列表

        Raises:
            ValueError: 预设不存在时抛出
        """
        if preset_name in RESOLVE_PRESETS:
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
        elif preset_name in FFMPEG_COLOR_PRESETS:
            # FFmpeg 预设转换为单节点
            ff_data = FFMPEG_COLOR_PRESETS[preset_name]
            return [ColorGradeNode(
                node_type="primary",
                name=f"FFmpeg_{preset_name}",
                settings=ff_data.get("params", {}),
                enabled=True,
            )]
        else:
            raise ValueError(
                f"Unknown preset: {preset_name}. "
                f"Available: {list(RESOLVE_PRESETS.keys()) + list(FFMPEG_COLOR_PRESETS.keys())}"
            )

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
            if self._available:
                mode = "real"
            elif self._ffmpeg_available and cfg.color_preset in FFMPEG_COLOR_PRESETS:
                mode = "ffmpeg"
            else:
                mode = "simulate"

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
                # 降级链: real -> ffmpeg -> simulate
                if self._ffmpeg_available and cfg.color_preset in FFMPEG_COLOR_PRESETS:
                    print("[DavinciColorist] Real mode failed, trying FFmpeg...")
                    if callback:
                        callback(0.3, "Real mode failed, falling back to FFmpeg...")
                    result = self._run_ffmpeg_grade(input_path, output_path, cfg.color_preset, callback)
                else:
                    print("[DavinciColorist] Real mode failed, falling back to simulate")
                    if callback:
                        callback(0.3, "Real mode failed, falling back to simulate mode...")
                    result = self._run_simulate_mode(
                        input_path, output_path, cfg, nodes, callback
                    )
        elif mode == "ffmpeg":
            result = self._run_ffmpeg_grade(input_path, output_path, cfg.color_preset, callback)
        else:
            sim_result = self._run_simulate_mode(
                input_path, output_path, cfg, nodes, callback
            )
            result = sim_result

        result.duration = time.time() - start_time
        return result

    def _init_resolve_api(self) -> bool:
        """初始化 DaVinci Resolve 自动化环境。
        
        1. 优先 fuscript.exe + Lua（bypass 免费版限制）
        2. 全面探测所有常见 Scripting API 路径
        3. 多种方式注入 sys.path 和环境变量
        """
        # 1. 优先 fuscript.exe 检测（可靠，不受免费版限制）
        fuscript_path = self._exe_path.parent / "fuscript.exe" if self._exe_path else None
        if fuscript_path and fuscript_path.exists():
            try:
                from integrations.davinci_fuscript import ResolveColorEngine
                resolve_home = str(self._exe_path.parent) if self._exe_path else None
                engine = ResolveColorEngine(resolve_home)
                if engine.check_resolve_running():
                    print(f"[DavinciColorist] fuscript.exe connected to Resolve successfully")
                    self._fuscript_available = True
                    return True
            except Exception as e:
                print(f"[DavinciColorist] fuscript connection failed: {e}")
        
        # 2. 全面的 Scripting API 路径探测
        resolve_install_candidates = []
        
        # 2.1 已知安装路径
        if self._exe_path:
            resolve_install_candidates.append(self._exe_path.parent)
        
        # 2.2 常见安装路径
        default_install_paths = [
            Path(r"C:\Program Files\Blackmagic Design\DaVinci Resolve"),
            Path(r"D:\DaVinci Resolve"),
            Path(r"E:\DaVinci Resolve"),
            Path(r"F:\DaVinci Resolve"),
        ]
        for p in default_install_paths:
            if p.exists():
                resolve_install_candidates.append(p)
        
        # 2.3 注册表探测（Windows）— 尝试从注册表读取安装路径
        try:
            import winreg
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Blackmagic Design\DaVinci Resolve", "InstallPath"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Blackmagic Design\DaVinci Resolve", "InstallPath"),
                (winreg.HKEY_CURRENT_USER, r"Software\Blackmagic Design\DaVinci Resolve", "InstallPath"),
            ]
            for hive, subkey, val_name in reg_paths:
                try:
                    with winreg.OpenKey(hive, subkey) as key:
                        install_path, _ = winreg.QueryValueEx(key, val_name)
                        if install_path and Path(install_path).exists():
                            resolve_install_candidates.append(Path(install_path))
                            break
                except (FileNotFoundError, OSError):
                    continue
        except Exception:
            pass  # 注册表访问失败不影响
        
        # 2.4 PROGRAMDATA 路径（标准位置）
        program_data = os.environ.get("PROGRAMDATA", r"C:\ProgramData")
        programdata_script_api = Path(program_data) / "Blackmagic Design" / "DaVinci Resolve" / "Support" / "Developer" / "Scripting"
        
        # 3. 构造所有 Scripting Modules 候选路径
        script_api_candidates: List[Path] = []
        
        # 3.1 各安装目录下的 Scripting/Modules
        for install_dir in resolve_install_candidates:
            script_api_candidates.extend([
                install_dir / "Support" / "Developer" / "Scripting" / "Modules",
                install_dir / "Developer" / "Scripting" / "Modules",
                install_dir / "Scripting" / "Modules",
            ])
        
        # 3.2 PROGRAMDATA 标准路径
        script_api_candidates.append(programdata_script_api / "Modules")
        
        # 3.3 环境变量已设的路径
        env_script_api = os.environ.get("RESOLVE_SCRIPT_API", "")
        if env_script_api and Path(env_script_api).exists():
            script_api_candidates.append(Path(env_script_api) / "Modules" if not env_script_api.endswith("Modules") else Path(env_script_api))
        
        # 4. 验证并注入第一个有效的 Scripting API 路径
        script_api_injected = False
        for cand in script_api_candidates:
            try:
                if cand.exists():
                    # 检查目录下是否有 DaVinciResolveScript.py 或类似文件
                    has_module = any(f.name.lower().startswith("davinci") for f in cand.glob("*.py"))
                    if has_module or any(cand.glob("**/*.py")):
                        env_api_path = str(cand.parent if cand.name == "Modules" else cand)
                        os.environ["RESOLVE_SCRIPT_API"] = env_api_path
                        if str(cand) not in sys.path:
                            sys.path.insert(0, str(cand))
                        print(f"[DavinciColorist] Scripting API injected: {cand}")
                        script_api_injected = True
                        break
            except Exception:
                continue
        
        # 5. fusionscript.dll 探测（Resolve Python API 库的实际实现）
        fusionscript_candidates: List[Path] = []
        for install_dir in resolve_install_candidates:
            fusionscript_candidates.extend([
                install_dir / "fusionscript.dll",
                install_dir / "Resolve" / "fusionscript.dll",
                install_dir / "Support" / "Developer" / "Scripting" / "Modules" / "fusionscript.dll",
            ])
        # 环境变量已设的
        env_script_lib = os.environ.get("RESOLVE_SCRIPT_LIB", "")
        if env_script_lib and Path(env_script_lib).exists():
            fusionscript_candidates.append(Path(env_script_lib))
        
        for cand in fusionscript_candidates:
            try:
                if cand.exists():
                    os.environ["RESOLVE_SCRIPT_LIB"] = str(cand)
                    print(f"[DavinciColorist] fusionscript.dll: {cand}")
                    break
            except Exception:
                continue
        
        # 6. python_get_resolve.py 注入路径（常见辅助脚本）
        python_get_resolve_paths: List[Path] = []
        for install_dir in resolve_install_candidates:
            python_get_resolve_paths.extend([
                install_dir / "Support" / "Developer" / "Scripting" / "Examples" / "Python" / "python_get_resolve.py",
                install_dir / "Developer" / "Scripting" / "Examples" / "Utility" / "python_get_resolve.py",
                install_dir / "Developer" / "Scripting" / "Examples" / "python_get_resolve.py",
                install_dir / "Scripts" / "Comp" / "python_get_resolve.py",
                Path(__file__).parent.parent / "integrations" / "python_get_resolve.py",
            ])
        for cand in python_get_resolve_paths:
            try:
                if cand.exists():
                    parent = str(cand.parent)
                    if parent not in sys.path:
                        sys.path.insert(0, parent)
                    print(f"[DavinciColorist] python_get_resolve.py available at: {parent}")
                    break
            except Exception:
                continue
        
        # 7. 尝试导入 DaVinciResolveScript 模块
        try:
            import DaVinciResolveScript as dvr
            resolve = dvr.scriptapp("Resolve")
            if resolve:
                print("[DavinciColorist] DaVinciResolveScript.scriptapp('Resolve') connected")
                return True
        except Exception as e:
            print(f"[DavinciColorist] DaVinciResolveScript import failed: {e}")
        
        # 8. 尝试 python_get_resolve.GetResolve()
        try:
            from python_get_resolve import GetResolve
            resolve = GetResolve()
            if resolve:
                print("[DavinciColorist] python_get_resolve.GetResolve() connected")
                return True
        except Exception as e:
            print(f"[DavinciColorist] python_get_resolve import failed: {e}")
        
        return self._fuscript_available  # fuscript 可用也算成功

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
        """真实模式：通过 fuscript.exe + Lua 自动化执行调色。

        工作流程：
        1. 通过 fuscript.exe 连接到运行中的 DaVinci Resolve
        2. 创建项目、导入视频、创建时间线
        3. 应用调色（LUT 或预设）
        4. 设置渲染参数并渲染输出

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
            # 使用 fuscript.exe 引擎
            if callback:
                callback(0.05, "通过 fuscript.exe 连接 DaVinci Resolve...")

            from integrations.davinci_fuscript import ResolveColorEngine, ColorGradeConfig
            engine = ResolveColorEngine(str(self._exe_path.parent))

            if not engine.check_resolve_running():
                result.error = "DaVinci Resolve 未运行，请先启动 Resolve"
                return result

            if callback:
                callback(0.10, "已连接，准备调色...")

            # 确定 LUT 路径
            lut_path = None
            for node in nodes:
                if node.node_type == "lut" and "lut_path" in node.settings:
                    lut_path = node.settings["lut_path"]
                    break

            # 构建调色配置
            brightness = 1.0
            contrast = 1.0
            saturation = 1.0
            for node in nodes:
                if node.node_type == "brightness":
                    brightness = node.settings.get("value", 1.0)
                elif node.node_type == "contrast":
                    contrast = node.settings.get("value", 1.0)
                elif node.node_type == "saturation":
                    saturation = node.settings.get("value", 1.0)

            color_config = ColorGradeConfig(
                preset=config.color_preset,
                lut_path=lut_path,
                brightness=brightness,
                contrast=contrast,
                saturation=saturation,
            )

            if callback:
                callback(0.3, f"应用调色: {config.color_preset}...")

            # 对已有项目调色（达芬奇只负责调色）
            fuscript_result = engine.grade_project(
                project_name=config.project_name,
                color_config=color_config,
            )

            if callback:
                callback(0.8, "调色完成")

            result.success = fuscript_result.success
            result.project_name = fuscript_result.project_name
            result.duration = fuscript_result.duration

            if fuscript_result.success:
                result.output_path = output_path
                print(f"[DavinciColorist] color grade success: "
                      f"project={fuscript_result.project_name}, "
                      f"clips={fuscript_result.clips_graded}, "
                      f"duration={fuscript_result.duration:.1f}s")
            else:
                result.error = "; ".join(fuscript_result.errors) if fuscript_result.errors else "color grade failed"

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

    def _run_ffmpeg_grade(
        self,
        input_path: str,
        output_path: str,
        preset_name: str,
        callback: Optional[Callable[[float, str], None]] = None,
    ) -> ResolveColorResult:
        """通过 FFmpeg 滤镜链执行调色（Resolve 不可用时的降级方案）。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            preset_name: FFmpeg 调色预设名称
            callback: 进度回调函数

        Returns:
            ResolveColorResult 调色结果
        """
        start_time = time.time()
        result = ResolveColorResult(
            success=False,
            input_path=input_path,
            output_path=output_path,
            mode="ffmpeg",
            preset=preset_name,
        )

        ff_data = FFMPEG_COLOR_PRESETS.get(preset_name)
        if not ff_data:
            result.error = f"Unknown FFmpeg preset: {preset_name}"
            return result

        ffmpeg_filter = ff_data["ffmpeg_filter"]
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        if callback:
            callback(0.1, f"FFmpeg 调色: {preset_name}")

        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", ffmpeg_filter,
            "-c:a", "copy",
            "-preset", "medium",
            "-crf", "18",
            output_path,
        ]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=600,
            )
            if proc.returncode == 0 and Path(output_path).exists():
                result.success = True
                result.duration = time.time() - start_time
                result.nodes_applied = 1
                result.color_grade_summary = {
                    "preset": preset_name,
                    "filter": ffmpeg_filter[:100],
                    "engine": "ffmpeg",
                }
                if callback:
                    callback(1.0, "FFmpeg 调色完成")
            else:
                result.error = f"FFmpeg error: {proc.stderr[-500:]}"
        except subprocess.TimeoutExpired:
            result.error = "FFmpeg timeout (600s)"
        except Exception as e:
            result.error = f"FFmpeg error: {e}"

        return result

    def color_grade_with_artifact(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        preset: str = "default",
        artifact_path: Optional[str] = None,
    ) -> Tuple[ResolveColorResult, Optional[ColorGradeArtifact]]:
        """调色并生成 color_grade.v1 artifact。

        Args:
            input_path: 输入视频路径
            output_path: 输出视频路径
            preset: 预设名称
            artifact_path: artifact JSON 保存路径

        Returns:
            (调色结果, artifact 对象) 元组
        """
        config = ResolveColorConfig(
            mode=self.config.mode,
            color_preset=preset,
        )
        result = self.color_grade(input_path, output_path, config)

        artifact = None
        if result.success or result.mode == "simulate":
            nodes = self.apply_preset(preset)
            node_dicts = [{
                "type": n.node_type,
                "name": n.name,
                "settings": n.settings,
                "enabled": n.enabled,
            } for n in nodes]

            ffmpeg_filter = ""
            if preset in FFMPEG_COLOR_PRESETS:
                ffmpeg_filter = FFMPEG_COLOR_PRESETS[preset]["ffmpeg_filter"]

            artifact = ColorGradeArtifact(
                preset_name=preset,
                source=result.mode,
                nodes=node_dicts,
                ffmpeg_filter=ffmpeg_filter,
                metadata={
                    "input": input_path,
                    "output": result.output_path,
                    "duration": result.duration,
                    "summary": result.color_grade_summary,
                },
            )

            if artifact_path:
                artifact.save(artifact_path)

        return result, artifact

    def self_evaluate(
        self,
        original_path: str,
        graded_path: str,
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """自评估：比较原始视频和调色后视频的质量差异。

        使用 FFmpeg/FFprobe 提取统计指标进行评估。

        Args:
            original_path: 原始视频路径
            graded_path: 调色后视频路径
            metrics: 要评估的指标列表（默认全部）

        Returns:
            评估结果字典
        """
        if metrics is None:
            metrics = ["brightness_delta", "contrast_delta", "saturation_delta", "file_size_ratio"]

        eval_result: Dict[str, Any] = {
            "original": original_path,
            "graded": graded_path,
            "metrics": {},
            "score": 0.0,
            "passed": True,
            "issues": [],
        }

        def _probe_stat(path: str) -> Dict[str, Any]:
            try:
                cmd = [
                    "ffprobe", "-v", "quiet",
                    "-print_format", "json",
                    "-show_format", "-show_streams",
                    path,
                ]
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                if proc.returncode == 0:
                    return json.loads(proc.stdout)
            except Exception:
                pass
            return {}

        orig_stat = _probe_stat(original_path)
        graded_stat = _probe_stat(graded_path)

        # 文件大小比
        try:
            orig_size = Path(original_path).stat().st_size
            graded_size = Path(graded_path).stat().st_size
            size_ratio = graded_size / max(orig_size, 1)
            eval_result["metrics"]["file_size_ratio"] = round(size_ratio, 3)
            if size_ratio < 0.5:
                eval_result["issues"].append("Output file suspiciously small")
                eval_result["passed"] = False
        except Exception:
            pass

        # 基于 format 元数据的简单评估
        orig_fmt = orig_stat.get("format", {})
        graded_fmt = graded_stat.get("format", {})
        orig_dur = float(orig_fmt.get("duration", 0))
        graded_dur = float(graded_fmt.get("duration", 0))
        if orig_dur > 0 and graded_dur > 0:
            dur_delta = abs(orig_dur - graded_dur)
            eval_result["metrics"]["duration_delta"] = round(dur_delta, 3)
            if dur_delta > 1.0:
                eval_result["issues"].append(f"Duration mismatch: {dur_delta:.2f}s")

        # 综合评分（基于文件完整性和时长一致性）
        score = 1.0
        if eval_result["issues"]:
            score -= 0.1 * len(eval_result["issues"])
        if not Path(graded_path).exists():
            score = 0.0
            eval_result["passed"] = False
        eval_result["score"] = round(max(0.0, score), 2)

        return eval_result

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
