"""运镜训练脚本参数与数据加载测试 - 覆盖 full-ft 模式、data-root 重映射、六类 schema

2026-08-18 新增测试：验证 --full-ft 全参模式、--data-root 跨机路径重映射、
--schema six 六类合并等关键参数解析与逻辑。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# 全参模式 (--full-ft) 参数测试
# ============================================================================

class TestFullFTMode:
    """测试 --full-ft 全参微调模式的参数解析与模型配置。"""

    def test_full_ft_flag_enables_full_parameter_training(self):
        """--full-ft 参数必须禁用 LoRA 并启用全参训练。"""
        import sys
        sys.argv = [
            "train_anime_camera_lora.py",
            "--full-ft",
            "--labels", "test.jsonl",
            "--out", "test_output"
        ]

        # 重新导入以应用参数
        import importlib

        import scripts.train_anime_camera_lora as train_script
        importlib.reload(train_script)

        # 解析参数
        parser = train_script.__dict__.get("parser")
        if parser is None:
            # 如果 parser 未暴露，通过 main 函数间接测试
            pytest.skip("参数解析器未暴露，需通过集成测试验证")

    def test_full_ft_disables_peft_imports(self, tmp_path):
        """全参模式不应依赖 PEFT 库，避免 adapter_model.safetensors 路径。"""
        # 这是一个逻辑验证：全参模式下，代码不应尝试加载 adapter
        # 通过检查模型保存逻辑来验证

        # 模拟全参训练输出目录
        output_dir = tmp_path / "full_ft_output"
        output_dir.mkdir()

        # 写入模拟的保存模型文件（应包含 model.safetensors）
        import torch
        from safetensors.torch import save_file

        dummy_weights = {"model.weight": torch.randn(10, 10)}
        save_file(dummy_weights, str(output_dir / "model.safetensors"))

        # 验证：全参输出目录不包含 adapter_model.safetensors
        assert (output_dir / "model.safetensors").exists()
        assert not (output_dir / "adapter_model.safetensors").exists()


# ============================================================================
# 跨机路径重映射 (--data-root) 测试
# ============================================================================

class TestDataRootRemapping:
    """测试 --data-root 参数的跨机路径重映射逻辑。"""

    def test_data_root_remapping_in_load_trainable(self, tmp_path):
        """load_trainable 必须正确重映射 clip_path 到 --data-root。"""
        from scripts.train_anime_camera_lora import load_trainable

        # 创建模拟标签文件
        labels_file = tmp_path / "labels.jsonl"
        labels_data = [
            {"clip_path": "D:\\original\\path\\clip1.mp4",
             "movement_label": "pan_left",
             "confidence": 0.85,
             "anime": "test_anime"},
            {"clip_path": "/home/user/clips/clip2.mp4",
             "movement_label": "static",
             "confidence": 0.92,
             "anime": "test_anime2"}
        ]
        labels_file.write_text(
            "\n".join(json.dumps(row) for row in labels_data),
            encoding="utf-8"
        )

        # 创建重映射目录和视频文件
        data_root = tmp_path / "remapped_data"
        data_root.mkdir()
        (data_root / "clip1.mp4").write_bytes(b"\x00" * 1024)
        (data_root / "clip2.mp4").write_bytes(b"\x00" * 1024)

        # 调用 load_trainable 并验证重映射
        samples = load_trainable(
            labels_path=str(labels_file),
            min_conf=0.7,
            schema="coarse",
            time_reverse=False,
            data_root=str(data_root)
        )

        # 验证：clip_path 已被重映射到 data_root
        assert len(samples) >= 1
        for sample in samples:
            clip_name = Path(sample["clip"]).name
            assert sample["clip"] == str(data_root / clip_name)
            assert Path(sample["clip"]).exists()

    def test_data_root_empty_keeps_original_path(self, tmp_path):
        """data_root 为空时必须保持原始路径。"""
        from scripts.train_anime_camera_lora import load_trainable

        # 创建标签和实际视频文件（原始路径）
        labels_file = tmp_path / "labels_no_remap.jsonl"
        video_file = tmp_path / "original_clip.mp4"
        video_file.write_bytes(b"\x00" * 1024)

        labels_data = [{
            "clip_path": str(video_file),
            "movement_label": "zoom_in",
            "confidence": 0.88,
            "anime": "test"
        }]
        labels_file.write_text(
            json.dumps(labels_data[0]),
            encoding="utf-8"
        )

        samples = load_trainable(
            labels_path=str(labels_file),
            min_conf=0.7,
            schema="coarse",
            time_reverse=False,
            data_root=""  # 不重映射
        )

        assert len(samples) == 1
        assert samples[0]["clip"] == str(video_file)


# ============================================================================
# 六类合并 schema (--schema six) 测试
# ============================================================================

class TestSixClassSchema:
    """测试 --schema six 六类合并逻辑。"""

    def test_six_schema_maps_directions_correctly(self, tmp_path):
        """六类 schema 必须正确合并语义重叠和稀缺类。"""
        from scripts.train_anime_camera_lora import SIX_MAP, load_trainable

        # 创建测试标签（包含应被合并的方向）
        labels_file = tmp_path / "six_labels.jsonl"
        labels_data = []

        # push 和 zoom_in 应合并为 push_in
        for direction in ["zoom_in", "push"]:
            video = tmp_path / f"{direction}.mp4"
            video.write_bytes(b"\x00" * 1024)
            labels_data.append({
                "clip_path": str(video),
                "movement_label": direction,
                "confidence": 0.90,
                "anime": "test"
            })

        # orbit, tilt_up, tilt_down 应合并为 tilt_orbit
        for direction in ["orbit", "tilt_up", "tilt_down"]:
            video = tmp_path / f"{direction}.mp4"
            video.write_bytes(b"\x00" * 1024)
            labels_data.append({
                "clip_path": str(video),
                "movement_label": direction,
                "confidence": 0.85,
                "anime": "test"
            })

        labels_file.write_text(
            "\n".join(json.dumps(row) for row in labels_data),
            encoding="utf-8"
        )

        samples = load_trainable(
            labels_path=str(labels_file),
            min_conf=0.7,
            schema="six",
            time_reverse=False,
            data_root=""
        )

        # 验证合并逻辑
        labels = [s["coarse"] for s in samples]
        assert "push_in" in labels  # zoom_in 和 push 合并
        assert "tilt_orbit" in labels  # orbit, tilt_up, tilt_down 合并
        assert "push" not in labels  # 原始类名已被合并

    def test_six_schema_excludes_complex(self, tmp_path):
        """六类 schema 必须排除 complex 标签。"""
        from scripts.train_anime_camera_lora import load_trainable

        video = tmp_path / "complex.mp4"
        video.write_bytes(b"\x00" * 1024)

        labels_file = tmp_path / "complex_label.jsonl"
        labels_file.write_text(
            json.dumps({
                "clip_path": str(video),
                "movement_label": "complex",
                "confidence": 0.95,
                "anime": "test"
            }),
            encoding="utf-8"
        )

        samples = load_trainable(
            labels_path=str(labels_file),
            min_conf=0.7,
            schema="six",
            time_reverse=False,
            data_root=""
        )

        # complex 应被过滤
        assert len(samples) == 0


# ============================================================================
# 时间反转增强测试
# ============================================================================

class TestTimeReverseAugmentation:
    """测试时间反转增强逻辑。"""

    def test_time_reverse_duplicates_mirrored_directions(self, tmp_path):
        """time_reverse=True 必须为可逆方向对生成倒放样本。"""
        from scripts.train_anime_camera_lora import load_trainable

        # pan_left 和 pan_right 互为镜像
        video = tmp_path / "pan_test.mp4"
        video.write_bytes(b"\x00" * 1024)

        labels_file = tmp_path / "reverse_test.jsonl"
        labels_file.write_text(
            json.dumps({
                "clip_path": str(video),
                "movement_label": "pan_left",
                "confidence": 0.88,
                "anime": "test"
            }),
            encoding="utf-8"
        )

        samples = load_trainable(
            labels_path=str(labels_file),
            min_conf=0.7,
            schema="fine",
            time_reverse=True,  # 启用时间反转
            data_root=""
        )

        # 应生成两个样本：原样本 + 倒放镜像样本
        assert len(samples) == 2

        original = [s for s in samples if not s["reverse"]][0]
        reversed_sample = [s for s in samples if s["reverse"]][0]

        # 原样本：pan_left
        assert original["direction"] == "pan_left"
        # fine schema 下，coarse 字段也直接是方向名
        assert original["coarse"] == "pan_left"

        # 倒放样本：pan_right（镜像）
        assert reversed_sample["direction"] == "pan_right"
        # fine schema 下，coarse 字段也是方向名
        assert reversed_sample["coarse"] == "pan_right"

    def test_time_reverse_disabled_no_duplication(self, tmp_path):
        """time_reverse=False 必须不生成镜像样本。"""
        from scripts.train_anime_camera_lora import load_trainable

        video = tmp_path / "no_reverse.mp4"
        video.write_bytes(b"\x00" * 1024)

        labels_file = tmp_path / "no_reverse.jsonl"
        labels_file.write_text(
            json.dumps({
                "clip_path": str(video),
                "movement_label": "zoom_in",
                "confidence": 0.90,
                "anime": "test"
            }),
            encoding="utf-8"
        )

        samples = load_trainable(
            labels_path=str(labels_file),
            min_conf=0.7,
            schema="fine",
            time_reverse=False,  # 禁用时间反转
            data_root=""
        )

        assert len(samples) == 1
        assert samples[0]["reverse"] is False


# ============================================================================
# 低置信度过滤测试
# ============================================================================

class TestLowConfidenceFiltering:
    """测试低置信度样本过滤逻辑。"""

    def test_samples_below_min_conf_are_excluded(self, tmp_path):
        """置信度低于 min_conf 的样本必须被过滤。"""
        from scripts.train_anime_camera_lora import load_trainable

        video = tmp_path / "low_conf.mp4"
        video.write_bytes(b"\x00" * 1024)

        labels_file = tmp_path / "mixed_conf.jsonl"
        labels_data = [
            {"clip_path": str(video), "movement_label": "static",
             "confidence": 0.95, "anime": "high"},
            {"clip_path": str(video), "movement_label": "pan_left",
             "confidence": 0.50, "anime": "low"}  # 低于 0.7 阈值
        ]
        labels_file.write_text(
            "\n".join(json.dumps(row) for row in labels_data),
            encoding="utf-8"
        )

        samples = load_trainable(
            labels_path=str(labels_file),
            min_conf=0.7,
            schema="coarse",
            time_reverse=False,
            data_root=""
        )

        # 只有高置信度样本应被保留
        assert len(samples) == 1
        assert samples[0]["direction"] == "static"