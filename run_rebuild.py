import json

script_content = """
function log(msg) {
    $.writeln(msg);
    try {
        var f = new File("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/rebuild_v7_log.txt");
        f.encoding = "UTF-8"; f.open("a"); f.write(msg + "\\n"); f.close();
    } catch(e) {}
}

function setEasing(prop) {
    if (!prop) return;
    try {
        for (var k = 1; k <= prop.numKeys; k++) {
            prop.setInterpolationTypeAtKey(k, KeyframeInterpolationType.BEZIER, KeyframeInterpolationType.BEZIER);
        }
    } catch(e) {}
}

app.beginUndoGroup("一拳超人完整重构v7");

try {
    log("========================================");
    log("一拳超人完整重构 v7");
    log("时间: " + new Date().toString());
    log("AE版本: " + app.version);
    log("========================================");

    var frameDir = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/frames";
    var compW = 576, compH = 768, compDur = 12, compFps = 30;
    var numFrames = 18;

    var toRemove = [];
    for (var i = app.project.numItems; i >= 1; i--) {
        var item = app.project.item(i);
        if (item instanceof CompItem) {
            if (item.name.indexOf("一拳超人_埼玉") >= 0 || item.name == "FrameSeq") {
                toRemove.push({item: item, name: item.name});
            }
        }
    }
    for (var j = 0; j < toRemove.length; j++) {
        try { toRemove[j].item.remove(); log("  删除: " + toRemove[j].name); } catch(e) {}
    }

    var comp = app.project.items.addComp("一拳超人_埼玉_重构版_v26", compW, compH, 1, compDur, compFps);
    comp.motionBlur = true;
    comp.bgColor = [0, 0, 0];
    log("  主合成: " + comp.name);

    var frameFootages = [];
    for (var f = 1; f <= numFrames; f++) {
        var num = f < 10 ? "00" + f : (f < 100 ? "0" + f : "" + f);
        var fp = new File(frameDir + "/frame_" + num + ".png");
        if (fp.exists) {
            var importOpts = new ImportOptions(fp);
            importOpts.sequence = false;
            var footage = app.project.importFile(importOpts);
            footage.name = "Frame_" + num;
            frameFootages.push(footage);
        }
    }
    log("  总导入帧数: " + frameFootages.length);

    // 创建顺序: 从下到上
    // 最底层: Sky_BG
    var sky = comp.layers.addSolid([0.02, 0.02, 0.08], "Sky_BG", compW, compH, 1, compDur);
    sky.threeDLayer = false;
    try {
        var ramp = sky.property("ADBE Effect Parade").addProperty("ADBE Ramp");
        ramp.property(1).setValue([compW/2, 100]);
        ramp.property(2).setValue([0.05, 0.05, 0.15]);
        ramp.property(3).setValue([compW/2, compH - 68]);
        ramp.property(4).setValue([0.01, 0.01, 0.03]);
        ramp.property(5).setValue(1);
        ramp.property(6).setValue(0);
    } catch(e) {}
    log("  Sky_BG OK");

    // 背景粒子
    function createParticle(name, color, z, birth, longevity, vel) {
        var solid = comp.layers.addSolid(color, name, compW, compH, 1, compDur);
        solid.threeDLayer = true;
        solid.motionBlur = true;
        try { solid.property("ADBE Transform Group").property("ADBE Position").setValue([compW/2, compH/2, z]); } catch(e) {}
        try {
            var pw = solid.property("ADBE Effect Parade").addProperty("CC Particle World");
            pw.property(14).setValue(birth);
            pw.property(15).setValue(longevity);
            pw.property(26).setValue(vel);
            try { pw.property(10).setValue(0.3); pw.property(12).setValue(1); } catch(e) {}
        } catch(e) {}
        return solid;
    }
    var pBG = createParticle("P_BG", [0.05, 0.05, 0.1], 800, 0.3, 3.0, 0.01);
    var pMID = createParticle("P_MID", [0.1, 0.1, 0.15], 200, 0.8, 2.0, 0.03);
    log("  背景粒子 OK");

    // 主体帧图层
    var mainFrameLayers = [];
    var frameSchedule = [
        {start: 0, end: 1.2}, {start: 1.2, end: 2.4}, {start: 2.4, end: 3.4}, {start: 3.4, end: 4.2},
        {start: 4.2, end: 4.8}, {start: 4.8, end: 5.3}, {start: 5.3, end: 5.7}, {start: 5.7, end: 6.0},
        {start: 6.0, end: 6.3}, {start: 6.3, end: 6.55}, {start: 6.55, end: 6.75}, {start: 6.75, end: 6.9},
        {start: 6.9, end: 7.1}, {start: 7.1, end: 7.3}, {start: 7.3, end: 7.7}, {start: 7.7, end: 8.5},
        {start: 8.5, end: 10.0}, {start: 10.0, end: 12.0}
    ];

    for (var i = 0; i < frameFootages.length; i++) {
        var layer = comp.layers.add(frameFootages[i]);
        layer.name = "Saitama_Frame_" + (i + 1);
        layer.enabled = true;
        layer.motionBlur = true;
        try {
            layer.property("ADBE Transform Group").property("ADBE Position").setValue([compW/2, compH/2]);
            layer.property("ADBE Transform Group").property("ADBE Scale").setValue([100, 100]);
            layer.property("ADBE Transform Group").property("ADBE Opacity").setValue(100);
        } catch(e) {}
        layer.inPoint = frameSchedule[i].start;
        layer.outPoint = frameSchedule[i].end;

        try {
            var ck = layer.property("ADBE Effect Parade").addProperty("ADBE Color Key");
            ck.property(2).setValue(30);
            ck.property(1).setValue([0.1, 0.6, 0.2]);
            ck.property(3).setValue(0);
            ck.property(4).setValue(2);
        } catch(e) {}
        try {
            var mc = layer.property("ADBE Effect Parade").addProperty("ADBE Matte Choker");
            mc.property(2).setValue(5);
            mc.property(5).setValue(3);
        } catch(e) {}
        try {
            var glow = layer.property("ADBE Effect Parade").addProperty("ADBE Glo2");
            glow.property(1).setValue(1);
            glow.property(2).setValue(80);
            glow.property(3).setValue(2.5);
            glow.property(4).setValue(1.2);
        } catch(e) {}
        try {
            var tint = layer.property("ADBE Effect Parade").addProperty("ADBE Tint");
            tint.property(1).setValue([0.1, 0.15, 0.3]);
            tint.property(2).setValue([0.8, 0.85, 1.0]);
            tint.property(3).setValue(15);
        } catch(e) {}
        mainFrameLayers.push(layer);
    }
    log("  18帧主体图层 OK");

    // 前景粒子
    var pFG = createParticle("P_FG", [0.15, 0.15, 0.2], -100, 1.5, 1.2, 0.06);
    log("  前景粒子 OK");

    // 雾气层 (Screen模式)
    var fog = comp.layers.addSolid([0.5, 0.5, 0.5], "Fog_Overlay", compW, compH, 1, compDur);
    fog.threeDLayer = false;
    try {
        fog.property("ADBE Transform Group").property("ADBE Opacity").setValue(25);
        var fn = fog.property("ADBE Effect Parade").addProperty("ADBE Fractal Noise");
        fn.property(1).setValue(6);
        fn.property(2).setValue(1);
        fn.property(8).setValue(200);
        fog.property("ADBE Blend Mode").setValue(3);
    } catch(e) {}
    log("  Fog_Overlay OK (Screen)");

    // 暗角层 (Multiply模式)
    var vig = comp.layers.addSolid([0, 0, 0], "Vignette", compW, compH, 1, compDur);
    vig.threeDLayer = false;
    try {
        vig.property("ADBE Transform Group").property("ADBE Opacity").setValue(40);
        var vigRamp = vig.property("ADBE Effect Parade").addProperty("ADBE Ramp");
        vigRamp.property(1).setValue([compW/2, compH/2]);
        vigRamp.property(2).setValue([0, 0, 0]);
        vigRamp.property(3).setValue([compW/2, 0]);
        vigRamp.property(4).setValue([1, 1, 1]);
        vigRamp.property(5).setValue(1);
        vig.property("ADBE Blend Mode").setValue(1);
    } catch(e) {}
    log("  Vignette OK (Multiply)");

    // 调色调整层
    var adj = comp.layers.addSolid([0.5, 0.5, 0.5], "Color_Adjust", compW, compH, 1, compDur);
    adj.adjustmentLayer = true;
    try {
        var bc = adj.property("ADBE Effect Parade").addProperty("ADBE Brightness & Contrast 2");
        bc.property(1).setValue(5);
        bc.property(2).setValue(10);
        var hue = adj.property("ADBE Effect Parade").addProperty("ADBE HUE SATURATION");
        hue.property(1).setValue(1);
        hue.property(3).setValue(0);
        hue.property(4).setValue(15);
        hue.property(5).setValue(10);
    } catch(e) {}
    log("  Color_Adjust OK");

    // 摄像机
    var cam = comp.layers.addCamera("Main_Camera", [compW/2, compH/2]);
    try {
        var camOpts = cam.property("ADBE Camera Options Group");
        camOpts.property(1).setValue(800);
        camOpts.property(2).setValue(1);
        camOpts.property(3).setValue(350);
        camOpts.property(4).setValue(8.0);
        camOpts.property(5).setValue(120);
        var camPos = cam.property("ADBE Transform Group").property("ADBE Position");
        camPos.setValueAtTime(0, [compW/2, compH/2, -600]);
        camPos.setValueAtTime(4, [compW/2, compH/2, -480]);
        camPos.setValueAtTime(7, [compW/2 + 15, compH/2 - 8, -530]);
        camPos.setValueAtTime(8, [compW/2 + 20, compH/2 - 12, -550]);
        camPos.setValueAtTime(12, [compW/2, compH/2, -600]);
        setEasing(camPos);
    } catch(e) {}
    log("  Camera OK");

    // 控制器
    var ctrlBG = comp.layers.addNull();
    ctrlBG.name = "Ctrl_Background";
    ctrlBG.property("ADBE Effect Parade").addProperty("ADBE Slider Control").name = "Brightness";
    ctrlBG.property("ADBE Effect Parade").property(1).property(1).setValue(100);
    ctrlBG.property("ADBE Effect Parade").addProperty("ADBE Slider Control").name = "Fog";
    ctrlBG.property("ADBE Effect Parade").property(2).property(1).setValue(100);

    var ctrlPart = comp.layers.addNull();
    ctrlPart.name = "Ctrl_Particles";
    ctrlPart.property("ADBE Effect Parade").addProperty("ADBE Slider Control").name = "Amount";
    ctrlPart.property("ADBE Effect Parade").property(1).property(1).setValue(100);
    ctrlPart.property("ADBE Effect Parade").addProperty("ADBE Slider Control").name = "Speed";
    ctrlPart.property("ADBE Effect Parade").property(2).property(1).setValue(100);

    var ctrlCam = comp.layers.addNull();
    ctrlCam.name = "Ctrl_Camera";
    ctrlCam.threeDLayer = true;
    ctrlCam.property("ADBE Transform Group").property("ADBE Position").setValue([compW/2, compH/2, -600]);
    cam.parent = ctrlCam;
    var camCtrlPos = ctrlCam.property("ADBE Transform Group").property("ADBE Position");
    camCtrlPos.setValueAtTime(0, [compW/2, compH/2, -600]);
    camCtrlPos.setValueAtTime(4, [compW/2, compH/2, -480]);
    camCtrlPos.setValueAtTime(7, [compW/2 + 15, compH/2 - 8, -530]);
    camCtrlPos.setValueAtTime(8, [compW/2 + 20, compH/2 - 12, -550]);
    camCtrlPos.setValueAtTime(12, [compW/2, compH/2, -600]);
    setEasing(camCtrlPos);

    var ctrlSaitama = comp.layers.addNull();
    ctrlSaitama.name = "Ctrl_Saitama";
    ctrlSaitama.property("ADBE Transform Group").property("ADBE Position").setValue([compW/2, compH/2]);
    ctrlSaitama.property("ADBE Effect Parade").addProperty("ADBE Slider Control").name = "Scale";
    ctrlSaitama.property("ADBE Effect Parade").property(1).property(1).setValue(100);
    ctrlSaitama.property("ADBE Effect Parade").addProperty("ADBE Slider Control").name = "Glow";
    ctrlSaitama.property("ADBE Effect Parade").property(2).property(1).setValue(100);
    ctrlSaitama.property("ADBE Effect Parade").addProperty("ADBE Angle Control").name = "Rotation";
    ctrlSaitama.property("ADBE Effect Parade").property(3).property(1).setValue(0);

    for (var i = 0; i < mainFrameLayers.length; i++) {
        mainFrameLayers[i].parent = ctrlSaitama;
    }
    for (var i = 0; i < mainFrameLayers.length; i++) {
        try { mainFrameLayers[i].property("ADBE Transform Group").property("ADBE Scale").expression = "var s = thisComp.layer(\\'Ctrl_Saitama\\').effect(\\'Scale\\')(1); [s, s]"; } catch(e) {}
        try { mainFrameLayers[i].property("ADBE Transform Group").property("ADBE Rotation").expression = "thisComp.layer(\\'Ctrl_Saitama\\').effect(\\'Rotation\\')(1)"; } catch(e) {}
    }

    var ctrlGlobal = comp.layers.addNull();
    ctrlGlobal.name = "Ctrl_Global";
    ctrlGlobal.property("ADBE Effect Parade").addProperty("ADBE Slider Control").name = "Speed";
    ctrlGlobal.property("ADBE Effect Parade").property(1).property(1).setValue(100);
    ctrlGlobal.property("ADBE Effect Parade").addProperty("ADBE Slider Control").name = "FX_Intensity";
    ctrlGlobal.property("ADBE Effect Parade").property(2).property(1).setValue(100);
    log("  控制器 OK");

    // 表达式链接
    try { sky.property("ADBE Transform Group").property("ADBE Opacity").expression = "thisComp.layer(\\'Ctrl_Background\\').effect(\\'Brightness\\')(1)"; } catch(e) {}
    try { fog.property("ADBE Transform Group").property("ADBE Opacity").expression = "thisComp.layer(\\'Ctrl_Background\\').effect(\\'Fog\\')(1) * 0.3"; } catch(e) {}
    try { vig.property("ADBE Transform Group").property("ADBE Opacity").expression = "thisComp.layer(\\'Ctrl_Global\\').effect(\\'FX_Intensity\\')(1) * 0.4"; } catch(e) {}
    log("  表达式链接 OK");

    // 主体动画
    var sPos = ctrlSaitama.property("ADBE Transform Group").property("ADBE Position");
    sPos.setValueAtTime(0, [compW/2, compH/2]);
    sPos.setValueAtTime(4, [compW/2, compH/2 - 15]);
    sPos.setValueAtTime(7, [compW/2 + 10, compH/2 - 5]);
    sPos.setValueAtTime(8, [compW/2 + 15, compH/2]);
    sPos.setValueAtTime(12, [compW/2, compH/2]);
    setEasing(sPos);
    log("  主体动画 OK");

    // 工作区域
    comp.workAreaStart = 0;
    comp.workAreaDuration = compDur;

    // 验证
    log("\\n[验证] 最终图层顺序 (索引1=最顶层):");
    for (var j = 1; j <= comp.numLayers; j++) {
        var L = comp.layer(j);
        var type = L.nullLayer ? "[NULL]" : (L.adjustmentLayer ? "[ADJ]" : (L.cameraLayer ? "[CAM]" : (L.threeDLayer ? "[3D]" : "[2D]")));
        var blend = "";
        try {
            var bm = L.property("ADBE Blend Mode").value;
            var modes = ["Normal", "Multiply", "Screen"];
            blend = " [" + (modes[bm] || bm) + "]";
        } catch(e) {}
        log("  [" + j + "] " + type + " " + L.name + blend);
    }

    log("\\n========================================");
    log("一拳超人完整重构v7完成!");
    log("总层数: " + comp.numLayers);
    log("========================================");

} catch (err) {
    log("[FATAL ERROR] " + err.toString());
}

app.endUndoGroup();
""".strip()

command = {
    "command": "executeAtomScript",
    "description": "一拳超人重构v7 - 按正确顺序创建图层",
    "script": script_content,
    "timestamp": "2026-07-08T12:30:00.000Z",
    "processed": False
}

with open("C:/Users/Administrator/Desktop/AE-Knowledge-Vault/ae_command.json", "w", encoding="utf-8") as f:
    json.dump(command, f, ensure_ascii=False, indent=2)

print("Command file written successfully!")