"""
AE MCP 客户端使用示例
======================

展示 AEMCPClient 的各种用法，包括：
1. 基础连接与心跳检测
2. 查询类方法
3. 合成管理
4. 图层创建与属性设置
5. 动画与关键帧
6. 效果应用
7. 流式构建接口
8. 错误处理
9. 异步命令
10. 调用统计
"""

from __future__ import annotations

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from ae.ae_mcp_client import (
    AEMCPClient,
    AEMCPError,
    AEConnectionError,
    AECommandError,
    AENotFoundError,
    CompositionBuilder,
    LayerBuilder,
    EffectStack,
    BlendMode,
    TrackMatteType,
    EasingType,
    create_client,
)


BRIDGE_DIR = r"C:\Users\Administrator\Documents\ae-mcp-bridge"


def example_1_basic_connection() -> None:
    """示例 1：基础连接与心跳检测"""
    print("=" * 60)
    print("示例 1：基础连接与心跳检测")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)

    print("检测 AE 是否运行...")
    if client.is_alive():
        print("✓ AE 运行正常")
        result = client.ping()
        print(f"  AE 版本: {result.get('appVersion', '未知')}")
    else:
        print("✗ AE 未运行或无响应")

    print()


def example_2_query_methods() -> None:
    """示例 2：查询类方法"""
    print("=" * 60)
    print("示例 2：查询类方法")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        project_info = client.get_project_info()
        print(f"项目名称: {project_info.get('projectName', '未命名')}")
        print(f"项目路径: {project_info.get('path', '未保存')}")
        print(f"项目条目数: {project_info.get('numItems', 0)}")

        comps = client.list_compositions()
        print(f"\n合成数量: {len(comps)}")
        for comp in comps[:5]:
            print(f"  - {comp.name} ({comp.width}x{comp.height}, {comp.frame_rate}fps, {comp.duration:.2f}s)")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_3_composition_management() -> None:
    """示例 3：合成管理"""
    print("=" * 60)
    print("示例 3：合成管理")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        comp_name = "Demo_Comp"
        print(f"创建合成: {comp_name}")
        result = client.create_composition(
            name=comp_name,
            width=1920,
            height=1080,
            duration=5.0,
            frame_rate=30.0,
            bg_color=[0.1, 0.1, 0.1],
        )
        print(f"✓ 合成创建成功: {result.get('name')}")

        print(f"\n修改合成设置...")
        result = client.set_composition_settings(
            comp_name=comp_name,
            duration=10.0,
        )
        print(f"✓ 合成设置已更新")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_4_layer_creation() -> None:
    """示例 4：图层创建与属性设置"""
    print("=" * 60)
    print("示例 4：图层创建与属性设置")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)
    comp_name = "Demo_Comp"

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("创建文字图层...")
        result = client.create_text_layer(
            comp_name=comp_name,
            text="Hello World",
            layer_name="Title",
            font_size=72,
            fill_color=[1, 1, 1],
            position=[960, 540],
        )
        print(f"✓ 文字图层创建成功: {result.get('layer', '未知')}")

        print("\n创建固态层...")
        result = client.create_solid_layer(
            comp_name=comp_name,
            layer_name="Background",
            color=[0.2, 0.3, 0.5],
        )
        print(f"✓ 固态层创建成功")

        print("\n创建形状图层...")
        result = client.create_shape_layer(
            comp_name=comp_name,
            shape_type="ellipse",
            layer_name="Circle",
            fill_color=[1, 0.5, 0],
            size=[200, 200],
            position=[300, 300],
        )
        print(f"✓ 形状图层创建成功")

        print("\n添加调整图层...")
        result = client.add_adjustment_layer(
            comp_name=comp_name,
            layer_name="Adjustment",
        )
        print(f"✓ 调整图层添加成功")

        print("\n设置图层属性...")
        result = client.set_layer_properties(
            comp_name=comp_name,
            layer_name="Title",
            properties={
                "position": [960, 400],
                "scale": [120, 120],
                "opacity": 80,
            },
        )
        print(f"✓ 图层属性已更新")

        print("\n设置混合模式...")
        result = client.set_blend_mode(
            comp_name=comp_name,
            layer_name="Circle",
            blend_mode=BlendMode.ADD,
        )
        print(f"✓ 混合模式已设置为 ADD")

        print("\n设置运动模糊...")
        result = client.set_motion_blur(
            comp_name=comp_name,
            layer_name="Circle",
            enabled=True,
        )
        print(f"✓ 运动模糊已启用")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_5_animation_keyframes() -> None:
    """示例 5：动画与关键帧"""
    print("=" * 60)
    print("示例 5：动画与关键帧")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)
    comp_name = "Demo_Comp"

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("添加位移动画关键帧...")
        client.set_layer_keyframe(
            comp_name=comp_name,
            layer_name="Circle",
            property_name="Position",
            time=0.0,
            value=[200, 540],
            easing=EasingType.EASE_OUT,
        )
        client.set_layer_keyframe(
            comp_name=comp_name,
            layer_name="Circle",
            property_name="Position",
            time=2.0,
            value=[1720, 540],
            easing=EasingType.EASE_IN,
        )
        print("✓ 位移动画关键帧已添加")

        print("\n添加缩放动画关键帧...")
        client.set_layer_keyframe(
            comp_name=comp_name,
            layer_name="Title",
            property_name="Scale",
            time=0.0,
            value=[0, 0],
        )
        client.set_layer_keyframe(
            comp_name=comp_name,
            layer_name="Title",
            property_name="Scale",
            time=1.0,
            value=[120, 120],
            easing=EasingType.EASE_OUT,
        )
        print("✓ 缩放动画关键帧已添加")

        print("\n添加表达式...")
        client.set_layer_expression(
            comp_name=comp_name,
            layer_name="Circle",
            property_name="Rotation",
            expression="time * 50",
        )
        print("✓ 旋转表达式已添加")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_6_effects() -> None:
    """示例 6：效果应用"""
    print("=" * 60)
    print("示例 6：效果应用")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)
    comp_name = "Demo_Comp"

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("应用高斯模糊效果...")
        result = client.apply_effect(
            comp_name=comp_name,
            layer_name="Adjustment",
            effect_name="高斯模糊",
            properties={"Blurriness": 10},
        )
        print(f"✓ 高斯模糊效果已应用")

        print("\n设置效果属性...")
        result = client.set_effect_property(
            comp_name=comp_name,
            layer_name="Adjustment",
            effect_name="高斯模糊",
            property_name="Blurriness",
            value=20,
        )
        print(f"✓ 效果属性已更新")

        print("\n查看图层效果列表...")
        effects = client.list_effects(comp_name, "Adjustment")
        for effect in effects:
            print(f"  - {effect.name} (启用: {effect.enabled})")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_7_composition_builder() -> None:
    """示例 7：流式构建接口 - CompositionBuilder"""
    print("=" * 60)
    print("示例 7：流式构建接口 - CompositionBuilder")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("使用 CompositionBuilder 流式构建合成...")
        result = (
            CompositionBuilder(client, "Builder_Demo")
            .size(1280, 720)
            .duration(8.0)
            .fps(30)
            .bg_color([0.05, 0.05, 0.1])
            .add_solid_layer("BG", [0.1, 0.1, 0.2])
            .add_text_layer("MainTitle", "Streamlined AE", font_size=64, fill_color=[1, 1, 1], position=[640, 300])
            .add_shape_layer("Logo", "ellipse", fill_color=[0, 0.8, 1], size=[100, 100], position=[640, 500])
            .add_adjustment_layer("FX")
            .add_null_layer("Controller")
            .build()
        )
        print(f"✓ 合成构建成功: {result['composition'].get('name')}")
        print(f"  图层数量: {len(result['layers'])}")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_8_layer_builder() -> None:
    """示例 8：流式构建接口 - LayerBuilder"""
    print("=" * 60)
    print("示例 8：流式构建接口 - LayerBuilder")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)
    comp_name = "Builder_Demo"

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("使用 LayerBuilder 配置图层...")
        result = (
            LayerBuilder(client, comp_name, "MainTitle")
            .position([640, 200])
            .scale([100, 100])
            .opacity(100)
            .blend_mode(BlendMode.NORMAL)
            .keyframe("Position", 0, [-200, 200], easing=EasingType.EASE_OUT)
            .keyframe("Position", 1, [640, 200], easing=EasingType.EASE_OUT)
            .keyframe("Opacity", 0, 0)
            .keyframe("Opacity", 0.5, 100)
            .expression("Rotation", "Math.sin(time * 2) * 5")
            .apply_effect("高斯模糊", {"Blurriness": 0})
            .build()
        )
        print(f"✓ 图层配置完成")
        print(f"  属性设置: {'成功' if 'properties' in result else '跳过'}")
        print(f"  关键帧: {'成功' if 'keyframes' in result else '跳过'}")
        print(f"  效果: {len(result.get('effects', []))} 个")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_9_effect_stack() -> None:
    """示例 9：效果栈管理器 - EffectStack"""
    print("=" * 60)
    print("示例 9：效果栈管理器 - EffectStack")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)
    comp_name = "Builder_Demo"

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("使用 EffectStack 批量应用效果...")
        stack = EffectStack(client, comp_name, "FX")
        result = (
            stack
            .add("色阶", {"Input Black": 10, "Input White": 245})
            .add("曲线")
            .add("高斯模糊", {"Blurriness": 2})
            .apply()
        )
        print(f"✓ 批量效果应用完成")

        print("\n查看已应用的效果...")
        effects = stack.list_effects()
        for effect in effects:
            print(f"  - {effect.name}")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_10_error_handling() -> None:
    """示例 10：错误处理"""
    print("=" * 60)
    print("示例 10：错误处理")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("尝试访问不存在的合成...")
        client.get_layer_info("NonExistentComp")
    except AENotFoundError as e:
        print(f"✓ 捕获到资源不存在异常: {e.message}")
    except AEConnectionError as e:
        print(f"✗ 连接错误: {e}")
    except AECommandError as e:
        print(f"✗ 命令错误: {e}")
    except AEMCPError as e:
        print(f"✗ 通用错误: {e}")

    print("\n尝试访问不存在的图层...")
    try:
        comps = client.list_compositions()
        if comps:
            client.set_layer_properties(
                comp_name=comps[0].name,
                layer_name="NonExistentLayer",
                properties={"opacity": 50},
            )
    except AENotFoundError as e:
        print(f"✓ 捕获到图层不存在异常: {e.message}")
    except AEMCPError as e:
        print(f"其他错误: {e}")

    print()


def example_11_async_commands() -> None:
    """示例 11：异步命令"""
    print("=" * 60)
    print("示例 11：异步命令")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("发送异步命令...")
        command_id = client.send_command_async(
            command="createComposition",
            params={
                "name": "Async_Comp",
                "width": 1920,
                "height": 1080,
                "duration": 5.0,
                "frameRate": 30,
            },
        )
        print(f"✓ 命令已发送, ID: {command_id}")

        print("\n等待命令完成...")
        result = client.wait_for_completion(command_id, timeout_ms=10000)
        print(f"✓ 命令完成: {result.get('name', '未知')}")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def example_12_stats() -> None:
    """示例 12：调用统计"""
    print("=" * 60)
    print("示例 12：调用统计")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)

    stats = client.get_stats()
    print(f"总调用次数: {stats.total_calls}")
    print(f"成功次数: {stats.success_count}")
    print(f"失败次数: {stats.failure_count}")
    print(f"平均延迟: {stats.avg_latency_ms:.2f}ms")
    print(f"最小延迟: {stats.min_latency_ms:.2f}ms")
    print(f"最大延迟: {stats.max_latency_ms:.2f}ms")

    print("\n重置统计...")
    client.reset_stats()
    stats = client.get_stats()
    print(f"重置后总调用次数: {stats.total_calls}")

    print()


def example_13_track_matte_and_parent() -> None:
    """示例 13：轨道遮罩与父子关系"""
    print("=" * 60)
    print("示例 13：轨道遮罩与父子关系")
    print("=" * 60)

    client = create_client(bridge_dir=BRIDGE_DIR, signature_enabled=False)
    comp_name = "Matte_Demo"

    if not client.is_alive():
        print("AE 未运行，跳过此示例")
        return

    try:
        print("创建演示合成...")
        client.create_composition(
            name=comp_name,
            width=1280,
            height=720,
            duration=5.0,
            bg_color=[0, 0, 0],
        )

        print("创建背景图层...")
        client.create_solid_layer(comp_name, "Background", [0.2, 0.4, 0.8])

        print("创建文字遮罩层...")
        client.create_text_layer(
            comp_name,
            "MASK",
            layer_name="TextMatte",
            font_size=150,
            position=[640, 360],
        )

        print("创建填充图层...")
        client.create_solid_layer(comp_name, "FillLayer", [1, 0.5, 0])

        print("\n设置轨道遮罩...")
        result = client.set_track_matte(
            comp_name=comp_name,
            target_layer="FillLayer",
            matte_layer="TextMatte",
            matte_type=TrackMatteType.ALPHA,
        )
        print(f"✓ 轨道遮罩已设置")

        print("\n创建空对象作为父图层...")
        client.create_null_layer(comp_name, "ParentNull")

        print("设置父子关系...")
        result = client.set_parent_layer(
            comp_name=comp_name,
            child_layer="TextMatte",
            parent_layer="ParentNull",
        )
        print(f"✓ 父子关系已设置")

    except AEMCPError as e:
        print(f"错误: {e}")

    print()


def main() -> None:
    """运行所有示例"""
    print("\n")
    print("╔" + "═" * 58 + "╗")
    print("║" + " " * 10 + "AE MCP 客户端使用示例" + " " * 24 + "║")
    print("╚" + "═" * 58 + "╝")
    print()

    examples = [
        ("基础连接与心跳检测", example_1_basic_connection),
        ("查询类方法", example_2_query_methods),
        ("合成管理", example_3_composition_management),
        ("图层创建与属性设置", example_4_layer_creation),
        ("动画与关键帧", example_5_animation_keyframes),
        ("效果应用", example_6_effects),
        ("CompositionBuilder 流式构建", example_7_composition_builder),
        ("LayerBuilder 图层构建", example_8_layer_builder),
        ("EffectStack 效果栈", example_9_effect_stack),
        ("错误处理", example_10_error_handling),
        ("异步命令", example_11_async_commands),
        ("调用统计", example_12_stats),
        ("轨道遮罩与父子关系", example_13_track_matte_and_parent),
    ]

    for name, func in examples:
        try:
            func()
        except Exception as e:
            print(f"示例执行出错 [{name}]: {e}")
            print()

    print("=" * 60)
    print("所有示例执行完毕")
    print("=" * 60)


if __name__ == "__main__":
    main()
