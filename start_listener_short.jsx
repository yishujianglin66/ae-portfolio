// 启动 MCP Listener 轮询
(function(){
    try {
        var listenerPath = new File("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/ae_mcp_auto_listener.jsx");
        if (!listenerPath.exists) {
            $.global.__listenerResult = "error:file_not_found";
            return;
        }
        $.evalFile(listenerPath);
        $.sleep(300);
        if (typeof __startMcpPolling === "function") {
            __startMcpPolling();
            $.global.__listenerResult = "started";
        } else {
            $.global.__listenerResult = "loaded_no_poll";
        }
    } catch(e) {
        $.global.__listenerResult = "error:" + e.toString() + "|line:" + e.line;
    }
})();
