// 重新启用 Bridge polling
(function() {
    try {
        // 清除可能存在的旧 polling
        try { $.global.__mcpPoll = null; } catch(e) {}

        // 重新加载 Bridge 脚本
        var bridgePath = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/2_mcp_bridge_loader.jsx";
        var f = new File(bridgePath);
        if (f.exists) {
            $.evalFile(f);
        }
    } catch(e) {
        // 写入错误日志
        var logFile = new File("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/poll_restart_error.log");
        logFile.open("w");
        logFile.write("Error: " + e.toString());
        logFile.close();
    }
})();
