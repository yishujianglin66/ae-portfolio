#!/usr/bin/env python3
"""
test_blender_nl_service.py — Blender 自然语言服务单元测试

验证项：
1. test_safety_filter_denies_dangerous_code：
   - 通过 mock LLM 响应生成含 subprocess/system/exec 等高危调用的脚本
   - 断言静态安全审查 _safety_check 会拦截这些调用
   - 断言 BlenderNLService.execute() 返回 status="safety_violation"，不调用执行层

2. test_service_schema：
   - 服务可正常实例化（无异常）
   - 入参校验：空指令 → 立即返回错误（不调用 LLM）
   - 缺 LLM 网关时诚实降级：返回 status="llm_unavailable"，不抛异常
   - 响应结构符合约定 schema：{status, generated_code, attempt_count, stdout, stderr, error}
"""
from __future__ import annotations

import asyncio
import sys
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "puppet-automation" / "src"))


# ---------------------------------------------------------------------------
# 与 bridges/blender_ae_bridge.py 保持一致的 shim 导入
# 然后直接按文件路径加载 blender_nl_service.py，绕过 services/__init__.py
# 中的连锁相对导入。
# ---------------------------------------------------------------------------

_impl_cache: dict[str, Any] = {}


def _register_shim() -> None:
    """注册 puppet_automation 包别名（目录名 puppet-automation 含连字符）。"""
    import importlib.machinery
    import importlib.util

    if "puppet_automation" in sys.modules and "puppet_automation.src" in sys.modules:
        return

    _pa_dir = PROJECT_ROOT / "puppet-automation"
    _src_dir = _pa_dir / "src"

    if "puppet_automation" not in sys.modules:
        _pkg = importlib.util.module_from_spec(
            importlib.machinery.ModuleSpec("puppet_automation", loader=None, is_package=True)
        )
        _pkg.__path__ = [str(_pa_dir)]
        sys.modules["puppet_automation"] = _pkg

    if "puppet_automation.src" not in sys.modules:
        _svc_dir_spec = importlib.machinery.ModuleSpec(
            "puppet_automation.src", loader=None, is_package=True
        )
        _svc_dir_spec.submodule_search_locations = [str(_src_dir)]
        _src_pkg = importlib.util.module_from_spec(_svc_dir_spec)
        sys.modules["puppet_automation.src"] = _src_pkg

    if "puppet_automation.src.services" not in sys.modules:
        _svc_dir = _src_dir / "services"
        _spec = importlib.machinery.ModuleSpec(
            "puppet_automation.src.services", loader=None, is_package=True
        )
        _spec.submodule_search_locations = [str(_svc_dir)]
        sys.modules["puppet_automation.src.services"] = importlib.util.module_from_spec(_spec)


def _get_impl() -> Any:
    """按文件路径直加载 blender_nl_service.py，返回模块对象（缓存）。"""
    if "mod" in _impl_cache:
        return _impl_cache["mod"]

    _register_shim()

    import importlib.util

    file_path = PROJECT_ROOT / "puppet-automation" / "src" / "services" / "blender_nl_service.py"
    module_name = "_test_blender_nl_impl_v1"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载 blender_nl_service.py: {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    _impl_cache["mod"] = module
    return module


# ---------------------------------------------------------------------------
# 1. 安全审查单元测试（测试 _safety_check 纯函数）
# ---------------------------------------------------------------------------

class TestSafetyFilterDenyDangerousCode(unittest.TestCase):
    """静态安全审查拦截高危调用。"""

    def test_empty_code_fails(self):
        """空代码 → 审查失败。"""
        mod = _get_impl()
        result = mod._safety_check("")
        self.assertFalse(result.passed)
        self.assertTrue(any("空" in v for v in result.violations))

    def test_exec_blocked(self):
        """检测到 exec() 调用 → 拦截。"""
        mod = _get_impl()
        code = "import bpy\nexec('bpy.ops.object.delete()')\n"
        result = mod._safety_check(code)
        self.assertFalse(result.passed)
        self.assertTrue(any("exec" in v.lower() for v in result.violations),
                        f"exec 未被拦截，violations={result.violations}")

    def test_eval_blocked(self):
        """检测到 eval() 调用 → 拦截。"""
        mod = _get_impl()
        code = "import bpy\nx = eval('1+1')\n"
        result = mod._safety_check(code)
        self.assertFalse(result.passed, f"eval 未被拦截，violations={result.violations}")
        self.assertTrue(any("eval" in v.lower() for v in result.violations))

    def test_subprocess_blocked(self):
        """检测到 import subprocess → 拦截。"""
        mod = _get_impl()
        code = (
            "import bpy\n"
            "import subprocess\n"
            "subprocess.run(['rm', '-rf', '/'])\n"
        )
        result = mod._safety_check(code)
        self.assertFalse(result.passed,
                         f"subprocess 未被拦截，violations={result.violations}")
        self.assertTrue(any("subprocess" in v.lower() for v in result.violations))

    def test_os_system_blocked(self):
        """检测到 os.system() 调用 → 拦截。"""
        mod = _get_impl()
        code = (
            "import bpy\n"
            "import os\n"
            "os.system('calc.exe')\n"
        )
        result = mod._safety_check(code)
        self.assertFalse(result.passed,
                         f"os.system 未被拦截，violations={result.violations}")
        self.assertTrue(any("os.system" in v.lower() or "系统命令" in v
                            for v in result.violations))

    def test_dunder_import_blocked(self):
        """检测到 __import__() 动态导入 → 拦截。"""
        mod = _get_impl()
        code = "import bpy\nmod = __import__('subprocess')\n"
        result = mod._safety_check(code)
        self.assertFalse(result.passed,
                         f"__import__ 未被拦截，violations={result.violations}")
        self.assertTrue(any("__import__" in v for v in result.violations))

    def test_open_non_binary_blocked(self):
        """open() 使用文本模式（'r'/'w'/'a'，不含 'b'）→ 拦截。"""
        mod = _get_impl()
        code = "import bpy\nwith open('C:/secret.txt', 'w') as f:\n    f.write('leak')\n"
        result = mod._safety_check(code)
        self.assertFalse(result.passed,
                         f"open('w') 未被拦截，violations={result.violations}")
        self.assertTrue(any("二进制" in v or "b'" in v or "非二进制" in v
                            for v in result.violations))

    def test_open_r_plus_blocked(self):
        """open('r+') 非二进制 → 拦截。"""
        mod = _get_impl()
        code = "import bpy\nf = open('data.txt', 'r+')\n"
        result = mod._safety_check(code)
        self.assertFalse(result.passed,
                         f"open('r+') 未被拦截，violations={result.violations}")

    def test_compile_blocked(self):
        """compile() → 拦截。"""
        mod = _get_impl()
        code = "import bpy\ncode_obj = compile('a=1', '<s>', 'exec')\n"
        result = mod._safety_check(code)
        self.assertFalse(result.passed,
                         f"compile 未被拦截，violations={result.violations}")

    def test_socket_blocked(self):
        """import socket → 拦截（防止网络外发）。"""
        mod = _get_impl()
        code = "import bpy\nimport socket\ns = socket.socket()\n"
        result = mod._safety_check(code)
        self.assertFalse(result.passed,
                         f"socket 未被拦截，violations={result.violations}")

    def test_legitimate_bpy_code_passes(self):
        """纯 bpy 合法脚本（无高危调用）→ 通过审查。"""
        mod = _get_impl()
        code = (
            "import bpy\n"
            "# 创建红色立方体\n"
            "bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 0))\n"
            "cube = bpy.context.active_object\n"
            "cube.name = '红色立方体'\n"
            "mat = bpy.data.materials.new(name='红色材质')\n"
            "mat.use_nodes = True\n"
            "bsdf = mat.node_tree.nodes['Principled BSDF']\n"
            "bsdf.inputs['Base Color'].default_value = (0.8, 0.1, 0.1, 1.0)\n"
            "if cube.data.materials:\n"
            "    cube.data.materials[0] = mat\n"
            "else:\n"
            "    cube.data.materials.append(mat)\n"
        )
        result = mod._safety_check(code)
        self.assertTrue(result.passed,
                        f"合法 bpy 代码被误拦截，violations={result.violations}")

    def test_open_binary_passes(self):
        """open() 使用二进制模式（rb/wb/ab/r+b）→ 允许。"""
        mod = _get_impl()
        code = (
            "import bpy\n"
            "with open('/tmp/model.bin', 'wb') as f:\n"
            "    f.write(b'hello')\n"
        )
        result = mod._safety_check(code)
        self.assertTrue(result.passed,
                        f"open('wb') 被误拦截，violations={result.violations}")

    def test_service_execute_with_mocked_unsafe_llm(self):
        """端到端：mock LLM 返回含高危代码的脚本，断言服务拦截且不执行。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService
        BlenderNLResult = mod.BlenderNLResult

        dangerous_code = (
            "import bpy\n"
            "import subprocess\n"
            "subprocess.run(['cmd', '/c', 'dir'], shell=True)\n"
        )

        @dataclass
        class FakeLLMResponse:
            success: bool = True
            content: str = ""

        async def fake_chat_with_routing(*a, **kw):
            return FakeLLMResponse(success=True, content=dangerous_code)

        async def fake_chat(*a, **kw):
            return FakeLLMResponse(success=True, content=dangerous_code)

        fake_bundle = {
            "chat_with_routing": fake_chat_with_routing,
            "chat": fake_chat,
            "TaskType": None,
            "gateway": None,
        }

        execution_called = {"flag": False}

        class DummyBlenderEngine:
            async def run_script(self, script_content: str):
                execution_called["flag"] = True
                raise AssertionError("安全审查未拦截，执行层不该被调用")

        service = BlenderNLService(
            blender_engine=DummyBlenderEngine(),
            llm_gateway_bundle=fake_bundle,
            knowledge_api_dir=None,
        )

        async def run():
            return await service.execute(command="做个立方体", max_attempts=1)

        result: BlenderNLResult = asyncio.run(run())

        self.assertEqual(result.status, "safety_violation",
                         f"期望 status=safety_violation，实际={result.status}，"
                         f"error={result.error}")
        self.assertIn("subprocess", result.generated_code,
                      "mock 生成的含 subprocess 代码未被保存在 generated_code 字段中")
        self.assertFalse(execution_called["flag"],
                         "安全审查未拦截，竟已执行到 BlenderEngine.run_script")
        self.assertTrue(result.error, "safety_violation 时 error 字段不应为空")


# ---------------------------------------------------------------------------
# 2. 服务 Schema / 降级行为测试
# ---------------------------------------------------------------------------

class TestServiceSchema(unittest.TestCase):
    """服务初始化、入参校验、缺 LLM 时诚实降级。"""

    def test_service_instantiation(self):
        """服务可正常实例化，不抛异常。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService
        try:
            service = BlenderNLService(
                blender_engine=None,
                llm_gateway_bundle=None,
                knowledge_api_dir=None,
            )
        except Exception as e:
            self.fail(f"BlenderNLService 实例化抛异常: {e}")
        self.assertIsInstance(service, BlenderNLService)

    def test_empty_command_short_circuits(self):
        """空指令 → 立即返回错误，不调用 LLM。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService

        llm_called = {"flag": False}

        async def fake_chat(*a, **kw):
            llm_called["flag"] = True
            raise AssertionError("空指令不该调用 LLM")

        fake_bundle = {
            "chat_with_routing": None,
            "chat": fake_chat,
            "TaskType": None,
            "gateway": None,
        }
        service = BlenderNLService(
            blender_engine=None,
            llm_gateway_bundle=fake_bundle,
        )

        async def run():
            return await service.execute(command="")

        result = asyncio.run(run())
        self.assertEqual(result.status, "execution_failed",
                         f"空指令应返回 execution_failed，实际={result.status}")
        self.assertIn("空", result.error or "",
                      "错误信息应说明指令为空")
        self.assertFalse(llm_called["flag"], "空指令不应调用 LLM")

    def test_whitespace_only_command_short_circuits(self):
        """纯空白指令 → 立即返回错误。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService

        async def fake_chat(*a, **kw):
            raise AssertionError("空白指令不该调用 LLM")

        service = BlenderNLService(
            blender_engine=None,
            llm_gateway_bundle={
                "chat_with_routing": None,
                "chat": fake_chat,
                "TaskType": None,
                "gateway": None,
            },
        )

        async def run():
            return await service.execute(command="   \t\n  ")

        result = asyncio.run(run())
        self.assertEqual(result.status, "execution_failed")

    def test_missing_llm_honest_degradation(self):
        """LLM 网关不可用时诚实降级：status=llm_unavailable，不抛异常。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService

        unavailable_bundle: dict[str, Any] = {
            "chat_with_routing": None,
            "chat": None,
            "TaskType": None,
            "gateway": None,
        }
        service = BlenderNLService(
            blender_engine=None,
            llm_gateway_bundle=unavailable_bundle,
        )

        async def run():
            return await service.execute(
                command="创建一个红色立方体",
                scene_context="场景中有默认相机和灯光",
                max_attempts=1,
            )

        result = asyncio.run(run())
        self.assertIn(
            result.status,
            ("llm_unavailable", "execution_failed"),
            (f"无可用 LLM 接口时应返回 llm_unavailable 或 execution_failed，"
             f"实际={result.status}，error={result.error}"),
        )
        self.assertTrue(result.error, "error 字段应说明 LLM 不可用原因")
        self.assertIsNotNone(result.status)
        self.assertIsInstance(result.attempt_count, int)
        self.assertGreaterEqual(result.attempt_count, 1)

    def test_response_schema_conformance(self):
        """响应结构符合约定：{status, generated_code, attempt_count, stdout, stderr, error}。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService
        BlenderNLResult = mod.BlenderNLResult

        service = BlenderNLService(
            blender_engine=None,
            llm_gateway_bundle=None,
        )

        async def run():
            return await service.execute(command="")

        result = asyncio.run(run())
        as_dict = result.to_dict()

        expected_keys = {
            "status", "generated_code", "attempt_count",
            "stdout", "stderr", "error",
        }
        self.assertTrue(expected_keys.issubset(set(as_dict.keys())),
                        f"响应缺少字段，期望键={expected_keys}，实际={set(as_dict.keys())}")

        self.assertIsInstance(as_dict["status"], str)
        self.assertIsInstance(as_dict["generated_code"], str)
        self.assertIsInstance(as_dict["attempt_count"], int)
        self.assertIsInstance(as_dict["stdout"], str)
        self.assertIsInstance(as_dict["stderr"], str)
        self.assertIsInstance(as_dict["error"], str)

        self.assertIsInstance(result.status, str)
        self.assertIsInstance(result.generated_code, str)
        self.assertIsInstance(result.attempt_count, int)
        self.assertIsInstance(result.stdout, str)
        self.assertIsInstance(result.stderr, str)
        self.assertIsInstance(result.error, str)
        self.assertIsInstance(result, BlenderNLResult)

    def test_max_attempts_input_clamped(self):
        """max_attempts 入参被限制在 1~5，防止无限循环或恶意大值。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService

        @dataclass
        class FakeResp:
            success: bool = True
            content: str = "import bpy\nbpy.ops.mesh.primitive_cube_add()\n"

        async def fake_chat(*a, **kw):
            return FakeResp()

        fake_bundle = {
            "chat_with_routing": None,
            "chat": fake_chat,
            "TaskType": None,
            "gateway": None,
        }

        execution_count = {"n": 0}

        class FailEngine:
            """每次执行都失败，触发重试循环。"""
            async def run_script(self, script_content: str):
                execution_count["n"] += 1
                r = MagicMock()
                r.success = False
                r.metadata = {}
                r.error = "故意失败"
                return r

        service = BlenderNLService(
            blender_engine=FailEngine(),
            llm_gateway_bundle=fake_bundle,
        )

        async def run():
            return await service.execute(
                command="创建立方体", max_attempts=100,
            )

        result = asyncio.run(run())
        self.assertLessEqual(
            execution_count["n"], 5,
            f"max_attempts=100 未被钳制，实际执行次数={execution_count['n']}",
        )
        self.assertEqual(result.attempt_count, execution_count["n"],
                         "attempt_count 应等于实际执行/重试次数")

    def test_clean_code_block_strips_markdown(self):
        """响应清洗：去除 Markdown ```python 围栏。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService

        fenced = (
            "```python\n"
            "import bpy\n"
            "bpy.ops.object.delete()\n"
            "```"
        )
        cleaned = BlenderNLService._clean_code_block(fenced)
        self.assertNotIn("```", cleaned, "应清除 ``` 围栏")
        self.assertTrue(cleaned.startswith("import bpy"),
                        f"清洗后应以 import bpy 开头，实际={cleaned[:40]}")
        self.assertIn("bpy.ops.object.delete()", cleaned)

    def test_clean_code_block_strips_backticks_only(self):
        """响应清洗：去除通用 ``` ``` 围栏（无语言标识）。"""
        mod = _get_impl()
        BlenderNLService = mod.BlenderNLService

        fenced = "```\nimport bpy\nprint('hi')\n```"
        cleaned = BlenderNLService._clean_code_block(fenced)
        self.assertNotIn("```", cleaned)
        self.assertEqual(cleaned, "import bpy\nprint('hi')")


if __name__ == "__main__":
    unittest.main(verbosity=2)
