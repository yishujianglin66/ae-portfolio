# 设计模式库 — Design Patterns Library

> **项目**: 第一阶段 — 遗产资产深度剖析
> **日期**: 2026-06-05
> **收录**: 24 个从遗产代码中提炼的优良设计模式

---

## 模式分类

| 类别 | 模式数 | 模式编号 |
|------|--------|----------|
| 异步与调度 | 4 | DP-01 ~ DP-04 |
| 错误处理 | 4 | DP-05 ~ DP-08 |
| 数据与配置 | 4 | DP-09 ~ DP-12 |
| AE API 封装 | 4 | DP-13 ~ DP-16 |
| UI 构建 | 4 | DP-17 ~ DP-20 |
| 性能与资源 | 4 | DP-21 ~ DP-24 |

---

## 异步与调度模式

### DP-01: Submit-Poll-Complete 异步三元组

**来源**: `VocalSep_Consolidated.jsx:1938-2076`
**类型**: 架构模式
**评级**: ⭐⭐⭐⭐⭐ (核心参考模式)

**模式描述**:
将长时间操作拆分为三个异步阶段：
1. **Submit**: 通过 `$.evalFile()` 或 `system.callSystem()` 启动后台任务，立即返回 jobId
2. **Poll**: 使用 `app.scheduleTask('PollLoop', interval, true)` 注册重复任务，检查状态
3. **Complete**: 当 poll 返回 DONE 时，使用 `app.scheduleTask('OnComplete', 100, false)` 执行一次性完成处理

**代码骨架**:
```javascript
// Phase 1: Submit
function submitJob() {
    var jobId = system.callSystem('python server.py --submit "' + input + '"');
    STATE.currentJobId = jobId;
    app.scheduleTask('PollLoop', 2000, true);  // 每 2 秒轮询
}

// Phase 2: Poll (注册为 app.scheduleTask 的任务)
function PollLoop() {
    var status = system.callSystem('python server.py --check ' + STATE.currentJobId);
    if (status === 'DONE') {
        app.cancelTask(taskId);
        app.scheduleTask('OnComplete', 100, false);
        return;
    }
    // 更新进度 UI
    updateProgress(status);
}

// Phase 3: Complete
function OnComplete() {
    downloadResults();
    importToComp();
    app.redraw();
}
```

**为何优良**: 这是 AE ExtendScript 中唯一不阻塞主线程的长时间操作处理方式。Tab 1 的人声分离流程是项目中唯一正确实现了此模式的组件。

**何时使用**: 任何可能超过 50ms 的操作（FFmpeg、Python 推理、文件下载、网络请求）。

---

### DP-02: CEP 轮询管理器 (PollManager)

**来源**: `client/poll-manager.js:1-338`
**类型**: 架构模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
统一的客户端轮询管理器，支持：
- 多任务并行轮询
- 自定义间隔和最大尝试次数
- 超时自动取消
- 进度/状态/消息的三层解包
- 启动前自动停止同名重复任务

**接口**:
```javascript
PollManager.start({
    id: string,           // 唯一任务 ID
    interval: number,     // 轮询间隔 (ms), 默认 2000
    maxAttempts: number,  // 最大尝试次数, 默认 150 (5min)
    checkFn: function,    // 状态检查函数, 返回 {success, data}
    onUpdate: function,   // 每次尝试回调 (progress, status)
    onComplete: function, // 完成回调
    onError: function     // 错误回调
});
```

**为何优良**: 将 CEP 面板侧的异步轮询逻辑集中管理，避免了散布各处的 `setTimeout`，并提供统一的取消、超时和进度机制。

**何时使用**: CEP 面板需要轮询后端任务状态时。

---

### DP-03: 模块守护加载 (Guarded $.evalFile)

**来源**: `host/index.jsx:34-84`
**类型**: 容错模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
每个 `$.evalFile()` 调用包裹在独立的 try/catch 中，按关键性分级处理：
- 核心模块 (bridge, logger): 加载失败抛出/退出
- 功能模块 (text-fx, vocal): 加载失败记录 WARN，继续启动，对应的 UI 按钮保持禁用
- 工具模块 (utils): 加载失败静默降级

**代码骨架**:
```javascript
// Core modules — fail fast
try { $.evalFile(BRIDGE_PATH); } catch (e) {
    alert('Critical: Bridge module failed to load. Panel cannot start.');
    return;
}

// Feature modules — degrade gracefully
try {
    $.evalFile(TEXT_FX_PATH);
    STATE.modules.textFx = true;
} catch (e) {
    _logWarn('Text FX module unavailable — text animation features disabled.');
    STATE.modules.textFx = false;
}
```

**为何优良**: 防止单个模块加载失败导致整个扩展崩溃，同时保持用户对可用功能的知情权。

**何时使用**: 任何需要加载多个独立模块的 ExtendScript 入口点。

---

### DP-04: 写缓冲日志 (Write-Buffered Logger)

**来源**: `test-suites/_shared/AEStudioKit_Logger.jsx:60-73`、`AEStudioKit_Panel.jsx:66-92`
**类型**: 性能模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
日志写入不直接操作文件，而是先入缓冲区，仅在以下条件下刷盘：
1. 缓冲区满 (10 行)
2. 日志级别为 ERROR (确保关键信息在崩溃前持久化)
3. 模块卸载时手动调用 `flush()`

**性能数据**: 减少文件 I/O 约 73%（根据代码注释）。

**代码骨架**:
```javascript
var _buffer = [];
var BUFFER_SIZE = 10;

function log(msg, level) {
    var line = _timestamp() + ' [' + level + '] ' + msg;
    _buffer.push(line);
    if (_buffer.length >= BUFFER_SIZE || level === 'ERROR') {
        _flushBuffer();
    }
    $.writeln(line); // 控制台始终即时输出
}

function _flushBuffer() {
    if (!_logFile || _buffer.length === 0) return;
    _logFile.open('a');
    for (var i = 0; i < _buffer.length; i++) {
        _logFile.write(_buffer[i] + '\n');
    }
    _logFile.close();
    _buffer = [];
}
```

**为何优良**: 在 ExtendScript 中每次 `File.open/write/close` 都是同步系统调用，缓冲显著减少了 I/O 开销。

**何时使用**: 任何需要文件日志的 ExtendScript 模块。

---

## 错误处理模式

### DP-05: 防御性返回 + 结构化错误

**来源**: `host/main.jsx:1361-1772`、`F1_layer_type.jsx:393-417`
**类型**: 容错模式
**评级**: ⭐⭐⭐⭐⭐

**模式描述**:
每个公共函数返回统一结构 `{success: boolean, data?: any, error?: string}`，而非抛出异常或返回 null。调用方通过检查 `success` 字段决定后续流程。

**代码骨架**:
```javascript
function cepDispatch(action, paramsJson) {
    try {
        var params = JSON.parse(paramsJson || '{}');
        var result;
        switch (action) {
            case 'getAudioInfo': result = getSelectedAudioInfo(); break;
            // ... 30 cases
            default: return JSON.stringify({success: false, error: 'Unknown action: ' + action});
        }
        return JSON.stringify({success: true, data: result});
    } catch (e) {
        return JSON.stringify({success: false, error: e.toString(), code: 'E999'});
    }
}
```

**为何优良**: 
- CEP 面板始终得到可解析的 JSON 响应
- 错误不会导致面板崩溃
- 统一的错误码 (`E999`) 便于日志检索

**何时使用**: CEP evalScript 桥接的所有入口函数。

---

### DP-06: 图层级错误隔离 (Per-Layer Error Isolation)

**来源**: `F2_text_anim.jsx:518-530`、`text_engine.jsx:614-624`
**类型**: 容错模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
批量处理选中图层时，每个图层的操作包裹在独立的 try/catch 中。单个图层处理失败不会中断整个批次，结果汇总包含成功/失败/跳过的完整计数。

**代码骨架**:
```javascript
var okCount = 0, failCount = 0, skippedCount = 0;
for (var i = 0; i < layers.length; i++) {
    try {
        if (!_isTextLayer(layers[i])) { skippedCount++; continue; }
        applyPreset(layers[i], preset);
        okCount++;
    } catch (e) {
        LOG.log('Layer "' + layers[i].name + '" failed: ' + e.toString(), 'ERROR');
        failCount++;
    }
}
LOG.alert('Done: ' + okCount + ' OK, ' + failCount + ' failed, ' + skippedCount + ' skipped.');
```

**为何优良**: 
- 用户不会因为一个图层的问题而丢失所有工作
- 明确的成功/失败计数帮助用户诊断问题

**何时使用**: 任何批量处理多个图层的操作。

---

### DP-07: 日志降级链 (Logger Degradation Chain)

**来源**: `AEStudioKit_Logger.jsx:81-118`、`VocalSep_Consolidated.jsx:98-118`
**类型**: 容错模式
**评级**: ⭐⭐⭐

**模式描述**:
日志初始化按优先级尝试多种存储位置：
1. `Folder.desktop` → 桌面日志文件
2. `Folder.temp` → 系统临时目录
3. 纯内存/控制台 → 降级为 `$.writeln()` 输出
每级降级记录原因，确保日志功能在任何环境下至少保留控制台输出。

**代码骨架**:
```javascript
function init(customPath, debug) {
    try {
        _logPath = customPath || Folder.desktop.fsName + '/AEStudioKit.log';
        _logFile = new File(_logPath);
        _logFile.open('a');
        _logFile.close();
    } catch (e1) {
        try {
            _logPath = Folder.temp.fsName + '/AEStudioKit.log';
            _logFile = new File(_logPath);
        } catch (e2) {
            _logPath = '';
            _logFile = null; // 仅控制台输出
        }
    }
}
```

**为何优良**: 确保日志功能在任何环境下至少保留部分输出，避免因日志初始化失败导致整个扩展无法启动。

**何时使用**: 任何 ExtendScript 项目的日志初始化。

---

### DP-08: 预条件门控 (Precondition Gating)

**来源**: `F1_layer_type.jsx:393-417`、`F4_extract_audio.jsx:140-190`
**类型**: 防御性模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
函数入口处按顺序检查所有前置条件，每个条件失败时立即返回明确的 null 或错误信息。这种"早期返回"模式避免了深层嵌套的 if-else。

**代码骨架**:
```javascript
function runF1() {
    if (typeof app === 'undefined') { alert('请在 AE 中运行'); return null; }
    if (!app.project) { alert('请打开一个项目'); return null; }
    var comp = app.project.activeItem;
    if (!comp || !(comp instanceof CompItem)) { alert('请选中一个合成'); return null; }
    var sel = comp.selectedLayers;
    if (!sel || sel.length === 0) { alert('请至少选中一个图层'); return null; }
    // ... 所有前置条件满足，开始处理
}
```

**为何优良**: 
- 错误消息精确告知用户缺少什么
- 避免了深层嵌套的 `if (ok) { if (ok2) { ... } }`结构
- 每个条件独立可测试

**何时使用**: 任何依赖 AE 状态的入口函数。

---

## 数据与配置模式

### DP-09: 数据驱动的预设系统

**来源**: `text_engine.jsx:30-74 (元数据) + 252-545 (30 个预设函数)`
**类型**: 架构模式
**评级**: ⭐⭐⭐⭐⭐

**模式描述**:
预设定义为数据（元数据对象）+ 纯函数，而非硬编码在 UI 或 switch-case 中：
- 元数据: `{id, name, category, description, icon, duration}`
- 应用函数: `function preset_name(layer, duration, intensity)`
- 注册表: 元数据数组 + 名称到函数的映射表

**代码骨架**:
```javascript
var PRESETS = [
    { id: 'fade_in', name: '淡入', category: '基础', duration: 1.0, fn: _presetFadeIn },
    { id: 'scale_pop', name: '缩放弹出', category: '动态', duration: 1.5, fn: _presetScalePop },
    // ... 30 预设
];

var PRESET_MAP = {};
for (var i = 0; i < PRESETS.length; i++) {
    PRESET_MAP[PRESETS[i].id] = PRESETS[i];
}

function applyPreset(layer, presetId, duration) {
    var preset = PRESET_MAP[presetId];
    if (!preset) return {success: false, error: 'Unknown preset: ' + presetId};
    preset.fn(layer, duration || preset.duration, 1.0);
    return {success: true};
}
```

**为何优良**: 
- 新增预设只需添加元数据 + 函数，不影响现有代码
- 预设可通过 JSON 文件导入/导出 (F3)
- 分类、搜索、预览等 UI 功能基于元数据自动生成

**何时使用**: 任何需要可扩展功能集的系统。

---

### DP-10: JSON Polyfill 自包含模式

**来源**: `F3_apply_preset.jsx:60-155`、`VocalSep_Consolidated.jsx:120-214`
**类型**: 兼容性模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
ExtendScript ES3 缺少 `JSON.parse/stringify`。项目中实现了基于 Douglas Crockford json2.js 的递归下降解析器，作为自包含的代码块嵌入需要 JSON 支持的每个脚本中。

**设计要点**:
- 纯函数，不依赖任何外部对象
- 完整实现 (支持 `\uXXXX` Unicode 转义、嵌套对象/数组、数字/字符串/布尔/null)
- 错误消息包含解析位置和失败上下文

**为何优良**: 自包含、零依赖，可嵌入任何 ExtendScript 文件。比 `eval()` 回退安全。

**何时使用**: 任何需要在 ExtendScript 中解析 JSON 的场景。

---

### DP-11: 可移植外部依赖发现

**来源**: `F5_vocal_separate.py:67-86 (find_ffmpeg)`、`F8_topaz_detect.jsx:66-89`
**类型**: 可移植性模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
对外部可执行文件的定位采用"优先级回退"策略：
1. 项目捆绑版本 (最可预测)
2. 已知安装目录 (按版本号尝试)
3. 系统 PATH 环境变量
4. 返回 null，让调用方决定降级策略

**代码骨架** (Python):
```python
def find_ffmpeg():
    candidates = [
        PROJECT_ROOT / "ffmpeg-8.1.1-essentials_build/bin/ffmpeg.exe",  # 捆绑
        "C:/Program Files/ffmpeg/bin/ffmpeg.exe",                        # 系统安装
        "ffmpeg",                                                         # PATH
    ]
    for c in candidates:
        try:
            result = subprocess.run([str(c), "-version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return str(c)
        except Exception:
            continue
    return None
```

**为何优良**: 在不同部署环境 (开发机、用户机、打包发布) 中自动适配，无需用户手动配置路径。

**何时使用**: 任何依赖外部可执行文件 (FFmpeg, Python, Topaz) 的场景。

---

### DP-12: 全局配置参数钳制 (Config Value Clamping)

**来源**: `F2_text_anim.jsx:436-455`
**类型**: 防御性模式
**评级**: ⭐⭐⭐

**模式描述**:
在 CONFIG 对象使用前，对所有数值参数执行范围钳制并记录 WARN 日志。防止用户误配置导致的异常行为（如负数持续时间、超出范围的强度值）。

**代码骨架**:
```javascript
var CONFIG = { animationType: 'fadeIn', duration: 1.0, intensity: 1.0, charMode: 1, smoothness: 40 };

// 参数钳制
if (CONFIG.duration < 0.1) { CONFIG.duration = 0.1; LOG.log('duration 钳制为 0.1', 'WARN'); }
if (CONFIG.duration > 30)  { CONFIG.duration = 30;  LOG.log('duration 钳制为 30', 'WARN'); }
if (CONFIG.intensity < 0)  { CONFIG.intensity = 0;  LOG.log('intensity 钳制为 0', 'WARN'); }
if (CONFIG.intensity > 3)  { CONFIG.intensity = 3;  LOG.log('intensity 钳制为 3', 'WARN'); }
```

**为何优良**: 将配置错误的影响限制在合理范围内，同时通过日志提醒用户配置被修改。

**何时使用**: 任何使用用户可编辑配置对象的脚本。

---

## AE API 封装模式

### DP-13: 安全属性访问器 (_safeGet)

**来源**: `F1_layer_type.jsx:297-310`
**类型**: 工具模式
**评级**: ⭐⭐⭐⭐⭐

**模式描述**:
通过点分隔路径字符串安全访问 AE 对象属性，每层都有 null 检查和 try/catch。

**代码骨架**:
```javascript
function _safeGet(obj, path, defaultValue) {
    if (obj == null) return defaultValue;
    var parts = path.split('.');
    var current = obj;
    for (var i = 0; i < parts.length; i++) {
        if (current == null) return defaultValue;
        try { current = current[parts[i]]; }
        catch (e) { return defaultValue; }
    }
    return (current != null) ? current : defaultValue;
}
```

**为何优良**: AE DOM 的深层属性访问经常因中间对象为 null 而抛出。此函数消除了一连串的 `if (a && a.b && a.b.c)` 检查。

**何时使用**: 任何需要访问 3 层以上嵌套 AE 属性的场景。示例: `_safeGet(layer, 'source.mainSource.file.fsName', '未知')`

---

### DP-14: 多策略属性检测 (Multi-Strategy Detection)

**来源**: `F1_layer_type.jsx:140-195 (classifyLayer)`、`F2_text_anim.jsx:379-398 (_isTextLayer)`
**类型**: 鲁棒性模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
对关键属性使用多条检测路径，按可靠性降序排列：
1. `instanceof` 类型检查 (最可靠)
2. matchName 属性探测
3. 名称/路径启发式回退

**代码骨架**:
```javascript
function _isTextLayer(layer) {
    // Path 1: instanceof (最可靠)
    if (layer instanceof TextLayer) return true;
    
    // Path 2: 特定属性探测
    try {
        var tp = layer.property("ADBE Text Properties");
        if (tp) return true;
    } catch (e) {}
    
    // Path 3: Source Text 属性 (回退)
    try {
        var st = layer.property("Source Text");
        if (st) return true;
    } catch (e) {}
    
    return false;
}
```

**为何优良**: AE 版本演进中某些 API 可能变化，多路径检测确保跨版本兼容性。

**何时使用**: 依赖 AE 特定属性或类型判断的关键逻辑。

---

### DP-15: 撤销组事务包装 (Undo Group Transaction)

**来源**: `F2_text_anim.jsx:519-530`、`text_engine.jsx:227-237`
**类型**: 数据完整性模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
所有修改合成的操作包裹在 `app.beginUndoGroup()` / `app.endUndoGroup()` 中。try/catch 确保即使操作失败，undo group 也被正确关闭。

**代码骨架**:
```javascript
app.beginUndoGroup('Apply Text Animation');
try {
    animFn(layer, duration, intensity, charMode, smoothness);
} catch (e) {
    LOG.log('Layer "' + layer.name + '" failed: ' + e.toString(), 'ERROR');
    app.endUndoGroup(); // 确保关闭
    throw e;
}
app.endUndoGroup();
```

**为何优良**: 
- 用户按一次 Ctrl+Z 即可撤销整个动画操作
- 即使中间出错也不会产生未闭合的 undo group

**何时使用**: 任何修改合成内容的操作。

---

### DP-16: 关键帧缓动安全设置 (Safe Keyframe Ease)

**来源**: `F2_text_anim.jsx:203-230`
**类型**: 鲁棒性模式
**评级**: ⭐⭐⭐

**模式描述**:
设置关键帧时，先获取最新关键帧，再设置缓动。缓动设置包裹在独立的 try/catch 中，确保缓动失败不影响关键帧值。

**代码骨架**:
```javascript
function _setKeyframe(prop, time, value, easeIn, easeOut) {
    try {
        prop.setValueAtTime(time, value);
        if (prop.numKeys > 0) {
            var kf = prop.keyframe(prop.numKeys);
            if (easeIn) {
                try { kf.easeIn = new KeyframeEase(easeIn[0], easeIn[1]); } catch (e) {}
            }
            if (easeOut) {
                try { kf.easeOut = new KeyframeEase(easeOut[0], easeOut[1]); } catch (e) {}
            }
        }
        return true;
    } catch (e) {
        return false;
    }
}
```

**为何优良**: `KeyframeEase` 在某些 AE 版本/上下文中可能不可用，将其与关键帧值设置分离避免了整个操作失败。

**何时使用**: 程序化设置关键帧时。

---

## UI 构建模式

### DP-17: 基于可见性切换的 Tab 面板

**来源**: `VocalSep_Consolidated.jsx:3025-3040`
**类型**: UI 模式
**评级**: ⭐⭐⭐

**模式描述**:
ScriptUI 不支持真正的 Tab 控件，通过将所有面板叠加并切换 `visible` 属性来模拟 Tab：
- 所有面板在初始化时创建并隐藏 (`visible = false`)
- Tab 按钮的 `onClick` 设置对应面板 `visible = true`，其余 `false`
- 避免了动态创建/销毁 DOM 的开销

**为何优良**: ScriptUI 中没有原生 TabPanel 控件，这是最有效的替代方案。

**何时使用**: ScriptUI 多面板切换。

---

### DP-18: CSS 变量暗色/亮色主题切换

**来源**: `client/style.css:1-50`
**类型**: UI 模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
使用 CSS 自定义属性 (`:root` / `[data-theme="light"]`) 实现主题切换：
- 暗色主题: 默认值在 `:root` 中
- 亮色主题: 覆盖值在 `[data-theme="light"]` 选择器中
- JS 通过 `document.documentElement.setAttribute('data-theme', 'light')` 切换
- 无需重新加载页面

**为何优良**: CEP Chromium 74 支持 CSS 变量，这是在不引入预处理器的情况下最干净的主题方案。

**何时使用**: CEP 面板的主题支持。

---

### DP-19: 自定义确认对话框替代 confirm()

**来源**: `client/app.js:1695-1713`
**类型**: 兼容性模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
CEP Chromium 74 中 `confirm()` 不可用。使用 CSS 模态层 + JS 回调实现自定义确认对话框：
- HTML 中始终存在 `modal-overlay` 和 `modal-dialog` 元素
- `showConfirm(message, onOk, onCancel)` 切换可见性并绑定回调
- 遮罩层点击、取消按钮、ESC 键均可取消

**代码骨架**:
```javascript
function showConfirm(message, onOk, onCancel) {
    var overlay = document.getElementById('modal-overlay');
    var msgEl = document.getElementById('modal-message');
    var okBtn = document.getElementById('modal-ok');
    var cancelBtn = document.getElementById('modal-cancel');
    
    msgEl.textContent = message;
    overlay.style.display = 'flex';
    
    okBtn.onclick = function() {
        overlay.style.display = 'none';
        if (onOk) onOk();
    };
    cancelBtn.onclick = function() {
        overlay.style.display = 'none';
        if (onCancel) onCancel();
    };
}
```

**为何优良**: 完全替代不可用的 `confirm()`，且可自定义样式和按钮文字。

**何时使用**: CEP 面板中任何需要用户确认的操作。

---

### DP-20: Toast 通知自动消失

**来源**: `client/app.js:83-91`
**类型**: UI 模式
**评级**: ⭐⭐⭐

**模式描述**:
非阻塞的临时通知，自动在 3.5 秒后消失。支持 info/error/warning 类型。重复调用时清除前一个定时器。

**代码骨架**:
```javascript
function toast(msg, type) {
    var el = document.getElementById('toast');
    el.textContent = msg;
    el.className = 'toast toast--' + (type || 'info');
    el.style.display = 'block';
    clearTimeout(el._timer);
    el._timer = setTimeout(function() { el.style.display = 'none'; }, 3500);
}
```

**为何优良**: 不打断用户操作的反馈方式，比 `alert()` 好得多。

**何时使用**: CEP 面板的非关键反馈消息。

---

## 性能与资源模式

### DP-21: ONNX 会话按需创建 (Lazy ONNX Session)

**来源**: `server/server.py:225-275` (推断)
**类型**: 性能模式
**评级**: ⭐⭐⭐⭐

**模式描述**:
AI 模型推理会话不在服务启动时预加载，而是在首次请求时懒加载。使用全局字典缓存会话实例：
- Key: 模型名称
- Value: `onnxruntime.InferenceSession` 实例
- 会话创建后保持打开，避免重复加载模型文件 (~1.24GB)

**为何优良**: 减少服务启动时间和内存占用，模型仅在需要时加载。

**何时使用**: Python 服务端管理大型 ML 模型。

---

### DP-22: 文件系统扫描带深度限制

**来源**: `VocalSep_Consolidated.jsx:1709-1738`
**类型**: 安全模式
**评级**: ⭐⭐⭐

**模式描述**:
递归目录扫描时有最大深度限制 (depth=3)，防止符号链接循环或深层嵌套导致的无限递归。

**代码骨架**:
```javascript
function scanDirRecursive(dirPath, maxDepth, currentDepth) {
    if (currentDepth > maxDepth) return [];
    var results = [];
    var dir = new Folder(dirPath);
    var files = dir.getFiles('*');
    for (var i = 0; i < files.length; i++) {
        if (files[i] instanceof Folder) {
            results = results.concat(scanDirRecursive(files[i].fsName, maxDepth, currentDepth + 1));
        } else {
            results.push(files[i]);
        }
    }
    return results;
}
```

**为何优良**: 防止无限递归和文件系统遍历攻击。

**何时使用**: 任何递归目录遍历。

---

### DP-23: 进程池复用 (Subprocess Output Caching)

**来源**: `VocalSep_Consolidated.jsx:496-557`、`host/main.jsx:300-349`
**类型**: 性能模式
**评级**: ⭐⭐⭐

**模式描述**:
`findPython()` 的结果缓存在全局变量中，避免每次操作都重新扫描文件系统。

**代码骨架**:
```javascript
var PYTHON_EXE = null; // 模块级缓存

function findPython() {
    if (PYTHON_EXE) return PYTHON_EXE;            // 缓存命中
    var candidates = [/* ... */];
    for (var i = 0; i < candidates.length; i++) {
        try {
            var r = system.callSystem('"' + candidates[i] + '" --version 2>&1');
            if (r.indexOf('Python') >= 0) {
                PYTHON_EXE = candidates[i];       // 缓存
                return PYTHON_EXE;
            }
        } catch (e) {}
    }
    return null;
}
```

**为何优良**: `system.callSystem()` 每次调用约 50-200ms 开销，缓存避免重复执行。

**何时使用**: 定位外部可执行文件的发现函数。

---

### DP-24: SPI (Single Point of Integration) 入口模式

**来源**: `host/main.jsx:1357-1772 (cepDispatch)`、`client/api.js:25-340 (AEStudioKitAPI)`
**类型**: 架构模式
**评级**: ⭐⭐⭐⭐⭐

**模式描述**:
所有外部通信收束到单一入口点：
- ExtendScript 侧: `cepDispatch(action, paramsJson)` — 一个 switch 处理 30+ 操作
- JS 客户端侧: `AEStudioKitAPI.xxx(params)` — 所有方法委托给统一的 `xhr()` 函数
- Python 侧: `ae_bridge.py` — 26 个命令通过单一 CLI 入口解析

**为何优良**: 
- 添加新功能只需在 switch/mapping 中新增 case
- 统一的错误处理、日志、超时策略
- CEP 面板通过 `aeCall()` 单一路径与 ExtendScript 通信

**何时使用**: 设计扩展的通信层时。

---

## 模式使用建议矩阵

| 场景 | 推荐模式 |
|------|----------|
| 长时间操作 | DP-01 (Submit-Poll-Complete) + DP-02 (PollManager) |
| 模块加载 | DP-03 (守护加载) |
| 错误处理 | DP-05 (结构化错误) + DP-06 (图层级隔离) |
| 日志 | DP-04 (写缓冲) + DP-07 (降级链) |
| AE 属性访问 | DP-13 (safeGet) + DP-14 (多策略检测) |
| 配置管理 | DP-09 (数据驱动) + DP-12 (参数钳制) |
| UI 构建 | DP-17 (Tab 切换) + DP-18 (CSS 主题) + DP-19 (自定义确认) |
| 外部依赖 | DP-11 (可移植发现) + DP-23 (缓存) |
| 通信架构 | DP-24 (SPI 入口) |
