// z_mcp_bridge_loader.jsx
// 超轻量 Startup 加载器 - 放在 AE Scripts/Startup 目录
// 作用：AE 启动时自动加载 MCP Bridge Listener 并启动轮询
// 设计原则：文件极小 (<1KB)，用 f.read()+eval() 避免 $.evalFile 大文件崩溃

(function () {
    var LISTENER_PATH = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/ae_mcp_auto_listener.jsx";
    try {
        var f = new File(LISTENER_PATH);
        if (f.exists) {
            f.encoding = "UTF-8";
            f.open("r");
            var code = f.read();
            f.close();
            eval(code);
            if (typeof $.global.__startMcpPolling === "function") {
                $.global.__startMcpPolling();
            }
        }
    } catch (e) {
        // 静默失败，避免影响 AE 启动
    }
})();
