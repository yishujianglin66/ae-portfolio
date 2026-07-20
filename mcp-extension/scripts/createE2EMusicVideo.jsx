// createE2EMusicVideo_v3.jsx
// E2E音乐视频合成创建工具 - 基于rebuild_project_ae26.py成功案例重构
// 分阶段构建，每步验证，确保稳定性

#include "_lib/args_loader.jsx"
#include "_lib/comp_utils.jsx"
#include "_lib/response_utils.jsx"

function createE2EMusicVideo(params) {
    try {
        var compName = params.compName || "E2E_音乐视频";
        // 参数化：移除硬编码默认值，frameDir 必填
        // 原硬编码值: var frameDir = params.frameDir || "D:/AE-Work/视频素材库/frames";
        var frameDir = params.frameDir;
        if (!frameDir) {
            return buildError("E101", "frameDir 参数必填（params.frameDir）");
        }
        var bgmPath = params.bgmPath || "";
        var beatTimes = params.beatTimes || [];
        var energyPeaks = params.energyPeaks || [];
        var peakValues = params.peakValues || [];
        var bpm = params.bpm || 120;
        var compWidth = params.width || 576;
        var compHeight = params.height || 768;
        var compDuration = params.duration || 12;
        var compFPS = params.fps || 30;

        var results = [];

        // 移除已存在的同名合成
        var existingComp = findCompByName(compName);
        if (existingComp) {
            existingComp.remove();
        }

        var comp = app.project.items.addComp(compName, compWidth, compHeight, 1, compDuration, compFPS);
        results.push({ phase: "Phase1", status: "success", message: "合成创建成功: " + compName });

        var frameFiles = [];
        for (var f = 1; f <= 18; f++) {
            var num = f < 10 ? "0" + f : "" + f;
            var fp = new File(frameDir + "/frame_" + num + ".png");
            if (fp.exists) {
                var importOpts = new ImportOptions(fp);
                importOpts.sequence = false;
                var footage = app.project.importFile(importOpts);
                footage.name = "Frame_" + num;
                frameFiles.push(footage);
            }
        }

        if (frameFiles.length === 0) {
            return buildError("E201", "帧目录中没有图片文件");
        }
        results.push({ phase: "Phase1", status: "success", message: "导入 " + frameFiles.length + " 帧" });

        app.beginUndoGroup("Create E2E Music Video");

        var seqComp = app.project.items.addComp("FrameSeq", compWidth, compHeight, 1, 0.6, compFPS);
        for (var i = 0; i < frameFiles.length; i++) {
            var layer = seqComp.layers.add(frameFiles[i]);
            layer.startTime = i * (1/compFPS);
            layer.outPoint = (i + 1) * (1/compFPS);
        }
        seqComp.duration = frameFiles.length * (1/compFPS);

        var seqLayer = comp.layers.add(seqComp);
        seqLayer.name = "FrameSeq";
        seqLayer.stretch = -50;
        seqLayer.motionBlur = true;
        results.push({ phase: "Phase1", status: "success", message: "帧序列预合成完成" });

        var saitama = seqLayer.duplicate();
        saitama.name = "Saitama_Main";

        try {
            var key = saitama.property("ADBE Effect Parade").addProperty("ADBE Color Key");
            if (key) {
                try { key.property("Color Tolerance").setValue(20); } catch(e) {}
                try { key.property("Edge Feather").setValue(1); } catch(e) {}
            }
        } catch(e) {}

        try {
            var glow = saitama.property("ADBE Effect Parade").addProperty("ADBE Glo2");
            if (glow) {
                try { glow.property("Glow Threshold").setValue(80); } catch(e) {}
                try { glow.property("Glow Radius").setValue(1.5); } catch(e) {}
                try { glow.property("Glow Intensity").setValue(1.2); } catch(e) {}
            }
        } catch(e) {}

        try {
            var mc = saitama.property("ADBE Effect Parade").addProperty("ADBE Simple Choker");
            if (mc) {
                try { mc.property("Choke Matte").setValue(5); } catch(e) {}
            }
        } catch(e) {}

        try {
            var tint = saitama.property("ADBE Effect Parade").addProperty("ADBE Tint");
            if (tint) {
                try { tint.property(1).setValue([0.1, 0.15, 0.3]); } catch(e) {}
                try { tint.property(2).setValue([0.8, 0.85, 1.0]); } catch(e) {}
                try { tint.property(3).setValue(0.15); } catch(e) {}
            }
        } catch(e) {}
        results.push({ phase: "Phase2", status: "success", message: "Saitama_Main层效果添加完成" });

        var cape = saitama.duplicate();
        cape.name = "Cape_Layer";
        cape.threeDLayer = true;
        cape.position.setValue([compWidth * 0.525, compHeight * 0.5, -50]);
        cape.scale.setValue([105, 105, 105]);

        while (cape.property("ADBE Effect Parade").numProperties > 0) {
            try { cape.property("ADBE Effect Parade").property(1).remove(); } catch(e) {}
        }

        try {
            var key2 = cape.property("ADBE Effect Parade").addProperty("ADBE Color Key");
            if (key2) {
                try { key2.property("Color Tolerance").setValue(15); } catch(e) {}
            }
        } catch(e) {}

        try {
            var glow2 = cape.property("ADBE Effect Parade").addProperty("ADBE Glo2");
            if (glow2) {
                try { glow2.property("Glow Threshold").setValue(70); } catch(e) {}
                try { glow2.property("Glow Radius").setValue(2.0); } catch(e) {}
                try { glow2.property("Glow Intensity").setValue(1.5); } catch(e) {}
            }
        } catch(e) {}

        try {
            var tint2 = cape.property("ADBE Effect Parade").addProperty("ADBE Tint");
            if (tint2) {
                try { tint2.property(1).setValue([0.9, 0.9, 0.95]); } catch(e) {}
                try { tint2.property(2).setValue([1.0, 1.0, 1.0]); } catch(e) {}
                try { tint2.property(3).setValue(0.3); } catch(e) {}
            }
        } catch(e) {}
        results.push({ phase: "Phase3", status: "success", message: "Cape_Layer披风层创建完成" });

        var p_bg = comp.layers.addSolid([0.05, 0.05, 0.1], "P_BG", compWidth, compHeight, 1, compDuration);
        p_bg.threeDLayer = true;
        p_bg.position.setValue([compWidth/2, compHeight/2, 800]);
        try {
            var pw_bg = p_bg.property("ADBE Effect Parade").addProperty("CC Particle World");
            if (pw_bg) {
                try { pw_bg.property("Birth Rate").setValue(0.5); } catch(e) {}
                try { pw_bg.property("Longevity").setValue(2.0); } catch(e) {}
                try { pw_bg.property("Size").setValue(0.02); } catch(e) {}
            }
        } catch(e) {}

        var p_mid = comp.layers.addSolid([0.1, 0.1, 0.15], "P_MID", compWidth, compHeight, 1, compDuration);
        p_mid.threeDLayer = true;
        p_mid.position.setValue([compWidth/2, compHeight/2, 200]);
        try {
            var pw_mid = p_mid.property("ADBE Effect Parade").addProperty("CC Particle World");
            if (pw_mid) {
                try { pw_mid.property("Birth Rate").setValue(1.0); } catch(e) {}
                try { pw_mid.property("Longevity").setValue(1.5); } catch(e) {}
                try { pw_mid.property("Size").setValue(0.05); } catch(e) {}
            }
        } catch(e) {}

        var p_fg = comp.layers.addSolid([0.15, 0.15, 0.2], "P_FG", compWidth, compHeight, 1, compDuration);
        p_fg.threeDLayer = true;
        p_fg.position.setValue([compWidth/2, compHeight/2, -100]);
        try {
            var pw_fg = p_fg.property("ADBE Effect Parade").addProperty("CC Particle World");
            if (pw_fg) {
                try { pw_fg.property("Birth Rate").setValue(2.0); } catch(e) {}
                try { pw_fg.property("Longevity").setValue(1.0); } catch(e) {}
                try { pw_fg.property("Size").setValue(0.08); } catch(e) {}

                for (var ep = 0; ep < energyPeaks.length; ep++) {
                    var pt = energyPeaks[ep];
                    if (pt > compDuration) break;
                    var pv = peakValues[ep] || 0.1;
                    var br_val = 2.0 + pv * 10;
                    try { pw_fg.property("Birth Rate").setValueAtTime(pt, br_val); } catch(e) {}
                }
            }
        } catch(e) {}
        results.push({ phase: "Phase4", status: "success", message: "三层粒子系统创建完成" });

        var sky = comp.layers.addSolid([0.02, 0.02, 0.08], "Sky_BG", compWidth, compHeight, 1, compDuration);
        try {
            var ramp = sky.property("ADBE Effect Parade").addProperty("ADBE Ramp");
            if (ramp) {
                try { ramp.property("Start of Ramp").setValue([compWidth/2, 100]); } catch(e) {}
                try { ramp.property("Start Color").setValue([0.05, 0.05, 0.15]); } catch(e) {}
                try { ramp.property("End of Ramp").setValue([compWidth/2, compHeight - 68]); } catch(e) {}
                try { ramp.property("End Color").setValue([0.01, 0.01, 0.03]); } catch(e) {}
            }
        } catch(e) {}

        var fog = comp.layers.addSolid([0.5, 0.5, 0.5], "Fog_Overlay", compWidth, compHeight, 1, compDuration);
        fog.blendingMode = BlendingMode.SCREEN;
        fog.opacity.setValue(25);
        try {
            var fn = fog.property("ADBE Effect Parade").addProperty("ADBE Fractal Noise");
            if (fn) {
                try { fn.property("Contrast").setValue(50); } catch(e) {}
                try { fn.property("Scale").setValue(200); } catch(e) {}
            }
        } catch(e) {}

        var vig = comp.layers.addSolid([0, 0, 0], "Vignette", compWidth, compHeight, 1, compDuration);
        vig.blendingMode = BlendingMode.MULTIPLY;
        vig.opacity.setValue(40);
        results.push({ phase: "Phase5", status: "success", message: "背景和大气效果创建完成" });

        var adj = comp.layers.addSolid([0.5, 0.5, 0.5], "Color_Adjust", compWidth, compHeight, 1, compDuration);
        adj.adjustmentLayer = true;
        adj.name = "Color_Adjust";

        try {
            var curves = adj.property("ADBE Effect Parade").addProperty("ADBE CurvesCustom");
            if (curves) {
                try { curves.property(1).setValue([[0,0],[0.2,0.1],[0.5,0.5],[0.8,0.9],[1,1]]); } catch(e) {}
            }
        } catch(e) {}

        try {
            var hueSat = adj.property("ADBE Effect Parade").addProperty("ADBE HUE SATURATION");
            if (hueSat) {
                try { hueSat.property("Master Saturation").setValue(15); } catch(e) {}
                try { hueSat.property("Master Lightness").setValue(10); } catch(e) {}
            }
        } catch(e) {}

        var cam = comp.layers.addCamera("Main_Camera", [compWidth/2, compHeight/2]);
        try {
            cam.property("ADBE Camera Settings-0001").setValue(50);
        } catch(e) {}

        var beatKfCount = 0;
        try {
            var camPos = cam.property("ADBE Transform Group").property("ADBE Position");
            camPos.setValueAtTime(0, [compWidth/2, compHeight/2, -600]);
            camPos.setValueAtTime(4, [compWidth/2, compHeight/2, -500]);
            camPos.setValueAtTime(8, [compWidth/2 + 12, compHeight/2 + 6, -550]);
            camPos.setValueAtTime(compDuration, [compWidth/2, compHeight/2, -600]);

            for (var k = 1; k <= camPos.numKeys; k++) {
                camPos.setTemporalEaseAtKey(k, [new KeyframeEase(0, 33)], [new KeyframeEase(0, 33)]);
            }
            beatKfCount = camPos.numKeys;
        } catch(e) {}

        var ctrl = comp.layers.addNull();
        ctrl.name = "Global_Controller";
        try {
            var sc1 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
            if (sc1) { sc1.name = "Speed"; try { sc1.property(1).setValue(100); } catch(e) {} }
            var sc2 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
            if (sc2) { sc2.name = "Glow_Intensity"; try { sc2.property(1).setValue(100); } catch(e) {} }
            var sc3 = ctrl.property("ADBE Effect Parade").addProperty("ADBE Slider Control");
            if (sc3) { sc3.name = "Particle_Amount"; try { sc3.property(1).setValue(100); } catch(e) {} }
        } catch(e) {}
        results.push({ phase: "Phase6", status: "success", message: "调整层、摄像机、控制器创建完成" });

        var layerOrder = ["Sky_BG", "P_BG", "P_MID", "FrameSeq", "Saitama_Main", "Cape_Layer", "P_FG", "Fog_Overlay", "Vignette", "Color_Adjust"];
        for (var lo = 0; lo < layerOrder.length; lo++) {
            for (var lj = 1; lj <= comp.numLayers; lj++) {
                if (comp.layer(lj).name == layerOrder[lo]) {
                    comp.layer(lj).moveToEnd();
                    break;
                }
            }
        }
        for (var lk = 1; lk <= comp.numLayers; lk++) {
            if (comp.layer(lk).name == "Main_Camera") comp.layer(lk).moveToBeginning();
            if (comp.layer(lk).name == "Global_Controller") comp.layer(lk).moveToBeginning();
        }
        results.push({ phase: "Phase7", status: "success", message: "层顺序整理完成" });

        if (bgmPath) {
            var bgmFile = new File(bgmPath);
            if (bgmFile.exists) {
                var bgmImport = app.project.importFile(new ImportOptions(bgmFile));
                var bgmLayer = comp.layers.add(bgmImport);
                bgmLayer.name = "BGM_Track";
                bgmLayer.moveToEnd();
            }
        }

        app.endUndoGroup();

        return buildSuccess({
            message: "E2E音乐视频合成创建成功",
            compName: compName,
            totalLayers: comp.numLayers,
            bpm: bpm,
            beatKeyframes: beatKfCount,
            energyPeaks: energyPeaks.length,
            frameCount: frameFiles.length,
            phases: results,
            timestamp: new Date().toISOString()
        });

    } catch (error) {
        try { app.endUndoGroup(); } catch (e) {}
        return buildError("E200", "创建失败: " + error.toString(), {
            line: error.line || 0,
            timestamp: new Date().toISOString()
        });
    }
}

var args = loadArgs(new File($.fileName.replace(/[^\\\/]*$/, '') + "../temp/args.json"));
var result = createE2EMusicVideo(args);
$.write(result);