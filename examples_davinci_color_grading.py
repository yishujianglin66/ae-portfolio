#!/usr/bin/env python3
"""
DaVinci Resolve Color 页面调色自动化 — 完整使用示例
=================================================

本脚本展示 8+ 个典型用法，覆盖：

1. 单色轮通道控制（Lift / Gamma / Gain / Offset）
2. 应用内置预设（电影感青橙、复古胶片、音乐 MV 冲击感等）
3. 节点图管理（添加并行节点、删除、混合透明度、标签）
4. 自定义曲线（Custom、HueVsHue 等）
5. Qualifier 限定器选择
6. LUT 应用与导出
7. 批量调色（多片段范围调色 + 复制调色）
8. 预设保存与加载
9. 与 ``ResolveColorEngine`` 集成
10. Lua/Fuscript 桥接（无 Python API 时降级方案）

运行方式::

    python examples_davinci_color_grading.py --demo 1
    python examples_davinci_color_grading.py --demo all

本示例默认不会真正修改你的 Resolve 工程。``--apply`` 参数才会触发实际写入。
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict


# 把项目根目录加入 sys.path，便于独立运行
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from integrations.davinci_color_grading import (  # noqa: E402
    ColorBalanceType,
    ColorGrader,
    ColorGradingPreset,
    ColorWheelChannel,
    ColorWheelValues,
    CurveType,
    NodeType,
    ResolveNotFoundError,
)
from integrations.color_presets import (  # noqa: E402
    BUILTIN_PRESETS,
    get_preset,
    list_preset_names,
    load_preset_from_file,
    save_preset_to_file,
)


# ============================================================================
# Mock Resolve 工具（用于无 Resolve 环境演示）
# ============================================================================

def make_mock_resolve() -> Any:
    """构造一个 Mock Resolve 对象，用于无 Resolve 环境演示。

    通过 :class:`unittest.mock.MagicMock` 自动响应所有方法调用，
    让 :class:`ColorGrader` 不会因属性缺失而报错。
    """
    from unittest.mock import MagicMock

    resolve = MagicMock()
    resolve.GetProductName.return_value = "DaVinci Resolve Studio (Mock)"

    project = MagicMock()
    timeline = MagicMock()
    item = MagicMock()
    second_item = MagicMock()
    third_item = MagicMock()
    fourth_item = MagicMock()

    # 节点与色轮：返回合理的初始值
    for it in (item, second_item, third_item, fourth_item):
        it.GetNodeColorWheels.return_value = {
            "Red": 0.0, "Green": 0.0, "Blue": 0.0, "Master": 0.0,
        }
        it.GetNumNodes.return_value = 1
        it.AddNode.return_value = 1
        it.DeleteNode.return_value = True
        it.SetNodeOpacity.return_value = True
        it.SetNodeLabel.return_value = True
        it.SetSaturation.return_value = True
        it.SetContrast.return_value = True
        it.SetPivot.return_value = True
        it.SetCustomCurve.return_value = True
        it.GetCustomCurve.return_value = []
        it.SetQualifier.return_value = True
        it.SetLUT.return_value = True
        it.ExportLUT.return_value = True
        it.GetSaturation.return_value = 1.0
        it.GetContrast.return_value = 1.0

    timeline.GetItemListInTrack.return_value = [item, second_item, third_item, fourth_item]
    project.GetCurrentTimeline.return_value = timeline
    project.GetCurrentProject.return_value = project

    pm = MagicMock()
    pm.GetCurrentProject.return_value = project
    pm.LoadProject.return_value = project
    resolve.GetProjectManager.return_value = pm

    return resolve, item


# ============================================================================
# 演示函数
# ============================================================================

def demo_1_color_wheel_control(grader: ColorGrader) -> None:
    """1) 单色轮通道控制：手动设置 Lift / Gamma / Gain。"""
    print("\n" + "=" * 60)
    print("Demo 1: 单色轮通道控制（Lift / Gamma / Gain）")
    print("=" * 60)

    # 阴影（lift）增加蓝色
    lift = ColorWheelValues(red=-0.02, green=0.01, blue=0.04, master=-0.02)
    grader.set_color_wheel(0, 0, ColorWheelChannel.LIFT, lift)
    print(f"  [OK] Set Lift: {lift.to_dict()}")

    # 中间调（gamma）增加红色
    gamma = ColorWheelValues(red=0.05, green=0.0, blue=-0.04)
    grader.set_color_wheel(0, 0, ColorWheelChannel.GAMMA, gamma)
    print(f"  [OK] Set Gamma: {gamma.to_dict()}")

    # 高光（gain）增加暖色
    gain = ColorWheelValues(red=0.08, green=0.02, blue=-0.05, master=0.02)
    grader.set_color_wheel(0, 0, ColorWheelChannel.GAIN, gain)
    print(f"  [OK] Set Gain: {gain.to_dict()}")

    # 读回验证
    current = grader.get_color_wheel(0, 0, ColorWheelChannel.LIFT)
    print(f"  [READ] Lift now: {current.to_dict()}")


def demo_2_apply_builtin_presets(grader: ColorGrader) -> None:
    """2) 应用内置预设：电影感 / 复古 / 高调 / 暗调 / MV / 黑白。"""
    print("\n" + "=" * 60)
    print("Demo 2: 应用内置预设（覆盖多种风格）")
    print("=" * 60)

    print("可用内置预设：", list_preset_names())
    for idx, key in enumerate(list_preset_names()):
        preset = get_preset(key)
        if not preset:
            continue
        ok = grader.apply_preset(idx % 4, 0, preset)
        print(f"  [{key}] -> clip {idx % 4} node 0: {'OK' if ok else 'FAIL'}")
        print(f"      {preset.summary()}")


def demo_3_node_graph_management(grader: ColorGrader) -> None:
    """3) 节点图管理：添加并行节点、删除、设置透明度与标签。"""
    print("\n" + "=" * 60)
    print("Demo 3: 节点图管理")
    print("=" * 60)

    before = grader.get_node_count(0)
    print(f"  当前节点数: {before}")

    new_idx = grader.add_node(0, NodeType.PARALLEL, label="Qualifier-Skin")
    print(f"  添加 PARALLEL 节点 -> index={new_idx}")

    new_idx2 = grader.add_node(0, NodeType.LAYER, label="Color-Wheels")
    print(f"  添加 LAYER 节点 -> index={new_idx2}")

    grader.set_node_opacity(0, new_idx, 0.85)
    print(f"  设置节点 {new_idx} opacity=0.85")

    after = grader.get_node_count(0)
    print(f"  最终节点数: {after}")


def demo_4_custom_curves(grader: ColorGrader) -> None:
    """4) 自定义曲线：Custom 曲线 + HueVsHue 曲线。"""
    print("\n" + "=" * 60)
    print("Demo 4: 自定义曲线")
    print("=" * 60)

    # Custom 曲线：S 形对比度
    s_curve = [0.0, 0.0, 0.25, 0.15, 0.5, 0.5, 0.75, 0.85, 1.0, 1.0]
    grader.set_custom_curve(0, 0, CurveType.CUSTOM, s_curve)
    print(f"  [OK] Set Custom curve (S-curve), {len(s_curve)//2} 控制点")

    # HueVsHue：把蓝色往青色偏移
    hue_shift = [0.0, 0.0, 0.5, 0.55, 0.7, 0.78, 1.0, 1.0]
    grader.set_custom_curve(0, 0, CurveType.HUE_VS_HUE, hue_shift)
    print(f"  [OK] Set HueVsHue curve, {len(hue_shift)//2} 控制点")

    # 读取曲线
    current = grader.get_custom_curve(0, 0, CurveType.CUSTOM)
    print(f"  [READ] Custom curve length: {len(current)}")


def demo_5_qualifier_selection(grader: ColorGrader) -> None:
    """5) Qualifier 限定器：选择蓝色天空区域。"""
    print("\n" + "=" * 60)
    print("Demo 5: Qualifier 限定器（选蓝色天空 + 反选）")
    print("=" * 60)

    # 选蓝色（Hue 180-230）
    ok = grader.select_with_qualifier(
        clip_index=0, node_index=0,
        hue_range=(180.0, 230.0),
        sat_range=(0.3, 1.0),
        lum_range=(0.3, 0.9),
    )
    print(f"  [OK] Qualifier hue=180~230, sat=0.3~1.0, lum=0.3~0.9: {ok}")

    # 反选
    ok_inv = grader.invert_selection(0, 0)
    print(f"  [OK] Invert selection: {ok_inv}")


def demo_6_lut_operations(grader: ColorGrader, tmp_dir: Path) -> None:
    """6) LUT 操作：应用 LUT、导出 LUT。"""
    print("\n" + "=" * 60)
    print("Demo 6: LUT 应用与导出")
    print("=" * 60)

    # 模拟 LUT 文件路径
    fake_lut = tmp_dir / "demo_lut.cube"
    fake_lut.write_text("# Demo cube file\n")
    ok = grader.apply_lut(0, 0, str(fake_lut))
    print(f"  [OK] Apply LUT: {ok}")

    out_lut = tmp_dir / "exported.cube"
    ok = grader.export_lut(0, 0, out_lut, cube_size=17)
    print(f"  [OK] Export LUT to {out_lut}: {ok}")


def demo_7_batch_grade(grader: ColorGrader) -> None:
    """7) 批量调色：多片段范围调色 + 复制调色。"""
    print("\n" + "=" * 60)
    print("Demo 7: 批量调色（多片段 + 复制）")
    print("=" * 60)

    preset = get_preset("cinematic_teal_orange")
    if preset is None:
        print("  [SKIP] Preset not found")
        return

    # 范围调色（应用 4 个片段）
    results = grader.grade_clip_range([0, 1, 2, 3], node_index=0, preset=preset)
    print(f"  [OK] Batch grade: {results}")

    # 复制调色（从片段 0 复制到 1, 2, 3）
    copies = grader.copy_grading(source_clip_index=0, target_clip_indices=[1, 2, 3])
    print(f"  [OK] Copy grade: {copies}")


def demo_8_preset_persistence(grader: ColorGrader, tmp_dir: Path) -> None:
    """8) 预设保存与加载：JSON 落盘、读取。"""
    print("\n" + "=" * 60)
    print("Demo 8: 预设保存与加载")
    print("=" * 60)

    # 自定义预设
    custom = ColorGradingPreset(
        name="My-Custom-Look",
        description="自定义调色样例",
        lift=ColorWheelValues(red=0.01, green=-0.02, blue=0.03, master=0.01),
        gain=ColorWheelValues(red=0.05, green=0.0, blue=-0.03, master=0.02),
        saturation=1.2,
        contrast=1.05,
        tags=["custom", "demo"],
    )

    preset_file = tmp_dir / "my_custom.json"
    grader.save_preset_to_file(custom, preset_file)
    print(f"  [OK] Saved preset: {preset_file}")

    loaded = grader.load_preset_from_file(preset_file)
    print(f"  [OK] Loaded preset: {loaded.summary()}")

    # 从内置预设库加载
    builtin = get_preset("vintage_film")
    if builtin:
        print(f"  [INFO] Builtin preset 'vintage_film' tags: {builtin.tags}")


def demo_9_engine_integration(tmp_dir: Path) -> None:
    """9) 与 ``ResolveColorEngine`` 集成：通过 davinci_fuscript 调用。"""
    print("\n" + "=" * 60)
    print("Demo 9: 与 ResolveColorEngine 集成")
    print("=" * 60)

    try:
        from integrations.davinci_fuscript import ResolveColorEngine

        engine = ResolveColorEngine()
        # 在没有真实 Resolve 的环境下，color_grader 会抛 ResolveNotFoundError
        try:
            grader = engine.color_grader
            print(f"  [OK] Got color_grader via engine: {type(grader).__name__}")
        except ResolveNotFoundError as exc:
            print(f"  [INFO] color_grader unavailable (expected in demo env): {exc}")
    except FileNotFoundError as exc:
        print(f"  [INFO] fuscript not found (expected in demo env): {exc}")


def demo_10_lua_fallback(tmp_dir: Path) -> None:
    """10) Lua/Fuscript 降级：直接生成可执行的 Lua 脚本。"""
    print("\n" + "=" * 60)
    print("Demo 10: Lua/Fuscript 降级（无需 Python API）")
    print("=" * 60)

    from integrations.davinci_color_lua import (
        build_apply_preset_lua,
        build_set_color_wheel_lua,
        build_apply_lut_lua,
        build_full_grading_lua,
    )

    preset = get_preset("cinematic_teal_orange")
    if preset is None:
        print("  [SKIP] Preset not found")
        return

    # 1) 单色轮
    lua1 = build_set_color_wheel_lua(
        project_name="MyProject", clip_index=0, node_index=0,
        channel=ColorWheelChannel.LIFT,
        red=-0.02, green=0.01, blue=0.04, master=-0.02,
    )
    print(f"  [OK] build_set_color_wheel_lua -> {len(lua1)} chars")

    # 2) 整套预设
    lua2 = build_apply_preset_lua(
        project_name="MyProject", clip_index=0, node_index=0, preset=preset,
    )
    print(f"  [OK] build_apply_preset_lua -> {len(lua2)} chars")

    # 3) 应用 LUT
    fake_lut = str(tmp_dir / "demo.cube")
    Path(fake_lut).write_text("# fake")
    lua3 = build_apply_lut_lua(
        project_name="MyProject", clip_index=0, node_index=0, lut_path=fake_lut,
    )
    print(f"  [OK] build_apply_lut_lua -> {len(lua3)} chars")

    # 4) 一站式
    lua4 = build_full_grading_lua(
        project_name="MyProject", clip_index=0, preset=preset,
        custom_curves={"Custom": [0.0, 0.0, 1.0, 1.0]},
        lut_path=fake_lut, node_label="Cinematic-Node",
    )
    out = tmp_dir / "full_grading.lua"
    out.write_text(lua4, encoding="utf-8")
    print(f"  [OK] build_full_grading_lua -> {out} ({len(lua4)} chars)")


# ============================================================================
# 入口
# ============================================================================

DEMOS = {
    "1": ("单色轮通道控制", demo_1_color_wheel_control),
    "2": ("应用内置预设", demo_2_apply_builtin_presets),
    "3": ("节点图管理", demo_3_node_graph_management),
    "4": ("自定义曲线", demo_4_custom_curves),
    "5": ("Qualifier 限定器", demo_5_qualifier_selection),
    "6": ("LUT 应用与导出", demo_6_lut_operations),
    "7": ("批量调色", demo_7_batch_grade),
    "8": ("预设保存与加载", demo_8_preset_persistence),
    "9": ("ResolveColorEngine 集成", demo_9_engine_integration),
    "10": ("Lua/Fuscript 降级", demo_10_lua_fallback),
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="DaVinci Color 页面调色自动化使用示例"
    )
    parser.add_argument(
        "--demo", default="all",
        help="要运行的 demo 编号（1-10）或 'all'",
    )
    parser.add_argument(
        "--real", action="store_true",
        help="使用真实 Resolve（默认使用 Mock，仅打印，无副作用）",
    )
    args = parser.parse_args(argv)

    # 构造 ColorGrader
    if args.real:
        try:
            grader = ColorGrader()
        except ResolveNotFoundError as exc:
            print(f"[ERROR] Cannot connect to real Resolve: {exc}")
            return 1
    else:
        mock_resolve, _ = make_mock_resolve()
        grader = ColorGrader(resolve=mock_resolve)
        print("[INFO] Using Mock Resolve (no side effects)")

    with tempfile.TemporaryDirectory(prefix="davinci_color_demo_") as tmp:
        tmp_dir = Path(tmp)
        if args.demo == "all":
            for k in sorted(DEMOS.keys(), key=int):
                _, fn = DEMOS[k]
                # 部分 demo 需要 tmp_dir
                if k == "6" or k == "8":
                    fn(grader, tmp_dir)
                elif k in ("9", "10"):
                    fn(tmp_dir)
                else:
                    fn(grader)
        elif args.demo in DEMOS:
            _, fn = DEMOS[args.demo]
            if args.demo == "6" or args.demo == "8":
                fn(grader, tmp_dir)
            elif args.demo in ("9", "10"):
                fn(tmp_dir)
            else:
                fn(grader)
        else:
            print(f"[ERROR] Unknown demo: {args.demo}")
            return 1

    print("\n[OK] All requested demos completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
