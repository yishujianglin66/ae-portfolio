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

from .adobe_bridge_adapter import (
    AdobeApp,
    AdobeBridgeAdapter,
    AppInfo,
    AppStatus,
    BatchResult,
)
from .au_bridge_client import AUBridgeClient
from .blender_ae_bridge import BlenderAEBridge
from .c4d_ae_bridge import C4DAEBridge
from .pipeline_orchestrator import PipelineOrchestrator
from .pr_bridge_client import PRBridgeClient
from .ps_bridge_client import PSBridgeClient
from .silhouette_ae_bridge import SilhouetteAEBridge
from .topaz_davinci_bridge import TopazDaVinciBridge


def __getattr__(name: str):
    """惰性导出 DEPRECATED 模块 (D-15): 不在导入期触发弃用警告。

    UnifiedBridgeBase 已无生产消费方, 仅保留 from bridges import
    UnifiedBridgeBase 的向后兼容 (访问时才触发警告)。
    """
    if name == "UnifiedBridgeBase":
        from .unified_bridge_base import UnifiedBridgeBase
        return UnifiedBridgeBase
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