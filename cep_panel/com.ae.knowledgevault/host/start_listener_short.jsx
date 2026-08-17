// Listener 启动器 - 放在 CEP host 目录，用 $.fileName 自定位
(function(){
    try {
        var scriptDir = File($.fileName).parent.fsName;
        var listenerFile = new File(scriptDir + "/ae_mcp_auto_listener.jsx");
        
        if (!listenerFile.exists) {
            $.global.__lr = "nf:" + listenerFile.fsName;
            return;
        }
        
        $.evalFile(listenerFile);
        $.sleep(300);
        
        if (typeof __startMcpPolling === "function") {
            __startMcpPolling();
            $.global.__lr = "ok";
        } else {
            $.global.__lr = "np";
        }
    } catch(e) {
        $.global.__lr = "e:" + e.toString() + "|" + e.line;
    }
})();
