import json, os, time

bridge_dir = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge")

# 创建景深参数测试合成 - 不同光圈值的对比
script_content = r'''
(function() {
    var result = {status: "unknown", log: []};
    try { app.beginUndoGroup("DOF Param Test"); } catch(e) {}
    
    try {
        var W = 720, H = 480, DUR = 3;
        var testApertures = [5, 15, 28, 56, 100];
        var testNames = ["f32", "f11", "f5.6", "f2.8", "f1.4"];
        
        var mainComp = app.project.items.addComp("DOF_Aperture_Test", W, H, 1.0, DUR, 30);
        mainComp.bgColor = [0.1, 0.1, 0.15];
        
        for (var t = 0; t < testApertures.length; t++) {
            // 子合成
            var subW = W/5 - 4, subH = H - 20;
            var subComp = app.project.items.addComp("Aperture_" + testNames[t], subW, subH, 1.0, DUR, 30);
            subComp.bgColor = [0.08, 0.08, 0.12];
            
            // 参考格子背景
            for (var i = 0; i < 5; i++) {
                var bar = subComp.layers.addSolid([0.15+i*0.05, 0.15+i*0.05, 0.2+i*0.05], "Bar"+i, subW, 30, 1, DUR);
                bar.threeDLayer = true;
                bar.property("ADBE Transform Group").property("ADBE Position").setValue([subW/2, 30+i*60, -600 + i*300]);
            }
            
            // 前景文字点
            var fgDot = subComp.layers.addSolid([1,0.9,0.7], "FocalPoint", 10, 10, 1, DUR);
            fgDot.threeDLayer = true;
            fgDot.property("ADBE Transform Group").property("ADBE Position").setValue([subW/2, subH/2, 0]);
            
            // 摄像机
            var cam = subComp.layers.addCamera("Cam", [subW/2, subH/2]);
            cam.threeDLayer = true;
            var co = cam.property("ADBE Camera Options Group");
            co.property("ADBE Camera Zoom").setValue(subW/2);
            co.property("ADBE Camera Depth of Field").setValue(1);
            co.property("ADBE Camera Focus Distance").setValue(subW/2);
            co.property("ADBE Camera Aperture").setValue(testApertures[t]);
            co.property("ADBE Camera Blur Level").setValue(150);
            co.property("ADBE Iris Shape").setValue(4);
            co.property("ADBE Iris Roundness").setValue(75);
            
            // 添加到主合成
            var layerInMain = mainComp.layers.add(subComp);
            layerInMain.property("ADBE Transform Group").property("ADBE Position").setValue([2 + t*(subW+4) + subW/2, subH/2 + 10]);
            
            // 标签文字
            var txt = mainComp.layers.addText(testNames[t] + " (" + testApertures[t] + "px)");
            var tPos = [2 + t*(subW+4) + subW/2, H - 5];
            txt.property("ADBE Text Properties").property("ADBE Text Document").property("ADBE Text Size").setValue(14);
            txt.property("ADBE Text Properties").property("ADBE Text Document").property("ADBE Text Color").setValue([1,1,1]);
            txt.property("ADBE Transform Group").property("ADBE Position").setValue(tPos);
            
            result.log.push("aperture_" + testNames[t] + "_ok");
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
        "scriptName": "dof_aperture_test",
        "timeout": 15000,
        "dryRun": False
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "status": "pending"
}

with open(os.path.join(bridge_dir, "ae_command.json"), "w", encoding="utf-8") as f:
    json.dump(cmd, f, indent=2, ensure_ascii=False)

print("景深光圈参数测试命令已发送")
