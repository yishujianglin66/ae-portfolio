"""
P0 可运行性冒烟测试 (smoke test)
================================
锁定 P0-1 / P0-2 治理成果：统一入口 bootstrap 注入 24 个子目录后，
8 个关键模块可跨目录导入（对应 `uv run --no-project python run.py check` 的 8/8）。

这些测试仅依赖 bootstrap.py 的 sys.path 注入，不依赖重型可选依赖
(audio / vision / video / ai / ml 等 dependency-groups)，因此可在 CI 默认环境稳定通过。

运行:
    uv run --no-project python -m pytest tests/test_p0_imports.py -v

背景：P0-1 统一了启动入口与依赖固化，P0-2 修复了硬编码路径与裸 import。
本测试防止这些跨目录 import 链路在未来的重构中悄然断裂。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# 项目根: tests/ 的上一级
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 注入 24 个子目录（与 bootstrap.py / run.py 完全一致）
import bootstrap  # noqa: E402

# P0-1 验证通过、且被 run.py check 锁定的 8 个关键模块
CRITICAL_MODULES = [
    "ae",
    "tools",
    "web",
    "rendering",
    "ae.unified_ae_client",
    "tools.unified_tool_integrator",
    "tools.toolchain_api",
    "rendering.ae_render_engine",
]


def test_bootstrap_injects_subdirs() -> None:
    """关键子目录必须在 sys.path 中（由 bootstrap 或 conftest 注入均可）。

    注意：pytest 运行时 tests/conftest.py 已先注入了子目录，因此 bootstrap
    本次实际「新增」的路径可能很少（inserted_paths() 只记录本次新增）。
    故这里断言「关键子目录可达」，而非 bootstrap 的注入计数——计数在不同
    运行环境下不恒定，但「ae/tools/rendering/web 可导入」才是真正的 P0 契约
    （见下方 parametrize 测试）。
    """
    inserted = bootstrap.inserted_paths()
    assert isinstance(inserted, list)
    # 关键子目录必须在 sys.path 中（无论由谁注入）
    present = {Path(p).name for p in sys.path}
    for expected in ("ae", "tools", "rendering", "web"):
        assert expected in present, f"关键子目录不在 sys.path: {expected}"


@pytest.mark.parametrize("modname", CRITICAL_MODULES)
def test_critical_module_importable(modname: str) -> None:
    """每个 P0 关键模块均可导入，跨目录 import 链路完好。"""
    assert importlib.import_module(modname) is not None


def test_all_critical_modules_import() -> None:
    """一次性导入全部 8 个关键模块（对应 `run.py check` 的 8/8）。"""
    imported = [importlib.import_module(m) for m in CRITICAL_MODULES]
    assert len(imported) == len(CRITICAL_MODULES)
