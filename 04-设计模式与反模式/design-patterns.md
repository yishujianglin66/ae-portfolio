# AE Vocal Remover 设计模式目录

> 从 ae-vocal-remover 遗留代码库中提炼的 10 个核心设计模式  
> 日期: 2026-06-05 | 版本: v1.0

---

## 模式概览

| # | 模式名 | 星级 | 来源文件 | 层次 |
|---|--------|------|----------|------|
| M1 | Poll Manager | ★★★★★ | `host/bridge/poll-manager.jsx` | ExtendScript |
| M2 | Bridge Protocol | ★★★★★ | `server/ae_bridge.py` | Python↔ExtendScript |
| M3 | Composite Module Loading | ★★★★ | `host/index.jsx` | ExtendScript |
| M4 | Async Chunked Execution | ★★★ | `host/utils/async-helper.jsx` | ExtendScript |
| M5 | Dual-Engine Fallback | ★★★★ | `test-suites/F5-vocal-sep/F5_vocal_separate.py` | Python |
| M6 | 6-Path Audio Detection | ★★★★ | `host/main.jsx` | ExtendScript |
| M7 | Seen-Map Dedup | ★★★ | `VocalSep_Consolidated.jsx` | ExtendScript |
| M8 | Singleton Service Registry | ★★★ | `server/services/vocal_engine.py` | Python |
| M9 | Layered NLP Fallback | ★★★ | `server/ai_recommender.py` | Python |
| M10 | Expression Animation | ★★★ | `host/text_engine.jsx` | ExtendScript |

---

## M1: Poll Manager ★★★★★

### 来源文件

- `host/bridge/poll-manager.jsx:1-187`
- `VocalSep_Consolidated.jsx` (ScriptUI 版本内联)

### 意图

解决 ExtendScript 中长时异步操作导致的 After Effects UI 冻结问题。使用 `app.scheduleTask()` 实现非阻塞轮询，以 task registry + lifecycle callbacks (onComplete/onProgress/onError) 模式管理批量异步任务。当 `app.scheduleTask` 不可用时自动回退到 `$.sleep()`。

### 结构

```javascript
// 核心结构: task registry + scheduleTask + lifecycle callbacks

AEStudioKit.PollManager._tasks = {};  // { taskId: { jobId, checkFn, onComplete, onProgress, onError, ... } }

AEStudioKit.PollManager.start = function(taskId, jobId, checkFn, options) {
    if (!options) options = {};
    var task = {
        taskId: taskId,
        jobId: jobId,
        checkFn: checkFn,
        onComplete: options.onComplete || null,
        onProgress: options.onProgress || null,
        onError: options.onError || null,
        maxAttempts: options.maxAttempts || 150,
        intervalMs: options.intervalMs || 2000,
        attempts: 0,
        callback: options.callback || null,
        running: true
    };
    AEStudioKit.PollManager._tasks[taskId] = task;
    AEStudioKit.PollManager._poll(taskId);
    return taskId;
};

// 非阻塞调度
AEStudioKit.PollManager._scheduleNext = function(taskId) {
    var task = AEStudioKit.PollManager._tasks[taskId];
    if (!task || !task.running) return;
    try {
        task.timerId = app.scheduleTask(
            "AEStudioKit.PollManager._poll('" + taskId + "');",
            Math.round(task.intervalMs),
            false
        );
    } catch (e) {
        // app.scheduleTask 不可用时回退到 $.sleep()
        $.sleep(Math.round(task.intervalMs / 1000 * 10) || 10);
        AEStudioKit.PollManager._poll(taskId);
    }
};

// 状态机驱动的轮询逻辑
AEStudioKit.PollManager._poll = function(taskId) {
    var task = AEStudioKit.PollManager._tasks[taskId];
    if (!task || !task.running) return;
    task.attempts++;
    var result = task.checkFn(task.jobId);
    var status = result.status || "";
    if (status === "completed" || status === "done") {
        task.running = false;
        if (task.onComplete) { try { task.onComplete(result); } catch (e) {} }
        AEStudioKit.PollManager._cleanup(taskId);
    } else if (task.attempts >= task.maxAttempts) {
        task.running = false;
        if (task.onError) {
            try { task.onError({ error: "轮询超时", attempts: task.attempts }); } catch (e) {}
        }
        AEStudioKit.PollManager._cleanup(taskId);
    } else {
        if (task.onProgress) {
            try { task.onProgress(result.progress || 0, result); } catch (e) {}
        }
        AEStudioKit.PollManager._scheduleNext(taskId);
    }
};
```

### 何时使用

- AE 面板需要查询后端任务状态且不阻塞 UI 时
- 需要管理多个并发轮询任务时（通过 taskId 隔离）
- 需要实时进度回调 + 超时保护时
- 环境可能不支持 `app.scheduleTask()` 需要自动降级时

### 何时不使用

- 轮询频率极高（<100ms）—— `scheduleTask` 精度有限，应改用 `$.sleep()` 循环
- 单次短操作（<2s）—— 直接同步调用即可
- WebSocket 可用的环境 —— 推送优于轮询

---

## M2: Bridge Protocol ★★★★★

### 来源文件

- `server/ae_bridge.py:41-55`
- `VocalSep_Consolidated.jsx:34-38` (协议定义注释)

### 意图

定义 ExtendScript 与 Python 之间的标准化进程间通信协议。ExtendScript 通过 `system.callSystem("python ae_bridge.py ...")` 调用 Python CLI，Python 通过 stdout 三令牌协议返回结果。`OK`/`ERROR`/`PROGRESS` 三元组实现了状态码、数据载荷、错误消息和进度的统一编码。

### 结构

```python
# Python 端: 协议发送函数

def ok(data):
    """输出成功结果"""
    print(f"OK:{json.dumps(data, ensure_ascii=False)}")
    sys.exit(0)

def error(msg):
    """输出错误"""
    print(f"ERROR:{msg}")
    sys.exit(1)

def progress(pct, msg=""):
    """输出进度 (通常输出到 stderr，防止干扰 stdout 协议)"""
    print(f"PROGRESS:{pct}/{msg}")

# 使用示例: ae_bridge.py 主入口
def cmd_separate(args):
    ensure_server_running()
    # ... 上传文件、获取 job_id ...
    result = resp.json()
    job_id = result["job_id"]

    # 轮询期间输出进度
    while waited < max_wait:
        time.sleep(poll_interval)
        status = status_resp.json()
        if status["status"] == "completed":
            ok({"job_id": job_id, "files": downloaded, "duration": status.get("duration", 0)})
            return
        elif status["status"] == "failed":
            error(status.get("message", "处理失败"))
        else:
            pct = status.get("progress", 10 + int(waited / max_wait * 80))
            print(f"PROGRESS:{pct}/{status.get('message', '处理中...')}", file=sys.stderr)
    error(f"处理超时 ({max_wait}秒)")

# 协议格式:
#   OK:<JSON数据>         — 成功，后跟 JSON 数据
#   ERROR:<消息>          — 失败，后跟可读错误消息
#   PROGRESS:<百分比>/<消息>  — 进度更新 (可选，通常到 stderr)
```

### 何时使用

- ExtendScript ↔ Python 进程间通信（`system.callSystem()` 调用的场景）
- 需要区分成功/失败/进行中三种状态的同步 CLI 调用
- stdout 承载结果、stderr 承载进度的双通道通信场景
- 解析端需要简单快速的字符串匹配（`startsWith("OK:")` / `startsWith("ERROR:")`）而非完整 JSON 解析器

### 何时不使用

- 超大数据传输（>1MB JSON）—— stdout buffer 可能截断，应改用文件或 HTTP 下载
- 需要双向流式通信 —— 应改用 WebSocket 或命名管道
- 多行输出场景 —— `PROGRESS` 令牌只能传递百分比和简短消息

---

## M3: Composite Module Loading ★★★★

### 来源文件

- `host/index.jsx:34-101` (v4.0 主项目)
- `AE-MotionStudio/AE-MotionStudio/host/index.jsx` (MotionStudio 重构版)

### 意图

解决 ExtendScript 无原生模块系统（无 `import`/`require`）的问题。通过 `$.evalFile()` 依次加载多个 .jsx 模块，每个模块用 `try-catch` 包裹实现优雅降级——任意模块加载失败不影响其余模块。加载后通过命名空间合并将不同来源的模块统一到一个入口命名空间中。

### 结构

```javascript
// 基础模块加载: try-catch + $.evalFile + 命名空间初始化

var utilDir = AEStudioKit.scriptDir + "/utils";

try { $.evalFile(utilDir + "/logger.jsx"); }
catch (e) { /* logger 不可用 */ }

try { $.evalFile(utilDir + "/async-helper.jsx"); }
catch (e) { /* optional */ }

try { $.evalFile(utilDir + "/json-polyfill.jsx"); }
catch (e) { /* optional */ }

// 功能模块按目录分组加载
try { $.evalFile(AEStudioKit.scriptDir + "/text-fx/apply-preset.jsx"); }
catch (e) { AEStudioKit._logWarn("text-fx/apply-preset.jsx: " + e); }

try { $.evalFile(AEStudioKit.scriptDir + "/vocal/import-audio.jsx"); }
catch (e) { AEStudioKit._logWarn("vocal/import-audio.jsx: " + e); }

try { $.evalFile(AEStudioKit.scriptDir + "/bridge/ae-bridge.jsx"); }
catch (e) { AEStudioKit._logWarn("bridge/ae-bridge.jsx: " + e); }

// 命名空间合并: 将 MotionStudio 子命名空间映射到统一入口
if (typeof MotionStudio !== "undefined") {
    if (typeof MotionStudio.TextFx !== "undefined") {
        AEStudioKit.TextFx = MotionStudio.TextFx;
    }
    if (typeof MotionStudio.Vocal !== "undefined") {
        AEStudioKit.Vocal = MotionStudio.Vocal;
    }
    if (typeof MotionStudio.Utils !== "undefined") {
        AEStudioKit.MSUtils = MotionStudio.Utils;
    }
}
```

### 何时使用

- ExtendScript 需要多文件模块化组织时
- 不同开发线（v4.0 vs MotionStudio）的模块需要合并到同一命名空间时
- 模块间存在可选依赖，部分模块缺失不应导致整体崩溃
- 从单体脚本向模块化架构迁移的过渡期

### 何时不使用

- 所有模块必须同时存在才能正常工作的场景 —— `try-catch` 隐藏了依赖缺失
- 模块间有强加载顺序依赖且顺序很重要 —— 需要显式的拓扑排序加载器
- 可用 ES6 import 的环境 —— `$.evalFile` 是 ES3 的权宜之计

---

## M4: Async Chunked Execution ★★★

### 来源文件

- `host/utils/async-helper.jsx:1-80` (v4.0 主项目)
- `AE-MotionStudio/AE-MotionStudio/host/utils/async-helper.jsx` (MotionStudio)

### 意图

在 ExtendScript 中模拟异步任务执行。将大任务数组分割为小段，每段之间调用 `$.sleep(10)` 让出控制权给 AE 主线程处理 UI 事件，防止界面卡死。使用 `while` 循环代替递归以避免 ExtendScript 调用栈溢出。

### 结构

```javascript
MotionStudio.Utils.asyncExecute = function(tasks, taskFunc, callback, chunkSize) {
    if (!tasks || tasks.length === 0) {
        if (callback) callback();
        return;
    }
    if (!chunkSize || chunkSize <= 0) { chunkSize = 1; }

    var currentIndex = 0;
    var totalTasks = tasks.length;

    // while 循环代替递归，避免 ExtendScript 调用栈溢出
    while (currentIndex < totalTasks) {
        try {
            var endIndex = currentIndex + chunkSize;
            if (endIndex > totalTasks) { endIndex = totalTasks; }

            // 执行本段内的所有任务
            for (var i = currentIndex; i < endIndex; i++) {
                taskFunc(tasks[i]);
            }
            currentIndex = endIndex;

            // 让出控制权，让 AE 处理 UI 事件
            $.sleep(10);
        } catch (e) {
            if (callback) { callback(e); }
            return;
        }
    }
    if (callback) { callback(); }
};
```

### 何时使用

- 需要在 AE 中批量处理大量图层/文件而不冻结 UI 时
- 任务本身是同步的但总数量很大（>50 项）
- 无法使用 `app.scheduleTask()` 或 Web Worker 的环境

### 何时不使用

- 任务间有复杂回调依赖 —— 此模式是线性的，不支持 then/catch 链
- 单个任务执行时间超过 500ms —— `$.sleep(10)` 之前 UI 仍会冻结
- 可用 `app.scheduleTask()` 时 —— M1 Poll Manager 更优（真正的非阻塞）

---

## M5: Dual-Engine Fallback ★★★★

### 来源文件

- `test-suites/F5-vocal-sep/F5_vocal_separate.py:193-400`

### 意图

为音频分离提供自动引擎选择与降级策略。主引擎 Demucs (AI 高质量) 在第一优先级，FFmpeg 相位抵消法 (通用降级) 作为 fallback。通过运行时环境检测（`detect_demucs()` 检查 `import demucs` 是否成功）自动选择可用引擎，将引擎选择逻辑与分离执行逻辑分离。

### 结构

```python
def detect_demucs():
    """检测 Demucs 是否可用"""
    try:
        import demucs
        import torch
        return True
    except ImportError:
        LOG.log("Demucs 未安装 — 将使用 FFmpeg 相位抵消作为降级方案", "WARN")
        return False


def separate_vocals(input_path, mode="both", engine="auto", output_dir=None):
    # ── 引擎选择 ──
    if engine == "auto":
        has_demucs = detect_demucs()
        if has_demucs:
            engine = "demucs"
        else:
            engine = "ffmpeg"
            LOG.log("自动选择 FFmpeg (Demucs 不可用)", "INFO")

    # ── 执行分离 ──
    if engine == "ffmpeg":
        results = ffmpeg_phase_separation(input_path, output_dir, mode)
    elif engine == "demucs":
        results = demucs_separation(input_path, output_dir, mode)
    else:
        raise ValueError(f"未知引擎: {engine}。可选: demucs, ffmpeg, auto")

    return {
        "vocals": results.get('vocals'),
        "instrumental": results.get('instrumental'),
        "engine_used": engine,       # 始终告知调用方实际使用的引擎
        "elapsed_sec": round(elapsed, 1),
    }
```

### 何时使用

- 功能有多个后端实现且质量/性能差异显著时
- 主引擎有重依赖（如 PyTorch GPU）不应强制安装
- 需要在用户无感知的情况下提供最佳可用效果
- 结果中需要标记实际使用的引擎（`engine_used` 字段）以供调试

### 何时不使用

- 两个引擎的输出质量差异不可接受（如 FFmpeg 仅对立体声有效，单声道会失败）
- 引擎间 API 差异太大导致统一接口成本过高
- 需要用户显式选择引擎的场景 —— `auto` 会隐藏选择

---

## M6: 6-Path Audio Detection ★★★★

### 来源文件

- `host/main.jsx:531-679`

### 意图

在 After Effects 中鲁棒地检测图层是否包含音频及获取音频源文件路径。由于 AE 图层类型多样（FootageItem / SolidSource / PlaceholderSource / 嵌套合成等），单一检测方法不可靠。通过 6 层递进式检测路径，从最可靠到最宽松，每一层失败后自动尝试下一层。

### 结构

```javascript
// 综合检测策略: 6 层递进式探测
var hasAudio = false;
var filePath = '';
var sourceType = 'unknown';

// 路径 1: hasAudio (ExtendScript 原生属性，最可靠)
try { hasAudio = layer.hasAudio; } catch(e) {}

// 路径 2: source.hasAudio (间接访问)
var src = layer.source;
try { if (src && src.hasAudio) hasAudio = true; } catch(e) {}

// 路径 3: FootageItem + mainSource.conformAudioRate (音频相关指示器)
if (src) {
    if (src instanceof FootageItem) {
        try {
            if (src.file) { filePath = src.file.fsName; sourceType = 'footage'; }
                            duration = src.duration || 0;
        } catch(e) {}
    }
    try {
        var ms = src.mainSource;
        if (ms && ms.conformAudioRate && ms.conformAudioRate > 0) hasAudio = true;
    } catch(e) {}

    // 路径 4: 嵌套合成递归扫描
    if (!filePath && src instanceof CompItem) {
        for (var sri = 1; sri <= src.numLayers; sri++) {
            var subLayer = src.layer(sri);
            var subSrc = subLayer.source;
            if (subSrc instanceof FootageItem && subSrc.file) {
                // 检查是否为音频扩展名
                var subExt = String(subSrc.file.name).toLowerCase();
                var subAudioExts = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac', '.aiff', '.wma', '.opus'];
                for (var se = 0; se < subAudioExts.length; se++) {
                    if (subExt.indexOf(subAudioExts[se]) >= 0) {
                        filePath = subSrc.file.fsName; hasAudio = true;
                        sourceType = 'nested_comp'; break;
                    }
                }
            }
        }
    }
}

// 路径 5: 属性遍历 — Audio Levels / Audio Group
if (!hasAudio && !filePath) {
    try {
        var audioLevels = layer.property("ADBE Audio Levels");
        if (audioLevels && audioLevels.numKeys > 0) hasAudio = true;
    } catch(e) {}
    try {
        var audioGroup = layer.property("Audio");
        if (audioGroup && audioGroup.numProperties > 0) hasAudio = true;
    } catch(e) {}
}

// 路径 6: 扩展名匹配 (回退检测 — 覆盖视频文件含音频场景)
if (!hasAudio && !filePath && src instanceof FootageItem) {
    var ext = String(src.file.name).toLowerCase();
    var audioExts = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', /*...*/];
    var videoExts = ['.mp4', '.mov', '.avi', '.mkv', /*...*/];
    // 检查音频扩展名 → 检查视频扩展名 (视频可能含音频轨)
}
```

### 何时使用

- 需要从 AE 图层中提取音频文件路径时（用于后续处理）
- 图层类型未知——可能是素材、固态层、嵌套合成、占位符
- 每种检测方法可能在不同 AE 版本/图层类型下抛出异常

### 何时不使用

- 只需要判断"是否有音频"（是/否）而不需要文件路径——路径 1 就够用
- AE 版本确定且图层类型已知——可以省略冗余检测
- 性能敏感的批量操作——6 层检测在最坏情况下可能触发多次属性访问

---

## M7: Seen-Map Dedup ★★★

### 来源文件

- `VocalSep_Consolidated.jsx:1801-1857`

### 意图

在收集分离结果时去重，避免同一个 stem（如 "vocals"）从多个数据源重复出现。使用 Object map (`{}`) 的 O(1) 键查找替代 `Array.some()` 的 O(n) 线性扫描。适合在 ES3 环境（无 `Set`/`Map`）下实现高效去重。

### 结构

```javascript
/**
 * 从分离结果中收集所有需要处理的条目 (本地路径 + 远程URL)。
 * 使用 seen map 去重替代 O(n²) 的 some() 查找，时间复杂度 O(n)。
 */
function collectResults(data) {
    var results = [];
    var urls = [];
    var seen = {};  // stem → true 去重 Map

    // 从 output_files 收集
    if (data.output_files && typeof data.output_files === 'object') {
        for (var stem in data.output_files) {
            if (!data.output_files.hasOwnProperty(stem)) continue;
            var info = data.output_files[stem];
            if (typeof info.url === 'string' && info.url.indexOf('http') === 0) {
                if (!seen[stem]) { seen[stem] = true; urls.push({ s: stem, u: info.url }); }
            } else if (typeof info.path === 'string') {
                if (!seen[stem]) { seen[stem] = true; results.push({ s: stem, p: info.path, l: getLabel(stem) }); }
            }
        }
    }

    // 从 files 收集 (跨源去重 — 复用同一个 seen map)
    if (data.files && typeof data.files === 'object') {
        for (var stem2 in data.files) {
            if (!data.files.hasOwnProperty(stem2)) continue;
            if (seen[stem2]) continue;  // O(1) 查重
            var fp = data.files[stem2];
            if (typeof fp === 'string' && fp.indexOf('http') === 0) {
                seen[stem2] = true; urls.push({ s: stem2, u: fp });
            } else if (typeof fp === 'string') {
                seen[stem2] = true; results.push({ s: stem2, p: fp, l: getLabel(stem2) });
            }
        }
    }

    // 从 output/vocals_url 等属性收集 (第三次遍历 — 仍复用 seen)
    var urlKeys = ['vocals_url', 'instrumental_url', 'drums_url', 'bass_url', 'other_url'];
    for (var i = 0; i < urlKeys.length; i++) {
        var key = urlKeys[i];
        if (typeof out2[key] === 'string' && out2[key].indexOf('http') === 0) {
            var s2 = key.replace('_url', '');
            if (!seen[s2]) { seen[s2] = true; urls.push({ s: s2, u: out2[key] }); }
        }
    }

    return { results: results, urls: urls };
}
```

### 何时使用

- 多个数据源（output_files / files / URL 属性）可能产生重复 stem 时
- ES3 环境下无 `Set`/`Map` 可用时
- 去重键是简单字符串（stem 名称）
- 需要跨多次遍历保持去重状态时

### 何时不使用

- 去重键是复杂对象——Object key 只能是字符串
- 数据量极小（<10 项）—— O(n²) 的差异不可感知
- 可用 `Set` 的环境——`new Set()` 语义更清晰

---

## M8: Singleton Service Registry ★★★

### 来源文件

- `server/services/vocal_engine.py:776-860`

### 意图

管理多个 AI 分离引擎（Demucs / Spleeter / Open-Unmix）的实例化和缓存。使用线程安全的类级工厂模式，每个引擎类型只创建一次实例，避免重复加载大型 AI 模型（>80MB）。提供统一的 `get_engine()` 接口，调用方无需关心实例是否已创建。

### 结构

```python
class SeparatorFactory:
    """分离引擎工厂 - 管理引擎的创建和缓存"""

    # 缓存已实例化的引擎
    _engines: Dict[str, BaseSeparator] = {}

    # 线程安全锁
    _lock = threading.Lock()

    # 引擎注册表 — 新增引擎只需添加一行
    _engine_classes = {
        "demucs": DemucsSeparator,
        "spleeter": SpleeterSeparator,
        "openunmix": OpenUnmixSeparator,
    }

    @classmethod
    def get_engine(cls, model_name: str) -> BaseSeparator:
        """获取指定名称的分离引擎实例 (线程安全缓存)"""
        model_name = model_name.lower()
        if model_name not in cls._engine_classes:
            raise ValueError(
                f"不支持的分离引擎: {model_name}，"
                f"可用引擎: {list(cls._engine_classes.keys())}"
            )
        with cls._lock:
            if model_name not in cls._engines:
                cls._engines[model_name] = cls._engine_classes[model_name]()
            return cls._engines[model_name]

    @classmethod
    def get_available_engines(cls) -> List[Dict[str, Any]]:
        """获取所有可用的分离引擎列表 (含状态检测)"""
        engines_info = []
        with cls._lock:
            for name, engine_class in cls._engine_classes.items():
                if name not in cls._engines:
                    cls._engines[name] = engine_class()
                engine = cls._engines[name]
                engines_info.append({
                    "name": engine.name,
                    "display_name": engine.display_name,
                    "available": engine.is_available(),
                    "status": "已安装" if engine.is_available() else "未安装",
                    "stems": engine.get_available_stems(),
                })
        return engines_info

    @classmethod
    def unload_all(cls):
        """卸载所有已加载的引擎模型 (释放显存)"""
        for name, engine in cls._engines.items():
            try:
                engine.unload_model()
            except Exception:
                pass
        print("[分离引擎] 所有引擎模型已卸载")
```

### 何时使用

- 多个重资源对象（AI 模型、数据库连接池）需要全局复用
- 对象实例化成本高（模型加载 >1s, 内存占用 >100MB）
- 调用方不需要知道实例是否已存在——透明缓存
- 需要线程安全的懒加载

### 何时不使用

- 需要每请求独立状态的引擎实例——缓存会导致状态污染
- 引擎生命周期与请求绑定（如临时模型）——应直接实例化并随请求销毁
- 单线程环境——`threading.Lock()` 开销不必要

---

## M9: Layered NLP Fallback ★★★

### 来源文件

- `server/ai_recommender.py:61-115`

### 意图

为文字内容提供多层级的情感分析与预设推荐。三层降级策略确保在任意环境下都能返回结果：HuggingFace Transformers（最高质量，需网络）→ SnowNLP（中文专用，本地运行）→ 关键词匹配（内置词典，零依赖）。每层加载失败时自动降级到下一层，最终保证有结果返回。

### 结构

```python
class AIRecommender:
    """AI 智能推荐器 — 三层降级策略"""

    def __init__(self, use_ai=True):
        self.use_ai = use_ai
        self.hf_pipeline = None
        self.snownlp_available = False
        self.nlp_source = "keyword"  # keyword | snownlp | huggingface

    def _init_nlp(self):
        """初始化 NLP 引擎 — 混合模式: 关键词(主力) + SnowNLP(增强) + HuggingFace(可选)"""
        self.nlp_source = "hybrid"

        # 层 2: 加载 SnowNLP (中文情感增强)
        if self._try_snownlp():
            print("   + SnowNLP 中文情感增强已启用")
        else:
            print("   💡 pip install snownlp 可获得更好的中文情感分析")

        # 层 1: 尝试 HuggingFace (多语言，需网络)
        if self._try_huggingface():
            print("   + HuggingFace 多语言增强已启用")
        else:
            print("   💡 pip install transformers 并设置 HF_ENDPOINT=https://hf-mirror.com")

    def _try_huggingface(self):
        try:
            from transformers import pipeline
            self.hf_pipeline = pipeline(
                "sentiment-analysis",
                model="lxyuan/distilbert-base-multilingual-cased-sentiments-student",
                top_k=None   # 返回所有情感分数
            )
            return True
        except ImportError:
            print("⚠️ transformers 未安装 (pip install transformers)")
        except Exception as e:
            print(f"⚠️ HuggingFace 加载失败: {e}")
        return False

    def _try_snownlp(self):
        try:
            from snownlp import SnowNLP
            self.snownlp_available = True
            return True
        except ImportError:
            pass
        return False

    # 层 3: 内置关键词词典 (永远可用)
    EMOTION_KEYWORDS = {
        "excited": ["激动", "兴奋", "震撼", "炸裂", "燃", "amazing", "wow", "fire"],
        "calm": ["宁静", "优雅", "简约", "清新", "calm", "minimal", "clean"],
        "tech": ["科技", "未来", "数字", "AI", "代码", "tech", "digital", "cyber"],
        # ... 10 个情感类别，120+ 中英文关键词
    }
```

### 何时使用

- NLP 模型加载可能失败（网络不可达、依赖未安装）
- 用户环境差异大——从完整 AI 环境到裸 Python 都需返回结果
- 结果质量可降级——完美分析 > 大致情感 > 关键词匹配
- 各层之间相互独立，不存在强依赖

### 何时不使用

- 所有层都需要网络或大依赖——如果连内置词典都不可用则无意义
- 各层输出格式差异太大导致无法统一——此处三层都输出情感标签
- 需要严格保证分析质量——降级结果可能严重偏离

---

## M10: Expression Animation ★★★

### 来源文件

- `host/text_engine.jsx:256-545`

### 意图

After Effects 文字动画预设通过编程方式构建。每个预设操作 AE 的文字动画器(Text Animator) 属性组，为选择器 (Selector) 设置关键帧或写入 JavaScript 表达式字符串 (`prop.expression = expr`)，实现弹跳、故障、Matrix 雨、彩虹色、打字机等复杂效果——所有这些效果在代码中表示为 AEScript 表达式字符串。

### 结构

```javascript
// ===== 弹跳入场: setValueAtTime 关键帧 + expression =====
_presetFns.bounce = function(layer, dur, delay, intensity) {
    var a = _addAnimator(layer);
    _addAnimProp(a, "ADBE Text Scale 3D").setValue([150 * intensity, 150 * intensity, 100]);
    _addAnimProp(a, "ADBE Text Position 3D").setValue([0, -80 * intensity, 0]);
    var s = _addSelector(a); _setMode(s, 1); _setSmooth(s, 60);
    var amt = s.property("ADBE Text Percent Amount");
    _setExpr(amt,
        'freq=2;decay=5;dly=textIndex*thisComp.frameDuration*3;' +
        't=Math.max(time-(inPoint+dly),0);' +
        '100*Math.cos(t*freq*Math.PI*2)/Math.exp(t*decay)');
};

// ===== Matrix 字符雨: Source Text 表达式 =====
_presetFns.matrix_rain = function(layer, dur, delay, intensity) {
    var st = layer.property("Source Text");
    _setExpr(st,
        'txt=text.sourceText;' +
        'chars="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789ｱｲｳｴｵｶｷｸｹｺ";' +
        'r="";seedRandom(Math.floor(time*' + (10*intensity) + '),true);' +
        'for(j=0;j<txt.length;j++)r+=chars[Math.floor(random(chars.length))];r');
};

// ===== 彩虹色: Fill Color 表达式 =====
_presetFns.rainbow = function(layer, dur, delay, intensity) {
    var anim = _addAnimator(layer);
    var fill = anim.property("ADBE Text Animator Properties").property("ADBE Text Fill Color");
    if (!fill) { fill = _addAnimProp(anim, "ADBE Text Fill Color"); }
    if (fill) {
        _setExpr(fill,
            'h=time*' + (0.5*intensity) + '+textIndex*0.1;' +
            'hslToRgb([h%1,0.8,0.6,1])');
    }
};

// ===== 打字机效果: 逐帧步进表达式 =====
_presetFns.typewriter = function(layer, dur, delay, intensity) {
    var a = _addAnimator(layer); _addAnimProp(a, "ADBE Text Opacity").setValue(0);
    var s = _addSelector(a); _setMode(s, 1); _setSmooth(s, 0);
    _setExpr(s.property("ADBE Text Percent Start"),
        'Math.min(100,(time-inPoint)*' + (8*intensity) + '*1/thisComp.frameDuration)');
};

// ===== 通用工具: _setExpr 封装 expression 字符串赋值 =====
function _setExpr(prop, expr) {
    if (!prop) return;
    try { if (prop.canSetExpression) prop.expression = expr; } catch(e) {}
}
```

### 何时使用

- 需要以编程方式生成 AE 文字动画预设（30 个预设统一管理）
- 动画效果难以用关键帧描述（如弹跳衰减、噪声驱动）
- 需要将用户参数（intensity/duration）注入到实时表达式计算中
- 预设间共享大量通用模板代码（animator + selector + range 设置）

### 何时不使用

- 简单动画只用 setValueAtTime 关键帧即可——expression 增加 AE 每帧计算开销
- 表达式字符串需要包含用户输入时——需严格转义防止表达式注入
- AE 版本过老不支持 `canSetExpression` / `expression` 属性

---

## 附录: 模式关系图

```
┌─────────────────────────────────────────────────────────┐
│                    CEP Panel (client/)                   │
│                         ↑ CSInterface                   │
├─────────────────────────────────────────────────────────┤
│              ExtendScript Host (host/)                   │
│                                                         │
│  M1 Poll Manager ──→ M2 Bridge Protocol ──→ Python      │
│       │                                              │
│  M3 Module Loading                                     │
│  M4 Chunked Execution                                  │
│  M6 6-Path Audio Detect                                │
│  M7 Seen-Map Dedup                                     │
│  M10 Expression Animation                               │
├─────────────────────────────────────────────────────────┤
│              Python Server (server/)                     │
│                                                         │
│  M5 Dual-Engine Fallback                                │
│  M8 Singleton Registry                                  │
│  M9 Layered NLP Fallback                                │
└─────────────────────────────────────────────────────────┘
```

- **M1 + M2** 是核心通信模式: Poll Manager 在 ExtendScript 侧管理轮询，Bridge Protocol 在 Python 侧编码结果
- **M3** 是架构模式: 组合所有 ExtendScript 模块，包括 M4/M6/M7/M10 的实现
- **M5 + M8 + M9** 是 Python 服务端降级模式: 都体现了"检测可用性→降级→保证结果"的设计哲学
- **M6 + M7** 是数据处理模式: 多路径探测 + O(1) 去重解决 ExtendScript 的鲁棒性问题
