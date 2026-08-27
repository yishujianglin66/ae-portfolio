// ============================================================
// PRBridgeCEP - Host ExtendScript v2.0
// 运行在 Premiere Pro 的 ExtendScript 引擎中
// 由 CEP 11 通过 ScriptPath 自动加载
//
// v2.0 核心变更：
//   - 新增 PRBridge_poll() 函数供 Chromium 侧 setInterval 调用
//   - 不再依赖 app.scheduleTask（PR 2025 不支持）
//   - 轮询由 CEP main.js 的 Chromium setInterval 驱动
// ============================================================

// 项目根目录
var PRBRIDGE_PROJECT_ROOT = null;
try { var _er = $.getenv("AEKV_PROJECT_ROOT"); if (_er && new File(_er + "/scripts/pr_bridge_core.jsx").exists) { PRBRIDGE_PROJECT_ROOT = _er; } } catch (e) {}
if (!PRBRIDGE_PROJECT_ROOT) { try { var _sd = new File($.fileName).parent.parent; if (new File(_sd.fsName + "/scripts/pr_bridge_core.jsx").exists) { PRBRIDGE_PROJECT_ROOT = _sd.fsName; } } catch (e) {} }
if (!PRBRIDGE_PROJECT_ROOT) { var _cs = ["C:/Users/Administrator/Desktop/AE-Knowledge-Vault", "D:/AE-Knowledge-Vault", "C:/AE-Knowledge-Vault"]; for (var _i = 0; _i < _cs.length; _i++) { if (new File(_cs[_i] + "/scripts/pr_bridge_core.jsx").exists) { PRBRIDGE_PROJECT_ROOT = _cs[_i]; break; } } }
if (!PRBRIDGE_PROJECT_ROOT) { PRBRIDGE_PROJECT_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault"; }
var PRBRIDGE_CORE_PATH = PRBRIDGE_PROJECT_ROOT + "/scripts/pr_bridge_core.jsx";
var PRBRIDGE_BUSINESS_HANDLER_SRC = PRBRIDGE_PROJECT_ROOT + "/scripts/handler_pr_business.jsx";
var PRBRIDGE_BRIDGE_DIR = PRBRIDGE_PROJECT_ROOT + "/.premiere-mcp-bridge";
var PRBRIDGE_BUSINESS_HANDLER_DST = PRBRIDGE_BRIDGE_DIR + "/handler_pr_business.jsx";

/**
 * 同步业务 handler 文件从 scripts/ 到 .premiere-mcp-bridge/
 */
function PRBridge_syncBusinessHandler() {
    try {
        var srcFile = new File(PRBRIDGE_BUSINESS_HANDLER_SRC);
        var dstFile = new File(PRBRIDGE_BUSINESS_HANDLER_DST);

        var dstFolder = new Folder(PRBRIDGE_BRIDGE_DIR);
        if (!dstFolder.exists) {
            dstFolder.create();
        }

        if (!srcFile.exists) {
            return { synced: false, reason: "source not found" };
        }

        srcFile.encoding = "UTF-8";
        srcFile.open("r");
        var content = srcFile.read();
        srcFile.close();

        dstFile.encoding = "UTF-8";
        dstFile.open("w");
        dstFile.write(content);
        dstFile.close();

        return { synced: true, bytes: content.length };
    } catch(e) {
        return { synced: false, error: e.toString() };
    }
}

/**
 * 加载 PR Bridge 核心 JSX
 */
function PRBridge_loadCore() {
    try {
        var coreFile = new File(PRBRIDGE_CORE_PATH);
        if (!coreFile.exists) {
            return { loaded: false, error: "Core JSX not found: " + PRBRIDGE_CORE_PATH };
        }

        coreFile.encoding = "UTF-8";
        coreFile.open("r");
        var content = coreFile.read();
        coreFile.close();

        var fn = new Function(content);
        fn();

        return { loaded: true };
    } catch(e) {
        return { loaded: false, error: e.toString() };
    }
}

/**
 * 初始化 PR Bridge：先同步 handler，再加载核心
 * 由 CEP main.js 通过 evalScript 调用
 */
function PRBridge_init() {
    var result = { sync: null, core: null, version: "2.0.0" };

    // 1. 同步业务 handler
    result.sync = PRBridge_syncBusinessHandler();

    // 2. 加载核心 JSX
    result.core = PRBridge_loadCore();

    // 3. 报告状态
    if (typeof PRBridge !== "undefined") {
        result.bridgeVersion = PRBridge.version;
        result.handlers = PRBridge.listHandlers();
    }

    return JSON.stringify(result);
}

/**
 * PRBridge_poll — 供 Chromium setInterval 每 500ms 调用
 * 检查命令文件，有命令则处理并返回结果摘要
 * 无命令则返回空字符串（避免 evalScript 回调报错）
 */
function PRBridge_poll() {
    try {
        if (typeof PRBridge === "undefined") return "";
        if (typeof processCommandFile !== "function") return "";

        var cmdFile = new File(PRBridge.commandFile);
        if (!cmdFile.exists) return "";

        // 有命令文件，处理它
        processCommandFile();

        // 读取结果文件返回摘要
        var resFile = new File(PRBridge.resultFile);
        if (resFile.exists) {
            resFile.encoding = "UTF-8";
            resFile.open("r");
            var resContent = resFile.read();
            resFile.close();
            if (resContent && resContent.length > 2) {
                try {
                    var resObj = JSON.parse(resContent);
                    return JSON.stringify({
                        executed: true,
                        status: resObj.status || "success",
                        command: resObj.command || "unknown"
                    });
                } catch(e) {
                    return JSON.stringify({ executed: true, status: "success", command: "parsed" });
                }
            }
        }
        return JSON.stringify({ executed: true, status: "success", command: "processed" });
    } catch(e) {
        return "";
    }
}

/**
 * 获取 Bridge 状态
 */
function PRBridge_status() {
    if (typeof PRBridge === "undefined") {
        return JSON.stringify({ running: false, reason: "PRBridge not loaded" });
    }
    return JSON.stringify({
        running: true,
        version: PRBridge.version,
        handlers: PRBridge.listHandlers()
    });
}

// ============================================================
// 自动启动
// CEP 的 ScriptPath 会在 PR 启动时加载本文件
// 直接初始化（不再依赖 app.scheduleTask）
// ============================================================
try {
    PRBridge_init();
} catch(e) {
    // 静默失败，CEP main.js 会通过 startBridge() 重试
}

// host.jsx 加载完成标记
"PRBridgeCEP host.jsx v2.0 loaded";
