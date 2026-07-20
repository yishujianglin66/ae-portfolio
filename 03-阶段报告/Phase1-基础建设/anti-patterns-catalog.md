# 反模式清单 — Anti-Patterns Catalog

> **项目**: 第一阶段 — 遗产资产深度剖析
> **日期**: 2026-06-05
> **收录**: 37 个从遗产代码中识别的应避免模式
> **风险等级**: 🔴 高: 8 / 🟡 中: 19 / 🟢 低: 10

---

## 🔴 高风险反模式 (8)

### AP-001: 同步 system.callSystem() 用于长时间操作

**严重性**: 🔴 高 | **影响**: AE UI 完全冻结
**出现**: 13+ 处

**描述**:
`system.callSystem()` 在 ExtendScript 中是同步阻塞调用。当用于 FFmpeg、Python 推理或网络下载时，AE 主线程完全冻结，操作系统会将 AE 标记为"无响应"。

**具体位置**:

| 文件 | 行号 | 操作 | 预估阻塞时间 |
|------|------|------|-------------|
| `F4_extract_audio.jsx` | 252 | FFmpeg 音频提取 | 5-30s |
| `F7_download.jsx` | 157 | PowerShell/curl 下载 | 10s-5min |
| `VocalSep_Consolidated.jsx` | 1156 | localSplit (Tab2) | 最长 600s |
| `VocalSep_Consolidated.jsx` | 1174 | localJoin (Tab3) | 10-120s |
| `VocalSep_Consolidated.jsx` | 885-902 | startLocalServer | 5-20s |
| `VocalSep_Consolidated.jsx` | 3949 | topazExec (Tab6) | 10s-10min |
| `AEStudioKit_Panel.jsx` | 339 | F5 人声分离 | 最长 600s |
| `AEStudioKit_Panel.jsx` | 430 | F7 下载 | 10s-5min |
| `host/main.jsx` | 975-981 | localEnhanceVideo | 30s-5min |
| `host/main.jsx` | 1168-1200 | reg.exe 注册表查询 | 2-5s |

**错误代码示例**:
```javascript
// ❌ 反模式
var cmd = 'ffmpeg -i "' + input + '" -vn "' + output + '"';
var result = system.callSystem(cmd); // AE UI 冻结 5-30 秒
```

**正确做法**:
```javascript
// ✅ 使用 DP-01 Submit-Poll-Complete 模式
var jobId = submitBackgroundJob(cmd);
app.scheduleTask('VocalSep_PollLoop', 2000, true); // 异步轮询
```

---

### AP-002: $.sleep() 忙等待

**严重性**: 🔴 高 | **影响**: 每次调用阻塞 AE 主线程
**出现**: `VocalSep_Consolidated.jsx:918`

**描述**:
`$.sleep()` 在 ExtendScript 中是忙等待——它不释放线程，而是完全阻塞。在轮询循环中使用会导致 UI 完全冻结。

**错误代码**:
```javascript
// ❌ 反模式
function waitForServer(url, maxRetries) {
    for (var i = 0; i < maxRetries; i++) {
        var ok = checkServer(url);
        if (ok) return true;
        $.sleep(500); // 阻塞 500ms — AE 在此期间完全冻结
    }
    return false;
}
```

**正确做法**:
```javascript
// ✅ 使用 app.scheduleTask 驱动的轮询
var retryCount = 0;
function pollLoop() {
    if (checkServer(url)) {
        onServerReady();
        return;
    }
    if (++retryCount < maxRetries) {
        app.scheduleTask('pollLoop', 500, false); // 非阻塞延迟
    }
}
```

---

### AP-003: 空 catch 块静默吞噬异常

**严重性**: 🔴 高 | **影响**: 调试极其困难，静默功能降级
**出现**: 37 处

**描述**:
`catch (e) {}` 或 `except Exception: pass` 完全忽略异常，使得错误发生时用户和开发者完全不知情。

**具体位置 (代表性样本)**:

| 文件 | 行号 | 吞噬的异常 |
|------|------|-----------|
| `F1_layer_type.jsx` | 168, 183-188, 192, 203, 210 | classifyLayer 中的属性访问 |
| `F2_text_anim.jsx` | 178-193 | 选择器模式/平滑度设置 |
| `F5_vocal_separate.py` | 84 | FFmpeg 发现 |
| `F5_vocal_separate.py` | 167-168 | 磁盘空间检查 |
| `F8_topaz_detect.jsx` | 86 | 通配符搜索 |
| `AEStudioKit_Panel.jsx` | 91, 112, 122, 126, 185, 370, 386, 453, 456 | PanleLog 操作 |
| `VocalSep_Consolidated.jsx` | 365, 504, 689, 704 | 各种 IO |
| `host/main.jsx` | 338, 339, 345, 386, 397 | Python 路径扫描 |

**错误代码**:
```javascript
// ❌ 反模式
try {
    var ver = layer.source.mainSource.color;
} catch (e) {} // 静默 — 永远不会知道 color 访问失败
```

**正确做法**:
```javascript
// ✅ 最少记录日志
try {
    var ver = layer.source.mainSource.color;
} catch (e) {
    LOG.log('Failed to read color from layer "' + layer.name + '": ' + e.toString(), 'DEBUG');
}
```

---

### AP-004: buildUI() 单体巨型函数

**严重性**: 🔴 高 | **影响**: 不可测试、不可维护
**出现**: `VocalSep_Consolidated.jsx:2085-4364` (2285 行)

**描述**:
`buildUI()` 函数约 2285 行，包含 9 个 Tab 的全部 UI 构建逻辑、事件处理和状态管理。圈复杂度约 40。

**错误代码结构**:
```javascript
function buildUI() {
    // ... lines 2085-2150: 窗口创建
    // ... lines 2151-2300: Tab1 构建
    // ... lines 2301-2800: Tab2-4 构建
    // ... lines 2801-3500: Tab5-7 构建
    // ... lines 3501-4100: Tab8-9 构建
    // ... lines 4101-4364: 事件绑定 + 状态初始化
    // 总计 2285 行
}
```

**正确做法**:
```javascript
// ✅ 每个 Tab 一个独立函数
function buildUI() {
    var win = createWindow();
    var tabs = createTabBar(win);
    buildTab1_VocalSep(tabs[0]);
    buildTab2_MultiTrack(tabs[1]);
    buildTab3_AudioTools(tabs[2]);
    // ... 每个 100-200 行
}
```

---

### AP-005: getSelectedAudioInfo() 4 层嵌套循环

**严重性**: 🔴 高 | **影响**: O(n*m*k) 复杂度，大量图层时性能退化
**出现**: `host/main.jsx:518-697` (170 行)

**描述**:
`getSelectedAudioInfo()` 包含 4 层嵌套循环：图层遍历 → 嵌套合成子图层遍历 → 音频扩展名匹配 → 视频扩展名匹配。每层都包含 try/catch 和条件分支。

**代码结构**:
```javascript
// 4 层嵌套
for (selectedLayers) {           // 第 1 层
    if (compItem) {
        for (compLayers) {       // 第 2 层 (嵌套合成)
            for (audioExts) {    // 第 3 层 (扩展名匹配)
                for (videoExts) { // 第 4 层 (扩展名匹配)
                    // ...
                }
            }
        }
    }
}
```

**正确做法**: 使用查表替换线性循环，将嵌套逻辑展平。

---

### AP-006: 硬编码用户路径

**严重性**: 🔴 高 | **影响**: 跨机器不可移植
**出现**: 多处

**描述**:
代码包含硬编码的 `Users/Administrator` 路径，在其他用户账户上完全失效。

**具体位置**:

| 文件 | 行号 | 硬编码路径 |
|------|------|-----------|
| `VocalSep_Consolidated.jsx` | 408 | `Folder.userData.fsName` + 回退中包含用户名 |
| `VocalSep_Consolidated.jsx` | 412, 448, 549 | Python/FFmpeg 候选路径中包含用户名 |
| `F5_vocal_separate.py` | 73 | `Path.home() / "..."` (正确) 但同时有硬编码 Windows 路径 |
| `F8_topaz_detect.jsx` | 45-46 | `C:/Program Files/Topaz Labs/` |
| `config.py` | 95-98 | `C:/Program Files/Topaz Labs/` |

---

### AP-007: CORS 完全开放 + 无认证

**严重性**: 🔴 高 | **影响**: 安全风险
**出现**: `server/server.py:507-513`, `config.py:65`

**描述**:
Python 服务端配置了 `allow_origins=["*"]`（任何来源可访问），同时 `API_SECRET_KEY` 为空字符串。虽然服务仅绑定 127.0.0.1，但在本地恶意软件/浏览器扩展攻击场景下仍有风险。

**错误代码**:
```python
# server.py:507-513
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # ❌ 完全开放
    allow_methods=["*"],
    allow_headers=["*"],
)

# config.py:65
API_SECRET_KEY = ""             # ❌ 无认证
```

---

### AP-008: CEP manifest 允许本地文件访问

**严重性**: 🔴 高 | **影响**: Web 安全风险
**出现**: `CSXS/manifest.xml:34`

**描述**:
manifest 包含 `--allow-file-access-from-files` CEF 命令行参数，赋予面板 JS 从 `file://` URL 读取任意本地文件的权限。

**错误配置**:
```xml
<CEFCommandLine>
    <Parameter>--enable-nodejs</Parameter>
    <Parameter>--mixed-context</Parameter>
    <Parameter>--allow-file-access-from-files</Parameter>  <!-- ❌ 安全风险 -->
</CEFCommandLine>
```

---

## 🟡 中等风险反模式 (19)

### AP-009: F3 中 overrideIntensity 声明但未使用

**出现**: `F3_apply_preset.jsx:53`
**描述**: CONFIG 中定义了 `overrideIntensity` 字段但在 `applyPresetToLayer()` 中从未引用。死代码 + 用户困惑。

---

### AP-010: F3/F4 缺少 CEP 桥接返回值

**出现**: `F3_apply_preset.jsx:485`、`F4_extract_audio.jsx:298`
**描述**: 不像 F1/F2 那样在脚本末尾返回 `'F1_OK:' + JSON.stringify(...)` 字符串。CEPP evalScript 无法获取成功/失败信号。

---

### AP-011: Animator API 函数重复 (3 次)

**出现**: `F2_text_anim.jsx`, `F3_apply_preset.jsx`, `text_engine.jsx`
**描述**: `_getAnimatorsGroup()`, `_addAnimator()`, `_addSelector()`, `_addAnimProp()` 在 3 个文件中几乎完全相同 (~80 行重复)。应提取为共享模块。

---

### AP-012: JSON polyfill 重复 (3 次)

**出现**: `F3_apply_preset.jsx:60-155`, `VocalSep_Consolidated.jsx:120-214`, `host/main.jsx:113-227`
**描述**: 完整的 JSON 解析器在 3 个地方重复实现，总计约 300 行重复代码。考虑到 ES3 限制，这是可以理解的，但应统一为一个共享的 `$.evalFile()` 加载模块。

---

### AP-013: Logger 初始化模式重复 (6 次)

**出现**: F1:71-75, F2:86-88, F3:167-170, F4:34-36, F6:48-58, F7:30-41, F8:25-35
**描述**: 每个 F# 模块都包含了加载 `AEStudioKit_Logger.jsx` 的相同 try/catch + fallback 逻辑。应提取为单一的 `requireLogger()` 辅助函数。

---

### AP-014: 音频扩展名列表重复 (4 次)

**出现**: `F1_layer_type.jsx:341`, `F4_extract_audio.jsx:108-110`, `F6_import_audio.jsx:101-106`, `host/main.jsx:583-601`
**描述**: 支持的文件扩展名列表（.wav, .mp3, .aiff, .flac, .ogg, .wma, .m4a, .aac 等）在 4 个地方独立维护，可能不同步。

---

### AP-015: system.callSystem() stderr 捕获不可靠

**出现**: `F4_extract_audio.jsx:70-71`, `VocalSep_Consolidated.jsx:641-648`
**描述**: 在 Windows 上，ExtendScript 的 `system.callSystem()` 对 stderr 的重定向行为因 AE 版本而异。依赖 `2>&1` 或输出内容检测可能在不同版本上失败。

---

### AP-016: 路径分隔符混合 (正斜杠 vs 反斜杠)

**出现**: `F4_extract_audio.jsx:232-233`
**描述**: `Folder.desktop.fsName` 在 Windows 上返回反斜杠路径 (`C:\Users\...\Desktop`)，但代码追加 `'/' + outputName`。虽大多数 Windows API 能处理但不够规范。

---

### AP-017: F4 仅处理第一个选中图层

**出现**: `F4_extract_audio.jsx:162`
**描述**: `var layer = sel[0]` 只取第一个图层，不警告用户其余图层被忽略。不符合用户预期。

---

### AP-018: cepDispatch() 巨型 switch (30 case)

**出现**: `host/main.jsx:1361-1772` (410 行)
**描述**: 30 个 case 的 switch 语句，每个包含独立的参数解析和错误处理。应使用命令映射表替代。

---

### AP-019: ae_bridge.py 巨型 if/elif 链 (26 命令)

**出现**: `server/ae_bridge.py:500-514`
**描述**: 26 个 `if command == 'foo':` 的条件链。应使用字典映射。

---

### AP-020: F6 getFiles() 可能返回 null

**出现**: `F6_import_audio.jsx:70-71`
**描述**: `f5Dir.getFiles('*.wav')` 在目录不存在或空时可能返回 null。`files.length` 会在 null 上抛出异常。

---

### AP-021: F7 下载无 URL 验证

**出现**: `F7_download.jsx:20-24 (CONFIG.url)`
**描述**: URL 未经验证直接传递给 `system.callSystem()`，可能导致命令注入或意外的网络行为。

---

### AP-022: F5 Demucs 下载无用户提示

**出现**: `F5_vocal_separate.py:299-304`
**描述**: Demucs 模型首次运行时自动下载（可能数 GB），但无任何用户提示或进度显示。用户只看到"运行中，请稍候"。

---

### AP-023: 服务端 threading.Thread 在 ASGI 中

**出现**: `server/server.py:1506`、`server/server.py:1768`
**描述**: 在 FastAPI (ASGI) 中使用原生 `threading.Thread` 而非 `BackgroundTasks`，可能在服务器关闭时丢失任务。

---

### AP-024: ae_bridge.py 同步 time.sleep() 轮询

**出现**: `server/ae_bridge.py:234-274`
**描述**: 3 个命令 (separate, split, effect) 都包含相同的 `time.sleep()` + 检查循环模式。应提取为公共轮询函数，且应考虑使用 asyncio。

---

### AP-025: setInterval 无清理

**出现**: `client/app.js:1785`
**描述**: `updateAllStatus` 的 `setInterval` 定时器在面板隐藏/卸载时从未 `clearInterval()`。可能导致后台持续发送 HTTP 请求。

---

### AP-026: onclick 替代 addEventListener (40+ 处)

**出现**: `client/app.js:1587-1691`
**描述**: 使用 `element.onclick = function() {}` 而非 `addEventListener`。这使事件处理器可被覆盖，且不支持多个监听器。

---

### AP-027: 轮询进度盲目估算

**出现**: `client/poll-manager.js:207`
**描述**: `Math.min(10 + Math.floor(t.attempts / 2), 90)` 在没有真实进度数据时生成虚假进度值。用户可能看到进度条倒退或跳跃。

---

## 🟢 低风险反模式 (10)

### AP-028: F3 回退 Logger 无文件输出

**出现**: `F3_apply_preset.jsx:171-175`
**描述**: F3 的回退 Logger 仅写入 `$.writeln()`，不像 F1/F2 那样也写文件。如果 `AEStudioKit.Logger` 加载失败，所有日志丢失。

---

### AP-029: F4 hasAudio 包�的扩展名列表

**出现**: `F4_extract_audio.jsx:106-111`
**描述**: 音频检测的扩展名列表包含视频容器格式 (.mp4, .mov, .avi)。可能错误地将无声音的视频文件分类为"有音频"。

---

### AP-030: 硬编码日志文件名

**出现**: `AEStudioKit_Logger.jsx:88`
**描述**: 日志文件名硬编码为 `AEStudioKit_F9_test.log`，但被所有 F1-F8 模块共享。文件名暗示它是"F9 的测试日志"。

---

### AP-031: 内联样式 (15+ 处)

**出现**: `client/app.js:913, 918-931, 1105, 1117-1121`
**描述**: JS 中使用 `element.style.xxx = '...'` 设置样式，应使用 CSS 类控制。

---

### AP-032: CSInterface.js cep_node 非标准

**出现**: `client/CSInterface.js:25-38`
**描述**: polyfill 中引用了 `cep_node.EvalScript()`，这不是 Adobe 官方的 CEP API。可能只在特定构建或运行时环境中可用。

---

### AP-033: API_BASE 硬编码

**出现**: `client/api.js:19`
**描述**: 后端 URL `http://127.0.0.1:8765` 硬编码在 JS 中。如果端口冲突需修改，必须重新编译。

---

### AP-034: API 响应 JSON 解析错误静默转换

**出现**: `client/api.js:44-46, 96-98`
**描述**: 非 JSON 的 HTTP 响应被静默强制转换为 `{success: true}`，可能隐藏实际的服务器错误。

---

### AP-035: 动态 text_engine 加载无缓存

**出现**: `VocalSep_Consolidated.jsx:1391-1406`
**描述**: `text_engine.jsx` 每次首次使用时通过 `$.evalFile()` 动态加载 (~200ms 开销)，但未缓存编译结果或预加载。

---

### AP-036: F8 版本检测依赖中文字符串

**出现**: `F8_topaz_detect.jsx:100`
**描述**: `if (ver.indexOf('错误') < 0)` 检查 PowerShell 错误消息中的中文字符串。在不同语言系统上失效。

---

### AP-037: F1 脚本路径解析依赖 $.fileName

**出现**: `F1_layer_type.jsx:62`
**描述**: 使用 `new File($.fileName)` 定位同级文件。如果脚本通过 `$.evalFile()` 从另一个脚本加载，`$.fileName` 指向调用方的路径而非本文件路径。

---

## 反模式优先级修复路线图

### 第二阶段需立即修复 (随 F# 模块优化)

| 优先级 | 反模式 | 涉及模块 |
|--------|--------|----------|
| 1 | AP-001 同步 callSystem | F4, F5, F7 (Tab 2-6) |
| 2 | AP-003 空 catch 块 | 全部 F# + VocalSep |
| 3 | AP-010 缺少 CEP 返回值 | F3, F4 |
| 4 | AP-017 仅处理第一个图层 | F4 |

### 第三阶段需修复 (面板开发)

| 优先级 | 反模式 | 涉及区域 |
|--------|--------|----------|
| 1 | AP-004 buildUI 单体 | VocalSep_Consolidated |
| 2 | AP-005 4 层嵌套循环 | host/main.jsx |
| 3 | AP-006 硬编码路径 | 全部 |
| 4 | AP-007/008 安全配置 | server.py, manifest.xml |

### 第四/五阶段需修复 (规范化 + 测试)

| 优先级 | 反模式 | 涉及区域 |
|--------|--------|----------|
| 1 | AP-011~014 代码重复 | 全部 |
| 2 | AP-025~027 CEP 面板问题 | client/ |
| 3 | AP-022 下载无提示 | F5 |
