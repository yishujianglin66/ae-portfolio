// AE MCP Bridge - Headless ONLY (No Panel)
// 纯净版: 只有轮询逻辑, 不打开MCP面板, 避免文件争用
#target aftereffects

(function() {
    // 项目根解析 (2026-08-14 D-24): 环境变量 → 脚本路径 → 候选表 → 回退
var PROJ_ROOT = null;
try { var _er = $.getenv("AEKV_PROJECT_ROOT"); if (_er && new File(_er + "/ae_mcp_auto_listener.jsx").exists) { PROJ_ROOT = _er; } } catch (e) {}
if (!PROJ_ROOT) { try { var _sd = new File($.fileName).parent; if (new File(_sd.fsName + "/ae_mcp_auto_listener.jsx").exists) { PROJ_ROOT = _sd.fsName; } } catch (e) {} }
if (!PROJ_ROOT) { var _cs = ["C:/Users/Administrator/Desktop/AE-Knowledge-Vault", "D:/AE-Knowledge-Vault", "C:/AE-Knowledge-Vault"]; for (var _i = 0; _i < _cs.length; _i++) { if (new File(_cs[_i] + "/ae_mcp_auto_listener.jsx").exists) { PROJ_ROOT = _cs[_i]; break; } } }
if (!PROJ_ROOT) { PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault"; }
    var BRIDGE_DIR = PROJ_ROOT + "/.ae-mcp-bridge";
    var CMD_FILE = BRIDGE_DIR + "/ae_command.json";
    var RES_FILE = BRIDGE_DIR + "/ae_result.json";
    var LOG_FILE = BRIDGE_DIR + "/ae_auto_listener.log";

    if (typeof JSON === "undefined") { JSON = {}; }
    if (typeof JSON.parse !== "function") {
        JSON.parse = function(text) { return eval("(" + text + ")"); };
    }
    if (typeof JSON.stringify !== "function") {
        JSON.stringify = function(obj) {
            function serialize(val) {
                if (val === null || val === undefined) return "null";
                if (typeof val === "boolean" || typeof val === "number") return String(val);
                if (typeof val === "string") return '"' + val.replace(/\\/g, "\\\\").replace(/"/g, '\\"').replace(/\n/g, "\\n").replace(/\r/g, "\\r").replace(/\t/g, "\\t") + '"';
                if (val instanceof Date) return '"' + val.toString() + '"';
                if (val instanceof Array) {
                    var items = [];
                    for (var i = 0; i < val.length; i++) items.push(serialize(val[i]));
                    return "[" + items.join(",") + "]";
                }
                if (typeof val === "object") {
                    var pairs = [];
                    for (var k in val) {
                        if (val.hasOwnProperty(k)) pairs.push('"' + k + '":' + serialize(val[k]));
                    }
                    return "{" + pairs.join(",") + "}";
                }
                return '"' + String(val) + '"';
            }
            return serialize(obj);
        };
    }

    function log(msg) {
        try {
            var f = new File(LOG_FILE);
            f.open("a"); f.encoding = "UTF-8";
            f.write("[" + new Date().toLocaleString() + "] " + msg + "\n");
            f.close();
        } catch(e) {}
    }

    function readJSON(path) {
        try {
            var f = new File(path);
            if (!f.exists) return null;
            f.encoding = "UTF-8"; f.open("r");
            var text = f.read(); f.close();
            return JSON.parse(text);
        } catch(e) { return null; }
    }

    function writeJSON(path, obj) {
        try {
            var f = new File(path);
            f.encoding = "UTF-8"; f.open("w");
            f.write(JSON.stringify(obj));
            f.close();
        } catch(e) { log("writeJSON FAIL: " + path + " " + e.toString()); }
    }

    function successResponse(data) { return { success: true, data: data }; }
    function errorResponse(code, msg) { return { success: false, error: { errorCode: code, message: msg } }; }

    // === Commands ===
    var handlers = {};
    handlers["ping"] = function() {
        return successResponse({ pong: true, appVersion: app.version });
    };
    handlers["runScript"] = function(params) {
        try {
            if (params.code) {
                var result = eval(params.code);
                return successResponse({ result: String(result) });
            }
            if (params.file) {
                var f = new File(params.file);
                if (!f.exists) return errorResponse("NOT_FOUND", params.file);
                f.encoding = "UTF-8"; f.open("r");
                var code = f.read(); f.close();
                var result = eval(code);
                return successResponse({ result: String(result) });
            }
            return errorResponse("MISSING", "No code or file");
        } catch(e) { return errorResponse("EVAL_ERROR", e.toString()); }
    };
    handlers["getProjectInfo"] = function() {
        try {
            return successResponse({
                name: app.project.file ? app.project.file.name : "Untitled",
                numItems: app.project.numItems
            });
        } catch(e) { return errorResponse("PROJ", e.toString()); }
    };

    log("========================================");
    log("MCP Bridge NOPANEL v1.0 starting...");
    log("App version: " + app.version);

    var lastProcessedId = "";

    function poll() {
        try {
            var f = new File(CMD_FILE);
            if (!f.exists) return;
            var data = readJSON(CMD_FILE);
            if (!data) return;
            if (data.processed) return;
            var cmdId = data.timestamp + "_" + data.command;
            if (cmdId === lastProcessedId) return;
            lastProcessedId = cmdId;

            var cmd = data.command;
            var args = data.args || {};
            var handler = handlers[cmd];
            var result;
            if (handler) {
                try { result = handler(args); }
                catch(e) { result = errorResponse("EXEC", e.toString()); }
            } else {
                result = errorResponse("UNKNOWN", cmd);
            }

            var response = {
                command: cmd,
                status: result.success ? "success" : "error",
                result: result,
                timestamp: new Date().toISOString ? new Date().toISOString() : String(new Date())
            };
            writeJSON(RES_FILE, response);
            data.processed = true;
            writeJSON(CMD_FILE, data);
            log(cmd + " -> " + (result.success ? "OK" : "ERR"));
        } catch(e) {
            log("Poll error: " + e.toString());
        }
    }

    $.global.__mcpPollNoPanel = function() { poll(); };

    try {
        app.scheduleTask("$.global.__mcpPollNoPanel()", 500, true);
        log("Polling started (500ms, NOPANEL mode)");
    } catch(e) {
        log("scheduleTask FAILED: " + e.toString());
    }

    // 标记启动
    try {
        var mf = new File(BRIDGE_DIR + "/_bridge_started.marker");
        mf.open("w"); mf.writeln("NOPANEL bridge started " + new Date().toLocaleString()); mf.close();
    } catch(e) {}

    log("MCP Bridge NOPANEL v1.0 ready");
    log("========================================");
})();
