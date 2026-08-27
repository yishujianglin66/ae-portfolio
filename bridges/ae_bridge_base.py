"""DEPRECATED - 兼容转发层：``bridges.ae_bridge_base`` → ``ae.ae_bridge_base``。

.. deprecated::
    本模块属于自研 .ae-mcp-bridge 文件轮询协议栈，已整体弃用。
    权威实现已迁移至 ``ae.ae_bridge_base``，本模块仅保留旧导入路径兼容。
    AE MCP 已转向开源基线（after-effects-mcp + 原版 mcp-bridge-auto.jsx）。
"""
import warnings as _warnings

_warnings.warn(
    "bridges.ae_bridge_base 已弃用：自研 .ae-mcp-bridge 协议已弃用，"
    "请改用 ae.ae_bridge_base。AE MCP 已转向开源 after-effects-mcp 基线。",
    DeprecationWarning,
    stacklevel=2,
)

from ae.ae_bridge_base import (  # noqa: F401,E402
    AEBridgeClient,
    _BridgeClient,
    _MiddlewarePipeline,
    _try_import_core,
)

__all__ = [
    "AEBridgeClient",
    "_BridgeClient",
    "_MiddlewarePipeline",
    "_try_import_core",
]
