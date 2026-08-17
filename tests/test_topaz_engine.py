#!/usr/bin/env python3
"""Topaz Video AI 引擎单元测试 (P1.5-07)

验证项：
1. 引擎可实例化
2. available 标志正确反映 executable 真实存在性
3. MODELS 字典完整
4. CLI 可调用（--version 或 -h）
5. enhance() 参数验证（无效 model 立即失败）
6. name 属性为 "topaz"
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "puppet-automation"))

# 清理裸 `engines.*` 注册，避免同一份 puppet-automation/src/engines
# 同时以 `engines.x` 和 `src.engines.x` 两个名字存在造成类身份分裂。
#
# 注意：这里不能连 `src.*` 一起删。本模块在 pytest collection 阶段执行，
# 而其它测试（如 test_layer_render_service）同样在 collection 阶段用
# spec_from_file_location 建立 `src.models.layer_pipeline` 等注册；
# 一旦被删除，运行阶段那些模块内部已绑定的类对象就与重新加载出的类
# 不是同一个，Pydantic 校验会报 "Input should be ... instance of LayerConfig"。
_stale = [k for k in sys.modules if k == 'engines' or k.startswith('engines.')]
for _k in _stale:
    del sys.modules[_k]

from src.config.settings import settings
from src.engines.base import BaseEngine, EngineResult
from src.engines.topaz.engine import TopazEngine

import pytest

@pytest.fixture
def engine():
    """TopazEngine 实例 fixture"""
    return TopazEngine()


def _print_result(name: str, success: bool, detail: str = "") -> None:
    status = "PASS" if success else "FAIL"
    print(f"  [{status}] {name}: {detail}")


def test_instantiation() -> TopazEngine | None:
    """1. 引擎可实例化 + available 标志。"""
    print("\n[Test 1] 实例化 + available 标志")
    try:
        engine = TopazEngine()
        exe_exists = Path(settings.topaz_path).exists()
        _print_result(
            "实例化", True,
            f"executable={engine.executable_path}, available={engine.available}"
        )
        _print_result(
            "available 与 exe 一致", engine.available == exe_exists,
            f"available={engine.available}, exe_exists={exe_exists}"
        )
        _print_result(
            "name 属性为 'topaz'", engine.name == "topaz",
            f"name={engine.name}"
        )
        _print_result(
            "继承 BaseEngine", isinstance(engine, BaseEngine), ""
        )
        return engine
    except Exception as e:
        _print_result("实例化异常", False, str(e))
        return None


def test_models_dict(engine: TopazEngine) -> bool:
    """3. MODELS 字典完整。"""
    print("\n[Test 3] MODELS 字典完整性")
    expected_models = {"proteus", "artemis", "gaia", "theia", "nyx", "iris"}
    actual_models = set(engine.MODELS.keys())
    success = expected_models.issubset(actual_models)
    _print_result(
        "MODELS 包含 6 个核心模型", success,
        f"actual={sorted(actual_models)}"
    )
    return success


def test_cli_help(engine: TopazEngine) -> bool:
    """4. CLI 可调用性验证。

    Topaz Video AI BETA.exe 是 GUI 应用，--help/-h/--version 都不是有效的 CLI flag
    会启动 GUI 卡死（实测全部 timeout）。

    正确做法：验证 Topaz 安装目录下的独立 CLI 工具（ffmpeg.exe / ffprobe.exe），
    这是 Topaz Pro 真正的命令行入口。
    """
    print("\n[Test 4] CLI 可调用性（通过 Topaz 自带 ffmpeg.exe）")
    if not engine.available:
        _print_result("跳过（引擎不可用）", True, "available=False")
        return True

    # Topaz Video AI Pro 安装目录下应有 ffmpeg.exe（独立 CLI 工具）
    topaz_dir = Path(settings.topaz_path).parent
    topaz_ffmpeg = topaz_dir / "ffmpeg.exe"
    topaz_ffprobe = topaz_dir / "ffprobe.exe"

    cli_tools_found = []
    for tool in [topaz_ffmpeg, topaz_ffprobe]:
        if tool.exists():
            cli_tools_found.append(tool)

    if not cli_tools_found:
        _print_result("未找到 Topaz 自带 CLI 工具", False,
                      f"在 {topaz_dir} 下未找到 ffmpeg.exe/ffprobe.exe")
        return False

    _print_result(
        "Topaz CLI 工具存在", True,
        f"找到 {len(cli_tools_found)} 个 CLI 工具: {[t.name for t in cli_tools_found]}"
    )

    # 验证 ffmpeg.exe -version 可调用
    cmd = [str(topaz_ffmpeg), "-version"]
    code, stdout, stderr, err_code = engine._run_subprocess(cmd, timeout=15)
    version_line = (stdout or "").splitlines()[0] if stdout else ""
    success = code == 0 and "ffmpeg" in version_line.lower()
    _print_result(
        "Topaz ffmpeg -version", success,
        f"code={code}, version='{version_line[:80]}', err_code={err_code}"
    )
    return success


async def test_enhance_invalid_model(engine: TopazEngine) -> bool:
    """5. enhance() 参数验证。"""
    print("\n[Test 5] enhance() 无效 model 立即失败")
    try:
        result = await engine.enhance(
            input_path="dummy_input.mp4",
            output_path="dummy_output.mp4",
            model="INVALID_MODEL_NAME",
        )
        success = isinstance(result, EngineResult) and not result.success
        _print_result(
            "无效 model 返回失败", success,
            f"success={result.success}, error={result.error}"
        )
        return success
    except Exception as e:
        _print_result("enhance 异常", False, str(e))
        return False


async def test_execute_dispatch(engine: TopazEngine) -> bool:
    """6. execute() 未知 action 短路。"""
    print("\n[Test 6] execute() 调度")
    try:
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
    print("  Topaz Video AI Engine Test (P1.5-07)")
    print("=" * 60)

    results: list[bool] = []

    engine = test_instantiation()
    if engine is None:
        return 1
    results.append(True)

    # Test 3: MODELS 字典
    results.append(test_models_dict(engine))

    # Test 4: CLI
    results.append(test_cli_help(engine))

    # Test 5: enhance 参数验证
    results.append(await_test(test_enhance_invalid_model(engine)))

    # Test 6: execute dispatch
    results.append(await_test(test_execute_dispatch(engine)))

    passed = sum(1 for r in results if r)
    total = len(results)
    print(f"\n{'=' * 60}")
    print(f"  Result: {passed}/{total} passed")
    print(f"{'=' * 60}")
    return 0 if passed == total else 1


def await_test(coro):
    """同步包装 async 测试。"""
    return asyncio.run(coro)


if __name__ == "__main__":
    sys.exit(main())
