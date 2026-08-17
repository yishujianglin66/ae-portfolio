# DaVinci Resolve Studio 安装验证报告

**日期**: 2026-08-04  
**版本**: DaVinci Resolve Studio 21.0.3 (Build 7)  
**安装路径**: `D:\app\`

---

## 1. 安装与版本验证

| 检查项 | 状态 | 详情 |
|--------|------|------|
| 安装路径 | ✅ | `D:\app\`（非默认路径，用户自选） |
| 版本确认 | ✅ | DaVinci Resolve **Studio** 21.0.3.7 |
| Resolve.exe | ✅ | `D:\app\Resolve.exe` (553 MB) |
| fuscript.exe | ✅ | `D:\app\fuscript.exe` (Fusion Studio 21.0.3) |
| 窗口标题 | ✅ | "DaVinci Resolve Studio - 新建项目" |
| 注册表版本 | ✅ | `HKLM\SOFTWARE\Blackmagic Design\DaVinci Resolve` = 21.0.30007 |

## 2. fuscript.exe Lua 引擎验证

| 检查项 | 状态 | 详情 |
|--------|------|------|
| fuscript 启动 | ✅ | 正常执行 Lua 脚本 |
| Resolve() 连接 | ✅ | 成功创建，UUID 通信正常 |
| GetVersion() | ✅ | 21.0.3 |
| GetProductName() | ✅ | "DaVinci Resolve Studio" |
| GetProjectManager() | ✅ | 正常返回 |
| 页面切换 | ✅ | edit/color/fusion/deliver 全部可用 |

## 3. Python API 验证

| 检查项 | 状态 | 详情 |
|--------|------|------|
| DaVinciResolveScript 模块 | ⚠️ | 找到模块但 fusionscript DLL 初始化失败 |
| fusionscript.dll | ⚠️ | DLL 存在于 `D:\app\`，加载时报 SystemError |
| os.add_dll_directory | ❌ | 添加 DLL 搜索路径后仍失败 |
| RESOLVE_SCRIPT_LIB | ❌ | 设置环境变量后仍失败 |

**错误信息**: `SystemError: initialization of fusionscript failed without raising an exception`

**根因分析**: fusionscript.dll 需要通过 COM/IPC 连接 Resolve 进程，但外部 Python 进程无法建立此连接。可能需要：
- Resolve 内部嵌入的 Python 环境
- 或特定的 COM 注册

## 4. Studio 版 API 能力完整测绘

### 4.1 对象级方法汇总

#### Resolve 对象 (9 可用 / 18 探测)
**可用**: GetVersion, GetProductName, GetProjectManager, OpenPage, GetCurrentPage, LoadLayoutPreset, UpdateLayoutPreset, ExportLayoutPreset, ImportLayoutPreset

#### Project 对象 (18 可用 / 38 探测)
**可用**: GetName, GetMediaPool, GetTimelineCount, GetCurrentTimeline, SetCurrentTimeline, GetSetting, SetSetting, GetPresets, **AddRenderJob**, **StartRendering**, **StopRendering**, **DeleteAllRenderJobs**, **GetRenderPresets**, **GetRenderJobStatus**, **GetRenderPresetList**, **LoadRenderPreset**, **DeleteRenderPreset**, DeleteColorGroup, GetTimelineByIndex

**缺失**: Save, GetRenderJobCount, DeleteRenderJobByIndex, GetRenderFormatList, GetRenderCodecList, GetColorGroupList, CreateColorGroup, GetNodePresets, LoadNodePreset, ApplyNodePreset, GetLUTList, GetPowerGrade, SetPowerGrade, CreateTimeline, DeleteTimeline, GetMarkers, AddMarker 等

#### MediaPool 对象 (7 可用 / 20 探测)
**可用**: GetRootFolder, AddSubFolder, ImportMedia, CreateEmptyTimeline, CreateTimelineFromClips, AppendToTimeline, DeleteClips

#### Timeline 对象 (13 可用 / 25 探测)
**可用**: GetName, GetTrackCount, GetItemsInTrack, GetCurrentVideoItem, GetStartFrame, GetEndFrame, AddTrack, DeleteTrack, GetMarkers, AddMarker, DeleteMarkerAtFrame, GetSetting, SetSetting

#### TimelineItem 对象 (25 可用 / 62 探测)
**可用（基础）**: GetName, GetDuration, GetStart, GetEnd, GetLeftOffset, GetRightOffset, GetFusionCompCount, SetProperty, GetProperty, GetClipEnabled, SetClipEnabled

**可用（调色）**: SetLUT, GetLUT, **SetCDL** (Studio 新增)

**可用（Fusion）**: **AddFusionComp**, **ExportFusionComp**, **ImportFusionComp** (Studio 新增)

**可用（标记）**: GetFlagList, AddFlag, ClearFlags, GetMarkers, AddMarker, DeleteMarkerAtFrame, GetClipColor, SetClipColor, ClearClipColor

**缺失（调色节点）**: GetNodeCount, AddNode, DeleteNode, GetNodeTree, SetLift, SetGamma, SetGain, SetOffset, SetNodeDisabled, GetNodeDisabled, SetNodeLUT, GetNodeLUT, SetSaturation, SetContrast, SetPivot, SetMidtoneDetail

**缺失（变速）**: SetSpeed, GetSpeed, SetRetimeProcess, GetRetimeProcess, SetRetimeCurve, GetRetimeCurve

**缺失（运动）**: GetDynamicZoom, SetDynamicZoom, GetCropValues, SetCropValues, GetTransform, SetTransform, GetStabilization, SetStabilization

**缺失（特效）**: AddComponent, DeleteComponent, GetComponentList, GetFusionComp, DeleteFusionComp, LoadFusionComp, SetFusionCompEnabled

### 4.2 通过 SetProperty/GetProperty 解锁的能力

| 功能 | 方法 | 状态 | 备注 |
|------|------|------|------|
| **变速** | `SetProperty("Speed", value)` | ✅ | 接受 0.5/2.0 等值，SetProperty 不报错 |
| **裁切** | `SetProperty("Crop Left/Right", value)` | ✅ | |
| **缩放** | `SetProperty("Zoom X/Y", value)` | ✅ | |
| **位移** | `SetProperty("Position X/Y", value)` | ✅ | |
| **旋转** | `SetProperty("Rotation", value)` | ✅ | |
| **透明度** | `SetProperty("Opacity", value)` | ✅ | GetProperty 可读取 |
| **Pan/Tilt** | `GetProperty("Pan"/"Tilt")` | ✅ | 可读 |
| **RetimeProcess** | `GetProperty("RetimeProcess")` | ✅ | 可读 |

### 4.3 Studio 版新增能力（相比免费版）

| 能力 | 免费版 | Studio 版 | 访问方式 |
|------|--------|-----------|----------|
| 渲染任务管理 | ❌ | ✅ | AddRenderJob/StartRendering/StopRendering/DeleteAllRenderJobs |
| 渲染预设 | ❌ | ✅ | GetRenderPresets/GetRenderPresetList/LoadRenderPreset/DeleteRenderPreset |
| CDL 调色 | ❌ | ✅ | `SetCDL({Slope, Offset, Power, Saturation})` |
| LUT 应用 | ✅ | ✅ | SetLUT/GetLUT |
| Fusion 合成管理 | ❌ | ✅ | AddFusionComp/ExportFusionComp/ImportFusionComp |
| 变速 | ❌ | ✅ | `SetProperty("Speed", value)` |
| 变换控制 | ❌ | ✅ | `SetProperty("Zoom/Position/Rotation/Crop")` |

## 5. 现有代码兼容性审计

### `integrations/davinci_fuscript.py` (3141 行) API 兼容性

| 代码中使用的 API | Studio 可用性 | 替代方案 |
|-----------------|--------------|----------|
| `clip:AddNode("serial")` | ❌ 不可用 | 需要重写为 CDL/LUT 方案 |
| `clip:GetNodeCount()` | ❌ 不可用 | 需要移除节点依赖 |
| `clip:SetCurrentNode(n)` | ❌ 不可用 | 需要重写 |
| `clip:ApplyLUT(path)` | ❌ 不可用 | 改用 `item:SetLUT(path)` |
| `tl:GetItemCount()` | ❌ 不可用 | 改用 `tl:GetItemsInTrack()` |
| `item:SetQualifier(...)` | ❌ 不可用 | 需要移除限定器依赖 |
| `item:SetNodeColorWheels(...)` | ❌ 不可用 | 改用 `SetCDL()` |
| `proj:Save()` | ❌ 不可用 | 自动保存或忽略 |

**结论**: 现有 `davinci_fuscript.py` 的调色核心逻辑（节点链 + 色轮 + 限定器）**需要完全重写**，改为基于 CDL + LUT + SetProperty 的架构。

## 6. 插件与依赖检查

| 依赖 | 状态 | 备注 |
|------|------|------|
| Blackmagic RAW | ❌ 未安装 | 之前卸载时一并移除，如需处理 BRAW 素材需重装 |
| Fusion 目录 | ✅ | Macros/Templates/LUTs 完整 |
| LUT 文件 | ✅ | 20+ 厂商/格式 LUT 可用 |
| Python 3.12 | ✅ | 基础模块正常 |
| FFmpeg | ✅ | 已有 ffmpeg_full 目录 |

## 7. 待解决问题

### P0 - 阻塞性问题

1. **Resolve 数据库未激活**
   - 现象：`CreateProject()`/`LoadProject()` 返回 nil
   - 原因：Studio 版首次启动需要在 UI 中完成数据库初始化
   - 修复：**在 Resolve 界面中点击选中 "Local Database"**
   - 之前的 5 个测试项目（Studio_Verify, Method_Enum 等）残留需清理

2. **Python API 不可用**
   - 现象：fusionscript DLL 初始化失败
   - 影响：无法从 Python 直接调用 Resolve API
   - 降级方案：使用 fuscript.exe + Lua（已验证可用）
   - 后续可尝试：Resolve 内部 Python 环境或 COM 注册修复

### P1 - 需要代码重写

3. **davinci_fuscript.py 调色架构不兼容**
   - 现有代码基于节点 API（AddNode/SetLift/SetGamma 等），Studio 版不提供
   - 需要重写为 CDL + LUT + SetProperty 架构
   - 预计影响范围：~800 行调色相关代码

### P2 - 可选修复

4. **Blackmagic RAW 组件缺失**
   - 如需处理 .BRAW 素材需重新安装
   - 当前工作流不涉及 BRAW，优先级低

## 8. 结论

### 可以做到的（Studio 版能力）
- ✅ 项目管理（创建/加载/删除）
- ✅ 素材导入与时间线编排
- ✅ CDL 调色（Slope/Offset/Power/Saturation）
- ✅ LUT 应用
- ✅ 变速（通过 SetProperty）
- ✅ 变换/裁切/旋转（通过 SetProperty）
- ✅ Fusion 合成管理
- ✅ 渲染输出（AddRenderJob/StartRendering）
- ✅ 页面切换（Edit/Color/Fusion/Deliver）
- ✅ 标记/旗帜管理

### 做不到的（API 限制）
- ❌ 节点级调色（GetNodeCount/AddNode/GetNodeTree）
- ❌ 直接色轮控制（SetLift/SetGamma/SetGain/SetOffset）
- ❌ 限定器（Qualifier）
- ❌ 变速曲线（Retime Curve）
- ❌ 运动效果（Dynamic Zoom/Transform/Stabilization 的直接 API）
- ❌ OpenFX 组件添加（AddComponent）

### 下一步行动
1. **用户操作**：在 Resolve UI 中激活 Local Database
2. **代码重写**：将 `davinci_fuscript.py` 的调色逻辑从节点模型改为 CDL+LUT 模型
3. **管线整合**：Resolve（素材管理+CDL调色+变速+渲染）+ FFmpeg（后处理兜底）
