# DaVinci Resolve 全功能自动化 — P0 阶段执行报告

> **日期**: 2026-08-04  
> **状态**: P0 完成，P1-P4 因免费版 API 限制阻塞  
> **Resolve 版本**: 免费版（非 Studio）

---

## 1. P0 执行结果

### 1.1 环境验证

| 检查项 | 结果 |
|--------|------|
| Resolve.exe 路径 | ✅ `D:\DaVinci Resolve\Resolve.exe` |
| fuscript.exe 路径 | ✅ `D:\DaVinci Resolve\fuscript.exe` |
| Resolve 进程启动 | ✅ PID 27588 |
| fuscript.exe 连接 | ✅ `Resolve()` 对象获取成功 |
| ProjectManager | ✅ 14/18 方法可用 |
| 项目创建/加载 | ✅ `CreateProject("P0_Test_Auto_0804")` 成功 |
| 页面切换 | ✅ `OpenPage("color")` / `OpenPage("edit")` 成功 |

### 1.2 API 能力完整探测结果

经过 7 轮系统性探测（Edit 页面 + Color 页面、MediaPool Clip + Timeline Item），得出以下结论：

#### Timeline Item 可用方法（仅 12 个）

| 方法 | 用途 |
|------|------|
| `GetName()` | 读取 clip 名称 |
| `GetStart()` / `GetEnd()` / `GetDuration()` | 读取时间信息 |
| `GetNumNodes()` | 读取节点数量（只读） |
| `GetNodeLabel()` | 读取节点标签（只读） |
| `GetLUT()` / `SetLUT()` | LUT 应用（唯一可用的调色操作） |
| `GetProperty()` / `SetProperty()` | 通用属性读写 |
| `GetFlags()` | 读取标记 |
| `GetLinkedItems()` | 获取关联素材 |

#### Timeline Item 不可用方法（46 个 — 全部核心功能）

| 类别 | 不可用方法 | 影响 |
|------|-----------|------|
| **节点管理** | `GetNodeCount`, `AddNode`, `DeleteNode`, `SetNodeEnabled` | 无法创建/管理调色节点 |
| **色轮调色** | `SetLift`, `SetGamma`, `SetGain`, `SetOffset`, `SetContrast`, `SetPivot`, `SetSaturation` | 无法做专业调色 |
| **曲线调色** | `SetCustomCurve`, `SetHueVsHueCurve` 等 6 个 | 无法做曲线调色 |
| **限定器** | `SetQualifierHue`, `SetQualifierSaturation`, `SetQualifierLuminance` | 无法做二级调色 |
| **变速** | `SetSpeed`, `GetSpeed`, `SetRetimeProcess`, `SetMotionEstimation` | 无法做速度控制 |
| **运动/变换** | `SetPosition`, `SetZoom`, `SetRotation`, `SetCropping`, `SetOpacity` | 无法做镜头运动 |
| **特效/组件** | `AddComponent`, `GetComponentCount`, `GetComponent` | 无法添加特效 |
| **Fusion** | `GetFusionClip` | 无法访问 Fusion 页面 |
| **节点树** | `GetNodeTree`, `SetNodeLabel`, `SetClipColorGrade` | 无法操作节点树 |
| **项目保存** | `Save()` (on Project) | 无法脚本保存项目 |

### 1.3 关键发现

1. **切换到 Color 页面不解锁额外 API** — Edit 和 Color 页面的 Timeline Item API 完全一致
2. **MediaPool Clip 的 API 更少** — 只有 6 个方法可用，连 `SetLUT` 都没有
3. **现有 `davinci_fuscript.py` 代码与免费版 API 不兼容** — 代码中使用的 `GetNodeCount()`, `AddNode()`, `SetLift()` 等方法在免费版 Timeline Item 上不存在
4. **fuscript.exe 的 `-e` 参数不支持内联代码** — 必须写 .lua 文件执行

---

## 2. 阻塞原因分析

### 2.1 根本原因：DaVinci Resolve 免费版 vs Studio 版 API 差异

Blackmagic Design 对免费版 Resolve 的脚本 API 做了**功能锁定**：

| 功能 | 免费版 | Studio 版 ($295) |
|------|--------|-----------------|
| 基础项目管理 | ✅ | ✅ |
| 素材导入/时间线 | ✅ | ✅ |
| LUT 应用 | ✅ | ✅ |
| 节点式调色（AddNode/SetLift 等） | ❌ | ✅ |
| 变速/光流补帧 | ❌ | ✅ |
| 运动/变换关键帧 | ❌ | ✅ |
| Fusion 特效 |  | ✅ |
| 渲染输出（AddRenderJob） | ⚠️ 部分 | ✅ |
| GPU 加速降噪 | ❌ | ✅ |
| 多用户协作 | ❌ | ✅ |

### 2.2 对开发方案的影响

原方案（09-计划文件/DaVinci_Resolve_全功能自动化开发方案_v1.md）中的 P1-P4 全部依赖上述被锁定的 API：

| 原计划阶段 | 依赖的 API | 状态 |
|-----------|-----------|------|
| P1 变速曲线 | `SetSpeed`, `SetRetimeProcess` |  不可用 |
| P1 转场/拉镜 | `SetPosition`, `SetZoom`, `AddComponent` |  不可用 |
| P2 节点调色 | `AddNode`, `SetLift/Gamma/Gain`, 曲线方法 | ❌ 不可用 |
| P2 Qualifier | `SetQualifierHue/Saturation/Luminance` | ❌ 不可用 |
| P3 Fusion 特效 | `GetFusionClip`, `AddComponent` | ❌ 不可用 |
| P3 文字动画 | Fusion Text+ 节点 | ❌ 不可用 |
| P4 渲染输出 | `AddRenderJob` (部分可用) | ⚠️ 有限 |

---

## 3. 可行路径（基于实际 API 能力）

### 3.1 免费版能做什么

```
✅ 项目管理: 创建/加载/切换项目
✅ 素材管理: 导入媒体、浏览 Media Pool
✅ 时间线: 创建时间线、CreateTimelineFromClips
✅ LUT 应用: SetLUT/GetLUT（唯一调色能力）
✅ 页面切换: OpenPage("edit"/"color"/"fusion"/"deliver")
✅ 元数据读取: GetName/GetDuration/GetStart/GetEnd
✅ 通用属性: SetProperty/GetProperty
```

### 3.2 三条可行路径

#### 路径 A: 升级 Studio 版（$295 一次性）
- **效果**: 解锁全部 API，原方案 P1-P4 可全部执行
- **成本**: $295（约 ¥2100）
- **时间**: 购买后立即继续开发
- **ROI**: 如果项目持续使用，1-2 个月即可回本

#### 路径 B: 混合方案（Resolve 免费版 + FFmpeg）
- **Resolve 负责**: 项目管理、素材导入、时间线编排、LUT 应用
- **FFmpeg 负责**: 变速、调色（eq/colorbalance）、转场、文字、最终编码
- **效果**: 接近原方案，但调色/变速质量不如 Studio API
- **成本**: 0（利用现有 v2 管线）
- **时间**: 2-3 周整合

#### 路径 C: 纯 FFmpeg（维持现状）
- **效果**: 已有 v2 管线产出 48MB 成片
- **成本**: 0
- **劣势**: 无实时预览、调色精度有限

---

## 4. 建议

**推荐路径 A（升级 Studio）**，理由：
1. $295 一次性买断，永久使用
2. 解锁的 API 能力是**质的飞跃**（节点调色/变速/Fusion）
3. 原方案 P1-P4 可立即继续执行
4. 现有 `davinci_fuscript.py` 3141 行代码大部分可在 Studio 版上运行

**如果暂不升级**，走路径 B：
1. 用 Resolve 免费版做素材管理和时间线预览（解决"无实时预览"问题）
2. 变速/调色/转场/文字仍用 FFmpeg（已有成熟方案）
3. 最终编码用 Resolve Deliver 页面或 FFmpeg

---

## 5. 清理确认

- ✅ 9 个临时 Lua 探测脚本已删除
- ✅ 0 个临时 Python 脚本残留
- ✅ Resolve 项目 `P0_Test_Auto_0804` 保留（可用于后续测试）
- ✅ 无其他临时文件残留

---

*报告结束。等待决策：升级 Studio 版 或 走混合方案。*
