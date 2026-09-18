#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_opensource_adapters.py — 开源项目适配器单元测试
=====================================================

覆盖所有新增适配器:
  - AdobeMCPAdapter (P0)
  - MediaCrawlerAdapter (P1)
  - BlenderProcAdapter (P1)
  - FirecrawlAdapter (P1)
  - ComfyUIClient (P1)
  - NexrenderIntegration (P1)
  - IntegrationRegistry (统一注册)

测试原则:
  - 所有测试在无外部服务时也能通过 (simulate/degraded 模式)
  - fail-closed: 外部依赖不可用时优雅降级
  - 每个适配器至少验证: 实例化 / check_available / list_operations / execute
"""

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# 确保项目根目录在 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


class TestAdobeMCPAdapter(unittest.TestCase):
    """adobe-mcp 适配器测试"""

    def test_import(self):
        from integrations.adobe_mcp_adapter import AdobeMCPAdapter
        self.assertIsNotNone(AdobeMCPAdapter)

    def test_instantiate(self):
        from integrations.adobe_mcp_adapter import AdobeMCPAdapter
        adapter = AdobeMCPAdapter()
        self.assertIsNotNone(adapter)

    def test_check_available(self):
        from integrations.adobe_mcp_adapter import AdobeMCPAdapter
        adapter = AdobeMCPAdapter()
        result = adapter.check_available()
        self.assertIsInstance(result, bool)

    def test_list_operations(self):
        from integrations.adobe_mcp_adapter import AdobeMCPAdapter
        adapter = AdobeMCPAdapter()
        ops = adapter.list_operations()
        self.assertIsInstance(ops, list)
        self.assertGreater(len(ops), 0)
        self.assertIn("ae_new_composition", ops)
        self.assertIn("ps_new_document", ops)

    def test_operations_count(self):
        from integrations.adobe_mcp_adapter import AdobeMCPAdapter
        adapter = AdobeMCPAdapter()
        ops = adapter.list_operations()
        self.assertGreaterEqual(len(ops), 40)  # 至少 40 个操作

    def test_supported_operations_structure(self):
        from integrations.adobe_mcp_adapter import AdobeMCPAdapter
        adapter = AdobeMCPAdapter()
        for op_name, op_info in adapter.SUPPORTED_OPERATIONS.items():
            self.assertIn("app", op_info, f"Operation {op_name} missing 'app'")
            self.assertIn("desc", op_info, f"Operation {op_name} missing 'desc'")

    def test_execute_unknown_operation(self):
        from integrations.adobe_mcp_adapter import AdobeMCPAdapter
        adapter = AdobeMCPAdapter()
        result = adapter.execute("nonexistent_op")
        self.assertEqual(result.status, "failed")

    def test_quick_test(self):
        from integrations.adobe_mcp_adapter import quick_test
        result = quick_test()
        self.assertIn("available", result)
        self.assertIn("operations_count", result)
        self.assertGreater(result["operations_count"], 0)


class TestMediaCrawlerAdapter(unittest.TestCase):
    """MediaCrawler 适配器测试"""

    def test_import(self):
        from integrations.media_crawler_adapter import MediaCrawlerAdapter
        self.assertIsNotNone(MediaCrawlerAdapter)

    def test_instantiate(self):
        from integrations.media_crawler_adapter import MediaCrawlerAdapter
        adapter = MediaCrawlerAdapter()
        self.assertIsNotNone(adapter)

    def test_list_operations(self):
        from integrations.media_crawler_adapter import MediaCrawlerAdapter
        adapter = MediaCrawlerAdapter()
        ops = adapter.list_operations()
        self.assertEqual(len(ops), 11)
        self.assertIn("xhs_search", ops)
        self.assertIn("douyin_search", ops)
        self.assertIn("bilibili_search", ops)

    def test_list_platforms(self):
        from integrations.media_crawler_adapter import MediaCrawlerAdapter
        adapter = MediaCrawlerAdapter()
        platforms = adapter.list_platforms()
        self.assertEqual(len(platforms), 7)
        self.assertIn("xhs", platforms)
        self.assertIn("douyin", platforms)

    def test_execute_unknown(self):
        from integrations.media_crawler_adapter import MediaCrawlerAdapter
        adapter = MediaCrawlerAdapter()
        result = adapter.execute("nonexistent_op")
        self.assertEqual(result.status, "failed")

    def test_crawl_result_structure(self):
        from integrations.media_crawler_adapter import CrawlResult
        result = CrawlResult(platform="xhs", keyword="test")
        self.assertEqual(result.platform, "xhs")
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.items, [])


class TestBlenderProcAdapter(unittest.TestCase):
    """BlenderProc 适配器测试"""

    def test_import(self):
        from integrations.blender_proc_adapter import BlenderProcAdapter
        self.assertIsNotNone(BlenderProcAdapter)

    def test_instantiate(self):
        from integrations.blender_proc_adapter import BlenderProcAdapter
        adapter = BlenderProcAdapter()
        self.assertIsNotNone(adapter)

    def test_list_operations(self):
        from integrations.blender_proc_adapter import BlenderProcAdapter
        adapter = BlenderProcAdapter()
        ops = adapter.list_operations()
        self.assertEqual(len(ops), 8)
        self.assertIn("generate_indoor", ops)
        self.assertIn("render_depth", ops)

    def test_execute_unknown(self):
        from integrations.blender_proc_adapter import BlenderProcAdapter
        adapter = BlenderProcAdapter()
        result = adapter.execute("nonexistent_op")
        self.assertEqual(result.status, "failed")

    def test_scene_gen_result_structure(self):
        from integrations.blender_proc_adapter import SceneGenResult
        result = SceneGenResult(scene_type="indoor")
        self.assertEqual(result.scene_type, "indoor")
        self.assertEqual(result.status, "pending")
        self.assertEqual(result.output_files, [])


class TestFirecrawlAdapter(unittest.TestCase):
    """Firecrawl 适配器测试"""

    def test_import(self):
        from integrations.firecrawl_adapter import FirecrawlAdapter
        self.assertIsNotNone(FirecrawlAdapter)

    def test_instantiate(self):
        from integrations.firecrawl_adapter import FirecrawlAdapter
        adapter = FirecrawlAdapter()
        self.assertIsNotNone(adapter)

    def test_list_operations(self):
        from integrations.firecrawl_adapter import FirecrawlAdapter
        adapter = FirecrawlAdapter()
        ops = adapter.list_operations()
        self.assertEqual(len(ops), 7)
        self.assertIn("scrape", ops)
        self.assertIn("search", ops)
        self.assertIn("crawl", ops)

    def test_check_available_without_key(self):
        from integrations.firecrawl_adapter import FirecrawlAdapter
        adapter = FirecrawlAdapter()
        # 无 API key 时应该不可用（fail-closed）
        available = adapter.check_available()
        self.assertFalse(available)

    def test_scrape_without_client(self):
        from integrations.firecrawl_adapter import FirecrawlAdapter
        adapter = FirecrawlAdapter()
        result = adapter.scrape("https://example.com")
        self.assertEqual(result.status, "degraded")

    def test_search_without_client(self):
        from integrations.firecrawl_adapter import FirecrawlAdapter
        adapter = FirecrawlAdapter()
        result = adapter.search("test query")
        self.assertEqual(result.status, "degraded")

    def test_execute_unknown(self):
        from integrations.firecrawl_adapter import FirecrawlAdapter
        adapter = FirecrawlAdapter()
        result = adapter.execute("nonexistent_op")
        self.assertEqual(result["status"], "failed")

    def test_cache_roundtrip(self):
        from integrations.firecrawl_adapter import FirecrawlAdapter
        adapter = FirecrawlAdapter()
        test_data = {"markdown": "# Test", "metadata": {"title": "Test"}}
        adapter._cache_result("test_url", test_data)
        cached = adapter._get_cached("test_url")
        self.assertIsNotNone(cached)
        self.assertEqual(cached["markdown"], "# Test")


class TestComfyUIClient(unittest.TestCase):
    """ComfyUI 客户端测试"""

    def test_import(self):
        from integrations.comfyui_mcp_server import ComfyUIClient
        self.assertIsNotNone(ComfyUIClient)

    def test_instantiate(self):
        from integrations.comfyui_mcp_server import ComfyUIClient
        client = ComfyUIClient()
        self.assertIsNotNone(client)

    def test_is_available_returns_bool(self):
        from integrations.comfyui_mcp_server import ComfyUIClient
        client = ComfyUIClient()
        result = client.is_available()
        self.assertIsInstance(result, bool)


class TestNexrenderIntegration(unittest.TestCase):
    """nexrender 集成测试"""

    def test_import(self):
        from integrations.nexrender import NexrenderIntegration
        self.assertIsNotNone(NexrenderIntegration)


class TestIntegrationRegistry(unittest.TestCase):
    """统一集成注册中心测试"""

    def test_import(self):
        from integrations.integration_registry import IntegrationRegistry
        self.assertIsNotNone(IntegrationRegistry)

    def test_discover_all(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        result = registry.discover_all()
        self.assertIsInstance(result, dict)
        self.assertGreater(len(result), 0)

    def test_known_integrations_count(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        self.assertGreaterEqual(len(registry.KNOWN_INTEGRATIONS), 12)

    def test_health_check(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        report = registry.health_check()
        self.assertIsInstance(report, dict)
        for name, info in report.items():
            self.assertIn("status", info)
            self.assertIn("layer", info)
            self.assertIn("priority", info)

    def test_summary(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        summary = registry.summary()
        self.assertIn("total", summary)
        self.assertIn("available", summary)
        self.assertIn("total_operations", summary)
        self.assertGreaterEqual(summary["total"], 10)

    def test_list_by_layer(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        registry.discover_all()
        by_layer = registry.list_by_layer()
        self.assertIn(1, by_layer)  # Layer 1 必须有集成
        self.assertGreater(len(by_layer[1]), 0)

    def test_get_adobe_mcp(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        adapter = registry.get("adobe_mcp")
        self.assertIsNotNone(adapter)

    def test_get_nonexistent(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        adapter = registry.get("nonexistent_integration")
        self.assertIsNone(adapter)

    def test_p0_integrations_present(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        registry.discover_all()
        by_priority = registry.list_by_priority()
        self.assertIn("P0", by_priority)
        self.assertIn("adobe_mcp", by_priority["P0"])
        self.assertIn("qwen_mm", by_priority["P0"])

    def test_p1_integrations_present(self):
        from integrations.integration_registry import IntegrationRegistry
        registry = IntegrationRegistry()
        registry.discover_all()
        by_priority = registry.list_by_priority()
        self.assertIn("P1", by_priority)
        p1_names = by_priority["P1"]
        self.assertIn("comfyui", p1_names)
        self.assertIn("media_crawler", p1_names)
        self.assertIn("firecrawl", p1_names)


class TestLLMGatewayNewTaskTypes(unittest.TestCase):
    """llm_gateway.py 新增 TaskType 测试"""

    def test_new_task_types_exist(self):
        from core.llm_gateway import TaskType
        new_types = [
            "SOCIAL_MEDIA_CRAWL",
            "WEB_CONTEXT_FETCH",
            "SCENE_GENERATION_3D",
            "COMFYUI_WORKFLOW",
            "ADOBE_AUTOMATION",
            "RENDER_AUTOMATION",
        ]
        for name in new_types:
            self.assertTrue(hasattr(TaskType, name), f"TaskType.{name} missing")

    def test_task_provider_map_has_new_types(self):
        from core.llm_gateway import TASK_PROVIDER_MAP, TaskType
        for tt in [TaskType.SOCIAL_MEDIA_CRAWL, TaskType.WEB_CONTEXT_FETCH,
                    TaskType.SCENE_GENERATION_3D, TaskType.COMFYUI_WORKFLOW,
                    TaskType.ADOBE_AUTOMATION, TaskType.RENDER_AUTOMATION]:
            self.assertIn(tt, TASK_PROVIDER_MAP, f"{tt} not in TASK_PROVIDER_MAP")

    def test_task_tier_map_has_new_types(self):
        from core.llm_gateway import TASK_TIER_MAP, TaskType
        for tt in [TaskType.SOCIAL_MEDIA_CRAWL, TaskType.WEB_CONTEXT_FETCH,
                    TaskType.SCENE_GENERATION_3D, TaskType.COMFYUI_WORKFLOW,
                    TaskType.ADOBE_AUTOMATION, TaskType.RENDER_AUTOMATION]:
            self.assertIn(tt, TASK_TIER_MAP, f"{tt} not in TASK_TIER_MAP")


if __name__ == "__main__":
    unittest.main(verbosity=2)
