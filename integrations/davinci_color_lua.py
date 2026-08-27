#!/usr/bin/env python3
"""
[DEPRECATED] DaVinci Resolve Color 页面 Lua 桥接 v1.0
=====================================================

** 已废弃 ** — 请使用 ``integrations/davinci_fuscript.py`` (ResolveColorEngine v4.0)

废弃原因:
- 数据类型已迁移到 davinci_fuscript.py
- Lua 模板已吸收到 ResolveColorEngine._gen_clip_color_lua()
- 依赖 davinci_color_grading.py（已废弃）

保留此文件供参考，不应删除。

原功能:
为 ``davinci_fuscript.py`` 引擎提供 Color 页面调色的 Lua 脚本生成能力。

当 Resolve Python 集成（``DaVinciResolveScript`` / ``python_get_resolve``）
不可用时，可通过 ``fuscript.exe -lua script.lua`` 间接控制 Color 页面。

本模块提供：

- :func:`build_set_color_wheel_lua` — 设置单个色轮（Lift/Gamma/Gain/Offset）
- :func:`build_custom_curve_lua` — 自定义曲线
- :func:`build_apply_preset_lua` — 应用整套预设
- :func:`build_node_management_lua` — 节点增删
- :func:`build_qualifier_lua` — 限定器选择
- :func:`build_apply_lut_lua` — 应用 LUT
- :func:`build_export_lut_lua` — 导出 LUT
- :func:`build_full_grading_lua` — 一站式调色脚本

所有 builder 接受结构化参数（如 :class:`ColorGradingPreset`），返回可直接
写入临时文件并经 ``fuscript.exe -lua`` 执行的字符串。

调用示例::

    from integrations.davinci_color_lua import build_set_color_wheel_lua
    lua = build_set_color_wheel_lua(
        project_name="MyProj", clip_index=0, node_index=0,
        channel="Lift", red=-0.02, green=0.01, blue=0.04, master=-0.02,
    )
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from integrations.davinci_color_grading import (
    ColorBalanceType,
    ColorGradingPreset,
    ColorWheelChannel,
    ColorWheelValues,
    CurveType,
    NodeType,
)


# ============================================================================
# 工具
# ============================================================================

def _lua_str(value: str) -> str:
    """转义 Lua 字符串。"""
    if value is None:
        return '""'
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _lua_num(value) -> str:
    """格式化 Lua 数字（Python bool/float/int -> Lua number）。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(float(value))


# ============================================================================
# 头部脚本（公共前置）
# ============================================================================

def _common_header() -> str:
    """公共前置：连接 Resolve + 工程/时间线/片段获取。"""
    return '''-- Color Grading Lua Bridge v1.0 (auto-generated)
local resolveOk, resolve = pcall(Resolve)
if not resolveOk or not resolve then print("ERROR: Cannot connect to Resolve"); return end

local pm = resolve:GetProjectManager()
if not pm then print("ERROR: No ProjectManager"); return end

local function getProject(name)
    if name and name ~= "" then
        local p = pm:LoadProject(name)
        if not p then p = pm:GetCurrentProject() end
        return p
    end
    return pm:GetCurrentProject()
end

local function getTimeline(project, idx)
    if not project then return nil end
    if idx then
        local t = project:GetTimelineByIndex(idx)
        if t then return t end
    end
    return project:GetCurrentTimeline()
end

local function getItemAt(timeline, clipIdx)
    if not timeline then return nil end
    local items = timeline:GetItemListInTrack("video", 1) or {}
    if clipIdx < 0 or clipIdx >= #items then
        print(string.format("ERROR: clip_index %d out of range (total=%d)", clipIdx, #items))
        return nil
    end
    return items[clipIdx + 1]
end
'''


# ============================================================================
# Color Wheel 脚本
# ============================================================================

def build_set_color_wheel_lua(
    project_name: str = "",
    clip_index: int = 0,
    node_index: int = 0,
    channel: str | ColorWheelChannel = ColorWheelChannel.LIFT,
    red: float = 0.0,
    green: float = 0.0,
    blue: float = 0.0,
    master: float = 0.0,
    balance_type: str | ColorBalanceType = ColorBalanceType.RGB,
) -> str:
    """生成设置单个色轮的 Lua 脚本。

    Args:
        project_name: 工程名（空字符串表示使用当前工程）。
        clip_index: 片段在时间线 video 1 上的索引（0-based）。
        node_index: 节点索引。
        channel: 色轮通道（``"Lift"`` / ``"Gamma"`` / ``"Gain"`` / ``"Offset"``）。
        red/green/blue/master: 四元组色轮值。
        balance_type: 平衡模式（``"rgb"`` / ``"hsl"`` / ``"yrgb"``）。
    """
    channel_str = channel.value if isinstance(channel, ColorWheelChannel) else str(channel)
    balance_str = balance_type.value if isinstance(balance_type, ColorBalanceType) else str(balance_type)

    # RGB / YRGB 使用 Red/Green/Blue；HSL 改用 Hue/Sat/Lum
    if balance_str == "hsl":
        values_dict = (
            f'    Hue = {_lua_num(red)},\n'
            f'    Saturation = {_lua_num(green)},\n'
            f'    Luminance = {_lua_num(blue)},\n'
            f'    Master = {_lua_num(master)},\n'
            f'}}'
        )
    else:
        values_dict = (
            f'    Red = {_lua_num(red)},\n'
            f'    Green = {_lua_num(green)},\n'
            f'    Blue = {_lua_num(blue)},\n'
            f'    Master = {_lua_num(master)},\n'
            f'}}'
        )

    header = _common_header()
    return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end

local values = {{
{values_dict}

print(string.format("Setting color wheel %s on clip=%d node=%d (balance=%s)",
    {_lua_str(channel_str)}, {int(clip_index)}, {int(node_index)}, {_lua_str(balance_str)}))
local ok, err = pcall(function()
    return item:SetNodeColorWheels({int(node_index)}, {_lua_str(channel_str)}, {_lua_str(balance_str)}, values)
end)
if ok then
    print("OK: color wheel applied, result=" .. tostring(err))
else
    print("ERROR: " .. tostring(err))
end
print("DONE")
'''


# ============================================================================
# 自定义曲线
# ============================================================================

def build_custom_curve_lua(
    project_name: str = "",
    clip_index: int = 0,
    node_index: int = 0,
    curve_type: str | CurveType = CurveType.CUSTOM,
    points: Optional[List[float]] = None,
) -> str:
    """生成设置自定义曲线的 Lua 脚本。

    Args:
        curve_type: 曲线类型（``"Custom"`` / ``"HueVsHue"`` / ...）。
        points: 控制点扁平列表（每两个值一组 x/y）。
    """
    if points is None:
        points = []
    ct = curve_type.value if isinstance(curve_type, CurveType) else str(curve_type)
    points_lua = ", ".join(_lua_num(p) for p in points) or ""
    header = _common_header()
    return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end

local curveValues = {{ {points_lua} }}
print(string.format("Setting custom curve %s on clip=%d node=%d (points=%d)",
    {_lua_str(ct)}, {int(clip_index)}, {int(node_index)}, #curveValues))
local ok, err = pcall(function()
    return item:SetCustomCurve({int(node_index)}, {_lua_str(ct)}, curveValues)
end)
if ok then
    print("OK: curve applied")
else
    print("ERROR: " .. tostring(err))
end
print("DONE")
'''


# ============================================================================
# 节点管理
# ============================================================================

def build_node_management_lua(
    project_name: str = "",
    clip_index: int = 0,
    action: str = "add",  # "add" / "delete" / "opacity" / "label"
    node_type: int | NodeType = NodeType.SERIAL,
    node_index: int = 0,
    opacity: float = 1.0,
    label: str = "",
) -> str:
    """生成节点管理脚本（新增/删除/设置透明度/标签）。"""
    nt = node_type.value if isinstance(node_type, NodeType) else int(node_type)
    header = _common_header()
    if action == "add":
        return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end
local newIdx = item:AddNode({int(nt)})
print("OK: Added node type={int(nt)} -> index=" .. tostring(newIdx))
{("item:SetNodeLabel(newIdx, " + _lua_str(label) + ")") if label else ""}
print("DONE")
'''
    if action == "delete":
        return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end
local ok = item:DeleteNode({int(node_index)})
print("OK: Deleted node {int(node_index)} -> " .. tostring(ok))
print("DONE")
'''
    if action == "opacity":
        return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end
local ok = item:SetNodeOpacity({int(node_index)}, {_lua_num(opacity)})
print("OK: SetNodeOpacity {int(node_index)}={_lua_num(opacity)} -> " .. tostring(ok))
print("DONE")
'''
    if action == "label":
        return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end
local ok = item:SetNodeLabel({int(node_index)}, {_lua_str(label)})
print("OK: SetNodeLabel {int(node_index)} -> " .. tostring(ok))
print("DONE")
'''
    raise ValueError(f"Unknown action: {action}")


# ============================================================================
# Qualifier
# ============================================================================

def build_qualifier_lua(
    project_name: str = "",
    clip_index: int = 0,
    node_index: int = 0,
    hue_range: Tuple[float, float] = (0.0, 360.0),
    sat_range: Tuple[float, float] = (0.0, 1.0),
    lum_range: Tuple[float, float] = (0.0, 1.0),
    invert: bool = False,
) -> str:
    """生成 Qualifier 限定器选择脚本。"""
    header = _common_header()
    return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end

local qualifier = {{
    Hue = {{ min = {_lua_num(hue_range[0])}, max = {_lua_num(hue_range[1])} }},
    Sat = {{ min = {_lua_num(sat_range[0])}, max = {_lua_num(sat_range[1])} }},
    Lum = {{ min = {_lua_num(lum_range[0])}, max = {_lua_num(lum_range[1])} }},
}}

print(string.format("Setting qualifier on clip=%d node=%d hue=[%.1f,%.1f] sat=[%.2f,%.2f] lum=[%.2f,%.2f]",
    {int(clip_index)}, {int(node_index)},
    {float(hue_range[0])}, {float(hue_range[1])},
    {float(sat_range[0])}, {float(sat_range[1])},
    {float(lum_range[0])}, {float(lum_range[1])}))
local ok, err = pcall(function()
    return item:SetQualifier({int(node_index)}, qualifier)
end)
if ok then
    print("OK: qualifier applied")
else
    print("ERROR: " .. tostring(err))
end
{("local ok2 = pcall(function() return item:InvertQualifierSelection(" + str(int(node_index)) + ") end); print('Invert: ' .. tostring(ok2))") if invert else ""}
print("DONE")
'''


# ============================================================================
# LUT
# ============================================================================

def build_apply_lut_lua(
    project_name: str = "",
    clip_index: int = 0,
    node_index: int = 0,
    lut_path: str = "",
) -> str:
    """生成应用 LUT 的 Lua 脚本（自动转义路径）。"""
    safe = _lua_str(lut_path.replace("\\", "\\\\") if lut_path else "")
    header = _common_header()
    return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end
local ok = item:SetLUT({int(node_index)}, {safe})
print("OK: SetLUT {int(node_index)} -> " .. tostring(ok))
print("DONE")
'''


def build_export_lut_lua(
    project_name: str = "",
    clip_index: int = 0,
    node_index: int = 0,
    output_path: str = "",
    cube_size: int = 33,
) -> str:
    """生成导出 LUT 的 Lua 脚本（Studio only）。"""
    safe = _lua_str(output_path.replace("\\", "\\\\") if output_path else "")
    header = _common_header()
    return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end
local ok = item:ExportLUT({int(node_index)}, {safe}, {int(cube_size)})
print("OK: ExportLUT -> " .. tostring(ok))
print("DONE")
'''


# ============================================================================
# 完整预设
# ============================================================================

def build_apply_preset_lua(
    project_name: str = "",
    clip_index: int = 0,
    node_index: int = 0,
    preset: Optional[ColorGradingPreset] = None,
    balance_type: str | ColorBalanceType = ColorBalanceType.RGB,
) -> str:
    """生成应用整套预设的 Lua 脚本。"""
    if preset is None:
        raise ValueError("preset is required")
    balance_str = balance_type.value if isinstance(balance_type, ColorBalanceType) else str(balance_type)

    def _values_dict(w: ColorWheelValues) -> str:
        if balance_str == "hsl":
            return (
                f'    {{ Hue = {_lua_num(w.red)}, Saturation = {_lua_num(w.green)}, '
                f'Luminance = {_lua_num(w.blue)}, Master = {_lua_num(w.master)} }}'
            )
        return (
            f'    {{ Red = {_lua_num(w.red)}, Green = {_lua_num(w.green)}, '
            f'Blue = {_lua_num(w.blue)}, Master = {_lua_num(w.master)} }}'
        )

    header = _common_header()
    return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
local item = getItemAt(timeline, {int(clip_index)})
if not item then print("ERROR: Item not found"); return end

print("=== Applying preset: {_lua_str(preset.name)} on clip={int(clip_index)} node={int(node_index)} ===")

local ok_lift = item:SetNodeColorWheels({int(node_index)}, "Lift",   {_lua_str(balance_str)}, {_values_dict(preset.lift)})
local ok_gamma = item:SetNodeColorWheels({int(node_index)}, "Gamma",  {_lua_str(balance_str)}, {_values_dict(preset.gamma)})
local ok_gain  = item:SetNodeColorWheels({int(node_index)}, "Gain",   {_lua_str(balance_str)}, {_values_dict(preset.gain)})
local ok_off   = item:SetNodeColorWheels({int(node_index)}, "Offset", {_lua_str(balance_str)}, {_values_dict(preset.offset)})

item:SetSaturation({_lua_num(preset.saturation)}, {int(node_index)})
item:SetContrast({_lua_num(preset.contrast)}, {int(node_index)})
if item.SetPivot then item:SetPivot({_lua_num(preset.pivot)}, {int(node_index)}) end
if item.SetNodeOpacity then item:SetNodeOpacity({int(node_index)}, {_lua_num(preset.blend_opacity)}) end

print(string.format("Channels: lift=%s gamma=%s gain=%s offset=%s",
    tostring(ok_lift), tostring(ok_gamma), tostring(ok_gain), tostring(ok_off)))
print("DONE")
'''


# ============================================================================
# 一站式（同时做色轮+曲线+LUT+节点）
# ============================================================================

def build_full_grading_lua(
    project_name: str = "",
    clip_index: int = 0,
    preset: Optional[ColorGradingPreset] = None,
    custom_curves: Optional[dict] = None,
    lut_path: Optional[str] = None,
    node_label: str = "",
) -> str:
    """生成一站式调色 Lua（包含色轮 + 曲线 + LUT + 节点元数据）。

    Args:
        project_name: 工程名。
        clip_index: 片段索引。
        preset: 调色预设。
        custom_curves: ``{curve_type: [points...]}`` 字典。
        lut_path: 可选 LUT 路径。
        node_label: 节点标签。
    """
    if preset is None:
        raise ValueError("preset is required")
    custom_curves = custom_curves or {}

    preset_lua = build_apply_preset_lua(
        project_name=project_name, clip_index=clip_index, node_index=0, preset=preset,
    )

    extras = []
    for curve_type, points in custom_curves.items():
        curve_lua = build_custom_curve_lua(
            project_name=project_name,
            clip_index=clip_index,
            node_index=0,
            curve_type=curve_type,
            points=list(points),
        )
        # 去掉头部公共代码
        marker = "-- Color Grading Lua Bridge v1.0"
        idx = curve_lua.find(marker)
        if idx >= 0:
            # 保留公共头之后的部分
            curve_lua = curve_lua[idx:]
        extras.append(curve_lua)

    if lut_path:
        extras.append(build_apply_lut_lua(
            project_name=project_name, clip_index=clip_index, node_index=0, lut_path=lut_path,
        ))

    if node_label:
        extras.append(build_node_management_lua(
            project_name=project_name, clip_index=clip_index,
            action="label", node_index=0, label=node_label,
        ))

    return preset_lua + "\n\n" + "\n\n".join(extras)


# ============================================================================
# 批量片段调色
# ============================================================================

def build_batch_grade_lua(
    project_name: str = "",
    clip_indices: Optional[List[int]] = None,
    preset: Optional[ColorGradingPreset] = None,
    node_index: int = 0,
) -> str:
    """生成对多个片段应用同一预设的 Lua 脚本。"""
    if preset is None:
        raise ValueError("preset is required")
    if clip_indices is None:
        clip_indices = [0]
    header = _common_header()
    indices_lua = "{" + ", ".join(str(int(i)) for i in clip_indices) + "}"
    count_str = str(len(clip_indices))
    return f'''{header}
local project = getProject({_lua_str(project_name)})
local timeline = getTimeline(project)
if not timeline then print("ERROR: No timeline"); return end

local items = timeline:GetItemListInTrack("video", 1) or {{}}
local targets = {indices_lua}
local presetName = {_lua_str(preset.name)}
print(string.format("=== Batch grading: preset=%s, targets={count_str} clips ===", presetName))

local lift, gamma, gain, offset = nil, nil, nil, nil
local results = {{}}
for _, idx in ipairs(targets) do
    if idx >= 0 and idx < #items then
        local it = items[idx + 1]
        if it then
            local ok1 = pcall(function() return it:SetNodeColorWheels({int(node_index)}, "Lift",
                "rgb", {{ Red = {_lua_num(preset.lift.red)}, Green = {_lua_num(preset.lift.green)},
                Blue = {_lua_num(preset.lift.blue)}, Master = {_lua_num(preset.lift.master)} }}) end)
            local ok2 = pcall(function() return it:SetNodeColorWheels({int(node_index)}, "Gamma",
                "rgb", {{ Red = {_lua_num(preset.gamma.red)}, Green = {_lua_num(preset.gamma.green)},
                Blue = {_lua_num(preset.gamma.blue)}, Master = {_lua_num(preset.gamma.master)} }}) end)
            local ok3 = pcall(function() return it:SetNodeColorWheels({int(node_index)}, "Gain",
                "rgb", {{ Red = {_lua_num(preset.gain.red)}, Green = {_lua_num(preset.gain.green)},
                Blue = {_lua_num(preset.gain.blue)}, Master = {_lua_num(preset.gain.master)} }}) end)
            local ok4 = pcall(function() return it:SetNodeColorWheels({int(node_index)}, "Offset",
                "rgb", {{ Red = {_lua_num(preset.offset.red)}, Green = {_lua_num(preset.offset.green)},
                Blue = {_lua_num(preset.offset.blue)}, Master = {_lua_num(preset.offset.master)} }}) end)
            pcall(function() it:SetSaturation({_lua_num(preset.saturation)}, {int(node_index)}) end)
            pcall(function() it:SetContrast({_lua_num(preset.contrast)}, {int(node_index)}) end)
            results[idx] = ok1 and ok2 and ok3 and ok4
            print(string.format("  clip %d: %s", idx, tostring(results[idx])))
        end
    end
end
local okCount = 0
for _, v in pairs(results) do if v then okCount = okCount + 1 end end
print(string.format("Batch graded: %d/%d", okCount, #targets))
print("DONE")
'''


# ============================================================================
# 模块导出
# ============================================================================

__all__ = [
    "build_set_color_wheel_lua",
    "build_custom_curve_lua",
    "build_node_management_lua",
    "build_qualifier_lua",
    "build_apply_lut_lua",
    "build_export_lut_lua",
    "build_apply_preset_lua",
    "build_full_grading_lua",
    "build_batch_grade_lua",
]
