# -*- coding: utf-8 -*-
"""SkillRegistryService 测试（P1-2：网关消费技能卡片库）。"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import yaml
from src.mcp_gateway import initialize_gateway
from src.mcp_gateway.skill_service import SkillRegistryService


# ------------------------------------------------------------------ 真实卡片库
class TestRealRegistry:
    """直接消费仓库 schemas/skill_cards（P1-1 产物 64 张）。"""

    def setup_method(self):
        self.svc = SkillRegistryService()

    def test_list_all(self):
        r = self.svc.list_skills(limit=200)
        assert r["success"] and r["total_in_registry"] >= 64

    def test_list_filters(self):
        headless = self.svc.list_skills(headless="headless", limit=200)
        assert headless["count"] >= 20
        for row in headless["skills"]:
            assert row["headless"] == "headless"
        gpu = self.svc.list_skills(cost_class="gpu_local", limit=200)
        assert 0 < gpu["count"] <= 6

    def test_show_known_card(self):
        r = self.svc.show_skill("fx_bloom")
        assert r["success"] and r["card"]["stage"] == "active"
        assert r["card"]["evidence_chain"]["status"] == "real_execution"

    def test_show_missing(self):
        assert self.svc.show_skill("no_such_skill")["success"] is False

    def test_invoke_guidance_for_recipe(self):
        r = asyncio.run(self.svc.invoke("fx_badtv"))
        assert r["success"] and r["mode"] == "guidance"
        assert "RECIPES" in r["recipe_ref"]

    def test_invoke_tool_not_registered_hint(self):
        # 未 bind registry 时诚实报错，不静默
        r = asyncio.run(self.svc.invoke("ffmpeg_concat_videos",
                                        {"input_paths": ["a.mp4"], "output_path": "o.mp4"}))
        assert r["success"] is False and "bind" in r["error"]


# ------------------------------------------------------------------ 治理闸门
def _make_mini_library(tmp_path: Path) -> SkillRegistryService:
    cards = tmp_path / "skill_cards"
    (cards / "media").mkdir(parents=True)
    dep = {
        "skill_id": "dep_tool", "domain": "media", "skill_type": "tool_wrapper",
        "version": "1.0.0", "stage": "deprecated",
        "requires_host": [{"app": "ffmpeg", "version": "*"}],
        "headless": "headless",
        "cost": {"class": "free_local", "typical_duration_sec": 1},
        "contract": {"inputs": {"type": "object"}},
        "tool_ref": {"gateway_tool": "dep_tool"},
        "intended_use": "x", "out_of_scope": "y",
        "evidence_chain": {"validated_at": "2026-09-25", "status": "auto_generated"},
    }
    (cards / "media" / "dep_tool.yaml").write_text(
        yaml.safe_dump(dep, allow_unicode=True), encoding="utf-8")
    reg = {"registry": "skill_cards", "schema_version": "0.1", "count": 1,
           "skills": {"dep_tool": {"domain": "media", "skill_type": "tool_wrapper",
                                   "version": "1.0.0", "stage": "deprecated",
                                   "headless": "headless", "cost_class": "free_local",
                                   "cost_sec": 1, "hosts": ["ffmpeg"],
                                   "path": "skill_cards/media/dep_tool.yaml"}}}
    (cards / "registry.json").write_text(json.dumps(reg), encoding="utf-8")
    import src.mcp_gateway.skill_service as ss
    ss.REPO_ROOT = tmp_path  # _load_card 用 REPO_ROOT 拼相对路径——mini 库以 tmp_path 为根
    return SkillRegistryService(registry_path=cards / "registry.json")


def test_governance_gate_deprecated_blocked(tmp_path):
    svc = _make_mini_library(tmp_path)
    r = asyncio.run(svc.invoke("dep_tool", {}))
    assert r["success"] is False and "治理闸门" in r["error"]


# ------------------------------------------------------------------ 契约校验 + 路由
class _StubTool:
    engine, action = "ffmpeg", "concat"


class _StubRegistry:
    def __init__(self):
        self.calls = []

    def get_tool(self, name):
        return _StubTool() if name == "real_tool" else None

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        return {"content": [{"type": "text", "text": json.dumps(
            {"success": True, "metadata": {"echo": arguments}})}], "isError": False}


def _svc_with_wrapped_tool(tmp_path):
    cards = tmp_path / "skill_cards"
    (cards / "media").mkdir(parents=True)
    card = {
        "skill_id": "wrap_ok", "domain": "media", "skill_type": "tool_wrapper",
        "version": "1.0.0", "stage": "validated",
        "requires_host": [{"app": "ffmpeg", "version": "*"}],
        "headless": "headless",
        "cost": {"class": "free_local", "typical_duration_sec": 1},
        "contract": {"inputs": {"type": "object",
                                "properties": {"p": {"type": "string"}},
                                "required": ["p"]}},
        "tool_ref": {"gateway_tool": "real_tool"},
        "intended_use": "x", "out_of_scope": "y",
        "evidence_chain": {"validated_at": "2026-09-25", "status": "auto_generated"},
    }
    (cards / "media" / "wrap_ok.yaml").write_text(yaml.safe_dump(card), encoding="utf-8")
    reg = {"count": 1, "skills": {"wrap_ok": {**{k: card[k] for k in
            ("domain", "skill_type", "version", "stage", "headless")},
            "cost_class": "free_local", "cost_sec": 1, "hosts": ["ffmpeg"],
            "path": "skill_cards/media/wrap_ok.yaml"}}}
    (cards / "registry.json").write_text(json.dumps(reg), encoding="utf-8")
    import src.mcp_gateway.skill_service as ss
    ss.REPO_ROOT = tmp_path
    svc = SkillRegistryService(registry_path=cards / "registry.json")
    stub = _StubRegistry()
    svc.bind(stub)
    return svc, stub


def test_invoke_contract_validation_blocks(tmp_path):
    svc, stub = _svc_with_wrapped_tool(tmp_path)
    r = asyncio.run(svc.invoke("wrap_ok", {"wrong": 1}))  # 缺 required p
    assert r["success"] is False and "契约校验失败" in r["error"]
    assert stub.calls == []  # 未漏到底层工具


def test_invoke_routes_to_gateway_tool(tmp_path):
    svc, stub = _svc_with_wrapped_tool(tmp_path)
    r = asyncio.run(svc.invoke("wrap_ok", {"p": "hello"}))
    assert r["success"] and r["mode"] == "tool_call"
    assert stub.calls == [("real_tool", {"p": "hello"})]
    assert r["card_meta"]["headless"] == "headless"


def test_invoke_missing_card(tmp_path):
    svc, _ = _svc_with_wrapped_tool(tmp_path)
    r = asyncio.run(svc.invoke("no_such_card", {}))
    assert r["success"] is False and "不存在" in r["error"]


# ------------------------------------------------------------------ 网关注册
class TestGatewayWiring:
    def test_skill_tools_registered_without_engines(self):
        reg = initialize_gateway(engines={}, services={})
        names = set(reg.tools)
        assert {"skill_list", "skill_show", "skill_invoke"} <= names

    def test_skill_list_via_registry_call(self):
        reg = initialize_gateway(engines={}, services={})
        out = asyncio.run(reg.call_tool("skill_list", {"stage": "active", "limit": 200}))
        payload = json.loads(out["content"][0]["text"])
        meta = payload["metadata"]
        assert meta["success"] and meta["count"] >= 9  # P1-1 基线 9 张 active
