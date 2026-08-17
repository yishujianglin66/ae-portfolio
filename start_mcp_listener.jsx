// start_mcp_listener.jsx
// 启动 MCP Bridge 监听器
// 用法1: AE菜单 File > Scripts > Run Script File 选择此文件
// 用法2: 从文件管理器双击此文件（AE 运行时会自动执行）
// 用法3: Python 自动启动通过文件关联触发

var PROJ_ROOT = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault";
var LISTENER_PATH = PROJ_ROOT + "/ae_mcp_auto_listener.jsx";

// 检查是否以参数模式运行（支持 --silent 静默启动）
var isSilent = false;
try {
    if (typeof $ !== "undefined" && $ && $.argv) {
        for (var i = 0; i < $.argv.length; i++) {
            if ($.argv[i] === "--silent") {
                isSilent = true;
                break;
            }
        }
    }
} catch (e) {
    // 忽略参数解析错误
}

try {
    var listenerFile = new File(LISTENER_PATH);
    if (listenerFile.exists) {
        listenerFile.encoding = "UTF-8";
        listenerFile.open("r");
        var code = listenerFile.read();
        listenerFile.close();
        eval(code);

        if (typeof checkForCommands === "function") {
            if (typeof __startMcpPolling === "function") {
                __startMcpPolling();
            } else {
                app.scheduleTask("checkForCommands()", 500, true);
            }
            if (!isSilent) {
                alert("MCP Bridge Listener started!\nPolling every 0.5s (recurring).\nClose AE to stop.");
            }
        } else {
            if (!isSilent) {
                alert("ERROR: checkForCommands not defined after loading.\n" +
                      "typeof checkForCommands = " + typeof checkForCommands);
            }
        }
    } else {
        if (!isSilent) {
            alert("Listener not found: " + LISTENER_PATH);
        }
    }
} catch (e) {
    if (!isSilent) {
        alert("Failed to start Listener:\n" + e.toString() +
              "\nLine: " + (e.line || "unknown"));
    }
}
