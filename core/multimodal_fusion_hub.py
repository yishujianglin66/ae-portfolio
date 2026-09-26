"""
core/multimodal_fusion_hub.py — 多模态融合决策中枢 v1.0
=========================================================

跨模态注意力融合 + 联合推理，驱动风格决策、阶段跳过和参数选择。

设计原则:
1. 离线可用: 轻量级特征提取（不依赖大型预训练模型）
2. 缺失鲁棒: 任意模态缺失时自动降级
3. 跨模态对齐: 时间轴自动对齐
4. 注意力融合: Cross-Attention 动态决定模态权重
5. 多决策头: 阶段跳过/效果选择/参数调节/质量阈值

集成方式:
    from core.multimodal_fusion_hub import get_fusion_hub

    hub = get_fusion_hub()
    embedding = await hub.encode_all(video_path="...", audio_path="...")
    decision = await hub.fused_decision(embedding, "skip_stage")
"""
from __future__ import annotations

import json
import logging
import math
import struct
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


# ============================================================================
#  数据结构
# ============================================================================

@dataclass
class VisualFeatures:
    """视觉特征"""
    # 全局特征
    color_distribution: np.ndarray = field(default_factory=lambda: np.zeros(12))  # RGB 直方图
    brightness_mean: float = 0.0
    contrast: float = 0.0
    saturation: float = 0.0
    
    # 运动特征
    motion_intensity: float = 0.0       # 运动强度 [0, 1]
    scene_change_frequency: float = 0.0 # 场景切换频率
    camera_movement: str = "static"     # static / pan / tilt / zoom
    # TemporalAnalyzer 精细运动特征
    avg_magnitude: float = 0.0          # 平均光流幅度
    shake_score: float = 0.0            # 抖动评分 [0, 1]
    shot_count: int = 0                 # 镜头数
    asl: float = 0.0                    # 平均镜头长度
    rhythm_pattern: str = "uniform"     # uniform/accelerating/decelerating/irregular
    motion_curve: list = None           # 运动曲线
    arc_shape: str = "unknown"          # peak/valley/rising/falling/flat/wave
    
    # 情感特征
    visual_mood: str = "neutral"        # energetic / dark / warm / cool / neutral
    visual_energy: float = 0.5          # [0, 1]
    
    # 嵌入向量
    embedding: np.ndarray = field(default_factory=lambda: np.zeros(64))
    confidence: float = 0.0
    available: bool = False


@dataclass
class AudioFeatures:
    """音频特征"""
    # 节奏特征
    bpm: float = 120.0
    beat_strength: float = 0.5          # [0, 1]
    rhythm_regularity: float = 0.5      # [0, 1]
    
    # 频谱特征
    spectral_centroid: float = 0.0
    spectral_rolloff: float = 0.0
    energy_curve: np.ndarray = field(default_factory=lambda: np.zeros(10))  # 10段能量
    
    # 情感特征
    audio_mood: str = "neutral"         # energetic / melancholic / tense / calm
    audio_energy: float = 0.5
    
    # 语音特征
    has_speech: bool = False
    speech_ratio: float = 0.0
    
    # 嵌入向量
    embedding: np.ndarray = field(default_factory=lambda: np.zeros(64))
    confidence: float = 0.0
    available: bool = False


@dataclass
class TextFeatures:
    """文本特征"""
    style_description: str = ""
    keywords: list[str] = field(default_factory=list)
    
    # 语义特征
    style_category: str = ""            # energetic / cinematic / minimal / vintage
    target_audience: str = ""           # young / general / professional
    
    # 嵌入向量
    embedding: np.ndarray = field(default_factory=lambda: np.zeros(64))
    confidence: float = 0.0
    available: bool = False


@dataclass
class MultimodalEmbedding:
    """多模态融合嵌入"""
    visual: VisualFeatures = field(default_factory=VisualFeatures)
    audio: AudioFeatures = field(default_factory=AudioFeatures)
    text: TextFeatures = field(default_factory=TextFeatures)
    
    # 融合后的嵌入
    fused_embedding: np.ndarray = field(default_factory=lambda: np.zeros(128))
    modality_weights: dict[str, float] = field(default_factory=dict)
    alignment_quality: float = 0.0      # 跨模态对齐质量


@dataclass
class FusedDecision:
    """融合决策结果"""
    decision_type: str                   # skip_stage / select_effect / tune_params / quality_threshold
    decision: Any = None                 # 具体决策值
    confidence: float = 0.0
    modality_contributions: dict[str, float] = field(default_factory=dict)
    reasoning: str = ""
    alternatives: list[tuple[Any, float]] = field(default_factory=list)


# ============================================================================
#  L2.1: 视觉特征提取器
# ============================================================================

class VisualFeatureExtractor:
    """轻量级视觉特征提取器
    
    不依赖大型预训练模型，使用 numpy + 简单图像处理:
    - 颜色直方图分析
    - 帧间差分（运动检测）
    - 亮度/对比度统计
    - 简化 CLIP 风格嵌入（随机投影近似）
    """
    
    EMBEDDING_DIM = 64
    
    def __init__(self):
        # 随机投影矩阵（使用独立 RandomState，避免污染全局随机种子）
        rng = np.random.RandomState(42)
        self._projection = rng.randn(256, self.EMBEDDING_DIM) / math.sqrt(256)
    
    async def extract(self, video_path: str | None = None,
                      image_paths: list[str] | None = None,
                      frame_data: np.ndarray | None = None
                      ) -> VisualFeatures:
        """提取视觉特征"""
        features = VisualFeatures()
        
        try:
            if frame_data is not None:
                features = self._extract_from_array(frame_data)
            elif video_path and Path(video_path).exists():
                features = await self._extract_from_video(video_path)
            elif image_paths:
                features = await self._extract_from_images(image_paths)
            else:
                return features
            
            # FIX-04/契约 §4：不再无条件置 available=True+confidence 0.7——
            # 仅子路径自身声明做了真实内容计算（array 路径）才放行；
            # video/images 路径为文件大小启发式，已在各自函数内标 available=False。
            if features.available:
                features.confidence = 0.7
            
        except Exception as e:
            logger.warning(f"[VisualExtractor] 提取失败: {e}")
            features.confidence = 0.0
        
        return features
    
    def _extract_from_array(self, frame: np.ndarray) -> VisualFeatures:
        """从 numpy 数组提取特征"""
        features = VisualFeatures()
        
        if frame.ndim == 3:
            h, w, c = frame.shape
        elif frame.ndim == 2:
            h, w = frame.shape
            c = 1
        else:
            return features
        
        # 颜色统计
        if c >= 3:
            r, g, b = frame[:,:,0].astype(float), frame[:,:,1].astype(float), frame[:,:,2].astype(float)
            features.brightness_mean = float(np.mean(frame)) / 255.0
            features.contrast = float(np.std(frame)) / 128.0
            
            # 饱和度近似
            max_c = np.maximum(np.maximum(r, g), b)
            min_c = np.minimum(np.minimum(r, g), b)
            features.saturation = float(np.mean(max_c - min_c)) / 255.0
            
            # 颜色分布 (简化RGB直方图)
            for i, channel in enumerate([r, g, b]):
                hist, _ = np.histogram(channel, bins=4, range=(0, 256))
                features.color_distribution[i*4:(i+1)*4] = hist / max(np.sum(hist), 1)
        
        # 运动特征（单帧无法计算，给默认值）
        features.motion_intensity = 0.5
        features.visual_energy = features.brightness_mean * features.contrast
        
        # 视觉情绪推断
        if features.visual_energy > 0.4:
            features.visual_mood = "energetic"
        elif features.brightness_mean < 0.3:
            features.visual_mood = "dark"
        elif features.saturation > 0.5:
            features.visual_mood = "warm"
        else:
            features.visual_mood = "neutral"
        
        # 生成嵌入
        raw_features = self._build_raw_features(frame)
        features.embedding = raw_features @ self._projection
        norm = np.linalg.norm(features.embedding)
        if norm > 0:
            features.embedding /= norm
        
        features.available = True
        return features
    
    def _build_raw_features(self, frame: np.ndarray) -> np.ndarray:
        """构建原始特征向量（256维）"""
        # 下采样到 16x16
        h, w = frame.shape[:2]
        block_h, block_w = max(1, h // 16), max(1, w // 16)
        
        features = []
        for i in range(16):
            for j in range(16):
                block = frame[i*block_h:(i+1)*block_h, j*block_w:(j+1)*block_w]
                features.append(np.mean(block))
        
        return np.array(features) / 255.0
    
    async def _extract_from_video(self, video_path: str) -> VisualFeatures:
        """从视频文件提取特征 — ⚠ 未解码视频，仅文件大小启发式（FIX-04 诚实化）

        旧实现在此伪造亮度/对比度常量与随机嵌入却返回 available=True+confidence=0.7，
        使随机特征参与 fused_decision 真实决策（0924 审计 F4）。现改为 available=False，
        融合层（按其门控）将自动排除本模态；需真实视觉分析请接 models/ CNN 链路。
        """
        # 简化: 读取文件头获取基本信息
        file_size = Path(video_path).stat().st_size
        
        # 基于文件大小估算特征（启发式，非内容分析）
        features = VisualFeatures()
        features.brightness_mean = 0.5
        features.contrast = 0.3
        features.motion_intensity = min(1.0, file_size / (100 * 1024 * 1024))
        features.visual_energy = features.brightness_mean * features.motion_intensity
        
        # 生成嵌入（随机占位，仅供结构完整；不得参与决策）
        raw = np.random.randn(256) * 0.1  # 简化: 用随机特征近似
        raw[0] = features.brightness_mean
        raw[1] = features.contrast
        raw[2] = features.motion_intensity
        features.embedding = raw @ self._projection
        norm = np.linalg.norm(features.embedding)
        if norm > 0:
            features.embedding /= norm
        
        features.available = False   # FIX-04/契约 §4：不解码内容不得声称可用
        features.confidence = 0.0
        logger.warning("[VisualExtractor] video 路径为文件大小启发式，未解码内容 → 标 unavailable")
        return features
    
    async def _extract_from_images(self, image_paths: list[str]) -> VisualFeatures:
        """从图片列表提取特征 — ⚠ 未读像素，仅文件总大小启发式（FIX-04 诚实化）"""
        features = VisualFeatures()
        
        total_size = sum(Path(p).stat().st_size for p in image_paths if Path(p).exists())
        features.brightness_mean = 0.5
        features.contrast = min(1.0, total_size / (50 * 1024 * 1024))
        features.motion_intensity = 0.0  # 图片无运动
        features.visual_energy = features.contrast
        
        raw = np.random.randn(256) * 0.1
        raw[0] = features.brightness_mean
        raw[1] = features.contrast
        features.embedding = raw @ self._projection
        norm = np.linalg.norm(features.embedding)
        if norm > 0:
            features.embedding /= norm
        
        features.available = False   # FIX-04/契约 §4
        features.confidence = 0.0
        return features


# ============================================================================
#  L2.2: 音频特征提取器
# ============================================================================

class AudioFeatureExtractor:
    """轻量级音频特征提取器
    
    不依赖 PANNs 等大型模型，使用 numpy + 简单信号处理:
    - 过零率（节奏近似）
    - 能量包络
    - 频谱质心近似
    """
    
    EMBEDDING_DIM = 64
    
    def __init__(self):
        np.random.seed(43)
        self._projection = np.random.randn(256, self.EMBEDDING_DIM) / math.sqrt(256)
    
    async def extract(self, audio_path: str | None = None,
                      audio_data: np.ndarray | None = None,
                      sample_rate: int = 44100) -> AudioFeatures:
        """提取音频特征"""
        features = AudioFeatures()
        
        try:
            if audio_data is not None:
                features = self._extract_from_array(audio_data, sample_rate)
            elif audio_path and Path(audio_path).exists():
                features = await self._extract_from_file(audio_path)
            else:
                return features
            
            if features.available:
                features.confidence = 0.7
            
        except Exception as e:
            logger.warning(f"[AudioExtractor] 提取失败: {e}")
            features.confidence = 0.0
        
        return features
    
    def _extract_from_array(self, audio: np.ndarray, sr: int) -> AudioFeatures:
        """从音频数组提取特征"""
        features = AudioFeatures()
        
        if audio.ndim > 1:
            audio = np.mean(audio, axis=1)
        
        # 能量包络
        frame_size = sr // 10  # 100ms 帧
        n_frames = len(audio) // frame_size
        energy = np.zeros(min(n_frames, 10))
        for i in range(len(energy)):
            frame = audio[i*frame_size:(i+1)*frame_size]
            energy[i] = np.mean(frame ** 2)
        
        features.energy_curve = energy / max(np.max(energy), 1e-10)
        
        # BPM 近似（基于能量峰值间隔）
        if len(energy) > 2:
            peaks = np.where(energy > np.mean(energy) * 1.5)[0]
            if len(peaks) > 1:
                intervals = np.diff(peaks)
                avg_interval = np.mean(intervals) * 0.1  # 100ms 帧 → 秒
                if avg_interval > 0:
                    features.bpm = min(200, 60.0 / avg_interval)
        
        # 过零率（高频内容近似）
        zcr = np.sum(np.abs(np.diff(np.sign(audio)))) / (2 * len(audio))
        features.spectral_centroid = zcr * sr / 2
        
        # 节拍强度
        features.beat_strength = float(np.std(energy)) / max(np.mean(energy), 1e-10)
        features.beat_strength = min(1.0, features.beat_strength)
        
        # 节奏规律性
        if len(energy) > 2:
            features.rhythm_regularity = 1.0 - float(np.std(np.diff(energy))) / max(float(np.mean(np.abs(np.diff(energy)))), 1e-10)
            features.rhythm_regularity = float(np.clip(features.rhythm_regularity, 0, 1))
        
        # 音频情绪
        if features.beat_strength > 0.5 and features.bpm > 120:
            features.audio_mood = "energetic"
        elif features.bpm < 80:
            features.audio_mood = "calm"
        else:
            features.audio_mood = "neutral"
        
        features.audio_energy = features.beat_strength * 0.5 + float(np.mean(energy)) * 0.5
        
        # 嵌入
        raw = np.zeros(256)
        raw[0] = features.bpm / 200.0
        raw[1] = features.beat_strength
        raw[2] = features.rhythm_regularity
        raw[3:13] = features.energy_curve
        raw[13] = features.audio_energy
        features.embedding = raw @ self._projection
        norm = np.linalg.norm(features.embedding)
        if norm > 0:
            features.embedding /= norm
        
        features.available = True
        return features
    
    async def _extract_from_file(self, audio_path: str) -> AudioFeatures:
        """从音频文件提取 — ⚠ 未解码音频，bpm=120 常量+文件大小启发式（FIX-04 诚实化，契约 §4）。

        旧实现与真实信号分析（_extract_from_array）同构且 available=True，下游无法分辨；
        现标 unavailable，需真实音频分析请传 audio_data 或接 librosa/core.audio_edit_engine 链路。
        """
        file_size = Path(audio_path).stat().st_size
        
        features = AudioFeatures()
        features.bpm = 120.0
        features.beat_strength = min(1.0, file_size / (50 * 1024 * 1024))
        features.audio_energy = features.beat_strength
        features.energy_curve = np.ones(10) * 0.5
        
        raw = np.zeros(256)
        raw[0] = features.bpm / 200.0
        raw[1] = features.beat_strength
        features.embedding = raw @ self._projection
        norm = np.linalg.norm(features.embedding)
        if norm > 0:
            features.embedding /= norm
        
        features.available = False   # FIX-04/契约 §4：伪造分析不得声称可用
        features.confidence = 0.0
        return features


# ============================================================================
#  L2.3: 文本特征提取器
# ============================================================================

class TextFeatureExtractor:
    """轻量级文本特征提取器
    
    基于关键词匹配 + 哈希嵌入（不依赖大型语言模型）
    """
    
    EMBEDDING_DIM = 64
    
    # 风格关键词映射
    STYLE_KEYWORDS: dict[str, list[str]] = {
        "energetic": ["燃", "热血", "高燃", "节奏", "快速", "energetic", "dynamic", "intense", "powerful"],
        "cinematic": ["电影", "cinematic", "cinema", "epic", "dramatic", "宏大", "叙事"],
        "minimal": ["简约", "minimal", "clean", "simple", "极简", "干净"],
        "vintage": ["复古", "vintage", "retro", "怀旧", "胶片", "film"],
        "dark": ["暗黑", "dark", "gothic", "哥特", "阴暗", "神秘"],
        "warm": ["温暖", "warm", "温馨", "治愈", "柔和", "soft"],
    }
    
    PLATFORM_KEYWORDS: dict[str, list[str]] = {
        "bilibili": ["b站", "bilibili", "二次元", "动漫"],
        "douyin": ["抖音", "douyin", "竖屏", "短视频"],
        "youtube": ["youtube", "油管", "横屏"],
    }
    
    def __init__(self):
        np.random.seed(44)
        self._projection = np.random.randn(256, self.EMBEDDING_DIM) / math.sqrt(256)
    
    async def extract(self, text: str | None = None) -> TextFeatures:
        """提取文本特征"""
        features = TextFeatures()
        
        if not text:
            return features
        
        text_lower = text.lower()
        features.style_description = text
        features.available = True
        features.confidence = 0.8
        
        # 风格分类
        style_scores: dict[str, int] = {}
        for style, keywords in self.STYLE_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                style_scores[style] = score
        
        if style_scores:
            features.style_category = max(style_scores, key=style_scores.get)
        else:
            features.style_category = "neutral"
        
        # 平台识别
        for platform, keywords in self.PLATFORM_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                features.target_audience = platform
                break
        
        # 关键词提取（简化: 按空格/逗号分词，取高频词）
        words = text_lower.replace(",", " ").replace("，", " ").split()
        features.keywords = [w for w in words if len(w) > 1][:10]
        
        # 嵌入
        raw = np.zeros(256)
        for i, kw in enumerate(features.keywords[:8]):
            h = hash(kw) % 256
            raw[h] += 1.0
        
        # 风格编码
        style_idx = list(self.STYLE_KEYWORDS.keys()).index(features.style_category) if features.style_category in self.STYLE_KEYWORDS else 0
        raw[style_idx * 32:(style_idx + 1) * 32] += 0.5
        
        features.embedding = raw @ self._projection
        norm = np.linalg.norm(features.embedding)
        if norm > 0:
            features.embedding /= norm
        
        return features


# ============================================================================
#  L2.4: 跨模态注意力融合层
# ============================================================================

class CrossModalAttention:
    """跨模态注意力融合层
    
    轻量级实现: 以任务 query 对各模态特征做缩放点积注意力
    """
    
    def __init__(self, d_model: int = 64, n_heads: int = 4):
        self._d_model = d_model
        self._n_heads = n_heads
        self._d_k = d_model // n_heads
        
        # 可学习参数（简化: 随机初始化）
        np.random.seed(45)
        scale = 1.0 / math.sqrt(d_model)
        self._W_q = np.random.randn(d_model, d_model) * scale
        self._W_k = np.random.randn(d_model, d_model) * scale
        self._W_v = np.random.randn(d_model, d_model) * scale
        self._W_o = np.random.randn(d_model, d_model) * scale
    
    def forward(
        self,
        query: np.ndarray,
        keys: list[np.ndarray],
        values: list[np.ndarray],
        modality_mask: list[bool] | None = None
    ) -> tuple[np.ndarray, np.ndarray]:
        """前向传播
        
        Args:
            query: (d_model,) 任务查询向量
            keys: List[(d_model,)] 各模态 key
            values: List[(d_model,)] 各模态 value
            modality_mask: List[bool] 各模态是否可用
            
        Returns:
            output: (d_model,) 融合输出
            attention_weights: (n_modalities,) 注意力权重
        """
        n = len(keys)
        if n == 0:
            return np.zeros(self._d_model), np.array([])
        
        # 线性变换
        q = query @ self._W_q  # (d_model,)
        
        # 计算注意力分数
        scores = np.zeros(n)
        for i in range(n):
            if modality_mask and not modality_mask[i]:
                scores[i] = -1e9  # mask 掉不可用模态
                continue
            k = keys[i] @ self._W_k
            scores[i] = np.dot(q, k) / math.sqrt(self._d_k)
        
        # Softmax
        exp_scores = np.exp(scores - np.max(scores))
        weights = exp_scores / max(np.sum(exp_scores), 1e-10)
        
        # 加权求和
        output = np.zeros(self._d_model)
        for i in range(n):
            v = values[i] @ self._W_v
            output += weights[i] * v
        
        # 输出投影
        output = output @ self._W_o
        
        return output, weights


# ============================================================================
#  L2.6: 决策头
# ============================================================================

class DecisionHead:
    """多任务决策头"""
    
    def __init__(self, input_dim: int = 128):
        np.random.seed(46)
        scale = 1.0 / math.sqrt(input_dim)
        
        # 各决策头的权重
        self._skip_weights = np.random.randn(input_dim) * scale
        self._effect_weights = np.random.randn(input_dim, 8) * scale  # 8种效果类型
        self._param_weights = np.random.randn(input_dim, 5) * scale   # 5个参数维度
        self._quality_weight = np.random.randn(input_dim) * scale
    
    def predict_skip_stage(self, embedding: np.ndarray) -> tuple[bool, float]:
        """预测是否应跳过某阶段"""
        score = float(np.dot(embedding, self._skip_weights))
        prob = 1.0 / (1.0 + math.exp(-score))  # sigmoid
        return prob > 0.6, prob
    
    def predict_effect_selection(self, embedding: np.ndarray
                                  ) -> list[tuple[str, float]]:
        """预测效果选择"""
        scores = embedding @ self._effect_weights
        # softmax
        exp_scores = np.exp(scores - np.max(scores))
        probs = exp_scores / np.sum(exp_scores)
        
        effect_names = ["glow", "blur", "color", "transition", "particle",
                       "shake", "zoom", "flash"]
        return [(name, float(probs[i])) for i, name in enumerate(effect_names)]
    
    def predict_parameter_adjustment(self, embedding: np.ndarray
                                      ) -> dict[str, float]:
        """预测参数调整"""
        adjustments = embedding @ self._param_weights
        param_names = ["intensity", "speed", "size", "threshold", "duration"]
        return {name: float(np.clip(adj, -1, 1))
                for name, adj in zip(param_names, adjustments)}
    
    def predict_quality_threshold(self, embedding: np.ndarray) -> float:
        """预测质量阈值"""
        score = float(np.dot(embedding, self._quality_weight))
        return float(np.clip(1.0 / (1.0 + math.exp(-score)), 0, 1))


# ============================================================================
#  主中枢: MultimodalFusionHub
# ============================================================================

class MultimodalFusionHub:
    """多模态融合决策中枢"""
    
    DEFAULT_DATA_DIR = "data/multimodal_hub"
    
    def __init__(self, data_dir: str = DEFAULT_DATA_DIR):
        self._data_dir = Path(data_dir)
        self._data_dir.mkdir(parents=True, exist_ok=True)
        
        # 特征提取器
        self._visual_extractor = VisualFeatureExtractor()
        self._audio_extractor = AudioFeatureExtractor()
        self._text_extractor = TextFeatureExtractor()
        
        # 融合层
        self._attention = CrossModalAttention(d_model=64, n_heads=4)
        
        # 决策头
        self._decision_head = DecisionHead(input_dim=128)
        
        # 特征缓存
        self._cache: dict[str, Any] = {}
    
    # ----------------------------------------------------------------
    #  多模态编码
    # ----------------------------------------------------------------
    
    async def encode_all(
        self,
        video_path: str | None = None,
        audio_path: str | None = None,
        text_description: str | None = None,
        image_paths: list[str] | None = None,
        frame_data: np.ndarray | None = None,
        audio_data: np.ndarray | None = None
    ) -> MultimodalEmbedding:
        """多模态编码（支持任意模态组合）"""
        embedding = MultimodalEmbedding()
        
        # 并行提取各模态特征
        import asyncio
        
        tasks = []
        
        # 视觉
        if video_path or image_paths or frame_data is not None:
            tasks.append(("visual", self._visual_extractor.extract(
                video_path=video_path, image_paths=image_paths, frame_data=frame_data
            )))
        
        # 音频
        if audio_path or audio_data is not None:
            tasks.append(("audio", self._audio_extractor.extract(
                audio_path=audio_path, audio_data=audio_data
            )))
        
        # 文本
        if text_description:
            tasks.append(("text", self._text_extractor.extract(text=text_description)))
        
        if tasks:
            results = await asyncio.gather(*[t for _, t in tasks], return_exceptions=True)
            
            for (modality, _), result in zip(tasks, results):
                if isinstance(result, Exception):
                    logger.warning(f"[FusionHub] {modality} 提取失败: {result}")
                    continue
                
                if modality == "visual":
                    embedding.visual = result
                elif modality == "audio":
                    embedding.audio = result
                elif modality == "text":
                    embedding.text = result
        
        # 跨模态融合
        embedding.fused_embedding = self._fuse_embeddings(embedding)
        embedding.modality_weights = self._compute_modality_weights(embedding)
        embedding.alignment_quality = self._compute_alignment_quality(embedding)
        
        return embedding
    
    def _fuse_embeddings(self, embedding: MultimodalEmbedding) -> np.ndarray:
        """融合各模态嵌入"""
        available = []
        masks = []
        
        if embedding.visual.available:
            available.append(embedding.visual.embedding)
            masks.append(True)
        if embedding.audio.available:
            available.append(embedding.audio.embedding)
            masks.append(True)
        if embedding.text.available:
            available.append(embedding.text.embedding)
            masks.append(True)
        
        if not available:
            return np.zeros(128)
        
        # 使用注意力融合
        query = np.zeros(64)  # 默认查询
        if embedding.text.available:
            query = embedding.text.embedding[:64]
        
        keys = [v[:64] for v in available]
        values = [v[:64] for v in available]
        
        fused_64, weights = self._attention.forward(query, keys, values, masks)
        
        # 拼接原始特征（128维）
        raw_concat = np.zeros(128)
        idx = 0
        for v in available:
            end = min(idx + 64, 128)
            raw_concat[idx:end] = v[:end - idx]
            idx = end
        
        # 融合嵌入 = attention 输出 + 原始拼接 的混合
        fused = np.zeros(128)
        fused[:64] = fused_64
        fused[64:] = raw_concat[64:]
        
        return fused
    
    def _compute_modality_weights(self, embedding: MultimodalEmbedding
                                   ) -> dict[str, float]:
        """计算模态权重"""
        weights = {}
        total = 0.0
        
        if embedding.visual.available:
            w = embedding.visual.confidence
            weights["visual"] = w
            total += w
        if embedding.audio.available:
            w = embedding.audio.confidence
            weights["audio"] = w
            total += w
        if embedding.text.available:
            w = embedding.text.confidence
            weights["text"] = w
            total += w
        
        # 归一化
        if total > 0:
            for k in weights:
                weights[k] /= total
        
        return weights
    
    def _compute_alignment_quality(self, embedding: MultimodalEmbedding) -> float:
        """计算跨模态对齐质量"""
        available_embeddings = []
        if embedding.visual.available:
            available_embeddings.append(embedding.visual.embedding)
        if embedding.audio.available:
            available_embeddings.append(embedding.audio.embedding)
        if embedding.text.available:
            available_embeddings.append(embedding.text.embedding)
        
        if len(available_embeddings) < 2:
            return 0.5  # 单模态默认对齐质量
        
        # 计算模态间余弦相似度的平均值
        similarities = []
        for i in range(len(available_embeddings)):
            for j in range(i + 1, len(available_embeddings)):
                a = available_embeddings[i]
                b = available_embeddings[j]
                norm_a = np.linalg.norm(a)
                norm_b = np.linalg.norm(b)
                if norm_a > 0 and norm_b > 0:
                    sim = np.dot(a, b) / (norm_a * norm_b)
                    similarities.append(abs(sim))
        
        return float(np.mean(similarities)) if similarities else 0.5
    
    # ----------------------------------------------------------------
    #  L2.5: 缺失模态鲁棒推理
    # ----------------------------------------------------------------
    
    def _adaptive_modality_weighting(
        self, embedding: MultimodalEmbedding
    ) -> dict[str, float]:
        """自适应模态加权（缺失模态鲁棒）"""
        weights = {}
        
        # 可用模态
        available = {}
        if embedding.visual.available:
            available["visual"] = embedding.visual.confidence
        if embedding.audio.available:
            available["audio"] = embedding.audio.confidence
        if embedding.text.available:
            available["text"] = embedding.text.confidence
        
        if not available:
            return {"visual": 0.33, "audio": 0.33, "text": 0.34}
        
        # 重新归一化
        total = sum(available.values())
        for mod, conf in available.items():
            weights[mod] = conf / max(total, 1e-10)
        
        # 不可用模态权重为0
        for mod in ["visual", "audio", "text"]:
            if mod not in weights:
                weights[mod] = 0.0
        
        return weights
    
    # ----------------------------------------------------------------
    #  融合决策
    # ----------------------------------------------------------------
    
    async def fused_decision(
        self,
        embedding: MultimodalEmbedding,
        decision_type: str,
        context: dict[str, Any] | None = None
    ) -> FusedDecision:
        """跨模态融合决策"""
        fused = embedding.fused_embedding
        
        if decision_type == "skip_stage":
            skip, prob = self._decision_head.predict_skip_stage(fused)
            return FusedDecision(
                decision_type=decision_type,
                decision=skip,
                confidence=prob,
                modality_contributions=embedding.modality_weights,
                reasoning=f"多模态融合决策: skip={skip} (prob={prob:.3f})"
            )
        
        elif decision_type == "select_effect":
            effects = self._decision_head.predict_effect_selection(fused)
            top_effects = sorted(effects, key=lambda x: -x[1])[:3]
            return FusedDecision(
                decision_type=decision_type,
                decision=top_effects[0][0] if top_effects else "none",
                confidence=top_effects[0][1] if top_effects else 0.0,
                modality_contributions=embedding.modality_weights,
                reasoning=f"效果选择: {', '.join(f'{n}({p:.2f})' for n, p in top_effects)}",
                alternatives=[(n, p) for n, p in top_effects[1:]]
            )
        
        elif decision_type == "tune_params":
            adjustments = self._decision_head.predict_parameter_adjustment(fused)
            # 找到最大调整方向
            max_param = max(adjustments, key=lambda k: abs(adjustments[k]))
            return FusedDecision(
                decision_type=decision_type,
                decision=adjustments,
                confidence=abs(adjustments[max_param]),
                modality_contributions=embedding.modality_weights,
                reasoning=f"参数调整: {max_param}={adjustments[max_param]:+.3f}"
            )
        
        elif decision_type == "quality_threshold":
            threshold = self._decision_head.predict_quality_threshold(fused)
            return FusedDecision(
                decision_type=decision_type,
                decision=threshold,
                confidence=0.6,
                modality_contributions=embedding.modality_weights,
                reasoning=f"质量阈值: {threshold:.3f}"
            )
        
        else:
            return FusedDecision(
                decision_type=decision_type,
                decision=None,
                confidence=0.0,
                reasoning=f"未知决策类型: {decision_type}"
            )
    
    # ----------------------------------------------------------------
    #  缓存 / 决策持久化
    # ----------------------------------------------------------------

    def save_cache(self, path: str | None = None) -> str:
        """把特征缓存写到 data_dir/cache.json，返回落盘路径。"""
        target = Path(path) if path else self._data_dir / "cache.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=2)
        return str(target)

    def load_cache(self, path: str | None = None) -> dict[str, Any]:
        """从 data_dir/cache.json 读回特征缓存（文件不存在返回空 dict）。"""
        source = Path(path) if path else self._data_dir / "cache.json"
        if not source.is_file():
            return {}
        with open(source, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._cache = data if isinstance(data, dict) else {}
        return self._cache

    def record_decision(self, decision: FusedDecision) -> None:
        """把一次融合决策追加写盘（JSON Lines）。"""
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "decision_type": decision.decision_type,
            "decision": decision.decision,
            "confidence": decision.confidence,
            "modality_contributions": decision.modality_contributions,
            "reasoning": decision.reasoning,
        }
        try:
            with open(self._data_dir / "decisions.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass

    def get_decisions(self, limit: int = 100) -> list[dict[str, Any]]:
        """读取最近 limit 条融合决策。"""
        path = self._data_dir / "decisions.jsonl"
        if not path.is_file():
            return []
        lines: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    lines.append(json.loads(line))
                except ValueError:
                    continue
        return lines[-limit:]

    def clear_decisions(self) -> None:
        """清空融合决策日志。"""
        path = self._data_dir / "decisions.jsonl"
        if path.is_file():
            path.unlink()

    # ----------------------------------------------------------------
    #  统计
    # ----------------------------------------------------------------

    def get_statistics(self) -> dict[str, Any]:
        return {
            "cache_size": len(self._cache),
            "attention_heads": self._attention._n_heads,
            "embedding_dim": 128,
        }


# ============================================================================
#  全局单例
# ============================================================================

_global_hub: MultimodalFusionHub | None = None


def get_fusion_hub(data_dir: str = MultimodalFusionHub.DEFAULT_DATA_DIR
                   ) -> MultimodalFusionHub:
    """获取全局融合中枢单例

    FIX-04：旧文件尾部存在 3 份逐字重复定义（后定义静默覆盖前两者）——已去重保留唯一实现。
    """
    global _global_hub
    if _global_hub is None:
        _global_hub = MultimodalFusionHub(data_dir)
    return _global_hub
