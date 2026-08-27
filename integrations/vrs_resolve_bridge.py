# -*- coding: utf-8 -*-
"""
VRS ↔ Resolve 自动化引擎桥接模块（P0 集成）
==============================================

职责：
    把 VRS 音视频同步分析器（vrs/vrs_audio_sync_analyzer.py 的 AudioSyncAnalyzer）
    的分析结果转换为 resolve_engine（integrations/resolve_engine.py）的可执行剪辑原语，
    并提供一条完整的 VRS 驱动踩拍混剪管线 build_vrs_montage()。

转换映射：
    VRS beats                → 镜头切点（每 beat_group 拍一个镜头，切点严格落拍）
    VRS beat_driven_effects  → FFmpeg 效果滤镜（beat_bounce→zoompan 缩放脉冲、
                               high_flash→白色 overlay 脉冲）
    VRS sync_keyframes       → resolve_engine Keyframe 列表（供 set_keyframe_animation）
    VRS energy_curve         → 闪光峰值触发点

依赖：
    - integrations/resolve_engine.py（ResolveAutomationEngine / Keyframe / TransitionConfig）
    - vrs/vrs_audio_sync_analyzer.py（AudioSyncAnalyzer，异步 analyze_sync）
    - VRS 不可用时自动降级到引擎内置 detect_beats（silencedetect / BPM 网格）

用法：
    python integrations/vrs_resolve_bridge.py --clips C:\\VinlandClips --bgm "D:\\AE-Work\\音频素材库\\BGM\\ae实战音乐.mp3"
"""
from __future__ import annotations

import asyncio
import importlib.util
import math
import os
import shlex
import subprocess
import sys
import uuid
from typing import Any, Dict, List, Optional, Tuple

from loguru import logger

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# -----------------------------------------------------------------------------
# 动态加载（路径含下划线模块名，避免包导入副作用）
# -----------------------------------------------------------------------------
def _load_module(module_name: str, rel_path: str):
    """按相对项目根的路径动态加载模块；失败返回 None。"""
    file_path = os.path.join(_PROJECT_ROOT, rel_path)
    if not os.path.exists(file_path):
        logger.warning(f"模块不存在: {file_path}")
        return None
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"加载模块失败 {rel_path}: {exc}")
        sys.modules.pop(module_name, None)
        return None


_engine_mod = _load_module("_vrs_bridge_resolve_engine", "integrations/resolve_engine.py")
if _engine_mod is not None:
    # vrs 子模块导入 loguru 等依赖时需要 vrs 目录在 sys.path
    vrs_dir = os.path.join(_PROJECT_ROOT, "vrs")
    if vrs_dir not in sys.path:
        sys.path.insert(0, vrs_dir)
    _vrs_mod = _load_module("_vrs_bridge_audio_sync", "vrs/vrs_audio_sync_analyzer.py")
else:
    _vrs_mod = None

if _engine_mod is None:
    raise ImportError("无法加载 integrations/resolve_engine.py，桥接模块不可用")

ResolveAutomationEngine = _engine_mod.ResolveAutomationEngine
ResolveError = _engine_mod.ResolveError
Keyframe = _engine_mod.Keyframe
TransitionConfig = _engine_mod.TransitionConfig


# -----------------------------------------------------------------------------
# 桥接器
# -----------------------------------------------------------------------------
class VrsResolveBridge:
    """VRS 分析 → resolve_engine 执行的桥接器。"""

    # beat_bounce 脉冲形状：attack 0.05s 上冲，decay 0.15s 回落
    PULSE_ATTACK = 0.05
    PULSE_DECAY = 0.15
    # zoompan 表达式中单个脉冲约 ~120 字符，Windows 命令行安全上限约束脉冲数
    MAX_PULSES_PER_SEGMENT = 7

    def __init__(self, engine: Optional[Any] = None,
                 use_vrs: bool = True) -> None:
        self.engine = engine or ResolveAutomationEngine()
        self.use_vrs = use_vrs and _vrs_mod is not None
        self._analyzer = None
        self.last_analysis: Dict[str, Any] = {}
        if not self.use_vrs:
            logger.warning("VRS AudioSyncAnalyzer 不可用，降级为引擎内置节拍检测")

    # ------------------------------------------------------------------
    # 1. VRS 分析入口（带降级）
    # ------------------------------------------------------------------
    def _get_analyzer(self):
        if self._analyzer is None and _vrs_mod is not None:
            self._analyzer = _vrs_mod.AudioSyncAnalyzer()
        return self._analyzer

    def analyze(self, audio_path: str,
                video_path: Optional[str] = None) -> Dict[str, Any]:
        """
        分析音频（可选参考视频）得到节拍/能量/踩拍效果。

        Returns:
            {"success", "source"("vrs"|"fallback"), "bpm", "beats",
             "energy_curve", "beat_driven_effects", "sync_keyframes"}
        """
        if self.use_vrs:
            analyzer = self._get_analyzer()
            if analyzer is not None and video_path:
                try:
                    result = asyncio.run(analyzer.analyze_sync(video_path, audio_path))
                    if result.get("success"):
                        self.last_analysis = {
                            "success": True,
                            "source": "vrs",
                            "bpm": result.get("audio_features", {}).get("bpm", 0.0),
                            "beats": result.get("beats", []),
                            # analyze_sync 输出不含原始能量曲线，闪光将跳过
                            "energy_curve": [],
                            "beat_driven_effects": result.get("beat_driven_effects", []),
                            "sync_keyframes": result.get("sync_keyframes", []),
                            "sync_score": result.get("sync_score", 0.0),
                            "raw": result,
                        }
                        logger.info(
                            f"VRS 分析成功: bpm={self.last_analysis['bpm']:.1f}, "
                            f"beats={len(self.last_analysis['beats'])}, "
                            f"score={self.last_analysis['sync_score']}")
                        return self.last_analysis
                    logger.warning(f"VRS analyze_sync 失败: {result.get('error')}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"VRS 分析异常，降级: {exc}")
            elif analyzer is not None:
                # 无参考视频：只做音频特征分析（beat_times + energy_curve）
                try:
                    feat = analyzer.analyze_audio_features(audio_path)
                    if feat.get("success") and feat.get("beat_times"):
                        energy = feat.get("energy_curve", [])
                        effects = analyzer.infer_beat_driven_effects([], energy)
                        keyframes = analyzer.build_sync_keyframes(
                            feat["beat_times"], energy)
                        self.last_analysis = {
                            "success": True,
                            "source": "vrs_audio_only",
                            "bpm": feat.get("bpm", 0.0),
                            "beats": feat["beat_times"],
                            "energy_curve": energy,
                            "beat_driven_effects": [
                                analyzer._beat_driven_effect_to_dict(e) for e in effects],
                            "sync_keyframes": keyframes,
                            "sync_score": 0.0,
                            "raw": feat,
                        }
                        logger.info(
                            f"VRS 纯音频分析成功: bpm={feat.get('bpm', 0):.1f}, "
                            f"beats={len(feat['beat_times'])}")
                        return self.last_analysis
                    logger.warning(f"VRS 音频特征分析失败: {feat.get('error')}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning(f"VRS 纯音频分析异常，降级: {exc}")

        # 降级：引擎内置 silencedetect / BPM 网格
        beats = self.engine.detect_beats(audio_path)
        self.last_analysis = {
            "success": bool(beats),
            "source": "fallback",
            "bpm": 0.0,
            "beats": beats,
            "energy_curve": [],
            "beat_driven_effects": [],
            "sync_keyframes": [],
            "sync_score": 0.0,
        }
        return self.last_analysis

    # ------------------------------------------------------------------
    # 2. VRS 关键帧 → 引擎 Keyframe 转换
    # ------------------------------------------------------------------
    @staticmethod
    def vrs_keyframes_to_engine(sync_keyframes: List[Dict[str, Any]],
                                prop: str = "scale") -> List[Any]:
        """
        将 VRS sync_keyframes（{property,time,value,easing}）转换为
        resolve_engine Keyframe 列表。scale 值(1.0基线)自动转为 zoompan 缩放倍率。
        """
        out = []
        for kf in sync_keyframes:
            if kf.get("property") != prop:
                continue
            value = kf.get("value", 1.0)
            # VRS scale 关键帧 value 是 1.0 基线的比例，直接作 zoom 倍率使用
            out.append(Keyframe(time=float(kf.get("time", 0.0)),
                                value=float(value)))
        return sorted(out, key=lambda k: k.time)

    # ------------------------------------------------------------------
    # 3. 踩拍脉冲表达式（beat_bounce → zoompan z 表达式）
    # ------------------------------------------------------------------
    def build_beat_pulse_expression(self, beats: List[float],
                                    seg_duration: float,
                                    amplitudes: Optional[List[float]] = None,
                                    fps: int = 24,
                                    base_zoom: float = 1.06) -> Optional[str]:
        """
        为单个镜头片段构建踩拍缩放脉冲表达式（zoompan z 用，时间变量 on/fps）。

        Args:
            beats: 片段内部的节拍时间（相对片段起点，秒）
            seg_duration: 片段时长（秒）
            amplitudes: 每拍脉冲幅度（0~1），默认按 4/4 强拍加权
            base_zoom: 基础缩放（>1 留出脉冲上冲空间，避免黑边）

        Returns:
            zoompan z 表达式；无节拍/超脉冲上限时返回 None
        """
        if not beats:
            return None
        pulses = [b for b in beats if 0.0 <= b < seg_duration]
        if not pulses or len(pulses) > self.MAX_PULSES_PER_SEGMENT:
            return None

        if amplitudes is None:
            # 4/4 拍结构：强拍幅度大（与 VRS _estimate_beat_strength 同逻辑）
            amplitudes = []
            for i, _ in enumerate(pulses):
                pos = i % 4
                amplitudes.append(1.0 if pos == 0 else (0.75 if pos == 2 else 0.55))

        T = f"on/{fps}"
        expr = f"{base_zoom:.4f}"
        for t, amp in zip(pulses, amplitudes):
            peak = base_zoom + 0.05 * amp
            t_atk = t + self.PULSE_ATTACK
            t_end = t + self.PULSE_DECAY
            if t_end > seg_duration:
                t_end = seg_duration - 0.001
            if t_atk >= t_end:
                continue
            # 攻击段：base → peak；衰减段：peak → base
            rise = (f"({base_zoom:.4f}+({peak - base_zoom:.4f})*"
                    f"(({T}-{t:.4f})/{self.PULSE_ATTACK:.4f}))")
            fall = (f"({peak:.4f}-({peak - base_zoom:.4f})*"
                    f"(({T}-{t_atk:.4f})/{(t_end - t_atk):.4f}))")
            pulse_expr = f"if(lt({T},{t_atk:.4f}),{rise},{fall})"
            expr = (f"if(lt({T},{t:.4f}),{expr},"
                    f"if(lt({T},{t_end:.4f}),{pulse_expr},{expr}))")
        return expr

    # ------------------------------------------------------------------
    # 4. 能量闪光表达式（high_flash → overlay enable）
    # ------------------------------------------------------------------
    def find_flash_points(self, energy_curve: List[Dict[str, float]],
                          threshold_percent: float = 0.85,
                          min_interval: float = 0.4) -> List[float]:
        """在能量曲线中找高能量尖峰（闪光触发时间，秒）。"""
        if not energy_curve:
            return []
        values = [p.get("value", 0.0) for p in energy_curve]
        max_v = max(values) if values else 0.0
        if max_v <= 0:
            return []
        threshold = max_v * threshold_percent
        points, last = [], -9.0
        for i, pt in enumerate(energy_curve):
            v = pt.get("value", 0.0)
            t = pt.get("time", 0.0)
            prev_v = energy_curve[i - 1].get("value", 0.0) if i > 0 else -1.0
            next_v = (energy_curve[i + 1].get("value", 0.0)
                      if i < len(energy_curve) - 1 else -1.0)
            if v >= threshold and v > prev_v and v > next_v and (t - last) >= min_interval:
                points.append(t)
                last = t
        return points

    # ------------------------------------------------------------------
    # 5. VRS 驱动踩拍混剪管线（主入口）
    # ------------------------------------------------------------------
    def build_vrs_montage(self, clip_paths: List[str], bgm_path: str,
                          output_path: str,
                          beat_group: int = 2,
                          reference_video: Optional[str] = None,
                          transitions: Optional[List[str]] = None,
                          lut_path: Optional[str] = None,
                          enable_flash: bool = True,
                          enable_bounce: bool = True,
                          fps: int = 24,
                          beat_offset: float = 0.0) -> str:
        """
        VRS 驱动的踩拍混剪管线（端到端）。

        管线顺序（经验档案第3节配方）：
            VRS 分析 → 按拍分组切镜头（切点严格落拍）→ 单镜头加工
            （beat_bounce 缩放脉冲 + high_flash 闪光）→ xfade 转场链
            → 全片 LUT 统一调色 → 混入 BGM 尾部 afade 淡出

        Args:
            clip_paths: 画面素材列表（循环使用）
            bgm_path: BGM 音频（必须来自用户音频素材库）
            beat_group: 每多少拍切一个镜头
            reference_video: VRS 参考视频（可选，提供则做完整音画同步分析）
            transitions: 转场类型循环列表（None=硬切拼接）
            lut_path: 全片统一 .cube LUT（可选）
            enable_bounce: 是否应用踩拍缩放脉冲
            enable_flash: 是否应用能量闪光

        Returns:
            输出视频路径
        """
        if not clip_paths:
            raise ResolveError("clip_paths 为空")
        if not os.path.exists(bgm_path):
            raise ResolveError(f"BGM 不存在: {bgm_path}")

        # ---------- 1. VRS 分析 ----------
        analysis = self.analyze(bgm_path, reference_video)
        if not analysis.get("success") or not analysis.get("beats"):
            raise ResolveError("VRS/降级节拍分析失败，无可用节拍")
        beats: List[float] = analysis["beats"]
        bpm = analysis.get("bpm", 0.0)
        energy_curve = analysis.get("energy_curve", [])
        logger.info(f"Montage: source={analysis['source']}, bpm={bpm:.1f}, "
                    f"beats={len(beats)}")

        # ---------- 2. 镜头切点：每 beat_group 拍一个镜头（起点/终点严格落拍）----------
        # 【B4 节拍对齐优化】应用 beat_offset 微调补偿，校正系统性切点-节拍偏差
        if beat_offset != 0.0:
            beats = [b + beat_offset for b in beats]
            logger.info(f"Montage: 应用节拍偏移补偿 {beat_offset*1000:+.1f}ms")
        cut_beats = beats[::beat_group]
        boundaries = [0.0] + list(cut_beats)
        bgm_dur = self.engine._get_media_duration(bgm_path) or beats[-1] + 1.0
        # 去掉过短尾段
        shot_bounds: List[Tuple[float, float]] = []
        for i in range(len(boundaries) - 1):
            a, b = boundaries[i], boundaries[i + 1]
            if b - a >= 0.3:
                shot_bounds.append((a, b))
        if not shot_bounds:
            raise ResolveError("节拍过密，无可用镜头区间")
        total_dur = shot_bounds[-1][1]
        logger.info(f"Montage: {len(shot_bounds)} shots, total={total_dur:.2f}s, "
                    f"group={beat_group} beats/shot")

        # ---------- 3. 闪光触发点（全片能量尖峰）----------
        flash_points = self.find_flash_points(energy_curve) if enable_flash else []
        flash_points = [t for t in flash_points if t < total_dur]

        # ---------- 3b. 转场时长预计算 + xfade 重叠补偿 ----------
        # xfade 链式叠加会吞时长：链长 = Σ镜头时长 - Σ转场时长，
        # 导致后续每个切点提前累积量而漂移出拍。
        # 补偿：第 i 个镜头（非末尾）时长预加长其后转场时长 t_i，
        # 则 Σd_j - Σt_j = Σ拍区间，切点精确回到节拍上。
        t_durs: List[float] = []
        if transitions and len(shot_bounds) >= 2:
            for i in range(len(shot_bounds) - 1):
                next_dur = shot_bounds[i + 1][1] - shot_bounds[i + 1][0]
                t_durs.append(min(0.2, next_dur * 0.35))

        # ---------- 4. 逐镜头加工 ----------
        work_dir = os.path.join(self.engine._temp_dir,
                                f"vrs_montage_{uuid.uuid4().hex[:8]}")
        os.makedirs(work_dir, exist_ok=True)
        codec = self.engine._get_encoder_args(quality="fast")

        segments: List[str] = []
        for si, (a, b) in enumerate(shot_bounds):
            seg_dur = b - a
            # 补偿后的实际渲染时长（末尾镜头不加）
            render_dur = seg_dur + (t_durs[si] if si < len(t_durs) else 0.0)
            src = clip_paths[si % len(clip_paths)]
            # 素材循环使用错开起始位置，避免重复观感
            src_offset = (si // max(len(clip_paths), 1)) * 1.5

            vf_parts = [
                "scale=1920:1080:force_original_aspect_ratio=decrease",
                "pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
            ]

            # 4a. beat_bounce：本镜头内部节拍的缩放脉冲
            pulse_expr = None
            if enable_bounce:
                local_beats = [t - a for t in beats if a <= t < b]
                pulse_expr = self.build_beat_pulse_expression(
                    local_beats, render_dur, fps=fps)
            if pulse_expr:
                vf_parts = [
                    (f"zoompan=z='{pulse_expr}':x='iw/2-(iw/zoom/2)'"
                     f":y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps={fps}")
                ]

            # 4b. high_flash：白色 overlay 脉冲（enable 表达式）
            flash_in_seg = [t - a for t in flash_points if a <= t < b]
            flash_in_seg = flash_in_seg[:self.MAX_PULSES_PER_SEGMENT]

            seg_path = os.path.join(work_dir, f"shot_{si:03d}.mp4")
            if flash_in_seg:
                enable_parts = " + ".join(
                    f"between(t,{t:.3f},{t + 0.08:.3f})" for t in flash_in_seg)
                fc = (f"[0:v]{','.join(vf_parts)}[base];"
                      f"color=c=white:s=1920x1080:d={render_dur:.3f}:r={fps}[flash];"
                      f"[base][flash]blend=all_mode=screen:"
                      f"enable='{enable_parts}'[v]")
                cmd = (["ffmpeg", "-y", "-ss", f"{src_offset:.2f}",
                        "-stream_loop", "-1", "-i", src,
                        "-filter_complex", fc, "-map", "[v]",
                        "-t", f"{render_dur:.3f}"]
                       + shlex.split(codec, posix=False)
                       + ["-r", str(fps), "-an", seg_path])
            else:
                cmd = (["ffmpeg", "-y", "-ss", f"{src_offset:.2f}",
                        "-stream_loop", "-1", "-i", src,
                        "-t", f"{render_dur:.3f}", "-vf", ",".join(vf_parts)]
                       + shlex.split(codec, posix=False)
                       + ["-r", str(fps), "-an", seg_path])
            subprocess.run(cmd, check=True, capture_output=True,
                           timeout=300)
            segments.append(seg_path)

        logger.info(f"Montage: {len(segments)} shots processed "
                    f"(bounce={'on' if enable_bounce else 'off'}, "
                    f"flash={len(flash_points)} pts)")

        # ---------- 5. 转场链（时长已预补偿，切点不漂移）----------
        if transitions and len(segments) >= 2:
            tc_list = [
                TransitionConfig(type=transitions[i % len(transitions)],
                                 duration=t_durs[i])
                for i in range(len(segments) - 1)
            ]
            chained = self.engine.render_with_transitions(
                segments, os.path.join(work_dir, "chained.mp4"), tc_list)
        else:
            list_file = os.path.join(work_dir, "concat_list.txt")
            with open(list_file, "w", encoding="utf-8") as f:
                for s in segments:
                    f.write(f"file '{os.path.abspath(s).replace(os.sep, '/')}'\n")
            chained = os.path.join(work_dir, "chained.mp4")
            cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0",
                   "-i", list_file, "-c", "copy", chained]
            subprocess.run(cmd, check=True, capture_output=True,
                           timeout=300)

        # ---------- 6. 全片统一调色（LUT + 饱和/对比微调）----------
        if lut_path and os.path.exists(lut_path):
            lut_ff = lut_path.replace("\\", "/").replace(":", "\\:")
            graded = os.path.join(work_dir, "graded.mp4")
            cmd = (["ffmpeg", "-y", "-i", chained,
                    "-vf", f"lut3d=\'{lut_ff}\',eq=saturation=1.1:contrast=1.04"]
                   + shlex.split(codec, posix=False)
                   + ["-an", graded])
            subprocess.run(cmd, check=True, capture_output=True,
                           timeout=300)
            chained = graded

        # ---------- 7. 混入 BGM + 尾部 afade 淡出 ----------
        chained_dur = self.engine._get_media_duration(chained) or total_dur
        fade_start = max(0.0, chained_dur - 1.5)
        cmd = ["ffmpeg", "-y", "-i", chained, "-i", bgm_path,
               "-filter_complex",
               f"[1:a]afade=t=out:st={fade_start:.2f}:d=1.5[a]",
               "-map", "0:v", "-map", "[a]",
               "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
               "-shortest", output_path]
        subprocess.run(cmd, check=True, capture_output=True,
                       timeout=300)

        if not os.path.exists(output_path):
            raise ResolveError("VRS montage 渲染失败")

        final_dur = self.engine._get_media_duration(output_path) or 0
        logger.info(f"VRS montage complete: {output_path} ({final_dur:.1f}s)")
        return output_path

    # ------------------------------------------------------------------
    # 6. VRS 关键帧动画桥接（sync_keyframes → set_keyframe_animation）
    # ------------------------------------------------------------------
    def apply_vrs_sync_keyframes(self, source_path: str, output_path: str,
                                 sync_keyframes: List[Dict[str, Any]],
                                 mode: str = "ease", fps: int = 24) -> str:
        """
        把 VRS sync_keyframes 中的 scale 弹跳应用为引擎关键帧动画。
        用于单镜头的音画同步动画复刻。
        """
        zoom_kfs = self.vrs_keyframes_to_engine(sync_keyframes, prop="scale")
        if not zoom_kfs:
            raise ResolveError("sync_keyframes 中无 scale 关键帧")
        return self.engine.set_keyframe_animation(
            source_path, output_path, {"zoom": zoom_kfs}, mode=mode, fps=fps)

    # ------------------------------------------------------------------
    # 7. 切点-节拍偏差量化（质量指标）
    # ------------------------------------------------------------------
    def measure_sync_quality(self, video_path: str, beats: List[float],
                             scene_threshold: float = 0.2,
                             tolerance_ms: float = 120.0) -> Dict[str, Any]:
        """
        量化成片的音画同步质量：用场景突变检测提取实际切点，
        与目标节拍匹配，输出偏差统计。

        Returns:
            {"cuts": 检出切点数, "matched": 匹配到节拍的切点数,
             "avg_dev_ms": 平均偏差, "max_dev_ms": 最大偏差,
             "on_beat_rate": 踩拍率(偏差<tolerance), "deviations": [...]}
        """
        import re as _re
        cmd = ["ffmpeg", "-i", video_path,
               "-vf", f"select=\'gt(scene,{scene_threshold})\',showinfo",
               "-f", "null", "-"]
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="ignore", timeout=300)
        cuts = sorted(float(t) for t in _re.findall(r'pts_time:([\d.]+)', r.stderr))
        # 去重（转场帧可能连续多帧超阈）
        merged: List[float] = []
        for t in cuts:
            if not merged or t - merged[-1] > 0.15:
                merged.append(t)
        cuts = merged

        deviations: List[float] = []
        matched = 0
        for t in cuts:
            best = min(beats, key=lambda b: abs(b - t)) if beats else 0.0
            dev_ms = abs(t - best) * 1000.0
            deviations.append(round(dev_ms, 1))
            if dev_ms <= tolerance_ms:
                matched += 1

        avg_dev = sum(deviations) / len(deviations) if deviations else 0.0
        max_dev = max(deviations) if deviations else 0.0
        result = {
            "cuts": len(cuts),
            "matched": matched,
            "avg_dev_ms": round(avg_dev, 1),
            "max_dev_ms": round(max_dev, 1),
            "on_beat_rate": round(matched / len(cuts), 3) if cuts else 0.0,
            "deviations": deviations,
        }
        logger.info(f"Sync quality: cuts={len(cuts)} avg_dev={avg_dev:.1f}ms "
                    f"max_dev={max_dev:.1f}ms on_beat={result['on_beat_rate']:.0%}")
        return result


# -----------------------------------------------------------------------------
# CLI 入口
# -----------------------------------------------------------------------------
def _main():
    import argparse
    parser = argparse.ArgumentParser(description="VRS-Resolve 桥接：踩拍混剪")
    parser.add_argument("--clips", required=True, help="素材目录或逗号分隔文件列表")
    parser.add_argument("--bgm", required=True, help="BGM 音频路径（用户素材库）")
    parser.add_argument("--output", default=os.path.join(
        _PROJECT_ROOT, "output", "vrs_montage.mp4"))
    parser.add_argument("--beat-group", type=int, default=2)
    parser.add_argument("--reference", default=None, help="VRS 参考视频（可选）")
    parser.add_argument("--transitions", default="whip_pan,glitch,flash,zoom")
    parser.add_argument("--lut", default=None)
    args = parser.parse_args()

    if os.path.isdir(args.clips):
        exts = {'.mp4', '.mov', '.mkv'}
        clips = sorted(os.path.join(args.clips, f) for f in os.listdir(args.clips)
                       if os.path.splitext(f)[1].lower() in exts)
    else:
        clips = [c.strip() for c in args.clips.split(",") if c.strip()]

    bridge = VrsResolveBridge()
    out = bridge.build_vrs_montage(
        clips, args.bgm, args.output,
        beat_group=args.beat_group,
        reference_video=args.reference,
        transitions=args.transitions.split(","),
        lut_path=args.lut)
    print(f"DONE: {out}")


if __name__ == "__main__":
    _main()
