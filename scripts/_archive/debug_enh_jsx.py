#!/usr/bin/env python3
"""调试增强版JSX - 逐步测试"""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"

def send(code, wait=20):
    BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": datetime.now().isoformat(), "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.5)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") != "waiting" and "result" in r:
                return r
        except:
            pass
    return {"error": "timeout"}

# 测试1: 简化版增强JSX
jsx = '''(function() {
    try {
        for (var i = app.project.items.length; i >= 1; i--) {
            if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "ENH_test") {
                app.project.item(i).remove();
            }
        }
        var dur = 3.0;
        var c = app.project.items.addComp("ENH_test", 1920, 1080, 1, dur, 30);
        c.bgColor = [0.01, 0.01, 0.03];
        
        var L = c.layers.addText("3D TITLE");
        L.name = "Title";
        L.threeDLayer = true;
        L.property('Position').setValue([960, 540, 0]);
        var td = L.property('ADBE Text Properties').property('ADBE Text Document');
        var doc = td.value;
        doc.font = "Impact";
        doc.fontSize = 180;
        doc.fillColor = [0.92, 0.94, 0.98];
        doc.justification = ParagraphJustification.CENTER_JUSTIFY;
        td.setValue(doc);
        
        var mo = L.property('ADBE Material Options Group');
        mo.property('ADBE Specular Coefficient').setValue(100);
        mo.property('ADBE Shininess Coefficient').setValue(95);
        mo.property('ADBE Metal Coefficient').setValue(100);
        mo.property('ADBE Diffuse Coefficient').setValue(14);
        mo.property('ADBE Ambient Coefficient').setValue(4);
        mo.property('ADBE Casts Shadows').setValue(1);
        mo.property('ADBE Accepts Lights').setValue(1);
        L.motionBlur = true;
        
        // Z-stack
        var nDepth = 16;
        var spacing = 7.2;
        for (var d = 1; d < nDepth; d++) {
            var copy = L.duplicate();
            copy.name = 'Title_depth_' + d;
            copy.threeDLayer = true;
            copy.property('Position').setValue([960, 540, d * spacing]);
            var darkF = Math.max(0.02, 1.0 - d / (nDepth * 1.02));
            try {
                var tdc = copy.property('ADBE Text Properties').property('ADBE Text Document');
                var docc = tdc.value;
                docc.fillColor = [0.92 * darkF, 0.94 * darkF, 0.98 * darkF];
                tdc.setValue(docc);
            } catch(e2) {}
            copy.moveAfter(L);
        }
        
        // Parent null
        var ctrl = c.layers.addNull(dur);
        ctrl.name = 'ctrl_3d';
        ctrl.threeDLayer = true;
        ctrl.property('Position').setValue([960, 540, 0]);
        for (var li = 1; li <= c.numLayers; li++) {
            var lyr = c.layer(li);
            if (lyr.name === 'Title' || lyr.name.indexOf('Title_depth_') === 0) {
                lyr.parent = ctrl;
            }
        }
        
        // Entrance
        ctrl.property('Scale').setValueAtTime(0, [78, 78, 78]);
        ctrl.property('Scale').setValueAtTime(dur * 0.35, [100, 100, 100]);
        try {
            ctrl.property('Scale').setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 92), new KeyframeEase(0, 92), new KeyframeEase(0, 92)],
                [new KeyframeEase(0, 60), new KeyframeEase(0, 60), new KeyframeEase(0, 60)]);
        } catch(eEase) {}
        
        // Camera with Z push
        var cam = c.layers.addCamera('EnhCam', [960, 540]);
        cam.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
        var camPos = cam.property('Position');
        camPos.setValueAtTime(0, [960, 480, -2200]);
        camPos.setValueAtTime(dur * 0.85, [960, 520, -1200]);
        try {
            camPos.setTemporalEaseAtKey(1,
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100), new KeyframeEase(0, 100)],
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100), new KeyframeEase(0, 100)]);
            camPos.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 75), new KeyframeEase(0, 75), new KeyframeEase(0, 75)],
                [new KeyframeEase(0, 75), new KeyframeEase(0, 75), new KeyframeEase(0, 75)]);
        } catch(eCam) {}
        cam.property('X Rotation').setValue(-11);
        
        // Lights
        var keyLight = c.layers.addLight('KeyLight', [960, 200]);
        keyLight.lightType = LightType.POINT;
        keyLight.property('Position').setValue([1100, 180, -700]);
        var klOpts = keyLight.property('ADBE Light Options Group');
        klOpts.property('ADBE Light Intensity').setValue(546);
        klOpts.property('ADBE Light Color').setValue([1.0, 0.97, 0.90]);
        klOpts.property('ADBE Light Falloff Type').setValue(1);
        klOpts.property('ADBE Light Falloff Start').setValue(50);
        klOpts.property('ADBE Light Falloff Distance').setValue(2600);
        
        var rimLight = c.layers.addLight('RimLight', [1600, 300]);
        rimLight.lightType = LightType.POINT;
        rimLight.property('Position').setValue([1650, 280, 700]);
        var rlOpts = rimLight.property('ADBE Light Options Group');
        rlOpts.property('ADBE Light Intensity').setValue(280);
        rlOpts.property('ADBE Light Color').setValue([0.6, 0.7, 1.0]);
        rlOpts.property('ADBE Light Falloff Type').setValue(1);
        rlOpts.property('ADBE Light Falloff Start').setValue(60);
        rlOpts.property('ADBE Light Falloff Distance').setValue(3000);
        
        var amb = c.layers.addLight('Amb', [960, 540]);
        amb.lightType = LightType.AMBIENT;
        amb.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(4);
        
        return JSON.stringify({status:"success", comp:"ENH_test", layers:c.numLayers});
    } catch(e) {
        return JSON.stringify({status:"error", msg:e.toString(), line:e.line});
    }
})();'''

print("发送增强版JSX...")
r = send(jsx, 30)
print(f"Raw result: {json.dumps(r, indent=2, ensure_ascii=False)[:800]}")
