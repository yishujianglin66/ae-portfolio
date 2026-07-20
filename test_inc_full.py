import json, os, time

bridge_dir = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge")

# 增量测试2：加调整层 + 灯光 + 摄像机 + Rig + 控制器
script_content = r'''
(function() {
    var result = {status: "unknown", log: [], err: ""};
    try { app.beginUndoGroup("IncTest2"); } catch(e) {}
    
    try {
        var W = 576, H = 768, DUR = 10;
        function sPI(p,i,v){try{p.property(i).setValue(v);return true;}catch(e){return false;}}
        function sPN(p,n,v){try{p.property(n).setValue(v);return true;}catch(e){return false;}}
        
        var comp = app.project.items.addComp("IncTest2", W, H, 1.0, DUR, 30);
        comp.bgColor = [0.08, 0.08, 0.12];
        result.log.push("1_comp");
        
        // 7个层（简化，不加效果，测试上层建筑）
        var bg = comp.layers.addSolid([0.1,0.1,0.2], "BG", W, H, 1, DUR);
        bg.threeDLayer = true;
        bg.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,500]);
        var subj = comp.layers.addSolid([0.4,0.5,0.6], "Subj", W, H, 1, DUR);
        subj.threeDLayer = true;
        var fg = comp.layers.addSolid([0.3,0.3,0.3], "FG", W, H, 1, DUR);
        fg.threeDLayer = true;
        fg.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,-180]);
        result.log.push("2_layers");
        
        // 调整层
        var glowA = comp.layers.addSolid([1,1,1], "Adj_Glow", W, H, 1, DUR);
        glowA.adjustmentLayer = true;
        glowA.blendingMode = BlendingMode.SCREEN;
        glowA.opacity.setValue(50);
        var gl = glowA.Effects.addProperty("ADBE Glo2");
        sPN(gl,"Glow Threshold",70);
        sPN(gl,"Glow Radius",25);
        sPN(gl,"Glow Intensity",1.8);
        result.log.push("3_adjGlow");
        
        var vigA = comp.layers.addSolid([1,1,1], "Adj_Vignette", W, H, 1, DUR);
        vigA.adjustmentLayer = true;
        vigA.Effects.addProperty("ADBE Lumetri");
        result.log.push("4_adjVignette");
        
        var colA = comp.layers.addSolid([1,1,1], "Adj_Color", W, H, 1, DUR);
        colA.adjustmentLayer = true;
        var bc = colA.Effects.addProperty("ADBE Brightness & Contrast 2");
        sPI(bc,1,0); sPI(bc,2,15);
        var vi = colA.Effects.addProperty("ADBE Vibrance");
        sPI(vi,1,5);
        var sh = colA.Effects.addProperty("ADBE Sharpen");
        sPI(sh,1,20);
        var ns = colA.Effects.addProperty("ADBE Noise2");
        sPI(ns,1,4);
        result.log.push("5_adjColor");
        
        // 灯光
        var kL = comp.layers.addLight("Key_Light", [W/2-180, H/2-250]);
        kL.threeDLayer = true;
        kL.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(100);
        kL.property("ADBE Light Options Group").property("ADBE Light Color").setValue([1.0,0.96,0.9]);
        kL.property("ADBE Light Options Group").property("ADBE Casts Shadows").setValue(1);
        kL.property("ADBE Light Options Group").property("ADBE Light Shadow Darkness").setValue(75);
        kL.property("ADBE Light Options Group").property("ADBE Light Shadow Diffusion").setValue(12);
        kL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2-180,H/2-250,-400]);
        result.log.push("6_keyLight");
        
        var fL = comp.layers.addLight("Fill_Light", [W/2-150, H/2+80]);
        fL.threeDLayer = true;
        fL.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(35);
        fL.property("ADBE Light Options Group").property("ADBE Light Color").setValue([0.85,0.92,1.0]);
        fL.property("ADBE Light Options Group").property("ADBE Casts Shadows").setValue(0);
        fL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2-150,H/2+80,-120]);
        result.log.push("7_fillLight");
        
        var rL = comp.layers.addLight("Rim_Light", [W/2+180, H/2-80]);
        rL.threeDLayer = true;
        rL.property("ADBE Light Options Group").property("ADBE Light Intensity").setValue(65);
        rL.property("ADBE Light Options Group").property("ADBE Light Color").setValue([0.9,0.95,1.0]);
        rL.property("ADBE Light Options Group").property("ADBE Casts Shadows").setValue(0);
        rL.property("ADBE Transform Group").property("ADBE Position").setValue([W/2+180,H/2-80,280]);
        result.log.push("8_rimLight");
        
        // 摄像机
        var cam = comp.layers.addCamera("Main_Camera", [W/2, H/2]);
        cam.threeDLayer = true;
        var co = cam.property("ADBE Camera Options Group");
        co.property("ADBE Camera Zoom").setValue(850);
        co.property("ADBE Camera Depth of Field").setValue(1);
        co.property("ADBE Camera Focus Distance").setValue(850);
        co.property("ADBE Camera Aperture").setValue(28);
        co.property("ADBE Camera Blur Level").setValue(180);
        co.property("ADBE Camera Iris Shape").setValue(3);
        co.property("ADBE Camera Iris Roundness").setValue(75);
        co.property("ADBE Camera Diffraction Fringe").setValue(18);
        co.property("ADBE Camera Highlight Gain").setValue(100);
        co.property("ADBE Camera Highlight Threshold").setValue(45);
        result.log.push("9_cameraDOF");
        
        var cPos = cam.property("ADBE Transform Group").property("ADBE Position");
        cPos.setValueAtTime(0, [W/2, H/2, -1000]);
        cPos.setValueAtTime(DUR, [W/2, H/2, -750]);
        cPos.expression = "wiggle(1.5, 4) + value";
        result.log.push("10_cameraAnim");
        
        // Camera Rig
        var rig = comp.layers.addNull(DUR);
        rig.name = "Camera_Rig";
        rig.threeDLayer = true;
        cam.parent = rig;
        result.log.push("11_cameraRig");
        
        // Global Controller
        var ctrl = comp.layers.addNull(DUR);
        ctrl.name = "Global_Controller";
        var s1 = ctrl.Effects.addProperty("ADBE Slider Control");
        s1.name = "DOF_Amount";
        sPI(s1,1,100);
        var s2 = ctrl.Effects.addProperty("ADBE Slider Control");
        s2.name = "Particle_Amount";
        sPI(s2,1,100);
        var s3 = ctrl.Effects.addProperty("ADBE Slider Control");
        s3.name = "Glow_Intensity";
        sPI(s3,1,100);
        result.log.push("12_controller");
        
        result.total_layers = comp.layers.length;
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
        "scriptName": "inc_test_full",
        "timeout": 12000,
        "dryRun": False
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "status": "pending"
}

with open(os.path.join(bridge_dir, "ae_command.json"), "w", encoding="utf-8") as f:
    json.dump(cmd, f, indent=2, ensure_ascii=False)

print("增量测试2（全功能）已发送")
