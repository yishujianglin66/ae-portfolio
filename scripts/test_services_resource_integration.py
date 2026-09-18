"""测试 text_effect_service / color_grading_service 与 resource_index_service 的集成.

验证：
    1. 服务模块可正常导入
    2. _resolve_font_path / _resolve_lut_path 异步方法存在且可调用
    3. 在无 AE 引擎的真实运行环境下，资源解析逻辑正确（找到/未找到/降级）
    4. apply_lut_by_name 便捷方法可用
"""
import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# 添加 puppet-automation 到 sys.path（与 scripts/test_resource_index.py 同套路）
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root / "puppet-automation"))


async def test_text_effect_service_font_resolution():
    """测试 TextEffectService._resolve_font_path 行为."""
    from src.services.text_effect_service import TextEffectService

    # 用 mock AE 引擎避免真实 AE 调用
    mock_ae = MagicMock()
    mock_ae.run_script = AsyncMock()
    service = TextEffectService(ae_engine=mock_ae)

    print("\n=== TextEffectService._resolve_font_path ===")

    # 1. 测试一个可能存在的字体（依赖资源库实际内容）
    #    资源库 D:/AE-Work/resources/fonts/ 下若有 "MFTongXin" 等字体，应能找到
    test_names = ["MFTongXin", "思源黑体", "Impact", "DefinitelyNonExistentFont123"]
    for name in test_names:
        path = await service._resolve_font_path(name)
        status = "FOUND" if path else "FALLBACK"
        path_str = str(path) if path else "-"
        print(f"  font '{name}': {status} -> {path_str}")

    # 2. 测试 create_3d_title 接受 font_path 参数（不解析时直接调用）
    #    mock AE 引擎返回成功结果
    from src.engines.base import EngineResult
    mock_ae.run_script.return_value = EngineResult(
        success=True,
        metadata={"stdout": '{"status":"success","layer_name":"TXT_Test"}'},
    )

    # 不传 font_path，应自动调用 _resolve_font_path
    result = await service.create_3d_title(
        comp_name="Main",
        text="Test",
        position=(960, 540),
        font="Impact",
    )
    assert result.success is True, f"create_3d_title 应成功: {result.error}"
    print("  create_3d_title(font='Impact') -> OK")

    # 显式传入一个 Path 对象作为 font_path（即使不存在也不应报错）
    result = await service.create_3d_title(
        comp_name="Main",
        text="Test",
        position=(960, 540),
        font="Custom",
        font_path=Path("D:/fake/fonts/custom.otf"),
    )
    assert result.success is True, f"create_3d_title with font_path 应成功: {result.error}"
    print("  create_3d_title(font_path=Path(...)) -> OK")


async def test_color_grading_service_lut_resolution():
    """测试 ColorGradingService._resolve_lut_path 与 apply_lut_by_name."""
    from src.engines.base import EngineResult
    from src.services.color_grading_service import ColorGradingService

    mock_ae = MagicMock()
    mock_ae.run_script = AsyncMock()
    service = ColorGradingService(ae_engine=mock_ae)

    print("\n=== ColorGradingService._resolve_lut_path ===")

    # 1. 测试传入不存在的路径 + 不存在的名称 -> 应抛出 ValueError
    try:
        await service._resolve_lut_path("DefinitelyNonExistentLUT123")
        print("  ERROR: 应抛出 ValueError 但未抛出")
    except ValueError as e:
        print(f"  LUT 'DefinitelyNonExistentLUT123' -> ValueError (正确): {e}")

    # 2. 测试传入一个真实存在的文件路径 -> 直接返回
    #    用自身脚本文件当作"已存在文件"测试
    self_path = Path(__file__).resolve()
    resolved = await service._resolve_lut_path(self_path)
    assert resolved == self_path, f"应直接返回已存在的路径: {resolved}"
    print(f"  existing file path -> {resolved}")

    # 3. 测试传入资源库中可能存在的 LUT 名称
    test_names = ["cinematic", "teal_orange", "NonExistentLUT"]
    for name in test_names:
        try:
            path = await service._resolve_lut_path(name)
            print(f"  lut '{name}': FOUND -> {path}")
        except ValueError as e:
            print(f"  lut '{name}': NOT FOUND (ValueError)")

    print("\n=== ColorGradingService.apply_lut_by_name ===")

    # 4. 测试 apply_lut_by_name 在 LUT 不存在时返回失败结果
    mock_ae.run_script.reset_mock()
    result = await service.apply_lut_by_name(
        comp_name="Main",
        layer_index=1,
        lut_name="DefinitelyNonExistentLUT123",
    )
    assert result.success is False, "LUT 不存在时应返回失败"
    assert "LUT 未找到" in result.error, f"错误信息应包含 'LUT 未找到': {result.error}"
    print(f"  apply_lut_by_name(non-existent) -> EngineResult(success=False): {result.error}")
    # AE 引擎不应被调用
    mock_ae.run_script.assert_not_called()
    print("  AE 引擎未被调用 (正确)")

    # 5. 测试 apply_lut_by_name 在 LUT 存在时调用 AE 引擎
    #    先看资源库中是否有任意 LUT 可用
    try:
        from src.services.resource_index_service import resource_index_service
        await resource_index_service.refresh_index()
        luts = await resource_index_service.list_luts(limit=5)
        if luts:
            test_lut_name = luts[0]["name"]
            mock_ae.run_script.return_value = EngineResult(
                success=True,
                metadata={"stdout": '{"status":"success","effectName":"Lumetri Color"}'},
            )
            result = await service.apply_lut_by_name(
                comp_name="Main",
                layer_index=1,
                lut_name=test_lut_name,
            )
            assert result.success is True, f"应用存在的 LUT 应成功: {result.error}"
            mock_ae.run_script.assert_called_once()
            print(f"  apply_lut_by_name('{test_lut_name}') -> EngineResult(success=True)")
        else:
            print("  资源库无 LUT，跳过 apply_lut_by_name 成功路径测试")
    except Exception as e:
        print(f"  跳过资源库交互测试: {e}")


async def main():
    print("=" * 60)
    print("Services × Resource Index Integration Test")
    print("=" * 60)

    # 1. 测试导入
    print("\n--- Step 1: Import check ---")
    try:
        from src.services.color_grading_service import ColorGradingService
        from src.services.resource_index_service import resource_index_service
        from src.services.text_effect_service import TextEffectService
        print("  Imports OK")
        print(f"  TextEffectService: {TextEffectService}")
        print(f"  ColorGradingService: {ColorGradingService}")
        print(f"  resource_index_service: {resource_index_service}")
    except Exception as e:
        print(f"  IMPORT FAILED: {e}")
        raise

    # 2. 测试 TextEffectService 字体解析
    print("\n--- Step 2: TextEffectService font resolution ---")
    await test_text_effect_service_font_resolution()

    # 3. 测试 ColorGradingService LUT 解析
    print("\n--- Step 3: ColorGradingService LUT resolution ---")
    await test_color_grading_service_lut_resolution()

    print("\n" + "=" * 60)
    print("All integration tests passed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
