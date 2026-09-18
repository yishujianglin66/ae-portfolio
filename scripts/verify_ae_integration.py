#!/usr/bin/env python3
"""
验证 AE 资源索引服务和引擎层集成
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "puppet-automation" / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


async def main() -> None:
    print("=== AE 项目集成验证 ===\n")

    # 1. 验证配置
    print("[1/4] 验证配置加载...")
    try:
        from config import settings
        print(f"  AE 2025 路径: {settings.ae_2025_path}")
        print(f"  aerender 路径: {settings.aerender_path}")
        print(f"  aerender 存在: {settings.aerender_path.exists()}")
        print(f"  资源库根目录: {settings.resources_dir}")
        print(f"  资源库存在: {settings.resources_dir.exists()}")
        print(f"  脚本目录: {settings.scripts_dir} 存在={settings.scripts_dir.exists()}")
        print(f"  插件目录: {settings.plugins_dir} 存在={settings.plugins_dir.exists()}")
        print(f"  模板目录: {settings.templates_dir} 存在={settings.templates_dir.exists()}")
        print(f"  图片目录: {settings.images_dir} 存在={settings.images_dir.exists()}")
        print("  OK")
    except Exception as e:
        print(f"  失败: {e}")
    print()

    # 2. 验证资源索引服务
    print("[2/4] 验证资源索引服务...")
    try:
        from services.resource_index_service import resource_index_service
        print("  资源索引服务单例创建成功")

        summary = resource_index_service.get_index_summary()
        if summary:
            print(f"  已初始化: {resource_index_service.is_initialized()}")
            print(f"  资源总数: {resource_index_service.get_total_count()}")
            for cat, count in summary.items():
                print(f"    {cat}: {count}")
        else:
            print("  索引尚未初始化，开始构建...")
            await resource_index_service.refresh_index()
            print("  索引构建完成")
            summary = resource_index_service.get_index_summary()
            print(f"  资源总数: {resource_index_service.get_total_count()}")
            for cat, count in sorted(summary.items()):
                print(f"    {cat}: {count}")

        # 测试查找
        font = await resource_index_service.find_font("华文中宋")
        print(f"  字体查找测试 (华文中宋): {font}")
        print("  OK")
    except Exception as e:
        import traceback
        print(f"  失败: {e}")
        traceback.print_exc()
    print()

    # 3. 验证 AE 引擎
    print("[3/4] 验证 AE 引擎...")
    try:
        from engines.ae.engine import AEEngine
        ae = AEEngine()
        print(f"  引擎名称: {ae.name}")
        print(f"  可执行文件: {ae.executable_path}")
        print(f"  可执行文件存在: {ae.executable_path.exists()}")
        print("  OK")
    except Exception as e:
        import traceback
        print(f"  失败: {e}")
        traceback.print_exc()
    print()

    # 4. 资源库完整度
    print("[4/4] 资源库完整度评估...")
    categories = {
        "fonts": ("字体", 5000),
        "luts": ("LUT 调色", 8000),
        "audio": ("音频音效", 2000),
        "effects": ("特效贴图", 9000),
        "psd": ("PSD 素材", 300),
        "models": ("3D 模型", 3),
        "davinci": ("达芬奇插件", 90),
        "premiere": ("PR 预设", 120),
        "projects": ("AE 工程", 12),
        "ae_presets": ("AE 预设", 0),
        "scripts": ("AE 脚本", 0),
        "plugins": ("插件包", 0),
        "templates": ("模板", 0),
        "images": ("图片素材", 0),
        "video": ("视频素材", 0),
    }
    try:
        summary = resource_index_service.get_index_summary()
        total = 0
        completed = 0
        for cat, (name, expected) in categories.items():
            actual = summary.get(cat, 0)
            total += 1
            if actual > 0:
                completed += 1
            status = "✅" if actual > 0 else "❌"
            expected_str = f" (预期 ~{expected})" if expected > 0 else ""
            print(f"  {status} {name} ({cat}): {actual} 个{expected_str}")
        print()
        print(f"  完整度: {completed}/{total} 类别有资源 ({completed/total*100:.1f}%)")
    except Exception as e:
        print(f"  评估失败: {e}")
    print()

    print("=== 验证完成 ===")


if __name__ == "__main__":
    asyncio.run(main())
