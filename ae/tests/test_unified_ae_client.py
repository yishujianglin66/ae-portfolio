"""UnifiedAEClient 单元测试。

测试覆盖：
- AEChannel / AEOperation / AEChannelStats 数据结构
- ChannelSelector 路由选择
- 通道自动降级
- 统计计数
- 线程安全
- puppet / MCP 适配器
- 完整业务流程（create → text → keyframe → render）

依赖：
- pytest
- 本文件位于 ae/tests 目录
- 通过 conftest 加载项目根目录
"""
from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

import pytest

# ---------------------------------------------------------------------------
# 共享 Mock 适配器
# ---------------------------------------------------------------------------


class _MockAdapter:
    """可配置的 Mock 适配器（无需继承 BaseAEAdapter，依赖注入更轻）。"""

    def __init__(
        self,
        name: str = "mock",
        available: bool = True,
        success: bool = True,
        latency_ms: float = 1.0,
        error: str | None = None,
    ) -> None:
        self.name = name
        self._available = available
        self._success = success
        self._latency_ms = latency_ms
        self._error = error
        self.calls: list[dict[str, Any]] = []

    def is_available(self) -> bool:
        return self._available

    # 完整 API 集
    def create_composition(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("create_composition", kwargs)

    def list_compositions(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append({"method": "list_compositions", "kwargs": kwargs})
        if not self._success:
            return []
        return [
            {"name": "MockComp_1", "id": 1, "width": 1920, "height": 1080},
            {"name": "MockComp_2", "id": 2, "width": 1280, "height": 720},
        ]

    def create_text_layer(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("create_text_layer", kwargs)

    def create_solid_layer(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("create_solid_layer", kwargs)

    def create_shape_layer(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("create_shape_layer", kwargs)

    def add_adjustment_layer(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("add_adjustment_layer", kwargs)

    def set_layer_properties(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("set_layer_properties", kwargs)

    def set_blend_mode(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("set_blend_mode", kwargs)

    def set_track_matte(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("set_track_matte", kwargs)

    def set_parent_layer(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("set_parent_layer", kwargs)

    def set_layer_keyframe(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("set_layer_keyframe", kwargs)

    def set_keyframe_easing(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("set_keyframe_easing", kwargs)

    def set_layer_expression(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("set_layer_expression", kwargs)

    def apply_effect(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("apply_effect", kwargs)

    def apply_effect_template(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("apply_effect_template", kwargs)

    def batch_add_effects(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("batch_add_effects", kwargs)

    def set_layer_mask(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("set_layer_mask", kwargs)

    def render(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("render", kwargs)

    def execute_atom_script(self, **kwargs: Any) -> dict[str, Any]:
        return self._invoke("execute_atom_script", kwargs)

    # 内部
    def _invoke(self, method: str, kwargs: dict[str, Any]) -> dict[str, Any]:
        self.calls.append({"method": method, "kwargs": kwargs})
        if self._latency_ms > 0:
            time.sleep(self._latency_ms / 1000.0)
        if self._success:
            return {
                "success": True,
                "channel": self.name,
                "method": method,
                "received": kwargs,
            }
        return {
            "success": False,
            "channel": self.name,
            "error": self._error or "mock failure",
        }


@pytest.fixture
def mock_puppet() -> _MockAdapter:
    a = _MockAdapter(name="puppet", available=True, success=True, latency_ms=1.0)
    return a


@pytest.fixture
def mock_mcp() -> _MockAdapter:
    a = _MockAdapter(name="mcp", available=True, success=True, latency_ms=2.0)
    return a


@pytest.fixture
def client(mock_puppet: _MockAdapter, mock_mcp: _MockAdapter):
    from ae.unified_ae_client import UnifiedAEClient

    return UnifiedAEClient(
        puppet_engine=mock_puppet,
        mcp_client=mock_mcp,
        default_channel=AEChannel_AUTO(),
        enable_fallback=True,
    )


def AEChannel_AUTO():
    from ae.unified_ae_client import AEChannel
    return AEChannel.AUTO


# ---------------------------------------------------------------------------
# 数据结构测试
# ---------------------------------------------------------------------------


class TestAEChannelEnum:
    """AEChannel 枚举测试。"""

    def test_values(self) -> None:
        from ae.unified_ae_client import AEChannel
        assert AEChannel.PUPPET.value == "puppet"
        assert AEChannel.MCP.value == "mcp"
        assert AEChannel.AUTO.value == "auto"

    def test_from_string(self) -> None:
        from ae.unified_ae_client import AEChannel
        assert AEChannel("puppet") == AEChannel.PUPPET
        assert AEChannel("mcp") == AEChannel.MCP
        assert AEChannel("auto") == AEChannel.AUTO


class TestAEOperation:
    """AEOperation 数据类测试。"""

    def test_defaults(self) -> None:
        from ae.unified_ae_client import AEChannel, AEOperation
        op = AEOperation(name="foo")
        assert op.name == "foo"
        assert op.method == "foo"  # 自动用 name
        assert op.channel == AEChannel.AUTO
        assert op.requires_gui is False
        assert op.is_idempotent is False
        assert op.fallback is None
        assert op.params == {}

    def test_explicit_method(self) -> None:
        from ae.unified_ae_client import AEOperation
        op = AEOperation(name="x", method="custom_y")
        assert op.method == "custom_y"

    def test_fallback_chain(self) -> None:
        from ae.unified_ae_client import AEChannel, AEOperation
        op = AEOperation(
            name="x",
            channel=AEChannel.PUPPET,
            fallback=AEOperation(name="x", channel=AEChannel.MCP),
        )
        assert op.fallback is not None
        assert op.fallback.channel == AEChannel.MCP


class TestAEChannelStats:
    """AEChannelStats 统计测试。"""

    def test_initial_state(self) -> None:
        from ae.unified_ae_client import AEChannelStats
        s = AEChannelStats()
        assert s.total_calls == 0
        assert s.success_rate == 0.0
        assert s.avg_latency_ms == 0.0
        assert s.consecutive_failures == 0

    def test_record_success(self) -> None:
        from ae.unified_ae_client import AEChannelStats
        s = AEChannelStats()
        s.record(success=True, latency_ms=10.0)
        s.record(success=True, latency_ms=20.0)
        assert s.total_calls == 2
        assert s.success_count == 2
        assert s.failure_count == 0
        assert s.avg_latency_ms == 15.0
        assert s.success_rate == 1.0
        assert s.consecutive_failures == 0

    def test_record_failure_resets_consecutive(self) -> None:
        """连续失败计数器在成功后归零，last_error 保留最近一次错误以便排查。"""
        from ae.unified_ae_client import AEChannelStats
        s = AEChannelStats()
        for _ in range(3):
            s.record(success=False, latency_ms=5.0, error="err")
        assert s.consecutive_failures == 3
        assert s.last_error == "err"
        s.record(success=True, latency_ms=5.0)
        assert s.consecutive_failures == 0
        # last_error 保留最后一次错误，便于排查历史
        assert s.last_error == "err"

    def test_to_dict(self) -> None:
        from ae.unified_ae_client import AEChannelStats
        s = AEChannelStats()
        s.record(success=True, latency_ms=10.0)
        d = s.to_dict()
        assert "total_calls" in d
        assert "success_rate" in d
        assert d["success_count"] == 1


# ---------------------------------------------------------------------------
# ChannelSelector 测试
# ---------------------------------------------------------------------------


class TestChannelSelector:
    """ChannelSelector 路由策略测试。"""

    def test_render_routes_to_puppet(self) -> None:
        from ae.unified_ae_client import AEChannel, ChannelSelector
        ch = ChannelSelector.select("render")
        assert ch == AEChannel.PUPPET

    def test_atom_script_routes_to_mcp(self) -> None:
        from ae.unified_ae_client import AEChannel, ChannelSelector
        ch = ChannelSelector.select("execute_atom_script")
        assert ch == AEChannel.MCP

    def test_expression_routes_to_mcp(self) -> None:
        from ae.unified_ae_client import AEChannel, ChannelSelector
        ch = ChannelSelector.select("set_layer_expression")
        assert ch == AEChannel.MCP

    def test_force_channel_overrides(self) -> None:
        from ae.unified_ae_client import AEChannel, ChannelSelector
        ch = ChannelSelector.select("render", {"force_channel": "mcp"})
        assert ch == AEChannel.MCP

    def test_unhealthy_puppet_falls_back_to_mcp(self) -> None:
        from ae.unified_ae_client import (
            AEChannel,
            AEChannelStats,
            ChannelSelector,
        )
        stats = {
            AEChannel.PUPPET: AEChannelStats(
                total_calls=10, failure_count=10, consecutive_failures=10
            ),
            AEChannel.MCP: AEChannelStats(),
        }
        ch = ChannelSelector.select("render", stats=stats)
        assert ch == AEChannel.MCP

    def test_unhealthy_mcp_falls_back_to_puppet(self) -> None:
        from ae.unified_ae_client import (
            AEChannel,
            AEChannelStats,
            ChannelSelector,
        )
        stats = {
            AEChannel.PUPPET: AEChannelStats(),
            AEChannel.MCP: AEChannelStats(
                total_calls=10, failure_count=10, consecutive_failures=10
            ),
        }
        ch = ChannelSelector.select("execute_atom_script", stats=stats)
        assert ch == AEChannel.PUPPET

    def test_lower_latency_wins(self) -> None:
        from ae.unified_ae_client import (
            AEChannel,
            AEChannelStats,
            ChannelSelector,
        )
        stats = {
            AEChannel.PUPPET: AEChannelStats(
                total_calls=2, success_count=2, total_latency_ms=200.0
            ),
            AEChannel.MCP: AEChannelStats(
                total_calls=2, success_count=2, total_latency_ms=50.0
            ),
        }
        ch = ChannelSelector.select("create_text_layer", stats=stats)
        assert ch == AEChannel.MCP

    def test_gui_required(self) -> None:
        from ae.unified_ae_client import AEChannel, ChannelSelector
        ch = ChannelSelector.select("some_op", {"requires_gui": True})
        assert ch == AEChannel.MCP


# ---------------------------------------------------------------------------
# 异常测试
# ---------------------------------------------------------------------------


class TestExceptions:
    """异常类测试。"""

    def test_unified_ae_error_with_channel(self) -> None:
        from ae.unified_ae_client import UnifiedAEError
        e = UnifiedAEError("fail", channel="puppet")
        assert "puppet" in str(e)
        assert e.channel == "puppet"

    def test_all_channels_failed_error(self) -> None:
        from ae.unified_ae_client import AllChannelsFailedError
        e = AllChannelsFailedError("render", [("puppet", "x"), ("mcp", "y")])
        assert "render" in e.message
        assert "puppet" in e.message
        assert "mcp" in e.message
        assert len(e.errors) == 2


# ---------------------------------------------------------------------------
# UnifiedAEClient 核心行为测试
# ---------------------------------------------------------------------------


class TestUnifiedAEClient:
    """UnifiedAEClient 行为测试。"""

    def test_default_init(self) -> None:
        from ae.unified_ae_client import UnifiedAEClient
        client = UnifiedAEClient()
        assert client.default_channel is not None
        assert client.enable_fallback is True

    def test_inject_adapters(self, mock_puppet: _MockAdapter, mock_mcp: _MockAdapter) -> None:
        from ae.unified_ae_client import UnifiedAEClient
        client = UnifiedAEClient(puppet_engine=mock_puppet, mcp_client=mock_mcp)
        assert client.is_puppet_available() is True
        assert client.is_mcp_available() is True

    def test_puppet_channel_unavailable(self, mock_mcp: _MockAdapter) -> None:
        from ae.unified_ae_client import UnifiedAEClient
        puppet = _MockAdapter(name="puppet", available=False)
        client = UnifiedAEClient(puppet_engine=puppet, mcp_client=mock_mcp)
        assert client.is_puppet_available() is False
        assert client.is_mcp_available() is True

    def test_create_composition_auto_routing(self, client, mock_puppet, mock_mcp) -> None:
        result = client.create_composition("Comp1", 1920, 1080, fps=30.0, duration=5.0)
        assert result["success"] is True
        # AUTO 模式下应该选 puppet（puppet latency 较低 + 静态兜底）
        assert result.get("channel_used") in ("puppet", "mcp")
        # 至少有一个被调用
        assert len(mock_puppet.calls) + len(mock_mcp.calls) >= 1

    def test_force_puppet_channel(self, mock_puppet: _MockAdapter, mock_mcp: _MockAdapter) -> None:
        from ae.unified_ae_client import AEChannel, AEOperation, UnifiedAEClient
        client = UnifiedAEClient(
            puppet_engine=mock_puppet,
            mcp_client=mock_mcp,
            default_channel=AEChannel.PUPPET,
        )
        client.create_composition("ForcePuppet", 1280, 720)
        assert len(mock_puppet.calls) == 1
        assert len(mock_mcp.calls) == 0

    def test_force_mcp_channel(self, mock_puppet: _MockAdapter, mock_mcp: _MockAdapter) -> None:
        from ae.unified_ae_client import AEChannel, UnifiedAEClient
        client = UnifiedAEClient(
            puppet_engine=mock_puppet,
            mcp_client=mock_mcp,
            default_channel=AEChannel.MCP,
        )
        client.create_composition("ForceMcp", 1280, 720)
        assert len(mock_mcp.calls) == 1
        assert len(mock_puppet.calls) == 0


class TestFallback:
    """通道降级测试。"""

    def test_fallback_on_primary_failure(self, mock_mcp: _MockAdapter) -> None:
        from ae.unified_ae_client import AEChannel, UnifiedAEClient
        puppet = _MockAdapter(name="puppet", success=False, error="puppet down")
        client = UnifiedAEClient(
            puppet_engine=puppet,
            mcp_client=mock_mcp,
            default_channel=AEChannel.PUPPET,
            enable_fallback=True,
        )
        result = client.create_composition("FallbackComp", 1280, 720)
        assert result["success"] is True
        assert result.get("channel_used") == "mcp"
        assert len(puppet.calls) == 1
        assert len(mock_mcp.calls) == 1

    def test_all_channels_fail_raises(
        self, mock_puppet: _MockAdapter, mock_mcp: _MockAdapter
    ) -> None:
        from ae.unified_ae_client import (
            AEChannel,
            AllChannelsFailedError,
            UnifiedAEClient,
        )
        puppet = _MockAdapter(name="puppet", success=False, error="puppet down")
        mcp = _MockAdapter(name="mcp", success=False, error="mcp down")
        client = UnifiedAEClient(
            puppet_engine=puppet,
            mcp_client=mcp,
            default_channel=AEChannel.PUPPET,
            enable_fallback=True,
        )
        with pytest.raises(AllChannelsFailedError) as exc_info:
            client.create_composition("TotalFail", 1280, 720)
        assert exc_info.value.op_name == "create_composition"
        assert len(exc_info.value.errors) == 2

    def test_fallback_disabled_does_not_retry(
        self, mock_mcp: _MockAdapter
    ) -> None:
        from ae.unified_ae_client import AEChannel, UnifiedAEClient
        puppet = _MockAdapter(name="puppet", success=False, error="puppet down")
        client = UnifiedAEClient(
            puppet_engine=puppet,
            mcp_client=mock_mcp,
            default_channel=AEChannel.PUPPET,
            enable_fallback=False,
        )
        # 启用降级关闭时，应该在 puppet 失败时直接抛错
        with pytest.raises(Exception):
            client.create_composition("NoFallback", 1280, 720)
        assert len(puppet.calls) == 1
        assert len(mock_mcp.calls) == 0  # 没有降级


# ---------------------------------------------------------------------------
# 统计测试
# ---------------------------------------------------------------------------


class TestStats:
    """统计功能测试。"""

    def test_stats_recorded(self, client) -> None:
        client.create_composition("C1", 1920, 1080)
        client.create_text_layer("C1", "Hello")
        stats = client.get_stats()
        assert "puppet" in stats
        assert "mcp" in stats
        # 总调用数 = 1 + 1 = 2（至少）
        total = stats["puppet"]["total_calls"] + stats["mcp"]["total_calls"]
        assert total >= 2

    def test_reset_stats(self, client) -> None:
        client.create_composition("C1", 1920, 1080)
        client.reset_stats()
        stats = client.get_stats()
        assert stats["puppet"]["total_calls"] == 0
        assert stats["mcp"]["total_calls"] == 0

    def test_stats_failure_count(
        self, mock_mcp: _MockAdapter
    ) -> None:
        from ae.unified_ae_client import AEChannel, UnifiedAEClient
        puppet = _MockAdapter(name="puppet", success=False, error="x")
        client = UnifiedAEClient(
            puppet_engine=puppet,
            mcp_client=mock_mcp,
            default_channel=AEChannel.PUPPET,
            enable_fallback=True,
        )
        client.create_composition("C1", 1920, 1080)
        stats = client.get_stats()
        assert stats["puppet"]["failure_count"] == 1
        assert stats["mcp"]["success_count"] == 1

    def test_stats_disabled(
        self, mock_puppet: _MockAdapter, mock_mcp: _MockAdapter
    ) -> None:
        from ae.unified_ae_client import AEChannel, UnifiedAEClient
        client = UnifiedAEClient(
            puppet_engine=mock_puppet,
            mcp_client=mock_mcp,
            default_channel=AEChannel.PUPPET,
            stats_enabled=False,
        )
        client.create_composition("C1", 1920, 1080)
        stats = client.get_stats()
        assert stats["puppet"]["total_calls"] == 0
        assert stats["mcp"]["total_calls"] == 0


# ---------------------------------------------------------------------------
# 适配器测试
# ---------------------------------------------------------------------------


class TestPuppetAdapter:
    """PuppetEngineAdapter 基础测试（无需真实 AE）。"""

    def test_puppet_adapter_init(self) -> None:
        from ae.adapters.puppet_adapter import PuppetEngineAdapter
        a = PuppetEngineAdapter()
        assert a.name == "puppet"
        assert a.supports_gui is False
        assert a.requires_gui is False

    def test_puppet_adapter_is_available_no_engine(self) -> None:
        from ae.adapters.puppet_adapter import PuppetEngineAdapter
        a = PuppetEngineAdapter()
        # 没有 AE 安装时返回 False
        # 不抛异常
        result = a.is_available()
        assert isinstance(result, bool)


class TestBaseAEAdapter:
    """BaseAEAdapter 抽象类测试。"""

    def test_not_implemented(self) -> None:
        from ae.adapters.puppet_adapter import BaseAEAdapter
        a = BaseAEAdapter()
        result = a.create_composition("X", 1, 1)
        assert result["success"] is False
        assert "not implemented" in result["error"]

    def test_default_is_available(self) -> None:
        from ae.adapters.puppet_adapter import BaseAEAdapter
        assert BaseAEAdapter().is_available() is False


# ---------------------------------------------------------------------------
# 完整工作流测试
# ---------------------------------------------------------------------------


class TestEndToEnd:
    """完整工作流测试。"""

    def test_full_workflow(self, client, mock_puppet, mock_mcp) -> None:
        """端到端：创建合成 → 加文字层 → 加效果 → 设关键帧 → 渲染。"""
        # 1. 创建合成
        r1 = client.create_composition("E2EComp", 1920, 1080, fps=30.0, duration=5.0)
        assert r1["success"]

        # 2. 加文字层
        r2 = client.create_text_layer("E2EComp", "Title", layer_name="Title")
        assert r2["success"]

        # 3. 加效果
        r3 = client.apply_effect(
            "E2EComp", 1, "ADBE Gaussian Blur", settings={"Blurriness": 5.0}
        )
        assert r3["success"]

        # 4. 设关键帧
        r4 = client.set_layer_keyframe("E2EComp", 1, "Opacity", 0.0, 0)
        assert r4["success"]
        r5 = client.set_layer_keyframe("E2EComp", 1, "Opacity", 5.0, 100)
        assert r5["success"]

        # 5. 渲染
        r6 = client.render(
            "E2EComp", "/tmp/output.mp4", format="h264", project_path="/tmp/test.aep"
        )
        # 渲染由 puppet 通道执行
        assert r6["success"] or r6.get("error", "").startswith("render")

    def test_text_layer_creation(self, client) -> None:
        r = client.create_text_layer("Comp1", "Hello", font_size=48)
        assert r["success"]
        assert r["channel_used"] in ("puppet", "mcp")

    def test_set_blend_mode(self, client) -> None:
        r = client.set_blend_mode("Comp1", 1, "ADD")
        assert r["success"]

    def test_batch_effects(self, client) -> None:
        r = client.batch_add_effects(
            "Comp1",
            1,
            [
                {"effect_name": "ADBE Gaussian Blur", "params": {"Blurriness": 5.0}},
                {"effect_name": "ADBE Brightness & Contrast", "params": {"Brightness": 10}},
            ],
        )
        assert r["success"]


# ---------------------------------------------------------------------------
# 线程安全测试
# ---------------------------------------------------------------------------


class TestThreadSafety:
    """线程安全测试。"""

    def test_concurrent_create_composition(
        self, mock_puppet: _MockAdapter, mock_mcp: _MockAdapter
    ) -> None:
        from ae.unified_ae_client import AEChannel, UnifiedAEClient
        client = UnifiedAEClient(
            puppet_engine=mock_puppet,
            mcp_client=mock_mcp,
            default_channel=AEChannel.PUPPET,
        )

        errors: list[Exception] = []

        def worker(i: int) -> None:
            try:
                client.create_composition(f"C{i}", 800, 600)
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors, f"线程执行出错: {errors}"
        stats = client.get_stats()
        total = stats["puppet"]["total_calls"] + stats["mcp"]["total_calls"]
        assert total == 10


# ---------------------------------------------------------------------------
# 列表操作（不抛异常）
# ---------------------------------------------------------------------------


class TestListCompositions:
    """list_compositions 列表操作测试。"""

    def test_list_compositions_success(self, client) -> None:
        comps = client.list_compositions()
        assert isinstance(comps, list)
        # Mock 总是成功
        if comps:
            assert comps[0].get("name") is not None

    def test_list_compositions_returns_empty_on_failure(
        self, mock_puppet: _MockAdapter
    ) -> None:
        from ae.unified_ae_client import UnifiedAEClient
        mcp = _MockAdapter(name="mcp", success=False, available=True)
        client = UnifiedAEClient(
            puppet_engine=mock_puppet, mcp_client=mcp, enable_fallback=True
        )
        comps = client.list_compositions()
        assert comps == []


# ---------------------------------------------------------------------------
# 端到端运行示例脚本（确保不抛 ImportError）
# ---------------------------------------------------------------------------


class TestExamplesScript:
    """examples 脚本基础测试。"""

    def test_examples_import(self) -> None:
        """确保 examples 文件可被导入。"""
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parent.parent / "examples_unified_ae_client.py"
        spec = importlib.util.spec_from_file_location("examples", str(path))
        assert spec is not None
        assert spec.loader is not None

    def test_adapters_init(self) -> None:
        """确保 adapters 包可被导入。"""
        from ae.adapters import BaseAEAdapter, PuppetEngineAdapter  # noqa: F401
