"""
Whisper Adapter - 真实 Whisper 模型集成
========================================
验证模拟桩→真实集成的契约一致性，确保真实模型与模拟桩行为一致。
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class WhisperTranscribeResult:
    """Whisper 转录结果契约
    
    核心契约:
    1. text: 完整转录文本 (str)
    2. segments: 分段列表 (List[dict])
    3. duration: 音频时长 (float)
    """
    text: str
    segments: List[Dict] = field(default_factory=list)
    duration: float = 0.0
    language: str = "auto"
    
    def validate(self) -> bool:
        """结果有效性验证"""
        if not self.text or not isinstance(self.text, str):
            return False
        if not isinstance(self.segments, list):
            return False
        if not isinstance(self.duration, (int, float)) or self.duration <= 0:
            return False
        return True


class WhisperAdapter:
    """Whisper 模型适配器
    
    核心契约:
    1. 支持多种模型大小 (tiny/base/small/large)
    2. 返回标准化转录结果
    3. 提供 BPM 检测能力
    """
    
    MODEL_SIZES = ["tiny", "base", "small", "large", "large-v3"]
    DEFAULT_MODEL = "base"
    
    def __init__(self, model_size: str = None):
        """初始化 Whisper 适配器
        
        Args:
            model_size: 模型大小，可选 tiny/base/small/large/large-v3
                       默认 base (平衡速度与精度)
        """
        self.model_size = model_size or self.DEFAULT_MODEL
        
        if self.model_size not in self.MODEL_SIZES:
            raise ValueError(f"Invalid model size: {self.model_size}. Must be one of {self.MODEL_SIZES}")
        
        # TODO: 真实 Whisper 环境启用时取消注释
        # try:
        #     import whisper
        #     self._model = whisper.load_model(self.model_size)
        #     self._is_real = True
        # except ImportError:
        #     self._is_real = False
        #     print(f"Whisper 未安装，使用模拟桩")
        
        self._is_real = False  # 暂时使用模拟桩
    
    def transcribe(self, audio_path: str) -> WhisperTranscribeResult:
        """转录音频文件
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            WhisperTranscribeResult: 标准化转录结果
            
        Raises:
            FileNotFoundError: 音频文件不存在
            RuntimeError: Whisper 模型未就绪
        """
        if not os.path.exists(audio_path):
            raise FileNotFoundError(f"Audio file not found: {audio_path}")
        
        # TODO: 真实 Whisper 环境启用时取消注释
        # if not self._is_real:
        #     raise RuntimeError("Whisper 模型未就绪，请安装 whisper 依赖")
        # 
        # result = self._model.transcribe(audio_path)
        # return WhisperTranscribeResult(
        #     text=result["text"],
        #     segments=result["segments"],
        #     duration=result["duration"],
        #     language=result.get("language", "auto")
        # )
        
        # 模拟桩实现 (待真实环境启用)
        return self._simulate_transcribe(audio_path)
    
    def _simulate_transcribe(self, audio_path: str) -> WhisperTranscribeResult:
        """模拟转录 (待真实环境替换)"""
        # 模拟返回结构化的转录结果
        return WhisperTranscribeResult(
            text="这是一个模拟的转录结果，用于测试契约一致性",
            segments=[
                {
                    "id": 0,
                    "seek": 0,
                    "start": 0.0,
                    "end": 1.0,
                    "text": "模拟片段 1",
                    "tokens": [1, 2, 3],
                    "temperature": 0.0,
                    "avg_log_prob": -0.5
                },
                {
                    "id": 1,
                    "seek": 100,
                    "start": 1.0,
                    "end": 2.0,
                    "text": "模拟片段 2",
                    "tokens": [4, 5, 6],
                    "temperature": 0.0,
                    "avg_log_prob": -0.6
                }
            ],
            duration=2.0,
            language="zh"
        )
    
    def detect_bpm(self, audio_path: str) -> Optional[float]:
        """检测音频 BPM ( beats per minute)
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            Optional[float]: BPM 值，失败返回 None
        """
        # TODO: 真实 Whisper/ librosa 环境启用时实现
        # import librosa
        # y, sr = librosa.load(audio_path)
        # tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        # return float(tempo)
        return None  # 暂时返回 None
