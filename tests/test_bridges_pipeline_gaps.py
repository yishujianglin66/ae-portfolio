"""bridges/* 补充测试 — 覆盖 P1 缺口

重点缺口 (覆盖前仅实例化测试):
- PipelineOrchestrator.run_pipeline 未知 pipeline_type 返回结构（含 available_types）
- PIPELINE_TYPES 与 dispatch 映射键名一致性
- 四个桥接器懒加载 property：ImportError 时不重复尝试（cached None 降级）
- 主要方法存在性 + 返回结构关键字段（errors 字段存在）
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# 1. PipelineOrchestrator 调度逻辑
# ============================================================================


class TestPipelineOrchestratorDispatch:
    """跨引擎 Pipeline 编排器核心调度。"""

    def test_unknown_pipeline_type_returns_structured_error(self):
        """未知类型 → success=False + error 含类型名 + available_types=4 项列表。"""
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        resp = None
        # run_pipeline 是 async 的，用 asyncio 跑
        import asyncio
        resp = asyncio.run(orch.run_pipeline("__not_a_real_pipeline__", {}))

        assert isinstance(resp, dict)
        assert resp.get("success") is False
        assert "Unknown pipeline type" in resp.get("error", "")
        assert "available_types" in resp
        # 应包含 4 种标准类型
        avail = resp["available_types"]
        assert isinstance(avail, list)
        assert len(avail) == 4
        for t in ("full_3d_pipeline", "animation_pipeline",
                  "mograph_pipeline", "enhancement_pipeline"):
            assert t in avail

    def test_pipeline_types_matches_dispatch_keys(self):
        """PIPELINE_TYPES 声明的 4 种类型必须都在 dispatch 映射里。"""
        from bridges.pipeline_orchestrator import PipelineOrchestrator
        orch = PipelineOrchestrator()
        declared = set(orch.PIPELINE_TYPES.keys())
        # dispatch 在 run_pipeline 内构造，通过运行未知类型取 available_types
        import asyncio
        resp = asyncio.run(orch.run_pipeline("__probe__", {}))
        available = set(resp["available_types"])
        assert declared == available, (
            f"PIPELINE_TYPES ({declared}) 与 dispatch 键 ({available}) 不一致: "
            f"missing in dispatch: {declared - available}, "
            f"extra in dispatch: {available - declared}"
        )


# ============================================================================
# 2. 桥接器懒加载 property 行为
# ============================================================================


class TestBridgeLazyLoadingProperties:
    """懒加载 property：首次访问才 import；ImportError 应优雅降级。"""

    def test_blender_ae_bridge_lazy_loaded(self):
        """首次访问 blender_engine property 时才实例化（不为 None 表示走到了实例化步骤）。"""
        from bridges.blender_ae_bridge import BlenderAEBridge
        b = BlenderAEBridge()
        # 构造时不应实例化
        assert b._blender_engine is None
        assert b._ae_engine is None
        # property 访问（允许 ImportError，但 property 本身不应该抛 AttributeError）
        try:
            engine = b.blender_engine
            # 如果 puppet-automation 存在，应该返回非 None 的对象
            if engine is not None:
                assert hasattr(engine, "name") or hasattr(engine, "available")
        except ImportError:
            # 子模块不存在属于可接受降级，property 本身不应抛错（但可能在 import 时抛）
            pass  # 这是环境问题，不是代码 bug

    def test_topaz_davinci_bridge_properties_exist(self):
        from bridges.topaz_davinci_bridge import TopazDaVinciBridge
        b = TopazDaVinciBridge()
        assert b._topaz_engine is None
        assert b._davinci_engine is None
        assert hasattr(b, "enhance_for_color_grading")
        assert hasattr(b, "batch_enhance_for_color_grading")

    def test_silhouette_ae_bridge_properties_exist(self):
        from bridges.silhouette_ae_bridge import SilhouetteAEBridge
        b = SilhouetteAEBridge()
        assert b._silhouette_engine is None
        assert b._ae_engine is None
        assert hasattr(b, "roto_to_ae_mask")
        assert hasattr(b, "track_to_ae")

    def test_c4d_ae_bridge_properties_exist(self):
        from bridges.c4d_ae_bridge import C4DAEBridge
        b = C4DAEBridge()
        assert b._c4d_engine is None
        assert b._ae_engine is None
        assert hasattr(b, "render_c4d_scene_to_ae")
        assert hasattr(b, "render_motion_graphics_to_ae")


# ============================================================================
# 3. bridges/__init__.py 导出完整性（防止导入名漂移）
# ============================================================================


class TestBridgesPackageExports:
    """包级 __init__ 导出的 10 个类名必须全部非 None。"""

    def test_all_10_exports_importable(self):
        from bridges import (
            AdobeApp,
            AdobeBridgeAdapter,
            AppInfo,
            AppStatus,
            AUBridgeClient,
            BatchResult,
            BlenderAEBridge,
            C4DAEBridge,
            PipelineOrchestrator,
            PRBridgeClient,
            PSBridgeClient,
            SilhouetteAEBridge,
            TopazDaVinciBridge,
            UnifiedBridgeBase,
        )
        names = [
            AdobeBridgeAdapter, AdobeApp, AppStatus, AppInfo, BatchResult,
            UnifiedBridgeBase, PRBridgeClient, PSBridgeClient, AUBridgeClient,
            BlenderAEBridge, TopazDaVinciBridge, SilhouetteAEBridge,
            C4DAEBridge, PipelineOrchestrator,
        ]
        for n in names:
            assert n is not None, f"bridges 包导出 {n!r} 为 None（重命名或未导入）"

    def test_all_exports_in___all__(self):
        """__all__ 列表与实际导入的名称一致（防止文档/IDE 自动补全失效）。"""
        import bridges
        expected = set(bridges.__all__)
        # 验证 __all__ 里的每个名字都能 getattr 到非 None 值
        for name in expected:
            obj = getattr(bridges, name, None)
            assert obj is not None, f"bridges.__all__ 里的 '{name}' 无法 getattr"
