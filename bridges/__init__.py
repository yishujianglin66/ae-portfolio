"""
Adobe Bridge Package
====================

统一 Adobe 应用 Bridge 通信框架，支持 AE、PR、PS、AU。

核心组件：
- AdobeBridgeAdapter: 统一适配器，提供对所有 Adobe 应用的统一访问
- UnifiedBridgeBase: 统一 Bridge 基类
- PRBridgeClient: Premiere Pro Bridge 客户端
- PSBridgeClient: Photoshop Bridge 客户端
- AUBridgeClient: Audition Bridge 客户端

跨引擎桥接器 (P2 Phase):
- BlenderAEBridge: Blender → AE 3D 合成链路
- TopazDaVinciBridge: Topaz AI 增强 → DaVinci 调色链路
- SilhouetteAEBridge: Silhouette 抠像 → AE Mask 链路
- C4DAEBridge: Cinema 4D → AE 3D 场景链路
- PipelineOrchestrator: 跨引擎 Pipeline 编排器

Usage:
    from bridges import AdobeBridgeAdapter
    from bridges import PipelineOrchestrator

    adapter = AdobeBridgeAdapter()
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run_pipeline("full_3d_pipeline", config)
"""

from .au_bridge_client import AUBridgeClient
from .blender_ae_bridge import BlenderAEBridge
from .c4d_ae_bridge import C4DAEBridge
from .pipeline_orchestrator import PipelineOrchestrator
from .pr_bridge_client import PRBridgeClient
from .ps_bridge_client import PSBridgeClient
from .silhouette_ae_bridge import SilhouetteAEBridge
from .topaz_davinci_bridge import TopazDaVinciBridge


_DEPRECATED_EXPORTS = {
    "UnifiedBridgeBase": ".unified_bridge_base",
    # adobe_bridge_adapter 于 2026-09-19 从饿汉式导入改为惰性 (原写法让
    # `import bridges` 就触发 DeprecationWarning, 与 D-15 的既定约定不符)。
    # 注意: 被弃用的是**这个包装类**(无生产消费方), 不是 .ae-mcp-bridge 协议
    # 本身 —— 该协议仍由 ai/ae_render_channel.py 承载全部自动化 AE 渲染。
    "AdobeBridgeAdapter": ".adobe_bridge_adapter",
    "AdobeApp": ".adobe_bridge_adapter",
    "AppInfo": ".adobe_bridge_adapter",
    "AppStatus": ".adobe_bridge_adapter",
    "BatchResult": ".adobe_bridge_adapter",
}


def __getattr__(name: str):
    """惰性导出 DEPRECATED 模块 (D-15): 不在导入期触发弃用警告。

    访问时才 import, 因而弃用警告也只在真正使用时出现; `__all__` 里的名字
    仍可 getattr 到非 None 值 (tests/test_bridges_pipeline_gaps.py 的契约)。
    """
    mod = _DEPRECATED_EXPORTS.get(name)
    if mod:
        import importlib
        return getattr(importlib.import_module(mod, __package__), name)
    raise AttributeError(f"module 'bridges' has no attribute {name!r}")

__all__ = [
    "AdobeBridgeAdapter",
    "AdobeApp",
    "AppStatus",
    "AppInfo",
    "BatchResult",
    "UnifiedBridgeBase",
    "PRBridgeClient",
    "PSBridgeClient",
    "AUBridgeClient",
    "BlenderAEBridge",
    "TopazDaVinciBridge",
    "SilhouetteAEBridge",
    "C4DAEBridge",
    "PipelineOrchestrator",
]