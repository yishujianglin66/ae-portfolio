# 第三阶段：ExtendScript Debugger 调试器深度集成

> **插件**: adobe.extendscript-debug v2.1.0 (Adobe 官方)
> **核心**: 将 VSCode 调试协议桥接到 AE ExtendScript 引擎
> **能力**: 断点、变量监视、调用堆栈、条件断点、异常捕获

---

## 3.1 工作原理

```
┌──────────────┐    Debug Protocol     ┌──────────────────┐
│   VSCode     │ ◄──────────────────► │  ExtendScript     │
│  Debugger UI │    (TCP :8090)       │  Engine in AE     │
│              │                      │                   │
│ - 断点管理   │                      │ - 脚本执行         │
│ - 变量监视   │                      │ - 断点命中         │
│ - 调用堆栈   │                      │ - 变量返回         │
│ - 表达式求值 │                      │ - 异常报告         │
└──────────────┘                      └──────────────────┘
```

### 通信协议

- **传输层**: TCP 套接字
- **默认端口**: 8090 (调试器引擎)
- **协议**: Adobe ExtendScript Debug Protocol (类 V8 Inspector)
- **AE 版本需求**: AE 2023+ (CC 2023 以上)

## 3.2 launch.json 完整配置

### 文件位置

```
{workspace}/.vscode/launch.json
```

### 配置 1：启动并调试 (Launch)

直接将当前 .jsx 文件发送到 AE 并自动在入口处暂停。

```json
{
    "version": "0.2.0",
    "configurations": [
        {
            // ═══════════════════════════════════════════
            // 配置 A: 启动当前 JSX 文件并调试
            // ═══════════════════════════════════════════
            "type": "extendscript-debug",
            "request": "launch",
            "name": "🚀 AE — 启动并调试当前 JSX",
            "program": "${file}",
            "hostAppSpecifier": "aftereffects",
            "engineName": "main",
            "stopOnEntry": true,
            "trace": {
                "allCalls": false,
                "engineCalls": false
            },
            "preLaunchTask": ""
        },
        {
            // ═══════════════════════════════════════════
            // 配置 B: 附加到 AE (调试已在运行的脚本)
            // ═══════════════════════════════════════════
            "type": "extendscript-debug",
            "request": "attach",
            "name": "🔗 AE — 附加到已在运行的脚本",
            "hostAppSpecifier": "aftereffects",
            "engineName": "main",
            "port": 8090
        },
        {
            // ═══════════════════════════════════════════
            // 配置 C: 运行当前文件 (不暂停)
            // ═══════════════════════════════════════════
            "type": "extendscript-debug",
            "request": "launch",
            "name": "▶️ AE — 直接运行 (不调试)",
            "program": "${file}",
            "hostAppSpecifier": "aftereffects",
            "engineName": "main",
            "stopOnEntry": false
        },
        {
            // ═══════════════════════════════════════════
            // 配置 D: 调试 Host 端 ExtendScript
            // ═══════════════════════════════════════════
            "type": "extendscript-debug",
            "request": "launch",
            "name": "🏠 AE — 调试 CEP Host (index.jsx)",
            "program": "${workspaceFolder}/host/index.jsx",
            "hostAppSpecifier": "aftereffects",
            "engineName": "main",
            "stopOnEntry": true,
            "trace": {
                "allCalls": true,
                "engineCalls": false
            }
        },
        {
            // ═══════════════════════════════════════════
            // 配置 E: 调试 F 模块
            // ═══════════════════════════════════════════
            "type": "extendscript-debug",
            "request": "launch",
            "name": "🧩 AE — 调试特定 F 模块",
            "program": "${file}",
            "hostAppSpecifier": "aftereffects",
            "engineName": "main",
            "stopOnEntry": false,
            "args": ["${input:moduleName}"]
        }
    ],
    "inputs": [
        {
            "id": "moduleName",
            "type": "pickString",
            "description": "选择要调试的 F 模块",
            "options": [
                "F1 - Logger",
                "F2 - Text Animation",
                "F3 - Preset Files",
                "F4 - Audio Import",
                "F5 - Vocal Separation",
                "F6 - Batch Import",
                "F7 - File Download",
                "F8 - Path Detection"
            ]
        }
    ]
}
```

### 配置参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `type` | string | 固定为 `"extendscript-debug"` |
| `request` | `"launch"` / `"attach"` | launch=启动新脚本, attach=附加到运行中的 |
| `program` | string | 目标 .jsx 文件路径。`${file}` = 当前打开文件 |
| `hostAppSpecifier` | string | 目标 Adobe 应用: `aftereffects`, `photoshop`, `illustrator` 等 |
| `engineName` | string | ExtendScript 引擎名，通常为 `"main"` |
| `stopOnEntry` | boolean | 是否在脚本入口第一行自动暂停 |
| `trace.allCalls` | boolean | 是否跟踪所有函数调用 (性能开销大) |
| `trace.engineCalls` | boolean | 是否跟踪 ExtendScript 引擎内部调用 |
| `port` | number | attach 模式使用的 TCP 端口 |

## 3.3 条件断点与日志断点

### 条件断点

在循环中仅在特定条件下暂停 — 不影响不满足条件的迭代。

**设置方法**:
1. 在 VSCode 行号左侧右键 → `Add Conditional Breakpoint`
2. 输入条件表达式，例如：

```javascript
// 示例 1: 仅在第 5 次循环时暂停
i === 5

// 示例 2: 仅当图层名称为特定值时暂停
layer.name === "target_layer"

// 示例 3: 仅当文件大小超过阈值
file.length > 104857600  // 100 MB
```

**适用场景**:
| 场景 | 条件表达式 | 说明 |
|------|-----------|------|
| 循环中追踪特定项 | `layer.name.indexOf("背景") >= 0` | 仅在处理背景层时暂停 |
| 大循环中后期调试 | `i > 100 && i < 110` | 仅在 100-109 次迭代暂停 |
| 调试特定文件 | `filePath.indexOf("audio.wav") >= 0` | 特定文件处理时暂停 |
| 错误状态检查 | `result.success === false` | 失败时立即中断 |

### 日志断点 (Logpoint)

不暂停执行，仅输出变量值到调试控制台 — 相当于非侵入式的 `$.writeln()`。

**设置方法**:
1. 在 VSCode 行号左侧右键 → `Add Logpoint`
2. 输入要输出的消息（支持 `{}` 表达式插值）：

```javascript
// 示例 1: 输出图层名和索引
图层 {i}: {layer.name}, 类型: {layer.constructor.name}

// 示例 2: 输出文件大小
处理文件: {filePath}, 大小: {file.length} bytes

// 示例 3: 追踪 dispatch 调用
[cepDispatch] action={action}, params={paramsJson}
```

**适用场景**:
| 场景 | 日志表达式 |
|------|-----------|
| 追踪 dispatch 调用链 | `dispatch: {action} — {JSON.stringify(params)}` |
| 监控异步操作轮询 | `轮询 #{attempt}: status={response.status}` |
| 追踪文件 I/O | `读取: {file.fsName} ({file.length} bytes)` |

### 为何日志断点优于 $.writeln()

| 对比维度 | 日志断点 | $.writeln() |
|----------|----------|-------------|
| 修改代码 | ❌ 不需要 | ✅ 需要修改源码 |
| 性能开销 | 极低 | 中等 (文件 I/O) |
| 清除 | 一键删除断点 | 需手动删除代码 |
| 条件输出 | 原生支持 | 需手写 if 判断 |
| 格式化 | `{}` 插值 | 需字符串拼接 |

## 3.4 异常捕获配置

### 在未捕获异常时自动中断

在此项目的 `.vscode/settings.json` 中添加：

```json
{
    "extendscript.debug.breakOnCaughtExceptions": false,
    "extendscript.debug.breakOnUncaughtExceptions": true,
    "extendscript.debug.showExceptionStack": true
}
```

### 异常分析流程

```
异常抛出
    │
    ├─ breakOnUncaughtExceptions = true → 自动暂停
    │
    ├─ 查看 VSCode "变量" 面板:
    │   ├─ 局部变量 (Local): 当前函数作用域
    │   ├─ 闭包变量 (Closure): 父函数作用域
    │   └─ 全局变量 (Global): AEStudioKit, CONFIG 等
    │
    ├─ 查看 "调用堆栈" 面板:
    │   ├─ 最上层: 异常发生的确切位置
    │   ├─ 逐层向下: 调用链路
    │   └─ 点击每层可跳转到对应代码
    │
    └─ 调试控制台执行表达式:
        ├─ 检查对象: > layer.name
        ├─ 测试修复: > typeof cepDispatch
        └─ 验证假设: > AEStudioKit.scriptDir
```

### 异常类型速查

| 异常类型 | 常见原因 | 排查方向 |
|----------|----------|----------|
| `ReferenceError: X is not defined` | 依赖模块未加载 | 检查 `$.evalFile()` 顺序 |
| `TypeError: undefined is not an object` | 访问未初始化对象的属性 | 添加 `typeof` 守卫 |
| `SyntaxError` | ES6+ 语法在 ES3 环境中 | 检查 const/let/=>/`` |
| `IOError` | 文件不存在或权限不足 | 检查路径和 BOM |
| `Error: Cannot execute script` | AE 引擎状态异常 | 重启 AE |

## 3.5 调试黄金法则

### 🔴 遇到 "脚本无响应/无输出/图层无变化" 时的标准调试步骤

```
步骤 1: 复现
    └─ 确认问题可稳定复现 (非随机)

步骤 2: 缩小范围
    ├─ 注释掉后半部分代码 → 仍无响应? (问题在前半段)
    ├─ 二分法注释 → 定位到 ≤10 行的故障区域
    └─ 或使用日志断点标记 "经过点 A/B/C"

步骤 3: 断点定位
    ├─ 在故障区域前一行设断点
    ├─ 按 F5 启动调试 → F10 单步执行
    ├─ 每步观察:
    │   ├─ 变量面板: 当前变量值是否符合预期?
    │   ├─ 调用堆栈: 在哪个函数中?
    │   └─ 调试控制台: > app.project.activeItem 验证 AE 状态

步骤 4: 检查 AE 对象模型
    ├─ 当前合成: app.project.activeItem instanceof CompItem?
    ├─ 选中图层: comp.selectedLayers.length > 0?
    ├─ 图层类型: layer instanceof TextLayer / AVLayer?
    ├─ 属性存在: layer.property("ADBE Text Properties")?
    └─ AE 版本 API: app.version → API 兼容性矩阵

步骤 5: 修复 → 重新运行
    ├─ 在调试控制台测试修复 (即时反馈)
    ├─ 将修复应用到源代码
    ├─ 取消所有断点 → F5 完整运行 → 确认修复
    └─ 添加回归日志断点以防回归
```

## 3.6 调试实例教程

### 案例：调试 "文字动画应用.jsx" — "未正确选中文字图层" bug

**问题描述**: 用户调用 `applyPresetToSelected` 时返回 `{success: false, message: "未选中文字图层"}`，但在 AE 中确实选中了一个图层。

#### 步骤 1: 设置断点

在 `apply-preset.jsx` 的 `applyPresetToSelected` 函数入口处设断点：

```javascript
// apply-preset.jsx — 在此行设断点 ▼
MotionStudio.TextFx.applyPresetToSelected = function(presetId, options) {
    try {
        var comp = app.project.activeItem;      // ← 断点 1
        var layers = comp.selectedLayers;        // ← 断点 2
```

#### 步骤 2: 启动调试

1. VSCode: 按 `F5`，选择 "🚀 AE — 启动并调试当前 JSX"
2. 在 AE 面板点击 "应用文字动画"
3. 断点 1 被触发，VSCode 自动跳转到该行

#### 步骤 3: 检查变量

在调试控制台执行：
```javascript
> app.project.activeItem
// 输出: [object CompItem] ✅ 合成存在

> app.project.activeItem.name
// 输出: "Comp 1" ✅

> comp.selectedLayers
// 输出: [object Array] ✅ 有选中图层

> comp.selectedLayers.length
// 输出: 1 ✅

> comp.selectedLayers[0].name
// 输出: "白色 纯色 1" ← ❌ 这不是文字图层!

> comp.selectedLayers[0] instanceof TextLayer
// 输出: false ← 🔴 Bug! 选中的是纯色图层，不是文字图层!
```

#### 步骤 4: 验证修复

```javascript
> comp.selectedLayers[0] instanceof AVLayer
// 输出: true
> comp.selectedLayers[0] instanceof ShapeLayer
// 输出: false
```

#### 步骤 5: 确认根本原因

选中的图层是 `AVLayer` (纯色/视频图层)，不是 `TextLayer`，所以文字引擎正确拒绝了操作。错误消息 "未选中文字图层" 是正确的——但错误提示可以更明确。

#### 步骤 6: 改进错误消息

修改代码使错误消息包含实际图层类型：
```javascript
if (!(layer instanceof TextLayer)) {
    return {
        success: false,
        message: "图层 \"" + layer.name + "\" 类型为 " +
                 (layer.constructor.name || "未知") +
                 "，不是文字图层。请选中文字图层后重试。"
    };
}
```

#### 完整的调试流程时序图

```
时间轴:
T0: F5 → 启动调试会话
T1: AE 面板点击按钮 → evalScript 触发
T2: 断点 1 命中 → VSCode 暂停
T3: 单步执行 (F10) → 进入函数体
T4: 变量检查 → 发现图层类型不匹配
T5: 调试控制台测试修复方案
T6: Shift+F5 → 停止调试
T7: 应用修复代码
T8: F5 → 重新运行 → ✅ 通过
```

---

> **下一阶段**: [PHASE4_JSX_SNIPPETS.md](./PHASE4_JSX_SNIPPETS.md)
