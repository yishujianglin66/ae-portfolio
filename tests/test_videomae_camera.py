"""tests/test_videomae_camera.py — VideoMAE 运镜适配器测试

覆盖:
  1. MovieShots→项目标签映射
  2. 模型目录缺失 → available()=False, classify()=None (不抛异常)
  3. mock 模型推理 → 正确标签映射 + 低置信度回退 None
  4. _read_frames_cv2 不可读视频 → None
"""
from __future__ import annotations

import pytest


class TestLabelMapping:
    def test_movieshots_to_project(self):
        from models.camera.videomae_camera import MOVIESHOTS_TO_PROJECT
        assert MOVIESHOTS_TO_PROJECT == {
            "Static": "static",
            "Motion": "pan_left",
            "Pull": "zoom_out",
            "Push": "zoom_in",
            "Multi_movement": "complex",
        }

    def test_mapping_values_in_camera_labels(self):
        from core.camera_movement_classifier import CAMERA_LABELS
        from models.camera.videomae_camera import MOVIESHOTS_TO_PROJECT
        for label in MOVIESHOTS_TO_PROJECT.values():
            assert label in CAMERA_LABELS, f"{label} 不在 CAMERA_LABELS"


class TestClassifierGracefulDegradation:
    def test_missing_model_dir(self):
        from models.camera.videomae_camera import VideoMAECameraClassifier
        clf = VideoMAECameraClassifier(model_dir=r"Z:\no\such\dir")
        assert clf.available() is False
        assert clf.classify("whatever.mp4") is None

    def test_unreadable_video(self):
        from models.camera.videomae_camera import (
            VideoMAECameraClassifier,
            _read_frames_cv2,
        )
        assert _read_frames_cv2(r"Z:\no\such\video.mp4") is None
        clf = VideoMAECameraClassifier(model_dir=r"Z:\no\such\dir")
        assert clf.classify(r"Z:\no\such\video.mp4") is None

    def test_stats(self):
        from models.camera.videomae_camera import VideoMAECameraClassifier
        clf = VideoMAECameraClassifier(model_dir=r"Z:\no\such\dir")
        st = clf.stats()
        assert st["loaded"] is False
        assert "model_dir" in st


class TestMockedInference:
    """用假模型替换 transformers 加载, 验证推理路径与映射。"""

    def test_classify_maps_label_and_conf(self, monkeypatch):
        from models.camera.videomae_camera import VideoMAECameraClassifier

        class FakeLogits:
            def __init__(self, probs):
                import torch
                self._p = torch.tensor([probs])

            @property
            def logits(self):
                return self._p

        class FakeModel:
            def __init__(self):
                self.config = type("Cfg", (), {
                    "id2label": {0: "Static", 1: "Motion", 2: "Pull",
                                 3: "Push", 4: "Multi_movement"},
                })()
                self._param = type("P", (), {"device": "cpu"})()

            def eval(self): return self

            def to(self, d): return self

            def parameters(self):
                return iter([self._param])

            def __call__(self, **kw):
                return FakeLogits([0.1, 4.0, 0.02, 0.05, 0.03])

        class FakeProc:
            def __call__(self, frames, return_tensors):
                import torch
                return {"pixel_values": torch.zeros(1, 16, 3, 224, 224)}

        clf = VideoMAECameraClassifier(
            model_dir=r"D:\AE-Data\Models\VideoMAE-MovieShots\movement",
            conf_threshold=0.45,
            device="cpu",
        )
        clf._proc = FakeProc()
        clf._model = FakeModel()
        clf._labels = list(clf._model.config.id2label.values())

        # 用假帧绕过真实视频读取
        import numpy as np
        monkeypatch.setattr(
            "models.camera.videomae_camera._read_frames_cv2",
            lambda *a, **k: np.zeros((16, 3, 224, 224), dtype=np.float32),
        )
        res = clf.classify("fake.mp4")
        assert res is not None
        assert res["label"] == "pan_left"          # Motion → pan_left
        assert res["raw_label"] == "Motion"
        assert res["confidence"] > 0.85

    def test_low_confidence_returns_none(self, monkeypatch):
        from models.camera.videomae_camera import VideoMAECameraClassifier

        class FakeLogits:
            def __init__(self, probs):
                import torch
                self._p = torch.tensor([probs])

            @property
            def logits(self):
                return self._p

        class FakeModel:
            def __init__(self):
                self.config = type("Cfg", (), {
                    "id2label": {0: "Static", 1: "Motion", 2: "Pull",
                                 3: "Push", 4: "Multi_movement"},
                })()
                self._param = type("P", (), {"device": "cpu"})()

            def eval(self): return self

            def to(self, d): return self

            def parameters(self):
                return iter([self._param])

            def __call__(self, **kw):
                return FakeLogits([0.3, 0.25, 0.2, 0.15, 0.1])

        class FakeProc:
            def __call__(self, frames, return_tensors):
                import torch
                return {"pixel_values": torch.zeros(1, 16, 3, 224, 224)}

        clf = VideoMAECameraClassifier(
            model_dir=r"D:\AE-Data\Models\VideoMAE-MovieShots\movement",
            conf_threshold=0.45,
            device="cpu",
        )
        clf._proc = FakeProc()
        clf._model = FakeModel()
        clf._labels = list(clf._model.config.id2label.values())

        import numpy as np
        monkeypatch.setattr(
            "models.camera.videomae_camera._read_frames_cv2",
            lambda *a, **k: np.zeros((16, 3, 224, 224), dtype=np.float32),
        )
        res = clf.classify("fake.mp4")
        # 最高置信度 0.3 < 0.45 → 回退 None (调用方走光流规则)
        assert res is None


class TestKandinskyMultilabel:
    """kandinsky-large 多标签头 (18 类) 推理路径。"""

    def _make_clf(self, monkeypatch, logits):
        from models.camera.videomae_camera import (
            KANDINSKY_TO_PROJECT,
            VideoMAECameraClassifier,
        )

        class FakeModel:
            def __init__(self):
                self.config = type("Cfg", (), {
                    "id2label": {i: l for i, l in enumerate(
                        ["pan_left", "tilt_up", "undefined"])},
                })()
                self._param = type("P", (), {"device": "cpu"})()

            def eval(self): return self

            def to(self, d): return self

            def parameters(self):
                return iter([self._param])

            def __call__(self, **kw):
                import torch
                return type("O", (), {"logits": torch.tensor([logits])})()

        class FakeProc:
            def __call__(self, frames, return_tensors):
                import torch
                return {"pixel_values": torch.zeros(1, 16, 3, 224, 224)}

        clf = VideoMAECameraClassifier(
            model_dir=r"D:\AE-Data\Models\VideoMAE-MovieShots\kandinsky-large",
            multilabel=True,
            label_map=KANDINSKY_TO_PROJECT,
            sigmoid_threshold=0.5,
            device="cpu",
        )
        clf._proc = FakeProc()
        clf._model = FakeModel()
        clf._labels = list(clf._model.config.id2label.values())
        import numpy as np
        monkeypatch.setattr(
            "models.camera.videomae_camera._read_frames_cv2",
            lambda *a, **k: np.zeros((16, 3, 224, 224), dtype=np.float32),
        )
        return clf

    def test_multilabel_top_class_mapped(self, monkeypatch):
        clf = self._make_clf(monkeypatch, [3.0, 1.2, -2.0])
        res = clf.classify("fake.mp4")
        assert res is not None
        assert res["label"] == "pan_left"          # sigmoid(3.0)≈0.95 > 0.5
        assert res["raw_label"] == "pan_left"
        assert res["confidence"] > 0.9
        assert len(res["all_labels"]) >= 1

    def test_multilabel_undefined_returns_none(self, monkeypatch):
        # 只有 undefined 过阈值 → 放弃注入 (回退规则分类器)
        clf = self._make_clf(monkeypatch, [-2.0, -3.0, 3.0])
        res = clf.classify("fake.mp4")
        assert res is None

    def test_multilabel_none_above_threshold_returns_none(self, monkeypatch):
        clf = self._make_clf(monkeypatch, [-1.0, -2.0, -3.0])
        res = clf.classify("fake.mp4")
        assert res is None

    def test_kandinsky_map_covers_all_classes(self):
        from core.camera_movement_classifier import CAMERA_LABELS
        from models.camera.videomae_camera import (
            KANDINSKY_TO_PROJECT,
            get_kandinsky_classifier,
        )
        # 18 运镜类 + 3 镜头类全映射, 且映射值均在项目词汇表内
        assert len(KANDINSKY_TO_PROJECT) >= 21
        for v in KANDINSKY_TO_PROJECT.values():
            assert v in CAMERA_LABELS, f"{v} 不在 CAMERA_LABELS"
        clf = get_kandinsky_classifier()
        assert clf.multilabel is True
        assert clf.sigmoid_threshold == 0.5


class TestCascade:
    """三级级联: kandinsky → base → None(规则兜底)。"""

    def test_cascade_prefers_kandinsky(self, monkeypatch):
        from models.camera.videomae_camera import classify_cascade
        monkeypatch.setattr(
            "models.camera.videomae_camera.get_kandinsky_classifier",
            lambda: type("K", (), {
                "available": lambda self: True,
                "classify": lambda self, p: {"label": "orbit",
                                             "confidence": 0.99},
            })(),
        )
        # base 不应被调用 (kandinsky 命中)
        calls = []
        monkeypatch.setattr(
            "models.camera.videomae_camera.get_videomae_classifier",
            lambda: type("B", (), {
                "available": lambda self: True,
                "classify": lambda self, p: calls.append(p) or {"label": "x"},
            })(),
        )
        r = classify_cascade("v.mp4")
        assert r["label"] == "orbit"
        assert r["stage"] == "kandinsky"
        assert calls == []

    def test_cascade_falls_back_to_base(self, monkeypatch):
        from models.camera.videomae_camera import classify_cascade
        monkeypatch.setattr(
            "models.camera.videomae_camera.get_kandinsky_classifier",
            lambda: type("K", (), {
                "available": lambda self: True,
                "classify": lambda self, p: None,   # 拒绝
            })(),
        )
        monkeypatch.setattr(
            "models.camera.videomae_camera.get_videomae_classifier",
            lambda: type("B", (), {
                "available": lambda self: True,
                "classify": lambda self, p: {"label": "pan_left",
                                             "confidence": 0.7},
            })(),
        )
        r = classify_cascade("v.mp4")
        assert r["label"] == "pan_left"
        assert r["stage"] == "base"

    def test_cascade_both_reject_returns_none(self, monkeypatch):
        from models.camera.videomae_camera import classify_cascade
        monkeypatch.setattr(
            "models.camera.videomae_camera.get_kandinsky_classifier",
            lambda: type("K", (), {
                "available": lambda self: True,
                "classify": lambda self, p: None,
            })(),
        )
        monkeypatch.setattr(
            "models.camera.videomae_camera.get_videomae_classifier",
            lambda: type("B", (), {
                "available": lambda self: True,
                "classify": lambda self, p: None,
            })(),
        )
        assert classify_cascade("v.mp4") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
