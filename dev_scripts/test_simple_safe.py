import json
import os
import time

bridge_dir = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge")

# 最简化版本：只加核心功能，不用任何花哨的东西
script_content = r'''
(function() {
    var result = {status: "unknown", log: []};
    try {
        app.beginUndoGroup("TestSimple");
    } catch(e) {
        result.status = "error_beginundo";
        result.message = e.toString();
        return result.toSource ? result.toSource() : JSON.stringify(result);
    }
    
    try {
        var W = 576, H = 768, DUR = 10;
        var comp = app.project.items.addComp("SimpleTest", W, H, 1.0, DUR, 30);
        result.log.push("comp_ok");
        
        var bg = comp.layers.addSolid([0.1,0.1,0.15], "BG", W, H, 1, DUR);
        bg.threeDLayer = true;
        bg.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,500]);
        result.log.push("bg_ok");
        
        var fn = bg.Effects.addProperty("ADBE Fractal Noise");
        result.log.push("fn_added");
        
        try { fn.property(1).setValue(4); result.log.push("fn_1"); } catch(e) { result.log.push("fn_1_err:"+e.toString().substr(0,30)); }
        try { fn.property(2).setValue(2); result.log.push("fn_2"); } catch(e) { result.log.push("fn_2_err:"+e.toString().substr(0,30)); }
        try { fn.property(4).setValue(180); result.log.push("fn_4"); } catch(e) { result.log.push("fn_4_err:"+e.toString().substr(0,30)); }
        try { fn.property(5).setValue(-25); result.log.push("fn_5"); } catch(e) { result.log.push("fn_5_err:"+e.toString().substr(0,30)); }
        try { fn.property(10).setValue(280); result.log.push("fn_10"); } catch(e) { result.log.push("fn_10_err:"+e.toString().substr(0,30)); }
        try { fn.property(16).setValue(5); result.log.push("fn_16"); } catch(e) { result.log.push("fn_16_err:"+e.toString().substr(0,30)); }
        
        var cam = comp.layers.addCamera("Cam", [W/2, H/2]);
        cam.threeDLayer = true;
        var co = cam.property("ADBE Camera Options Group");
        co.property("ADBE Camera Zoom").setValue(850);
        co.property("ADBE Camera Depth of Field").setValue(1);
        co.property("ADBE Camera Focus Distance").setValue(850);
        co.property("ADBE Camera Aperture").setValue(28);
        result.log.push("camera_ok");
        
        app.endUndoGroup();
        result.status = "success";
        result.total_layers = comp.layers.length;
        
    } catch(e) {
        result.status = "error";
        result.message = e.toString();
        try { app.endUndoGroup(); } catch(e2) {}
    }
    
    try {
        return JSON.stringify(result, null, 2);
    } catch(e) {
        return result.toSource ? result.toSource() : "fallback: status=" + result.status;
    }
})();
'''

cmd = {
    "command": "executeAtomScript",
    "args": {
        "scriptContent": script_content,
        "scriptName": "test_simple_safe",
        "timeout": 10000,
        "dryRun": False
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "status": "pending"
}

with open(os.path.join(bridge_dir, "ae_command.json"), "w", encoding="utf-8") as f:
    json.dump(cmd, f, indent=2, ensure_ascii=False)

print("简化安全测试命令已发送")
