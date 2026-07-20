# 反模式登记册 — ae-vocal-remover

> 生成日期: 2026-06-05
> 基于: v4.0 主项目审计 + 多版本交叉分析
> 登记数量: 14 项反模式

---

## 目录

1. [A1: STATE.outDir 竞态条件](#a1-stateoutdir-竞态条件) 🔴 CRITICAL
2. [A2: confirm() 在 CEP 中不可用](#a2-confirm-在-cep-中不可用) 🔴 HIGH
3. [A3: 标签 3/4/5 缺失异步轮询](#a3-标签-345-缺失异步轮询) 🔴 HIGH
4. [A4: 同步 system.callSystem 阻塞 AE](#a4-同步-systemcallsystem-阻塞-ae) 🔴 HIGH
5. [A5: 单体巨石文件](#a5-单体巨石文件) 🟡 MEDIUM
6. [A6: eval() 用于 JSON 回退](#a6-eval-用于-json-回退) 🟡 MEDIUM
7. [A7: 空 catch 块](#a7-空-catch-块) 🟡 MEDIUM
8. [A8: 硬编码路径](#a8-硬编码路径) 🟡 MEDIUM
9. [A9: 跨标签状态共享](#a9-跨标签状态共享) 🟡 MEDIUM
10. [A10: 重复的 Logger 回退声明](#a10-重复的-logger-回退声明) 🟡 MEDIUM
11. [A11: 双重 Animator API](#a11-双重-animator-api) 🟡 MEDIUM
12. [A12: 脆弱的字符串替换](#a12-脆弱的字符串替换) 🟡 MEDIUM
13. [A13: 无模块自动发现](#a13-无模块自动发现) 🟢 LOW
14. [A14: 分裂的日志系统](#a14-分裂的日志系统) 🟢 LOW

---

## A1: STATE.outDir 竞态条件

| 属性 | 值 |
|------|-----|
| **严重性** | 🔴 CRITICAL |
| **文件** | `client/app.js` |
| **行号** | ~1813-1823 (异步初始化) vs ~508-512 (同步读取) |
| **影响** | 输出路径变为 `undefined/xxx.wav`，文件写入失败 |

### 为何有害

`STATE.outDir` 通过异步函数 `initState()` 从 CEP 偏好中读取并赋值。然而，标签渲染函数（`renderTab1()` 等）在 DOM 加载后立即同步执行，此时 `initState()` 的 Promise 尚未 resolve。结果：`STATE.outDir` 为 `undefined`，拼接路径得到 `"undefined/output.wav"`，后端写文件失败，用户看不到任何错误提示。

### 修复方案

**修复前:**
```javascript
// client/app.js ~1813 — 异步初始化
async function initState() {
    var prefs = await loadPreferences();  // 异步
    STATE.outDir = prefs.outDir || getDefaultOutDir();
}
// client/app.js ~508 — 同步使用（先于 initState resolve）
function renderTab1() {
    var outPath = STATE.outDir + "/" + fileName;  // undefined/xxx.wav
}
```

**修复后:**
```javascript
// 方案 A: 使用 sync getter，确保同步可读
function getOutDir() {
    if (STATE.outDir) return STATE.outDir;
    // 同步回退：从 localStorage/偏好缓存读取
    var cached = window.__cepGetPreference("outDir");
    STATE.outDir = cached || getDefaultOutDir();
    return STATE.outDir;
}

function renderTab1() {
    var outPath = getOutDir() + "/" + fileName;
}

// 方案 B: 延迟渲染，等待 STATE 就绪
async function bootstrap() {
    await initState();
    renderAllTabs();  // 所有渲染在 initState 之后
}
```

### 预防规则

> **任何异步初始化的全局状态，必须在所有同步消费代码执行前完成 resolve。** 使用启动栅栏（bootstrap gate）或将延迟初始化封装为 sync-with-cache getter。

---

## A2: confirm() 在 CEP 中不可用

| 属性 | 值 |
|------|-----|
| **严重性** | 🔴 HIGH |
| **文件** | `client/app.js` |
| **行号** | ~646, ~697 |
| **影响** | 用户点击无响应，无确认对话框弹出 |

### 为何有害

CEP 面板运行在 Chromium Embedded Framework 74 中，该环境不提供 `window.confirm()` API。代码中直接调用 `confirm("确定要删除吗?")` 会在静默中返回 `undefined`（而非 boolean），导致条件判断恒为 false 或抛出异常。

### 修复方案

**修复前:**
```javascript
// client/app.js ~646
function deleteItem(index) {
    if (!confirm("确定要删除此项吗？")) return;
    items.splice(index, 1);
}
```

**修复后:**
```javascript
// 使用 CEP 原生对话框或自定义模态框
function deleteItem(index) {
    showModal({
        title: "确认删除",
        message: "确定要删除此项吗？",
        buttons: ["取消", "确定"],
        onConfirm: function() {
            items.splice(index, 1);
            refreshList();
        }
    });
}

// showModal 基于 CEP CSInterface 或自绘 DOM 弹窗实现
function showModal(opts) {
    // 创建 DOM 遮罩层 + 按钮，避免依赖 confirm()
    var overlay = document.createElement("div");
    overlay.className = "modal-overlay";
    // ... 渲染按钮，绑定 opts.onConfirm
}
```

### 预防规则

> **在 CEP 环境中，永远不要使用 `alert()`、`confirm()`、`prompt()`。** 使用自绘 DOM 模态框或 `CSInterface.dispatchEvent()` 与宿主通信后调用原生对话框。

---

## A3: 标签 3/4/5 缺失异步轮询

| 属性 | 值 |
|------|-----|
| **严重性** | 🔴 HIGH |
| **文件** | `client/app.js` |
| **行号** | ~534-680 (标签 3/4/5 处理逻辑) |
| **影响** | AE 界面冻结 10-60 秒，用户无法操作 |

### 为何有害

标签 3（多轨分离）、4（音频工具）、5（AI 音效）提交任务后，通过 `system.callSystem()` 同步等待后端响应。后端处理大型音频文件可能需要数十秒，期间 AE 主线程完全阻塞——界面冻结、进度条不更新、无法取消操作。

### 修复方案

**修复前:**
```javascript
// 同步等待 — AE UI 冻结
function processMultiTrack(files) {
    for (var i = 0; i < files.length; i++) {
        var result = system.callSystem(
            'python backend.py --task separate --input "' + files[i] + '"'
        );
        // 处理期间 UI 完全无响应
    }
}
```

**修复后:**
```javascript
// 异步轮询 — 每 2 秒检查一次任务状态
function processMultiTrack(files) {
    var taskId = submitTaskAsync(files);  // POST /api/task → 返回 taskId
    var pollTimer = setInterval(function() {
        var status = fetchTaskStatus(taskId);  // GET /api/task/{taskId}
        updateProgressBar(status.progress);
        if (status.state === "done") {
            clearInterval(pollTimer);
            onTaskComplete(status.result);
        }
    }, 2000);
}
```

### 预防规则

> **任何耗时超过 500ms 的操作必须使用异步模式。** CEP 端使用 `setInterval` 轮询或 `XMLHttpRequest` 长轮询，后端返回任务 ID 后立即释放请求。

---

## A4: 同步 system.callSystem 阻塞 AE

| 属性 | 值 |
|------|-----|
| **严重性** | 🔴 HIGH |
| **文件** | `AEStudioKit_Panel.jsx` |
| **行号** | F5 处理器 (ExtendScript 端) |
| **影响** | 所有面板操作冻结，After Effects 无响应 |

### 为何有害

ExtendScript 中 `system.callSystem()` 同步执行外部进程。当 F5 功能触发 Python 处理时（如人声分离/音频增强），AE 的 ExtendScript 引擎完全阻塞。用户不仅无法操作当前面板，整个 AE 应用程序都会卡死，直到子进程退出。

### 修复方案

**修复前:**
```javascript
// AEStudioKit_Panel.jsx — F5 处理器
function onF5Pressed() {
    var cmd = 'python ' + SCRIPT_DIR + '/vocal_sep.py --input "' + inputFile + '"';
    var result = system.callSystem(cmd);  // 阻塞整个 AE
    parseResult(result);
}
```

**修复后:**
```javascript
// 调度任务并立即返回，通过 CEP 回调获取结果
function onF5Pressed() {
    var taskPayload = JSON.stringify({ input: inputFile, mode: "vocal_sep" });
    // 发送到 CEP 面板，由面板通过 fetch/XMLHttpRequest 调用后端
    csInterface.evalScript('startAsyncTask(' + taskPayload + ')');
    // ExtendScript 立即返回，保持 AE 响应
}

// client/app.js
function startAsyncTask(payload) {
    fetch("http://localhost:8765/api/task", {
        method: "POST",
        body: JSON.stringify(payload)
    }).then(function(r) { return r.json(); })
      .then(function(data) { pollUntilDone(data.taskId); });
}
```

### 预防规则

> **ExtendScript 中 `system.callSystem()` 只能用于瞬时命令（<100ms）。** 任何涉及磁盘 I/O、网络请求、模型推理的操作必须委托给 CEP 面板的异步 HTTP 客户端。

---

## A5: 单体巨石文件

| 属性 | 值 |
|------|-----|
| **严重性** | 🟡 MEDIUM |
| **文件** | `VocalSep_Consolidated.jsx` (4543 行)，`client/app.js` (2113 行) |
| **影响** | 维护困难、合并冲突频繁、新成员上手成本高 |

### 为何有害

`VocalSep_Consolidated.jsx` 将 UI 渲染、业务逻辑、网络请求、文件操作、偏好管理全部塞进一个 4500+ 行的文件中。任何修改都需要理解全局上下文，代码审查困难，两个开发者几乎不可能并行修改不同功能。

### 修复方案

**修复前 (单体结构):**
```
VocalSep_Consolidated.jsx  (4543 行)
  ├── UI rendering
  ├── Business logic
  ├── HTTP client
  ├── File system
  └── Preferences
```

**修复后 (模块化结构):**
```
src/
├── ui/
│   ├── panels.jsx        (~400 行) — UI 渲染
│   └── dialogs.jsx       (~200 行) — 对话框
├── core/
│   ├── engine.jsx        (~500 行) — 业务逻辑
│   └── state.jsx         (~150 行) — 状态管理
├── io/
│   ├── http.jsx          (~200 行) — HTTP 客户端
│   └── files.jsx         (~250 行) — 文件操作
└── main.jsx              (~100 行) — 入口 + 模块组装
```

### 预防规则

> **单文件不超过 500 行。** 按职责拆分：UI、业务逻辑、I/O 各占独立模块。ExtendScript 使用 `$.evalFile()` 加载依赖，确保加载顺序和 BOM 标记。

---

## A6: eval() 用于 JSON 回退

| 属性 | 值 |
|------|-----|
| **严重性** | 🟡 MEDIUM |
| **文件** | `host/utils/json-polyfill.jsx`，`AEStudioKit_Panel.jsx` F2/F7 |
| **行号** | json-polyfill.jsx ~12, AEStudioKit_Panel.jsx F2 ~89, F7 ~45 |
| **影响** | 代码注入风险，恶意 JSON 可执行任意 ExtendScript |

### 为何有害

ExtendScript (ES3) 没有原生 `JSON.parse()`。代码使用 `eval("(" + jsonString + ")")` 作为回退。如果 JSON 来源不可信（如用户输入、网络响应），攻击者可在 JSON 中嵌入 ExtendScript 代码实现任意文件读写。

### 修复方案

**修复前:**
```javascript
// json-polyfill.jsx ~12
function parseJSON(str) {
    if (typeof JSON !== "undefined") return JSON.parse(str);
    return eval("(" + str + ")");  // 不安全
}
```

**修复后:**
```javascript
// 使用成熟的纯 ES3 JSON 解析器（如 Douglas Crockford 的 json2.js）
// 或捆绑一个安全解析器
#include "vendor/json2.js"  // 提供安全的 JSON.parse polyfill

function parseJSON(str) {
    // json2.js 已提供安全的 JSON.parse
    return JSON.parse(str);  // 不依赖 eval()
}

// 如果必须自己实现，使用严格的白名单验证：
function safeParseJSON(str) {
    // 移除所有可能包含代码的 key
    var sanitized = str.replace(/[^\[\]{}\",:.\-\d\w\s]/g, "");
    // 但仍不推荐 — 应使用成熟库
}
```

### 预防规则

> **禁止使用 `eval()` 解析 JSON。** ExtendScript 中引入 Douglas Crockford 的 `json2.js` 或等效安全 polyfill。在任何环境中，`eval()` 必须仅作为最后手段且输入完全受控时使用。

---

## A7: 空 catch 块

| 属性 | 值 |
|------|-----|
| **严重性** | 🟡 MEDIUM |
| **文件** | 分散在 ~20+ 个位置 |
| **影响** | 错误静默丢弃，问题难以诊断，生产环境幽灵 bug |

### 为何有害

代码中大量 `try { ... } catch(e) {}` 模式静默丢弃所有异常。当功能神秘失败时，日志中没有任何线索，开发者只能逐行加断点排查。

### 修复方案

**修复前:**
```javascript
// 多处出现此模式
try {
    var result = riskyOperation();
    processResult(result);
} catch (e) {}  // 错误静默消失
```

**修复后:**
```javascript
try {
    var result = riskyOperation();
    processResult(result);
} catch (e) {
    Logger.error("riskyOperation 失败: " + e.message, {
        stack: e.stack,
        context: "processResult"
    });
    // 必要时降级处理
    showUserFriendlyError("操作失败，请重试");
}
```

### 预防规则

> **每个 catch 块至少记录错误日志。** 如果错误可恢复，执行降级逻辑；如果不可恢复，通知用户。lint 工具应标记空 catch 块为 warning。

---

## A8: 硬编码路径

| 属性 | 值 |
|------|-----|
| **严重性** | 🟡 MEDIUM |
| **文件** | 分散在多个文件中 |
| **影响** | 程序仅在某台特定机器上运行，无法分发 |

### 为何有害

代码中直接写死了 `C:/Users/Administrator/...`、`C:/Program Files/Topaz Labs/...` 等绝对路径。换一台机器或另一个用户账户，所有路径失效。

### 修复方案

**修复前:**
```javascript
// 多处出现
var PYTHON = "C:/Users/Administrator/AppData/Local/Programs/Python/Python39/python.exe";
var TOPAZ = "C:/Program Files/Topaz Labs/Topaz Video AI/topaz.exe";
var DATA_DIR = "C:/Users/Administrator/Desktop/ae-vocal-remover/server/data/";
```

**修复后:**
```javascript
// 方案 A: 基于安装目录推导
var BASE_DIR = Folder.current.fullName;  // 或 $.fileName 所在目录
var PYTHON = detectPython();  // 运行时探测
var DATA_DIR = BASE_DIR + "/server/data/";

// 方案 B: 从配置文件读取
var config = loadConfig(BASE_DIR + "/config.json");
var TOPAZ = config.tools.topaz || detectTopaz();

function detectPython() {
    var candidates = [
        system.callSystem("where python 2>nul").trim(),
        "C:/Python39/python.exe",
        // ... 探测常见路径
    ];
    for (var i = 0; i < candidates.length; i++) {
        var f = new File(candidates[i]);
        if (f.exists) return candidates[i];
    }
    throw new Error("未找到 Python 安装");
}
```

### 预防规则

> **禁止提交包含绝对路径（含用户名）的代码。** 所有路径必须基于安装目录推导或从配置文件读取。使用 `Folder.current`、`$.fileName`、环境变量作为基准。

---

## A9: 跨标签状态共享

| 属性 | 值 |
|------|-----|
| **严重性** | 🟡 MEDIUM |
| **文件** | `client/app.js` |
| **行号** | `importAddCheck` 引用位置: ~534 (Tab 1), ~620 (Tab 3), ~680 (Tab 4) |
| **影响** | 用户在标签 3 的操作意外影响标签 1 的结果 |

### 为何有害

多个标签共享同一个 DOM 元素引用 `importAddCheck`（复选框"添加到项目面板"）。当用户在标签 3 切换此复选框后切换到标签 1，标签 1 的行为已被意外改变。这种隐式耦合导致 bug 难以复现和定位。

### 修复方案

**修复前:**
```javascript
// 所有标签共享同一个变量和 DOM 元素
var importAddCheck = document.getElementById("importAddCheck");

// Tab 1
function processTab1() { if (importAddCheck.checked) { /* ... */ } }
// Tab 3
function processTab3() { if (importAddCheck.checked) { /* ... */ } }
```

**修复后:**
```javascript
// 每个标签独立管理自己的状态
var tabState = {
    tab1: { importToProject: false },
    tab3: { importToProject: true },   // 不同标签可以有不同默认值
    tab4: { importToProject: false }
};

// 或者每个标签拥有独立的复选框 DOM 元素
// <input id="tab1-importAdd" type="checkbox">
// <input id="tab3-importAdd" type="checkbox">

function getImportPreference(tabId) {
    return tabState[tabId].importToProject;
}
```

### 预防规则

> **不同标签/视图的状态必须隔离。** 每个功能模块维护自己的 state 对象，禁止通过全局 DOM 元素引用跨模块通信。

---

## A10: 重复的 Logger 回退声明

| 属性 | 值 |
|------|-----|
| **严重性** | 🟡 MEDIUM |
| **文件** | `AEStudioKit_Panel.jsx` F1-F8 函数 |
| **影响** | 代码冗余 ~70 行，修改 Logger 需要改 8 处 |

### 为何有害

F1 到 F8 共 8 个函数在每个函数开头声明了完全相同的 Logger 回退代码（约 9 行），总计 ~70 行重复代码。如果 Logger 路径需要修改，必须同时修改 8 处，遗漏任何一处都会导致该函数日志静默丢失。

### 修复方案

**修复前 (F1-F8 各自重复):**
```javascript
// F1 ~L5
var Logger = (typeof Logger !== "undefined") ? Logger : {
    log: function(m) { $.writeln("[LOG] " + m); },
    error: function(m) { $.writeln("[ERROR] " + m); },
    warn: function(m) { $.writeln("[WARN] " + m); }
};
// F2 ~L5 — 完全相同
// F3 ~L5 — 完全相同
// ... 重复 8 次
```

**修复后:**
```javascript
// logger-polyfill.jsx — 单一定义，所有模块引用
#ifndef LOGGER_LOADED
var Logger = (typeof Logger !== "undefined") ? Logger : (function() {
    var prefix = "[VocalSep]";
    return {
        log:   function(m) { $.writeln(prefix + " [LOG] " + m); },
        error: function(m) { $.writeln(prefix + " [ERROR] " + m); },
        warn:  function(m) { $.writeln(prefix + " [WARN] " + m); },
        debug: function(m) { $.writeln(prefix + " [DEBUG] " + m); }
    };
})();
#endif

// main.jsx — 入口文件加载一次
$.evalFile(SCRIPTS_DIR + "/logger-polyfill.jsx");
$.evalFile(SCRIPTS_DIR + "/modules/F1.jsx");  // 直接使用全局 Logger
$.evalFile(SCRIPTS_DIR + "/modules/F2.jsx");
```

### 预防规则

> **DRY 原则：公共工具代码只定义一次。** 使用 `$.evalFile()` 加载共享模块到全局作用域，或使用 `#include` 指令（ExtendScript 预处理器支持）。

---

## A11: 双重 Animator API

| 属性 | 值 |
|------|-----|
| **严重性** | 🟡 MEDIUM |
| **文件** | `AEStudioKit_Panel.jsx` F2 (~L30-80), F3 (~L25-75) |
| **影响** | 修改动画 API 需要改 2 处，两处可能行为不一致 |

### 为何有害

F2（文字特效）和 F3（多轨分离）分别声明了相同的 AE Animator API 辅助函数（`addTextAnimator`、`setKeyframe`、`applyEasing` 等），总计约 50 行重复代码。如果修复一个 bug 或增加新缓动类型，必须同步两处，极易遗忘。

### 修复方案

**修复前:**
```javascript
// F2 ~L30 — 声明 addTextAnimator、setKeyframe、applyEasing
// F3 ~L25 — 声明完全相同的 3 个函数
```

**修复后:**
```javascript
// ae-animator-api.jsx — 单一来源
function addTextAnimator(layer, property, value, time) { /* ... */ }
function setKeyframe(property, value, time, easing) { /* ... */ }
function applyEasing(keyframe, type) { /* ... */ }

// F2.jsx
$.evalFile(SCRIPTS_DIR + "/ae-animator-api.jsx");
// 直接使用 addTextAnimator、setKeyframe 等

// F3.jsx
$.evalFile(SCRIPTS_DIR + "/ae-animator-api.jsx");
// 使用相同的函数，行为一致
```

### 预防规则

> **共享的 AE API 封装必须抽取到独立模块。** 使用 `$.evalFile()` 在需要处加载。定期检查各 Fn 文件是否有重复函数定义。

---

## A12: 脆弱的字符串替换

| 属性 | 值 |
|------|-----|
| **严重性** | 🟡 MEDIUM |
| **文件** | `AEStudioKit_Panel.jsx` |
| **行号** | F2 处理器 (~L120) |
| **影响** | 修改源代码结构可能导致功能静默失效 |

### 为何有害

F2 文字特效通过正则表达式替换"源代码"中的 `animationType` 字段来切换动画类型。这是一种极其脆弱的方案——如果变量名被重命名、代码格式改变、或同一字符串出现在注释中，功能就会静默失效或产生错误行为。

### 修复方案

**修复前:**
```javascript
// F2 ~L120 — 字符串替换源码
function setAnimationType(srcCode, newType) {
    return srcCode.replace(
        /var animationType = "[^"]*"/,
        'var animationType = "' + newType + '"'
    );
}
```

**修复后:**
```javascript
// 使用配置对象，不操作源码字符串
var animConfig = {
    animationType: "fadeIn",
    duration: 1.0,
    easing: "easeOut"
};

function setAnimationType(newType) {
    animConfig.animationType = newType;
    // 动画引擎读取 animConfig.animationType，无需修改源码
}

function applyEffect(layer) {
    var anim = createAnimation(layer, animConfig);
    anim.render();
}
```

### 预防规则

> **禁止通过字符串/正则替换修改源代码。** 使用配置对象、策略模式或参数化函数来控制行为变化。源码是静态的，行为是动态的——不要在运行时改写源码。

---

## A13: 无模块自动发现

| 属性 | 值 |
|------|-----|
| **严重性** | 🟢 LOW |
| **文件** | `VocalSep_Consolidated.jsx`，`AEStudioKit_Panel.jsx` |
| **行号** | MODULES 对象定义处 |
| **影响** | 添加新功能需要修改硬编码的模块注册表 |

### 为何有害

模块列表通过硬编码的 `MODULES` 对象注册（如 `{F1: "F1.jsx", F2: "F2.jsx", ...}`）。每次添加新模块（F9、F10...）都需要手动更新此对象，容易遗漏且纯属机械劳动。

### 修复方案

**修复前:**
```javascript
var MODULES = {
    F1: "modules/F1_VocalSep.jsx",
    F2: "modules/F2_TextFX.jsx",
    F3: "modules/F3_MultiTrack.jsx",
    F4: "modules/F4_AudioTools.jsx",
    // 添加 F5 必须手动更新此处
};
```

**修复后:**
```javascript
// 运行时扫描 modules/ 目录自动发现
function discoverModules(dir) {
    var modules = {};
    var folder = new Folder(dir);
    var files = folder.getFiles(/^F\d+_.*\.jsx$/i);
    for (var i = 0; i < files.length; i++) {
        var match = files[i].name.match(/^(F\d+)_/);
        if (match) {
            modules[match[1]] = files[i].fullName;
        }
    }
    return modules;
}

var MODULES = discoverModules(SCRIPTS_DIR + "/modules/");
// 新模块只需放入目录即自动注册
```

### 预防规则

> **模块注册应基于约定优于配置。** 使用文件名约定（如 `F\d+_` 前缀）实现自动发现。硬编码列表仅用于无法遵守约定时的显式排除。

---

## A14: 分裂的日志系统

| 属性 | 值 |
|------|-----|
| **严重性** | 🟢 LOW |
| **文件** | `client/app.js` (Panel 日志)，`host/` (Logger 日志) |
| **影响** | 排查问题需要对照两个日志文件，时间线难以对齐 |

### 为何有害

CEP 面板端使用 `console.log()` 写入 Chromium DevTools 控制台（或通过 CSInterface 写入单独的文件），而 ExtendScript 端通过 `Logger.log()` 写入 `.txt` 文件。两端日志时间戳格式不同、位置不同，当问题跨越面板/宿主角本边界时，需要手动对照两个日志源，效率极低。

### 修复方案

**修复前 (两个独立日志系统):**
```javascript
// CEP 面板 — client/app.js
console.log("[Panel] 用户点击分离按钮");  // → DevTools 控制台

// ExtendScript — host/logger.jsx
Logger.log("收到分离请求: " + inputFile);  // → VocalSep.log
```

**修复后 (统一日志通道):**
```javascript
// 统一日志格式 + 合并输出
function UnifiedLogger(channel) {
    this.channel = channel;  // "panel" | "host"
    this.log = function(level, msg) {
        var entry = "[" + new Date().toISOString() + "][" + level + "][" + this.channel + "] " + msg;
        // 面板端：通过 CSInterface 转发到 ExtendScript 端统一写入
        if (this.channel === "panel") {
            csInterface.evalScript('UnifiedLogger.write("' + escapeStr(entry) + '")');
        } else {
            // 宿主端：直接追加到统一日志文件
            logFile.writeln(entry);
        }
    };
}

// 只需查看一个文件即可获得完整的时间线
// [2026-06-05T10:30:01][INFO][panel] 用户点击分离按钮
// [2026-06-05T10:30:01][INFO][host] 收到分离请求: C:/audio/input.wav
```

### 预防规则

> **所有日志输出到同一个文件/流，使用统一的格式。** 包含时间戳、级别、来源标识（panel/host）。CEP 面板通过 CSInterface 将日志转发到宿主端统一写入。

---

## 反模式分布总结

| 严重性 | 数量 | 项目 |
|-------|------|------|
| 🔴 CRITICAL | 1 | A1: STATE.outDir 竞态条件 |
| 🔴 HIGH | 3 | A2: confirm(), A3: 缺失轮询, A4: 同步阻塞 |
| 🟡 MEDIUM | 8 | A5-A12 |
| 🟢 LOW | 2 | A13: 无自动发现, A14: 分裂日志 |

### 修复优先级建议

1. **立即** (阻塞发布): A1, A2 — 导致功能完全不可用
2. **本周** (严重影响体验): A3, A4 — 导致 UI 冻结
3. **本迭代**: A5, A7, A8, A9 — 可维护性和可移植性
4. **下迭代**: A6, A10, A11, A12 — 代码质量和安全性
5. **后续优化**: A13, A14 — 开发体验改进

---

> 本文档由项目审计自动生成，应与 `AUDIT_REPORT.md` 和 `.claude/CLAUDE.md` 配合使用。
> 每次修复反模式后，请更新对应条目的状态并注明修复 commit。
