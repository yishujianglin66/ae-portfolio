import json
import os
import time

bridge_dir = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge")

# 创建景深参数测试合成 - 简化版
script_content = r'''
(function() {
    var result = {status: "unknown", log: []};
    try { app.beginUndoGroup("DOF Param Test 2"); } catch(e) {}
    
    try {
        function sPN(p,n,v){try{p.property(n).setValue(v);return true;}catch(e){return false;}}
        
        var W = 720, H = 480, DUR = 3;
        var testApertures = [5, 15, 28, 56, 100];
        var testNames = ["f32", "f11", "f5_6", "f2_8", "f1_4"];
        
        var mainComp = app.project.items.addComp("DOF_Aperture_Test", W, H, 1.0, DUR, 30);
        mainComp.bgColor = [0.1, 0.1, 0.15];
        
        for (var t = 0; t < testApertures.length; t++) {
            var subW = Math.floor(W/5 - 4), subH = H - 30;
            var subComp = app.project.items.addComp("Aperture_" + testNames[t], subW, subH, 1.0, DUR, 30);
            subComp.bgColor = [0.08, 0.08, 0.12];
            
            // 多层Z深度测试条
            for (var i = 0; i < 6; i++) {
                var bar = subComp.layers.addSolid([0.15+i*0.1, 0.15+i*0.08, 0.2+i*0.05], "Bar"+i, subW, 35, 1, DUR);
                bar.threeDLayer = true;
                var p = bar.property("ADBE Transform Group").property("ADBE Position");
                p.setValue([subW/2, 40 + i*65, -800 + i*320]);
            }
            
            // 焦平面标记
            var focal = subComp.layers.addSolid([1,0.95,0.7], "Focal", subW, 3, 1, DUR);
            focal.threeDLayer = true;
            focal.property("ADBE Transform Group").property("ADBE Position").setValue([subW/2, subH/2, 0]);
            
            // 摄像机
            var cam = subComp.layers.addCamera("Cam", [subW/2, subH/2]);
            cam.threeDLayer = true;
            var co = cam.property("ADBE Camera Options Group");
            sPN(co, "ADBE Camera Zoom", subW/2);
            sPN(co, "ADBE Camera Depth of Field", 1);
            sPN(co, "ADBE Camera Focus Distance", subW/2);
            sPN(co, "ADBE Camera Aperture", testApertures[t]);
            sPN(co, "ADBE Camera Blur Level", 150);
            sPN(co, "ADBE Iris Shape", 4);
            sPN(co, "ADBE Iris Roundness", 75);
            
            // 加入主合成
            var ly = mainComp.layers.add(subComp);
            ly.property("ADBE Transform Group").property("ADBE Position").setValue([2 + t*(subW+4) + subW/2, subH/2 + 5]);
            
            // 标签 (用纯色条代替文字)
            var label = mainComp.layers.addSolid([0.3,0.3,0.35], "Label_"+testNames[t], subW, 18, 1, DUR);
            label.property("ADBE Transform Group").property("ADBE Position").setValue([2 + t*(subW+4) + subW/2, H - 9]);
            
            result.log.push("test_" + testNames[t] + "_ok");
        }
        
        result.status = "success";
        result.comp_name = mainComp.name;
        result.num_tests = testApertures.length;
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
        "scriptName": "dof_aperture_test2",
        "timeout": 15000,
        "dryRun": False
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "status": "pending"
}

with open(os.path.join(bridge_dir, "ae_command.json"), "w", encoding="utf-8") as f:
    json.dump(cmd, f, indent=2, ensure_ascii=False)

print("景深光圈参数测试v2命令已发送")
