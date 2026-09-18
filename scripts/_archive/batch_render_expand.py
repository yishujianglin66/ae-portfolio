#!/usr/bin/env python3
"""Phase 1+2 扩充渲染：20个新特效组合，填补风格缺口"""
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")
AEP_PATH = Path(r"D:\AE-Work\TextFX_Expand.aep")
OUTPUT_DIR = Path(r"D:\AE-Work\output\textfx_batch")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")

def send_bridge(code, wait=45):
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
    cmd = [str(AERENDER), "-project", str(AEP_PATH), "-comp", comp_name, "-output", str(output_path)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="ignore")
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None: break
    return proc.returncode == 0 and output_path.exists()

# === 20个扩充组合：P0(10个) + P1(10个) ===
# 竖屏12个 + 横屏8个 = 20个
COMBOS = [
    # ===== P0: 大缺口填补 (10个) =====
    # P0-1: 弹性果冻字 (竖屏) - 对标 Aest
    {"id":"jelly_bounce_v", "text":"BOUNCE", "font":"BebasNeue", "sz":180,
     "color":[1,0.4,0.7], "w":1080,"h":1920, "bg":[0.03,0.01,0.04],
     "fx":[("glow_pink",{}),("wiggly_jelly",{})], "anim":"jelly_pop", "fmt":"竖屏"},
    # P0-2: 电影感极简字 (横屏) - 对标 Kyoukai
    {"id":"cinematic_min", "text":"SILENCE", "font":"Georgia-Bold", "sz":120,
     "color":[0.9,0.9,0.9], "w":1920,"h":1080, "bg":[0.02,0.02,0.02],
     "fx":[("shadow_clean",{})], "anim":"tracking_blur", "fmt":"横屏"},
    # P0-3: Lo-fi暖调手写字 (竖屏) - 对标 Lo-fi Anime Edits
    {"id":"lofi_warmth", "text":"午后", "font":"KaiTi", "sz":130,
     "color":[0.95,0.85,0.7], "w":1080,"h":1920, "bg":[0.12,0.08,0.05],
     "fx":[("fractal_grain",{}),("tint_warm",{}),("glow_warm",{})], "anim":"blur_reveal", "fmt":"竖屏"},
    # P0-4: 柔焦氛围字 (竖屏) - 对标 Zenit/@softamv
    {"id":"soft_bokeh", "text":"梦境", "font":"DengXian-Bold", "sz":140,
     "color":[0.8,0.7,1], "w":1080,"h":1920, "bg":[0.04,0.02,0.06],
     "fx":[("glow_soft",{}),("fractal_bokeh",{})], "anim":"fade_float", "fmt":"竖屏"},
    # P0-5: 无缝转场文字 (横屏) - 对标 Flux
    {"id":"seamless_trans", "text":"FLOW", "font":"Oswald-Bold", "sz":160,
     "color":[1,1,1], "w":1920,"h":1080, "bg":[0.03,0.03,0.03],
     "fx":[("glow_white",{}),("turb_smooth",{})], "anim":"slide_through", "fmt":"横屏"},
    # P0-6: 弹性果冻字 (横屏版)
    {"id":"jelly_bounce_h", "text":"JELLY", "font":"Anton", "sz":170,
     "color":[0.3,1,0.6], "w":1920,"h":1080, "bg":[0.02,0.04,0.03],
     "fx":[("glow_green",{}),("wiggly_jelly",{})], "anim":"jelly_pop", "fmt":"横屏"},
    # P0-7: 柔焦氛围字 (横屏版)
    {"id":"soft_bokeh_h", "text":"DREAM", "font":"DengXian-Bold", "sz":130,
     "color":[1,0.8,0.9], "w":1920,"h":1080, "bg":[0.05,0.02,0.04],
     "fx":[("glow_soft",{}),("fractal_bokeh",{})], "anim":"fade_float", "fmt":"横屏"},
    # P0-8: Lo-fi手写 (横屏版)
    {"id":"lofi_warmth_h", "text":"暖阳", "font":"KaiTi", "sz":140,
     "color":[0.9,0.8,0.6], "w":1920,"h":1080, "bg":[0.1,0.07,0.04],
     "fx":[("fractal_grain",{}),("tint_warm",{})], "anim":"blur_reveal", "fmt":"横屏"},
    # P0-9: 电影感极简 (竖屏)
    {"id":"cinematic_min_v", "text":"静寂", "font":"Georgia-Bold", "sz":130,
     "color":[0.85,0.85,0.85], "w":1080,"h":1920, "bg":[0.01,0.01,0.01],
     "fx":[("shadow_clean",{})], "anim":"tracking_blur", "fmt":"竖屏"},
    # P0-10: 转场文字 (竖屏)
    {"id":"seamless_trans_v", "text":"移転", "font":"Oswald-Bold", "sz":150,
     "color":[0.9,0.9,1], "w":1080,"h":1920, "bg":[0.02,0.02,0.04],
     "fx":[("glow_blue",{}),("turb_smooth",{})], "anim":"slide_through", "fmt":"竖屏"},

    # ===== P1: 高优先级扩充 (10个) =====
    # P1-1: 全息投影字 (横屏) - 对标 Nxnja/CyberCore
    {"id":"holo_proj", "text":"HOLOGRAM", "font":"Consolas", "sz":110,
     "color":[0.3,0.8,1], "w":1920,"h":1080, "bg":[0.01,0.02,0.05],
     "fx":[("glow_blue",{}),("venetian_holo",{}),("turb_holo",{})], "anim":"scan_line", "fmt":"横屏"},
    # P1-2: 文字破碎重组 (横屏) - 对标 Nxnja
    {"id":"text_shatter", "text":"BREAK", "font":"Impact", "sz":190,
     "color":[1,0.2,0.2], "w":1920,"h":1080, "bg":[0.02,0.01,0.01],
     "fx":[("turb_glitch",{}),("glow_red",{})], "anim":"shatter_pop", "fmt":"横屏"},
    # P1-3: 3D景深伪效果 (横屏) - 对标 DizzyAMV
    {"id":"depth_3d", "text":"DEPTH", "font":"Anton", "sz":180,
     "color":[0.7,0.7,0.8], "w":1920,"h":1080, "bg":[0.02,0.02,0.03],
     "fx":[("glow_warm",{}),("shadow_depth",{})], "anim":"push_in", "fmt":"横屏"},
    # P1-4: UI/HUD界面字 (竖屏) - 对标 CyberCore
    {"id":"ui_hud", "text":"SYSTEM", "font":"Consolas", "sz":100,
     "color":[0,1,0.5], "w":1080,"h":1920, "bg":[0.01,0.02,0.01],
     "fx":[("glow_green",{}),("venetian_scan",{})], "anim":"data_load", "fmt":"竖屏"},
    # P1-5: 复古像素字 (横屏) - 对标 Retro AMV
    {"id":"retro_pixel", "text":"RETRO", "font":"Oswald-Bold", "sz":150,
     "color":[1,0.6,0.3], "w":1920,"h":1080, "bg":[0.06,0.03,0.01],
     "fx":[("mosaic_retro",{}),("fractal_vhs",{}),("tint_retro",{})], "anim":"vhs_in", "fmt":"横屏"},
    # P1-6: 前景遮挡字 (横屏) - 对标 Mephis
    {"id":"fg_occlude", "text":"BEHIND", "font":"SimHei", "sz":160,
     "color":[1,1,1], "w":1920,"h":1080, "bg":[0.03,0.03,0.05],
     "fx":[("glow_white",{})], "anim":"occlude_reveal", "fmt":"横屏"},
    # P1-7: 全息投影 (竖屏)
    {"id":"holo_proj_v", "text":"投影", "font":"Consolas", "sz":120,
     "color":[0.4,0.9,1], "w":1080,"h":1920, "bg":[0.01,0.02,0.04],
     "fx":[("glow_blue",{}),("venetian_holo",{})], "anim":"scan_line", "fmt":"竖屏"},
    # P1-8: 文字破碎 (竖屏)
    {"id":"text_shatter_v", "text":"砕裂", "font":"Impact", "sz":200,
     "color":[1,0.3,0.1], "w":1080,"h":1920, "bg":[0.02,0.01,0.01],
     "fx":[("turb_glitch",{}),("glow_red",{})], "anim":"shatter_pop", "fmt":"竖屏"},
    # P1-9: 复古像素 (竖屏)
    {"id":"retro_pixel_v", "text":"8BIT", "font":"Oswald-Bold", "sz":160,
     "color":[1,0.5,0.8], "w":1080,"h":1920, "bg":[0.04,0.02,0.05],
     "fx":[("mosaic_retro",{}),("tint_retro",{})], "anim":"vhs_in", "fmt":"竖屏"},
    # P1-10: UI/HUD (横屏)
    {"id":"ui_hud_h", "text":"DATA.LINK", "font":"Consolas", "sz":90,
     "color":[0,0.8,1], "w":1920,"h":1080, "bg":[0.01,0.01,0.03],
     "fx":[("glow_cyan",{}),("venetian_scan",{})], "anim":"data_load", "fmt":"横屏"},
]

def gen_jsx(c):
    cid = c["id"]; text = c["text"]; font = c["font"]; sz = c["sz"]
    color = c["color"]; w = c["w"]; h = c["h"]; bg = c["bg"]
    cx, cy = w//2, h//2

    jsx = f"""(function() {{
    try {{
        var comp = app.project.items.addComp("TextFX_{cid}", {w}, {h}, 1, 4, 30);
        comp.bgColor = [{bg[0]},{bg[1]},{bg[2]}];
        var L = comp.layers.addText("{text}");
        var tp = L.property("Text");
        var td = tp.property("ADBE Text Document").value;
        td.font = "{font}";
        td.fontSize = {sz};
        td.fillColor = [{color[0]},{color[1]},{color[2]}];
        td.applyFill = true;
        td.applyStroke = false;
        td.justification = ParagraphJustification.CENTER_JUSTIFY;
        tp.property("ADBE Text Document").setValue(td);
        L.position.setValue([{cx},{cy}]);
"""
    # === 入场动画 ===
    anim = c["anim"]
    if anim == "jelly_pop":
        jsx += """
        L.scale.setValueAtTime(0,[0,0]);
        L.scale.setValueAtTime(0.15,[130,130]);
        L.scale.setValueAtTime(0.3,[80,80]);
        L.scale.setValueAtTime(0.45,[115,115]);
        L.scale.setValueAtTime(0.6,[95,95]);
        L.scale.setValueAtTime(0.75,[103,103]);
        L.scale.setValueAtTime(0.9,[100,100]);
"""
    elif anim == "tracking_blur":
        jsx += """
        var an0=tp.property("ADBE Text Animators");
        var a0=an0.addProperty("ADBE Text Animator");a0.name="TrackBlur";
        var sl0=a0.property("ADBE Text Selectors");
        var r0=sl0.addProperty("ADBE Text Selector");
        r0.property("ADBE Text Percent Start").setValue(0);
        r0.property("ADBE Text Percent End").setValue(100);
        r0.property("ADBE Text Percent Offset").setValueAtTime(0,-100);
        r0.property("ADBE Text Percent Offset").setValueAtTime(2.5,0);
        var pr0=a0.property("ADBE Text Animator Properties");
        var tr0=pr0.addProperty("ADBE Text Tracking Amount");tr0.setValue(-50);
        var bl0=pr0.addProperty("ADBE Text Blur");bl0.setValue([30,30]);
        L.opacity.setValueAtTime(0,0);L.opacity.setValueAtTime(1,100);
"""
    elif anim == "blur_reveal":
        jsx += """
        var an0=tp.property("ADBE Text Animators");
        var a0=an0.addProperty("ADBE Text Animator");a0.name="BlurReveal";
        var sl0=a0.property("ADBE Text Selectors");
        var r0=sl0.addProperty("ADBE Text Selector");
        r0.property("ADBE Text Percent Start").setValue(0);
        r0.property("ADBE Text Percent End").setValue(100);
        r0.property("ADBE Text Percent Offset").setValueAtTime(0,-100);
        r0.property("ADBE Text Percent Offset").setValueAtTime(2,0);
        var pr0=a0.property("ADBE Text Animator Properties");
        var bl0=pr0.addProperty("ADBE Text Blur");bl0.setValue([40,40]);
"""
    elif anim == "fade_float":
        jsx += """
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(1.5,100);
        L.position.setValueAtTime(0,[{cx},{cy}+30]);
        L.position.setValueAtTime(1.5,[{cx},{cy}]);
""".replace("{cx}",str(cx)).replace("{cy}",str(cy))
    elif anim == "slide_through":
        jsx += f"""
        L.position.setValueAtTime(0,[{cx},{cy}+200]);
        L.position.setValueAtTime(0.4,[{cx},{cy}]);
        L.position.setValueAtTime(3.6,[{cx},{cy}]);
        L.position.setValueAtTime(4,[{cx},{cy}-200]);
"""
    elif anim == "scan_line":
        jsx += """
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(0.5,100);
        L.scale.setValueAtTime(0,[100,0]);
        L.scale.setValueAtTime(0.8,[100,100]);
"""
    elif anim == "shatter_pop":
        jsx += """
        L.scale.setValueAtTime(0,[0,0]);
        L.scale.setValueAtTime(0.1,[140,140]);
        L.scale.setValueAtTime(0.2,[90,90]);
        L.scale.setValueAtTime(0.3,[100,100]);
"""
    elif anim == "push_in":
        jsx += """
        L.scale.setValueAtTime(0,[40,40]);
        L.scale.setValueAtTime(1,[100,100]);
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(0.5,100);
"""
    elif anim == "data_load":
        jsx += """
        var an0=tp.property("ADBE Text Animators");
        var a0=an0.addProperty("ADBE Text Animator");a0.name="DataLoad";
        var sl0=a0.property("ADBE Text Selectors");
        var r0=sl0.addProperty("ADBE Text Selector");
        r0.property("ADBE Text Percent Start").setValue(0);
        r0.property("ADBE Text Percent End").setValue(0);
        r0.property("ADBE Text Percent Offset").setValueAtTime(0,0);
        r0.property("ADBE Text Percent Offset").setValueAtTime(2,100);
        var pr0=a0.property("ADBE Text Animator Properties");
        var op0=pr0.addProperty("ADBE Text Opacity");op0.setValue(0);
"""
    elif anim == "vhs_in":
        jsx += """
        L.scale.setValueAtTime(0,[100,0]);
        L.scale.setValueAtTime(0.3,[100,100]);
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(0.2,100);
"""
    elif anim == "occlude_reveal":
        jsx += """
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(0.3,0);
        L.opacity.setValueAtTime(1,100);
        L.scale.setValueAtTime(0,[100,100]);
        L.scale.setValueAtTime(0.5,[100,100]);
"""

    # 淡入淡出
    if anim not in ["tracking_blur","fade_float","scan_line","push_in","data_load","vhs_in","occlude_reveal"]:
        jsx += """
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(0.3,100);
        L.opacity.setValueAtTime(3.5,100);
        L.opacity.setValueAtTime(4,0);
"""

    # === 特效 ===
    for fx_item in c["fx"]:
        fx = fx_item[0] if isinstance(fx_item, tuple) else fx_item
        opts = fx_item[1] if isinstance(fx_item, tuple) and len(fx_item)>1 else {}

        if fx == "glow_pink":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.15);g.property("ADBE Glo2-0003").setValue(35);
        g.property("ADBE Glo2-0004").setValue(3.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([1,0.2,0.6,1]);g.property("ADBE Glo2-0007").setValue([0.3,0.5,1,1]);}catch(e){}
"""
        elif fx == "glow_green":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.2);g.property("ADBE Glo2-0003").setValue(20);
        g.property("ADBE Glo2-0004").setValue(2.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0,1,0.3,1]);g.property("ADBE Glo2-0007").setValue([0,0.5,0.1,1]);}catch(e){}
"""
        elif fx == "glow_white":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.15);g.property("ADBE Glo2-0003").setValue(25);
        g.property("ADBE Glo2-0004").setValue(2.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0.9,0.95,1,1]);g.property("ADBE Glo2-0007").setValue([0.5,0.6,0.8,1]);}catch(e){}
"""
        elif fx == "glow_blue":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.3);g.property("ADBE Glo2-0003").setValue(15);
        g.property("ADBE Glo2-0004").setValue(1.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0.3,0.7,1,1]);g.property("ADBE Glo2-0007").setValue([0.1,0.3,0.8,1]);}catch(e){}
"""
        elif fx == "glow_warm":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.3);g.property("ADBE Glo2-0003").setValue(20);
        g.property("ADBE Glo2-0004").setValue(1.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([1,0.95,0.8,1]);g.property("ADBE Glo2-0007").setValue([0.8,0.7,0.5,1]);}catch(e){}
"""
        elif fx == "glow_red":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.1);g.property("ADBE Glo2-0003").setValue(15);
        g.property("ADBE Glo2-0004").setValue(2.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([1,0,0,1]);g.property("ADBE Glo2-0007").setValue([0,0,1,1]);}catch(e){}
"""
        elif fx == "glow_soft":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.4);g.property("ADBE Glo2-0003").setValue(40);
        g.property("ADBE Glo2-0004").setValue(1.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0.8,0.7,1,1]);g.property("ADBE Glo2-0007").setValue([0.4,0.3,0.6,1]);}catch(e){}
"""
        elif fx == "glow_cyan":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.2);g.property("ADBE Glo2-0003").setValue(20);
        g.property("ADBE Glo2-0004").setValue(2.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0,0.8,1,1]);g.property("ADBE Glo2-0007").setValue([0,0.3,0.5,1]);}catch(e){}
"""
        elif fx == "wiggly_jelly":
            jsx += """
        var an1=tp.property("ADBE Text Animators");
        var a1=an1.addProperty("ADBE Text Animator");a1.name="JellyWig";
        var sl1=a1.property("ADBE Text Selectors");
        var w1=sl1.addProperty("ADBE Text Wiggly Selector");
        w1.property("ADBE Text Wiggly Max Amount").setValue(60);
        w1.property("ADBE Text Temporal Freq").setValue(4);
        var pr1=a1.property("ADBE Text Animator Properties");
        var sc1=pr1.addProperty("ADBE Text Scale 3D");sc1.setValue([15,0,0]);
"""
        elif fx == "shadow_clean":
            jsx += """
        var s=L.property("Effects").addProperty("ADBE Drop Shadow");
        s.property("ADBE Drop Shadow-0004").setValue(3);
        s.property("ADBE Drop Shadow-0003").setValue(135);
        s.property("ADBE Drop Shadow-0005").setValue(5);
        s.property("ADBE Drop Shadow-0002").setValue(40);
"""
        elif fx == "fractal_grain":
            jsx += """
        try{var f=L.property("Effects").addProperty("ADBE Fractal Noise");
        f.property("ADBE Fractal Noise-0001").setValue(3);
        f.property("Contrast").setValue(20);f.property("Brightness").setValue(-10);}catch(e){}
"""
        elif fx == "fractal_bokeh":
            jsx += """
        try{var f=L.property("Effects").addProperty("ADBE Fractal Noise");
        f.property("ADBE Fractal Noise-0001").setValue(1);
        f.property("Contrast").setValue(50);f.property("Brightness").setValue(-20);}catch(e){}
"""
        elif fx == "fractal_vhs":
            jsx += """
        try{var f=L.property("Effects").addProperty("ADBE Fractal Noise");
        f.property("ADBE Fractal Noise-0001").setValue(1);
        f.property("Contrast").setValue(40);f.property("Brightness").setValue(-10);}catch(e){}
"""
        elif fx == "tint_warm":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([0.3,0.15,0.05,1]);
        t.property("ADBE Tint-0002").setValue([1,0.85,0.6,1]);
"""
        elif fx == "tint_retro":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([0.3,0.1,0.2,1]);
        t.property("ADBE Tint-0002").setValue([1,0.6,0.8,1]);
"""
        elif fx == "turb_smooth":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Turbulent Displace");
        t.property("ADBE Turbulent Displace-0001").setValue(4);
        t.property("ADBE Turbulent Displace-0002").setValue(60);
"""
        elif fx == "turb_glitch":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Turbulent Displace");
        t.property("ADBE Turbulent Displace-0001").setValue(10);
        t.property("ADBE Turbulent Displace-0002").setValue(15);
"""
        elif fx == "turb_holo":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Turbulent Displace");
        t.property("ADBE Turbulent Displace-0001").setValue(3);
        t.property("ADBE Turbulent Displace-0002").setValue(40);
"""
        elif fx == "venetian_holo":
            jsx += """
        var v=L.property("Effects").addProperty("ADBE Venetian Blinds");
        v.property("ADBE Venetian Blinds-0001").setValue(90);
        v.property("ADBE Venetian Blinds-0002").setValue(4);
        v.property("ADBE Venetian Blinds-0003").setValue(60);
"""
        elif fx == "venetian_scan":
            jsx += """
        var v=L.property("Effects").addProperty("ADBE Venetian Blinds");
        v.property("ADBE Venetian Blinds-0001").setValue(70);
        v.property("ADBE Venetian Blinds-0002").setValue(5);
        v.property("ADBE Venetian Blinds-0003").setValue(30);
"""
        elif fx == "mosaic_retro":
            jsx += """
        try{var m=L.property("Effects").addProperty("ADBE Mosaic");
        m.property("ADBE Mosaic-0001").setValue([4,4]);
        m.property("ADBE Mosaic-0002").setValue(1);}catch(e){}
"""
        elif fx == "shadow_depth":
            jsx += """
        var s=L.property("Effects").addProperty("ADBE Drop Shadow");
        s.property("ADBE Drop Shadow-0004").setValue(15);
        s.property("ADBE Drop Shadow-0003").setValue(135);
        s.property("ADBE Drop Shadow-0005").setValue(20);
        s.property("ADBE Drop Shadow-0002").setValue(30);
"""

    # push_in表达式
    if anim == "push_in":
        jsx += """
        L.property("Position").expression = "t=time;zoom=1+t*0.3;[value[0],value[1],zoom*10];";
"""

    jsx += """
        return JSON.stringify({status:"success",comp:comp.name,layers:comp.numLayers});
    } catch(e) {
        return JSON.stringify({status:"error",error:e.toString().substring(0,80),line:e.line});
    }
})();"""
    return jsx


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"TextFX EXPAND - {len(COMBOS)} new combos (P0:{10} + P1:{10})")
    print(f"Vertical: {sum(1 for c in COMBOS if c['fmt']=='竖屏')} | Horizontal: {sum(1 for c in COMBOS if c['fmt']=='横屏')}")
    print(f"{'='*60}\n")

    # Step 1: 创建合成
    created = []
    failed = []
    for i, combo in enumerate(COMBOS):
        comp_name = f"TextFX_{combo['id']}"
        print(f"[{i+1}/{len(COMBOS)}] {comp_name} ({combo['fmt']})...")
        jsx = gen_jsx(combo)
        r = send_bridge(jsx, 30)
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
                        print(f"  FAIL: {parsed.get('error','?')[:60]}")
                except: pass
        print(f"  FAIL: {json.dumps(r, ensure_ascii=False)[:200]}")
        failed.append(combo['id'])

    print(f"\nCreated {len(created)}/{len(COMBOS)} comps")
    if failed:
        print(f"Failed: {', '.join(failed)}")

    if not created:
        print("No comps. Exiting.")
        sys.exit(1)

    # Step 2: 保存工程
    print("\nSaving project...")
    aep_unix = str(AEP_PATH).replace("\\", "/")
    save_code = f'(function(){{try{{var f=new File("{aep_unix}");app.project.save(f);return "ok";}}catch(e){{return e.toString();}}}})();'
    send_bridge(save_code, 15)
    print(f"  Saved: {AEP_PATH}")

    # Step 3: 渲染
    print(f"\n{'='*60}\nRendering...\n{'='*60}\n")
    rendered = []
    for comp_name in created:
        combo_id = comp_name.replace("TextFX_", "")
        output_file = OUTPUT_DIR / f"TextFX_{combo_id}.mp4"
        if output_file.exists():
            output_file = OUTPUT_DIR / f"TextFX_{combo_id}_v2.mp4"
        print(f"  Rendering {comp_name}...")
        ok = render_comp(comp_name, output_file)
        if ok:
            mb = output_file.stat().st_size / (1024*1024)
            print(f"  OK: {output_file.name} ({mb:.1f} MB)")
            rendered.append({"comp":comp_name, "file":str(output_file), "size_mb":round(mb,1)})
        else:
            print(f"  FAIL: {output_file}")

    # Step 4: 汇总
    print(f"\n{'='*60}")
    print(f"EXPAND SUMMARY: {len(rendered)}/{len(COMBOS)} new clips rendered")
    print(f"{'='*60}")
    for r in rendered:
        print(f"  {r['comp']} -> {r['file']} ({r['size_mb']} MB)")

    print("\n=== ALL FILES IN OUTPUT DIR ===")
    total = 0
    for f in sorted(OUTPUT_DIR.glob("*.mp4")):
        mb = f.stat().st_size / (1024*1024)
        print(f"  {f.name} ({mb:.1f} MB)")
        total += 1
    print(f"\nTotal: {total} clips")
