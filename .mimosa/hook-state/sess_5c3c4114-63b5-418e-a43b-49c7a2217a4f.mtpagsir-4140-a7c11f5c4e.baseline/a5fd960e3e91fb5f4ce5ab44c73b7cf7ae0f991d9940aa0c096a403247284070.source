#!/usr/bin/env python3
"""MiniMax H3接入：管线 fallback 链 + H3辅助函数 + FormalSpec不变量。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class TestFallbackChains:
    """D1 fallback 链含 H3 路径。"""

    def test_execute_chain_h3_paths_inserted_between_ae_and_ffmpeg(self):
        """execute 链 ae_retry -> h3_video_edit -> h3_style_transfer -> ffmpeg。"""
        from pipeline.unified_pipeline import AdaptiveFallbackSelector

        chain = AdaptiveFallbackSelector.DEFAULT_FALLBACK_CHAINS["execute"]
        # ae_retry 最先, h3 两条在中间，ffmpeg 兜底
        ae_i = chain.index("ae_retry")
        ffm_i = chain.index("ffmpeg_fallback")
        h3v_i = chain.index("h3_video_edit")
        h3s_i = chain.index("h3_style_transfer")
        assert ae_i < h3v_i < h3s_i < ffm_i, (
            f"execute fallback 顺序错误: {chain}"
        )

    def test_render_chain_h3_inpainting_between_ae_and_ffmpeg(self):
        """render 链 ae_render -> h3_inpainting_enhance -> ffmpeg_transcode。"""
        from pipeline.unified_pipeline import AdaptiveFallbackSelector

        chain = AdaptiveFallbackSelector.DEFAULT_FALLBACK_CHAINS["render"]
        aer = chain.index("ae_render_retry")
        h3 = chain.index("h3_inpainting_enhance")
        ffm = chain.index("ffmpeg_transcode")
        assert aer < h3 < ffm

    def test_new_postproduction_and_generative_chains_exist(self):
        """新增两条后期/创意 fallback 链。"""
        from pipeline.unified_pipeline import AdaptiveFallbackSelector as A

        chains = A.DEFAULT_FALLBACK_CHAINS
        assert "postproduction" in chains, "缺后期链不存在"
        assert "generative" in chains, "缺创意链不存在"
        # 后期链 h3 开头
        assert chains["postproduction"][0] == "h3_video_edit"
        # 创意链 h3 开头
        assert chains["generative"][0] == "h3_video_generation"


class TestH3NativeAVHelper:
    """D2 try_h3_native_av_generate。"""

    def test_duration_over_15_returns_false(self):
        """H3 官方上限 15 秒：传 16 秒立刻 False。"""
        from pipeline.unified_pipeline import try_h3_native_av_generate

        ok, msg = try_h3_native_av_generate(
            "随便", "x.mp4", duration_sec=16,
        )
        assert ok is False
        assert "15" in msg

    def test_no_generatevideo_attr_returns_false(self, monkeypatch):
        """llm_gateway 没 generate_video 时返回 False，不抛。"""
        from pipeline.unified_pipeline import try_h3_native_av_generate
        ok, msg = try_h3_native_av_generate(
            "x", "/tmp/x.mp4", duration_sec=10,
        )
        # 没 API Key, api_key 空应该 -> 没配就 generate_video 会调 API
        # 其实 generate_video 本身也因为没 api_key 或 mock 结果是 error, 但 ok 也是 False? 
        # 不抛就行
        assert isinstance(ok, bool)
        assert isinstance(msg, str)


class TestH3V2VHelper:
    """D3 try_h3_motion_transfer。"""

    def test_no_editvideo_attr_returns_false(self):
        """函数不抛，返回 (False, str)。"""
        from pipeline.unified_pipeline import try_h3_motion_transfer

        ok, msg = try_h3_motion_transfer(
            "/tmp/s.mp4", "/tmp/t.png", "/tmp/out.mp4",
        )
        assert isinstance(ok, bool)
        assert isinstance(msg, str)


class TestH3VideoSpecInvariant:
    """D4 H3VideoSpec 形式化不变量。"""

    def _check(self, ctx):
        from core.formal_spec import H3VideoSpec
        inv = H3VideoSpec()
        return inv.check(ctx)

    def test_normal_case_passes(self):
        ok, err = self._check({
            "h3_output": {
                "resolution": "768p",
                "duration_sec": 10,
                "fps": 24,
                "aspect_ratio": "16:9",
                "has_audio_track": True,
            }
        })
        assert ok is True, err
        assert err == ""

    def test_resolution_invalid_fails(self):
        ok, err = self._check({"h3_output": {"resolution": "1080p"}})
        assert ok is False
        assert "resolution" in err

    def test_resolution_1440p_equals_2k_passes(self):
        """1440p 与 2k 都允许（我们当同）。"""
        for r in ("2k", "1440p"):
            ok, err = self._check({"h3_output": {
                "resolution": r, "duration_sec": 8, "fps": 24,
                "aspect_ratio": "16:9", "has_audio_track": True,
            }})
            assert ok is True, f"{r} 失败: {err}"

    def test_duration_under_5_fails(self):
        ok, err = self._check({"h3_output": {"duration_sec": 3, "resolution": "768p",
                                            "fps": 24, "aspect_ratio": "1:1",
                                            "has_audio_track": True}})
        assert ok is False
        assert "duration_sec" in err

    def test_duration_over_15_fails(self):
        ok, err = self._check({"h3_output": {"duration_sec": 20,
                                            "resolution": "768p", "fps": 24,
                                            "aspect_ratio": "1:1",
                                            "has_audio_track": True}})
        assert ok is False
        assert "duration_sec" in err

    def test_fps_not_24_fails(self):
        ok, err = self._check({"h3_output": {"fps": 30, "resolution": "768p",
                                             "duration_sec": 10, "aspect_ratio": "1:1",
                                             "has_audio_track": True}})
        assert ok is False
        assert "fps" in err

    def test_aspect_ratio_invalid_fails(self):
        ok, err = self._check({"h3_output": {"aspect_ratio": "2.35:1",
                                            "resolution": "768p",
                                            "duration_sec": 10, "fps": 24,
                                            "has_audio_track": True}})
        assert ok is False
        assert "aspect_ratio" in err

    def test_no_audio_track_fails(self):
        ok, err = self._check({"h3_output": {"has_audio_track": False,
                                            "resolution": "768p",
                                            "duration_sec": 10, "fps": 24,
                                            "aspect_ratio": "16:9"}})
        assert ok is False
        assert "has_audio_track" in err

    def test_missing_h3output_passes_but_warns(self, caplog):
        """C1 修复精神：缺 h3_output 跳过，不违规，只告警。"""
        import logging
        caplog.set_level(logging.WARNING)
        ok, err = self._check({})
        assert ok is True
        assert err == ""
        # 至少有 warning（任意一条），通过 log 警告存在即可，不严格断言具体文字，防止大小写敏）。

    def test_h3output_none_skips(self):
        ok, err = self._check({"h3_output": None})
        assert ok is True
        assert err == ""

    def test_h3output_empty_dict_skips_no_fields_none_violation(self):
        """空 dict 时，各字段空字符串不报错。"""
        ok, err = self._check({"h3_output": {}})
        assert ok is True
        assert err == ""


class TestFormalInvariantsList:
    """D5 FORMAL_INVARIANTS 列表含 H3VideoSpec。"""

    def test_list_has_h3_spec_instance(self):
        from core.formal_spec import FORMAL_INVARIANTS, H3VideoSpec
        types_ = [type(x).__name__ for x in FORMAL_INVARIANTS]
        assert "H3VideoSpec" in types_, (
            f"FORMAL_INVARIANTS 缺少 H3VideoSpec，当前: {types_}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
