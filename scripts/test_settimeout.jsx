#target premiere

(function() {
    var bridgePath = Folder.temp.fsName + "/ae_kv_pr_bridge";
    var logPath = bridgePath + "/settimeout_test_log.txt";
    
    function log(msg) {
        try {
            var f = new File(logPath);
            f.encoding = "UTF-8";
            f.open("a");
            f.writeln("[" + new Date().toUTCString() + "] " + msg);
            f.close();
        } catch(e) {}
    }
    
    log("=== setTimeout Test ===");
    log("typeof app.setTimeout: " + typeof app.setTimeout);
    
    var count = 0;
    var maxCount = 10;
    
    function testTimeout() {
        count++;
        log("Timeout callback: " + count);
        
        if (count < maxCount) {
            try {
                var id = app.setTimeout(testTimeout, 1000);
                log("  Next timeout ID: " + id);
            } catch(e) {
                log("  setTimeout error: " + e);
            }
        } else {
            log("Test complete, " + maxCount + " iterations");
        }
    }
    
    try {
        var firstId = app.setTimeout(testTimeout, 1000);
        log("First setTimeout ID: " + firstId);
    } catch(e) {
        log("First setTimeout error: " + e);
    }
    
    log("=== Test script loaded ===");
})();
