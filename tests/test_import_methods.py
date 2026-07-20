import json, os, time

bridge_dir = os.path.expanduser("~") + "\\Documents\\ae-mcp-bridge"

script_content = r'''
(function() {
    var result = {status: "unknown", log: []};
    try { app.beginUndoGroup("测试文件导入"); } catch(e) {}
    
    try {
        function log(s){result.log.push(s);}
        
        // 方式1: 直接用字符串路径
        try {
            var filePath = "D:/AE-Work/视频素材库/frames/frame_001.png";
            var item = app.project.importFile(filePath);
            if(item) {
                item.name = "Test_Frame_Slash";
                log("import_success_slash:" + item.name);
            } else {
                log("import_null_slash");
            }
        } catch(e) {
            log("import_error_slash:" + e.toString());
        }
        
        // 方式2: 用File对象的fullName
        try {
            var fileObj = new File("D:\\AE-Work\\视频素材库\\frames\\frame_002.png");
            log("file_fullName:" + fileObj.fullName);
            var item2 = app.project.importFile(fileObj.fullName);
            if(item2) {
                item2.name = "Test_Frame_FullName";
                log("import_success_fullName:" + item2.name);
            } else {
                log("import_null_fullName");
            }
        } catch(e) {
            log("import_error_fullName:" + e.toString());
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
        "scriptName": "test_import_methods",
        "timeout": 10000,
        "dryRun": False
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "status": "pending"
}

with open(bridge_dir + "\\ae_command.json", "w", encoding="utf-8") as f:
    json.dump(cmd, f, indent=2, ensure_ascii=False)

print("测试文件导入方法脚本已发送")
