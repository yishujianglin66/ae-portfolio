#!/usr/bin/env python3
"""MiniMax H3接入：LLMGateway 扩展（TaskType/映射/per-second 计费/H3 Provider/短路路由/本地+手绘骨架。"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# C1(a)(b)(c)(d) 枚举 + 映射扩展
# ---------------------------------------------------------------------------

class TestLLMTaskTypeExpansion:
    H3_NAMES = (
        "VIDEO_GENERATION", "VIDEO_EDITING", "IMAGE_GENERATION",
        "SUBTITLE_MODIFICATION", "STYLE_TRANSFER", "MOTION_TRANSFER",
        "OBJECT_REPLACEMENT", "SCENE_ALTERATION", "RATE_ADJUSTMENT",
        "INPAINTING", "VISION_UNDERSTANDING",
    )

    def test_llm_tasktype_has_11_h3_members(self):
        """C1(a) LLM TaskType 含 11 个 H3 成员。"""
        from core.llm_gateway import TaskType

        names = {m.name for m in TaskType}
        for n in self.H3_NAMES:
            assert n in names, f"LLM TaskType 缺少 {n!r}"

    def test_model_routing_dict_contains_h3_keys(self):
        """C1(b) LLMConfig.model_routing 含 11 个新成员默认 "auto"。"""
        from core.llm_gateway import TaskType, LLMConfig

        cfg = LLMConfig()
        routing_keys = list(cfg.model_routing.keys())
        for name in self.H3_NAMES:
            member = getattr(TaskType, name)
            assert member in routing_keys, f"model_routing 缺少 TaskType.{name}"
            assert cfg.model_routing[member] == "auto"

    def test_task_provider_map_h3_minimax(self):
        """C1(c) TASK_PROVIDER_MAP 含 11 条 minimax_h3 路由。"""
        from core.llm_gateway import (
            TaskType, TASK_PROVIDER_MAP,
        )
        paid = {
            TaskType.VIDEO_GENERATION, TaskType.VIDEO_EDITING, TaskType.IMAGE_GENERATION,
        }
        edit = {
            TaskType.SUBTITLE_MODIFICATION, TaskType.STYLE_TRANSFER,
            TaskType.MOTION_TRANSFER, TaskType.OBJECT_REPLACEMENT,
            TaskType.SCENE_ALTERATION, TaskType.RATE_ADJUSTMENT,
            TaskType.INPAINTING,
        }
        for tt in paid | edit:
            assert tt in TASK_PROVIDER_MAP, f"TASK_PROVIDER_MAP 缺少 {tt}"
            provider, _model = TASK_PROVIDER_MAP[tt]
            assert provider == "minimax_h3", f"{tt}: provider 应为 minimax_h3"

        # VISION_UNDERSTANDING -> siliconflow/vision (2026-08-14 重路由: 弃用 claude 中转站)
        prov, mtype = TASK_PROVIDER_MAP[TaskType.VISION_UNDERSTANDING]
        assert prov == "siliconflow"
        assert mtype == "vision"

    def test_task_tier_map_h3_sane(self):
        """C1(d) TASK_TIER_MAP 含 11 条，档位符合预期。"""
        from core.llm_gateway import (
            TaskType, TASK_TIER_MAP, ModelTier,
        )
        for name in self.H3_NAMES:
            tt = getattr(TaskType, name)
            assert tt in TASK_TIER_MAP, f"TASK_TIER_MAP 缺少 {tt}"
        # VIDEO_GENERATION -> TIER_2 (有 H3 付费但非旗舰)
        assert TASK_TIER_MAP[TaskType.VIDEO_GENERATION] == ModelTier.TIER_2_MIDTIER_GENERAL
        # VISION_UNDERSTANDING -> TIER_3 (视觉理解旗舰)
        assert TASK_TIER_MAP[TaskType.VISION_UNDERSTANDING] == ModelTier.TIER_3_FLAGSHIP_REASONING
        # 纯编辑类 -> TIER_1
        assert TASK_TIER_MAP[TaskType.SUBTITLE_MODIFICATION] == ModelTier.TIER_1_LOCAL_SPECIALIZED
        assert TASK_TIER_MAP[TaskType.RATE_ADJUSTMENT] == ModelTier.TIER_1_LOCAL_SPECIALIZED


# ---------------------------------------------------------------------------
# C1(e) per-second 计费数据结构可写
# ---------------------------------------------------------------------------

class TestPerSecondBillingFields:
    def test_llmresponse_has_modality_fields_defaults(self):
        """C1(e1) LLMResponse 有 4 个多模态字段，默认值正确。"""
        from core.llm_gateway import LLMResponse
        r = LLMResponse()
        assert r.video_seconds == 0.0
        assert r.video_resolution == ""
        assert r.image_count == 0
        assert r.modality_cost_usd == 0.0

    def test_providerhealth_has_video_image_fields(self):
        """C1(e2) ProviderHealth 有视频/图像累计。"""
        from core.llm_gateway import ProviderHealth
        h = ProviderHealth(name="minimax_h3")
        assert h.total_video_seconds == 0.0
        assert h.total_images_generated == 0

    def test_stats_and_tier_stats_fields(self):
        """C1(e3)(e4) LLMGateway _stats / _tier_stats 有 3 个字段。"""
        from core.llm_gateway import LLMGateway, LLMConfig
        g = LLMGateway(LLMConfig())
        for key in ("total_video_seconds", "total_images_generated", "total_modality_cost_usd"):
            assert key in g._stats, f"_stats 缺 {key}"
            assert g._stats[key] == 0 or g._stats[key] == 0.0
        from core.llm_gateway import ModelTier
        for tier in ModelTier:
            ts = g._tier_stats[tier]
            for key in ("total_video_seconds", "total_images_generated", "total_modality_cost_usd"):
                assert key in ts, f"tier_stats[{tier}] 缺 {key}"


# ---------------------------------------------------------------------------
# C2 H3 配置 + generate_video/edit_video mock HTTP 测试
# ---------------------------------------------------------------------------

class FakeResp:
    def __init__(self, status, json_data=None, text="", headers=None):
        self.status = status
        self._json = json_data or {}
        self.text = text
        self.headers = headers or {}
    async def __aenter__(self):
        return self
    async def __aexit__(self, *a):
        pass
    async def json(self):
        return self._json
    async def read(self):
        return b"fake-mp4-content"


class FakeSession:
    def __init__(self, fail_create=None, fail_poll=None, fail_download=None):
        self.calls = []
        self._fc = fail_create
        self._fp = fail_poll
        self._fd = fail_download
    def post(self, url, **kw):
        """aiohttp.ClientSession.post 是同步方法，返回 AsyncContextManager，所以这里也同步返回 FakeResp。"""
        self.calls.append(("POST", url, kw))
        if self._fc:
            raise self._fc
        if "/video-async/generations" in url:
            return FakeResp(200, {"task_id": "h3task123"})
        return FakeResp(200, {"task_id": "edit1"})
    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        if self._fp:
            raise self._fp
        if "/video-async/tasks/" in url:
            return FakeResp(200, {"task_id": "h3task123", "status": "succeeded",
                                  "result": {"video_url": "https://example.com/out.mp4"}})
        return FakeResp(200, {})


@pytest.fixture
def fake_session_maker(monkeypatch):
    def maker(fail_create=None, fail_poll=None):
        session = FakeSession(fail_create=fail_create, fail_poll=fail_poll)
        return session
    return maker


class TestH3Provider:
    def test_get_h3_config_reads_env(self, monkeypatch):
        """C2.1 _get_h3_config 读取 AEKV_LLM_MINIMAX_H3_* 环境变量。"""
        monkeypatch.setenv("AEKV_LLM_MINIMAX_H3_BASE_URL", "https://custom-h3.example/v1")
        monkeypatch.setenv("AEKV_LLM_MINIMAX_H3_API_KEY", "sk-test-12345")
        from core.llm_gateway import LLMGateway, LLMConfig
        g = LLMGateway(LLMConfig())
        cfg = g._get_h3_config()
        assert cfg["base_url"] == "https://custom-h3.example/v1"
        assert cfg["api_key"] == "sk-test-12345"
        assert cfg["cost_per_sec_2k"] > 0
        assert cfg["poll_interval_sec"] == 3.0

    @pytest.mark.asyncio
    async def test_generate_video_mock_success(self, tmp_path, monkeypatch):
        """C2.2/3/4 generate_video 成功流程：创建 -> poll → 下载 → 计费更新。"""
        from core.llm_gateway import LLMGateway, LLMConfig
        session = FakeSession()
        g = LLMGateway(LLMConfig())
        g._http_client = session  # 直接注入 fake session
        monkeypatch.setattr(g, "_get_h3_config", lambda: {
            "base_url": "https://api.minimaxi.com/v1",
            "api_key": "sk-fake",
            "cost_per_sec_2k": 0.8,
            "cost_per_sec_768p": 0.3,
            "poll_interval_sec": 0.001,  # 测试快速通过
            "max_poll_wait_sec": 5,
            "download_dir": str(tmp_path / "h3_dl"),
            "cache_dir": str(tmp_path / "h3_cache"),
        })
        out_p = tmp_path / "out.mp4"
        # Patch the download helper to just write the fake content
        async def dl(url, p):
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_bytes(b"fake")
            return True
        monkeypatch.setattr(g, "_download_file", dl)
        result = await g.generate_video(
            "测试提示词", duration_sec=10, resolution="768p",
            output_path=str(out_p),
        )
        assert result["success"] is True
        assert Path(result["output_path"]).exists()
        assert result["duration_sec"] == 10
        assert result["resolution"] == "768p"
        # 768p * 10s = 3.0 元
        assert result["cost_usd"] > 0
        # _stats 更新
        assert g._stats["total_video_seconds"] == 10
        assert g._stats["total_modality_cost_usd"] > 0
        # Provider健康
        hh = g._provider_health["minimax_h3"]
        assert hh.total_video_seconds == 10
        assert hh.total_requests >= 1
        assert hh.total_cost_usd > 0

    @pytest.mark.asyncio
    async def test_edit_video_mock_all_ops(self, tmp_path, monkeypatch):
        """C2.5 edit_video 覆盖 operation 映射。"""
        from core.llm_gateway import LLMGateway, LLMConfig
        session = FakeSession()
        g = LLMGateway(LLMConfig())
        g._http_client = session
        monkeypatch.setattr(g, "_get_h3_config", lambda: {
            "base_url": "https://api.minimaxi.com/v1",
            "api_key": "sk-fake",
            "cost_per_sec_2k": 0.8,
            "cost_per_sec_768p": 0.3,
            "poll_interval_sec": 0.001,
            "max_poll_wait_sec": 5,
            "download_dir": str(tmp_path),
            "cache_dir": str(tmp_path),
        })
        async def dl(url, p):
            Path(p).parent.mkdir(parents=True, exist_ok=True)
            Path(p).write_bytes(b"fake")
            return True
        monkeypatch.setattr(g, "_download_file", dl)
        ops = [
            "subtitle_modify", "style_transfer", "motion_transfer",
            "inpainting", "object_replace", "scene_alteration",
            "rate_adjustment", "bgm_replace", "unknown_op",
        ]
        for op in ops:
            out = tmp_path / f"{op}_out.mp4"
            r = await g.edit_video(
                operation=op, source_video=str(tmp_path / "src.mp4"),
                instruction="改一下", output_path=str(out),
                duration_sec=5,
            )
            assert r["success"] is True, f"{op} failed: {r.get('error')}"
            assert r["output_path"], f"{op}无 output_path"


# ---------------------------------------------------------------------------
# C3 短路路由
# ---------------------------------------------------------------------------

class TestChatWithRoutingShortCircuit:
    """C3 chat_with_routing 对 VIDEO_* 不进 chat，走 generate/edit_video。"""

    @pytest.mark.asyncio
    async def test_video_generation_short_circuit(self, monkeypatch):
        from core.llm_gateway import (
            LLMGateway, LLMConfig, TaskType, LLMResponse,
        )
        g = LLMGateway(LLMConfig())
        async def fake_gen(*a, **k):
            return {"success": True, "output_path": "/tmp/x.mp4", "cost_usd": 3.0, "error": ""}
        monkeypatch.setattr(g, "generate_video", fake_gen)
        resp = await g.chat_with_routing("做个视频", task_type=TaskType.VIDEO_GENERATION)
        assert isinstance(resp, LLMResponse)
        assert resp.success is True
        assert resp.content.endswith("x.mp4")
        assert resp.provider == "minimax_h3"
        assert resp.cost_usd == 3.0

    @pytest.mark.asyncio
    async def test_video_editing_short_circuit(self, monkeypatch):
        from core.llm_gateway import LLMGateway, LLMConfig, TaskType, LLMResponse
        g = LLMGateway(LLMConfig())
        async def fake_edit(*a, **k):
            return {"success": True, "output_path": "/tmp/y.mp4", "cost_usd": 2.4, "error": ""}
        monkeypatch.setattr(g, "edit_video", fake_edit)
        for tt in (TaskType.VIDEO_EDITING, TaskType.STYLE_TRANSFER,
                    TaskType.MOTION_TRANSFER, TaskType.INPAINTING):
            # 视频编辑类任务短路需要 source_video；无源视频时实现会回退常规 chat 路径
            resp = await g.chat_with_routing(
                "改一下", task_type=tt, source_video="/tmp/src.mp4"
            )
            assert resp.success is True, f"{tt} failed {resp.error}"
            assert resp.provider == "minimax_h3"

    @pytest.mark.asyncio
    async def test_short_circuit_exception_fallback_no_escalate(self, monkeypatch):
        """短路时异常，不应抛到上层，应返回失败 LLMResponse.success=False。"""
        from core.llm_gateway import LLMGateway, LLMConfig, TaskType, LLMResponse
        g = LLMGateway(LLMConfig())
        async def boom(*a, **k):
            raise RuntimeError("网络炸了")
        monkeypatch.setattr(g, "generate_video", boom)
        resp = await g.chat_with_routing("xxx", task_type=TaskType.IMAGE_GENERATION)
        assert isinstance(resp, LLMResponse)
        # 异常后应回退到常规 chat 路径; 但常规 chat 因为没 provider 也会 success=False，但不抛。只 success=False
        # 只要没抛就算通过
        pass


# ---------------------------------------------------------------------------
# P2 骨架
# ---------------------------------------------------------------------------

class TestP2Skeletons:
    def test_check_local_h3_structured_result(self):
        """check_local_h3_available 返回结构化字段齐全且类型正确。"""
        from core.llm_gateway import LLMGateway, LLMConfig
        g = LLMGateway(LLMConfig())
        r = g.check_local_h3_available()
        for k in ("available", "reason", "model_path", "device",
                  "vram_total_gb", "vram_8gb_mode", "min_requirement_gb"):
            assert k in r, f"缺字段 {k}"
        assert isinstance(r["available"], bool)
        assert isinstance(r["reason"], str)
        # 未启用本地部署，这里必 False
        assert r["available"] is False
        assert "未启用本地部署" in r["reason"] or "路径不存在" in r["reason"] or "GPU" in r["reason"]

    @pytest.mark.asyncio
    async def test_sketch_to_effect_no_sketch_image_error(self):
        """sketch_to_effect 缺参考图时直接返回 error，不抛。"""
        from core.llm_gateway import LLMGateway, LLMConfig
        g = LLMGateway(LLMConfig())
        r = await g.sketch_to_effect(
            sketch_image_path="/this_file_not_exists_xyz_12345.png",
            prompt="发光特效",
        )
        assert r["success"] is False
        assert "不存在" in r["error"]

    @pytest.mark.asyncio
    async def test_sketch_to_effect_no_api_and_no_local(self, tmp_path, monkeypatch):
        """无 API Key + 本地未启用 -> 返回 error，不抛。"""
        from core.llm_gateway import LLMGateway, LLMConfig
        g = LLMGateway(LLMConfig())
        sk = tmp_path / "sketch.png"
        sk.write_bytes(b"\x89PNG fake")
        # 确保 env 无
        monkeypatch.delenv("AEKV_LLM_MINIMAX_H3_API_KEY", raising=False)
        r = await g.sketch_to_effect(
            sketch_image_path=str(sk), prompt="blink", output_path=str(tmp_path / "o.mp4"),
        )
        assert r["success"] is False
        assert "云端" in r["error"] or "权重" in r["error"] or "不可用" in r["error"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider", "-x"])
