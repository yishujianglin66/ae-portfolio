#!/usr/bin/env python3
"""
文字特效预设三维矩阵数据库构建器 v1.0
以 TextFX_Showcase.jsx 基准案例为 Ground Truth
三维独立扩展: effect_combos(30+) + entrance_animations(25+) + font_library(50+)
"""
import json, os
from datetime import date

OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# ============================================================
# 辅助函数
# ============================================================
def glow(threshold=0.2, radius=20, intensity=2.0, colorA=None, colorB=None):
    e = {"matchName": "ADBE Glo2", "params": {"threshold": threshold, "radius": radius, "intensity": intensity}}
    if colorA: e["params"]["color_mode"] = 3; e["params"]["colorA"] = colorA
    if colorB: e["params"]["colorB"] = colorB
    return e

def turb(amount=25, size=30):
    return {"matchName": "ADBE Turbulent Displace", "params": {"amount": amount, "size": size}}

def fractal(noise_type=1, contrast=80, brightness=-30):
    return {"matchName": "ADBE Fractal Noise", "params": {"noise_type": noise_type, "contrast": contrast, "brightness": brightness}}

def tint(black=None, white=None):
    p = {}
    if black: p["black"] = black
    if white: p["white"] = white
    return {"matchName": "ADBE Tint", "params": p}

def venetian(completion=85, width=8, feather=50):
    return {"matchName": "ADBE Venetian Blinds", "params": {"completion": completion, "width": width, "feather": feather}}

def bevel(thickness=5, softness=3, direction=1, angle=135, altitude=30,
          hl_color=None, hl_opacity=80, sh_color=None, sh_opacity=60):
    p = {"edgeThickness": thickness, "softness": softness, "direction": direction,
         "angle": angle, "altitude": altitude, "highlightOpacity": hl_opacity, "shadowOpacity": sh_opacity}
    if hl_color: p["highlightColor"] = hl_color
    if sh_color: p["shadowColor"] = sh_color
    return {"matchName": "ADBE Bevel Emboss", "params": p}

def drop_shadow(distance=5, angle=135, softness=5, opacity=30, color=None):
    p = {"distance": distance, "angle": angle, "softness": softness, "opacity": opacity}
    if color: p["color"] = color
    return {"matchName": "ADBE Drop Shadow", "params": p}

def ramp(start_color=None, end_color=None, start_point=None, end_point=None, ramp_type=0):
    p = {"type": ramp_type}
    if start_color: p["startColor"] = start_color
    if end_color: p["endColor"] = end_color
    if start_point: p["startPoint"] = start_point
    if end_point: p["endPoint"] = end_point
    return {"matchName": "ADBE Ramp", "params": p}

# ============================================================
# 维度一：特效组合库（30+套）
# ============================================================
EFFECT_COMBOS = [
    # ---- Ground Truth (6) ----
    {"id": "effect_cyber_glitch", "name": "赛博故障", "name_en": "Cyber Glitch",
     "effects": [glow(0.2, 20, 2.0, [0,0.8,1,1], [0,0.3,0.5,1]), turb(25, 30)],
     "text_animators": [{"type":"wiggly","name":"GlitchJitter","prop":"ADBE Text Position 3D","value":[8,5,0],"size":30,"rate":12}],
     "expressions": {"position": "if(Math.sin(time*30)>0.9){seedRandom(Math.floor(time*10),true);[value[0]+random(-8,8),value[1]+random(-3,3)];}else value;"},
     "visual_style": "赛博朋克", "recommended_font_traits": ["粗体","无衬线","几何感","紧凑"],
     "best_for": ["科技片头","游戏标题","赛博朋克","故障艺术"], "quality_rating": 5, "verified": True,
     "notes": "基准S1。TurbulentDisplace Amount在AE2025范围1-11需clamp。"},

    {"id": "effect_ink_wash", "name": "水墨书法", "name_en": "Ink Calligraphy",
     "effects": [turb(8, 50), tint([0.1,0.08,0.05,1], [0.3,0.25,0.2,1])],
     "text_animators": [{"type":"range","name":"BlurReveal","prop":"ADBE Text Blur","value":40,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":2.0},"shape":2}],
     "expressions": {}, "visual_style": "东方水墨",
     "recommended_font_traits": ["书法体","衬线体","中文","传统"],
     "best_for": ["文化片头","古籍引用","教育类","中国风"], "quality_rating": 5, "verified": True,
     "notes": "基准S2。Range Selector shape=2(RampUp)实现柔和揭示。"},

    {"id": "effect_neon_pulse", "name": "霓虹脉冲", "name_en": "Neon Pulse",
     "effects": [glow(0.15, 35, 3.0, [1,0.2,0.6,1], [0.3,0.5,1,1])],
     "text_animators": [{"type":"wiggly","name":"ScalePulse","prop":"ADBE Text Scale 3D","value":[5,5,0],"size":40,"rate":3}],
     "expressions": {"opacity": "base=90;flicker=Math.sin(time*60)*5+Math.sin(time*23)*3;if(Math.random()>0.95)base-30;else base+flicker;"},
     "visual_style": "霓虹灯光", "recommended_font_traits": ["粗体","无衬线","几何","高x-height"],
     "best_for": ["夜店风格","音乐视频","潮流标题"], "quality_rating": 5, "verified": True,
     "notes": "基准S3。双色Glow(粉+蓝)营造霓虹感。"},

    {"id": "effect_hologram_hud", "name": "全息HUD", "name_en": "Hologram HUD",
     "effects": [glow(0.3, 15, 1.5, [0.3,0.7,1,1], [0.1,0.3,0.8,1]), venetian(85, 8, 50)],
     "text_animators": [{"type":"range","name":"FloatUp","prop":"ADBE Text Position 3D","value":[0,-30,0],
         "animateOffset":True,"animStart":0,"animEnd":1.5,"shape":5}],
     "expressions": {"position": "[value[0],value[1]+Math.sin(time*2)*5];"},
     "visual_style": "科幻全息", "recommended_font_traits": ["无衬线","等宽","现代","纤细"],
     "best_for": ["科幻界面","HUD显示","科技数据"], "quality_rating": 5, "verified": True,
     "notes": "基准S4。VenetianBlinds扫描线+Position正弦浮动。"},

    {"id": "effect_fire_ice", "name": "元素对比", "name_en": "Fire & Ice",
     "effects": [turb(40, 25), fractal(1, 80, -30), tint([0.2,0.4,0.6,1], [0.7,0.9,1,1]),
                 glow(0.3, 25, 1.5, [0.5,0.8,1,1], [0.2,0.4,0.8,1])],
     "text_animators": [],
     "expressions": {"position_fire": "freq=15;amp=6;[value[0]+Math.sin(time*freq*0.7)*amp*0.3,value[1]+Math.sin(time*freq)*amp*0.5];",
                     "opacity_ice": "100+Math.sin(time*1.5)*8;"},
     "visual_style": "元素对比", "recommended_font_traits": ["粗体","冲击","无衬线","极粗"],
     "best_for": ["对比展示","游戏元素","热血标题"], "quality_rating": 5, "verified": True,
     "notes": "基准S5。Fire侧TurbulentDisplace+抖动，Ice侧FractalNoise+Tint。"},

    {"id": "effect_golden_logo", "name": "金色LOGO", "name_en": "Golden Logo",
     "effects": [glow(0.1, 40, 2.5, [1,0.85,0.3,1], [1,0.6,0.1,1]),
                 ramp([1,0.85,0.3,1], [0.05,0.05,0.08,1], [960,540], [960,1080])],
     "text_animators": [],
     "expressions": {"scale": "base=value;breath=1+Math.sin(time*2)*0.02;[base[0]*breath,base[1]*breath];"},
     "visual_style": "高端金色", "recommended_font_traits": ["粗体","展示体","衬线","几何"],
     "best_for": ["LOGO展示","颁奖典礼","品牌片尾"], "quality_rating": 5, "verified": True,
     "notes": "基准S6。金色Glow+Ramp背景+Scale呼吸。"},

    # ---- 故障/科技系 (5) ----
    {"id": "effect_rgb_split", "name": "RGB分离", "name_en": "RGB Split",
     "effects": [turb(11, 20), tint([1,0,0,1], [0,1,1,1]), glow(0.1, 8, 1.0, [1,0,0,1], [0,0,1,1])],
     "text_animators": [{"type":"wiggly","name":"RGBJitter","prop":"ADBE Text Position 3D","value":[5,2,0],"size":20,"rate":8}],
     "expressions": {"position": "seedRandom(Math.floor(time*8),true);[value[0]+random(-4,4),value[1]+random(-2,2)];"},
     "visual_style": "故障艺术", "recommended_font_traits": ["粗体","无衬线","几何"],
     "best_for": ["故障风标题","MV字幕","潮流视觉"], "quality_rating": 4, "verified": False,
     "notes": "TurbulentDisplace max=11(AE2025)。RGB色彩分离通过Tint。"},

    {"id": "effect_data_corrupt", "name": "数据损坏", "name_en": "Data Corrupt",
     "effects": [turb(6, 15), fractal(3, 2, -50), tint([0,1,0,1], [0,0.3,0,1])],
     "text_animators": [{"type":"wiggly","name":"DataGlitch","prop":"ADBE Text Position 3D","value":[3,1,0],"size":50,"rate":15}],
     "expressions": {"opacity": "if(random()>0.9)50;else 100;"},
     "visual_style": "数据故障", "recommended_font_traits": ["等宽","科技感","无衬线"],
     "best_for": ["黑客主题","科技惊悚","数据可视化"], "quality_rating": 4, "verified": False,
     "notes": "绿色终端风格，Fractal Noise type=3(Block)数字噪点。"},

    {"id": "effect_matrix_digital", "name": "矩阵数字", "name_en": "Matrix Digital",
     "effects": [glow(0.3, 12, 1.8, [0,1,0,1], [0,0.4,0,1]), fractal(1, 3, -60)],
     "text_animators": [{"type":"range","name":"MatrixReveal","prop":"ADBE Text Opacity","value":0,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":2}],
     "expressions": {}, "visual_style": "黑客帝国", "recommended_font_traits": ["等宽","科技感"],
     "best_for": ["黑客主题","代码展示","科幻片头"], "quality_rating": 4, "verified": False,
     "notes": "经典Matrix绿色调，Range Selector逐字揭示。"},

    {"id": "effect_circuit_board", "name": "电路板", "name_en": "Circuit Board",
     "effects": [glow(0.4, 10, 1.2, [0,0.8,1,1], [0,0.2,0.5,1]), venetian(70, 3, 10)],
     "text_animators": [{"type":"range","name":"CircuitTrace","prop":"ADBE Text Stroke Width","value":2,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":2.0},"shape":2}],
     "expressions": {}, "visual_style": "科技电路", "recommended_font_traits": ["等宽","无衬线","几何"],
     "best_for": ["科技产品","工程展示","数据界面"], "quality_rating": 3, "verified": False,
     "notes": "细扫描线+描边揭示模拟电路走线。"},

    {"id": "effect_glitch_mirror", "name": "镜像故障", "name_en": "Glitch Mirror",
     "effects": [turb(5, 40), glow(0.2, 15, 1.5, [1,0,1,1], [0,1,1,1])],
     "text_animators": [{"type":"wiggly","name":"MirrorShake","prop":"ADBE Text Position 3D","value":[6,0,0],"size":15,"rate":10}],
     "expressions": {"position": "if(Math.sin(time*20)>0.85){[value[0]+random(-10,10),value[1]];}else value;"},
     "visual_style": "镜像故障", "recommended_font_traits": ["粗体","无衬线","几何"],
     "best_for": ["故障艺术","实验视觉","电子音乐"], "quality_rating": 4, "verified": False,
     "notes": "品红+青色双色Glow营造镜像色差。"},

    # ---- 光效/发光系 (5) ----
    {"id": "effect_soft_glow", "name": "柔光梦幻", "name_en": "Soft Glow",
     "effects": [glow(0.5, 50, 1.0, [1,0.9,0.95,1], [0.9,0.7,0.8,1])],
     "text_animators": [],
     "expressions": {"opacity": "95+Math.sin(time*1.5)*5;"},
     "visual_style": "柔和梦幻", "recommended_font_traits": ["纤细","衬线","手写","优雅"],
     "best_for": ["婚礼字幕","浪漫场景","美妆品牌"], "quality_rating": 4, "verified": False,
     "notes": "大radius(50)+低intensity(1.0)柔光晕，粉白色调。"},

    {"id": "effect_neon_sign", "name": "霓虹灯牌", "name_en": "Neon Sign",
     "effects": [glow(0.1, 25, 2.5, [1,0.1,0.5,1], [1,0.5,0.8,1]), tint([0.1,0,0.05,1], [1,0.3,0.6,1])],
     "text_animators": [],
     "expressions": {"opacity": "base=95;f=Math.sin(time*45)*3+Math.sin(time*17)*2;if(random()>0.97)base-25;else base+f;"},
     "visual_style": "霓虹灯牌", "recommended_font_traits": ["手写","圆润","粗体","展示体"],
     "best_for": ["街景风格","酒吧标题","夜生活"], "quality_rating": 4, "verified": False,
     "notes": "比neon_pulse更暖粉色调，更频繁闪烁。"},

    {"id": "effect_laser_scan", "name": "激光扫描", "name_en": "Laser Scan",
     "effects": [glow(0.05, 30, 2.0, [0,1,0.5,1], [0,0.5,1,1]), venetian(90, 4, 80)],
     "text_animators": [{"type":"range","name":"LaserReveal","prop":"ADBE Text Opacity","value":0,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.0},"shape":5}],
     "expressions": {}, "visual_style": "激光科技", "recommended_font_traits": ["无衬线","几何","现代"],
     "best_for": ["科技发布会","产品展示","未来感"], "quality_rating": 4, "verified": False,
     "notes": "绿-蓝渐变Glow+细扫描线+逐字揭示。"},

    {"id": "effect_aurora", "name": "极光幻彩", "name_en": "Aurora",
     "effects": [glow(0.3, 40, 1.8, [0.2,1,0.5,1], [0.3,0.2,1,1]), tint([0.1,0.3,0.2,1], [0.5,1,0.8,1])],
     "text_animators": [],
     "expressions": {"opacity": "90+Math.sin(time*0.8)*10;"},
     "visual_style": "极光梦幻", "recommended_font_traits": ["纤细","优雅","无衬线","衬线"],
     "best_for": ["自然纪录片","梦幻场景","冥想视频"], "quality_rating": 3, "verified": False,
     "notes": "绿-紫双色Glow模拟极光色彩。"},

    {"id": "effect_light_leak", "name": "漏光胶片", "name_en": "Light Leak",
     "effects": [glow(0.6, 60, 0.8, [1,0.8,0.3,1], [1,0.4,0.2,1]), fractal(1, 1.5, -70)],
     "text_animators": [],
     "expressions": {"opacity": "85+Math.sin(time*0.5)*15;"},
     "visual_style": "复古漏光", "recommended_font_traits": ["衬线","手写","优雅"],
     "best_for": ["复古Vlog","胶片风格","怀旧场景"], "quality_rating": 3, "verified": False,
     "notes": "暖色大范围柔光+微弱噪点模拟胶片漏光。"},

    # ---- 质感/材质系 (5) ----
    {"id": "effect_metallic_bevel", "name": "金属浮雕", "name_en": "Metallic Bevel",
     "effects": [bevel(5, 3, 1, 135, 30, [1,1,0.9,1], 80, [0.2,0.15,0.1,1], 60),
                 glow(0.5, 8, 0.6, [1,0.95,0.8,1], [0.8,0.7,0.5,1])],
     "text_animators": [], "expressions": {}, "visual_style": "金属质感",
     "recommended_font_traits": ["粗体","衬线","展示体"],
     "best_for": ["高端品牌","金属质感","电影标题"], "quality_rating": 4, "verified": False,
     "notes": "Bevel Emboss模拟金属浮雕，弱Glow增强高光。"},

    {"id": "effect_chrome_reflect", "name": "镀铬反射", "name_en": "Chrome Reflect",
     "effects": [bevel(8, 1, 1, 45, 60, [1,1,1,1], 100, [0.3,0.3,0.4,1], 80),
                 ramp([0.8,0.8,0.9,1], [0.3,0.3,0.4,1], [0,0], [0,1080], 1)],
     "text_animators": [], "expressions": {}, "visual_style": "镀铬金属",
     "recommended_font_traits": ["粗体","展示体","几何"],
     "best_for": ["汽车标题","工业风格","高端展示"], "quality_rating": 4, "verified": False,
     "notes": "强Bevel+垂直Ramp模拟镀铬反射。"},

    {"id": "effect_glass_crystal", "name": "玻璃水晶", "name_en": "Glass Crystal",
     "effects": [bevel(3, 5, 1, 120, 45, [1,1,1,1], 60, [0.5,0.6,0.8,1], 40),
                 glow(0.7, 15, 0.5, [0.8,0.9,1,1], [0.5,0.6,0.8,1])],
     "text_animators": [],
     "expressions": {"opacity": "80+Math.sin(time)*10;"},
     "visual_style": "玻璃通透", "recommended_font_traits": ["纤细","无衬线","现代"],
     "best_for": ["清新标题","科技产品","水晶质感"], "quality_rating": 3, "verified": False,
     "notes": "柔和Bevel+弱Glow模拟玻璃折射。"},

    {"id": "effect_stone_carve", "name": "石刻浮雕", "name_en": "Stone Carve",
     "effects": [bevel(10, 8, 2, 135, 25, [0.9,0.85,0.75,1], 50, [0.3,0.25,0.2,1], 70),
                 fractal(1, 1.2, -80)],
     "text_animators": [], "expressions": {}, "visual_style": "石刻质感",
     "recommended_font_traits": ["粗体","衬线","传统"],
     "best_for": ["历史题材","纪念碑","古典标题"], "quality_rating": 3, "verified": False,
     "notes": "厚Bevel+内蚀刻(direction=2)+噪点模拟石刻。"},

    {"id": "effect_ice_frost", "name": "冰霜凝结", "name_en": "Ice Frost",
     "effects": [fractal(1, 100, -40), tint([0.3,0.5,0.7,1], [0.8,0.95,1,1]),
                 glow(0.4, 20, 1.0, [0.6,0.85,1,1], [0.3,0.5,0.8,1])],
     "text_animators": [],
     "expressions": {"opacity": "95+Math.sin(time*1.2)*5;"},
     "visual_style": "冰霜质感", "recommended_font_traits": ["粗体","无衬线","展示体"],
     "best_for": ["冬季主题","冰雪场景","冷饮广告"], "quality_rating": 4, "verified": False,
     "notes": "高对比Fractal Noise+蓝白Tint模拟冰霜。"},

    # ---- 复古/怀旧系 (4) ----
    {"id": "effect_retro_vhs", "name": "复古VHS", "name_en": "Retro VHS",
     "effects": [fractal(1, 2, -60), tint([0.1,0.05,0.15,1], [0.8,0.7,0.9,1]), venetian(92, 6, 60)],
     "text_animators": [{"type":"wiggly","name":"VHSShake","prop":"ADBE Text Position 3D","value":[2,1,0],"size":10,"rate":5}],
     "expressions": {"position": "value+[Math.sin(time*3)*2,0];"},
     "visual_style": "复古录像带", "recommended_font_traits": ["粗体","展示体","等宽"],
     "best_for": ["80年代复古","怀旧Vlog","复古音乐"], "quality_rating": 4, "verified": False,
     "notes": "扫描线+噪点+水平抖动模拟VHS。"},

    {"id": "effect_film_grain", "name": "胶片颗粒", "name_en": "Film Grain",
     "effects": [fractal(1, 1.8, -65), tint([0.12,0.1,0.08,1], [0.9,0.85,0.75,1])],
     "text_animators": [], "expressions": {}, "visual_style": "胶片复古",
     "recommended_font_traits": ["衬线","手写","优雅"],
     "best_for": ["电影字幕","文艺片","复古风格"], "quality_rating": 3, "verified": False,
     "notes": "暖色调Tint+微弱噪点模拟胶片。"},

    {"id": "effect_old_tv", "name": "老电视", "name_en": "Old TV",
     "effects": [venetian(88, 10, 40), fractal(1, 1.5, -70), tint([0.05,0.08,0.05,1], [0.7,0.75,0.7,1])],
     "text_animators": [{"type":"wiggly","name":"TVFlicker","prop":"ADBE Text Opacity","value":5,"size":8,"rate":4}],
     "expressions": {}, "visual_style": "老式电视",
     "recommended_font_traits": ["等宽","粗体","圆润"],
     "best_for": ["复古节目","怀旧场景","恐怖题材"], "quality_rating": 3, "verified": False,
     "notes": "粗扫描线+灰绿调+Wiggly透明度。"},

    {"id": "effect_vintage_print", "name": "复古印刷", "name_en": "Vintage Print",
     "effects": [tint([0.15,0.1,0.05,1], [0.85,0.75,0.6,1]), fractal(1, 1.3, -75),
                 bevel(2, 6, 1, 135, 20, [0.9,0.8,0.65,1], 30, [0.3,0.2,0.1,1], 40)],
     "text_animators": [], "expressions": {}, "visual_style": "复古印刷",
     "recommended_font_traits": ["衬线","粗体","展示体"],
     "best_for": ["复古海报","报纸风格","怀旧标题"], "quality_rating": 3, "verified": False,
     "notes": "暖棕色调+微弱Bevel+噪点模拟旧报纸。"},

    # ---- 动态/能量系 (3) ----
    {"id": "effect_electric_shock", "name": "电击闪击", "name_en": "Electric Shock",
     "effects": [glow(0.05, 18, 2.5, [0.5,0.7,1,1], [1,1,1,1]), turb(3, 10)],
     "text_animators": [{"type":"wiggly","name":"ElectricJitter","prop":"ADBE Text Position 3D","value":[4,3,0],"size":60,"rate":20}],
     "expressions": {"opacity": "if(random()>0.92)60;else 100;"},
     "visual_style": "电击能量", "recommended_font_traits": ["粗体","无衬线","几何"],
     "best_for": ["能量展示","战斗场景","电竞标题"], "quality_rating": 4, "verified": False,
     "notes": "蓝白强Glow+高频抖动+随机闪烁。"},

    {"id": "effect_fire_burn", "name": "烈焰燃烧", "name_en": "Fire Burn",
     "effects": [turb(11, 25), glow(0.2, 25, 2.0, [1,0.5,0,1], [1,0.15,0,1])],
     "text_animators": [{"type":"wiggly","name":"FireShake","prop":"ADBE Text Position 3D","value":[3,5,0],"size":25,"rate":12}],
     "expressions": {"position": "freq=15;amp=6;[value[0]+Math.sin(time*freq*0.7)*amp*0.3,value[1]+Math.sin(time*freq)*amp*0.5];"},
     "visual_style": "火焰燃烧", "recommended_font_traits": ["粗体","冲击","极粗"],
     "best_for": ["热血标题","战斗场景","火焰特效"], "quality_rating": 4, "verified": False,
     "notes": "TurbulentDisplace max+橙红Glow+抖动。"},

    {"id": "effect_smoke_dissolve", "name": "烟雾消散", "name_en": "Smoke Dissolve",
     "effects": [fractal(1, 2.5, -50), tint([0.2,0.2,0.25,1], [0.7,0.7,0.75,1]),
                 glow(0.5, 30, 0.8, [0.6,0.6,0.65,1], [0.3,0.3,0.35,1])],
     "text_animators": [{"type":"range","name":"SmokeFade","prop":"ADBE Text Opacity","value":0,
         "start":0,"end":100,"offset_anim":{"from":100,"to":0,"duration":2.0},"shape":3}],
     "expressions": {}, "visual_style": "烟雾弥漫",
     "recommended_font_traits": ["粗体","无衬线"],
     "best_for": ["消散效果","神秘场景","过渡转场"], "quality_rating": 3, "verified": False,
     "notes": "Fractal Noise+灰调+Range反向揭示。"},

    # ---- 简约/优雅系 (3) ----
    {"id": "effect_minimal_line", "name": "极简线条", "name_en": "Minimal Line",
     "effects": [drop_shadow(3, 135, 5, 30, [0,0,0,1])],
     "text_animators": [{"type":"range","name":"LineReveal","prop":"ADBE Text Stroke Width","value":1,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":2}],
     "expressions": {}, "visual_style": "极简主义",
     "recommended_font_traits": ["纤细","无衬线","现代"],
     "best_for": ["品牌设计","极简标题","高端字幕"], "quality_rating": 4, "verified": False,
     "notes": "纯描边揭示+微弱投影。"},

    {"id": "effect_elegant_fade", "name": "优雅淡入", "name_en": "Elegant Fade",
     "effects": [drop_shadow(5, 135, 8, 20, [0,0,0,1]), glow(0.7, 20, 0.4, [1,1,1,1], [0.9,0.9,0.9,1])],
     "text_animators": [],
     "expressions": {"opacity": "linear(time,inPoint,inPoint+1.5,0,100);"},
     "visual_style": "优雅简约", "recommended_font_traits": ["衬线","纤细","优雅"],
     "best_for": ["文艺片字幕","优雅标题","纪录片"], "quality_rating": 4, "verified": False,
     "notes": "弱投影+极柔Glow+缓慢淡入。"},

    {"id": "effect_clean_shadow", "name": "干净投影", "name_en": "Clean Shadow",
     "effects": [drop_shadow(8, 135, 3, 50, [0,0,0,1])],
     "text_animators": [], "expressions": {}, "visual_style": "现代简约",
     "recommended_font_traits": ["无衬线","粗体","现代"],
     "best_for": ["UI展示","产品标题","现代字幕"], "quality_rating": 3, "verified": False,
     "notes": "单一DropShadow，干净利落。"},
]

print(f"[OK] 特效组合库: {len(EFFECT_COMBOS)} 套")

# ============================================================
# 维度二：入场动画库（25+种）
# ============================================================
ENTRANCE_ANIMATIONS = [
    # ---- Ground Truth (5) ----
    {"id":"anim_bounce_in","name":"弹性入场","name_en":"Bounce In",
     "keyframes":{"scale":[{"t":0,"v":[0,0]},{"t":0.25,"v":[110,110]},{"t":0.4,"v":[100,100]}],
                  "opacity":[{"t":0,"v":0},{"t":0.15,"v":100}]},
     "easing":"bezier","duration_sec":0.5,"text_animator":None,"expression":None,
     "best_for":["通用标题","活力场景","弹跳强调"],"difficulty":1,
     "notes":"基准S3/S5/S6。Scale过冲110%后回弹100%。"},

    {"id":"anim_glitch_pop","name":"故障弹出","name_en":"Glitch Pop",
     "keyframes":{"scale":[{"t":0,"v":[0,0]},{"t":0.2,"v":[115,115]},{"t":0.35,"v":[95,95]},{"t":0.45,"v":[100,100]}],
                  "opacity":[{"t":0,"v":0},{"t":0.1,"v":100}]},
     "easing":"bezier","duration_sec":0.5,
     "text_animator":{"type":"wiggly","prop":"ADBE Text Position 3D","value":[6,4,0],"size":20,"rate":10,"duration":0.5},
     "expression":"if(time<inPoint+0.5){seedRandom(Math.floor(time*12),true);[value[0]+random(-5,5),value[1]+random(-3,3)];}else value;",
     "best_for":["故障风标题","科技感","潮流视觉"],"difficulty":2,
     "notes":"基准S1风格。弹性+抖动，入场后抖动渐弱。"},

    {"id":"anim_kinetic_smash","name":"动力撞击","name_en":"Kinetic Smash",
     "keyframes":{"scale":[{"t":0,"v":[0,0]},{"t":0.15,"v":[130,130]},{"t":0.25,"v":[90,90]},{"t":0.35,"v":[105,105]},{"t":0.45,"v":[100,100]}],
                  "opacity":[{"t":0,"v":0},{"t":0.08,"v":100}],
                  "position_y":[{"t":0,"v":-50},{"t":0.15,"v":10},{"t":0.25,"v":-5},{"t":0.35,"v":0}]},
     "easing":"bezier","duration_sec":0.5,"text_animator":None,
     "expression":"if(time<inPoint+0.5){seedRandom(Math.floor(time*15),true);[value[0]+random(-4,4),value[1]+random(-2,2)];}else value;",
     "best_for":["热血标题","运动场景","冲击感"],"difficulty":2,
     "notes":"基准S5风格。Scale过冲130%+多次回弹+Position震动。"},

    {"id":"anim_tracking_fade","name":"字距渐显","name_en":"Tracking Fade",
     "keyframes":{"opacity":[{"t":0,"v":0},{"t":1.5,"v":100}]},
     "easing":"ease_out","duration_sec":1.5,
     "text_animator":{"type":"range","prop":"ADBE Text Tracking Amount","value":-200,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":2},
     "expression":None,
     "best_for":["高端标题","电影字幕","优雅展示"],"difficulty":2,
     "notes":"字距从极宽到正常+透明度渐显，Range Selector RampUp驱动。"},

    {"id":"anim_typewriter","name":"打字机","name_en":"Typewriter",
     "keyframes":{},
     "easing":"linear","duration_sec":1.5,
     "text_animator":{"type":"range","prop":"ADBE Text Opacity","value":0,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":1,
         "units":"characters"},
     "expression":None,
     "best_for":["代码展示","对话引言","打字效果"],"difficulty":1,
     "notes":"Range Selector逐字揭示，线性匀速。"},

    # ---- 基础变换类 (6) ----
    {"id":"anim_scale_zoom","name":"缩放淡入","name_en":"Scale Zoom",
     "keyframes":{"scale":[{"t":0,"v":[50,50]},{"t":0.5,"v":[100,100]}],
                  "opacity":[{"t":0,"v":0},{"t":0.3,"v":100}]},
     "easing":"ease_out","duration_sec":0.5,"text_animator":None,"expression":None,
     "best_for":["通用标题","简约入场"],"difficulty":1,
     "notes":"Scale 50%->100%+Opacity渐显，easeOut缓动。"},

    {"id":"anim_slide_from_left","name":"从左滑入","name_en":"Slide From Left",
     "keyframes":{"position_x":[{"t":0,"v":-500},{"t":0.6,"v":0}],
                  "opacity":[{"t":0,"v":0},{"t":0.2,"v":100}]},
     "easing":"ease_out","duration_sec":0.6,"text_animator":None,"expression":None,
     "best_for":["列表项","信息展示","副标题"],"difficulty":1,
     "notes":"从左侧500px滑入+渐显。"},

    {"id":"anim_slide_from_right","name":"从右滑入","name_en":"Slide From Right",
     "keyframes":{"position_x":[{"t":0,"v":500},{"t":0.6,"v":0}],
                  "opacity":[{"t":0,"v":0},{"t":0.2,"v":100}]},
     "easing":"ease_out","duration_sec":0.6,"text_animator":None,"expression":None,
     "best_for":["列表项","信息展示","副标题"],"difficulty":1,
     "notes":"从右侧500px滑入+渐显。"},

    {"id":"anim_slide_from_top","name":"从上下滑","name_en":"Slide From Top",
     "keyframes":{"position_y":[{"t":0,"v":-300},{"t":0.5,"v":0}],
                  "opacity":[{"t":0,"v":0},{"t":0.15,"v":100}]},
     "easing":"ease_out","duration_sec":0.5,"text_animator":None,"expression":None,
     "best_for":["标题","说明文字","字幕"],"difficulty":1,
     "notes":"从上方300px滑入。"},

    {"id":"anim_slide_from_bottom","name":"从下滑入","name_en":"Slide From Bottom",
     "keyframes":{"position_y":[{"t":0,"v":300},{"t":0.5,"v":0}],
                  "opacity":[{"t":0,"v":0},{"t":0.15,"v":100}]},
     "easing":"ease_out","duration_sec":0.5,"text_animator":None,"expression":None,
     "best_for":["字幕","说明文字","基准S4风格"],"difficulty":1,
     "notes":"基准S4使用。从下方80px滑入(参数可调)。"},

    {"id":"anim_rotate_spin","name":"旋转入场","name_en":"Rotate Spin",
     "keyframes":{"rotation":[{"t":0,"v":-180},{"t":0.6,"v":0}],
                  "scale":[{"t":0,"v":[0,0]},{"t":0.6,"v":[100,100]}],
                  "opacity":[{"t":0,"v":0},{"t":0.2,"v":100}]},
     "easing":"ease_out","duration_sec":0.6,"text_animator":None,"expression":None,
     "best_for":["动感标题","活力场景","转场"],"difficulty":1,
     "notes":"旋转-180°->0°+缩放0->100%。"},

    # ---- 文字特效类 (5) ----
    {"id":"anim_blur_reveal","name":"模糊揭示","name_en":"Blur Reveal",
     "keyframes":{"opacity":[{"t":0,"v":0},{"t":0.3,"v":100}]},
     "easing":"ease_out","duration_sec":1.5,
     "text_animator":{"type":"range","prop":"ADBE Text Blur","value":40,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":2},
     "expression":None,
     "best_for":["梦幻标题","文化片","优雅入场"],"difficulty":2,
     "notes":"基准S2使用。模糊40->0+Range Selector揭示。"},

    {"id":"anim_stroke_draw","name":"描边绘制","name_en":"Stroke Draw",
     "keyframes":{},
     "easing":"ease_in_out","duration_sec":2.0,
     "text_animator":{"type":"range","prop":"ADBE Text Stroke Width","value":3,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":2.0},"shape":2},
     "expression":None,
     "best_for":["优雅标题","描边风格","简约展示"],"difficulty":2,
     "notes":"描边宽度从0逐字揭示到3px。"},

    {"id":"anim_color_wipe","name":"色彩擦除","name_en":"Color Wipe",
     "keyframes":{},
     "easing":"linear","duration_sec":1.5,
     "text_animator":{"type":"range","prop":"ADBE Text Fill Color","value":[1,0.2,0.4],
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":5},
     "expression":None,
     "best_for":["色彩强调","活力标题","潮流视觉"],"difficulty":2,
     "notes":"填充色从一种颜色逐字擦除到另一种。"},

    {"id":"anim_letter_pop","name":"逐字弹出","name_en":"Letter Pop",
     "keyframes":{},
     "easing":"bezier","duration_sec":1.0,
     "text_animator":{"type":"range","prop":"ADBE Text Scale","value":[150,150,0],
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.0},"shape":5,
         "units":"characters"},
     "expression":None,
     "best_for":["活泼标题","综艺花字","趣味展示"],"difficulty":2,
     "notes":"每个字依次弹出放大150%后回弹。"},

    {"id":"anim_baseline_wave","name":"基线波浪","name_en":"Baseline Wave",
     "keyframes":{},
     "easing":"ease_in_out","duration_sec":1.5,
     "text_animator":{"type":"range","prop":"ADBE Text Baseline Shift","value":30,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":5},
     "expression":None,
     "best_for":["波浪标题","活泼场景","音乐视频"],"difficulty":2,
     "notes":"基线偏移逐字形成波浪。"},

    # ---- 高级动画类 (5) ----
    {"id":"anim_elastic_overshoot","name":"弹性过冲","name_en":"Elastic Overshoot",
     "keyframes":{"scale":[{"t":0,"v":[0,0]},{"t":0.3,"v":[120,120]},{"t":0.5,"v":[95,95]},{"t":0.65,"v":[103,103]},{"t":0.8,"v":[100,100]}],
                  "opacity":[{"t":0,"v":0},{"t":0.1,"v":100}]},
     "easing":"bezier","duration_sec":0.8,"text_animator":None,
     "expression":"freq=3;decay=2;amp=10;value+[0,Math.sin(time*freq*Math.PI*2)*amp/Math.exp(decay*(time-inPoint))]",
     "best_for":["强调标题","弹性展示"],"difficulty":3,
     "notes":"多次过冲收敛+表达式弹性余震。"},

    {"id":"anim_squash_stretch","name":"挤压拉伸","name_en":"Squash & Stretch",
     "keyframes":{"scale":[{"t":0,"v":[0,0]},{"t":0.15,"v":[60,140]},{"t":0.3,"v":[130,80]},{"t":0.45,"v":[95,105]},{"t":0.55,"v":[100,100]}],
                  "opacity":[{"t":0,"v":0},{"t":0.1,"v":100}]},
     "easing":"bezier","duration_sec":0.6,"text_animator":None,"expression":None,
     "best_for":["卡通风格","趣味标题","弹性展示"],"difficulty":3,
     "notes":"先纵向拉伸(60x140)再横向挤压(130x80)再回弹。"},

    {"id":"anim_flip_3d_x","name":"3D水平翻转","name_en":"3D Flip X",
     "keyframes":{"rotation_y":[{"t":0,"v":90},{"t":0.6,"v":0}],
                  "opacity":[{"t":0,"v":0},{"t":0.2,"v":100}]},
     "easing":"ease_out","duration_sec":0.6,"text_animator":None,"expression":None,
     "best_for":["科技标题","3D展示","转场"],"difficulty":3,
     "notes":"Y轴旋转90°->0°，需开启3D图层。"},

    {"id":"anim_flip_3d_y","name":"3D垂直翻转","name_en":"3D Flip Y",
     "keyframes":{"rotation_x":[{"t":0,"v":-90},{"t":0.6,"v":0}],
                  "opacity":[{"t":0,"v":0},{"t":0.2,"v":100}]},
     "easing":"ease_out","duration_sec":0.6,"text_animator":None,"expression":None,
     "best_for":["科技标题","3D展示","翻转入场"],"difficulty":3,
     "notes":"X轴旋转-90°->0°，需开启3D图层。"},

    {"id":"anim_spiral_in","name":"螺旋入场","name_en":"Spiral In",
     "keyframes":{"rotation":[{"t":0,"v":-360},{"t":0.8,"v":0}],
                  "scale":[{"t":0,"v":[0,0]},{"t":0.8,"v":[100,100]}],
                  "opacity":[{"t":0,"v":0},{"t":0.2,"v":100}]},
     "easing":"ease_out","duration_sec":0.8,"text_animator":None,"expression":None,
     "best_for":["创意标题","动感入场","趣味展示"],"difficulty":2,
     "notes":"旋转-360°+缩放0->100%组合螺旋入场。"},

    # ---- 逐字控制类 (5) ----
    {"id":"anim_wave_per_char","name":"逐字波浪","name_en":"Wave Per Character",
     "keyframes":{},
     "easing":"ease_in_out","duration_sec":2.0,
     "text_animator":{"type":"range","prop":"ADBE Text Position 3D","value":[0,-40,0],
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":2.0},"shape":5,
         "units":"characters"},
     "expression":None,
     "best_for":["波浪标题","音乐视频","活泼场景"],"difficulty":2,
     "notes":"逐字上下浮动形成波浪传播效果。"},

    {"id":"anim_cascade_fall","name":"级联坠落","name_en":"Cascade Fall",
     "keyframes":{},
     "easing":"ease_in","duration_sec":1.0,
     "text_animator":{"type":"range","prop":"ADBE Text Position 3D","value":[0,-200,0],
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.0},"shape":2,
         "units":"characters"},
     "expression":None,
     "best_for":["标题入场","力量感","动感展示"],"difficulty":2,
     "notes":"每个字从上方200px依次坠落。"},

    {"id":"anim_random_pop","name":"随机弹出","name_en":"Random Pop",
     "keyframes":{},
     "easing":"bezier","duration_sec":1.0,
     "text_animator":{"type":"range","prop":"ADBE Text Scale","value":[200,200,0],
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.0},"shape":5,
         "units":"characters","randomize":True},
     "expression":None,
     "best_for":["趣味标题","综艺花字","随机效果"],"difficulty":2,
     "notes":"每个字随机顺序弹出放大200%后回弹。"},

    {"id":"anim_domino_fall","name":"多米诺骨牌","name_en":"Domino Fall",
     "keyframes":{},
     "easing":"ease_in","duration_sec":1.5,
     "text_animator":{"type":"range","prop":"ADBE Text Rotation","value":90,
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":2,
         "units":"characters"},
     "expression":None,
     "best_for":["创意标题","趣味入场","多米诺效果"],"difficulty":2,
     "notes":"每个字依次旋转90°倒下如多米诺。"},

    {"id":"anim_scatter_converge","name":"散点汇聚","name_en":"Scatter Converge",
     "keyframes":{},
     "easing":"ease_out","duration_sec":1.5,
     "text_animator":{"type":"range","prop":"ADBE Text Position 3D","value":[200,150,0],
         "start":0,"end":100,"offset_anim":{"from":-100,"to":0,"duration":1.5},"shape":5,
         "units":"characters","randomize":True},
     "expression":None,
     "best_for":["汇聚效果","创意标题","科幻场景"],"difficulty":3,
     "notes":"每个字从随机位置汇聚到最终位置。"},
]

print(f"[OK] 入场动画库: {len(ENTRANCE_ANIMATIONS)} 种")

# ============================================================
# 维度三：精选字体库（50+款）
# ============================================================
FONT_LIBRARY = [
    # ---- 中文黑体 (6) ----
    {"id":"font_simhei","postscript_name":"SimHei","file_path":"C:\\Windows\\Fonts\\simhei.ttf",
     "category":"中文黑体","style_keywords":["粗壮","醒目","中性","无衬线"],
     "stroke_traits":{"weight":"heavy","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_cyber_glitch","effect_neon_pulse","effect_fire_ice","effect_golden_logo","effect_electric_shock"],
     "recommended_animations":["anim_bounce_in","anim_kinetic_smash","anim_glitch_pop"],
     "best_for":["新闻标题","警示文字","强对比副标题"],"verified":False,"notes":"单一字重，中文标题主力。"},

    {"id":"font_noto_sans_sc","postscript_name":"NotoSansSC-VF","file_path":"C:\\Windows\\Fonts\\NotoSansSC-VF.ttf",
     "category":"中文黑体","style_keywords":["开源","现代无衬线","字重可变","科技感"],
     "stroke_traits":{"weight":"variable(100-900)","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_hologram_hud","effect_laser_scan","effect_clean_shadow","effect_circuit_board"],
     "recommended_animations":["anim_tracking_fade","anim_slide_from_bottom","anim_blur_reveal"],
     "best_for":["现代企业片","UI演示","科技品牌字幕"],"verified":False,"notes":"可变字重100-900连续可调，极灵活。"},

    {"id":"font_dengxian_bold","postscript_name":"DengXian-Bold","file_path":"C:\\Windows\\Fonts\\Dengb.ttf",
     "category":"中文黑体","style_keywords":["现代","清爽","微软默认","中文字重"],
     "stroke_traits":{"weight":"bold","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_clean_shadow","effect_neon_pulse","effect_minimal_line"],
     "recommended_animations":["anim_bounce_in","anim_slide_from_left","anim_scale_zoom"],
     "best_for":["科技类视频","Windows UI","现代字幕"],"verified":False,"notes":"DengXian家族Bold字重。"},

    {"id":"font_alibaba_puhui","postscript_name":"AlibabaPuHuiTi-3-45-Light","file_path":"C:\\Windows\\Fonts\\AlibabaPuHuiTi-3-45-Light.ttf",
     "category":"中文黑体","style_keywords":["免费商用","互联网感","现代","轻盈"],
     "stroke_traits":{"weight":"light","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_soft_glow","effect_elegant_fade","effect_clean_shadow"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_slide_from_bottom"],
     "best_for":["互联网产品字幕","电商短视频","品牌片尾"],"verified":False,"notes":"免费商用，轻盈现代。"},

    {"id":"font_msyh_bold","postscript_name":"MicrosoftYaHeiBold","file_path":"C:\\Windows\\Fonts\\msyhbd.ttc",
     "category":"中文黑体","style_keywords":["微软雅黑","粗壮","圆润","现代"],
     "stroke_traits":{"weight":"bold","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_neon_pulse","effect_golden_logo","effect_clean_shadow"],
     "recommended_animations":["anim_bounce_in","anim_kinetic_smash","anim_scale_zoom"],
     "best_for":["通用标题","综艺字幕","品牌展示"],"verified":False,"notes":"微软雅黑Bold，圆润粗壮。"},

    {"id":"font_stheiti","postscript_name":"STHeiti","file_path":"C:\\Windows\\Fonts\\STHeiti Light.ttc",
     "category":"中文黑体","style_keywords":["华文黑体","传统","中性","清晰"],
     "stroke_traits":{"weight":"light-medium","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_clean_shadow","effect_minimal_line","effect_elegant_fade"],
     "recommended_animations":["anim_tracking_fade","anim_slide_from_left","anim_blur_reveal"],
     "best_for":["通用字幕","文档标题","教育视频"],"verified":False,"notes":"华文黑体，传统清晰。"},

    # ---- 中文宋体/衬线 (5) ----
    {"id":"font_simsun","postscript_name":"SimSun-ExtB","file_path":"C:\\Windows\\Fonts\\simsunb.ttf",
     "category":"中文宋体","style_keywords":["古典","衬线","阅读感强","传统"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"yes","width":"normal"},
     "recommended_effects":["effect_ink_wash","effect_film_grain","effect_vintage_print"],
     "recommended_animations":["anim_typewriter","anim_blur_reveal","anim_tracking_fade"],
     "best_for":["大段中文正文","传统文化题材","古典字幕"],"verified":False,"notes":"经典宋体，阅读感强。"},

    {"id":"font_noto_serif_sc","postscript_name":"NotoSerifSC-VF","file_path":"C:\\Windows\\Fonts\\NotoSerifSC-VF.ttf",
     "category":"中文宋体","style_keywords":["开源","衬线","可变字重","文化感"],
     "stroke_traits":{"weight":"variable(200-900)","x_height":"medium","serif":"yes","width":"normal"},
     "recommended_effects":["effect_ink_wash","effect_elegant_fade","effect_stone_carve","effect_film_grain"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_typewriter"],
     "best_for":["纪录片字幕","文化题材","文学性标题"],"verified":False,"notes":"可变字重200-900。"},

    {"id":"font_fangsong","postscript_name":"FangSong","file_path":"C:\\Windows\\Fonts\\simfang.ttf",
     "category":"中文宋体","style_keywords":["官方公文","规整","纤细","字脚微衬"],
     "stroke_traits":{"weight":"light","x_height":"medium","serif":"subtle","width":"normal"},
     "recommended_effects":["effect_minimal_line","effect_clean_shadow","effect_elegant_fade"],
     "recommended_animations":["anim_typewriter","anim_tracking_fade","anim_blur_reveal"],
     "best_for":["政府/法律类正文","技术说明字幕"],"verified":False,"notes":"纤细规整，公文风格。"},

    {"id":"font_stsong","postscript_name":"STSong","file_path":"C:\\Windows\\Fonts\\simsun.ttc",
     "category":"中文宋体","style_keywords":["华文宋体","经典","衬线","阅读"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"yes","width":"normal"},
     "recommended_effects":["effect_ink_wash","effect_vintage_print","effect_film_grain"],
     "recommended_animations":["anim_typewriter","anim_blur_reveal","anim_tracking_fade"],
     "best_for":["文化片字幕","古典引用","正式文档"],"verified":False,"notes":"华文宋体，经典衬线。"},

    {"id":"font_dengxian_light","postscript_name":"DengXian-Light","file_path":"C:\\Windows\\Fonts\\Dengl.ttf",
     "category":"中文宋体","style_keywords":["现代","轻盈","清爽","细衬线"],
     "stroke_traits":{"weight":"light","x_height":"tall","serif":"subtle","width":"normal"},
     "recommended_effects":["effect_soft_glow","effect_elegant_fade","effect_minimal_line"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_slide_from_bottom"],
     "best_for":["轻盈字幕","现代副标题","优雅展示"],"verified":False,"notes":"DengXian家族Light字重。"},

    # ---- 中文书法/手写 (5) ----
    {"id":"font_kaiti","postscript_name":"KaiTi","file_path":"C:\\Windows\\Fonts\\simkai.ttf",
     "category":"中文书法","style_keywords":["传统书法","文化感","手写味","温润"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"brush","width":"normal"},
     "recommended_effects":["effect_ink_wash","effect_stone_carve","effect_film_grain"],
     "recommended_animations":["anim_blur_reveal","anim_typewriter","anim_tracking_fade"],
     "best_for":["文化片标题","古籍引用","教育类字幕"],"verified":True,
     "notes":"基准S2使用。传统楷体，温润文化感。"},

    {"id":"font_mashanzheng","postscript_name":"MaShanZheng","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\MaShanZheng-Regular.ttf",
     "category":"中文书法","style_keywords":["中文手写","毛笔感","灵动"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"brush","width":"normal"},
     "recommended_effects":["effect_ink_wash","effect_fire_burn","effect_stone_carve"],
     "recommended_animations":["anim_blur_reveal","anim_stroke_draw","anim_tracking_fade"],
     "best_for":["MV中文歌词","文化片题字","海报式标题"],"verified":False,"notes":"毛笔书法感，灵动。"},

    {"id":"font_stkaiti","postscript_name":"STKaiti","file_path":"C:\\Windows\\Fonts\\simkai.ttf",
     "category":"中文书法","style_keywords":["华文楷体","优雅","传统","清晰"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"brush","width":"normal"},
     "recommended_effects":["effect_ink_wash","effect_elegant_fade","effect_soft_glow"],
     "recommended_animations":["anim_blur_reveal","anim_typewriter","anim_tracking_fade"],
     "best_for":["文化片字幕","优雅引用","教育视频"],"verified":False,"notes":"华文楷体，优雅清晰。"},

    {"id":"font_lisu","postscript_name":"LiSu","file_path":"C:\\Windows\\Fonts\\SIMLI.TTF",
     "category":"中文书法","style_keywords":["隶书","古典","庄重","传统"],
     "stroke_traits":{"weight":"medium","x_height":"medium","serif":"brush","width":"wide"},
     "recommended_effects":["effect_ink_wash","effect_stone_carve","effect_vintage_print"],
     "recommended_animations":["anim_blur_reveal","anim_stroke_draw","anim_tracking_fade"],
     "best_for":["古典标题","印章风格","文化片头"],"verified":False,"notes":"隶书，古典庄重。"},

    {"id":"font_youyuan","postscript_name":"YouYuan","file_path":"C:\\Windows\\Fonts\\SIMYOU.TTF",
     "category":"中文书法","style_keywords":["幼圆","圆润","可爱","柔和"],
     "stroke_traits":{"weight":"medium","x_height":"medium","serif":"none","width":"normal"},
     "recommended_effects":["effect_soft_glow","effect_neon_sign","effect_clean_shadow"],
     "recommended_animations":["anim_bounce_in","anim_letter_pop","anim_wave_per_char"],
     "best_for":["儿童节目","可爱标题","轻松场景"],"verified":False,"notes":"圆润可爱，轻松柔和。"},

    # ---- 中文展示/装饰 (4) ----
    {"id":"font_fzcuheisong","postscript_name":"FZCuHeiSongS-B-GB","file_path":"C:\\Windows\\Fonts\\方正粗黑宋简体.ttf",
     "category":"中文展示","style_keywords":["粗黑+宋体混合","方正","装饰性强"],
     "stroke_traits":{"weight":"bold","x_height":"tall","serif":"mixed","width":"normal"},
     "recommended_effects":["effect_golden_logo","effect_metallic_bevel","effect_neon_pulse","effect_fire_ice"],
     "recommended_animations":["anim_bounce_in","anim_kinetic_smash","anim_tracking_fade"],
     "best_for":["新闻大标题","强冲击力中文标题","文化片头"],"verified":False,"notes":"粗黑+宋体混合，强装饰性。"},

    {"id":"font_stxihei","postscript_name":"STXihei","file_path":"C:\\Windows\\Fonts\\SIMHEI.ttf",
     "category":"中文展示","style_keywords":["华文细黑","纤细","现代","精致"],
     "stroke_traits":{"weight":"light","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_minimal_line","effect_soft_glow","effect_elegant_fade","effect_laser_scan"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_slide_from_bottom"],
     "best_for":["高端字幕","现代标题","精致展示"],"verified":False,"notes":"华文细黑，纤细精致。"},

    {"id":"font_alibaba_heavy","postscript_name":"AlibabaPuHuiTi-3-85-Bold","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\AlibabaPuHuiTi-3-85-Bold.ttf",
     "category":"中文展示","style_keywords":["阿里巴巴","粗体","现代","冲击"],
     "stroke_traits":{"weight":"bold","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_neon_pulse","effect_golden_logo","effect_electric_shock","effect_cyber_glitch"],
     "recommended_animations":["anim_bounce_in","anim_kinetic_smash","anim_glitch_pop"],
     "best_for":["电商标题","品牌展示","冲击力标题"],"verified":False,"notes":"阿里巴巴普惠体Bold。"},

    {"id":"font_fzzhenghei","postscript_name":"FZZhengHei-M-02","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\FZZHJW.TTF",
     "category":"中文展示","style_keywords":["方正正黑","粗壮","中性","现代"],
     "stroke_traits":{"weight":"medium-bold","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_neon_pulse","effect_clean_shadow","effect_metallic_bevel"],
     "recommended_animations":["anim_bounce_in","anim_scale_zoom","anim_kinetic_smash"],
     "best_for":["通用标题","品牌展示","现代字幕"],"verified":False,"notes":"方正正黑，粗壮中性。"},

    # ---- 英文粗犷冲击 (5) ----
    {"id":"font_impact","postscript_name":"Impact","file_path":"C:\\Windows\\Fonts\\impact.ttf",
     "category":"英文冲击","style_keywords":["极粗","无衬线","紧凑","高冲击"],
     "stroke_traits":{"weight":"heavy","x_height":"tall","serif":"none","width":"condensed"},
     "recommended_effects":["effect_cyber_glitch","effect_neon_pulse","effect_fire_ice","effect_golden_logo","effect_fire_burn","effect_electric_shock"],
     "recommended_animations":["anim_bounce_in","anim_kinetic_smash","anim_glitch_pop"],
     "best_for":["标题","冲击感","英文"],"verified":True,
     "notes":"基准S1/S5/S6主力字体。极粗无衬线，冲击力强。"},

    {"id":"font_anton","postscript_name":"Anton","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Anton-Regular.ttf",
     "category":"英文冲击","style_keywords":["超粗","展示体","广告风","紧凑"],
     "stroke_traits":{"weight":"heavy","x_height":"tall","serif":"none","width":"condensed"},
     "recommended_effects":["effect_neon_pulse","effect_golden_logo","effect_metallic_bevel","effect_clean_shadow"],
     "recommended_animations":["anim_bounce_in","anim_kinetic_smash","anim_scale_zoom"],
     "best_for":["广告标题","展示体","冲击力英文"],"verified":False,"notes":"超粗展示体，广告风。"},

    {"id":"font_bebasneue","postscript_name":"BebasNeue","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\BebasNeue.otf",
     "category":"英文冲击","style_keywords":["极窄","高挑","欧美海报","展示"],
     "stroke_traits":{"weight":"bold","x_height":"very_tall","serif":"none","width":"very_condensed"},
     "recommended_effects":["effect_neon_sign","effect_laser_scan","effect_retro_vhs","effect_golden_logo"],
     "recommended_animations":["anim_bounce_in","anim_slide_from_left","anim_tracking_fade"],
     "best_for":["海报标题","欧美风","展示体"],"verified":False,"notes":"极窄高挑，海报风。"},

    {"id":"font_blackopsone","postscript_name":"BlackOpsOne","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\BlackOpsOne.ttf",
     "category":"英文冲击","style_keywords":["军事","粗犷"," stencil","力量"],
     "stroke_traits":{"weight":"heavy","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_cyber_glitch","effect_data_corrupt","effect_electric_shock","effect_fire_burn"],
     "recommended_animations":["anim_glitch_pop","anim_kinetic_smash","anim_bounce_in"],
     "best_for":["军事题材","游戏标题","力量感"],"verified":False,"notes":"Stencil风格，军事力量感。"},

    {"id":"font_oswald_bold","postscript_name":"Oswald-Bold","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Oswald-Bold.ttf",
     "category":"英文冲击","style_keywords":["粗体","紧凑","现代","展示"],
     "stroke_traits":{"weight":"bold","x_height":"tall","serif":"none","width":"condensed"},
     "recommended_effects":["effect_neon_pulse","effect_clean_shadow","effect_metallic_bevel"],
     "recommended_animations":["anim_bounce_in","anim_scale_zoom","anim_kinetic_smash"],
     "best_for":["现代标题","展示体","品牌标题"],"verified":False,"notes":"紧凑粗体，现代展示。"},

    # ---- 英文现代无衬线 (6) ----
    {"id":"font_arial_bold","postscript_name":"Arial-BoldMT","file_path":"C:\\Windows\\Fonts\\arialbd.ttf",
     "category":"英文无衬线","style_keywords":["通用","粗体","中性","跨平台"],
     "stroke_traits":{"weight":"bold","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_neon_pulse","effect_golden_logo","effect_clean_shadow","effect_neon_sign"],
     "recommended_animations":["anim_bounce_in","anim_kinetic_smash","anim_scale_zoom"],
     "best_for":["通用标题","英文正文","跨平台"],"verified":True,
     "notes":"基准S3使用。Arial Bold，通用中性。"},

    {"id":"font_helvetica","postscript_name":"Helvetica","file_path":"C:\\Windows\\Fonts\\helvetica.ttf",
     "category":"英文无衬线","style_keywords":["经典","中性","现代","设计标准"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_hologram_hud","effect_clean_shadow","effect_minimal_line","effect_laser_scan"],
     "recommended_animations":["anim_slide_from_bottom","anim_tracking_fade","anim_scale_zoom"],
     "best_for":["经典标题","设计展示","现代字幕"],"verified":True,
     "notes":"基准S4使用。经典中性，设计标准。"},

    {"id":"font_inter","postscript_name":"Inter","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Inter.ttf",
     "category":"英文无衬线","style_keywords":["Google系","现代UI","清晰","屏幕优化"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_hologram_hud","effect_clean_shadow","effect_laser_scan","effect_minimal_line"],
     "recommended_animations":["anim_tracking_fade","anim_slide_from_bottom","anim_blur_reveal"],
     "best_for":["UI展示","科技产品","现代字幕"],"verified":False,"notes":"Google系现代UI风。"},

    {"id":"font_lato","postscript_name":"Lato","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Lato-Regular.ttf",
     "category":"英文无衬线","style_keywords":["温暖","现代","人文","清晰"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_soft_glow","effect_clean_shadow","effect_elegant_fade"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_slide_from_left"],
     "best_for":["品牌字幕","温暖场景","现代展示"],"verified":False,"notes":"温暖现代，人文无衬线。"},

    {"id":"font_montserrat","postscript_name":"Montserrat","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Montserrat-Regular.ttf",
     "category":"英文无衬线","style_keywords":["几何","现代","城市","潮流"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_neon_pulse","effect_neon_sign","effect_clean_shadow","effect_laser_scan"],
     "recommended_animations":["anim_bounce_in","anim_tracking_fade","anim_scale_zoom"],
     "best_for":["潮流标题","城市风格","现代展示"],"verified":False,"notes":"几何现代，城市潮流风。"},

    {"id":"font_poppins","postscript_name":"Poppins","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Poppins-Regular.ttf",
     "category":"英文无衬线","style_keywords":["几何","圆润","现代","友好"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_soft_glow","effect_neon_sign","effect_clean_shadow"],
     "recommended_animations":["anim_bounce_in","anim_letter_pop","anim_scale_zoom"],
     "best_for":["友好标题","现代展示","清新场景"],"verified":False,"notes":"几何圆润，友好现代。"},

    # ---- 英文衬线/优雅 (4) ----
    {"id":"font_georgia_bold","postscript_name":"Georgia-Bold","file_path":"C:\\Windows\\Fonts\\georgiab.ttf",
     "category":"英文衬线","style_keywords":["屏幕衬线","优雅","经典","粗衬线"],
     "stroke_traits":{"weight":"bold","x_height":"medium","serif":"yes","width":"normal"},
     "recommended_effects":["effect_elegant_fade","effect_ink_wash","effect_film_grain","effect_stone_carve"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_typewriter"],
     "best_for":["优雅标题","文学性展示","纪录片"],"verified":False,"notes":"屏幕优化衬线体，优雅经典。"},

    {"id":"font_times","postscript_name":"TimesNewRomanPSMT","file_path":"C:\\Windows\\Fonts\\times.ttf",
     "category":"英文衬线","style_keywords":["经典衬线","正式","印刷","传统"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"yes","width":"normal"},
     "recommended_effects":["effect_film_grain","effect_vintage_print","effect_ink_wash","effect_elegant_fade"],
     "recommended_animations":["anim_typewriter","anim_blur_reveal","anim_tracking_fade"],
     "best_for":["正式文档","印刷风格","古典引用"],"verified":False,"notes":"经典衬线，正式印刷品质。"},

    {"id":"font_merriweather","postscript_name":"Merriweather","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Merriweather-Regular.ttf",
     "category":"英文衬线","style_keywords":["现代衬线","屏幕优化","温暖","阅读"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"yes","width":"wide"},
     "recommended_effects":["effect_elegant_fade","effect_film_grain","effect_soft_glow"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_typewriter"],
     "best_for":["优雅字幕","阅读型展示","温暖场景"],"verified":False,"notes":"现代衬线，屏幕优化。"},

    {"id":"font_playfair","postscript_name":"PlayfairDisplay","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\PlayfairDisplay-Regular.ttf",
     "category":"英文衬线","style_keywords":["高对比","优雅","时尚","展示衬线"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"yes_hairline","width":"normal"},
     "recommended_effects":["effect_elegant_fade","effect_golden_logo","effect_metallic_bevel","effect_soft_glow"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_stroke_draw"],
     "best_for":["时尚标题","高端展示","优雅英文"],"verified":False,"notes":"高对比展示衬线，时尚优雅。"},

    # ---- 英文手写/签名 (4) ----
    {"id":"font_greatvibes","postscript_name":"GreatVibes","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\GreatVibes-Regular.ttf",
     "category":"英文手写","style_keywords":["优雅花体","婚礼","浪漫","连笔"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"script","width":"normal"},
     "recommended_effects":["effect_soft_glow","effect_neon_sign","effect_light_leak","effect_elegant_fade"],
     "recommended_animations":["anim_stroke_draw","anim_blur_reveal","anim_tracking_fade"],
     "best_for":["婚礼字幕","浪漫场景","优雅签名"],"verified":False,"notes":"优雅花体，婚礼浪漫。"},

    {"id":"font_allura","postscript_name":"Allura","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Allura-Regular.ttf",
     "category":"英文手写","style_keywords":["流畅","优雅","签名风","柔和"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"script","width":"normal"},
     "recommended_effects":["effect_soft_glow","effect_elegant_fade","effect_light_leak"],
     "recommended_animations":["anim_stroke_draw","anim_blur_reveal","anim_tracking_fade"],
     "best_for":["签名风格","优雅展示","浪漫标题"],"verified":False,"notes":"流畅签名风，优雅柔和。"},

    {"id":"font_pacifico","postscript_name":"Pacifico","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Pacifico.ttf",
     "category":"英文手写","style_keywords":["圆润","休闲","冲浪","友好"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"script_round","width":"normal"},
     "recommended_effects":["effect_neon_sign","effect_soft_glow","effect_clean_shadow"],
     "recommended_animations":["anim_bounce_in","anim_letter_pop","anim_stroke_draw"],
     "best_for":["休闲标题","友好展示","潮流手写"],"verified":False,"notes":"圆润休闲，冲浪友好。"},

    {"id":"font_dancingscript","postscript_name":"DancingScript","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\DancingScript.ttf",
     "category":"英文手写","style_keywords":["活泼","连笔","手写","动感"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"script","width":"normal"},
     "recommended_effects":["effect_soft_glow","effect_neon_sign","effect_clean_shadow"],
     "recommended_animations":["anim_stroke_draw","anim_wave_per_char","anim_bounce_in"],
     "best_for":["活泼标题","手写展示","轻松场景"],"verified":False,"notes":"活泼连笔，动感手写。"},

    # ---- 等宽/科技 (3) ----
    {"id":"font_consolas","postscript_name":"Consolas","file_path":"C:\\Windows\\Fonts\\consola.ttf",
     "category":"等宽体","style_keywords":["代码等宽","科技感","清晰","终端"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"monospaced"},
     "recommended_effects":["effect_matrix_digital","effect_data_corrupt","effect_circuit_board","effect_hologram_hud"],
     "recommended_animations":["anim_typewriter","anim_glitch_pop","anim_tracking_fade"],
     "best_for":["代码展示","科技字幕","终端界面"],"verified":False,"notes":"代码等宽字体，科技感。"},

    {"id":"font_courier","postscript_name":"CourierNewPSMT","file_path":"C:\\Windows\\Fonts\\cour.ttf",
     "category":"等宽体","style_keywords":["经典打字机","等宽","复古","新闻"],
     "stroke_traits":{"weight":"regular","x_height":"medium","serif":"slab","width":"monospaced"},
     "recommended_effects":["effect_retro_vhs","effect_old_tv","effect_film_grain","effect_typewriter"],
     "recommended_animations":["anim_typewriter","anim_blur_reveal","anim_tracking_fade"],
     "best_for":["打字机效果","复古字幕","新闻字幕"],"verified":False,"notes":"经典打字机等宽。"},

    {"id":"font_dinnext","postscript_name":"DINNextLTPro-Regular","file_path":"C:\\Windows\\Fonts\\DINNextLTPro-Regular.ttf",
     "category":"等宽体","style_keywords":["工业","数字","现代","精准"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"condensed"},
     "recommended_effects":["effect_hologram_hud","effect_laser_scan","effect_circuit_board","effect_clean_shadow"],
     "recommended_animations":["anim_tracking_fade","anim_scale_zoom","anim_slide_from_left"],
     "best_for":["数字展示","工业标题","科技字幕"],"verified":False,"notes":"DIN工业标准，数字精准。"},

    # ---- 童趣/装饰 (4) ----
    {"id":"font_bangers","postscript_name":"Bangers","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Bangers-Regular.ttf",
     "category":"童趣装饰","style_keywords":["漫画","冲击","趣味","POP"],
     "stroke_traits":{"weight":"heavy","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_neon_pulse","effect_rgb_split","effect_electric_shock","effect_clean_shadow"],
     "recommended_animations":["anim_bounce_in","anim_letter_pop","anim_kinetic_smash"],
     "best_for":["漫画风格","趣味标题","POP展示"],"verified":False,"notes":"漫画冲击风，趣味性强。"},

    {"id":"font_chewy","postscript_name":"Chewy","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Chewy.ttf",
     "category":"童趣装饰","style_keywords":["圆润","可爱","卡通","友好"],
     "stroke_traits":{"weight":"bold","x_height":"medium","serif":"none","width":"wide"},
     "recommended_effects":["effect_soft_glow","effect_clean_shadow","effect_neon_sign"],
     "recommended_animations":["anim_bounce_in","anim_letter_pop","anim_squash_stretch"],
     "best_for":["儿童节目","卡通标题","友好展示"],"verified":False,"notes":"圆润可爱，卡通友好。"},

    {"id":"font_luckiestguy","postscript_name":"LuckiestGuy","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\LuckiestGuy.ttf",
     "category":"童趣装饰","style_keywords":["复古漫画","粗体","活泼","50年代"],
     "stroke_traits":{"weight":"heavy","x_height":"tall","serif":"none","width":"wide"},
     "recommended_effects":["effect_neon_sign","effect_retro_vhs","effect_clean_shadow"],
     "recommended_animations":["anim_bounce_in","anim_squash_stretch","anim_letter_pop"],
     "best_for":["复古漫画","活泼标题","50年代风"],"verified":False,"notes":"复古漫画风，活泼有趣。"},

    {"id":"font_fredokaone","postscript_name":"FredokaOne","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\FredokaOne.ttf",
     "category":"童趣装饰","style_keywords":["圆润","粗体","可爱","现代"],
     "stroke_traits":{"weight":"bold","x_height":"tall","serif":"none","width":"wide"},
     "recommended_effects":["effect_soft_glow","effect_clean_shadow","effect_neon_sign"],
     "recommended_animations":["anim_bounce_in","anim_letter_pop","anim_squash_stretch"],
     "best_for":["儿童标题","可爱展示","友好场景"],"verified":False,"notes":"圆润粗体，可爱现代。"},

    # ---- 数字专用 (2) ----
    {"id":"font_bahnschrift","postscript_name":"Bahnschrift","file_path":"C:\\Windows\\Fonts\\bahnschrift.ttf",
     "category":"数字专用","style_keywords":["工业","数字","现代","清晰"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"condensed"},
     "recommended_effects":["effect_hologram_hud","effect_laser_scan","effect_circuit_board"],
     "recommended_animations":["anim_tracking_fade","anim_scale_zoom","anim_typewriter"],
     "best_for":["数字展示","工业标题","科技字幕"],"verified":False,"notes":"工业数字字体。"},

    {"id":"font_arial_black","postscript_name":"Arial-Black","file_path":"C:\\Windows\\Fonts\\arialbd.ttf",
     "category":"数字专用","style_keywords":["极粗","冲击","通用","数字清晰"],
     "stroke_traits":{"weight":"heavy","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_golden_logo","effect_neon_pulse","effect_metallic_bevel","effect_fire_ice"],
     "recommended_animations":["anim_bounce_in","anim_kinetic_smash","anim_scale_zoom"],
     "best_for":["数字冲击","粗体标题","通用展示"],"verified":False,"notes":"Arial Black，极粗通用。"},

    # ---- 额外补充 (2) ----
    {"id":"font_roboto","postscript_name":"Roboto","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Roboto-Regular.ttf",
     "category":"英文无衬线","style_keywords":["机械","现代","Android","清晰"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"none","width":"normal"},
     "recommended_effects":["effect_hologram_hud","effect_clean_shadow","effect_laser_scan","effect_minimal_line"],
     "recommended_animations":["anim_tracking_fade","anim_slide_from_bottom","anim_scale_zoom"],
     "best_for":["Android风格","科技字幕","现代展示"],"verified":False,"notes":"Roboto，机械现代。"},

    {"id":"font_raleway","postscript_name":"Raleway","file_path":"C:\\Users\\Administrator\\AppData\\Local\\Microsoft\\Windows\\Fonts\\Raleway-Regular.ttf",
     "category":"英文衬线","style_keywords":["纤细","优雅","现代","高端"],
     "stroke_traits":{"weight":"regular","x_height":"tall","serif":"subtle","width":"normal"},
     "recommended_effects":["effect_elegant_fade","effect_soft_glow","effect_minimal_line","effect_stone_carve"],
     "recommended_animations":["anim_tracking_fade","anim_blur_reveal","anim_stroke_draw"],
     "best_for":["高端品牌","优雅标题","时尚展示"],"verified":False,"notes":"Raleway，纤细优雅。"},
]

print(f"[OK] 精选字体库: {len(FONT_LIBRARY)} 款")

# ============================================================
# 生成 JSON 数据库
# ============================================================
def build_database():
    db = {
        "metadata": {
            "version": "1.0",
            "created": str(date.today()),
            "ground_truth_source": "temp/textfx_showcase_build.jsx",
            "ground_truth_video": "D:/AE-Work/output/TextFX_Showcase.mp4",
            "architecture": "three_independent_dimensions",
            "stats": {
                "effect_combos": len(EFFECT_COMBOS),
                "entrance_animations": len(ENTRANCE_ANIMATIONS),
                "font_library": len(FONT_LIBRARY),
                "total_entries": len(EFFECT_COMBOS) + len(ENTRANCE_ANIMATIONS) + len(FONT_LIBRARY)
            }
        },
        "effect_combos": EFFECT_COMBOS,
        "entrance_animations": ENTRANCE_ANIMATIONS,
        "font_library": FONT_LIBRARY
    }
    return db

def validate_database(db):
    errors = []
    # 检查 effect_combos
    ids_seen = set()
    for ec in db["effect_combos"]:
        if ec["id"] in ids_seen: errors.append(f"Duplicate effect id: {ec['id']}")
        ids_seen.add(ec["id"])
        for key in ["id","name","effects","visual_style","best_for","quality_rating"]:
            if key not in ec: errors.append(f"Missing {key} in {ec.get('id','?')}")
    # 检查 entrance_animations
    for ea in db["entrance_animations"]:
        if ea["id"] in ids_seen: errors.append(f"Duplicate anim id: {ea['id']}")
        ids_seen.add(ea["id"])
        for key in ["id","name","keyframes","duration_sec","best_for","difficulty"]:
            if key not in ea: errors.append(f"Missing {key} in {ea.get('id','?')}")
    # 检查 font_library
    for fl in db["font_library"]:
        if fl["id"] in ids_seen: errors.append(f"Duplicate font id: {fl['id']}")
        ids_seen.add(fl["id"])
        for key in ["id","postscript_name","category","style_keywords","best_for"]:
            if key not in fl: errors.append(f"Missing {key} in {fl.get('id','?')}")
    return errors

def print_stats(db):
    s = db["metadata"]["stats"]
    print(f"\n{'='*60}")
    print(f"文字特效预设数据库 v{db['metadata']['version']}")
    print(f"{'='*60}")
    print(f"  特效组合: {s['effect_combos']} 套")
    print(f"  入场动画: {s['entrance_animations']} 种")
    print(f"  精选字体: {s['font_library']} 款")
    print(f"  总条目数: {s['total_entries']} 条")
    print(f"  架构模式: {db['metadata']['architecture']}")
    # 特效风格分布
    styles = {}
    for ec in db["effect_combos"]:
        st = ec.get("visual_style","未分类")
        styles[st] = styles.get(st, 0) + 1
    print(f"\n  特效风格分布:")
    for st, cnt in sorted(styles.items(), key=lambda x: -x[1]):
        print(f"    {st}: {cnt}")
    # 字体类别分布
    cats = {}
    for fl in db["font_library"]:
        c = fl.get("category","未分类")
        cats[c] = cats.get(c, 0) + 1
    print(f"\n  字体类别分布:")
    for c, cnt in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"    {c}: {cnt}")
    # 评分分布
    ratings = {}
    for ec in db["effect_combos"]:
        r = ec.get("quality_rating", 0)
        ratings[r] = ratings.get(r, 0) + 1
    print(f"\n  特效评分分布:")
    for r in sorted(ratings.keys(), reverse=True):
        print(f"    {'★'*r}: {ratings[r]}套")
    # 基准验证
    verified_effects = sum(1 for ec in db["effect_combos"] if ec.get("verified"))
    verified_fonts = sum(1 for fl in db["font_library"] if fl.get("verified"))
    print(f"\n  基准验证: {verified_effects}套特效 + {verified_fonts}款字体")
    print(f"{'='*60}")

if __name__ == "__main__":
    db = build_database()
    errors = validate_database(db)
    if errors:
        print(f"\n[ERROR] 验证失败:")
        for e in errors: print(f"  - {e}")
    else:
        print("[OK] 数据库验证通过")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, "text_presets_database.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)
    print(f"[OK] 已保存: {out_path}")
    print_stats(db)
