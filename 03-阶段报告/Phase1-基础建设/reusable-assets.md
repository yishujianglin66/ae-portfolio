# 可复用资产库 — Reusable Assets Library

> **项目**: 第一阶段 — 遗产资产深度剖析
> **日期**: 2026-06-05
> **收录**: 28 个经评估可直接复用的代码片段/模块

---

## 资产分类

| 类别 | 数量 | 资产编号 |
|------|------|----------|
| ExtendScript 工具函数 | 8 | RA-01 ~ RA-08 |
| AE API 封装层 | 6 | RA-09 ~ RA-14 |
| Python 服务端组件 | 5 | RA-15 ~ RA-19 |
| CEP 客户端组件 | 5 | RA-20 ~ RA-24 |
| 完整可复用模块 | 4 | RA-25 ~ RA-28 |

---

## 一、ExtendScript 工具函数

### RA-01: `_safeGet()` — 安全属性访问器

**来源**: `test-suites/F1-layer-type/F1_layer_type.jsx:297-310`
**复用评级**: ⭐⭐⭐⭐⭐ (核心工具)
**预估节省**: 每次调用节省 4-8 行防御性检查代码

```javascript
/**
 * 安全深度属性访问
 * @param {Object} obj - 起始对象
 * @param {string} path - 点分隔路径，如 "source.mainSource.file.fsName"
 * @param {*} defaultValue - 任何层级为 null/undefined 时返回的默认值
 * @returns {*} 属性值或默认值
 */
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

// 使用示例:
// _safeGet(layer, 'source.mainSource.file.fsName', '未知文件')
// _safeGet(app, 'project.activeItem.name', '无合成')
```

---

### RA-02: `_safeSetKeyframe()` — 安全关键帧设置

**来源**: `test-suites/F2-text-anim/F2_text_anim.jsx:203-230`
**复用评级**: ⭐⭐⭐⭐⭐ (核心工具)
**预估节省**: 每次调用节省 10-15 行的 try/catch + ease 处理

```javascript
/**
 * 安全设置关键帧值 (缓动失败不影响值设置)
 * @param {Property} prop - AE 属性对象
 * @param {number} time - 关键帧时间 (秒)
 * @param {*} value - 关键帧值
 * @param {Array} [easeIn] - [speed, influence] 或 undefined
 * @param {Array} [easeOut] - [speed, influence] 或 undefined
 * @returns {boolean} 成功/失败
 */
function _safeSetKeyframe(prop, time, value, easeIn, easeOut) {
    if (!prop) return false;
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

---

### RA-03: `_clampNumber()` — 数值范围钳制

**来源**: `VocalSep_Consolidated.jsx:346-352`
**复用评级**: ⭐⭐⭐⭐

```javascript
/**
 * 数值钳制到 [min, max] 范围
 * @param {number} value - 输入值
 * @param {number} min - 下限
 * @param {number} max - 上限
 * @returns {number} 钳制后的值
 */
function _clampNumber(value, min, max) {
    if (value < min) return min;
    if (value > max) return max;
    return value;
}
```

---

### RA-04: `_sanitizeFilename()` — 文件名安全处理

**来源**: `test-suites/F4-audio-extract/F4_extract_audio.jsx:120-132`
**复用评级**: ⭐⭐⭐⭐

```javascript
/**
 * 移除文件名中的非法字符
 * @param {string} name - 原始文件名
 * @returns {string} 安全文件名
 */
function _sanitizeFilename(name) {
    if (!name || typeof name !== 'string') return 'untitled';
    var badChars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*'];
    var result = '';
    for (var i = 0; i < name.length; i++) {
        var ch = name.charAt(i);
        var isBad = false;
        for (var j = 0; j < badChars.length; j++) {
            if (ch === badChars[j]) { isBad = true; break; }
        }
        result += isBad ? '_' : ch;
    }
    return result.replace(/\s+/g, '_').substring(0, 200);
}
```

---

### RA-05: `_timestamp()` — 毫秒精度时间戳

**来源**: `test-suites/_shared/AEStudioKit_Logger.jsx:39-55`
**复用评级**: ⭐⭐⭐⭐

```javascript
/**
 * 生成毫秒精度时间戳 (ExtendScript ES3 兼容)
 * @returns {string} 格式: "2026-06-05 14:30:00.123"
 */
function _timestamp() {
    var d = new Date();
    function _pad(n) { return n < 10 ? '0' + n : '' + n; }
    return d.getFullYear() + '-' +
        _pad(d.getMonth() + 1) + '-' +
        _pad(d.getDate()) + ' ' +
        _pad(d.getHours()) + ':' +
        _pad(d.getMinutes()) + ':' +
        _pad(d.getSeconds()) + '.' +
        (d.getMilliseconds() < 100 ? (d.getMilliseconds() < 10 ? '00' : '0') : '') + d.getMilliseconds();
}
```

---

### RA-06: `_isValidFile()` / `_isValidDir()` — 路径验证

**来源**: `VocalSep_Consolidated.jsx:283-306`
**复用评级**: ⭐⭐⭐⭐

```javascript
/**
 * 验证文件路径是否有效且存在
 * @param {string} path - 文件路径
 * @returns {boolean}
 */
function _isValidFile(path) {
    if (!path || typeof path !== 'string') return false;
    try { var f = new File(path); return f.exists; }
    catch (e) { return false; }
}

/**
 * 验证目录路径是否有效且存在
 * @param {string} path - 目录路径
 * @returns {boolean}
 */
function _isValidDir(path) {
    if (!path || typeof path !== 'string') return false;
    try { var d = new Folder(path); return d.exists; }
    catch (e) { return false; }
}
```

---

### RA-07: `_sanitizeErrorMessage()` — 错误消息安全处理

**来源**: `VocalSep_Consolidated.jsx:741-747`
**复用评级**: ⭐⭐⭐

```javascript
/**
 * 从错误消息中移除潜在敏感信息 (文件路径等)
 * @param {string} msg - 原始错误消息
 * @returns {string} 安全消息
 */
function _sanitizeErrorMessage(msg) {
    if (!msg || typeof msg !== 'string') return 'Unknown error';
    return msg.replace(/[A-Z]:\\[^\s]*/g, '[path]')
              .replace(/\/Users\/[^/\s]*/g, '/Users/[user]');
}
```

---

### RA-08: `_ensureDir()` — 确保目录存在

**来源**: 跨文件通用模式

```javascript
/**
 * 确保目录存在，不存在则创建
 * @param {string} dirPath - 目录路径
 * @returns {boolean} 成功/失败
 */
function _ensureDir(dirPath) {
    try {
        var dir = new Folder(dirPath);
        if (!dir.exists) {
            return dir.create();
        }
        return true;
    } catch (e) {
        return false;
    }
}
```

---

## 二、AE API 封装层

### RA-09: `_classifyLayer()` — 图层类型识别

**来源**: `test-suites/F1-layer-type/F1_layer_type.jsx:140-270`
**复用评级**: ⭐⭐⭐⭐⭐ (用作文本/图层类型检测的基础)
**行数**: ~130 行

**导出接口**:
```javascript
/**
 * 识别 AE 图层类型
 * @param {Layer} layer - AE Layer 对象
 * @returns {{type: string, category: string, details: object}}
 *    categories: 'TEXT', 'SHAPE', 'SOLID', 'AUDIO', 'VIDEO', 'IMAGE',
 *               'NULL', 'CAMERA', 'LIGHT', 'ADJUSTMENT', 'COMP', 'UNKNOWN'
 */
function _classifyLayer(layer) { /* ... */ }
```

---

### RA-10: `_getAnimatorsGroup()` / `_addAnimator()` / `_addSelector()` / `_addAnimProp()`

**来源**: `test-suites/F2-text-anim/F2_text_anim.jsx:107-170` (或 `text_engine.jsx:78-156`)
**复用评级**: ⭐⭐⭐⭐⭐ (所有文字动画的基础)
**行数**: ~70 行 (4 个函数)

**导出接口**:
```javascript
function _getAnimatorsGroup(layer)  // → PropertyGroup | null
function _addAnimator(layer)        // → Animator PropertyGroup | null
function _addSelector(animator)     // → Selector PropertyGroup | null
function _addAnimProp(animator, matchName)  // → Property | null
```

---

### RA-11: `_detectAudio()` — 音频检测

**来源**: `test-suites/F1-layer-type/F1_layer_type.jsx:315-360`
**复用评级**: ⭐⭐⭐⭐
**行数**: ~45 行，4 条检测路径

```javascript
/**
 * 多策略音频检测 (hasAudio → footage.hasAudio → file 扩展名 → mainSource)
 */
function _detectAudio(footage, layer) { /* ... */ }
```

---

### RA-12: `_detectVideo()` — 视频检测

**来源**: `test-suites/F1-layer-type/F1_layer_type.jsx:365-375`
**复用评级**: ⭐⭐⭐
**行数**: ~10 行

---

### RA-13: `_applyPresetToLayer()` — 数据驱动预设应用

**来源**: `test-suites/F3-preset-file/F3_apply_preset.jsx:222-322`
**复用评级**: ⭐⭐⭐⭐⭐ (JSON 预设文件 → AE Text Animator)
**行数**: ~100 行

**预设 JSON 格式**:
```json
{
  "name": "淡入",
  "duration": 1.0,
  "animators": [{
    "selector": {
      "mode": 1,
      "start": 0, "end": 100, "offset": 0,
      "smoothness": 40,
      "keyframes": {
        "start": [{"time": 0, "value": 0}, {"time": 1, "value": 100}]
      }
    },
    "properties": [
      {"matchName": "ADBE Text Opacity", "value": 0}
    ]
  }]
}
```

**导出接口**:
```javascript
function applyPresetToLayer(layer, preset, durOverride)  // void (throws on error)
```

---

### RA-14: `_isTextLayer()` — 文字图层判断

**来源**: `test-suites/F2-text-anim/F2_text_anim.jsx:379-398`
**复用评级**: ⭐⭐⭐⭐
**行数**: ~20 行，3 条检测路径

```javascript
/**
 * 3 路径文字图层检测: instanceof → ADBE Text Properties → Source Text
 */
function _isTextLayer(layer) { /* ... */ }
```

---

## 三、Python 服务端组件

### RA-15: `find_ffmpeg()` — FFmpeg 路径发现

**来源**: `test-suites/F5-vocal-sep/F5_vocal_separate.py:67-86`
**复用评级**: ⭐⭐⭐⭐⭐
**行数**: ~20 行

```python
def find_ffmpeg(project_root: Optional[Path] = None) -> Optional[str]:
    """
    多策略 FFmpeg 定位: 捆绑版本 → 已知安装目录 → 系统 PATH
    """
    candidates = []
    if project_root:
        candidates.append(str(project_root / "ffmpeg-8.1.1-essentials_build/bin/ffmpeg.exe"))
        candidates.append(str(project_root / "ffmpeg-8.1.1-essentials_build/bin/ffmpeg"))
    candidates.extend(["ffmpeg", "ffmpeg.exe"])
    
    for c in candidates:
        try:
            result = subprocess.run([c, "-version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                return c
        except Exception:
            continue
    return None
```

---

### RA-16: `Logger` 类 — 文件日志器

**来源**: `test-suites/F5-vocal-sep/F5_vocal_separate.py:43-57`
**复用评级**: ⭐⭐⭐
**行数**: ~15 行

```python
class Logger:
    """最小文件日志器"""
    def __init__(self, log_path: Path):
        self.log_path = log_path
    
    def log(self, msg: str, level: str = "INFO"):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{timestamp} [{level}] {msg}"
        print(line)
        try:
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(line + '\n')
        except Exception:
            pass
```

---

### RA-17: `validate_audio_file()` — 音频文件验证

**来源**: `test-suites/F5-vocal-sep/F5_vocal_separate.py:106-137`
**复用评级**: ⭐⭐⭐⭐
**行数**: ~30 行

```python
def validate_audio_file(filepath: Path, ffprobe_path: Optional[str] = None) -> Optional[float]:
    """
    使用 ffprobe 验证音频文件并返回时长
    Returns: float (duration in seconds) or None if invalid
    """
    # 文件存在性 → ffprobe 探测 → 时长解析
```

---

### RA-18: `check_disk_space()` — 磁盘空间检查

**来源**: `test-suites/F5-vocal-sep/F5_vocal_separate.py:158-169`
**复用评级**: ⭐⭐⭐
**行数**: ~12 行

```python
def check_disk_space(output_dir: Path, required_mb: int = 500) -> bool:
    """检查输出目录是否有足够的磁盘空间"""
    try:
        usage = shutil.disk_usage(output_dir)
        free_mb = usage.free / (1024 * 1024)
        return free_mb >= required_mb
    except OSError:
        return True  # 无法检查时不阻止操作
```

---

### RA-19: FastAPI 后台任务 + SSE 进度模式

**来源**: `server/server.py:850-1100` (推断)
**复用评级**: ⭐⭐⭐⭐⭐ (核心参考模式)
**行数**: ~250 行

```python
# 模式骨架:
active_jobs: Dict[str, dict] = {}

@app.post("/separate")
async def separate(file: UploadFile, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    active_jobs[job_id] = {"status": "processing", "progress": 0}
    background_tasks.add_task(run_separation, job_id, file)
    return {"job_id": job_id}

@app.get("/progress/{job_id}")
async def progress(job_id: str):
    async def event_stream():
        while True:
            job = active_jobs.get(job_id)
            if not job: break
            yield f"data: {json.dumps(job)}\n\n"
            if job["status"] in ("done", "failed"): break
            await asyncio.sleep(1)
    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

---

## 四、CEP 客户端组件

### RA-20: `aeCall()` — CEP ExtendScript 通信原语

**来源**: `client/app.js:134-175`
**复用评级**: ⭐⭐⭐⭐⭐ (所有 CEP 通信的基础)
**行数**: ~40 行

```javascript
/**
 * 统一的 CEP → ExtendScript 通信封装
 * @param {string} action - 操作名称
 * @param {object} params - 参数对象
 * @param {function} callback - function({success, data, error})
 */
function aeCall(action, params, callback) {
    var jsonParams = JSON.stringify(params || {});
    cs.evalScript("cepDispatch('" + action + "', '" + jsonParams + "')", function(result) {
        if (!result) { callback({success: false, error: 'No response'}); return; }
        var cleaned = result.replace(/\r\n/g, '\n').trim();
        if (cleaned.indexOf('OK:') === 0) {
            try { callback({success: true, data: JSON.parse(cleaned.substring(3))}); }
            catch (e) { callback({success: true, data: cleaned.substring(3)}); }
        } else if (cleaned.indexOf('ERROR:') === 0) {
            callback({success: false, error: cleaned.substring(6)});
        } else {
            try { callback({success: true, data: JSON.parse(cleaned)}); }
            catch (e) { callback({success: false, error: cleaned}); }
        }
    });
}
```

---

### RA-21: `PollManager` — 统一轮询管理器

**来源**: `client/poll-manager.js:1-338`
**复用评级**: ⭐⭐⭐⭐⭐ (完整模块)
**行数**: 338 行 (完整模块)

**接口**:
```javascript
var PollManager = {
    start: function(config) { /* ... */ },   // config: {id, interval, maxAttempts, checkFn, onUpdate, onComplete, onError}
    stop: function(id) { /* ... */ },
    stopAll: function() { /* ... */ },
    activeCount: function() { /* ... */ }
};
```

---

### RA-22: `showConfirm()` — 自定义确认对话框

**来源**: `client/app.js:1695-1713`
**复用评级**: ⭐⭐⭐⭐ (CEP 中 confirm() 不可用时的替代方案)
**行数**: ~20 行

```javascript
/**
 * CEP 兼容的自定义确认对话框
 * @param {string} message - 提示消息
 * @param {function} onOk - 确认回调
 * @param {function} [onCancel] - 取消回调
 */
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

---

### RA-23: `toast()` — Toast 通知

**来源**: `client/app.js:83-91`
**复用评级**: ⭐⭐⭐⭐
**行数**: ~10 行

```javascript
/**
 * 显示自动消失的 Toast 通知
 * @param {string} msg - 消息
 * @param {string} [type] - 'info'|'error'|'warning'
 * @param {number} [duration] - 显示时长 ms，默认 3500
 */
function toast(msg, type, duration) {
    var el = document.getElementById('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'toast toast--' + (type || 'info');
    el.style.display = 'block';
    clearTimeout(el._timer);
    el._timer = setTimeout(function() { el.style.display = 'none'; }, duration || 3500);
}
```

---

### RA-24: 暗色/亮色主题切换 CSS 系统

**来源**: `client/style.css:1-50`
**复用评级**: ⭐⭐⭐⭐
**行数**: ~50 行 CSS

```css
:root {
    --bg-primary: #1a1a2e;
    --bg-secondary: #16213e;
    --bg-card: #0f3460;
    --text-primary: #e0e0e0;
    --text-secondary: #a0a0b0;
    --accent: #e94560;
    --accent-hover: #ff6b81;
    --success: #388e3c;
    --error: #d32f2f;
    --warning: #f57c00;
    --border: #2a2a4a;
    --shadow: rgba(0,0,0,0.3);
}

[data-theme="light"] {
    --bg-primary: #f5f5f5;
    --bg-secondary: #ffffff;
    --bg-card: #e8e8e8;
    --text-primary: #212121;
    --text-secondary: #757575;
    --border: #e0e0e0;
    --shadow: rgba(0,0,0,0.1);
}

/* 使用示例: */
/* .panel { background: var(--bg-primary); color: var(--text-primary); } */
```

---

## 五、完整可复用模块

### RA-25: AEStudioKit_Logger.jsx — 写缓冲日志系统

**来源**: `test-suites/_shared/AEStudioKit_Logger.jsx` (224 行)
**复用评级**: ⭐⭐⭐⭐⭐ (所有 JSX 模块的基础设施)
**评估**: 可直接作为独立的 `$.evalFile()` 加载模块使用

**公共 API**:
```javascript
AEStudioKit.Logger.init(customPath, debugMode)  // → string (log path)
AEStudioKit.Logger.log(msg, level)              // → void
AEStudioKit.Logger.alert(msg, level)            // → void (alert dialog)
AEStudioKit.Logger.getLogPath()                 // → string
AEStudioKit.Logger.flush()                      // → void (force write)
AEStudioKit.Logger.setDebug(enabled)            // → void
```

**特点**: 写缓冲、ERROR 即时刷盘、桌面/temp 降级、控制台同步输出

---

### RA-26: text_engine.jsx — 文字动画引擎

**来源**: `host/text_engine.jsx` (670 行)
**复用评级**: ⭐⭐⭐⭐⭐ (30 个预设的文字动画核心)
**评估**: 可作为独立的 `$.evalFile()` 加载模块。包含 30 个动画预设、API 封装层、批量操作支持。

**公共 API**:
```javascript
// 核心操作
TEXT_ENGINE.applyTextPreset(layer, presetId, duration)  // → {success, message}
TEXT_ENGINE.applyPresetToSelected(presetId, duration)   // → {success, okCount, failCount, skippedCount}
TEXT_ENGINE.clearAllAnimators(layer)                    // → void

// 查询
TEXT_ENGINE.listAllPresets()                            // → [{id, name, category, ...}]
TEXT_ENGINE.getPresetsByCategory(category)              // → [{id, name, ...}]
TEXT_ENGINE.getPresetMeta(presetId)                     // → {id, name, ...} | null
```

---

### RA-27: `resolvePython()` — Python 解释器发现

**来源**: `VocalSep_Consolidated.jsx:386-493` + `host/main.jsx:300-349`
**复用评级**: ⭐⭐⭐⭐
**行数**: ~100 行 (含缓存)

```javascript
var PYTHON_EXE = null;

function resolvePython() {
    if (PYTHON_EXE) return PYTHON_EXE; // 缓存命中
    
    var candidates = [
        // 项目捆绑
        resolvePath(SCRIPT_DIR, '../../python/python.exe'),
        // Windows Store Python
        Folder.userData.fsName + '/../Local/Microsoft/WindowsApps/python3.exe',
        // 系统 Python
        'python', 'python3', 'py',
    ];
    
    for (var i = 0; i < candidates.length; i++) {
        try {
            var r = system.callSystem('"' + candidates[i] + '" --version 2>&1');
            if (r.indexOf('Python') >= 0) {
                PYTHON_EXE = candidates[i];
                return PYTHON_EXE;
            }
        } catch (e) {}
    }
    return null;
}
```

---

### RA-28: JSON Polyfill — 自包含解析器

**来源**: `test-suites/F3-preset-file/F3_apply_preset.jsx:60-155`
**复用评级**: ⭐⭐⭐⭐⭐ (ExtendScript ES3 必需)
**行数**: 95 行

**公共 API**:
```javascript
// 自包含 — 不依赖任何外部模块
var data = JSON.parse('{"name": "test", "values": [1, 2, 3]}');
var text = JSON.stringify({name: "test", values: [1, 2, 3]});
```

**特点**: 
- 基于 Douglas Crockford json2.js
- 完整支持 `\uXXXX` Unicode 转义
- 错误消息包含解析位置

---

## 资产集成建议

### 第二阶段 (F# 模块优化) 需集成的资产

| 模块 | 需集成资产 |
|------|-----------|
| F1 图层识别 | RA-01, RA-09, RA-11, RA-12, RA-25 |
| F2 文字动画 | RA-02, RA-03, RA-10, RA-14, RA-25, RA-26 |
| F3 预设应用 | RA-02, RA-10, RA-13, RA-14, RA-25, RA-28 |
| F4 音频提取 | RA-04, RA-06, RA-08, RA-25, RA-27 |
| F5 人声分离 | RA-15, RA-16, RA-17, RA-18 |
| F6 音频导入 | RA-04, RA-06, RA-25 |
| F7 文件下载 | RA-06, RA-08, RA-25 |
| F8 Topaz 检测 | RA-06, RA-25, RA-27 |

### 第三阶段 (面板开发) 需集成的资产

| 面板组件 | 需集成资产 |
|----------|-----------|
| 通信层 | RA-20 (aeCall) |
| 轮询管理 | RA-21 (PollManager) |
| 对话框 | RA-22 (showConfirm), RA-23 (toast) |
| 主题 | RA-24 (CSS 变量主题) |
| ExtendScript 后端 | RA-01~14 (全部 AE API 封装), RA-25~28 (完整模块) |
