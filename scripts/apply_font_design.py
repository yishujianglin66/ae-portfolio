#!/usr/bin/env python3
"""方向2: 字体×效果组合设计 + 更新预设配置
基于外网MAD/AMV/漫剪调研 + 本机38个AE可用字体
"""
import json
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "text_animation_presets.json"

# ============================================================
# 字体×效果组合策略 (基于MAD/AMV/漫剪调研)
# ============================================================
# 调研结论:
# - 日系MAD: 毛笔书法体(STXingkai) + 速度线/集中线 → 热血/战斗
# - 欧美AMV: Impact/粗黑无衬线 + 故障/RGB分离 → 力量/冲击
# - 国漫混剪: STKaiti/STXinwei + 水墨/粒子 → 古风/意境
# - 赛博朋克: 等宽/工业字体 + 扫描线/数据流 → 科技/未来
# - 电影标题: 衬线/百老汇 + 光晕/渐变 → 史诗/高级
# - 社交媒体: 圆润字体 + 弹跳/彩虹 → 活力/可爱
# - 艺术字: 书法/手写 + 水墨/霓虹 → 艺术/文化

FONT_STRATEGY = {
    # 动态排版 - 力量感+现代感 (AMV风格: Impact + kinetic motion)
    "kinetic_typography": {
        "fonts": ["Impact", "DINNextLTPro-Bold", "Bahnschrift", "SimHei", "NotoSansSC-VF"],
        "primary": "Impact",
        "rationale": "AMV/MAD标准: Impact粗黑+动态运动=最大冲击力",
        "style": "power_modern"
    },
    # 赛博朋克 - 科技感 (等宽+工业: 终端/数据流美学)
    "cyberpunk": {
        "fonts": ["Consolas", "DINNextLTPro-Bold", "Bahnschrift", "SimHei", "NotoSansSC-VF"],
        "primary": "Consolas",
        "rationale": "等宽字体=终端美学, DIN=工业精密感",
        "style": "tech_monospace"
    },
    # 电影级 - 史诗衬线 (Netflix/预告片风格)
    "cinematic": {
        "fonts": ["BodoniMT", "NiagaraEngraved", "NotoSerifSC-VF", "STXinwei", "Broadway"],
        "primary": "BodoniMT",
        "rationale": "高对比衬线=电影海报标准, 华文新魏=中文史诗感",
        "style": "epic_serif"
    },
    # 社交媒体 - 圆润活力 (抖音/快手风格)
    "social_media": {
        "fonts": ["YouYuan", "CooperBlack", "CurlzMT", "SnapITC", "YouYuan"],
        "primary": "YouYuan",
        "rationale": "幼圆/Cooper=圆润亲切, 适合快节奏短视频",
        "style": "rounded_playful"
    },
    # 3D标题 - 几何厚重 (需要3D extrusion厚度感)
    "3d_title": {
        "fonts": ["Impact", "CooperBlack", "DINNextLTPro-Bold", "SimHei", "Bahnschrift"],
        "primary": "Impact",
        "rationale": "粗厚字体在3D挤出时体积感最强",
        "style": "bold_geometric"
    },
    # 高级动态文字 - 工业/实验 (液态金属/粒子/维度)
    "advanced_kinetic": {
        "fonts": ["Stencil", "Playbill", "Impact", "Bahnschrift", "DINNextLTPro-Bold"],
        "primary": "Stencil",
        "rationale": "Stencil工业模板感+液态金属=硬核美学",
        "style": "industrial_experimental"
    },
    # 动漫特效 - 日系热血 (MAD标准: 游ゴシック+书法)
    "anime_fx": {
        "fonts": ["YuGothic-Bold", "STXingkai", "STHupo", "SimHei", "Impact"],
        "primary": "YuGothic-Bold",
        "rationale": "日系MAD标准: 游ゴシック粗体+速度线=热血冲击",
        "style": "japanese_impact"
    },
    # VFX特效 - 神秘/能量 (魔法/粒子/能量波)
    "vfx_presets": {
        "fonts": ["Chiller", "NiagaraEngraved", "RageItalic", "STCaiyun", "BodoniMT"],
        "primary": "Chiller",
        "rationale": "Chiller神秘感+能量特效=魔幻VFX标准搭配",
        "style": "mystical_energy"
    },
    # 3D标题扩展 - 材质表现 (玻璃/熔岩/全息)
    "3d_title_extended": {
        "fonts": ["BodoniMT", "CooperBlack", "Bahnschrift", "DINNextLTPro-Bold", "NotoSerifSC-VF"],
        "primary": "BodoniMT",
        "rationale": "高对比衬线在材质贴图(玻璃折射/熔岩)下细节最丰富",
        "style": "material_showcase"
    },
    # 电影标题 - 优雅/叙事 (Netflix开场/片尾/章节)
    "cinema_titles": {
        "fonts": ["PalaceScriptMT", "BodoniMT", "NotoSerifSC-VF", "Broadway", "VladimirScript"],
        "primary": "PalaceScriptMT",
        "rationale": "优雅手写体+衬线=电影片头标准, 华文宋=中文电影感",
        "style": "elegant_narrative"
    },
    # 艺术字 - 书法/手写 (水墨/霓虹/铸造)
    "art_typography": {
        "fonts": ["STXingkai", "STKaiti", "BrushScriptMT", "FZShuTi", "STHupo"],
        "primary": "STXingkai",
        "rationale": "行楷+水墨=国风艺术字黄金搭配, Brush Script=霓虹手写",
        "style": "calligraphy_art"
    }
}

# 每个预设的字体分配规则:
# - 主字体(primary): 用于该分类大部分预设
# - 变体字体(fonts列表): 按预设索引轮转, 增加视觉多样性
def assign_font(category, preset_index, preset_id):
    """为单个预设分配字体"""
    strategy = FONT_STRATEGY.get(category)
    if not strategy:
        return "Impact"
    fonts = strategy["fonts"]
    # 特殊预设使用特殊字体
    special_map = {
        "at_ink_wash": "STXingkai",      # 水墨 → 行楷
        "at_neon_tube": "BrushScriptMT",  # 霓虹 → 手写
        "at_metal_cast": "STHupo",        # 金属铸造 → 琥珀体(厚重)
        "ct_netflix_opening": "BodoniMT", # Netflix → 衬线
        "ct_credits_roll": "NotoSerifSC-VF", # 片尾 → 宋体
        "ct_chapter_transition": "PalaceScriptMT", # 章节 → 花体
        "af_speed_impact": "YuGothic-Bold",  # 速度线 → 游ゴシック
        "af_focus_lines": "STXingkai",       # 集中线 → 行楷(日系书法)
        "af_manga_panel": "STHupo",          # 漫画分格 → 琥珀(粗)
        "ak_liquid_metal": "Stencil",        # 液态金属 → 工业模板
        "ak_particle_scatter": "Impact",     # 粒子爆散 → 力量
        "ak_dimension_fold": "Bahnschrift",  # 维度折叠 → 几何
        "cp_rgb_split": "Consolas",          # RGB分离 → 等宽
        "cp_data_corrupt": "Consolas",       # 数据损坏 → 等宽
        "cp_neon_pulse": "DINNextLTPro-Bold",# 霓虹脉冲 → 工业
        "cp_matrix_rain": "Consolas",        # 矩阵雨 → 等宽
        "cp_terminal_type": "Consolas",      # 终端打字 → 等宽
        "ci_epic_opener": "BodoniMT",        # 史诗开场 → 衬线
        "ci_burning_text": "STXinwei",       # 燃烧文字 → 新魏(刚劲)
        "ci_frost_freeze": "NotoSerifSC-VF", # 冰冻 → 宋体(冷峻)
        "sm_douyin_bounce": "YouYuan",       # 抖音弹跳 → 幼圆
        "sm_danmaku_scroll": "SimHei",       # 弹幕 → 黑体
        "sm_emoji_text": "CurlzMT",          # 表情 → 花体
        "td_metallic_depth": "Impact",       # 金属深度 → 力量
        "td_glass_refract": "BodoniMT",      # 玻璃折射 → 衬线
        "td_lava_flow": "STHupo",            # 熔岩 → 琥珀(厚重)
        "td_hologram_flicker": "Consolas",   # 全息 → 等宽
        "vfx_energy_wave": "RageItalic",     # 能量波 → 狂野
        "vfx_magic_circle": "Chiller",       # 魔法阵 → 神秘
        "vfx_particle_explosion": "Impact",  # 粒子爆炸 → 力量
    }
    if preset_id in special_map:
        return special_map[preset_id]
    # 默认: 按索引轮转
    return fonts[preset_index % len(fonts)]


def update_presets():
    """更新配置文件中所有预设的字体参数"""
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    
    updated = 0
    font_usage = {}
    
    for cat_key, cat_data in cfg["categories"].items():
        presets = cat_data.get("presets", [])
        for idx, p in enumerate(presets):
            new_font = assign_font(cat_key, idx, p["id"])
            
            # 更新parameters中的fontFamily默认值
            params = p.get("parameters", [])
            font_param_found = False
            for param in params:
                if param["name"] == "fontFamily":
                    old_font = param.get("default", "")
                    param["default"] = new_font
                    font_param_found = True
                    if old_font != new_font:
                        updated += 1
                    break
            
            if not font_param_found:
                # 没有fontFamily参数的预设,添加一个
                params.append({
                    "name": "fontFamily",
                    "type": "string",
                    "default": new_font,
                    "description": "Font family"
                })
                p["parameters"] = params
                updated += 1
            
            # 同时更新jsx_template中的字体引用
            tpl = p.get("jsx_template", "")
            if tpl and "font=" in tpl:
                # 替换 _tv.font='xxx' 或类似模式
                tpl = re.sub(
                    r"(_tv\.font\s*=\s*')[^']*(')",
                    f"\\g<1>{new_font}\\2",
                    tpl
                )
                # 替换 gtv.font='xxx' (ghost layer)
                tpl = re.sub(
                    r"(gtv\.font\s*=\s*')[^']*(')",
                    f"\\g<1>{new_font}\\2",
                    tpl
                )
                p["jsx_template"] = tpl
            
            # 统计
            font_usage[new_font] = font_usage.get(new_font, 0) + 1
    
    # 更新版本标记
    cfg["version"] = "5.0-font-design"
    cfg["font_strategy"] = {
        "description": "Professional font x effect combination system",
        "based_on": "MAD/AMV/manga-edit research + 38 AE-verified fonts",
        "categories": {k: {"primary": v["primary"], "style": v["style"], "rationale": v["rationale"]} 
                      for k, v in FONT_STRATEGY.items()}
    }
    
    # 保存
    CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    
    print(f"\n{'='*60}")
    print("  FONT DESIGN SYSTEM APPLIED")
    print(f"{'='*60}")
    print(f"  Presets updated: {updated}/109")
    print("  Version: 5.0-font-design")
    print("\n  Font usage distribution:")
    for font, count in sorted(font_usage.items(), key=lambda x: -x[1]):
        print(f"    {font:<30} {count} presets")
    
    print("\n  Category → Primary font:")
    for cat, strategy in FONT_STRATEGY.items():
        print(f"    {cat:<25} → {strategy['primary']} ({strategy['style']})")


if __name__ == "__main__":
    update_presets()
