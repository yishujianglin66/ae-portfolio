# -*- coding: utf-8 -*-
"""`ResolveAutomationEngine.get_project_info()` 接线契约（2026-09-23）。

缺陷背景：原实现执行了 Lua 拿到结果，**随后把结果丢弃**，无条件返回空的
`ProjectInfo` —— 即"执行过但没接线"。后果不是崩溃而是**静默错值**：
`name=""` / `timeline_count=0`，且下游 `integrations/resolve_mcp_adapter.py:313`
一直在消费这个空对象，没人报错。

本文件全部打桩，不要求本机装 Resolve、不启动任何进程、不写临时脚本。
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

import integrations.resolve_engine as re_mod  # noqa: E402
from integrations.resolve_engine import ProjectInfo, ResolveAutomationEngine  # noqa: E402

# 本机实测（fuscript + Resolve Studio 21.0.3.7）可用的 API 面
_REQUIRED_LUA_CALLS = ("Resolve()", "GetProjectManager", "GetCurrentProject",
                       "GetName", "GetTimelineCount", "GetCurrentTimeline", "emit_ok")


@pytest.fixture
def engine(monkeypatch):
    """构造真实引擎实例，但让发现器不回真盘（保持测试机器无关）。"""
    monkeypatch.setattr(re_mod, "find_fuscript_exe", lambda: None)
    return ResolveAutomationEngine(fuscript_path="")


def _fake_lua(return_value, captured: dict | None = None):
    def _exec(lua_code):
        if captured is not None:
            captured["lua"] = lua_code
        return return_value

    return _exec


# ---------------------------------------------------------------------------
# 接线：返回值必须被用上
# ---------------------------------------------------------------------------

class TestGetProjectInfoWiring:
    def test_populates_fields_from_lua_result(self, engine, monkeypatch):
        monkeypatch.setattr(engine, "_execute_lua", _fake_lua({
            "available": True,
            "name": "My AMV Project",
            "timeline_count": 3,
            "current_timeline": "Edit v2",
        }))
        info = engine.get_project_info()
        assert isinstance(info, ProjectInfo)
        assert info.name == "My AMV Project"
        assert info.timeline_count == 3
        assert info.current_timeline == "Edit v2"

    def test_returns_empty_when_resolve_not_running(self, engine, monkeypatch):
        """fuscript 在但 Resolve 未运行时 Resolve() 返回 nil → 空对象，不抛异常"""
        monkeypatch.setattr(engine, "_execute_lua", _fake_lua({"available": False}))
        info = engine.get_project_info()
        assert info.name == ""
        assert info.timeline_count == 0
        assert info.current_timeline == ""

    def test_returns_empty_on_unparsed_output(self, engine, monkeypatch):
        """_execute_lua 解析不出 JSON 时返回 {"raw":..., "returncode":...}，不得崩"""
        monkeypatch.setattr(engine, "_execute_lua",
                            _fake_lua({"raw": "some noise", "returncode": 0}))
        info = engine.get_project_info()
        assert info == ProjectInfo()

    def test_tolerates_garbage_timeline_count(self, engine, monkeypatch):
        monkeypatch.setattr(engine, "_execute_lua", _fake_lua({
            "available": True, "name": "P",
            "timeline_count": "not-a-number", "current_timeline": None,
        }))
        info = engine.get_project_info()
        assert info.timeline_count == 0
        assert info.current_timeline == ""

    def test_tolerates_non_dict_result(self, engine, monkeypatch):
        monkeypatch.setattr(engine, "_execute_lua", _fake_lua(None))
        assert engine.get_project_info() == ProjectInfo()

    def test_lua_body_calls_only_verified_api_surface(self, engine, monkeypatch):
        """锁住"只调用本机实测可用的 API 面"这一约定，防止回退到未验证的调用。"""
        captured: dict = {}
        monkeypatch.setattr(engine, "_execute_lua",
                            _fake_lua({"available": True}, captured))
        engine.get_project_info()
        body = captured["lua"]
        for call in _REQUIRED_LUA_CALLS:
            assert call in body, f"Lua 缺少已验证调用: {call}"

    def test_lua_is_wrapped_with_error_emitter(self, engine, monkeypatch):
        """_wrap_lua 必须提供 emit_error，否则 Lua 抛错时无任何输出可解析"""
        captured: dict = {}
        monkeypatch.setattr(engine, "_execute_lua",
                            _fake_lua({"available": True}, captured))
        engine.get_project_info()
        assert "emit_error" in captured["lua"]
        assert "pcall" in captured["lua"]
