"""动漫运镜分类器测试 - 覆盖全参模型加载、阈值校准、降级链路

2026-08-18 新增测试：验证 v4 全参模型加载分支（full-ft），
确保 LoRA 与全参两种形态都能正确加载并推理。
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# 全参模型加载分支测试
# ============================================================================

class TestFullFTModelLoading:
    """测试全参模型（v4+）加载路径，验证不依赖 LoRA adapter 的直接加载。"""

    def test_full_ft_model_loaded_without_adapter(self, tmp_path):
        """全参模型目录不包含 adapter_model.safetensors 时，必须走直接加载分支。"""
        # 创建模拟的全参模型目录
        model_dir = tmp_path / "full_ft_model"
        model_dir.mkdir()

        # 写入 meta.json（fine schema）
        meta = {"labels": ["static", "pan_left", "pan_right", "tilt_up",
                          "tilt_down", "zoom_in", "zoom_out", "push",
                          "zoom_back", "orbit"]}
        (model_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        # 不创建 adapter_model.safetensors（模拟全参形态）

        # Mock torch 和 transformers（在函数内部导入）
        mock_model = MagicMock()
        mock_model.config.num_labels = 10
        mock_model.eval = MagicMock(return_value=mock_model)
        mock_model.to = MagicMock(return_value=mock_model)

        with patch("torch.cuda.is_available", return_value=False), \
             patch("transformers.VideoMAEForVideoClassification.from_pretrained",
                   return_value=mock_model) as mock_from_pretrained:

            from models.anime_camera_classifier import AnimeCameraClassifier

            clf = AnimeCameraClassifier(lora_dir=str(model_dir))

            # 触发模型加载
            success = clf._ensure_model()

            # 验证：应调用 from_pretrained 加载全参模型
            assert success is True
            mock_from_pretrained.assert_called_once()

    def test_full_ft_with_cuda_device_placement(self, tmp_path):
        """全参模型在 CUDA 可用时必须正确放置到 GPU。"""
        model_dir = tmp_path / "full_ft_cuda"
        model_dir.mkdir()

        meta = {"labels": ["static", "Motion", "Pull", "Push"]}
        (model_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        mock_model = MagicMock()
        mock_model.config.num_labels = 4
        mock_model.eval = MagicMock(return_value=mock_model)
        mock_device = None
        def mock_to(device):
            nonlocal mock_device
            mock_device = device
            return mock_model
        mock_model.to = mock_to

        with patch("torch.cuda.is_available", return_value=True), \
             patch("transformers.VideoMAEForVideoClassification.from_pretrained",
                   return_value=mock_model) as mock_from_pretrained:

            from models.anime_camera_classifier import AnimeCameraClassifier

            clf = AnimeCameraClassifier(lora_dir=str(model_dir))
            success = clf._ensure_model()

            assert success is True
            assert mock_device == "cuda"
            mock_from_pretrained.assert_called_once_with(
                str(model_dir), local_files_only=True
            )


# ============================================================================
# 阈值加载测试
# ============================================================================

class TestThresholdLoading:
    """测试分类阈值配置加载与校验。"""

    def test_thresholds_loaded_from_json(self, tmp_path):
        """阈值必须正确从 JSON 文件加载。"""
        thresh_file = tmp_path / "thresholds.json"
        thresholds_data = {
            "thresholds": {
                "Static": 0.55,
                "Motion": 0.48,
                "Pull": 0.20,
                "Push": 0.42
            }
        }
        thresh_file.write_text(json.dumps(thresholds_data), encoding="utf-8")

        from models.anime_camera_classifier import AnimeCameraClassifier

        labels = ["Static", "Motion", "Pull", "Push"]
        loaded = AnimeCameraClassifier._load_thresholds(str(thresh_file), labels)

        assert loaded is not None
        assert loaded["Static"] == 0.55
        assert loaded["Motion"] == 0.48
        assert loaded["Pull"] == 0.20
        assert loaded["Push"] == 0.42

    def test_thresholds_none_on_missing_file(self):
        """阈值文件缺失时必须返回 None（不做门控），禁止伪造默认值。"""
        from models.anime_camera_classifier import AnimeCameraClassifier

        loaded = AnimeCameraClassifier._load_thresholds(
            "/nonexistent/path/thresholds.json", ["Static", "Motion", "Pull", "Push"])

        assert loaded is None

    def test_thresholds_none_on_incomplete_coverage(self, tmp_path):
        """侧车未覆盖全部标签时必须返回 None，不得让未覆盖类共用一个阈值。"""
        thresh_file = tmp_path / "coarse_vs_fine.json"
        coarse = {"thresholds": {"Static": 0.55, "Motion": 0.48,
                                 "Pull": 0.20, "Push": 0.42}}
        thresh_file.write_text(json.dumps(coarse), encoding="utf-8")

        from models.anime_camera_classifier import AnimeCameraClassifier

        fine_labels = ["static", "pan_left", "pan_right", "tilt_up", "tilt_down",
                       "zoom_in", "zoom_out", "push", "zoom_back", "orbit"]
        loaded = AnimeCameraClassifier._load_thresholds(str(thresh_file), fine_labels)

        assert loaded is None


# ============================================================================
# Schema 自动识别测试
# ============================================================================

class TestSchemaAutoDetection:
    """测试 fine/coarse schema 自动识别。"""

    def test_fine_schema_detected_for_10_classes(self, tmp_path):
        """meta.json 包含 10 类标签时必须识别为 fine schema。"""
        model_dir = tmp_path / "fine_model"
        model_dir.mkdir()

        meta = {"labels": ["static", "pan_left", "pan_right", "tilt_up",
                          "tilt_down", "zoom_in", "zoom_out", "push",
                          "zoom_back", "orbit"]}
        (model_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        with patch("models.anime_camera_classifier.Path") as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.__truediv__ = lambda self, other: mock_path_instance
            mock_path_instance.read_text.return_value = json.dumps(meta)
            mock_path_class.return_value = mock_path_instance

            from models.anime_camera_classifier import AnimeCameraClassifier

            clf = AnimeCameraClassifier(lora_dir=str(model_dir))

            assert clf.schema == "fine"
            assert len(clf.labels) == 10

    def test_coarse_schema_detected_for_4_classes(self, tmp_path):
        """meta.json 包含 4 类标签时必须识别为 coarse schema。"""
        model_dir = tmp_path / "coarse_model"
        model_dir.mkdir()

        meta = {"labels": ["Static", "Motion", "Pull", "Push"]}
        (model_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        with patch("models.anime_camera_classifier.Path") as mock_path_class:
            mock_path_instance = MagicMock()
            mock_path_instance.exists.return_value = True
            mock_path_instance.__truediv__ = lambda self, other: mock_path_instance
            mock_path_instance.read_text.return_value = json.dumps(meta)
            mock_path_class.return_value = mock_path_instance

            from models.anime_camera_classifier import AnimeCameraClassifier

            clf = AnimeCameraClassifier(lora_dir=str(model_dir))

            assert clf.schema == "coarse"
            assert len(clf.labels) == 4


# ============================================================================
# 降级链路测试
# ============================================================================

class TestDegradationFallback:
    """测试模型加载失败时的降级链路。"""

    def test_nonexistent_video_returns_unknown(self, tmp_path):
        """视频文件不存在时必须快速返回 unknown，不触发模型加载。"""
        from models.anime_camera_classifier import AnimeCameraClassifier

        clf = AnimeCameraClassifier(lora_dir=str(tmp_path))

        result = clf.classify_video("/nonexistent/video.mp4")

        assert result["label"] == "unknown"
        assert result["confidence"] == 0.0
        assert result["source"] == "unknown"

    def test_model_load_failure_falls_back_to_flow_rule(self, tmp_path):
        """模型加载失败时必须降级到光流规则或返回 unknown。

        由于 core.camera_movement_classifier 模块可能未部署，
        测试应能处理两种情况：成功降级或返回 unknown。
        """
        model_dir = tmp_path / "failed_model"
        model_dir.mkdir()

        meta = {"labels": ["Static", "Motion", "Pull", "Push"]}
        (model_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

        # 创建一个临时视频文件用于测试
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"\x00" * 1024)  # 最小占位

        with patch("transformers.VideoMAEForVideoClassification.from_pretrained",
                   side_effect=RuntimeError("Model load failed")):

            from models.anime_camera_classifier import AnimeCameraClassifier

            clf = AnimeCameraClassifier(lora_dir=str(model_dir))

            # Mock 光流规则降级（如果模块存在）
            # 注意：sys.modules 注入必须限定在 try/finally 内，
            # 否则会永久污染 core.camera_movement_classifier，
            # 导致后续 camera_classifier/camera_decision/videomae 等测试串扰失败。
            import sys
            _orig_ccc = sys.modules.get('core.camera_movement_classifier')
            try:
                # 尝试 mock 降级逻辑
                _mock_ccc = MagicMock()
                _mock_ccc.classify_video = MagicMock(
                    return_value={"dominant": "pan_left", "confidence": 0.65}
                )
                sys.modules['core.camera_movement_classifier'] = _mock_ccc

                result = clf.classify_video(str(video_file))

                # 验证降级到光流规则
                assert result["source"] == "flow_rule_degraded"
                assert result["label"] == "pan_left"
                assert result["confidence"] == 0.65
            except ImportError:
                # 如果降级模块不存在，应返回 unknown
                result = clf.classify_video(str(video_file))
                assert result["label"] == "unknown"
                assert result["source"] == "unknown"
            finally:
                if _orig_ccc is not None:
                    sys.modules['core.camera_movement_classifier'] = _orig_ccc
                else:
                    sys.modules.pop('core.camera_movement_classifier', None)


# ============================================================================
# 缺口: Schema 自动识别边缘情况（meta.json 缺失/损坏/非list/边界长度）
# ============================================================================

class TestSchemaAutoDetectionEdgeCases:
    """测试 _load_meta_labels + schema 自动检测的未覆盖边缘情况。

    覆盖缺口（提交 6f134fa：len(labels)>=8 → fine 否则 coarse）：
    - meta.json 不存在时回退到 COARSE_LABELS
    - meta.json JSON 解码损坏时回退
    - labels 字段非 list 类型时回退
    - labels 长度边界：7 类 → coarse；8 类 → fine
    - 读取时 OSError（权限/磁盘错误）回退
    """

    def test_no_meta_json_falls_back_to_coarse_labels(self, tmp_path):
        """meta.json 不存在 → 使用默认 COARSE_LABELS，schema 自动为 coarse。"""
        from models.anime_camera_classifier import AnimeCameraClassifier, COARSE_LABELS

        model_dir = tmp_path / "no_meta_dir"
        model_dir.mkdir()
        # 不创建 meta.json

        clf = AnimeCameraClassifier(lora_dir=str(model_dir))

        assert clf.labels == COARSE_LABELS
        assert clf.schema == "coarse"

    def test_malformed_json_falls_back_to_coarse(self, tmp_path):
        """meta.json 语法损坏（JSONDecodeError）→ 回退 COARSE_LABELS。"""
        from models.anime_camera_classifier import AnimeCameraClassifier, COARSE_LABELS

        model_dir = tmp_path / "bad_json"
        model_dir.mkdir()
        # 写入损坏 JSON（缺少逗号）
        (model_dir / "meta.json").write_text(
            '{"labels": ["static" "pan_left" "orbit"]}',  # 无逗号
            encoding="utf-8",
        )

        clf = AnimeCameraClassifier(lora_dir=str(model_dir))

        assert clf.labels == COARSE_LABELS
        assert clf.schema == "coarse"

    def test_labels_not_a_list_falls_back(self, tmp_path):
        """meta.json 中 labels 字段不是 list → 回退 COARSE_LABELS。"""
        from models.anime_camera_classifier import AnimeCameraClassifier, COARSE_LABELS

        model_dir = tmp_path / "nonlist_labels"
        model_dir.mkdir()
        # labels 写成字符串、dict、数字三种非 list 形态
        for bad_value in ['"just_a_string"', '{"k": "v"}', "123", "null"]:
            (model_dir / "meta.json").write_text(
                f'{{"labels": {bad_value}}}', encoding="utf-8"
            )
            clf = AnimeCameraClassifier(lora_dir=str(model_dir))
            assert clf.labels == COARSE_LABELS, (
                f"labels={bad_value} 时应回退默认粗类，但实际 {clf.labels}"
            )
            assert clf.schema == "coarse"

    def test_seven_classes_still_coarse(self, tmp_path):
        """7 类（<8） → 阈值判断为 coarse schema。"""
        from models.anime_camera_classifier import AnimeCameraClassifier

        model_dir = tmp_path / "seven_classes"
        model_dir.mkdir()
        seven_labels = [f"cls{i}" for i in range(7)]
        (model_dir / "meta.json").write_text(
            json.dumps({"labels": seven_labels}), encoding="utf-8"
        )

        clf = AnimeCameraClassifier(lora_dir=str(model_dir))

        assert len(clf.labels) == 7
        assert clf.schema == "coarse"  # 7 < 8

    def test_eight_classes_triggers_fine(self, tmp_path):
        """8 类（>=8） → 越过阈值识别为 fine schema。"""
        from models.anime_camera_classifier import AnimeCameraClassifier

        model_dir = tmp_path / "eight_classes"
        model_dir.mkdir()
        eight_labels = [f"cls{i}" for i in range(8)]
        (model_dir / "meta.json").write_text(
            json.dumps({"labels": eight_labels}), encoding="utf-8"
        )

        clf = AnimeCameraClassifier(lora_dir=str(model_dir))

        assert len(clf.labels) == 8
        assert clf.schema == "fine"  # 8 >= 8

    def test_meta_labels_str_items_casted(self, tmp_path):
        """labels 中元素应为字符串类型（即使 JSON 里是数字也强制 str）。"""
        from models.anime_camera_classifier import AnimeCameraClassifier

        model_dir = tmp_path / "num_labels"
        model_dir.mkdir()
        # JSON 中 labels 写数字值：0, 1, 2, 3, 4, 5, 6, 7, 8, 9
        (model_dir / "meta.json").write_text(
            json.dumps({"labels": list(range(10))}), encoding="utf-8"
        )

        clf = AnimeCameraClassifier(lora_dir=str(model_dir))

        # 所有 label 都应被 str() 转换
        assert all(isinstance(lbl, str) for lbl in clf.labels)
        assert clf.labels == [str(i) for i in range(10)]
        assert clf.schema == "fine"

    def test_meta_json_read_oserror_falls_back(self, tmp_path):
        """读取 meta.json 抛 OSError（权限/磁盘坏） → 回退 COARSE_LABELS。"""
        from models.anime_camera_classifier import (
            AnimeCameraClassifier,
            COARSE_LABELS,
        )

        model_dir = tmp_path / "oserror_dir"
        model_dir.mkdir()
        meta_file = model_dir / "meta.json"
        meta_file.write_text(  # 先创建存在文件，方便 patch OSError
            json.dumps({"labels": ["a", "b", "c", "d", "e", "f", "g", "h"]}),
            encoding="utf-8",
        )

        # 通过 mock Path.read_text 注入 OSError
        real_read_text = Path.read_text
        call_count = {"n": 0}

        def fake_read_text(self, *a, **kw):
            if self.name == "meta.json" and self.parent == model_dir:
                call_count["n"] += 1
                raise OSError("磁盘读取失败: 扇区损坏")
            return real_read_text(self, *a, **kw)

        with patch.object(Path, "read_text", fake_read_text):
            clf = AnimeCameraClassifier(lora_dir=str(model_dir))

        assert call_count["n"] >= 1  # 确认触发了 mock
        assert clf.labels == COARSE_LABELS
        assert clf.schema == "coarse"