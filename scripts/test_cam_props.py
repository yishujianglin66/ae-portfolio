import json
import os
import time

bridge_dir = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge")

# 测试摄像机属性
script_content = r'''
(function() {
    var result = {status: "unknown", log: []};
    try { app.beginUndoGroup("CamProps"); } catch(e) {}
    
    try {
        var W = 576, H = 768, DUR = 5;
        var comp = app.project.items.addComp("CamTest", W, H, 1.0, DUR, 30);
        
        var cam = comp.layers.addCamera("TestCam", [W/2, H/2]);
        cam.threeDLayer = true;
        var co = cam.property("ADBE Camera Options Group");
        result.log.push("cam_created");
        
        // 枚举摄像机选项组的所有属性
        for (var i = 1; i <= co.numProperties; i++) {
            try {
                var p = co.property(i);
                var val = "";
                try { val = p.value; } catch(e) { val = "[group]"; }
                result.log.push(i + ": " + p.name + " (match=" + p.matchName + ") val=" + val);
            } catch(e) {
                result.log.push(i + ": ERROR_" + e.toString().substr(0,30));
            }
        }
        
        result.status = "success";
        result.num_props = co.numProperties;
        try { app.endUndoGroup(); } catch(e) {}
        
    } catch(e) {
        result.status = "error";
        result.message = e.toString();
        try { app.endUndoGroup(); } catch(e2) {}
    }
    
    try { return JSON.stringify(result, null, 2); }
    catch(e) { return "fallback: " + result.status; }
})();
'''

cmd = {
    "command": "executeAtomScript",
    "args": {
        "scriptContent": script_content,
        "scriptName": "enum_camera_props",
        "timeout": 10000,
        "dryRun": False
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "status": "pending"
}

with open(os.path.join(bridge_dir, "ae_command.json"), "w", encoding="utf-8") as f:
    json.dump(cmd, f, indent=2, ensure_ascii=False)

print("摄像机属性枚举命令已发送")
