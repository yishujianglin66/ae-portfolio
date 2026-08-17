"""Cinema 4D engine tests.

验证 Cinema4DEngine 引擎适配器的导入、实例化、动作分发与脚本执行接口。
不实际启动 c4dpy.exe（避免 30s+ 启动耗时），仅验证接口可用性与命令构造正确性。
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from src.config import settings
from src.engines.cinema4d import Cinema4DEngine
from src.engines.base import EngineResult


class TestCinema4DEngine:
    """Test Cinema4DEngine adapter."""

    def test_cinema4d_engine_init(self):
        """引擎能正确初始化，且 c4dpy.exe 存在。"""
        engine = Cinema4DEngine()
        assert engine is not None
        assert engine.name == "cinema4d"
        # executable_path 应指向 c4dpy.exe
        assert engine.executable_path.name.lower() == "c4dpy.exe"
        # c4dpy.exe 必须存在（验证 Cinema 4D 2026 已安装）
        assert engine.executable_path.exists(), (
            f"c4dpy.exe not found at {engine.executable_path}"
        )
        assert engine.available is True
        # 同时保留 Cinema 4D.exe 路径
        assert engine.c4d_executable.name.lower() == "cinema 4d.exe"
        # 验证所有公开方法都已实现
        for method in (
            "render_scene",
            "export_fbx",
            "export_camera_data",
            "render_motion_graphics",
            "run_python_script",
            "execute",
        ):
            assert hasattr(engine, method), f"Missing method: {method}"

    @pytest.mark.asyncio
    async def test_execute_impl_unknown_action_returns_failure(self):
        """_execute_impl 分发未知 action 时返回 success=False。"""
        engine = Cinema4DEngine()
        # 跳过实际渲染：未知 action 应在分发阶段就失败
        result = await engine.execute(action="nonexistent_action_xyz")

        assert isinstance(result, EngineResult)
        assert result.success is False
        assert result.error is not None
        assert "nonexistent_action_xyz" in result.error
        # 错误信息中应列出可用 action
        assert "render_scene" in result.error
        assert "run_python_script" in result.error

    @pytest.mark.asyncio
    async def test_run_python_script_interface(self):
        """run_python_script 接口可用性测试（mock 子进程，避免启动 c4dpy）。

        c4dpy.exe 启动需加载完整 C4D 运行时（30s+），单元测试中改用 mock 验证：
        - 脚本被正确写入临时文件
        - 命令构造正确（c4dpy.exe + script.py）
        - 返回 EngineResult 包含 returncode / stdout_tail
        """
        engine = Cinema4DEngine()

        # Mock _run_subprocess 返回成功结果（避免实际启动 c4dpy）
        def fake_run_subprocess(cmd, timeout, cwd=None):
            # 验证命令构造正确
            assert str(engine.executable_path) in cmd[0], \
                f"Expected c4dpy.exe in cmd, got: {cmd[0]}"
            # 第二个参数应是脚本文件路径
            assert len(cmd) >= 2, f"Expected script path in cmd, got: {cmd}"
            script_path = cmd[-1]
            assert script_path.endswith(".py"), \
                f"Expected .py script path, got: {script_path}"
            # 读取脚本内容，验证 c4d 模块导入语句存在
            script_text = Path(script_path).read_text(encoding="utf-8")
            assert "import c4d" in script_text, \
                "Script should import c4d module"
            assert "C4D_VERSION" in script_text, \
                "Script should print c4d version"
            return 0, "C4D_VERSION: 2026002\nAPI_VERSION: (26, 0, 0)\n", "", None

        with patch.object(engine, "_run_subprocess", side_effect=fake_run_subprocess):
            script = (
                "import c4d\n"
                "print('C4D_VERSION:', c4d.GetC4DVersion())\n"
                "print('API_VERSION:', c4d.GetApiVersion())\n"
            )
            result = await engine.run_python_script(script_content=script)

        assert isinstance(result, EngineResult)
        assert result.success is True
        assert result.metadata["returncode"] == 0
        assert "C4D_VERSION" in result.metadata["stdout_tail"]
        assert result.error is None

    @pytest.mark.asyncio
    async def test_run_python_script_with_c4d_file(self):
        """run_python_script 接受 c4d_file 参数时命令包含场景路径。"""
        engine = Cinema4DEngine()

        captured_cmd = []

        def fake_run_subprocess(cmd, timeout, cwd=None):
            captured_cmd.extend(cmd)
            return 0, "ok\n", "", None

        # 准备一个假 .c4d 文件
        fake_c4d = Path(__file__).parent / "fake_test_scene.c4d"
        fake_c4d.write_bytes(b"fake c4d content")

        try:
            with patch.object(engine, "_run_subprocess", side_effect=fake_run_subprocess):
                result = await engine.run_python_script(
                    script_content="import c4d\nprint('hello')\n",
                    c4d_file=fake_c4d,
                )

            # 命令应为 [c4dpy.exe, scene.c4d, script.py]
            assert len(captured_cmd) == 3, \
                f"Expected 3-element cmd, got: {captured_cmd}"
            assert str(engine.executable_path) in captured_cmd[0]
            assert captured_cmd[1].endswith("fake_test_scene.c4d")
            assert captured_cmd[2].endswith(".py")
            assert result.success is True
        finally:
            fake_c4d.unlink(missing_ok=True)


if __name__ == "__main__":
    """直接运行基础测试。"""

    async def _run_basic():
        engine = Cinema4DEngine()
        print(f"Engine: {engine.name}")
        print(f"c4dpy path: {engine.executable_path}")
        print(f"c4dpy exists: {engine.executable_path.exists()}")
        print(f"available: {engine.available}")

        result = await engine.execute(action="nonexistent_action_xyz")
        print(f"Unknown action result: success={result.success}, error={result.error}")

    asyncio.run(_run_basic())
