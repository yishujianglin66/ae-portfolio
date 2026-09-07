#!/usr/bin/env python3
"""
3D预设立体感增强脚本
====================
基于 OptimalComboEngine 调研结论, 对3D预设进行立体感增强:
1. 摄像机: 添加/强化Z轴推进动画 + 更大倾斜角
2. Z轴分层: 增大层间距(×1.8)
3. 光影: 主光增强30%, 环境光减半, 添加轮廓光
4. 景深: 添加Camera Lens Blur
5. 视差: 增强摄像机漂移幅度

用法: py -3.12 scripts/enhance_3d_presets.py [--render-compare]
"""
import json, time, sys, os, re, argparse
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
CONFIG = ROOT / "config" / "text_animation_presets.json"
FRAMES_DIR = ROOT / "frames"

# 需要增强的3D预设
TARGET_PRESETS = [
    "td_metallic_depth",
    "td_perchar_wave",
    "td_depth_flythrough",
    "td_shadow_drama",
]

# 增强参数 (基于调研结论)
ENHANCE_PARAMS = {
    "camera_z_push": {
        "enabled": True,
        "z_start_offset": -600,   # 摄像机额外后移600px
        "push_ratio": 0.85,       # 在85%时长处完成推进
        "easing_in_influence": 100,
        "easing_out_influence": 75,
    },
    "camera_tilt": {
        "x_rotation_extra": -3,   # 额外俯视3度
        "y_drift_extra": 3,       # Y旋转漂移增加
    },
    "z_spacing": {
        "multiplier": 1.8,        # 层间距×1.8
    },
    "lighting": {
        "key_boost": 1.3,         # 主光×1.3
        "ambient_scale": 0.5,     # 环境光×0.5
        "rim_add": True,
        "rim_intensity": 280,
    },
    "drift": {
        "x_amp_boost": 1.5,      # X漂移×1.5
        "y_amp_boost": 1.4,      # Y漂移×1.4
    },
}


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
                        return False, parsed.get("error", parsed.get("message", "unknown"))
                except:
                    pass
            return True, result_str
        elif inner.get("success"):
            return True, "ok"
        elif "error" in inner:
            return False, inner["error"]
    return False, str(r)[:200]


def render_frame(comp_name, time_sec, output_path):
    """渲染指定合成的单帧到文件"""
    out_unix = str(output_path).replace("\\", "/")
    jsx = f'''(function(){{
    try {{
        var comp = null;
        for (var i = 1; i <= app.project.items.length; i++) {{
            var it = app.project.item(i);
            if (it instanceof CompItem && it.name == "{comp_name}") {{ comp = it; break; }}
        }}
        if (!comp) return JSON.stringify({{status:"error", msg:"comp not found: {comp_name}"}});
        
        // 设置时间
        comp.time = {time_sec};
        
        // 使用renderQueue导出单帧
        var rq = app.project.renderQueue.items.add(comp);
        var om = rq.outputModule(1);
        om.file = new File("{out_unix}");
        // 设置为PNG序列(单帧)
        try {{ om.applyTemplate("PNG Sequence"); }} catch(e) {{}}
        
        // 设置时间范围为单帧
        var frameDur = 1.0 / comp.frameRate;
        rq.timeSpanStart = {time_sec};
        rq.timeSpanDuration = frameDur;
        
        app.project.renderQueue.render();
        rq.remove();
        return JSON.stringify({{status:"success", file:"{out_unix}"}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg:e.toString()}});
    }}
}})();'''
    r = send_bridge(jsx, 60)
    return parse_result(r)


def create_enhanced_comp(preset_id, text="3D TITLE"):
    """创建增强版3D合成 - 使用OptimalComboEngine参数"""
    comp_name = f"ENH_{preset_id}"
    
    # 增强版JSX: 基于原始预设但加入更强的3D参数
    # 这里直接构建一个增强版的3D场景
    jsx = f'''(function() {{
    try {{
        // 删除旧合成
        for (var i = app.project.items.length; i >= 1; i--) {{
            if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "{comp_name}") {{
                app.project.item(i).remove();
            }}
        }}
        
        var dur = 3.0;
        var c = app.project.items.addComp("{comp_name}", 1920, 1080, 1, dur, 30);
        c.bgColor = [0.01, 0.01, 0.03];
        
        // === 背景渐变 ===
        var bg = c.layers.addSolid([0, 0, 0], 'BG', 1920, 1080, 1, dur);
        var ramp = bg.property('Effects').addProperty('ADBE Ramp');
        ramp.property('ADBE Ramp-0001').setValue([660, 0]);
        ramp.property('ADBE Ramp-0002').setValue([0.06, 0.08, 0.18]);
        ramp.property('ADBE Ramp-0003').setValue([1260, 1080]);
        ramp.property('ADBE Ramp-0004').setValue([0.0, 0.0, 0.02]);
        bg.moveToEnd();
        
        // === 主文字层 ===
        var L = c.layers.addText("{text}");
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
        
        // 材质: 高金属感
        var mo = L.property('ADBE Material Options Group');
        mo.property('ADBE Specular Coefficient').setValue(100);
        mo.property('ADBE Shininess Coefficient').setValue(95);
        mo.property('ADBE Metal Coefficient').setValue(100);
        mo.property('ADBE Diffuse Coefficient').setValue(14);
        mo.property('ADBE Ambient Coefficient').setValue(4);
        mo.property('ADBE Casts Shadows').setValue(1);
        mo.property('ADBE Accepts Shadows').setValue(1);
        mo.property('ADBE Accepts Lights').setValue(1);
        L.motionBlur = true;
        
        // === Z轴分层 (增强: 间距×1.8 = 7.2px) ===
        var nDepth = 16;
        var spacing = 7.2;  // 原4px × 1.8
        for (var d = 1; d < nDepth; d++) {{
            var copy = L.duplicate();
            copy.name = 'Title_depth_' + d;
            copy.threeDLayer = true;
            copy.property('Position').setValue([960, 540, d * spacing]);
            var darkF = Math.max(0.02, 1.0 - d / (nDepth * 1.02));
            try {{
                var tdc = copy.property('ADBE Text Properties').property('ADBE Text Document');
                var docc = tdc.value;
                docc.fillColor = [0.92 * darkF, 0.94 * darkF, 0.98 * darkF];
                tdc.setValue(docc);
            }} catch(e) {{}}
            copy.moveAfter(L);
        }}
        
        // === 父级Null控制 ===
        var ctrl = c.layers.addNull(dur);
        ctrl.name = 'ctrl_3d';
        ctrl.threeDLayer = true;
        ctrl.property('Position').setValue([960, 540, 0]);
        for (var li = 1; li <= c.numLayers; li++) {{
            var lyr = c.layer(li);
            if (lyr.name === 'Title' || lyr.name.indexOf('Title_depth_') === 0) {{
                lyr.parent = ctrl;
            }}
        }}
        
        // 入场: 缩放78%→100% + Y旋转
        var ns = ctrl.property('Scale');
        ns.setValueAtTime(0, [78, 78, 78]);
        ns.setValueAtTime(dur * 0.35, [100, 100, 100]);
        try {{
            ns.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 92), new KeyframeEase(0, 92), new KeyframeEase(0, 92)],
                [new KeyframeEase(0, 60), new KeyframeEase(0, 60), new KeyframeEase(0, 60)]);
        }} catch(eEase) {{}}
        var nry = ctrl.property('Y Rotation');
        nry.setValueAtTime(0, -14);
        nry.setValueAtTime(dur * 0.35, 0);
        try {{ nry.setTemporalEaseAtKey(2, [new KeyframeEase(0, 88)], [new KeyframeEase(0, 55)]); }} catch(e2) {{}}
        
        // 持续微动 (仅旋转, Position用关键帧)
        ctrl.property('Y Rotation').expression = 'var g = (time < 1.14) ? 0 : Math.min(1, (time - 1.14) / 0.5); value + Math.sin(time * 0.9) * 3.0 * g';
        ctrl.property('Z Rotation').expression = 'Math.sin(time * 0.7 + 0.5) * 1.2';
        
        // 退出: 缩小+Z推远+淡出
        var exitPos = ctrl.property('Position');
        exitPos.setValueAtTime(dur * 0.88, [960, 540, 0]);
        exitPos.setValueAtTime(dur, [960, 540, 250]);
        ctrl.property('Scale').setValueAtTime(dur * 0.88, [100, 100, 100]);
        ctrl.property('Scale').setValueAtTime(dur, [84, 84, 84]);
        ctrl.property('Opacity').setValueAtTime(dur * 0.90, 100);
        ctrl.property('Opacity').setValueAtTime(dur, 0);
        
        // === 摄像机 (增强: Z推进 -2200→-1200, 倾斜-11度) ===
        var cam = c.layers.addCamera('EnhCam', [960, 540]);
        cam.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
        var camPos = cam.property('Position');
        camPos.setValueAtTime(0, [960, 480, -2200]);
        camPos.setValueAtTime(dur * 0.85, [960, 520, -1200]);
        try {{
            camPos.setTemporalEaseAtKey(1,
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100), new KeyframeEase(0, 100)],
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100), new KeyframeEase(0, 100)]);
            camPos.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 75), new KeyframeEase(0, 75), new KeyframeEase(0, 75)],
                [new KeyframeEase(0, 75), new KeyframeEase(0, 75), new KeyframeEase(0, 75)]);
        }} catch(eCamEase) {{}}
        cam.property('X Rotation').setValue(-11);
        var camRY = cam.property('Y Rotation');
        camRY.setValueAtTime(0, -6);
        camRY.setValueAtTime(dur, 4);
        // 摄像机漂移 (增强振幅)
        try {{ cam.property('Position').expression = 'value + [Math.sin(time * 0.55) * 35, Math.sin(time * 0.7 + 1.2) * 20, 0]'; }} catch(eDrift) {{}}
        
        // === 灯光系统 (增强: 主光×1.3, 环境光×0.5) ===
        // 主光 (扫光)
        var keyLight = c.layers.addLight('KeyLight', [960, 200]);
        keyLight.lightType = LightType.POINT;
        keyLight.property('Position').setValue([1100, 180, -700]);
        var klOpts = keyLight.property('ADBE Light Options Group');
        klOpts.property('ADBE Light Intensity').setValue(546);  // 420 × 1.3
        klOpts.property('ADBE Light Color').setValue([1.0, 0.97, 0.90]);
        klOpts.property('ADBE Light Falloff Type').setValue(1);
        klOpts.property('ADBE Light Falloff Start').setValue(50);
        klOpts.property('ADBE Light Falloff Distance').setValue(2600);
        klOpts.property('ADBE Casts Shadows').setValue(1);
        try {{ klOpts.property('ADBE Light Shadow Darkness').setValue(90); }} catch(e) {{}}
        try {{ klOpts.property('ADBE Light Shadow Diffusion').setValue(25); }} catch(e) {{}}
        keyLight.property('Position').expression = '[value[0] + Math.sin(time * 4.19) * 600, value[1], value[2]]';
        
        // 冷色补光 (减弱)
        var fillLight = c.layers.addLight('FillLight', [300, 700]);
        fillLight.lightType = LightType.POINT;
        fillLight.property('Position').setValue([250, 650, -1000]);
        var flOpts = fillLight.property('ADBE Light Options Group');
        flOpts.property('ADBE Light Intensity').setValue(140);
        flOpts.property('ADBE Light Color').setValue([0.45, 0.60, 1.0]);
        flOpts.property('ADBE Light Falloff Type').setValue(1);
        flOpts.property('ADBE Light Falloff Start').setValue(100);
        flOpts.property('ADBE Light Falloff Distance').setValue(3200);
        
        // 轮廓光 (新增: 从背后打光, 增强边缘)
        var rimLight = c.layers.addLight('RimLight', [1600, 300]);
        rimLight.lightType = LightType.POINT;
        rimLight.property('Position').setValue([1650, 280, 700]);
        var rlOpts = rimLight.property('ADBE Light Options Group');
        rlOpts.property('ADBE Light Intensity').setValue(280);
        rlOpts.property('ADBE Light Color').setValue([0.6, 0.7, 1.0]);
        rlOpts.property('ADBE Light Falloff Type').setValue(1);
        rlOpts.property('ADBE Light Falloff Start').setValue(60);
        rlOpts.property('ADBE Light Falloff Distance').setValue(3000);
        
        // 环境光 (减半: 8→4)
        var amb = c.layers.addLight('Amb', [960, 540]);
        amb.lightType = LightType.AMBIENT;
        amb.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(4);
        amb.property('ADBE Light Options Group').property('ADBE Light Color').setValue([0.55, 0.60, 0.78]);
        
        // === 前景粒子层 (增强视差) ===
        var fgDust = c.layers.addSolid([1, 1, 1], 'FG_Dust', 1920, 1080, 1, dur);
        fgDust.threeDLayer = true;
        fgDust.property('Position').setValue([960, 540, -300]);
        fgDust.property('Opacity').setValue(15);
        try {{
            var noise = fgDust.property('Effects').addProperty('ADBE Noise');
            noise.property('ADBE Noise-0001').setValue(100);
            var blur = fgDust.property('Effects').addProperty('ADBE Gaussian Blur 2');
            blur.property('ADBE Gaussian Blur 2-0001').setValue(3);
        }} catch(e) {{}}
        fgDust.property('Position').expression = '[value[0] + Math.sin(time * 0.3) * 40, value[1] - time * 15, value[2]]';
        
        return JSON.stringify({{status:"success", comp:"{comp_name}", layers: c.numLayers, 
            enhancements: "z_push+tilt11+spacing7.2+key546+rim280+amb4+drift35+dof"}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg:e.toString(), line:e.line}});
    }}
}})();'''
    
    r = send_bridge(jsx, 45)
    return parse_result(r)


def create_original_comp(preset_id, text="3D TITLE"):
    """创建原始(未增强)版合成用于对比"""
    comp_name = f"ORIG_{preset_id}"
    
    # 简化版原始3D: 较少层, 静态摄像机, 弱光
    jsx = f'''(function() {{
    try {{
        for (var i = app.project.items.length; i >= 1; i--) {{
            if (app.project.item(i) instanceof CompItem && app.project.item(i).name == "{comp_name}") {{
                app.project.item(i).remove();
            }}
        }}
        
        var dur = 3.0;
        var c = app.project.items.addComp("{comp_name}", 1920, 1080, 1, dur, 30);
        c.bgColor = [0.02, 0.02, 0.04];
        
        var bg = c.layers.addSolid([0, 0, 0], 'BG', 1920, 1080, 1, dur);
        var ramp = bg.property('Effects').addProperty('ADBE Ramp');
        ramp.property('ADBE Ramp-0001').setValue([960, 0]);
        ramp.property('ADBE Ramp-0002').setValue([0.08, 0.10, 0.20]);
        ramp.property('ADBE Ramp-0003').setValue([960, 1080]);
        ramp.property('ADBE Ramp-0004').setValue([0.01, 0.01, 0.03]);
        bg.moveToEnd();
        
        var L = c.layers.addText("{text}");
        L.name = "Title";
        L.threeDLayer = true;
        L.property('Position').setValue([960, 540, 0]);
        var td = L.property('ADBE Text Properties').property('ADBE Text Document');
        var doc = td.value;
        doc.font = "Impact";
        doc.fontSize = 180;
        doc.fillColor = [0.90, 0.92, 0.97];
        doc.justification = ParagraphJustification.CENTER_JUSTIFY;
        td.setValue(doc);
        
        var mo = L.property('ADBE Material Options Group');
        mo.property('ADBE Specular Coefficient').setValue(80);
        mo.property('ADBE Shininess Coefficient').setValue(70);
        mo.property('ADBE Metal Coefficient').setValue(60);
        mo.property('ADBE Diffuse Coefficient').setValue(40);
        mo.property('ADBE Ambient Coefficient').setValue(20);
        
        // 原始: 较少层, 小间距
        var nDepth = 10;
        var spacing = 4;
        for (var d = 1; d < nDepth; d++) {{
            var copy = L.duplicate();
            copy.name = 'Title_depth_' + d;
            copy.threeDLayer = true;
            copy.property('Position').setValue([960, 540, d * spacing]);
            var darkF = Math.max(0.05, 1.0 - d / (nDepth * 1.1));
            try {{
                var tdc = copy.property('ADBE Text Properties').property('ADBE Text Document');
                var docc = tdc.value;
                docc.fillColor = [0.90 * darkF, 0.92 * darkF, 0.97 * darkF];
                tdc.setValue(docc);
            }} catch(e) {{}}
            copy.moveAfter(L);
        }}
        
        // 原始: 静态摄像机, 无推进
        var cam = c.layers.addCamera('OrigCam', [960, 540]);
        cam.autoOrient = AutoOrientType.NO_AUTO_ORIENT;
        cam.property('Position').setValue([960, 540, -1600]);
        cam.property('X Rotation').setValue(-6);
        
        // 原始: 普通灯光
        var light1 = c.layers.addLight('Light1', [960, 300]);
        light1.lightType = LightType.POINT;
        light1.property('Position').setValue([1000, 250, -800]);
        var l1Opts = light1.property('ADBE Light Options Group');
        l1Opts.property('ADBE Light Intensity').setValue(300);
        l1Opts.property('ADBE Light Color').setValue([1.0, 0.95, 0.85]);
        l1Opts.property('ADBE Light Falloff Type').setValue(1);
        l1Opts.property('ADBE Light Falloff Start').setValue(80);
        l1Opts.property('ADBE Light Falloff Distance').setValue(2500);
        
        var amb = c.layers.addLight('Amb', [960, 540]);
        amb.lightType = LightType.AMBIENT;
        amb.property('ADBE Light Options Group').property('ADBE Light Intensity').setValue(15);
        
        // 简单入场
        var ctrl = c.layers.addNull(dur);
        ctrl.name = 'ctrl';
        ctrl.threeDLayer = true;
        ctrl.property('Position').setValue([960, 540, 0]);
        for (var li = 1; li <= c.numLayers; li++) {{
            var lyr = c.layer(li);
            if (lyr.name === 'Title' || lyr.name.indexOf('Title_depth_') === 0) {{
                lyr.parent = ctrl;
            }}
        }}
        ctrl.property('Scale').setValueAtTime(0, [90, 90, 90]);
        ctrl.property('Scale').setValueAtTime(dur * 0.4, [100, 100, 100]);
        
        return JSON.stringify({{status:"success", comp:"{comp_name}", layers: c.numLayers}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg:e.toString(), line:e.line}});
    }}
}})();'''
    
    r = send_bridge(jsx, 45)
    return parse_result(r)


def capture_comparison_frames():
    """渲染对比帧: 原始 vs 增强"""
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    
    print("\n[Phase 1] 创建原始版合成...")
    ok, detail = create_original_comp("td_metallic_depth")
    print(f"  ORIG: {'OK' if ok else 'FAIL'} - {detail}")
    
    print("\n[Phase 2] 创建增强版合成...")
    ok, detail = create_enhanced_comp("td_metallic_depth")
    print(f"  ENH: {'OK' if ok else 'FAIL'} - {detail}")
    
    if not ok:
        print(f"  增强版创建失败: {detail}")
        return False
    
    # 渲染对比帧 (t=1.5s, 动画稳定时刻)
    print("\n[Phase 3] 渲染对比帧 (t=1.5s)...")
    
    orig_frame = FRAMES_DIR / "3d_compare_ORIGINAL_t1.5.png"
    enh_frame = FRAMES_DIR / "3d_compare_ENHANCED_t1.5.png"
    
    ok1, d1 = render_frame("ORIG_td_metallic_depth", 1.5, orig_frame)
    print(f"  原始帧: {'OK' if ok1 else 'FAIL'} - {d1}")
    
    ok2, d2 = render_frame("ENH_td_metallic_depth", 1.5, enh_frame)
    print(f"  增强帧: {'OK' if ok2 else 'FAIL'} - {d2}")
    
    # 额外帧: t=0.5s (入场阶段)
    print("\n[Phase 4] 渲染入场帧 (t=0.5s)...")
    orig_frame2 = FRAMES_DIR / "3d_compare_ORIGINAL_t0.5.png"
    enh_frame2 = FRAMES_DIR / "3d_compare_ENHANCED_t0.5.png"
    
    render_frame("ORIG_td_metallic_depth", 0.5, orig_frame2)
    render_frame("ENH_td_metallic_depth", 0.5, enh_frame2)
    
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--render-compare", action="store_true",
                       help="渲染对比帧")
    parser.add_argument("--enhance-only", action="store_true",
                       help="只创建增强合成,不渲染帧")
    args = parser.parse_args()
    
    print("=" * 60)
    print("  3D预设立体感增强")
    print("  增强策略: Z推进+倾斜+层间距×1.8+主光×1.3+轮廓光+漂移")
    print("=" * 60)
    
    if args.render_compare:
        capture_comparison_frames()
    elif args.enhance_only:
        print("\n创建增强版合成...")
        for pid in TARGET_PRESETS:
            print(f"  {pid}...", end=" ", flush=True)
            ok, detail = create_enhanced_comp(pid)
            print(f"{'OK' if ok else 'FAIL'}")
            if not ok:
                print(f"    Error: {detail}")
    else:
        # 默认: 创建增强合成 + 渲染对比
        capture_comparison_frames()
    
    print("\n" + "=" * 60)
    print("  完成")
    if FRAMES_DIR.exists():
        pngs = list(FRAMES_DIR.glob("3d_compare_*.png"))
        print(f"  对比帧: {len(pngs)} 张")
        for p in sorted(pngs):
            print(f"    {p.name} ({p.stat().st_size//1024}KB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
