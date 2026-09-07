// z_mcp_bridge_loader.jsx
// 诊断版本 - 详细记录 Startup 上下文中的可用功能
// 放在 AE Scripts/Startup 目录

(function () {
    var PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
    var LOG_DIR = PROJ_ROOT + "/.ae-mcp-bridge";
    var LOG_FILE = LOG_DIR + "/startup_loader_diag.log";
    var LISTENER_PATH = PROJ_ROOT + "/ae_mcp_auto_listener.jsx";

    function logDiag(msg) {
        try {
            var f = new File(LOG_FILE);
            f.encoding = "UTF-8";
            f.open("a");
            var d = new Date();
            var ts = d.getFullYear() + "-" + (d.getMonth()+1) + "-" + d.getDate() + " " +
                     d.getHours() + ":" + d.getMinutes() + ":" + d.getSeconds();
            f.write("[" + ts + "] " + msg + "\n");
            f.close();
        } catch (e) {
        }
    }

    function testScheduleTaskRecurring() {
        try {
            if (typeof app.scheduleTask !== "function") {
                logDiag("FAIL: app.scheduleTask is not a function: " + typeof app.scheduleTask);
                return false;
            }
            logDiag("app.scheduleTask type: " + typeof app.scheduleTask);
            return true;
        } catch (e) {
            logDiag("ERROR checking scheduleTask: " + e.toString());
            return false;
        }
    }

    function testEvalListener() {
        try {
            var f = new File(LISTENER_PATH);
            if (!f.exists) {
                logDiag("FAIL: Listener file not found: " + LISTENER_PATH);
                return false;
            }
            logDiag("Listener file found, size: " + f.length + " bytes");

            f.encoding = "UTF-8";
            f.open("r");
            var code = f.read();
            f.close();
            logDiag("Listener code read: " + code.length + " chars");

            logDiag("Eval starting...");
            eval(code);
            logDiag("Eval completed");

            // Check if functions are defined
            if (typeof checkForCommands === "function") {
                logDiag("OK: checkForCommands is a function (local scope)");
            } else {
                logDiag("WARN: checkForCommands not in local scope, type: " + typeof checkForCommands);
            }

            if (typeof $.global.checkForCommands === "function") {
                logDiag("OK: $.global.checkForCommands is a function");
            } else {
                logDiag("WARN: $.global.checkForCommands not function, type: " + typeof $.global.checkForCommands);
            }

            if (typeof __startMcpPolling === "function") {
                logDiag("OK: __startMcpPolling is a function (local scope)");
            } else {
                logDiag("WARN: __startMcpPolling not in local scope, type: " + typeof __startMcpPolling);
            }

            if (typeof $.global.__startMcpPolling === "function") {
                logDiag("OK: $.global.__startMcpPolling is a function");
            } else {
                logDiag("WARN: $.global.__startMcpPolling not function, type: " + typeof $.global.__startMcpPolling);
            }

            return true;
        } catch (e) {
            logDiag("ERROR during eval: " + e.toString() + " (line: " + (e.line || "?") + ")");
            return false;
        }
    }

    function testStartPolling() {
        try {
            if (typeof $.global.__startMcpPolling === "function") {
                logDiag("Calling __startMcpPolling()...");
                $.global.__startMcpPolling();
                logDiag("__startMcpPolling() returned");
                return true;
            }
            return false;
        } catch (e) {
            logDiag("ERROR starting polling: " + e.toString());
            return false;
        }
    }

    // ===== 主流程 =====
    try {
        // Ensure log directory exists
        var logDir = new File(LOG_DIR);
        if (!logDir.exists) {
            logDir.create();
        }

        logDiag("========================================");
        logDiag("Startup loader diagnostic - START");
        logDiag("app version: " + (app.version || "unknown"));
        logDiag("app name: " + (app.name || "unknown"));

        // Test 1: scheduleTask availability
        testScheduleTaskRecurring();

        // Test 2: eval listener
        var evalOk = testEvalListener();

        // Test 3: try to start polling
        if (evalOk) {
            testStartPolling();
        }

        logDiag("Startup loader diagnostic - END");
        logDiag("========================================");
    } catch (e) {
        logDiag("FATAL ERROR in startup loader: " + e.toString());
    }
})();
