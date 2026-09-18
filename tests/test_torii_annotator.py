"""tests/test_torii_annotator.py — ToriiGate-2B 氛围标注器测试 (W6)

覆盖: JSON 解析容错 / 氛围归一化 / energy 稳健解析 / 优雅降级 / mock 推理。
"""
from __future__ import annotations

import pytest


class TestParsing:
    def test_parse_plain_json(self):
        from models.atmosphere.torii_annotator import _parse_json_response
        d = _parse_json_response(
            '{"atmosphere": "燃向", "energy": 9, "confidence": 0.8}')
        assert d["atmosphere"] == "燃向"
        assert d["energy"] == 9

    def test_parse_markdown_fenced(self):
        from models.atmosphere.torii_annotator import _parse_json_response
        d = _parse_json_response(
            '好的,分析如下:\n```json\n{"atmosphere": "抒情", "energy": 3}\n```\n希望有帮助')
        assert d["atmosphere"] == "抒情"

    def test_parse_garbage_returns_none(self):
        from models.atmosphere.torii_annotator import _parse_json_response
        assert _parse_json_response("这不是JSON") is None
        assert _parse_json_response("") is None


class TestNormalization:
    def test_normalize_known_words(self):
        from models.atmosphere.torii_annotator import _normalize_atmosphere
        assert _normalize_atmosphere("热血战斗") == "燃向"
        assert _normalize_atmosphere("高燃") == "燃向"
        assert _normalize_atmosphere("温馨治愈") == "治愈"
        assert _normalize_atmosphere("打斗") == "战斗"

    def test_normalize_english_words(self):
        from models.atmosphere.torii_annotator import _normalize_atmosphere
        assert _normalize_atmosphere("tense and dramatic") == "悬疑"
        assert _normalize_atmosphere("intense action") == "燃向"
        assert _normalize_atmosphere("warm healing") == "治愈"

    def test_normalize_unknown_passthrough(self):
        from models.atmosphere.torii_annotator import _normalize_atmosphere
        assert _normalize_atmosphere("诡异氛围") == "诡异氛围"[:12]
        assert _normalize_atmosphere("") == ""


class TestEnergyParsing:
    def test_int(self):
        from models.atmosphere.torii_annotator import _parse_energy
        assert _parse_energy(9) == 9
        assert _parse_energy(0) == 1
        assert _parse_energy(99) == 10

    def test_digit_in_sentence(self):
        from models.atmosphere.torii_annotator import _parse_energy
        assert _parse_energy("能量大约 7 分左右") == 7

    def test_word_mapping(self):
        from models.atmosphere.torii_annotator import _parse_energy
        assert _parse_energy("The energy is high, with a sense of action") == 8
        assert _parse_energy("整体较为平静舒缓") == 2
        assert _parse_energy("中等强度") == 5

    def test_fallback_default(self):
        from models.atmosphere.torii_annotator import _parse_energy
        assert _parse_energy(None) == 5
        assert _parse_energy("莫名其妙") == 5


class TestDegradation:
    def test_missing_model_dir(self):
        from models.atmosphere.torii_annotator import ToriiAtmosphereAnnotator
        ann = ToriiAtmosphereAnnotator(model_dir=r"Z:\no\such\dir")
        assert ann.available() is False
        assert ann.annotate("whatever.mp4") is None
        assert "model_dir" in ann.stats()

    def test_unreadable_video(self):
        from models.atmosphere.torii_annotator import (
            ToriiAtmosphereAnnotator,
            _sample_frames,
        )
        assert _sample_frames(r"Z:\no\such\video.mp4") is None
        ann = ToriiAtmosphereAnnotator(model_dir=r"Z:\no\such\dir")
        assert ann.annotate(r"Z:\no\such\video.mp4") is None


class TestMockedInference:
    def test_annotate_maps_result(self, monkeypatch):
        from models.atmosphere.torii_annotator import (
            AtmosphereResult,
            ToriiAtmosphereAnnotator,
        )

        class FakeOut:
            def __getitem__(self, key):
                import torch
                return torch.zeros(1, 0, dtype=torch.long)

        class FakeModel:
            def __init__(self):
                self._param = type("P", (), {"device": "cpu"})()

            def eval(self): return self

            def parameters(self):
                return iter([self._param])

            def generate(self, **kw):
                return FakeOut()

        class FakeProc:
            def __call__(self, *a, **k):
                import torch
                return {"input_ids": torch.zeros(1, 8, dtype=torch.long),
                        "pixel_values": torch.zeros(1, 3, 448, 448)}

            def apply_chat_template(self, messages, **kw):
                assert messages[0]["role"] == "user"
                return "chat"

            def batch_decode(self, ids, **kw):
                import json
                text = json.dumps(
                    {"atmosphere": "燃向", "emotion": "热血",
                     "energy": 9, "scene_type": "战斗",
                     "shot_scale": "中景", "confidence": 0.85},
                    ensure_ascii=False)
                return [text]

        ann = ToriiAtmosphereAnnotator(
            model_dir=r"D:\AE-Data\Models\ToriiGate\ToriiGate-v0.4-2B",
            device="cpu")
        ann._processor = FakeProc()
        ann._model = FakeModel()

        import numpy as np
        from PIL import Image
        monkeypatch.setattr(
            "models.atmosphere.torii_annotator._sample_frames",
            lambda *a, **k: [Image.fromarray(
                np.zeros((448, 448, 3), dtype=np.uint8))] * 2,
        )
        r = ann.annotate("fake.mp4")
        assert isinstance(r, AtmosphereResult)
        assert r.atmosphere == "燃向"
        assert r.energy == 9
        assert r.confidence == 0.85
        assert r.scene_type == "战斗"

    def test_annotate_low_confidence_none(self, monkeypatch):
        from models.atmosphere.torii_annotator import ToriiAtmosphereAnnotator

        class FakeOut:
            def __getitem__(self, key):
                import torch
                return torch.zeros(1, 0, dtype=torch.long)

        class FakeModel:
            def __init__(self):
                self._param = type("P", (), {"device": "cpu"})()

            def eval(self): return self

            def parameters(self):
                return iter([self._param])

            def generate(self, **kw):
                return FakeOut()

        class FakeProc:
            def __call__(self, *a, **k):
                import torch
                return {"input_ids": torch.zeros(1, 8, dtype=torch.long)}

            def apply_chat_template(self, messages, **kw):
                return "chat"

            def batch_decode(self, ids, **kw):
                import json
                return [json.dumps({"atmosphere": "日常", "confidence": 0.2})]

        ann = ToriiAtmosphereAnnotator(
            model_dir=r"D:\AE-Data\Models\ToriiGate\ToriiGate-v0.4-2B",
            device="cpu")
        ann._processor = FakeProc()
        ann._model = FakeModel()

        import numpy as np
        from PIL import Image
        monkeypatch.setattr(
            "models.atmosphere.torii_annotator._sample_frames",
            lambda *a, **k: [Image.fromarray(
                np.zeros((448, 448, 3), dtype=np.uint8))],
        )
        assert ann.annotate("fake.mp4") is None


class TestQualityGate:
    """氛围质量门: 归一化后仍非词表值 (散文未命中) → 拒绝。"""

    def _make(self, monkeypatch, atmosphere):
        from models.atmosphere.torii_annotator import ToriiAtmosphereAnnotator

        class FakeOut:
            def __getitem__(self, key):
                import torch
                return torch.zeros(1, 0, dtype=torch.long)

        class FakeModel:
            def __init__(self):
                self._param = type("P", (), {"device": "cpu"})()

            def eval(self): return self

            def parameters(self):
                return iter([self._param])

            def generate(self, **kw):
                return FakeOut()

        class FakeProc:
            def __call__(self, *a, **k):
                import torch
                return {"input_ids": torch.zeros(1, 8, dtype=torch.long)}

            def apply_chat_template(self, messages, **kw):
                return "chat"

            def batch_decode(self, ids, **kw):
                import json
                return [json.dumps({"atmosphere": atmosphere,
                                    "confidence": 0.7})]

        ann = ToriiAtmosphereAnnotator(
            model_dir=r"D:\AE-Data\Models\ToriiGate\ToriiGate-v0.4-2B",
            device="cpu")
        ann._processor = FakeProc()
        ann._model = FakeModel()
        import numpy as np
        from PIL import Image
        monkeypatch.setattr(
            "models.atmosphere.torii_annotator._sample_frames",
            lambda *a, **k: [Image.fromarray(
                np.zeros((448, 448, 3), dtype=np.uint8))],
        )
        return ann

    def test_prose_with_keyword_passes(self, monkeypatch):
        ann = self._make(monkeypatch, "The atmosphere is quite mysterious")
        r = ann.annotate("fake.mp4")
        assert r is not None and r.atmosphere == "悬疑"

    def test_prose_no_keyword_rejected(self, monkeypatch):
        ann = self._make(monkeypatch, "There is no recognizable keyword here")
        assert ann.annotate("fake.mp4") is None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])