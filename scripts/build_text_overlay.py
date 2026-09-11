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
        "size": (85, 120), "fill": [0.95, 0.95, 0.98],
        "stroke": ([0.03, 0.03, 0.06], 2.2), "pos": "side_alt", "enter": "slide_back",
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

# ── v6.1 字体池 (2026-09-11 fontTools nameID6 真相表: 只收 HKLM 系统字体真实 PS 名) ──
# 铁律 (v6 事故实证): AE 只解析 HKLM 系统字体, 用户目录 (LOCALAPPDATA) 字体全部不可见;
#   预设库 §8.1 set→回读探针有盲区 — 回读只是回显存储字符串, 不证明可解析
#   (v6 实证: Anton/BebasNeue/Antonio 等 USER 字体 v1 起从未真正渲染, 全被替换成同一默认字体)。
# 真相表方法: fontTools 枚举全部 face (含 TTC 多 face) 的 nameID 6 + 文件位置 → HKLM 才可用。
FONT_POOLS = {
    "drop_impact": {   # 冲击词: 重笔画/压缩展示系
        "jp":    ["YuGothic-Bold", "MS-PGothic", "YuGothic-Medium"],
        "cn":    ["FZCHSJW--GB1-0", "SimHei", "MicrosoftYaHei-Bold"],   # FZCHSJW=方正粗黑宋简体
        "latin": ["Impact", "Haettenschweiler", "Arial-Black", "FranklinGothic-Heavy"],
    },
    "build_side": {    # 铺垫词: 现代无衬线/窄体
        "jp":    ["YuGothic-Regular", "YuGothic-Medium"],
        "cn":    ["STXihei", "MicrosoftYaHei", "YouYuan"],
        "latin": ["TwCenMT-CondensedBold", "TrebuchetMS-Bold", "AgencyFB-Bold"],
    },
    "intro_serif": {   # 开场/收尾: 衬线/书法质感
        "jp":    ["YuGothic-Light", "SimSun"],
        "cn":    ["STKaiti", "STXinwei", "KaiTi"],
        "latin": ["Georgia", "Rockwell"],
    },
}
VERIFIED_FONTS = {          # fontTools 真相表实证 HKLM + PS 名精确匹配 (2026-09-11)
    "YuGothic-Bold", "YuGothic-Medium", "YuGothic-Light", "YuGothic-Regular",
    "MS-PGothic", "MS-Gothic", "SimSun", "SimHei", "KaiTi", "LiSu", "YouYuan",
    "MicrosoftYaHei", "MicrosoftYaHei-Bold", "DengXian-Bold",
    "FZCHSJW--GB1-0", "STKaiti", "STXinwei", "STZhongsong", "STXihei",
    "STFangsong", "STSong", "STHupo", "STXingkai", "STLiti", "STCaiyun",
    "Impact", "Haettenschweiler", "Arial-Black", "SegoeUIBlack",
    "FranklinGothic-Heavy", "FranklinGothic-DemiCond", "GillSans-UltraBoldCondensed",
    "TwCenMT-CondensedBold", "TrebuchetMS-Bold", "AgencyFB-Bold",
    "Georgia", "Georgia-Bold", "Rockwell", "Rockwell-ExtraBold",
    "TimesNewRomanPSMT", "TimesNewRomanPS-BoldMT", "Cambria-Bold",
}
JP_ONLY_CHARS = set("強発壊無縛臨韻")      # 词库内 JP 专字形 (JP 字体优先保字形正确)


def script_class(word):
    """jp=含 JP 专字形; cn=仅通用汉字; latin=ASCII"""
    if any(ch in JP_ONLY_CHARS for ch in word):
        return "jp"
    if any("\u4e00" <= ch <= "\u9fff" for ch in word):
        return "cn"
    return "latin"

# 默认词库 (报告无歌词素材 → 按源 IP 咒术回战/五条悟 的 AMV 惯用词; --words-json 可覆盖)
DEFAULT_WORDS = {
    "intro": ["五条悟", "THE STRONGEST"],
    "build": ["無限", "束縛", "加速", "VIOLATION", "迂回", "LIMIT",
              "静止", "臨界", "REVERSE"],
    "drop":  ["最強", "BREAK", "爆発", "無下限", "ZERO", "IMPACT",
              "崩壊", "RED", "虚式"],
    "outro": ["THE END", "余韻"],
}

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
                max_events=None, total_dur=None, bg_video=None):
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

        # 词 (区内轮换, 不与上一词重复)
        bank = words.get(zone) or words.get(mood) or ["TEXT"]
        w = bank[bank_pos[zone] % len(bank)]
        if len(events) and events[-1]["word"] == w:
            w = bank[(bank_pos[zone] + 1) % len(bank)]
            bank_pos[zone] += 1
        bank_pos[zone] += 1

        # v6: 字体按文字系分池轮换 (jp/cn/latin 见 FONT_POOLS), 池内不背靠背重复
        scl = script_class(w)
        pool = FONT_POOLS[style_id][scl]
        fkey = (style_id, scl)
        font = pool[font_pos.get(fkey, 0) % len(pool)]
        if last_font.get(fkey) == font and len(pool) > 1:
            font = pool[(font_pos.get(fkey, 0) + 1) % len(pool)]
            font_pos[fkey] = font_pos.get(fkey, 0) + 1
        font_pos[fkey] = font_pos.get(fkey, 0) + 1
        last_font[fkey] = font

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

        # v9: drop 变款全整层平移 (RS 动画器与脚本字体互斥; v8 实证旋转变款使文字倾斜超框压高光)
        # _v: 0=drop_fall 自上落下 / 1=rise_up 自下升起 / 2=纯 punch tracking
        drop_fall = rise_up = False
        if style_id == "drop_impact":
            _v = bank_pos[zone] % 3
            drop_fall, rise_up = (_v == 0), (_v == 1)

        ev = {
            "id": i, "t_in": t_in, "t_out": t_out, "hold": hold,
            "mood": mood, "energy": energy, "style_id": style_id,
            "word": w, "size": size, "x": x, "y": y, "closeup": closeup,
            "font": font,
            "font_stack": pool,
            "script": scl,
            "probe_font": font not in VERIFIED_FONTS,
            "fill": st["fill"],
            "stroke": st["stroke"],
            "enter": st["enter"],
            "glow": glow,
            "glow2": glow2,
            "shadow": st.get("shadow"),
            "bevel": bevel,
            "glow_pulse": pulse,
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
        d["shadow"] = list(e["shadow"]) if e.get("shadow") else None
        d["bevel"] = list(e["bevel"]) if e.get("bevel") else None
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
      var evs = {evs_js};
      for (var i = 0; i < evs.length; i++) {{
        var ev = evs[i];
        var L = comp.layers.addText(ev.word);
        L.name = "TXT" + i + "_" + ev.word;
        var tp = L.property("Text");
        var d = tp.property("ADBE Text Document").value;
        d.font = ev.font; d.fontSize = ev.size;
        d.fillColor = [ev.fill[0], ev.fill[1], ev.fill[2]];
        d.applyFill = true;
        try {{
          d.applyStroke = ev.strokeW > 0;
          if (ev.strokeW > 0) {{
            d.strokeColor = [ev.strokeColor[0], ev.strokeColor[1], ev.strokeColor[2]];
            d.strokeWidth = ev.strokeW; d.strokeOverFill = false;
          }}
        }} catch (se) {{ rep += "|STROKE" + i; }}
        d.justification = ParagraphJustification.CENTER_JUSTIFY;
        tp.property("ADBE Text Document").setValue(d);
        L.position.setValue([ev.x, ev.y]);
        L.inPoint = ev.t_in; L.outPoint = ev.t_out + 0.05;
        // 入场砸入 → 保持 → 出场淡出 (opacity 0-100, 实证口径)
        L.opacity.setValueAtTime(ev.t_in, 0);
        L.opacity.setValueAtTime(ev.t_in + ev.fin, 100);
        L.opacity.setValueAtTime(ev.t_out - ev.fout, 100);
        L.opacity.setValueAtTime(ev.t_out, 0);
        if (ev.enter == "fade_scale") {{
          L.scale.setValueAtTime(ev.t_in, [115, 115]);
          L.scale.setValueAtTime(ev.t_in + 0.35, [100, 100]);
        }} else if (ev.enter == "slide_back") {{
          var dx = ev.x < 960 ? -420 : 420;   // 从所在侧外侧滑入
          L.position.expression =
            "t=time-inPoint;var x0=" + (ev.x + dx) + ",x1=" + ev.x + ";var y=" + ev.y + ";" +
            "if(t<0.08){{[x0,y];}}else if(t<0.58){{p=(t-0.08)/0.5;s=1.70158;p=p-1;" +
            "x=x0+(x1-x0)*(1+((s+1)*p*p*p+s*p*p));[x,y];}}else{{[x1,y];}}";
        }} else if (ev.enter == "punch_tracking" && ev.tracking) {{
          var an = tp.property("ADBE Text Animators").addProperty("ADBE Text Animator");
          an.name = "Punch";
          var tr = an.property("ADBE Text Animator Properties")
                     .addProperty("ADBE Text Tracking Amount");
          tr.setValueAtTime(ev.t_in, ev.tracking);
          tr.setValueAtTime(ev.t_in + 0.2, 0);
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
        if (ev.elastic) {{                                     // 弹性缩放砸入 (手册 §二十)
          try {{
            L.scale.expression =
              "t=time-inPoint;if(t<0.01){{[0,0];}}else{{" +
              "amp=38;freq=2.8;decay=5;" +
              "s=amp*Math.sin(freq*t*Math.PI*2)/Math.exp(decay*t)+100;[s,s];}}";
          }} catch (ee) {{ rep += "|ELASTIC" + i; }}
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
        if (ev.drop_fall) {{                                     // v9 整层下落砸入 (纯平移, 不旋转)
          try {{
            L.position.setValueAtTime(ev.t_in, [ev.x, ev.y - 240]);
            L.position.setValueAtTime(ev.t_in + 0.26, [ev.x, ev.y]);
          }} catch (dfe) {{ rep += "|DROPFALL" + i; }}
        }}
        if (ev.rise_up) {{                                       // v9 整层自下升起 (纯平移)
          try {{
            L.position.setValueAtTime(ev.t_in, [ev.x, ev.y + 240]);
            L.position.setValueAtTime(ev.t_in + 0.26, [ev.x, ev.y]);
          }} catch (rue) {{ rep += "|RISEUP" + i; }}
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
          // v1 曾把 0002 当强度/0004 当阈值 —— 参数反转是"效果普通"的根因
          var gf = L.property("Effects").addProperty("ADBE Glo2");
          gf.property("ADBE Glo2-0002").setValue(ev.glow[0]);          // threshold
          gf.property("ADBE Glo2-0003").setValue(ev.glow[1]);          // radius
          gf.property("ADBE Glo2-0004").setValueAtTime(                // 强度入场脉冲 (ENV 语法, v6.1 按文字系)
            ev.t_in, ev.glow[2] * ev.glow_pulse);
          gf.property("ADBE Glo2-0004").setValueAtTime(
            ev.t_in + {ENV_DECAY_S}, ev.glow[2]);
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

    words = dict(DEFAULT_WORDS)
    if args.words_json:
        words.update(json.loads(Path(args.words_json).read_text(encoding="utf-8")))

    segs = load_segments(run_dir)
    onsets = load_onsets()
    env_at = load_envelope_at()
    scenes = load_scenes()
    total_dur = float(segs[-1]["end_time"]) if segs else 0.0

    events, disposition = plan_events(segs, onsets, env_at, scenes, words,
                                      hold_mode=args.hold_mode,
                                      max_events=args.max_events,
                                      total_dur=total_dur,
                                      bg_video=run_dir / "run53_premium_final.mp4")
    checks = validate(events, disposition, segs, onsets, total_dur)

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
              f"{e['size']}px @({e['x']},{e['y']}){cu}{probe}")
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
