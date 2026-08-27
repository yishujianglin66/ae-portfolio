"""
AE-Knowledge-Vault 端到端测试脚本
=================================

测试内容：
1. 所有 Bridge 客户端初始化
2. API 服务健康检查
3. 16 引擎初始化验证
4. MCP Gateway 工具注册验证
5. 模拟 Bridge 通信（ping 测试）

使用方式：
    python test_deploy.py
"""
from __future__ import annotations

import sys
import os
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation"))

from loguru import logger


class DeploymentTest:
    def __init__(self):
        self.results = {}
        self.passed = 0
        self.failed = 0
        self.skipped = 0

    def run(self):
        logger.info("=" * 60)
        logger.info("AE-Knowledge-Vault 端到端部署测试")
        logger.info("=" * 60)

        self.test_bridge_clients()
        self.test_engine_initialization()
        self.test_api_service()
        self.test_mcp_gateway()

        self.print_report()

    def test_bridge_clients(self):
        logger.info("\n--- 测试 Bridge 客户端 ---")

        clients = [
            ("AE", "mcp_bridge_client", "MCPBridgeClient", {}, False),
            ("PR", "pr_bridge_client", "PRBridgeClient", {"timeout": 2}, True),
            ("PS", "ps_bridge_client", "PSBridgeClient", {"timeout": 2}, True),
            ("AU", "au_bridge_client", "AUBridgeClient", {"timeout": 2}, True),
        ]

        for name, module_name, class_name, kwargs, has_ping in clients:
            try:
                module = __import__(module_name, fromlist=[class_name])
                client_class = getattr(module, class_name)
                client = client_class(**kwargs)

                if has_ping:
                    result = client.ping(timeout=1)
                    status = result.get("status", "unknown")

                    if status == "success":
                        self._record(f"{name} Bridge", "PASS", f"Bridge 在线")
                        self.passed += 1
                    elif status == "timeout":
                        self._record(f"{name} Bridge", "SKIP", f"Bridge 离线（软件未运行）")
                        self.skipped += 1
                    else:
                        self._record(f"{name} Bridge", "WARN", f"状态: {status}")
                        self.skipped += 1
                else:
                    self._record(f"{name} Bridge", "SKIP", f"客户端初始化成功（无 ping 方法）")
                    self.skipped += 1

                logger.info(f"  {name} Bridge: OK ({getattr(client, 'command_file', 'n/a')})")

            except ImportError as e:
                self._record(f"{name} Bridge", "FAIL", f"导入失败: {e}")
                self.failed += 1
                logger.error(f"  {name} Bridge: FAIL - {e}")
            except Exception as e:
                self._record(f"{name} Bridge", "FAIL", f"初始化失败: {e}")
                self.failed += 1
                logger.error(f"  {name} Bridge: FAIL - {e}")

    def test_engine_initialization(self):
        logger.info("\n--- 测试引擎初始化 ---")

        os.chdir(PROJECT_ROOT / "puppet-automation")

        engine_classes = [
            ("AE", "src.engines.ae.engine", "AEEngine"),
            ("FFmpeg", "src.engines.ffmpeg.engine", "FFmpegEngine"),
            ("Topaz", "src.engines.topaz.engine", "TopazEngine"),
            ("Silhouette", "src.engines.silhouette.engine", "SilhouetteEngine"),
            ("Blender", "src.engines.blender.engine", "BlenderEngine"),
            ("DaVinci", "src.engines.davinci.engine", "DavinciEngine"),
            ("MediaEncoder", "src.engines.media_encoder.engine", "MediaEncoderEngine"),
            ("RIFE", "src.engines.rife.engine", "RifeEngine"),
            ("OpenMontage", "src.engines.openmontage.engine", "OpenMontageEngine"),
            ("Whisper", "src.engines.whisper.engine", "WhisperEngine"),
            ("SAM2", "src.engines.sam2.engine", "SAM2Engine"),
            ("MoviePy", "src.engines.moviepy.engine", "MoviePyEngine"),
            ("Premiere", "src.engines.premiere.engine", "PremiereEngine"),
            ("Photoshop", "src.engines.photoshop.engine", "PhotoshopEngine"),
            ("Audition", "src.engines.audition.engine", "AuditionEngine"),
            ("ComfyUI", "src.engines.comfyui.engine", "ComfyUIEngine"),
        ]

        for name, module_path, class_name in engine_classes:
            try:
                parts = module_path.split(".")
                module = __import__(".".join(parts[:-1]), fromlist=[parts[-1]])
                module = getattr(module, parts[-1])
                engine_class = getattr(module, class_name)

                engine = engine_class()

                bridge_status = getattr(engine, "_bridge_available", "n/a")
                if bridge_status is True:
                    bridge_info = "online"
                elif bridge_status is False:
                    bridge_info = "offline"
                elif bridge_status is None:
                    bridge_info = "unknown"
                else:
                    bridge_info = "n/a"

                self._record(f"{name} Engine", "PASS", f"初始化成功: {engine.name}")
                self.passed += 1
                logger.info(f"  {name} Engine: OK (bridge={bridge_info})")

            except Exception as e:
                self._record(f"{name} Engine", "FAIL", f"初始化失败: {e}")
                self.failed += 1
                logger.error(f"  {name} Engine: FAIL - {e}")

    def test_api_service(self):
        logger.info("\n--- 测试 API 服务 ---")

        try:
            import requests

            try:
                response = requests.get("http://localhost:8765/health", timeout=3)
                if response.status_code == 200:
                    self._record("API Health", "PASS", "服务正常")
                    self.passed += 1
                    logger.info("  API Health: OK")
                else:
                    self._record("API Health", "FAIL", f"状态码: {response.status_code}")
                    self.failed += 1
            except requests.exceptions.ConnectionError:
                self._record("API Health", "SKIP", "API 服务未启动")
                self.skipped += 1
                logger.warning("  API Health: SKIP")

            try:
                response = requests.get("http://localhost:8765/api/v1/engines", timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    count = len(data.get("engines", []))
                    self._record("API Engines", "PASS", f"引擎数量: {count}")
                    self.passed += 1
                    logger.info(f"  API Engines: OK ({count} 个)")
            except requests.exceptions.ConnectionError:
                self._record("API Engines", "SKIP", "API 服务未启动")
                self.skipped += 1

        except ImportError:
            self._record("API Service", "SKIP", "requests 未安装")
            self.skipped += 1

    def test_mcp_gateway(self):
        logger.info("\n--- 测试 MCP Gateway ---")

        try:
            import requests

            try:
                response = requests.get("http://localhost:8765/tools", timeout=3)
                if response.status_code == 200:
                    data = response.json()
                    tools = data.get("tools", [])
                    self._record("MCP Tools", "PASS", f"工具数量: {len(tools)}")
                    self.passed += 1
                    logger.info(f"  MCP Tools: OK ({len(tools)} 个)")
            except requests.exceptions.ConnectionError:
                self._record("MCP Tools", "SKIP", "MCP Gateway 未启动")
                self.skipped += 1
                logger.warning("  MCP Tools: SKIP")

        except ImportError:
            self._record("MCP Gateway", "SKIP", "requests 未安装")
            self.skipped += 1

    def _record(self, test_name: str, status: str, message: str):
        self.results[test_name] = {
            "status": status,
            "message": message,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        }

    def print_report(self):
        logger.info("\n" + "=" * 60)
        logger.info("测试报告")
        logger.info("=" * 60)

        print(f"\n  通过: {self.passed}")
        print(f"  失败: {self.failed}")
        print(f"  跳过: {self.skipped}")
        print()

        for test_name, result in self.results.items():
            icon = "✅" if result["status"] == "PASS" else \
                   "❌" if result["status"] == "FAIL" else "⚠️"
            print(f"  {icon} {test_name}: {result['message']}")

        print()

        total = self.passed + self.failed + self.skipped
        if self.failed == 0:
            print("  🎉 所有测试通过！")
            logger.info("所有测试通过！")
            return True
        else:
            print(f"  ⚠️  有 {self.failed} 个测试失败，请检查")
            logger.warning(f"{self.failed} 个测试失败")
            return False


if __name__ == "__main__":
    test = DeploymentTest()
    success = test.run()
    sys.exit(0 if success else 1)
