// AE MCP Bridge Auto Listener - 自动启动加载器
// 每次 AE 启动时自动加载 MCP Bridge 监听器
// 使用$.evalFile 直接加载，避免 eval 大段代码导致崩溃
var __mcpListenerPath = "C:\\Users\\Administrator\\Desktop\\AE-Knowledge-Vault\\ae_mcp_auto_listener.jsx";
if (new File(__mcpListenerPath).exists) {
    $.evalFile(__mcpListenerPath);
    $.writeln("[MCP Bridge] Auto listener loaded via $.evalFile");
} else {
    $.writeln("[MCP Bridge] Listener not found: " + __mcpListenerPath);
}
