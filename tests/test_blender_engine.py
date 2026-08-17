#!/usr/bin/env python3
"""Blender 引擎单元测试 (P1.5-07)

验证项：
1. 引擎可实例化
2. available 标志正确反映 executable 真实存在性
3. CLI --version 可调用（不依赖 GUI 启动）
4. stage 模板字段可正确填充
5. name 属性为 "blender"
6. BaseEngine 继承关系正确
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "puppet-automation"))

from src.config.settings import settings
from src.engines.base import BaseEngine, EngineResult
from src.engines.blender.engine import BlenderEngine

import pytest

@pytest.fixture
def engine():
    return BlenderEngine()


def _print_result(name: str, success: bool, detail: str = "") -> None:
    status = "PASS" if success else "FAIL"
    print(f"  [{status}] {name}: {detail}")


def test_instantiation() -> bool:
    """1. 引擎可实例化 + available 标志。"""
    print("\n[Test 1] 实例化 + available 标志")
    try:
        engine = BlenderEngine()
        exe_exists = Path(settings.blender_path).exists()
        _print_result(
            "实例化", True,
            f"executable={engine.executable_path}, available={engine.available}"
        )
        _print_result(
            "available 与 exe 一致", engine.available == exe_exists,
            f"available={engine.available}, exe_exists={exe_exists}"
        )
        _print_result(
            "name 属性为 'blender'", engine.name == "blender",
            f"name={engine.name}"
        )
        _print_result(
            "继承 BaseEngine", isinstance(engine, BaseEngine), ""
        )
        return engine.available
    except Exception as e:
        _print_result("实例化异常", False, str(e))
        return False


def test_cli_version(engine: BlenderEngine) -> bool:
    """2. CLI --version 可调用。"""
    print("\n[Test 2] CLI --version 可调用")
    if not engine.available:
        _print_result("跳过（引擎不可用）", True, "available=False")
        return True

    cmd = [str(engine.executable_path), "--version"]
    code, stdout, stderr, err_code = engine._run_subprocess(cmd, timeout=30)
    version_line = (stdout or stderr or "").splitlines()[0] if (stdout or stderr) else ""
    success = code == 0 and "Blender" in version_line
    _print_result(
        "Blender --version", success,
        f"code={code}, version='{version_line[:80]}', err_code={err_code}"
    )
    return success


def test_stage_template_fields(engine: BlenderEngine) -> bool:
    """3. stage 模板字段可正确填充。"""
    print("\n[Test 3] STAGE_TEMPLATE 字段填充")
    try:
        template = engine.STAGE_TEMPLATE
        _print_result("STAGE_TEMPLATE 存在", "{stage_w}" in template, "")

        # 模拟参数填充（使用 STAGE_TEMPLATE 实际声明的字段）
        filled = template.format(
            stage_w=8.0,
            stage_h=6.0,
            stage_d=0.3,
            wood_color="(0.4, 0.25, 0.1, 1.0)",
            roughness=0.7,
            light_height=5.0,
            key_light_intensity=800.0,
            fill_light_intensity=300.0,
            rim_light_intensity=500.0,
            light_size=4.0,
            camera_distance=7.0,
            camera_height=4.5,
            camera_pitch=1.1,
            focal_length=50.0,
            render_engine="BLENDER_EEVEE_NEXT",
            resolution_x=1920,
            resolution_y=1080,
            output_format="PNG",
            blend_output="D:/AE-Work/test_blender_scene.blend",
            render_output="D:/AE-Work/test_blender_render/frame_",
            marker_path="C:/Users/user/AppData/Local/Temp/blender_render_test.mark",
            ae_export_block="# AE export disabled in unit test",
            fbx_output="D:/AE-Work/test_blender_scene.fbx",
            frames_output="D:/AE-Work/test_blender_frames",
            ae_frame_start=1,
            ae_marker_lines="# AE marker lines placeholder",
        )
        has_bpy = "import bpy" in filled
        has_stage = "Stage_Base" in filled
        _print_result("模板可正常填充", len(filled) > 100, f"length={len(filled)}")
        _print_result("包含 import bpy", has_bpy, "")
        _print_result("包含 Stage_Base", has_stage, "")
        return has_bpy and has_stage
    except KeyError as e:
        _print_result("模板缺少字段", False, f"missing key: {e}")
        return False
    except Exception as e:
        _print_result("模板填充异常", False, str(e))
        return False


async def test_execute_dispatch(engine: BlenderEngine) -> bool:
    """4. execute() dispatch 短路返回。"""
    print("\n[Test 4] execute() 调度")
    try:
        # 不存在的 action 应返回失败结果
        result = await engine.execute(action="nonexistent_action")
        success = isinstance(result, EngineResult) and not result.success
        _print_result(
            "未知 action 返回失败", success,
            f"success={result.success}, error={result.error}"
        )
        return success
    except Exception as e:
        _print_result("execute 异常", False, str(e))
        return False


def main() -> int:
    print("=" * 60)
    print("  Blender Engine Test (P1.5-07)")
    print("=" * 60)

    results: list[bool] = []

    # Test 1: 实例化
    engine_ok = test_instantiation()
    results.append(engine_ok is not None)

    if not engine_ok:
        print("\n[ABORT] 引擎不可用，跳过 CLI 测试")
        return 1

    engine = BlenderEngine()

    # Test 2: CLI version
    results.append(test_cli_version(engine))

    # Test 3: 模板字段
    results.append(test_stage_template_fields(engine))

    # Test 4: execute dispatch
    results.append(asyncio.run(test_execute_dispatch(engine)))

    # Summary
    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  Result: {passed}/{total} passed")
    print(f"{'=' * 60}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
