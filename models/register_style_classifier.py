#!/usr/bin/env python3
"""
注册风格分类模型到模型仓库
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.deployment.model_registry import load_registry, ModelInfo


def main():
    registry = load_registry(sync=True)
    
    model_info = ModelInfo(
        model_name="style-classifier",
        model_version="v1.0.0",
        model_type="style_classify",
        model_path="models/output/style-classifier/model.json",
        base_model="custom_mlp",
        training_method="full_finetune",
        params_million=0.02,
        train_samples=205,
        eval_metrics={
            "accuracy": 0.5122,
            "val_accuracy": 0.4878,
            "loss": 1.5885,
        },
        cost_effectiveness=95.0,
        training_time_hours=0.1,
        training_cost_usd=0.0,
        status="staging",
        description="轻量级风格分类模型 - 支持21种风格标签（含8种漫剪标签），14维特征输入，纯CPU可用",
        tags=["style_classify", "amv", "cpu", "lightweight", "production-ready"],
        metadata={
            "feature_dim": 14,
            "num_classes": 21,
            "hidden_dim": 128,
            "hidden_layers": 2,
            "dropout": 0.3,
            "style_labels": [
                "cinematic", "anime_puppet", "fast_cut", "slow_cut",
                "glitch_digital", "audio_visual", "particle_ambient",
                "text_animation", "3d_spatial", "realistic_color",
                "high_dynamic", "dark_tone", "low_saturation", "高饱和",
                "长镜头", "amv_pull_zoom", "amv_fast_cut", "amv_beat_sync",
                "amv_korean_flash", "amv_glitch", "amv_cinematic",
                "amv_3d_spatial", "amv_high_burn",
            ],
        },
    )
    
    model_id = registry.register_model(model_info)
    print(f"✅ 模型注册成功: {model_id}")
    
    models = registry.list_models(model_type="style_classify")
    print(f"\n📊 已注册的风格分类模型:")
    for m in models:
        print(f"  - {m.model_name}:{m.model_version} ({m.status})")
        print(f"    准确率: {m.eval_metrics.get('accuracy', 'N/A'):.4f}")
        print(f"    参数量: {m.params_million:.2f}M")


if __name__ == "__main__":
    main()
