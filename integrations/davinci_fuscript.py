#!/usr/bin/env python3
"""
DaVinci Resolve 自动化引擎 v5.0
================================

通过 fuscript.exe + Lua 脚本自动化 DaVinci Resolve Studio。
基于 CDL + LUT + SetProperty 架构（Studio 版可用 API）。

核心能力:
- 全流程：创建项目 + 导入素材 + 建时间线 + 逐片段调色
- LUT 应用（.cube 文件）+ 强度控制
- CDL 调色（Slope/Offset/Power/Saturation）
- 变速控制（SetProperty）
- 变换控制（缩放/位移/旋转/裁切/透明度）
- FFmpeg 混合渲染
- 场景感知推荐（20 种场景类型）
- 12 个 Resolve 调色预设
- 7 个 FFmpeg 降级预设
- ColorGradeArtifact 标准化调色描述（跨软件互通）
- quick_grade() 一键调色 + ffmpeg_grade() 降级调色

接口设计:
- create_project()         → 全流程（创建+导入+调色）
- grade_project()          → 对已有项目调色
- apply_preset_config()    → 应用命名预设（12 个 RESOLVE_PRESETS）
- apply_lut()              → 应用 LUT 到时间线
- batch_grade()            → 批量调色多个项目
- render_project()         → 渲染输出
- get_recommendation()     → 获取场景调色推荐
- quick_grade()            → 一键创建+导入+调色+渲染+关闭
- ffmpeg_grade()           → FFmpeg 降级调色
- build_artifact()         → 生成 ColorGradeArtifact
"""
import os
import subprocess
import tempfile
import time
import json
import hashlib
import signal
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import datetime

# 导入新引擎
from integrations.resolve_engine import (
    ResolveAutomationEngine,
    CDLConfig as _CDLConfig,
    TransformConfig as _TransformConfig,
    SpeedConfig as _SpeedConfig,
    ResolveError,
)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class FuscriptResult:
    """fuscript.exe 执行结果"""
    success: bool
    stdout: str = ""
    stderr: str = ""
    return_code: int = -1
    duration: float = 0.0
    project_name: str = ""
    timeline_name: str = ""
    clips_graded: int = 0
    clips_imported: int = 0
    render_complete: bool = False
    output_path: str = ""
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ColorWheelParams:
    """色轮参数（Lift/Gamma/Gain/Offset）"""
    red: float = 0.0
    green: float = 0.0
    blue: float = 0.0
    master: float = 0.0


@dataclass
class CurvePoint:
    """曲线控制点"""
    x: float = 0.0
    y: float = 0.0


@dataclass
class QualifierParams:
    """Qualifier 限定器参数"""
    hue_min: float = 0.0
    hue_max: float = 360.0
    sat_min: float = 0.0
    sat_max: float = 1.0
    lum_min: float = 0.0
    lum_max: float = 1.0
    invert: bool = False


@dataclass
class ColorGradeConfig:
    """调色配置"""
    preset: str = "cinematic"
    lut_path: Optional[str] = None
    lut_intensity: float = 1.0
    brightness: float = 1.0
    contrast: float = 1.0
    saturation: float = 1.0
    scene_type: Optional[str] = None
    segment_presets: Optional[Dict[str, str]] = None
    lift: ColorWheelParams = field(default_factory=ColorWheelParams)
    gamma: ColorWheelParams = field(
        default_factory=lambda: ColorWheelParams(red=1.0, green=1.0, blue=1.0, master=1.0)
    )
    gain: ColorWheelParams = field(
        default_factory=lambda: ColorWheelParams(red=1.0, green=1.0, blue=1.0, master=1.0)
    )
    offset: ColorWheelParams = field(default_factory=ColorWheelParams)
    pivot: float = 0.435
    blend_opacity: float = 1.0
    custom_curve: List[float] = field(default_factory=list)
    hue_vs_hue: List[float] = field(default_factory=list)
    hue_vs_sat: List[float] = field(default_factory=list)
    hue_vs_lum: List[float] = field(default_factory=list)
    lum_vs_sat: List[float] = field(default_factory=list)
    sat_vs_sat: List[float] = field(default_factory=list)
    lum_vs_lum: List[float] = field(default_factory=list)
    qualifier: Optional[QualifierParams] = None


@dataclass
class RenderConfig:
    """渲染配置"""
    format: str = "MP4"
    codec: str = "H.264"
    resolution: str = "1920x1080"
    frame_rate: str = "24"
    quality: str = "Automatic"
    timeout: int = 600


@dataclass
class ColorGradeArtifact:
    """color_grade.v1 JSON artifact 数据类。

    标准化的调色描述格式，可在 Resolve / FFmpeg / AE 之间互通。
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


# ============================================================================
# Resolve LUT 查找（集成预设库）
# ============================================================================

RESOLVE_LUT_DIRS = [
    r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT",
    r"%APPDATA%\Blackmagic Design\DaVinci Resolve\Support\LUT",
    r"D:\app\LUT",
]

DCTL_PRESET_MAP = {
    "cinematic": ("Demystify-Color", "DMC_3x3Matrix"),
    "film": ("Demystify-Color", "ExposureTool"),
    "exposure": ("Demystify-Color", "Just_Exposure"),
    "primal": ("Demystify-Color", "DMC_Primal"),
    "log-lin": ("Demystify-Color", "DMC_PLogLin"),
    "filmic": ("MoazElgabry", "ME_Filmic Contrast"),
    "hue-curve": ("MoazElgabry", "ME_Hue Curve"),
    "localized-contrast": ("MoazElgabry", "ME_Localized Contrast"),
    "ratio-shaper": ("MoazElgabry", "ME_Ratio Shaper"),
    "color-model": ("MoazElgabry", "ME_Color Models"),
    "opendrt": ("OpenDisplayTransform", "OpenDRT"),
    "tesseract": ("OpenDisplayTransform", "Tesseract"),
    "chromagnon": ("OpenDisplayTransform", "Chromagnon"),
    "jzdt": ("OpenDisplayTransform", "JzDT"),
    "zone-grade": ("OpenDisplayTransform", "ZoneGrade"),
    "zone-saturation": ("OpenDisplayTransform", "ZoneSaturation"),
    "saturation": ("OpenDisplayTransform", "Saturation"),
    "shadow-contrast": ("OpenDisplayTransform", "ShadowContrast"),
}


# ============================================================================
# Resolve 调色预设 (CDL 架构)
# ============================================================================

RESOLVE_PRESETS: Dict[str, Dict[str, Any]] = {
    "default": {
        "description": "默认轻微调色，自然色彩增强",
        "cdl": {"slope": (1.03, 1.03, 1.03), "offset": (0.0, 0.0, 0.0),
                "power": (1.0, 1.0, 1.0), "saturation": 1.05},
    },
    "cinematic": {
        "description": "电影级调色（高对比，偏蓝阴影，暖高光）",
        "cdl": {"slope": (1.08, 1.05, 0.98), "offset": (-0.02, 0.0, 0.03),
                "power": (1.0, 1.0, 1.02), "saturation": 0.95},
    },
    "warm_vintage": {
        "description": "温暖复古（暖色调，低对比）",
        "cdl": {"slope": (1.1, 1.02, 0.9), "offset": (0.03, 0.0, -0.02),
                "power": (1.0, 1.03, 1.08), "saturation": 0.8},
    },
    "cool_teal": {
        "description": "冷色调青蓝（青色阴影，蓝色高光）",
        "cdl": {"slope": (0.95, 1.02, 1.1), "offset": (-0.02, 0.0, 0.05),
                "power": (1.0, 1.0, 1.08), "saturation": 1.0},
    },
    "vivid_pop": {
        "description": "鲜艳活泼（高饱和，高对比）",
        "cdl": {"slope": (1.1, 1.1, 1.1), "offset": (0.0, 0.0, 0.0),
                "power": (1.0, 1.05, 1.05), "saturation": 1.35},
    },
    "muted_film": {
        "description": "低饱和胶片（低饱和，柔和对比）",
        "cdl": {"slope": (0.97, 0.97, 0.97), "offset": (0.02, 0.02, 0.02),
                "power": (0.95, 0.95, 0.95), "saturation": 0.6},
    },
    "noir_bw": {
        "description": "黑白 noir（高对比黑白）",
        "cdl": {"slope": (1.15, 1.15, 1.15), "offset": (0.0, 0.0, 0.0),
                "power": (0.9, 0.9, 0.9), "saturation": 0.0},
    },
    "pastel_dream": {
        "description": "粉彩梦幻（低对比，高明度）",
        "cdl": {"slope": (1.02, 1.0, 1.02), "offset": (0.05, 0.03, 0.05),
                "power": (1.08, 1.05, 1.08), "saturation": 0.7},
    },
    "puppet_warm": {
        "description": "木偶暖调（暖棕色，柔和高光）",
        "cdl": {"slope": (1.08, 1.02, 0.93), "offset": (0.03, 0.0, -0.02),
                "power": (1.05, 1.0, 0.92), "saturation": 0.9},
    },
    "puppet_porcelain": {
        "description": "瓷娃娃冷调（冷白，微蓝）",
        "cdl": {"slope": (1.02, 1.03, 1.08), "offset": (0.0, 0.0, 0.03),
                "power": (0.98, 0.99, 1.03), "saturation": 0.85},
    },
    "horror_grade": {
        "description": "恐怖调色（低饱和，绿色调）",
        "cdl": {"slope": (0.9, 1.05, 0.9), "offset": (-0.02, 0.02, -0.02),
                "power": (0.88, 1.0, 0.88), "saturation": 0.5},
    },
    "anime_style": {
        "description": "动画风格（鲜艳色彩，高对比）",
        "cdl": {"slope": (1.1, 1.1, 1.1), "offset": (0.0, 0.0, 0.0),
                "power": (1.0, 1.0, 1.0), "saturation": 1.4},
    },
}


# ============================================================================
# FFmpeg Filter 调色预设
# ============================================================================

FFMPEG_COLOR_PRESETS: Dict[str, Dict[str, Any]] = {
    "natural": {
        "description": "自然色彩增强",
        "ffmpeg_filter": (
            "eq=saturation=1.1:contrast=1.05:brightness=0.02:gamma=1.02,"
            "curves=m='0/0 0.25/0.28 0.5/0.53 0.75/0.78 1/1'"
        ),
        "params": {"saturation": 1.1, "contrast": 1.05, "brightness": 0.02},
    },
    "warm": {
        "description": "暖色调",
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
        "description": "冷色调",
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
        "description": "冲击力",
        "ffmpeg_filter": (
            "eq=saturation=1.3:contrast=1.25:brightness=-0.03:gamma=0.95,"
            "curves=m='0/0 0.2/0.15 0.5/0.55 0.8/0.85 1/1',"
            "unsharp=3:3:0.8"
        ),
        "params": {"saturation": 1.3, "contrast": 1.25, "sharpness": 0.8},
    },
    "soft": {
        "description": "柔和梦幻",
        "ffmpeg_filter": (
            "eq=saturation=0.85:contrast=0.85:brightness=0.05:gamma=1.08,"
            "curves=m='0/0.05 0.3/0.35 0.6/0.65 1/1'"
        ),
        "params": {"saturation": 0.85, "contrast": 0.85, "glow": 0.2},
    },
    "cinematic_ff": {
        "description": "电影感",
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
        "description": "银幕感",
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


def preset_to_color_grade_config(preset_name: str) -> ColorGradeConfig:
    """将 RESOLVE_PRESETS 中的预设名转为 ColorGradeConfig。"""
    preset_data = RESOLVE_PRESETS.get(preset_name)
    if not preset_data:
        return ColorGradeConfig(preset=preset_name)
    cdl = preset_data.get("cdl", {})
    slope = cdl.get("slope", (1, 1, 1))
    offset = cdl.get("offset", (0, 0, 0))
    power = cdl.get("power", (1, 1, 1))
    return ColorGradeConfig(
        preset=preset_name,
        lift=ColorWheelParams(red=offset[0], green=offset[1], blue=offset[2]),
        gamma=ColorWheelParams(red=power[0], green=power[1], blue=power[2]),
        gain=ColorWheelParams(red=slope[0], green=slope[1], blue=slope[2]),
        saturation=cdl.get("saturation", 1.0),
    )


def find_dctl_for_preset(preset_name: str) -> Optional[str]:
    """查找预设对应的 DCTL 文件路径"""
    resolve_lut = Path(r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\LUT")
    if preset_name in DCTL_PRESET_MAP:
        subdir, pattern = DCTL_PRESET_MAP[preset_name]
        search_dir = resolve_lut / subdir
        if search_dir.exists():
            for f in search_dir.glob(f"{pattern}*.dctl"):
                return str(f)
    for lut_dir_template in RESOLVE_LUT_DIRS:
        lut_dir = Path(os.path.expandvars(lut_dir_template))
        if lut_dir.exists():
            for dctl_file in lut_dir.rglob("*.dctl"):
                if preset_name.lower() in dctl_file.stem.lower():
                    return str(dctl_file)
    return None


def find_lut_for_preset(preset_name: str, variant: int = 1) -> Optional[str]:
    """查找预设对应的 LUT/DCTL 文件"""
    try:
        from integrations.lut_preset_library import get_lut_library
        lib = get_lut_library()
        lut_path = lib.get_preset_lut(preset_name, variant)
        if lut_path:
            return lut_path
    except ImportError:
        pass
    dctl_path = find_dctl_for_preset(preset_name)
    if dctl_path:
        return dctl_path
    custom_lut_dir = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\resources\luts")
    if custom_lut_dir.exists():
        for ext in [".cube", ".3dl"]:
            candidate = custom_lut_dir / f"{preset_name}{ext}"
            if candidate.exists():
                return str(candidate)
    for lut_dir_template in RESOLVE_LUT_DIRS:
        lut_dir = Path(os.path.expandvars(lut_dir_template))
        if lut_dir.exists():
            for lut_file in lut_dir.rglob("*.cube"):
                if preset_name.lower() in lut_file.stem.lower():
                    return str(lut_file)
    return None


# ============================================================================
# 辅助函数
# ============================================================================

def _config_to_cdl(config: ColorGradeConfig) -> _CDLConfig:
    """将 ColorGradeConfig 转为 resolve_engine 的 CDLConfig"""
    return _CDLConfig(
        slope=(config.gain.red, config.gain.green, config.gain.blue),
        offset=(config.lift.red, config.lift.green, config.lift.blue),
        power=(config.gamma.red, config.gamma.green, config.gamma.blue),
        saturation=config.saturation,
    )


def _preset_to_cdl(preset_name: str) -> _CDLConfig:
    """将预设名转为 CDLConfig"""
    preset_data = RESOLVE_PRESETS.get(preset_name)
    if not preset_data:
        return _CDLConfig()
    cdl = preset_data.get("cdl", {})
    return _CDLConfig(
        slope=cdl.get("slope", (1, 1, 1)),
        offset=cdl.get("offset", (0, 0, 0)),
        power=cdl.get("power", (1, 1, 1)),
        saturation=cdl.get("saturation", 1.0),
    )


# ============================================================================
# 自动化引擎 v5.0（基于 resolve_engine.py 委托）
# ============================================================================

class ResolveColorEngine:
    """DaVinci Resolve Studio 自动化引擎 v5.0
    
    内部委托给 ResolveAutomationEngine（fuscript.exe + Lua + CDL/LUT/SetProperty）。
    保持与 v4.0 相同的公共 API 接口。
    """

    def __init__(
        self,
        resolve_home: Optional[str] = None,
        lut_dirs: Optional[List[str]] = None,
        custom_lut_dir: Optional[str] = None,
    ):
        # fuscript.exe 路径
        self.fuscript_path = Path(resolve_home or os.environ.get(
            "AEKV_RESOLVE_HOME", r"D:\app"
        )) / "fuscript.exe"
        
        # 创建内部引擎
        self._engine = ResolveAutomationEngine(
            fuscript_path=str(self.fuscript_path),
            timeout=120,
        )
        
        # LUT 搜索路径
        if lut_dirs is None:
            env_lut_dirs = os.environ.get("AEKV_LUT_DIRS", "")
            if env_lut_dirs:
                lut_dirs = [d.strip() for d in env_lut_dirs.split(";") if d.strip()]
            else:
                lut_dirs = RESOLVE_LUT_DIRS.copy()
        self.lut_dirs: List[Path] = [Path(os.path.expandvars(d)) for d in lut_dirs]

        if custom_lut_dir is None:
            custom_lut_dir = os.environ.get(
                "AEKV_CUSTOM_LUT_DIR",
                str(Path(__file__).resolve().parent.parent / "resources" / "luts")
            )
        self.custom_lut_dir = Path(custom_lut_dir)

    # ================================================================
    # Resolve 进程管理
    # ================================================================
    
    def check_resolve_running(self) -> bool:
        """检查 Resolve 是否正在运行"""
        try:
            result = self._engine._execute_lua(
                self._engine._wrap_lua('emit_ok({running = true})')
            )
            return True
        except Exception:
            return False
    
    def launch_resolve(self, wait_timeout: int = 60, callback: Optional[Callable] = None) -> bool:
        """确保 Resolve 正在运行（如果已运行则直接返回 True）"""
        if self.check_resolve_running():
            return True
        # Resolve 应该已经在运行（Studio 版通常手动启动）
        # 等待一段时间看它是否启动
        for i in range(wait_timeout // 3):
            if callback:
                callback(f"Waiting for Resolve... ({(i+1)*3}s)")
            time.sleep(3)
            if self.check_resolve_running():
                return True
        return False
    
    def close_resolve(self, wait_timeout: int = 30, callback: Optional[Callable] = None) -> bool:
        """不关闭 Resolve（Studio 版保持运行）"""
        return True
    
    @contextmanager
    def with_resolve(self, wait_timeout: int = 60, close_after: bool = True):
        """上下文管理器：确保 Resolve 可用"""
        self.launch_resolve(wait_timeout=wait_timeout)
        try:
            yield self
        finally:
            if close_after:
                self.close_resolve()

    # ================================================================
    # 核心操作
    # ================================================================
    
    def create_project(
        self,
        project_name: str,
        media_files: List[str],
        timeline_name: str = "MainTimeline",
        color_config: Optional[ColorGradeConfig] = None,
        render: bool = False,
        output_dir: Optional[str] = None,
    ) -> FuscriptResult:
        """创建项目、导入素材、建时间线、逐片段调色（可选渲染）"""
        t0 = time.time()
        result = FuscriptResult(success=False, project_name=project_name)
        
        if color_config is None:
            color_config = ColorGradeConfig()
        
        try:
            # Step 1: 创建项目 + 时间线 + 导入素材
            tl_info = self._engine.create_timeline_with_media(
                project_name, timeline_name, media_files
            )
            result.clips_imported = tl_info.get("clip_count", 0)
            result.timeline_name = timeline_name
            
            # Step 2: 调色
            cdl = _config_to_cdl(color_config)
            items = tl_info.get("items", [])
            for item in items:
                idx = item.get("index", 1)
                # 检查是否有分段预设
                if color_config.segment_presets:
                    item_name = item.get("name", "")
                    seg_preset = color_config.segment_presets.get(
                        item_name, color_config.segment_presets.get(str(idx))
                    )
                    # v4.0 兼容：精确匹配失败时按子串匹配（片段名常含序号后缀）
                    if seg_preset is None and item_name:
                        for pattern, preset_name in color_config.segment_presets.items():
                            if pattern and pattern in item_name:
                                seg_preset = preset_name
                                break
                    if seg_preset:
                        cdl = _preset_to_cdl(seg_preset)
                
                self._engine.apply_cdl(project_name, timeline_name, idx, cdl)
                result.clips_graded += 1
            
            # Step 2.5: 应用 LUT（如果指定）
            lut_path = color_config.lut_path or find_lut_for_preset(color_config.preset)
            lut_path = self._safe_lut_path(lut_path)
            if lut_path and os.path.exists(lut_path):
                for item in items:
                    idx = item.get("index", 1)
                    self._engine.apply_lut(project_name, timeline_name, idx, lut_path)
            
            # Step 3: 渲染（可选）
            if render and output_dir:
                os.makedirs(output_dir, exist_ok=True)
                output_path = os.path.join(output_dir, f"{project_name}.mp4")
                self._engine.render_timeline(project_name, output_path)
                result.output_path = output_path
                result.render_complete = os.path.exists(output_path)
            
            result.success = True
            result.duration = time.time() - t0
            
        except Exception as e:
            result.errors.append(str(e))
            result.duration = time.time() - t0
        
        return result
    
    def grade_project(
        self,
        project_name: str,
        color_config: Optional[ColorGradeConfig] = None,
    ) -> FuscriptResult:
        """对已有项目调色"""
        t0 = time.time()
        result = FuscriptResult(success=False, project_name=project_name)
        
        if color_config is None:
            color_config = ColorGradeConfig()
        
        try:
            # 加载项目
            self._engine.load_project(project_name)
            
            # 获取项目信息
            lua = self._engine._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found: {project_name}") end
    local tl = proj:GetCurrentTimeline()
    if not tl then error("No current timeline") end
    local items = tl:GetItemsInTrack("video", 1)
    local count = 0
    if items then
        for k, v in pairs(items) do count = count + 1 end
    end
    emit_ok({{item_count = count}})
''')
            info = self._engine._execute_lua(lua)
            item_count = info.get("item_count", 0)
            
            # 逐片段调色
            cdl = _config_to_cdl(color_config)
            for idx in range(1, item_count + 1):
                self._engine.apply_cdl(project_name, "", idx, cdl)
                result.clips_graded += 1
            
            # 应用 LUT
            lut_path = color_config.lut_path or find_lut_for_preset(color_config.preset)
            lut_path = self._safe_lut_path(lut_path)
            if lut_path and os.path.exists(lut_path):
                for idx in range(1, item_count + 1):
                    self._engine.apply_lut(project_name, "", idx, lut_path)
            
            result.success = True
            result.duration = time.time() - t0
            
        except Exception as e:
            result.errors.append(str(e))
            result.duration = time.time() - t0
        
        return result
    
    def auto_grade(
        self,
        project_name: str,
        media_files: List[str],
        color_config: Optional[ColorGradeConfig] = None,
        render: bool = False,
        output_dir: Optional[str] = None,
        close_after: bool = True,
        callback: Optional[Callable] = None,
    ) -> FuscriptResult:
        """全自动调色"""
        def _cb(progress: float, msg: str):
            if callback:
                callback(progress, msg)
        
        _cb(0.1, "Checking Resolve...")
        if not self.check_resolve_running():
            _cb(0.2, "Waiting for Resolve...")
            if not self.launch_resolve(callback=callback):
                return FuscriptResult(success=False, errors=["Resolve not available"])
        
        _cb(0.3, "Creating and grading...")
        result = self.create_project(
            project_name=project_name,
            media_files=media_files,
            color_config=color_config,
            render=render,
            output_dir=output_dir,
        )
        
        if close_after:
            _cb(0.9, "Done")
        return result
    
    def render_project(
        self,
        project_name: str,
        output_path: str,
        render_config: Optional[RenderConfig] = None,
    ) -> FuscriptResult:
        """渲染项目"""
        t0 = time.time()
        result = FuscriptResult(success=False, project_name=project_name)
        
        try:
            self._engine.render_timeline(project_name, output_path)
            result.output_path = output_path
            result.render_complete = os.path.exists(output_path)
            result.success = result.render_complete
            result.duration = time.time() - t0
        except Exception as e:
            result.errors.append(str(e))
            result.duration = time.time() - t0
        
        return result
    
    def apply_lut(
        self,
        project_name: str,
        lut_path: str,
        timeline_name: Optional[str] = None,
    ) -> FuscriptResult:
        """对项目的当前时间线应用 LUT"""
        t0 = time.time()
        result = FuscriptResult(success=False, project_name=project_name)
        safe_path = self._safe_lut_path(lut_path)
        
        try:
            self._engine.load_project(project_name)
            # 获取 item 数量
            lua = self._engine._wrap_lua(f'''
    local resolve = Resolve()
    local pm = resolve:GetProjectManager()
    local proj = pm:LoadProject("{project_name}")
    if not proj then error("Project not found") end
    local tl = proj:GetCurrentTimeline()
    if not tl then error("No timeline") end
    local items = tl:GetItemsInTrack("video", 1)
    local count = 0
    if items then
        for k, v in pairs(items) do
            count = count + 1
            v:SetLUT("{safe_path.replace(chr(92), "/")}")
        end
    end
    emit_ok({{count = count}})
''')
            info = self._engine._execute_lua(lua)
            result.clips_graded = info.get("count", 0)
            result.success = True
            result.duration = time.time() - t0
        except Exception as e:
            result.errors.append(str(e))
            result.duration = time.time() - t0
        
        return result
    
    def batch_grade(
        self,
        projects: List[Dict[str, Any]],
    ) -> List[FuscriptResult]:
        """批量调色多个项目"""
        results = []
        for proj_info in projects:
            name = proj_info.get("name", "")
            media = proj_info.get("media_files", [])
            config = proj_info.get("color_config")
            result = self.create_project(name, media, color_config=config)
            results.append(result)
        return results
    
    def apply_preset_config(
        self,
        project_name: str,
        preset_name: str,
        item_index: int = 1,
    ) -> bool:
        """应用命名预设到指定片段"""
        cdl = _preset_to_cdl(preset_name)
        try:
            self._engine.apply_cdl(project_name, "", item_index, cdl)
            return True
        except Exception:
            return False
    
    def get_recommendation(self, scene_type: str) -> Dict[str, Any]:
        """获取场景调色推荐"""
        try:
            from integrations.lut_preset_library import get_scene_presets
            preset_names = get_scene_presets(scene_type)
            if preset_names:
                best_name = preset_names[0]
                lut = find_lut_for_preset(best_name)
                return {
                    "preset": best_name,
                    "lut_path": lut,
                    "cdl": _preset_to_cdl(best_name).__dict__,
                    "presets": preset_names,
                }
        except ImportError:
            pass
        fallback = {
            "高燃": "cinematic",
            "vlog": "warm_vintage",
            "电影": "cinematic",
            "自然": "default",
        }
        for key, preset in fallback.items():
            if key in scene_type:
                return {
                    "preset": preset,
                    "lut_path": find_lut_for_preset(preset),
                    "cdl": _preset_to_cdl(preset).__dict__,
                    "presets": [],
                }
        return {
            "preset": "cinematic",
            "lut_path": find_lut_for_preset("cinematic"),
            "cdl": _preset_to_cdl("cinematic").__dict__,
            "presets": [],
        }

    # ================================================================
    # 变速 & 变换
    # ================================================================
    
    def set_speed(self, project_name: str, item_index: int, speed: float) -> bool:
        """设置片段播放速度"""
        try:
            self._engine.set_speed(project_name, item_index, speed)
            return True
        except Exception:
            return False
    
    def set_transform(self, project_name: str, item_index: int,
                      zoom_x: float = 1.0, zoom_y: float = 1.0,
                      position_x: float = 0.0, position_y: float = 0.0,
                      rotation: float = 0.0, opacity: float = 100.0) -> bool:
        """设置片段变换"""
        tf = _TransformConfig(
            zoom_x=zoom_x, zoom_y=zoom_y,
            position_x=position_x, position_y=position_y,
            rotation=rotation, opacity=opacity,
        )
        try:
            self._engine.set_transform(project_name, item_index, tf)
            return True
        except Exception:
            return False

    # ================================================================
    # 内部辅助方法
    # ================================================================
    
    def _safe_lut_path(self, lut_path: Optional[str]) -> Optional[str]:
        """将含非 ASCII 字符的 LUT 路径复制到纯英文临时目录"""
        if not lut_path:
            return lut_path
        try:
            lut_path.encode('ascii')
            return lut_path
        except UnicodeEncodeError:
            pass
        src = Path(lut_path)
        if not src.exists():
            return lut_path
        temp_base = tempfile.gettempdir()
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetLongPathNameW(temp_base, buf, 1024) > 0:
                temp_base = buf.value
        except Exception:
            pass
        safe_dir = Path(temp_base) / "resolve_luts"
        safe_dir.mkdir(exist_ok=True)
        path_hash = hashlib.md5(str(src).encode('utf-8')).hexdigest()[:12]
        safe_name = f"lut_{path_hash}{src.suffix}"
        safe_file = safe_dir / safe_name
        if safe_file.exists() and safe_file.stat().st_size == src.stat().st_size:
            return str(safe_file)
        shutil.copy2(str(src), str(safe_file))
        return str(safe_file)

    # ================================================================
    # FFmpeg 降级
    # ================================================================
    
    def ffmpeg_grade(
        self,
        input_path: str,
        preset: str = "natural",
        output_path: Optional[str] = None,
    ) -> FuscriptResult:
        """FFmpeg 降级调色"""
        preset_data = FFMPEG_COLOR_PRESETS.get(preset)
        if not preset_data:
            return FuscriptResult(success=False, errors=[f"Unknown FFmpeg preset: {preset}"])
        
        ffmpeg_filter = preset_data["ffmpeg_filter"]
        inp = Path(input_path)
        if not output_path:
            output_path = str(inp.parent / f"{inp.stem}_{preset}_graded{inp.suffix}")
        
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", ffmpeg_filter,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-c:a", "copy", output_path,
        ]
        
        t0 = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            duration = time.time() - t0
            success = result.returncode == 0 and Path(output_path).exists()
            return FuscriptResult(
                success=success, stdout=result.stdout, stderr=result.stderr,
                return_code=result.returncode, duration=duration,
                output_path=output_path, clips_graded=1 if success else 0,
                metadata={"ffmpeg_filter": ffmpeg_filter, "preset": preset},
                errors=[] if success else [result.stderr[-500:] if result.stderr else "FFmpeg failed"],
            )
        except FileNotFoundError:
            return FuscriptResult(success=False, duration=time.time() - t0,
                                  errors=["FFmpeg not found."])
        except subprocess.TimeoutExpired:
            return FuscriptResult(success=False, duration=300.0, errors=["FFmpeg timeout"])

    def quick_grade(
        self,
        video_path: str,
        preset: str = "cinematic",
        output_dir: Optional[str] = None,
        close_after: bool = True,
        callback: Optional[Callable] = None,
    ) -> FuscriptResult:
        """一键调色"""
        def _cb(progress: float, msg: str):
            if callback:
                callback(progress, msg)
        
        video = Path(video_path)
        if not video.exists():
            return FuscriptResult(success=False, errors=[f"Video not found: {video_path}"])
        
        if output_dir is None:
            output_dir = str(video.parent)
        
        project_name = f"QuickGrade_{video.stem}_{int(time.time())}"
        
        if not self.check_resolve_running():
            _cb(0.3, "Resolve unavailable, falling back to FFmpeg...")
            ffmpeg_preset = preset if preset in FFMPEG_COLOR_PRESETS else "natural"
            return self.ffmpeg_grade(video_path, ffmpeg_preset)
        
        _cb(0.3, f"Creating project '{project_name}'...")
        config = preset_to_color_grade_config(preset) if preset in RESOLVE_PRESETS else ColorGradeConfig(preset=preset)
        result = self.create_project(
            project_name, [video_path],
            color_config=config, render=True, output_dir=output_dir,
        )
        result.metadata["preset"] = preset
        result.metadata["mode"] = "quick_grade"
        return result

    # ================================================================
    # Artifact 生成
    # ================================================================
    
    def build_artifact(
        self,
        preset_name: str,
        source: str = "resolve",
    ) -> ColorGradeArtifact:
        """为指定预设生成 ColorGradeArtifact。

        节点采用 node_type=primary + settings 的标准格式（跨平台互通），
        同时保留 type=cdl + slope/offset/power/saturation 平铺字段，
        兼容 Resolve 侧 apply_artifact_resolve 的 CDL 消费方。
        未知预设返回空 Artifact。
        """
        cdl = _preset_to_cdl(preset_name)
        preset_data = RESOLVE_PRESETS.get(preset_name, {})

        if not preset_data:
            # FFmpeg 预设：无 Resolve CDL，但可提供滤镜链
            ff_preset = FFMPEG_COLOR_PRESETS.get(preset_name)
            if ff_preset:
                return ColorGradeArtifact(
                    preset_name=preset_name,
                    source=source,
                    ffmpeg_filter=ff_preset["ffmpeg_filter"],
                )
            return ColorGradeArtifact(preset_name=preset_name, source=source)
        # 从 CDL 推导统一 settings（Resolve 值域：0..2 以 1.0 为中心）
        slope = list(cdl.slope)
        offset = list(cdl.offset)
        power = list(cdl.power)
        saturation = cdl.saturation
        contrast = sum(power) / 3.0 if power else 1.0
        brightness = sum(offset) / 3.0 if offset else 0.0
        
        nodes = [{
            "node_type": "primary",
            "name": "Primary",
            "enabled": True,
            "type": "cdl",
            "settings": {
                "gain": slope,
                "lift": offset,
                "gamma": power,
                "saturation": saturation,
                "contrast": contrast,
                "brightness": brightness,
            },
            "slope": slope,
            "offset": offset,
            "power": power,
            "saturation": saturation,
        }]
        
        lut = find_lut_for_preset(preset_name)
        if lut:
            nodes.append({"type": "lut", "path": lut})
        
        # 推导 FFmpeg 滤镜：优先匹配 FFMPEG_COLOR_PRESETS，否则从 settings 生成
        ffmpeg_filter = ""
        if preset_name in FFMPEG_COLOR_PRESETS:
            ffmpeg_filter = FFMPEG_COLOR_PRESETS[preset_name]["ffmpeg_filter"]
        elif preset_name == "cinematic":
            ffmpeg_filter = "eq=saturation=0.95:contrast=1.02:brightness=-0.01"
        else:
            eq_parts = []
            if abs(saturation - 1.0) > 1e-6:
                eq_parts.append(f"saturation={saturation:.3f}")
            if abs(contrast - 1.0) > 1e-6:
                eq_parts.append(f"contrast={contrast:.3f}")
            if abs(brightness) > 1e-6:
                eq_parts.append(f"brightness={brightness:.3f}")
            if eq_parts:
                ffmpeg_filter = "eq=" + ":".join(eq_parts)
        
        return ColorGradeArtifact(
            preset_name=preset_name,
            source=source,
            nodes=nodes,
            ffmpeg_filter=ffmpeg_filter,
            metadata={"description": preset_data.get("description", "")},
        )
    
    def artifact_to_ffmpeg_filter(self, artifact: ColorGradeArtifact) -> str:
        """将 Artifact 转为 FFmpeg 滤镜链。

        优先使用 artifact.ffmpeg_filter；为空时从节点 settings 推导。
        """
        if artifact.ffmpeg_filter:
            return artifact.ffmpeg_filter
        
        settings: Dict[str, Any] = {}
        for node in artifact.nodes or []:
            node_settings = self._node_settings(node)
            settings.update(node_settings)
        
        if not settings:
            # 空 Artifact 回退到 natural 预设
            return FFMPEG_COLOR_PRESETS["natural"]["ffmpeg_filter"]
        
        enabled = [n for n in (artifact.nodes or []) if n.get("enabled", True)]
        if not enabled:
            # 全部禁用 → natural 回退
            return FFMPEG_COLOR_PRESETS["natural"]["ffmpeg_filter"]
        
        eq_parts: List[str] = []
        if "saturation" in settings and settings["saturation"] is not None:
            eq_parts.append(f"saturation={float(settings['saturation']):.3f}")
        if "contrast" in settings and settings["contrast"] is not None:
            eq_parts.append(f"contrast={float(settings['contrast']):.3f}")
        if "brightness" in settings and settings["brightness"] is not None:
            eq_parts.append(f"brightness={float(settings['brightness']):.3f}")
        
        has_color_wheel = any(
            k in settings for k in ("lift", "gamma", "gain")
        )
        if eq_parts and not has_color_wheel:
            return "eq=" + ":".join(eq_parts)
        
        # 色轮 → colorbalance 滤镜
        colorbalance = self._settings_to_colorbalance(settings)
        if eq_parts and colorbalance:
            return "eq=" + ":".join(eq_parts) + "," + colorbalance
        if colorbalance:
            return colorbalance
        return "eq=" + ":".join(eq_parts) if eq_parts else FFMPEG_COLOR_PRESETS["natural"]["ffmpeg_filter"]
    
    def _settings_to_colorbalance(self, settings: Dict[str, Any]) -> str:
        """将 lift/gamma/gain 色轮转成 FFmpeg colorbalance 滤镜。"""
        lift = settings.get("lift")
        gamma = settings.get("gamma")
        gain = settings.get("gain")
        
        def _delta(vals, base=1.0):
            if not vals:
                return None
            return [float(vals[i]) - base for i in range(3)]
        
        parts: List[str] = []
        l_d = _delta(lift)
        g_d = _delta(gamma)
        gn_d = _delta(gain)
        if l_d:
            parts.append(f"rs={l_d[0]:.3f}:gs={l_d[1]:.3f}:bs={l_d[2]:.3f}")
        if g_d:
            parts.append(f"rm={g_d[0]:.3f}:gm={g_d[1]:.3f}:bm={g_d[2]:.3f}")
        if gn_d:
            parts.append(f"rh={gn_d[0]:.3f}:gh={gn_d[1]:.3f}:bh={gn_d[2]:.3f}")
        return "colorbalance=" + ":".join(parts) if parts else ""

    def apply_artifact_ffmpeg(
        self,
        input_path: str,
        artifact: ColorGradeArtifact,
        output_path: Optional[str] = None,
    ) -> FuscriptResult:
        """使用 FFmpeg 应用 Artifact 调色"""
        ffmpeg_filter = artifact.ffmpeg_filter
        if not ffmpeg_filter:
            # 从 CDL 节点构建简单滤镜
            for node in artifact.nodes:
                if node.get("type") == "cdl":
                    slope = node.get("slope", [1, 1, 1])
                    offset = node.get("offset", [0, 0, 0])
                    sat = node.get("saturation", 1.0)
                    ffmpeg_filter = f"eq=saturation={sat}"
                    break
        
        if not ffmpeg_filter:
            return FuscriptResult(success=False, errors=["No FFmpeg filter in artifact"])
        
        inp = Path(input_path)
        if not output_path:
            output_path = str(inp.parent / f"{inp.stem}_graded{inp.suffix}")
        
        cmd = [
            "ffmpeg", "-y", "-i", str(input_path),
            "-vf", ffmpeg_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "18",
            "-c:a", "copy", output_path,
        ]
        
        t0 = time.time()
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            success = result.returncode == 0 and Path(output_path).exists()
            return FuscriptResult(
                success=success, output_path=output_path,
                duration=time.time() - t0,
                errors=[] if success else [result.stderr[-500:] if result.stderr else "Failed"],
            )
        except Exception as e:
            return FuscriptResult(success=False, errors=[str(e)])
    
    def apply_artifact_resolve(
        self,
        project_name: str,
        artifact: ColorGradeArtifact,
        item_index: int = 1,
    ) -> FuscriptResult:
        """在 Resolve 中应用 Artifact 调色"""
        t0 = time.time()
        result = FuscriptResult(success=False, project_name=project_name)
        
        try:
            for node in artifact.nodes:
                if node.get("type") == "cdl":
                    cdl = _CDLConfig(
                        slope=tuple(node.get("slope", [1, 1, 1])),
                        offset=tuple(node.get("offset", [0, 0, 0])),
                        power=tuple(node.get("power", [1, 1, 1])),
                        saturation=node.get("saturation", 1.0),
                    )
                    self._engine.apply_cdl(project_name, "", item_index, cdl)
                elif node.get("type") == "lut":
                    lut_path = node.get("path", "")
                    if lut_path and os.path.exists(lut_path):
                        self._engine.apply_lut(project_name, "", item_index, lut_path)
            
            result.success = True
            result.clips_graded = 1
            result.duration = time.time() - t0
        except Exception as e:
            result.errors.append(str(e))
            result.duration = time.time() - t0
        
        return result

    # ================================================================
    # Artifact <-> AE 跨平台互通
    # ================================================================

    @staticmethod
    def _node_settings(node: Dict[str, Any]) -> Dict[str, Any]:
        """提取节点设置：兼容 node_type(primary)+settings 与 type(cdl) 两种格式。"""
        if "settings" in node and isinstance(node["settings"], dict):
            return node["settings"]
        # cdl 格式：slope/offset/power/saturation 平铺在节点上
        settings: Dict[str, Any] = {}
        if "slope" in node:
            settings["gain"] = list(node["slope"])
        if "offset" in node:
            settings["lift"] = list(node["offset"])
        if "power" in node:
            settings["gamma"] = list(node["power"])
        if "saturation" in node:
            settings["saturation"] = node["saturation"]
        return settings

    @staticmethod
    def _fmt_color(val: float) -> str:
        """将数值格式化为 JSX 可读的保留两位字符串。"""
        return f"{float(val):.2f}"

    def artifact_to_ae_jsx(
        self,
        artifact: ColorGradeArtifact,
        layer_name: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
        """将 Artifact 调色描述转为 AE ExtendScript (JSX)。

        生成一个调整图层并为其添加 Brightness & Contrast / Hue Saturation /
        Color Balance 效果，效果属性从 Artifact 节点设置推导。
        """
        name = layer_name or f"Grade - {artifact.preset_name or 'untitled'}"
        # JSX 字符串转义：双引号必须转义
        safe_name = name.replace('\\', '\\\\').replace('"', '\\"')

        # 聚合所有启用节点的设置，按效果分组；效果名用节点 name
        nodes = artifact.nodes or []
        brightness = 0.0
        contrast = 0.0
        saturation = 0.0
        lift: Optional[List[float]] = None
        gamma: Optional[List[float]] = None
        gain: Optional[List[float]] = None
        node_name = "Primary"

        for node in nodes:
            if not node.get("enabled", True):
                continue
            settings = self._node_settings(node)
            node_name = node.get("name") or node_name
            if "brightness" in settings:
                brightness = float(settings["brightness"])
            if "contrast" in settings:
                contrast = float(settings["contrast"])
            if "saturation" in settings:
                saturation = float(settings["saturation"])
            if "lift" in settings:
                lift = [float(x) for x in settings["lift"]]
            if "gamma" in settings:
                gamma = [float(x) for x in settings["gamma"]]
            if "gain" in settings:
                gain = [float(x) for x in settings["gain"]]

        lines: List[str] = []
        lines.append("var comp = app.project.activeItem;")
        lines.append("var adjLayer = comp.layers.addSolid([0, 0, 0], 'Temp', comp.width, comp.height, comp.pixelAspect, comp.duration);")
        lines.append("adjLayer.adjustmentLayer = true;")
        lines.append(f"adjLayer.name = '{safe_name}';")

        has_color = lift is not None or gamma is not None or gain is not None

        # 节点名用于效果实例命名（JSX 安全转义）
        safe_node = node_name.replace('\\', '\\\\').replace('"', '\\"')

        # AE 来源的 artifact：优先输出原始 AE 参数（无损往返）
        ae_raw = (artifact.metadata or {}).get("ae_raw") or {}
        raw_shadow = ae_raw.get("shadow") or [0.0, 0.0, 0.0]
        raw_midtone = ae_raw.get("midtone") or [0.0, 0.0, 0.0]
        raw_highlight = ae_raw.get("highlight") or [0.0, 0.0, 0.0]

        # Brightness & Contrast
        if brightness != 0.0 or contrast != 0.0:
            bc = f"adjLayer.property('ADBE Effect Parade').addProperty('ADBE Brightness & Contrast');"
            lines.append(bc)
            lines.append(f"bc.name = '{safe_node} - BC';")
            lines.append(f"bc.property('ADBE Brightness-Contrast-1').setValue({self._fmt_color(brightness)});")
            lines.append(f"bc.property('ADBE Brightness-Contrast-2').setValue({self._fmt_color(contrast)});")

        # Hue Saturation
        if saturation != 0.0:
            hs = f"adjLayer.property('ADBE Effect Parade').addProperty('ADBE Hue Saturation');"
            lines.append(hs)
            lines.append(f"hs.name = '{safe_node} - HS';")
            lines.append(f"hs.property('ADBE HSL-2').setValue({self._fmt_color(saturation)});")

        # Color Balance（色轮：lift/gamma/gain → 阴影/中间调/高光）
        if has_color:
            cb = f"adjLayer.property('ADBE Effect Parade').addProperty('ADBE Color Balance');"
            lines.append(cb)
            lines.append(f"cb.name = '{safe_node} - CB';")
            for idx, (name, wheel) in enumerate(
                (("0001", lift), ("0002", gamma), ("0003", gain)), start=1
            ):
                if wheel is None:
                    continue
                # AE 来源优先用原始值
                if raw_shadow or raw_midtone or raw_highlight:
                    if idx == 1:
                        r, g, b = raw_shadow[0], raw_shadow[1], raw_shadow[2]
                    elif idx == 2:
                        r, g, b = raw_midtone[0], raw_midtone[1], raw_midtone[2]
                    else:
                        r, g, b = raw_highlight[0], raw_highlight[1], raw_highlight[2]
                    lines.append(f"cb.property('ADBE Color Balance-{name}').setValue([{self._fmt_color(r)}, {self._fmt_color(g)}, {self._fmt_color(b)}]);")
                else:
                    r, g, b = wheel[0], wheel[1], wheel[2]
                    lines.append(f"cb.property('ADBE Color Balance-{name}').setValue([{self._fmt_color(r)}, {self._fmt_color(g)}, {self._fmt_color(b)}]);")

        lines.append("app.project.save();")
        jsx = "\n".join(lines)

        if output_path:
            out = Path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(jsx, encoding="utf-8")
        return jsx

    def build_artifact_from_ae(
        self,
        ae_effects: List[Dict[str, Any]],
        preset_name: str = "from_ae",
    ) -> ColorGradeArtifact:
        """从 AE 效果列表构建 ColorGradeArtifact。

        支持 ADBE Brightness & Contrast / ADBE Hue Saturation / ADBE Color Balance。
        未知效果被忽略，亮度/对比度/饱和度采用累加式映射。
        """
        settings: Dict[str, Any] = {}
        brightness = 0.0
        contrast = 0.0
        saturation = 0.0
        lift: List[float] = [1.0, 1.0, 1.0, 0.0]
        gamma: List[float] = [1.0, 1.0, 1.0, 0.0]
        gain: List[float] = [1.0, 1.0, 1.0, 0.0]
        effect_count = 0
        # 原始 AE 参数（往返无损保留，供 JSX 重建）
        ae_raw: Dict[str, Any] = {
            "brightness": 0.0, "contrast": 0.0, "saturation": 0.0,
            "shadow": [0.0, 0.0, 0.0], "midtone": [0.0, 0.0, 0.0],
            "highlight": [0.0, 0.0, 0.0],
        }

        for fx in ae_effects:
            match = fx.get("matchName", "")
            props = fx.get("properties", {})
            if match == "ADBE Brightness & Contrast":
                effect_count += 1
                brightness += float(props.get("ADBE Brightness-Contrast-1", 0.0))
                contrast += float(props.get("ADBE Brightness-Contrast-2", 0.0))
                ae_raw["brightness"] = brightness
                ae_raw["contrast"] = contrast
            elif match == "ADBE Hue Saturation":
                effect_count += 1
                sat_val = float(props.get("ADBE HSL-2", 0.0))
                saturation += sat_val
                ae_raw["saturation"] = saturation
            elif match == "ADBE Color Balance":
                effect_count += 1
                shadow = props.get("ADBE Color Balance-0001", [0.0, 0.0, 0.0])
                midtone = props.get("ADBE Color Balance-0002", [0.0, 0.0, 0.0])
                highlight = props.get("ADBE Color Balance-0003", [0.0, 0.0, 0.0])
                for i in range(3):
                    lift[i] += float(shadow[i]) / 50.0
                    gamma[i] += float(midtone[i]) / 50.0
                    gain[i] += float(highlight[i]) / 50.0
                    ae_raw["shadow"][i] += float(shadow[i])
                    ae_raw["midtone"][i] += float(midtone[i])
                    ae_raw["highlight"][i] += float(highlight[i])

        # AE 值域（-100..100 / -180..180）归一化到 Resolve 风格 (0..2 以 1.0 为中心)
        norm_brightness = brightness / 100.0
        norm_contrast = 1.0 + contrast / 100.0
        norm_saturation = 1.0 + saturation / 100.0
        # AE 亮度映射到 gain 的 master 通道（统一表示）
        gain[3] = norm_brightness
        settings["brightness"] = norm_brightness
        settings["contrast"] = norm_contrast
        settings["saturation"] = norm_saturation
        settings["lift"] = lift
        settings["gamma"] = gamma
        settings["gain"] = gain

        nodes = [{
            "node_type": "primary",
            "name": "AE Import",
            "enabled": True,
            "settings": settings,
        }]
        return ColorGradeArtifact(
            preset_name=preset_name,
            source="after_effects",
            nodes=nodes,
            ffmpeg_filter=(
                f"eq=brightness={settings['brightness']:.3f}:saturation={settings['saturation']:.3f}:contrast={settings['contrast']:.3f}"
            ),
            metadata={"ae_effects_count": effect_count, "ae_raw": ae_raw},
        )

    def _artifact_to_color_grade_config(
        self, artifact: ColorGradeArtifact
    ) -> ColorGradeConfig:
        """将 Artifact 转为 Resolve 调色配置 ColorGradeConfig。"""
        settings: Dict[str, Any] = {}
        for node in artifact.nodes or []:
            node_settings = self._node_settings(node)
            settings.update(node_settings)

        def _wheel(key: str) -> ColorWheelParams:
            vals = settings.get(key)
            if isinstance(vals, (list, tuple)) and len(vals) >= 4:
                return ColorWheelParams(
                    red=float(vals[0]), green=float(vals[1]),
                    blue=float(vals[2]), master=float(vals[3]),
                )
            if isinstance(vals, (list, tuple)) and len(vals) >= 3:
                return ColorWheelParams(
                    red=float(vals[0]), green=float(vals[1]), blue=float(vals[2]),
                )
            return ColorWheelParams()

        return ColorGradeConfig(
            preset=artifact.preset_name or "cinematic",
            brightness=float(settings.get("brightness", 1.0)),
            contrast=float(settings.get("contrast", 1.0)),
            saturation=float(settings.get("saturation", 1.0)),
            pivot=float(settings.get("pivot", 0.435)),
            lift=_wheel("lift"),
            gamma=_wheel("gamma"),
            gain=_wheel("gain"),
        )


# ============================================================================
# 便捷函数
# ============================================================================

def grade_project(
    project_name: str,
    preset: str = "cinematic",
    lut_path: Optional[str] = None,
    brightness: float = 1.0,
    contrast: float = 1.0,
    saturation: float = 1.0,
    lut_intensity: float = 1.0,
    resolve_home: Optional[str] = None,
) -> FuscriptResult:
    """便捷函数：对已有项目调色"""
    engine = ResolveColorEngine(resolve_home=resolve_home)
    config = ColorGradeConfig(
        preset=preset, lut_path=lut_path,
        brightness=brightness, contrast=contrast,
        saturation=saturation, lut_intensity=lut_intensity,
    )
    return engine.grade_project(project_name, config)


def get_color_recommendation(scene_type: str) -> Dict[str, Any]:
    """便捷函数：获取场景调色推荐"""
    engine = ResolveColorEngine()
    return engine.get_recommendation(scene_type)


def quick_grade(
    video_path: str,
    preset: str = "cinematic",
    output_dir: Optional[str] = None,
    resolve_home: Optional[str] = None,
) -> FuscriptResult:
    """便捷函数：一键调色"""
    engine = ResolveColorEngine(resolve_home=resolve_home)
    return engine.quick_grade(video_path, preset=preset, output_dir=output_dir)


def ffmpeg_grade(
    input_path: str,
    preset: str = "natural",
    output_path: Optional[str] = None,
) -> FuscriptResult:
    """便捷函数：FFmpeg 降级调色"""
    engine = ResolveColorEngine()
    return engine.ffmpeg_grade(input_path, preset=preset, output_path=output_path)
