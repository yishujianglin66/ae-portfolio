#!/usr/bin/env python3
"""
基于OptimalComboEngine开发新预设 + 单独渲染验证
================================================
新预设方向:
1. oc_camera_impact - 摄像机冲击推进 (push_in_fast + impact_in)
2. oc_3d_depth_enhanced - 增强3D纵深 (flythrough + 大Z间距)
3. oc_speed_transition - 速度线转场预设 (speed_lines + hard_stop)

每个预设单独渲染3秒视频验证
"""
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
OUTPUT_DIR = Path(r"D:\AE-Work\output\new_presets")

sys.path.insert(0, str(ROOT))
from core.optimal_combo_engine import get_optimal_engine


def send_bridge(code, wait=30):
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge not found"}
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
    return {"success": False, "error": "timeout"}


def parse_result(r):
    inner = r.get("result", {})
    if isinstance(inner, dict):
        if inner.get("success") and "data" in inner:
            result_str = inner["data"].get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    if parsed.get("status") == "success":
                        return True, parsed
                    elif parsed.get("status") == "error":
                        return False, parsed.get("msg", parsed.get("error", "unknown"))
                except:
                    pass
            return True, result_str
        elif inner.get("success"):
            return True, "ok"
        elif "error" in inner:
            return False, inner["error"]
    return False, str(r)[:200]


def render_comp_to_mp4(comp_name, output_path, wait=120):
    """渲染合成到MP4"""
    out_unix = str(output_path).replace("\\", "/")
    jsx = f'''(function() {{
    try {{
        var comp = null;
        for (var i = 1; i <= app.project.items.length; i++) {{
            var it = app.project.item(i);
            if (it instanceof CompItem && it.name == "{comp_name}") {{ comp = it; break; }}
        }}
        if (!comp) return JSON.stringify({{status:"error", msg:"comp not found"}});
        var rq = app.project.renderQueue.items.add(comp);
        var om = rq.outputModule(1);
        var tpls = om.templates;
        var mp4Tpl = null;
        for (var t = 0; t < tpls.length; t++) {{
            if (tpls[t].toLowerCase().indexOf("h.264") >= 0 || tpls[t].toLowerCase().indexOf("mp4") >= 0) {{
                mp4Tpl = tpls[t]; break;
            }}
        }}
        if (mp4Tpl) om.applyTemplate(mp4Tpl);
        om.file = new File("{out_unix}");
        app.project.renderQueue.render();
        rq.remove();
        return JSON.stringify({{status:"success", file:"{out_unix}"}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg:e.toString()}});
    }}
}})();'''
    r = send_bridge(jsx, wait)
    return parse_result(r)


# ============================================================
# 新预设1: 摄像机冲击推进
# 基于调研: Z轴从-2800→-1000, impact_in缓动(92% influence), 急停
# ============================================================
def create_camera_impact():
    comp_name = "NEW_oc_camera_impact"
    jsx = '''(function() {
    try {
        for (var i = app.project.items.length; i >= 1; i--) {
            if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "''' + comp_name + '''") {
                app.project.item(i).remove();
            }
        }
        var dur = 3.0;
        var c = app.project.items.addComp("''' + comp_name + '''", 1920, 1080, 1, dur, 30);
        c.bgColor = [0.01, 0.01, 0.02];
        
        // 背景
        var bg = c.layers.addSolid([0,0,0], 'BG', 1920, 1080, 1, dur);
        var ramp = bg.property('Effects').addProperty('ADBE Ramp');
        ramp.property('ADBE Ramp-0001').setValue([960, 0]);
        ramp.property('ADBE Ramp-0002').setValue([0.05, 0.02, 0.12]);
        ramp.property('ADBE Ramp-0003').setValue([960, 1080]);
        ramp.property('ADBE Ramp-0004').setValue([0.0, 0.0, 0.02]);
        bg.moveToEnd();
        
        // 文字
        var L = c.layers.addText("IMPACT");
        L.name = "Title";
        L.threeDLayer = true;
        L.property('Position').setValue([960, 540, 0]);
        var td = L.property('ADBE Text Properties').property('ADBE Text Document');
        var doc = td.value;
        doc.font = "Impact";
        doc.fontSize = 220;
        doc.fillColor = [1.0, 0.95, 0.9];
        doc.justification = ParagraphJustification.CENTER_JUSTIFY;
        td.setValue(doc);
        L.motionBlur = true;
        
        var mo = L.property('ADBE Material Options Group');
        mo.property('ADBE Specular Coefficient').setValue(90);
        mo.property('ADBE Shininess Coefficient').setValue(80);
        mo.property('ADBE Metal Coefficient').setValue(70);
        mo.property('ADBE Diffuse Coefficient').setValue(50);
        mo.property('ADBE Ambient Coefficient').setValue(8);
        mo.property('ADBE Accepts Lights').setValue(1);
        
        // 入场: 从远处急速冲入 (impact_in: influence 92%)
        var pos = L.property('Position');
        pos.setValueAtTime(0, [960, 540, 1500]);
        pos.setValueAtTime(0.4, [960, 540, 0]);
        try {
            pos.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 92), new KeyframeEase(0, 92), new KeyframeEase(0, 92)],
                [new KeyframeEase(0, 15), new KeyframeEase(0, 15), new KeyframeEase(0, 15)]);
        } catch(e) {}
        
        // 缩放冲击: 大→正常 (模拟冲击波)
        var scl = L.property('Scale');
        scl.setValueAtTime(0.35, [130, 130, 130]);
        scl.setValueAtTime(0.55, [95, 95, 95]);
        scl.setValueAtTime(0.7, [102, 102, 102]);
        scl.setValueAtTime(0.85, [100, 100, 100]);
        
        // 摄像机: 快速推进 (push_in_fast)
        var cam = c.layers.addCamera('ImpactCam', [960, 540]);
        cam.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
        var camPos = cam.property('Position');
        camPos.setValueAtTime(0, [960, 500, -2800]);
        camPos.setValueAtTime(0.6, [960, 530, -1200]);
        camPos.setValueAtTime(dur, [960, 540, -1000]);
        try {
            camPos.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 92), new KeyframeEase(0, 92), new KeyframeEase(0, 92)],
                [new KeyframeEase(0, 30), new KeyframeEase(0, 30), new KeyframeEase(0, 30)]);
        } catch(e) {}
        cam.property('X Rotation').setValue(-4);
        
        // 冲击闪光 (t=0.4时闪烁)
        var flash = c.layers.addSolid([1, 1, 1], 'Flash', 1920, 1080, 1, dur);
        flash.property('Opacity').setValueAtTime(0, 0);
        flash.property('Opacity').setValueAtTime(0.38, 0);
        flash.property('Opacity').setValueAtTime(0.42, 70);
        flash.property('Opacity').setValueAtTime(0.6, 0);
        
        // 灯光
        var keyLt = c.layers.addLight('Key', [960, 300]);
        keyLt.lightType = LightType.POINT;
        keyLt.property('Position').setValue([1100, 200, -800]);
        var klO = keyLt.property('ADBE Light Options Group');
        klO.property('ADBE Light Intensity').setValue(450);
        klO.property('ADBE Light Color').setValue([1.0, 0.92, 0.80]);
        klO.property('ADBE Light Falloff Type').setValue(1);
        klO.property('ADBE Light Falloff Start').setValue(50);
        klO.property('ADBE Light Falloff Distance').setValue(2800);
        
        var rimLt = c.layers.addLight('Rim', [400, 700]);
        rimLt.lightType = LightType.POINT;
        rimLt.property('Position').setValue([300, 600, 500]);
        var rlO = rimLt.property('ADBE Light Options Group');
        rlO.property('ADBE Light Intensity').setValue(200);
        rlO.property('ADBE Light Color').setValue([0.5, 0.6, 1.0]);
        rlO.property('ADBE Light Falloff Type').setValue(1);
        rlO.property('ADBE Light Falloff Start').setValue(80);
        rlO.property('ADBE Light Falloff Distance').setValue(2500);
        
        var amb = c.layers.addLight('Amb', [960, 540]);
        amb.lightType = LightType.AMBIENT;
        amb.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(6);
        
        // 退出
        L.property('Opacity').setValueAtTime(dur * 0.88, 100);
        L.property('Opacity').setValueAtTime(dur, 0);
        
        return JSON.stringify({status:"success", comp:"''' + comp_name + '''", layers:c.numLayers});
    } catch(e) {
        return JSON.stringify({status:"error", msg:e.toString(), line:e.line});
    }
})();'''
    return send_bridge(jsx, 40), comp_name


# ============================================================
# 新预设2: 增强3D纵深穿越
# 基于调研: flythrough摄像机(-3500→-800), 大Z间距, 多层视差
# ============================================================
def create_3d_depth_enhanced():
    comp_name = "NEW_oc_3d_depth"
    jsx = '''(function() {
    try {
        for (var i = app.project.items.length; i >= 1; i--) {
            if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "''' + comp_name + '''") {
                app.project.item(i).remove();
            }
        }
        var dur = 3.5;
        var c = app.project.items.addComp("''' + comp_name + '''", 1920, 1080, 1, dur, 30);
        c.bgColor = [0.0, 0.0, 0.02];
        
        // 背景
        var bg = c.layers.addSolid([0,0,0], 'BG', 1920, 1080, 1, dur);
        var ramp = bg.property('Effects').addProperty('ADBE Ramp');
        ramp.property('ADBE Ramp-0001').setValue([960, 0]);
        ramp.property('ADBE Ramp-0002').setValue([0.03, 0.04, 0.12]);
        ramp.property('ADBE Ramp-0003').setValue([960, 1080]);
        ramp.property('ADBE Ramp-0004').setValue([0.0, 0.01, 0.04]);
        bg.moveToEnd();
        
        // 主文字
        var L = c.layers.addText("DEPTH");
        L.name = "Title";
        L.threeDLayer = true;
        L.property('Position').setValue([960, 500, 0]);
        var td = L.property('ADBE Text Properties').property('ADBE Text Document');
        var doc = td.value;
        doc.font = "DINNextLTPro-Bold";
        doc.fontSize = 200;
        doc.fillColor = [0.85, 0.92, 1.0];
        doc.justification = ParagraphJustification.CENTER_JUSTIFY;
        td.setValue(doc);
        L.motionBlur = true;
        var mo = L.property('ADBE Material Options Group');
        mo.property('ADBE Specular Coefficient').setValue(95);
        mo.property('ADBE Shininess Coefficient').setValue(88);
        mo.property('ADBE Metal Coefficient').setValue(80);
        mo.property('ADBE Diffuse Coefficient').setValue(30);
        mo.property('ADBE Ambient Coefficient').setValue(5);
        mo.property('ADBE Casts Shadows').setValue(1);
        mo.property('ADBE Accepts Lights').setValue(1);
        
        // Z-stack: 20层, 间距8px (增强)
        for (var d = 1; d < 20; d++) {
            var copy = L.duplicate();
            copy.name = 'Title_z_' + d;
            copy.threeDLayer = true;
            copy.property('Position').setValue([960, 500, d * 8]);
            var darkF = Math.max(0.02, 1.0 - d / 20.5);
            try {
                var tdc = copy.property('ADBE Text Properties').property('ADBE Text Document');
                var docc = tdc.value;
                docc.fillColor = [0.85 * darkF, 0.92 * darkF, 1.0 * darkF];
                tdc.setValue(docc);
            } catch(e2) {}
            copy.moveAfter(L);
        }
        
        // 前景参考文字 (视差层, Z=-400)
        var fgText = c.layers.addText("///");
        fgText.threeDLayer = true;
        fgText.property('Position').setValue([350, 800, -400]);
        fgText.property('Opacity').setValue(25);
        var fgTd = fgText.property('ADBE Text Properties').property('ADBE Text Document');
        var fgDoc = fgTd.value;
        fgDoc.font = "Consolas";
        fgDoc.fontSize = 60;
        fgDoc.fillColor = [0.4, 0.6, 0.9];
        fgTd.setValue(fgDoc);
        
        // 背景参考文字 (视差层, Z=600)
        var bgText = c.layers.addText("BACKGROUND");
        bgText.threeDLayer = true;
        bgText.property('Position').setValue([960, 300, 600]);
        bgText.property('Opacity').setValue(12);
        bgText.property('Scale').setValue([200, 200, 200]);
        var bgTd = bgText.property('ADBE Text Properties').property('ADBE Text Document');
        var bgDoc = bgTd.value;
        bgDoc.font = "Consolas";
        bgDoc.fontSize = 40;
        bgDoc.fillColor = [0.3, 0.4, 0.7];
        bgTd.setValue(bgDoc);
        
        // 摄像机: flythrough (-3500 → -800)
        var cam = c.layers.addCamera('FlyCam', [960, 540]);
        cam.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
        var camPos = cam.property('Position');
        camPos.setValueAtTime(0, [960, 450, -3500]);
        camPos.setValueAtTime(dur * 0.9, [960, 520, -800]);
        try {
            camPos.setTemporalEaseAtKey(1,
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100), new KeyframeEase(0, 100)],
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100), new KeyframeEase(0, 100)]);
            camPos.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 80), new KeyframeEase(0, 80), new KeyframeEase(0, 80)],
                [new KeyframeEase(0, 70), new KeyframeEase(0, 70), new KeyframeEase(0, 70)]);
        } catch(e) {}
        cam.property('X Rotation').setValue(-5);
        try { cam.property('Y Rotation').expression = 'Math.sin(time * 0.4) * 3'; } catch(e) {}
        
        // 灯光
        var keyLt = c.layers.addLight('Key', [960, 200]);
        keyLt.lightType = LightType.POINT;
        keyLt.property('Position').setValue([1200, 150, -1200]);
        var klO = keyLt.property('ADBE Light Options Group');
        klO.property('ADBE Light Intensity').setValue(500);
        klO.property('ADBE Light Color').setValue([0.8, 0.9, 1.0]);
        klO.property('ADBE Light Falloff Type').setValue(1);
        klO.property('ADBE Light Falloff Start').setValue(80);
        klO.property('ADBE Light Falloff Distance').setValue(3500);
        try { keyLt.property('Position').expression = '[value[0] + Math.sin(time * 0.7) * 100, value[1], value[2]]'; } catch(e) {}
        
        var rimLt = c.layers.addLight('Rim', [1600, 400]);
        rimLt.lightType = LightType.POINT;
        rimLt.property('Position').setValue([1700, 350, 400]);
        var rlO = rimLt.property('ADBE Light Options Group');
        rlO.property('ADBE Light Intensity').setValue(300);
        rlO.property('ADBE Light Color').setValue([0.5, 0.65, 1.0]);
        rlO.property('ADBE Light Falloff Type').setValue(1);
        rlO.property('ADBE Light Falloff Start').setValue(60);
        rlO.property('ADBE Light Falloff Distance').setValue(3000);
        
        var amb = c.layers.addLight('Amb', [960, 540]);
        amb.lightType = LightType.AMBIENT;
        amb.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(5);
        
        return JSON.stringify({status:"success", comp:"''' + comp_name + '''", layers:c.numLayers});
    } catch(e) {
        return JSON.stringify({status:"error", msg:e.toString(), line:e.line});
    }
})();'''
    return send_bridge(jsx, 45), comp_name


# ============================================================
# 新预设3: 速度线转场
# 基于调研: 径向模糊+缩放冲击, hard_stop缓动
# ============================================================
def create_speed_transition():
    comp_name = "NEW_oc_speed_trans"
    jsx = '''(function() {
    try {
        for (var i = app.project.items.length; i >= 1; i--) {
            if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "''' + comp_name + '''") {
                app.project.item(i).remove();
            }
        }
        var dur = 3.0;
        var c = app.project.items.addComp("''' + comp_name + '''", 1920, 1080, 1, dur, 30);
        c.bgColor = [0.02, 0.0, 0.03];
        
        // 背景
        var bg = c.layers.addSolid([0,0,0], 'BG', 1920, 1080, 1, dur);
        var ramp = bg.property('Effects').addProperty('ADBE Ramp');
        ramp.property('ADBE Ramp-0001').setValue([960, 540]);
        ramp.property('ADBE Ramp-0002').setValue([0.08, 0.02, 0.12]);
        ramp.property('ADBE Ramp-0003').setValue([960, 0]);
        ramp.property('ADBE Ramp-0004').setValue([0.0, 0.0, 0.02]);
        bg.moveToEnd();
        
        // 速度线背景 (径向线条)
        var lines = c.layers.addSolid([1, 1, 1], 'SpeedLines', 1920, 1080, 1, dur);
        lines.threeDLayer = true;
        lines.property('Position').setValue([960, 540, 200]);
        try {
            var noise = lines.property('Effects').addProperty('ADBE Noise');
            noise.property('ADBE Noise-0001').setValue(100);
            var blur = lines.property('Effects').addProperty('ADBE Radial Blur');
            blur.property('ADBE Radial Blur-0001').setValue(80);
            blur.property('ADBE Radial Blur-0002').setValue([960, 540]);
            blur.property('ADBE Radial Blur-0003').setValue(1);
        } catch(e) {}
        lines.property('Opacity').setValue(20);
        lines.property('Scale').setValueAtTime(0, [100, 100, 100]);
        lines.property('Scale').setValueAtTime(dur, [250, 250, 250]);
        
        // 文字
        var L = c.layers.addText("SPEED");
        L.name = "Title";
        L.threeDLayer = true;
        L.property('Position').setValue([960, 540, 0]);
        var td = L.property('ADBE Text Properties').property('ADBE Text Document');
        var doc = td.value;
        doc.font = "Impact";
        doc.fontSize = 250;
        doc.fillColor = [1.0, 0.3, 0.2];
        doc.justification = ParagraphJustification.CENTER_JUSTIFY;
        td.setValue(doc);
        L.motionBlur = true;
        
        // 入场: 极速缩放 (hard_stop: 从300%→100%, 瞬间停止)
        var scl = L.property('Scale');
        scl.setValueAtTime(0, [350, 350, 350]);
        scl.setValueAtTime(0.25, [90, 90, 90]);
        scl.setValueAtTime(0.35, [105, 105, 105]);
        scl.setValueAtTime(0.45, [100, 100, 100]);
        try {
            scl.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100), new KeyframeEase(0, 100)],
                [new KeyframeEase(0, 10), new KeyframeEase(0, 10), new KeyframeEase(0, 10)]);
        } catch(e) {}
        
        // 文字Z轴冲入
        var pos = L.property('Position');
        pos.setValueAtTime(0, [960, 540, 800]);
        pos.setValueAtTime(0.3, [960, 540, 0]);
        
        // 退出: 速度线转场 (zoom blur + 缩放)
        L.property('Scale').setValueAtTime(dur * 0.85, [100, 100, 100]);
        L.property('Scale').setValueAtTime(dur, [400, 400, 400]);
        L.property('Opacity').setValueAtTime(dur * 0.9, 100);
        L.property('Opacity').setValueAtTime(dur, 0);
        
        // 摄像机
        var cam = c.layers.addCamera('SpeedCam', [960, 540]);
        cam.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
        cam.property('Position').setValue([960, 540, -1600]);
        cam.property('X Rotation').setValue(-3);
        
        // 灯光
        var keyLt = c.layers.addLight('Key', [960, 300]);
        keyLt.lightType = LightType.POINT;
        keyLt.property('Position').setValue([960, 200, -600]);
        var klO = keyLt.property('ADBE Light Options Group');
        klO.property('ADBE Light Intensity').setValue(400);
        klO.property('ADBE Light Color').setValue([1.0, 0.85, 0.7]);
        klO.property('ADBE Light Falloff Type').setValue(1);
        klO.property('ADBE Light Falloff Start').setValue(50);
        klO.property('ADBE Light Falloff Distance').setValue(2500);
        
        var amb = c.layers.addLight('Amb', [960, 540]);
        amb.lightType = LightType.AMBIENT;
        amb.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(10);
        
        // 冲击闪帧
        var flash = c.layers.addSolid([1, 0.3, 0.2], 'Flash', 1920, 1080, 1, dur);
        flash.property('Opacity').setValueAtTime(0, 0);
        flash.property('Opacity').setValueAtTime(0.24, 0);
        flash.property('Opacity').setValueAtTime(0.27, 50);
        flash.property('Opacity').setValueAtTime(0.4, 0);
        
        return JSON.stringify({status:"success", comp:"''' + comp_name + '''", layers:c.numLayers});
    } catch(e) {
        return JSON.stringify({status:"error", msg:e.toString(), line:e.line});
    }
})();'''
    return send_bridge(jsx, 40), comp_name


def main():
    print("=" * 60)
    print("  OptimalComboEngine 新预设开发 + 渲染验证")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    engine = get_optimal_engine()
    
    # 显示组合参数
    print("\n[Engine] 3D Title 最优组合:")
    combo = engine.get_optimal_combo("3d_title")
    print(f"  Camera Z: {combo['camera']['z_start']} → {combo['camera']['z_end']}")
    print(f"  Easing: {combo['easing']['name']}")
    print(f"  Speed: {combo['speed']['perception']}")
    
    # 创建3个新预设
    presets = [
        ("oc_camera_impact", create_camera_impact),
        ("oc_3d_depth", create_3d_depth_enhanced),
        ("oc_speed_trans", create_speed_transition),
    ]
    
    created = []
    for name, creator in presets:
        print(f"\n[Create] {name}...", end=" ", flush=True)
        r, comp_name = creator()
        ok, detail = parse_result(r)
        if ok:
            print(f"OK ({detail})")
            created.append(comp_name)
        else:
            print(f"FAIL: {detail}")
    
    # 渲染每个预设
    print(f"\n[Render] 渲染 {len(created)} 个新预设...")
    for comp_name in created:
        out_file = OUTPUT_DIR / f"{comp_name}.mp4"
        print(f"  {comp_name} → {out_file.name}...", end=" ", flush=True)
        ok, detail = render_comp_to_mp4(comp_name, out_file)
        if ok:
            size_mb = out_file.stat().st_size / (1024*1024) if out_file.exists() else 0
            print(f"OK ({size_mb:.1f}MB)")
        else:
            print(f"FAIL: {detail}")
    
    # 验证
    print("\n[Verify] 输出文件:")
    for f in sorted(OUTPUT_DIR.glob("NEW_*.mp4")):
        print(f"  {f.name} ({f.stat().st_size//(1024)}KB)")
    
    print("\n" + "=" * 60)
    print("  完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
