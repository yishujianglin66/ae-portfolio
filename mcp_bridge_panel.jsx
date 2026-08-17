/*
 * AE MCP Bridge Control Panel
 * Usage: Window > mcp_bridge_panel.jsx
 * 
 * Features:
 *   - Auto-start Listener when panel opens
 *   - Start/Stop Listener manually
 *   - Real-time connection status
 *   - Test command buttons
 *   - Log viewer
 */

// 项目根解析 (2026-08-14 D-24): 环境变量 → 脚本路径 → 候选表 → 回退
var PROJ_ROOT = null;
try { var _er = $.getenv("AEKV_PROJECT_ROOT"); if (_er && new File(_er + "/mcp_bridge_panel.jsx").exists) { PROJ_ROOT = _er; } } catch (e) {}
if (!PROJ_ROOT) { try { var _sd = new File($.fileName).parent; if (new File(_sd.fsName + "/mcp_bridge_panel.jsx").exists) { PROJ_ROOT = _sd.fsName; } } catch (e) {} }
if (!PROJ_ROOT) { var _cs = ["C:/Users/Administrator/Desktop/AE-Knowledge-Vault", "D:/AE-Knowledge-Vault", "C:/AE-Knowledge-Vault"]; for (var _i = 0; _i < _cs.length; _i++) { if (new File(_cs[_i] + "/mcp_bridge_panel.jsx").exists) { PROJ_ROOT = _cs[_i]; break; } } }
if (!PROJ_ROOT) { PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault"; }
var LISTENER_PATH = PROJ_ROOT + "/ae_mcp_auto_listener.jsx";
var BRIDGE_PATH = PROJ_ROOT + "/.ae-mcp-bridge";
var CMD_PATH = BRIDGE_PATH + "/ae_command.json";
var RESP_PATH = BRIDGE_PATH + "/ae_response.json";
var LOG_PATH = BRIDGE_PATH + "/ae_auto_listener.log";
var PANEL_LOG_PATH = BRIDGE_PATH + "/panel.log";

var listenerStarted = false;
var pollInterval = 500;
var statusText = null;
var statusIndicator = null;
var logList = null;

function buildUI(thisObj) {
    var win = (thisObj instanceof Panel) ? thisObj : new Window("palette", "MCP Bridge", undefined, {resizeable: true});
    win.orientation = "column";
    win.alignChildren = ["fill", "top"];

    // ===== Title bar =====
    var titleGroup = win.add("group");
    titleGroup.orientation = "row";
    titleGroup.alignChildren = ["left", "center"];
    var title = titleGroup.add("statictext", undefined, "MCP Bridge");
    title.graphics.font = ScriptUI.newFont("Arial", "bold", 14);

    statusIndicator = titleGroup.add("statictext", undefined, " [ ] ");
    statusIndicator.graphics.font = ScriptUI.newFont("Arial", "bold", 12);

    statusText = titleGroup.add("statictext", undefined, "Disconnected");
    statusText.graphics.font = ScriptUI.newFont("Arial", "regular", 11);

    // ===== Control buttons =====
    var btnGroup = win.add("group");
    btnGroup.orientation = "row";
    btnGroup.alignChildren = ["fill", "center"];

    var startBtn = btnGroup.add("button", undefined, "Start Listener");
    var stopBtn = btnGroup.add("button", undefined, "Stop");
    var refreshBtn = btnGroup.add("button", undefined, "Refresh");

    startBtn.onClick = function() { startListener(false); };
    stopBtn.onClick = function() { stopListener(); };
    refreshBtn.onClick = function() { updateStatus(); refreshLog(); };

    // ===== Quick Commands =====
    var cmdGroup1 = win.add("group");
    cmdGroup1.orientation = "row";
    cmdGroup1.alignChildren = ["fill", "center"];
    cmdGroup1.add("statictext", undefined, "Quick:");

    var pingBtn = cmdGroup1.add("button", undefined, "Ping");
    pingBtn.onClick = function() { sendTestCommand("ping"); };

    var versionBtn = cmdGroup1.add("button", undefined, "Version");
    versionBtn.onClick = function() { sendTestCommand("getVersion"); };

    var infoBtn = cmdGroup1.add("button", undefined, "Project Info");
    infoBtn.onClick = function() { sendTestCommand("getProjectInfo"); };

    // ===== Composition Commands =====
    var cmdGroup2 = win.add("group");
    cmdGroup2.orientation = "row";
    cmdGroup2.alignChildren = ["fill", "center"];
    cmdGroup2.add("statictext", undefined, "Comp:");

    var listCompBtn = cmdGroup2.add("button", undefined, "List Comps");
    listCompBtn.onClick = function() { sendTestCommand("listCompositions"); };

    var createCompBtn = cmdGroup2.add("button", undefined, "New Comp");
    createCompBtn.onClick = function() {
        sendCommand("createComposition", {name:"TestComp", width:1920, height:1080, duration:5, fps:30});
    };

    // ===== Log area =====
    var logGroup = win.add("group");
    logGroup.orientation = "column";
    logGroup.alignChildren = ["fill", "fill"];
    logGroup.add("statictext", undefined, "Log:");

    var logContainer = logGroup.add("group");
    logContainer.orientation = "stack";
    logContainer.alignment = ["fill", "fill"];
    logContainer.preferredSize.height = 200;

    logList = logContainer.add("listbox", undefined, [], {multiselect: false});
    logList.alignment = ["fill", "fill"];

    // ===== Footer =====
    var infoGroup = win.add("group");
    infoGroup.orientation = "row";
    infoGroup.alignChildren = ["left", "center"];
    var info = infoGroup.add("statictext", undefined, "Tip: Dock panel to auto-start on AE launch");
    info.graphics.font = ScriptUI.newFont("Arial", "regular", 9);

    win.onResizing = win.onResize = function() {
        this.layout.resize();
    };

    // Auto-start when panel shows
    if (win instanceof Window) {
        win.onShow = function() {
            app.scheduleTask("panelAutoStart()", 500, false);
        };
    }

    return win;
}

function panelAutoStart() {
    if (!listenerStarted) {
        startListener(true);
    }
    app.scheduleTask("panelAutoRefresh()", 2000, true);
}

function panelAutoRefresh() {
    try {
        refreshLog();
        updateStatus();
    } catch (e) {}
}

function loadListenerCode() {
    try {
        var f = new File(LISTENER_PATH);
        if (!f.exists) {
            panelLog("ERROR: Listener file not found: " + LISTENER_PATH);
            return false;
        }
        f.encoding = "UTF-8";
        f.open("r");
        var code = f.read();
        f.close();
        eval(code);
        return true;
    } catch (e) {
        panelLog("ERROR: Failed to load listener: " + e.toString());
        return false;
    }
}

function startListener(silent) {
    if (listenerStarted) {
        if (!silent) alert("Listener is already running.");
        return;
    }

    if (loadListenerCode()) {
        if (typeof __startMcpPolling === "function") {
            __startMcpPolling();
            listenerStarted = true;
            updateStatus();
            panelLog("Listener started (recurring polling)");
            if (!silent) alert("MCP Bridge Listener started!");
        } else if (typeof checkForCommands === "function") {
            app.scheduleTask("checkForCommands()", pollInterval, true);
            listenerStarted = true;
            updateStatus();
            panelLog("Listener started (scheduleTask)");
            if (!silent) alert("MCP Bridge Listener started!");
        } else {
            panelLog("ERROR: checkForCommands function not found");
            if (!silent) alert("ERROR: Listener functions not found.");
        }
    } else {
        if (!silent) alert("Failed to load listener:\n" + LISTENER_PATH);
    }
}

function stopListener() {
    if (typeof __stopMcpPolling === "function") {
        __stopMcpPolling();
    }
    listenerStarted = false;
    updateStatus();
    panelLog("Listener stopped");
}

function updateStatus() {
    var isConnected = false;
    try {
        var cmdFile = new File(CMD_PATH);
        var respFile = new File(RESP_PATH);

        var testCmd = '{"command":"ping","timestamp":' + Date.now() + '}';
        cmdFile.open("w");
        cmdFile.write(testCmd);
        cmdFile.close();

        $.sleep(600);

        if (respFile.exists) {
            respFile.open("r");
            var resp = respFile.read();
            respFile.close();
            if (resp.indexOf("pong") >= 0 || resp.indexOf("status") >= 0) {
                isConnected = true;
            }
        }
    } catch (e) {}

    if (statusIndicator && statusText) {
        if (isConnected) {
            statusIndicator.text = " [\u25CF] ";
            statusIndicator.graphics.foregroundColor = statusIndicator.graphics.newPen(
                statusIndicator.graphics.PenType.SOLID_COLOR, [0.2, 0.8, 0.2, 1], 1
            );
            statusText.text = "Connected";
        } else if (listenerStarted) {
            statusIndicator.text = " [\u25CB] ";
            statusIndicator.graphics.foregroundColor = statusIndicator.graphics.newPen(
                statusIndicator.graphics.PenType.SOLID_COLOR, [0.9, 0.7, 0.1, 1], 1
            );
            statusText.text = "Starting";
        } else {
            statusIndicator.text = " [ ] ";
            statusIndicator.graphics.foregroundColor = statusIndicator.graphics.newPen(
                statusIndicator.graphics.PenType.SOLID_COLOR, [0.8, 0.2, 0.2, 1], 1
            );
            statusText.text = "Disconnected";
        }
    }
}

function sendTestCommand(cmd) {
    sendCommand(cmd, {});
}

function sendCommand(cmd, args) {
    if (!listenerStarted) {
        alert("Please start Listener first.");
        return;
    }

    try {
        var cmdFile = new File(CMD_PATH);
        var cmdObj = { command: cmd, args: args || {}, timestamp: Date.now() };

        // Ensure bridge directory exists
        var bridgeFolder = new Folder(BRIDGE_PATH);
        if (!bridgeFolder.exists) {
            bridgeFolder.create();
        }

        cmdFile.open("w");
        cmdFile.write(cmdObj.toSource());
        cmdFile.close();

        panelLog("> " + cmd);

        $.sleep(1000);

        var respFile = new File(RESP_PATH);
        if (respFile.exists) {
            respFile.open("r");
            var resp = respFile.read();
            respFile.close();
            panelLog("< " + resp.substring(0, 200));
        }

        refreshLog();
    } catch (e) {
        panelLog("ERROR: " + e.toString());
    }
}

function refreshLog() {
    if (!logList) return;

    try {
        var logFile = new File(LOG_PATH);
        if (logFile.exists) {
            logFile.open("r");
            var content = logFile.read();
            logFile.close();
            var lines = content.split("\n");

            logList.removeAll();
            var start = Math.max(0, lines.length - 100);
            for (var i = start; i < lines.length; i++) {
                if (lines[i].length > 0) {
                    logList.add("item", lines[i]);
                }
            }
        }
    } catch (e) {}
}

function panelLog(msg) {
    try {
        var bridgeFolder = new Folder(BRIDGE_PATH);
        if (!bridgeFolder.exists) {
            bridgeFolder.create();
        }
        var f = new File(PANEL_LOG_PATH);
        f.open("a");
        var d = new Date();
        var ts = d.toLocaleTimeString();
        f.write("[" + ts + "] " + msg + "\n");
        f.close();
    } catch (e) {}
}

var win = buildUI(this);
