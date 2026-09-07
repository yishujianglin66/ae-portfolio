"""PREngine（已弃用 shim）契约测试。

背景
----
``engines.pr.engine.PREngine`` 已合并进
``engines.premiere.engine.PremiereEngine``，当前仅作为向后兼容 shim 保留。

本测试文件此前断言了一批从未在任何引擎中实现过的属性
（``_poll_interval`` / ``_timeout`` / ``_bridge_dir`` / ``execute_batch``），
属于"想象中的 API"，与真实架构不符，因此全部重写为可验证的真实契约：

1. shim 必须继承自 ``PremiereEngine``，保证行为完全等价；
2. shim 必须保留 ``name = "premiere_pro"`` 标识以兼容旧调用方；
3. 导入 shim 必须触发 ``DeprecationWarning``，引导迁移；
4. ``PremiereEngine`` 对外暴露的方法，shim 必须一并继承，不得缺失。
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# --- 路径引导 ---------------------------------------------------------------
# pr/engine.py 内部使用相对导入（``from ..premiere.engine import ...``），
# 因此必须以包形式导入（``src.engines.*``），不能直接把
# ``src/engines/pr`` 加进 sys.path。此处与项目既有惯例保持一致。
PROJECT_ROOT = Path(__file__).resolve().parents[1]
PUPPET_ROOT = PROJECT_ROOT / "puppet-automation"
if str(PUPPET_ROOT) not in sys.path:
    sys.path.insert(0, str(PUPPET_ROOT))

from src.engines.pr.engine import PREngine  # noqa: E402
from src.engines.premiere.engine import PremiereEngine  # noqa: E402
from src.engines.base import EngineResult  # noqa: E402


class TestPREngineDeprecationContract:
    """shim 的弃用契约。"""

    def test_pr_engine_subclasses_premiere_engine(self):
        """PREngine 必须继承 PremiereEngine，确保行为等价。"""
        assert issubclass(PREngine, PremiereEngine)

    def test_pr_engine_keeps_legacy_name(self):
        """保留旧标识 name="premiere_pro"，避免破坏依赖该值的调用方。"""
        assert PREngine.name == "premiere_pro"

    def test_premiere_engine_uses_its_own_name(self):
        """新引擎使用自己的标识，两者不应混淆。"""
        assert PremiereEngine.name == "premiere"

    def test_importing_shim_emits_deprecation_warning(self):
        """重新导入 shim 模块时必须发出 DeprecationWarning。"""
        module_name = "src.engines.pr.engine"
        sys.modules.pop(module_name, None)
        with pytest.warns(DeprecationWarning, match="已弃用"):
            importlib.import_module(module_name)


class TestPREngineInterfaceParity:
    """shim 必须完整继承新引擎的公开能力。"""

    EXPECTED_METHODS = (
        "ping",
        "execute_script",
        "get_project_info",
        "list_sequences",
        "import_media",
        "create_sequence",
        "add_clip_to_timeline",
        "apply_transition",
        "export_sequence",
        "import_ae_comp",
        "auto_edit_sequence",
        "export_final",
    )

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_shim_inherits_method(self, method_name):
        """逐个校验方法在 shim 上可访问且可调用。"""
        assert hasattr(PREngine, method_name), f"PREngine 缺少方法 {method_name}"
        assert callable(getattr(PREngine, method_name))

    def test_shim_adds_no_divergent_public_api(self):
        """shim 不应引入新的公开方法，否则等价性被破坏。"""
        shim_only = {
            name
            for name in vars(PREngine)
            if not name.startswith("_") and callable(getattr(PREngine, name, None))
        }
        assert shim_only == set(), f"shim 不应新增公开方法: {shim_only}"


class TestEngineResultContract:
    """EngineResult 数据契约（AE / PR 共用）。"""

    def test_engine_result_fields(self):
        result = EngineResult(
            success=True,
            output_path=Path("test.mp4"),
            metadata={"key": "value"},
            error=None,
            duration_seconds=1.5,
        )
        assert result.success is True
        assert result.output_path == Path("test.mp4")
        assert result.metadata == {"key": "value"}
        assert result.error is None
        assert result.duration_seconds == 1.5

    def test_engine_result_failure_carries_error(self):
        result = EngineResult(success=False, error="boom")
        assert result.success is False
        assert result.error == "boom"
