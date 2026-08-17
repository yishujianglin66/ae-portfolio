"""ae.adapters - Adobe 应用操作通道适配器包。

将 puppet-automation 引擎与 MCP 客户端统一封装为同一接口，
让上层（UnifiedAEClient）以一致的方式调用两套通道。

子模块：
- puppet_adapter：适配 puppet-automation 的 AEEngine。
- mcp_adapter：适配 AEMCPClient（占位实现，与现有 AEMCPClient 同语义）。
- pr_adapter：适配 Premiere Pro MCP 客户端。
- ps_adapter：适配 Photoshop MCP 客户端。
- au_adapter：适配 Audition MCP 客户端。

依赖注入：
适配器通过可选对象注入，单元测试时可注入 Mock。
"""
from .puppet_adapter import PuppetEngineAdapter, BaseAEAdapter
from .mcp_adapter import MCPClientAdapter
from .pr_adapter import PRAdapter, BasePRAdapter
from .ps_adapter import BasePSAdapter, MCPClientPSAdapter, PuppetEnginePSAdapter, PSAdapterFactory
from .au_adapter import BaseAUAdapter, MCPClientAUAdapter, PuppetEngineAUAdapter, AUAdapterFactory

__all__ = [
    "BaseAEAdapter",
    "PuppetEngineAdapter",
    "MCPClientAdapter",
    "BasePRAdapter",
    "PRAdapter",
    "BasePSAdapter",
    "MCPClientPSAdapter",
    "PuppetEnginePSAdapter",
    "PSAdapterFactory",
    "BaseAUAdapter",
    "MCPClientAUAdapter",
    "PuppetEngineAUAdapter",
    "AUAdapterFactory",
]
