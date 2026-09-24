# -*- coding: utf-8 -*-
"""AE 通道收敛回归测试 (2026-09-19)。

背景: 集成计划评审 §六 指出"三轨并存、弃用声明与实际不符"。盘点中确认两处
**真缺陷**（不是文档问题），本测试固化修复：

  1. `AdobeMCPManager` 默认 project_root = bridges/, 而四个 JSX 监听器都在
     仓库根 → `install_bridge` 解析 `bridges/*.jsx` 全部不存在, 安装功能恒失败。
  2. `bridges/__init__.py` 饿汉式导入已弃用的 adobe_bridge_adapter →
     `import bridges` 就触发 DeprecationWarning, 与项目既有的 D-15 惰性导出
     约定（UnifiedBridgeBase）不一致。

另固化一条**语义澄清**: 被弃用的是那个包装类, 不是 `.ae-mcp-bridge` 协议
本身 —— 该协议仍由 ai/ae_render_channel.py 承载全部自动化 AE 渲染。
"""
import importlib
import warnings
from pathlib import Path

import pytest

PROJECT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(PROJECT))
sys.path.insert(0, str(PROJECT / "bridges"))


@pytest.fixture()
def manager():
    from adobe_mcp_manager import AdobeMCPManager
    return AdobeMCPManager()


class TestListenerResolution:
    """缺陷 1: 监听器路径必须能从 bridges/ 找到仓库根那一层"""

    def test_all_listeners_resolve_to_existing_files(self, manager):
        missing = {k: v for k, v in manager.jsx_files.items()
                   if not Path(v).exists()}
        assert not missing, f"监听器未解析到真实文件: {missing}"

    def test_listeners_live_in_repo_root(self, manager):
        """监听器在仓库根 (bridges/ 的上一层), 不在 bridges/ 内"""
        for p in manager.jsx_files.values():
            assert Path(p).parent == PROJECT, p
            assert Path(p).name.endswith(".jsx")

    def test_explicit_repo_root_also_works(self):
        from adobe_mcp_manager import AdobeMCPManager
        m = AdobeMCPManager(project_root=str(PROJECT))
        assert all(Path(v).exists() for v in m.jsx_files.values())

    def test_install_bridge_gate_no_longer_blocks_on_missing_jsx(self, manager):
        """install_bridge 的第一道闸门是 jsx 存在性; 现在不应再被它挡住。

        这里不真的安装到 AE Startup 目录 (环境依赖), 只验证闸门条件本身:
        四个 app 的 jsx_path 均已存在 → 不会走"JSX文件不存在"分支。
        """
        for app, p in manager.jsx_files.items():
            assert Path(p).exists(), f"{app} 的监听器缺失: {p}"


class TestLazyDeprecatedExport:
    """缺陷 2: 弃用模块惰性导出, 导入期不触发警告"""

    def test_package_import_emits_no_deprecation_warning(self):
        import bridges
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            importlib.reload(bridges)
            deps = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert not deps, [str(w.message) for w in deps]

    def test_attribute_access_emits_warning(self):
        import bridges
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            _ = bridges.AdobeBridgeAdapter
            deps = [w for w in caught if issubclass(w.category, DeprecationWarning)]
        assert deps, "访问弃用符号时应触发 DeprecationWarning"

    def test_dunder_all_still_resolvable(self):
        """__all__ 契约 (tests/test_bridges_pipeline_gaps.py 已断言)"""
        import bridges
        for name in bridges.__all__:
            assert getattr(bridges, name, None) is not None, name


class TestProtocolStillInProduction:
    """语义澄清: 协议未弃用 —— 它仍由渲染通道承载"""

    def test_render_channel_uses_ae_mcp_bridge_protocol(self):
        src = (PROJECT / "ai" / "ae_render_channel.py"
               ).read_text(encoding="utf-8", errors="replace")
        assert ".ae-mcp-bridge" in src
        assert "ae_command.json" in src
        assert "hmac" in src            # 签名层在产
        assert "core.bridge_failure" in src

    def test_deprecated_wrapper_docstring_does_not_claim_protocol_dead(self):
        """弃用说明必须区分"包装类无消费方"与"协议已弃用"。"""
        src = (PROJECT / "bridges" / "adobe_bridge_adapter.py"
               ).read_text(encoding="utf-8", errors="replace")
        head = src[:2000]
        assert "DEPRECATED" in head
        assert "仍在产" in head, "docstring 应澄清协议仍在产, 避免被误读为协议已死"

    def test_no_stale_archive_reference(self):
        """docstring 曾指向不存在的 archive/deprecated_self_built_bridge/"""
        src = (PROJECT / "bridges" / "adobe_bridge_adapter.py"
               ).read_text(encoding="utf-8", errors="replace")
        if "archive/deprecated_self_built_bridge" in src:
            assert (PROJECT / "archive" / "deprecated_self_built_bridge"
                    / "README.md").exists(), "引用了不存在的归档路径"
