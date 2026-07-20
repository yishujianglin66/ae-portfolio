# F1 — 图层类型自动识别: 完整研究报告

> 日期: 2026-06-05 | 版本: v1.0.0 | 状态: 待用户验证

---

## A. 对象模型验证 (Object Model Verification)

### 涉及 API 与兼容性确认

| API | 引入版本 | AE 2023-25 状态 | 风险等级 | 备注 |
|-----|----------|-----------------|---------|------|
| `app.project` | CS3 | ✅ 确认可用 | 无 | 所有版本 |
| `CompItem` | CS3 | ✅ 确认可用 | 无 | 父类 Item |
| `app.project.activeItem` | CS3 | ✅ 确认可用 | 无 | 返回当前焦点项 |
| `comp.selectedLayers` | CS3 | ✅ 确认可用 | 低 | 返回 Array, 非 null |
| `instaneof TextLayer` | CS3 | ✅ 确认可用 | 低 | 文字图层首选判断 |
| `instaneof ShapeLayer` | CS3 | ✅ 确认可用 | 无 | 形状图层 |
| `instaneof CameraLayer` | CS3 | ✅ 确认可用 | 无 | 摄像机 |
| `instaneof LightLayer` | CS3 | ✅ 确认可用 | 无 | 灯光 |
| `instaneof AVLayer` | CS3 | ✅ 确认可用 | 无 | 音频/视频/固态/空 |
| `instaneof SolidSource` | CS3 | ✅ 确认可用 | 低 | 固态源判断 |
| `instaneof FootageItem` | CS3 | ✅ 确认可用 | 低 | 文件素材 |
| `layer.adjustmentLayer` | CS4 | ✅ 确认可用 | 中* | 某些版本可能 throw |
| `layer.hasAudio` | CS4 | ✅ 确认可用 | 中* | AVLayer 专有, 非AVLayer可能throw |
| `layer.hasVideo` | CS4 | ✅ 确认可用 | 中* | 同上 |
| `layer.source` | CS3 | ✅ 确认可用 | 中 | 可能为 null/undefined |
| `layer.source.mainSource` | CS3 | ✅ 确认可用 | 中* | 非 FootageItem 可能 throw |
| `layer.locked` | CS3 | ✅ 确认可用 | 低 | Boolean |
| `layer.shy` | CS3 | ✅ 确认可用 | 低 | Boolean |
| `layer.parent` | CS3 | ✅ 确认可用 | 低 | 可能为 null |
| `app.redraw()` | CS3 | ✅ 确认可用 | 无 | UI 刷新 |

> *标注"中"的 API 在不同图层类型上调用时可能抛出异常，已在代码中用 try/catch 包裹。

### API 继承链确认

```
Layer (抽象基类)
  ├── AVLayer (主要图层类型)
  │     ├── TextLayer      ← instanceof 判断
  │     ├── ShapeLayer     ← instanceof 判断
  │     ├── CameraLayer    ← instanceof 判断
  │     └── LightLayer     ← instanceof 判断
  └── (无其他直接子类)
```

**关键发现**: Null 对象没有专门的类 — 它就是一个 AVLayer，其 source 为 null。

---

## B. 代码骨架 (Code Skeleton)

### 文件位置
`test-suites/F1-layer-type/F1_layer_type.jsx` (272 行)

### 核心函数签名

| 函数 | 签名 | 职责 |
|------|------|------|
| `classifyLayer` | `(layer) → {type, category, details}` | 单图层白盒分类 |
| `_detectAudio` | `(footage, layer) → boolean` | 4 路径音频检测 |
| `_detectVideo` | `(layer) → boolean` | 视频标记检测 |
| `_hasParent` | `(layer) → boolean` | 父子关系检测 |
| `_safeGet` | `(obj, path, default) → *` | 深层属性安全获取 |
| `runF1LayerTypeDetection` | `() → result \| null` | 主入口, 全边界覆盖 |

### 判断优先级链

```
1. instanceof TextLayer     → "文字图层 (TextLayer)"
2. instanceof CameraLayer   → "摄像机图层 (CameraLayer)"
3. instanceof LightLayer    → "灯光图层 (LightLayer)"
4. instanceof ShapeLayer    → "形状图层 (ShapeLayer)"
5. instanceof AVLayer:
   a. adjustmentLayer       → "调整图层 (AdjustmentLayer)"
   b. source is null        → "空对象图层 (Null)"
   c. SolidSource           → "固态/纯色图层 (AVLayer+Solid)"
   d. FootageItem + audio   → "音频图层 (AVLayer+Audio)"
   e. FootageItem + video   → "视频/图像图层 (AVLayer+Video)"
   f. FootageItem + unknown → "素材图层 (Footage/其他)"
   g. 其他                  → "AVLayer (source=...)"
6. constructor.name 回退     → "未知(...)"
```

---

## C. 静态模拟执行 (Static Simulation)

### 场景 C1: 项目未打开 (app.project == null)

```
执行路径:
  runF1LayerTypeDetection()
    → 检查 typeof app === 'undefined' → false (AE 中运行)
    → 检查 !app.project → true
    → LOG.alert("错误: 未打开任何项目...")
    → return null

预期输出:
  alert: "错误: 未打开任何项目。请先打开或创建一个 AE 项目。"
  日志: [ERROR] 错误: 未打开任何项目...
  返回: null (停止执行)
```

### 场景 C2: 合成未选中 (activeItem 是 FolderItem 或 null)

```
执行路径:
  runF1LayerTypeDetection()
    → app.project → OK
    → !activeItem → true (或 activeItem 不是 CompItem)
    → LOG.alert("错误: 未选中任何项..." 或 "当前活动项不是合成...")

预期输出:
  alert: 对应的错误消息
  返回: null
```

### 场景 C3: 未选中任何图层

```
执行路径:
  runF1LayerTypeDetection()
    → comp is CompItem → OK
    → comp.selectedLayers.length == 0 → true
    → LOG.alert("提示: 未选中任何图层...")

预期输出:
  alert: "提示: 未选中任何图层。请在时间轴面板中选中至少一个图层后重新运行此脚本。"
  返回: null
```

### 场景 C4: 选中 1 个 TextLayer "测试文字"

```
执行路径:
  runF1LayerTypeDetection()
    → 获取所有 pre-checks 通过
    → 遍历 selectedLayers[0]
    → classifyLayer(layer):
       → instanceof TextLayer → true
       → 获取 textContent + fontName
       → 返回 {type: "文字图层 (TextLayer)", category: "text", ...}
    → 统计: categoryCounts.text = 1
    → 汇总: "文字×1"

预期 alert:
  ══════════════════════════════════
    F1 — 图层类型识别 完成
  ══════════════════════════════════
  合成: Test_Main
  选中图层数: 1
  ──────────────────────────────────
  文字×1
  ──────────────────────────────────
  日志文件: C:\Users\...\Desktop\AEStudioKit_F9_test.log
  ══════════════════════════════════

预期日志:
  [INFO] [1] 测试文字 → 文字图层 (TextLayer) (hasAudio=false, hasVideo=false, locked=false, parent=false)
```

### 场景 C5: 选中 1 个音频 AVLayer "Audio_Music"

```
执行路径:
  classifyLayer(layer):
    → instanceof TextLayer → false
    → instanceof CameraLayer → false
    → instanceof LightLayer → false
    → instanceof ShapeLayer → false
    → instanceof AVLayer → true
       → adjustmentLayer → false
       → source != null → OK
       → mainSource instanceof SolidSource → false
       → source instanceof FootageItem → true
          → _detectAudio: hasAudio=true, hasVideo=false, 扩展名=.wav → true
          → isAudio && !hasVid → true
       → 返回 {type: "音频图层 (AVLayer+Audio)", category: "audio", ...}

预期 alert:
  音频×1
```

### 场景 C6: 选中 1 个错误类型图层 (假设选中了一个 ShapeLayer)

```
执行路径:
  classifyLayer(layer):
    → instanceof TextLayer → false
    → instanceof CameraLayer → false
    → instanceof LightLayer → false
    → instanceof ShapeLayer → true  ✅
    → 返回 {type: "形状图层 (ShapeLayer)", category: "shape"}

预期 alert:
  形状×1
```

### 场景 C7: 选中 5 个混合图层

```
假设选中: TextLayer × 2, AVLayer+Audio × 1, ShapeLayer × 1, Null × 1

执行路径:
  遍历 5 个图层, 每个按对应分支分类

预期 alert:
  ══════════════════════════════════
  ...
  选中图层数: 5
  ──────────────────────────────────
  文字×2
  音频×1
  形状×1
  空对象×1
  ──────────────────────────────────
  ...
```

---

## D. 异常注入测试 (Exception Injection)

### D1: 文件写入权限被拒绝

```
模拟: 桌面目录不可写 (企业策略)

代码行为:
  AEStudioKit.Logger.init() 中 catch 块:
    → 尝试 init(Folder.temp) 作为降级方案
    → 如果 temp 也不可写 → logFile 设为 null
    → log() 中的写入操作被 try/catch 跳过, 仅保留 $.writeln

预期结果:
  - $.writeln 仍正常工作 (ExtendScript Console)
  - alert 弹窗仍正常显示
  - 日志文件写入静默失败, 不崩溃
```

### D2: layer.hasAudio 在特定图层类型上 throw

```
模拟: 选中一个 CameraLayer, 但代码尝试访问 hasAudio

代码行为:
  _detectAudio() 中 try { layer.hasAudio } catch(e) { /* 忽略 */ }
  → 返回 false → audio 被正确标记为 false

  classifyLayer() 中 CameraLayer 在 AVLayer 之前被处理
  → instaneof CameraLayer 命中 → 直接返回

预期结果:
  - CameraLayer 不会被错误分类为 audio
  - 无异常传播
```

### D3: layer.source 为空 (Null object layer)

```
模拟: 选中一个 Null 对象图层

代码行为:
  classifyLayer(layer):
    → instanceof AVLayer → true
    → adjustmentLayer → false
    → layer.source → null → 触发 null check
    → 返回 {type: "空对象图层 (Null)", category: "null"}

预期结果:
  - 正确分类为"空对象图层"
  - 无 crash, 无 undefined 属性访问
```

### D4: constructor.name 不可用 (罕见)

```
模拟: 某种未知图层类型的 constructor 没有 name 属性

代码行为:
  classifyLayer(layer):
    → 前 5 步均未命中
    → 路径 6: ctorName = "" → result.type = "未知类型"

预期结果:
  - 错误安全处理
  - 分类为"未知类型"而非 crash
```

---

## E. 测试用例说明书 (Test Case Manual)

### 测试环境准备

1. 启动 **Adobe After Effects 2025** (或 2023/2024)
2. 新建项目: 文件 → 新建 → 新建项目
3. 新建合成:
   - 合成名称: `F1_Test_Comp`
   - 预设: HDTV 1080 29.97
   - 时长: 10 秒
   - 背景色: 任意

### 创建测试图层

| 序号 | 操作 | 图层名 | 预期类型 |
|------|------|--------|---------|
| 1 | 图层 → 新建 → 文本 → 输入 "Hello 测试" | "Hello 测试" | 文字图层 |
| 2 | 图层 → 新建 → 纯色 → 红色 | "Red Solid" | 固态/纯色 |
| 3 | 图层 → 新建 → 空对象 | "Null 1" | 空对象 |
| 4 | 图层 → 新建 → 形状图层 → 矩形 | "Shape Layer 1" | 形状图层 |
| 5 | 图层 → 新建 → 摄像机 → 确定 | "Camera 1" | 摄像机 |
| 6 | 图层 → 新建 → 灯光 → 确定 | "Light 1" | 灯光 |
| 7 | 图层 → 新建 → 调整图层 | "Adjustment Layer 1" | 调整图层 |

### 测试步骤

#### 测试 T1: 基础 — 无合成选中

1. 关闭所有合成时间轴面板（或新建项目但不创建合成）
2. 运行脚本: 文件 → 脚本 → 运行脚本文件 → 选择 `F1_layer_type.jsx`
3. 预期: 弹出错误 alert, 提示未打开合成

#### 测试 T2: 基础 — 无图层选中

1. 确保合成 F1_Test_Comp 的时间轴有焦点
2. 取消所有图层选择 (Ctrl+Shift+A 或点击空白区域)
3. 运行 `F1_layer_type.jsx`
4. 预期: 弹出提示 alert, 告知未选中图层

#### 测试 T3: 核心 — 单图层逐类测试

对每个图层:
1. 仅在时间轴中选中该一个图层
2. 运行 `F1_layer_type.jsx`
3. 观察 alert 内容
4. 检查是否显示正确的图层类型

| 选中图层 | 预期 alert 中显示 |
|----------|------------------|
| "Hello 测试" | 文字×1 |
| "Red Solid" | 固态/纯色×1 |
| "Null 1" | 空对象×1 |
| "Shape Layer 1" | 形状×1 |
| "Camera 1" | 摄像机×1 |
| "Light 1" | 灯光×1 |
| "Adjustment Layer 1" | 调整层×1 |

#### 测试 T4: 核心 — 混合图层批量测试

1. 选中所有 7 个图层 (Ctrl+A)
2. 运行 `F1_layer_type.jsx`
3. 预期 alert 显示所有类型汇总: 文字×1, 固态/纯色×1, 空对象×1, 形状×1, 摄像机×1, 灯光×1, 调整层×1

#### 测试 T5: 边界 — 锁定/隐藏图层

1. 锁定 "Red Solid" 图层 (点击锁图标)
2. 隐藏 (Shy) "Shape Layer 1" 图层
3. 选中所有图层运行
4. 预期: 锁定和隐藏的图层仍然被正确识别 (锁定/Shy 不影响类型判断)

#### 测试 T6: 异常 — 图层 source 缺失

1. 导入一个文件到项目面板, 但不添加到合成
2. 将素材从项目面板拖到时间轴, 创建为图层
3. 在项目面板中重命名或删除该素材 (使 source reference 断裂)
4. 选中该图层运行脚本
5. 预期: 不崩溃, 可能分类为"空对象"或"AVLayer (source=...)"

---

## F. 通过标准 (Pass Criteria)

**当满足以下所有条件时，F1 功能单元通过：**

1. ✅ T1-T6 所有测试用例均输出预期的 alert 内容
2. ✅ 无一例崩溃、卡死、或未捕获异常
3. ✅ 每种图层类型的 alert 摘要中显示正确的类型名称（中文）
4. ✅ 日志文件在桌面上成功创建，包含每次运行的完整日志
5. ✅ 混合多图层时，汇总计数正确（无遗漏或重复）
6. ✅ 没有使用任何禁止的 ES6 语法（const/let/arrow/class/template string）
7. ✅ 异常环境（无图层、无合成、无项目）均给出友好提示而非崩溃
8. ✅ app.redraw() 调用不引起错误

---

## 附录: 代码行数统计

| 文件 | 行数 | 说明 |
|------|------|------|
| `F1_layer_type.jsx` | 272 | 主脚本 |
| `_shared/AEStudioKit_Logger.jsx` | 105 | 共享日志模块 |
| `F1_REPORT.md` | 本文件 | 研究报告 |
| `F1_test_cases.md` | — | 测试用例说明书 |
