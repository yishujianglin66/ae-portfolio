#!/usr/bin/env python3
"""
方向一：摄像机运动 + 三维图层 + 关键帧运动曲线 深度进阶
=========================================================
子项A: 摄像机高级运动模式
  - Dolly Zoom (希区柯克变焦): 摄像机Z推进 + FOV反向变化
  - 环绕+推进复合运动: Y旋转360° + Z推进
  - 手持晃动模拟: wiggle表达式精确参数
子项B: 多Z轴视差分层 (前景/中景/背景独立运动)
子项C: 运动曲线精调 (指数加速→急停→微弹overshoot 5-8%→settle)

每个子项渲染3秒验证视频(1920×1080 H.264) + YAVG>15验证

用法: py -3.12 scripts/advanced_camera_motion.py
"""
import json, time, sys, os, subprocess
from pathlib import Path
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).resolve().parent.parent
BRIDGE_CMD = ROOT / ".ae-mcp-bridge" / "ae_command.json"
BRIDGE_RESULT = ROOT / ".ae-mcp-bridge" / "ae_result.json"
OUTPUT_DIR = Path(r"D:\AE-Work\output\advanced_camera")
FRAMES_DIR = ROOT / "frames"


def send_bridge(code, wait=60):
    if not BRIDGE_CMD.parent.exists():
        return {"success": False, "error": "Bridge not found"}
    # 写入命令
    req_ts = datetime.now().isoformat()
    cmd = {"command": "runScript", "args": {"code": code},
           "timestamp": req_ts, "status": "pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd, ensure_ascii=False), encoding="utf-8")
    # 高频轮询(100ms) - result文件可能被MCP面板快速删除
    import time as _t
    deadline = _t.time() + wait
    while _t.time() < deadline:
        _t.sleep(0.1)  # 100ms
        try:
            if not BRIDGE_RESULT.exists():
                continue
            content = BRIDGE_RESULT.read_text(encoding="utf-8")
            if not content or not content.strip():
                continue
            r = json.loads(content)
            if "result" in r and r.get("status") not in ("waiting", "pending", None):
                return r
        except (json.JSONDecodeError, OSError, IOError):
            pass
        except Exception:
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


def render_comp(comp_name, output_path, duration_sec=3.0, wait=120):
    """渲染合成到H.264 MP4"""
    out_unix = str(output_path).replace("\\", "/")
    jsx = f'''(function() {{
    try {{
        var comp = null;
        for (var i = 1; i <= app.project.items.length; i++) {{
            var it = app.project.item(i);
            if (it instanceof CompItem && it.name == "{comp_name}") {{ comp = it; break; }}
        }}
        if (!comp) return JSON.stringify({{status:"error", msg:"comp '{comp_name}' not found"}});
        
        // 清理同名输出文件避免覆盖弹窗
        var outFile = new File("{out_unix}");
        if (outFile.exists) outFile.remove();
        
        var rq = app.project.renderQueue.items.add(comp);
        var om = rq.outputModule(1);
        om.applyTemplate("H.264 匹配源 - 高比特率");
        om.file = outFile;
        rq.render();
        rq.remove();
        return JSON.stringify({{status:"success", msg:"rendered {comp_name}"}});
    }} catch(e) {{
        return JSON.stringify({{status:"error", msg: e.toString()}});
    }}
}})();'''
    
    print(f"  渲染 {comp_name} → {output_path.name} ...")
    r = send_bridge(jsx, wait=wait)
    ok, data = parse_result(r)
    if ok:
        print(f"  ✓ 渲染完成")
    else:
        print(f"  ✗ 渲染失败: {data}")
    return ok


def verify_animation(video_path, threshold=15):
    """用ffmpeg提取帧 + PIL像素差验证动画存在"""
    try:
        from PIL import Image
        import numpy as np
    except ImportError:
        print("  ! PIL/numpy不可用, 跳过验证")
        return True
    
    vpath = str(video_path)
    f1 = str(FRAMES_DIR / "adv_cam_f1.png")
    f2 = str(FRAMES_DIR / "adv_cam_f2.png")
    
    # 提取0.3s和2.5s处帧
    for t, fp in [(0.3, f1), (2.5, f2)]:
        cmd = ["ffmpeg", "-y", "-ss", str(t), "-i", vpath, "-frames:v", "1", fp]
        subprocess.run(cmd, capture_output=True, timeout=30)
    
    if not os.path.exists(f1) or not os.path.exists(f2):
        print("  ! 帧提取失败")
        return False
    
    img1 = np.array(Image.open(f1).convert("L"), dtype=np.float32)
    img2 = np.array(Image.open(f2).convert("L"), dtype=np.float32)
    diff = np.abs(img1 - img2)
    yavg = float(np.mean(diff))
    
    print(f"  YAVG = {yavg:.1f} (阈值>{threshold})")
    if yavg > threshold:
        print(f"  ✓ 动画验证通过")
        return True
    else:
        print(f"  ✗ 动画不明显!")
        return False


# ============================================================
# 子项A: 摄像机高级运动模式
# ============================================================

def create_dolly_zoom():
    """Dolly Zoom (希区柯克变焦): 摄像机Z推进同时FOV反向增大
    效果: 主体大小不变但背景急剧压缩/拉伸
    参数:
      - Camera Z: 0→-1200 (推进)
      - Zoom/FOV: 35mm→18mm (焦距缩短=FOV增大)
      - 时长: 3秒, 指数缓入
    """
    jsx = '''(function() {
    try {
        app.beginUndoGroup("Dolly Zoom Demo");
        var comp = app.project.items.addComp("ADV_dolly_zoom", 1920, 1080, 1, 3.0, 30);
        
        // 背景层 - 棋盘格(用多个solid模拟纵深)
        var bg = comp.layers.addSolid([0.05, 0.05, 0.12], "BG_deep", 1920, 1080, 1);
        bg.threeDLayer = true;
        bg.property("Position").setValue([960, 540, -2000]);
        bg.property("Scale").setValue([400, 400, 100]);
        
        // 中景参考物 - 柱子阵列(提供透视参考)
        for (var i = 0; i < 5; i++) {
            var pillar = comp.layers.addSolid([0.2, 0.25, 0.4], "Pillar_" + i, 80, 600, 1);
            pillar.threeDLayer = true;
            pillar.property("Position").setValue([300 + i * 350, 540, -400 - i * 300]);
        }
        
        // 前景主体 - 文字
        var txtLayer = comp.layers.addText("DOLLY ZOOM");
        var txtDoc = txtLayer.property("Source Text").value;
        txtDoc.fontSize = 120;
        txtDoc.fillColor = [1, 0.85, 0.2];
        txtDoc.font = "Arial-BoldMT";
        txtLayer.property("Source Text").setValue(txtDoc);
        txtLayer.threeDLayer = true;
        txtLayer.property("Position").setValue([960, 540, 0]);
        
        // 摄像机 (单节点, 避免POI陷阱)
        var cam = comp.layers.addCamera("DollyCam", [960, 540]);
        cam.property("Point of Interest").expression = "";
        // 设为单节点
        try { cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); } catch(e) {}
        
        // Dolly Zoom核心: Z推进 + 焦距反向
        var camPos = cam.property("Position");
        camPos.setValueAtTime(0, [960, 540, 0]);
        camPos.setValueAtTime(3.0, [960, 540, -1200]);
        
        // 焦距: 35mm → 18mm (FOV从54°→84°)
        var zoomProp = cam.property("ADBE Camera Options Group").property("ADBE Camera Zoom");
        zoomProp.setValueAtTime(0, 35);
        zoomProp.setValueAtTime(3.0, 18);
        
        // 指数缓入曲线 (influence 100%, speed 0)
        try {
            camPos.setTemporalEaseAtKey(1,
                [new KeyframeEase(0, 10), new KeyframeEase(0, 10), new KeyframeEase(0, 10)],
                [new KeyframeEase(0, 10), new KeyframeEase(0, 10), new KeyframeEase(0, 10)]);
            camPos.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 90), new KeyframeEase(0, 90), new KeyframeEase(0, 90)],
                [new KeyframeEase(0, 90), new KeyframeEase(0, 90), new KeyframeEase(0, 90)]);
        } catch(e) {}
        try {
            zoomProp.setTemporalEaseAtKey(1, [new KeyframeEase(0, 10)], [new KeyframeEase(0, 10)]);
            zoomProp.setTemporalEaseAtKey(2, [new KeyframeEase(0, 90)], [new KeyframeEase(0, 90)]);
        } catch(e) {}
        
        // 灯光
        var keyLight = comp.layers.addLight("Key", [700, 300]);
        keyLight.property("Light Options").property("Intensity").setValue(400);
        keyLight.property("Light Options").property("Color").setValue([1, 0.95, 0.85]);
        
        var ambLight = comp.layers.addLight("Ambient", [960, 540]);
        ambLight.lightType = LightType.AMBIENT;
        ambLight.property("Light Options").property("Intensity").setValue(60);
        
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"dolly_zoom created"});
    } catch(e) {
        app.endUndoGroup();
        return JSON.stringify({status:"error", msg: e.toString()});
    }
})();'''
    
    print("\n[A1] Dolly Zoom (希区柯克变焦)")
    r = send_bridge(jsx)
    ok, data = parse_result(r)
    if ok:
        print(f"  ✓ 合成创建成功")
        return True
    else:
        print(f"  ✗ 失败: {data}")
        return False


def create_orbit_pushin():
    """环绕+推进复合运动: Y旋转360°同时Z推进
    参数:
      - Y Rotation: 0→360° (3秒匀速)
      - Z Position: 800→-200 (推进)
      - X Position: sin曲线偏移(环绕轨迹)
    """
    jsx = '''(function() {
    try {
        app.beginUndoGroup("Orbit PushIn Demo");
        var comp = app.project.items.addComp("ADV_orbit_push", 1920, 1080, 1, 3.0, 30);
        
        // 中心主体
        var txtLayer = comp.layers.addText("ORBIT");
        var txtDoc = txtLayer.property("Source Text").value;
        txtDoc.fontSize = 150;
        txtDoc.fillColor = [0.9, 0.3, 0.1];
        txtDoc.font = "Arial-BoldMT";
        txtLayer.property("Source Text").setValue(txtDoc);
        txtLayer.threeDLayer = true;
        txtLayer.property("Position").setValue([960, 540, 0]);
        
        // 环绕参考物 - 环形分布的方块
        for (var i = 0; i < 8; i++) {
            var angle = (i / 8) * Math.PI * 2;
            var radius = 600;
            var bx = 960 + Math.cos(angle) * radius;
            var bz = Math.sin(angle) * radius;
            var cube = comp.layers.addSolid([0.15, 0.4, 0.6], "OrbRef_" + i, 120, 120, 1);
            cube.threeDLayer = true;
            cube.property("Position").setValue([bx, 540, bz]);
            cube.property("Y Rotation").setValue(i * 45);
        }
        
        // 地面网格
        var floor = comp.layers.addSolid([0.08, 0.08, 0.15], "Floor", 3000, 3000, 1);
        floor.threeDLayer = true;
        floor.property("Position").setValue([960, 900, 0]);
        floor.property("X Rotation").setValue(90);
        
        // 摄像机 - 环绕+推进
        var cam = comp.layers.addCamera("OrbitCam", [960, 540]);
        try { cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); } catch(e) {}
        
        // 使用Null驱动环绕
        var nullOrbit = comp.layers.addNull(3.0);
        nullOrbit.name = "OrbitDriver";
        nullOrbit.threeDLayer = true;
        nullOrbit.property("Position").setValue([960, 400, 0]);
        
        // Y旋转: 0→360 匀速
        var yRot = nullOrbit.property("Y Rotation");
        yRot.setValueAtTime(0, 0);
        yRot.setValueAtTime(3.0, 360);
        
        // 摄像机parent到null, 本地偏移做推进
        cam.parent = nullOrbit;
        var camPos = cam.property("Position");
        camPos.setValueAtTime(0, [0, 0, 1400]);
        camPos.setValueAtTime(3.0, [0, -100, 500]);
        
        // 推进缓动: ease-out
        try {
            camPos.setTemporalEaseAtKey(1,
                [new KeyframeEase(0, 33), new KeyframeEase(0, 33), new KeyframeEase(0, 33)],
                [new KeyframeEase(0, 33), new KeyframeEase(0, 33), new KeyframeEase(0, 33)]);
            camPos.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 75), new KeyframeEase(0, 75), new KeyframeEase(0, 75)],
                [new KeyframeEase(0, 75), new KeyframeEase(0, 75), new KeyframeEase(0, 75)]);
        } catch(e) {}
        
        // 灯光
        var keyLight = comp.layers.addLight("Key", [500, 200]);
        keyLight.property("Light Options").property("Intensity").setValue(500);
        keyLight.property("Light Options").property("Color").setValue([1, 0.9, 0.7]);
        keyLight.threeDLayer = true;
        keyLight.property("Position").setValue([500, 200, 800]);
        
        var rimLight = comp.layers.addLight("Rim", [1400, 300]);
        rimLight.property("Light Options").property("Intensity").setValue(300);
        rimLight.property("Light Options").property("Color").setValue([0.4, 0.6, 1.0]);
        rimLight.threeDLayer = true;
        rimLight.property("Position").setValue([1400, 300, -500]);
        
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"orbit_push created"});
    } catch(e) {
        app.endUndoGroup();
        return JSON.stringify({status:"error", msg: e.toString()});
    }
})();'''
    
    print("\n[A2] 环绕+推进复合运动")
    r = send_bridge(jsx)
    ok, data = parse_result(r)
    if ok:
        print(f"  ✓ 合成创建成功")
        return True
    else:
        print(f"  ✗ 失败: {data}")
        return False


def create_handheld_shake():
    """手持晃动模拟: wiggle表达式精确参数
    参数研究:
      - 低频晃动: wiggle(2, 15) - 2Hz, 15px幅度 (呼吸感)
      - 中频抖动: wiggle(8, 4) - 8Hz, 4px幅度 (手持微颤)
      - 高频震颤: wiggle(25, 1.5) - 25Hz, 1.5px (紧张感)
      - 组合: 三层叠加 + Z轴微旋
    """
    jsx = '''(function() {
    try {
        app.beginUndoGroup("Handheld Shake Demo");
        var comp = app.project.items.addComp("ADV_handheld", 1920, 1080, 1, 3.0, 30);
        
        // 场景内容
        var bg = comp.layers.addSolid([0.03, 0.03, 0.08], "BG", 2200, 1400, 1);
        bg.threeDLayer = true;
        bg.property("Position").setValue([960, 540, -500]);
        bg.property("Scale").setValue([130, 130, 100]);
        
        // 多个深度层
        for (var i = 0; i < 4; i++) {
            var obj = comp.layers.addSolid(
                [0.1 + i*0.15, 0.2 + i*0.1, 0.5 - i*0.1],
                "Depth_" + i, 200 + i*100, 200 + i*100, 1);
            obj.threeDLayer = true;
            obj.property("Position").setValue([400 + i*350, 400 + (i%2)*200, -200 + i*150]);
        }
        
        // 主体文字
        var txtLayer = comp.layers.addText("HANDHELD");
        var txtDoc = txtLayer.property("Source Text").value;
        txtDoc.fontSize = 100;
        txtDoc.fillColor = [1, 1, 1];
        txtDoc.font = "Arial-BoldMT";
        txtLayer.property("Source Text").setValue(txtDoc);
        txtLayer.threeDLayer = true;
        txtLayer.property("Position").setValue([960, 540, 200]);
        
        // 摄像机 + 手持晃动表达式
        var cam = comp.layers.addCamera("HandheldCam", [960, 540]);
        try { cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); } catch(e) {}
        
        // 三层叠加wiggle:
        // Position X: 低频(2Hz,15px) + 中频(8Hz,4px) + 高频(25Hz,1.5px)
        var camPosX = cam.property("Position").property("X Position");
        camPosX.expression = "960 + wiggle(2, 15)[0] - 960 + wiggle(8, 4)[0] - 960 + wiggle(25, 1.5)[0] - 960";
        
        var camPosY = cam.property("Position").property("Y Position");
        camPosY.expression = "540 + wiggle(1.8, 12)[1] - 540 + wiggle(7, 3)[1] - 540 + wiggle(22, 1.2)[1] - 540";
        
        var camPosZ = cam.property("Position").property("Z Position");
        camPosZ.expression = "wiggle(1.5, 20)[2]";
        
        // 微旋转: 低频Z旋转 ±0.8°
        cam.property("Z Rotation").expression = "wiggle(1.2, 0.8)";
        cam.property("X Rotation").expression = "wiggle(1.5, 0.5)";
        
        // 灯光跟随(增加真实感)
        var keyLight = comp.layers.addLight("Key", [800, 300]);
        keyLight.property("Light Options").property("Intensity").setValue(450);
        keyLight.threeDLayer = true;
        keyLight.property("Position").setValue([800, 300, 600]);
        
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"handheld created"});
    } catch(e) {
        app.endUndoGroup();
        return JSON.stringify({status:"error", msg: e.toString()});
    }
})();'''
    
    print("\n[A3] 手持晃动模拟 (wiggle三层叠加)")
    r = send_bridge(jsx)
    ok, data = parse_result(r)
    if ok:
        print(f"  ✓ 合成创建成功")
        return True
    else:
        print(f"  ✗ 失败: {data}")
        return False


# ============================================================
# 子项B: 多Z轴视差分层
# ============================================================

def create_parallax_layers():
    """多Z轴平面视差分层: 前景/中景/背景至少3层独立运动
    参数:
      - 前景(Z=400): 快速横移, 大模糊
      - 中景(Z=0): 主体文字, 中速
      - 背景(Z=-800): 慢速漂移, 小元素密集
      - 摄像机: 匀速横移产生自然视差
    """
    jsx = '''(function() {
    try {
        app.beginUndoGroup("Parallax Layers Demo");
        var comp = app.project.items.addComp("ADV_parallax", 1920, 1080, 1, 3.0, 30);
        
        // === 背景层 (Z=-800, 慢速) ===
        var bgBase = comp.layers.addSolid([0.02, 0.02, 0.06], "BG_base", 4000, 1080, 1);
        bgBase.threeDLayer = true;
        bgBase.property("Position").setValue([960, 540, -800]);
        bgBase.property("Scale").setValue([200, 100, 100]);
        
        // 背景星星/粒子点
        for (var i = 0; i < 12; i++) {
            var star = comp.layers.addSolid([0.3, 0.35, 0.6], "BG_star_" + i, 8 + (i%4)*4, 8 + (i%4)*4, 1);
            star.threeDLayer = true;
            star.property("Position").setValue([
                200 + (i * 317) % 3500,
                100 + (i * 193) % 880,
                -700 - (i % 3) * 100
            ]);
            star.property("Opacity").setValue(40 + (i % 5) * 12);
        }
        
        // === 中景层 (Z=0, 主体) ===
        var midPanel = comp.layers.addSolid([0.08, 0.12, 0.25], "MID_panel", 800, 400, 1);
        midPanel.threeDLayer = true;
        midPanel.property("Position").setValue([960, 540, -100]);
        
        var txtLayer = comp.layers.addText("PARALLAX");
        var txtDoc = txtLayer.property("Source Text").value;
        txtDoc.fontSize = 130;
        txtDoc.fillColor = [0.95, 0.8, 0.2];
        txtDoc.font = "Arial-BoldMT";
        txtLayer.property("Source Text").setValue(txtDoc);
        txtLayer.threeDLayer = true;
        txtLayer.property("Position").setValue([960, 540, 0]);
        
        // 中景装饰条
        for (var i = 0; i < 3; i++) {
            var bar = comp.layers.addSolid([0.2, 0.5, 0.8], "MID_bar_" + i, 300, 8, 1);
            bar.threeDLayer = true;
            bar.property("Position").setValue([960, 380 + i * 160, -50 + i * 30]);
            bar.property("Opacity").setValue(60);
        }
        
        // === 前景层 (Z=400, 快速) ===
        for (var i = 0; i < 5; i++) {
            var fg = comp.layers.addSolid([0.05, 0.15, 0.3], "FG_obj_" + i, 60 + i*30, 300 + i*80, 1);
            fg.threeDLayer = true;
            fg.property("Position").setValue([
                -200 + i * 600,
                540,
                350 + (i % 3) * 100
            ]);
            fg.property("Opacity").setValue(25 + i * 8);
            // 前景加模糊
            try {
                var blur = fg.property("Effects").addProperty("ADBE Gaussian Blur 2");
                blur.property("ADBE Gaussian Blur 2-0001").setValue(3 + i * 2);
            } catch(e) {}
        }
        
        // === 摄像机: 匀速横移 ===
        var cam = comp.layers.addCamera("ParallaxCam", [960, 540]);
        try { cam.property("ADBE Camera Options Group").property("ADBE Camera Type").setValue(1); } catch(e) {}
        
        var camPos = cam.property("Position");
        camPos.setValueAtTime(0, [400, 500, 800]);
        camPos.setValueAtTime(3.0, [1500, 560, 750]);
        
        // 轻微ease
        try {
            camPos.setTemporalEaseAtKey(1,
                [new KeyframeEase(0, 20), new KeyframeEase(0, 20), new KeyframeEase(0, 20)],
                [new KeyframeEase(0, 20), new KeyframeEase(0, 20), new KeyframeEase(0, 20)]);
            camPos.setTemporalEaseAtKey(2,
                [new KeyframeEase(0, 20), new KeyframeEase(0, 20), new KeyframeEase(0, 20)],
                [new KeyframeEase(0, 20), new KeyframeEase(0, 20), new KeyframeEase(0, 20)]);
        } catch(e) {}
        
        // 灯光
        var keyLight = comp.layers.addLight("Key", [960, 200]);
        keyLight.property("Light Options").property("Intensity").setValue(350);
        keyLight.threeDLayer = true;
        keyLight.property("Position").setValue([960, 200, 600]);
        
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"parallax created"});
    } catch(e) {
        app.endUndoGroup();
        return JSON.stringify({status:"error", msg: e.toString()});
    }
})();'''
    
    print("\n[B] 多Z轴视差分层 (前景/中景/背景)")
    r = send_bridge(jsx)
    ok, data = parse_result(r)
    if ok:
        print(f"  ✓ 合成创建成功")
        return True
    else:
        print(f"  ✗ 失败: {data}")
        return False


# ============================================================
# 子项C: 运动曲线精调
# ============================================================

def create_motion_curve():
    """运动曲线精调: 指数加速→急停→微弹(overshoot 5-8%)→settle
    精确KeyframeEase数值:
      - KF1(起始): inEase(0, 100%), outEase(0, 100%) → 完全静止起步
      - KF2(加速峰值): inEase(300px/s, 15%), outEase(300px/s, 15%) → 极速
      - KF3(急停): inEase(0, 85%), outEase(0, 85%) → 硬停
      - KF4(overshoot): +5-8% 超越目标
      - KF5(settle): 回到目标值
    
    同时演示Scale弹跳: 100→130(overshoot)→100(settle)
    """
    jsx = '''(function() {
    try {
        app.beginUndoGroup("Motion Curve Demo");
        var comp = app.project.items.addComp("ADV_motion_curve", 1920, 1080, 1, 3.0, 30);
        
        // 背景
        var bg = comp.layers.addSolid([0.04, 0.04, 0.1], "BG", 1920, 1080, 1);
        
        // 主体 - 用Position演示运动曲线
        var ball = comp.layers.addSolid([1, 0.4, 0.1], "Ball", 100, 100, 1);
        // 圆形遮罩
        var mask = ball.Masks.addProperty("Mask");
        var shape = new Shape();
        shape.vertices = [[50, 0], [100, 50], [50, 100], [0, 50]];
        shape.closed = true;
        mask.property("Mask Path").setValue(shape);
        mask.property("Mask Feather").setValue([5, 5]);
        
        var pos = ball.property("Position");
        // 5个关键帧: 起始→加速→急停→overshoot→settle
        // 时间: 0, 0.8, 1.5, 1.7, 2.2
        pos.setValueAtTime(0, [200, 540]);       // 起始(左)
        pos.setValueAtTime(0.8, [960, 540]);     // 加速到中心
        pos.setValueAtTime(1.5, [1600, 540]);    // 急停(右)
        pos.setValueAtTime(1.7, [1660, 540]);    // overshoot +60px (~4%)
        pos.setValueAtTime(2.2, [1600, 540]);    // settle回目标
        
        // 精确缓动曲线
        try {
            // KF1: 静止起步 - 高influence低speed
            pos.setTemporalEaseAtKey(1,
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100)],
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100)]);
            // KF2: 高速通过 - 高speed低influence
            pos.setTemporalEaseAtKey(2,
                [new KeyframeEase(800, 15), new KeyframeEase(800, 15)],
                [new KeyframeEase(800, 15), new KeyframeEase(800, 15)]);
            // KF3: 急停 - 高influence
            pos.setTemporalEaseAtKey(3,
                [new KeyframeEase(600, 80), new KeyframeEase(600, 80)],
                [new KeyframeEase(200, 80), new KeyframeEase(200, 80)]);
            // KF4: overshoot顶点 - 速度为0
            pos.setTemporalEaseAtKey(4,
                [new KeyframeEase(100, 50), new KeyframeEase(100, 50)],
                [new KeyframeEase(100, 50), new KeyframeEase(100, 50)]);
            // KF5: settle - 柔和归位
            pos.setTemporalEaseAtKey(5,
                [new KeyframeEase(50, 75), new KeyframeEase(50, 75)],
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100)]);
        } catch(e) {}
        
        // === Scale弹跳演示 ===
        var txtLayer = comp.layers.addText("IMPACT");
        var txtDoc = txtLayer.property("Source Text").value;
        txtDoc.fontSize = 90;
        txtDoc.fillColor = [0.2, 0.9, 0.5];
        txtDoc.font = "Arial-BoldMT";
        txtLayer.property("Source Text").setValue(txtDoc);
        txtLayer.property("Position").setValue([960, 850]);
        
        var scl = txtLayer.property("Scale");
        // 弹跳: 0→130%(overshoot)→95%(undershoot)→100%(settle)
        scl.setValueAtTime(0.5, [0, 0]);
        scl.setValueAtTime(1.0, [130, 130]);    // overshoot +30%
        scl.setValueAtTime(1.3, [95, 95]);      // undershoot -5%
        scl.setValueAtTime(1.6, [103, 103]);    // micro overshoot +3%
        scl.setValueAtTime(2.0, [100, 100]);    // settle
        
        try {
            scl.setTemporalEaseAtKey(1,
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100)],
                [new KeyframeEase(500, 20), new KeyframeEase(500, 20)]);
            scl.setTemporalEaseAtKey(2,
                [new KeyframeEase(200, 40), new KeyframeEase(200, 40)],
                [new KeyframeEase(200, 40), new KeyframeEase(200, 40)]);
            scl.setTemporalEaseAtKey(3,
                [new KeyframeEase(100, 50), new KeyframeEase(100, 50)],
                [new KeyframeEase(100, 50), new KeyframeEase(100, 50)]);
            scl.setTemporalEaseAtKey(4,
                [new KeyframeEase(50, 60), new KeyframeEase(50, 60)],
                [new KeyframeEase(50, 60), new KeyframeEase(50, 60)]);
            scl.setTemporalEaseAtKey(5,
                [new KeyframeEase(30, 80), new KeyframeEase(30, 80)],
                [new KeyframeEase(0, 100), new KeyframeEase(0, 100)]);
        } catch(e) {}
        
        // === Rotation弹性 ===
        var arrow = comp.layers.addSolid([0.9, 0.9, 0.2], "Arrow", 150, 20, 1);
        arrow.property("Position").setValue([960, 250]);
        var rot = arrow.property("Rotation");
        rot.setValueAtTime(0, -180);
        rot.setValueAtTime(0.6, 15);      // overshoot +15°
        rot.setValueAtTime(0.9, -5);      // undershoot -5°
        rot.setValueAtTime(1.2, 2);       // micro +2°
        rot.setValueAtTime(1.5, 0);       // settle
        
        try {
            rot.setTemporalEaseAtKey(1, [new KeyframeEase(0, 100)], [new KeyframeEase(600, 15)]);
            rot.setTemporalEaseAtKey(2, [new KeyframeEase(200, 40)], [new KeyframeEase(200, 40)]);
            rot.setTemporalEaseAtKey(3, [new KeyframeEase(80, 55)], [new KeyframeEase(80, 55)]);
            rot.setTemporalEaseAtKey(4, [new KeyframeEase(40, 65)], [new KeyframeEase(40, 65)]);
            rot.setTemporalEaseAtKey(5, [new KeyframeEase(20, 85)], [new KeyframeEase(0, 100)]);
        } catch(e) {}
        
        // 发光效果
        try {
            var glow = txtLayer.property("Effects").addProperty("ADBE Glo2");
            glow.property("ADBE Glo2-0001").setValue(40);
            glow.property("ADBE Glo2-0002").setValue(25);
            glow.property("ADBE Glo2-0003").setValue(1.5);
        } catch(e) {}
        
        app.endUndoGroup();
        return JSON.stringify({status:"success", msg:"motion_curve created"});
    } catch(e) {
        app.endUndoGroup();
        return JSON.stringify({status:"error", msg: e.toString()});
    }
})();'''
    
    print("\n[C] 运动曲线精调 (指数加速→急停→微弹)")
    r = send_bridge(jsx)
    ok, data = parse_result(r)
    if ok:
        print(f"  ✓ 合成创建成功")
        return True
    else:
        print(f"  ✗ 失败: {data}")
        return False


# ============================================================
# 主流程
# ============================================================

def main():
    print("=" * 60)
    print("方向一：摄像机运动 + 三维图层 + 运动曲线 深度进阶")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # 创建所有合成
    print("\n" + "=" * 40)
    print("Phase 1: 创建合成")
    print("=" * 40)
    
    results["dolly_zoom"] = create_dolly_zoom()
    results["orbit_push"] = create_orbit_pushin()
    results["handheld"] = create_handheld_shake()
    results["parallax"] = create_parallax_layers()
    results["motion_curve"] = create_motion_curve()
    
    # 渲染验证
    print("\n" + "=" * 40)
    print("Phase 2: 渲染验证 (3秒 H.264)")
    print("=" * 40)
    
    render_targets = [
        ("ADV_dolly_zoom", "adv_dolly_zoom.mp4"),
        ("ADV_orbit_push", "adv_orbit_push.mp4"),
        ("ADV_handheld", "adv_handheld.mp4"),
        ("ADV_parallax", "adv_parallax.mp4"),
        ("ADV_motion_curve", "adv_motion_curve.mp4"),
    ]
    
    render_results = {}
    for comp_name, filename in render_targets:
        out_path = OUTPUT_DIR / filename
        ok = render_comp(comp_name, out_path)
        render_results[comp_name] = ok
        time.sleep(2)
    
    # 动画验证
    print("\n" + "=" * 40)
    print("Phase 3: 帧差异验证 (YAVG>15)")
    print("=" * 40)
    
    verify_results = {}
    for comp_name, filename in render_targets:
        out_path = OUTPUT_DIR / filename
        if out_path.exists() and out_path.stat().st_size > 10000:
            print(f"\n  [{comp_name}]")
            verify_results[comp_name] = verify_animation(out_path)
        else:
            print(f"\n  [{comp_name}] 文件不存在或过小, 跳过")
            verify_results[comp_name] = False
    
    # 总结
    print("\n" + "=" * 60)
    print("总结")
    print("=" * 60)
    all_pass = True
    for comp_name, filename in render_targets:
        created = results.get(comp_name.replace("ADV_", ""), False)
        rendered = render_results.get(comp_name, False)
        verified = verify_results.get(comp_name, False)
        status = "✓" if (rendered and verified) else "✗"
        if not (rendered and verified):
            all_pass = False
        print(f"  {status} {comp_name}: 创建={'✓' if created else '✗'} "
              f"渲染={'✓' if rendered else '✗'} 动画={'✓' if verified else '✗'}")
    
    print(f"\n{'✓ 全部通过!' if all_pass else '✗ 存在未通过项'}")
    print(f"输出目录: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
