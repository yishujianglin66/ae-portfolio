"""
TextEffectService 使用示例
=========================

本示例展示如何使用 TextEffectService 创建高级文字效果。
"""

import asyncio
from pathlib import Path

# 导入服务
from src.services.text_effect_service import TextEffectService
from src.engines.ae.engine import AEEngine


async def example_1_create_simple_title():
    """示例 1：创建简单的 3D 标题"""
    service = TextEffectService()

    # 创建基础文字层
    result = await service.create_3d_title(
        comp_name="Main Comp",
        text="EPIC TITLE",
        position=(960, 540),
        style="epic3D",
        font="Impact",
        font_size=150,
        fill_color="#FFFFFF",
        stroke_color="#000000",
        stroke_width=10,
    )

    if result.success:
        print(f"✓ 创建标题成功: {result.metadata}")
    else:
        print(f"✗ 创建标题失败: {result.error}")


async def example_2_create_full_title_system():
    """示例 2：创建完整的文字系统（主层 + GLOW + RGB + GRAD）"""
    service = TextEffectService()

    # 一键创建完整文字系统
    result = await service.create_full_title_system(
        comp_name="Main Comp",
        text="AWESOME TITLE",
        position=(960, 540),
        style="epic3D",
        font_size=140,
        fill_color="#FFFFFF",
        stroke_color="#000000",
        glow_color="#00FFFF",  # 青色辉光
        glow_intensity=0.8,
        rgb_offset=6,  # RGB 分离 ±6px
        gradient_colors=["#FF6600", "#0066FF"],  # 橙到蓝渐变
    )

    if result.success:
        print(f"✓ 完整文字系统创建成功")
        print(f"  图层架构: {result.metadata['architecture']}")
        print(f"  创建图层数: {result.metadata['layers_created']}")
    else:
        print(f"✗ 创建失败: {result.error}")


async def example_3_apply_neon_effect():
    """示例 3：应用霓虹发光效果（参考知识库预设）"""
    service = TextEffectService()

    # 先创建基础文字层
    await service.create_3d_title(
        comp_name="Main Comp",
        text="NEON",
        position=(960, 540),
        font_size=200,
    )

    # 应用霓虹效果
    result = await service.apply_neon_effect(
        comp_name="Main Comp",
        text_layer_index=0,
        glow_size=25,
        glow_intensity=1.5,
        flicker=0.3,  # 闪烁幅度
        color="#00FFFF",  # 青色霓虹
    )

    if result.success:
        print(f"✓ 霓虹效果应用成功")


async def example_4_apply_text_animation():
    """示例 4：应用打字机动画效果"""
    service = TextEffectService()

    # 先创建文字层
    await service.create_3d_title(
        comp_name="Main Comp",
        text="Typewriter Effect",
        position=(960, 540),
    )

    # 应用打字机动画
    result = await service.apply_text_animation(
        comp_name="Main Comp",
        text_layer_index=0,
        animation_type="typewriter",
        duration=2.0,  # 2秒完成
        stagger=0.05,  # 每字延迟 0.05s
    )

    if result.success:
        print(f"✓ 打字机动画应用成功")


async def example_5_combined_workflow():
    """示例 5：组合工作流 - 创建标题 + 发光 + RGB分离 + 动画"""
    service = TextEffectService()

    # 步骤 1: 创建主文字层
    result = await service.create_3d_title(
        comp_name="Main Comp",
        text="COMPLEX TITLE",
        position=(960, 540),
        style="cinematic",
        font_size=130,
    )

    if not result.success:
        print(f"✗ 主层创建失败: {result.error}")
        return

    # 等待 AE 处理
    await asyncio.sleep(0.2)

    # 步骤 2: 添加 GLOW 辉光层
    result = await service.apply_glow_layer(
        comp_name="Main Comp",
        text_layer_index=0,
        glow_color="#FF00FF",  # 品红色辉光
        glow_intensity=0.6,
        blur_radius=30,
    )

    # 等待
    await asyncio.sleep(0.2)

    # 步骤 3: 添加 RGB 分离效果
    result = await service.apply_rgb_separation(
        comp_name="Main Comp",
        text_layer_index=0,
        offset_x=8,  # ±8px 偏移
        offset_y=2,  # 略微垂直偏移
    )

    # 等待
    await asyncio.sleep(0.2)

    # 步骤 4: 应用打字机动画
    result = await service.apply_text_animation(
        comp_name="Main Comp",
        text_layer_index=4,  # 原始文字层（现在在底层）
        animation_type="typewriter",
        duration=1.5,
    )

    print(f"✓ 组合工作流完成")


async def example_6_style_presets():
    """示例 6：使用不同的字体预设"""
    service = TextEffectService()

    styles = ["cinematic", "epic", "elegant", "modern", "tech"]

    for i, style in enumerate(styles):
        result = await service.create_3d_title(
            comp_name="Main Comp",
            text=f"{style.upper()} STYLE",
            position=(960, 200 + i * 150),  # 垂直排列
            style=style,
            font_size=80,
        )

        if result.success:
            print(f"✓ {style} 风格创建成功")
            await asyncio.sleep(0.1)  # 短暂延迟


async def example_7_color_variations():
    """示例 7：颜色变化效果"""
    service = TextEffectService()

    colors = [
        ("#FF0000", "Red Glow"),
        ("#00FF00", "Green Glow"),
        ("#0000FF", "Blue Glow"),
        ("#FF00FF", "Magenta Glow"),
        ("#00FFFF", "Cyan Glow"),
    ]

    for i, (color, name) in enumerate(colors):
        # 创建文字层
        result = await service.create_3d_title(
            comp_name="Main Comp",
            text=name,
            position=(960, 150 + i * 120),
            font_size=60,
        )

        if result.success:
            # 添加对应颜色的辉光
            await service.apply_glow_layer(
                comp_name="Main Comp",
                text_layer_index=0,
                glow_color=color,
                glow_intensity=0.7,
            )
            await asyncio.sleep(0.1)


async def main():
    """运行所有示例"""
    print("=" * 60)
    print("TextEffectService 使用示例")
    print("=" * 60)

    # 选择要运行的示例（取消注释即可运行）

    # await example_1_create_simple_title()
    # await example_2_create_full_title_system()
    # await example_3_apply_neon_effect()
    # await example_4_apply_text_animation()
    # await example_5_combined_workflow()
    # await example_6_style_presets()
    # await example_7_color_variations()

    print("\n所有示例完成！")


if __name__ == "__main__":
    asyncio.run(main())


"""
与知识库预设的对应关系
======================

本服务实现的核心功能与知识库预设的对应关系：

1. create_3d_title() 对应：
   - 竖屏大字标题（知识库预设 9）
   - 3D 标题基础架构

2. apply_glow_layer() 对应：
   - GLOW_ 辉光层（高级文字系统架构）
   - 霓虹效果基础

3. apply_rgb_separation() 对应：
   - RGB_R_/RGB_C_ 红青分离层
   - 故障风效果基础

4. apply_gradient_overlay() 对应：
   - GRAD_ 渐变层（Alpha Matte 蒙版）
   - 彩虹渐变标题（知识库预设 8）

5. create_full_title_system() 对应：
   - 高级文字系统完整架构：
     * TXT_ 主文字层（填充+描边+Drop Shadow）
     * GLOW_ 辉光层（复制+Fast Blur+ADD 混合）
     * RGB_R_/RGB_C_ 分离层（±6px 偏移+SCREEN 混合）
     * GRAD_ 渐变层（Alpha Matte 蒙版）

6. apply_neon_effect() 对应：
   - 竖屏霓虹标题（知识库预设 3）
   - Glow 效果 + 闪烁动画

7. apply_text_animation() 对应：
   - 打字机效果（入场动画基础篇）
   - 逐字淡入效果

图层顺序约定
============
从上到下：
1. GRAD_ 渐变层（最上层）
2. RGB_C_ 青色分离层
3. RGB_R_ 红色分离层
4. GLOW_ 辉光层
5. TXT_ 主文字层（最下层）

字体预设库
==========
- cinematic: Impact, tracking 80, bold（电影感）
- epic: Impact, tracking 100, bold（史诗感）
- elegant: Georgia, tracking 40, normal（优雅）
- modern: Arial, tracking 60, bold（现代）
- tech: Courier New, tracking 50, bold（科技感）
- japanese: MS Gothic, tracking 30, normal（日式）
- brush: Brush Script MT, tracking 20, normal（手写）
- display: Impact, tracking 90, bold（展示）

颜色格式
========
所有颜色参数均支持 HEX 格式（如 "#FF0000"）
"""