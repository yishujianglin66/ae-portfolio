import json
import os
import time

bridge_dir = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge")

# 增量测试：基础 + BG粒子 + 中景 + 中景粒子 + 主体 + 前景 + 前景粒子
script_content = r'''
(function() {
    var result = {status: "unknown", log: [], err: ""};
    try { app.beginUndoGroup("IncTest1"); } catch(e) {}
    
    try {
        var W = 576, H = 768, DUR = 10;
        function sPI(p,i,v){try{p.property(i).setValue(v);return true;}catch(e){return false;}}
        function sPN(p,n,v){try{p.property(n).setValue(v);return true;}catch(e){return false;}}
        
        var comp = app.project.items.addComp("IncTest", W, H, 1.0, DUR, 30);
        comp.bgColor = [0.08, 0.08, 0.12];
        result.log.push("1_comp");
        
        // BG_Sky
        var bgSky = comp.layers.addSolid([0.12,0.15,0.22], "BG_Sky", W, H, 1, DUR);
        bgSky.threeDLayer = true;
        bgSky.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,500]);
        bgSky.property("ADBE Transform Group").property("ADBE Scale").setValue([65,65,65]);
        var fn = bgSky.Effects.addProperty("ADBE Fractal Noise");
        sPI(fn,1,4); sPI(fn,2,2); sPI(fn,4,180); sPI(fn,5,-25); sPI(fn,10,280); sPI(fn,16,5);
        var gb = bgSky.Effects.addProperty("ADBE Gaussian Blur 2");
        sPI(gb,1,8);
        result.log.push("2_bgSky");
        
        // BG_Particles
        var bgP = comp.layers.addSolid([0,0,0], "Particles_BG", W, H, 1, DUR);
        bgP.threeDLayer = true;
        bgP.blendingMode = BlendingMode.SCREEN;
        bgP.opacity.setValue(60);
        bgP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,400]);
        bgP.property("ADBE Transform Group").property("ADBE Scale").setValue([70,70,70]);
        var cp1 = bgP.Effects.addProperty("CC Particle World");
        sPN(cp1,"Birth Rate",80);
        sPN(cp1,"Longevity (sec)",4);
        sPN(cp1,"Particle Type",7);
        sPN(cp1,"Size",0.025);
        sPN(cp1,"Max Opacity",50);
        sPN(cp1,"Gravity",0.015);
        sPN(cp1,"Wind X",0.04);
        result.log.push("3_bgParticles");
        
        // Midground
        var mid = comp.layers.addSolid([0.18,0.22,0.28], "Midground", W, H, 1, DUR);
        mid.threeDLayer = true;
        mid.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,180]);
        mid.property("ADBE Transform Group").property("ADBE Scale").setValue([82,82,82]);
        result.log.push("4_midground");
        
        // MID_Particles
        var midP = comp.layers.addSolid([0,0,0], "Particles_MID", W, H, 1, DUR);
        midP.threeDLayer = true;
        midP.blendingMode = BlendingMode.SCREEN;
        midP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,120]);
        var cp2 = midP.Effects.addProperty("CC Particle World");
        sPN(cp2,"Birth Rate",40);
        sPN(cp2,"Longevity (sec)",2.5);
        sPN(cp2,"Particle Type",8);
        sPN(cp2,"Size",0.05);
        sPN(cp2,"Max Opacity",80);
        sPN(cp2,"Gravity",0.08);
        sPN(cp2,"Wind X",0.1);
        result.log.push("5_midParticles");
        
        // Subject
        var subj = comp.layers.addSolid([0.4,0.45,0.55], "Main_Subject", W, H, 1, DUR);
        subj.threeDLayer = true;
        subj.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,0]);
        var ds = subj.Effects.addProperty("ADBE Drop Shadow");
        sPI(ds,1,[0,0,0]); sPI(ds,2,45); sPI(ds,3,135); sPI(ds,4,10); sPI(ds,5,12);
        result.log.push("6_subject");
        
        // Foreground
        var fg = comp.layers.addSolid([0.25,0.28,0.32], "Foreground", W, H, 1, DUR);
        fg.threeDLayer = true;
        fg.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,-180]);
        fg.property("ADBE Transform Group").property("ADBE Scale").setValue([125,125,125]);
        result.log.push("7_foreground");
        
        // FG_Particles
        var fgP = comp.layers.addSolid([0,0,0], "Particles_FG", W, H, 1, DUR);
        fgP.threeDLayer = true;
        fgP.blendingMode = BlendingMode.SCREEN;
        fgP.property("ADBE Transform Group").property("ADBE Position").setValue([W/2,H/2,-280]);
        fgP.property("ADBE Transform Group").property("ADBE Scale").setValue([140,140,140]);
        var cp3 = fgP.Effects.addProperty("CC Particle World");
        sPN(cp3,"Birth Rate",12);
        sPN(cp3,"Longevity (sec)",2);
        sPN(cp3,"Particle Type",8);
        sPN(cp3,"Size",0.1);
        sPN(cp3,"Max Opacity",70);
        sPN(cp3,"Gravity",0.04);
        sPN(cp3,"Wind X",0.25);
        result.log.push("8_fgParticles");
        
        result.total_layers = comp.layers.length;
        result.status = "success";
        try { app.endUndoGroup(); } catch(e) {}
        
    } catch(e) {
        result.status = "error";
        result.message = e.toString();
        result.err_line = e.line ? e.line : "unknown";
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
        "scriptName": "inc_test_layers",
        "timeout": 12000,
        "dryRun": False
    },
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
    "status": "pending"
}

with open(os.path.join(bridge_dir, "ae_command.json"), "w", encoding="utf-8") as f:
    json.dump(cmd, f, indent=2, ensure_ascii=False)

print("增量测试1（图层）已发送")
