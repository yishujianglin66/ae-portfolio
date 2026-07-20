# 第四阶段：JS JSX Snippets 代码片段高效运用

> **插件**: adpyke.js-jsx-snippets
> **核心**: ExtendScript/JSX 专用代码片段库 + 自定义项目片段
> **目标**: 将常用 ExtendScript 模式从 30 秒手动编写降至 2 秒片段触发

---

## 4.1 内置代码片段速查

### 插件提供的 ExtendScript 常用片段

| 触发前缀 | 展开内容 | 用途 |
|----------|----------|------|
| `ae-comp` | 创建合成 | 新建 CompItem |
| `ae-layer` | 添加图层 | 创建 AVLayer/TextLayer/ShapeLayer |
| `ae-text` | 文字图层 | 创建 TextLayer + 设置文字属性 |
| `ae-effect` | 添加效果 | 给图层添加 AE 内置效果 |
| `ae-keyframe` | 设置关键帧 | 属性关键帧操作 |
| `ae-property` | 访问属性 | 按 MatchName 获取属性 |
| `ae-import` | 导入素材 | ImportOptions + app.project.importFile() |
| `ae-render` | 渲染队列 | 添加到渲染队列 |
| `ae-loop-layers` | 遍历图层 | for 循环遍历 comp.layers |
| `ae-loop-items` | 遍历项目 | for 循环遍历 app.project.items |
| `ae-loop-selected` | 遍历选中 | for 循环遍历 comp.selectedLayers |
| `ae-file-read` | 读取文件 | File 对象 open/read/close |
| `ae-file-write` | 写入文件 | File 对象 open/write/close |
| `ae-folder` | 目录操作 | Folder 对象 exists/create/getFiles |
| `ae-alert` | 弹窗 | alert() / confirm() / prompt() |
| `ae-dispatcher` | cepDispatch 模板 | cepDispatch 路由框架 |
| `ae-trycatch` | 异常处理 | try/catch/finally 模板 |

## 4.2 项目专属自定义代码片段

### 文件位置

```
.vscode/ae-extendscript.code-snippets
```

### 完整片段定义

```json
{
    // ═══════════════════════════════════════════════════════
    // 1. 标准图层遍历模板 (ae-layer-loop)
    //    含类型判断 + try/catch + 日志输出
    // ═══════════════════════════════════════════════════════
    "AE Layer Loop with Type Guard": {
        "prefix": "ae-layer-loop",
        "scope": "javascript",
        "body": [
            "/**",
            " * 遍历 ${1:comp} 图层 — ${2:操作描述}",
            " * @param {CompItem} comp — 目标合成",
            " */",
            "function ${3:processLayers}(comp) {",
            "    if (!comp || !(comp instanceof CompItem)) {",
            "        _logPanel('[${3}] 错误: 无效合成');",
            "        return { success: false, error: '无效合成' };",
            "    }",
            "",
            "    var i, layer, result;",
            "    var processed = 0;",
            "    var errors = [];",
            "",
            "    for (i = 1; i <= comp.numLayers; i++) {",
            "        try {",
            "            layer = comp.layer(i);",
            "",
            "            // 类型判断",
            "            if (layer instanceof TextLayer) {",
            "                // 文字图层处理",
            "                $4",
            "                processed++;",
            "            } else if (layer instanceof AVLayer) {",
            "                // 音视频图层处理",
            "                $5",
            "                processed++;",
            "            }",
            "            // 跳过其他类型",
            "",
            "        } catch (e) {",
            "            errors.push('图层 ' + i + ': ' + e.toString());",
            "            _logPanel('[${3}] 图层 ' + i + ' 处理异常: ' + e, 'warn');",
            "        }",
            "    }",
            "",
            "    _logPanel('[${3}] 完成: ' + processed + '/' + comp.numLayers + ' 图层');",
            "    return {",
            "        success: errors.length === 0,",
            "        processed: processed,",
            "        total: comp.numLayers,",
            "        errors: errors",
            "    };",
            "}"
        ],
        "description": "遍历合成图层模板，含 TextLayer/AVLayer 类型判断、异常处理、日志输出"
    },

    // ═══════════════════════════════════════════════════════
    // 2. 异步任务调度模板 (ae-schedule-task)
    //    scheduleTask 异步执行分片
    // ═══════════════════════════════════════════════════════
    "AE Async ScheduleTask Template": {
        "prefix": "ae-schedule-task",
        "scope": "javascript",
        "body": [
            "/**",
            " * 异步分片执行 ${1:任务描述}",
            " * @param {Array} items — 待处理项",
            " * @param {Function} onItem — 单项处理函数",
            " * @param {Function} onComplete — 完成回调",
            " * @param {Number} chunkSize — 每片数量 (默认 5)",
            " */",
            "function ${2:processAsync}(items, onItem, onComplete, chunkSize) {",
            "    if (!items || items.length === 0) {",
            "        if (onComplete) onComplete({ success: true, count: 0 });",
            "        return;",
            "    }",
            "",
            "    chunkSize = chunkSize || 5;",
            "    var index = 0;",
            "    var results = [];",
            "",
            "    function processChunk() {",
            "        var end = Math.min(index + chunkSize, items.length);",
            "        var i;",
            "",
            "        for (i = index; i < end; i++) {",
            "            try {",
            "                var r = onItem(items[i], i);",
            "                results.push({ index: i, success: true, result: r });",
            "            } catch (e) {",
            "                results.push({ index: i, success: false, error: e.toString() });",
            "            }",
            "        }",
            "",
            "        index = end;",
            "",
            "        if (index >= items.length) {",
            "            // 全部完成",
            "            if (onComplete) onComplete({",
            "                success: true,",
            "                count: items.length,",
            "                results: results",
            "            });",
            "        } else {",
            "            // 继续下一片 (让 AE UI 有机会刷新)",
            "            app.scheduleTask(",
            "                'processChunk()',",
            "                50,",  // 50ms 延迟
            "                false",
            "            );",
            "        }",
            "    }",
            "",
            "    // 启动第一片",
            "    app.scheduleTask('processChunk()', 10, false);",
            "}"
        ],
        "description": "scheduleTask 异步分片执行模板 — 防止 AE UI 阻塞"
    },

    // ═══════════════════════════════════════════════════════
    // 3. CSInterface evalScript 桥接调用模板 (ae-cs-eval)
    //    CEP 面板侧 evalScript 完整封装
    // ═══════════════════════════════════════════════════════
    "AE CSInterface evalScript Bridge": {
        "prefix": "ae-cs-eval",
        "scope": "javascript",
        "body": [
            "/**",
            " * CEP 面板调用 ExtendScript",
            " * @param {String} action — cepDispatch 操作名",
            " * @param {Object} params — 参数对象",
            " * @returns {Promise<Object>} 解析后的结果",
            " */",
            "function aeCall(action, params) {",
            "    return new Promise(function (resolve, reject) {",
            "        var cs = new CSInterface();",
            "        var script = 'cepDispatch(\"' + action + '\", ' +",
            "            JSON.stringify(params || {}) + ')';",
            "",
            "        cs.evalScript(script, function (result) {",
            "            try {",
            "                if (!result) {",
            "                    resolve({ ",
            "                        success: false, ",
            "                        error: 'null result from evalScript',",
            "                        code: 'E_CS_NULL'",
            "                    });",
            "                    return;",
            "                }",
            "                var parsed = JSON.parse(result);",
            "                resolve(parsed);",
            "            } catch (e) {",
            "                resolve({",
            "                    success: false,",
            "                    error: 'Parse error: ' + e.toString(),",
            "                    raw: result ? result.substring(0, 200) : 'null',",
            "                    code: 'E_CS_PARSE'",
            "                });",
            "            }",
            "        });",
            "    });",
            "}"
        ],
        "description": "CSInterface.evalScript 标准调用封装 — 含 JSON 解析和错误处理"
    },

    // ═══════════════════════════════════════════════════════
    // 4. 日志写入标准模板 (ae-log-storage)
    //    将日志写入 _storage 文件夹
    // ═══════════════════════════════════════════════════════
    "AE Log to _storage": {
        "prefix": "ae-log-storage",
        "scope": "javascript",
        "body": [
            "/**",
            " * 日志写入 _storage 文件夹",
            " * 用途: 诊断 ExtendScript 初始化错误 (CEP 面板中 $.writeln 不可见)",
            " */",
            "var ${1:LOG_NAME} = (function() {",
            "    var _logFile;",
            "    var _logPath;",
            "",
            "    function getLogPath() {",
            "        if (_logPath) return _logPath;",
            "        try {",
            "            _logPath = Folder.desktop.fsName + '/${2:debug_filename}.log';",
            "        } catch (e) {",
            "            try {",
            "                _logPath = Folder.temp.fsName + '/${2:debug_filename}.log';",
            "            } catch (e2) {",
            "                _logPath = '~/desktop/${2:debug_filename}.log';",
            "            }",
            "        }",
            "        return _logPath;",
            "    }",
            "",
            "    function write(level, msg) {",
            "        try {",
            "            _logFile = new File(getLogPath());",
            "            _logFile.open('a');",
            "            var ts = new Date().toString();",
            "            _logFile.write('[' + ts + '] [' + level + '] ' + msg + '\\n');",
            "            _logFile.close();",
            "        } catch (e) {}",
            "    }",
            "",
            "    return {",
            "        debug: function(m) { write('DEBUG', m); },",
            "        info:  function(m) { write('INFO', m); },",
            "        warn:  function(m) { write('WARN', m); },",
            "        error: function(m) { write('ERROR', m); }",
            "    };",
            "})();",
            "",
            "// 使用示例:",
            "// ${1:LOG_NAME}.info('初始化完成');",
            "// ${1:LOG_NAME}.error('失败: ' + e.toString());"
        ],
        "description": "文件日志记录器 — 写入桌面 _storage 诊断日志"
    },

    // ═══════════════════════════════════════════════════════
    // 5. F 模块 CEP Dispatch 接口模板 (ae-fmodule-dispatch)
    //    为 F 模块添加标准 dispatch 导出
    // ═══════════════════════════════════════════════════════
    "AE F-Module Dispatch Export": {
        "prefix": "ae-fmodule-dispatch",
        "scope": "javascript",
        "body": [
            "/**",
            " * ${1:F1} — ${2:模块名称} CEP Dispatch 接口",
            " * ",
            " * 导出到 $.global.${1}_dispatch",
            " * 由 studio-kit-bridge.jsx 统一调度",
            " * ",
            " * @param {String} action — 操作: ${3:listOfActions}",
            " * @param {Object} params — 参数",
            " * @returns {Object} { success: Boolean, data/error: Any }",
            " */",
            "$.global.${1}_dispatch = function(action, params) {",
            "    try {",
            "        if (!params) params = {};",
            "",
            "        switch (String(action)) {",
            "            case '${4:defaultAction}':",
            "                return {",
            "                    success: true,",
            "                    data: ${5:resultData},",
            "                    timestamp: new Date().toString()",
            "                };",
            "",
            "            case 'status':",
            "                return {",
            "                    success: true,",
            "                    data: {",
            "                        module: '${1}',",
            "                        loaded: true,",
            "                        version: '1.0.0'",
            "                    }",
            "                };",
            "",
            "            default:",
            "                return {",
            "                    success: false,",
            "                    error: '${1}: 未知操作 \"' + String(action) + '\"',",
            "                    code: 'E_INVALID_ACTION'",
            "                };",
            "        }",
            "    } catch (e) {",
            "        return {",
            "            success: false,",
            "            error: '${1}: ' + e.toString(),",
            "            code: 'E_EXCEPTION'",
            "        };",
            "    }",
            "};",
            "",
            "// 模块自动跳过标志 (由 Bridge 设置)",
            "if (!$.global._STUDIO_KIT_SKIP_RUN) {",
            "    // 直接调用时的默认行为",
            "    // ${1}_dispatch('default', {});",
            "}"
        ],
        "description": "F 模块 CEP Dispatch 标准接口 — 含 action 路由和错误处理"
    },

    // ═══════════════════════════════════════════════════════
    // 6. AE 属性安全访问模板 (ae-property-safe)
    //    ExtendScript 属性访问 + 多层容错
    // ═══════════════════════════════════════════════════════
    "AE Safe Property Access": {
        "prefix": "ae-property-safe",
        "scope": "javascript",
        "body": [
            "/**",
            " * 安全获取 AE 图层属性",
            " * 支持多层回退检测",
            " */",
            "function ${1:getSafeProperty}(layer) {",
            "    var result = {",
            "        value: null,",
            "        found: false,",
            "        method: ''",
            "    };",
            "",
            "    // 方法 1: 直接 instanceof 检查",
            "    try {",
            "        if (layer instanceof ${2:TextLayer}) {",
            "            result.value = layer.sourceText.value;",
            "            result.found = true;",
            "            result.method = 'instanceof';",
            "            return result;",
            "        }",
            "    } catch (e1) {}",
            "",
            "    // 方法 2: MatchName 查找",
            "    try {",
            "        var prop = layer.property('${3:ADBE Text Properties}');",
            "        if (prop) {",
            "            result.value = prop;",
            "            result.found = true;",
            "            result.method = 'matchName';",
            "            return result;",
            "        }",
            "    } catch (e2) {}",
            "",
            "    // 方法 3: 遍历子属性",
            "    try {",
            "        var j;",
            "        for (j = 1; j <= layer.numProperties; j++) {",
            "            var p = layer.property(j);",
            "            if (p && p.matchName === '${3:ADBE Text Properties}') {",
            "                result.value = p;",
            "                result.found = true;",
            "                result.method = 'iterate';",
            "                return result;",
            "            }",
            "        }",
            "    } catch (e3) {}",
            "",
            "    return result;",
            "}"
        ],
        "description": "AE 属性安全访问 — instanceof → MatchName → 遍历，三层回退检测"
    },

    // ═══════════════════════════════════════════════════════
    // 7. cepDispatch 路由器模板 (ae-dispatch-router)
    //    标准 cepDispatch switch-case 骨架
    // ═══════════════════════════════════════════════════════
    "AE Dispatch Router Template": {
        "prefix": "ae-dispatch-router",
        "scope": "javascript",
        "body": [
            "/**",
            " * cepDispatch — 统一路由入口",
            " * 由 CEP 面板通过 cs.evalScript 调用",
            " * ",
            " * @param {String} action — 操作名称",
            " * @param {String} paramsJson — JSON 参数字符串",
            " * @returns {String} JSON 结果",
            " */",
            "function cepDispatch(action, paramsJson) {",
            "    try {",
            "        // 解析参数",
            "        var params = {};",
            "        if (paramsJson && typeof paramsJson === 'string' && paramsJson !== '') {",
            "            try {",
            "                params = JSON.parse(paramsJson);",
            "            } catch (e) {",
            "                return JSON.stringify({",
            "                    success: false,",
            "                    error: '参数解析失败: ' + e.toString(),",
            "                    code: 'E_JSON_PARSE'",
            "                });",
            "            }",
            "        }",
            "",
            "        // 路由分发",
            "        var result;",
            "        switch (String(action)) {",
            "            case '${1:action1}':",
            "                result = ${2:handler1}(params);",
            "                break;",
            "",
            "            case '${3:action2}':",
            "                result = ${4:handler2}(params);",
            "                break;",
            "",
            "            case 'status':",
            "                result = {",
            "                    loaded: true,",
            "                    version: '${5:1.0.0}',",
            "                    timestamp: new Date().toString()",
            "                };",
            "                break;",
            "",
            "            default:",
            "                return JSON.stringify({",
            "                    success: false,",
            "                    error: '未知操作: ' + String(action),",
            "                    code: 'E_UNKNOWN_ACTION'",
            "                });",
            "        }",
            "",
            "        return JSON.stringify({",
            "            success: true,",
            "            data: result",
            "        });",
            "",
            "    } catch (e) {",
            "        _logPanel('[DISPATCH] Error: ' + e.toString());",
            "        return JSON.stringify({",
            "            success: false,",
            "            error: String(e).substring(0, 300),",
            "            code: 'E_DISPATCH'",
            "        });",
            "    }",
            "}"
        ],
        "description": "cepDispatch 标准路由模板 — 含参数解析、路由分发、异常处理"
    },

    // ═══════════════════════════════════════════════════════
    // 8. Utils 命名空间初始化 (ae-utils-init)
    //    标准 Utils 对象创建模板
    // ═══════════════════════════════════════════════════════
    "AE Utils Namespace Init": {
        "prefix": "ae-utils-init",
        "scope": "javascript",
        "body": [
            "// 初始化 Utils 命名空间",
            "if (typeof ${1:AEStudioKit} === 'undefined') {",
            "    var ${1:AEStudioKit} = {};",
            "}",
            "if (typeof ${1:AEStudioKit}.Utils === 'undefined') {",
            "    ${1:AEStudioKit}.Utils = {};",
            "}",
            "",
            "// 日志方法 (安全 — 确保即使未初始化也不崩溃)",
            "${1:AEStudioKit}.Utils.log = function(msg, level) {",
            "    try {",
            "        $.writeln('[' + (level || 'INFO') + '] ' + msg);",
            "        // 同时写入桌面诊断日志",
            "        var logFile = new File(Folder.desktop.fsName + '/ae_debug.log');",
            "        logFile.open('a');",
            "        logFile.write(new Date().toString() + ' [' + (level || 'INFO') + '] ' + msg + '\\n');",
            "        logFile.close();",
            "    } catch (e) {}",
            "};"
        ],
        "description": "安全初始化 Utils 命名空间 — 先创建对象再赋值方法 (防止 undefined is not an object)"
    }
}
```

## 4.3 命名前缀规范

| 前缀 | 用途 | 示例 |
|------|------|------|
| `ae-` | Adobe ExtendScript 通用模式 | `ae-layer-loop`, `ae-comp` |
| `ae-cs-` | CEP/CSInterface 桥接相关 | `ae-cs-eval`, `ae-cs-event` |
| `ae-fmodule-` | F 模块结构模板 | `ae-fmodule-dispatch` |
| `ae-dispatch-` | cepDispatch 路由相关 | `ae-dispatch-router` |
| `ae-log-` | 日志和诊断相关 | `ae-log-storage` |
| `ae-property-` | AE 对象模型属性访问 | `ae-property-safe` |
| `ae-schedule-` | 异步调度相关 | `ae-schedule-task` |
| `ae-utils-` | 工具类和命名空间 | `ae-utils-init` |

## 4.4 效率对比：片段 vs 手动编写

### 案例：创建一个完整的 F 模块 (含 dispatch 接口 + 错误处理 + 日志)

| 维度 | 手动编写 | 使用片段 | 节省 |
|------|----------|----------|------|
| **时间** | ~4 分钟 | ~30 秒 | **87.5%** |
| **按键数** | ~800 次 | ~30 次 | **96%** |
| **错误率** | 高 (易缺 try/catch) | 低 (模板已含) | — |
| **一致性** | 因人而异 | 统一格式 | — |

### 操作步骤 (使用片段)

```
1. 新建 .jsx 文件
2. 输入 ae-fmodule-dispatch → Tab → 填入模块名 → Tab → Tab...
3. 输入 ae-schedule-task → Tab (异步执行)
4. 输入 ae-log-storage → Tab (日志)
5. Ctrl+S → 完成
```

**总耗时**: ≤30 秒
**手动编写同类代码**: ≥4 分钟

---

> **下一阶段**: [PHASE5_LINGMA_AI_RULES.md](./PHASE5_LINGMA_AI_RULES.md)
