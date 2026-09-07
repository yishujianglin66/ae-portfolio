/*
 * pr_mcp_bridge.jsx
 * =================
 * Premiere Pro MCP Bridge
 *
 * 通过文件轮询机制实现 Python → Premiere Pro 全自动控制。
 * 原理与 ae_mcp_bridge_v26.jsx 一致：
 *   1. Python 端写入命令到 pr_command.json
 *   2. 本脚本在 Premiere 内定时轮询命令文件
 *   3. 读取命令 → 执行 ExtendScript → 写入结果到 pr_result.json
 *   4. Python 端轮询读取结果
 *
 * 安装方式：
 *   1. 将此脚本复制到 Premiere Pro 的 Scripts 目录，或
 *   2. 在 Premiere Pro 中: File > Scripts > Run Script File... 选择此文件
 *
 * 使用方式：
 *   1. 打开 Premiere Pro 2025
 *   2. 运行此脚本，出现 MCP Bridge 面板
 *   3. 点击"启动监听"按钮
 *   4. 面板会每秒检查命令文件并自动执行
 *
 * 兼容性：Premiere Pro 2022+（需要 app.setInterval 支持）
 */

// ==================== 配置 ====================

var PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
var BASE_DIR = PROJ_ROOT + "/.pr-mcp-bridge";
var CMD_FILE = BASE_DIR + "/pr_command.json";
var RES_FILE = BASE_DIR + "/pr_result.json";
var LOG_FILE = BASE_DIR + "/pr_listener_log.txt";
var SECRET_FILE = PROJ_ROOT + "/.pr_mcp_secret";

// 签名验证（默认关闭，与 AE Bridge 保持一致）
var SIGNATURE_ENABLED = false;

// 轮询间隔（毫秒）
var POLL_INTERVAL = 1000;

// ==================== 全局状态 ====================

var isRunning = false;
var timerId = null;
var cmdCount = 0;
var lastCmdTime = 0;
var MCP_SECRET = "";

// ==================== 工具函数 ====================

/**
 * ISO 时间戳（ExtendScript 不支持 Date.prototype.toISOString）
 */
function isoTimestamp() {
    var d = new Date();
    function pad(n) { return (n < 10 ? "0" : "") + n; }
    return d.getFullYear() + "-" + pad(d.getMonth() + 1) + "-" + pad(d.getDate()) +
           "T" + pad(d.getHours()) + ":" + pad(d.getMinutes()) + ":" + pad(d.getSeconds());
}

/**
 * 写入日志
 */
function log(msg) {
    try {
        var f = new File(LOG_FILE);
        f.encoding = "UTF-8";
        if (f.open("a")) {
            f.writeln("[" + isoTimestamp() + "] " + msg);
            f.close();
        }
    } catch (e) { /* 忽略日志写入错误 */ }
}

/**
 * 读取 JSON 文件
 */
function readJSON(filePath) {
    var f = new File(filePath);
    if (!f.exists) return null;
    f.encoding = "UTF-8";
    if (!f.open("r")) return null;
    var content = f.read();
    f.close();
    if (!content || content.length === 0) return null;
    try {
        return eval("(" + content + ")");
    } catch (e) {
        log("JSON parse error: " + e.toString() + " | content: " + content.substring(0, 200));
        return null;
    }
}

/**
 * 写入 JSON 文件
 */
function writeJSON(filePath, obj) {
    var f = new File(filePath);
    f.encoding = "UTF-8";
    if (!f.open("w")) {
        log("Cannot write to: " + filePath);
        return false;
    }
    // 手动序列化（ExtendScript 无 JSON.stringify）
    var json = serializeJSON(obj);
    f.write(json);
    f.close();
    return true;
}

/**
 * 手动 JSON 序列化（ExtendScript ES3 兼容）
 */
function serializeJSON(obj) {
    if (obj === null || obj === undefined) return "null";
    if (typeof obj === "boolean") return obj ? "true" : "false";
    if (typeof obj === "number") return String(obj);
    if (typeof obj === "string") {
        var escaped = obj.replace(/\\/g, "\\\\")
                         .replace(/"/g, "\\\"")
                         .replace(/\n/g, "\\n")
                         .replace(/\r/g, "\\r")
                         .replace(/\t/g, "\\t");
        return "\"" + escaped + "\"";
    }
    if (obj instanceof Array) {
        var items = [];
        for (var i = 0; i < obj.length; i++) {
            items.push(serializeJSON(obj[i]));
        }
        return "[" + items.join(",") + "]";
    }
    if (typeof obj === "object") {
        var pairs = [];
        for (var key in obj) {
            if (obj.hasOwnProperty(key)) {
                pairs.push("\"" + key + "\":" + serializeJSON(obj[key]));
            }
        }
        return "{" + pairs.join(",") + "}";
    }
    return "null";
}

/**
 * 读取密钥文件
 */
function loadSecret() {
    var f = new File(SECRET_FILE);
    if (!f.exists) return "";
    f.encoding = "UTF-8";
    if (!f.open("r")) return "";
    var secret = f.read().trim();
    f.close();
    return secret;
}

/**
 * HMAC-SHA256 签名验证（简化版，需要 ExtendScript 加密支持）
 */
function verifySignature(data) {
    if (!SIGNATURE_ENABLED) return true;
    if (!MCP_SECRET || MCP_SECRET.length === 0) return true;
    // 签名验证逻辑与 AE Bridge 一致
    // 此处简化处理，生产环境应实现完整 HMAC-SHA256
    log("签名验证: 密钥已加载，但 ExtendScript HMAC 实现不完整，跳过验证");
    return true;
}

// ==================== 确保目录存在 ====================

function ensureDir(dirPath) {
    var d = new Folder(dirPath);
    if (!d.exists) {
        d.create();
    }
}

// ==================== 命令处理 ====================

/**
 * 处理命令文件
 */
function processCommand() {
    var data = readJSON(CMD_FILE);
    if (!data) return false;
    if (data.processed) return false;

    // 标记为已处理（防止重复执行）
    data.processed = true;
    writeJSON(CMD_FILE, data);

    // 签名验证
    if (!verifySignature(data)) {
        writeJSON(RES_FILE, {
            status: "error",
            message: "Signature verification failed",
            timestamp: isoTimestamp()
        });
        log("签名验证失败");
        return false;
    }

    var command = data.command || "";
    var script = data.script || "";
    var result = {};

    try {
        switch (command) {
            case "ping":
                result = {
                    status: "success",
                    result: {
                        pong: true,
                        appName: app.appName,
                        appVersion: app.version,
                        project: app.project ? app.project.name : "(none)",
                        timestamp: isoTimestamp()
                    },
                    timestamp: isoTimestamp()
                };
                log("Ping received");
                break;

            case "getProjectInfo":
                result = {
                    status: "success",
                    result: getProjectInfo(),
                    timestamp: isoTimestamp()
                };
                break;

            case "listSequences":
                result = {
                    status: "success",
                    result: listSequences(),
                    timestamp: isoTimestamp()
                };
                break;

            case "execute_script":
            case "executeAtomScript":
                if (!script || script.length === 0) {
                    result = {
                        status: "error",
                        message: "No script provided",
                        timestamp: isoTimestamp()
                    };
                } else {
                    log("Executing script (" + script.length + " chars)...");
                    var evalResult = eval(script);
                    result = {
                        status: "success",
                        result: evalResult !== undefined ? serializeJSON(evalResult) : "undefined",
                        timestamp: isoTimestamp()
                    };
                    log("Script executed successfully");
                }
                break;

            default:
                result = {
                    status: "error",
                    message: "Unknown command: " + command,
                    timestamp: isoTimestamp()
                };
                log("Unknown command: " + command);
        }
    } catch (e) {
        result = {
            status: "error",
            message: e.toString(),
            line: e.line || 0,
            timestamp: isoTimestamp()
        };
        log("Command error: " + e.toString() + " (line " + (e.line || 0) + ")");
    }

    // 写入结果
    writeJSON(RES_FILE, result);
    return true;
}

/**
 * 获取项目信息
 */
function getProjectInfo() {
    var info = {
        name: "(no project)",
        path: "",
        numSequences: 0,
        sequences: []
    };

    if (app.project) {
        info.name = app.project.name;
        info.path = app.project.path || "";
        info.numSequences = app.project.sequences ? app.project.sequences.numSequences : 0;

        if (app.project.sequences) {
            for (var i = 0; i < app.project.sequences.numSequences; i++) {
                var seq = app.project.sequences[i];
                info.sequences.push({
                    id: seq.sequenceID,
                    name: seq.name,
                    duration: seq.end || 0,
                    videoTracks: seq.videoTracks ? seq.videoTracks.numTracks : 0,
                    audioTracks: seq.audioTracks ? seq.audioTracks.numTracks : 0
                });
            }
        }
    }

    return info;
}

/**
 * 列出所有序列
 */
function listSequences() {
    var seqs = [];
    if (app.project && app.project.sequences) {
        for (var i = 0; i < app.project.sequences.numSequences; i++) {
            var seq = app.project.sequences[i];
            seqs.push({
                id: seq.sequenceID,
                name: seq.name,
                duration: seq.end || 0,
                videoTracks: seq.videoTracks ? seq.videoTracks.numTracks : 0,
                audioTracks: seq.audioTracks ? seq.audioTracks.numTracks : 0
            });
        }
    }
    return { sequences: seqs, count: seqs.length };
}

// ==================== 轮询循环 ====================

function checkLoop() {
    if (!isRunning) return;

    try {
        var f = new File(CMD_FILE);
        if (f.exists) {
            var mtime = f.modified;
            if (mtime && mtime.getTime() !== lastCmdTime) {
                lastCmdTime = mtime.getTime();
                var processed = processCommand();
                if (processed) {
                    cmdCount++;
                    log("Command #" + cmdCount + " processed");
                }
            }
        }
    } catch (e) {
        log("Loop error: " + e.toString());
    }
}

// ==================== 启动/停止 ====================

function startListening() {
    if (isRunning) return;

    // 确保目录存在
    ensureDir(BASE_DIR);

    // 加载密钥
    MCP_SECRET = loadSecret();

    // 清理旧文件
    var oldCmd = new File(CMD_FILE);
    if (oldCmd.exists) oldCmd.remove();
    var oldRes = new File(RES_FILE);
    if (oldRes.exists) oldRes.remove();

    isRunning = true;
    cmdCount = 0;
    lastCmdTime = 0;

    // 启动定时器
    // Premiere Pro 2022+ 支持 app.setInterval
    if (typeof app.setInterval === "function") {
        timerId = app.setInterval(checkLoop, POLL_INTERVAL);
        log("监听已启动 (app.setInterval, " + POLL_INTERVAL + "ms)");
    } else if (typeof app.scheduleTask === "function") {
        // AE 兼容模式（备用）
        function scheduleNext() {
            if (!isRunning) return;
            checkLoop();
            app.scheduleTask("scheduleNext()", POLL_INTERVAL, false);
        }
        scheduleNext();
        log("监听已启动 (app.scheduleTask, " + POLL_INTERVAL + "ms)");
    } else {
        // 降级：无法启动定时器
        isRunning = false;
        log("错误: 当前 Premiere 版本不支持 app.setInterval 或 app.scheduleTask");
        alert(
            "无法启动定时器轮询。\n\n" +
            "当前 Premiere 版本可能不支持 app.setInterval。\n" +
            "需要 Premiere Pro 2022+ (版本 22.0+)。\n\n" +
            "当前版本: " + app.version,
            "PR MCP Bridge - 不兼容"
        );
        return;
    }

    log("=== PR MCP Bridge Started ===");
    log("命令文件: " + CMD_FILE);
    log("结果文件: " + RES_FILE);
    log("签名验证: " + (SIGNATURE_ENABLED && MCP_SECRET ? "ENABLED" : "DISABLED"));
}

function stopListening() {
    if (!isRunning) return;

    isRunning = false;

    // 清除定时器
    if (timerId !== null) {
        if (typeof app.clearInterval === "function") {
            app.clearInterval(timerId);
        }
        timerId = null;
    }

    log("=== PR MCP Bridge Stopped ===");
    log("Total commands processed: " + cmdCount);
}

// ==================== ScriptUI 面板 ====================

function buildUI(thisObj) {
    var win = (thisObj instanceof Panel) ? thisObj : new Window("palette", "PR MCP Bridge", undefined, { resizeable: true });

    // 面板布局
    win.orientation = "column";
    win.alignChildren = ["fill", "top"];
    win.spacing = 8;
    win.margins = 12;

    // 标题
    var titleGroup = win.add("group");
    titleGroup.add("statictext", undefined, "Premiere Pro MCP Bridge");
    titleGroup.alignChildren = ["center", "center"];

    // 状态显示
    var statusGroup = win.add("group");
    statusGroup.orientation = "row";
    statusGroup.alignChildren = ["left", "center"];
    statusGroup.add("statictext", undefined, "状态:");
    var statusLabel = statusGroup.add("statictext", undefined, "未启动");
    statusLabel.characters = 20;

    // 命令计数
    var countGroup = win.add("group");
    countGroup.orientation = "row";
    countGroup.alignChildren = ["left", "center"];
    countGroup.add("statictext", undefined, "已执行:");
    var countLabel = countGroup.add("statictext", undefined, "0");
    countLabel.characters = 10;

    // 分隔线
    win.add("panel", undefined, undefined, { orientation: "horizontal" });

    // 按钮组
    var buttonGroup = win.add("group");
    buttonGroup.orientation = "row";
    buttonGroup.alignChildren = ["center", "center"];

    var startBtn = buttonGroup.add("button", undefined, "启动监听");
    var stopBtn = buttonGroup.add("button", undefined, "停止监听");
    stopBtn.enabled = false;

    // 测试按钮
    var testGroup = win.add("group");
    testGroup.orientation = "row";
    testGroup.alignChildren = ["center", "center"];
    var pingBtn = testGroup.add("button", undefined, "Ping 测试");
    var infoBtn = testGroup.add("button", undefined, "项目信息");

    // 路径显示
    var pathGroup = win.add("group");
    pathGroup.orientation = "column";
    pathGroup.alignChildren = ["left", "top"];
    pathGroup.add("statictext", undefined, "命令文件:");
    var cmdPathLabel = pathGroup.add("statictext", undefined, CMD_FILE, { multiline: true });
    cmdPathLabel.characters = 45;

    // 更新 UI 的函数
    function updateUI() {
        statusLabel.text = isRunning ? "监听中..." : "已停止";
        countLabel.text = String(cmdCount);
        startBtn.enabled = !isRunning;
        stopBtn.enabled = isRunning;
        win.layout.layout(true);
    }

    // 按钮事件
    startBtn.onClick = function() {
        startListening();
        updateUI();
    };

    stopBtn.onClick = function() {
        stopListening();
        updateUI();
    };

    pingBtn.onClick = function() {
        if (!isRunning) {
            alert("请先启动监听", "提示");
            return;
        }
        // 写入一个 ping 命令
        ensureDir(BASE_DIR);
        writeJSON(CMD_FILE, {
            command: "ping",
            timestamp: isoTimestamp(),
            processed: false
        });
        alert("Ping 命令已发送，请查看结果文件", "Ping");
    };

    infoBtn.onClick = function() {
        var info = getProjectInfo();
        var msg = "项目: " + info.name + "\n" +
                  "序列数: " + info.numSequences + "\n";
        for (var i = 0; i < info.sequences.length; i++) {
            msg += "  " + (i + 1) + ". " + info.sequences[i].name + "\n";
        }
        alert(msg, "项目信息");
    };

    // 定时更新 UI
    if (typeof app.setInterval === "function") {
        app.setInterval(function() {
            if (win.visible) {
                updateUI();
            }
        }, 500);
    }

    win.layout.layout(true);
    win.layout.resize();
    win.onResizing = win.onResize = function() {
        this.layout.resize();
    };

    // 如果是独立窗口（非面板），显示窗口
    if (!(thisObj instanceof Panel)) {
        win.center();
        win.show();
    }

    return win;
}

// ==================== 启动 ====================

try {
    buildUI(this);
} catch (e) {
    alert("PR MCP Bridge 启动失败:\n" + e.toString() + "\n(line " + (e.line || 0) + ")", "错误");
}
