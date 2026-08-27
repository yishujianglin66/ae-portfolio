import os
import json
import math
import logging
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).parent / "config" / "media-config.json"

# librosa 分析超时时间（秒）
LIBROSA_TIMEOUT = 60
# 最大分析音频时长（秒），超过此长度自动截断
MAX_ANALYSIS_DURATION = 600

@dataclass
class AudioFeatures:
    bpm: float = 0.0
    tempo: float = 0.0
    key: str = ""
    mode: str = ""
    duration: float = 0.0
    loudness: float = 0.0
    spectral_centroid: float = 0.0
    spectral_bandwidth: float = 0.0
    spectral_rolloff: float = 0.0
    zero_crossing_rate: float = 0.0
    mfccs: List[float] = None
    chroma: List[float] = None
    energy: float = 0.0
    mood: str = ""
    mood_score: float = 0.0
    genre: str = ""

    def to_dict(self):
        return {
            "bpm": round(self.bpm, 1),
            "tempo": round(self.tempo, 1),
            "key": self.key,
            "mode": self.mode,
            "duration": round(self.duration, 2),
            "loudness": round(self.loudness, 2),
            "spectral_centroid": round(self.spectral_centroid, 2),
            "spectral_bandwidth": round(self.spectral_bandwidth, 2),
            "spectral_rolloff": round(self.spectral_rolloff, 2),
            "zero_crossing_rate": round(self.zero_crossing_rate, 4),
            "mfccs": [round(v, 3) for v in (self.mfccs or [])],
            "chroma": [round(v, 3) for v in (self.chroma or [])],
            "energy": round(self.energy, 3),
            "mood": self.mood,
            "mood_score": round(self.mood_score, 3),
            "genre": self.genre
        }

class AudioAnalyzer:
    def __init__(self, config_path: Path = CONFIG_PATH):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self._librosa = None
        self._scipy = None

    def _ensure_librosa(self):
        if self._librosa is None:
            try:
                import librosa
                self._librosa = librosa
            except ImportError:
                raise ImportError("librosa 未安装，请执行: pip install librosa")
        return self._librosa

    def _ensure_scipy(self):
        if self._scipy is None:
            try:
                import scipy
                self._scipy = scipy
            except ImportError:
                raise ImportError("scipy 未安装，请执行: pip install scipy")
        return self._scipy

    def analyze_audio(self, audio_path: str) -> Dict:
        if not os.path.exists(audio_path):
            return {"success": False, "error": "音频文件不存在"}

        # A3 修复：使用 ThreadPoolExecutor 添加超时保护
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self._analyze_audio_impl, audio_path)
                return future.result(timeout=LIBROSA_TIMEOUT)
        except FuturesTimeoutError:
            logger.warning(f"librosa 分析超时 ({LIBROSA_TIMEOUT}s)，降级到 FFprobe 基础分析: {audio_path}")
            return self._fallback_analyze(audio_path)
        except Exception as e:
            logger.error(f"librosa 分析异常，降级到 FFprobe: {e}")
            return self._fallback_analyze(audio_path)

    def _analyze_audio_impl(self, audio_path: str) -> Dict:
        """librosa 完整分析实现（内部方法，受超时保护）。"""
        try:
            librosa = self._ensure_librosa()
            # A3 修复：限制分析时长，避免大文件卡死
            y, sr = librosa.load(audio_path, sr=self.config["audio"]["default_sample_rate"],
                                 duration=MAX_ANALYSIS_DURATION)
            duration = librosa.get_duration(y=y, sr=sr)

            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            spectral_centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
            spectral_bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr)
            spectral_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            zero_crossing_rate = librosa.feature.zero_crossing_rate(y)
            rms = librosa.feature.rms(y=y)

            energy = float(rms.mean())
            loudness = float(20 * math.log10(energy + 1e-10))
            avg_spectral_centroid = float(spectral_centroid.mean())
            avg_spectral_bandwidth = float(spectral_bandwidth.mean())
            avg_spectral_rolloff = float(spectral_rolloff.mean())
            avg_zcr = float(zero_crossing_rate.mean())

            chroma_avg = chroma.mean(axis=1).tolist()
            mfccs_avg = mfccs.mean(axis=1).tolist()

            key, mode = self._detect_key(chroma_avg)
            mood, mood_score = self._infer_mood(tempo, energy, avg_spectral_centroid)
            genre = self._infer_genre(tempo, energy, key)

            features = AudioFeatures(
                bpm=float(tempo),
                tempo=float(tempo),
                key=key,
                mode=mode,
                duration=duration,
                loudness=loudness,
                spectral_centroid=avg_spectral_centroid,
                spectral_bandwidth=avg_spectral_bandwidth,
                spectral_rolloff=avg_spectral_rolloff,
                zero_crossing_rate=avg_zcr,
                mfccs=mfccs_avg,
                chroma=chroma_avg,
                energy=energy,
                mood=mood,
                mood_score=mood_score,
                genre=genre
            )

            return {
                "success": True,
                "features": features.to_dict(),
                "beat_count": len(beat_frames),
                "beat_times": [round(t, 2) for t in librosa.frames_to_time(beat_frames, sr=sr)]
            }

        except Exception as e:
            return {"success": False, "error": str(e)}

    def _fallback_analyze(self, audio_path: str) -> Dict:
        """降级方案：使用 FFprobe 获取基础音频信息（无需 librosa）。"""
        try:
            ffprobe_cmd = self.config.get("tools", {}).get("ffprobe", "ffprobe")
            cmd = [
                ffprobe_cmd, "-v", "quiet",
                "-print_format", "json",
                "-show_format", "-show_streams",
                "-select_streams", "a:0",
                audio_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return {"success": False, "error": f"FFprobe 降级分析失败: {result.stderr}"}

            info = json.loads(result.stdout)
            audio_stream = (info.get("streams") or [{}])[0]
            fmt = info.get("format", {})

            duration = float(audio_stream.get("duration", fmt.get("duration", 0)))
            sample_rate = int(audio_stream.get("sample_rate", 0))
            channels = int(audio_stream.get("channels", 0))
            codec = audio_stream.get("codec_name", "unknown")

            return {
                "success": True,
                "features": {
                    "bpm": 0.0,
                    "tempo": 0.0,
                    "key": "",
                    "mode": "",
                    "duration": round(duration, 2),
                    "loudness": 0.0,
                    "spectral_centroid": 0.0,
                    "spectral_bandwidth": 0.0,
                    "spectral_rolloff": 0.0,
                    "zero_crossing_rate": 0.0,
                    "mfccs": [],
                    "chroma": [],
                    "energy": 0.0,
                    "mood": "",
                    "mood_score": 0.0,
                    "genre": ""
                },
                "fallback": True,
                "fallback_reason": "librosa_timeout",
                "ffprobe_info": {
                    "codec": codec,
                    "sample_rate": sample_rate,
                    "channels": channels,
                    "duration": round(duration, 2)
                }
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "FFprobe 也超时了"}
        except Exception as e:
            return {"success": False, "error": f"降级分析失败: {e}"}

    def _detect_key(self, chroma: List[float]) -> Tuple[str, str]:
        key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        mode_names = ['major', 'minor']

        chroma_sum = sum(chroma)
        if chroma_sum == 0:
            return "Unknown", "unknown"

        normalized = [c / chroma_sum for c in chroma]

        key_index = normalized.index(max(normalized))
        key = key_names[key_index]

        mode_score = self._calculate_mode_score(chroma)
        mode = mode_names[0] if mode_score > 0 else mode_names[1]

        return key, mode

    def _calculate_mode_score(self, chroma: List[float]) -> float:
        major_pattern = [1, 0.6, 0.8, 0.6, 1, 0.8, 0.6, 1, 0.8, 0.6, 0.8, 0.6]
        minor_pattern = [1, 0.8, 0.6, 0.8, 0.6, 1, 0.6, 1, 0.8, 0.6, 0.8, 0.6]

        major_score = sum(c * p for c, p in zip(chroma, major_pattern))
        minor_score = sum(c * p for c, p in zip(chroma, minor_pattern))

        return major_score - minor_score

    def _infer_mood(self, tempo: float, energy: float, spectral_centroid: float) -> Tuple[str, float]:
        mood_scores = {}

        mood_scores["excited"] = min(tempo / 150, 1.0) * 0.5 + min(energy / 0.3, 1.0) * 0.3 + min(spectral_centroid / 2000, 1.0) * 0.2
        mood_scores["calm"] = max(1 - tempo / 120, 0) * 0.4 + max(1 - energy / 0.2, 0) * 0.4 + max(1 - spectral_centroid / 1500, 0) * 0.2
        mood_scores["happy"] = min(tempo / 120, 1.0) * 0.3 + min(energy / 0.25, 1.0) * 0.4 + min(spectral_centroid / 1800, 1.0) * 0.3
        mood_scores["sad"] = max(1 - tempo / 100, 0) * 0.3 + max(1 - energy / 0.15, 0) * 0.4 + max(1 - spectral_centroid / 1200, 0) * 0.3
        mood_scores["epic"] = min(tempo / 100, 1.0) * 0.3 + min(energy / 0.35, 1.0) * 0.5 + min(spectral_centroid / 2200, 1.0) * 0.2
        mood_scores["mysterious"] = max(1 - tempo / 80, 0) * 0.3 + max(1 - energy / 0.2, 0) * 0.3 + min(spectral_centroid / 800, 1.0) * 0.4

        best_mood = max(mood_scores, key=mood_scores.get)
        return best_mood, mood_scores[best_mood]

    def _infer_genre(self, tempo: float, energy: float, key: str) -> str:
        if tempo > 140 and energy > 0.25:
            return "rock"
        elif tempo > 120 and energy > 0.2:
            return "pop"
        elif tempo > 100 and energy > 0.15:
            return "electronic"
        elif tempo < 80 and energy < 0.15:
            return "ambient"
        elif tempo < 90 and energy < 0.2:
            return "classical"
        elif 80 <= tempo <= 100 and 0.15 <= energy <= 0.25:
            return "jazz"
        elif tempo > 90 and energy > 0.3:
            return "epic"
        else:
            return "other"

    def find_best_bgm_match(self, target_features: Dict, bgm_directory: str, 
                            max_results: int = 5) -> List[Dict]:
        if not os.path.exists(bgm_directory):
            return []

        matches = []
        audio_extensions = self.config["download"]["audio_only_formats"]

        for root, dirs, files in os.walk(bgm_directory):
            for file in files:
                ext = file.split(".")[-1].lower()
                if ext in audio_extensions:
                    full_path = os.path.join(root, file)
                    analysis = self.analyze_audio(full_path)
                    
                    if analysis["success"]:
                        features = analysis["features"]
                        similarity = self._calculate_similarity(target_features, features)
                        
                        matches.append({
                            "name": file,
                            "path": full_path,
                            "features": features,
                            "similarity": similarity,
                            "duration": features["duration"]
                        })

        return sorted(matches, key=lambda x: x["similarity"], reverse=True)[:max_results]

    def _calculate_similarity(self, target: Dict, candidate: Dict) -> float:
        score = 0.0

        if "tempo" in target and "tempo" in candidate:
            tempo_diff = abs(target["tempo"] - candidate["tempo"])
            score += max(0, 1 - tempo_diff / 50) * 0.3

        if "mood" in target and "mood" in candidate:
            if target["mood"] == candidate["mood"]:
                score += 0.3

        if "duration" in target and "duration" in candidate:
            duration_diff = abs(target["duration"] - candidate["duration"])
            max_duration = max(target["duration"], candidate["duration"])
            score += max(0, 1 - duration_diff / max_duration) * 0.2

        if "energy" in target and "energy" in candidate:
            energy_diff = abs(target["energy"] - candidate["energy"])
            score += max(0, 1 - energy_diff / 0.5) * 0.1

        if "key" in target and "key" in candidate:
            if target["key"] == candidate["key"]:
                score += 0.1

        return round(score, 3)

    def generate_beat_map(self, audio_path: str) -> Dict:
        analysis = self.analyze_audio(audio_path)
        if not analysis["success"]:
            return analysis

        beat_times = analysis["beat_times"]
        duration = analysis["features"]["duration"]

        sections = self._detect_sections(beat_times, duration)

        return {
            "success": True,
            "beat_times": beat_times,
            "beat_count": len(beat_times),
            "duration": duration,
            "bpm": analysis["features"]["bpm"],
            "sections": sections,
            "features": analysis["features"]
        }

    def _detect_sections(self, beat_times: List[float], duration: float) -> List[Dict]:
        sections = []
        if len(beat_times) < 4:
            return []

        beats_per_section = max(8, len(beat_times) // 8)
        section_duration = duration / max(4, len(beat_times) // beats_per_section)

        for i in range(0, len(beat_times), beats_per_section):
            end_idx = min(i + beats_per_section, len(beat_times))
            section_beats = beat_times[i:end_idx]
            
            if section_beats:
                sections.append({
                    "start_time": round(section_beats[0], 2),
                    "end_time": round(section_beats[-1], 2),
                    "beat_count": len(section_beats),
                    "section_number": len(sections) + 1,
                    "suggested_action": self._get_section_action(len(sections) + 1)
                })

        return sections

    def _get_section_action(self, section_number: int) -> str:
        actions = [
            "intro",
            "build",
            "drop",
            "verse",
            "chorus",
            "bridge",
            "outro"
        ]
        return actions[(section_number - 1) % len(actions)]
    
    def test_librosa(self) -> Dict:
        """测试librosa和scipy可用性"""
        librosa_available = False
        scipy_available = False
        
        try:
            import librosa
            librosa_available = True
        except:
            pass
        
        try:
            import scipy
            scipy_available = True
        except:
            pass
        
        return {
            "librosa_available": librosa_available,
            "scipy_available": scipy_available
        }

def main():
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--json-input":
        try:
            if len(sys.argv) > 2:
                input_data = sys.argv[2]
            else:
                input_data = sys.stdin.read()
            
            if input_data:
                request = json.loads(input_data)
                analyzer = AudioAnalyzer()
                
                func_name = request.get("func")
                params = request.get("params", {})
                
                func_map = {
                    "analyze_audio": analyzer.analyze_audio,
                    "find_best_bgm_match": analyzer.find_best_bgm_match,
                    "generate_beat_map": analyzer.generate_beat_map,
                    "test_librosa": analyzer.test_librosa
                }
                
                if func_name in func_map:
                    result = func_map[func_name](**params)
                else:
                    result = {"success": False, "error": f"Unknown function: {func_name}"}
                
                print(json.dumps(result, ensure_ascii=False))
        except Exception as e:
            print(json.dumps({"success": False, "error": str(e)}))
        return
    
    analyzer = AudioAnalyzer()
    
    bgm_dir = r"D:\AE-Work\音频素材库\BGM"
    
    if os.path.exists(bgm_dir):
        print("分析 BGM 库...")
        for f in os.listdir(bgm_dir):
            if f.endswith((".mp3", ".m4a")):
                full_path = os.path.join(bgm_dir, f)
                print(f"\n分析: {f}")
                result = analyzer.analyze_audio(full_path)
                if result["success"]:
                    features = result["features"]
                    print(f"  BPM: {features['bpm']}")
                    print(f"  情绪: {features['mood']} ({features['mood_score']:.2f})")
                    print(f"  曲风: {features['genre']}")
                    print(f"  调性: {features['key']} {features['mode']}")
                else:
                    print(f"  分析失败: {result['error']}")
    else:
        print(f"BGM目录不存在: {bgm_dir}")

if __name__ == "__main__":
    main()