# AE StudioKit — 研究级性能重构、功能增强与高级面板集成

> 创建日期: 2026-06-05
> 状态: 第一阶段 — 遗产代码深度剖析 (已完成探索，待输出正式报告)
> 基于: F1-F9 原子功能已独立验证通过

## 背景

9 个原子功能单元 (F1-F9) 已独立验证通过，ScriptUI 集成面板已创建。但现有实现存在性能瓶颈、代码重复和架构缺陷。项目目录中 4 套代码并存，遗留了大量设计智慧和反模式。本任务对这些资产进行逆向分析，提取设计模式，推动原子模块深度优化与 CEP 高级面板架构设计。

---

## 第一阶段：遗产代码深度剖析 → 技术剖面报告

> **探索已完成** (3 个并行 agent 覆盖全部 JSX/JS/Python/HTML 资产)。待输出正式报告。

### 1.1 技术剖面报告 (10 份文档)

创建 `docs/profiles/` 目录，每份报告覆盖一个核心组件：

| # | 组件 | 源文件 | 规模 | 剖面重点 |
|---|------|--------|------|---------|
| P1 | cepDispatch 路由器 | `host/main.jsx` | 1209 行 | 30+ action 分支、bridge 协议、错误码覆盖 |
| P2 | 面板协调器 | `client/app.js` | 2113 行 | 48 函数、异步模式、STATE 竞态条件 |
| P3 | 文字动画引擎 | `host/text_engine.jsx` | 670 行 | 30 预设定义、表达式动画模式 |
| P4 | Python 桥接 | `server/ae_bridge.py` | 1278 行 | 16 子命令、OK:/ERROR: 协议、超时处理 |
| P5 | FastAPI 服务 | `server/server.py` | 2204 行 | 31 端点、后台任务、SSE 流 |
| P6 | AI 音效引擎 | `server/effects.py` | 294 行 | 5 类 18 效果、DSP 管线 |
| P7 | AI 推荐器 | `server/ai_recommender.py` | 508 行 | 3 层降级 (HuggingFace→SnowNLP→关键词) |
| P8 | 预设抓取器 | `server/preset_scraper.py` | 668 行 | 4 级降级、Cloudflare 问题 |
| P9 | VocalSep 整合脚本 | `VocalSep_Consolidated.jsx` | 4543 行 | 16 章节、Poll Loop 模式、去重模式 |
| P10 | MotionStudio 模块系统 | `AE-MotionStudio/` | ~20 文件 | webpack+ES6+Flask、模块化架构 |

### 1.2 设计模式库 (提取自遗产代码)

| # | 模式名称 | 来源 | 可复用性 | 用途 |
|---|---------|------|---------|------|
| M1 | **Poll Manager** | `VocalSep_Consolidated.jsx` + `host/bridge/poll-manager.jsx` | ★★★★★ | `app.scheduleTask()` 非阻塞轮询，任务注册表，生命周期回调 |
| M2 | **Bridge Protocol** | `server/ae_bridge.py` | ★★★★★ | `OK:<JSON>` / `ERROR:<msg>` stdout 协议，ExtendScript↔Python 通信 |
| M3 | **Composite Module Loading** | `host/index.jsx` + `AE-MotionStudio/host/index.jsx` | ★★★★ | `$.evalFile()` + try-catch + 命名空间合并 |
| M4 | **Async Chunked Execution** | `host/utils/async-helper.jsx` | ★★★ | `while` + `$.sleep(10)` 协作式多任务 |
| M5 | **Dual-Engine Fallback** | `F5_vocal_separate.py` | ★★★★ | Demucs AI → FFmpeg 相位抵消 自动检测降级 |
| M6 | **6-Path Audio Detection** | `host/main.jsx:536-560` | ★★★★ | hasAudio → source.hasAudio → conformAudioRate → 嵌套合成扫描 → 属性遍历 → 扩展名匹配 |
| M7 | **Seen-Map Dedup** | `VocalSep_Consolidated.jsx:collectResults` | ★★★ | O(n) 对象映射去重 (替代 O(n²) array.some) |
| M8 | **Singleton Service Registry** | `server/services/vocal_engine.py` | ★★★ | SeparatorFactory + 线程安全缓存 |
| M9 | **Layered NLP Fallback** | `server/ai_recommender.py` | ★★★ | HuggingFace → SnowNLP → 关键词匹配 |
| M10 | **Expression Animation** | `host/text_engine.jsx:_presetFns` | ★★★ | AE 表达式 (弹跳/矩阵雨/彩虹色/打字机) |

### 1.3 反模式清单 (附精确文件:行号)

| # | 反模式 | 位置 | 严重度 | 修复方案 |
|---|--------|------|--------|---------|
| A1 | **STATE.outDir 竞态条件** | `client/app.js:1813-1823` (异步 init) vs `:508-512` (同步使用) | 🔴 CRITICAL | 添加 `STATE.ready` 守卫 |
| A2 | **confirm() 在 CEP 不可用** | `client/app.js:646,697` | 🔴 HIGH | 自定义 HTML 确认对话框 |
| A3 | **Tabs 3/4/5 缺异步轮询** | `client/app.js:534-680` | 🔴 HIGH | PollManager 统一异步模式 |
| A4 | **同步 system.callSystem 阻塞 AE** | `AEStudioKit_Panel.jsx:F5 handler` | 🔴 HIGH | 迁移到 submit→poll→download 模式 |
| A5 | **单体文件** | `VocalSep_Consolidated.jsx` (4543 行), `client/app.js` (2113 行) | 🟡 MEDIUM | 提取模块到独立文件 |
| A6 | **eval() 用于 JSON 回退** | `host/utils/json-polyfill.jsx`, `AEStudioKit_Panel.jsx:F2/F7` | 🟡 MEDIUM | 使用经过验证的 Crockford polyfill |
| A7 | **空 catch 块** | ~20+ 处遍布代码库 | 🟡 MEDIUM | 至少 `$.writeln(e)` |
| A8 | **硬编码路径** | Python 路径、Topaz 路径、用户名 | 🟡 MEDIUM | 多候选项扫描 + 缓存 |
| A9 | **跨标签状态共享** | `importAddCheck.value` 被 Tab 1/3/4 共享 | 🟡 MEDIUM | 标签前缀 ID 命名 (`sep_`, `split_`, `tool_`) |
| A10 | **重复的 Logger 回退** | F1-F8 各自声明相同回退代码 | 🟡 MEDIUM | 提取到 `_shared/` |
| A11 | **双份 Animator API** | F2 + F3 独立声明相同 AE API 函数 | 🟡 MEDIUM | 创建 `host/utils/animator-api.jsx` |
| A12 | **脆弱的字符串替换** | `AEStudioKit_Panel.jsx:F2` 用 regex 替换 animationType | 🟡 MEDIUM | 参数化函数调用 |
| A13 | **无模块注册表** | 硬编码 MODULES 对象，无自动发现 | 🟢 LOW | 实现简单注册表 |
| A14 | **日志分散两处** | Panel log + Logger log 写入不同文件 | 🟢 LOW | 统一日志路径 |

### 1.4 性能热点

| # | 热点 | 位置 | 影响 | 优化方向 |
|---|------|------|------|---------|
| H1 | F5 同步 system.callSystem | `AEStudioKit_Panel.jsx:runF5VocalSep` | AE 冻结数分钟 | 异步 submit→poll→download |
| H2 | F2/F7 eval() 重复执行 | `AEStudioKit_Panel.jsx:runF2WithType/runF7Download` | ~15-20ms/点击 | 参数化调用 |
| H3 | 日志文件 I/O ×3 | `AEStudioKit_Logger.jsx:log` (open→write→close) | 3 次磁盘操作/条 | 写合并缓冲 (10 行) |
| H4 | 500 行日志 split/join | `AEStudioKit_Panel.jsx:PanelLog.write` | 长会话累积 | 环形缓冲区 |
| H5 | Python 检测无缓存 | `host/main.jsx:findPython` | 每次 status 调用扫描 | 会话级缓存 |
| H6 | 递归文件系统扫描 | `VocalSep_Consolidated.jsx:scanDirRecursive` | 深度 3 递归 | 结果缓存 |
| H7 | 轮询循环 150 次×2s | `client/app.js:pollSeparation` | 最长 5 分钟 | 自适应间隔 |

---

## 第二阶段：原子模块性能与功能增强

### 2.1 F9 — 日志系统 (优先：被所有模块依赖)

**当前**: 每次 log 调用 open→write→close (3 次 I/O)，无级别过滤

**优化**:
- **写合并缓冲**: 10 行环形缓冲区，仅 DEBUG 或缓冲区满或 ERROR 时刷盘 → 73% I/O 减少
- **级别门控**: 生产模式下抑制 DEBUG → ~40% 日志量减少
- **统一日志源**: `test-suites/_shared/AEStudioKit_Logger.jsx` 为权威实现，`host/main.jsx:52-110` 替换为 `$.evalFile()` 加载

**预测提升**: I/O 操作减少 73%，代码去重 ~60 行

### 2.2 F2+F3 — 共享 Animator API (去重)

**当前**: F2 和 F3 独立声明相同的 `_getAnimatorsGroup`, `_addAnimator`, `_addSelector`, `_addAnimProp`, `_setKeyframe` 等

**优化**:
- 创建 `host/utils/animator-api.jsx` (~80 行) — 权威 Animator API
- `host/text_engine.jsx` 改为加载共享模块 (减少 670→~600 行)
- `AEStudioKit_Panel.jsx` F2 调用改为参数化 (移除 `eval()` + regex 替换)

**预测提升**: 去重 ~50 行，消除 eval() 调用 (~20ms/点击)，零风险 (相同 AE API)

### 2.3 F1+F4 — 图层分类与音频检测提取

**优化**:
- 创建 `host/utils/layer-classify.jsx` — 分类表替代 if-else 链
- 创建 `host/utils/audio-detect.jsx` — 6 路径音频检测
- 图层类型缓存到 `layer.label` 属性 (O(1) 重分类)
- MIME 类型检测补充 (.m4a, .ogg)

**预测提升**: 缓存命中时 40% 更快的重分类，消除 MIME 假阴性

### 2.4 F5 — 人声分离异步化 (最高优先级)

**当前**: ScriptUI 面板中 `system.callSystem()` 同步阻塞 AE

**优化**:
- 创建 `client/poll-manager.js` — 统一 PollManager 类 (~100 行)
- 替换 `client/app.js` 中 3 个独立 poll 函数为 PollManager
- 修复 STATE.outDir 竞态 (C1 bug)

**预测提升**: 消除 AE 冻结，代码减少 ~70 行，修复 1 个 CRITICAL bug

### 2.5 F6 — AE 导入统一

**优化**: 创建 `host/utils/ae-import.jsx`，3 个导入路径合并为 1 个参数化函数，导入前预验证文件存在

### 2.6 F7 — 下载重试

**优化**: 添加重试逻辑 (最多 3 次，指数退避 1s/2s/4s)，进度回调

### 2.7 F8 — Topaz 检测缓存

**优化**: 缓存检测结果 5 分钟 TTL，避免重复注册表扫描 (~200-500ms/次)

---

## 第三阶段：CEP 12+ 高级面板架构设计

### 3.1 组件树

```
index.html
├── #sidebar (垂直标签栏)
│   ├── .sidebar-header (logo "AE StudioKit")
│   ├── 9× .tab-btn[data-tab="..."]
│   └── .sidebar-footer (状态指示器)
├── .main-content
│   ├── #panel-vocalsep (Tab 1: 音频选择→引擎→模型→模式→分离→进度→结果)
│   ├── #panel-texteffects (Tab 2: 预设浏览器→参数→应用)
│   ├── #panel-multitrack (Tab 3: 音频→分轨选择→引擎→分离→进度→结果)
│   ├── #panel-audiotools (Tab 4: 工具选择→参数表单→执行→进度)
│   ├── #panel-aieffects (Tab 5: 效果分类→参数→执行→进度)
│   ├── #panel-results (Tab 6: 文件网格→导入→打开文件夹→清理)
│   ├── #panel-videoenhance (Tab 7: Topaz状态→文件→模型→缩放→增强→进度)
│   ├── #panel-templates (Tab 8: 模板库→导入FFX)
│   └── #panel-airecommend (Tab 9: 文本输入→推荐→结果列表)
├── #confirmDialog (自定义确认框)
├── #toast (通知提示)
└── #logPanel (可折叠日志)
```

### 3.2 状态管理

```javascript
STATE = {
  // 系统
  ready: Boolean,          // init() 完成标志 (修复 C1)
  outDir: String,          // 异步设置，ready 后才可读
  
  // 连接健康
  pythonOk, bridgeOk, serverRunning,
  
  // 统一轮询
  pollManager: PollManager,  // 替代 pollTimer/mtPollTimer/fxPollTimer
  
  // 标签页状态 (每标签独立)
  vocals:   { jobId, engine, model, mode },
  textFx:   { selectedPresetId, presets, categories },
  multi:    { jobId, stems, engine },
  audio:    { jobId, tool, params },
  effects:  { jobId, category, effect, params },
  video:    { topazDetected, topazPath, jobId },
  
  // 全局缓存
  modelCache, presetCache, audioPathCache
}
```

### 3.3 通信协议

```
UI Event → app.js handler → aeCall(action, params)
  → CSInterface.evalScript("cepDispatch('action', '{json}')")
    → host/main.jsx → cepDispatch switch → 核心函数
      → system.callSystem("python ae_bridge.py subcommand ...")
        → server/ae_bridge.py → HTTP → FastAPI/Flask 服务
          → AI 模型处理
        ← OK:{json} / ERROR:{msg}
      ← system.callSystem 返回
    ← cepDispatch 返回 JSON
  ← CSInterface 回调
← 更新 UI / PollManager 继续轮询
```

### 3.4 安全沙箱设计

- 禁止 `eval()` 用于代码执行 → 仅 Crockford JSON.parse polyfill
- 文件系统访问限制 → 所有路径经 `sanitizePath()` (移除 `|;&$` 等)
- CSInterface 仅调用 `cepDispatch` 单一入口 → 不暴露任意 ExtendScript 执行
- 外部进程调用仅通过预定义 subcommand → `ae_bridge.py` 白名单

---

## 第四阶段：实施与集成

### 4.1 新建文件清单

| 文件 | 行数 | 说明 |
|------|------|------|
| `client/poll-manager.js` | ~100 | PollManager 类 (start/stop/stopAll/_poll) |
| `host/utils/animator-api.jsx` | ~80 | 共享 AE Animator API |
| `host/utils/audio-detect.jsx` | ~60 | 6 路径音频检测 |
| `host/utils/ae-import.jsx` | ~50 | 统一 AE 导入 |
| `host/utils/layer-classify.jsx` | ~40 | 分类表工具 |

### 4.2 修改文件清单

| 文件 | 变更 | 说明 |
|------|------|------|
| `client/app.js` | -150 / +80 | PollManager 集成、STATE 守卫、confirm 替换、Tab 3/4/5 异步 |
| `client/index.html` | +30 | 确认对话框 HTML、标签前缀 ID |
| `client/style.css` | +30 | 确认对话框样式 |
| `host/main.jsx` | -90 / +60 | Logger 替换、模块注册表、异步 action、Python 缓存 |
| `host/text_engine.jsx` | -60 / +20 | 委托到 animator-api.jsx |
| `test-suites/_shared/AEStudioKit_Logger.jsx` | +30 | 写合并 + 级别门控 |
| `server/ae_bridge.py` | +40 | Tab 3 异步 subcommand |
| `AEStudioKit_Panel.jsx` | -50 / +40 | 移除 eval、参数化调用、F5 改为异步 |

### 4.3 任务调度器 — PollManager 设计

```javascript
// client/poll-manager.js
var PollManager = function() {
  this._tasks = {};  // jobId → {attempts, maxAttempts, interval, onProgress, onComplete, onError, timer}
};

PollManager.prototype.start = function(jobId, options) {
  // options: {checkAction, maxAttempts, interval, onProgress, onComplete, onError}
  // 创建任务记录，启动 setTimeout 轮询
};

PollManager.prototype._poll = function(jobId) {
  // aeCall(checkAction, {jobId}, callback)
  // 解析状态 → onProgress / onComplete / onError
  // 仍在处理 → setTimeout(_poll, interval)
};

PollManager.prototype.stop = function(jobId) { /* clearTimeout + delete */ };
PollManager.prototype.stopAll = function() { /* 遍历清除 */ };
```

### 4.4 关键 Bug 修复

| Bug | 修复方案 | 位置 |
|-----|---------|------|
| C1: STATE.outDir 竞态 | `STATE.ready` 守卫 + 空字符串回退 | `client/app.js:508-512` |
| H1-H3: Tabs 3/4/5 缺异步 | PollManager 统一 submit→poll→download | `client/app.js:534-680` |
| H4: confirm() 不可用 | 自定义 HTML 确认对话框 | `client/index.html` + `app.js` |
| A11: 双份 Animator API | 提取到 animator-api.jsx | `host/utils/animator-api.jsx` |

---

## 第五阶段：验证与测试矩阵

### 5.1 测试用例矩阵

| ID | 验证目标 | 运行方式 | 通过标准 | 优先级 |
|----|---------|---------|---------|--------|
| F1-F8 | 原子功能无回归 | AE 中 `$.evalFile()` | 所有已有通过标准 | P1 |
| F9 | Logger 缓冲+门控 | `$.evalFile("F9_logger_test.jsx")` | 20 次 log 调用 ≤5 次 I/O (基线 60) | P1 |
| INT01 | PollManager 并发轮询 | 3 个同时 submit→poll | 全部完成无干扰 | P1 |
| INT02 | Tab 3/4/5 异步 | 多轨分离+音频工具+AI 效果 | UI 保持响应，进度更新 | P1 |
| INT03 | 模块加载 | 通过注册表加载全部模块 | 无错误，无重复声明 | P2 |
| INT04 | 状态隔离 | 切换全部 9 标签 | 标签切换不改变其他标签值 | P2 |
| INT05 | Logger I/O 减少 | 100 次 log，计数磁盘写 | 写入 <30 (基线 300) | P2 |
| REG01 | STATE.outDir 竞态 | 加载后立即点下载 (before init) | 优雅处理，无 undefined/ 路径 | P1 |
| REG02 | confirm 替换 | Tab 4/5 触发 showConfirm | 对话框出现，Yes/No 工作 | P1 |
| REG03 | PollManager 清理 | 轮询中切换标签 | 无孤儿 setTimeout | P2 |
| REG04 | Python 缓存 | 两次 status() 调用 | 第二次 O(1) 文件检查 | P2 |

### 5.2 测试环境

```
CEP Debug: reg add "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_DWORD /d 1 /f
部署路径: %APPDATA%\Adobe\CEP\extensions\AE_StudioKit\
AE 版本: 2023-2025, 合成已打开, 至少一个音频图层
Python: 3.11+ with Demucs/PyTorch, server.py on :8765
```

### 5.3 回滚策略

1. F1-F9 原子测试是基线 — 它们通过则单个功能正确
2. INT01+INT02 是最高风险集成点 — 失败时可隔离 PollManager 而不影响 Tab 1
3. REG01 是最关键回归 — 失败时回退下载路径变更

---

## 实施顺序 (依赖图)

```
Phase 1 (分析) — 纯文档，无代码变更
  ↓
Phase 2 (优化)
  F9 Logger → F2+F3 Animator API → F1+F4 提取 → F5 PollManager → F6/F7/F8
  ↓
Phase 3 (架构) — 设计文档 + HTML ID 重命名
  ↓
Phase 4 (实施)
  PollManager 实现 → confirm 替换 → Tab 3/4/5 异步 → Python 缓存 → 模块加载器
  ↓
Phase 5 (验证) — 创建测试 → 运行矩阵 → 修复回归 → 输出报告
```
