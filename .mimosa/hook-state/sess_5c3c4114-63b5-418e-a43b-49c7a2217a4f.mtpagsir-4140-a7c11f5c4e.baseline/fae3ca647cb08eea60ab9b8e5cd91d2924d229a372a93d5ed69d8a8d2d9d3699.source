#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRS 音视频同步分析器 v2.0
========================

VRS (Video Reverse-engineering System) v2.0 子模块。

职责：
    识别"节拍驱动的效果"与"音画同步关系"。从参考视频中提取转场/速度/效果事件，
    与音频节拍对齐，识别哪些效果是"踩拍"触发的，并生成对应的 AE 关键帧与表达式。

输入：
    - 视频文件路径（必填）
    - 音频文件路径（可选，未提供时由 ffmpeg 从视频提取）

输出（dict）：
    {
        "audio_features": {...},
        "beats": [0.5, 1.0, ...],
        "rhythm_events": [{time, event_type, on_beat, beat_strength, deviation_ms}],
        "sync_points": [{video_time, beat_time, confidence}],
        "beat_driven_effects": [{effect_type, audio_source, trigger_times, ae_params, confidence}],
        "sync_keyframes": [{property, time, value, easing}],
        "audio_reactive_expressions": [{property, expression, description}],
        "sync_score": 0.85
    }

依赖：
    - 必需：loguru
    - 可选：audio-analyzer.py（AudioAnalyzer，librosa 实现）
    - 可选：audio_analyzer_librosa.py（LibrosaAudioAnalyzer，降级时使用）
    - 可选：video-effect-analyzer.py（VideoEffectAnalyzer）
    - 可选：ffmpeg-toolkit.py（FFmpegToolkit）
    - 可选：librosa / numpy（用于能量曲线与相关性计算）

降级策略：
    1. 优先调用 audio-analyzer.py 的 AudioAnalyzer
    2. 不可用时降级到 audio_analyzer_librosa.py 的 LibrosaAudioAnalyzer
    3. 仍不可用时返回 success=False（不抛 ImportError）
    4. librosa/numpy 不可用时使用简化算法（基于时间间隔的能量估计）

用法：
    python vrs_audio_sync_analyzer.py --test
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import math
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

# -----------------------------------------------------------------------------
# 路径与依赖动态加载（与 video_effect_analyzer_v2.py 一致的风格）
# -----------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent
_OUTPUT_DIR = _PROJECT_ROOT / "output"


def _load_module_by_path(module_name: str, file_path: Path):
    """根据文件路径动态加载 Python 模块（兼容连字符文件名）。

    修复 dataclasses 加载问题：模块必须先注册到 sys.modules，
    否则 @dataclass 装饰器在解析 cls.__module__ 时会因
    sys.modules.get(name) 返回 None 而抛出
    "'NoneType' object has no attribute '__dict__'" 错误。
    """
    if not file_path.exists():
        return None
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    # 关键修复：先注册到 sys.modules，避免 dataclasses 装饰器查找失败
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
        return module
    except Exception as exc:  # noqa: BLE001
        # 加载失败时清理 sys.modules，避免残留
        sys.modules.pop(module_name, None)
        logger.warning(f"加载模块失败 {file_path.name}: {exc}")
        return None


# 动态加载现有分析器（可选依赖）
_audio_analyzer_mod = _load_module_by_path(
    "_vrs_audio_analyzer_legacy", _PROJECT_ROOT / "audio-analyzer.py"
)
_audio_analyzer_librosa_mod = _load_module_by_path(
    "_vrs_audio_analyzer_librosa", _PROJECT_ROOT / "audio_analyzer_librosa.py"
)
_video_effect_analyzer_mod = _load_module_by_path(
    "_vrs_video_effect_analyzer_legacy", _PROJECT_ROOT / "video-effect-analyzer.py"
)
_ffmpeg_toolkit_mod = _load_module_by_path(
    "_vrs_ffmpeg_toolkit", _PROJECT_ROOT / "ffmpeg-toolkit.py"
)

# numpy / librosa 可用性
try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:  # pragma: no cover
    _NUMPY_AVAILABLE = False
    np = None  # type: ignore

try:
    import librosa
    _LIBROSA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LIBROSA_AVAILABLE = False
    librosa = None  # type: ignore


# -----------------------------------------------------------------------------
# 常量
# -----------------------------------------------------------------------------
# 节拍对齐阈值（毫秒）
STRONG_SYNC_THRESHOLD_MS = 50.0
WEAK_SYNC_THRESHOLD_MS = 100.0

# 默认采样率
DEFAULT_SAMPLE_RATE = 44100

# 段落标签候选（按出现顺序循环使用）
SECTION_LABELS = ["intro", "verse", "chorus", "bridge", "drop", "outro"]


# -----------------------------------------------------------------------------
# 数据类
# -----------------------------------------------------------------------------
@dataclass
class SyncPoint:
    """音画同步点"""
    video_time: float
    beat_time: float
    confidence: float
    deviation_ms: float


@dataclass
class RhythmEvent:
    """节奏事件：视频事件与节拍的对齐结果"""
    time: float
    event_type: str            # transition / speed_change / effect_change / scene
    on_beat: bool
    beat_strength: float
    deviation_ms: float
    sync_level: str            # strong / weak / none
    source_detail: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BeatDrivenEffect:
    """音频驱动的 AE 效果推断"""
    effect_type: str           # beat_bounce / bass_glow / high_flash / energy_blur
    audio_source: str          # beat / bass / high / energy
    trigger_times: List[float]
    intensity_curve: List[float]
    ae_params: Dict[str, Any]
    confidence: float


# -----------------------------------------------------------------------------
# 主类
# -----------------------------------------------------------------------------
class AudioSyncAnalyzer:
    """音视频同步分析器：识别节拍驱动的效果与音画同步关系。"""

    def __init__(
        self,
        strong_sync_ms: float = STRONG_SYNC_THRESHOLD_MS,
        weak_sync_ms: float = WEAK_SYNC_THRESHOLD_MS,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
    ) -> None:
        """
        初始化同步分析器。

        :param strong_sync_ms: 强同步偏差阈值（毫秒）
        :param weak_sync_ms:   弱同步偏差阈值（毫秒）
        :param sample_rate:    音频采样率
        """
        self.strong_sync_ms = strong_sync_ms
        self.weak_sync_ms = weak_sync_ms
        self.sample_rate = sample_rate

        # 内部分析器实例（懒加载）
        self._audio_analyzer = None
        self._librosa_analyzer = None
        self._video_analyzer = None
        self._ffmpeg_toolkit = None

        logger.debug(
            f"AudioSyncAnalyzer 初始化完成 "
            f"(strong={strong_sync_ms}ms, weak={weak_sync_ms}ms)"
        )

    # ------------------------------------------------------------------
    # 懒加载内部分析器
    # ------------------------------------------------------------------
    def _get_ffmpeg_toolkit(self):
        if self._ffmpeg_toolkit is None and _ffmpeg_toolkit_mod is not None:
            try:
                self._ffmpeg_toolkit = _ffmpeg_toolkit_mod.FFmpegToolkit()
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"FFmpegToolkit 初始化失败: {exc}")
        return self._ffmpeg_toolkit

    @staticmethod
    def _resolve_ffmpeg_path() -> str:
        """解析 ffmpeg 可执行文件路径，避免误用精简版。

        优先级：
            1. 项目硬约束路径 C:\\ffmpeg\\bin\\ffmpeg.exe（essentials_build，含音频解码器）
            2. 环境变量 AEKV_FFMPEG_PATH / FFMPEG_PATH
            3. puppet-automation settings.py 中的 ffmpeg_path 配置
            4. PATH 中的 ffmpeg（最后兜底，可能是精简版）

        Returns:
            ffmpeg 可执行文件的绝对路径
        """
        # 1. 项目硬约束路径
        candidate = Path(r"C:\ffmpeg\bin\ffmpeg.exe")
        if candidate.exists():
            return str(candidate)

        # 2. 环境变量
        env_path = os.environ.get("AEKV_FFMPEG_PATH") or os.environ.get("FFMPEG_PATH")
        if env_path and Path(env_path).exists():
            return env_path

        # 3. settings.py 中的配置
        try:
            puppet_root = _PROJECT_ROOT / "puppet-automation"
            if str(puppet_root) not in sys.path:
                sys.path.insert(0, str(puppet_root))
            from src.config.settings import settings  # type: ignore
            settings_ff = getattr(settings, "ffmpeg_path", None) or getattr(settings, "ffmpeg", None)
            if settings_ff and Path(str(settings_ff)).exists():
                return str(settings_ff)
        except Exception:
            pass

        # 4. 兜底：PATH 中的 ffmpeg（可能是精简版，但仍是最后保障）
        import shutil
        return shutil.which("ffmpeg") or "ffmpeg"

    def _get_audio_analyzer(self):
        """优先 audio-analyzer.py，降级到 librosa 版本。"""
        if self._audio_analyzer is None and _audio_analyzer_mod is not None:
            try:
                self._audio_analyzer = _audio_analyzer_mod.AudioAnalyzer()
                logger.debug("使用 AudioAnalyzer (audio-analyzer.py)")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"AudioAnalyzer 初始化失败: {exc}")
                self._audio_analyzer = None
        return self._audio_analyzer

    def _get_librosa_analyzer(self):
        if self._librosa_analyzer is None and _audio_analyzer_librosa_mod is not None:
            try:
                self._librosa_analyzer = (
                    _audio_analyzer_librosa_mod.LibrosaAudioAnalyzer()
                )
                logger.debug("使用 LibrosaAudioAnalyzer (audio_analyzer_librosa.py)")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"LibrosaAudioAnalyzer 初始化失败: {exc}")
                self._librosa_analyzer = None
        return self._librosa_analyzer

    def _get_video_analyzer(self):
        if self._video_analyzer is None and _video_effect_analyzer_mod is not None:
            try:
                self._video_analyzer = _video_effect_analyzer_mod.VideoEffectAnalyzer()
                logger.debug("使用 VideoEffectAnalyzer (video-effect-analyzer.py)")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"VideoEffectAnalyzer 初始化失败: {exc}")
                self._video_analyzer = None
        return self._video_analyzer

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------
    async def analyze_sync(
        self,
        video_path: str,
        audio_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        分析视频与音频的同步关系（主入口，异步）。

        :param video_path: 视频文件路径
        :param audio_path: 音频文件路径（None 时从视频提取）
        :return: 完整同步分析结果字典
        """
        video_p = Path(video_path)
        if not video_p.exists():
            logger.error(f"视频文件不存在: {video_path}")
            return {"success": False, "error": f"视频文件不存在: {video_path}"}

        logger.info(f"开始音视频同步分析: video={video_p.name}, audio={audio_path}")

        # 1. 获取音频路径（必要时提取）
        if audio_path is None:
            try:
                audio_path = await self.extract_audio_from_video_async(video_path)
            except Exception as exc:  # noqa: BLE001
                logger.error(f"从视频提取音频失败: {exc}")
                return {"success": False, "error": f"音频提取失败: {exc}"}

        # 2. 分析音频特征
        audio_features = await self.analyze_audio_features_async(audio_path)
        if not audio_features.get("success", False):
            logger.error(f"音频分析失败: {audio_features.get('error')}")
            return {"success": False, "error": audio_features.get("error", "音频分析失败")}

        beats: List[float] = audio_features.get("beat_times", [])
        energy_curve: List[Dict[str, float]] = audio_features.get("energy_curve", [])

        # 3. 分析视频（用于获取事件）
        video_analysis = await self._analyze_video_async(video_path)
        if not video_analysis.get("success", False):
            logger.warning(
                f"视频分析失败，将仅输出音频特征: {video_analysis.get('error')}"
            )
            video_analysis = {"transitions": [], "motion_analysis": {}, "scenes": []}

        # 4. 节奏事件检测
        rhythm_events = await asyncio.to_thread(
            self.detect_rhythm_events, video_analysis, beats
        )

        # 5. 同步点提取
        sync_points = self._build_sync_points(rhythm_events, beats)

        # 6. 节拍驱动效果推断
        beat_driven_effects = await asyncio.to_thread(
            self.infer_beat_driven_effects, rhythm_events, energy_curve
        )

        # 7. 节拍同步关键帧
        sync_keyframes = await asyncio.to_thread(
            self.build_sync_keyframes, beats, energy_curve
        )

        # 8. 音频响应表达式
        audio_reactive_expressions = await asyncio.to_thread(
            self.generate_audio_reactive_expressions, beats, energy_curve
        )

        # 9. 综合同步分数
        sync_score = self._compute_sync_score(rhythm_events, beats, energy_curve)

        # 10. 段落对齐
        section_mapping = self._match_sections(
            video_analysis.get("scenes", []),
            audio_features.get("segments", []),
        )

        result: Dict[str, Any] = {
            "success": True,
            "audio_features": {
                "bpm": audio_features.get("bpm", 0.0),
                "mood": audio_features.get("mood", ""),
                "genre": audio_features.get("genre", ""),
                "key": audio_features.get("key", ""),
                "beat_count": len(beats),
                "duration": audio_features.get("duration", 0.0),
                "energy": audio_features.get("energy", 0.0),
                "segments": audio_features.get("segments", []),
            },
            "beats": beats,
            "rhythm_events": [self._rhythm_event_to_dict(e) for e in rhythm_events],
            "sync_points": [self._sync_point_to_dict(p) for p in sync_points],
            "beat_driven_effects": [
                self._beat_driven_effect_to_dict(e) for e in beat_driven_effects
            ],
            "sync_keyframes": sync_keyframes,
            "audio_reactive_expressions": audio_reactive_expressions,
            "section_mapping": section_mapping,
            "sync_score": round(sync_score, 3),
        }

        logger.info(
            f"同步分析完成: beats={len(beats)}, rhythm_events={len(rhythm_events)}, "
            f"sync_points={len(sync_points)}, score={sync_score:.3f}"
        )
        return result

    # ------------------------------------------------------------------
    # 1. 音频提取
    # ------------------------------------------------------------------
    async def extract_audio_from_video_async(self, video_path: str) -> str:
        """异步包装：从视频提取音频。"""
        return await asyncio.to_thread(self.extract_audio_from_video, video_path)

    def extract_audio_from_video(self, video_path: str) -> str:
        """
        用 ffmpeg 从视频提取音频到临时文件。

        :param video_path: 视频文件路径
        :return: 临时音频文件路径（.mp3）
        """
        video_p = Path(video_path)
        if not video_p.exists():
            raise FileNotFoundError(f"视频文件不存在: {video_path}")

        # 优先使用 FFmpegToolkit
        toolkit = self._get_ffmpeg_toolkit()
        if toolkit is not None:
            tmp_dir = Path(tempfile.gettempdir())
            out_path = tmp_dir / f"vrs_audio_{video_p.stem}_{os.getpid()}.mp3"
            result = toolkit.extract_audio(
                input_file=str(video_p),
                output_file=str(out_path),
                format="mp3",
            )
            if result.get("success") and out_path.exists():
                logger.debug(f"FFmpegToolkit 提取音频成功: {out_path}")
                return str(out_path)
            logger.warning(
                f"FFmpegToolkit 提取失败: {result.get('error')}，回退到裸 ffmpeg"
            )

        # 裸 ffmpeg 兜底
        tmp_dir = Path(tempfile.gettempdir())
        out_path = tmp_dir / f"vrs_audio_{video_p.stem}_{os.getpid()}.mp3"
        import subprocess

        # 解析 ffmpeg 可执行文件路径：
        #   1. 项目硬约束路径 C:\ffmpeg\bin\ffmpeg.exe
        #   2. settings.py / .env 中的 FFmpeg 路径
        #   3. PATH 中的 ffmpeg（最后兜底）
        # 必须避免误用 TRAE SOLO CN / FormatFactory 自带的精简版 ffmpeg
        # （其编译配置为 --disable-everything，缺少音频解码器）。
        ffmpeg_bin = self._resolve_ffmpeg_path()
        cmd = [
            ffmpeg_bin, "-y", "-i", str(video_p),
            "-vn", "-acodec", "libmp3lame", "-b:a", "192k",
            str(out_path),
        ]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120,
                encoding="utf-8", errors="replace",
            )
            if proc.returncode == 0 and out_path.exists():
                logger.debug(f"裸 ffmpeg 提取音频成功: {out_path}")
                return str(out_path)
            raise RuntimeError(
                f"ffmpeg 失败 (code={proc.returncode}): {proc.stderr[:200]}"
            )
        except FileNotFoundError:
            raise RuntimeError("ffmpeg 未安装或不在 PATH 中")

    # ------------------------------------------------------------------
    # 2. 音频特征分析
    # ------------------------------------------------------------------
    async def analyze_audio_features_async(self, audio_path: str) -> Dict[str, Any]:
        """异步包装：分析音频特征。"""
        return await asyncio.to_thread(self.analyze_audio_features, audio_path)

    def analyze_audio_features(self, audio_path: str) -> Dict[str, Any]:
        """
        分析音频特征，调用现有 AudioAnalyzer 或 LibrosaAudioAnalyzer。

        :param audio_path: 音频文件路径
        :return: 包含 bpm/beat_times/energy_curve/mood/genre/key/segments 的字典
        """
        audio_p = Path(audio_path)
        if not audio_p.exists():
            return {"success": False, "error": f"音频文件不存在: {audio_path}"}

        # 路径 1：AudioAnalyzer
        analyzer = self._get_audio_analyzer()
        if analyzer is not None:
            try:
                raw = analyzer.analyze_audio(str(audio_p))
                if raw.get("success"):
                    return self._normalize_audio_result(raw, audio_p, source="audio_analyzer")
                logger.warning(f"AudioAnalyzer 返回失败: {raw.get('error')}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"AudioAnalyzer 异常: {exc}")

        # 路径 2：LibrosaAudioAnalyzer 降级
        librosa_analyzer = self._get_librosa_analyzer()
        if librosa_analyzer is not None:
            try:
                raw = librosa_analyzer.analyze_audio(str(audio_p))
                if isinstance(raw, dict) and raw.get("success", True):
                    return self._normalize_audio_result(raw, audio_p, source="librosa")
                logger.warning(f"LibrosaAudioAnalyzer 返回失败: {raw}")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"LibrosaAudioAnalyzer 异常: {exc}")

        # 路径 3：直连 librosa（无依赖封装）
        if _LIBROSA_AVAILABLE:
            try:
                return self._analyze_audio_librosa_direct(audio_p)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"直连 librosa 分析失败: {exc}")

        return {
            "success": False,
            "error": "无可用音频分析器（AudioAnalyzer / LibrosaAudioAnalyzer / librosa 均失败）",
        }

    def _normalize_audio_result(
        self, raw: Dict[str, Any], audio_p: Path, source: str
    ) -> Dict[str, Any]:
        """将不同来源的音频分析结果归一化为统一格式。"""
        features = raw.get("features", raw)

        # beat_times 可能在顶层或 features 中
        beat_times: List[float] = (
            raw.get("beat_times") or features.get("beats") or features.get("beat_times") or []
        )
        beat_times = [round(float(t), 4) for t in beat_times]

        # energy_curve 统一为 [{time, value}, ...]
        energy_curve_raw = features.get("energy_curve") or raw.get("energy_curve")
        energy_curve = self._normalize_energy_curve(energy_curve_raw, beat_times)

        # segments 归一化
        segments_raw = (
            features.get("segments") or raw.get("segments") or []
        )
        segments = self._normalize_segments(segments_raw)

        bpm = float(features.get("bpm") or features.get("tempo") or 0.0)
        duration = float(features.get("duration") or 0.0)

        logger.debug(
            f"音频分析归一化 (source={source}): bpm={bpm}, beats={len(beat_times)}, "
            f"segments={len(segments)}, energy_pts={len(energy_curve)}"
        )

        return {
            "success": True,
            "source": source,
            "bpm": bpm,
            "tempo": bpm,
            "key": features.get("key", ""),
            "mode": features.get("mode", ""),
            "duration": duration,
            "energy": float(features.get("energy", 0.0)),
            "loudness": float(features.get("loudness", 0.0)),
            "mood": features.get("mood", ""),
            "mood_score": float(features.get("mood_score", 0.0)),
            "genre": features.get("genre", ""),
            "beat_times": beat_times,
            "energy_curve": energy_curve,
            "segments": segments,
            "downbeats": [round(float(t), 4) for t in (features.get("downbeats") or [])],
        }

    def _normalize_energy_curve(
        self,
        raw: Any,
        beat_times: List[float],
    ) -> List[Dict[str, float]]:
        """将多种 energy_curve 格式归一化为 [{time, value}, ...]。"""
        if not raw:
            # 兜底：用节拍时间生成默认能量曲线
            return [{"time": t, "value": 0.5} for t in beat_times]

        # 形式 1: {"times": [...], "values": [...]}
        if isinstance(raw, dict):
            times = raw.get("times") or raw.get("time") or []
            values = raw.get("values") or raw.get("value") or []
            if times and values:
                return [
                    {"time": round(float(t), 4), "value": round(float(v), 4)}
                    for t, v in zip(times, values)
                ]

        # 形式 2: [(time, value), ...]
        if isinstance(raw, list) and raw and isinstance(raw[0], (list, tuple)):
            return [
                {"time": round(float(t), 4), "value": round(float(v), 4)}
                for t, v in raw
            ]

        # 形式 3: [{time, value}, ...]
        if isinstance(raw, list) and raw and isinstance(raw[0], dict):
            return [
                {
                    "time": round(float(p.get("time", p.get("t", 0.0))), 4),
                    "value": round(float(p.get("value", p.get("v", 0.0))), 4),
                }
                for p in raw
            ]

        # 形式 4: 纯数值数组 → 用节拍时间配对
        if isinstance(raw, list) and raw and isinstance(raw[0], (int, float)):
            times = beat_times if len(beat_times) == len(raw) else (
                [i * 0.5 for i in range(len(raw))]
            )
            return [
                {"time": round(float(t), 4), "value": round(float(v), 4)}
                for t, v in zip(times, raw)
            ]

        return [{"time": t, "value": 0.5} for t in beat_times]

    def _normalize_segments(self, raw: Any) -> List[Dict[str, Any]]:
        """归一化段落列表为 [{start, end, label, energy}]。"""
        if not raw:
            return []
        out: List[Dict[str, Any]] = []
        for i, seg in enumerate(raw):
            if isinstance(seg, dict):
                start = float(seg.get("start", seg.get("start_time", 0.0)))
                end = float(seg.get("end", seg.get("end_time", seg.get("duration", 0.0))))
                if end < start:
                    end = start + 1.0
                label = seg.get("label") or seg.get("type") or SECTION_LABELS[i % len(SECTION_LABELS)]
                energy = float(seg.get("energy", seg.get("intensity", 0.5)))
                out.append({
                    "start": round(start, 3),
                    "end": round(end, 3),
                    "label": str(label),
                    "energy": round(energy, 3),
                })
            elif isinstance(seg, (list, tuple)) and len(seg) >= 2:
                out.append({
                    "start": round(float(seg[0]), 3),
                    "end": round(float(seg[1]), 3),
                    "label": SECTION_LABELS[i % len(SECTION_LABELS)],
                    "energy": 0.5,
                })
        return out

    def _analyze_audio_librosa_direct(self, audio_p: Path) -> Dict[str, Any]:
        """直连 librosa 分析（无封装层时的最后兜底）。"""
        if not _LIBROSA_AVAILABLE or not _NUMPY_AVAILABLE:
            return {"success": False, "error": "librosa/numpy 未安装"}

        y, sr = librosa.load(str(audio_p), sr=self.sample_rate)
        duration = float(librosa.get_duration(y=y, sr=sr))

        # librosa 0.10+ 返回 tempo 为 0-d 或 1-d numpy 数组，需兼容
        tempo_raw, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        if hasattr(tempo_raw, "__len__") and len(tempo_raw) > 0:
            tempo = float(tempo_raw[0]) if len(tempo_raw) > 0 else 0.0
        elif hasattr(tempo_raw, "item"):
            tempo = float(tempo_raw.item())
        else:
            tempo = float(tempo_raw)

        beat_times = [
            round(float(t), 4)
            for t in librosa.frames_to_time(beat_frames, sr=sr)
        ]
        rms = librosa.feature.rms(y=y)
        # rms[0] 是 1-D 数组，对应每个帧的能量
        rms_array = rms[0] if rms.ndim > 1 else rms
        frame_indices = np.arange(rms_array.shape[0])
        rms_times = librosa.frames_to_time(frame_indices, sr=sr)
        energy_curve = [
            {"time": round(float(t), 4), "value": round(float(v), 4)}
            for t, v in zip(rms_times, rms_array)
        ]

        # 简化情绪推断
        energy = float(rms.mean())
        if tempo > 130 and energy > 0.05:
            mood, genre = "epic", "electronic"
        elif tempo < 90:
            mood, genre = "calm", "ambient"
        else:
            mood, genre = "happy", "pop"

        # 段落估算（按 4 个均分段）
        segments: List[Dict[str, Any]] = []
        if duration > 0:
            seg_count = 4
            seg_len = duration / seg_count
            labels = ["intro", "verse", "chorus", "outro"]
            for i in range(seg_count):
                segments.append({
                    "start": round(i * seg_len, 3),
                    "end": round((i + 1) * seg_len, 3),
                    "label": labels[i],
                    "energy": round(energy, 3),
                })

        return {
            "success": True,
            "source": "librosa_direct",
            "bpm": float(tempo),
            "tempo": float(tempo),
            "key": "Unknown",
            "mode": "unknown",
            "duration": duration,
            "energy": energy,
            "mood": mood,
            "genre": genre,
            "beat_times": beat_times,
            "energy_curve": energy_curve,
            "segments": segments,
            "downbeats": [],
        }

    # ------------------------------------------------------------------
    # 3. 视频分析（内部）
    # ------------------------------------------------------------------
    async def _analyze_video_async(self, video_path: str) -> Dict[str, Any]:
        """异步包装：调用 VideoEffectAnalyzer。"""
        return await asyncio.to_thread(self._analyze_video, video_path)

    def _analyze_video(self, video_path: str) -> Dict[str, Any]:
        """调用 VideoEffectAnalyzer 获取视频事件。"""
        analyzer = self._get_video_analyzer()
        if analyzer is None:
            return {
                "success": False,
                "error": "VideoEffectAnalyzer 不可用",
                "transitions": [],
                "motion_analysis": {},
                "scenes": [],
            }
        try:
            result = analyzer.analyze_video(video_path, detail_level="standard")
            if not result.get("success", False) and "transitions" not in result:
                return {
                    "success": False,
                    "error": result.get("error", "未知错误"),
                    "transitions": [],
                    "motion_analysis": {},
                    "scenes": [],
                }
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"VideoEffectAnalyzer 异常: {exc}")
            return {
                "success": False,
                "error": str(exc),
                "transitions": [],
                "motion_analysis": {},
                "scenes": [],
            }

    # ------------------------------------------------------------------
    # 4. 节奏事件检测
    # ------------------------------------------------------------------
    def detect_rhythm_events(
        self,
        analysis_result: Dict[str, Any],
        beats: List[float],
    ) -> List[RhythmEvent]:
        """
        将视频事件（转场/速度变化/效果变化）与音频节拍对齐。

        :param analysis_result: VideoEffectAnalyzer 输出
        :param beats: 节拍时间列表（秒）
        :return: RhythmEvent 列表
        """
        if not beats:
            logger.warning("节拍列表为空，无法检测节奏事件")
            return []

        # 收集所有视频事件
        video_events = self._collect_video_events(analysis_result)
        logger.debug(f"从视频分析中提取 {len(video_events)} 个事件")

        rhythm_events: List[RhythmEvent] = []
        for ev in video_events:
            time_s = ev["time"]
            event_type = ev["type"]

            # 找最近节拍
            nearest_beat, idx = self._find_nearest_beat(time_s, beats)
            deviation_ms = abs(time_s - nearest_beat) * 1000.0

            # 同步等级
            if deviation_ms < self.strong_sync_ms:
                sync_level = "strong"
                on_beat = True
            elif deviation_ms < self.weak_sync_ms:
                sync_level = "weak"
                on_beat = True
            else:
                sync_level = "none"
                on_beat = False

            # 节拍强度估算（基于在节拍序列中的位置：强拍优先）
            beat_strength = self._estimate_beat_strength(idx, beats)

            rhythm_events.append(RhythmEvent(
                time=round(time_s, 4),
                event_type=event_type,
                on_beat=on_beat,
                beat_strength=round(beat_strength, 3),
                deviation_ms=round(deviation_ms, 2),
                sync_level=sync_level,
                source_detail={
                    "nearest_beat": round(nearest_beat, 4),
                    "beat_index": idx,
                    "transition_type": ev.get("transition_type", ""),
                    "confidence": ev.get("confidence", 0.0),
                },
            ))

        # 按时间排序
        rhythm_events.sort(key=lambda e: e.time)
        return rhythm_events

    def _collect_video_events(self, analysis_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从视频分析结果中提取所有时间事件（转场 + 速度变化 + 效果变化 + 场景切换）。"""
        events: List[Dict[str, Any]] = []

        # 转场
        for t in analysis_result.get("transitions", []) or []:
            time_s = t.get("time_sec") or t.get("time") or 0.0
            events.append({
                "time": float(time_s),
                "type": "transition",
                "transition_type": t.get("type", "unknown"),
                "confidence": float(t.get("confidence", 0.0)),
            })

        # 速度变化
        motion = analysis_result.get("motion_analysis", {}) or {}
        for sc in motion.get("speed_changes", []) or []:
            time_s = sc.get("time_sec") or sc.get("time") or 0.0
            events.append({
                "time": float(time_s),
                "type": "speed_change",
                "transition_type": sc.get("type", "speed"),
                "confidence": float(sc.get("confidence", 0.5)),
            })

        # 视觉效果
        vfx = analysis_result.get("visual_effects", {}) or {}
        for eff in vfx.get("detected_effects", []) or []:
            time_s = eff.get("time_sec") or eff.get("time") or 0.0
            events.append({
                "time": float(time_s),
                "type": "effect_change",
                "transition_type": eff.get("name", "effect"),
                "confidence": float(eff.get("confidence", 0.5)),
            })

        # 场景切换（每个场景的起始视为事件）
        for sc in analysis_result.get("scenes", []) or []:
            time_s = sc.get("start_time") or sc.get("start") or 0.0
            events.append({
                "time": float(time_s),
                "type": "scene",
                "transition_type": f"scene_{sc.get('scene_idx', 0)}",
                "confidence": 0.5,
            })

        return events

    def _find_nearest_beat(
        self, time_s: float, beats: List[float]
    ) -> Tuple[float, int]:
        """找到距离 time_s 最近的节拍及其索引。"""
        if not beats:
            return 0.0, 0
        # 简单线性查找（节拍数量通常 < 1000，性能足够）
        best_idx = 0
        best_diff = abs(time_s - beats[0])
        for i, b in enumerate(beats[1:], start=1):
            diff = abs(time_s - b)
            if diff < best_diff:
                best_diff = diff
                best_idx = i
        return beats[best_idx], best_idx

    def _estimate_beat_strength(self, beat_idx: int, beats: List[float]) -> float:
        """
        估算节拍强度：基于 4/4 拍结构，强拍 (idx % 4 == 0) 强度最高。
        """
        if not beats:
            return 0.5
        # 4/4 拍：第 1 拍强、第 3 拍次强
        position = beat_idx % 4
        if position == 0:
            return 1.0
        elif position == 2:
            return 0.75
        elif position == 1 or position == 3:
            return 0.5
        return 0.5

    # ------------------------------------------------------------------
    # 5. 同步点提取
    # ------------------------------------------------------------------
    def _build_sync_points(
        self,
        rhythm_events: List[RhythmEvent],
        beats: List[float],
    ) -> List[SyncPoint]:
        """从节奏事件中提取同步点（仅保留 on_beat 的事件）。"""
        sync_points: List[SyncPoint] = []
        for ev in rhythm_events:
            if not ev.on_beat:
                continue
            confidence = 1.0 - (ev.deviation_ms / max(self.weak_sync_ms * 2, 1.0))
            confidence = max(0.0, min(1.0, confidence))
            sync_points.append(SyncPoint(
                video_time=ev.time,
                beat_time=ev.source_detail.get("nearest_beat", 0.0),
                confidence=round(confidence, 3),
                deviation_ms=ev.deviation_ms,
            ))
        return sync_points

    # ------------------------------------------------------------------
    # 6. 节拍驱动效果推断
    # ------------------------------------------------------------------
    def infer_beat_driven_effects(
        self,
        rhythm_events: List[RhythmEvent],
        energy_curve: List[Dict[str, float]],
    ) -> List[BeatDrivenEffect]:
        """
        推断音频驱动的效果：
            - beat_bounce:    节拍上的 Scale 弹跳
            - bass_glow:      低频驱动的发光强度
            - high_flash:     高频驱动的闪烁
            - energy_blur:    能量峰值驱动的模糊
        """
        effects: List[BeatDrivenEffect] = []

        # 提取踩拍事件
        on_beat_events = [e for e in rhythm_events if e.on_beat]
        if not on_beat_events and not energy_curve:
            return effects

        # 1. beat_bounce：所有踩拍事件触发 Scale 弹跳
        beat_triggers = sorted({e.source_detail.get("nearest_beat", e.time) for e in on_beat_events})
        if beat_triggers:
            bounce_curve = self._align_intensity_to_triggers(beat_triggers, on_beat_events)
            # 为每个触发时间生成 3 个关键帧（1.0 → 1.05 → 1.0 弹跳）
            bounce_keyframes: List[Dict[str, Any]] = []
            for t, v in zip(beat_triggers, bounce_curve):
                peak = round(105.0 * (0.8 + 0.2 * v), 2)
                bounce_keyframes.append({"time": round(t, 4), "value": [100, 100], "easing": "ease_out"})
                bounce_keyframes.append({"time": round(t + 0.05, 4), "value": [peak, peak], "easing": "ease_in_out"})
                bounce_keyframes.append({"time": round(t + 0.15, 4), "value": [100, 100], "easing": "ease_out"})
            effects.append(BeatDrivenEffect(
                effect_type="beat_bounce",
                audio_source="beat",
                trigger_times=[round(t, 4) for t in beat_triggers],
                intensity_curve=[round(v, 3) for v in bounce_curve],
                ae_params={
                    "property": "scale",
                    "keyframes": bounce_keyframes,
                    "amplitude": 5.0,
                },
                confidence=round(
                    min(1.0, len(on_beat_events) / max(len(beat_triggers), 1)) * 0.9, 3
                ),
            ))

        # 2. bass_glow：能量曲线峰值 → 发光强度
        if energy_curve:
            bass_triggers, bass_intensity = self._find_energy_peaks(
                energy_curve, threshold_percent=0.7, min_interval=0.3
            )
            if bass_triggers:
                glow_keyframes: List[Dict[str, Any]] = []
                for t, v in zip(bass_triggers, bass_intensity):
                    glow_keyframes.append({"time": round(t, 4), "value": round(0.3 + v * 0.7, 3), "easing": "ease_out"})
                    glow_keyframes.append({"time": round(t + 0.2, 4), "value": 0.3, "easing": "ease_in"})
                effects.append(BeatDrivenEffect(
                    effect_type="bass_glow",
                    audio_source="bass",
                    trigger_times=[round(t, 4) for t in bass_triggers],
                    intensity_curve=[round(v, 3) for v in bass_intensity],
                    ae_params={
                        "property": "glow_intensity",
                        "effect": "Glow",
                        "keyframes": glow_keyframes,
                        "glow_radius": 20,
                        "glow_threshold": 50,
                    },
                    confidence=0.75,
                ))

        # 3. high_flash：高频快速变化 → 闪烁
        if energy_curve:
            flash_triggers, flash_intensity = self._find_flash_points(energy_curve)
            if flash_triggers:
                flash_keyframes: List[Dict[str, Any]] = []
                for t in flash_triggers:
                    flash_keyframes.append({"time": round(t, 4), "value": 100, "easing": "linear"})
                    flash_keyframes.append({"time": round(t + 0.05, 4), "value": 0, "easing": "linear"})
                    flash_keyframes.append({"time": round(t + 0.1, 4), "value": 100, "easing": "linear"})
                effects.append(BeatDrivenEffect(
                    effect_type="high_flash",
                    audio_source="high",
                    trigger_times=[round(t, 4) for t in flash_triggers],
                    intensity_curve=[round(v, 3) for v in flash_intensity],
                    ae_params={
                        "property": "opacity",
                        "keyframes": flash_keyframes,
                        "frequency_hz": 10,
                    },
                    confidence=0.65,
                ))

        # 4. energy_blur：能量峰值 → 模糊
        if energy_curve:
            blur_triggers, blur_intensity = self._find_energy_peaks(
                energy_curve, threshold_percent=0.85, min_interval=0.5
            )
            if blur_triggers:
                blur_keyframes: List[Dict[str, Any]] = []
                for t, v in zip(blur_triggers, blur_intensity):
                    blur_keyframes.append({"time": round(t, 4), "value": round(v * 30, 2), "easing": "ease_out"})
                    blur_keyframes.append({"time": round(t + 0.3, 4), "value": 0, "easing": "ease_in"})
                effects.append(BeatDrivenEffect(
                    effect_type="energy_blur",
                    audio_source="energy",
                    trigger_times=[round(t, 4) for t in blur_triggers],
                    intensity_curve=[round(v, 3) for v in blur_intensity],
                    ae_params={
                        "property": "blur_radius",
                        "effect": "Gaussian Blur",
                        "keyframes": blur_keyframes,
                        "max_blur": 30,
                    },
                    confidence=0.7,
                ))

        return effects

    def _align_intensity_to_triggers(
        self, triggers: List[float], events: List[RhythmEvent]
    ) -> List[float]:
        """将事件强度对齐到触发时间列表。"""
        intensity_map: Dict[float, float] = {}
        for e in events:
            t = e.source_detail.get("nearest_beat", e.time)
            intensity_map[round(t, 4)] = max(
                intensity_map.get(round(t, 4), 0.0), e.beat_strength
            )
        return [intensity_map.get(round(t, 4), 0.5) for t in triggers]

    def _find_energy_peaks(
        self,
        energy_curve: List[Dict[str, float]],
        threshold_percent: float = 0.7,
        min_interval: float = 0.3,
    ) -> Tuple[List[float], List[float]]:
        """在能量曲线中寻找峰值（用于 bass_glow / energy_blur）。"""
        if not energy_curve:
            return [], []

        values = [p.get("value", 0.0) for p in energy_curve]
        max_v = max(values) if values else 0.0
        threshold = max_v * threshold_percent

        triggers: List[float] = []
        intensities: List[float] = []
        last_trigger = -1.0

        for i, point in enumerate(energy_curve):
            v = point.get("value", 0.0)
            t = point.get("time", 0.0)
            # 局部最大且超过阈值
            is_local_max = True
            if i > 0 and energy_curve[i - 1].get("value", 0.0) >= v:
                is_local_max = False
            if i < len(energy_curve) - 1 and energy_curve[i + 1].get("value", 0.0) >= v:
                is_local_max = False

            if is_local_max and v >= threshold and (t - last_trigger) >= min_interval:
                triggers.append(t)
                intensities.append(min(1.0, v / max_v if max_v > 0 else 0.5))
                last_trigger = t

        return triggers, intensities

    def _find_flash_points(
        self,
        energy_curve: List[Dict[str, float]],
    ) -> Tuple[List[float], List[float]]:
        """寻找能量快速跳变点（用于 high_flash）。"""
        if len(energy_curve) < 3:
            return [], []

        triggers: List[float] = []
        intensities: List[float] = []
        values = [p.get("value", 0.0) for p in energy_curve]
        max_v = max(values) if values else 0.0

        for i in range(1, len(energy_curve) - 1):
            prev_v = energy_curve[i - 1].get("value", 0.0)
            curr_v = energy_curve[i].get("value", 0.0)
            next_v = energy_curve[i + 1].get("value", 0.0)
            t = energy_curve[i].get("time", 0.0)

            # 尖峰形态：当前远高于前后
            spike = curr_v - max(prev_v, next_v)
            if spike > 0.1 and curr_v > 0.3 * max_v:
                triggers.append(t)
                intensities.append(min(1.0, curr_v / max_v if max_v > 0 else 0.5))

        return triggers, intensities

    # ------------------------------------------------------------------
    # 7. 节拍同步关键帧
    # ------------------------------------------------------------------
    def build_sync_keyframes(
        self,
        beats: List[float],
        energy_curve: List[Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """
        生成节拍同步的关键帧序列：
            - Scale 关键帧（1.0 → 1.05 → 1.0 弹跳）
            - 强拍额外生成发光强度关键帧
        """
        keyframes: List[Dict[str, Any]] = []
        if not beats:
            return keyframes

        # 构建节拍 -> 能量映射
        energy_map = self._build_energy_lookup(energy_curve)

        for i, beat_time in enumerate(beats):
            beat_strength = self._estimate_beat_strength(i, beats)
            energy_val = self._lookup_energy(energy_map, beat_time)
            # 弹跳幅度按节拍强度调整
            amplitude = 0.05 * beat_strength + 0.02 * energy_val
            # 保留 3 位小数
            scale_peak = round(1.0 + amplitude, 3)

            # Scale 弹跳三关键帧
            keyframes.append({
                "property": "scale",
                "time": round(beat_time, 4),
                "value": 1.0,
                "easing": "ease_out",
            })
            keyframes.append({
                "property": "scale",
                "time": round(beat_time + 0.05, 4),
                "value": scale_peak,
                "easing": "ease_in_out",
            })
            keyframes.append({
                "property": "scale",
                "time": round(beat_time + 0.15, 4),
                "value": 1.0,
                "easing": "ease_out",
            })

            # 强拍 (idx % 4 == 0) 添加发光关键帧
            if i % 4 == 0 and energy_val > 0.3:
                glow_peak = round(0.4 + energy_val * 0.6, 3)
                keyframes.append({
                    "property": "glow_intensity",
                    "time": round(beat_time, 4),
                    "value": glow_peak,
                    "easing": "ease_out",
                })
                keyframes.append({
                    "property": "glow_intensity",
                    "time": round(beat_time + 0.2, 4),
                    "value": 0.3,
                    "easing": "ease_in",
                })

        return keyframes

    def _build_energy_lookup(
        self, energy_curve: List[Dict[str, float]]
    ) -> List[Tuple[float, float]]:
        """构建 (time, value) 排序列表用于快速查找。"""
        if not energy_curve:
            return []
        return sorted(
            [(p.get("time", 0.0), p.get("value", 0.0)) for p in energy_curve],
            key=lambda x: x[0],
        )

    def _lookup_energy(
        self,
        energy_map: List[Tuple[float, float]],
        time_s: float,
    ) -> float:
        """在能量映射中查找指定时间的能量值（线性插值）。"""
        if not energy_map:
            return 0.5
        # 二分查找
        lo, hi = 0, len(energy_map) - 1
        if time_s <= energy_map[0][0]:
            return energy_map[0][1]
        if time_s >= energy_map[-1][0]:
            return energy_map[-1][1]
        while lo < hi - 1:
            mid = (lo + hi) // 2
            if energy_map[mid][0] < time_s:
                lo = mid
            else:
                hi = mid
        t0, v0 = energy_map[lo]
        t1, v1 = energy_map[hi]
        if t1 == t0:
            return v0
        ratio = (time_s - t0) / (t1 - t0)
        return v0 + (v1 - v0) * ratio

    # ------------------------------------------------------------------
    # 8. 音频响应表达式
    # ------------------------------------------------------------------
    def generate_audio_reactive_expressions(
        self,
        beats: List[float],
        energy_curve: List[Dict[str, float]],
    ) -> List[Dict[str, Any]]:
        """
        生成音频驱动 AE 表达式。

        包含：
            - 基础 wiggle 抖动
            - 低频驱动（音频振幅层滑块）
            - 节拍触发的正弦波缩放
            - 能量驱动的发光
        """
        expressions: List[Dict[str, Any]] = []

        if not beats:
            return expressions

        bpm = self._estimate_bpm_from_beats(beats)
        avg_energy = self._compute_avg_energy(energy_curve)

        # 1. 基础 wiggle 抖动（位置）
        expressions.append({
            "property": "position",
            "expression": "wiggle(2, 5)",
            "description": "基础抖动：2Hz 频率，振幅 5 像素",
        })

        # 2. 低频驱动（缩放）
        expressions.append({
            "property": "scale",
            "expression": (
                'thisComp.layer("音频振幅").effect("双声道")("滑块")*0.1 + [100,100]'
            ),
            "description": "低频驱动缩放：从音频振幅层读取滑块值，乘 0.1 作为偏移",
        })

        # 3. 节拍触发正弦波（缩放）
        if bpm > 0:
            amplitude = 2.0 + avg_energy * 3.0
            expressions.append({
                "property": "scale",
                "expression": (
                    f"[100 + Math.sin(time*2*Math.PI*{bpm}/60)*{amplitude:.2f}, "
                    f"100 + Math.sin(time*2*Math.PI*{bpm}/60)*{amplitude:.2f}]"
                ),
                "description": f"节拍正弦波缩放：BPM={bpm:.0f}，振幅={amplitude:.2f}",
            })

        # 4. 能量驱动发光
        expressions.append({
            "property": "glow_intensity",
            "expression": (
                'linear(thisComp.layer("音频振幅").effect("双声道")("滑块"), '
                "0, 1, 0.3, 1.0)"
            ),
            "description": "能量驱动发光：将音频滑块 0-1 映射到发光强度 0.3-1.0",
        })

        # 5. 节拍触发的不透明度脉冲
        if bpm > 0:
            beat_freq = bpm / 60.0
            expressions.append({
                "property": "opacity",
                "expression": (
                    f"100 + Math.sin(time*2*Math.PI*{beat_freq:.3f})*"
                    f"{10 + avg_energy * 20:.2f}"
                ),
                "description": f"节拍脉冲不透明度：BPM={bpm:.0f}，振幅={10 + avg_energy * 20:.2f}",
            })

        return expressions

    def _estimate_bpm_from_beats(self, beats: List[float]) -> float:
        """根据节拍时间序列估算 BPM。"""
        if len(beats) < 2:
            return 0.0
        intervals = [beats[i + 1] - beats[i] for i in range(len(beats) - 1)]
        intervals = [iv for iv in intervals if 0.1 < iv < 2.0]  # 过滤异常
        if not intervals:
            return 0.0
        avg_interval = sum(intervals) / len(intervals)
        return 60.0 / avg_interval if avg_interval > 0 else 0.0

    def _compute_avg_energy(self, energy_curve: List[Dict[str, float]]) -> float:
        """计算能量曲线的平均值。"""
        if not energy_curve:
            return 0.5
        values = [p.get("value", 0.0) for p in energy_curve]
        return sum(values) / len(values) if values else 0.5

    # ------------------------------------------------------------------
    # 9. 综合同步分数与段落对齐
    # ------------------------------------------------------------------
    def _compute_sync_score(
        self,
        rhythm_events: List[RhythmEvent],
        beats: List[float],
        energy_curve: List[Dict[str, float]],
    ) -> float:
        """
        综合同步分数：
            - 60%：节奏事件踩拍率（强同步 + 弱同步 * 0.5）
            - 40%：节拍密度合理性（节拍数 / 时长是否在合理范围）
        """
        if not rhythm_events:
            # 没有视频事件时，仅基于节拍完整性给分
            return 0.5 if beats else 0.0

        strong_count = sum(1 for e in rhythm_events if e.sync_level == "strong")
        weak_count = sum(1 for e in rhythm_events if e.sync_level == "weak")
        total = len(rhythm_events)

        beat_alignment_score = (
            (strong_count + weak_count * 0.5) / total if total > 0 else 0.0
        )

        # 节拍密度合理性
        density_score = 0.5
        if beats and len(beats) >= 2:
            duration = beats[-1] - beats[0]
            if duration > 0:
                bpm = self._estimate_bpm_from_beats(beats)
                # 60-180 BPM 视为合理
                if 60 <= bpm <= 180:
                    density_score = 1.0
                elif 40 <= bpm <= 200:
                    density_score = 0.7
                else:
                    density_score = 0.3

        score = 0.6 * beat_alignment_score + 0.4 * density_score
        return max(0.0, min(1.0, score))

    def _match_sections(
        self,
        scenes: List[Dict[str, Any]],
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """将视频场景与音频段落对应。"""
        if not scenes or not segments:
            return []

        mapping: List[Dict[str, Any]] = []
        for seg in segments:
            seg_start = seg.get("start", 0.0)
            seg_end = seg.get("end", 0.0)
            seg_label = seg.get("label", "unknown")

            # 找出落在该段落内的场景
            matched_scenes: List[int] = []
            for sc in scenes:
                sc_start = float(sc.get("start_time", sc.get("start", 0.0)))
                if seg_start <= sc_start < seg_end:
                    matched_scenes.append(int(sc.get("scene_idx", 0)))

            mapping.append({
                "section": seg_label,
                "start": seg_start,
                "end": seg_end,
                "scene_indices": matched_scenes,
                "scene_count": len(matched_scenes),
            })

        return mapping

    # ------------------------------------------------------------------
    # 序列化辅助
    # ------------------------------------------------------------------
    def _rhythm_event_to_dict(self, e: RhythmEvent) -> Dict[str, Any]:
        return {
            "time": e.time,
            "event_type": e.event_type,
            "on_beat": e.on_beat,
            "beat_strength": e.beat_strength,
            "deviation_ms": e.deviation_ms,
            "sync_level": e.sync_level,
            "source_detail": e.source_detail,
        }

    def _sync_point_to_dict(self, p: SyncPoint) -> Dict[str, Any]:
        return {
            "video_time": p.video_time,
            "beat_time": p.beat_time,
            "confidence": p.confidence,
            "deviation_ms": p.deviation_ms,
        }

    def _beat_driven_effect_to_dict(self, e: BeatDrivenEffect) -> Dict[str, Any]:
        return {
            "effect_type": e.effect_type,
            "audio_source": e.audio_source,
            "trigger_times": e.trigger_times,
            "intensity_curve": e.intensity_curve,
            "ae_params": e.ae_params,
            "confidence": e.confidence,
        }


# -----------------------------------------------------------------------------
# CLI 入口
# -----------------------------------------------------------------------------
def _run_test() -> None:
    """运行同步分析测试。"""
    import argparse

    parser = argparse.ArgumentParser(description="VRS 音视频同步分析测试")
    parser.add_argument("--test", action="store_true", help="运行内置测试")
    parser.add_argument("--video", default=str(_OUTPUT_DIR / "test_sample.mp4"),
                        help="视频文件路径")
    parser.add_argument("--audio", default=str(_OUTPUT_DIR / "test_audio.mp3"),
                        help="音频文件路径（不传则从视频提取）")
    parser.add_argument("--output", default=str(_OUTPUT_DIR / "vrs_audio_sync.json"),
                        help="输出 JSON 路径")
    parser.add_argument("--extract", action="store_true",
                        help="强制从视频提取音频（忽略 --audio）")
    args = parser.parse_args()

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    analyzer = AudioSyncAnalyzer()

    audio_path: Optional[str] = None
    if not args.extract and Path(args.audio).exists():
        audio_path = args.audio
        logger.info(f"使用提供的音频: {audio_path}")
    else:
        logger.info("未提供音频或指定 --extract，将从视频提取")

    result = asyncio.run(analyzer.analyze_sync(args.video, audio_path))

    out_path = Path(args.output)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    logger.info(f"分析结果已写入: {out_path}")

    if result.get("success"):
        print("\n========== VRS 音视频同步分析结果 ==========")
        af = result.get("audio_features", {})
        print(f"BPM:        {af.get('bpm', 0):.1f}")
        print(f"情绪:       {af.get('mood', '')}")
        print(f"曲风:       {af.get('genre', '')}")
        print(f"调性:       {af.get('key', '')}")
        print(f"节拍数:     {af.get('beat_count', 0)}")
        print(f"节奏事件:   {len(result.get('rhythm_events', []))}")
        print(f"同步点:     {len(result.get('sync_points', []))}")
        print(f"节拍驱动效果: {len(result.get('beat_driven_effects', []))}")
        print(f"同步关键帧:   {len(result.get('sync_keyframes', []))}")
        print(f"AE 表达式:    {len(result.get('audio_reactive_expressions', []))}")
        print(f"同步分数:   {result.get('sync_score', 0):.3f}")
        print(f"段落映射:   {len(result.get('section_mapping', []))} 段")
        print("============================================\n")
    else:
        print(f"分析失败: {result.get('error')}")
        sys.exit(1)


if __name__ == "__main__":
    _run_test()
