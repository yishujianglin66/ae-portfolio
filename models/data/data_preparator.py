"""
数据准备工具 - 统一的数据准备入口
支持多种数据集类型，提供便捷的数据准备流程
参考 Antares 哲学：数据质量是小模型成功的关键
"""
import os
import logging
from typing import Any, Dict, Optional, Tuple, Type

from .dataset_base import BaseDataset, DatasetConfig, DatasetStats
from .jsx_code_dataset import JSXCodeDataset
from .style_classify_dataset import StyleClassifyDataset

logger = logging.getLogger(__name__)


class DataPreparator:
    """数据准备工具类
    
    提供统一的数据准备接口，支持多种数据集类型。
    参考 Antares 哲学：高质量、经过校验的数据是小模型精悍够用的基础。
    """

    DATASET_TYPES = {
        'jsx_code': JSXCodeDataset,
        'style_classify': StyleClassifyDataset,
    }

    @classmethod
    def create_dataset(
        cls,
        dataset_type: str,
        data_path: str,
        dataset_name: str = "",
        max_samples: Optional[int] = None,
        data_augmentation: bool = True,
        filter_invalid: bool = True,
        test_split_ratio: float = 0.1,
        val_split_ratio: float = 0.1,
        seed: int = 42,
        **kwargs
    ) -> Tuple[BaseDataset, DatasetStats]:
        """创建并准备数据集
        
        Args:
            dataset_type: 数据集类型（jsx_code, style_classify 等）
            data_path: 数据路径
            dataset_name: 数据集名称
            max_samples: 最大样本数限制
            data_augmentation: 是否启用数据增强
            filter_invalid: 是否过滤无效样本
            test_split_ratio: 测试集比例
            val_split_ratio: 验证集比例
            seed: 随机种子
            **kwargs: 额外参数
            
        Returns:
            Tuple[BaseDataset, DatasetStats]: (数据集对象, 统计信息)
            
        Raises:
            ValueError: 数据集类型不支持
        """
        dataset_class = cls.DATASET_TYPES.get(dataset_type)
        if not dataset_class:
            raise ValueError(
                f"Unsupported dataset type: {dataset_type}. "
                f"Supported types: {list(cls.DATASET_TYPES.keys())}"
            )
        
        config = DatasetConfig(
            dataset_name=dataset_name or dataset_type,
            data_path=data_path,
            max_samples=max_samples,
            test_split_ratio=test_split_ratio,
            val_split_ratio=val_split_ratio,
            seed=seed,
            data_augmentation=data_augmentation,
            filter_invalid=filter_invalid,
        )
        
        dataset = dataset_class(config)
        stats = dataset.prepare()
        
        logger.info(f"Dataset '{dataset_type}' prepared: "
                   f"{stats.train_samples} train, "
                   f"{stats.val_samples} val, "
                   f"{stats.test_samples} test")
        
        return dataset, stats

    @classmethod
    def prepare_jsx_code_dataset(
        cls,
        data_path: str,
        dataset_name: str = "jsx_code",
        **kwargs
    ) -> Tuple[JSXCodeDataset, DatasetStats]:
        """准备 JSX 代码数据集
        
        Args:
            data_path: 数据路径
            dataset_name: 数据集名称
            **kwargs: 额外参数
            
        Returns:
            Tuple[JSXCodeDataset, DatasetStats]: (数据集对象, 统计信息)
        """
        return cls.create_dataset('jsx_code', data_path, dataset_name, **kwargs)

    @classmethod
    def prepare_style_classify_dataset(
        cls,
        data_path: str,
        dataset_name: str = "style_classify",
        **kwargs
    ) -> Tuple[StyleClassifyDataset, DatasetStats]:
        """准备风格分类数据集
        
        Args:
            data_path: 数据路径
            dataset_name: 数据集名称
            **kwargs: 额外参数
            
        Returns:
            Tuple[StyleClassifyDataset, DatasetStats]: (数据集对象, 统计信息)
        """
        return cls.create_dataset('style_classify', data_path, dataset_name, **kwargs)

    @classmethod
    def list_supported_datasets(cls) -> Dict[str, str]:
        """列出支持的数据集类型
        
        Returns:
            Dict[str, str]: 数据集类型到描述的映射
        """
        descriptions = {
            'jsx_code': 'AE JSX 代码生成数据集，支持 JSONL 格式和代码增强',
            'style_classify': '视频风格分类数据集，基于风格指纹特征',
        }
        return descriptions

    @staticmethod
    def create_sample_data(
        output_path: str,
        dataset_type: str = "jsx_code",
        num_samples: int = 100
    ) -> str:
        """创建示例数据（用于测试）
        
        Args:
            output_path: 输出文件路径
            dataset_type: 数据集类型
            num_samples: 样本数量
            
        Returns:
            str: 创建的文件路径
        """
        os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else '.', exist_ok=True)
        
        if dataset_type == 'jsx_code':
            return DataPreparator._create_jsx_samples(output_path, num_samples)
        elif dataset_type == 'style_classify':
            return DataPreparator._create_style_samples(output_path, num_samples)
        else:
            raise ValueError(f"Unsupported dataset type: {dataset_type}")

    @staticmethod
    def _create_jsx_samples(output_path: str, num_samples: int) -> str:
        """创建 JSX 示例数据
        
        Args:
            output_path: 输出路径
            num_samples: 样本数
            
        Returns:
            str: 文件路径
        """
        import json
        
        samples = []
        templates = [
            {
                "instruction": "创建一个新的合成",
                "input": "",
                "output": """var comp = app.project.items.addComp("New Composition", 1920, 1080, 1, 10, 30);
var solidLayer = comp.layers.addSolid([1, 1, 1], "Background", 1920, 1080, 1);"""
            },
            {
                "instruction": "添加高斯模糊效果",
                "input": "选中图层",
                "output": """var layer = app.project.activeItem.selectedLayers[0];
var blurEffect = layer.Effects.addProperty("ADBE Gaussian Blur 2");
blurEffect.property("ADBE Gaussian Blur 2-0001").setValue(15);"""
            },
            {
                "instruction": "创建文字图层",
                "input": "文字内容：Hello World",
                "output": """var comp = app.project.activeItem;
var textLayer = comp.layers.addText("Hello World");
var textProp = textLayer.property("Source Text");
var textDoc = textProp.value;
textDoc.fontSize = 72;
textProp.setValue(textDoc);"""
            },
            {
                "instruction": "添加位置关键帧动画",
                "input": "从左到右移动",
                "output": """var layer = app.project.activeItem.selectedLayers[0];
var posProp = layer.property("Position");
posProp.setValueAtTime(0, [100, 540]);
posProp.setValueAtTime(2, [1820, 540]);"""
            },
            {
                "instruction": "添加调整图层",
                "input": "",
                "output": """var comp = app.project.activeItem;
var adjLayer = comp.layers.addSolid([1, 1, 1], "Adjustment Layer", 1920, 1080, 1);
adjLayer.adjustmentLayer = true;"""
            },
        ]
        
        for i in range(num_samples):
            template = templates[i % len(templates)]
            sample = {
                "instruction": template["instruction"],
                "input": template["input"],
                "output": template["output"],
                "id": f"sample_{i:04d}",
            }
            samples.append(sample)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        logger.info(f"Created {num_samples} JSX samples at {output_path}")
        return output_path

    @staticmethod
    def _create_style_samples(output_path: str, num_samples: int) -> str:
        """创建风格分类示例数据
        
        Args:
            output_path: 输出路径
            num_samples: 样本数
            
        Returns:
            str: 文件路径
        """
        import json
        import random
        
        random.seed(42)
        
        styles = StyleClassifyDataset.STYLE_LABELS
        feature_dim = 128
        samples = []
        
        style_centers = {}
        for style in styles:
            style_centers[style] = [random.uniform(-1, 1) for _ in range(feature_dim)]
        
        for i in range(num_samples):
            style = random.choice(styles)
            center = style_centers[style]
            features = [c + random.gauss(0, 0.2) for c in center]
            
            sample = {
                "features": features,
                "label": style,
                "id": f"sample_{i:04d}",
            }
            samples.append(sample)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for sample in samples:
                f.write(json.dumps(sample, ensure_ascii=False) + '\n')
        
        logger.info(f"Created {num_samples} style samples at {output_path}")
        return output_path
