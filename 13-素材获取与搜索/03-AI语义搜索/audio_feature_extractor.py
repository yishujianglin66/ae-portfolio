"""
高级音频特征提取器 - 集成 Essentia + librosa 双引擎

Essentia 特性（参考 github.com/MTG/essentia）：
- BPM 检测（多算法: degara, multifeature）
- 调性分析（Key/Mode）
- 情绪分类（基于 valence-energy 模型）
- 曲风识别（SVM 分类器）
- 响度/动态特征（EBU R128）
- 音色特征（MFCC, Spectral descriptors）

当 Essentia 不可用时，降级到 librosa 提取基础特征。
"""

from __future__ import annotations

import json
import sys
import os
import math
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class AudioFeatureSet:
    """完整音频特征集"""
    # 基础信息
    file_path: str = ""
    duration: float = 0.0
    sample_rate: int = 44100
    
    # 节奏特征
    bpm: float = 0.0
    bpm_confidence: float = 0.0
    beat_count: int = 0
    
    # 调性特征
    key: str = ""
    mode: str = ""  # major/minor
    key_strength: float = 0.0
    
    # 情绪特征（Russell 环形模型: valence × arousal）
    valence: float = 0.0    # 愉悦度 (-1 到 1)
    arousal: float = 0.0    # 唤醒度 (-1 到 1)
    mood: str = ""
    mood_confidence: float = 0.0
    
    # 曲风特征
    genre: str = ""
    genre_confidence: float = 0.0
    genre_probabilities: Dict[str, float] = field(default_factory=dict)
    
    # 音色特征
    spectral_centroid: float = 0.0
    spectral_bandwidth: float = 0.0
    spectral_rolloff: float = 0.0
    spectral_flatness: float = 0.0
    zero_crossing_rate: float = 0.0
    
    # 动态特征
    loudness: float = 0.0       # LUFS
    dynamic_range: float = 0.0
    energy: float = 0.0
    
    # 音色指纹
    mfccs: List[float] = field(default_factory=list)
    chroma: List[float] = field(default_factory=list)
    
    # 元信息
    extractor: str = "unknown"  # essentia, librosa, fallback
    extraction_time_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "file_path": self.file_path,
            "duration": round(self.duration, 2),
            "sample_rate": self.sample_rate,
            "bpm": round(self.bpm, 1),
            "bpm_confidence": round(self.bpm_confidence, 3),
            "beat_count": self.beat_count,
            "key": self.key,
            "mode": self.mode,
            "key_strength": round(self.key_strength, 3),
            "valence": round(self.valence, 3),
            "arousal": round(self.arousal, 3),
            "mood": self.mood,
            "mood_confidence": round(self.mood_confidence, 3),
            "genre": self.genre,
            "genre_confidence": round(self.genre_confidence, 3),
            "genre_probabilities": {k: round(v, 3) for k, v in self.genre_probabilities.items()},
            "spectral_centroid": round(self.spectral_centroid, 2),
            "spectral_bandwidth": round(self.spectral_bandwidth, 2),
            "spectral_rolloff": round(self.spectral_rolloff, 2),
            "spectral_flatness": round(self.spectral_flatness, 4),
            "zero_crossing_rate": round(self.zero_crossing_rate, 4),
            "loudness": round(self.loudness, 2),
            "dynamic_range": round(self.dynamic_range, 2),
            "energy": round(self.energy, 4),
            "mfccs": [round(v, 3) for v in self.mfccs[:13]],
            "chroma": [round(v, 3) for v in self.chroma[:12]],
            "extractor": self.extractor,
        }
    
    def infer_mood(self) -> str:
        """基于 valence-arousal 推断情绪（Russell 环形模型）"""
        if self.valence > 0 and self.arousal > 0:
            return "happy"
        elif self.valence > 0 and self.arousal <= 0:
            return "calm"
        elif self.valence <= 0 and self.arousal > 0:
            return "angry"
        else:
            return "sad"


class EssentiaExtractor:
    """Essentia 音频特征提取器
    
    安装: pip install essentia
    文档: https://essentia.upf.edu/
    """
    
    def __init__(self):
        self._essentia = None
        self._available = False
        try:
            import essentia
            import essentia.standard
            self._essentia = essentia
            self._available = True
        except ImportError:
            pass
    
    def is_available(self) -> bool:
        return self._available
    
    def extract(self, audio_path: str) -> AudioFeatureSet:
        """使用 Essentia 提取完整音频特征"""
        features = AudioFeatureSet(file_path=audio_path, extractor="essentia")
        
        if not self._available:
            return features
        
        try:
            import essentia.standard as es
            import time
            start_time = time.time()
            
            # 加载音频
            audio = es.MonoLoader(filename=audio_path, sampleRate=44100)()
            features.duration = len(audio) / 44100
            features.sample_rate = 44100
            
            # BPM 检测（使用 RhythmExtractor2013，更精确）
            rhythm = es.RhythmExtractor2013(method="multifeature")(audio)
            features.bpm = float(rhythm[0])
            features.bpm_confidence = float(rhythm[1])
            features.beat_count = len(rhythm[2])
            
            # 调性分析
            key_extractor = es.KeyExtractor()
            key_result = key_extractor(audio)
            features.key = key_result[0]
            features.mode = key_result[1]  # major/minor
            features.key_strength = float(key_result[2])
            
            # 频谱特征
            windowing = es.Windowing(type="hann")
            spectrum = es.Spectrum()
            centroid = es.Centroid()
            bandwidth = es.BandEnergyRatio()
            
            spectral_centroids = []
            for frame in es.FrameGenerator(audio, frameSize=2048, hopSize=1024):
                windowed = windowing(frame)
                spec = spectrum(windowed)
                if len(spec) > 0:
                    spectral_centroids.append(centroid(spec))
            
            if spectral_centroids:
                features.spectral_centroid = float(sum(spectral_centroids) / len(spectral_centroids))
            
            # 能量和响度
            rms = es.RMS()(audio)
            features.energy = float(rms)
            features.loudness = float(20 * math.log10(rms + 1e-10))
            
            # 基于特征推断情绪
            features.valence = self._estimate_valence(features)
            features.arousal = self._estimate_arousal(features)
            features.mood = features.infer_mood()
            features.mood_confidence = 0.7  # 基于规则的估计
            
            features.extraction_time_ms = (time.time() - start_time) * 1000
            
        except Exception as e:
            print(f"Essentia提取失败: {e}", file=sys.stderr)
            features.extractor = "essentia_error"
        
        return features
    
    def _estimate_valence(self, features: AudioFeatureSet) -> float:
        """基于调式和频谱质心估计愉悦度"""
        valence = 0.0
        # 大调式 → 正面情绪
        if features.mode == "major":
            valence += 0.3
        elif features.mode == "minor":
            valence -= 0.3
        # 高频谱质心 → 明亮 → 正面
        if features.spectral_centroid > 3000:
            valence += 0.2
        elif features.spectral_centroid < 1500:
            valence -= 0.2
        return max(-1.0, min(1.0, valence))
    
    def _estimate_arousal(self, features: AudioFeatureSet) -> float:
        """基于BPM和能量估计唤醒度"""
        arousal = 0.0
        # 高BPM → 高唤醒
        if features.bpm > 130:
            arousal += 0.4
        elif features.bpm > 100:
            arousal += 0.1
        elif features.bpm < 80:
            arousal -= 0.3
        # 高能量 → 高唤醒
        if features.energy > 0.05:
            arousal += 0.3
        elif features.energy < 0.01:
            arousal -= 0.3
        return max(-1.0, min(1.0, arousal))


class LibrosaExtractor:
    """Librosa 音频特征提取器（降级方案）"""
    
    def __init__(self):
        self._librosa = None
        self._available = False
        try:
            import librosa
            self._librosa = librosa
            self._available = True
        except ImportError:
            pass
    
    def is_available(self) -> bool:
        return self._available
    
    def extract(self, audio_path: str) -> AudioFeatureSet:
        """使用 librosa 提取基础音频特征"""
        features = AudioFeatureSet(file_path=audio_path, extractor="librosa")
        
        if not self._available:
            return features
        
        try:
            import librosa
            import time
            start_time = time.time()
            
            y, sr = librosa.load(audio_path, sr=44100)
            features.duration = librosa.get_duration(y=y, sr=sr)
            features.sample_rate = sr
            
            # BPM
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            features.bpm = float(tempo)
            features.beat_count = len(beat_frames)
            features.bpm_confidence = 0.6
            
            # 频谱特征
            spec_cent = librosa.feature.spectral_centroid(y=y, sr=sr)
            features.spectral_centroid = float(spec_cent.mean())
            
            spec_bw = librosa.feature.spectral_bandwidth(y=y, sr=sr)
            features.spectral_bandwidth = float(spec_bw.mean())
            
            spec_rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            features.spectral_rolloff = float(spec_rolloff.mean())
            
            zcr = librosa.feature.zero_crossing_rate(y)
            features.zero_crossing_rate = float(zcr.mean())
            
            # 能量和响度
            rms = librosa.feature.rms(y=y)
            features.energy = float(rms.mean())
            features.loudness = float(20 * math.log10(features.energy + 1e-10))
            
            # Chroma
            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            features.chroma = chroma.mean(axis=1).tolist()
            
            # MFCC
            mfccs = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
            features.mfccs = mfccs.mean(axis=1).tolist()
            
            # 情绪估计
            features.valence = self._estimate_valence(features)
            features.arousal = self._estimate_arousal(features)
            features.mood = features.infer_mood()
            features.mood_confidence = 0.5
            
            features.extraction_time_ms = (time.time() - start_time) * 1000
            
        except Exception as e:
            print(f"Librosa提取失败: {e}", file=sys.stderr)
            features.extractor = "librosa_error"
        
        return features
    
    def _estimate_valence(self, f: AudioFeatureSet) -> float:
        if f.spectral_centroid > 3000: return 0.3
        if f.spectral_centroid < 1500: return -0.3
        return 0.0
    
    def _estimate_arousal(self, f: AudioFeatureSet) -> float:
        a = 0.0
        if f.bpm > 130: a += 0.4
        elif f.bpm > 100: a += 0.1
        elif f.bpm < 80: a -= 0.3
        if f.energy > 0.05: a += 0.3
        elif f.energy < 0.01: a -= 0.3
        return max(-1.0, min(1.0, a))


class AudioFeatureExtractor:
    """统一音频特征提取器（自动选择最佳引擎）"""
    
    def __init__(self):
        self.essentia = EssentiaExtractor()
        self.librosa = LibrosaExtractor()
    
    def extract(self, audio_path: str) -> AudioFeatureSet:
        """提取音频特征（优先 Essentia，降级 librosa）"""
        if not os.path.exists(audio_path):
            return AudioFeatureSet(file_path=audio_path, extractor="file_not_found")
        
        # 优先使用 Essentia
        if self.essentia.is_available():
            return self.essentia.extract(audio_path)
        
        # 降级到 librosa
        if self.librosa.is_available():
            return self.librosa.extract(audio_path)
        
        # 都不可用
        return AudioFeatureSet(file_path=audio_path, extractor="none_available")
    
    def extract_batch(self, audio_paths: List[str]) -> List[Dict[str, Any]]:
        """批量提取音频特征"""
        results = []
        for path in audio_paths:
            features = self.extract(path)
            results.append(features.to_dict())
        return results
    
    def get_engine_info(self) -> Dict[str, Any]:
        """获取当前可用的引擎信息"""
        return {
            "essentia_available": self.essentia.is_available(),
            "librosa_available": self.librosa.is_available(),
            "recommended_engine": "essentia" if self.essentia.is_available() else ("librosa" if self.librosa.is_available() else "none"),
        }


def main() -> None:
    """主函数"""
    if len(sys.argv) < 2:
        print("用法: python audio_feature_extractor.py --json-input '<JSON字符串>'")
        sys.exit(1)
    
    if sys.argv[1] != "--json-input":
        print("错误: 必须使用 --json-input 参数")
        sys.exit(1)
    
    try:
        input_json = json.loads(sys.argv[2])
        action = input_json.get("action", "")
        
        result: Dict[str, Any] = {"success": False}
        
        if action == "extract":
            audio_path = input_json.get("audio_path", "")
            extractor = AudioFeatureExtractor()
            features = extractor.extract(audio_path)
            
            result["features"] = features.to_dict()
            result["success"] = True
        
        elif action == "extract_batch":
            audio_paths = input_json.get("audio_paths", [])
            extractor = AudioFeatureExtractor()
            results = extractor.extract_batch(audio_paths)
            
            result["results"] = results
            result["success"] = True
        
        elif action == "engine_info":
            extractor = AudioFeatureExtractor()
            result["engine_info"] = extractor.get_engine_info()
            result["success"] = True
        
        else:
            result["error"] = f"未知操作: {action}"
        
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    except json.JSONDecodeError as e:
        print(json.dumps({"success": False, "error": f"JSON解析错误: {str(e)}"}, ensure_ascii=False, indent=2))
        sys.exit(1)
    except Exception as e:
        print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    main()
