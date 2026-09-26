# -*- coding: utf-8 -*-
"""core/multimodal_fusion_hub.py 单元测试。

使用临时 data_dir 隔离持久化；encode_all 仅用纯文本模态（不依赖外部文件），
fused_decision 为纯 numpy 计算，全程离线。
"""
from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict

from core.multimodal_fusion_hub import (
    AudioFeatureExtractor,
    FusedDecision,
    MultimodalEmbedding,
    MultimodalFusionHub,
    VisualFeatureExtractor,
    get_fusion_hub,
)


class TestHubInstantiation:
    """中枢实例化。"""

    def test_instantiation_creates_data_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = str(Path(tmp) / "hub")
            MultimodalFusionHub(data_dir=data_dir)
            assert Path(data_dir).is_dir()

    def test_get_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            stats = hub.get_statistics()
            assert stats["embedding_dim"] == 128
            assert stats["attention_heads"] == 4


class TestEncode:
    """多模态编码（纯文本）。"""

    def test_encode_all_text_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            emb = asyncio.run(hub.encode_all(text_description="高燃混剪，节奏快，打击感"))
            assert isinstance(emb, MultimodalEmbedding)
            assert emb.text.available is True
            assert emb.text.style_category == "energetic"
            assert emb.fused_embedding.shape == (128,)
            assert set(emb.modality_weights) <= {"visual", "audio", "text"}

    def test_encode_all_empty_is_robust(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            emb = asyncio.run(hub.encode_all())
            assert emb.visual.available is False
            assert emb.audio.available is False
            assert emb.text.available is False


class TestDecision:
    """融合决策。"""

    def test_skip_stage_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            emb = asyncio.run(hub.encode_all(text_description="电影感，克制，高级"))
            dec = asyncio.run(hub.fused_decision(emb, "skip_stage"))
            assert isinstance(dec, FusedDecision)
            assert dec.decision_type == "skip_stage"
            assert isinstance(dec.decision, bool)
            assert 0.0 <= dec.confidence <= 1.0

    def test_select_effect_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            emb = asyncio.run(hub.encode_all(text_description="霓虹赛博朋克"))
            dec = asyncio.run(hub.fused_decision(emb, "select_effect"))
            assert dec.decision_type == "select_effect"
            assert isinstance(dec.decision, str)
            assert dec.alternatives  # 应存在备选效果

    def test_tune_params_decision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            emb = asyncio.run(hub.encode_all(text_description="高燃"))
            dec = asyncio.run(hub.fused_decision(emb, "tune_params"))
            assert isinstance(dec.decision, dict)

    def test_unknown_decision_type(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            emb = asyncio.run(hub.encode_all(text_description="测试"))
            dec = asyncio.run(hub.fused_decision(emb, "not_a_type"))
            assert dec.decision is None


class TestPersistence:
    """决策与缓存持久化。"""

    def test_record_and_get_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            hub.record_decision(FusedDecision(decision_type="skip_stage",
                                              decision=True, confidence=0.9))
            hub.record_decision(FusedDecision(decision_type="select_effect",
                                              decision="glow", confidence=0.8))
            decisions = hub.get_decisions()
            assert len(decisions) == 2
            assert decisions[0]["decision_type"] == "skip_stage"
            assert decisions[0]["decision"] is True
            assert decisions[1]["decision_type"] == "select_effect"

    def test_clear_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            hub.record_decision(FusedDecision(decision_type="skip_stage",
                                              decision=False, confidence=0.5))
            assert len(hub.get_decisions()) == 1
            hub.clear_decisions()
            assert hub.get_decisions() == []

    def test_save_and_load_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            hub._cache["key"] = {"value": 1}
            path = hub.save_cache()
            assert Path(path).is_file()
            hub2 = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            cache: dict[str, Any] = hub2.load_cache()
            assert cache["key"] == {"value": 1}

    def test_load_missing_cache_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            assert hub.load_cache() == {}


class TestSingleton:
    """全局单例入口。"""

    def test_get_fusion_hub_returns_same_instance(self) -> None:
        a = get_fusion_hub()
        b = get_fusion_hub()
        assert a is b
        assert isinstance(a, MultimodalFusionHub)


class TestHeuristicPathsHonestMarking:
    """FIX-04 规格钉（与 tests/test_fake_success_packs_fix0405.py 双保险）：

    文件大小启发式的 video/images/audio-file 路径必须 available=False（未解码内容
    不得声称可用，0924 审计 F4）；array 真实轻计算路径必须保持可用（误伤检测）。
    """

    def test_video_file_path_marked_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            v = Path(tmp) / "clip.mp4"
            v.write_bytes(b"\x00" * 2048)
            feats = asyncio.run(VisualFeatureExtractor()._extract_from_video(str(v)))
            assert feats.available is False
            assert feats.confidence == 0.0

    def test_images_path_marked_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            img = Path(tmp) / "f.png"
            img.write_bytes(b"\x00" * 1024)
            feats = asyncio.run(VisualFeatureExtractor()._extract_from_images([str(img)]))
            assert feats.available is False

    def test_audio_file_path_marked_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            a = Path(tmp) / "bgm.mp3"
            a.write_bytes(b"\x00" * 2048)
            feats = asyncio.run(AudioFeatureExtractor()._extract_from_file(str(a)))
            assert feats.available is False, "bpm=120 常量伪造分析不得参与融合决策"

    def test_encode_all_with_fake_files_degrades_to_text_only(self) -> None:
        """集成层：传启发式文件路径 + 文本 → 仅 text 模态存活，融合权重不含 visual/audio。"""
        with tempfile.TemporaryDirectory() as tmp:
            v = Path(tmp) / "clip.mp4"
            v.write_bytes(b"\x00" * 2048)
            hub = MultimodalFusionHub(data_dir=str(Path(tmp) / "hub"))
            emb = asyncio.run(hub.encode_all(
                video_path=str(v), text_description="节快 热血",
            ))
            assert emb.visual.available is False
            assert emb.text.available is True
            assert "visual" not in emb.modality_weights