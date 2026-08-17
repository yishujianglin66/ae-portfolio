# DaVinci Resolve 全功能自动化开发方案

> **版本**: v1.2（Studio 验证 + 引擎重写修订版）  
> **日期**: 2026-08-04  
> **状态**: Studio 版已验证，核心引擎 v5.0 已实现，P1-P3 可推进  
> **作者**: AE-Knowledge-Vault 工程团队

> **Studio 版验证重要发现（2026-08-04）**:
> - DaVinci Resolve Studio 21.0.3 已安装于 `D:\app\`
> - fuscript.exe + Lua 通路完全可用
> - **SetProperty/GetProperty 解锁全套变换能力**：变速/缩放/位移/旋转/裁切/透明度
> - **SetCDL 调色** 替代节点级色轮控制（Studio 新增 API）
> - **渲染 API** 可用：AddRenderJob/StartRendering/StopRendering
> - **Fusion 合成管理** 可用：AddFusionComp/ExportFusionComp/ImportFusionComp
> - 新引擎 `resolve_engine.py` (870行) + `davinci_fuscript.py` v5.0 (1157行) 已实现
> - E2E 测试 8/8 通过（素材导入→时间线→CDL调色→变速→变换→FFmpeg渲染）

---

## 0. 背景与问题定义

### 0.1 当前管线的核心矛盾

```
┌─────────────────────────────────────────────────────────┐
│  PR 2025 ExtendScript API 能力矩阵                        │
│                                                          │
│  ✅ 能做的: 读clip信息、插入clip、保存项目、Motion关键帧    │
│  ❌ 做不了的: 变速(setSpeed)、调色(addComponent)、          │
│             文字(无接口)、转场(无接口)、app.execute(不存在)  │
│                                                          │
│  结果: PR 在项目里 ≈ "素材管理器 + 时间线预览器"             │
│        核心创意处理全靠 FFmpeg 后处理                       │
─────────────────────────────────────────────────────────┘
```

**已验证的失败路径**：
- MCP Bridge（CEP 面板）→ 仍是 ExtendScript eval，无法突破 API 限制
- QE DOM → `enableQE(true)` 返回 true 但对象不可访问
- ComputerUse UI 自动化 → DroverLord 框架拦截 GUI 操作

### 0.2 现有 DaVinci 集成基础（可复用资产）

| 文件 | 行数 | 能力 | 状态 |
|------|------|------|------|
| `integrations/davinci_fuscript.py` | 1157 | 调色引擎 v5.0（CDL+LUT+SetProperty） | ✅ 已重写 |
| `integrations/resolve_engine.py` | 870 | 核心自动化引擎（fuscript+Lua+JSON） | ✅ 新实现 |
| `integrations/davinci_resolve_integration.py` | 1400+ | 8 阶段连接探测 + DavinciColorist | ✅ 可用 |
| `pipeline/engine_task_dispatcher.py` | - | ResolveTaskDispatcher 调度器 | ✅ 可用 |
| `scripts/pr_to_resolve_pipeline.py` | ~100 | PR→Resolve 基础管线 | ⚠️ 基础 |
| `integrations/davinci_color_grading.py` | - | 调色数据模型 | ⚠️ 已废弃 |
| `software_sdk/adapters/davinci_adapter.py` | - | 适配器 |  已废弃 |

**关键发现**：现有代码 **100% 聚焦调色**，缺少变速/转场/Fusion特效/文字/时间线编辑能力。

---

## 1. 目标定义

### 1.1 DaVinci Resolve 在项目管线中的定位

```
┌──────────────────────────────────────────────────────────┐
│                    新管线架构（目标态）                      │
│                                                          │
│  S0 环境自检 → S1 风格分析 → S2 音乐感知 → S3 素材选择     │
│       ↓                                                  │
│  S4 风格化规划（生成 Resolve 操作指令集）                    │
│       ↓                                                  │
│  S5 执行引擎                                              │
│  ┌────────────┬────────────┬────────────┐                │
│  │ Edit 页面   │ Color 页面  │ Fusion 页面 │                │
│  │ 变速/转场   │ 节点调色     │ 特效/文字    │                │
│  │ 拉镜/嵌套   │ LUT应用     │ 粒子/合成    │                │
│  ────────────┴────────────┴────────────                │
│       ↓                                                  │
│  S6 验证 + Deliver 渲染输出                                │
│                                                          │
│  FFmpeg 角色降级: 仅做最终编码（H.264/H.265）               │
└──────────────────────────────────────────────────────────┘
```

### 1.2 效果提升目标（对比 PR+FFmpeg 方案）

| 维度 | PR+FFmpeg（现状） | Resolve 自动化（目标） | 提升幅度 |
|------|-------------------|----------------------|---------|
| 变速精度 | FFmpeg `setpts` 线性变速 | Resolve 曲线变速+光流补帧 | **质的飞跃** |
| 调色质量 | FFmpeg `eq` 6 参数 | Resolve 节点式 6 维调色+Qualifier | **专业级** |
| 转场丰富度 | FFmpeg `xfade` 5 种 | Resolve 50+ 种+自定义遮罩 | **10x** |
| 文字动画 | FFmpeg `drawtext` 静态 | Fusion Text+ 关键帧动画 | **质的飞跃** |
| 实时预览 |  无（FFmpeg 盲跑） | ✅ Resolve 实时预览 | **从 0 到 1** |
| 参数调节 | 改代码→重跑 | Resolve UI 手动微调 | **效率 10x** |

---

## 2. 能力映射表

### 2.1 PR 做不到的操作 → Resolve 对应方案

| # | PR 不可用操作 | Resolve 页面 | 具体 API / 方法 | 自动化难度 |
|---|-------------|-------------|----------------|-----------|
| 1 | **曲线变速** | Edit | `clip.GetFusionClip()` → Fusion TimeStretcher 节点 | ⭐⭐⭐ |
| 2 | **时间重映射** | Edit | `clip.SetClipProperty("Speed")` + Retime Controls | ⭐⭐ |
| 3 | **光流补帧** | Edit | `clip.SetClipProperty("OpticalFlow")` (需 Studio) |  |
| 4 | **Lumetri 调色** | Color | `clip.AddNode()` → SetLift/Gamma/Gain/Offset | ⭐⭐ |
| 5 | **节点式二级调色** | Color | `clip.AddNode()` → Qualifier + Power Window | ⭐⭐⭐ |
| 6 | **LUT 应用** | Color | `node.SetLUT(lutPath)` (已有实现) | ✅ 已实现 |
| 7 | **文字标题** | Fusion | `Text+` 节点 + `StyledText` + 关键帧 | ⭐⭐⭐ |
| 8 | **遮罩转场** | Fusion | `Merge` + `Polygon/Mask` 节点 + 动画 | ⭐⭐⭐⭐ |
| 9 | **RGB 分离转场** | Fusion | `ChannelBooleans` + 位移关键帧 | ⭐⭐⭐ |
| 10 | **Zoom 冲击转场** | Edit | `clip.SetPosition()` + `SetZoom()` 关键帧 | ⭐ |
| 11 | **2.5D 视差拉镜** | Fusion | `Transform3D` + `Camera3D` + 分层 Z 轴 | ⭐⭐⭐⭐ |
| 12 | **动态裁剪运镜** | Edit | `clip.SetCropping()` + Position 关键帧 | ⭐ |
| 13 | **嵌套序列** | Edit | `timeline.AppendClips()` → 子时间线 | ⭐⭐ |
| 14 | **导出帧** | Media | `project.Render()` 单帧输出 |  |
| 15 | **脚本回读** | Edit | `timeline.GetItemsInTrack()` 遍历 | ⭐ |

### 2.2 难度分级说明

- ⭐ = 已有实现或 API 直接支持（1-2h）
- ⭐⭐ = 需要封装但 API 清晰（4-8h）
- ⭐⭐⭐ = 需要复杂脚本生成（1-2d）
- ⭐⭐⭐⭐ = 需要 Fusion 节点流设计（2-4d）

---

## 3. 开发阶段规划

### P0: 基础通信验证（已完成 ✅）

**状态**：全部完成，Studio 版验证通过。

| 任务 | 状态 | 备注 |
|------|------|------|
| P0-1: Resolve 进程检测 | ✅ | `check_resolve_running()` 通过 fuscript IPC 检测 |
| P0-2: fuscript.exe 路径探测 | ✅ | `D:\app\fuscript.exe` |
| P0-3: 基础 Lua 脚本执行 | ✅ | `_execute_lua()` + JSON 输出解析协议 |
| P0-4: 项目创建/加载 | ✅ | `create_project()` / `load_project()` |
| P0-5: 命令投递协议设计 | ✅ | Python→Lua→JSON→Python 闭环 |

**新增能力（Studio 版）**：
- `SetProperty("Speed"/"Zoom X"/"Position X"/"Rotation"/"Opacity"/...)` 变换控制
- `SetCDL({Slope, Offset, Power, Saturation})` CDL 调色
- `AddRenderJob()` / `StartRendering()` 渲染输出
- `AddFusionComp()` / `ExportFusionComp()` Fusion 合成管理

**E2E 测试结果**：8/8 通过（项目创建→素材导入→CDL调色→预设调色→变速→变换→页面切换→FFmpeg渲染 5.4MB）

---

### P1: 剪辑自动化（可推进 ✅）

**目标**：实现素材导入、时间线编排、变速、变换的自动化。

| 任务 | 状态 | 实现方式 |
|------|------|----------|
| P1-1: 素材导入 | ✅ 已实现 | `MediaPool:ImportMedia()` via `create_timeline_with_media()` |
| P1-2: 时间线创建 | ✅ 已实现 | `CreateEmptyTimeline()` + `AppendToTimeline()` |
| P1-3: Clip 排列 | ✅ 已实现 | 按顺序 append 到时间线 |
| P1-4: 变速（基础） | ✅ 已实现 | `SetProperty("Speed", value)` |
| P1-5: 变速（曲线） | 待实现 | 需 FFmpeg setpts 滤镜或 Fusion TimeStretcher |
| P1-6: 光流补帧 | 待实现 | `SetProperty("RetimeProcess", 2)` Optical Flow |
| P1-7: Zoom 转场 | 待实现 | `SetProperty("Zoom X"/"Zoom Y")` + FFmpeg 关键帧 |
| P1-8: 动态裁剪拉镜 | ✅ 基础可用 | `SetProperty("Crop Left/Right/Top/Bottom")` + Position |
| P1-9: 嵌套序列 | 待实现 | 需导出子时间线再导入 |
| P1-10: 脚本回读 | ✅ 已实现 | `GetItemsInTrack()` + JSON 输出 |

**关键技术点**：
- 变速：`SetProperty("Speed", value)` 已验证可用
- 变换：`SetProperty("Zoom X"/"Position X"/"Rotation"/"Opacity")` 已验证
- 裁切：`SetProperty("Crop Left/Right/Top/Bottom")` 已验证
- 渲染：Resolve 渲染有路径问题，已改用 FFmpeg 混合渲染方案

---

### P2: 调色自动化（可推进 ✅）

**目标**：基于 CDL + LUT 架构实现精细调色。

| 任务 | 状态 | 实现方式 |
|------|------|----------|
| P2-1: 节点管理 | 已替代 | 节点 API 不可用，改用 `SetCDL()` 直接调色 |
| P2-2: CDL 调色 | ✅ 已实现 | `SetCDL({Slope, Offset, Power, Saturation})` |
| P2-3: 曲线调色 | 待实现 | 需 Fusion 页面手动操作或自定义 LUT |
| P2-4: Qualifier 二级调色 | 不可用 | Qualifier API 在 fuscript 中不可用 |
| P2-5: Power Window | 不可用 | 同上 |
| P2-6: LUT 批量应用 | ✅ 已实现 | `item:SetLUT(path)` 逐片段应用 |
| P2-7: 分段调色 | ✅ 已实现 | 逐片段不同 CDL 配置 |

**架构变更**：
- 旧方案（v4.0）：节点图 → AddNode/SetLift/SetGamma/SetNodeColorWheels（不可用）
- 新方案（v5.0）：CDL + LUT + SetProperty（Studio 验证可用）
- 12 个预设已从节点参数转为 CDL 参数
- ColorGradeArtifact 支持跨平台互通（Resolve/FFmpeg/AE）

---

### P3: Fusion 特效（预计 5-7 天）

**目标**：实现文字动画、遮罩转场、粒子效果等 Fusion 页面能力。

| 任务 | 输入 | 输出 | 验收标准 |
|------|------|------|---------|
| P3-1: Text+ 基础文字 | 文字内容 + 字体 + 大小 | 文字图层 | Text+ 节点创建成功 |
| P3-2: 文字关键帧动画 | 文字 + 动画类型(fade/slide/bounce) | 动画文字 | 位置/透明度/缩放关键帧 |
| P3-3: 逐字符动画 | 文字 + 弹性参数 | 逐字弹跳效果 | 类似 AE Text Animator |
| P3-4: 遮罩转场 | 两个 Clip + 遮罩形状 | 遮罩转场 | Merge + Mask 节点动画 |
| P3-5: RGB 分离转场 | 两个 Clip + 分离参数 | Glitch 转场 | ChannelBooleans 位移 |
| P3-6: Glow 光效 | Clip + 光效参数 | 发光效果 | Glow 节点应用 |
| P3-7: 粒子效果（基础） | 参数配置 | 粒子图层 | pEmitter 节点（需 Studio） |
| P3-8: Fusion Macro 保存 | 节点流 | .setting 文件 | 可复用的转场/特效预设 |
| P3-9: 2.5D 视差 | 分层素材(前景/背景) | 视差效果 | Camera3D + Transform3D |

**关键技术点**：
- Fusion 节点流通过 Lua 脚本生成 `.setting` 文件，再加载到 Clip 的 Fusion 页面
- 文字动画需要 `StyledText` + `Shake`/`Transform` 修改器
- 粒子效果免费版受限，pEmitter 功能有限

**验收**：产出 3 个 Fusion Macro 预设（Zoom转场/Glitch转场/文字弹出）→ 可拖拽复用。

---

### P4: 全流程贯通（预计 3-5 天）

**目标**：将 P1-P3 能力整合到 unified_pipeline 的 S0-S6 阶段。

| 任务 | 输入 | 输出 | 验收标准 |
|------|------|------|---------|
| P4-1: Resolve 执行引擎 | 风格化规划 JSON | Resolve 操作指令集 | 将 S4 输出转为 Resolve API 调用 |
| P4-2: S5 阶段替换 | v2 管线的 S5 输出 | Resolve 时间线 | 替代 FFmpeg 执行环节 |
| P4-3: Deliver 渲染 | 时间线 + 渲染配置 | MP4/MOV 文件 | H.264 1080p 输出成功 |
| P4-4: FFmpeg 降级路径 | Resolve 失败 | FFmpeg 后处理 | Resolve 不可用时自动降级 |
| P4-5: 端到端验证 | 参考视频 + BGM + 素材 | 最终成片 | 完整跑通 S0→S6 |
| P4-6: 性能基准测试 | 标准测试集 | 耗时/质量报告 | 与 FFmpeg 方案对比 |

**整合架构**：
```python
# unified_pipeline.py S5 阶段伪代码
def stage5_execute(plan, materials, bgm):
    resolve = ResolveTaskDispatcher()
    
    if resolve.is_available():
        # 新路径: Resolve 全功能执行
        engine = ResolveAutomationEngine()
        engine.create_project(plan.project_name)
        engine.import_media(materials)
        engine.build_timeline(plan.clips)       # P1
        engine.apply_speed_ramps(plan.ramps)    # P1
        engine.apply_transitions(plan.transitions)  # P1+P3
        engine.apply_camera_moves(plan.cameras) # P1
        engine.apply_color_grade(plan.grading)  # P2
        engine.apply_fusion_effects(plan.effects)   # P3
        engine.render(output_path)              # P4
    else:
        # 降级路径: FFmpeg 后处理（现有逻辑）
        ffmpeg_execute(plan, materials, bgm)
```

**验收**：输入 `--reference clip.mp4 --bgm bgm.mp3 --materials-dir ./clips` → 自动产出带变速/调色/转场/文字的成片 → 五重验证全 PASS。

---

## 4. 技术路线

### 4.1 执行引擎选择

| 方案 | 优势 | 劣势 | 选择 |
|------|------|------|------|
| **fuscript.exe + Lua** | 免费版可用、稳定、已有 3141 行基础 | Lua 生态小、Fusion 节点脚本复杂 | ✅ **主力** |
| Python API (`DaVinciResolveScript`) | Python 生态好、类型提示 | 免费版外部脚本受限、fusionscript.dll 加载问题 | ⚠️ 备选 |
| UXP 插件 | 官方支持、异步 API | PR 的 UXP 都实验性，Resolve 的更不成熟 | ❌ 不选 |

**决策**：以 **fuscript.exe + Lua** 为主力执行引擎，原因：
1. 现有 `davinci_fuscript.py` 已有 3141 行成熟代码
2. 免费版不受限（Python API 外部调用需 Studio 版）
3. Lua 是 Fusion 的原生脚本语言，节点操作最直接

### 4.2 通信层设计

```
┌─────────────────────────────────────────────────────┐
│  Python 管线层 (unified_pipeline.py)                  │
│  ↓ 生成操作指令集 (JSON)                               │
│  resolve_command.json                                 │
│  {                                                    │
│    "command": "applySpeedRamp",                       │
│    "clip_index": 3,                                   │
│    "curve": [{"t":0,"speed":1.0},{"t":0.3,"speed":0.2},  │
│              {"t":0.7,"speed":0.2},{"t":1.0,"speed":3.0}] │
│  }                                                    │
└────────────────────┬──────────────────────────────────┘
                     │ 文件投递（与 PR Bridge 同构）
┌────────────────────▼──────────────────────────────────┐
│  fuscript.exe 执行层                                    │
│  fuscript.exe -lua resolve_executor.lua                 │
│  ↓ 读取 resolve_command.json                            │
│  ↓ 生成并执行 Lua 脚本                                   │
│  ↓ 写入 resolve_result.json                             │
└─────────────────────────────────────────────────────┘
```

**与现有 PR Bridge 的关系**：
- 通信协议同构（JSON 文件投递）
- 可复用 `ResolveTaskDispatcher` 的调度逻辑
- 新建 `resolve_command.json` / `resolve_result.json`（不与 PR 的 `pr_command.json` 冲突）

### 4.3 代码组织

```
integrations/
├── davinci_fuscript.py          # 现有 v4.0 调色引擎（保留）
├── davinci_resolve_automation.py # 新增: 全功能自动化引擎
│   ├── ResolveAutomationEngine   # 主引擎类
│   ├── SpeedRampController       # P1 变速
│   ├── TransitionController      # P1+P3 转场
│   ├── CameraMoveController      # P1 拉镜
│   ├── ColorGradeController      # P2 调色（扩展现有）
│   ├── FusionEffectController    # P3 Fusion 特效
│   └── TextAnimationController   # P3 文字动画
── resolve_command_schema.json   # 命令协议定义
└── fusion_macros/                # P3 Fusion Macro 预设库
    ├── zoom_transition.setting
    ├── glitch_transition.setting
    ── text_pop.setting

scripts/
── resolve_executor.lua          # fuscript 执行器（Lua）
└── resolve_pipeline_runner.py    # 端到端运行脚本

tests/
├── test_resolve_p0.py            # P0 通信测试
├── test_resolve_p1.py            # P1 剪辑测试
├── test_resolve_p2.py            # P2 调色测试
├── test_resolve_p3.py            # P3 Fusion 测试
└── test_resolve_e2e.py           # P4 端到端测试
```

---

## 5. 风险与备选方案

### 5.1 风险矩阵

| # | 风险 | 概率 | 影响 | 缓解措施 |
|---|------|------|------|---------|
| R1 | **免费版 vs Studio 版差异** | 高 | 中 | 光流补帧/降噪/pEmitter 需 Studio；免费版用 FFmpeg 降级 |
| R2 | **Fusion 节点脚本化复杂度高** | 高 | 高 | 先做 Edit 页面能力（变速/转场），Fusion 逐步推进 |
| R3 | **fuscript.exe Lua API 文档不全** | 中 | 中 | 用 Resolve 内置控制台交互式探索 + 录制宏 |
| R4 | **Resolve 进程稳定性** | 低 | 高 | 超时保护 + 自动重启 + 项目自动保存 |
| R5 | **Python API 免费版外部调用受限** | 高 | 低 | 已决策用 fuscript+Lua，不依赖 Python API |
| R6 | **Fusion Macro 跨版本兼容性** | 中 | 低 | 锁定 Resolve 版本，Macro 带版本标记 |

### 5.2 降级策略

```
优先级 1: Resolve 全功能执行（Edit + Color + Fusion）
    ↓ 失败
优先级 2: Resolve 部分执行（Edit + Color，Fusion 降级为 FFmpeg）
    ↓ 失败
优先级 3: Resolve 仅调色（Color 页面），剪辑/特效用 FFmpeg
    ↓ 失败
优先级 4: 纯 FFmpeg 后处理（现有 v2 管线，已验证可行）
```

**关键原则**：每一步降级都有已验证的备选方案，不会阻塞管线运行。

---

## 6. 与现有管线的整合

### 6.1 unified_pipeline.py S0-S6 阶段映射

| 阶段 | 现有实现 | Resolve 整合方式 |
|------|---------|-----------------|
| **S0 环境自检** | 检查 ffmpeg/librosa/cv2 | + 检查 Resolve 进程 + fuscript.exe |
| **S1 风格分析** | StyleFingerprintExtractor | 不变（AI 分析层） |
| **S2 音乐感知** | BeatOrchestrator | 不变（音频分析层） |
| **S3 素材选择** | 内容评分+能量匹配 | 不变（决策层） |
| **S4 风格化规划** | 生成 FFmpeg 命令 | **改为生成 Resolve 操作指令集** |
| **S5 执行** | FFmpeg 逐段处理 | **改为 ResolveAutomationEngine 执行** |
| **S6 验证** | 五重验证 | + Resolve 回读验证（替代 ffprobe） |

### 6.2 S4 阶段输出格式变更

**现有（FFmpeg 命令）**：
```json
{
  "segments": [
    {"file": "clip_01.mp4", "speed": 1.0, "grade": "cinematic", "transition": "dissolve"},
    {"file": "clip_02.mp4", "speed": 0.5, "grade": "warm_vintage", "transition": "xfade_zoom"}
  ]
}
```

**目标（Resolve 操作指令集）**：
```json
{
  "project_name": "VinlandAMV_20260804",
  "timeline": {"resolution": "1920x1080", "fps": 24},
  "clips": [
    {
      "source": "clip_01.mp4",
      "track": "V1",
      "start_frame": 0,
      "speed_ramp": {
        "mode": "curve",
        "points": [{"t": 0, "speed": 1.0}, {"t": 0.3, "speed": 0.2}, {"t": 0.7, "speed": 0.2}, {"t": 1.0, "speed": 3.0}],
        "interpolation": "bezier",
        "optical_flow": true
      },
      "color_grade": {
        "preset": "cinematic",
        "nodes": [
          {"type": "color_wheel", "wheel": "gain", "rgb": [1.1, 1.0, 0.9]},
          {"type": "curve", "curve": "custom", "points": [[0,0],[0.3,0.2],[0.7,0.8],[1,1]]}
        ]
      },
      "transition_out": {
        "type": "zoom_impact",
        "duration_frames": 12,
        "fusion_macro": "zoom_transition.setting"
      },
      "camera_move": {
        "type": "ken_burns",
        "start": {"zoom": 1.0, "x": 0, "y": 0},
        "end": {"zoom": 1.3, "x": 50, "y": -30},
        "easing": "ease_in_out"
      }
    }
  ],
  "text_overlays": [
    {"content": "進撃", "font": "Noto Sans JP Bold", "start_frame": 24, "end_frame": 48, "animation": "pop_in"}
  ],
  "render": {"format": "MP4", "codec": "H.264", "quality": "Best"}
}
```

### 6.3 FFmpeg 角色重新定义

| 环节 | 之前 | 之后 |
|------|------|------|
| 变速 | ✅ 主力（setpts） |  降级备选 |
| 调色 | ✅ 主力（eq/colorbalance） |  降级备选 |
| 转场 | ✅ 主力（xfade） | ❌ 降级备选 |
| 文字 | ✅ 唯一（drawtext） | ❌ 降级备选 |
| **最终编码** | ✅ | ✅ **保留**（H.264/H.265 输出） |
| **音频提取** | ✅ | ✅ **保留**（ffprobe/ffmpeg） |
| **素材预处理** | ✅ | ✅ **保留**（分辨率统一/格式转换） |

---

## 7. 预期效果

### 7.1 能力上限

| 效果类型 | 能否实现 | 说明 |
|---------|---------|------|
| **"快-慢-爆"节奏变速** | ✅ | Resolve 曲线变速 + 光流补帧，可达 Aniplex/UFOtable 级别 |
| **节点级精细调色** | ✅ | 6 维曲线 + Qualifier + Power Window，超越 Lumetri |
| **遮罩/形变转场** | ✅ | Fusion Merge + Mask 节点，可自定义任意形状 |
| **RGB 分离/Glitch** | ✅ | ChannelBooleans 节点，参数化控制 |
| **2.5D 视差拉镜** | ✅ | Camera3D + Transform3D，真 3D 空间 |
| **文字逐字符动画** | ⚠️ | Text+ 修改器可实现基础版，不如 AE Text Animator 灵活 |
| **粒子/光效** | ⚠️ | pEmitter 基础版可用（免费版），高级粒子需 Studio 或 AE |

### 7.2 质量对比（预期）

```
PR+FFmpeg 方案:   ████░░░░░░  40%（变速粗糙/调色有限/无实时预览）
Resolve 自动化:  ████████░░  80%（专业级变速调色/实时预览/Fusion特效）
Resolve+AE 混合: ██████████  100%（粒子/高级文字由 AE 补充）
```

### 7.3 效率对比（预期）

| 操作 | PR+FFmpeg | Resolve 自动化 | 提升 |
|------|-----------|---------------|------|
| 参数调节 | 改代码→重跑(5-10min) | UI 拖拽实时预览(秒级) | **30-60x** |
| 调色迭代 | FFmpeg 盲调→导出对比 | Resolve 实时看效果 | **质的飞跃** |
| 转场预览 | 渲染后看 | 时间线直接播放 | **质的飞跃** |
| 批量处理 | 逐段 FFmpeg | Resolve 批量 Apply Attributes | **5-10x** |

---

## 8. 里程碑与时间线

| 阶段 | 时间 | 交付物 | 验收方式 |
|------|------|--------|---------|
| **P0** 基础通信 | 第 1-2 天 | `test_resolve_p0.py` 全 PASS | 自动化测试 |
| **P1** 剪辑自动化 | 第 3-7 天 | 带变速/转场/拉镜的时间线 | 手动预览 + 截图 |
| **P2** 调色自动化 | 第 8-10 天 | 节点调色后的导出帧 | ΔE 对比验证 |
| **P3** Fusion 特效 | 第 11-17 天 | 3 个 Fusion Macro 预设 | 拖拽复用测试 |
| **P4** 全流程贯通 | 第 18-22 天 | 端到端成片 + 五重验证 | 完整管线跑通 |
| **缓冲** | 第 23-25 天 | Bug 修复 + 文档 | - |

**总计**：约 25 个工作日（5 周）

---

## 9. 快速启动指南

### 9.1 环境准备

```powershell
# 1. 确认 DaVinci Resolve 已安装
Test-Path "D:\DaVinci Resolve\Resolve.exe"

# 2. 确认 fuscript.exe 存在
Test-Path "D:\DaVinci Resolve\fuscript.exe"

# 3. 启动 Resolve（必须保持运行）
Start-Process "D:\DaVinci Resolve\Resolve.exe"

# 4. 验证 fuscript 连接
& "D:\DaVinci Resolve\fuscript.exe" -lua -e 'print("Resolve connected")'
```

### 9.2 第一个测试脚本

```python
# tests/test_resolve_p0.py
import sys
sys.path.insert(0, r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault")

from integrations.davinci_fuscript import ResolveColorEngine

engine = ResolveColorEngine(resolve_home=r"D:\DaVinci Resolve")
print(f"fuscript: {engine.fuscript_path}")
print(f"Resolve running: {engine.check_resolve_running()}")

# 创建项目
result = engine.create_project("TestP0", media_paths=[], config=None)
print(f"Project created: {result.success}")
```

---

## 10. 决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| 执行引擎 | fuscript.exe + Lua | 免费版可用、已有 3141 行基础、Fusion 原生语言 |
| 通信协议 | JSON 文件投递 | 与 PR Bridge 同构、简单可靠 |
| Python API | 不采用 | 免费版外部调用受限、fusionscript.dll 加载不稳定 |
| Fusion 特效 | 逐步推进 | 先做 Edit 页面能力，Fusion 复杂节点后做 |
| FFmpeg 角色 | 降级备选 + 最终编码 | 保留为降级路径，最终编码仍用 FFmpeg |
| AE 协作 | 暂不整合 | 先完成 Resolve 全功能，后续再加 AE 粒子/文字 |

---

*方案结束。待审批后进入 P0 阶段开发。*
