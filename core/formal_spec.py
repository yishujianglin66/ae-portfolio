#!/usr/bin/env python3
"""形式化规范层：将管线硬规则实现为可执行不变量。

Phase C 修复要点（对应已确认漏洞清单）:
  C1  不变量读取的 key 与生产管线真实数据对齐 —— 缺字段/空数据由
      check_invariants 记 logger.warning 告警（区分"未测量"与"真实值"），
      不再静默通过。
  H1  非数字类型统一经 _to_number / _parse_position / _parse_bitrate 归一化，
      无法解析的值记违规而非抛 TypeError。
  H2  bitrate 支持三种形态并统一为 bps：整数/浮点（视为 bps）、带 K/M/G
      后缀字符串（"192k"→192000、"20M"→20000000、"1.5G"→1500000000，
      大小写不敏感）、纯数字字符串（视为 bps）。解析失败 → 违规。
  M1  ae_render_time_ms 缺失/ffmpeg_params 为空时返回通过但记 warning，
      不再默认 0 恒通过。
  M2  check_invariants 聚合全部违规后一次性抛出，不再首个违规即短路。
  M4  rotation 归一化到 [0, 360)（-45 % 360 = 315 合法，450 % 360 = 90 合法）。
"""
from __future__ import annotations

import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class InvariantViolation(Exception):
    """不变量违规异常。"""


class Invariant(ABC):
    """形式化不变量基类。"""

    @abstractmethod
    def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        """校验管线上下文并返回通过状态和错误信息。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """不变量名称。"""


def _to_number(value: Any, default: float | None = None) -> float | None:
    """将任意输入安全归一化为 float（H1）。

    支持 int / float / 数字字符串（"90"→90.0）。无法解析时返回 default，
    不抛 TypeError/ValueError。
    """
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_bitrate(value: Any) -> float | None:
    """将 FFmpeg 码率参数归一化为 bps（H2）。

    三种形态：
      1. 整数/浮点 → 直接视为 bps；
      2. 带 K/M/G 后缀字符串（大小写不敏感）：
         "192k" → 192_000, "20M" → 20_000_000, "1.5G" → 1_500_000_000；
      3. 纯数字字符串（"3000000"）→ 视为 bps。
    解析失败返回 None（由调用方记为违规）。
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        m = re.fullmatch(r"([+-]?\d+(?:\.\d+)?)\s*([kKmMgG]?)\s*", s)
        if not m:
            return None
        num = float(m.group(1))
        suffix = m.group(2).lower()
        if suffix == "k":
            return num * 1_000
        if suffix == "m":
            return num * 1_000_000
        if suffix == "g":
            return num * 1_000_000_000
        return num  # 纯数字字符串 → bps
    return None


def _parse_position(value: Any) -> tuple[float, float] | None:
    """将图层位置归一化为 (x, y)（H1）。

    - None → (0, 0)（缺省位置语义）；
    - tuple/list → 取前两个元素转 float，不足补 0；
    - 字符串 "10,20" → (10, 20)；纯数字字符串 "5" → (5, 0)；
    - 数字（非可迭代）→ 视为 (0, 0)，不抛 TypeError；
    - 无法解析 → None（由调用方记为违规）。
    """
    if value is None or isinstance(value, bool):
        return (0.0, 0.0)
    if isinstance(value, (int, float)):
        # 非可迭代数字 → 视为 (0, 0)
        return (0.0, 0.0)
    if isinstance(value, str):
        parts = [p.strip() for p in value.split(",")]
        try:
            nums = [float(p) for p in parts if p != ""]
        except ValueError:
            return None
        if not nums:
            return None
        return (nums[0], nums[1] if len(nums) >= 2 else 0.0)
    try:
        seq = list(value)
    except TypeError:
        return (0.0, 0.0)
    if not seq:
        return (0.0, 0.0)
    try:
        x = float(seq[0])
        y = float(seq[1]) if len(seq) >= 2 else 0.0
    except (TypeError, ValueError):
        return None
    return (x, y)


class FanPositionConstraint(Invariant):
    """3D 扇子位置和旋转约束。"""

    @property
    def name(self) -> str:
        return "FanPositionConstraint"

    def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        layers = context.get("ae_layers")
        if not layers:
            # C1/M1: ae_layers 未提供或为空 → 视为"未测量"，告警并跳过
            logger.warning(
                "FanPositionConstraint: ae_layers 未提供或为空, 跳过扇叶位置校验"
            )
            return True, ""
        for layer in layers:
            if not isinstance(layer, dict):
                continue
            if layer.get("type") != "fan_blade":
                continue  # 非 fan_blade 图层不参与扇叶约束
            pos = _parse_position(layer.get("position"))
            if pos is None:
                return False, (
                    f"扇叶位置无法解析: {layer.get('position')!r} "
                    f"(期望 (x, y) 可迭代或 \"x,y\" 字符串)"
                )
            x, y = pos
            if not (-960 <= x <= 960):
                return False, f"扇叶 X 越界: {x} (允许范围 [-960, 960])"
            if not (-540 <= y <= 540):
                return False, f"扇叶 Y 越界: {y} (允许范围 [-540, 540])"
            rotation = _to_number(layer.get("rotation"), default=0.0)
            if rotation is None:
                return False, f"扇叶旋转角无法解析: {layer.get('rotation')!r}"
            # M4: 负角度/超 360 归一化到 [0, 360)（Python 取模对负数返回正余数）
            rotation = rotation % 360.0
            if not (0 <= rotation < 360):
                return False, f"扇叶旋转角越界: {rotation} (允许范围 [0, 360))"
        return True, ""


class FFmpegParamBoundary(Invariant):
    """FFmpeg 码率和帧率边界。"""

    @property
    def name(self) -> str:
        return "FFmpegParamBoundary"

    def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        params = context.get("ffmpeg_params")
        if not params:
            # C1/M1: ffmpeg_params 未提供或为空 → 视为"未测量"，告警并跳过
            logger.warning(
                "FFmpegParamBoundary: ffmpeg_params 未提供或为空, 跳过码率/帧率校验"
            )
            return True, ""
        if not isinstance(params, dict):
            return False, (
                f"ffmpeg_params 类型错误: {type(params).__name__} (期望 dict)"
            )
        bitrate = _parse_bitrate(params.get("bitrate"))
        if bitrate is None:
            return False, (
                f"码率无法解析: {params.get('bitrate')!r} "
                f"(支持 bps 数字或 k/M/G 后缀, 如 20M)"
            )
        if bitrate > 50_000_000:
            return False, f"码率超限: {bitrate} bps (最大 50 Mbps)"
        framerate = _to_number(params.get("framerate"), default=30.0)
        if framerate is None:
            return False, f"帧率无法解析: {params.get('framerate')!r}"
        if not (23.976 <= framerate <= 120):
            return False, f"帧率越界: {framerate} (允许范围 [23.976, 120])"
        return True, ""


class AERenderTimeout(Invariant):
    """AE 单帧渲染超时保护。"""

    @property
    def name(self) -> str:
        return "AERenderTimeout"

    def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        render_time = context.get("ae_render_time_ms")
        if render_time is None:
            # M1: 未测量 → 告警并跳过超时校验（不再默认 0 恒通过）
            logger.warning(
                "AERenderTimeout: ae_render_time_ms 未提供, 跳过超时校验"
            )
            return True, ""
        rt = _to_number(render_time)
        if rt is None:
            return False, f"ae_render_time_ms 无法解析: {render_time!r}"
        if rt > 30_000:
            return False, f"单帧渲染超时: {rt}ms (最大 30s)"
        return True, ""


class H3VideoSpec(Invariant):
    """H3 生成/编辑产物规格约束（官方硬规格）。

    校验项：
      - resolution 必须是 768p / 2k(1440p) 之一
      - duration_sec ∈ [5, 15]
      - fps 必须 == 24（H3 固定 24FPS）
      - aspect_ratio ∈ {9:16, 16:9, 1:1, 4:3, 21:9}
      - has_audio_track == True（H3 原生双声道）
    """

    _ALLOWED_RESOLUTIONS = ("768p", "2k", "1440p")
    _ALLOWED_RATIOS = ("9:16", "16:9", "1:1", "4:3", "21:9")

    @property
    def name(self) -> str:
        return "H3VideoSpec"

    def check(self, context: dict[str, Any]) -> tuple[bool, str]:
        # C1 修复精神：H3 专属字段缺时视为"未测量"，告警不视为违规
        h3 = context.get("h3_output")
        if not h3 or not isinstance(h3, dict):
            logger.warning("H3VideoSpec: h3_output 未提供或为空，跳过规格校验")
            return True, ""
        resolution = str(h3.get("resolution", "")).lower()
        if resolution and resolution not in self._ALLOWED_RESOLUTIONS:
            return False, (
                f"H3 resolution={resolution!r} 非官方规格, 允许: {self._ALLOWED_RESOLUTIONS}"
            )
        duration = _to_number(h3.get("duration_sec"))
        if duration is not None and not (5.0 <= duration <= 15.0):
            return False, f"H3 duration_sec={duration} 超出 [5, 15]"
        fps = _to_number(h3.get("fps"))
        if fps is not None and abs(fps - 24.0) > 0.001:
            return False, f"H3 fps={fps} 非官方固定 24"
        ratio = str(h3.get("aspect_ratio", ""))
        if ratio and ratio not in self._ALLOWED_RATIOS:
            return False, f"H3 aspect_ratio={ratio!r} 非官方规格, 允许: {self._ALLOWED_RATIOS}"
        has_audio = h3.get("has_audio_track")
        if has_audio is False:
            return False, "H3 应带原生双声道音轨, 但 has_audio_track=False"
        return True, ""


FORMAL_INVARIANTS: list[Invariant] = [
    FanPositionConstraint(),
    FFmpegParamBoundary(),
    AERenderTimeout(),
    H3VideoSpec(),
]


def check_invariants(context: dict[str, Any], skip: bool = False) -> None:
    """校验全部注册不变量，违规时抛出 `InvariantViolation`。

    M2: 遍历全部不变量并聚合所有违规，全部检查完若存在违规则一次性抛出
        （消息用 "; " 连接），不再首个违规即短路。
    skip=True 时跳过校验（调试模式）。
    """
    if skip:
        logger.debug("跳过不变量校验（调试模式）")
        return
    errors: list[str] = []
    for invariant in FORMAL_INVARIANTS:
        passed, error = invariant.check(context)
        if not passed:
            errors.append(f"[{invariant.name}] {error}")
        else:
            logger.debug("不变量校验通过: %s", invariant.name)
    if errors:
        raise InvariantViolation("; ".join(errors))
