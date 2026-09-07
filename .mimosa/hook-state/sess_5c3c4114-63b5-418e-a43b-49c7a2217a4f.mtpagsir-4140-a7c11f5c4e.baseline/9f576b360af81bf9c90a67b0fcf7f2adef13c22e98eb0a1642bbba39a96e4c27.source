// AE Knowledge Vault - CEP Host (ExtendScript)
// 此脚本在 AE 启动时自动加载

#target aftereffects

(function() {
    "use strict";

    // 自动启动 MCP listener
    function autoStartListener() {
        try {
            var listenerPath = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/ae_mcp_auto_listener.jsx";
            if (File(listenerPath).exists) {
                $.evalFile(listenerPath);
                $.sleep(500);
                var startPath = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/start_mcp_listener.jsx";
                if (File(startPath).exists) {
                    $.evalFile(startPath);
                }
            }
        } catch(e) {
            // 静默失败，不弹窗
        }
    }

    // 应用启动时执行
    if (app.project) {
        autoStartListener();
    } else {
        // 等项目打开
        app.addEventListener("newProject", function() {
            autoStartListener();
        });
        app.addEventListener("openProject", function() {
            autoStartListener();
        });
    }

})();
