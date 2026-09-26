# -*- coding: utf-8 -*-
"""
FIX-04 / FIX-05 行为锁死测试（伪造成功切断包）
=================================================
FIX-04: core/multimodal_fusion_hub.py — 文件大小启发式路径不得再伪装 available=True
       （0924 审计 F4：随机特征以 confidence 0.7 参与真实融合决策）
FIX-05: MockAIGCAdapter 默认禁用 + ai_director 素材入池白名单（审计 F6：蓝色占位片入成片）
契约出处: docs/execution_result_contract.md §1/§2.4/§4
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import pytest

import ai.aigc_generator as ag
from ai.ai_director import _is_trusted_material_result
from core.multimodal_fusion_hub import (
    AudioFeatureExtractor,
    TextFeatureExtractor,
    VisualFeatureExtractor,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
HUB_SRC = REPO_ROOT / "core" / "multimodal_fusion_hub.py"


class TestVisualFakePathUnavailable:
    def test_video_file_heuristic_marked_unavailable(self, tmp_path):
        v = tmp_path / "x.mp4"
        v.write_bytes(b"\x00" * 4096)
        ex = VisualFeatureExtractor()
        feats = asyncio.run(ex._extract_from_video(str(v)))
        assert feats.available is False, "不解码视频的文件大小启发式不得声称可用（F4）"
        assert feats.confidence == 0.0

    def test_images_heuristic_marked_unavailable(self, tmp_path):
        img = tmp_path / "y.png"
        img.write_bytes(b"\x00" * 2048)
        ex = VisualFeatureExtractor()
        feats = asyncio.run(ex._extract_from_images([str(img)]))
        assert feats.available is False
        assert feats.confidence == 0.0

    def test_real_array_path_still_flows(self):
        # 真实像素计算路径（_extract_from_array）必须仍放行——修复不能误伤真能力
        frame = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)
        ex = VisualFeatureExtractor()
        feats = asyncio.run(ex.extract(frame_data=frame))
        assert feats.available is True
        assert feats.confidence == 0.7


class TestAudioFakePathUnavailable:
    def test_audio_file_heuristic_marked_unavailable(self, tmp_path):
        a = tmp_path / "z.mp3"
        a.write_bytes(b"\x00" * 4096)
        ex = AudioFeatureExtractor()
        feats = asyncio.run(ex._extract_from_file(str(a)))
        assert feats.available is False, "bpm=120 常量伪造分析不得可用（F4）"
        assert feats.confidence == 0.0

    def test_text_modality_still_real(self):
        # 文本关键词/哈希路径是真实计算，不受本包影响
        feats = asyncio.run(TextFeatureExtractor().extract(text="高燃 热血 节奏"))
        assert feats.available is True


class TestHubSingletonDedup:
    def test_get_fusion_hub_defined_once(self):
        # 旧文件尾部 3 份逐字重复 def（后定义静默覆盖）——去重回归守卫
        src = HUB_SRC.read_text(encoding="utf-8")
        assert src.count("def get_fusion_hub(") == 1


class TestMockAIGCOptInGating:
    def test_unavailable_by_default(self, monkeypatch):
        monkeypatch.delenv("AEKV_AIGC_ALLOW_MOCK", raising=False)
        assert ag.MockAIGCAdapter().is_available() is False, "Mock 不再恒可用（F6）"

    def test_disabled_generate_returns_failure(self, monkeypatch, tmp_path):
        monkeypatch.delenv("AEKV_AIGC_ALLOW_MOCK", raising=False)
        r = ag.MockAIGCAdapter().generate_video("p", str(tmp_path / "o.mp4"))
        assert r["success"] is False
        assert r["execution_path"] == "simulated"
        assert r["source"] == "Mock"
        assert not (tmp_path / "o.mp4").exists()  # 禁用时连文件都不该造

    def test_available_only_with_env_flag(self, monkeypatch):
        monkeypatch.setenv("AEKV_AIGC_ALLOW_MOCK", "1")
        assert ag.MockAIGCAdapter().is_available() is True


class TestMaterialWhitelistLogic:
    """_is_trusted_material_result 值断言（含兼容性边界，文档于函数 docstring）"""

    def test_rejects_mock_source_even_with_success(self):
        assert _is_trusted_material_result(
            {"success": True, "path": "x.mp4", "source": "Mock"}
        ) is False

    def test_rejects_simulated_execution_path(self):
        assert _is_trusted_material_result(
            {"success": True, "path": "x.mp4", "execution_path": "simulated"}
        ) is False

    def test_rejects_missing_path_or_failure(self):
        assert _is_trusted_material_result({"success": True}) is False
        assert _is_trusted_material_result(
            {"success": False, "path": "x.mp4"}
        ) is False

    def test_accepts_real_and_legacy_unmarked(self):
        assert _is_trusted_material_result(
            {"success": True, "path": "x.mp4", "execution_path": "real"}
        ) is True
        # 历史适配器未带标记暂按 real 兼容（FIX-09 扫描器负责收敛）
        assert _is_trusted_material_result(
            {"success": True, "path": "x.mp4", "source": "Kling"}
        ) is True
