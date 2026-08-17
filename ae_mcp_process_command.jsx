
// ae_mcp_process_command.jsx
// 由 Python 看门狗通过 COM 触发，快速处理命令后退出
var PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
var BASE_DIR = PROJ_ROOT + "/.ae-mcp-bridge";
var CMD_FILE = BASE_DIR + "/ae_command.json";
var RES_FILE = BASE_DIR + "/ae_result.json";
var LOG_FILE = BASE_DIR + "/ae_watchdog.log";

function log(msg) {
    try {
        var f = new File(LOG_FILE);
        f.encoding = "UTF-8";
        f.open("a");
        var now = new Date();
        var ts = now.getFullYear() + "-" + (now.getMonth()+1) + "-" + 
                 now.getDate() + " " + now.getHours() + ":" + 
                 now.getMinutes() + ":" + now.getSeconds();
        f.write("[" + ts + "] " + msg + "\n");
        f.close();
    } catch (e) {}
}

function readJSON(path) {
    var f = new File(path);
    if (!f.exists) return null;
    f.encoding = "UTF-8";
    f.open("r");
    var txt = f.read();
    f.close();
    try { return JSON.parse(txt); } catch (e) { return null; }
}

function writeJSON(path, obj) {
    var f = new File(path);
    f.encoding = "UTF-8";
    f.open("w");
    f.write(JSON.stringify(obj));
    f.close();
}

// 导入主 listener 的处理函数
var listenerPath = PROJ_ROOT + "/ae_mcp_auto_listener.jsx";
if (new File(listenerPath).exists) {
    $.evalFile(listenerPath);
}

// 执行命令处理
log("Processing command via external trigger...");
var processed = processCommand();
if (processed) {
    log("Command processed successfully");
} else {
    log("No command to process or already processed");
}
