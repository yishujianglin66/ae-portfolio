# -*- coding: utf-8 -*-
"""`ResolveAutomationEngine` 返回值诚实性契约（2026-09-24 审计）。

被修掉的缺陷：8 个方法注解 `-> bool` 却**无条件 `return True`**，使"操作没生效"
被静默当成成功 —— 其中 `apply_cdl` 最典型：Lua 里 `local ok = item:SetCDL(...)`
已经把真实结果接住了，却只 emit `cdl_applied = true`，真相在手上被丢掉。

本文件锁三条契约：
  1. Lua **必须** 从 API 返回值取 `ok` 并 emit；
  2. Python 必须**消费**它：ok=true→True，ok=false→False；
  3. **取不到 `ok` 一律判失败**（不得默认成功）—— 这是防线本身。

全部打桩，不需要 Resolve、不启动任何进程。
"""
import sys
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from integrations.resolve_engine import (  # noqa: E402
    CDLConfig,
    KenBurnsConfig,
    ResolveAutomationEngine,
    ResolveError,
    SpeedCurve,
    TransformConfig,
)

# 会调 Resolve 改状态的方法（审计对象的 6 个）
RESOLVE_METHODS = [
    ("delete_project", lambda e: e.delete_project("p"), "DeleteProject"),
    ("switch_page", lambda e: e.switch_page("edit"), "OpenPage"),
]
# 需要预置项目/片段参数的方法单独构造
LAMBDA_EXTRA = {
    "apply_cdl": (lambda e: e.apply_cdl("p", "t", 1, CDLConfig()), "SetCDL"),
    "apply_lut": (lambda e: e.apply_lut("p", "t", 1, "x.cube"), "SetLUT"),
    "set_speed": (lambda e: e.set_speed("p", 1, 1.0), "Speed"),
    "set_transform": (lambda e: e.set_transform("p", 1, TransformConfig()), "Zoom X"),
}


@pytest.fixture
def engine(monkeypatch):
    """构造真实实例并**标为可用**：本文件测的是"返回值消费"，
    可用性门槛会挡在 `_execute_lua` 之前（那是另一条契约，由
    `test_requires_available` 用不可用实例单独覆盖）。"""
    import integrations.resolve_engine as re_mod

    monkeypatch.setattr(re_mod, "find_fuscript_exe", lambda: None)
    eng = ResolveAutomationEngine(fuscript_path="")
    eng.available = True
    eng.unavailable_reason = ""
    return eng


@pytest.fixture
def unavailable_engine(monkeypatch):
    """不可用实例：用于验证前置检查抛明确错误"""
    import integrations.resolve_engine as re_mod

    monkeypatch.setattr(re_mod, "find_fuscript_exe", lambda: None)
    eng = ResolveAutomationEngine(fuscript_path="")
    eng.available = False
    eng.unavailable_reason = "test: fuscript 缺失"
    return eng


def _stub(monkeypatch, engine, ret):
    """把 _execute_lua 打桩成返回给定值"""
    monkeypatch.setattr(engine, "_execute_lua", lambda code: ret)


def _capture(monkeypatch, engine, ret):
    """打桩并抓住 Lua 文本"""
    box = {}
    monkeypatch.setattr(engine, "_execute_lua", lambda code: (box.setdefault("lua", code), ret)[1])
    return box


# ---------------------------------------------------------------------------
# 1) _ok_from 的三态
# ---------------------------------------------------------------------------

class TestOkFrom:
    def test_true(self, engine):
        assert engine._ok_from({"ok": True}, "x") is True

    def test_false(self, engine):
        assert engine._ok_from({"ok": False}, "x") is False

    def test_missing_flag_is_failure_not_success(self, engine):
        """**最关键的一条**：拿不到标志不得默认成功（Bool 型 API 的严格判据）"""
        assert engine._ok_from({"item": "a"}, "x") is False

    def test_bool_api_with_nil_return_is_failure(self, engine):
        """Bool 型 API 却拿到 nil（无返回值）→ 判失败，不得放行"""
        assert engine._ok_from(
            {"ret_type": "nil", "completed": True}, "x") is False

    def test_void_api_with_nil_return_is_success_but_unverified(self, engine):
        """void 型 API（实测 OpenPage 对合法/非法页都返回 nil）：
        调用未报错即成功，但明确标注未经效果验证"""
        assert engine._ok_from(
            {"ret_type": "nil", "completed": True}, "x", void_api=True) is True

    def test_void_api_with_unexpected_type_is_failure(self, engine):
        """void 型却拿到非 nil 的怪类型 → 不能放行"""
        assert engine._ok_from(
            {"ret_type": "table", "completed": True}, "x", void_api=True) is False

    def test_void_api_without_completed_is_failure(self, engine):
        """缺 completed（说明 Lua 没走到 emit）→ 判失败"""
        assert engine._ok_from(
            {"ret_type": "nil"}, "x", void_api=True) is False

    def test_non_dict_is_failure(self, engine):
        assert engine._ok_from(None, "x") is False
        assert engine._ok_from({"raw": "noise", "returncode": 0}, "x") is False

    def test_non_bool_flag_is_failure(self, engine):
        """字符串 "true" / 1 都不算数 —— 只认真布尔"""
        assert engine._ok_from({"ok": "true"}, "x") is False
        assert engine._ok_from({"ok": 1}, "x") is False


# ---------------------------------------------------------------------------
# 2) 六个改状态的方法：消费真实标志
# ---------------------------------------------------------------------------

class TestResolveCallingMethods:
    @pytest.mark.parametrize("name,call,_api", RESOLVE_METHODS)
    def test_true_passthrough(self, engine, monkeypatch, name, call, _api):
        _stub(monkeypatch, engine, {"ok": True})
        assert call(engine) is True

    @pytest.mark.parametrize("name,call,_api", RESOLVE_METHODS)
    def test_false_passthrough(self, engine, monkeypatch, name, call, _api):
        _stub(monkeypatch, engine, {"ok": False})
        assert call(engine) is False, f"{name} 必须把 API 的 false 传出来"

    def test_bool_methods_strict_on_nil(self, engine, monkeypatch):
        """`delete_project` 属 Bool 型（真机实测返回 boolean）→ 拿到 nil 必须判失败"""
        _stub(monkeypatch, engine, {"ret_type": "nil", "completed": True})
        assert engine.delete_project("p") is False

    def test_switch_page_tolerates_nil(self, engine, monkeypatch):
        """`switch_page` 属 void 型（真机实测 nil）→ 调用未报错记成功（未验证）"""
        _stub(monkeypatch, engine, {"ret_type": "nil", "completed": True})
        assert engine.switch_page("edit") is True

    def test_extra_methods(self, engine, monkeypatch):
        for name, (call, api_kw) in LAMBDA_EXTRA.items():
            _stub(monkeypatch, engine, {"ok": True})
            assert call(engine) is True, name
            _stub(monkeypatch, engine, {"ok": False})
            assert call(engine) is False, name

    def test_requires_available(self, unavailable_engine):
        """不可用时前置检查抛明确错误（而非拿假 True 糊过去）"""
        for _name, (call, _api) in LAMBDA_EXTRA.items():
            with pytest.raises(ResolveError):
                call(unavailable_engine)
        with pytest.raises(ResolveError):
            unavailable_engine.delete_project("p")
        with pytest.raises(ResolveError):
            unavailable_engine.switch_page("edit")


# ---------------------------------------------------------------------------
# 3) Lua 侧必须真的接住 API 返回值
# ---------------------------------------------------------------------------

class TestLuaCapturesApiResult:
    @pytest.mark.parametrize(
        "name,call,api",
        RESOLVE_METHODS + [(k, v[0], v[1]) for k, v in LAMBDA_EXTRA.items()])
    def test_lua_references_api_return(self, engine, monkeypatch, name, call, api):
        box = _capture(monkeypatch, engine, {"ok": True})
        call(engine)
        lua = box["lua"]
        assert api in lua, f"{name}: Lua 未调用 {api}"
        assert "local ok" in lua, f"{name}: Lua 未接住 {api} 的返回值"
        assert "emit_ok({ok =" in lua, f"{name}: 未 emit 真实 ok 标志"

    def test_set_transform_ands_all_six_properties(self, engine, monkeypatch):
        """6 个 SetProperty 必须逐项相与 —— 任一项失败即整体 False"""
        box = _capture(monkeypatch, engine, {"ok": True})
        engine.set_transform("p", 1, TransformConfig())
        lua = box["lua"]
        for prop in ("Zoom X", "Zoom Y", "Position X", "Position Y", "Rotation", "Opacity"):
            assert f'SetProperty("{prop}"' in lua, f"缺 {prop}"
        assert lua.count("and ok") >= 5, "未逐项相与"


# ---------------------------------------------------------------------------
# 4) 两个"委托型"方法不得吞掉结果
# ---------------------------------------------------------------------------

class TestDelegates:
    def test_speed_curve_returns_delegate_result(self, engine, monkeypatch):
        monkeypatch.setattr(engine, "set_speed", lambda *a, **k: False)
        assert engine.apply_speed_curve("p", 1, SpeedCurve()) is False

    def test_ken_burns_returns_delegate_result(self, engine, monkeypatch):
        monkeypatch.setattr(engine, "set_transform", lambda *a, **k: False)
        assert engine.apply_ken_burns("p", 1, KenBurnsConfig()) is False


# ---------------------------------------------------------------------------
# 5) 两个"仅本地登记"的方法：明确它们**不是**缺陷
# ---------------------------------------------------------------------------

class TestLocalOnlyTrackingIsHonest:
    """`apply_lut_file` / `apply_color_wheel` 只把配置登记到 Python map（给 FFmpeg 滤镜用），
    不调 Resolve —— 它们的 True 表示"配置已登记"，属实。审计时已据此排除，此处锁住语义。"""

    def test_apply_lut_file_tracks_and_true(self, engine, tmp_path):
        cube = tmp_path / "x.cube"
        cube.write_text("LUT_3D_SIZE 2\n", encoding="utf-8")
        assert engine.apply_lut_file("p", 1, str(cube)) is True
        assert engine._lut_file_map["p"][1] == str(cube)

    def test_apply_lut_file_missing_raises(self, engine, tmp_path):
        with pytest.raises(ResolveError):
            engine.apply_lut_file("p", 1, str(tmp_path / "nope.cube"))
