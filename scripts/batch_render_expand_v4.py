#!/usr/bin/env python3
"""V4 高级电影感手法：第一批 摄像机运动+Z轴视差+CC粒子+动态点光
基线: V3.1 (batch_render_expand_v3.py, 不改动)
所有新手法已通过 temp/test_feasibility_v4_p1.py 独立实测(>100KB验证):
  摄像机推进 1677KB / 摄像机环绕 2491KB / Z视差 4930KB / CC粒子 11620KB / 点光 1116KB
硬性约束: opacity 0-100; ES3语法(禁let/const/箭头函数); 逐字动画只用ADBE Text Opacity
"""
import json, time, subprocess, sys
from pathlib import Path
from datetime import datetime

BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")
AEP_PATH = Path(r"D:\AE-Work\TextFX_Expand_V4.aep")
OUTPUT_DIR = Path(r"D:\AE-Work\output\textfx_v4")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")

def send_bridge(code, wait=60):
    BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command":"runScript","args":{"code":code},"timestamp":datetime.now().isoformat(),"status":"pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd,ensure_ascii=False), encoding="utf-8")
    time.sleep(1)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") != "waiting" and "result" in r:
                return r
        except: pass
    return {"error":"timeout"}

def render_comp(comp_name, output_path):
    cmd = [str(AERENDER), "-project", str(AEP_PATH), "-comp", comp_name,
           "-output", str(output_path)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None: break
    return proc.returncode == 0 and output_path.exists()

# === V4 第一批特效组合 (4个) ===
COMBOS = [
    {"id":"epic_push","text":"RISE","sub":"EPIC","font":"BebasNeue","sz":220,
     "c1":[1,0.35,0.4],"c2":[0.3,0.6,1],"w":1920,"h":1080,"bg":[0.01,0.01,0.03],
     "style":"epic_push","fmt":"横屏"},
    {"id":"holo_orbit","text":"HOLO","sub":"幻影","font":"Consolas","sz":180,
     "c1":[0.2,0.9,1],"c2":[1,0.2,0.8],"w":1080,"h":1920,"bg":[0.005,0.01,0.04],
     "style":"holo_orbit","fmt":"竖屏"},
    {"id":"ember_burst","text":"BURN","sub":"IGNITE","font":"Anton","sz":220,
     "c1":[1,0.5,0.1],"c2":[1,0.15,0.05],"w":1920,"h":1080,"bg":[0.02,0.005,0.005],
     "style":"ember_burst","fmt":"横屏"},
    {"id":"cyber_depth","text":"GRID","sub":"SYS.ON","font":"Consolas","sz":160,
     "c1":[0,1,0.6],"c2":[0,0.7,1],"w":1920,"h":1080,"bg":[0.005,0.015,0.02],
     "style":"cyber_depth","fmt":"横屏"},
    {"id":"glitch_path","text":"VOID","sub":"ERR","font":"Impact","sz":200,
     "c1":[1,0.1,0.1],"c2":[0.1,1,0.3],"w":1920,"h":1080,"bg":[0.005,0.01,0.005],
     "style":"glitch_path","fmt":"横屏"},
    {"id":"fluid_flow","text":"FLOW","sub":"LIQUID","font":"Anton","sz":180,
     "c1":[0.2,0.8,1],"c2":[0.4,0.3,1],"w":1080,"h":1920,"bg":[0.005,0.01,0.03],
     "style":"fluid_flow","fmt":"竖屏"},
    {"id":"dof_focus","text":"FOCUS","sub":"CINEMA","font":"BebasNeue","sz":210,
     "c1":[1,0.85,0.3],"c2":[0.3,0.5,0.9],"w":1920,"h":1080,"bg":[0.01,0.01,0.02],
     "style":"dof_focus","fmt":"横屏"},
    {"id":"speed_blur","text":"RUSH","sub":"VELOCITY","font":"BebasNeue","sz":230,
     "c1":[1,0.4,0.2],"c2":[0.2,0.7,1],"w":1920,"h":1080,"bg":[0.015,0.005,0.005],
     "style":"speed_blur","fmt":"横屏"},
]

def gen_jsx(c):
    cid = c["id"]; text = c["text"]; sub = c.get("sub",""); font = c["font"]; sz = c["sz"]
    c1 = c["c1"]; c2 = c["c2"]; w = c["w"]; h = c["h"]; bg = c["bg"]
    style = c["style"]
    cx, cy = w//2, h//2

    jsx = f"""(function() {{
    try {{
        for (var _i = app.project.numItems; _i >= 1; _i--) {{
            if (app.project.item(_i) instanceof CompItem && app.project.item(_i).name === "TextFX_{cid}") {{
                app.project.item(_i).remove();
            }}
        }}
        var comp = app.project.items.addComp("TextFX_{cid}", {w}, {h}, 1, 5, 30);
        comp.bgColor = [{bg[0]},{bg[1]},{bg[2]}];
        var bgS = comp.layers.addSolid([{bg[0]},{bg[1]},{bg[2]}], "Bg", {w}, {h}, 1, 5);
        try {{
            var bgFx = bgS.property("Effects").addProperty("ADBE Fractal Noise");
            if(bgFx) {{ bgFx.property("ADBE Fractal Noise-0001").setValue(6);
                bgFx.property("Contrast").setValue(40);
                bgFx.property("Brightness").setValue(-40);
                bgFx.property("Opacity").setValue(15); }}
        }} catch(e) {{}}
"""
    gens = {
        "epic_push": _gen_epic_push,
        "holo_orbit": _gen_holo_orbit,
        "ember_burst": _gen_ember_burst,
        "cyber_depth": _gen_cyber_depth,
        "glitch_path": _gen_glitch_path,
        "fluid_flow": _gen_fluid_flow,
        "dof_focus": _gen_dof_focus,
        "speed_blur": _gen_speed_blur,
    }
    jsx += gens[style](text, sub, font, sz, c1, c2, cx, cy, w, h)

    jsx += """
        return JSON.stringify({status:"success",comp:comp.name,layers:comp.numLayers});
    } catch(e) {
        return JSON.stringify({status:"error",error:e.toString().substring(0,150),line:e.line});
    }
})();"""
    return jsx

# === 基础辅助 (复用V3.1已验证模式) ===
def _glow(var, intensity, radius, threshold, c1, c2):
    """Glow效果 [2026-07-25修正] 属性索引实测: 2=发光阈值 3=发光半径 4=发光强度
    中文版AE不能用英文名('Glow Threshold'等返回null)，必须用索引"""
    return f"""{var}.property(2).setValue({threshold});
        {var}.property(3).setValue({radius});
        {var}.property(4).setValue({intensity});
        try{{{var}.property(12).setValue([{c1[0]},{c1[1]},{c1[2]},1]);
        {var}.property(13).setValue([{c2[0]},{c2[1]},{c2[2]},1]);}}catch(e){{}}"""

def _txt(var, text, font, sz, color, cx, cy, just="CENTER"):
    jc = {"CENTER":"ParagraphJustification.CENTER_JUSTIFY","LEFT":"ParagraphJustification.LEFT_JUSTIFY","RIGHT":"ParagraphJustification.RIGHT_JUSTIFY"}[just]
    return f"""var {var} = comp.layers.addText("{text}");
        var {var}p = {var}.property("Text");
        var {var}d = {var}p.property("ADBE Text Document").value;
        {var}d.font = "{font}"; {var}d.fontSize = {sz};
        {var}d.fillColor = [{color[0]},{color[1]},{color[2]}];
        {var}d.applyFill = true; {var}d.applyStroke = false;
        {var}d.justification = {jc};
        {var}p.property("ADBE Text Document").setValue({var}d);
        {var}.position.setValue([{cx},{cy}]);"""

def _brighter(c, amt=0.2):
    return [min(c[0]+amt,1), min(c[1]+amt,1), min(c[2]+amt,1)]
def _dim(c, f=0.3):
    return [c[0]*f, c[1]*f, c[2]*f]

def _fade(var, tin, tout0=4.5, tout1=5.0):
    """标准淡入淡出(opacity用0-100)"""
    c = '%s.opacity.setValueAtTime(0,0);' % var
    c += '%s.opacity.setValueAtTime(%s,100);' % (var, tin)
    c += '%s.opacity.setValueAtTime(%s,100);' % (var, tout0)
    c += '%s.opacity.setValueAtTime(%s,0);' % (var, tout1)
    return c

def _slideBack(var, x0, x1, y, t0, t1):
    """水平滑入+easeOutBack过冲(2D层用;3D层用_slideBack3d)"""
    dt = round(t1 - t0, 3)
    e = "t=time-inPoint;"
    e += "if(t<%s){[%s,%s];}" % (t0, x0, y)
    e += "else if(t<%s){p=(t-%s)/%s;s=1.70158;p=p-1;" % (t1, t0, dt)
    e += "x=%s+(%s-(%s))*(1+((s+1)*p*p*p+s*p*p));[x,%s];}" % (x0, x1, x0, y)
    e += "else{[%s,%s];}" % (x1, y)
    return '%s.position.expression="%s";' % (var, e)

def _maskCircle(var, r0, r1, t0, t1):
    """圆形遮罩扩散: r0->r1 (贝塞尔近似圆k=0.5523, V3.1实测可靠)"""
    k = 0.5523
    a0 = round(r0 * k, 1)
    a1 = round(r1 * k, 1)
    c = 'var %s_mp=%s.property("ADBE Mask Parade");' % (var, var)
    c += 'var %s_mk=%s_mp.addProperty("Mask");' % (var, var)
    c += 'var %s_ms=%s_mk.property("ADBE Mask Shape");' % (var, var)
    c += 'var %s_c0=new Shape();' % var
    c += '%s_c0.vertices=[[0,-%s],[%s,0],[0,%s],[-%s,0]];' % (var, r0, r0, r0, r0)
    c += '%s_c0.inTangents=[[-%s,0],[0,-%s],[%s,0],[0,%s]];' % (var, a0, a0, a0, a0)
    c += '%s_c0.outTangents=[[%s,0],[0,%s],[-%s,0],[0,-%s]];' % (var, a0, a0, a0, a0)
    c += '%s_c0.closed=true;' % var
    c += 'var %s_c1=new Shape();' % var
    c += '%s_c1.vertices=[[0,-%s],[%s,0],[0,%s],[-%s,0]];' % (var, r1, r1, r1, r1)
    c += '%s_c1.inTangents=[[-%s,0],[0,-%s],[%s,0],[0,%s]];' % (var, a1, a1, a1, a1)
    c += '%s_c1.outTangents=[[%s,0],[0,%s],[-%s,0],[0,-%s]];' % (var, a1, a1, a1, a1)
    c += '%s_c1.closed=true;' % var
    c += '%s_ms.setValueAtTime(%s,%s_c0);' % (var, t0, var)
    c += '%s_ms.setValueAtTime(%s,%s_c1);' % (var, t1, var)
    return c

def _staggerOpacity(var, t_start, t_end):
    """逐字透明度错开入场(ADBE Text Opacity实测可用;ADBE Text Position不存在勿用)"""
    c = 'var %s_an=%s.property("Text").property("ADBE Text Animators");' % (var, var)
    c += 'var %s_a=%s_an.addProperty("ADBE Text Animator");%s_a.name="Stagger";' % (var, var, var)
    c += 'var %s_sl=%s_a.property("ADBE Text Selectors");' % (var, var)
    c += 'var %s_r=%s_sl.addProperty("ADBE Text Selector");' % (var, var)
    c += '%s_r.property("ADBE Text Percent Start").setValue(0);' % var
    c += '%s_r.property("ADBE Text Percent End").setValue(100);' % var
    c += '%s_r.property("ADBE Text Percent Offset").setValueAtTime(%s,0);' % (var, t_start)
    c += '%s_r.property("ADBE Text Percent Offset").setValueAtTime(%s,100);' % (var, t_end)
    c += 'var %s_pr=%s_a.property("ADBE Text Animator Properties");' % (var, var)
    c += 'var %s_op=%s_pr.addProperty("ADBE Text Opacity");%s_op.setValue(0);' % (var, var, var)
    return c


# === V4 新增辅助函数 (全部经 test_feasibility_v4_p1.py 实测>100KB) ===
def _txt3d(var, text, font, sz, color, x, y, z, just="CENTER"):
    """3D文字层: threeDLayer=true + 三维position (摄像机/灯光只影响3D层)"""
    jc = {"CENTER":"ParagraphJustification.CENTER_JUSTIFY","LEFT":"ParagraphJustification.LEFT_JUSTIFY","RIGHT":"ParagraphJustification.RIGHT_JUSTIFY"}[just]
    return f"""var {var} = comp.layers.addText("{text}");
        var {var}p = {var}.property("Text");
        var {var}d = {var}p.property("ADBE Text Document").value;
        {var}d.font = "{font}"; {var}d.fontSize = {sz};
        {var}d.fillColor = [{color[0]},{color[1]},{color[2]}];
        {var}d.applyFill = true; {var}d.applyStroke = false;
        {var}d.justification = {jc};
        {var}p.property("ADBE Text Document").setValue({var}d);
        {var}.threeDLayer = true;
        {var}.position.setValue([{x},{y},{z}]);"""

def _make3d(var, z=0):
    """已有图层转3D并设z深度"""
    return '%s.threeDLayer=true;%s.property("ADBE Transform Group").property("ADBE Position Z").setValue(%s);' % (var, var, z)

def _cameraPush(var, cx, cy, z0, z1, t0, t1):
    """摄像机推进: z0(远)->z1(近), 文字层需threeDLayer=true [实测1677KB PASS]"""
    c = 'var %s=comp.layers.addCamera("%s",[%s,%s]);' % (var, var, cx, cy)
    c += '%s.pointOfInterest.setValue([%s,%s,0]);' % (var, cx, cy)
    c += '%s.position.setValueAtTime(%s,[%s,%s,%s]);' % (var, t0, cx, cy, z0)
    c += '%s.position.setValueAtTime(%s,[%s,%s,%s]);' % (var, t1, cx, cy, z1)
    return c

def _cameraOrbit(var, cx, cy, radius, amp, speed, depth):
    """摄像机环绕: sin弧线运动+注视中心 [实测2491KB PASS]"""
    c = 'var %s=comp.layers.addCamera("%s",[%s,%s]);' % (var, var, cx, cy)
    c += '%s.pointOfInterest.setValue([%s,%s,0]);' % (var, cx, cy)
    e = "t=time-inPoint;var a=Math.sin(t*%s)*%s;" % (speed, amp)
    e += "[%s+Math.sin(a)*%s,%s,-Math.cos(a)*%s];" % (cx, radius, cy, depth)
    c += '%s.position.expression="%s";' % (var, e)
    return c

def _cameraDrift(var, cx, cy, amp, speed, depth):
    """摄像机横向漂移: 配合多层Z深度产生视差 [实测4930KB PASS]"""
    c = 'var %s=comp.layers.addCamera("%s",[%s,%s]);' % (var, var, cx, cy)
    c += '%s.pointOfInterest.setValue([%s,%s,0]);' % (var, cx, cy)
    e = "t=time-inPoint;[%s+Math.sin(t*%s)*%s,%s,-%s];" % (cx, speed, amp, cy, depth)
    c += '%s.position.expression="%s";' % (var, e)
    return c

def _particleWorld(var, x, y, birth_rate, longevity):
    """CC Particle World粒子发射器 [2026-07-25修正版 实测ALL PASS]
    属性索引经实测映射(104个属性): BirthRate=0004, Longevity=0005,
    PosX=0007, PosY=0008, PosZ=0009, Velocity=0016, Gravity=0018,
    Animation=0015(1-14), ParticleType=0023, BirthSize=0024, DeathSize=0025,
    MaxOpacity=0027, BirthColor=0029, DeathColor=0030, TransferMode=0039"""
    c = 'var %s=comp.layers.addSolid([0,0,0],"%s",1920,1080,1,5);' % (var, var)
    c += 'var %s_fx=%s.property("Effects").addProperty("CC Particle World");' % (var, var)
    c += '%s_fx.property("CC Particle World-0004").setValue(%s);' % (var, birth_rate)
    c += '%s_fx.property("CC Particle World-0005").setValue(%s);' % (var, longevity)
    c += '%s_fx.property("CC Particle World-0007").setValue(%s);' % (var, x)
    c += '%s_fx.property("CC Particle World-0008").setValue(%s);' % (var, y)
    c += '%s_fx.property("CC Particle World-0009").setValue(0);' % var
    c += '%s_fx.property("CC Particle World-0010").setValue(200);' % var  # Radius X
    c += '%s_fx.property("CC Particle World-0011").setValue(10);' % var   # Radius Y
    c += '%s_fx.property("CC Particle World-0016").setValue(1.2);' % var  # Velocity
    c += '%s_fx.property("CC Particle World-0018").setValue(-0.3);' % var # Gravity(负=上升)
    c += '%s_fx.property("CC Particle World-0015").setValue(3);' % var    # Animation=Spherical
    c += '%s_fx.property("CC Particle World-0023").setValue(5);' % var    # Star粒子
    c += '%s_fx.property("CC Particle World-0024").setValue(8);' % var    # Birth Size
    c += '%s_fx.property("CC Particle World-0025").setValue(1);' % var    # Death Size
    c += '%s_fx.property("CC Particle World-0027").setValue(90);' % var   # Max Opacity
    c += '%s_fx.property("CC Particle World-0029").setValue([1,0.8,0.2]);' % var  # Birth Color
    c += '%s_fx.property("CC Particle World-0030").setValue([1,0.2,0.05]);' % var # Death Color
    c += '%s_fx.property("CC Particle World-0039").setValue(1);' % var    # TransferMode=Add
    c += '%s.blendMode=5;' % var  # Add混合模式
    return c

def _pointLight(var, x0, y0, z0, x1, y1, z1, t0, t1, color, intensity):
    """动态点光源: 位移制造光影扫过(3D层受光) [实测1116KB PASS]"""
    c = 'var %s=comp.layers.addLight("%s",[%s,%s]);' % (var, var, x0, y0)
    c += '%s.position.setValueAtTime(%s,[%s,%s,%s]);' % (var, t0, x0, y0, z0)
    c += '%s.position.setValueAtTime(%s,[%s,%s,%s]);' % (var, t1, x1, y1, z1)
    c += 'var %s_o=%s.property("ADBE Light Options Group");' % (var, var)
    c += '%s_o.property("ADBE Light Intensity").setValue(%s);' % (var, intensity)
    c += '%s_o.property("ADBE Light Color").setValue([%s,%s,%s]);' % (var, color[0], color[1], color[2])
    c += 'try{%s_o.property("ADBE Light Falloff Type").setValue(1);}catch(e){}' % var
    return c

def _slideBack3d(var, x0, x1, y, z, t0, t1):
    """3D层水平滑入+easeOutBack过冲: [x,y,z]三维position表达式"""
    dt = round(t1 - t0, 3)
    e = "t=time-inPoint;"
    e += "if(t<%s){[%s,%s,%s];}" % (t0, x0, y, z)
    e += "else if(t<%s){p=(t-%s)/%s;s=1.70158;p=p-1;" % (t1, t0, dt)
    e += "x=%s+(%s-(%s))*(1+((s+1)*p*p*p+s*p*p));[x,%s,%s];}" % (x0, x1, x0, y, z)
    e += "else{[%s,%s,%s];}" % (x1, y, z)
    return '%s.position.expression="%s";' % (var, e)


# === V4 第二批辅助函数 (全部经 test_feasibility_v4_p2.py 实测>100KB) ===
def _pathRefLayer(var, w, h, verts, tang=220):
    """隐藏路径参考层(opacity=0的Solid)+mask贝塞尔曲线.
    verts相对图层中心锚点的偏移; in/outTangents自动生成水平切线"""
    vs = "[" + ",".join("[%s,%s]" % (v[0], v[1]) for v in verts) + "]"
    n = len(verts)
    tin = "[" + ",".join("[-%s,0]" % tang for _ in range(n)) + "]"
    tout = "[" + ",".join("[%s,0]" % tang for _ in range(n)) + "]"
    c = 'var %s=comp.layers.addSolid([0,0,0],"%s",%s,%s,1,5);' % (var, var, w, h)
    c += '%s.opacity.setValue(0);' % var
    c += 'var %s_mp=%s.property("ADBE Mask Parade");' % (var, var)
    c += 'var %s_mk=%s_mp.addProperty("Mask");' % (var, var)
    c += 'var %s_ms=%s_mk.property("ADBE Mask Shape");' % (var, var)
    c += 'var %s_s=new Shape();' % var
    c += '%s_s.vertices=%s;' % (var, vs)
    c += '%s_s.inTangents=%s;' % (var, tin)
    c += '%s_s.outTangents=%s;' % (var, tout)
    c += '%s_s.closed=false;' % var
    c += '%s_ms.setValue(%s_s);' % (var, var)
    return c

def _pathMove(var, ref_layer, duration, delay=0, z=None):
    """路径动画: 跟随ref_layer的maskPath [实测328.3KB PASS]
    pointOnPath返回图层坐标, toComp换算到合成空间; z=None返回2D坐标"""
    e = "var ref=thisComp.layer('%s');" % ref_layer
    e += "var tt=Math.max(0,time-%s);" % delay
    e += "var t01=clamp(tt/%s,0,1);" % duration
    e += "var p=ref.mask('Mask 1').maskPath.pointOnPath(t01);"
    if z is None:
        e += "ref.toComp(p);"
    else:
        e += "p=ref.toComp(p);[p[0],p[1],%s];" % z
    return '%s.position.expression="%s";' % (var, e)

def _pathPingPong(var, ref_layer, period, z=None):
    """路径往返循环动画(0->1->0平滑ping-pong, 用于glitch抱动)"""
    e = "var ref=thisComp.layer('%s');" % ref_layer
    e += "var ph=(time/%s)%%2;" % period
    e += "var t01=ph<1?ph:2-ph;"
    e += "var p=ref.mask('Mask 1').maskPath.pointOnPath(t01);"
    if z is None:
        e += "ref.toComp(p);"
    else:
        e += "p=ref.toComp(p);[p[0],p[1],%s];" % z
    return '%s.position.expression="%s";' % (var, e)

def _dof(var, cx, cy, camZ, fd0, fd1, t0, t1, aperture):
    """景深: camera depthOfField + focusDistance焦点转移 [实测891.4KB PASS]
    fd0/fd1=焦跞(镜头到焦点距离), aperture越大景深越浅"""
    c = 'var %s=comp.layers.addCamera("%s",[%s,%s]);' % (var, var, cx, cy)
    c += '%s.pointOfInterest.setValue([%s,%s,0]);' % (var, cx, cy)
    c += '%s.position.setValue([%s,%s,%s]);' % (var, cx, cy, camZ)
    c += 'var %s_o=%s.property("ADBE Camera Options Group");' % (var, var)
    c += '%s_o.property("ADBE Camera Depth of Field").setValue(1);' % var
    c += '%s_o.property("ADBE Camera Focus Distance").setValueAtTime(%s,%s);' % (var, t0, fd0)
    c += '%s_o.property("ADBE Camera Focus Distance").setValueAtTime(%s,%s);' % (var, t1, fd1)
    c += '%s_o.property("ADBE Camera Aperture").setValue(%s);' % (var, aperture)
    return c

def _motionBlur(var, comp_mb=True):
    """运动模糊: comp.motionBlur + layer.motionBlur + 快速位移 [实测545.8KB PASS]"""
    c = 'comp.motionBlur=true;' if comp_mb else ''
    c += '%s.motionBlur=true;' % var
    return c


# === 生成器1: epic_push 电影推进 (摄像机推进+三层Z视差+点光扫过) ===
def _gen_epic_push(text, sub, font, sz, c1, c2, cx, cy, w, h):
    mx, my = int(w*0.5), int(h*0.46)
    return f"""
        // 背景大字(z=-1000, 视差最远层)
        {_txt3d("bgT", text, font, int(sz*2.6), _dim(c1,0.12), mx, int(h*0.42), -1000)}
        {_fade("bgT", 0.8)}
        bgT.opacity.expression = "t=time-inPoint;if(t<0.8){{0;}}else if(t<1.6){{(t-0.8)/0.8*22;}}else{{22;}}";

        // 中景装饰线(z=-500)
        var midBar = comp.layers.addSolid([{c2[0]},{c2[1]},{c2[2]}], "MidBar", {int(w*0.55)}, 3, 1, 5);
        midBar.threeDLayer = true;
        midBar.position.setValue([{mx},{int(h*0.62)},-500]);
        midBar.opacity.setValue(50);
        {_fade("midBar", 0.6)}

        // 主文字(z=0, easeOutBack滑入)
        {_txt3d("L", text, font, sz, _brighter(c1,0.15), mx, my, 0)}
        var gf1=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("gf1", 2.0, 180, 0, c1, _dim(c1,0.4))}
        var gf2=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("gf2", 1.4, 60, 1, c2, _dim(c2,0.3))}
        {_slideBack3d("L", -500, mx, my, 0, 0.2, 1.1)}
        {_fade("L", 0.25)}
        L.rotation.expression = "t=time-inPoint;if(t>1.5){{wiggle(1.5,0.8);}}else{{0;}}";

        // 摄像机推进 (z: -2400 -> -1300, 实测可靠)
        {_cameraPush("cam", mx, int(h*0.5), -2400, -1300, 0, 4.5)}

        // 点光横扫 (光影扫过3D文字)
        {_pointLight("sweepLt", -200, my, -400, w+200, my, -400, 0.3, 3.3, c2, 280)}

        // 副文字 (圆形遮罩揭示, 延迟出场)
        {_txt("subL", sub, font, int(sz*0.32), c2, mx, int(h*0.74))}
        {_maskCircle("subL", 5, 320, 1.0, 1.7)}
        {_fade("subL", 1.05)}
"""


# === 生成器2: holo_orbit 全息投影 (摄像机环绕+扫描线+RGB色差) ===
def _gen_holo_orbit(text, sub, font, sz, c1, c2, cx, cy, w, h):
    mx, my = int(w*0.5), int(h*0.40)
    return f"""
        // 扫描线背景
        var scanL = comp.layers.addSolid([0,0,0], "Scan", {w}, {h}, 1, 5);
        try {{ var vb = scanL.property("Effects").addProperty("ADBE Venetian Blinds");
            if(vb) {{ vb.property("ADBE Venetian Blinds-0001").setValue(85);
                vb.property("ADBE Venetian Blinds-0002").setValue(3);
                vb.property("ADBE Venetian Blinds-0003").setValue(90); }}
        }} catch(e) {{}}
        scanL.blendMode = 5; scanL.opacity.setValue(12);

        // 红色色差层 (blendMode=5叠加, 闪烁)
        {_txt3d("redL", text, font, sz, [1,0.05,0.15], mx+5, my, 20)}
        redL.blendMode = 5;
        var rG = redL.property("Effects").addProperty("ADBE Glo2");
        {_glow("rG", 1.8, 100, 0, [1,0.05,0.15], [0.5,0,0.05])}
        redL.opacity.expression = "t=time-inPoint;base=t<0.3?0:(t<0.6?(t-0.3)/0.3:1);(20+Math.sin(t*11)*15)*base*(t>4.5?(5-t)/0.5:1)";

        // 蓝色色差层
        {_txt3d("bluL", text, font, sz, [0.1,0.2,1], mx-5, my, -20)}
        bluL.blendMode = 5;
        var bG = bluL.property("Effects").addProperty("ADBE Glo2");
        {_glow("bG", 1.8, 100, 0, [0.1,0.2,1], [0.02,0.1,0.5])}
        bluL.opacity.expression = "t=time-inPoint;base=t<0.3?0:(t<0.6?(t-0.3)/0.3:1);(20+Math.cos(t*11)*15)*base*(t>4.5?(5-t)/0.5:1)";

        // 主文字 (3D翻转入场)
        {_txt3d("L", text, font, sz, _brighter(c1,0.1), mx, my, 0)}
        var mg=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("mg", 2.0, 150, 0, c1, _dim(c1,0.4))}
        L.property("ADBE Transform Group").property("ADBE Rotate Y").expression = "t=time-inPoint;if(t<0.2){{105;}}else if(t<1.0){{p=(t-0.2)/0.8;s=1.70158;p=p-1;105*(1+((s+1)*p*p*p+s*p*p));}}else{{0;}}";
        {_fade("L", 0.25)}
        // 全息灯管闪烁
        L.opacity.expression = "t=time-inPoint;base=t<0.25?0:(t<0.6?(t-0.25)/0.35*100:100);out=t>4.5?(5-t)/0.5*100:base;flick=(t>1.2&&Math.random()>0.93)?0.3:1;out*flick";

        // 摄像机环绕 (sin弧线, 实测可靠)
        {_cameraOrbit("cam", int(w*0.5), int(h*0.5), 1500, 0.45, 1.1, 1500)}

        // 副文字 (延迟淡入+呼吸)
        {_txt("subL", sub, font, int(sz*0.38), c2, mx, int(h*0.68))}
        subL.opacity.expression = "t=time-inPoint;if(t<1.2){{0;}}else if(t<1.6){{(t-1.2)/0.4*80;}}else if(t<4.5){{60+Math.sin(t*8)*20;}}else{{(5-t)/0.5*80;}}";
"""


# === 生成器3: ember_burst 粒子爆发 (CC Particle World火星+强Glow+冲击波) ===
def _gen_ember_burst(text, sub, font, sz, c1, c2, cx, cy, w, h):
    mx, my = int(w*0.5), int(h*0.44)
    return f"""
        // 粒子层 (底部发射, 火星上升)
        {_particleWorld("pL", mx, int(h*0.88), 6, 3)}
        var pG = pL.property("Effects").addProperty("ADBE Glo2");
        {_glow("pG", 2.5, 80, 0.3, c1, c2)}
        pL.blendMode = 5;
        {_fade("pL", 0.2)}

        // 冲击波环 (圆形遮罩扩散)
        var ringL = comp.layers.addSolid([{c1[0]},{c1[1]},{c1[2]}], "Ring", {w}, {h}, 1, 5);
        {_maskCircle("ringL", 10, 600, 0.15, 0.9)}
        ringL.blendMode = 5;
        ringL.opacity.expression = "t=time-inPoint;if(t<0.15){{0;}}else if(t<0.4){{70;}}else if(t<1.2){{70*(1-(t-0.4)/0.8);}}else{{0;}}";

        // 红色色差 (爆发抖动)
        {_txt("redL", text, font, sz, [1,0.08,0.05], mx+6, my)}
        redL.blendMode = 5;
        redL.opacity.expression = "t=time-inPoint;base=t<0.2?0:(t<0.4?(t-0.2)/0.2:1);(22+Math.sin(t*14)*16)*base*(t>4.5?(5-t)/0.5:1)";
        redL.position.expression = "t=time-inPoint;if(t>0.4&&t<1.4){{[%s+6+(Math.random()-0.5)*8,%s+(Math.random()-0.5)*6];}}else{{[%s+6,%s];}}";

        // 主文字 (缩放爆发+easeOutBack过冲)
        {_txt("L", text, font, sz, _brighter(c1,0.2), mx, my)}
        var gf1=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("gf1", 2.5, 200, 0, c1, _dim(c1,0.4))}
        var gf2=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("gf2", 1.6, 70, 1, c2, _dim(c2,0.3))}
        L.scale.expression = "t=time-inPoint;if(t<0.15){{[320,320];}}else if(t<0.85){{p=(t-0.15)/0.7;s=1.70158;p=p-1;v=320+(100-320)*(1+((s+1)*p*p*p+s*p*p));[v,v];}}else{{[100,100];}}";
        {_fade("L", 0.2)}

        // 副文字 (底部, 延迟滑入)
        {_txt("subL", sub, font, int(sz*0.3), c2, mx, int(h*0.78))}
        {_slideBack("subL", mx+200, mx, int(h*0.78), 0.9, 1.5)}
        {_fade("subL", 0.95)}
"""


# === 生成器4: cyber_depth 赛博HUD仪表盘 (Z视差+HUD数据层+点光扫过) ===
def _gen_cyber_depth(text, sub, font, sz, c1, c2, cx, cy, w, h):
    mx, my = int(w*0.42), int(h*0.42)
    sx = int(w*0.82)
    return f"""
        // 背景网格层(z=-900, 视差远景)
        var gridL = comp.layers.addSolid([0,0.05,0.08], "Grid", {w}, {h}, 1, 5);
        gridL.threeDLayer = true;
        gridL.position.setValue([{int(w*0.5)},{int(h*0.5)},-900]);
        try {{ var vb = gridL.property("Effects").addProperty("ADBE Venetian Blinds");
            if(vb) {{ vb.property("ADBE Venetian Blinds-0001").setValue(45);
                vb.property("ADBE Venetian Blinds-0002").setValue(6);
                vb.property("ADBE Venetian Blinds-0003").setValue(0); }}
        }} catch(e) {{}}
        gridL.opacity.setValue(35);
        {_fade("gridL", 0.5)}

        // 数据流层(z=-450, 视差中景)
        var dataL = comp.layers.addText("01001 SYS 11010 NET 00101 PWR 10110");
        var dataLp = dataL.property("Text");
        var dataLd = dataLp.property("ADBE Text Document").value;
        dataLd.font = "Consolas"; dataLd.fontSize = 42;
        dataLd.fillColor = [{c2[0]},{c2[1]},{c2[2]}];
        dataLd.applyFill = true; dataLd.applyStroke = false;
        dataLp.property("ADBE Text Document").setValue(dataLd);
        dataL.threeDLayer = true;
        dataL.position.setValue([{int(w*0.5)},{int(h*0.16)},-450]);
        dataL.opacity.expression = "t=time-inPoint;if(t<0.4){{0;}}else if(t<0.8){{(t-0.4)/0.4*40;}}else{{30+Math.sin(t*5)*10;}}";

        // 主文字(z=0, 左缘滑入+逐字加载重叠)
        {_txt3d("L", text, font, sz, _brighter(c1,0.1), mx, my, 0, "LEFT")}
        var mg=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("mg", 2.0, 130, 0, c1, _dim(c1,0.4))}
        {_slideBack3d("L", -400, mx, my, 0, 0.2, 0.9)}
        {_staggerOpacity("L", 0.3, 1.5)}
        {_fade("L", 0.2)}

        // 副文字 (右侧, 延迟+呼吸闪烁)
        {_txt("subL", sub, font, int(sz*0.4), c2, sx, my, "RIGHT")}
        subL.opacity.expression = "t=time-inPoint;if(t<1.3){{0;}}else if(t<1.7){{(t-1.3)/0.4*90;}}else if(t<4.5){{70+Math.sin(t*7)*20;}}else{{(5-t)/0.5*90;}}";

        // 摄像机横漂 (视差驱动)
        {_cameraDrift("cam", int(w*0.5), int(h*0.5), 250, 0.7, 1600)}

        // 点光扫过 (HUD冷光)
        {_pointLight("scanLt", -100, int(h*0.3), -300, w+100, int(h*0.5), -300, 0.5, 3.5, [0.2,0.8,1], 250)}

        // 进度条 (左下)
        var barBg = comp.layers.addSolid([0.1,0.15,0.2], "BarBg", {int(w*0.3)}, 8, 1, 5);
        barBg.position.setValue([{int(w*0.19)},{int(h*0.88)}]);
        barBg.opacity.setValue(60);
        {_fade("barBg", 0.5)}
        var barF = comp.layers.addSolid([{c1[0]},{c1[1]},{c1[2]}], "BarFill", {int(w*0.3)}, 8, 1, 5);
        barF.position.setValue([{int(w*0.19)},{int(h*0.88)}]);
        barF.scale.expression = "t=time-inPoint;if(t<0.5){{[0,100];}}else if(t<3){{[(t-0.5)/2.5*100,100];}}else{{[100,100];}}";
        {_fade("barF", 0.55)}
"""


# === 生成器5: glitch_path 故障艺术进阶 (RGB碎片沿路径+摄像机抖动) ===
def _gen_glitch_path(text, sub, font, sz, c1, c2, cx, cy, w, h):
    mx, my = int(w*0.5), int(h*0.5)
    return f"""
        // 路径参考层 (文字区域内锅齿路径)
        {_pathRefLayer("pathRef", w, h, [[-300,-40],[-100,40],[100,-40],[300,40]], 120)}

        // 红色碎片沿路径往返抱动 (blendMode=5叠加)
        {_txt3d("redL", text, font, sz, [1,0.05,0.1], mx, my, 0)}
        redL.blendMode = 5;
        redL.opacity.expression = "t=time-inPoint;base=t<0.2?0:(t<0.5?(t-0.2)/0.3:1);(35+Math.sin(t*13)*25)*base*(t>4.5?(5-t)/0.5:1)";
        {_pathPingPong("redL", "pathRef", 1.3, 0)}

        // 蓝色碎片沿路径往返抱动 (不同周期)
        {_txt3d("bluL", text, font, sz, [0.1,0.2,1], mx, my, 0)}
        bluL.blendMode = 5;
        bluL.opacity.expression = "t=time-inPoint;base=t<0.25?0:(t<0.55?(t-0.25)/0.3:1);(35+Math.cos(t*11)*25)*base*(t>4.5?(5-t)/0.5:1)";
        {_pathPingPong("bluL", "pathRef", 1.7, 0)}

        // 主文字 (湍流置换故障+Glow)
        {_txt3d("L", text, font, sz, _brighter(c1,0.2), mx, my, 0)}
        var mg=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("mg", 2.0, 140, 0, c1, _dim(c1,0.4))}
        try {{ var td = L.property("Effects").addProperty("ADBE Turbulent Displace");
            td.property("ADBE Turbulent Displace-0001").setValue(8);
            td.property("ADBE Turbulent Displace-0002").setValue(25);
            td.property("ADBE Turbulent Displace-0004").expression = "time*60"; }} catch(e) {{}}
        {_fade("L", 0.2)}

        // 摄像机抖动 (seedRandom阶梯随机, 8步/秒)
        var cam = comp.layers.addCamera("Cam", [{mx},{my}]);
        cam.pointOfInterest.setValue([{mx},{my},0]);
        cam.position.expression = "seedRandom(Math.floor(time*8),true);[{mx}+(Math.random()-0.5)*30,{my}+(Math.random()-0.5)*30,-1600];";

        // 副文字 (左上角, 延迟+呼吸闪烁)
        {_txt("subL", sub, font, int(sz*0.35), c2, int(w*0.15), int(h*0.15), "LEFT")}
        subL.opacity.expression = "t=time-inPoint;base=t<0.8?0:(t<1.1?(t-0.8)/0.3:1);(50+Math.sin(t*9)*20)*base*(t>4.5?(5-t)/0.5:1)";
"""


# === 生成器6: fluid_flow 流体模拟 (湍流变形+光球沿路径流动) ===
def _gen_fluid_flow(text, sub, font, sz, c1, c2, cx, cy, w, h):
    mx, my = int(w*0.5), int(h*0.32)
    return f"""
        // 路径参考层 (S形曲线向下流动)
        {_pathRefLayer("pathRef", w, h, [[-350,-700],[200,-300],[-200,200],[300,700]], 250)}

        // 主文字 (湍流置换流体扭曲+摇摆)
        {_txt("L", text, font, sz, _brighter(c1,0.15), mx, my)}
        var mg=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("mg", 2.2, 160, 0, c1, _dim(c1,0.4))}
        try {{ var td = L.property("Effects").addProperty("ADBE Turbulent Displace");
            td.property("ADBE Turbulent Displace-0001").setValue(12);
            td.property("ADBE Turbulent Displace-0002").setValue(60);
            td.property("ADBE Turbulent Displace-0004").expression = "time*40"; }} catch(e) {{}}
        {_fade("L", 0.3)}
        L.position.expression = "t=time-inPoint;[{mx}+Math.sin(t*1.5)*15,{my}+Math.cos(t*1.2)*10];";

        // 流动光球1 (沿路径, 强Glow+叠加)
        var orb1 = comp.layers.addSolid([{c1[0]},{c1[1]},{c1[2]}], "Orb1", 40, 40, 1, 5);
        var og1 = orb1.property("Effects").addProperty("ADBE Glo2");
        {_glow("og1", 2.5, 60, 0, c1, c2)}
        orb1.blendMode = 5;
        {_pathMove("orb1", "pathRef", 2.5, 0.2)}
        {_fade("orb1", 0.25)}

        // 流动光球2 (延迟)
        var orb2 = comp.layers.addSolid([{c2[0]},{c2[1]},{c2[2]}], "Orb2", 30, 30, 1, 5);
        var og2 = orb2.property("Effects").addProperty("ADBE Glo2");
        {_glow("og2", 2.5, 50, 0, c2, c1)}
        orb2.blendMode = 5;
        {_pathMove("orb2", "pathRef", 2.5, 0.7)}
        {_fade("orb2", 0.75)}

        // 流动光球3 (延迟)
        var orb3 = comp.layers.addSolid([{c1[0]},{c1[1]},{c1[2]}], "Orb3", 24, 24, 1, 5);
        var og3 = orb3.property("Effects").addProperty("ADBE Glo2");
        {_glow("og3", 2.5, 40, 0, c1, c2)}
        orb3.blendMode = 5;
        {_pathMove("orb3", "pathRef", 2.5, 1.2)}
        {_fade("orb3", 1.25)}

        // 副文字 (下方, 延迟滑入)
        {_txt("subL", sub, font, int(sz*0.4), c2, mx, int(h*0.75))}
        {_slideBack("subL", mx+180, mx, int(h*0.75), 0.9, 1.5)}
        {_fade("subL", 0.95)}
"""


# === 生成器7: dof_focus 景深电影 (焦点从背景拉至主字+虚化) ===
def _gen_dof_focus(text, sub, font, sz, c1, c2, cx, cy, w, h):
    mx, my = int(w*0.5), int(h*0.52)
    return f"""
        // 背景文字 (远层z=-900, 先清晰后虚化)
        {_txt3d("bgL", "DEPTH", font, int(sz*1.8), _dim(c2,0.35), mx, int(h*0.35), -900)}
        {_fade("bgL", 0.4)}

        // 主文字 (z=0, 焦点拉到这里)
        {_txt3d("L", text, font, sz, _brighter(c1,0.15), mx, my, 0)}
        var mg=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("mg", 2.0, 150, 0, c1, _dim(c1,0.4))}
        {_fade("L", 0.3)}
        L.scale.expression = "t=time-inPoint;if(t<0.3){{[70,70,100];}}else if(t<1.2){{p=(t-0.3)/0.9;v=70+30*ease(p,0,1,0,1);[v,v,100];}}else{{[100,100,100];}}";

        // 摄像机+景深 (焦点从背景700拉到主字1600, aperture=10)
        {_dof("cam", mx, int(h*0.5), -1600, 700, 1600, 0.3, 2.5, 10)}

        // 副文字 (下方, 延迟滑入)
        {_txt("subL", sub, font, int(sz*0.32), c2, mx, int(h*0.82))}
        {_slideBack("subL", mx-200, mx, int(h*0.82), 1.0, 1.6)}
        {_fade("subL", 1.05)}
"""


# === 生成器8: speed_blur 运动模糊冲击 (高速滑入+拖影) ===
def _gen_speed_blur(text, sub, font, sz, c1, c2, cx, cy, w, h):
    mx, my = int(w*0.55), int(h*0.45)
    return f"""
        // 速度线背景 (水平细条)
        var lineL = comp.layers.addSolid([{c2[0]*0.3},{c2[1]*0.3},{c2[2]*0.3}], "Lines", {w}, {h}, 1, 5);
        try {{ var vb = lineL.property("Effects").addProperty("ADBE Venetian Blinds");
            if(vb) {{ vb.property("ADBE Venetian Blinds-0001").setValue(90);
                vb.property("ADBE Venetian Blinds-0002").setValue(5);
                vb.property("ADBE Venetian Blinds-0003").setValue(0); }}
        }} catch(e) {{}}
        lineL.opacity.setValue(25);
        {_fade("lineL", 0.3)}

        // 主文字 (高速关键帧滑入+运动模糊, 0.4s内-600->mx)
        {_txt("L", text, font, sz, _brighter(c1,0.2), mx, my)}
        var mg=L.property("Effects").addProperty("ADBE Glo2");
        {_glow("mg", 2.0, 130, 0, c1, _dim(c1,0.4))}
        {_motionBlur("L")}
        L.position.setValueAtTime(0.2, [-600,{my}]);
        L.position.setValueAtTime(0.6, [{mx},{my}]);
        {_fade("L", 0.2)}

        // 红色残影层 (延迟跟随+运动模糊)
        {_txt("redL", text, font, sz, [1,0.1,0.1], mx, my)}
        redL.blendMode = 5;
        {_motionBlur("redL", False)}
        redL.opacity.expression = "t=time-inPoint;base=t<0.25?0:(t<0.5?(t-0.25)/0.25:1);(30+Math.sin(t*12)*15)*base*(t>4.5?(5-t)/0.5:1)";
        redL.position.setValueAtTime(0.25, [-750,{my}]);
        redL.position.setValueAtTime(0.65, [{mx}+8,{my}]);

        // 副文字 (右下, 延迟滑入)
        {_txt("subL", sub, font, int(sz*0.32), c2, int(w*0.82), int(h*0.8), "RIGHT")}
        {_slideBack("subL", int(w*0.82)+200, int(w*0.82), int(h*0.8), 0.8, 1.4)}
        {_fade("subL", 0.85)}
"""


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("="*60)
    print("V4 Phase1: 4个高级电影感特效 (摄像机/视差/粒子/点光)")
    print("="*60)

    created = []
    failed = []
    for i, combo in enumerate(COMBOS):
        comp_name = f"TextFX_{combo['id']}"
        print(f"[{i+1}/{len(COMBOS)}] {comp_name} ({combo['fmt']})...")
        jsx = gen_jsx(combo)
        r = send_bridge(jsx, 45)
        inner = r.get("result", {})
        if isinstance(inner, dict) and inner.get("success"):
            result_str = inner.get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    if parsed.get("status") == "success":
                        created.append(comp_name)
                        print(f"  OK ({parsed.get('layers',0)} layers)")
                        continue
                    else:
                        print(f"  FAIL: {parsed.get('error','?')[:100]}")
                except: pass
        print(f"  FAIL: {json.dumps(r, ensure_ascii=False)[:250]}")
        failed.append(combo["id"])

    print(f"\nCreated {len(created)}/{len(COMBOS)} comps")
    if failed:
        print(f"Failed: {', '.join(failed)}")
    if not created:
        print("No comps. Exiting.")
        sys.exit(1)

    print("\nSaving project...")
    aep_unix = str(AEP_PATH).replace("\\", "/")
    save_code = f'(function(){{try{{var f=new File("{aep_unix}");app.project.save(f);return "ok";}}catch(e){{return e.toString();}}}})();'
    send_bridge(save_code, 15)
    print(f"  Saved: {AEP_PATH}")

    print(f"\n{'='*60}\nRendering {len(created)} comps...\n{'='*60}\n")
    rendered = []
    for comp_name in created:
        combo_id = comp_name.replace("TextFX_", "")
        output_file = OUTPUT_DIR / f"TextFX_{combo_id}_v4.mp4"
        print(f"  Rendering {comp_name}...")
        ok = render_comp(comp_name, output_file)
        if ok:
            kb = output_file.stat().st_size / 1024
            verdict = "PASS" if kb > 100 else "FAIL(<100KB)"
            print(f"  {output_file.name}: {kb:.1f} KB -> {verdict}")
            rendered.append({"comp":comp_name, "file":str(output_file), "size_kb":round(kb,1)})
        else:
            print(f"  RENDER FAIL: {output_file}")

    print(f"\n{'='*60}")
    print(f"V4 PHASE1 SUMMARY: {len(rendered)}/{len(COMBOS)} rendered")
    print(f"{'='*60}")
    all_pass = True
    for r in rendered:
        v = "PASS" if r["size_kb"] > 100 else "FAIL"
        if r["size_kb"] <= 100: all_pass = False
        print(f"  {r['comp']} -> {r['size_kb']} KB  {v}")
    print(f"\n全部>100KB: {'YES' if all_pass and len(rendered)==len(COMBOS) else 'NO'}")
