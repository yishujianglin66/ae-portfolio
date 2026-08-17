#target premiere

(function() {
    var bridgePath = Folder.temp.fsName + "/ae_kv_pr_bridge";
    var logPath = bridgePath + "/schedule_test_log.txt";
    
    function log(msg) {
        try {
            var f = new File(logPath);
            f.encoding = "UTF-8";
            f.open("a");
            f.writeln("[" + new Date().toUTCString() + "] " + msg);
            f.close();
        } catch(e) {}
    }
    
    log("=== Schedule Task Test ===");
    log("typeof app.scheduleTask: " + typeof app.scheduleTask);
    
    if (typeof app.scheduleTask === 'function') {
        var count = 0;
        
        function testCallback() {
            count++;
            log("Callback called: " + count);
            
            if (count < 10) {
                try {
                    app.scheduleTask(testCallback, 1000, false);
                    log("  Scheduled next");
                } catch(e) {
                    log("  Schedule error: " + e);
                }
            }
        }
        
        try {
            app.scheduleTask(testCallback, 1000, false);
            log("First schedule succeeded");
        } catch(e) {
            log("First schedule error: " + e);
        }
    } else {
        log("scheduleTask not available");
        
        var props = [];
        for (var k in app) {
            if (typeof app[k] === 'function') {
                props.push(k);
            }
        }
        log("App functions: " + props.join(", "));
    }
    
    log("=== Test script loaded ===");
})();
