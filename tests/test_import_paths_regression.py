"""
回归测试: puppet_automation (下划线) 目录已重命名为 puppet-automation (连字符),
旧的 from puppet_automation.src.engines.xxx import YyyEngine 导入路径必须已修复。

触发 Bug: 当调用使用了旧路径的属性 / 方法时, Python 会抛出:
    ModuleNotFoundError: No module named 'puppet_automation'
这是一个 100% 复现的崩溃。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 旧模块名 (下划线) - 在任何回归情况下出现的 ImportError 都会包含它
BAD_MODULE_NAME = "puppet_automation"


def _import_error_is_old_path(exc: BaseException) -> bool:
    """判断异常是否因 puppet_automation (旧下划线路径) 未找到而引发。"""
    msg = str(exc)
    # 两种典型信息: "No module named 'puppet_automation'" 或 "puppet_automation.src.engines..."
    return BAD_MODULE_NAME in msg


# ============================================================
# bridges/ 目录桥接器测试
# ============================================================

class TestBridgesEngineImportRegression:
    """所有桥接器的延迟 engine 属性访问必须不使用旧的下划线路径。"""

    def test_blender_ae_bridge_engine_getter_no_old_module_path(self):
        """BlenderAEBridge.blender_engine / ae_engine 访问不应报 puppet_automation 缺失。"""
        from bridges.blender_ae_bridge import BlenderAEBridge

        b = BlenderAEBridge()
        # BlenderEngine / AEEngine 构造器可能因实际软件未安装抛出其他错误,
        # 但不能是 "No module named 'puppet_automation'"
        for attr in ("blender_engine", "ae_engine"):
            try:
                _ = getattr(b, attr)
            except ModuleNotFoundError as e:
                if _import_error_is_old_path(e):
                    pytest.fail(f"BlenderAEBridge.{attr} 使用了旧下划线导入路径: {e}")
                raise  # 其他错误 (软件未安装) 是正常可接受的

    def test_silhouette_ae_bridge_engine_getter_no_old_module_path(self):
        """SilhouetteAEBridge.silhouette_engine / ae_engine 不应报旧下划线路径。"""
        from bridges.silhouette_ae_bridge import SilhouetteAEBridge

        b = SilhouetteAEBridge()
        for attr in ("silhouette_engine", "ae_engine"):
            try:
                _ = getattr(b, attr)
            except ModuleNotFoundError as e:
                if _import_error_is_old_path(e):
                    pytest.fail(f"SilhouetteAEBridge.{attr} 使用了旧下划线路径: {e}")
                raise

    def test_c4d_ae_bridge_engine_getter_no_old_module_path(self):
        from bridges.c4d_ae_bridge import C4DAEBridge

        b = C4DAEBridge()
        for attr in ("c4d_engine", "ae_engine"):
            try:
                _ = getattr(b, attr)
            except ModuleNotFoundError as e:
                if _import_error_is_old_path(e):
                    pytest.fail(f"C4DAEBridge.{attr} 使用了旧下划线路径: {e}")
                raise

    def test_topaz_davinci_bridge_engine_getter_no_old_module_path(self):
        from bridges.topaz_davinci_bridge import TopazDaVinciBridge

        b = TopazDaVinciBridge()
        for attr in ("topaz_engine", "davinci_engine"):
            try:
                _ = getattr(b, attr)
            except ModuleNotFoundError as e:
                if _import_error_is_old_path(e):
                    pytest.fail(f"TopazDaVinciBridge.{attr} 使用了旧下划线路径: {e}")
                raise


# ============================================================
# ae/adapters/ 目录适配器测试
# ============================================================

class TestAdaptersEngineImportRegression:
    """PS/AU 适配器 _ensure_engine 不应使用旧的 ps_engine/au_engine + 下划线路径。"""

    def test_ps_adapter_ensure_engine_no_old_module_path(self):
        """PuppetEnginePSAdapter._ensure_engine 不应报 puppet_automation / ps_engine。"""
        from ae.adapters.ps_adapter import PuppetEnginePSAdapter

        a = PuppetEnginePSAdapter()
        try:
            a._ensure_engine()
        except RuntimeError as e:
            # 正常路径: _ensure_engine 捕获 ImportError 后 raise RuntimeError("Puppet Engine not available")
            # 这是预期的 (引擎依赖可能没装)
            if "not available" in str(e).lower():
                return
            raise
        except ModuleNotFoundError as e:
            if _import_error_is_old_path(e) or "ps_engine" in str(e):
                pytest.fail(f"PuppetEnginePSAdapter 使用了旧下划线路径: {e}")
            raise

    def test_au_adapter_ensure_engine_no_old_module_path(self):
        """PuppetEngineAUAdapter._ensure_engine 不应报 puppet_automation / au_engine。"""
        from ae.adapters.au_adapter import PuppetEngineAUAdapter

        a = PuppetEngineAUAdapter()
        try:
            a._ensure_engine()
        except RuntimeError as e:
            if "not available" in str(e).lower():
                return
            raise
        except ModuleNotFoundError as e:
            if _import_error_is_old_path(e) or "au_engine" in str(e):
                pytest.fail(f"PuppetEngineAUAdapter 使用了旧下划线路径: {e}")
            raise


# ============================================================
# 源码静态检查: 确保不再有任何 from puppet_automation 残留 (双重保险)
# ============================================================

class TestStaticNoOldModuleNameRemnants:
    """静态扫描运行时代码文件, 确认不再残留 `from puppet_automation.` 或 `import puppet_automation`。"""

    # 扫描范围: 本次确认的 Bug3 运行时代码所在的目录
    SCAN_DIRS = [
        PROJECT_ROOT / "bridges",
        PROJECT_ROOT / "ae" / "adapters",
        PROJECT_ROOT / "vrs",
        PROJECT_ROOT / "integrations",
        PROJECT_ROOT / "scripts",
    ]

    def test_no_unguarded_old_import_path_in_running_source(self):
        """静态检查: `puppet_automation.*` 导入必须有 shim 保护。

        设计说明
        --------
        实际目录名为 ``puppet-automation``（含连字符），而连字符不是合法的
        Python 标识符，无法直接作为包名导入；同时引擎内部使用 3 级相对导入
        （``from ...config import settings``），要求模块路径前缀必须是
        ``puppet_automation.src.engines.xxx``。

        因此项目采用 shim 方案：调用 ``_ensure_puppet_automation_shim()``
        在运行时把连字符目录注册进 ``sys.modules``，随后再以下划线名导入。
        这是该约束下的正确解法，**不能**简单禁止源码中出现下划线导入。

        本测试因此校验真正会导致崩溃的情况：
        **导入语句之前没有任何 shim 注册调用**（即"裸导入"）。
        """
        shim_markers = (
            "_ensure_puppet_automation_shim",
            'sys.modules["puppet_automation"]',
            "sys.modules['puppet_automation']",
        )

        unguarded: list[str] = []
        for d in self.SCAN_DIRS:
            if not d.exists():
                continue
            for py_file in d.rglob("*.py"):
                try:
                    text = py_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

                lines = text.splitlines()
                for lineno, line in enumerate(lines, 1):
                    stripped = line.strip()
                    is_runtime_import = (
                        stripped.startswith("from puppet_automation")
                        or stripped.startswith("import puppet_automation")
                    )
                    if not is_runtime_import:
                        continue

                    # 该导入之前的源码中必须出现 shim 注册
                    preceding = "\n".join(lines[: lineno - 1])
                    if not any(marker in preceding for marker in shim_markers):
                        unguarded.append(
                            f"{py_file.relative_to(PROJECT_ROOT)}:{lineno}: {stripped[:100]}"
                        )

        assert not unguarded, (
            "以下 puppet_automation 导入缺少 shim 保护，运行时会抛 "
            "ModuleNotFoundError:\n  - " + "\n  - ".join(unguarded)
        )
