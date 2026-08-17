/**
 * pr_startup_bridge.jsx — PR 启动时自动加载的桥接监听器 (v3.0)
 *
 * 安装位置：
 *   D:\Pr25\Adobe Premiere Pro 2025\Scripts\Startup\90_pr_mcp_bridge.jsx
 *
 * 通信协议：
 *   Python 写入 .premiere-mcp-bridge/pr_command.json
 *   本脚本通过 while(true) + $.sleep() 轮询 + onProjectChanged 事件驱动
 *   结果写入 .premiere-mcp-bridge/pr_result.json
 *
 * 注意：PR 2025 ExtendScript 不支持 $.setTimeout、app.scheduleTask 等定时器 API，
 * 因此使用 while(true) + $.sleep() 阻塞式轮询。$.sleep() 会释放控制权给应用事件循环，
 * 不会完全阻塞 UI。
 */

// ============================================================
// 配置（使用绝对路径）
// ============================================================

var BRIDGE_PATH = "C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\.premiere-mcp-bridge";
var CMD_FILE = BRIDGE_PATH + "\\pr_command.json";
var RES_FILE = BRIDGE_PATH + "\\pr_result.json";
var LOG_FILE = BRIDGE_PATH + "\\startup_bridge_log.txt";
var POLL_INTERVAL_MS = 500; // 轮询间隔（毫秒）
var LAST_CONTENT = "";
var BRIDGE_VERSION = "3.0";

// ============================================================
// 日志（兼容 ES3：不依赖 toISOString）
// ============================================================

function nowStr() {
    var d = new Date();
    function pad(n) { return n < 10 ? "0" + n : String(n); }
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate())
        + "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
}

function bridgeLog(msg) {
    try {
        var f = new File(LOG_FILE);
        f.encoding = "UTF-8";
        f.open("a");
        f.writeln(nowStr() + " " + msg);
        f.close();
    } catch (e) {}
}

// ============================================================
// 结果写入
// ============================================================

function bridgeWriteResult(status, result, message) {
    try {
        var res = {
            status: status,
            result: result,
            message: message,
            version: "startup-" + BRIDGE_VERSION,
            timestamp: nowStr()
        };
        // 手动构建 JSON（兼容 ES3，不依赖 JSON.stringify 的 polyfill）
        var json = "{";
        json += '"status":"' + String(status) + '",';
        json += '"result":' + (result === null || result === undefined ? "null" : result) + ',';
        json += '"message":' + (message === null || message === undefined ? "null" : '"' + String(message).replace(/"/g, '\\"') + '"') + ',';
        json += '"version":"startup-' + BRIDGE_VERSION + '",';
        json += '"timestamp":"' + nowStr() + '"';
        json += "}";
        var f = new File(RES_FILE);
        f.encoding = "UTF-8";
        f.open("w");
        f.write(json);
        f.close();
    } catch (e) {
        bridgeLog("WriteResult error: " + e.toString());
    }
}

// ============================================================
// JSON 解析（兼容 ES3，手动实现）
// ============================================================

function simpleJSONParse(str) {
    // 仅支持本协议所需的简单 JSON 解析
    // 格式: {"command":"xxx","script":"xxx","params":{...}}
    try {
        var result = {};
        var s = str.replace(/[\r\n\t]/g, " ").trim();
        if (s.charAt(0) !== "{" || s.charAt(s.length - 1) !== "}") return null;
        s = s.substring(1, s.length - 1).trim();

        // 提取 command
        var cmdMatch = s.match(/"command"\s*:\s*"([^"]*)"/);
        if (cmdMatch) result.command = cmdMatch[1];

        // 提取 script
        var scriptMatch = s.match(/"script"\s*:\s*"((?:[^"\\]|\\.)*)"/);
        if (scriptMatch) result.script = scriptMatch[1];

        // 提取 params
        var paramsMatch = s.match(/"params"\s*:\s*(\{[^}]*\})/);
        if (paramsMatch) {
            try { result.params = eval("(" + paramsMatch[1] + ")"); } catch (e) { result.params = {}; }
        }

        return result;
    } catch (e) {
        return null;
    }
}

// ============================================================
// 命令执行
// ============================================================

function bridgeExecuteCommand(cmdData) {
    var command = cmdData.command || "";
    var script = cmdData.script || "";

    try {
        if (command === "ping") {
            bridgeWriteResult("success",
                '{"pong":true,"version":"startup-' + BRIDGE_VERSION + '",'
                + '"appName":"' + String(app.appName).replace(/"/g, '\\"') + '",'
                + '"appVersion":"' + String(app.version).replace(/"/g, '\\"') + '",'
                + '"project":"' + (app.project ? String(app.project.name).replace(/"/g, '\\"') : "") + '"}'
            );
            return;
        }

        if (command === "executeScript" || command === "eval") {
            if (!script) {
                bridgeWriteResult("error", null, "No script provided");
                return;
            }
            var helpers = ""
                + "var TICKS_PER_SECOND = 254016000000;\n"
                + "function __ticksToSeconds(t) { return t / TICKS_PER_SECOND; }\n"
                + "function __secondsToTicks(s) { return Math.round(s * TICKS_PER_SECOND); }\n"
                + "function __result(d) { return JSON.stringify({success: true, data: d}); }\n"
                + "function __error(m) { return JSON.stringify({success: false, error: String(m)}); }\n";
            var result = eval(helpers + "\n" + script);
            if (typeof result === "object" || (typeof result === "object" && result !== null)) {
                bridgeWriteResult("success", JSON.stringify(result));
            } else if (result === undefined || result === null) {
                bridgeWriteResult("success", null);
            } else {
                bridgeWriteResult("success", String(result));
            }
            return;
        }

        if (command === "status") {
            bridgeWriteResult("success",
                '{"status":"running","version":"startup-' + BRIDGE_VERSION + '","baseDir":"' + BRIDGE_PATH.replace(/\\/g, "\\\\") + '"}'
            );
            return;
        }

        bridgeWriteResult("error", null, "Unknown command: " + command);
    } catch (e) {
        bridgeWriteResult("error", null, "Execute error: " + e.toString());
    }
}

// ============================================================
// 核心检查函数
// ============================================================

function bridgeCheckCommand() {
    try {
        var cmdFile = new File(CMD_FILE);
        if (cmdFile.exists) {
            cmdFile.encoding = "UTF-8";
            cmdFile.open("r");
            var content = cmdFile.read();
            cmdFile.close();

            if (content && content.length > 2 && content !== LAST_CONTENT) {
                LAST_CONTENT = content;
                try {
                    var cmdData = simpleJSONParse(content);
                    if (cmdData && cmdData.command) {
                        bridgeExecuteCommand(cmdData);
                        // 处理完成后删除命令文件
                        try { cmdFile.remove(); } catch (e) {}
                    } else {
                        // 尝试原生 JSON.parse
                        try {
                            var cmdData2 = JSON.parse(content);
                            if (cmdData2 && cmdData2.command) {
                                bridgeExecuteCommand(cmdData2);
                                try { cmdFile.remove(); } catch (e) {}
                            }
                        } catch (e2) {
                            bridgeWriteResult("error", null, "JSON parse error: " + e2.toString());
                        }
                    }
                } catch (parseError) {
                    bridgeWriteResult("error", null, "JSON parse error: " + parseError.toString());
                }
            }
        }
    } catch (e) {
        bridgeLog("Check error: " + e.toString());
    }
}

// ============================================================
// 事件驱动（辅助）
// ============================================================

function bridgeOnProjectChanged() {
    bridgeCheckCommand();
}

// ============================================================
// 启动
// ============================================================

bridgeLog("=== Bridge v" + BRIDGE_VERSION + " loaded ===");
bridgeLog("Bridge path: " + BRIDGE_PATH);

// 第1步：注册项目变更事件
try {
    app.addEventListener("onProjectChanged", bridgeOnProjectChanged);
    bridgeLog("onProjectChanged listener registered");
} catch (e) {
    bridgeLog("onProjectChanged error: " + e.toString());
}
try {
    app.addEventListener("onSequenceChanged", bridgeOnProjectChanged);
    bridgeLog("onSequenceChanged listener registered");
} catch (e) {
    bridgeLog("onSequenceChanged error: " + e.toString());
}

// 第2步：立即检查一次
bridgeCheckCommand();

// 第3步：主轮询循环（因为 PR 不支持任何定时器 API）
// while(true) + $.sleep() 会释放控制权给应用事件循环，不会完全阻塞 UI
bridgeLog("Starting poll loop (interval: " + POLL_INTERVAL_MS + "ms)");
var pollCount = 0;
while (true) {
    try {
        $.sleep(POLL_INTERVAL_MS);
        bridgeCheckCommand();
        pollCount++;
        if (pollCount % 200 === 0) {
            bridgeLog("poll iteration " + pollCount + " (alive)");
        }
    } catch (e) {
        bridgeLog("Poll error: " + e.toString());
        // 出错后继续轮询
        try { $.sleep(2000); } catch (e2) {}
    }
}

// 不应到达这里
bridgeLog("WARNING: Bridge poll loop exited unexpectedly");