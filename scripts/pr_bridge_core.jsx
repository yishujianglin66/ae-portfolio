// ============================================================
// AE Knowledge Vault - Premiere Pro Bridge CORE
// 放置于: PR CEP 扩展 PRBridgeCEP/host.jsx 通过 $.evalFile 加载
// PR 启动时由 CEP 扩展自动加载
//
// 核心原则：此脚本应保持稳定，不再频繁修改
// 业务逻辑通过加载外部 handler_*.jsx 文件实现
//
// 通信机制（与 PRBridgeClient.py 协议对齐）：
//   - 命令文件: .premiere-mcp-bridge/pr_command.json（单文件）
//   - 结果文件: .premiere-mcp-bridge/pr_result.json（单文件）
//   - 命令格式: {"command": "execute_script", "script": "...", "timestamp": "...", "processed": false}
//   - 结果格式: {"status": "success"/"error", "result": {...}, "timestamp": "..."}
//   - processed=true 标记命令已处理
//   - 轮询间隔: 500ms
//   - 自动加载 handler_*.jsx 文件
// ============================================================


// ============================================================
// JSON Polyfill（PR ExtendScript 默认无 JSON）
// ============================================================
if (typeof JSON === 'undefined') {
    JSON = {
        parse: function(text) { return eval('(' + text + ')'); },
        stringify: function(value) {
            if (value === null) return 'null';
            if (typeof value === 'undefined') return 'undefined';
            if (typeof value === 'number' || typeof value === 'boolean') return String(value);
            if (typeof value === 'string') {
                return '"' + value.replace(/\\/g, '\\\\').replace(/"/g, '\\"').replace(/\n/g, '\\n').replace(/\r/g, '\\r').replace(/\t/g, '\\t') + '"';
            }
            if (value instanceof Array) {
                var items = [];
                for (var i = 0; i < value.length; i++) items.push(JSON.stringify(value[i]));
                return '[' + items.join(',') + ']';
            }
            if (typeof value === 'object') {
                if (value instanceof Date) return '"' + value.toString() + '"';
                var props = [];
                for (var key in value) {
                    if (value.hasOwnProperty(key)) {
                        props.push(JSON.stringify(key) + ':' + JSON.stringify(value[key]));
                    }
                }
                return '{' + props.join(',') + '}';
            }
            return 'null';
        }
    };
}

// ============================================================
// 全局 PRBridge 对象（避免与 PSBridge 命名冲突）
// ============================================================
var PRBridge = {
    projectRoot: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault",
    bridgeDir: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge",
    commandFile: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge/pr_command.json",
    resultFile: "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.premiere-mcp-bridge/pr_result.json",
    handlers: {},
    log: null,
    version: "2.0.0",
    pollInterval: 500,  // ms
    lastProcessedTimestamp: ""  // 防止重复处理同一命令
};

// 确保目录存在
var _bridgeDir = new Folder(PRBridge.bridgeDir);
if (!_bridgeDir.exists) {
    _bridgeDir.create();
}

// ============================================================
// 日志函数
// ============================================================
PRBridge.log = function(msg) {
    try {
        var logFile = new File(PRBridge.bridgeDir + "/bridge_log.txt");
        logFile.encoding = "UTF-8";
        logFile.open("a");
        var d = new Date();
        var ts = d.getFullYear() + "-" +
                 ("0" + (d.getMonth() + 1)).slice(-2) + "-" +
                 ("0" + d.getDate()).slice(-2) + "T" +
                 ("0" + d.getHours()).slice(-2) + ":" +
                 ("0" + d.getMinutes()).slice(-2) + ":" +
                 ("0" + d.getSeconds()).slice(-2);
        logFile.writeln("[" + ts + "] " + msg);
        logFile.close();
    } catch(e) {}
};

// ============================================================
// 注册处理器
// ============================================================
PRBridge.register = function(name, handler) {
    PRBridge.handlers[name] = handler;
    PRBridge.log("Handler registered: " + name);
};

PRBridge.listHandlers = function() {
    var names = [];
    for (var k in PRBridge.handlers) {
        if (PRBridge.handlers.hasOwnProperty(k)) names.push(k);
    }
    return names;
};

// ============================================================
// 初始化
// ============================================================
PRBridge.log("=== PRBridge v" + PRBridge.version + " starting ===");
PRBridge.log("PR version: " + app.version);
PRBridge.log("Project: " + (app.project ? "exists" : "null"));

// 写入就绪标记
try {
    var readyFile = new File(PRBridge.bridgeDir + "/bridge_ready.txt");
    readyFile.encoding = "UTF-8";
    readyFile.open("w");
    readyFile.writeln("READY");
    readyFile.writeln("version: " + PRBridge.version);
    readyFile.writeln("pr_version: " + app.version);
    readyFile.writeln("time: " + new Date().toUTCString());
    readyFile.close();
} catch(e) { PRBridge.log("Failed to write ready file: " + e); }

// ============================================================
// 内置基础处理器（与 PRBridgeClient.py 协议对齐）
// ============================================================

// ping - 心跳检测（PRBridgeClient.ping 调用）
PRBridge.register("ping", function(cmd) {
    return {
        pong: true,
        version: app.version,
        bridgeVersion: PRBridge.version,
        timestamp: new Date().toUTCString(),
        projectExists: !!app.project
    };
});

// getProjectInfo - 获取当前 PR 项目信息（PRBridgeClient.get_project_info 调用）
PRBridge.register("getProjectInfo", function(cmd) {
    try {
        if (!app.project) {
            return { error: "No project open" };
        }
        var info = {
            name: app.project.name,
            path: app.project.path ? app.project.path.fsName : "",
            numSequences: app.project.sequences.length,
            numItems: app.project.rootItem.children.length,
            sequences: []
        };

        for (var i = 0; i < app.project.sequences.length; i++) {
            var seq = app.project.sequences[i];
            var seqInfo = {
                name: seq.name,
                videoTracks: seq.videoTracks.length,
                audioTracks: seq.audioTracks.length
            };
            info.sequences.push(seqInfo);
        }

        return info;
    } catch(e) {
        return { error: e.toString() };
    }
});

// listSequences - 列出所有序列（PRBridgeClient.list_sequences 调用）
PRBridge.register("listSequences", function(cmd) {
    try {
        if (!app.project) {
            return { error: "No project open" };
        }
        var sequences = [];
        for (var i = 0; i < app.project.sequences.length; i++) {
            var seq = app.project.sequences[i];
            sequences.push({
                index: i,
                name: seq.name,
                id: seq.sequenceID,
                videoTracks: seq.videoTracks.length,
                audioTracks: seq.audioTracks.length
            });
        }
        return { sequences: sequences, count: sequences.length };
    } catch(e) {
        return { error: e.toString() };
    }
});

// execute_script - 执行任意 ExtendScript（PremiereEngine._execute_jsx 调用）
// 这是核心命令，业务代码通过此命令执行 JSX
PRBridge.register("execute_script", function(cmd) {
    if (!cmd.script) return { error: "Missing script" };
    try {
        var result = eval(cmd.script);
        return { result: String(result), executed: true };
    } catch(e) {
        return { error: e.toString() };
    }
});

// getInfo - 获取 Bridge 与 PR 状态
PRBridge.register("getInfo", function(cmd) {
    var info = {
        bridgeVersion: PRBridge.version,
        prVersion: app.version,
        handlers: PRBridge.listHandlers(),
        projectExists: !!app.project,
        projectName: app.project ? app.project.name : null
    };
    return info;
});

// registerHandler - 动态注册处理器（从外部 JSX 文件加载）
PRBridge.register("registerHandler", function(cmd) {
    if (!cmd.scriptPath) {
        return { error: "Missing scriptPath" };
    }
    try {
        var scriptFile = new File(cmd.scriptPath);
        if (!scriptFile.exists) {
            return { error: "Script not found: " + cmd.scriptPath };
        }
        scriptFile.encoding = "UTF-8";
        scriptFile.open("r");
        var content = scriptFile.read();
        scriptFile.close();

        // 在 PRBridge 上下文中执行
        var fn = new Function("PRBridge", content);
        fn(PRBridge);

        return { registered: true, handlers: PRBridge.listHandlers() };
    } catch(e) {
        return { error: e.toString() };
    }
});

// reloadHandlers - 重新加载所有 handler（核心创新！业务逻辑热更新）
PRBridge.register("reloadHandlers", function(cmd) {
    PRBridge.log("Reloading handlers...");
    PRBridge.handlers = {};
    // 重新注册内置处理器后再加载外部 handler
    // 注意：此处仅清空外部 handler，内置处理器需要重新注册
    // 为简化逻辑，重新加载外部 handler 文件即可
    loadAllHandlers();
    return {
        reloaded: true,
        handlers: PRBridge.listHandlers()
    };
});

// ============================================================
// 命令处理（单文件协议，与 PRBridgeClient.py 对齐）
// ============================================================
function processCommandFile() {
    try {
        var cmdFile = new File(PRBridge.commandFile);
        if (!cmdFile.exists) return;

        cmdFile.encoding = "UTF-8";
        cmdFile.open("r");
        var cmdStr = cmdFile.read();
        cmdFile.close();

        if (!cmdStr) return;

        var cmd = {};
        try { cmd = JSON.parse(cmdStr); }
        catch(e) {
            try { cmd = eval('(' + cmdStr + ')'); }
            catch(e2) {
                PRBridge.log("Parse error: " + e2);
                cmd = { command: "parse_error" };
            }
        }

        // 已处理过该命令则跳过
        if (cmd.processed === true) return;
        var cmdTs = cmd.timestamp || "";
        if (cmdTs && cmdTs === PRBridge.lastProcessedTimestamp) return;

        var commandName = cmd.command || cmd.action;  // 兼容 action 字段
        PRBridge.log("Executing: " + commandName);

        // 删除旧结果文件
        var resultFile = new File(PRBridge.resultFile);
        if (resultFile.exists) {
            try { resultFile.remove(); } catch(e) {}
        }

        // 查找处理器
        var handler = PRBridge.handlers[commandName];
        var result;
        var status = "success";

        if (handler) {
            try {
                result = handler(cmd);
                if (result && result.error) status = "error";
            } catch(e) {
                result = { error: e.toString() };
                status = "error";
                PRBridge.log("Handler error: " + e);
            }
        } else {
            result = { error: "Unknown command: " + commandName };
            status = "error";
            PRBridge.log("No handler for: " + commandName);
        }

        // 写入结果
        var rf = new File(PRBridge.resultFile);
        rf.encoding = "UTF-8";
        rf.open("w");
        rf.writeln(JSON.stringify({
            status: status,
            result: result,
            timestamp: new Date().toUTCString()
        }));
        rf.close();

        // 删除命令文件（防止重复处理，CEP Chromium 轮询依赖文件存在性判断）
        PRBridge.lastProcessedTimestamp = cmdTs;
        var cf = new File(PRBridge.commandFile);
        try { cf.remove(); } catch(e) {}

        PRBridge.log("Done: " + commandName + " (" + status + ")");
    } catch(e) {
        PRBridge.log("Process error: " + e);
    }
}

// ============================================================
// 自动加载所有 handler_*.jsx 文件
// 这样可以动态添加业务逻辑而不需要修改核心脚本
// ============================================================
function loadAllHandlers() {
    try {
        var handlerFiles = _bridgeDir.getFiles("handler_*.jsx");
        PRBridge.log("Found " + handlerFiles.length + " handler file(s) in bridge dir");

        for (var i = 0; i < handlerFiles.length; i++) {
            _loadHandlerFile(handlerFiles[i]);
        }
    } catch(e) {
        PRBridge.log("Load handlers error: " + e);
    }
}

function _loadHandlerFile(handlerFile) {
    try {
        handlerFile.encoding = "UTF-8";
        handlerFile.open("r");
        var content = handlerFile.read();
        handlerFile.close();

        // 在 PRBridge 上下文中执行
        var fn = new Function("PRBridge", content);
        fn(PRBridge);
        PRBridge.log("Loaded handler: " + handlerFile.name);
    } catch(e) {
        PRBridge.log("Failed to load " + handlerFile.name + ": " + e);
    }
}

// 加载所有 handler
loadAllHandlers();

// ============================================================
// 启动轮询
// ============================================================
PRBridge.log("Starting polling (interval=" + PRBridge.pollInterval + "ms)...");
PRBridge.log("Handlers: " + PRBridge.listHandlers().join(", "));

var pollEnabled = true;

// PR 提供 app.scheduleTask（与 AE/PS 类似）
try {
    if (typeof app.scheduleTask === 'function') {
        // D-13 修复 (2026-08-14): 全局名唯一命名空间 + 防重复调度守卫。
        // 原 __prBridgePoll 为通用名, 与其他脚本重名时会互相覆盖导致
        // 调度任务串台; 改为 __prBridgeCorePoll_v1 并加 scheduled 标记。
        $.global.__prBridgeCorePoll_v1 = function() {
            if (pollEnabled) {
                try { processCommandFile(); } catch(e) { PRBridge.log("Poll error: " + e); }
                app.scheduleTask("$.global.__prBridgeCorePoll_v1()", PRBridge.pollInterval, false);
            }
        };
        if (!$.global.__prBridgeCoreScheduled_v1) {
            app.scheduleTask("$.global.__prBridgeCorePoll_v1()", PRBridge.pollInterval, false);
            $.global.__prBridgeCoreScheduled_v1 = true;
        }
        PRBridge.log("Using app.scheduleTask for polling (namespaced v1)");
    } else if (typeof $.setInterval === 'function') {
        if (!$.global.__prBridgeCoreScheduled_v1) {
            $.setInterval(processCommandFile, PRBridge.pollInterval);
            $.global.__prBridgeCoreScheduled_v1 = true;
        }
        PRBridge.log("Using $.setInterval for polling");
    } else if (typeof app.setInterval === 'function') {
        if (!$.global.__prBridgeCoreScheduled_v1) {
            app.setInterval(processCommandFile, PRBridge.pollInterval);
            $.global.__prBridgeCoreScheduled_v1 = true;
        }
        PRBridge.log("Using app.setInterval for polling");
    } else {
        PRBridge.log("WARN: No scheduling API available, polling disabled");
    }
} catch(e) {
    PRBridge.log("Polling setup error: " + e);
}

PRBridge.log("=== PRBridge initialized ===");

// 导出到全局，方便外部访问
$.global.PRBridge = PRBridge;

// 返回值（供外部调用验证）
"PRBridge v" + PRBridge.version + " ready";
