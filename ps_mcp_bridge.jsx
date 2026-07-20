/*
 * ps_mcp_bridge.jsx
 * =================
 * Photoshop MCP Bridge
 *
 * 通过文件轮询机制实现 Python → Photoshop 全自动控制。
 * 原理与 pr_mcp_bridge.jsx 一致：
 *   1. Python 端写入命令到 ps_command.json
 *   2. 本脚本在 Photoshop 内定时轮询命令文件
 *   3. 读取命令 → 执行 ExtendScript → 写入结果到 ps_result.json
 *   4. Python 端轮询读取结果
 *
 * 安装方式：
 *   1. 将此脚本复制到 Photoshop 的 Scripts 目录，或
 *   2. 在 Photoshop 中: File > Scripts > Browse... 选择此文件
 *
 * 使用方式：
 *   1. 打开 Photoshop CS6+
 *   2. 运行此脚本，出现 MCP Bridge 面板
 *   3. 点击"启动监听"按钮
 *   4. 面板会每秒检查命令文件并自动执行
 *
 * 兼容性：Photoshop CS6+（使用 app.scheduleTask 或 setInterval）
 */

// ==================== 配置 ====================

var PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
var BASE_DIR = PROJ_ROOT + "/.ps-mcp-bridge";
var CMD_FILE = BASE_DIR + "/ps_command.json";
var RES_FILE = BASE_DIR + "/ps_result.json";
var LOG_FILE = BASE_DIR + "/ps_listener_log.txt";
var SECRET_FILE = PROJ_ROOT + "/.ps_mcp_secret";

// 签名验证（默认关闭，与 PR Bridge 保持一致）
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
                        appName: app.name,
                        appVersion: app.version,
                        document: app.activeDocument ? app.activeDocument.name : "(none)",
                        timestamp: isoTimestamp()
                    },
                    timestamp: isoTimestamp()
                };
                log("Ping received");
                break;

            case "getDocumentInfo":
                result = {
                    status: "success",
                    result: getDocumentInfo(),
                    timestamp: isoTimestamp()
                };
                break;

            case "listLayers":
                result = {
                    status: "success",
                    result: listLayers(),
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
 * 获取当前文档信息
 */
function getDocumentInfo() {
    var info = {
        name: "(no document)",
        path: "",
        width: 0,
        height: 0,
        resolution: 0,
        colorMode: "",
        numLayers: 0,
        layers: []
    };

    if (app.activeDocument) {
        var doc = app.activeDocument;
        info.name = doc.name;
        info.path = doc.path ? doc.path.fsName : "";
        info.width = doc.width.value;
        info.height = doc.height.value;
        info.resolution = doc.resolution;
        info.colorMode = doc.mode.toString();
        info.numLayers = doc.layers.length;

        info.layers = getLayerList(doc.layers);
    }

    return info;
}

/**
 * 递归获取图层列表
 */
function getLayerList(layers) {
    var result = [];
    for (var i = 0; i < layers.length; i++) {
        var layer = layers[i];
        var layerInfo = {
            id: layer.id,
            name: layer.name,
            visible: layer.visible,
            typename: layer.typename,
            opacity: layer.opacity,
            blendMode: layer.blendMode.toString()
        };

        if (layer.typename === "LayerSet") {
            layerInfo.numChildren = layer.layers.length;
            layerInfo.children = getLayerList(layer.layers);
        }

        result.push(layerInfo);
    }
    return result;
}

/**
 * 列出所有图层
 */
function listLayers() {
    var layers = [];
    if (app.activeDocument) {
        layers = getLayerList(app.activeDocument.layers);
    }
    return { layers: layers, count: layers.length };
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
    // Photoshop CS6+ 支持 app.scheduleTask
    if (typeof app.scheduleTask === "function") {
        function scheduleNext() {
            if (!isRunning) return;
            checkLoop();
            app.scheduleTask("scheduleNext()", POLL_INTERVAL, false);
        }
        scheduleNext();
        log("监听已启动 (app.scheduleTask, " + POLL_INTERVAL + "ms)");
    } else if (typeof app.setInterval === "function") {
        timerId = app.setInterval(checkLoop, POLL_INTERVAL);
        log("监听已启动 (app.setInterval, " + POLL_INTERVAL + "ms)");
    } else {
        // 降级：无法启动定时器
        isRunning = false;
        log("错误: 当前 Photoshop 版本不支持 app.scheduleTask 或 app.setInterval");
        alert(
            "无法启动定时器轮询。\n\n" +
            "当前 Photoshop 版本可能不支持 app.scheduleTask。\n" +
            "需要 Photoshop CS6+ (版本 13.0+)。\n\n" +
            "当前版本: " + app.version,
            "PS MCP Bridge - 不兼容"
        );
        return;
    }

    log("=== PS MCP Bridge Started ===");
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

    log("=== PS MCP Bridge Stopped ===");
    log("Total commands processed: " + cmdCount);
}

// ==================== ScriptUI 面板 ====================

function buildUI(thisObj) {
    var win = (thisObj instanceof Panel) ? thisObj : new Window("palette", "PS MCP Bridge", undefined, { resizeable: true });

    // 面板布局
    win.orientation = "column";
    win.alignChildren = ["fill", "top"];
    win.spacing = 8;
    win.margins = 12;

    // 标题
    var titleGroup = win.add("group");
    titleGroup.add("statictext", undefined, "Photoshop MCP Bridge");
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
    var infoBtn = testGroup.add("button", undefined, "文档信息");

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
        var info = getDocumentInfo();
        var msg = "文档: " + info.name + "\n" +
                  "尺寸: " + info.width + " x " + info.height + "\n" +
                  "图层数: " + info.numLayers + "\n";
        for (var i = 0; i < info.layers.length && i < 10; i++) {
            msg += "  " + (i + 1) + ". " + info.layers[i].name + " (" + info.layers[i].typename + ")\n";
        }
        if (info.layers.length > 10) {
            msg += "  ... 共 " + info.layers.length + " 个图层\n";
        }
        alert(msg, "文档信息");
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
    alert("PS MCP Bridge 启动失败:\n" + e.toString() + "\n(line " + (e.line || 0) + ")", "错误");
}
