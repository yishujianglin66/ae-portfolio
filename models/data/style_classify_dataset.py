"""
风格分类数据集 - 用于视频风格分类小模型
数据格式：{ "features": [...], "label": "cinematic" }
支持从风格指纹 JSON 加载和数据增强
参考 Antares 哲学：用高质量特征数据训练小模型，精悍够用
"""
import json
import os
import random
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from .dataset_base import BaseDataset, DatasetConfig, DatasetStats

logger = logging.getLogger(__name__)


@dataclass
class StyleSample:
    """风格分类样本"""
    features: List[float]
    """特征向量（风格指纹）"""
    label: str
    """风格标签"""
    feature_dim: int = 0
    """特征维度"""
    metadata: Dict[str, Any] = None
    """元数据"""

    def __post_init__(self):
        if self.feature_dim == 0:
            self.feature_dim = len(self.features)
        if self.metadata is None:
            self.metadata = {}


class StyleClassifyDataset(BaseDataset):
    """风格分类数据集
    
    用于训练视频风格分类小模型。
    支持：
    - 从风格指纹 JSON 文件加载
    - 数据增强（特征噪声、亮度微调等）
    - 标签分布统计
    
    参考 Antares 哲学：高质量特征 + 小模型 = 高效分类
    """

    STYLE_LABELS = [
        "cinematic",
        "anime_puppet",
        "fast_cut",
        "slow_cut",
        "glitch_digital",
        "audio_visual",
        "particle_ambient",
        "text_animation",
        "3d_spatial",
        "realistic_color",
        "high_dynamic",
        "dark_tone",
        "low_saturation",
        "高饱和",
        "长镜头",
        # 漫剪 (AMV/MAD) 专属标签
        "amv_pull_zoom",
        "amv_fast_cut",
        "amv_beat_sync",
        "amv_korean_flash",
        "amv_glitch",
        "amv_cinematic",
        "amv_3d_spatial",
        "amv_high_burn",
    ]

    def __init__(self, config: DatasetConfig):
        """初始化风格分类数据集
        
        Args:
            config: 数据集配置
        """
        super().__init__(config)
        self._label_to_idx: Dict[str, int] = {}
        self._idx_to_label: Dict[int, str] = {}
        self._feature_dim: int = 0
        self._build_label_mapping()

    def _build_label_mapping(self) -> None:
        """构建标签映射"""
        for idx, label in enumerate(self.STYLE_LABELS):
            self._label_to_idx[label] = idx
            self._idx_to_label[idx] = label

    def load_data(self, data_path: str) -> List[StyleSample]:
        """从 JSON 文件加载风格指纹数据
        
        Args:
            data_path: JSON 文件路径或目录
            
        Returns:
            List[StyleSample]: 样本列表
        """
        samples = []
        
        if os.path.isdir(data_path):
            for filename in os.listdir(data_path):
                if filename.endswith('.json') or filename.endswith('.jsonl'):
                    filepath = os.path.join(data_path, filename)
                    samples.extend(self._load_file(filepath))
        else:
            samples.extend(self._load_file(data_path))
        
        if samples:
            self._feature_dim = samples[0].feature_dim
            logger.info(f"Feature dimension: {self._feature_dim}")
        
        return samples

    def _load_file(self, filepath: str) -> List[StyleSample]:
        """加载单个文件
        
        Args:
            filepath: 文件路径
            
        Returns:
            List[StyleSample]: 样本列表
        """
        samples = []
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                if filepath.endswith('.jsonl'):
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                            sample = self._dict_to_sample(data)
                            if sample:
                                samples.append(sample)
                        except json.JSONDecodeError as e:
                            logger.warning(f"JSON parse error at line {line_num}: {e}")
                else:
                    data = json.load(f)
                    if isinstance(data, list):
                        for item in data:
                            sample = self._dict_to_sample(item)
                            if sample:
                                samples.append(sample)
                    elif isinstance(data, dict):
                        if 'samples' in data and isinstance(data['samples'], list):
                            for item in data['samples']:
                                sample = self._dict_to_sample(item)
                                if sample:
                                    samples.append(sample)
                        else:
                            sample = self._dict_to_sample(data)
                            if sample:
                                samples.append(sample)
        except Exception as e:
            logger.error(f"Failed to load file {filepath}: {e}")
        
        return samples

    def _dict_to_sample(self, data: Dict[str, Any]) -> Optional[StyleSample]:
        """将字典转换为 StyleSample
        
        Args:
            data: 数据字典
            
        Returns:
            Optional[StyleSample]: 样本对象，格式错误返回 None
        """
        try:
            features = data.get('features', data.get('fingerprint', data.get('embedding', [])))
            label = data.get('label', data.get('style', data.get('category', '')))
            
            if not features or not label:
                return None
            
            if not isinstance(features, list):
                return None
            
            if len(features) == 0:
                return None
            
            if label not in self._label_to_idx:
                logger.debug(f"Unknown label: {label}, skipping")
                return None
            
            metadata = {k: v for k, v in data.items() 
                       if k not in ('features', 'fingerprint', 'embedding', 'label', 'style', 'category')}
            
            return StyleSample(
                features=features,
                label=label,
                feature_dim=len(features),
                metadata=metadata
            )
        except Exception:
            return None

    def preprocess(self, data: List[StyleSample]) -> List[StyleSample]:
        """数据预处理
        
        标准化特征维度，归一化等。
        
        Args:
            data: 原始数据
            
        Returns:
            List[StyleSample]: 预处理后的数据
        """
        if not data:
            return []
        
        target_dim = data[0].feature_dim
        processed = []
        
        for sample in data:
            try:
                if sample.feature_dim != target_dim:
                    continue
                
                normalized_features = self._normalize_features(sample.features)
                
                processed_sample = StyleSample(
                    features=normalized_features,
                    label=sample.label,
                    feature_dim=target_dim,
                    metadata=sample.metadata.copy()
                )
                processed.append(processed_sample)
            except Exception as e:
                logger.warning(f"Preprocessing failed: {e}")
        
        return processed

    def _normalize_features(self, features: List[float]) -> List[float]:
        """特征归一化（L2 归一化）
        
        Args:
            features: 原始特征
            
        Returns:
            List[float]: 归一化后的特征
        """
        import math
        
        norm = math.sqrt(sum(x * x for x in features))
        if norm == 0:
            return features
        
        return [x / norm for x in features]

    def validate_sample(self, sample: StyleSample) -> bool:
        """验证样本是否有效
        
        Args:
            sample: 单个样本
            
        Returns:
            bool: 样本是否有效
        """
        if not isinstance(sample, StyleSample):
            return False
        
        if sample.label not in self._label_to_idx:
            return False
        
        if not sample.features or len(sample.features) == 0:
            return False
        
        if any(not isinstance(x, (int, float)) for x in sample.features):
            return False
        
        return True

    def augment_sample(self, sample: StyleSample) -> List[StyleSample]:
        """数据增强 - 从单个样本生成多个变体
        
        增强策略：
        - 添加高斯噪声
        - 特征值微调（亮度/对比度模拟）
        - 随机特征丢弃
        
        Args:
            sample: 单个样本
            
        Returns:
            List[StyleSample]: 增强后的样本列表
        """
        augmented = []
        
        if random.random() < 0.5:
            noisy = self._add_gaussian_noise(sample)
            if noisy:
                augmented.append(noisy)
        
        if random.random() < 0.4:
            scaled = self._scale_features(sample)
            if scaled:
                augmented.append(scaled)
        
        if random.random() < 0.3:
            dropped = self._random_dropout(sample)
            if dropped:
                augmented.append(dropped)
        
        return augmented

    def _add_gaussian_noise(self, sample: StyleSample) -> Optional[StyleSample]:
        """添加高斯噪声增强
        
        Args:
            sample: 原样本
            
        Returns:
            Optional[StyleSample]: 加噪后的样本
        """
        try:
            noise_level = random.uniform(0.005, 0.02)
            
            new_features = []
            for feat in sample.features:
                noise = random.gauss(0, noise_level)
                new_features.append(feat + noise)
            
            return StyleSample(
                features=new_features,
                label=sample.label,
                feature_dim=sample.feature_dim,
                metadata={**sample.metadata, 'augmented': 'gaussian_noise'}
            )
        except Exception as e:
            logger.warning(f"Gaussian noise augmentation failed: {e}")
            return None

    def _scale_features(self, sample: StyleSample) -> Optional[StyleSample]:
        """特征缩放增强（模拟亮度/对比度变化）
        
        Args:
            sample: 原样本
            
        Returns:
            Optional[StyleSample]: 缩放后的样本
        """
        try:
            scale = random.uniform(0.9, 1.1)
            shift = random.uniform(-0.05, 0.05)
            
            new_features = [feat * scale + shift for feat in sample.features]
            
            return StyleSample(
                features=new_features,
                label=sample.label,
                feature_dim=sample.feature_dim,
                metadata={**sample.metadata, 'augmented': 'feature_scale'}
            )
        except Exception as e:
            logger.warning(f"Feature scale augmentation failed: {e}")
            return None

    def _random_dropout(self, sample: StyleSample) -> Optional[StyleSample]:
        """随机特征丢弃增强
        
        Args:
            sample: 原样本
            
        Returns:
            Optional[StyleSample]: 特征丢弃后的样本
        """
        try:
            dropout_rate = random.uniform(0.01, 0.05)
            
            new_features = []
            for feat in sample.features:
                if random.random() < dropout_rate:
                    new_features.append(0.0)
                else:
                    new_features.append(feat)
            
            return StyleSample(
                features=new_features,
                label=sample.label,
                feature_dim=sample.feature_dim,
                metadata={**sample.metadata, 'augmented': 'feature_dropout'}
            )
        except Exception as e:
            logger.warning(f"Feature dropout augmentation failed: {e}")
            return None

    def get_label_distribution(self) -> Dict[str, int]:
        """获取标签分布统计
        
        Returns:
            Dict[str, int]: 各标签的样本数
        """
        distribution = {}
        all_data = self._train_data + self._val_data + self._test_data
        
        for sample in all_data:
            label = sample.label
            distribution[label] = distribution.get(label, 0) + 1
        
        return distribution

    def label_to_idx(self, label: str) -> int:
        """标签转索引
        
        Args:
            label: 标签名称
            
        Returns:
            int: 标签索引
        """
        return self._label_to_idx.get(label, -1)

    def idx_to_label(self, idx: int) -> Optional[str]:
        """索引转标签
        
        Args:
            idx: 标签索引
            
        Returns:
            Optional[str]: 标签名称
        """
        return self._idx_to_label.get(idx)

    @property
    def num_classes(self) -> int:
        """类别数"""
        return len(self._label_to_idx)

    @property
    def feature_dim(self) -> int:
        """特征维度"""
        return self._feature_dim
