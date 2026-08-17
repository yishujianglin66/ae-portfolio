"""
效果参数优化数据集类
参考 Antares 哲学：高质量数据 + 精悍模型 = 精准调参

输入：风格标签 + 效果类型 + 基础参数
输出：优化后的效果参数
"""
import json
import os
import random
import re
from typing import Any, Dict, List, Tuple, Optional
import logging
import numpy as np

from .dataset_base import BaseDataset, DatasetConfig, DatasetStats

logger = logging.getLogger(__name__)

STYLE_LABELS = [
    "cinematic", "neon", "vintage", "minimal", "dramatic",
    "soft", "sharp", "colorful", "monochrome", "dreamy",
    "futuristic", "warm", "cool", "natural", "artistic",
    "professional", "creative", "clean", "elegant", "dynamic",
]

STYLE_DESCRIPTIONS = {
    "cinematic": ["电影感", "电影调色", "好莱坞风格", "电影级质感", "cinematic", "film"],
    "neon": ["霓虹", "赛博朋克", "发光效果", "霓虹灯", "neon", "cyberpunk", "glow"],
    "vintage": ["复古", "怀旧", "老电影", "经典", "vintage", "retro", "old movie"],
    "minimal": ["极简", "简约", "干净", "清爽", "minimal", "simple"],
    "dramatic": ["戏剧化", "强烈对比", "戏剧性", "震撼", "dramatic", "contrast"],
    "soft": ["柔和", "轻柔", "温柔", "淡雅", "soft", "gentle"],
    "sharp": ["锐利", "清晰", "高对比", "鲜明", "sharp", "crisp"],
    "colorful": ["多彩", "鲜艳", "丰富色彩", "饱和", "colorful", "vibrant"],
    "monochrome": ["黑白", "单色", "灰度", "黑白摄影", "monochrome", "black and white"],
    "dreamy": ["梦幻", "朦胧", "梦幻感", "恍惚", "dreamy", "dreamlike", "hazy"],
    "futuristic": ["未来感", "科幻", "科技感", "未来主义", "futuristic", "sci-fi"],
    "warm": ["温暖", "暖色", "温馨", "暖阳", "warm", "sunny"],
    "cool": ["冷色", "清凉", "冷静", "冷色调", "cool", "cold"],
    "natural": ["自然", "真实", "写实", "自然色彩", "natural", "realistic"],
    "artistic": ["艺术", "创意", "美术", "艺术感", "artistic", "creative"],
    "professional": ["专业", "商务", "严谨", "高品质", "professional", "business"],
    "creative": ["创意", "创新", "独特", "想象力", "creative", "innovative"],
    "clean": ["干净", "整洁", "清爽", "纯净", "clean", "pure"],
    "elegant": ["优雅", "精致", "高贵", "典雅", "elegant", "sophisticated"],
    "dynamic": ["动感", "活力", "充满能量", "动态", "dynamic", "energetic"],
}

EFFECT_PARAM_RANGES = {
    "Glow": {
        "Glow Threshold": (0, 100),
        "Glow Radius": (0, 300),
        "Glow Intensity": (0, 5),
        "Blend With Original": (0, 100),
    },
    "Lens Flare": {
        "Flare Brightness": (0, 300),
        "Blend With Original": (0, 100),
    },
    "Gaussian Blur": {
        "Blurriness": (0, 1000),
    },
    "Sharpen": {
        "Amount": (0, 400),
        "Radius": (0, 100),
    },
    "Vignette": {
        "Amount": (-100, 100),
        "Midpoint": (0, 100),
        "Roundness": (-100, 100),
        "Feather": (0, 100),
    },
    "Hue/Saturation": {
        "Master Hue": (-180, 180),
        "Master Saturation": (-100, 100),
        "Master Lightness": (-100, 100),
    },
    "Levels": {
        "Input Black": (0, 255),
        "Input White": (0, 255),
        "Gamma": (0.1, 9.99),
        "Output Black": (0, 255),
        "Output White": (0, 255),
    },
    "Color Balance": {
        "Red Shadow Level": (-100, 100),
        "Green Shadow Level": (-100, 100),
        "Blue Shadow Level": (-100, 100),
        "Red Midtone Level": (-100, 100),
        "Green Midtone Level": (-100, 100),
        "Blue Midtone Level": (-100, 100),
        "Red Highlight Level": (-100, 100),
        "Green Highlight Level": (-100, 100),
        "Blue Highlight Level": (-100, 100),
    },
    "Drop Shadow": {
        "Opacity": (0, 100),
        "Distance": (0, 1000),
        "Softness": (0, 1000),
    },
}

STYLE_EFFECT_PARAM_MAP = {
    "cinematic": {
        "Glow": {"Glow Intensity": 0.7, "Glow Radius": 0.6},
        "Lens Flare": {"Flare Brightness": 0.7},
        "Vignette": {"Amount": 0.6, "Feather": 0.5},
        "Color Balance": {"Red Midtone Level": 0.1, "Blue Highlight Level": 0.1},
    },
    "neon": {
        "Glow": {"Glow Intensity": 0.9, "Glow Radius": 0.8},
        "Lens Flare": {"Flare Brightness": 0.85},
        "Hue/Saturation": {"Master Saturation": 0.8},
    },
    "vintage": {
        "Glow": {"Glow Intensity": 0.3, "Glow Radius": 0.5},
        "Vignette": {"Amount": 0.7, "Feather": 0.6},
        "Color Balance": {"Red Midtone Level": 0.15, "Blue Midtone Level": -0.1},
        "Hue/Saturation": {"Master Saturation": -0.2},
    },
    "minimal": {
        "Gaussian Blur": {"Blurriness": 0.1},
        "Vignette": {"Amount": 0.1},
        "Color Balance": {"Red Midtone Level": 0.0, "Blue Midtone Level": 0.0},
    },
    "dramatic": {
        "Glow": {"Glow Intensity": 0.8, "Glow Radius": 0.5},
        "Vignette": {"Amount": 0.8},
        "Color Balance": {"Red Midtone Level": 0.15, "Blue Shadow Level": -0.15},
        "Hue/Saturation": {"Master Saturation": 0.3},
    },
    "soft": {
        "Gaussian Blur": {"Blurriness": 0.2},
        "Glow": {"Glow Intensity": 0.4, "Glow Radius": 0.7},
        "Vignette": {"Amount": 0.3},
        "Color Balance": {"Red Midtone Level": 0.05, "Blue Midtone Level": 0.05},
    },
    "sharp": {
        "Sharpen": {"Amount": 0.7, "Radius": 0.3},
        "Hue/Saturation": {"Master Saturation": 0.2},
    },
    "colorful": {
        "Hue/Saturation": {"Master Saturation": 0.7},
        "Color Balance": {"Red Midtone Level": 0.1, "Green Midtone Level": 0.1, "Blue Midtone Level": 0.1},
    },
    "monochrome": {
        "Hue/Saturation": {"Master Saturation": -1.0},
        "Color Balance": {"Red Midtone Level": 0.0, "Green Midtone Level": 0.0, "Blue Midtone Level": 0.0},
    },
    "dreamy": {
        "Gaussian Blur": {"Blurriness": 0.3},
        "Glow": {"Glow Intensity": 0.5, "Glow Radius": 0.8},
        "Vignette": {"Amount": 0.4},
    },
    "futuristic": {
        "Glow": {"Glow Intensity": 0.8, "Glow Radius": 0.6},
        "Lens Flare": {"Flare Brightness": 0.9},
        "Color Balance": {"Blue Midtone Level": 0.15},
    },
    "warm": {
        "Color Balance": {"Red Midtone Level": 0.15, "Blue Midtone Level": -0.1},
        "Hue/Saturation": {"Master Hue": -0.1},
    },
    "cool": {
        "Color Balance": {"Red Midtone Level": -0.1, "Blue Midtone Level": 0.15},
        "Hue/Saturation": {"Master Hue": 0.1},
    },
    "natural": {
        "Color Balance": {"Red Midtone Level": 0.0, "Green Midtone Level": 0.0, "Blue Midtone Level": 0.0},
        "Hue/Saturation": {"Master Saturation": 0.0},
        "Vignette": {"Amount": 0.1},
    },
    "artistic": {
        "Glow": {"Glow Intensity": 0.6, "Glow Radius": 0.6},
        "Hue/Saturation": {"Master Saturation": 0.4},
        "Color Balance": {"Red Midtone Level": 0.1, "Green Midtone Level": -0.05},
    },
    "professional": {
        "Vignette": {"Amount": 0.2},
        "Color Balance": {"Red Midtone Level": 0.02, "Blue Midtone Level": 0.02},
    },
    "creative": {
        "Glow": {"Glow Intensity": 0.7, "Glow Radius": 0.6},
        "Hue/Saturation": {"Master Saturation": 0.5, "Master Hue": 0.2},
    },
    "clean": {
        "Vignette": {"Amount": 0.0},
        "Color Balance": {"Red Midtone Level": 0.0, "Green Midtone Level": 0.0, "Blue Midtone Level": 0.0},
        "Gaussian Blur": {"Blurriness": 0.05},
    },
    "elegant": {
        "Vignette": {"Amount": 0.3},
        "Glow": {"Glow Intensity": 0.4, "Glow Radius": 0.4},
        "Color Balance": {"Red Midtone Level": 0.05},
    },
    "dynamic": {
        "Glow": {"Glow Intensity": 0.8, "Glow Radius": 0.5},
        "Lens Flare": {"Flare Brightness": 0.8},
        "Hue/Saturation": {"Master Saturation": 0.4},
    },
}


class ParamOptimDataset(BaseDataset):
    """效果参数优化数据集

    从 effect_presets.json 和其他数据源收集效果参数数据，
    构建用于训练参数优化模型的数据集。

    输入：风格标签 + 效果类型 + 基础参数（归一化向量）
    输出：优化后的效果参数（归一化向量）
    """

    def __init__(self, config: DatasetConfig):
        super().__init__(config)
        self._style_to_idx = {style: idx for idx, style in enumerate(STYLE_LABELS)}
        self._effect_to_idx = {}
        self._param_names = []
        self._effect_param_map = {}

    def load_data(self, data_path: str) -> List[Dict]:
        all_data = []

        effect_presets_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            "config", "effect_presets.json"
        )

        if os.path.exists(effect_presets_path):
            try:
                with open(effect_presets_path, 'r', encoding='utf-8') as f:
                    presets_data = json.load(f)

                for effect_name, effect_info in presets_data.get('effects', {}).items():
                    params_info = effect_info.get('params', {})
                    presets = effect_info.get('presets', [])
                    category = effect_info.get('category', '')

                    if effect_name not in self._effect_to_idx:
                        self._effect_to_idx[effect_name] = len(self._effect_to_idx)

                    effect_params = []
                    for param_name, param_info in params_info.items():
                        if param_info.get('type') == 'number':
                            effect_params.append(param_name)
                            if param_name not in self._param_names:
                                self._param_names.append(param_name)

                    self._effect_param_map[effect_name] = effect_params

                    for preset in presets:
                        preset_params = preset.get('params', {})
                        description = preset.get('description', '')
                        preset_name = preset.get('name', '')

                        matched_styles = []
                        for style_label in STYLE_LABELS:
                            style_keywords = STYLE_DESCRIPTIONS.get(style_label, [])
                            matches_style = any(
                                kw.lower() in description.lower() or kw.lower() in preset_name.lower()
                                for kw in style_keywords
                            )
                            if matches_style:
                                matched_styles.append(style_label)

                        if matched_styles:
                            for style_label in matched_styles:
                                sample = self._create_sample(
                                    effect_name,
                                    params_info,
                                    preset_params,
                                    style_label,
                                    category,
                                )
                                if sample:
                                    all_data.append(sample)
                        else:
                            for _ in range(2):
                                style_label = random.choice(STYLE_LABELS)
                                sample = self._create_sample(
                                    effect_name,
                                    params_info,
                                    preset_params,
                                    style_label,
                                    category,
                                )
                                if sample:
                                    all_data.append(sample)

                logger.info(f"Loaded {len(all_data)} samples from effect_presets.json")
            except Exception as e:
                logger.error(f"Failed to load effect_presets.json: {e}")

        all_data = self._generate_style_based_samples(all_data)

        all_data = self._generate_effect_variations(all_data)

        logger.info(f"Total samples after augmentation: {len(all_data)}")
        return all_data

    def _generate_style_based_samples(self, existing_data: List[Dict]) -> List[Dict]:
        new_samples = existing_data.copy()

        for style_label in STYLE_LABELS:
            effect_map = STYLE_EFFECT_PARAM_MAP.get(style_label, {})
            for effect_name, param_adjustments in effect_map.items():
                effect_ranges = EFFECT_PARAM_RANGES.get(effect_name, {})
                if not effect_ranges:
                    continue

                params_info = {}
                for param_name, (min_val, max_val) in effect_ranges.items():
                    params_info[param_name] = {
                        'type': 'number',
                        'min': min_val,
                        'max': max_val,
                        'default': (min_val + max_val) / 2,
                    }

                for _ in range(5):
                    preset_params = {}
                    for param_name, (min_val, max_val) in effect_ranges.items():
                        default_val = (min_val + max_val) / 2
                        if param_name in param_adjustments:
                            factor = param_adjustments[param_name]
                            variation = (factor - 0.5) * (max_val - min_val) * 0.8
                            preset_params[param_name] = max(min_val, min(max_val, default_val + variation))
                        else:
                            preset_params[param_name] = default_val + random.uniform(-0.1, 0.1) * (max_val - min_val)

                    sample = self._create_sample(
                        effect_name,
                        params_info,
                        preset_params,
                        style_label,
                        'style_based',
                    )
                    if sample:
                        new_samples.append(sample)

        logger.info(f"Generated {len(new_samples) - len(existing_data)} style-based samples")
        return new_samples

    def _generate_effect_variations(self, existing_data: List[Dict]) -> List[Dict]:
        new_samples = existing_data.copy()

        for effect_name in EFFECT_PARAM_RANGES:
            effect_ranges = EFFECT_PARAM_RANGES[effect_name]

            params_info = {}
            for param_name, (min_val, max_val) in effect_ranges.items():
                params_info[param_name] = {
                    'type': 'number',
                    'min': min_val,
                    'max': max_val,
                    'default': (min_val + max_val) / 2,
                }

            if effect_name not in self._effect_to_idx:
                self._effect_to_idx[effect_name] = len(self._effect_to_idx)

            effect_params = list(effect_ranges.keys())
            for param_name in effect_params:
                if param_name not in self._param_names:
                    self._param_names.append(param_name)
            self._effect_param_map[effect_name] = effect_params

            for style_label in STYLE_LABELS:
                for _ in range(3):
                    preset_params = {}
                    for param_name, (min_val, max_val) in effect_ranges.items():
                        base_val = (min_val + max_val) / 2
                        style_factor = self._get_style_factor(style_label, param_name)
                        variation = (style_factor - 0.5) * (max_val - min_val) * 0.6
                        noise = random.uniform(-0.05, 0.05) * (max_val - min_val)
                        preset_params[param_name] = max(min_val, min(max_val, base_val + variation + noise))

                    sample = self._create_sample(
                        effect_name,
                        params_info,
                        preset_params,
                        style_label,
                        'variation',
                    )
                    if sample:
                        new_samples.append(sample)

        logger.info(f"Generated {len(new_samples) - len(existing_data)} effect variation samples")
        return new_samples

    def _create_sample(
        self,
        effect_name: str,
        params_info: Dict,
        preset_params: Dict,
        style_label: str,
        category: str,
    ) -> Optional[Dict]:
        base_params = {}
        optimized_params = {}

        for param_name, param_info in params_info.items():
            if param_info.get('type') != 'number':
                continue

            min_val = param_info.get('min', 0)
            max_val = param_info.get('max', 100)
            default_val = param_info.get('default', (min_val + max_val) / 2)

            base_params[param_name] = default_val

            if param_name in preset_params:
                optimized_params[param_name] = preset_params[param_name]
            else:
                optimized_params[param_name] = default_val

        if not base_params:
            return None

        return {
            'effect_name': effect_name,
            'effect_idx': self._effect_to_idx.get(effect_name, 0),
            'style_label': style_label,
            'style_idx': self._style_to_idx.get(style_label, 0),
            'category': category,
            'base_params': base_params,
            'optimized_params': optimized_params,
            'params_info': params_info,
        }

    def _get_style_factor(self, style_label: str, param_name: str) -> float:
        style_factors = {
            "cinematic": {"Intensity": 0.7, "Amount": 0.6, "Radius": 0.5, "Brightness": 0.7},
            "neon": {"Intensity": 0.85, "Amount": 0.8, "Radius": 0.7, "Brightness": 0.85},
            "vintage": {"Intensity": 0.3, "Amount": 0.5, "Radius": 0.6, "Brightness": 0.5},
            "minimal": {"Intensity": 0.2, "Amount": 0.2, "Radius": 0.2, "Brightness": 0.4},
            "dramatic": {"Intensity": 0.8, "Amount": 0.75, "Radius": 0.5, "Brightness": 0.75},
            "soft": {"Intensity": 0.35, "Amount": 0.4, "Radius": 0.7, "Brightness": 0.4},
            "sharp": {"Intensity": 0.7, "Amount": 0.8, "Radius": 0.2, "Brightness": 0.6},
            "colorful": {"Intensity": 0.75, "Amount": 0.8, "Radius": 0.5, "Brightness": 0.7},
            "monochrome": {"Intensity": 0.5, "Amount": 0.4, "Radius": 0.4, "Brightness": 0.5},
            "dreamy": {"Intensity": 0.45, "Amount": 0.5, "Radius": 0.8, "Brightness": 0.5},
            "futuristic": {"Intensity": 0.8, "Amount": 0.7, "Radius": 0.6, "Brightness": 0.85},
            "warm": {"Intensity": 0.5, "Amount": 0.6, "Radius": 0.5, "Brightness": 0.6},
            "cool": {"Intensity": 0.45, "Amount": 0.4, "Radius": 0.5, "Brightness": 0.5},
            "natural": {"Intensity": 0.4, "Amount": 0.45, "Radius": 0.4, "Brightness": 0.5},
            "artistic": {"Intensity": 0.65, "Amount": 0.7, "Radius": 0.6, "Brightness": 0.65},
            "professional": {"Intensity": 0.5, "Amount": 0.5, "Radius": 0.4, "Brightness": 0.5},
            "creative": {"Intensity": 0.7, "Amount": 0.65, "Radius": 0.6, "Brightness": 0.7},
            "clean": {"Intensity": 0.3, "Amount": 0.3, "Radius": 0.3, "Brightness": 0.4},
            "elegant": {"Intensity": 0.45, "Amount": 0.5, "Radius": 0.5, "Brightness": 0.5},
            "dynamic": {"Intensity": 0.75, "Amount": 0.7, "Radius": 0.5, "Brightness": 0.75},
        }

        default_factor = style_factors.get(style_label, {})
        return default_factor.get(param_name, default_factor.get('Intensity', 0.5))

    def preprocess(self, data: List[Dict]) -> List[Dict]:
        processed = []

        for sample in data:
            params_info = sample.get('params_info', {})
            base_params = sample.get('base_params', {})
            optimized_params = sample.get('optimized_params', {})

            normalized_base = {}
            normalized_optimized = {}

            for param_name in base_params:
                if param_name not in params_info:
                    continue

                param_info = params_info[param_name]
                min_val = param_info.get('min', 0)
                max_val = param_info.get('max', 100)

                if max_val == min_val:
                    normalized_base[param_name] = 0.5
                    normalized_optimized[param_name] = 0.5
                else:
                    normalized_base[param_name] = (base_params[param_name] - min_val) / (max_val - min_val)
                    normalized_optimized[param_name] = (optimized_params[param_name] - min_val) / (max_val - min_val)

            sample['normalized_base'] = normalized_base
            sample['normalized_optimized'] = normalized_optimized

            input_vector = self._encode_input(sample)
            output_vector = self._encode_output(sample)

            sample['input_vector'] = input_vector
            sample['output_vector'] = output_vector

            processed.append(sample)

        return processed

    def _encode_input(self, sample: Dict) -> np.ndarray:
        style_idx = sample.get('style_idx', 0)
        effect_idx = sample.get('effect_idx', 0)
        normalized_base = sample.get('normalized_base', {})

        style_one_hot = np.zeros(len(STYLE_LABELS))
        style_one_hot[style_idx] = 1.0

        effect_one_hot = np.zeros(len(self._effect_to_idx) + 1)
        effect_one_hot[effect_idx] = 1.0

        param_values = []
        for param_name in self._param_names:
            param_values.append(normalized_base.get(param_name, 0.5))

        while len(param_values) < 16:
            param_values.append(0.5)
        param_values = param_values[:16]

        input_vector = np.concatenate([
            style_one_hot,
            effect_one_hot,
            np.array(param_values)
        ])

        return input_vector.astype(np.float32)

    def _encode_output(self, sample: Dict) -> np.ndarray:
        normalized_optimized = sample.get('normalized_optimized', {})

        output_values = []
        for param_name in self._param_names:
            output_values.append(normalized_optimized.get(param_name, 0.5))

        while len(output_values) < 16:
            output_values.append(0.5)
        output_values = output_values[:16]

        return np.array(output_values, dtype=np.float32)

    def validate_sample(self, sample: Dict) -> bool:
        input_vector = sample.get('input_vector')
        output_vector = sample.get('output_vector')

        if input_vector is None or output_vector is None:
            return False

        if np.isnan(input_vector).any() or np.isnan(output_vector).any():
            return False

        if np.isinf(input_vector).any() or np.isinf(output_vector).any():
            return False

        if not (np.all(input_vector >= 0) and np.all(input_vector <= 1)):
            return False

        if not (np.all(output_vector >= 0) and np.all(output_vector <= 1)):
            return False

        return True

    def augment_sample(self, sample: Dict) -> List[Dict]:
        augmented = []

        jitter_std = 0.05
        for _ in range(5):
            jittered_base = {}
            for param_name, value in sample.get('normalized_base', {}).items():
                jittered = value + np.random.normal(0, jitter_std)
                jittered = max(0, min(1, jittered))
                jittered_base[param_name] = jittered

            new_sample = sample.copy()
            new_sample['normalized_base'] = jittered_base
            new_sample['input_vector'] = self._encode_input(new_sample)
            augmented.append(new_sample)

        style_idx = sample.get('style_idx', 0)
        similar_styles = self._get_similar_styles(style_idx)
        for similar_idx in similar_styles[:3]:
            new_sample = sample.copy()
            new_sample['style_idx'] = similar_idx
            new_sample['style_label'] = STYLE_LABELS[similar_idx]
            new_sample['input_vector'] = self._encode_input(new_sample)
            augmented.append(new_sample)

        return augmented

    def _get_similar_styles(self, style_idx: int) -> List[int]:
        style_clusters = [
            [0, 10, 14],
            [1, 10, 16],
            [2, 11, 13],
            [3, 17, 12],
            [4, 7, 18],
            [5, 12, 13],
            [6, 7, 3],
            [7, 15, 16],
            [8, 2, 12],
            [9, 1, 10],
            [10, 1, 9],
            [11, 2, 18],
            [12, 5, 13],
            [13, 12, 5],
            [14, 0, 16],
            [15, 7, 3],
            [16, 14, 7],
            [17, 3, 12],
            [18, 11, 4],
            [19, 4, 7],
        ]

        if style_idx < len(style_clusters):
            return style_clusters[style_idx]
        return []

    def get_input_dim(self) -> int:
        return len(STYLE_LABELS) + (len(self._effect_to_idx) + 1) + 16

    def get_output_dim(self) -> int:
        return 16

    def get_num_styles(self) -> int:
        return len(STYLE_LABELS)

    def get_param_names(self) -> List[str]:
        return self._param_names[:16]

    def denormalize_params(self, normalized_params: Dict, params_info: Dict) -> Dict:
        denormalized = {}
        for param_name, normalized_value in normalized_params.items():
            if param_name not in params_info:
                continue
            param_info = params_info[param_name]
            min_val = param_info.get('min', 0)
            max_val = param_info.get('max', 100)
            denormalized[param_name] = normalized_value * (max_val - min_val) + min_val
        return denormalized