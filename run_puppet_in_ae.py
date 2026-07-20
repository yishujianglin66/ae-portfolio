import json
import os
import time

CMD_FILE = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json"
RES_FILE = "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_mcp_result.json"

os.makedirs(os.path.dirname(CMD_FILE), exist_ok=True)

def write_command(op, params):
    cmd = {
        "command": op,
        "args": params,
        "status": "pending",
        "timestamp": time.time()
    }
    with open(CMD_FILE, "w", encoding="utf-8") as f:
        json.dump(cmd, f, ensure_ascii=False, separators=(",", ":"))
    return cmd

def read_result(timeout=60, poll_interval=0.5):
    start = time.time()
    while time.time() - start < timeout:
        try:
            with open(RES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception:
            pass
        time.sleep(poll_interval)
    return {"status": "timeout", "error": f"Timeout after {timeout}s"}

jsx_code = '''
(function() {
    var _result = {};
    try {
        var proj = app.project;
        if (!proj) {
            proj = app.newProject();
        }

        for (var i = proj.items.length; i >= 1; i--) {
            if (proj.items[i] instanceof CompItem) {
                proj.items[i].remove();
            }
        }

        var comp = proj.items.addComp("壮壮木偶_托尔芬", 1080, 1920, 1, 8, 30);
        comp.bgColor = [0.05, 0.05, 0.05];

        var folders = [
            "D:/AE-Work/style_copy/puppet_style/source_frames/托尔芬特写",
            "D:/AE-Work/style_copy/puppet_style/source_frames/冰海战记",
            "D:/AE-Work/style_copy/puppet_style/source_frames/冰海战记120fps"
        ];

        var currentTime = 0;
        var frameDuration = 0.6;
        var importedFrames = 0;

        for (var f = 0; f < folders.length; f++) {
            var folderName = folders[f].split("/").pop();
            for (var i = 1; i <= 8; i++) {
                var filePath = folders[f] + "/frame_" + ("00" + i).slice(-3) + ".jpg";
                var file = new File(filePath);
                if (file.exists) {
                    var importOptions = new ImportOptions(file);
                    var footage = proj.importFile(importOptions);
                    var layer = comp.layers.add(footage);
                    layer.name = folderName + "_" + i;
                    layer.startTime = currentTime;
                    layer.outPoint = currentTime + frameDuration;
                    currentTime += frameDuration;
                    importedFrames++;
                }
            }
        }

        var adj1 = comp.layers.addSolid([0.5, 0.5, 0.5], "调色-冷色调", 1080, 1920, 1, 8);
        adj1.adjustmentLayer = true;
        adj1.name = "01_调色_冷色调";

        var curves = adj1.Effects.addProperty("ADBE Curve");
        var curveData = curves.property("ADBE Curve-0002");
        curveData.setValue("RgbCurves24{0.0,0.05,0.25,0.2,0.5,0.55,0.75,0.8,1.0,1.0}");

        var hueSat = adj1.Effects.addProperty("ADBE HUE SATURATION");
        hueSat.property("ADBE HUE SATURATION-0008").setValue(-30);

        var colorBalance = adj1.Effects.addProperty("ADBE Color Balance");
        colorBalance.property("ADBE Color Balance-0006").setValue(25);
        colorBalance.property("ADBE Color Balance-0009").setValue(20);

        var adj2 = comp.layers.addSolid([0.5, 0.5, 0.5], "抽帧", 1080, 1920, 1, 8);
        adj2.adjustmentLayer = true;
        adj2.name = "02_抽帧_8fps";
        var posterize = adj2.Effects.addProperty("ADBE Posterize Time");
        posterize.property("ADBE Posterize Time-0001").setValue(8);

        var adj3 = comp.layers.addSolid([0.5, 0.5, 0.5], "颗粒", 1080, 1920, 1, 8);
        adj3.adjustmentLayer = true;
        adj3.name = "03_颗粒_胶片";
        var noise = adj3.Effects.addProperty("ADBE Noise");
        noise.property("ADBE Noise-0001").setValue(12);
        noise.property("ADBE Noise-0002").setValue(0);

        var vignette = comp.layers.addSolid([0, 0, 0], "暗角", 1080, 1920, 1, 8);
        vignette.name = "04_暗角";
        var mask = vignette.Masks.addMask();
        mask.maskMode = MaskMode.SUBTRACT;
        var shape = mask.maskShape.value;
        shape.vertices = [[162, 288], [918, 288], [918, 1632], [162, 1632]];
        shape.inTangents = [[0,0],[0,0],[0,0],[0,0]];
        shape.outTangents = [[0,0],[0,0],[0,0],[0,0]];
        shape.closed = true;
        mask.maskShape.setValue(shape);
        mask.maskFeather.setValue([400, 400]);
        vignette.opacity.setValue(55);

        var textLayer = comp.layers.addText("杀戮不意味着活着");
        textLayer.name = "字幕_标题";
        var textProp = textLayer.property("Source Text");
        var textDoc = textProp.value;
        textDoc.font = "Microsoft YaHei";
        textDoc.fontSize = 60;
        textDoc.fillColor = [1, 1, 1];
        textDoc.strokeColor = [0, 0, 0];
        textDoc.strokeWidth = 3;
        textProp.setValue(textDoc);
        textLayer.position.setValue([540, 1750]);
        textLayer.startTime = 0;
        textLayer.outPoint = 4;

        var textLayer2 = comp.layers.addText("托尔芬，放下你的仇恨");
        textLayer2.name = "字幕_副标题";
        var textProp2 = textLayer2.property("Source Text");
        var textDoc2 = textProp2.value;
        textDoc2.font = "Microsoft YaHei";
        textDoc2.fontSize = 45;
        textDoc2.fillColor = [0.9, 0.9, 0.9];
        textDoc2.strokeColor = [0, 0, 0];
        textDoc2.strokeWidth = 2;
        textProp2.setValue(textDoc2);
        textLayer2.position.setValue([540, 1820]);
        textLayer2.startTime = 4;
        textLayer2.outPoint = 8;

        textLayer.Effects.addProperty("ADBE Typewriter").property("ADBE Typewriter-0001").setValue(0);
        textLayer.Effects.property("ADBE Typewriter-0001").setKeyframeAtTime(0, 0);
        textLayer.Effects.property("ADBE Typewriter-0001").setKeyframeAtTime(2, 100);

        textLayer.property("Transform").property("Rotation").expression = "wiggle(3, 0.5)";

        var savePath = "D:/AE-Work/style_copy/puppet_style/壮壮木偶_托尔芬.aep";
        proj.save(new File(savePath));

        _result = {
            status: "success",
            compName: comp.name,
            framesImported: importedFrames,
            layersCount: comp.numLayers,
            savedPath: savePath,
            message: "壮壮木偶风格工程创建完成"
        };
    } catch(e) {
        _result = {status:"error", message:e.toString(), line:e.line};
    }
    return JSON.stringify(_result);
})();
'''

print("发送命令到AE...")
write_command("executeAtomScript", {"scriptContent": jsx_code})
result = read_result(timeout=120)
print("执行结果:", json.dumps(result, ensure_ascii=False, indent=2))
