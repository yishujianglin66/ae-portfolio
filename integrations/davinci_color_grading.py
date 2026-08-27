#!/usr/bin/env python3
"""
[DEPRECATED] DaVinci Resolve Color 页面专业调色自动化 v1.0
===========================================================

** 已废弃 ** — 请使用 ``integrations/davinci_fuscript.py`` (ResolveColorEngine v4.0)

废弃原因:
- DaVinciResolveScript Python API 不可用（fusionscript.dll 初始化失败）
- 数据类型和调色逻辑已吸收到 davinci_fuscript.py 引擎
- 唯一可靠执行路径: fuscript.exe + Lua（见 davinci_fuscript.py）

保留此文件供参考，不应删除。

原功能:
为 AE Knowledge Vault 项目提供 Color 页面的完整编程控制能力，覆盖：

- **色轮控制**: Primaries Bars / Wheels（Lift / Gamma / Gain / Offset / Saturation）
- **节点图管理**: Serial / Parallel / Layer / Key / Outside 五种节点类型
- **自定义曲线**: Custom Curve、HueVsHue、HueVsSat、HueVsLum、LumVsSat、SatVsSat、LumVsLum
- **Qualifier 限定器**: 按 Hue / Sat / Lum 范围选择 + 反选
- **色彩空间**: Color Space Transform（输入/输出空间指定）
- **LUT 操作**: 应用 .cube/.3dl LUT、导出当前调色为 LUT
- **批量调色**: 多片段范围调色、复制调色到多目标
- **预设管理**: 内置预设库 + JSON 落盘 + 文件加载
- **优雅降级**: Resolve Python API 不可用时退化为 Fuscript/Lua 桥接

依赖:
- ``DaVinciResolveScript`` (Resolve 提供的 Python 集成)
- 或者 ``python_get_resolve`` (跨平台封装)

若两者均不可用，模块会保留数据结构和脚本生成能力，仅运行时调用会抛出
``ImportError``。这样设计方便在 CI / 测试环境做单元测试。
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# 可选依赖：Resolve Python API
# ============================================================================
try:
    import DaVinciResolveScript  # type: ignore
    HAS_RESOLVE_SCRIPT = True
except Exception:  # noqa: BLE001
    # Resolve 18+ 在某些 Python 版本下会触发 fusionscript SystemError
    # 捕获所有异常以保证模块在无 Resolve 环境下仍可导入
    DaVinciResolveScript = None  # type: ignore
    HAS_RESOLVE_SCRIPT = False

try:
    from python_get_resolve import GetResolve  # type: ignore
    HAS_GET_RESOLVE = True
except Exception:  # noqa: BLE001
    GetResolve = None  # type: ignore
    HAS_GET_RESOLVE = False

HAS_RESOLVE_API = HAS_RESOLVE_SCRIPT or HAS_GET_RESOLVE


# ============================================================================
# 常量与枚举
# ============================================================================

# Resolve API 实际枚举值（与 Scripting Reference 保持一致）
# nodeType for AddNode
NODE_TYPE_SERIAL = 0
NODE_TYPE_PARALLEL = 1
NODE_TYPE_LAYER = 2
NODE_TYPE_KEY = 3
NODE_TYPE_OUTSIDE = 4

# 曲线类型（Resolve 字符串）
CURVE_TYPES = (
    "Custom",
    "HueVsHue",
    "HueVsSat",
    "HueVsLum",
    "LumVsSat",
    "SatVsSat",
    "LumVsLum",
)

# 限定器范围键
QUALIFIER_HUE = "hue"
QUALIFIER_SAT = "sat"
QUALIFIER_LUM = "lum"

# 预设库目录
DEFAULT_PRESETS_DIR = (
    Path(__file__).resolve().parent / "color_presets"
)


class ColorWheelChannel(Enum):
    """Primaries 色轮通道。"""

    LIFT = "Lift"
    GAMMA = "Gamma"
    GAIN = "Gain"
    OFFSET = "Offset"
    SATURATION = "Saturation"


class ColorBalanceType(Enum):
    """色轮平衡模式（影响色轮与控制环的算法）。"""

    RGB = "rgb"
    HSL = "hsl"
    YRGB = "yrgb"


class NodeType(Enum):
    """节点类型（对应 Resolve 节点图）。"""

    SERIAL = 0
    PARALLEL = 1
    LAYER = 2
    KEY = 3
    OUTSIDE = 4

    @property
    def label(self) -> str:
        return self.name.lower()


class CurveType(Enum):
    """自定义曲线类型。"""

    CUSTOM = "Custom"
    HUE_VS_HUE = "HueVsHue"
    HUE_VS_SAT = "HueVsSat"
    HUE_VS_LUM = "HueVsLum"
    LUM_VS_SAT = "LumVsSat"
    SAT_VS_SAT = "SatVsSat"
    LUM_VS_LUM = "LumVsLum"


# ============================================================================
# 数据结构
# ============================================================================

@dataclass
class ColorWheelValues:
    """色轮值（四元组：Red/Green/Blue/Master 或 H/S/L/Master）。

    Resolve 实际色轮返回/接收的字典键取决于 ``ColorBalanceType``：
    - ``RGB``/``YRGB`` -> ``{Red, Green, Blue, Master}``
    - ``HSL`` -> ``{Hue, Saturation, Luminance, Master}``

    为简化数据建模，本类统一用 ``red/green/blue/master`` 字段存储，
    ``to_dict`` 会在 ``ColorBalanceType`` 影响下输出对应键名。
    """

    red: float = 0.0
    green: float = 0.0
    blue: float = 0.0
    master: float = 0.0

    def to_dict(self, balance_type: ColorBalanceType = ColorBalanceType.RGB) -> Dict[str, float]:
        """转换为 Resolve API 所需的字典。"""
        if balance_type == ColorBalanceType.HSL:
            return {
                "Hue": self.red,
                "Saturation": self.green,
                "Luminance": self.blue,
                "Master": self.master,
            }
        # RGB 与 YRGB 均使用 Red/Green/Blue/Master
        return {
            "Red": self.red,
            "Green": self.green,
            "Blue": self.blue,
            "Master": self.master,
        }

    @classmethod
    def from_dict(
        cls, data: Dict[str, float], balance_type: ColorBalanceType = ColorBalanceType.RGB
    ) -> "ColorWheelValues":
        """从 Resolve API 字典反序列化。"""
        if not data:
            return cls()
        if balance_type == ColorBalanceType.HSL:
            return cls(
                red=float(data.get("Hue", 0.0)),
                green=float(data.get("Saturation", 0.0)),
                blue=float(data.get("Luminance", 0.0)),
                master=float(data.get("Master", 0.0)),
            )
        return cls(
            red=float(data.get("Red", 0.0)),
            green=float(data.get("Green", 0.0)),
            blue=float(data.get("Blue", 0.0)),
            master=float(data.get("Master", 0.0)),
        )

    def is_neutral(self, tolerance: float = 1e-6) -> bool:
        """是否接近中性（无调色）。"""
        return all(abs(v) < tolerance for v in (self.red, self.green, self.blue, self.master))


@dataclass
class ColorGradingPreset:
    """一套完整的调色预设（包含色轮 + 全局参数）。"""

    name: str
    description: str = ""
    lift: ColorWheelValues = field(default_factory=ColorWheelValues)
    gamma: ColorWheelValues = field(default_factory=ColorWheelValues)
    gain: ColorWheelValues = field(default_factory=ColorWheelValues)
    offset: ColorWheelValues = field(default_factory=ColorWheelValues)
    saturation: float = 1.0
    contrast: float = 1.0
    pivot: float = 0.435
    highlight_saturation: float = 1.0
    shadow_saturation: float = 1.0
    blend_opacity: float = 1.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转为可 JSON 序列化的字典。"""
        data = asdict(self)
        # asdict 会把 dataclass 嵌套转为 dict；这里我们希望嵌套结构更友好：
        data["lift"] = self.lift.to_dict()
        data["gamma"] = self.gamma.to_dict()
        data["gain"] = self.gain.to_dict()
        data["offset"] = self.offset.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ColorGradingPreset":
        """从字典反序列化（支持 JSON 加载）。"""
        kwargs: Dict[str, Any] = {}
        for key in (
            "name",
            "description",
            "saturation",
            "contrast",
            "pivot",
            "highlight_saturation",
            "shadow_saturation",
            "blend_opacity",
            "tags",
        ):
            if key in data:
                kwargs[key] = data[key]
        for wheel_key in ("lift", "gamma", "gain", "offset"):
            if wheel_key in data and data[wheel_key] is not None:
                wheel_data = data[wheel_key]
                if isinstance(wheel_data, dict):
                    kwargs[wheel_key] = ColorWheelValues.from_dict(wheel_data)
        return cls(**kwargs)

    def summary(self) -> str:
        """人类可读的简短摘要。"""
        return (
            f"{self.name}: sat={self.saturation:.2f}, contrast={self.contrast:.2f}, "
            f"pivot={self.pivot:.2f}, tags={self.tags}"
        )


# ============================================================================
# 异常
# ============================================================================

class ColorGradingError(RuntimeError):
    """Color 页面调色相关错误的基类。"""


class ResolveNotFoundError(ColorGradingError):
    """无法连接到 DaVinci Resolve。"""


class InvalidNodeError(ColorGradingError):
    """节点索引非法或节点不存在。"""


# ============================================================================
# 主类 ColorGrader
# ============================================================================

class ColorGrader:
    """Color 页面调色器主类。

    使用方式::

        grader = ColorGrader()                     # 自动连接 Resolve
        grader.set_color_wheel(0, 0, ColorWheelChannel.LIFT,
                               ColorWheelValues(red=-0.02, green=0.01, blue=0.04))
        grader.apply_preset(0, 0, preset)

    所有方法均接受依赖注入的 ``resolve`` 对象，方便在测试中传入 Mock。
    """

    def __init__(self, resolve: Any = None) -> None:
        if resolve is None:
            if not HAS_RESOLVE_API:
                raise ResolveNotFoundError(
                    "DaVinci Resolve Python API not available. "
                    "Install DaVinciResolveScript or python_get_resolve, "
                    "or inject a resolve instance via constructor."
                )
            resolve = self._acquire_resolve()
        self.resolve = resolve
        self._validate_resolve()

    # ----------------------------------------------------------------
    # 内部辅助
    # ----------------------------------------------------------------

    def _acquire_resolve(self) -> Any:
        """尝试通过可用包装器获取 Resolve 顶层对象。"""
        if HAS_GET_RESOLVE:
            return GetResolve()
        if HAS_RESOLVE_SCRIPT and DaVinciResolveScript is not None:
            return DaVinciResolveScript.scriptapp("Resolve")
        raise ResolveNotFoundError("No Resolve binding available")

    def _validate_resolve(self) -> None:
        """校验 Resolve 对象是否有效。"""
        if self.resolve is None:
            raise ResolveNotFoundError("Resolve object is None")
        # 必须同时具备 GetProductName 和 GetProjectManager 两个核心入口
        # 否则视为无效对象（覆盖 Mock 和部分降级场景）
        if not hasattr(self.resolve, "GetProjectManager"):
            raise ResolveNotFoundError(
                "Resolve object has no GetProjectManager()"
            )
        if hasattr(self.resolve, "GetProductName"):
            try:
                _ = self.resolve.GetProductName()
                return
            except Exception as exc:  # noqa: BLE001
                raise ResolveNotFoundError(
                    f"Resolve object unusable: {exc}"
                ) from exc
        # 当 resolve 是 Mock（无 GetProductName）时不强校验 GetProductName

    def _get_current_project(self) -> Any:
        """获取当前工程（current project）。"""
        pm_fn = getattr(self.resolve, "GetProjectManager", None)
        if not pm_fn:
            raise ColorGradingError("Resolve has no GetProjectManager()")
        pm = pm_fn()
        if pm is None:
            raise ColorGradingError("ProjectManager is None")
        proj = pm.GetCurrentProject()
        if proj is None:
            raise ColorGradingError("No current project")
        return proj

    def _get_current_timeline(self) -> Any:
        """获取当前时间线。"""
        project = self._get_current_project()
        timeline = project.GetCurrentTimeline()
        if timeline is None:
            raise ColorGradingError("No current timeline")
        return timeline

    def _get_timeline_item(self, clip_index: int) -> Any:
        """通过片段索引获取 TimelineItem。"""
        timeline = self._get_current_timeline()
        items = timeline.GetItemListInTrack("video", 1) or []
        if clip_index < 0 or clip_index >= len(items):
            raise InvalidNodeError(
                f"clip_index {clip_index} out of range (total={len(items)})"
            )
        return items[clip_index]

    def _safe_lut_path(self, lut_path: Optional[str]) -> Optional[str]:
        """复制非 ASCII 路径到纯英文临时目录（与 davinci_fuscript 保持一致）。"""
        if not lut_path:
            return lut_path
        try:
            lut_path.encode("ascii")
            return lut_path
        except UnicodeEncodeError:
            pass
        src = Path(lut_path)
        if not src.exists():
            return lut_path
        temp_base = Path(tempfile.gettempdir())
        try:
            import ctypes
            buf = ctypes.create_unicode_buffer(1024)
            if ctypes.windll.kernel32.GetLongPathNameW(str(temp_base), buf, 1024) > 0:
                temp_base = Path(buf.value)
        except Exception:  # noqa: BLE001
            pass
        safe_dir = temp_base / "resolve_color_luts"
        safe_dir.mkdir(exist_ok=True)
        import hashlib
        path_hash = hashlib.md5(str(src).encode("utf-8")).hexdigest()[:12]
        safe_file = safe_dir / f"lut_{path_hash}{src.suffix}"
        if safe_file.exists() and safe_file.stat().st_size == src.stat().st_size:
            return str(safe_file)
        shutil.copy2(str(src), str(safe_file))
        return str(safe_file)

    def switch_to_color_page(self) -> None:
        """切换 UI 到 Color 页面（仅当 resolve 是真实实例时有效）。"""
        open_page = getattr(self.resolve, "OpenPage", None)
        if not open_page:
            logger.debug("Resolve has no OpenPage() (likely a Mock); skipping page switch")
            return
        try:
            open_page("color")
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to switch to color page: %s", exc)

    # ----------------------------------------------------------------
    # 色轮控制
    # ----------------------------------------------------------------

    def set_color_wheel(
        self,
        clip_index: int,
        node_index: int,
        channel: ColorWheelChannel,
        values: ColorWheelValues,
        balance_type: ColorBalanceType = ColorBalanceType.RGB,
    ) -> bool:
        """设置指定片段指定节点的某个色轮值。"""
        item = self._get_timeline_item(clip_index)
        set_fn = getattr(item, "SetNodeColorWheels", None)
        if not set_fn:
            raise ColorGradingError("TimelineItem has no SetNodeColorWheels()")
        data_type = channel.value
        result = set_fn(
            int(node_index),
            data_type,
            balance_type.value,
            values.to_dict(balance_type),
        )
        if result is False:
            logger.warning(
                "SetNodeColorWheels returned False (clip=%d, node=%d, channel=%s)",
                clip_index, node_index, channel.value,
            )
        return bool(result)

    def get_color_wheel(
        self,
        clip_index: int,
        node_index: int,
        channel: ColorWheelChannel,
        balance_type: ColorBalanceType = ColorBalanceType.RGB,
    ) -> ColorWheelValues:
        """获取指定色轮的当前值。"""
        item = self._get_timeline_item(clip_index)
        get_fn = getattr(item, "GetNodeColorWheels", None)
        if not get_fn:
            raise ColorGradingError("TimelineItem has no GetNodeColorWheels()")
        data = get_fn(int(node_index), channel.value, balance_type.value)
        if not isinstance(data, dict):
            return ColorWheelValues()
        return ColorWheelValues.from_dict(data, balance_type)

    def apply_preset(
        self,
        clip_index: int,
        node_index: int,
        preset: ColorGradingPreset,
        balance_type: ColorBalanceType = ColorBalanceType.RGB,
    ) -> bool:
        """将整套预设应用到指定片段+节点。"""
        all_ok = True
        for channel, values in (
            (ColorWheelChannel.LIFT, preset.lift),
            (ColorWheelChannel.GAMMA, preset.gamma),
            (ColorWheelChannel.GAIN, preset.gain),
            (ColorWheelChannel.OFFSET, preset.offset),
        ):
            ok = self.set_color_wheel(clip_index, node_index, channel, values, balance_type)
            all_ok = all_ok and ok

        # 全局参数（饱和度/对比度/中点/混合）
        item = self._get_timeline_item(clip_index)
        try:
            set_sat = getattr(item, "SetSaturation", None)
            if set_sat:
                set_sat(preset.saturation, node_index)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SetSaturation failed: %s", exc)
            all_ok = False
        try:
            set_contrast = getattr(item, "SetContrast", None)
            if set_contrast:
                set_contrast(preset.contrast, node_index)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SetContrast failed: %s", exc)
            all_ok = False
        try:
            set_pivot = getattr(item, "SetPivot", None)
            if set_pivot:
                set_pivot(preset.pivot, node_index)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SetPivot failed: %s", exc)
            all_ok = False
        try:
            set_opacity = getattr(item, "SetNodeOpacity", None)
            if set_opacity:
                set_opacity(node_index, preset.blend_opacity)
        except Exception as exc:  # noqa: BLE001
            logger.warning("SetNodeOpacity failed: %s", exc)
            all_ok = False
        return all_ok

    def save_preset_from_node(
        self,
        clip_index: int,
        node_index: int,
        name: str,
        description: str = "",
        balance_type: ColorBalanceType = ColorBalanceType.RGB,
    ) -> ColorGradingPreset:
        """从指定片段+节点抓取当前调色生成预设。"""
        preset = ColorGradingPreset(name=name, description=description)
        preset.lift = self.get_color_wheel(clip_index, node_index, ColorWheelChannel.LIFT, balance_type)
        preset.gamma = self.get_color_wheel(clip_index, node_index, ColorWheelChannel.GAMMA, balance_type)
        preset.gain = self.get_color_wheel(clip_index, node_index, ColorWheelChannel.GAIN, balance_type)
        preset.offset = self.get_color_wheel(clip_index, node_index, ColorWheelChannel.OFFSET, balance_type)

        item = self._get_timeline_item(clip_index)
        # 饱和度 / 对比度 / pivot
        for attr, target in (
            ("Saturation", "saturation"),
            ("Contrast", "contrast"),
        ):
            try:
                getter = getattr(item, f"Get{attr}", None)
                if getter:
                    value = getter(node_index)
                    if value is not None:
                        setattr(preset, target, float(value))
            except Exception as exc:  # noqa: BLE001
                logger.debug("Get%s failed: %s", attr, exc)
        return preset

    # ----------------------------------------------------------------
    # 节点图管理
    # ----------------------------------------------------------------

    def add_node(
        self,
        clip_index: int,
        node_type: NodeType = NodeType.SERIAL,
        label: str = "",
    ) -> int:
        """在指定片段后追加节点，返回新节点索引。"""
        item = self._get_timeline_item(clip_index)
        add_fn = getattr(item, "AddNode", None)
        if not add_fn:
            raise ColorGradingError("TimelineItem has no AddNode()")
        new_index = add_fn(int(node_type.value))
        if new_index is None or new_index < 0:
            raise ColorGradingError(f"AddNode returned {new_index!r}")
        if label:
            self.set_node_label(clip_index, int(new_index), label)
        return int(new_index)

    def delete_node(self, clip_index: int, node_index: int) -> bool:
        """删除节点。"""
        item = self._get_timeline_item(clip_index)
        delete_fn = getattr(item, "DeleteNode", None)
        if not delete_fn:
            raise ColorGradingError("TimelineItem has no DeleteNode()")
        result = delete_fn(int(node_index))
        return bool(result)

    def set_node_opacity(self, clip_index: int, node_index: int, opacity: float) -> bool:
        """设置节点混合透明度（0.0~1.0）。"""
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "SetNodeOpacity", None)
        if not fn:
            raise ColorGradingError("TimelineItem has no SetNodeOpacity()")
        return bool(fn(int(node_index), float(opacity)))

    def set_node_label(self, clip_index: int, node_index: int, label: str) -> bool:
        """设置节点标签。"""
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "SetNodeLabel", None)
        if not fn:
            logger.debug("TimelineItem has no SetNodeLabel() (skipping)")
            return False
        return bool(fn(int(node_index), str(label)))

    def get_node_count(self, clip_index: int) -> int:
        """获取片段节点总数。"""
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "GetNumNodes", None)
        if not fn:
            raise ColorGradingError("TimelineItem has no GetNumNodes()")
        return int(fn())

    # ----------------------------------------------------------------
    # 自定义曲线
    # ----------------------------------------------------------------

    def set_custom_curve(
        self,
        clip_index: int,
        node_index: int,
        curve_type: CurveType | str,
        points: List[float],
    ) -> bool:
        """设置曲线（points 为控制点数值的扁平列表）。"""
        ct = curve_type.value if isinstance(curve_type, CurveType) else str(curve_type)
        if ct not in CURVE_TYPES:
            raise ColorGradingError(f"Invalid curve_type: {ct}")
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "SetCustomCurve", None)
        if not fn:
            raise ColorGradingError("TimelineItem has no SetCustomCurve()")
        # 拷贝并归一化（确保纯 ASCII 路径等无副作用时仍稳健）
        values = [float(p) for p in points]
        return bool(fn(int(node_index), ct, values))

    def add_curve_point(
        self,
        clip_index: int,
        node_index: int,
        curve_type: CurveType | str,
        x: float,
        y: float,
    ) -> bool:
        """在曲线上追加一个控制点（先读取当前曲线再合并）。"""
        ct = curve_type.value if isinstance(curve_type, CurveType) else str(curve_type)
        current = self.get_custom_curve(clip_index, node_index, ct)
        # 约定：每两个值为 (x, y) 对
        merged: List[float] = list(current) + [float(x), float(y)]
        return self.set_custom_curve(clip_index, node_index, ct, merged)

    def reset_curve(
        self,
        clip_index: int,
        node_index: int,
        curve_type: CurveType | str,
    ) -> bool:
        """重置曲线到默认（线性）。"""
        ct = curve_type.value if isinstance(curve_type, CurveType) else str(curve_type)
        if ct == "Custom":
            return self.set_custom_curve(clip_index, node_index, ct, [])
        # 其他曲线传空列表即可
        return self.set_custom_curve(clip_index, node_index, ct, [])

    def get_custom_curve(
        self,
        clip_index: int,
        node_index: int,
        curve_type: CurveType | str,
    ) -> List[float]:
        """读取当前曲线控制点列表。"""
        ct = curve_type.value if isinstance(curve_type, CurveType) else str(curve_type)
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "GetCustomCurve", None)
        if not fn:
            raise ColorGradingError("TimelineItem has no GetCustomCurve()")
        data = fn(int(node_index), ct) or []
        if isinstance(data, dict):
            # 兼容老版本可能返回 dict 的情况
            return [float(v) for v in data.values()]
        return [float(v) for v in data]

    # ----------------------------------------------------------------
    # Qualifier
    # ----------------------------------------------------------------

    def select_with_qualifier(
        self,
        clip_index: int,
        node_index: int,
        hue_range: Tuple[float, float],
        sat_range: Tuple[float, float] = (0.0, 1.0),
        lum_range: Tuple[float, float] = (0.0, 1.0),
    ) -> bool:
        """使用限定器按 HSL 范围选择区域。

        Args:
            clip_index: 片段索引。
            node_index: 节点索引。
            hue_range: (h_min, h_max)，单位度（0-360）。
            sat_range: (s_min, s_max)，0.0-1.0。
            lum_range: (l_min, l_max)，0.0-1.0。
        """
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "SetQualifier", None)
        if not fn:
            raise ColorGradingError("TimelineItem has no SetQualifier()")
        try:
            fn(int(node_index), {
                "Hue": {"min": float(hue_range[0]), "max": float(hue_range[1])},
                "Sat": {"min": float(sat_range[0]), "max": float(sat_range[1])},
                "Lum": {"min": float(lum_range[0]), "max": float(lum_range[1])},
            })
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("SetQualifier failed: %s", exc)
            return False

    def invert_selection(self, clip_index: int, node_index: int) -> bool:
        """反选 Qualifier（仅 Studio 支持）。"""
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "InvertQualifierSelection", None)
        if not fn:
            logger.debug("InvertQualifierSelection unavailable; skipping")
            return False
        try:
            fn(int(node_index))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("InvertQualifierSelection failed: %s", exc)
            return False

    # ----------------------------------------------------------------
    # 色彩空间
    # ----------------------------------------------------------------

    def set_color_space(
        self,
        clip_index: int,
        node_index: int,
        input_space: str,
        output_space: str = "Rec.709",
    ) -> bool:
        """设置色彩空间转换（通过 Resolve 的 Color Space Transform 效果或 LUT 节点）。

        Note:
            Resolve 18+ 通过 ``SetLUT`` + 色彩空间 transform 实现。
            为简化调用，优先尝试 ``SetColorSpace`` API，如不存在则降级为 LUT 节点标签提示。
        """
        item = self._get_timeline_item(clip_index)
        cs_fn = getattr(item, "SetColorSpace", None)
        if cs_fn:
            try:
                return bool(cs_fn(int(node_index), str(input_space), str(output_space)))
            except Exception as exc:  # noqa: BLE001
                logger.debug("SetColorSpace failed: %s", exc)
        # 降级：把色彩空间信息写进节点标签，便于人工复核
        try:
            label = f"CST:{input_space}->{output_space}"
            self.set_node_label(clip_index, node_index, label)
            return True
        except Exception:  # noqa: BLE001
            return False

    # ----------------------------------------------------------------
    # LUT 操作
    # ----------------------------------------------------------------

    def apply_lut(self, clip_index: int, node_index: int, lut_path: str) -> bool:
        """应用 LUT 到指定节点。"""
        safe = self._safe_lut_path(lut_path)
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "SetLUT", None)
        if not fn:
            raise ColorGradingError("TimelineItem has no SetLUT()")
        return bool(fn(int(node_index), str(safe)))

    def export_lut(
        self,
        clip_index: int,
        node_index: int,
        output_path: str | Path,
        cube_size: int = 33,
    ) -> bool:
        """导出当前调色为 .cube LUT。"""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        item = self._get_timeline_item(clip_index)
        fn = getattr(item, "ExportLUT", None)
        if not fn:
            raise ColorGradingError("TimelineItem has no ExportLUT() (Studio only)")
        result = fn(int(node_index), str(out), int(cube_size))
        return bool(result)

    # ----------------------------------------------------------------
    # 批量调色
    # ----------------------------------------------------------------

    def grade_clip_range(
        self,
        clip_indices: List[int],
        node_index: int,
        preset: ColorGradingPreset,
        balance_type: ColorBalanceType = ColorBalanceType.RGB,
    ) -> Dict[int, bool]:
        """将预设应用到多个片段（返回每个片段的成功标志）。"""
        results: Dict[int, bool] = {}
        for idx in clip_indices:
            try:
                results[idx] = self.apply_preset(idx, node_index, preset, balance_type)
            except Exception as exc:  # noqa: BLE001
                logger.warning("grade_clip_range failed for clip %d: %s", idx, exc)
                results[idx] = False
        return results

    def copy_grading(
        self,
        source_clip_index: int,
        target_clip_indices: List[int],
        node_index: int = 0,
        balance_type: ColorBalanceType = ColorBalanceType.RGB,
    ) -> Dict[int, bool]:
        """从源片段复制调色到多个目标片段。"""
        preset = self.save_preset_from_node(
            source_clip_index, node_index,
            name=f"copied_from_{source_clip_index}",
            description="",
            balance_type=balance_type,
        )
        return self.grade_clip_range(target_clip_indices, node_index, preset, balance_type)

    # ----------------------------------------------------------------
    # 预设管理
    # ----------------------------------------------------------------

    def save_preset_to_file(
        self,
        preset: ColorGradingPreset,
        file_path: str | Path,
    ) -> Path:
        """将预设保存为 JSON 文件，返回写入路径。"""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(preset.to_dict(), f, ensure_ascii=False, indent=2)
        return path

    def load_preset_from_file(self, file_path: str | Path) -> ColorGradingPreset:
        """从 JSON 文件加载预设。"""
        path = Path(file_path)
        if not path.exists():
            # 尝试在默认预设目录查找
            alt = DEFAULT_PRESETS_DIR / Path(file_path).with_suffix(".json").name
            if alt.exists():
                path = alt
            else:
                raise FileNotFoundError(f"Preset file not found: {file_path}")
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ColorGradingPreset.from_dict(data)


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    # 常量
    "HAS_RESOLVE_API",
    "HAS_RESOLVE_SCRIPT",
    "HAS_GET_RESOLVE",
    "DEFAULT_PRESETS_DIR",
    "CURVE_TYPES",
    "NODE_TYPE_SERIAL",
    "NODE_TYPE_PARALLEL",
    "NODE_TYPE_LAYER",
    "NODE_TYPE_KEY",
    "NODE_TYPE_OUTSIDE",
    "QUALIFIER_HUE",
    "QUALIFIER_SAT",
    "QUALIFIER_LUM",
    # 枚举
    "ColorWheelChannel",
    "ColorBalanceType",
    "NodeType",
    "CurveType",
    # 数据结构
    "ColorWheelValues",
    "ColorGradingPreset",
    # 异常
    "ColorGradingError",
    "ResolveNotFoundError",
    "InvalidNodeError",
    # 主类
    "ColorGrader",
]
