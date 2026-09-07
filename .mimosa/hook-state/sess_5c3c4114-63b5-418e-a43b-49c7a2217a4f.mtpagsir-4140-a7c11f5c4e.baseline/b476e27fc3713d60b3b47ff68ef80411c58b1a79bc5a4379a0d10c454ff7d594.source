"""
pipeline/stages/analysis.py - 分析阶段
========================================
深度分析素材内容：场景检测、节拍映射、情绪曲线

旗舰管线 S2 增强：
- BeatAnalysisStage: 产出 beats.json (BPM + drop 数组 ≥4) + waveform.png
- 零 fallback: librosa 不可用时直接 fail
"""
from __future__ import annotations

import json
import os
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _tempo_value(tempo) -> float:
    """兼容 librosa 0.9/0.10: beat_track 返回的 tempo 可能是标量或 1 维数组。

    librosa >=0.10 的 beat_track 返回 (tempo_ndarray, beats)，直接 float(tempo)
    会抛 "only 0-dimensional arrays can be converted to Python scalars"。
    """
    try:
        return float(tempo)
    except (TypeError, ValueError):
        import numpy as np
        return float(np.ravel(np.asarray(tempo))[0])


class AnalysisStage:
    """分析阶段：场景检测 + 节拍分析 + 情绪曲线"""

    def __init__(self, config):
        self.config = config

    def run(self, previous_data: Dict) -> Dict:
        """执行分析阶段"""
        perceive = previous_data.get("perceive", {})
        videos = perceive.get("videos", [])
        audios = perceive.get("audios", [])

        result = {
            "scenes": [],
            "beats": [],
            "mood_curve": [],
            "total_duration": 0.0,
        }

        # 1. 场景检测
        for v in videos:
            scenes = self._detect_scenes(v.get("path", ""))
            if scenes:
                result["scenes"].extend(scenes)
                result["total_duration"] += sum(s.get("duration", 0) for s in scenes)

        # 2. 节拍分析
        for a in audios:
            beats = self._analyze_beats(a.get("path", ""))
            if beats:
                result["beats"].extend(beats)

        # 3. 如果没有单独音频，从视频提取音频分析
        if not audios and videos:
            for v in videos[:2]:
                beats = self._analyze_beats(v.get("path", ""))
                if beats:
                    result["beats"].extend(beats)

        # 4. 情绪曲线
        result["mood_curve"] = self._build_mood_curve(result["scenes"], result["beats"])

        return result

    def _detect_scenes(self, path: str) -> List[Dict]:
        """场景检测"""
        if not path or not os.path.isfile(path):
            return []
        try:
            from analysis.scene_detector import SceneDetector
            detector = SceneDetector()
            result = detector.detect(path)
            if result.success and result.segments:
                return [
                    {
                        "index": seg.index,
                        "start": seg.start_time,
                        "end": seg.end_time,
                        "start_time": seg.start_time,
                        "duration": seg.duration,
                        "source": path,
                    }
                    for seg in result.segments
                ]
            return []
        except Exception as e:
            logger.debug(f"Scene detection failed for {path}: {e}")
            return []

    def _analyze_beats(self, path: str) -> List[Dict]:
        """节拍分析 (使用 librosa 或降级为 ffprobe BPM 估算)"""
        if not path or not os.path.isfile(path):
            return []
        # 尝试 librosa
        try:
            import librosa
            y, sr = librosa.load(path, sr=None, mono=True)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)
            return [
                {"time": round(float(t), 3), "bpm": round(_tempo_value(tempo), 1), "source": path}
                for t in beat_times
            ]
        except Exception:
            pass
        # 降级: 基于时长的均匀节拍估算
        try:
            import subprocess, json
            from pipeline.stages import resolve_ffprobe
            ffprobe = resolve_ffprobe(self.config)
            r = subprocess.run(
                [ffprobe, "-v", "quiet", "-print_format", "json", "-show_format", path],
                capture_output=True, text=True, timeout=10,
                encoding='utf-8', errors='replace',
            )
            if r.returncode == 0:
                dur = float(json.loads(r.stdout).get("format", {}).get("duration", 0))
                if dur > 0:
                    est_bpm = 120.0  # 默认估算
                    interval = 60.0 / est_bpm
                    return [
                        {"time": round(i * interval, 3), "bpm": est_bpm, "source": path, "estimated": True}
                        for i in range(int(dur / interval))
                    ]
        except Exception as e:
            logger.debug(f"Beat analysis failed for {path}: {e}")
        return []

    def _build_mood_curve(self, scenes: List, beats: List) -> List[Dict]:
        """构建情绪曲线"""
        curve = []
        # 基于场景切换频率和节拍密度估算情绪强度
        if not scenes and not beats:
            return curve

        total_dur = max(sum(s.get("duration", 0) for s in scenes), 1.0)
        # 按时间段采样情绪
        n_points = min(20, max(5, int(total_dur / 5)))
        for i in range(n_points):
            t = (i + 0.5) * total_dur / n_points
            # 场景切换密度
            scene_density = sum(1 for s in scenes
                                if s.get("start", 0) <= t < s.get("start", 0) + s.get("duration", 1))
            # 节拍密度
            beat_density = sum(1 for b in beats
                               if abs(b.get("time", 0) - t) < 2.0)
            # 综合情绪强度 (0-1)
            intensity = min(1.0, (scene_density * 0.4 + beat_density * 0.1))
            curve.append({"time": round(t, 2), "intensity": round(intensity, 3)})

        return curve


# ============================================================================
#  旗舰管线 S2: 节拍分析阶段
# ============================================================================

@dataclass
class BeatAnalysisResult:
    """节拍分析结果"""
    success: bool
    bpm: float = 0.0
    beats: List[float] = field(default_factory=list)
    drops: List[float] = field(default_factory=list)
    duration_s: float = 0.0
    beats_json_path: Optional[str] = None
    waveform_png_path: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    elapsed_s: float = 0.0


class BeatAnalysisStage:
    """旗舰管线 S2 节拍分析阶段

    产出：
    - beats.json: {"bpm": float, "beats": [float...], "drops": [float...], "duration_s": float}
    - waveform.png: 波形图 + drop 标记

    要求：
    - drops 数组 ≥ 4 个（通过 onset 强度峰值检测）
    - 零 fallback: librosa 不可用时直接 fail
    """

    def __init__(self, sr: int = 22050):
        self.sr = sr

    def run(
        self,
        audio_path: str | Path,
        output_dir: str | Path,
        min_drops: int = 4,
    ) -> BeatAnalysisResult:
        """执行节拍分析。

        Args:
            audio_path: 输入音频文件（WAV/MP3）
            output_dir: 输出目录
            min_drops: 最少 drop 数量

        Returns:
            BeatAnalysisResult
        """
        start = time.time()
        audio_path = Path(audio_path)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if not audio_path.exists():
            return BeatAnalysisResult(
                success=False,
                errors=[f"音频文件不存在: {audio_path}"],
                elapsed_s=time.time() - start,
            )

        # 零 fallback: librosa 必须可用
        try:
            import librosa
            import numpy as np
        except ImportError as e:
            return BeatAnalysisResult(
                success=False,
                errors=[f"librosa/numpy 不可用（S2 禁止 fallback）: {e}"],
                elapsed_s=time.time() - start,
            )

        try:
            # 加载音频
            y, sr = librosa.load(str(audio_path), sr=self.sr, mono=True)
            duration_s = float(len(y) / sr)

            # BPM + 节拍检测
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr).tolist()
            # librosa >=0.10 tempo 可能是 1 维数组，用兼容提取
            bpm = _tempo_value(tempo)

            # Drop 检测：基于 onset 强度峰值
            drops = self._detect_drops(y, sr, librosa, np, min_drops)

            # 写入 beats.json
            beats_data = {
                "bpm": round(bpm, 1),
                "beats": [round(t, 3) for t in beat_times],
                "drops": [round(t, 3) for t in drops],
                "duration_s": round(duration_s, 2),
                "sample_rate": sr,
                "beat_count": len(beat_times),
                "drop_count": len(drops),
            }
            beats_json_path = output_dir / "beats.json"
            beats_json_path.write_text(
                json.dumps(beats_data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 生成 waveform.png
            waveform_path = output_dir / "waveform.png"
            self._render_waveform(y, sr, drops, beat_times, waveform_path)

            success = len(drops) >= min_drops
            errors = []
            if not success:
                errors.append(
                    f"drop 数量不足: {len(drops)} < {min_drops}"
                )

            result = BeatAnalysisResult(
                success=success,
                bpm=round(bpm, 1),
                beats=[round(t, 3) for t in beat_times],
                drops=[round(t, 3) for t in drops],
                duration_s=round(duration_s, 2),
                beats_json_path=str(beats_json_path),
                waveform_png_path=str(waveform_path) if waveform_path.exists() else None,
                errors=errors,
                elapsed_s=time.time() - start,
            )

            logger.info(
                f"[S2] 节拍分析完成: BPM={bpm:.1f}, "
                f"beats={len(beat_times)}, drops={len(drops)}, "
                f"时长={duration_s:.1f}s"
            )
            return result

        except Exception as e:
            return BeatAnalysisResult(
                success=False,
                errors=[f"节拍分析异常: {e}"],
                elapsed_s=time.time() - start,
            )

    def _detect_drops(
        self, y, sr, librosa, np, min_drops: int
    ) -> List[float]:
        """检测 drop 点（基于 onset 强度 + 频谱通量峰值）

        策略：
        1. 计算 onset envelope
        2. 找局部峰值（比前后都大且超过均值+1std）
        3. 如果峰值不够 min_drops，降低阈值
        """
        # onset 强度
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        times = librosa.times_like(onset_env, sr=sr)

        # 峰值检测
        from scipy.signal import find_peaks
        mean_val = float(np.mean(onset_env))
        std_val = float(np.std(onset_env))

        # 第一次：严格阈值 (mean + 1.5*std)
        threshold = mean_val + 1.5 * std_val
        peaks, properties = find_peaks(onset_env, height=threshold, distance=10)

        # 如果不够，降低阈值
        if len(peaks) < min_drops:
            threshold = mean_val + 0.8 * std_val
            peaks, _ = find_peaks(onset_env, height=threshold, distance=8)

        # 还不够，用最低阈值
        if len(peaks) < min_drops:
            threshold = mean_val + 0.3 * std_val
            peaks, _ = find_peaks(onset_env, height=threshold, distance=5)

        drop_times = [float(times[p]) for p in peaks]
        return drop_times

    def _render_waveform(
        self, y, sr, drops: List[float], beats: List[float], output_path: Path
    ) -> None:
        """渲染波形图 + drop/beat 标记"""
        try:
            import matplotlib
            matplotlib.use("Agg")  # 无头模式
            import matplotlib.pyplot as plt
            import numpy as np

            fig, ax = plt.subplots(1, 1, figsize=(14, 4))
            times = np.linspace(0, len(y) / sr, len(y))

            # 波形
            ax.plot(times, y, linewidth=0.3, alpha=0.7, color="steelblue")

            # beat 标记
            for bt in beats:
                ax.axvline(x=bt, color="gray", linewidth=0.3, alpha=0.4)

            # drop 标记
            for dt in drops:
                ax.axvline(x=dt, color="red", linewidth=1.2, alpha=0.8)

            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Amplitude")
            ax.set_title(f"Waveform + Drops (red) / Beats (gray)")
            ax.set_xlim(0, len(y) / sr)

            plt.tight_layout()
            plt.savefig(str(output_path), dpi=100, bbox_inches="tight")
            plt.close(fig)
        except Exception as e:
            logger.warning(f"[S2] 波形图渲染失败（不影响主流程）: {e}")
