"""UnifiedAEClient 使用示例。

演示 UnifiedAEClient 的 5+ 个核心使用场景：
1. 基础通道自动选择
2. 渲染任务（强制走 puppet 通道）
3. 原子脚本（强制走 MCP 通道）
4. 通道降级（主通道失败自动切换）
5. 通道统计与监控
6. 依赖注入（自定义适配器，便于测试）

运行：
    python ae/examples_unified_ae_client.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict

# 确保项目根目录在 Python 路径中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ae.adapters.puppet_adapter import BaseAEAdapter
from ae.unified_ae_client import (
    AEChannel,
    AEChannelStats,
    AllChannelsFailedError,
    ChannelSelector,
    UnifiedAEClient,
)

# ---------------------------------------------------------------------------
# 示例 1：基础通道自动选择
# ---------------------------------------------------------------------------


def example_1_basic_auto() -> None:
    """示例 1：基础用法 - 默认 AUTO 模式自动选择通道。"""
    print("=" * 70)
    print("示例 1：基础通道自动选择")
    print("=" * 70)

    client = UnifiedAEClient()

    print("通道可用性：")
    print(f"  - puppet: {client.is_puppet_available()}")
    print(f"  - mcp:    {client.is_mcp_available()}")

    print("\n尝试创建合成（自动选择通道）...")
    try:
        result = client.create_composition(
            name="Demo_Auto_Comp",
            width=1920,
            height=1080,
            fps=30.0,
            duration=5.0,
        )
        print(f"  结果: {result}")
    except AllChannelsFailedError as exc:
        print(f"  所有通道失败: {exc.message}")
    print()


# ---------------------------------------------------------------------------
# 示例 2：渲染任务（puppet 通道最优）
# ---------------------------------------------------------------------------


def example_2_render_via_puppet() -> None:
    """示例 2：渲染任务 - 默认走 puppet 通道。"""
    print("=" * 70)
    print("示例 2：渲染任务（puppet 通道，aerender CLI）")
    print("=" * 70)

    client = UnifiedAEClient()
    output_path = str(
        PROJECT_ROOT / "output" / "demo_render" / "demo_comp.mp4"
    )

    print(f"渲染输出: {output_path}")
    try:
        result = client.render(
            comp_name="Demo_Comp",
            output_path=output_path,
            format="h264",
            project_path=r"D:/AE-Work/projects/demo.aep",
        )
        print(f"  结果: {result}")
    except AllChannelsFailedError as exc:
        print(f"  渲染失败: {exc.message}")
    print()


# ---------------------------------------------------------------------------
# 示例 3：原子脚本（MCP 通道最优）
# ---------------------------------------------------------------------------


def example_3_atom_script_via_mcp() -> None:
    """示例 3：执行原子脚本 - 默认走 MCP 通道。"""
    print("=" * 70)
    print("示例 3：原子脚本（MCP 通道，AE 面板监听）")
    print("=" * 70)

    client = UnifiedAEClient()

    # 一个简单原子脚本：在当前合成中创建一个文字图层
    atom_script = """
{
    "type": "createTextLayer",
    "params": {
        "compName": "Demo_Comp",
        "text": "Hello from UnifiedAEClient!",
        "layerName": "Greeting",
        "fontSize": 64,
        "fillColor": [1, 1, 1]
    }
}
"""
    print("执行原子脚本（先 dry_run 验证）：")
    result = client.execute_atom_script(atom_script, dry_run=True)
    print(f"  预演结果: {result}")

    print("\n真正执行（需要 AE 启动 + 桥接就绪）：")
    try:
        result = client.execute_atom_script(atom_script, dry_run=False)
        print(f"  执行结果: {result}")
    except AllChannelsFailedError as exc:
        print(f"  MCP 通道失败: {exc.message}")
    print()


# ---------------------------------------------------------------------------
# 示例 4：通道降级
# ---------------------------------------------------------------------------


class _FailingAdapter(BaseAEAdapter):
    """模拟总失败的 puppet 适配器。"""

    name = "puppet"
    fail_message = "puppet 引擎模拟失败"

    def is_available(self) -> bool:
        return True

    def create_composition(self, **kwargs: Any) -> dict[str, Any]:
        return {"success": False, "error": self.fail_message, "channel": self.name}


class _SucceedingAdapter(BaseAEAdapter):
    """模拟成功的 MCP 适配器。"""

    name = "mcp"

    def is_available(self) -> bool:
        return True

    def create_composition(self, **kwargs: Any) -> dict[str, Any]:
        return {
            "success": True,
            "channel": self.name,
            "compName": kwargs.get("name", "Unknown"),
            "width": kwargs.get("width"),
            "height": kwargs.get("height"),
            "via": "fallback",
        }


def example_4_fallback() -> None:
    """示例 4：主通道失败时自动降级到备用通道。"""
    print("=" * 70)
    print("示例 4：通道自动降级")
    print("=" * 70)

    # puppet 总失败，MCP 总成功
    puppet = _FailingAdapter()
    mcp = _SucceedingAdapter()
    client = UnifiedAEClient(
        puppet_engine=puppet,
        mcp_client=mcp,
        default_channel=AEChannel.PUPPET,  # 强制 puppet 优先
        enable_fallback=True,
    )

    print("puppet 通道模拟失败，验证降级到 MCP：")
    result = client.create_composition(
        name="Fallback_Demo",
        width=1280,
        height=720,
        fps=24.0,
        duration=3.0,
    )
    print(f"  结果: {result}")
    print(f"  实际使用通道: {result.get('channel_used')}")
    print(f"  期望: 'mcp'  → 实际: '{result.get('channel_used')}'")
    assert result.get("success"), "降级应成功"
    assert result.get("channel_used") == "mcp", "应使用 MCP 通道"
    print("  ✓ 降级成功")
    print()


# ---------------------------------------------------------------------------
# 示例 5：统计监控
# ---------------------------------------------------------------------------


def example_5_stats() -> None:
    """示例 5：调用统计与监控。"""
    print("=" * 70)
    print("示例 5：通道调用统计")
    print("=" * 70)

    # 注入可控的两个适配器
    puppet = _SucceedingAdapter()  # 借用同名方法
    puppet.name = "puppet"
    mcp = _SucceedingAdapter()
    mcp.name = "mcp"
    client = UnifiedAEClient(puppet_engine=puppet, mcp_client=mcp)

    print("执行 5 次混合操作...")
    for i in range(3):
        client.create_composition(f"Comp_{i}", 1920, 1080)
    for i in range(2):
        client.list_compositions()

    stats = client.get_stats()
    print("\n当前统计：")
    for ch, info in stats.items():
        if isinstance(info, dict) and "total_calls" in info:
            print(f"  {ch}: {info}")
    print()


# ---------------------------------------------------------------------------
# 示例 6：依赖注入（测试场景）
# ---------------------------------------------------------------------------


def example_6_dependency_injection() -> None:
    """示例 6：通过依赖注入使用自定义适配器（典型测试场景）。"""
    print("=" * 70)
    print("示例 6：依赖注入（Mock 适配器）")
    print("=" * 70)

    call_log: list = []

    class _LoggingAdapter(BaseAEAdapter):
        name = "mock"

        def is_available(self) -> bool:
            return True

        def create_composition(self, **kwargs: Any) -> dict[str, Any]:
            call_log.append(("create_composition", kwargs))
            return {"success": True, "channel": "mock", "mock": True}

    mock_adapter = _LoggingAdapter()
    client = UnifiedAEClient(
        puppet_engine=mock_adapter,
        mcp_client=mock_adapter,
        default_channel=AEChannel.PUPPET,
    )

    result = client.create_composition("MockComp", 800, 600)
    print(f"  结果: {result}")
    print(f"  调用日志: {call_log}")
    assert result.get("success")
    assert result.get("mock") is True
    print("  ✓ 依赖注入生效")
    print()


# ---------------------------------------------------------------------------
# 示例 7：ChannelSelector 直接使用
# ---------------------------------------------------------------------------


def example_7_channel_selector() -> None:
    """示例 7：直接使用 ChannelSelector 决定路由。"""
    print("=" * 70)
    print("示例 7：ChannelSelector 路由选择")
    print("=" * 70)

    # 模拟一个 puppet 不健康、MCP 健康的场景
    stats: dict[AEChannel, AEChannelStats] = {
        AEChannel.PUPPET: AEChannelStats(
            total_calls=5,
            success_count=1,
            failure_count=4,
            total_latency_ms=200.0,
            consecutive_failures=4,
        ),
        AEChannel.MCP: AEChannelStats(
            total_calls=3,
            success_count=3,
            failure_count=0,
            total_latency_ms=150.0,
        ),
    }

    cases = [
        ("render", {}),
        ("execute_atom_script", {}),
        ("set_layer_expression", {}),
        ("create_text_layer", {}),
        ("list_compositions", {}),
    ]
    for op_name, ctx in cases:
        ch = ChannelSelector.select(op_name, ctx, stats)
        print(f"  {op_name:30s} → {ch.value}")
    print()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------


def main() -> None:
    print("\n" + "=" * 70)
    print("  UnifiedAEClient 使用示例")
    print("=" * 70 + "\n")

    example_1_basic_auto()
    example_2_render_via_puppet()
    example_3_atom_script_via_mcp()
    example_4_fallback()
    example_5_stats()
    example_6_dependency_injection()
    example_7_channel_selector()

    print("=" * 70)
    print("  所有示例运行完成")
    print("=" * 70)


if __name__ == "__main__":
    main()
