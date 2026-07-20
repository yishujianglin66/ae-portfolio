# 第五阶段：Lingma AI 编程助手协作规则设定

> **插件**: alibaba-cloud.tongyi-lingma (通义灵码)
> **核心**: 阿里云 AI 编码助手 — 代码补全、错误解释、重构建议、自然语言到代码生成
> **能力边界**: 通义灵码了解通用 JavaScript，但不了解 Adobe ExtendScript API 特性和 CEP 通信协议

---

## 5.1 能力边界评估

### ✅ 通义灵码擅长的 AE 扩展开发任务

| 能力 | 说明 | 效果评级 |
|------|------|----------|
| **通用 JS 逻辑** | 循环、条件、数组操作、字符串处理、正则 | ⭐⭐⭐⭐⭐ |
| **错误解释** | 解读 `TypeError`/`ReferenceError`/`SyntaxError` | ⭐⭐⭐⭐⭐ |
| **代码重构** | 提取函数、消除重复、优化结构 | ⭐⭐⭐⭐ |
| **JSON 处理** | 序列化/反序列化、Schema 设计 | ⭐⭐⭐⭐⭐ |
| **异步模式** | 生成 Promise/async/回调包装 (通用模式) | ⭐⭐⭐⭐ |
| **代码补全** | 基于上下文的局部补全 | ⭐⭐⭐⭐ |
| **注释生成** | 自动生成 JSDoc 和中文注释 | ⭐⭐⭐⭐ |
| **正则表达式** | 编写和解释复杂正则 | ⭐⭐⭐⭐⭐ |

### ⚠️ 需要人工校验的能力

| 能力 | 局限性 | 校验方法 |
|------|--------|----------|
| **AE 对象模型** | 不了解 `app.project.activeItem` 等 API | 对照 AE 官方文档 |
| **ExtendScript ES3** | 可能生成 const/let/=> 等 ES6 语法 | 运行语法检查脚本 |
| **CEP 通信** | 不了解 `CSInterface.evalScript` 协议 | 在 AE 中实测 |
| **ExtendScript File API** | 可能混淆 Node.js fs 和 ExtendScript File | 检查 `new File()` 用法 |

### ❌ 通义灵码不擅长的

| 能力 | 原因 | 替代方案 |
|------|------|----------|
| **AE 特定 API 参数** | 训练数据缺乏 | 查 AE CS 文档 / 使用 `app.preferences` 探索 |
| **CEP manifest 生成** | 不了解 CSXS 规范 | 参考本项目模板 |
| **AE 版本兼容性** | 不了解版本间 API 差异 | 查 AE API 兼容性矩阵 |
| **BOM 编码** | 不了解 ExtendScript UTF-8 BOM 要求 | 使用本项目检查脚本 |

## 5.2 提示词库

### 场景 1：AE 对象模型操作

```
根据 Adobe After Effects ExtendScript 对象模型，为当前选中的文字图层添加一个淡入动画。
要求：
1. 使用 ES3 语法 (禁止 const/let/箭头函数/模板字符串/class)
2. 通过 app.project.activeItem.selectedLayers 获取图层
3. 使用 instanceof TextLayer 判断图层类型
4. 通过 sourceText.property("ADBE Opacity") 找到不透明度属性
5. 设置 3 个关键帧: 0%(0s) → 100%(1.5s)
6. 添加完整 try/catch 错误处理
7. 使用 $.writeln 日志输出
```

### 场景 2：错误诊断与自动修复

```
下面这段 ExtendScript 代码在 After Effects 2025 中抛出 "TypeError: undefined is not an object"：

    AEStudioKit.Utils.log("初始化完成", "info");

请分析可能原因并按优先级列出：
1. AEStudioKit 未定义
2. Utils 未定义
3. log 未定义
然后给出修复代码。约束: 使用 ES3 语法，用 typeof 和 undefined 守卫。
```

### 场景 3：同步→异步重构

```
将以下同步循环重构为 scheduleTask 异步模式，防止 AE UI 阻塞：

    for (var i = 0; i < items.length; i++) {
        var result = system.callSystem("python process.py " + items[i]);
        results.push(result);
    }

要求：
1. 使用 app.scheduleTask() 分片执行，每 5 个一批，间隔 50ms
2. 每批完成后更新进度
3. 全部完成后通过 cepDispatch 通知面板
4. ES3 语法 + 完整错误处理
```

### 场景 4：CEP/CSXS 配置生成

```
生成一个符合 CEP 12 规范的 manifest.xml 模板，要求：
1. ExtensionBundleId: com.mycompany.mytool
2. 扩展名称: MyTool
3. 版本: 1.0.0
4. 面板入口: ./client/index.html (700x500)
5. CEP 引擎版本: CSXS 12 (支持 AE 2025/2024/2023)
6. 主机兼容性: After Effects 23.0+
7. 包含两个 DispatchInfo: 主面板 + Studio Kit 面板
```

### 场景 5：代码审查

```
审查以下 ExtendScript 代码，找出：
1. ES6 语法违规 (应使用 ES3)
2. 潜在的 undefined 访问风险
3. 同步阻塞问题
4. 缺少错误处理的位置
5. BOM/编码相关问题

[粘贴代码]
```

### 场景 6：日志分析

```
分析以下 ExtendScript 初始化日志，定位问题并提供修复方案：

    [INFO] main.jsx 已加载
    [WARN] text-fx/apply-preset.jsx: SyntaxError: Unexpected token ':'
    [INFO] bridge/ae-bridge.jsx loaded OK
    [ERROR] studio-kit-bridge.jsx: ReferenceError: cepDispatch is not defined
    
问题可能是什么？按优先级给出修复步骤。
```

## 5.3 安全使用规则

### 🔴 绝对禁止

| 规则 | 说明 | 后果 |
|------|------|------|
| **1. 禁止上传完整项目代码** | 仅可发送 ≤200 行的局部片段 | 知识产权泄露风险 |
| **2. 禁止包含 API 密钥** | mvsep.com API key、服务器密码等 | 密钥泄露 |
| **3. 禁止包含硬编码路径** | `C:\Users\Administrator\Desktop\...` | 暴露系统结构 |
| **4. 禁止包含内网地址** | 公司服务器 IP、数据库连接串 | 网络信息泄露 |
| **5. 禁止上传签名密钥** | CEP 扩展签名证书 | 扩展被仿冒 |

### 🟡 需脱敏后使用

| 敏感信息 | 脱敏方式 | 示例 |
|----------|----------|------|
| 文件路径 | 替换为用户目录占位符 | `C:\Users\X\...` → `~/...` |
| 用户名 | 替换为 `{user}` | `Administrator` → `{user}` |
| 项目名 | 替换为 `{project}` | `ae-vocal-remover` → `{project}` |
| 端口号 | 保留 (通常不敏感) | `8765` — 可保留 |

### 🟢 安全使用场景

| 场景 | 内容范围 | 是否安全 |
|------|----------|----------|
| 单个函数调试 | ≤50 行代码 + 错误信息 | ✅ |
| ES3/ES5 语法转换 | 代码模式片段 | ✅ |
| ExtendScript API 咨询 | 自然语言问题 | ✅ |
| 通用 JS 逻辑优化 | 无 AE 特定数据 | ✅ |
| 错误消息解读 | 仅错误文本 | ✅ |

### 安全发送前检查清单

```
发送前确认:
[ ] 不包含 import/require 路径
[ ] 不包含 API key / token / secret
[ ] 不包含完整文件路径 (> 50 行)
[ ] 不包含公司内部 URL
[ ] 不包含签名证书内容
[ ] 已用 {user}/{project} 替换敏感字符串
```

## 5.4 第三方脚本分析工作流

### 从 lookae.com 等来源提取功能

```
┌─────────────────────────────────────────────────────┐
│ 步骤 1: 获取脚本                                      │
│ └─ 从 lookae.com / aescripts.com 下载 .jsx 文件      │
│                                                      │
│ 步骤 2: 安全检查                                      │
│ ├─ 扫描恶意模式: eval()、system.callSystem()、       │
│ │   Socket()、File().remove()                        │
│ ├─ 检查是否有混淆代码                                 │
│ └─ 确认脚本来源可信                                   │
│                                                      │
│ 步骤 3: 结构分析 (手动 + Lingma)                      │
│ ├─ 询问 Lingma: "解释这段 ExtendScript 的结构"         │
│ ├─ 识别入口函数和核心逻辑                             │
│ └─ 标注依赖的 AE API 调用                            │
│                                                      │
│ 步骤 4: 功能提取                                      │
│ ├─ 询问 Lingma: "仅提取 [文字动画] 相关的函数"         │
│ ├─ 将提取的函数粘贴到临时文件                         │
│ └─ 删除 UI 相关代码 (alert/Window/palette)            │
│                                                      │
│ 步骤 5: 适配本项目                                    │
│ ├─ 替换原生 logging 为 AEStudioKit.Utils.log         │
│ ├─ 添加 cepDispatch 路由                             │
│ ├─ 转换为 $.global.F#_dispatch 导出模式               │
│ └─ 确保 ES3 兼容性                                   │
│                                                      │
│ 步骤 6: 集成测试                                      │
│ ├─ 在 AE 中运行 → 检查控制台输出                     │
│ ├─ 通过 CEP 面板触发 → 检查 evalScript 返回          │
│ └─ 添加错误处理 → 提交                               │
└─────────────────────────────────────────────────────┘
```

### Lingma 提示词：脚本反向工程

```
分析以下 ExtendScript 代码片段（来源: lookae.com 文字动画预设）。
请提取：
1. 核心动画函数 (名称、参数、返回值)
2. 依赖的 AE API 调用
3. 任何 ES6 语法 (需要降级到 ES3)
4. 潜在的兼容性问题 (AE 版本 2023-2025)

[粘贴 ≤ 200 行代码]
```

---

> **下一阶段**: [PHASE6_UNIFIED_WORKFLOW.md](./PHASE6_UNIFIED_WORKFLOW.md)
