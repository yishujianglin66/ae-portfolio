#!/usr/bin/env python3
"""批量渲染文字特效预设组合 - 15个多样化搭配"""
import json, time, subprocess, sys, os
from pathlib import Path
from datetime import datetime

# === 路径配置 ===
BRIDGE_CMD = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_command.json")
BRIDGE_RESULT = Path(r"c:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\ae_result.json")
AEP_PATH = Path(r"D:\AE-Work\TextFX_Batch.aep")
OUTPUT_DIR = Path(r"D:\AE-Work\output\textfx_batch")
AERENDER = Path(r"C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\aerender.exe")

# === 15个多样化组合定义 ===
COMBOS = [
    # --- 横屏 16:9 (1920x1080) ---
    {"id":"cyber_glitch", "text":"CYBER ATTACK", "font":"Impact", "sz":150,
     "color":[0,1,0.8], "w":1920,"h":1080, "bg":[0.02,0.02,0.06],
     "fx":["glow_cyan","turb"], "anim":"glitch_pop",
     "expr":"if(Math.sin(time*30)>0.9){seedRandom(Math.floor(time*10),true);[value[0]+random(-8,8),value[1]+random(-3,3)];}else value;"},
    {"id":"neon_pulse", "text":"NEON NIGHTS", "font":"Arial-BoldMT", "sz":160,
     "color":[1,0.2,0.6], "w":1920,"h":1080, "bg":[0.03,0.01,0.05],
     "fx":["glow_pink","wiggly_scale"], "anim":"bounce_in",
     "expr":"100+Math.sin(time*60)*5+Math.sin(time*23)*3;"},
    {"id":"rgb_split", "text":"BREAK FREE", "font":"BebasNeue", "sz":180,
     "color":[1,0.3,0.5], "w":1920,"h":1080, "bg":[0.05,0.02,0.02],
     "fx":["turb","tint_rgb","glow_red"], "anim":"kinetic_smash",
     "expr":"seedRandom(Math.floor(time*8),true);[value[0]+random(-4,4),value[1]+random(-2,2)];"},
    {"id":"hologram_hud", "text":"SYSTEM BOOT", "font":"NotoSansSC-VF", "sz":100,
     "color":[0.3,0.7,1], "w":1920,"h":1080, "bg":[0.01,0.03,0.06],
     "fx":["glow_blue","venetian"], "anim":"slide_bottom",
     "expr":"[value[0],value[1]+Math.sin(time*2)*5];"},
    {"id":"ink_wash", "text":"水墨江湖", "font":"KaiTi", "sz":140,
     "color":[0.15,0.12,0.1], "w":1920,"h":1080, "bg":[0.95,0.92,0.85],
     "fx":["turb_soft","tint_ink"], "anim":"blur_reveal"},
    {"id":"electric_shock", "text":"ELECTRIC", "font":"SimHei", "sz":160,
     "color":[0.8,0.9,1], "w":1920,"h":1080, "bg":[0.02,0.02,0.08],
     "fx":["glow_white","turb_fast"], "anim":"elastic",
     "expr":"seedRandom(Math.floor(time*15),true);[value[0]+random(-10,10),value[1]+random(-5,5)];"},
    {"id":"matrix_digital", "text":"DECODED", "font":"Consolas", "sz":120,
     "color":[0,1,0.3], "w":1920,"h":1080, "bg":[0,0.02,0],
     "fx":["glow_green","fractal_noise"], "anim":"typewriter",
     "expr":"opacity=100+Math.sin(time*3)*20;"},
    {"id":"fire_burn", "text":"烈焰", "font":"MaShanZheng", "sz":180,
     "color":[1,0.5,0], "w":1920,"h":1080, "bg":[0.06,0.01,0],
     "fx":["turb_fire","glow_orange"], "anim":"scale_zoom",
     "expr":"freq=15;amp=6;[value[0]+Math.sin(time*freq*0.7)*amp*0.3,value[1]+Math.sin(time*freq)*amp*0.5];"},
    {"id":"soft_glow", "text":"ELEGANCE", "font":"Georgia-Bold", "sz":140,
     "color":[1,0.95,0.85], "w":1920,"h":1080, "bg":[0.08,0.05,0.03],
     "fx":["glow_warm","shadow"], "anim":"tracking_fade"},
    {"id":"retro_vhs", "text":"RETRO WAVE", "font":"Oswald-Bold", "sz":150,
     "color":[1,0.6,0.8], "w":1920,"h":1080, "bg":[0.04,0.02,0.06],
     "fx":["fractal_vhs","tint_retro","venetian_scan"], "anim":"letter_pop"},
    # --- 竖屏 9:16 (1080x1920) ---
    {"id":"golden_logo", "text":"LEGEND", "font":"Anton", "sz":200,
     "color":[1,0.85,0.3], "w":1080,"h":1920, "bg":[0.03,0.03,0.06],
     "fx":["glow_gold","ramp_bg"], "anim":"bounce_in",
     "expr":"base=value;breath=1+Math.sin(time*2)*0.02;[base[0]*breath,base[1]*breath];"},
    {"id":"ice_frost", "text":"冰霜凝结", "font":"STXihei", "sz":130,
     "color":[0.6,0.85,1], "w":1080,"h":1920, "bg":[0.02,0.04,0.08],
     "fx":["fractal_ice","tint_cold","glow_cyan_light"], "anim":"scatter",
     "expr":"100+Math.sin(time*1.5)*8;"},
    {"id":"data_corrupt", "text":"CORRUPTED", "font":"BlackOpsOne", "sz":120,
     "color":[0,1,0], "w":1080,"h":1920, "bg":[0.01,0.01,0.01],
     "fx":["turb_glitch","fractal_static","tint_green"], "anim":"random_pop",
     "expr":"seedRandom(Math.floor(time*12),true);[value[0]+random(-6,6),value[1]+random(-3,3)];"},
    {"id":"aurora", "text":"极光幻境", "font":"DengXian-Bold", "sz":140,
     "color":[0.4,0.9,0.7], "w":1080,"h":1920, "bg":[0.02,0.03,0.05],
     "fx":["glow_aurora","tint_aurora"], "anim":"wave_per_char",
     "expr":"[value[0]+Math.sin(time*1.5)*8,value[1]+Math.cos(time)*5];"},
    {"id":"minimal_line", "text":"MINIMAL", "font":"Montserrat", "sz":100,
     "color":[0.9,0.9,0.9], "w":1080,"h":1920, "bg":[0.12,0.12,0.12],
     "fx":["shadow_clean"], "anim":"spiral_in"},
]

# === JSX模板生成 ===
def gen_jsx(combo):
    """为一个组合生成完整的JSX代码"""
    c = combo
    cid = c["id"]
    text = c["text"]
    font = c["font"]
    sz = c["sz"]
    color = c["color"]
    w, h = c["w"], c["h"]
    bg = c["bg"]
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
    # 添加入场动画
    anim = c["anim"]
    if anim == "bounce_in":
        jsx += """
        L.scale.setValueAtTime(0,[0,0]);
        L.scale.setValueAtTime(0.2,[110,110]);
        L.scale.setValueAtTime(0.4,[100,100]);
"""
    elif anim == "glitch_pop":
        jsx += """
        L.scale.setValueAtTime(0,[0,0]);
        L.scale.setValueAtTime(0.15,[115,115]);
        L.scale.setValueAtTime(0.3,[95,95]);
        L.scale.setValueAtTime(0.4,[100,100]);
"""
    elif anim == "kinetic_smash":
        jsx += """
        L.scale.setValueAtTime(0,[0,0]);
        L.scale.setValueAtTime(0.1,[130,130]);
        L.scale.setValueAtTime(0.2,[90,90]);
        L.scale.setValueAtTime(0.3,[100,100]);
"""
    elif anim == "slide_bottom":
        jsx += f"""
        L.position.setValueAtTime(0,[{cx},{cy}+80]);
        L.position.setValueAtTime(0.5,[{cx},{cy}]);
"""
    elif anim == "blur_reveal":
        jsx += """
        var anims = tp.property("ADBE Text Animators");
        var a = anims.addProperty("ADBE Text Animator");
        a.name = "BlurReveal";
        var sels = a.property("ADBE Text Selectors");
        var rs = sels.addProperty("ADBE Text Selector");
        rs.property("ADBE Text Percent Start").setValue(0);
        rs.property("ADBE Text Percent End").setValue(100);
        rs.property("ADBE Text Percent Offset").setValueAtTime(0,-100);
        rs.property("ADBE Text Percent Offset").setValueAtTime(2,0);
        var props = a.property("ADBE Text Animator Properties");
        var bp = props.addProperty("ADBE Text Blur");
        bp.setValue([40,40]);
"""
    elif anim == "typewriter":
        jsx += """
        var anims = tp.property("ADBE Text Animators");
        var a = anims.addProperty("ADBE Text Animator");
        a.name = "Typewriter";
        var sels = a.property("ADBE Text Selectors");
        var rs = sels.addProperty("ADBE Text Selector");
        rs.property("ADBE Text Percent Start").setValue(0);
        rs.property("ADBE Text Percent End").setValue(0);
        rs.property("ADBE Text Percent Offset").setValueAtTime(0,0);
        rs.property("ADBE Text Percent Offset").setValueAtTime(2,100);
        var props = a.property("ADBE Text Animator Properties");
        var op = props.addProperty("ADBE Text Opacity");
        op.setValue(0);
"""
    elif anim == "tracking_fade":
        jsx += """
        var anims = tp.property("ADBE Text Animators");
        var a = anims.addProperty("ADBE Text Animator");
        a.name = "TrackingFade";
        var sels = a.property("ADBE Text Selectors");
        var rs = sels.addProperty("ADBE Text Selector");
        rs.property("ADBE Text Percent Start").setValue(0);
        rs.property("ADBE Text Percent End").setValue(100);
        rs.property("ADBE Text Percent Offset").setValueAtTime(0,-100);
        rs.property("ADBE Text Percent Offset").setValueAtTime(1.5,0);
        var props = a.property("ADBE Text Animator Properties");
        var trp = props.addProperty("ADBE Text Tracking Amount");
        trp.setValue(-200);
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(1.5,100);
"""
    elif anim == "elastic":
        jsx += """
        L.scale.setValueAtTime(0,[0,0]);
        L.scale.setValueAtTime(0.1,[140,140]);
        L.scale.setValueAtTime(0.2,[85,85]);
        L.scale.setValueAtTime(0.3,[108,108]);
        L.scale.setValueAtTime(0.4,[97,97]);
        L.scale.setValueAtTime(0.5,[100,100]);
"""
    elif anim == "scale_zoom":
        jsx += """
        L.scale.setValueAtTime(0,[30,30]);
        L.scale.setValueAtTime(0.5,[100,100]);
"""
    elif anim == "letter_pop":
        jsx += """
        var anims = tp.property("ADBE Text Animators");
        var a = anims.addProperty("ADBE Text Animator");
        a.name = "LetterPop";
        var sels = a.property("ADBE Text Selectors");
        var rs = sels.addProperty("ADBE Text Selector");
        rs.property("ADBE Text Percent Start").setValue(0);
        rs.property("ADBE Text Percent End").setValue(0);
        rs.property("ADBE Text Percent Offset").setValueAtTime(0,0);
        rs.property("ADBE Text Percent Offset").setValueAtTime(1.5,100);
        var props = a.property("ADBE Text Animator Properties");
        var sp = props.addProperty("ADBE Text Scale 3D");
        sp.setValue([120,120,0]);
"""
    elif anim == "scatter":
        jsx += """
        L.scale.setValueAtTime(0,[0,0]);
        L.scale.setValueAtTime(0.8,[100,100]);
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(0.5,100);
"""
    elif anim == "random_pop":
        jsx += """
        var anims = tp.property("ADBE Text Animators");
        var a = anims.addProperty("ADBE Text Animator");
        a.name = "RandomPop";
        var sels = a.property("ADBE Text Selectors");
        var ws = sels.addProperty("ADBE Text Wiggly Selector");
        ws.property("ADBE Text Wiggly Max Amount").setValue(80);
        ws.property("ADBE Text Temporal Freq").setValue(2);
        var props = a.property("ADBE Text Animator Properties");
        var op = props.addProperty("ADBE Text Opacity");
        op.setValue(100);
"""
    elif anim == "wave_per_char":
        jsx += """
        var anims = tp.property("ADBE Text Animators");
        var a = anims.addProperty("ADBE Text Animator");
        a.name = "WaveChar";
        var sels = a.property("ADBE Text Selectors");
        var ws = sels.addProperty("ADBE Text Wiggly Selector");
        ws.property("ADBE Text Wiggly Max Amount").setValue(20);
        ws.property("ADBE Text Temporal Freq").setValue(1.5);
        var props = a.property("ADBE Text Animator Properties");
        var pp = props.addProperty("ADBE Text Position 3D");
        pp.setValue([0,-20,0]);
"""
    elif anim == "spiral_in":
        jsx += """
        L.scale.setValueAtTime(0,[0,0]);
        L.rotation.setValueAtTime(0,-360);
        L.rotation.setValueAtTime(1,0);
        L.scale.setValueAtTime(0.8,[100,100]);
"""

    # 淡入淡出
    jsx += """
        L.opacity.setValueAtTime(0,0);
        L.opacity.setValueAtTime(0.3,100);
        L.opacity.setValueAtTime(3.5,100);
        L.opacity.setValueAtTime(4,0);
"""

    # 添加特效
    for fx in c["fx"]:
        if fx == "glow_cyan":
            jsx += """
        var g=comp.layers.byName("{text}").property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.2);g.property("ADBE Glo2-0003").setValue(20);
        g.property("ADBE Glo2-0004").setValue(2.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0,0.8,1,1]);g.property("ADBE Glo2-0007").setValue([0,0.3,0.5,1]);}catch(e){}
""".replace("{text}", text)
        elif fx == "glow_pink":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.15);g.property("ADBE Glo2-0003").setValue(35);
        g.property("ADBE Glo2-0004").setValue(3.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([1,0.2,0.6,1]);g.property("ADBE Glo2-0007").setValue([0.3,0.5,1,1]);}catch(e){}
"""
        elif fx == "glow_red":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.1);g.property("ADBE Glo2-0003").setValue(15);
        g.property("ADBE Glo2-0004").setValue(2.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([1,0,0,1]);g.property("ADBE Glo2-0007").setValue([0,0,1,1]);}catch(e){}
"""
        elif fx == "glow_blue":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.3);g.property("ADBE Glo2-0003").setValue(15);
        g.property("ADBE Glo2-0004").setValue(1.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0.3,0.7,1,1]);g.property("ADBE Glo2-0007").setValue([0.1,0.3,0.8,1]);}catch(e){}
"""
        elif fx == "glow_green":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.2);g.property("ADBE Glo2-0003").setValue(20);
        g.property("ADBE Glo2-0004").setValue(2.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0,1,0.3,1]);g.property("ADBE Glo2-0007").setValue([0,0.5,0.1,1]);}catch(e){}
"""
        elif fx == "glow_orange":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.2);g.property("ADBE Glo2-0003").setValue(25);
        g.property("ADBE Glo2-0004").setValue(2.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([1,0.5,0,1]);g.property("ADBE Glo2-0007").setValue([1,0.2,0,1]);}catch(e){}
"""
        elif fx == "glow_warm":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.3);g.property("ADBE Glo2-0003").setValue(20);
        g.property("ADBE Glo2-0004").setValue(1.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([1,0.95,0.8,1]);g.property("ADBE Glo2-0007").setValue([0.8,0.7,0.5,1]);}catch(e){}
"""
        elif fx == "glow_gold":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.1);g.property("ADBE Glo2-0003").setValue(40);
        g.property("ADBE Glo2-0004").setValue(2.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([1,0.85,0.3,1]);g.property("ADBE Glo2-0007").setValue([1,0.6,0.1,1]);}catch(e){}
"""
        elif fx == "glow_aurora":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.2);g.property("ADBE Glo2-0003").setValue(30);
        g.property("ADBE Glo2-0004").setValue(2.0);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0.4,0.9,0.7,1]);g.property("ADBE Glo2-0007").setValue([0.2,0.5,0.8,1]);}catch(e){}
"""
        elif fx == "glow_white":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.15);g.property("ADBE Glo2-0003").setValue(25);
        g.property("ADBE Glo2-0004").setValue(2.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0.9,0.95,1,1]);g.property("ADBE Glo2-0007").setValue([0.5,0.6,0.8,1]);}catch(e){}
"""
        elif fx == "glow_cyan_light":
            jsx += """
        var g=L.property("Effects").addProperty("ADBE Glo2");
        g.property("ADBE Glo2-0002").setValue(0.3);g.property("ADBE Glo2-0003").setValue(20);
        g.property("ADBE Glo2-0004").setValue(1.5);
        try{g.property("ADBE Glo2-0005").setValue(3);g.property("ADBE Glo2-0006").setValue([0.6,0.85,1,1]);g.property("ADBE Glo2-0007").setValue([0.3,0.5,0.8,1]);}catch(e){}
"""
        elif fx == "turb":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Turbulent Displace");
        t.property("ADBE Turbulent Displace-0001").setValue(8);
        t.property("ADBE Turbulent Displace-0002").setValue(30);
"""
        elif fx == "turb_soft":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Turbulent Displace");
        t.property("ADBE Turbulent Displace-0001").setValue(3);
        t.property("ADBE Turbulent Displace-0002").setValue(50);
"""
        elif fx == "turb_fast":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Turbulent Displace");
        t.property("ADBE Turbulent Displace-0001").setValue(11);
        t.property("ADBE Turbulent Displace-0002").setValue(20);
"""
        elif fx == "turb_fire":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Turbulent Displace");
        t.property("ADBE Turbulent Displace-0001").setValue(11);
        t.property("ADBE Turbulent Displace-0002").setValue(25);
"""
        elif fx == "turb_glitch":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Turbulent Displace");
        t.property("ADBE Turbulent Displace-0001").setValue(10);
        t.property("ADBE Turbulent Displace-0002").setValue(15);
"""
        elif fx == "tint":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([0.1,0.1,0.1,1]);
        t.property("ADBE Tint-0002").setValue([0.9,0.9,0.9,1]);
"""
        elif fx == "tint_rgb":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([1,0,0,1]);
        t.property("ADBE Tint-0002").setValue([0,1,1,1]);
"""
        elif fx == "tint_ink":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([0.1,0.08,0.05,1]);
        t.property("ADBE Tint-0002").setValue([0.3,0.25,0.2,1]);
"""
        elif fx == "tint_retro":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([0.3,0.1,0.2,1]);
        t.property("ADBE Tint-0002").setValue([1,0.6,0.8,1]);
"""
        elif fx == "tint_green":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([0,0.2,0,1]);
        t.property("ADBE Tint-0002").setValue([0,1,0.3,1]);
"""
        elif fx == "tint_cold":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([0.1,0.2,0.4,1]);
        t.property("ADBE Tint-0002").setValue([0.7,0.9,1,1]);
"""
        elif fx == "tint_aurora":
            jsx += """
        var t=L.property("Effects").addProperty("ADBE Tint");
        t.property("ADBE Tint-0001").setValue([0.1,0.3,0.2,1]);
        t.property("ADBE Tint-0002").setValue([0.4,0.9,0.7,1]);
"""
        elif fx == "venetian":
            jsx += """
        var v=L.property("Effects").addProperty("ADBE Venetian Blinds");
        v.property("ADBE Venetian Blinds-0001").setValue(85);
        v.property("ADBE Venetian Blinds-0002").setValue(8);
        v.property("ADBE Venetian Blinds-0003").setValue(50);
"""
        elif fx == "venetian_scan":
            jsx += """
        var v=L.property("Effects").addProperty("ADBE Venetian Blinds");
        v.property("ADBE Venetian Blinds-0001").setValue(70);
        v.property("ADBE Venetian Blinds-0002").setValue(5);
        v.property("ADBE Venetian Blinds-0003").setValue(30);
"""
        elif fx == "fractal_noise":
            jsx += """
        try{var f=L.property("Effects").addProperty("ADBE Fractal Noise");
        f.property("ADBE Fractal Noise-0001").setValue(1);
        f.property("Contrast").setValue(80);
        f.property("Brightness").setValue(-30);}catch(e){}
"""
        elif fx == "fractal_static":
            jsx += """
        try{var f=L.property("Effects").addProperty("ADBE Fractal Noise");
        f.property("ADBE Fractal Noise-0001").setValue(2);
        f.property("Contrast").setValue(60);
        f.property("Brightness").setValue(-20);}catch(e){}
"""
        elif fx == "fractal_vhs":
            jsx += """
        try{var f=L.property("Effects").addProperty("ADBE Fractal Noise");
        f.property("ADBE Fractal Noise-0001").setValue(1);
        f.property("Contrast").setValue(40);
        f.property("Brightness").setValue(-10);}catch(e){}
"""
        elif fx == "fractal_ice":
            jsx += """
        try{var f=L.property("Effects").addProperty("ADBE Fractal Noise");
        f.property("ADBE Fractal Noise-0001").setValue(1);
        f.property("Contrast").setValue(80);
        f.property("Brightness").setValue(-30);}catch(e){}
"""
        elif fx == "shadow":
            jsx += """
        var s=L.property("Effects").addProperty("ADBE Drop Shadow");
        s.property("ADBE Drop Shadow-0004").setValue(5);
        s.property("ADBE Drop Shadow-0003").setValue(135);
        s.property("ADBE Drop Shadow-0005").setValue(8);
        s.property("ADBE Drop Shadow-0002").setValue(60);
"""
        elif fx == "shadow_clean":
            jsx += """
        var s=L.property("Effects").addProperty("ADBE Drop Shadow");
        s.property("ADBE Drop Shadow-0004").setValue(3);
        s.property("ADBE Drop Shadow-0003").setValue(135);
        s.property("ADBE Drop Shadow-0005").setValue(5);
        s.property("ADBE Drop Shadow-0002").setValue(40);
"""
        elif fx == "ramp_bg":
            jsx += f"""
        var bgS=comp.layers.addSolid([1,1,1],"bgRamp",{w},{h},1,4);
        try{{var r=bgS.property("Effects").addProperty("ADBE Ramp");
        r.property("Start Color").setValue([1,0.85,0.3,1]);
        r.property("Start Point").setValue([{cx},{cy}]);
        r.property("End Color").setValue([0.03,0.03,0.06,1]);
        r.property("End Point").setValue([{cx},{h}]);}}catch(e){{}}
        bgS.moveToBeginning();
        bgS.opacity.setValueAtTime(0,0);bgS.opacity.setValueAtTime(0.5,50);
        bgS.opacity.setValueAtTime(3.5,50);bgS.opacity.setValueAtTime(4,0);
"""
        elif fx == "wiggly_scale":
            jsx += """
        var anims=tp.property("ADBE Text Animators");
        var a2=anims.addProperty("ADBE Text Animator");
        a2.name="ScalePulse";
        var sels2=a2.property("ADBE Text Selectors");
        var ws=sels2.addProperty("ADBE Text Wiggly Selector");
        ws.property("ADBE Text Wiggly Max Amount").setValue(40);
        ws.property("ADBE Text Temporal Freq").setValue(3);
        var props2=a2.property("ADBE Text Animator Properties");
        var sp=props2.addProperty("ADBE Text Scale 3D");
        sp.setValue([5,5,0]);
"""

    # 添加表达式
    if "expr" in c:
        expr_prop = "Position"
        if "opacity" in c["expr"].lower() or "Opacity" in c["expr"]:
            expr_prop = "Opacity"
        elif "scale" in c["expr"].lower() or "breath" in c["expr"]:
            expr_prop = "Scale"
        jsx += f"""
        L.property("{expr_prop}").expression = "{c['expr']}";
"""

    jsx += """
        return JSON.stringify({status:"success", comp:comp.name, layers:comp.numLayers});
    } catch(e) {
        return JSON.stringify({status:"error", error:e.toString(), line:e.line});
    }
})();"""
    return jsx


# === Bridge通信 ===
def send_bridge(code, wait=60):
    if BRIDGE_RESULT.exists():
        BRIDGE_RESULT.write_text('{"status":"waiting"}', encoding="utf-8")
    cmd = {"command":"runScript","args":{"code":code},
           "timestamp":datetime.now().isoformat(),"status":"pending"}
    BRIDGE_CMD.write_text(json.dumps(cmd,ensure_ascii=False), encoding="utf-8")
    time.sleep(1)
    for i in range(wait):
        time.sleep(1)
        try:
            r = json.loads(BRIDGE_RESULT.read_text(encoding="utf-8"))
            if r.get("status") != "waiting" and "result" in r:
                return r
        except: pass
    return {"success":False,"error":"timeout"}


def render_comp(comp_name, output_path):
    """用aerender渲染单个合成"""
    cmd = [str(AERENDER), "-project", str(AEP_PATH), "-comp", comp_name,
           "-output", str(output_path)]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="ignore")
    while True:
        line = proc.stdout.readline()
        if not line and proc.poll() is not None: break
        line = line.strip()
        if "PROGRESS" in line and ("开始" in line or "完成" in line or "总时间" in line):
            print(f"    {line[:120]}")
    return proc.returncode == 0 and output_path.exists()


# === 主流程 ===
if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n{'='*60}")
    print(f"TextFX Batch Render - {len(COMBOS)} combinations")
    print(f"{'='*60}\n")

    # Step 1: 通过Bridge创建所有合成
    success_count = 0
    created_comps = []
    for i, combo in enumerate(COMBOS):
        comp_name = f"TextFX_{combo['id']}"
        print(f"[{i+1}/{len(COMBOS)}] Creating {comp_name}...")
        jsx = gen_jsx(combo)
        r = send_bridge(jsx, 30)
        inner = r.get("result", {})
        if isinstance(inner, dict) and inner.get("success"):
            result_str = inner.get("result", "")
            if isinstance(result_str, str):
                try:
                    parsed = json.loads(result_str)
                    if parsed.get("status") == "success":
                        created_comps.append(comp_name)
                        print(f"  OK ({parsed.get('layers',0)} layers)")
                        success_count += 1
                        continue
                except: pass
        print(f"  FAIL: {json.dumps(r, ensure_ascii=False)[:200]}")

    print(f"\nCreated {success_count}/{len(COMBOS)} comps")

    if success_count == 0:
        print("No comps created. Exiting.")
        sys.exit(1)

    # Step 2: 保存工程
    print("\nSaving project...")
    aep_unix = str(AEP_PATH).replace("\\", "/")
    save_code = f'(function(){{try{{var f=new File("{aep_unix}");app.project.save(f);return JSON.stringify({{status:"saved"}});}}catch(e){{return JSON.stringify({{status:"error",err:e.toString()}});}}}})();'
    send_bridge(save_code, 15)
    print(f"  Saved: {AEP_PATH}")

    # Step 3: 逐个渲染
    print(f"\n{'='*60}")
    print("Rendering...")
    print(f"{'='*60}\n")
    rendered = []
    for comp_name in created_comps:
        combo_id = comp_name.replace("TextFX_", "")
        output_file = OUTPUT_DIR / f"TextFX_{combo_id}.mp4"
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
    print(f"RENDER SUMMARY: {len(rendered)}/{len(COMBOS)} clips rendered")
    print(f"{'='*60}")
    for r in rendered:
        print(f"  {r['comp']} -> {r['file']} ({r['size_mb']} MB)")
    print(f"\nOutput dir: {OUTPUT_DIR}")
