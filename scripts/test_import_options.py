import json
import os
import time

bridge_dir = os.path.expanduser("~") + "\\Documents\\ae-mcp-bridge"

script_content = r'''
(function() {
    var result = {status: "unknown", log: []};
    try { app.beginUndoGroup("测试ImportOptions导入"); } catch(e) {}
    
    try {
        function log(s){result.log.push(s);}
        
        // 使用ImportOptions导入
        try {
            var filePath = "D:\\AE-Work\\视频素材库\\frames\\frame_001.png";
            var fileObj = new File(filePath);
            log("file_exists:" + fileObj.exists);
            
            if(fileObj.exists) {
                var importOptions = new ImportOptions(fileObj);
                importOptions.sequence = false;
                var item = app.project.importFile(importOptions);
                if(item) {
                    item.name = "Test_Frame_001";
                    log("import_success:" + item.name);
                } else {
                    log("import_null");
                }
            }
        } catch(e) {
            log("import_error:" + e.toString());
        }
        
        result.status = "success";
        try { app.endUndoGroup(); } catch(e) {}
        
    } catch(e) {
        result.status = "error";
        result.message = e.toString();
        try { app.endUndoGroup(); } catch(e2) {}
    }
    
    try { return JSON.stringify(result, null, 2); }
    catch(e) { return "fallback: " + result.status + " | " + (result.message||""); }
})();
'''

cmd = {
    "command": "executeAtomScript",
    "args": {
        "scriptContent": script_content,
        "scriptName": "test_import_options",
        "timeout": 10000,
        "dryRun": False
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "status": "pending"
}

with open(bridge_dir + "\\ae_command.json", "w", encoding="utf-8") as f:
    json.dump(cmd, f, indent=2, ensure_ascii=False)

print("测试ImportOptions导入脚本已发送")
