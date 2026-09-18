"""
数据集基类 - 定义统一的数据接口
参考 Antares 哲学：高质量数据 > 大模型
"""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class DatasetConfig:
    """数据集配置"""
    dataset_name: str = ""
    data_path: str = ""
    max_samples: int | None = None
    test_split_ratio: float = 0.1
    val_split_ratio: float = 0.1
    seed: int = 42
    data_augmentation: bool = True
    """是否启用数据增强"""
    filter_invalid: bool = True
    """是否过滤无效数据"""


@dataclass
class DatasetStats:
    """数据集统计信息"""
    total_samples: int = 0
    train_samples: int = 0
    val_samples: int = 0
    test_samples: int = 0
    avg_length: float = 0.0
    max_length: int = 0
    min_length: int = 0
    invalid_samples: int = 0
    augmented_samples: int = 0
    label_distribution: dict[str, int] = field(default_factory=dict)


class BaseDataset(ABC):
    """数据集抽象基类
    
    定义所有数据集必须实现的统一接口。
    参考 Antares 哲学：高质量的垂直领域数据是小模型成功的关键。
    """

    def __init__(self, config: DatasetConfig):
        """初始化数据集
        
        Args:
            config: 数据集配置
        """
        self.config = config
        self._train_data: list[Any] = []
        self._val_data: list[Any] = []
        self._test_data: list[Any] = []
        self._stats: DatasetStats | None = None

    @abstractmethod
    def load_data(self, data_path: str) -> list[Any]:
        """从文件加载原始数据
        
        Args:
            data_path: 数据文件路径
            
        Returns:
            List[Any]: 原始数据列表
        """
        pass

    @abstractmethod
    def preprocess(self, data: list[Any]) -> list[Any]:
        """数据预处理
        
        Args:
            data: 原始数据
            
        Returns:
            List[Any]: 预处理后的数据
        """
        pass

    @abstractmethod
    def validate_sample(self, sample: Any) -> bool:
        """验证单个样本是否有效
        
        Args:
            sample: 单个样本
            
        Returns:
            bool: 样本是否有效
        """
        pass

    @abstractmethod
    def augment_sample(self, sample: Any) -> list[Any]:
        """数据增强 - 从单个样本生成多个变体
        
        Args:
            sample: 单个样本
            
        Returns:
            List[Any]: 增强后的样本列表
        """
        pass

    def prepare(self) -> DatasetStats:
        """准备数据集 - 加载、预处理、划分、增强
        
        Returns:
            DatasetStats: 数据集统计信息
        """
        logger.info(f"Preparing dataset: {self.config.dataset_name}")
        
        raw_data = self.load_data(self.config.data_path)
        logger.info(f"Loaded {len(raw_data)} raw samples")
        
        if self.config.max_samples:
            raw_data = raw_data[:self.config.max_samples]
            logger.info(f"Limited to {self.config.max_samples} samples")
        
        preprocessed = self.preprocess(raw_data)
        logger.info(f"Preprocessed to {len(preprocessed)} samples")
        
        if self.config.filter_invalid:
            valid_data = []
            invalid_count = 0
            for sample in preprocessed:
                if self.validate_sample(sample):
                    valid_data.append(sample)
                else:
                    invalid_count += 1
            preprocessed = valid_data
            logger.info(f"Filtered {invalid_count} invalid samples, {len(preprocessed)} remaining")
        else:
            invalid_count = 0
        
        augmented_count = 0
        if self.config.data_augmentation:
            augmented_data = []
            for sample in preprocessed:
                augmented_data.append(sample)
                variants = self.augment_sample(sample)
                augmented_data.extend(variants)
                augmented_count += len(variants)
            preprocessed = augmented_data
            logger.info(f"Data augmentation added {augmented_count} samples, total {len(preprocessed)}")
        
        self._split_data(preprocessed)
        
        stats = DatasetStats(
            total_samples=len(preprocessed),
            train_samples=len(self._train_data),
            val_samples=len(self._val_data),
            test_samples=len(self._test_data),
            invalid_samples=invalid_count,
            augmented_samples=augmented_count,
        )
        self._stats = stats
        
        logger.info(f"Dataset ready: train={stats.train_samples}, "
                   f"val={stats.val_samples}, test={stats.test_samples}")
        
        return stats

    def _split_data(self, data: list[Any]) -> None:
        """划分训练/验证/测试集
        
        Args:
            data: 全部数据
        """
        import random
        random.seed(self.config.seed)
        
        shuffled = data.copy()
        random.shuffle(shuffled)
        
        n = len(shuffled)
        test_size = int(n * self.config.test_split_ratio)
        val_size = int(n * self.config.val_split_ratio)
        
        self._test_data = shuffled[:test_size]
        self._val_data = shuffled[test_size:test_size + val_size]
        self._train_data = shuffled[test_size + val_size:]

    def get_train_data(self) -> list[Any]:
        """获取训练数据
        
        Returns:
            List[Any]: 训练数据
        """
        return self._train_data

    def get_val_data(self) -> list[Any]:
        """获取验证数据
        
        Returns:
            List[Any]: 验证数据
        """
        return self._val_data

    def get_test_data(self) -> list[Any]:
        """获取测试数据
        
        Returns:
            List[Any]: 测试数据
        """
        return self._test_data

    def get_stats(self) -> DatasetStats | None:
        """获取数据集统计信息
        
        Returns:
            Optional[DatasetStats]: 统计信息
        """
        return self._stats

    def __len__(self) -> int:
        """获取总样本数"""
        return len(self._train_data) + len(self._val_data) + len(self._test_data)

    def __iter__(self) -> Iterator[Any]:
        """迭代训练数据"""
        return iter(self._train_data)
