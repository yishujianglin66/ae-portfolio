# -*- coding: utf-8 -*-
"""文字-剪辑集成调度器 P0 (2026-09-08) — 八大方向方案 §7.1 / 交接文档 §四

定位: 文字不是静态叠加, 而是锚定镜头节拍/情绪的动态元素 (解锁 G1)。
本脚本 = 事件表规划器 + JSX 生成器, 本身不直接操作 AE:
  --dry-run  只出事件表 + JSX 不碰 AE (离线验证, 默认推荐先行)
  (无 --dry-run)  写 JSX 落盘 → 调 .ae-mcp-bridge/send_bridge.py 文件协议注入

数据输入 (缺一降级, 全缺报错):
  output/<run_dir>/production_report.json  → pr["script"]["segments"]
      (字段: start_time/end_time/mood/energy/speed; 注意顶层 segments 无 start_time, 别用错)
  tmp/true_onsets.json    [{t, s}] 真实 kick; 缺失回退 tmp/music_envelope.json strong 列表
  tmp/music_envelope.json {env, env_times, strong} RMS 包络 (能量→字号/发光缩放)
  tmp/shot_scenes_raw.json {t0: {motion, edge, skin, bright}} 肤色代理 (closeup 避让);
      缺失 → 关避障, 全部走默认位置

事件模型 (契约, P1-P3 消费):
  {t_in, t_out, hold, mood, energy, style_id, word, font, font_stack,
   probe_font, x, y, size, closeup, enter, fades, glow, tracking}

语义规则 (方案 §7.1):
  intro/outro → intro_serif 衬线居中低饱和 (衬线字体未实证 → 探针清单, 回退 BebasNeue)
  build       → build_side 无衬线侧置 (BebasNeue 已实证)
  drop        → drop_impact impact 字体居中+描边 (Anton/Impact 已实证)
  closeup (skin≥0.30 且 motion≤p70) → 避让主体框, 置上下安全带 (y=0.18h/0.82h), 字号×0.8

实证边界 (A1, 违反=翻车):
  - JSX 仅用已实证 API: addText + ADBE Text Document(font/fontSize/fillColor/applyFill/
    applyStroke/justification) / 图层 opacity(0-100) / ADBE Text Tracking Amount /
    ADBE Glo2(0002/0003/0004) / easeOutBack 位置表达式 / Scale 关键帧
  - Text Document 的 strokeColor/strokeWidth 见交接 §四已实证属性名, JSX 内 try/catch 保护
  - ES3 语法; aerender -s/-e 是帧号 (执行模式渲染时秒×24)
  - 字体实证清单 (v6, 2026-09-11 probe_font_pool.jsx 26 字体全 =YES): 见 VERIFIED_FONTS;
    字形覆盖约束: JP 词 (強発壊無縛臨韻) 只配 JP 字体, CN 池可混 JP 字体 (JIS1-2 覆盖简体常用字)

用法 (位置参数契约同 build_master_polish, 2026-09-05 公布, 不可变更):
  python scripts/build_text_overlay.py <run_dir> <tag> [--dry-run]
      [--words-json X] [--hold-mode phrase|shot] [--max-events N]
示例:
  python scripts/build_text_overlay.py unified_run53 run53 --dry-run
"""
import argparse
import json
import os
import random
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FPS = 24.0
FRAME = 1.0 / FPS          # 0.0417s
ONSET_TOL = 2 * FRAME      # 节拍门: ≤2 帧

# 乐段分区 (与 build_master_polish v23 分段调色 / plan_bursts 同口径)
ZONES = [
    ("intro", 0.0, 3.3),
    ("build", 3.3, 12.7),
    ("drop", 12.7, 27.0),
    ("outro", 27.0, 1e9),
]
ZONE_CFG = {
    #            最小间距  最大保持  事件上限
    "intro": {"gap": 1.2, "hold": 2.5, "cap": 2},
    "build": {"gap": 0.85, "hold": 2.2, "cap": 6},
    "drop":  {"gap": 0.60, "hold": 0.95, "cap": 12},
    "outro": {"gap": 1.2, "hold": 2.5, "cap": 2},
}
ZONE_END_GUARD = 0.35     # 锚点距分区结束 <0.35s 不选 (会被钳成不可读短事件)
DROP_POS_CYCLE = [(960, 540), (700, 380), (1220, 700)]   # v9: 内收 (v8 实证 620/1300 宽字超框)
ONSET_S_THR = 0.40         # 归一化强度阈值 (D4 口径 s≥0.5 收紧到 0.4 保覆盖)

# 字体: font_stack[0] 为首选 (probe_font=true 表示未实机实证, 探针不过则用栈尾已实证字体)
# v2 样式 (2026-09-10 Boss 反馈"效果太普通"后升级, 配方①描边投影+④双层发光+⑦轻斜面):
#   glow/glow2 = (threshold 0-255, radius, intensity) —— 实证序号: 0002=阈值(0-255!), 0003=半径, 0004=强度
#   shadow = (opacity 0-1, direction deg, distance, softness) —— ADBE Drop Shadow 0002/3/4/5
#   bevel  = (edge_thickness, light_angle, light_intensity) —— ADBE Bevel Alpha 0001/2/4
STYLES = {
    "build_side": {
        "size": (98, 134), "fill": [0.95, 0.95, 0.98],
        "stroke": ([0.03, 0.03, 0.06], 2.2), "pos": "side_alt", "enter": "slide_back",
        # W2 入场变款循环: 滑入 / 上升揭示 / 横向揭示 (Linear Wipe, 层级效果 → 字体安全)
        "enter_cycle": ["slide_back", "wipe_up", "slide_back", "wipe_right"],
        "glow": (130, 18, 0.9), "glow2": None,
        "shadow": (0.6, 135, 6, 8), "bevel": (2, -45, 0.35),
        "tracking": None,
        # v7 禁用 RS 动画器 (typewriter/cascade): 实证动画范围选择器切换逐字光栅化路径时
        # 脚本设置的字体被静默替换为默认字体 (v6.1 二分: punch/elastic/无动画层字体全部正常)
        "typewriter": False,
    },
    "intro_serif": {
        "size": (100, 125), "fill": [0.96, 0.94, 0.89],
        "stroke": ([0.05, 0.04, 0.06], 1.8), "pos": "center", "enter": "fade_scale",
        # W2 入场变款循环 (开场/收尾): 缩放淡入 / 上升揭示 / 模糊淡入 / 横向揭示
        "enter_cycle": ["fade_scale", "wipe_up", "blurfade", "wipe_right"],
        "glow": (150, 30, 0.55), "glow2": None,
        "shadow": (0.45, 135, 5, 15), "bevel": None,
        "tracking": None,
        "blurfade": True,     # v3: 模糊淡入（手册 §十七, ADBE Gaussian Blur 2 prop1: 60→0）
    },
    "drop_impact": {
        "size": (150, 196), "fill": [1.0, 1.0, 1.0],
        "stroke": ([0.02, 0.02, 0.05], 5.0), "pos": "center",
        "enter": "punch_tracking",
        # v8: 去 Bloom 第二发光 (Boss"特效重复添加"观感 = 双发光叠加); 主发光大幅收紧防全帧提亮
        "glow": (115, 25, 1.7), "glow2": None,
        "shadow": (0.78, 135, 10, 12), "bevel": (3, -45, 0.55),
        "tracking": 110,   # v9: 250→110 (v8 实证 punch 展开期 5 字母超框被切)
        "cascade": False,   # v7 禁用: RS 动画器与脚本字体互斥 (见 build_side 注)
        "elastic": True,    # 弹性缩放砸入: amp*sin/exp 衰减表达式（层变换, 字体安全）
        "shockwave": False, # v4 关闭: 合成级白固态闪光（视频被影响的感知来源）
    },
}
MOOD_TO_STYLE = {"intro": "intro_serif", "build": "build_side",
                 "drop": "drop_impact", "outro": "intro_serif"}

# v27 W4 情绪档案 (mood profile): 同一份音乐可演绎成不同风格, 由 CLI 切换
# chroma=通道分离 / wipe=遮罩揭示 / drift_mul=漂移幅度倍率 / glow_mul=发光倍率 / pulse_mul=节拍脉冲倍率
MOOD_PROFILES = {
    "auto":    None,                                                  # 保持既有行为
    "impact":  {"chroma": True,  "wipe": True,  "drift_mul": 1.2, "glow_mul": 1.15, "pulse_mul": 1.15},
    "elegant": {"chroma": False, "wipe": True,  "drift_mul": 0.7, "glow_mul": 0.85, "pulse_mul": 0.75},
    "kinetic": {"chroma": True,  "wipe": False, "drift_mul": 1.5, "glow_mul": 1.05, "pulse_mul": 1.35},
}

# ── v18 字体池 (2026-09-11 重建: HKLM 真相表 + fontTools cmap 字形覆盖双校验) ──
# 铁律: ① AE 只解析 HKLM 系统字体 (用户目录字体不可见) ② 必须校验 cmap 覆盖——
#   日文词 (強発壊無縛臨韻) 只有部分字体覆盖 (实测 琥珀/彩云/新魏/行楷/粗黑宋 = 9/17 不覆盖!),
#   故 jp 池只收 17/17 全覆字体 (LiSu/DengXian-Bold/YuGothic系/MS-Gothic系/STSong系/STXihei),
#   cn 池才能用装饰性字体 (琥珀/彩云/新魏/彩色系). 覆盖表见 tmp/check_glyph_coverage.py
FONT_POOLS = {
    "drop_impact": {   # 冲击词: v24 厚重字体回归池首 (细/装饰体后置, 避免整体观感变轻变平)
        "jp":    ["YuGothic-Bold", "MS-PGothic", "DengXian-Bold", "LiSu"],
        "cn":    ["FZCCHFW--GB1-0", "HYa0gj", "FZHPFW--GB1-0", "FZCHSJW--GB1-0", "STHupo", "STCaiyun"],
        "latin": ["Anton-Regular", "BlackOpsOne-Regular", "AlfaSlabOne-Regular",
                  "GillSans-UltraBoldCondensed", "CooperBlack", "Bangers-Regular",
                  "MetalMania-Regular", "Blanka-Regular", "321impact",
                  "BebasKai", "Brat", "BroadcastMatter", "FasterOne-Regular"],
    },
    "build_side": {    # 铺垫词 (4-11s 段): v25 换成有个性的字体 (原 等线/平黑/Lato 被 Boss 判不达标)
        "jp":    ["LiSu", "DengXian-Bold", "YuGothic-Bold", "STZhongsong"],
        "cn":    ["FZHPFW--GB1-0", "FZSTFW--GB1-0", "STHupo", "FZKTFW--GB1-0"],
        "latin": ["HansonBold", "BrandonGrotesque-Black", "Kanit-Black", "321impact",
                  "BebasNeue-Bold", "Inter-Black"],
    },
    "intro_serif": {   # 开场/收尾: 厚重衬线优先, 细花体后置
        "jp":    ["STZhongsong", "STFangsong", "YuGothic-Light"],
        "cn":    ["FZSSFW--GB1-0", "FZKTFW--GB1-0", "STXingkai", "STLiti", "STKaiti"],
        "latin": ["AlfaSlabOne-Regular", "BowlbyOneSC-Regular", "BodoniMTBlack",
                  "CopperplateGothic-Bold", "AutourOne-Regular", "Asset-Regular",
                  "DrSugiyama-Regular", "GreatVibes-Regular", "Allura-Regular"],
    },
}
VERIFIED_FONTS = {          # HKLM 真相表 + cmap 覆盖 + 渲染差分三重校验 (2026-09-11/12)
    # 系统级安装批次一 (tmp/install_fonts_full.py, 28 个; 不含 trial)
    "Anton-Regular", "BebasNeue-Bold", "Antonio-Bold", "BlackOpsOne-Regular",
    "Bangers-Regular", "AlfaSlabOne-Regular", "BowlbyOneSC-Regular", "Blanka-Regular",
    "BungeeShade-Regular", "HansonBold", "Kanit-Black", "Kanit-ExtraBold",
    "Bumrush", "321impact", "ArtBrush",
    "FZWBFW--GB1-0", "FZCCHFW--GB1-0", "FZH4FW--GB1-0", "FZHPFW--GB1-0",
    "FZHTFW--GB1-0", "FZPHFW--GB1-0", "FZSSFW--GB1-0", "FZKTFW--GB1-0",
    "FZSTFW--GB1-0", "HYa0gj", "GBWeiBei-Bold", "SungtiEG-Ultra-GB",
    # L1 白名单批次 (scripts/install_fonts_l1.py, 84 个)
    "BebasKai", "Brat", "BroadcastMatter", "FasterOne-Regular", "MetalMania-Regular",
    "Creepster-Regular", "GreatVibes-Regular", "Allura-Regular", "DrSugiyama-Regular",
    "Chewy-Regular", "LuckiestGuy-Regular", "Asset-Regular", "AutourOne-Regular",
    "Lato-Black", "Inter-Black", "BrandonGrotesque-Black", "AlegreyaSansSC-Black",
    "Kanit-Thin", "Merriweather-Black", "Eater-Regular", "LondrinaShadow-Regular",
    "LondrinaOutline-Regular", "FascinateInline-Regular", "Codystar-Light",
    "Galada-Regular", "Charmonman-Bold", "Elianto-Regular", "Hundo", "Aspire-DemiBold",
    "Barriecito-Regular", "Flavors-Regular", "HennyPenny-Regular", "FingerPaint-Regular",
    "BadScript-Regular", "HerrVonMuellerhoff-Regular",
    # 既有系统字体
    "LiSu", "DengXian-Bold", "YuGothic-Bold", "YuGothic-Medium", "YuGothic-Regular",
    "YuGothic-Light", "MS-PGothic", "MS-Gothic", "STHupo", "FZCHSJW--GB1-0",
    "STCaiyun", "STXinwei", "STKaiti", "STXingkai", "STLiti", "STZhongsong",
    "STSong", "STFangsong", "STXihei", "SimSun", "SimHei", "KaiTi", "YouYuan",
    "AlibabaPuHuiTi_3_45_Light", "MicrosoftYaHei-Bold",
    "Impact", "Haettenschweiler", "Arial-Black", "GillSans-UltraBoldCondensed",
    "CooperBlack", "BodoniMTBlack", "FranklinGothic-Heavy", "FranklinGothic-DemiCond",
    "SegoeUIBlack", "ShowcardGothic-Reg", "Stencil", "Rockwell-ExtraBold",
    "CopperplateGothic-Bold", "CenturyGothic-Bold", "AgencyFB-Bold",
    "BernardMT-Condensed", "TwCenMT-CondensedBold", "TrebuchetMS-Bold",
    "Georgia", "Rockwell", "GloucesterMT-ExtraCondensed", "BerlinSansFB-Bold",
}
JP_ONLY_CHARS = set("強発壊無縛臨韻")      # 词库内 JP 专字形 (JP 字体优先保字形正确)


def script_class(word):
    """jp=含 JP 专字形; cn=仅通用汉字; latin=ASCII"""
    if any(ch in JP_ONLY_CHARS for ch in word):
        return "jp"
    if any("\u4e00" <= ch <= "\u9fff" for ch in word):
        return "cn"
    return "latin"


# v28 字体-文字系兼容白名单 (依据 tmp/check_glyph_coverage.py 实测 cmap 结果)
JP_SAFE_FONTS = {          # 日文词全覆盖 (17/17)
    "LiSu", "DengXian-Bold", "YuGothic-Bold", "YuGothic-Medium", "YuGothic-Regular",
    "YuGothic-Light", "MS-PGothic", "MS-Gothic", "STSong", "STZhongsong", "STFangsong",
    "STXihei", "SimSun", "SimHei", "KaiTi", "STKaiti", "YouYuan", "AlibabaPuHuiTi_3_45_Light",
}
CN_SAFE_FONTS = JP_SAFE_FONTS | {   # 中文词额外可用 (中文 11/11, 日文不足)
    "STHupo", "STCaiyun", "STXinwei", "STXingkai", "STLiti", "MicrosoftYaHei-Bold",
    "FZCHSJW--GB1-0", "FZCCHFW--GB1-0", "FZH4FW--GB1-0", "FZHPFW--GB1-0", "FZHTFW--GB1-0",
    "FZPHFW--GB1-0", "FZSSFW--GB1-0", "FZKTFW--GB1-0", "FZSTFW--GB1-0", "FZWBFW--GB1-0",
    "HYa0gj", "GBWeiBei-Bold", "SungtiEG-Ultra-GB",
}


def font_allowed_for_script(font, scl):
    """latin 词: 任意已实证字体; cn 词: 中文白名单; jp 词: 仅日文全覆白名单"""
    if scl == "latin":
        return True
    if scl == "cn":
        return font in CN_SAFE_FONTS
    return font in JP_SAFE_FONTS

# 默认词库 (报告无歌词素材 → 按源 IP 咒术回战/五条悟 的 AMV 惯用词)
# v25: 词库外置 —— 若 data/text_overlay_words.json 存在则覆盖 (改文字无需改代码)
DEFAULT_WORDS = {
    "intro": ["五条悟", "THE STRONGEST"],
    "build": ["無限", "束縛", "加速", "VIOLATION", "迂回", "LIMIT",
              "静止", "臨界", "REVERSE"],
    "drop":  ["最強", "BREAK", "爆発", "無下限", "ZERO", "IMPACT",
              "崩壊", "RED", "虚式"],
    "outro": ["THE END", "余韻"],
}
WORDS_FILE = "data/text_overlay_words.json"
TIMELINE_FILE = "data/text_overlay_timeline.json"   # v28: 时间→文字(可带字体) 对应表
TIMELINE_TOL = 0.6                                  # 事件锚点与该时刻相差 ≤ 此值即命中 (秒)


def load_timeline():
    """时间-文字对应表: [{t, word, font?}] —— 存在则优先于分区词库的循环分配"""
    p = ROOT / TIMELINE_FILE
    if not p.exists():
        return []
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] 时间表解析失败, 忽略: {e}")
        return []
    items = raw if isinstance(raw, list) else raw.get("timeline", [])
    out = []
    for it in items:
        if isinstance(it, dict) and "t" in it and it.get("word"):
            try:
                out.append({"t": float(it["t"]), "word": str(it["word"]),
                            "font": it.get("font") or None,
                            "note": it.get("note") or ""})
            except (TypeError, ValueError):
                print(f"[WARN] 时间表条目非法, 跳过: {it}")
    out.sort(key=lambda x: x["t"])
    return out


def load_words(override: dict | None = None) -> dict:
    """词库优先级: --words-json > data/text_overlay_words.json > DEFAULT_WORDS"""
    words = {k: list(v) for k, v in DEFAULT_WORDS.items()}
    p = ROOT / WORDS_FILE
    if p.exists():
        try:
            ext = json.loads(p.read_text(encoding="utf-8"))
            for k, v in ext.items():
                if isinstance(v, list) and v:
                    words[k] = list(v)
        except Exception as e:
            print(f"[WARN] 词库文件解析失败, 用默认: {e}")
    if override:
        for k, v in override.items():
            if isinstance(v, list) and v:
                words[k] = list(v)
    return words

COMP_NAME = "run53_premium_v3"     # 验收基线合成 (交接 §一)
AEP_NAME = "run53_premium_v3.aep"


# ── 数据加载 (缺省降级, 与 build_master_polish 同源逻辑) ────────────────
def load_segments(run_dir: Path):
    pr = json.loads((run_dir / "production_report.json").read_text(encoding="utf-8"))
    return pr["script"]["segments"]


def load_onsets():
    """true_onsets 缺失回退 strong 列表 (交接 §八.3)"""
    p = ROOT / "tmp" / "true_onsets.json"
    if p.exists():
        return [(float(d["t"]), float(d["s"])) for d in json.loads(p.read_text(encoding="utf-8"))]
    d = json.loads((ROOT / "tmp" / "music_envelope.json").read_text(encoding="utf-8"))
    return [(float(t), 1.0) for t in d["strong"]]


def load_envelope_at():
    p = ROOT / "tmp" / "music_envelope.json"
    if not p.exists():
        return lambda t: 0.5
    d = json.loads(p.read_text(encoding="utf-8"))
    times, env = d["env_times"], d["env"]

    def at(t):
        i = min(range(len(times)), key=lambda k: abs(times[k] - t))
        return float(env[i])
    return at


def load_scenes():
    """{t0(str, 3位小数): {motion, skin, ...}}; 缺失返回空 dict → 关避障"""
    p = ROOT / "tmp" / "shot_scenes_raw.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


def zone_of(t):
    for name, lo, hi in ZONES:
        if lo <= t < hi:
            return name
    return "outro"


# ── 事件规划 ────────────────────────────────────────────────────────────
def plan_events(segs, onsets, env_at, scenes, words, hold_mode="phrase",
                max_events=None, total_dur=None, bg_video=None,
                profile=None, entropy=0.65, speed=1.0, seed=20260912, mood_name="auto",
                timeline=None, tl_tol=TIMELINE_TOL):
    """产出事件表 + 逐 segment 处置表 (显式记账, 不静默丢)"""
    if total_dur is None:
        total_dur = float(segs[-1]["end_time"]) if segs else 0.0
    smax = max(s for _, s in onsets) if onsets else 1.0
    smax = smax if smax > 0 else 1.0
    seg_bounds = [(float(s["start_time"]), float(s["end_time"])) for s in segs]

    # 1) 按强度贪心选锚点 (强优先, 间距护栏, 分区 cap)
    picked = []          # [(t, s_norm, zone)]
    for zone, _lo, _hi in ZONES:
        cfg = ZONE_CFG[zone]
        cands = sorted(((t, s / smax) for t, s in onsets
                        if zone_of(t) == zone and s / smax >= ONSET_S_THR),
                       key=lambda x: -x[1])
        n_zone = 0
        for t, sn in cands:
            if n_zone >= cfg["cap"]:
                break
            # 间距护栏: 区内用本区 gap; 跨分区只做 0.30s 边界护栏
            # (原实现误用本区 gap 对全区已选事件检查, 会把 outro 开场锚点误杀)
            if any(abs(t - pt) < cfg["gap"] for pt, _sn, pz in picked if pz == zone):
                continue
            if any(abs(t - pt) < 0.30 for pt, _, _ in picked):
                continue
            # 锚点必须落在有效镜头内 (找包含或紧邻镜头)
            if _shot_index(seg_bounds, t) is None:
                continue
            # 分区尾护栏: 太贴近分区界的锚点会被钳成 <0.25s 不可读事件
            z_end = min(z[2] for z in ZONES if z[0] == zone)
            if z_end - t < ZONE_END_GUARD:
                continue
            picked.append((t, sn, zone))
            n_zone += 1
    if max_events:
        picked = sorted(picked, key=lambda x: -x[1])[:int(max_events)]
    picked.sort(key=lambda x: x[0])

    # 2) 逐事件生成 (t_in=onset, t_out 见 hold_mode)
    events = []
    bank_pos = {z: 0 for z in ZONE_CFG}
    env_vals = [env_at(t) for t, _, _ in picked]
    env_max = max(env_vals) if env_vals else 1.0
    side_flip = 0
    font_pos = {}        # v6 池内轮换游标 (按 样式×文字系 独立, 保证每池首字都能轮到)
    last_font = {}
    wf_map = {}          # v18 词→最近一次字体 (同词换字体)
    enter_pos = {}       # W2 入场变款游标 (按样式)
    _rng = random.Random(seed)                 # 非安全用途: 确定性变款控制 (同 seed 同输出, 可复现性要求)
    _prof = profile or {}
    _ent = max(0.0, min(1.0, float(entropy)))
    _sp = 1.0 / max(float(speed), 0.1)          # 时长缩放 (speed 越大入场越快)
    _glow_mul = float(_prof.get("glow_mul", 1.0))
    _drift_mul = float(_prof.get("drift_mul", 1.0))
    _pulse_mul = float(_prof.get("pulse_mul", 1.0))
    _plugins_on = os.environ.get("TEXT_OVERLAY_PLUGINS", "1") not in ("0", "false", "False")
    for i, (t, sn, zone) in enumerate(picked):
        cfg = ZONE_CFG[zone]
        mood = "outro" if zone == "outro" else zone
        style_id = MOOD_TO_STYLE[mood]
        st = STYLES[style_id]
        si = _shot_index(seg_bounds, t)
        seg = segs[si]
        t0, t1 = seg_bounds[si]

        t_in = max(t, t0)                       # onset 贴镜头内即用原值, 越界钳到镜头头
        t_in = round(t_in, 3)
        nxt = picked[i + 1][0] if i + 1 < len(picked) else 1e9
        z_end = min(z[2] for z in ZONES if z[0] == zone)
        if hold_mode == "shot":
            t_out = min(t1 - 2 * FRAME, t_in + cfg["hold"])
        else:  # phrase: 保持到下一切点/分区界/上限 (可读性优先; 交接 §四 契约的工程化放宽)
            t_out = min(t_in + cfg["hold"], nxt - 2 * FRAME, z_end)
        t_out = min(t_out, total_dur)                  # 不越过片长
        t_out = round(max(t_out, t_in + 0.15), 3)      # 最小保持 0.15s (≈4帧)
        hold = round(t_out - t_in, 3)

        # 词 (v28: 时间表优先 → 未命中处回退分区词库循环)
        _tl = list(timeline or [])       # 拷贝! 不可 mutate 调用方列表 (否则主流程对账看不到条目)
        _tl_font_override = None
        _tl_hit = None
        for _k, _item in enumerate(_tl):
            if abs(_item["t"] - t_in) <= tl_tol:
                _tl_hit = _tl.pop(_k)
                break
        if _tl_hit is not None:
            w = _tl_hit["word"]
            _tl_font_override = _tl_hit.get("font")
        else:
            bank = words.get(zone) or words.get(mood) or ["TEXT"]
            w = bank[bank_pos[zone] % len(bank)]
            if len(events) and events[-1]["word"] == w:
                w = bank[(bank_pos[zone] + 1) % len(bank)]
                bank_pos[zone] += 1
            bank_pos[zone] += 1
        _from_tl = _tl_hit is not None

        # v6: 字体按文字系分池轮换 (jp/cn/latin 见 FONT_POOLS), 池内不背靠背重复
        scl = script_class(w)
        pool = FONT_POOLS[style_id][scl]
        fkey = (style_id, scl)
        font = pool[font_pos.get(fkey, 0) % len(pool)]
        _adv = 1 if _rng.random() < _ent else 0
        if _adv == 0 and last_font.get(fkey) == font and len(pool) > 1:
            _adv = 1                              # entropy=0 时也避免背靠背同款
        if last_font.get(fkey) == font and len(pool) > 1:
            font = pool[(font_pos.get(fkey, 0) + 1) % len(pool)]
            font_pos[fkey] = font_pos.get(fkey, 0) + 1
        font_pos[fkey] = font_pos.get(fkey, 0) + _adv
        last_font[fkey] = font
        # v28 时间表字体指定: 需已实证 + 覆盖该词文字系 (覆盖判定基于实测 cmap 结果)
        if _tl_font_override:
            if _tl_font_override not in VERIFIED_FONTS:
                print(f"[WARN] 时间表字体未实证, 忽略: {_tl_font_override} (词 {w})")
            elif not font_allowed_for_script(_tl_font_override, scl):
                print(f"[WARN] 时间表字体 {_tl_font_override} 不覆盖 {scl} 字形, 忽略 (词 {w})")
            else:
                font = _tl_font_override
        # v18: 同一个词再次出现时换字体 (词-字体去重, 防同词同款)
        if wf_map.get(w) == font and len(pool) > 1:
            font = pool[(font_pos.get(fkey, 0)) % len(pool)]
            font_pos[fkey] = font_pos.get(fkey, 0) + 1
        wf_map[w] = font

        # v8: 发光按文字系大幅收紧 — 全片逐帧扫描实证 107/720 帧整帧提亮 (峰值+13),
        # 来源=文字白墨+光晕覆盖画面 20-30% 面积 (Boss"视频被影响/亮度过剩"的量化根因);
        # 收紧目标: 阈值抬高只让最亮核心发光 + 半径砍半 + 去 Bloom 第二发光
        glow, glow2, bevel, pulse = st["glow"], st.get("glow2"), st.get("bevel"), 1.7
        if scl in ("jp", "cn"):
            glow = (185, 14, round(glow[2] * 0.62, 3)) if glow else glow
            glow2 = None
            bevel = (bevel[0], bevel[1], round(bevel[2] * 0.55, 3)) if bevel else bevel
            pulse = 1.28
        elif glow:   # latin
            glow = (158, 16, round(glow[2] * 0.78, 3))
            glow2 = None
            pulse = 1.42

        # 能量 → 字号/发光 (镜头 energy × 包络 归一混合)
        shot_en = float(seg.get("energy", 0.4))
        env_n = (env_at(t_in) / env_max) if env_max > 0 else 0.5
        energy = round(min(1.0, 0.55 * shot_en + 0.45 * env_n), 3)
        sz_lo, sz_hi = st["size"]
        size = int(round(sz_lo + (sz_hi - sz_lo) * energy))

        # 位置 (语义规则 + closeup 避让)
        sc = scenes.get(str(round(t0, 3)))
        closeup = bool(sc and sc.get("skin", 0) >= 0.30
                       and sc.get("motion", 99) <= _skin_p70(scenes))
        x, y = 960, 540
        if st["pos"] == "center":
            if closeup:
                y = int(1080 * (0.18 if side_flip % 2 == 0 else 0.82))
                size = int(size * 0.8)
                side_flip += 1
            elif style_id == "drop_impact":
                # v4.1: 背景亮度感知选位 (双时刻加权, 防白字压高光; 回退轮换)
                x, y = _pick_dark_pos(t_in, bg_video, bank_pos[zone], hold=hold)
        else:  # side_alt
            x = int(1920 * (0.30 if side_flip % 2 == 0 else 0.70))
            y = int(1080 * 0.42)
            side_flip += 1
            if closeup:
                y = int(1080 * (0.18 if side_flip % 2 == 0 else 0.82))

        # W2 三维层 (2026-09-11 探针: 基底4层全2D → 加摄像机不影响基底; 默认 z=-2666.67 为1:1)
        # 仅 drop 区 (能量最高) 转 3D; z 三档轮换做纵深层次; 摄像机方案实测否决 (整帧重合成)
        z_dep = 0
        is3d = (style_id == "drop_impact")
        if is3d:
            z_dep = (0, -140, 140)[bank_pos[zone] % 3]

        # v10 对比度感知样式 (Boss"有些字发光看不出"): 12 drop 事件 9 个落在亮背景
        # (读字期最坏亮度 136-254) → 白字+白辉光融进背景; 且同一位置亮度在保持期内
        # 大幅跳变(如 82→253→74) → 必须按最坏情况定样式, 不能一刀切
        stroke_cfg = st["stroke"]
        shadow_cfg = st.get("shadow")
        glow_col = None            # (A_rgb, B_rgb); None=AE 默认白/黑
        # W1 双描边 (2026-09-11 探针: 图层样式不可脚本启用 → 用双文字层实现"彩色外环+深色内描边")
        dbl, accent, outer_w, inner_w = False, None, 0.0, 0.0
        bg_lum = _worst_region_luma(bg_video, t_in, hold, x, y)
        if bg_lum >= 150:          # 亮底: 白字白辉光物理上看不出 → 青色光晕可见 + 粗描边保读
            bg_class = "bright"
            stroke_cfg = (stroke_cfg[0], 11.0)      # v24: 9→11 加强描边(观感变弱的主因之一)
            shadow_cfg = (0.85, 135, 8, 14)
            glow = (185, 20, round((glow[2] if glow else 1.0) * 1.35, 3)) if glow else glow
            glow_col = ([0.10, 0.80, 1.0], [0.0, 0.15, 0.45])
            pulse = 1.15
            dbl, accent, outer_w, inner_w = False, None, 0.0, 0.0
        elif bg_lum >= 90:         # 中间调: 暖金光晕
            bg_class = "mid"
            stroke_cfg = (stroke_cfg[0], 9.0)       # v24: 7→9
            shadow_cfg = (0.80, 135, 10, 14)
            glow = (175, 18, round((glow[2] if glow else 1.0) * 1.20, 3)) if glow else glow
            glow_col = ([1.0, 0.66, 0.18], [0.30, 0.10, 0.0])
            pulse = 1.25
            dbl, accent, outer_w, inner_w = False, None, 0.0, 0.0
        else:                      # 暗底: 白辉光清晰可见 (保留 v11 已验收单层样式)
            bg_class = "dark"
            stroke_cfg = (stroke_cfg[0], 3.5)
            shadow_cfg = (0.55, 135, 8, 10)
            glow = (150, 18, round((glow[2] if glow else 1.0) * 1.30, 3)) if glow else glow
            pulse = 1.45

        # v17 冲击分级 (镜头运动强度归一化调制) + 通道分离冲击 (高能 drop 词)
        # 依据: v15 的线性 energy 调制对静止镜头也过强; 改用 shot_scenes motion 归一值
        mo_n = 0.5
        if sc is not None:
            mo_n = min(1.0, float(sc.get("motion", 0)) / max(_skin_p70(scenes), 1e-6))
        impact_mul = round(0.82 + 0.36 * mo_n, 3)
        chroma = bool(is3d and energy >= 0.70)   # 仅最强 3 个爆点用通道分离 (防同款连打疲劳)
        chroma_dx = round(12 + 16 * mo_n, 1)

        # v9: drop 变款全整层平移 (RS 动画器与脚本字体互斥; v8 实证旋转变款使文字倾斜超框压高光)
        # _v: 0=drop_fall 自上落下 / 1=rise_up 自下升起 / 2=纯 punch tracking
        # v29 修正: 变款循环改用事件序号 (原用 bank_pos, 但时间表命中时不推进 bank_pos → 相邻同款)
        drop_fall = rise_up = False
        if style_id == "drop_impact":
            _v = i % 3
            drop_fall, rise_up = (_v == 0), (_v == 1)

        # W2 入场变款循环 (wipe_up/wipe_right = Linear Wipe 层级效果 → 字体安全, 已探针实证)
        enter = st["enter"]
        ecyc = st.get("enter_cycle")
        if ecyc and _ent > 0:
            _eadv = 1 if _rng.random() < _ent else 0
            enter = ecyc[enter_pos.get(style_id, 0) % len(ecyc)]
            enter_pos[style_id] = enter_pos.get(style_id, 0) + max(_eadv, 1)
        elif ecyc:
            enter = ecyc[0]                       # entropy=0 → 固定首款 (最稳最一致)
        if _prof.get("wipe") is False and enter in ("wipe_up", "wipe_right"):
            enter = "fade_scale" if style_id == "intro_serif" else "slide_back"

        # v25 音乐联动: 事件窗内节拍脉冲 (供非弹性层做缩放脉冲) + 包络采样 (供发光逐帧呼吸)
        bz = [(round(tt, 3), round(ss / smax, 3)) for tt, ss in onsets if t_in <= tt <= t_out]
        bz.sort(key=lambda x: -x[1])
        beats = bz[:3]                                   # 最多 3 个最强节拍脉冲
        n_s = 7
        env_s = [(round(t_in + hold * k / (n_s - 1), 3),
                  round((env_at(t_in + hold * k / (n_s - 1)) / env_max), 3) if env_max else 0.5)
                 for k in range(n_s)]

        # W3 运动迁移: 镜头运动强度 (shot_scenes.motion) 驱动**保持期缓慢漂移**
        # 负结果记录: 相位相关(置信0.004-0.015)/中值光流(前后景反向运动抵消≈0)/ECC(cc 0.03-0.55)
        # 三种矢量估计在本素材(平均每0.8s切点+粒子+前后景混合运动)均不可信 → 不硬凑矢量,
        # 改为: 方向取确定性循环(8 向, 按事件序号, 防重复疲劳) + 幅度随镜头运动强度(12~30px)
        _DIRS = [(0.71, -0.71), (-0.71, -0.71), (0.71, 0.71), (-0.71, 0.71),
                 (1.0, 0.0), (-1.0, 0.0), (0.0, -1.0), (0.0, 1.0)]
        _dir = _DIRS[i % len(_DIRS)]
        _amp = (12.0 + 18.0 * mo_n) * (1.2 if style_id == "drop_impact" else 1.0) * _drift_mul
        mv_dx = round(_dir[0] * _amp, 1)
        mv_dy = round(_dir[1] * _amp, 1)
        # 安全边距门禁: 估文字半宽/半高, 保证漂移后不出画
        _half_w = 0.30 * size * max(len(w), 1)
        _half_h = 0.75 * size
        mv_dx = max(min(mv_dx, 1740 - _half_w - x), -(_half_w + x - 180))
        mv_dy = max(min(mv_dy, 960 - _half_h - y), -(y - 120 - _half_h))

        # 情绪档案: 发光倍率
        if glow:
            glow = (glow[0], glow[1], round(glow[2] * _glow_mul, 3))
        chroma = bool(chroma and _prof.get("chroma", True))    # elegant 档关闭通道分离

        ev = {
            "id": i, "t_in": t_in, "t_out": t_out, "hold": hold,
            "mood": mood, "energy": energy, "style_id": style_id,
            "word": w, "size": size, "x": x, "y": y, "closeup": closeup,
            "font": font,
            "font_stack": pool,
            "script": scl,
            "probe_font": font not in VERIFIED_FONTS,
            "fill": st["fill"],
            "stroke": stroke_cfg,
            "enter": enter,
            "glow": glow,
            "glow2": glow2,
            "shadow": shadow_cfg,
            "bevel": bevel,
            "glow_pulse": pulse,
            "glow_col_a": glow_col[0] if glow_col else None,
            "glow_col_b": glow_col[1] if glow_col else None,
            "bg_lum": round(bg_lum, 1),
            "bg_class": bg_class,
            "dbl": dbl,
            "accent": accent,
            "outer_w": outer_w,
            "inner_w": inner_w,
            "is3d": is3d,
            "z": z_dep,
            "beats": beats,
            "env_s": env_s,
            "mv_dx": mv_dx,
            "mv_dy": mv_dy,
            "sp": round(_sp, 4),
            "pulse_mul": round(_pulse_mul, 3),
            "mood_profile": mood_name,
            "entropy": round(_ent, 3),
            # v30 冲击配方轮换 (解决"效果单一": 12 个爆点原来全用同一种抖动)
            # v31 扩到 6 配方 (12 爆点 → 每配方恰好 2 次, 不相邻) + 配方内参数按 i 取模变化
            "impact_recipe": (["shake", "rays", "chroma", "feedback", "edgerays", "filmflash"][i % 6]
                              if (style_id == "drop_impact" and beats and _plugins_on) else None),
            "recipe_i": i,
            "from_timeline": bool(_from_tl),
            "font_override": _tl_font_override,
            "chroma": chroma,
            "chroma_dx": chroma_dx,
            "impact_mul": impact_mul,
            "cascade": st.get("cascade", False),
            "elastic": st.get("elastic", False),
            "shockwave": st.get("shockwave", False),
            "typewriter": st.get("typewriter", False),
            "drop_fall": drop_fall,
            "rise_up": rise_up,
            "blurfade": st.get("blurfade", False),
            "tracking": st["tracking"],
            "anchor_shot": {"index": seg.get("index"), "t0": t0, "t1": t1},
        }
        events.append(ev)

    # 3) 逐 segment 处置 (覆盖记账: 事件窗 / 显式跳过原因)
    spans = [(e["t_in"], e["t_out"]) for e in events]
    disposition = []
    for si, (t0, t1) in enumerate(seg_bounds):
        hit = next((e["id"] for e, (a, b) in zip(events, spans)
                    if min(t1, b) - max(t0, a) >= 0.5 * (t1 - t0)), None)
        if hit is not None:
            disposition.append({"seg": si, "t0": round(t0, 3), "event": hit})
        else:
            reason = "无过阈值 onset 锚点" if si not in {e["anchor_shot"]["index"] for e in events} \
                else "间距护栏/cap 淘汰"
            disposition.append({"seg": si, "t0": round(t0, 3), "skip": reason})
    return events, disposition


def _shot_index(seg_bounds, t):
    """包含 t 的镜头; 无包含则找 start 距 t ≤2帧 的镜头; 都无 → None"""
    for i, (a, b) in enumerate(seg_bounds):
        if a <= t < b:
            return i
    for i, (a, _b) in enumerate(seg_bounds):
        if 0 <= t - a <= ONSET_TOL:
            return i
    return None


def _skin_p70(scenes):
    mos = sorted(v.get("motion", 99) for v in scenes.values())
    return mos[int(len(mos) * 0.7)] if mos else 99.0


def _region_luma(video, t, cx, cy, w=520, h=320):
    """采样视频 t 时刻候选位区域平均亮度 (gray 1x1); 失败返回 255=按亮处理不选"""
    try:
        r = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(max(t - 0.05, 0.0)), "-i", str(video),
             "-frames:v", "1", "-vf",
             "crop=%d:%d:%d:%d,scale=1:1" % (w, h, max(cx - w // 2, 0), max(cy - h // 2, 0)),
             "-f", "rawvideo", "-pix_fmt", "gray", "-"],
            capture_output=True, timeout=10)
        b = r.stdout
        return sum(b) / len(b) if b else 255.0
    except Exception:
        return 255.0


def _worst_region_luma(video, t_in, hold, x, y, w=520, h=320):
    """读字期内该位置的最大区域亮度 (最坏情况); 无基线/失败回退 128(中间调)"""
    if not video or not Path(video).exists():
        return 128.0
    vals = [_region_luma(video, t_in + f * hold, x, y, w, h)
            for f in (0.12, 0.45, 0.80)]
    vals = [v for v in vals if v is not None]
    return max(vals) if vals else 128.0


def _pick_dark_pos(t_in, bg_video, fallback_i, hold=0.9):
    """v4.1 背景亮度感知选位: 三候选位 × 读字窗口(t+0.35h / t+0.65h)两点采样,
    每位取最大亮度(最坏情况), 挑最小者——BREAK 案例实证: t_in 是切点闪光帧全屏无区分度,
    爆炸类高光会在保持期内瞬态后发, 只看 t_in 或单点中期都会漏;
    无基线视频/全失败 → 回退三分位轮换"""
    if not bg_video or not Path(bg_video).exists():
        return DROP_POS_CYCLE[fallback_i % len(DROP_POS_CYCLE)]
    best, best_l = DROP_POS_CYCLE[fallback_i % 3], 1e9
    for cx, cy in DROP_POS_CYCLE:
        # v9: 加早期采样 0.12h — v8 实证爆炸高光在 0.13h 就爆发, 0.35h 起步的采样全漏
        lum = max(_region_luma(bg_video, t_in + 0.12 * hold, cx, cy),
                  _region_luma(bg_video, t_in + 0.35 * hold, cx, cy),
                  _region_luma(bg_video, t_in + 0.65 * hold, cx, cy))
        if lum < best_l - 1e-6:
            best, best_l = (cx, cy), lum
    return best


# ── JSX 生成 (仅实证 API; ES3) ──────────────────────────────────────────
ENV_DECAY_S = 0.16
ENV_TAIL = 0.45


def build_jsx(events, out_aep: Path):
    """在验收基线工程上追加文字层 (非破坏: 不动现有层, 只 addText + save 新文件)

    消费 comp: run53_premium_v3 (已在 AE 打开则直接用 — apply_premium_fx.jsx 同款
    遍历; 未打开则 app.open 回退 — ae_auto_render_orchestrator 实证)。
    """
    def _ev_js(e):
        d = {k: e[k] for k in ("t_in", "t_out", "word", "size", "x", "y",
                               "fill", "font", "enter")}
        if e.get("stroke"):
            d["strokeColor"], d["strokeW"] = e["stroke"]
        else:
            d["strokeColor"], d["strokeW"] = None, 0
        if e.get("glow"):
            # glow = (threshold 0-255, radius, intensity); 能量只调制强度(第3位)
            gt_, gr, gi_ = e["glow"]
            d["glow"] = [gt_, gr, round(gi_ * (0.7 + 0.6 * e["energy"]), 3)]
        else:
            d["glow"] = None
        d["glow2"] = list(e["glow2"]) if e.get("glow2") else None
        d["glow_pulse"] = float(e.get("glow_pulse", 1.7))
        d["glow_col_a"] = list(e["glow_col_a"]) if e.get("glow_col_a") else None
        d["glow_col_b"] = list(e["glow_col_b"]) if e.get("glow_col_b") else None
        d["shadow"] = list(e["shadow"]) if e.get("shadow") else None
        d["bevel"] = list(e["bevel"]) if e.get("bevel") else None
        d["dbl"] = bool(e.get("dbl"))
        d["accent"] = list(e["accent"]) if e.get("accent") else None
        d["outer_w"] = float(e.get("outer_w", 0))
        d["inner_w"] = float(e.get("inner_w", 0))
        d["is3d"] = bool(e.get("is3d"))
        d["z"] = float(e.get("z", 0))
        d["beats"] = [[float(a), float(b)] for a, b in (e.get("beats") or [])]
        d["env_s"] = [[float(a), float(b)] for a, b in (e.get("env_s") or [])]
        d["mv_dx"] = float(e.get("mv_dx", 0))
        d["mv_dy"] = float(e.get("mv_dy", 0))
        d["sp"] = float(e.get("sp", 1.0))            # 时长缩放 (1/speed)
        d["pulse_mul"] = float(e.get("pulse_mul", 1.0))
        d["px_shake"] = bool(e.get("px_shake"))
        d["lshadow"] = bool(e.get("lshadow"))
        d["impact_recipe"] = e.get("impact_recipe")
        d["recipe_i"] = int(e.get("recipe_i", 0))
        # v15/v17 冲击力包参数 (探针实证: ADBE Motion Blur=方向模糊 / ADBE Radial Blur / ADBE Turbulent Displace)
        # v17: 冲量按镜头运动强度分级 (impact_mul), 静止镜头收敛 / 高速爆炸镜头拉满
        en = float(e.get("energy", 0.6))
        im = float(e.get("impact_mul", 1.0))
        d["chroma"] = bool(e.get("chroma"))
        d["chroma_dx"] = float(e.get("chroma_dx", 12))
        d["db_dir"] = 0 if e.get("z", 0) == 0 else 90
        d["db_in"] = round((45 + 45 * en) * im, 1)
        d["db_out"] = round((30 + 30 * en) * im, 1)
        d["rb_in"] = round((12 + 20 * en) * im, 1)
        d["tb_amt"] = round(2 + 4.5 * en, 2)
        d["tb_size"] = round(55 + 65 * en, 1)
        d["tb_evo"] = round(80 + 70 * en, 1)
        d["cascade"] = bool(e.get("cascade"))
        d["elastic"] = bool(e.get("elastic"))
        d["shockwave"] = bool(e.get("shockwave"))
        d["typewriter"] = bool(e.get("typewriter"))
        d["drop_fall"] = bool(e.get("drop_fall"))
        d["rise_up"] = bool(e.get("rise_up"))
        d["blurfade"] = bool(e.get("blurfade"))
        d["tracking"] = e.get("tracking")
        # 入/出场关键帧时刻 (hold 过短时按比例缩, 保证 keyframes 单调)
        hold = e["t_out"] - e["t_in"]
        fin = round(min(0.083, hold * 0.3), 3)            # 入场 2 帧
        fout = round(max(0.042, min(0.125, hold * 0.4)), 3)  # 出场 3 帧
        d["fin"], d["fout"] = fin, fout
        return d

    evs_js = json.dumps([_ev_js(e) for e in events], separators=(",", ":"))
    aep_in = (ROOT / "output" / "unified_run53" / AEP_NAME).resolve().as_posix()
    log_p = (ROOT / "tmp" / "ae_text_build.txt").as_posix()
    return f"""
(function() {{
  var rep = "start";
  var compName = "{COMP_NAME}";
  function findComp() {{
    for (var i = 1; i <= app.project.numItems; i++) {{
      if (app.project.item(i) instanceof CompItem && app.project.item(i).name == compName)
        return app.project.item(i);
    }}
    return null;
  }}
  try {{
    var comp = findComp();
    if (!comp) {{ var fp = new File("{aep_in}"); app.open(fp); comp = findComp(); }}
    if (!comp) {{ rep += "|NOCOMP"; }}
    else {{
      try {{ comp.motionBlur = true; }} catch (mbe) {{ rep += "|COMPMB"; }}   // v15: 合成运动模糊
      // v20 基底光效规范化 (Boss 设定): 素材层 Glo2 = OFF, 粒子层 Glo2 = ON
      // (独立 bridge 调用启用粒子发光曾多次超时/卡住 → 并入注入流程, 状态确定且可核验)
      for (var bi = 1; bi <= comp.numLayers; bi++) {{
        var bly = comp.layer(bi);
        var bfx = null;
        try {{ bfx = bly.property("Effects"); }} catch (be0) {{ continue; }}
        if (!bfx) continue;
        for (var bj = 1; bj <= bfx.numProperties; bj++) {{
          var be = bfx.property(bj);
          var bmn = "";
          try {{ bmn = be.matchName; }} catch (be1) {{ continue; }}
          if (bmn !== "ADBE Glo2") continue;
          var want = (bly.name.indexOf("PART_") === 0);
          try {{ be.enabled = want; }} catch (be2) {{ rep += "|GLOWNORM"; }}
        }}
      }}
      var evs = {evs_js};
      // ── W1 双描边 helper (2026-09-11) ─────────────────────────────────
      function setDoc(L, ev, fillCol, strokeCol, strokeW) {{
        var tp = L.property("Text");
        var d = tp.property("ADBE Text Document").value;
        d.font = ev.font; d.fontSize = ev.size;
        d.fillColor = [fillCol[0], fillCol[1], fillCol[2]];
        d.applyFill = true;
        try {{
          d.applyStroke = strokeW > 0;
          if (strokeW > 0) {{
            d.strokeColor = [strokeCol[0], strokeCol[1], strokeCol[2]];
            d.strokeWidth = strokeW; d.strokeOverFill = false;
          }}
        }} catch (se) {{ rep += "|STROKE"; }}
        d.justification = ParagraphJustification.CENTER_JUSTIFY;
        tp.property("ADBE Text Document").setValue(d);
      }}
      function addKick(L, ev) {{
        // 入场砸入 → 保持 → 出场淡出 (opacity 0-100, 实证口径)
        L.opacity.setValueAtTime(ev.t_in, 0);
        L.opacity.setValueAtTime(ev.t_in + ev.fin, 100);
        L.opacity.setValueAtTime(ev.t_out - ev.fout, 100);
        L.opacity.setValueAtTime(ev.t_out, 0);
      }}
      function addTrack(L, ev) {{
        if (!ev.tracking) return;
        var tp2 = L.property("Text");
        var an = tp2.property("ADBE Text Animators").addProperty("ADBE Text Animator");
        an.name = "Punch";
        var tr = an.property("ADBE Text Animator Properties")
                   .addProperty("ADBE Text Tracking Amount");
        tr.setValueAtTime(ev.t_in, ev.tracking);
        tr.setValueAtTime(ev.t_in + 0.2, 0);
      }}
      function addMove(GL, ev) {{
        // 变换类入场动画只施加于底层 (上层经 parent 继承)
        var yOff = 0, zOff = 0;
        if (ev.enter == "fade_scale") {{
          GL.scale.setValueAtTime(ev.t_in, [115, 115]);
          GL.scale.setValueAtTime(ev.t_in + 0.35 * ev.sp, [100, 100]);
        }} else if (ev.enter == "slide_back") {{
          var dx = ev.x < 960 ? -420 : 420;   // 从所在侧外侧滑入
          GL.position.expression =
            "t=time-inPoint;var x0=" + (ev.x + dx) + ",x1=" + ev.x + ";var y=" + ev.y + ";" +
            "if(t<0.08){{[x0,y];}}else if(t<0.58){{p=(t-0.08)/0.5;s=1.70158;p=p-1;" +
            "x=x0+(x1-x0)*(1+((s+1)*p*p*p+s*p*p));[x,y];}}else{{[x1,y];}}";
        }}
        if (ev.elastic) {{
          // 3D 层 scale 为三维 → 表达式须返回 3 值, 否则 AE 报错
          var s0 = ev.is3d ? "[0,0,0]" : "[0,0]";
          var s1 = ev.is3d ? "[s,s,s]" : "[s,s]";
          var fr = (2.8 / ev.sp).toFixed(3);            // speed 越大振荡越快
          var dc = (5.0 / ev.sp).toFixed(3);
          GL.scale.expression =
            "t=time-inPoint;if(t<0.01){{" + s0 + ";}}else{{" +
            "amp=38;freq=" + fr + ";decay=" + dc + ";" +
            "s=amp*Math.sin(freq*t*Math.PI*2)/Math.exp(decay*t)+100;" + s1 + ";}}";
        }}
        if (ev.is3d) {{ zOff = -170; }}          // 3D 纵深: 由远及近的 Z 位移 (无摄像机)
        var _mvDur = 0.26 * ev.sp;
        if (ev.drop_fall || ev.rise_up || zOff !== 0) {{
          var y0 = ev.y + (ev.drop_fall ? -240 : (ev.rise_up ? 240 : 0));
          var dur = (ev.drop_fall || ev.rise_up) ? _mvDur : (0.34 * ev.sp);
          GL.position.setValueAtTime(ev.t_in, [ev.x, y0, ev.z + zOff]);
          GL.position.setValueAtTime(ev.t_in + dur, [ev.x, ev.y, ev.z]);
        }}
      }}
      // W2 三维层: 不建摄像机 —— 实测 (v13) 合成内存在摄像机会使 Advanced 3D 渲染器
      // 对整帧重新合成 (无文字帧亦出现 0.48% 全画面细微差异) = "视频被影响"风险面;
      // 改为 3D 图层自身的 Z 位移动画 (无摄像机时 AE 用默认视图, 2D 基底层零影响)。
      for (var i = 0; i < evs.length; i++) {{
        var ev = evs[i];
        var L = null, U = null, MV = null;
        if (ev.dbl) {{
          // 双描边: 底层 = 彩色外环(实心), 上层 = 白字 + 深色内描边
          // (图层样式描边无法脚本启用 → canSetEnabled=false, 用双文字层等效实现)
          U = comp.layers.addText(ev.word);
          U.name = "TXTU" + i + "_" + ev.word;
          setDoc(U, ev, ev.accent, ev.accent, ev.outer_w);
          if (ev.is3d) {{ U.threeDLayer = true; }}
          U.position.setValue([ev.x, ev.y, ev.z]);
          U.inPoint = ev.t_in; U.outPoint = ev.t_out + 0.05;
          addKick(U, ev); addTrack(U, ev);
          L = comp.layers.addText(ev.word);
          L.name = "TXT" + i + "_" + ev.word;
          setDoc(L, ev, ev.fill, ev.strokeColor, ev.inner_w);
          if (ev.is3d) {{ L.threeDLayer = true; }}
          L.parent = U; L.position.setValue([0, 0, 0]);
          L.inPoint = ev.t_in; L.outPoint = ev.t_out + 0.05;
          addKick(L, ev); addTrack(L, ev);
          MV = U;
        }} else {{
          L = comp.layers.addText(ev.word);
          L.name = "TXT" + i + "_" + ev.word;
          setDoc(L, ev, ev.fill, ev.strokeColor, ev.strokeW);
          if (ev.is3d) {{ L.threeDLayer = true; }}
          L.position.setValue([ev.x, ev.y, ev.z]);
          L.inPoint = ev.t_in; L.outPoint = ev.t_out + 0.05;
          addKick(L, ev);
          if (ev.enter == "punch_tracking") addTrack(L, ev);
          MV = L;
        }}
        var tp = L.property("Text");
        try {{ addMove(MV, ev); }} catch (mve) {{ rep += "|MOVE" + i; }}
        // ── v25 音乐联动: 节拍脉冲缩放 (非弹性层; 弹性的 drop 层由发光呼吸负责律动) ──
        if (ev.beats && ev.beats.length && !ev.elastic) {{
          try {{
            for (var b = 0; b < ev.beats.length; b++) {{
              var bt = ev.beats[b][0], bstr = ev.beats[b][1];
              var amp = (4 + 10 * bstr) * ev.pulse_mul;            // 节拍越强脉冲越大; pulse_mul 为情绪档倍率
              L.scale.setValueAtTime(bt, [100 + amp, 100 + amp]);
              L.scale.setValueAtTime(bt + 0.12 * ev.sp, [100, 100]);
            }}
          }} catch (sbe) {{ rep += "|BEATSCALE" + i; }}
        }}
        // ── v26 W3 运动迁移: 镜头运动强度驱动的径向视差漂移 (保持期内缓慢位移) ──
        // 跳过 slide_back (其 position 由表达式持有); drop_fall/rise_up 已有起止键 → 追加末帧漂移
        if ((ev.mv_dx || ev.mv_dy) && ev.enter != "slide_back") {{
          try {{
            var px = ev.x, py = ev.y, pz = ev.z || 0;
            if (ev.is3d) {{
              MV.position.setValueAtTime(ev.t_out - ev.fout, [px, py, pz]);
              MV.position.setValueAtTime(ev.t_out, [px + ev.mv_dx, py + ev.mv_dy, pz]);
            }} else {{
              MV.position.setValueAtTime(ev.t_out - ev.fout, [px, py]);
              MV.position.setValueAtTime(ev.t_out, [px + ev.mv_dx, py + ev.mv_dy]);
            }}
          }} catch (mve2) {{ rep += "|MVDRIFT" + i; }}
        }}
        // ── v30 冲击配方轮换 (每事件一种, 解决"效果单一"; 参数按事件序号再变化) ──
        if (ev.impact_recipe) {{
          var ri = ev.recipe_i || 0;
          var bs = ev.beats || [];
          if (ev.impact_recipe == "shake") {{
            try {{
              var shk = L.property("Effects").addProperty("S_Shake");
              try {{ shk.property("S_Shake-0001").setValue(1 + (ri % 3)); }} catch (s0) {{}}   // Style 1/2/3 轮换
              shk.property("S_Shake-0051").setValue(5 + (ri % 3) * 3);                        // Freq 5/8/11
              try {{ shk.property("S_Shake-0054").setValue(1); }} catch (s1) {{}}
              try {{ shk.property("S_Shake-0056").setValue(7); }} catch (s2) {{}}
              var amp = shk.property("S_Shake-0050");
              amp.setValueAtTime(ev.t_in, 0);
              for (var b2 = 0; b2 < bs.length; b2++) {{
                var bt2 = bs[b2][0], bstr2 = bs[b2][1];
                amp.setValueAtTime(bt2, (0.35 + 0.9 * bstr2) * ev.pulse_mul);
                amp.setValueAtTime(bt2 + 0.14 * ev.sp, 0);
              }}
              amp.setValueAtTime(ev.t_out, 0);
            }} catch (e_sh) {{ rep += "|SHAKE" + i; }}
          }} else if (ev.impact_recipe == "rays") {{
            try {{
              var rys = L.property("Effects").addProperty("S_Rays");
              rys.property("S_Rays-0050").setValue([ev.x, ev.y]);                             // 中心=文字位
              rys.property("S_Rays-0051").setValue(0.18 + 0.10 * ((ri % 2) ? 1 : 0));         // 长度轮换
              try {{ rys.property("S_Rays-0100").setValue(ri % 2); }} catch (r0) {{}}          // 方向轮换
              var br = rys.property("S_Rays-0052");
              br.setValueAtTime(ev.t_in, 0.4);
              br.setValueAtTime(ev.t_in + 0.12 * ev.sp, 3.2 * ev.pulse_mul);
              br.setValueAtTime(ev.t_in + 0.42 * ev.sp, 0);
            }} catch (e_ry) {{ rep += "|RAYS" + i; }}
          }} else if (ev.impact_recipe == "chroma") {{
            try {{
              var wc = L.property("Effects").addProperty("S_WarpChroma");
              wc.property("S_WarpChroma-0051").setValue([ev.x, ev.y]);
              try {{ wc.property("S_WarpChroma-0054").setValue(((ri % 2) ? 1 : -1) * 0.03); }} catch (c0) {{}}
              try {{ wc.property("S_WarpChroma-0058").setValue(((ri % 2) ? -1 : 1) * 0.03); }} catch (c1) {{}}
              var wa = wc.property("S_WarpChroma-0100");
              wa.setValueAtTime(ev.t_in, 0.02);
              wa.setValueAtTime(ev.t_in + 0.14 * ev.sp, 0.55 * ev.pulse_mul);
              wa.setValueAtTime(ev.t_in + 0.5 * ev.sp, 0.02);
            }} catch (e_wc) {{ rep += "|WARPCHROMA" + i; }}
          }} else if (ev.impact_recipe == "feedback") {{
            try {{
              var fb = L.property("Effects").addProperty("S_Feedback");
              fb.property("S_Feedback-0100").setValue(10 + (ri % 3) * 4);                     // Max Steps 10/14/18
              var fbPrev = fb.property("S_Feedback-0050");                                    // Prev Brightness
              fbPrev.setValueAtTime(ev.t_in, 0.15);                                           // v31c: 文字先可见
              fbPrev.setValueAtTime(ev.t_in + 0.16 * ev.sp, 0.55);                            // 回授堆叠(爆发感)
              fbPrev.setValueAtTime(ev.t_in + 0.60 * ev.sp, 0.08);                            // 衰减
              var fbBlur = fb.property("S_Feedback-0056");
              fbBlur.setValueAtTime(ev.t_in, 2.5);
              fbBlur.setValueAtTime(ev.t_in + 0.3 * ev.sp, 0);
            }} catch (e_fb) {{ rep += "|FEEDBACK" + i; }}
          }} else if (ev.impact_recipe == "edgerays") {{
            try {{
              var er = L.property("Effects").addProperty("S_EdgeRays");
              er.property("S_EdgeRays-0050").setValue([ev.x, ev.y]);
              er.property("S_EdgeRays-0051").setValue(0.22 + 0.12 * (ri % 2));
              try {{ er.property("S_EdgeRays-0100").setValue(ri % 2); }} catch (er0) {{}}
              var erb = er.property("S_EdgeRays-0052");
              erb.setValueAtTime(ev.t_in, 0.3);
              erb.setValueAtTime(ev.t_in + 0.10 * ev.sp, 2.8 * ev.pulse_mul);
              erb.setValueAtTime(ev.t_in + 0.45 * ev.sp, 0);
            }} catch (e_er) {{ rep += "|EDGERAYS" + i; }}
          }} else if (ev.impact_recipe == "filmflash") {{
            try {{
              var fe = L.property("Effects").addProperty("S_FilmEffect");
              var fpe = fe.property("S_FilmEffect-0057");                                     // Print Exposure
              fpe.setValueAtTime(ev.t_in, 0);
              fpe.setValueAtTime(ev.t_in + 0.08 * ev.sp, 1.2 + 0.5 * (ri % 2));
              fpe.setValueAtTime(ev.t_in + 0.5 * ev.sp, 0);
              var fgb = fe.property("S_FilmEffect-0063");                                     // Glow Brightness
              fgb.setValueAtTime(ev.t_in, 0);
              fgb.setValueAtTime(ev.t_in + 0.08 * ev.sp, 2.2 * ev.pulse_mul);
              fgb.setValueAtTime(ev.t_in + 0.55 * ev.sp, 0);
              try {{ fe.property("S_FilmEffect-0056").setValueAtTime(ev.t_in, -0.4 + 0.8 * (ri % 2)); }} catch (fe0) {{}}
            }} catch (e_fe) {{ rep += "|FILMFLASH" + i; }}
          }}
        }}
        if (ev.lshadow) {{                                                // 文字长阴影 (显式开关; 默认关)
          try {{
            var ls = L.property("Effects").addProperty("LongShadow");
            ls.property("ADBE LongShadow-0005").setValue(225);
            ls.property("ADBE LongShadow-0006").setValue(22);
          }} catch (lse) {{ rep += "|LSHADOW" + i; }}
        }}
        // ── W2 揭示技法: 图层遮罩 (探针实证: mask atom + Shape 赋值/关键帧可用, 不碰文字动画器) ──
        // 为何不用 Linear Wipe: 它作用于整帧(1920x1080)而非文字范围 → 擦除线扫过时文字整块跳出
        // (v21/v22 实证); 遮罩按 sourceRectAtTime 的文字边界裁切 = 真正的"揭示"
        if (ev.enter == "wipe_up" || ev.enter == "wipe_right") {{
          try {{
            var mk = L.property("ADBE Mask Parade").addProperty("ADBE Mask Atom");
            var r = L.sourceRectAtTime(ev.t_in, false);
            var x0 = r.left - 8, x1 = r.left + r.width + 8;
            var y0 = r.top - 8, y1 = r.top + r.height + 8;
            var sFull = new Shape();
            sFull.vertices = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]; sFull.closed = true;
            var sZero = new Shape();
            if (ev.enter == "wipe_up") {{
              sZero.vertices = [[x0, y1], [x1, y1], [x1, y1], [x0, y1]];
            }} else {{
              sZero.vertices = [[x0, y0], [x0, y0], [x0, y1], [x0, y1]];
            }}
            sZero.closed = true;
            var shp = mk.property("ADBE Mask Shape");
            shp.setValueAtTime(ev.t_in, sZero);
            shp.setValueAtTime(ev.t_in + 0.34 * ev.sp, sFull);
            shp.setValueAtTime(ev.t_out - ev.fout, sFull);
            shp.setValueAtTime(ev.t_out, sZero);
            try {{ mk.property("ADBE Mask Feather").setValue([6, 6]); }} catch (mfe) {{}}
          }} catch (mke) {{ rep += "|MASKREVEAL" + i; }}
        }}
        // ── v3 手册实证技法（全部 try/catch, 手册: AE-文字特效JSX动画可靠参数手册 附D/E/F）──
        if (ev.cascade) {{                                    // 逐字级联翻入: RotY(-90)+Opacity(0)+RS idx3 扫过
          try {{
            var ca = tp.property("ADBE Text Animators").addProperty("ADBE Text Animator");
            ca.name = "Cascade";
            var crs = ca.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            crs.property(1).setValue(0);                      // Percent Start (必须用索引, 手册约束)
            crs.property(2).setValue(100);                    // Percent End
            crs.property(3).setValueAtTime(ev.t_in, -100);    // Offset: -100=全隐藏
            crs.property(3).setValueAtTime(ev.t_in + 0.30, 0);// 0=全显示 (0.30s 级联扫过)
            var cpr = ca.property("ADBE Text Animator Properties");
            cpr.addProperty("ADBE Text Opacity").setValue(0);
            cpr.addProperty("ADBE Text Rotation Y").setValue(-90);
          }} catch (ce) {{ rep += "|CASCADE" + i; }}
        }}
        if (ev.shockwave) {{                                    // 冲击波爆发 (手册 附F: Ramp radial + Add + 衰减)
          try {{
            var wv = comp.layers.addSolid([1, 1, 1], "SHOCK" + i, 240, 240, 1, 5);
            wv.position.setValue([ev.x, ev.y]);
            wv.blendMode = 5;                                  // Add
            wv.inPoint = ev.t_in - 0.02; wv.outPoint = ev.t_in + 0.7;
            var rp = wv.property("Effects").addProperty("ADBE Ramp");
            rp.property(1).setValue([120, 120]);
            rp.property(2).setValue([1, 1, 1, 1]);
            rp.property(3).setValue([120, 120]);
            rp.property(4).setValue([0, 0, 0, 0]);
            rp.property(5).setValue(2);                         // radial
            wv.scale.expression =
              "t=time-inPoint;p=Math.min(t/0.45,1);s=10+p*88;[s,s];";
            wv.opacity.expression =
              "t=time-inPoint;if(t<0.04){{85*(t/0.04);}}else{{Math.max(85*Math.exp(-7*(t-0.04)),0);}}";
          }} catch (we) {{ rep += "|SHOCKWAVE" + i; }}
        }}
        if (ev.typewriter) {{                                   // 打字机逐字揭示 (手册 §十六)
          try {{
            var ta = tp.property("ADBE Text Animators").addProperty("ADBE Text Animator");
            ta.name = "TypeIn";
            var trs = ta.property("ADBE Text Selectors").addProperty("ADBE Text Selector");
            trs.property(1).setValue(0);
            trs.property(2).setValue(100);
            trs.property(3).setValueAtTime(ev.t_in, -100);
            trs.property(3).setValueAtTime(ev.t_in + 0.45, 0);
            ta.property("ADBE Text Animator Properties").addProperty("ADBE Text Opacity").setValue(0);
          }} catch (te) {{ rep += "|TYPEWRITER" + i; }}
        }}
        if (ev.blurfade) {{                                     // 模糊淡入 (手册 §十七: Gaussian Blur 2 prop1)
          try {{
            var bl = L.property("Effects").addProperty("ADBE Gaussian Blur 2");
            bl.property(1).setValueAtTime(ev.t_in, 60);
            bl.property(1).setValueAtTime(ev.t_in + 0.5, 0);
          }} catch (be) {{ rep += "|BLURFADE" + i; }}
        }}
        if (ev.glow) {{
          // 实证序号 (2026-09-10 探针): 0002=发光阈值(0-255), 0003=半径, 0004=强度
          // v10 探针补充: 0012=颜色A / 0013=颜色B (默认 白/黑 → 光永远是白的; 亮底上不可见)
          var gf = L.property("Effects").addProperty("ADBE Glo2");
          gf.property("ADBE Glo2-0002").setValue(ev.glow[0]);          // threshold
          gf.property("ADBE Glo2-0003").setValue(ev.glow[1]);          // radius
          if (ev.glow_col_a) {{
            try {{
              gf.property("ADBE Glo2-0007").setValue(2);   // 发光颜色模式= A&B (默认1=原色, 忽略A/B!)
              gf.property("ADBE Glo2-0012").setValue(
                [ev.glow_col_a[0], ev.glow_col_a[1], ev.glow_col_a[2], 1]);
              gf.property("ADBE Glo2-0013").setValue(
                [ev.glow_col_b[0], ev.glow_col_b[1], ev.glow_col_b[2], 1]);
            }} catch (gce) {{ rep += "|GLOWCOL" + i; }}
          }}
          gf.property("ADBE Glo2-0004").setValueAtTime(                // 强度入场脉冲 (ENV 语法, v6.1 按文字系)
            ev.t_in, ev.glow[2] * ev.glow_pulse * ev.pulse_mul);
          gf.property("ADBE Glo2-0004").setValueAtTime(
            ev.t_in + {ENV_DECAY_S} * ev.sp, ev.glow[2]);
          // v25 音乐联动: 保持期内发光强度按音乐包络逐帧呼吸 (确定性烘焙, 非随机)
          var es = ev.env_s || [];
          for (var q = 1; q < es.length; q++) {{
            gf.property("ADBE Glo2-0004").setValueAtTime(
              es[q][0], Math.max(0.05, ev.glow[2] * (0.78 + 0.60 * es[q][1])));
          }}
        }}
        if (ev.glow2) {{                                                // 配方④: 高阈值大半径外层 bloom
          try {{
            var g2 = L.property("Effects").addProperty("ADBE Glo2");
            g2.name = "Bloom";
            g2.property("ADBE Glo2-0002").setValue(ev.glow2[0]);
            g2.property("ADBE Glo2-0003").setValue(ev.glow2[1]);
            g2.property("ADBE Glo2-0004").setValue(ev.glow2[2]);
          }} catch (g2e) {{ rep += "|GLOW2" + i; }}
        }}
        if (ev.shadow) {{                                               // 配方①: 投影层次
          try {{
            var sh = L.property("Effects").addProperty("ADBE Drop Shadow");
            sh.property("ADBE Drop Shadow-0001").setValue([0, 0, 0, 1]);   // 颜色
            sh.property("ADBE Drop Shadow-0002").setValue(ev.shadow[0] * 255); // 不透明度(0-255)
            sh.property("ADBE Drop Shadow-0003").setValue(ev.shadow[1]);   // 方向
            sh.property("ADBE Drop Shadow-0004").setValue(ev.shadow[2]);   // 距离
            sh.property("ADBE Drop Shadow-0005").setValue(ev.shadow[3]);   // 柔和度
          }} catch (she) {{ rep += "|SHADOW" + i; }}
        }}
        if (ev.bevel) {{                                                // 配方⑦lite: 边缘立体
          try {{
            var bv = L.property("Effects").addProperty("ADBE Bevel Alpha");
            bv.property("ADBE Bevel Alpha-0001").setValue(ev.bevel[0]);   // 边缘厚度
            bv.property("ADBE Bevel Alpha-0002").setValue(ev.bevel[1]);   // 灯光角度
            bv.property("ADBE Bevel Alpha-0004").setValue(ev.bevel[2]);   // 灯光强度
          }} catch (bve) {{ rep += "|BEVEL" + i; }}
        }}
        // ── v15 冲击力包 (探针实证内建效果参数) ──────────────────────────
        try {{                                        // 方向模糊: 入场拖影 + 出场拉出
          var dbf = L.property("Effects").addProperty("ADBE Motion Blur");
          dbf.property("ADBE Motion Blur-0001").setValue(ev.db_dir);
          dbf.property("ADBE Motion Blur-0002").setValueAtTime(ev.t_in, ev.db_in);
          dbf.property("ADBE Motion Blur-0002").setValueAtTime(ev.t_in + 0.14, 0);
          dbf.property("ADBE Motion Blur-0002").setValueAtTime(ev.t_out - ev.fout, 0);
          dbf.property("ADBE Motion Blur-0002").setValueAtTime(ev.t_out, ev.db_out);
        }} catch (dbe) {{ rep += "|DIRBLUR" + i; }}
        try {{                                        // 径向模糊: 入场爆发 (向心/离心)
          var rbf = L.property("Effects").addProperty("ADBE Radial Blur");
          rbf.property("ADBE Radial Blur-0002").setValue([ev.x, ev.y]);
          rbf.property("ADBE Radial Blur-0001").setValueAtTime(ev.t_in, ev.rb_in);
          rbf.property("ADBE Radial Blur-0001").setValueAtTime(ev.t_in + 0.16, 0);
        }} catch (rbe) {{ rep += "|RADBLUR" + i; }}
        try {{                                        // 湍流置换: 保持期微流动 (活起来)
          var tbf = L.property("Effects").addProperty("ADBE Turbulent Displace");
          tbf.property("ADBE Turbulent Displace-0002").setValue(ev.tb_amt);
          tbf.property("ADBE Turbulent Displace-0003").setValue(ev.tb_size);
          tbf.property("ADBE Turbulent Displace-0006").expression = "time*" + ev.tb_evo;
        }} catch (tbe) {{ rep += "|TURB" + i; }}
        try {{                                        // 图层运动模糊 (合成开关已开)
          L.motionBlur = true;
          if (U) U.motionBlur = true;
        }} catch (mbe2) {{ rep += "|LAYERMB" + i; }}
        if (ev.chroma) {{                             // v17 通道分离: 红/青幽灵层错位入场 (Add 混合)
          try {{
            var mkGhost = function (col, dx, nm) {{
              var G = comp.layers.addText(ev.word);
              G.name = nm + i + "_" + ev.word;
              setDoc(G, ev, col, col, 0);
              G.blendMode = 5;                        // Add
              G.parent = L;
              G.inPoint = ev.t_in; G.outPoint = ev.t_out + 0.05;
              addKick(G, ev);
              G.position.setValueAtTime(ev.t_in, [dx, 0, 0]);
              G.position.setValueAtTime(ev.t_in + 0.20, [0, 0, 0]);
            }};
            mkGhost([1.0, 0.06, 0.06], -ev.chroma_dx, "TXTR");
            mkGhost([0.06, 0.85, 1.0], ev.chroma_dx, "TXTC");
          }} catch (che) {{ rep += "|CHROMA" + i; }}
        }}
        // ── W2 揭示技法已前移至效果栈首 (见上方, 必须在发光/模糊之前才能裁字形) ──
      }}
      app.project.save(new File("{out_aep.as_posix()}"));
      rep += "|saved layers=" + comp.numLayers + " texts=" + evs.length;
    }}
  }} catch (e) {{ rep += "|FATAL:" + e.toString(); }}
  var f = new File("{log_p}");
  f.encoding = "UTF-8"; f.open("w"); f.write(rep); f.close();
}})()
"""


# ── 门禁自检 (dry-run 报告) ─────────────────────────────────────────────
def validate(events, disposition, segs, onsets, total_dur):
    smax = max(s for _, s in onsets) if onsets else 1.0
    checks = {}
    onset_ts = [t for t, _ in onsets]
    dev = [min(abs(e["t_in"] - t) for t in onset_ts) for e in events]
    checks["onset_align_max_frames"] = round(max(dev) * FPS, 2) if dev else None
    checks["onset_align_pass"] = all(d <= ONSET_TOL + 1e-6 for d in dev)
    checks["min_hold"] = round(min(e["hold"] for e in events), 3) if events else None
    checks["min_hold_pass"] = all(e["hold"] >= 0.15 for e in events)
    # 时间线覆盖 (事件窗并集 / 总时长)
    cov = 0.0
    for e in events:
        a, b = e["t_in"], e["t_out"]
        cov += max(0.0, b - a)
    checks["timeline_coverage"] = round(cov / total_dur, 3)
    checks["timeline_coverage_pass"] = checks["timeline_coverage"] >= 0.80
    # segment 处置覆盖 (每个镜头要么挂事件要么显式跳过)
    checks["segments_total"] = len(segs)
    checks["segments_in_event"] = sum(1 for d in disposition if "event" in d)
    checks["segment_disposition_coverage"] = round(len(disposition) / len(segs), 3)
    # 分区均有事件
    zones_hit = sorted({zone_of(e["t_in"]) for e in events})
    checks["zones_covered"] = zones_hit
    checks["zones_pass"] = set(zones_hit) >= {"intro", "build", "drop"}
    # 字体实证记账
    checks["probe_fonts"] = sorted({e["font"] for e in events if e["probe_font"]})
    checks["verified_fonts_only"] = not checks["probe_fonts"]

    # ── W4 硬门禁 (设计规则, 来自 bang-motion 类实践: menus-not-defaults / 不重复 / 两级文字 / 字号下限) ──
    def _variant(e):
        if e["style_id"] == "drop_impact":
            return "drop_fall" if e.get("drop_fall") else ("rise_up" if e.get("rise_up") else "punch")
        return e["enter"]

    rep_font = [f"{a['word']}→{b['word']}" for a, b in zip(events, events[1:]) if a["font"] == b["font"]]
    rep_var = [f"{a['word']}→{b['word']}" for a, b in zip(events, events[1:])
               if _variant(a) == _variant(b)]
    # 时间表显式指定字体导致的相邻重复 → 用户意图优先, 门禁不计失败, 仅提示
    rep_font_override = [f"{a['word']}→{b['word']}" for a, b in zip(events, events[1:])
                         if a["font"] == b["font"] and (a.get("font_override") or b.get("font_override"))]
    rep_font = [x for x in rep_font if x not in rep_font_override]
    checks["no_repeat_consecutive_fonts"] = not rep_font
    checks["font_repeat_from_override"] = rep_font_override
    _ent_used = events[0].get("entropy", 0.65) if events else 0.65
    # 低熵档 (entropy<0.35) 本就是"固定变款"的显式选择 → 该门禁标 N/A 而非失败 (诚实口径)
    checks["entropy"] = _ent_used
    checks["no_repeat_consecutive_variants"] = (not rep_var) or (_ent_used < 0.35)
    checks["variant_gate_note"] = "N/A(低熵档显式固定变款)" if _ent_used < 0.35 else ""
    checks["repeat_font_pairs"] = rep_font[:5]
    checks["repeat_variant_pairs"] = rep_var[:5]
    # 并发文字层数 (两级文字约束: 本项目设计为单层事件, 上限 2)
    ev_sorted = sorted(events, key=lambda e: e["t_in"])
    max_conc, cur = 0, []
    for e in ev_sorted:
        cur = [x for x in cur if x["t_out"] > e["t_in"]]
        cur.append(e)
        max_conc = max(max_conc, len(cur))
    checks["max_concurrent_text"] = max_conc
    checks["two_levels_pass"] = max_conc <= 2
    # 字号下限 (1920 宽舞台: 60px 下限, 对应 1080 宽 30px 的可读性经验)
    checks["min_font_size"] = min(e["size"] for e in events) if events else None
    checks["font_size_floor_pass"] = bool(events) and checks["min_font_size"] >= 60
    checks["mood_entropy_speed"] = {"mood": events[0].get("mood_profile") if events else None,
                                    "sp": events[0].get("sp") if events else None,
                                    "pulse_mul": events[0].get("pulse_mul") if events else None}
    return checks


# ── CLI ─────────────────────────────────────────────────────────────────
def _parse_args():
    ap = argparse.ArgumentParser(
        prog="build_text_overlay.py",
        description="文字-剪辑集成调度器 P0 — 消费 segments+onsets+envelope 出事件表与注入 JSX",
        epilog="示例: python scripts/build_text_overlay.py unified_run53 run53 --dry-run")
    ap.add_argument("run_dir", help="run 目录, 白名单 unified_run\\d+ (可带 output/ 前缀)")
    ap.add_argument("tag", help="tag, 白名单 run\\d+")
    ap.add_argument("--dry-run", action="store_true",
                    help="只生成事件表 + JSX 落盘, 不调用 AE Bridge (离线验证)")
    ap.add_argument("--words-json", default=None,
                    help="词库覆盖 {zone: [word, ...]}")
    ap.add_argument("--hold-mode", choices=["phrase", "shot"], default="phrase",
                    help="phrase=保持到下一切点/上限(可读性优先, 默认); shot=严格镜头边界")
    ap.add_argument("--max-events", type=int, default=None,
                    help="事件总数上限 (默认按分区 cap: 2+6+10+2=20)")
    ap.add_argument("--mood", choices=list(MOOD_PROFILES.keys()), default="auto",
                    help="情绪档案: auto=既有行为 / impact=冲击优先 / elegant=克制优雅 / kinetic=动感")
    ap.add_argument("--entropy", type=float, default=0.65,
                    help="变款随机度 0~1 (0=固定首款最一致, 1=每事件换款最多样); 确定性(固定 seed)")
    ap.add_argument("--speed", type=float, default=1.0,
                    help="节奏速度倍率 (入场/脉冲时长 ∝ 1/speed; 弹性动画频率 ∝ speed)")
    ap.add_argument("--seed", type=int, default=20260912, help="变款 PRNG 种子 (保证可复现)")
    return ap.parse_args()


def main():
    args = _parse_args()
    raw = str(args.run_dir).replace("\\", "/").removeprefix("output/")
    if not re.fullmatch(r"unified_run\d+", raw):
        print(f"[ERR] 非法 run 目录名(白名单 unified_run\\d+): {raw}")
        sys.exit(2)
    if not re.fullmatch(r"run\d+", str(args.tag)):
        print(f"[ERR] 非法 tag(白名单 run\\d+): {args.tag}")
        sys.exit(2)
    run_dir = ROOT / "output" / raw
    if not (run_dir / "production_report.json").exists():
        print(f"[ERR] 缺前置产物 {run_dir / 'production_report.json'}")
        sys.exit(2)

    words = load_words(None)
    _wp = ROOT / WORDS_FILE
    if not _wp.exists():
        _wp.parent.mkdir(parents=True, exist_ok=True)
        _wp.write_text(json.dumps(DEFAULT_WORDS, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"[P0] 已生成可编辑词库: {_wp} (改文字后重跑本脚本即生效)")
    if args.words_json:
        words = load_words(json.loads(Path(args.words_json).read_text(encoding="utf-8")))
        print(f"[P0] 词库覆盖: {args.words_json}")

    segs = load_segments(run_dir)
    onsets = load_onsets()
    env_at = load_envelope_at()
    scenes = load_scenes()
    total_dur = float(segs[-1]["end_time"]) if segs else 0.0
    timeline = load_timeline()
    if timeline:
        print(f"[P0] 时间表命中: 载入 {len(timeline)} 条 (容差 ±{TIMELINE_TOL}s)")

    events, disposition = plan_events(segs, onsets, env_at, scenes, words,
                                      hold_mode=args.hold_mode,
                                      max_events=args.max_events,
                                      total_dur=total_dur,
                                      bg_video=run_dir / "run53_premium_final.mp4",
                                      profile=MOOD_PROFILES.get(args.mood),
                                      entropy=args.entropy,
                                      speed=args.speed,
                                      seed=args.seed,
                                      mood_name=args.mood,
                                      timeline=timeline)
    checks = validate(events, disposition, segs, onsets, total_dur)
    # 时间表对账 (显式记账: 命中/未命中, 未命中告警——否则用户以为指定了其实没生效)
    if timeline:
        matched_t = [round(e["t_in"], 2) for e in events if e.get("from_timeline")]
        unmatched = [it for it in timeline if not any(abs(it["t"] - mt) <= TIMELINE_TOL for mt in matched_t)]
        checks["timeline_specified"] = len(timeline)
        checks["timeline_matched"] = len(matched_t)
        checks["timeline_unmatched"] = [{"t": it["t"], "word": it["word"]} for it in unmatched]
        if unmatched:
            _txt = ", ".join(f"{it['t']}s:{it['word']}" for it in unmatched)
            print(f"[P0] ⚠ 时间表未命中 {len(unmatched)} 条 (该时刻无事件锚点): {_txt}")

    out_dir = run_dir / "text_overlay"
    out_dir.mkdir(parents=True, exist_ok=True)
    ver = os.environ.get("TEXT_OVERLAY_VER", "v2")            # v2=P1配方①④⑦样式 (v1已被git历史覆盖备份)
    out_aep = run_dir / f"run53_text_{ver}.aep"
    jsx = build_jsx(events, out_aep)
    (out_dir / "events.json").write_text(
        json.dumps({"events": events, "disposition": disposition,
                    "checks": checks, "hold_mode": args.hold_mode,
                    "generated_by": "build_text_overlay.py P0"},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    jsx_p = out_dir / f"text_overlay_{ver}.jsx"
    jsx_p.write_text(jsx, encoding="utf-8")

    # ── 报告 ──
    print(f"[P0] 事件 {len(events)} 个 / 镜头 {len(segs)} / onsets {len(onsets)} "
          f"(hold_mode={args.hold_mode})")
    for e in events:
        probe = " [字体待探针]" if e["probe_font"] else ""
        cu = " closeup→安全带" if e["closeup"] else ""
        print(f"  #{e['id']:02d} {e['t_in']:6.2f}-{e['t_out']:6.2f} "
              f"({e['hold']:4.2f}s) {e['mood']:<5} {e['style_id']:<12} "
              f"'{e['word']}'[{e.get('script', '?')}] {e['font']} "
              f"{e['size']}px @({e['x']},{e['y']}) bg={e.get('bg_class', '?')}"
              f"({e.get('bg_lum', -1):.0f}){' 双描边' if e.get('dbl') else ''}{cu}{probe}")
    zc = {}
    for e in events:
        zc[zone_of(e["t_in"])] = zc.get(zone_of(e["t_in"]), 0) + 1
    print(f"[P0] 分区分布: {zc}")
    print(f"[P0] 门禁: onset对齐≤2帧={checks['onset_align_pass']} "
          f"({checks['onset_align_max_frames']}帧) | 最小保持≥0.15s={checks['min_hold_pass']} "
          f"({checks['min_hold']}s) | 时间线覆盖≥80%={checks['timeline_coverage_pass']} "
          f"({checks['timeline_coverage']:.0%}) | 分区覆盖={checks['zones_pass']} "
          f"{checks['zones_covered']}")
    print(f"[P0] 镜头处置: {checks['segments_in_event']}/{checks['segments_total']} "
          f"挂事件, 其余显式跳过 (处置覆盖 {checks['segment_disposition_coverage']:.0%})")
    print(f"[P0] W4 门禁: 同款不连打-字体={checks['no_repeat_consecutive_fonts']} "
          f"同款不连打-变款={checks['no_repeat_consecutive_variants']} "
          f"两级文字≤2={checks['two_levels_pass']}(实测并发 {checks['max_concurrent_text']}) "
          f"字号下限≥60={checks['font_size_floor_pass']}(最小 {checks['min_font_size']})")
    if checks["repeat_font_pairs"] or checks["repeat_variant_pairs"]:
        print(f"[P0] ⚠ 相邻重复: 字体 {checks['repeat_font_pairs']} / 变款 {checks['repeat_variant_pairs']}")
    print(f"[P0] 情绪档: mood={checks['mood_entropy_speed']['mood']} "
          f"时长缩放 sp={checks['mood_entropy_speed']['sp']} "
          f"脉冲倍率={checks['mood_entropy_speed']['pulse_mul']}")
    if checks["probe_fonts"]:
        print(f"[P0] ⚠ 字体待实机探针: {checks['probe_fonts']} — 注入前跑字体在位清单 "
              f"(交接 §六.6), 不过则降级 BebasNeue")
    print(f"[P0] 事件表: {out_dir / 'events.json'}")
    print(f"[P0] JSX: {jsx_p} ({len(jsx):,} 字符)")

    if args.dry_run:
        print("[dry-run] 未调用 AE Bridge — 注入由执行模式完成 "
              "(python .ae-mcp-bridge/send_bridge.py <jsx>)")
        hard_fail = not (checks["onset_align_pass"] and checks["min_hold_pass"]
                         and checks["zones_pass"])
        sys.exit(1 if hard_fail else 0)

    # 执行模式: 文件协议 Bridge (硬约束: python .ae-mcp-bridge/send_bridge.py <jsx>)
    r = subprocess.run([sys.executable, str(ROOT / ".ae-mcp-bridge" / "send_bridge.py"),
                        str(jsx_p)], capture_output=True, text=True, timeout=420)
    print(r.stdout[-1500:] if r.stdout else "(bridge 无输出)")
    if r.returncode != 0:
        print(f"[ERR] send_bridge 失败 exit={r.returncode}")
        sys.exit(4)
    log = ROOT / "tmp" / "ae_text_build.txt"
    if log.exists():
        print("build:", log.read_text(encoding="utf-8")[:600])
        rep = log.read_text(encoding="utf-8")
        if "FATAL" in rep or "NOCOMP" in rep:
            print("[ERR] AE 执行报错 — 见 ae_text_build.txt")
            sys.exit(4)
    else:
        print("[ERR] 未找到 ae_text_build.txt — AE 可能未执行 JSX")
        sys.exit(4)


if __name__ == "__main__":
    main()
