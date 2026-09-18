#!/usr/bin/env python3
"""
训练数据准备脚本 - 构建风格分类和JSX代码生成数据集
优化版本：目标500+样本，增加漫剪专属特征

特征工程扩展：
- 基础特征（7维）：brightness, saturation, warmth, cut_rate, avg_shot_duration, resolution_width, resolution_height
- 漫剪专属特征（7维）：bpm, zoom_intensity, rotation_angle, shutter_angle, motion_blur_enabled, dynamic_tile_enabled, beat_sync_strength
- 新增高级特征（6维）：keyframes_density, motion_trajectory_complexity, color_vibrancy, contrast_ratio, edge_detection_strength, depth_of_field
- 时序特征（4维）：shot_transition_diversity, rhythm_consistency, frame_rate_variation, visual_complexity

总计24维特征
"""
from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def safe_output_path(path: str | Path, root: Path = PROJECT_ROOT) -> Path:
    """把输出路径规范化到 root 之内，拒绝路径穿越。

    用途：--output 与 save() 的目标路径均来自外部输入，直接拼接会让
    `--output ../../etc` 之类的值写到项目外。此函数做三层校验：
      1. 拒绝含 `..` 的路径分量；
      2. resolve 后必须落在 root 之内；
      3. 拒绝 root 自身（必须是文件或子目录）。

    抛出 ValueError 由调用方处理，不静默降级。
    """
    p = Path(path)
    if any(part == ".." for part in p.parts):
        raise ValueError(f"输出路径含路径穿越分量: {p}")
    resolved = (root / p).resolve() if not p.is_absolute() else p.resolve()
    root_r = root.resolve()
    if resolved == root_r or root_r not in resolved.parents:
        raise ValueError(f"输出路径越出允许根目录: {resolved}")
    return resolved


@dataclass
class StyleSample:
    sample_id: str
    features: dict[str, float]
    label: str
    label_id: int
    source: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class JSXCodeSample:
    sample_id: str
    code: str
    task_type: str
    description: str
    parameters: dict[str, Any]
    source: str
    code_length: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class StyleDatasetBuilder:
    """风格分类数据集构建器 - 优化版本"""

    STYLE_LABELS = {
        "cinematic": 0,
        "anime_puppet": 1,
        "fast_cut": 2,
        "slow_cut": 3,
        "glitch_digital": 4,
        "audio_visual": 5,
        "particle_ambient": 6,
        "text_animation": 7,
        "3d_spatial": 8,
        "realistic_color": 9,
        "high_dynamic": 10,
        "dark_tone": 11,
        "low_saturation": 12,
        "高饱和": 13,
        "长镜头": 14,
        "amv_pull_zoom": 15,
        "amv_fast_cut": 16,
        "amv_beat_sync": 17,
        "amv_korean_flash": 18,
        "amv_glitch": 19,
        "amv_cinematic": 20,
        "amv_3d_spatial": 21,
        "amv_high_burn": 22,
    }

    ALL_FEATURE_NAMES = [
        "brightness", "saturation", "warmth", "cut_rate", "avg_shot_duration",
        "resolution_width", "resolution_height", "bpm", "zoom_intensity",
        "rotation_angle", "shutter_angle", "motion_blur_enabled",
        "dynamic_tile_enabled", "beat_sync_strength", "keyframes_density",
        "motion_trajectory_complexity", "color_vibrancy", "contrast_ratio",
        "edge_detection_strength", "depth_of_field", "shot_transition_diversity",
        "rhythm_consistency", "frame_rate_variation", "visual_complexity"
    ]

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.fingerprint_dir = project_root / "output_director" / "ae_10_tutorials_style"
        self.style_test_dir = project_root / "output_director" / "style_test"
        self.amv_masters_dir = project_root / "12-漫剪拉镜大师"
        self.samples: list[StyleSample] = []

    def collect_from_fingerprints(self) -> int:
        count = 0
        for fp_file in self.fingerprint_dir.glob("fp_*.json"):
            sample = self._parse_fingerprint(fp_file)
            if sample:
                self.samples.append(sample)
                count += 1
        for fp_file in self.style_test_dir.glob("fp_*.json"):
            sample = self._parse_fingerprint(fp_file)
            if sample:
                self.samples.append(sample)
                count += 1
        return count

    def _parse_fingerprint(self, fp_file: Path) -> StyleSample | None:
        try:
            with open(fp_file, encoding="utf-8") as f:
                data = json.load(f)

            features = self._build_full_features(data, "cinematic")
            style_tags = data.get("style_tags", [])
            primary_label = style_tags[0] if style_tags else "cinematic"

            if "快切" in style_tags or "hyper_fast" in data.get("rhythm_type", ""):
                primary_label = "fast_cut"
            elif "高动感" in style_tags:
                primary_label = "high_dynamic"
            elif "暗调" in style_tags:
                primary_label = "dark_tone"
            elif "低饱和" in style_tags:
                primary_label = "low_saturation"

            label_id = self.STYLE_LABELS.get(primary_label, 0)

            return StyleSample(
                sample_id=fp_file.stem,
                features=features,
                label=primary_label,
                label_id=label_id,
                source=str(fp_file),
                metadata={
                    "project": data.get("project", fp_file.stem),
                    "duration": data.get("duration", 0),
                    "color_mood": data.get("color_mood", ""),
                    "rhythm_type": data.get("rhythm_type", ""),
                    "style_tags": style_tags,
                }
            )
        except Exception:
            return None

    def _build_full_features(self, data: dict, label: str) -> dict[str, float]:
        """构建完整的24维特征向量"""
        features = {
            "brightness": float(data.get("brightness", 50)),
            "saturation": float(data.get("saturation", 50)),
            "warmth": float(data.get("warmth", 0)),
            "cut_rate": float(data.get("cut_rate", 1)),
            "avg_shot_duration": float(data.get("avg_shot_duration", 1)),
            "resolution_width": 1920,
            "resolution_height": 1080,
            "bpm": float(data.get("bpm", 120)),
            "zoom_intensity": float(data.get("zoom_intensity", 100)),
            "rotation_angle": float(data.get("rotation_angle", 0)),
            "shutter_angle": float(data.get("shutter_angle", 180)),
            "motion_blur_enabled": float(data.get("motion_blur_enabled", 0)),
            "dynamic_tile_enabled": float(data.get("dynamic_tile_enabled", 0)),
            "beat_sync_strength": float(data.get("beat_sync_strength", 0.5)),
            "keyframes_density": float(data.get("keyframes_density", 1.0)),
            "motion_trajectory_complexity": float(data.get("motion_trajectory_complexity", 0.5)),
            "color_vibrancy": float(data.get("color_vibrancy", 0.5)),
            "contrast_ratio": float(data.get("contrast_ratio", 1.0)),
            "edge_detection_strength": float(data.get("edge_detection_strength", 0.0)),
            "depth_of_field": float(data.get("depth_of_field", 0.0)),
            "shot_transition_diversity": float(data.get("shot_transition_diversity", 0.5)),
            "rhythm_consistency": float(data.get("rhythm_consistency", 0.5)),
            "frame_rate_variation": float(data.get("frame_rate_variation", 0.0)),
            "visual_complexity": float(data.get("visual_complexity", 0.5)),
        }

        resolution = data.get("resolution", "1920x1080")
        if "x" in str(resolution):
            parts = str(resolution).split("x")
            features["resolution_width"] = int(parts[0])
            features["resolution_height"] = int(parts[1])

        features = self._apply_style_feature_presets(features, label)
        return features

    def _apply_style_feature_presets(self, features: dict[str, float], label: str) -> dict[str, float]:
        """根据风格标签应用预设特征值"""
        presets = {
            "cinematic": {
                "brightness": 45, "saturation": 35, "warmth": 10,
                "cut_rate": 0.8, "avg_shot_duration": 2.5, "bpm": 80,
                "zoom_intensity": 105, "rotation_angle": 2, "shutter_angle": 180,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.2,
                "keyframes_density": 0.8, "motion_trajectory_complexity": 0.3,
                "color_vibrancy": 0.35, "contrast_ratio": 1.2,
                "depth_of_field": 0.7, "shot_transition_diversity": 0.3,
                "rhythm_consistency": 0.8, "visual_complexity": 0.4,
            },
            "fast_cut": {
                "brightness": 55, "saturation": 60, "warmth": 5,
                "cut_rate": 3.5, "avg_shot_duration": 0.25, "bpm": 140,
                "zoom_intensity": 125, "rotation_angle": 8, "shutter_angle": 360,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.7,
                "keyframes_density": 3.5, "motion_trajectory_complexity": 0.6,
                "color_vibrancy": 0.6, "contrast_ratio": 1.5,
                "depth_of_field": 0.2, "shot_transition_diversity": 0.8,
                "rhythm_consistency": 0.9, "visual_complexity": 0.7,
            },
            "slow_cut": {
                "brightness": 48, "saturation": 40, "warmth": 8,
                "cut_rate": 0.5, "avg_shot_duration": 3.0, "bpm": 60,
                "zoom_intensity": 102, "rotation_angle": 1, "shutter_angle": 180,
                "motion_blur_enabled": 0, "beat_sync_strength": 0.1,
                "keyframes_density": 0.5, "motion_trajectory_complexity": 0.2,
                "color_vibrancy": 0.4, "contrast_ratio": 1.1,
                "depth_of_field": 0.8, "shot_transition_diversity": 0.2,
                "rhythm_consistency": 0.6, "visual_complexity": 0.3,
            },
            "glitch_digital": {
                "brightness": 52, "saturation": 55, "warmth": -5,
                "cut_rate": 2.5, "avg_shot_duration": 0.4, "bpm": 140,
                "zoom_intensity": 110, "rotation_angle": 5, "shutter_angle": 180,
                "motion_blur_enabled": 0, "dynamic_tile_enabled": 1,
                "beat_sync_strength": 0.6, "keyframes_density": 2.5,
                "motion_trajectory_complexity": 0.8, "color_vibrancy": 0.55,
                "contrast_ratio": 1.8, "edge_detection_strength": 0.8,
                "depth_of_field": 0.1, "shot_transition_diversity": 0.9,
                "rhythm_consistency": 0.4, "visual_complexity": 0.9,
                "frame_rate_variation": 0.7,
            },
            "dark_tone": {
                "brightness": 30, "saturation": 30, "warmth": -10,
                "cut_rate": 1.0, "avg_shot_duration": 2.0, "bpm": 90,
                "zoom_intensity": 105, "rotation_angle": 3, "shutter_angle": 180,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.3,
                "keyframes_density": 1.0, "motion_trajectory_complexity": 0.3,
                "color_vibrancy": 0.2, "contrast_ratio": 1.8,
                "depth_of_field": 0.6, "shot_transition_diversity": 0.4,
                "rhythm_consistency": 0.7, "visual_complexity": 0.5,
            },
            "high_dynamic": {
                "brightness": 60, "saturation": 70, "warmth": 15,
                "cut_rate": 2.5, "avg_shot_duration": 0.4, "bpm": 150,
                "zoom_intensity": 135, "rotation_angle": 10, "shutter_angle": 270,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.8,
                "keyframes_density": 2.8, "motion_trajectory_complexity": 0.7,
                "color_vibrancy": 0.75, "contrast_ratio": 1.6,
                "depth_of_field": 0.3, "shot_transition_diversity": 0.7,
                "rhythm_consistency": 0.85, "visual_complexity": 0.8,
            },
            "low_saturation": {
                "brightness": 45, "saturation": 20, "warmth": 5,
                "cut_rate": 0.8, "avg_shot_duration": 2.0, "bpm": 75,
                "zoom_intensity": 102, "rotation_angle": 2, "shutter_angle": 180,
                "motion_blur_enabled": 0, "beat_sync_strength": 0.2,
                "keyframes_density": 0.8, "motion_trajectory_complexity": 0.25,
                "color_vibrancy": 0.15, "contrast_ratio": 1.0,
                "depth_of_field": 0.6, "shot_transition_diversity": 0.3,
                "rhythm_consistency": 0.75, "visual_complexity": 0.35,
            },
            "高饱和": {
                "brightness": 58, "saturation": 80, "warmth": 20,
                "cut_rate": 1.5, "avg_shot_duration": 1.2, "bpm": 100,
                "zoom_intensity": 115, "rotation_angle": 4, "shutter_angle": 220,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.5,
                "keyframes_density": 1.5, "motion_trajectory_complexity": 0.4,
                "color_vibrancy": 0.85, "contrast_ratio": 1.4,
                "depth_of_field": 0.4, "shot_transition_diversity": 0.5,
                "rhythm_consistency": 0.7, "visual_complexity": 0.6,
            },
            "长镜头": {
                "brightness": 48, "saturation": 42, "warmth": 8,
                "cut_rate": 0.2, "avg_shot_duration": 5.0, "bpm": 65,
                "zoom_intensity": 103, "rotation_angle": 1, "shutter_angle": 180,
                "motion_blur_enabled": 0, "beat_sync_strength": 0.15,
                "keyframes_density": 0.3, "motion_trajectory_complexity": 0.15,
                "color_vibrancy": 0.42, "contrast_ratio": 1.15,
                "depth_of_field": 0.9, "shot_transition_diversity": 0.1,
                "rhythm_consistency": 0.5, "visual_complexity": 0.25,
            },
            "amv_pull_zoom": {
                "brightness": 52, "saturation": 55, "warmth": 5,
                "cut_rate": 1.2, "avg_shot_duration": 1.2, "bpm": 100,
                "zoom_intensity": 115, "rotation_angle": 5, "shutter_angle": 180,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.4,
                "keyframes_density": 1.8, "motion_trajectory_complexity": 0.75,
                "color_vibrancy": 0.55, "contrast_ratio": 1.3,
                "depth_of_field": 0.4, "shot_transition_diversity": 0.6,
                "rhythm_consistency": 0.65, "visual_complexity": 0.65,
            },
            "amv_fast_cut": {
                "brightness": 58, "saturation": 68, "warmth": 8,
                "cut_rate": 3.8, "avg_shot_duration": 0.22, "bpm": 150,
                "zoom_intensity": 130, "rotation_angle": 12, "shutter_angle": 360,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.85,
                "keyframes_density": 4.0, "motion_trajectory_complexity": 0.8,
                "color_vibrancy": 0.7, "contrast_ratio": 1.7,
                "depth_of_field": 0.15, "shot_transition_diversity": 0.95,
                "rhythm_consistency": 0.95, "visual_complexity": 0.85,
            },
            "amv_beat_sync": {
                "brightness": 55, "saturation": 65, "warmth": 10,
                "cut_rate": 3.2, "avg_shot_duration": 0.28, "bpm": 140,
                "zoom_intensity": 125, "rotation_angle": 8, "shutter_angle": 270,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.95,
                "keyframes_density": 3.5, "motion_trajectory_complexity": 0.65,
                "color_vibrancy": 0.65, "contrast_ratio": 1.5,
                "depth_of_field": 0.25, "shot_transition_diversity": 0.85,
                "rhythm_consistency": 0.98, "visual_complexity": 0.75,
            },
            "amv_korean_flash": {
                "brightness": 65, "saturation": 75, "warmth": 15,
                "cut_rate": 4.2, "avg_shot_duration": 0.18, "bpm": 160,
                "zoom_intensity": 145, "rotation_angle": 15, "shutter_angle": 360,
                "motion_blur_enabled": 1, "dynamic_tile_enabled": 1,
                "beat_sync_strength": 0.9, "keyframes_density": 4.5,
                "motion_trajectory_complexity": 0.9, "color_vibrancy": 0.8,
                "contrast_ratio": 1.9, "edge_detection_strength": 0.6,
                "depth_of_field": 0.1, "shot_transition_diversity": 0.98,
                "rhythm_consistency": 0.92, "visual_complexity": 0.9,
                "frame_rate_variation": 0.5,
            },
            "amv_glitch": {
                "brightness": 52, "saturation": 50, "warmth": -8,
                "cut_rate": 2.8, "avg_shot_duration": 0.35, "bpm": 145,
                "zoom_intensity": 115, "rotation_angle": 6, "shutter_angle": 180,
                "motion_blur_enabled": 0, "dynamic_tile_enabled": 1,
                "beat_sync_strength": 0.65, "keyframes_density": 3.0,
                "motion_trajectory_complexity": 0.85, "color_vibrancy": 0.5,
                "contrast_ratio": 2.0, "edge_detection_strength": 0.9,
                "depth_of_field": 0.05, "shot_transition_diversity": 0.92,
                "rhythm_consistency": 0.45, "visual_complexity": 0.95,
                "frame_rate_variation": 0.8,
            },
            "amv_cinematic": {
                "brightness": 42, "saturation": 32, "warmth": 12,
                "cut_rate": 0.7, "avg_shot_duration": 3.0, "bpm": 75,
                "zoom_intensity": 102, "rotation_angle": 2, "shutter_angle": 180,
                "motion_blur_enabled": 1, "beat_sync_strength": 0.2,
                "keyframes_density": 0.6, "motion_trajectory_complexity": 0.25,
                "color_vibrancy": 0.3, "contrast_ratio": 1.25,
                "depth_of_field": 0.8, "shot_transition_diversity": 0.25,
                "rhythm_consistency": 0.85, "visual_complexity": 0.35,
            },
            "amv_3d_spatial": {
                "brightness": 50, "saturation": 52, "warmth": 3,
                "cut_rate": 1.5, "avg_shot_duration": 1.0, "bpm": 95,
                "zoom_intensity": 120, "rotation_angle": 6, "shutter_angle": 270,
                "motion_blur_enabled": 1, "dynamic_tile_enabled": 1,
                "beat_sync_strength": 0.45, "keyframes_density": 2.0,
                "motion_trajectory_complexity": 0.9, "color_vibrancy": 0.52,
                "contrast_ratio": 1.4, "depth_of_field": 0.5,
                "shot_transition_diversity": 0.7, "rhythm_consistency": 0.6,
                "visual_complexity": 0.7,
            },
            "amv_high_burn": {
                "brightness": 68, "saturation": 82, "warmth": 20,
                "cut_rate": 4.0, "avg_shot_duration": 0.18, "bpm": 170,
                "zoom_intensity": 150, "rotation_angle": 12, "shutter_angle": 360,
                "motion_blur_enabled": 1, "dynamic_tile_enabled": 1,
                "beat_sync_strength": 0.98, "keyframes_density": 4.8,
                "motion_trajectory_complexity": 0.85, "color_vibrancy": 0.88,
                "contrast_ratio": 2.2, "edge_detection_strength": 0.7,
                "depth_of_field": 0.08, "shot_transition_diversity": 0.95,
                "rhythm_consistency": 0.98, "visual_complexity": 0.92,
                "frame_rate_variation": 0.6,
            },
        }

        if label in presets:
            features.update(presets[label])

        return features

    def collect_from_amv_masters(self) -> int:
        count = 0
        if not self.amv_masters_dir.exists():
            return 0

        master_style_map = {
            "Floby-韩式快剪.md": "amv_korean_flash",
            "YUNG_DAGGER-卡点短剪.md": "amv_beat_sync",
            "YashFX-高燃插件流.md": "amv_high_burn",
            "Xenoz-推拉鼻祖.md": "amv_pull_zoom",
            "DxshNova-对角滑镜.md": "amv_pull_zoom",
            "Donya-三维空间.md": "amv_3d_spatial",
            "Molob-电影感大师.md": "amv_cinematic",
            "漫剪拉镜通用技法.md": "amv_pull_zoom",
        }

        for md_file in self.amv_masters_dir.glob("*.md"):
            if md_file.name not in master_style_map:
                continue

            label = master_style_map[md_file.name]
            label_id = self.STYLE_LABELS.get(label, 15)

            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            features = self._extract_amv_features(content, label)

            sample = StyleSample(
                sample_id=f"amv_{md_file.stem}",
                features=features,
                label=label,
                label_id=label_id,
                source=str(md_file),
                metadata={"master_doc": md_file.name, "style_family": "AMV"},
            )
            self.samples.append(sample)
            count += 1

        return count

    def _extract_amv_features(self, content: str, label: str) -> dict[str, float]:
        features = self._build_full_features({}, label)

        text = content.lower()

        bpm_matches = re.findall(r"(\d{2,3})\s*bpm", text)
        if bpm_matches:
            features["bpm"] = float(bpm_matches[0])

        zoom_matches = re.findall(r"(\d{2,3})%", text)
        if zoom_matches:
            zoom_vals = [int(z) for z in zoom_matches if 100 < int(z) <= 300]
            if zoom_vals:
                features["zoom_intensity"] = float(sum(zoom_vals) / len(zoom_vals))

        rot_matches = re.findall(r"(\d{1,2})°", text)
        if rot_matches:
            rot_vals = [int(r) for r in rot_matches if 0 < int(r) <= 45]
            if rot_vals:
                features["rotation_angle"] = float(sum(rot_vals) / len(rot_vals))

        shutter_matches = re.findall(r"(\d{2,3})°.*快门", text)
        if shutter_matches:
            features["shutter_angle"] = float(shutter_matches[0])
        elif "360°" in content or "360" in content:
            features["shutter_angle"] = 360.0

        if "运动模糊" in content or "motion blur" in text:
            features["motion_blur_enabled"] = 1.0
        if "不开运动模糊" in content:
            features["motion_blur_enabled"] = 0.0

        if "动态拼贴" in content or "dynamic tile" in text:
            features["dynamic_tile_enabled"] = 1.0

        if "关键帧" in content:
            features["keyframes_density"] *= 1.3
        if "曲线" in content or "bezier" in text:
            features["motion_trajectory_complexity"] = min(0.95, features["motion_trajectory_complexity"] * 1.2)

        return features

    def generate_amv_synthetic_samples(self) -> int:
        """生成大量合成样本，目标500+"""
        count = 0

        base_templates = [
            ("amv_pull_zoom", 100, 115, 5, 180, 1.2, 1.2, 0.4, 1, 1),
            ("amv_pull_zoom", 85, 110, 3, 180, 1.0, 1.5, 0.3, 1, 0),
            ("amv_pull_zoom", 120, 130, 8, 270, 1.8, 0.8, 0.6, 1, 1),
            ("amv_pull_zoom", 95, 112, 4, 220, 1.1, 1.3, 0.35, 1, 0),
            ("amv_pull_zoom", 110, 125, 6, 250, 1.5, 1.0, 0.5, 1, 1),
            ("amv_fast_cut", 140, 125, 10, 360, 3.5, 0.25, 0.7, 1, 0),
            ("amv_fast_cut", 160, 140, 12, 360, 4.0, 0.2, 0.8, 1, 1),
            ("amv_fast_cut", 130, 120, 8, 320, 3.0, 0.3, 0.65, 1, 0),
            ("amv_fast_cut", 150, 135, 11, 360, 3.8, 0.22, 0.75, 1, 1),
            ("amv_fast_cut", 170, 145, 14, 360, 4.2, 0.18, 0.85, 1, 1),
            ("amv_beat_sync", 130, 120, 6, 270, 3.0, 0.3, 0.85, 1, 0),
            ("amv_beat_sync", 150, 135, 8, 360, 3.8, 0.22, 0.95, 1, 1),
            ("amv_beat_sync", 170, 145, 10, 360, 4.5, 0.18, 1.0, 1, 1),
            ("amv_beat_sync", 120, 115, 5, 240, 2.5, 0.35, 0.8, 1, 0),
            ("amv_beat_sync", 145, 130, 7, 320, 3.5, 0.25, 0.9, 1, 1),
            ("amv_korean_flash", 145, 135, 12, 360, 3.8, 0.22, 0.8, 1, 1),
            ("amv_korean_flash", 160, 150, 15, 360, 4.2, 0.18, 0.9, 1, 1),
            ("amv_korean_flash", 155, 142, 13, 360, 4.0, 0.2, 0.85, 1, 1),
            ("amv_korean_flash", 170, 155, 16, 360, 4.5, 0.15, 0.95, 1, 1),
            ("amv_glitch", 140, 110, 5, 180, 2.5, 0.4, 0.6, 1, 0),
            ("amv_glitch", 155, 120, 8, 270, 3.0, 0.3, 0.7, 1, 1),
            ("amv_glitch", 135, 105, 4, 180, 2.2, 0.45, 0.55, 0, 0),
            ("amv_glitch", 160, 125, 9, 320, 3.2, 0.28, 0.75, 1, 1),
            ("amv_cinematic", 75, 105, 2, 180, 0.8, 2.5, 0.2, 1, 0),
            ("amv_cinematic", 90, 108, 3, 180, 1.0, 2.0, 0.3, 1, 0),
            ("amv_cinematic", 70, 102, 1, 180, 0.6, 3.0, 0.15, 1, 0),
            ("amv_cinematic", 85, 106, 2, 180, 0.9, 2.2, 0.25, 1, 0),
            ("amv_3d_spatial", 95, 120, 5, 270, 1.5, 1.0, 0.4, 1, 1),
            ("amv_3d_spatial", 110, 130, 8, 360, 2.0, 0.7, 0.5, 1, 1),
            ("amv_3d_spatial", 90, 115, 4, 240, 1.3, 1.2, 0.35, 1, 1),
            ("amv_3d_spatial", 105, 125, 6, 300, 1.8, 0.85, 0.45, 1, 1),
            ("amv_high_burn", 160, 140, 10, 360, 4.0, 0.2, 0.9, 1, 1),
            ("amv_high_burn", 175, 150, 12, 360, 4.5, 0.15, 1.0, 1, 1),
            ("amv_high_burn", 155, 135, 9, 360, 3.8, 0.22, 0.85, 1, 1),
            ("amv_high_burn", 180, 155, 13, 360, 4.8, 0.12, 1.0, 1, 1),
        ]

        for template_idx, (label, bpm, zoom, rot, shutter, cut_rate, duration, sync, blur, tile) in enumerate(base_templates):
            label_id = self.STYLE_LABELS.get(label, 15)

            for variant_idx in range(8):
                brightness = 50.0 + random.uniform(-10, 10)
                saturation = 50.0 + random.uniform(-15, 15)
                warmth = random.uniform(-15, 20)

                if "korean" in label or "high_burn" in label:
                    saturation = 65.0 + random.uniform(-10, 15)
                    brightness = 55.0 + random.uniform(-5, 15)
                elif "cinematic" in label:
                    saturation = 35.0 + random.uniform(-5, 10)
                    brightness = 45.0 + random.uniform(-5, 5)
                    warmth = 10.0 + random.uniform(-5, 5)
                elif "glitch" in label:
                    saturation = 45.0 + random.uniform(-10, 15)
                    brightness = 50.0 + random.uniform(-5, 10)
                    warmth = random.uniform(-15, 5)

                features = {
                    "brightness": brightness,
                    "saturation": saturation,
                    "warmth": warmth,
                    "cut_rate": float(cut_rate) * random.uniform(0.85, 1.15),
                    "avg_shot_duration": float(duration) * random.uniform(0.8, 1.2),
                    "resolution_width": 1920,
                    "resolution_height": 1080,
                    "bpm": float(bpm) * random.uniform(0.9, 1.1),
                    "zoom_intensity": float(zoom) * random.uniform(0.9, 1.1),
                    "rotation_angle": float(rot) * random.uniform(0.7, 1.3),
                    "shutter_angle": float(shutter),
                    "motion_blur_enabled": float(blur),
                    "dynamic_tile_enabled": float(tile),
                    "beat_sync_strength": float(sync) * random.uniform(0.8, 1.0),
                    "keyframes_density": float(cut_rate) * random.uniform(1.0, 1.5),
                    "motion_trajectory_complexity": random.uniform(0.3, 0.95),
                    "color_vibrancy": saturation / 100.0 * random.uniform(0.8, 1.2),
                    "contrast_ratio": random.uniform(1.0, 2.2),
                    "edge_detection_strength": random.uniform(0.0, 0.9),
                    "depth_of_field": random.uniform(0.05, 0.9),
                    "shot_transition_diversity": random.uniform(0.1, 0.98),
                    "rhythm_consistency": random.uniform(0.4, 0.98),
                    "frame_rate_variation": random.uniform(0.0, 0.8),
                    "visual_complexity": random.uniform(0.25, 0.95),
                }

                sample = StyleSample(
                    sample_id=f"amv_synth_{template_idx:03d}_{variant_idx:02d}_{label}",
                    features=features,
                    label=label,
                    label_id=label_id,
                    source="synthetic_amv_template",
                    metadata={
                        "style_family": "AMV",
                        "generation": "synthetic",
                        "template_index": template_idx,
                        "variant_index": variant_idx,
                    }
                )
                self.samples.append(sample)
                count += 1

        return count

    def generate_general_style_samples(self) -> int:
        """生成通用风格的合成样本"""
        count = 0

        general_templates = [
            ("cinematic", 80, 0.8, 2.5, 0.2),
            ("cinematic", 70, 0.7, 3.0, 0.15),
            ("cinematic", 90, 0.9, 2.0, 0.25),
            ("fast_cut", 140, 3.5, 0.25, 0.7),
            ("fast_cut", 160, 4.0, 0.2, 0.8),
            ("fast_cut", 130, 3.0, 0.3, 0.65),
            ("slow_cut", 60, 0.5, 3.0, 0.1),
            ("slow_cut", 55, 0.4, 3.5, 0.08),
            ("slow_cut", 65, 0.6, 2.5, 0.12),
            ("glitch_digital", 140, 2.5, 0.4, 0.6),
            ("glitch_digital", 150, 3.0, 0.35, 0.65),
            ("glitch_digital", 130, 2.0, 0.45, 0.55),
            ("dark_tone", 90, 1.0, 2.0, 0.3),
            ("dark_tone", 80, 0.8, 2.5, 0.25),
            ("dark_tone", 100, 1.2, 1.5, 0.35),
            ("high_dynamic", 150, 2.5, 0.4, 0.8),
            ("high_dynamic", 160, 3.0, 0.35, 0.85),
            ("high_dynamic", 140, 2.0, 0.45, 0.75),
            ("low_saturation", 75, 0.8, 2.0, 0.2),
            ("low_saturation", 70, 0.7, 2.5, 0.15),
            ("low_saturation", 80, 0.9, 1.5, 0.25),
            ("高饱和", 100, 1.5, 1.2, 0.5),
            ("高饱和", 110, 1.8, 1.0, 0.55),
            ("高饱和", 90, 1.2, 1.5, 0.45),
            ("长镜头", 65, 0.2, 5.0, 0.15),
            ("长镜头", 60, 0.15, 6.0, 0.12),
            ("长镜头", 70, 0.25, 4.0, 0.18),
            ("anime_puppet", 100, 1.2, 1.5, 0.4),
            ("anime_puppet", 90, 1.0, 1.8, 0.35),
            ("anime_puppet", 110, 1.4, 1.2, 0.45),
            ("audio_visual", 120, 2.0, 0.5, 0.5),
            ("audio_visual", 130, 2.5, 0.4, 0.6),
            ("audio_visual", 110, 1.5, 0.6, 0.45),
            ("particle_ambient", 90, 1.0, 1.8, 0.3),
            ("particle_ambient", 85, 0.8, 2.0, 0.25),
            ("particle_ambient", 95, 1.2, 1.5, 0.35),
            ("text_animation", 110, 1.5, 1.0, 0.4),
            ("text_animation", 100, 1.2, 1.2, 0.35),
            ("text_animation", 120, 1.8, 0.8, 0.45),
            ("3d_spatial", 95, 1.5, 1.0, 0.45),
            ("3d_spatial", 90, 1.3, 1.2, 0.4),
            ("3d_spatial", 100, 1.7, 0.8, 0.5),
            ("realistic_color", 85, 0.9, 2.0, 0.25),
            ("realistic_color", 80, 0.8, 2.2, 0.2),
            ("realistic_color", 90, 1.0, 1.8, 0.3),
        ]

        for template_idx, (label, bpm, cut_rate, duration, sync) in enumerate(general_templates):
            label_id = self.STYLE_LABELS.get(label, 0)

            for variant_idx in range(6):
                features = self._build_full_features({}, label)

                features["bpm"] = float(bpm) * random.uniform(0.85, 1.15)
                features["cut_rate"] = float(cut_rate) * random.uniform(0.8, 1.2)
                features["avg_shot_duration"] = float(duration) * random.uniform(0.8, 1.2)
                features["beat_sync_strength"] = float(sync) * random.uniform(0.8, 1.0)

                features["brightness"] += random.uniform(-8, 8)
                features["saturation"] += random.uniform(-10, 10)
                features["warmth"] += random.uniform(-8, 8)

                features["zoom_intensity"] = 100 + random.uniform(-10, 30)
                features["rotation_angle"] = random.uniform(0, 15)
                features["motion_trajectory_complexity"] = random.uniform(0.15, 0.7)
                features["visual_complexity"] = random.uniform(0.2, 0.7)

                sample = StyleSample(
                    sample_id=f"general_synth_{template_idx:03d}_{variant_idx:02d}_{label}",
                    features=features,
                    label=label,
                    label_id=label_id,
                    source="synthetic_general_template",
                    metadata={
                        "style_family": "General",
                        "generation": "synthetic",
                        "template_index": template_idx,
                        "variant_index": variant_idx,
                    }
                )
                self.samples.append(sample)
                count += 1

        return count

    def augment(self) -> int:
        """数据增强：对现有样本进行变换"""
        original_count = len(self.samples)
        augmented = []

        for sample in self.samples:
            augmented.append(sample)

            for _ in range(3):
                new_features = sample.features.copy()

                new_features["brightness"] = min(100, max(0, new_features["brightness"] * random.uniform(0.85, 1.15)))
                new_features["saturation"] = min(100, max(0, new_features["saturation"] * random.uniform(0.8, 1.2)))
                new_features["warmth"] = new_features["warmth"] * random.uniform(0.8, 1.2)

                new_features["cut_rate"] = new_features["cut_rate"] * random.uniform(0.85, 1.15)
                new_features["avg_shot_duration"] = new_features["avg_shot_duration"] * random.uniform(0.8, 1.2)
                new_features["bpm"] = new_features["bpm"] * random.uniform(0.85, 1.15)

                new_features["zoom_intensity"] = min(200, max(80, new_features["zoom_intensity"] * random.uniform(0.85, 1.15)))
                new_features["rotation_angle"] = max(0, new_features["rotation_angle"] * random.uniform(0.7, 1.3))

                new_features["keyframes_density"] = new_features["keyframes_density"] * random.uniform(0.8, 1.2)
                new_features["motion_trajectory_complexity"] = min(1.0, max(0, new_features["motion_trajectory_complexity"] + random.uniform(-0.1, 0.1)))
                new_features["color_vibrancy"] = min(1.0, max(0, new_features["color_vibrancy"] + random.uniform(-0.1, 0.1)))
                new_features["contrast_ratio"] = max(0.5, new_features["contrast_ratio"] * random.uniform(0.9, 1.1))

                augmented.append(StyleSample(
                    sample_id=f"{sample.sample_id}_aug_{len(augmented)}",
                    features=new_features,
                    label=sample.label,
                    label_id=sample.label_id,
                    source=f"{sample.source}_augmented",
                    metadata={**sample.metadata, "augmentation": "param_jitter"}
                ))

        self.samples = augmented
        return len(self.samples) - original_count

    def save(self, output_path: Path) -> int:
        output_path = safe_output_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for sample in self.samples:
                f.write(json.dumps(asdict(sample)) + "\n")

        return len(self.samples)

    def get_stats(self) -> dict[str, Any]:
        label_counts = {}
        for sample in self.samples:
            label_counts[sample.label] = label_counts.get(sample.label, 0) + 1

        return {
            "total_samples": len(self.samples),
            "label_distribution": label_counts,
            "feature_names": self.ALL_FEATURE_NAMES,
            "feature_dim": len(self.ALL_FEATURE_NAMES),
        }


class JSXDatasetBuilder:
    TASK_TYPES = ["effect_apply", "layer_create", "animation_keyframe", "expression", "general"]

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.presets_path = project_root / "config" / "effect_presets.json"
        self.expression_lib_path = project_root / "output_director" / "ae_project_analysis" / "replicate_templates" / "expression_template_library.json"
        self.style_presets_dir = project_root / "output_director" / "ae_project_analysis" / "style_presets"
        self.replicate_dir = project_root / "output_director" / "ae_project_analysis" / "replicate_templates"
        self.samples: list[JSXCodeSample] = []

    def collect_from_presets(self) -> int:
        count = 0
        if not self.presets_path.exists():
            return 0

        with open(self.presets_path, encoding="utf-8") as f:
            data = json.load(f)

        effects = data.get("effects", {})

        for effect_name, effect_data in effects.items():
            match_name = effect_data.get("match_name", effect_name)
            params = effect_data.get("params", {})

            for preset in effect_data.get("presets", []):
                code = self._generate_effect_code(match_name, preset.get("params", params))

                sample = JSXCodeSample(
                    sample_id=f"preset_{effect_name}_{preset.get('name', 'default')}",
                    code=code,
                    task_type="effect_apply",
                    description=f"应用{effect_name}效果，预设：{preset.get('name', '默认')}",
                    parameters=preset.get("params", {}),
                    source=str(self.presets_path),
                    code_length=len(code)
                )
                self.samples.append(sample)
                count += 1

        return count

    def collect_from_expressions(self) -> int:
        count = 0
        if not self.expression_lib_path.exists():
            return 0

        with open(self.expression_lib_path, encoding="utf-8") as f:
            data = json.load(f)

        expressions = data.get("expressions", {})

        for expr_name, expr_data in expressions.items():
            code = expr_data.get("code", "")
            if not code:
                continue

            sample = JSXCodeSample(
                sample_id=f"expr_{expr_name}",
                code=code,
                task_type="expression",
                description=expr_data.get("description", ""),
                parameters={"category": expr_data.get("category", "general")},
                source=expr_data.get("source_project", "unknown"),
                code_length=len(code)
            )
            self.samples.append(sample)
            count += 1

        return count

    def collect_from_style_presets(self) -> int:
        count = 0
        if not self.style_presets_dir.exists():
            return 0

        for jsx_file in self.style_presets_dir.glob("style_*.jsx"):
            try:
                code = jsx_file.read_text(encoding="utf-8", errors="ignore")
                style_name = jsx_file.stem.replace("style_", "")

                sample = JSXCodeSample(
                    sample_id=f"style_{style_name}",
                    code=code,
                    task_type="effect_apply",
                    description=f"风格预设：{style_name}",
                    parameters={"style": style_name},
                    source=str(jsx_file),
                    code_length=len(code)
                )
                self.samples.append(sample)
                count += 1
            except Exception:
                continue

        return count

    def collect_from_replicate_templates(self) -> int:
        count = 0
        if not self.replicate_dir.exists():
            return 0

        for jsx_file in self.replicate_dir.glob("replicate_*.jsx"):
            if "backup" in str(jsx_file):
                continue

            try:
                code = jsx_file.read_text(encoding="utf-8", errors="ignore")
                template_name = jsx_file.stem.replace("replicate_", "")

                sample = JSXCodeSample(
                    sample_id=f"replicate_{template_name}",
                    code=code,
                    task_type=self._classify_jsx_task(code),
                    description=f"复刻模板：{template_name}",
                    parameters={"template": template_name},
                    source=str(jsx_file),
                    code_length=len(code)
                )
                self.samples.append(sample)
                count += 1
            except Exception:
                continue

        return count

    def _generate_effect_code(self, match_name: str, params: dict[str, Any]) -> str:
        param_strs = []
        for param_name, param_value in params.items():
            if isinstance(param_value, list):
                param_strs.append(f'        "{param_name}": [{", ".join(map(str, param_value))}]')
            else:
                param_strs.append(f'        "{param_name}": {param_value}')

        newline = "\n"
        params_content = f",{newline}".join(param_strs)

        return f'''// 应用效果 {match_name}
var layer = app.project.activeItem.selectedLayers[0];
var effect = layer.Effects.addProperty("{match_name}");

var params = {{
{params_content}
}};

for (var key in params) {{
    try {{
        effect.property(key).setValue(params[key]);
    }} catch (e) {{
    }}
}}
'''

    def _classify_jsx_task(self, code: str) -> str:
        code_lower = code.lower()

        if "keyframe" in code_lower or "setvalueattime" in code_lower:
            return "animation_keyframe"
        elif "addlayer" in code_lower or "layers.add" in code_lower:
            return "layer_create"
        elif "effects.addproperty" in code_lower or "adbe" in code_lower:
            return "effect_apply"
        elif "wiggle" in code_lower or "loopout" in code_lower or "expression" in code_lower:
            return "expression"
        else:
            return "general"

    def clean_code(self) -> int:
        cleaned = []

        for sample in self.samples:
            code = sample.code
            code = re.sub(r'//.*$', '', code, flags=re.MULTILINE)
            code = re.sub(r'/\*.*?\*/', '', code, flags=re.DOTALL)
            code = re.sub(r'\n{3,}', '\n\n', code)
            code = code.strip()

            if len(code) > 50:
                sample.code = code
                sample.code_length = len(code)
                cleaned.append(sample)

        self.samples = cleaned
        return len(self.samples)

    def save(self, output_path: Path) -> int:
        output_path = safe_output_path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            for sample in self.samples:
                f.write(json.dumps(asdict(sample)) + "\n")

        return len(self.samples)

    def get_stats(self) -> dict[str, Any]:
        task_counts = {}
        total_length = 0

        for sample in self.samples:
            task_counts[sample.task_type] = task_counts.get(sample.task_type, 0) + 1
            total_length += sample.code_length

        return {
            "total_samples": len(self.samples),
            "task_type_distribution": task_counts,
            "avg_code_length": total_length / len(self.samples) if self.samples else 0,
            "total_code_length": total_length,
        }


def main():
    parser = argparse.ArgumentParser(description="训练数据准备 - 优化版本")
    parser.add_argument("--task", choices=["style", "jsx", "all"], default="all", help="数据集类型")
    parser.add_argument("--output", type=str, default="data/", help="输出目录")
    parser.add_argument("--augment", action="store_true", help="启用数据增强")
    parser.add_argument("--clean", action="store_true", default=True, help="清洗数据")
    args = parser.parse_args()

    try:
        output_dir = safe_output_path(args.output)
    except ValueError as _e:
        print(f"[ERR] 输出路径非法: {_e}")
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("训练数据准备 - AE Knowledge Vault (优化版本)")
    print("=" * 60)

    if args.task in ["style", "all"]:
        print("\n[1] 构建风格分类数据集...")
        builder = StyleDatasetBuilder(PROJECT_ROOT)

        count = builder.collect_from_fingerprints()
        print(f"  收集指纹样本: {count}")

        count = builder.collect_from_amv_masters()
        print(f"  收集漫剪大师样本: {count}")

        count = builder.generate_amv_synthetic_samples()
        print(f"  生成漫剪合成样本: {count}")

        count = builder.generate_general_style_samples()
        print(f"  生成通用风格合成样本: {count}")

        if args.augment:
            count = builder.augment()
            print(f"  数据增强新增样本: {count}")

        stats = builder.get_stats()
        print("\n  数据集统计:")
        print(f"  总样本数: {stats['total_samples']}")
        print(f"  特征维度: {stats['feature_dim']}")
        print("  标签分布:")
        for k, v in sorted(stats['label_distribution'].items()):
            print(f"    {k}: {v}")

        output_path = output_dir / "style_classify_dataset.jsonl"
        saved = builder.save(output_path)
        print(f"  保存到: {output_path} ({saved} 样本)")

    if args.task in ["jsx", "all"]:
        print("\n[2] 构建JSX代码数据集...")
        builder = JSXDatasetBuilder(PROJECT_ROOT)

        count = builder.collect_from_presets()
        print(f"  收集预设样本: {count}")

        count = builder.collect_from_expressions()
        print(f"  收集表达式样本: {count}")

        count = builder.collect_from_style_presets()
        print(f"  收集风格预设样本: {count}")

        count = builder.collect_from_replicate_templates()
        print(f"  收集复刻模板样本: {count}")

        if args.clean:
            count = builder.clean_code()
            print(f"  清洗后样本: {count}")

        stats = builder.get_stats()
        print(f"  任务类型分布: {stats['task_type_distribution']}")
        print(f"  平均代码长度: {stats['avg_code_length']:.0f} 字符")

        output_path = output_dir / "jsx_code_dataset.jsonl"
        saved = builder.save(output_path)
        print(f"  保存到: {output_path} ({saved} 样本)")

    print("\n" + "=" * 60)
    print("数据准备完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
