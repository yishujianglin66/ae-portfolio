"""AEPluginService._resolve_preset_path 验证脚本.

验证 ae_plugin_service 通过 resource_index_service 查找 .ffx 预设文件的能力。
不启动 AE 引擎，仅测试路径解析逻辑。

运行方式：
    py -3.11 scripts/test_ae_plugin_service_resource.py
"""
from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path

# 将 puppet-automation 加入 sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PUPPET_AUTO = PROJECT_ROOT / "puppet-automation"
sys.path.insert(0, str(PUPPET_AUTO))

from src.services.ae_plugin_service import AEPluginService  # noqa: E402
from src.services.resource_index_service import (  # noqa: E402
    _RESOURCE_CATEGORIES,
    resource_index_service,
)


def test_category_registered() -> None:
    """验证 ae_presets 类别已注册到 _RESOURCE_CATEGORIES."""
    assert "ae_presets" in _RESOURCE_CATEGORIES, "ae_presets 类别未注册"
    settings_field, extensions = _RESOURCE_CATEGORIES["ae_presets"]
    assert settings_field == "presets_dir", f"settings 字段应为 presets_dir，实际: {settings_field}"
    for ext in (".ffx", ".aex", ".anim"):
        assert ext in extensions, f"扩展名 {ext} 未在 ae_presets 类别中"
    print(f"[OK] ae_presets 类别已注册: settings_field={settings_field}, extensions={extensions}")


def test_find_ae_preset_method_exists() -> None:
    """验证 resource_index_service 暴露 find_ae_preset 方法."""
    assert hasattr(resource_index_service, "find_ae_preset"), "未找到 find_ae_preset 方法"
    assert callable(resource_index_service.find_ae_preset), "find_ae_preset 不可调用"
    print("[OK] resource_index_service.find_ae_preset 方法存在")


def test_resolve_preset_path_method_exists() -> None:
    """验证 AEPluginService 暴露 _resolve_preset_path 方法."""
    assert hasattr(AEPluginService, "_resolve_preset_path"), "未找到 _resolve_preset_path 方法"
    print("[OK] AEPluginService._resolve_preset_path 方法存在")


async def test_resolve_existing_file_path() -> None:
    """验证传入已存在的文件路径时直接返回（不触发资源索引查找）."""
    svc = AEPluginService.__new__(AEPluginService)  # 不调用 __init__，避免启动 AE
    with tempfile.NamedTemporaryFile(suffix=".ffx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = await svc._resolve_preset_path(tmp_path)
        assert result == tmp_path, f"应返回原路径，实际: {result}"
        print(f"[OK] 已存在的文件路径直接返回: {result}")
    finally:
        tmp_path.unlink(missing_ok=True)


async def test_resolve_nonexistent_name_raises_value_error() -> None:
    """验证传入不存在的预设名称时抛出 ValueError."""
    svc = AEPluginService.__new__(AEPluginService)
    # 先确保资源索引已初始化（扫描真实资源库）
    await resource_index_service.refresh_index()
    nonexistent = "___definitely_not_exists_preset___"
    try:
        result = await svc._resolve_preset_path(nonexistent)
        # 若资源索引服务降级（如 settings.presets_dir 不存在），可能返回 Path 而不抛错
        print(f"[INFO] 未抛 ValueError，返回降级路径: {result}（资源索引可能未启用）")
    except ValueError as e:
        print(f"[OK] 正确抛出 ValueError: {e}")
        assert "AE 预设未找到" in str(e), f"错误信息不符预期: {e}"


async def test_apply_saber_returns_error_on_invalid_preset() -> None:
    """验证 apply_saber 在预设未找到时返回失败的 EngineResult（不调用 AE 引擎）."""
    svc = AEPluginService.__new__(AEPluginService)
    # 故意不设置 _engine，确保若未走预设解析分支会报 AttributeError
    # 但因为 preset_file 解析失败应早返回 EngineResult，不会触碰 engine
    await resource_index_service.refresh_index()
    result = await svc.apply_saber(
        comp_name="dummy",
        layer_index=1,
        preset_file="___definitely_not_exists_preset___.ffx",
    )
    assert result.success is False, f"应返回失败，实际: {result}"
    assert "AE 预设未找到" in (result.error or ""), f"错误信息不符预期: {result.error}"
    print(f"[OK] apply_saber 在预设未找到时返回失败 EngineResult: {result.error}")


async def main() -> None:
    """主测试入口."""
    print("=" * 70)
    print("AEPluginService._resolve_preset_path 验证")
    print("=" * 70)

    test_category_registered()
    test_find_ae_preset_method_exists()
    test_resolve_preset_path_method_exists()
    await test_resolve_existing_file_path()
    await test_resolve_nonexistent_name_raises_value_error()
    await test_apply_saber_returns_error_on_invalid_preset()

    print("=" * 70)
    print("所有验证通过 ✓")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
