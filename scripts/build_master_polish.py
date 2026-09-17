# -*- coding: utf-8 -*-
"""镜头级 AE 精修 v4 — 拍点包络 + 连续密度曲线 + 转场冲击层 (2026-09-04)

用户定调: 外网顶尖 AMV 水平 = 效果跟着拍点呼吸, 不是平涂。
v4 三升级 (在 v3.1 已验收的映射骨架上):
1. 拍点包络: punch 类效果 (badtv/radial) setValueAtTime 打关键帧 —
   切点满剂量砸入, 3帧内 (0.12s) 衰减到 30%, 之后保持
2. 连续密度: 剂量 × (0.65 + 0.7×RMS包络) 连续映射, 替代分位数一刀切
   (包络 = BGM 谐波 RMS 0.6s 平滑, 与引擎呼吸语法同源, tmp/music_envelope.json)
3. 转场冲击层: 强鼓点上的切点 (drop 前12强/build 前6强) 加 2-4 帧
   顶层 burst 层 (radial@55 冲击延续 / badtv@2), 同样带衰减包络

用法: python scripts/build_master_polish.py <run_dir> <tag>
      python scripts/build_master_polish.py <run_dir> <tag> --effects-json <schema配置.json>
      python scripts/build_master_polish.py <run_dir> <tag> --dry-run   # 只出 plan+JSX, 不碰 AE

位置参数契约 (<run_dir> <tag>) 自 2026-09-05 起对外公布, 不可变更;
--effects-json / --dry-run 为 2026-09-07 新增可选参数, 不传时行为与旧版完全一致。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 并发会话加的 core 导入需要它先就位

from core.paths import aerender_exe  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# run 目录名 / tag 白名单 (路径安全: 严格 fullmatch 防遍历; 目录名重建自常量非拼接用户输入)
# Step1.5: run_dir 放宽接受 R1 修复run (unified_r1_fixed_vN) → 让 EDL 桥能指向 R1 成果, 解 K3
RUN_DIR_PATTERN = r"unified_(?:run\d+|r1_fixed_v\d+)"
TAG_PATTERN = r"run\d+"

# 效果配方 (v4: env=True 用 setValueAtTime 包络, 值会被剂量缩放)
RECIPES = {
    "bloom":    {"m": "ADBE Glo2", "ps": [("ADBE Glo2-0002", 0.80),
                                          ("ADBE Glo2-0003", 6),
                                          ("ADBE Glo2-0004", 0.38)], "env": False},
    "bloom_soft": {"m": "ADBE Glo2", "ps": [("ADBE Glo2-0002", 0.85),
                                            ("ADBE Glo2-0003", 5),
                                            ("ADBE Glo2-0004", 0.26)], "env": False},
    "bokeh":    {"m": "RWB Fast Bokeh", "ps": [("RWB Fast Bokeh-0001", 2.0)], "env": False},
    "badtv":    {"m": "GUTS BadTV", "ps": [("GUTS BadTV-0001", 9.0)], "env": True},
    "badtv_light": {"m": "GUTS BadTV", "ps": [("GUTS BadTV-0001", 4.0)], "env": True},
    "badtv_hard": {"m": "GUTS BadTV", "ps": [("GUTS BadTV-0001", 13.0)], "env": True},
    "fmb":      {"m": "CC Force Motion Blur", "ps": [("CC Force Motion Blur-0001", 28)], "env": False},
    "fmb_light": {"m": "CC Force Motion Blur", "ps": [("CC Force Motion Blur-0001", 22)], "env": False},
    "glitch":   {"m": "AESweetsGlitch7in1", "ps": [], "env": False},
    "radial":   {"m": "CC Radial Fast Blur", "ps": [("CC Radial Fast Blur-0002", 70)], "env": True},
    "radial_soft": {"m": "CC Radial Fast Blur", "ps": [("CC Radial Fast Blur-0002", 35)], "env": True},
    "fmb_dir": {"m": "CC Force Motion Blur", "ps": [], "env": False},  # ps 由光流注入: [amount, angle]
    "fmb_dir_light": {"m": "CC Force Motion Blur", "ps": [], "env": False},
    # 转场冲击层 (顶层短层)
    "burst_radial": {"m": "CC Radial Fast Blur", "ps": [("CC Radial Fast Blur-0002", 90)], "env": True},
    "burst_badtv":  {"m": "GUTS BadTV", "ps": [("GUTS BadTV-0001", 4.5)], "env": True},
    # premium 插件 (matchName 经 AE Bridge 实证)
    "particular": {"m": "tc Particular", "ps": [
        ("tc Particular-0011", 10),    # velocity
        ("tc Particular-0002", 1.5),   # life
        ("tc Particular-0027", 2.0),   # particle size
        ("tc Particular-0146", 200),   # particles per second
    ], "env": False},
    "sapphire_glow": {"m": "S_Glow", "ps": [], "env": False},
    "optical_flares": {"m": "Optical Flares", "ps": [], "env": False},
    "magic_bullet_looks": {"m": "Magic Bullet Looks", "ps": [], "env": False},
}

ENV_DECAY_S = 0.16   # 包络衰减时长 (~3帧@24fps)
ENV_TAIL = 0.45      # 衰减后保持比例

# 高光安全档 (2026-09-14 根因定位, handoff §9.4): 链路逐段实测过冲(hi% 0→14.7)由本脚本的
# AE 效果层引入, plan 证据指向 CC Radial Fast Blur(被冲爆镜头挂 radial_soft/radial,
# 且为主导效果 39/95 镜); dose(0.72-2.42) 会把基数 70/35 放大到有效 ~25-85。
# 本档按该系数下调 radial/radial_soft 基数(burst_radial 是有意的瞬时转场闪光, 不动)。
# 默认关闭 —— 属招牌观感, 需一次 AE 渲染视觉复验后才考虑转默认。
HL_SAFE_RADIAL_SCALE = 0.7

# v11: 垃圾窗口救援映射 — 底片窗口为源片水印卡/黑场 (报告↔底片镜头-源映射漂移的牺牲品),
# 内容用显式映射 (经帧条目检), 不自动回落到报告分配 (映射不可靠)。
RESCUE_MAP = {23.958: ("D:/AE-Work/resources/video/猫猫（一般）/素材/猫2.mp4", 109.0, 1.1)}

# Twixtor 连续速度曲线 (2026-09-05 #10): (时长占比, 相对速度)
# 快进冲入→急减速→冻结在拍点(顶尖慢镜招牌)。梯形积分归一=1 保平均速度不变, 落拍不漂。
# v10.1 (用户反馈: 22/25/27s 处只有死冻结没有"缓慢运动", 突兀): 底速 0.18→0.35,
# 冻结改缓爬 (~8fps 有效, 读作慢速运动而非停格), 加速放出段不变。§5 预留的 remedy 旋钮。
TWX_SPEED_PROFILE = [(0.0, 0.35), (0.55, 0.50), (1.0, 1.05)]

# ── visual_effect_schema.json 注入 (2026-09-07) ──────────────────────────
# schema effect_type → RECIPES 键。只映射已在 run53 实机跑通并验收的配方;
# 第三方插件 matchName 未经 AE 枚举实证的一律不编造 (硬性检查清单 A1)。
SCHEMA_TO_RECIPE = {
    "bloom": "bloom",
    "bokeh": "bokeh",
    "badtv": "badtv",
    "glitch": "glitch",
    "radial_blur": "radial",
    "radial": "radial",  # 别名: dense 数据用 RECIPES 键名
    "motion_blur": "fmb",
    "burst_radial": "burst_radial",
    "burst_badtv": "burst_badtv",
    "particular": "particular",  # matchName tc Particular (AE Bridge 实证)
    "sapphire_glow": "sapphire_glow",  # matchName S_Glow (AE Bridge 实证 2026-09-09)
    "optical_flares": "optical_flares",  # matchName Optical Flares (AE Bridge 实证 2026-09-09)
    "magic_bullet_looks": "magic_bullet_looks",  # matchName Magic Bullet Looks (AE Bridge 实证 2026-09-09)
}

# 需要运行时参数的类型 → spec 字符串 "fmb_dir:<amount>:<angle>" (见 _fx_js)
SCHEMA_DYN_RECIPE = {"fmb_directional": "fmb_dir"}

BURST_TYPES = {"burst_radial", "burst_badtv"}

# 明确不可注入的类型 + 原因。必须显式上报, 禁止静默丢弃:
# 2026-09-07 事故 — run53v43_effects_premium_v2.json 的 139 条里 105 条属于
# 下列类型, 静默丢弃会让上层报出"139 个特效已应用"的假绿灯。
SCHEMA_UNMAPPED = {
    "twixtor": "由 plan_effects 的 twx 通道按真实 onset 生成, 不接受外部注入",
    "zoom_pan": "由 production_report segments.zoompan_effect 驱动",
    "delirium": "RECIPES 无 Delirium matchName — 本机未安装 Digieffects Delirium, 无法 AE 实证",
    "film_stocks": "RECIPES 无 Tiffen Film Stocks matchName — 本机未安装 Tiffen Dfx, 无法 AE 实证",
}


def schema_effects_to_plan(effects):
    """把 visual_effect_schema.json 配置翻译为内部 (plan, bursts) 表示。

    返回 (plan, bursts, report)。report 显式记账 unmapped / skipped,
    供调用方如实上报 — 绝不把"没实现"粉饰成"已应用"。

    内部条目契约 (build_jsx 只取这几个键, 多余键安全忽略):
      plan : {t0, t1, fx:[spec...], dose}  可选 twx/rescue/grade/drift
      burst: {t0, t1, fx:[spec...], dose, en, env}
    """
    plan, bursts = [], []
    unmapped, skipped = {}, []
    for i, e in enumerate(effects):
        et = e.get("effect_type")
        tr = e.get("time_range") or {}
        t0 = round(float(tr.get("start_sec", 0.0)), 3)
        t1 = round(float(tr.get("end_sec", t0)), 3)
        if t1 <= t0:
            skipped.append({"index": i, "effect_id": e.get("effect_id"),
                            "reason": f"time_range 非法 (start={t0} >= end={t1})"})
            continue

        if et in SCHEMA_UNMAPPED:
            slot = unmapped.setdefault(
                et, {"reason": SCHEMA_UNMAPPED[et], "count": 0, "effect_ids": []})
            slot["count"] += 1
            if len(slot["effect_ids"]) < 5:
                slot["effect_ids"].append(e.get("effect_id"))
            continue

        params = e.get("parameters") or {}
        env = e.get("envelope") or {}
        dose = float(env.get("peak_value", 1.0)) if env.get("enabled") else 1.0

        if et in SCHEMA_DYN_RECIPE:
            amt = float(params.get("base_amount", 24))
            # 光流方向是 0-360°; _fx_js 写 CC Force Motion Blur-0003, 取模 180 对齐既有口径
            ang = float(params.get("flow_angle", 0.0)) % 180
            spec = f"{SCHEMA_DYN_RECIPE[et]}:{amt:.0f}:{ang:.0f}"
        elif et in SCHEMA_TO_RECIPE:
            spec = SCHEMA_TO_RECIPE[et]
        else:
            skipped.append({"index": i, "effect_id": e.get("effect_id"),
                            "reason": f"未知 effect_type '{et}' (schema 与映射表均无)"})
            continue

        entry = {"t0": t0, "t1": t1, "fx": [spec], "dose": round(dose, 3),
                 "en": 1, "env": 1 if env.get("enabled") else 0,
                 "src_effect_id": e.get("effect_id")}
        (bursts if et in BURST_TYPES else plan).append(entry)

    plan.sort(key=lambda x: x["t0"])
    bursts.sort(key=lambda x: x["t0"])
    report = {
        "input_count": len(effects),
        "plan_count": len(plan),
        "burst_count": len(bursts),
        "applied_count": len(plan) + len(bursts),
        "unmapped_count": sum(v["count"] for v in unmapped.values()),
        "unmapped_types": unmapped,
        "skipped_count": len(skipped),
        "skipped": skipped,
    }
    return plan, bursts, report


def _load_env():
    p = ROOT / "tmp" / "music_envelope.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    times, env = d["env_times"], d["env"]
    def at(t):
        i = min(range(len(times)), key=lambda k: abs(times[k] - t))
        return env[i]
    return at, d["strong"]


def _load_onsets():
    """真实 onset (谱通量, 无平滑滞后) — tmp/true_onsets.json 由 scripts/gen_true_onsets.py 生成。

    引擎切点网格源自 0.6s 平滑能量包络, 峰值可偏离真实 kick 达 ±0.3s;
    本表用于把 TWX 冻结点锚到真实 kick。缺失时退回 strong 列表 (口径同 burst)。
    """
    p = ROOT / "tmp" / "true_onsets.json"
    if p.exists():
        return [(d["t"], d["s"]) for d in json.loads(p.read_text(encoding="utf-8"))]
    return [(t, 1.0) for t in _load_env()[1]]


def _load_violin_accents():
    """小提琴持续乐句重音 (tmp/violin_phrases.json, [起,止,重音]) — v12。

    高潮段每段拖长音收在 1 个重点节拍上; 用户定调: 重音处镜头放慢曲线动帧 + 放大。
    缺失时返回空 (sva 层跳过, 其余语法不受影响)。
    """
    p = ROOT / "tmp" / "violin_phrases.json"
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8"))


def _twx_anchor(t0, t1, onsets):
    """TWX 冻结锚点选择 (v9, 用户反馈: 17s 后几处慢镜没对上音乐)。

    实测: 慢镜切点大多贴真实 kick (±2帧), 但 4 处偏离 —
    24.54 整段悬在两 kick 之间 (切点早 0.32s)、26.29/19.42/27.25 的 kick 在镜头
    中段 (最远 +0.076s)。v2 时代每拍闪帧掩盖了这些, deflash 后暴露。
    返回 (mode, anchor):
      cut  = onset 贴切点 (±0.05s≈±1.2帧) 或无 onset 信息 → 冻结在切点 (v7 现状, 大多数镜头)
      mid  = 镜头内 (t0+0.05, t1] 有 onset → 切点后恒速续放, 冻结在最强 onset, 再渐加速放出
      end  = 镜头内无 onset 但 t1+0.12s 内有 → 冲入减速, 冻结在出点 (正贴 kick)
    """
    win = [(t, s) for t, s in onsets if t0 - 0.05 <= t <= t1 + 0.12]
    if not win or any(abs(t - t0) <= 0.05 for t, _ in win):
        return "cut", t0
    in_shot = [(t, s) for t, s in win if t <= t1]
    if in_shot:
        t_best, _ = max(in_shot, key=lambda x: x[1])
        if t_best <= t1 - 0.09:      # 离出点 >2帧才有冻结→放出的空间
            return "mid", round(t_best, 3)
    return "end", round(t1, 3)


_SRC_DUR_CACHE = {}


def _src_dur(p):
    """源文件时长 (ffprobe format=duration, 带缓存)"""
    if str(p) not in _SRC_DUR_CACHE:
        import subprocess as _s
        _r = _s.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                     "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=60)
        try:
            _SRC_DUR_CACHE[str(p)] = float(_r.stdout.strip())
        except ValueError:
            _SRC_DUR_CACHE[str(p)] = 0.0
    return _SRC_DUR_CACHE[str(p)]


def _win_ok(src, off, dur):
    """候选替换窗口体检: 亮度非黑非白曝 + 有运动 (Nagi 教训: 盲选会选到黑场/卡)"""
    import numpy as np
    try:
        import subprocess as _s
        _r = _s.run(["ffmpeg", "-v", "error", "-ss", f"{off:.3f}", "-t", f"{dur + 0.1:.3f}",
                     "-i", src, "-vf", "scale=160:90", "-f", "rawvideo",
                     "-pix_fmt", "gray", "-"], capture_output=True, timeout=120)
        _n = len(_r.stdout) // (160 * 90)
        if _n < 3:
            return False
        _f = np.frombuffer(_r.stdout[:_n * 160 * 90],
                           dtype=np.uint8).reshape(_n, 90, 160).astype(np.float32)
        _lm = [float(x.mean()) for x in _f]
        if not all(18 <= v <= 225 for v in _lm):
            return False   # 真黑/过曝拒绝
        _mo = [float(np.abs(_f[i] - _f[i - 1]).mean()) for i in range(1, _n)]
        if max(_mo) > 40:
            return False   # 窗内含硬切 (合集类素材) 拒绝
        return float(np.mean(_mo)) >= 0.3
    except Exception:
        return False


def plan_effects(segs, run_dir=None, tag=None):
    """v4 = v3.1 骨架 (段落相对能量/轮换禁重复/呼吸留白) + 连续剂量 + 冲击层"""
    import statistics
    env_at, strong = _load_env()
    onsets = _load_onsets()
    build_en = [float(s.get("energy", 0.4)) for s in segs
                if s.get("mood") == "build" and float(s["start_time"]) < 27.0]
    drop_en = [float(s.get("energy", 0.4)) for s in segs if s.get("mood") == "drop"]
    b_med = statistics.median(build_en) if build_en else 0.4
    d_med = statistics.median(drop_en) if drop_en else 0.5
    d_q3 = statistics.quantiles(drop_en, n=4)[2] if len(drop_en) >= 4 else 0.6

    motion = {m["t0"]: m for m in json.loads(
        (ROOT / "tmp" / "shot_motion.json").read_text(encoding="utf-8"))}
    mags_all = sorted(m["mag"] for m in motion.values())
    m_p50 = mags_all[len(mags_all) // 2]
    drop_n = build_fx_n = fast_streak = hard_used = 0
    last_fx = None
    plan = []

    def _dir_fx(t0, light):
        """光流感知: 水平主导→方向条纹(角度=实测), 其他/静止→radial (v5)"""
        m = motion.get(round(t0, 3))
        if m and m["h"] and m["mag"] >= m_p50:
            amt = (14 if light else 24) + m["mag"] * (0.5 if light else 0.8)
            return f"fmb_dir{'_light' if light else ''}:{amt:.0f}:{m['ang'] % 180:.0f}"
        return "radial_soft"

    def _alt(*cands):
        for c in cands:
            if c != last_fx:
                return c
        return cands[0]

    for s in segs:
        t0 = round(float(s["start_time"]), 3)
        t1 = round(float(s.get("end_time", t0 + 0.25)), 3)
        spd = float(s.get("speed", 1.0))
        mood = s.get("mood", "build")
        en = float(s.get("energy", 0.4))
        fx = []
        if mood == "intro":
            fx = []
        elif t0 >= 27.0:
            if spd <= 0.55:
                fx = ["bloom_soft"]
        elif mood == "drop":
            drop_n += 1
            if spd <= 0.55:
                fx = ["bloom", "bokeh"] if (drop_n % 2 == 0 and en >= d_med) else ["bloom"]
            elif en >= d_q3 and spd >= 1.5:
                if 22.1 <= t0 <= 24.6 and hard_used < 3:
                    fx = ["badtv_hard"]; hard_used += 1
                else:
                    fx = [_alt("badtv", "radial")]
            elif drop_n % 9 == 4:
                fx = ["glitch"]
            elif spd >= 1.1:
                fast_streak += 1
                if fast_streak % 2 == 1:
                    fx = [_dir_fx(t0, light=False)]
            if fx and fx != ["fmb"]:
                fast_streak = 0
        else:  # build
            if spd >= 1.5 and en >= b_med:
                build_fx_n += 1
                cyc = build_fx_n % 4
                if cyc == 1:
                    fx = [_dir_fx(t0, light=True)]
                elif cyc == 3:
                    fx = ["badtv_light"] if en >= max(b_med, d_med * 0.9) else ["radial_soft"]
            elif spd <= 0.55:
                fx = ["bloom_soft"]
        if fx:
            last_fx = fx[-1]
            dose = 0.65 + 0.7 * env_at(t0)   # 连续密度曲线
            entry = {"t0": t0, "t1": t1, "fx": fx, "dose": round(dose, 3),
                     "en": round(en, 2), "env": round(env_at(t0), 2)}
            # v6: 决斗变速停顿慢镜 → Twixtor 光流重渲 (ffmpeg 重复帧最显瑕疵处)
            if spd <= 0.55 and 12.7 <= t0 and s.get("source_file"):
                entry["twx"] = {"src": s["source_file"],
                                "sin": float(s.get("source_start", 0)),
                                "spd": spd,
                                "zp": s.get("zoompan_effect") or "push"}
                # v9: 冻结点锚到真实 kick (只动 15s 后投诉区, 之前已验收镜头不动)
                if t0 >= 15.0:
                    mode, anc = _twx_anchor(t0, t1, onsets)
                    entry["twx"]["anchor_mode"] = mode
                    if mode != "cut":
                        entry["twx"]["anchor"] = anc
            plan.append(entry)
    # v12: 小提琴拖长音重音 (用户定调: 重音处镜头放慢曲线动帧 + 放大) —
    # 每段拖长音收在 1 个重点节拍上; 引擎已把多数重音对到慢镜 (13.46/15.29/19.0/20.83/22.67/26.29
    # 的切点冻结都在重音 ±0.4 帧内), 只补真正无慢镜覆盖的重音 (16.78)。
    for _ps, _pe, acc in _load_violin_accents():
        if not (12.7 <= acc <= 27.5):
            continue
        seg = next((s for s in segs if float(s["start_time"]) <= acc < float(s["end_time"])), None)
        if seg is None or not seg.get("source_file"):
            continue
        t0 = round(float(seg["start_time"]), 3)
        t1 = round(float(seg.get("end_time", t0 + 0.25)), 3)
        entry = next((e for e in plan if abs(e["t0"] - t0) < 0.05), None)
        if entry is None:
            entry = {"t0": t0, "t1": t1, "fx": [], "dose": 1.0, "en": 0.5, "env": 0.5}
            plan.append(entry)
            plan.sort(key=lambda e: e["t0"])
        if "twx" in entry or "rescue" in entry or round(t0, 3) in RESCUE_MAP:
            continue   # 已有慢镜/救援语法
        # 邻接覆盖: 重音落点 ±60ms 内有慢镜切点冻结 → 已覆盖
        if any(abs(e["t0"] - acc) <= 0.06 or (e["t0"] <= acc <= e["t1"])
               for e in plan if "twx" in e):
            continue
        entry["twx"] = {"src": seg["source_file"], "sin": float(seg.get("source_start", 0)),
                        "spd": 0.55, "zp": "zoom_in", "sva": acc}
        if abs(acc - t0) <= 0.05:                     # 重音贴切点 → 冻结在切点
            entry["twx"]["anchor_mode"] = "cut"
        elif acc <= t1 - 0.09:                        # 重音在镜头中段 → 冻结在重音
            entry["twx"]["anchor_mode"] = "mid"
            entry["twx"]["anchor"] = round(acc, 3)
        else:                                         # 重音贴出点 → 冲入末尾冻结
            entry["twx"]["anchor_mode"] = "end"
            entry["twx"]["anchor"] = t1
    # v12.1: 20s 后两个无慢镜覆盖的重音 (精细检测 0.85/0.75 双阈值并集) — 显式计划:
    # 20.25 镜头底片含引擎烘的叠化转场 (庭院→alya), 源替换会毁掉转场 → 底片重定时
    # (Twixtor 对底片自身窗口做慢曲线, 叠化保留, 冻结在 20.468 重音=叠化中点);
    # 23.958 救援镜头底片是卡+黑场, 用救援源猫2@109 重 timed, 冻结在 24.16 kick,
    # rush-out 峰值落在 24.52 第二重音/出点。两者都 zoom_in 1.12 (用户定调: 放大)。
    SVA_PLAN = {20.25: ("base", 20.468), 23.958: ("rescue_src", 24.16)}
    for _t0p, (_kind, acc) in SVA_PLAN.items():
        entry = next((e for e in plan if abs(e["t0"] - _t0p) < 0.05), None)
        if entry is None or "twx" in entry or "rescue" in entry:
            continue
        t0, t1 = entry["t0"], entry["t1"]
        if _kind == "base":
            if run_dir is None or tag is None:
                continue
            _src = (run_dir / f"{tag}_lut.mp4").resolve().as_posix()
            _sin = t0                      # 片内偏移=镜头起点, 底片窗口自引用
        else:
            _hit = RESCUE_MAP.get(round(t0, 3))
            if _hit is None:
                continue
            _src, _sin = _hit[0], _hit[1]
        entry["twx"] = {"src": _src, "sin": float(_sin), "spd": 0.55, "zp": "zoom_in",
                        "sva": acc}
        if acc <= t1 - 0.09:
            entry["twx"]["anchor_mode"] = "mid"
            entry["twx"]["anchor"] = round(acc, 3)
        else:
            entry["twx"]["anchor_mode"] = "end"
            entry["twx"]["anchor"] = t1
    # v17: 语义选效果 (#11, 离线降级) — CV 场景特征 (tmp/shot_scenes_raw.json,
    # Farneback 运动/Canny 边缘/肤色代理; VLM 额度失效后的降级方案)。
    # 规则: closeup (有人物+非高动) → 冲击类换柔光 (脸+冲击畸变=丑);
    #       battle (高动 top10%) → 全柔光换冲击。其余镜头维持速度/能量启发式。
    _scp = ROOT / "tmp" / "shot_scenes_raw.json"
    if _scp.exists():
        _sc = json.loads(_scp.read_text(encoding="utf-8"))
        _mos = sorted(v["motion"] for v in _sc.values())
        _p70 = _mos[int(len(_mos) * 0.7)] if _mos else 99.0
        _n_sem = 0
        for e in plan:
            _f = _sc.get(str(round(e["t0"], 3)))
            if not _f or not e["fx"]:
                continue
            if _f["skin"] >= 0.30 and _f["motion"] <= _p70:
                # closeup: 冲击类 (badtv/radial/fmb 族) → 柔光
                newfx = []
                for f in e["fx"]:
                    if f.startswith(("badtv", "fmb")):
                        f = "bokeh"
                    elif f in ("radial", "radial_soft"):
                        f = "bloom_soft"
                    newfx.append(f)
                if newfx != e["fx"]:
                    e["fx"] = newfx
                    _n_sem += 1
            elif _f["motion"] >= 2.4 and all(
                    f in ("bloom", "bokeh", "bloom_soft") for f in e["fx"]):
                e["fx"] = ["radial" for f in e["fx"]]   # battle 高动 → 冲击
                _n_sem += 1
        print(f"语义选效果 (v17): {_n_sem} 处调整")
    # v19: 源多样化替换 (用户反馈: 镜头重复出境) — top5 源贡献 62% 镜头
    # (独自升级5 19镜/5.7s源被切碎撒全片), 同场景反复出现。将超额 S 镜替换为
    # manifest 未使用源 (8 文件 ~80s 新素材) 的实测有效内容: twx 平速曲线覆盖
    # 底片 + 保留原 fx/zoompan。每源镜头数上限 9, 重音锚点镜头不动。
    _MAX_PER_SRC = 9
    _src_dur_cache = {}
    _violin_t = [a for _p0, _p1, a in _load_violin_accents()]
    # 每源已用源时间区间表 (供替换窗口避让)
    _spans_by_src = {}
    for _seg in segs:   # v19 修正: 按全量 segs 统计 (无 fx 镜头同样是重复内容)
        if not _seg.get("source_file"):
            continue
        _bn = os.path.basename(_seg["source_file"].replace(chr(92), "/"))
        _s0 = float(_seg.get("source_start", 0))
        _s1 = _s0 + (float(_seg["end_time"]) - float(_seg["start_time"])) * float(_seg.get("speed", 1.0))
        _t0s = round(float(_seg["start_time"]), 3)
        _e0 = next((e for e in plan if abs(e["t0"] - _t0s) < 0.05), None)
        _spans_by_src.setdefault(_bn, []).append((_s0, _s1, _t0s, _e0, _seg))
    _over = {bn: es for bn, es in _spans_by_src.items() if len(es) > _MAX_PER_SRC}
    if _over:
        _n_rep = 0
        for _bn in sorted(_over, key=lambda b: -len(_over[b])):
            _es = _over[_bn]
            _excess = len(_es) - _MAX_PER_SRC
            _cands = []
            for _s0, _s1, _t0s, e, seg in _es:
                if e is not None and ("twx" in e or "rescue" in e):
                    continue
                if _t0s in RESCUE_MAP:
                    continue
                if any(abs(a - _t0s) <= 0.30 for a in _violin_t):
                    continue   # 小提琴重音锚定镜头不动
                if e is None:
                    e = {"t0": _t0s, "t1": round(float(seg["end_time"]), 3),
                         "fx": [], "dose": 1.0, "en": 0.5, "env": 0.5}
                    plan.append(e)
                    _spans_by_src[_bn][-1] = (_spans_by_src[_bn][-1][0],
                                              _spans_by_src[_bn][-1][1],
                                              _t0s, e, seg)
                _cands.append((e, seg))
            _cands.sort(key=lambda x: x[0]["t0"])
            for e, seg in _cands[:_excess]:
                _spd = float(seg.get("speed", 1.0))
                _dur = e["t1"] - e["t0"]
                _span = _dur * _spd
                _srcf = seg["source_file"]
                _sin0 = float(seg.get("source_start", 0))
                if _bn not in _src_dur_cache:
                    _src_dur_cache[_bn] = _src_dur(_srcf)
                _sdur = _src_dur_cache[_bn]
                if _sdur <= _span + 1.0:
                    continue   # 源太短无处可移
                _others = [(a, b) for a, b, t0x, ex, sg in _spans_by_src[_bn]
                           if abs(t0x - e["t0"]) > 0.05]
                _got = None
                for _delta in (1.6, -1.6, 2.4, -2.4, 3.2, -3.2, 4.0, -4.0, 4.8, -4.8, 5.6, -5.6):
                    _cand = _sin0 + _delta * _spd
                    if _cand < 0.2 or _cand + _span > _sdur - 0.15:
                        continue
                    if any(min(_cand + _span, b) - max(_cand, a) > 0.3 for a, b in _others):
                        continue   # 与其他镜头的源窗重叠 = 还是重复
                    if not _win_ok(_srcf, _cand, _span):
                        continue
                    _got = (_srcf, round(_cand, 3))
                    break
                if _got is None:
                    continue
                e["twx"] = {"src": _got[0].replace(chr(92), "/"), "sin": _got[1], "spd": _spd,
                            "zp": "zoom_in", "anchor_mode": "flat", "repl": _bn[-12:]}
                e.setdefault("fx", e.get("fx", []))
                _n_rep += 1
        if _n_rep:
            plan.sort(key=lambda e: e["t0"])
        print(f"源多样化替换 (v19): {_n_rep} 处 ← {[b[-10:] for b in _over]}")
    # v22 情绪调色 — 默认关闭 (参照集实测: 顶尖漫剪整体冷暖中性 ±11, 不做全局段落
    # 冷暖偏移; 真语法 = 高对比+高饱和+冷阴影, 由分段调整层实现)。复开: AEKV_GRADE=1
    if os.environ.get("AEKV_GRADE", "0") == "1":
        for e in plan:
            _seg = next((s for s in segs if abs(round(float(s["start_time"]), 3) - round(e["t0"], 3)) < 0.05), None)
            _mood = (_seg or {}).get("mood", "build")
            if _mood == "drop":
                e["grade"] = {"r": 6, "b": -6}      # 高潮暖
            elif _mood == "build":
                e["grade"] = {"r": -4, "b": 5}      # 蓄力冷
    return plan



def plan_bursts(plan, strong):
    """转场冲击层: 强鼓点上的切点 → 顶层 2-4 帧 burst (drop radial / build badtv)

    v7.1 减密 (用户反馈: 15s 后连续闪动) — 底片闪帧已由 deflash 减到 ~1/2s,
    burst 也收紧: 读 tmp/kept_events.json 避开保留闪帧(±0.35s 不叠加),
    间距 0.8→1.8s, drop cap 12→5 / build 6→3, 让冲击回归乐句重音密度。
    """
    cuts = [p["t0"] for p in plan if p["t0"] > 0.3]
    on_strong = lambda t: any(abs(t - st) <= 0.080 for st in strong)
    kept_f = [e["t"] for e in json.loads(
        (ROOT / "tmp/kept_events.json").read_text(encoding="utf-8")).get("kept", [])]
    near_kept = lambda t: any(abs(t - k) < 0.35 for k in kept_f)
    bursts = []
    for zone, cap, gap, rec, dur in (("drop", 5, 1.8, "burst_radial", 0.15),
                                     ("build", 3, 2.2, "burst_badtv", 0.10)):
        picked = []
        for t in cuts:
            if zone == "drop" and not (12.7 <= t < 27.0):
                continue
            if zone == "build" and not (0.3 <= t < 12.7):
                continue
            if not on_strong(t) or near_kept(t):
                continue
            if picked and t - picked[-1] < gap:   # 最小间隔防连爆
                continue
            picked.append(t)
            if len(picked) >= cap:
                break
        for t in picked:
            t_eff = t + 0.13  # 闪帧后起爆 (v4.2: 落在纯色帧上的burst无效)
            bursts.append({"t0": round(t_eff, 3), "t1": round(t_eff + dur, 3),
                           "fx": [rec], "dose": 1.0, "en": 1, "env": 1})
    return bursts


def build_jsx(run_dir: Path, tag: str, plan, bursts):
    vin = (run_dir / f"{tag}_lut.mp4").resolve().as_posix()
    aep = (run_dir / "polish" / "master.aep").as_posix()
    def _fx_js(spec, dose):
        dyn = None
        if spec.startswith("fmb_dir") and ":" in spec:
            base, amt, ang = spec.split(":")
            dyn = [("CC Force Motion Blur-0001", float(amt)),
                   ("CC Force Motion Blur-0003", float(ang))]
            spec = base
        r = RECIPES[spec]
        if dyn:
            return {"m": r["m"], "ps": [[p, round(v * dose, 3)] for p, v in dyn], "env": False}
        ps = json.dumps([[p, round(v * dose, 4)] for p, v in r["ps"]],
                        separators=(",", ":"))
        return {"m": r["m"], "ps": json.loads(ps), "env": r["env"]}
    def _twx_curve(t0, t1, sin, spd, mode="cut", anchor=None):
        """连续速度曲线关键帧 [[comp_time, speed_pct], ...]

        v7 修复卡点漂移 (用户反馈: 曲线版卡点对不上):
        ① 相位锚 — startTime=t0-sin/spd 按恒速校准, 曲线版预卷段速度若≠spd,
          积分模型下起点漂移 sin×(v0/spd-1) (v1 用 123% 开头 → 偏 0.62s)。
          预卷段写两个恒速 spd 关键帧钉死相位 (对积分/逐点模型都成立)。
        ② 曲线反转 — 冻结对齐切点 (音乐坠落点画面速停), 向下一拍渐加速放出。
        v9 锚点升级 (用户反馈: 17s 后几处慢镜没对上音乐, 见 _twx_anchor):
        三模式, 平均速度恒=spd (归一), 预卷相位锚不受曲线形状影响:
          cut  — 冻结在切点 (原行为): profile @ [t0, t1]
          mid  — 切点恒速续放 → 出点前 1 帧急减速 → 冻结在 anchor (真实 kick) → 放出;
                 恒速段恰积 spd×fa, profile 段归一后仍积 spd×(1-fa), k 与 cut 模式相同
          end  — 反转 profile 冲入 → 冻结在出点 (正贴 t1 后 ≤0.12s 的 kick);
                 反转不改变梯形积分, k 与 cut 模式相同
        """
        dur = t1 - t0
        fr = [p[0] for p in TWX_SPEED_PROFILE]
        rs = [p[1] for p in TWX_SPEED_PROFILE]
        prof_integ = sum((rs[i] + rs[i + 1]) / 2 * (fr[i + 1] - fr[i])
                         for i in range(len(fr) - 1))
        k = spd / prof_integ   # 归一使曲线段平均速度=spd (时长占比梯形积分)
        t_pre = t0 - sin / spd
        eps = 1.0 / 24    # 锚末端留 1 帧过渡到曲线首值, 起点误差 <0.2 帧
        pre = [[round(t_pre, 3), spd * 100], [round(t0 - eps, 3), spd * 100]]
        if mode == "end":
            pts = sorted(((1.0 - f, r) for f, r in zip(fr, rs)))
            return pre + [[round(t0 + f * dur, 3), round(r * k * 100, 2)]
                          for f, r in pts]
        if mode == "flat":
            # v19 源多样化替换: 平速覆盖层 (源片段按镜头速度预烘焙, 无慢曲线)
            return pre + [[round(t0, 3), spd * 100], [round(t1, 3), spd * 100]]
        if mode == "mid" and anchor is not None and t0 < anchor < t1:
            a = min(max(anchor, t0 + eps), t1 - eps)
            # 1帧减速过渡吃掉 ≤0.008s 源内容 (平均速度 -4~-8%) → 出点内容早 0.2 源帧,
            # 亚帧级, 与 v7 起点锚 "<0.2帧" 同口径; 冻结时刻 (踩拍) 是精确的
            return pre + \
                [[round(t0, 3), spd * 100],
                 [round(a - eps, 3), spd * 100]] + \
                [[round(a + f * (t1 - a), 3), round(r * k * 100, 2)]
                 for f, r in zip(fr, rs)]
        return pre + [[round(t0 + f * dur, 3), round(r * k * 100, 2)]
                      for f, r in zip(fr, rs)]

    def _shot_js(s):
        d = {"t0": s["t0"], "t1": s["t1"], "r": [_fx_js(f, s["dose"]) for f in s["fx"]]}
        if "grade" in s:
            d["grade"] = s["grade"]
        if "drift" in s:
            d["drift"] = s["drift"]
        if "rescue" in s:
            d["rescue"] = s["rescue"]
        if "twx" in s:
            d["twx"] = {"src": s["twx"]["src"].replace(chr(92), "/"),
                        "sin": s["twx"]["sin"], "spd": s["twx"]["spd"], "zp": s["twx"]["zp"],
                        "curve": _twx_curve(s["t0"], s["t1"], s["twx"]["sin"], s["twx"]["spd"],
                                            s["twx"].get("anchor_mode", "cut"),
                                            s["twx"].get("anchor"))}
        return d
    shots_js = json.dumps([_shot_js(s) for s in plan], separators=(",", ":"))
    bursts_js = json.dumps(
        [{"t0": b["t0"], "t1": b["t1"], "r": [_fx_js(f, b["dose"]) for f in b["fx"]]}
         for b in bursts], separators=(",", ":"))
    return f"""
(function(){{
  var rep = "start";
  var DECAY = {ENV_DECAY_S}, TAIL = {ENV_TAIL};
  function applyGrade(ly, g) {{
    try {{
      var fx = ly.property("Effects").addProperty("ADBE Color Balance");
      fx.property(1).setValue(g.r);   // 红色平衡 (0 中心, ±100)
      fx.property(3).setValue(g.b);   // 蓝色平衡
    }} catch (ge) {{ rep += "|GRADE:" + ge.toString(); }}
  }}
  function applyFx(ly, r, t0) {{
    var fx = ly.property("Effects").addProperty(r.m);
    for (var k = 0; k < r.ps.length; k++) {{
      var pn = r.ps[k][0], v = r.ps[k][1];
      try {{
        if (r.env) {{
          var pr = fx.property(pn);
          pr.setValueAtTime(t0, v);          // 切点满剂量砸入
          pr.setValueAtTime(t0 + DECAY, v * TAIL);  // 3帧衰减
        }} else {{
          fx.property(pn).setValue(v);
        }}
      }} catch(ep) {{ rep += "|P:" + pn; }}
    }}
  }}
  try {{
    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
    app.newProject();
    var imp = app.project.importFile(new ImportOptions(new File("{vin}")));
    var comp = app.project.items.addComp("MASTER", imp.width, imp.height,
        1.0, imp.duration, imp.frameRate);
    var base = comp.layers.add(imp);
    base.name = "BASE";
    var shots = {shots_js};
    var srcCache = {{}};
    for (var i = 0; i < shots.length; i++) {{
      var sh = shots[i];
      var ly;
      if (sh.rescue) {{
        // v10.2 垃圾窗口救援层 — 预烘焙恒速源片段 (setpts 到镜头速度), 1:1 播放 + push 复刻
        if (!srcCache[sh.rescue.src]) {{
          srcCache[sh.rescue.src] = app.project.importFile(new ImportOptions(new File(sh.rescue.src)));
        }}
        var rsim = srcCache[sh.rescue.src];
        ly = comp.layers.add(rsim);
        ly.startTime = sh.t0;
        ly.inPoint = sh.t0; ly.outPoint = sh.t1;
        var rbs = Math.max(comp.width / rsim.width, comp.height / rsim.height) * 100;
        var rsc = ly.property("Scale");
        rsc.setValueAtTime(sh.t0, [rbs, rbs]);
        rsc.setValueAtTime(sh.t1, [rbs * sh.rescue.push, rbs * sh.rescue.push]);
        ly.name = "RS" + i;
      }} else if (sh.twx) {{
        // v6 Twixtor 层: 源素材 + 光流慢动作 + 缩放关键帧复刻推镜
        if (!srcCache[sh.twx.src]) {{
          srcCache[sh.twx.src] = app.project.importFile(new ImportOptions(new File(sh.twx.src)));
        }}
        var sim = srcCache[sh.twx.src];
        ly = comp.layers.add(sim);
        ly.startTime = sh.t0 - (sh.twx.sin / sh.twx.spd);  // (t-startTime)×spd=sin @t0 → 含t0项
        ly.inPoint = sh.t0; ly.outPoint = sh.t1;
        var bs = Math.max(comp.width / sim.width, comp.height / sim.height) * 100;
        var zoomEnd = (sh.twx.zp == "zoom_in") ? 1.12 : 1.09;
        var sc = ly.property("Scale");
        sc.setValueAtTime(sh.t0, [bs, bs]);
        sc.setValueAtTime(sh.t1, [bs * zoomEnd, bs * zoomEnd]);
        var tfx = ly.property("Effects").addProperty("Twixtor 45");
        tfx.property("Twixtor 45-0004").setValue(1);
        // v7 连续速度曲线: 预卷恒速锚(钉相位) + 冻结在切点→渐加速放出(平均=spd)
        for (var c = 0; c < sh.twx.curve.length; c++) {{
          tfx.property("Twixtor 45-0005").setValueAtTime(sh.twx.curve[c][0], sh.twx.curve[c][1]);
        }}
        ly.name = "TWX" + i;
      }} else {{
        ly = comp.layers.add(imp);
        ly.inPoint = sh.t0; ly.outPoint = sh.t1;
        ly.name = "S" + i;
        if (sh.drift) {{   // v10.1: 死帧段慢推镜 — 静止画面给节拍内的缓慢运动
          var dsc = ly.property("Scale");
          dsc.setValueAtTime(sh.t0, [100, 100]);
          dsc.setValueAtTime(sh.t1, [100 * sh.drift, 100 * sh.drift]);
        }}
      }}
      if (sh.grade) applyGrade(ly, sh.grade);
      for (var j = 0; j < sh.r.length; j++) applyFx(ly, sh.r[j], sh.t0);
    }}
    var bursts = {bursts_js};
    // v23 分段调色调整层 (参照集实测语法: 高对比 151 + 高饱和 99.6 + 冷阴影):
    var sections = [
      {{t0: 3.3,  t1: 12.7, bc: 30, vib: -35}},
      {{t0: 12.7, t1: 27.0, bc: 12, vib: 25}}
    ];
    for (var gi = 0; gi < sections.length; gi++) {{
      var gs = sections[gi];
      var sol = comp.layers.addSolid([0.5, 0.5, 0.5], "GRADE" + gi, comp.width, comp.height, 1.0);
      sol.adjustmentLayer = true;
      sol.inPoint = gs.t0; sol.outPoint = gs.t1;
      sol.moveToBeginning();
      var bc = sol.property("Effects").addProperty("ADBE Brightness & Contrast");
      bc.property(2).setValue(gs.bc);
      var vb = sol.property("Effects").addProperty("ADBE Vibrance");
      vb.property(1).setValue(gs.vib);
    }}
    for (var b = 0; b < bursts.length; b++) {{
      var bu = bursts[b];
      var bl = comp.layers.add(imp);
      bl.inPoint = bu.t0; bl.outPoint = bu.t1;
      bl.name = "BURST" + b;
      for (var j2 = 0; j2 < bu.r.length; j2++) applyFx(bl, bu.r[j2], bu.t0);
    }}
    app.project.save(new File("{aep}"));
    rep += "|saved layers=" + comp.numLayers;
  }} catch(e) {{ rep += "|FATAL:" + e.toString(); }}
  var f = new File("{(ROOT / 'tmp' / 'ae_master_build.txt').as_posix()}");
  f.encoding = "UTF-8"; f.open("w"); f.write(rep); f.close();
}})()
"""


def _parse_args():
    """argparse 包装 — 位置参数契约 (<run_dir> <tag>) 完全向后兼容。

    2026-09-07 修复: 原实现裸读 sys.argv[1]/[2], 导致
    agents/mastercut_agent.py 以 --input-video/--effects-json 等 flag 调用时,
    sys.argv[1]="--input-video" 撞白名单 → 直接 exit(1), 特效注入链路
    从建成起就从未真正执行过。
    """
    import argparse
    ap = argparse.ArgumentParser(
        prog="build_master_polish.py",
        description="镜头级 AE 精修 — 拍点包络 + 连续密度曲线 + 转场冲击层",
        epilog="示例: python scripts/build_master_polish.py output/unified_run53 run53")
    ap.add_argument("run_dir", help="run 目录, 白名单 unified_run\\d+ (可带 output/ 前缀)")
    ap.add_argument("tag", help="tag, 白名单 run\\d+")
    ap.add_argument("--effects-json", dest="effects_json", default=None,
                    help="visual_effect_schema.json 兼容配置; 传入时取代内部 plan_effects 的 fx 规划")
    ap.add_argument("--edl", dest="edl", default=None,
                    help="edl.json 路径; 提供时先过 lint 契约闸门, 并在无 --effects-json 时用其 effects 轨")
    ap.add_argument("--dry-run", action="store_true",
                    help="只生成 plan + JSX 并落盘, 不调用 AE Bridge (离线验证用)")
    ap.add_argument("--hl-safe", action="store_true",
                    help=f"高光安全档: radial/radial_soft 基数 ×{0.7} (对齐过冲根因, "
                         f"默认关闭, 视觉复验后再定默认)")
    return ap.parse_args()


def main():
    # 路径安全 (2026-09-05): argv 白名单校验, 目录名重建自常量而非拼接用户输入
    import re as _re
    args = _parse_args()
    _raw = str(args.run_dir).replace("\\", "/").removeprefix("output/")
    if not _re.fullmatch(RUN_DIR_PATTERN, _raw):
        print(f"[ERR] 非法 run 目录名(白名单 unified_run<N> | unified_r1_fixed_v<N>): {_raw}")
        sys.exit(2)
    if not _re.fullmatch(TAG_PATTERN, str(args.tag)):
        print(f"[ERR] 非法 tag(白名单 run\\d+): {args.tag}")
        sys.exit(2)
    run_dir = ROOT / "output" / _raw
    tag = args.tag
    if args.hl_safe:
        # 提前于 plan/build_jsx 生效(它们在调用点读取 RECIPES)
        for _rk in ("radial", "radial_soft"):
            RECIPES[_rk]["ps"] = [
                (p, round(v * HL_SAFE_RADIAL_SCALE, 1)) for p, v in RECIPES[_rk]["ps"]
            ]
        print(f"[hl-safe] radial 基数 ×{HL_SAFE_RADIAL_SCALE} → "
              f"radial={RECIPES['radial']['ps'][0][1]} "
              f"radial_soft={RECIPES['radial_soft']['ps'][0][1]} (过冲根因修正, 待渲染复验)")
    pr_p = run_dir / "production_report.json"
    if not pr_p.exists():
        print(f"[ERR] 缺前置产物 {pr_p} — 需先跑 unified_edit 生成 production_report")
        sys.exit(2)
    pr = json.loads(pr_p.read_text(encoding="utf-8"))
    segs = pr["script"]["segments"]

    # Step1: --edl 数据契约闸门(读+lint, fail-fast)。仅显式传入才启用 → 无 --edl 时零行为变化(BACKWARD)
    _edl = None
    if args.edl:
        from scripts.edl import load_edl
        _edl_p = Path(args.edl)
        if not _edl_p.exists():
            print(f"[ERR] --edl 不存在: {_edl_p}")
            sys.exit(2)
        try:
            _edl = load_edl(_edl_p)          # lint 失败抛 ValueError
        except ValueError as _e:
            print(f"[ERR] EDL 契约校验失败: {_e}")
            sys.exit(2)

    inj_report = None
    _eff = None
    if args.effects_json:                              # 优先级1: 显式文件(向后兼容)
        ej = Path(args.effects_json)
        if not ej.exists():
            print(f"[ERR] --effects-json 不存在: {ej}")
            sys.exit(2)
        _eff = json.loads(ej.read_text(encoding="utf-8"))
    elif _edl is not None and _edl.get("effects"):     # 优先级2: EDL effects 轨(Step1 桥)
        _eff = _edl["effects"]
    if _eff is not None:
        if isinstance(_eff, dict):
            _eff = _eff.get("effects") or _eff.get("effect_configs") or [_eff]
        plan, bursts, inj_report = schema_effects_to_plan(_eff)
        # 慢镜(twx)与垃圾窗救援(rescue)是已验收观感的一部分, 且 schema 无对应可注入类型
        # (twixtor 已标为不可外部注入) → 从 base plan 携带过来, fx 置空避免重复上效果。
        base = plan_effects(segs, run_dir, tag)
        carried = []
        for b in base:
            if not any(k in b for k in ("twx", "rescue")):
                continue
            c = {"t0": b["t0"], "t1": b["t1"], "fx": [], "dose": b.get("dose", 1.0)}
            for k in ("twx", "rescue", "grade", "drift"):
                if k in b:
                    c[k] = b[k]
            carried.append(c)
        plan = sorted(plan + carried, key=lambda x: x["t0"])
        inj_report["carried_from_base"] = len(carried)
        print(f"[schema注入] 输入 {inj_report['input_count']} 条 → "
              f"plan {inj_report['plan_count']} + burst {inj_report['burst_count']} "
              f"= 可执行 {inj_report['applied_count']} 条; 携带 base 慢镜/救援 {len(carried)} 条")
        if inj_report["unmapped_count"]:
            print(f"[schema注入] 无法映射 {inj_report['unmapped_count']} 条 "
                  f"({len(inj_report['unmapped_types'])} 种类型) — 不会静默丢弃, 详见报告:")
            for _t, _v in sorted(inj_report["unmapped_types"].items(),
                                 key=lambda kv: -kv[1]["count"]):
                print(f"    {_t}: {_v['count']} 条 — {_v['reason']}")
        if inj_report["skipped_count"]:
            print(f"[schema注入] 跳过 {inj_report['skipped_count']} 条 (时间区间非法/未知类型)")
        (ROOT / "tmp").mkdir(exist_ok=True)
        (ROOT / "tmp" / "effects_injection_report.json").write_text(
            json.dumps(inj_report, ensure_ascii=False, indent=1), encoding="utf-8")
        if inj_report["applied_count"] == 0:
            # 零可执行特效时继续渲染 = 产出一个看起来成功但什么也没加的片子 (假绿灯)
            print("[ERR] schema 注入后无可执行特效 — 拒绝空渲染")
            sys.exit(3)
    else:
        plan = plan_effects(segs, run_dir, tag)
        bursts = None
    ov_p = ROOT / "tmp" / "dose_overrides.json"
    if ov_p.exists():
        ov = {float(k): v for k, v in json.loads(ov_p.read_text(encoding="utf-8")).items()}
        for s in plan:
            for kt, m in ov.items():
                if abs(s["t0"] - kt) < 0.05:
                    s["dose"] = round(min(s["dose"] * m, 3.5), 3)
    # v15 顶点帧实验 — 默认关闭: 实测把定格内容移到运动顶点后, 0.35x 缓爬期
    # 仍可见滑动 (MAD 1-2 → 12-16), 停止变糊, 用户感知为"没卡准重音"。
    # 恢复验收观感 = 保持引擎所选平静姿态的脆冻结。要复开: AEKV_IMPACT_SHIFT=1
    if os.environ.get("AEKV_IMPACT_SHIFT", "0") == "1":
        # v15: 定格内容升级 — 冻结帧 = 动作顶点帧 (源窗口运动能量峰值), 音乐锚点一帧不动。
        # 原理: 冻结瞬间显示的源时刻 = sin + freeze_offset (cut=0 / mid=(锚-t0)*spd / end=dur*spd),
        # 平移 sin 让"顶点帧"落到冻结点; 叠化底片重定时镜头 (20.25) 除外 — 转场内容固定。
        import subprocess as _sp3
        import numpy as np

        def _src_meta(p):
            _pr = _sp3.run(["ffprobe", "-v", "error", "-show_entries",
                            "stream=r_frame_rate:format=duration", "-of", "csv=p=0", str(p)],
                           capture_output=True, text=True, timeout=60)
            _line = _pr.stdout.strip().splitlines()[0]
            _num, _den = _line.split(",")[0].split("/")
            _fps = float(_num) / float(_den)
            _dur = 0.0
            for _ln in _pr.stdout.strip().splitlines():
                _parts = _ln.split(",")
                if len(_parts) >= 2 and _parts[0] == _line.split(",")[0]:
                    try:
                        _dur = float(_parts[-1])
                        break
                    except ValueError:
                        pass
            if _dur <= 0:
                _pr2 = _sp3.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(p)], capture_output=True, text=True, timeout=60)
                try:
                    _dur = float(_pr2.stdout.strip())
                except ValueError:
                    _dur = 0.0
            return _fps, _dur

        def _motion_argmax(src, sin, span_lo, span_hi, fps, nfr):
            """返回 [sin+span_lo, sin+span_hi] 内运动能量最高帧的源时刻 (无数据→None)"""
            _d0 = max(0.0, sin + span_lo - 0.15)
            _r = _sp3.run(["ffmpeg", "-v", "error", "-ss", f"{_d0:.3f}",
                           "-t", f"{(sin + span_hi) - _d0 + 0.1:.3f}", "-i", str(src),
                           "-vf", "scale=240:135", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                          capture_output=True, timeout=180)
            _n = len(_r.stdout) // (240 * 135)
            if _n < 4:
                return None
            _fr = np.frombuffer(_r.stdout[:_n * 240 * 135],
                                dtype=np.uint8).reshape(_n, 135, 240).astype(np.float32)
            _mo = np.array([0.0] + [float(np.abs(_fr[i] - _fr[i - 1]).mean()) for i in range(1, _n)])
            _mo = np.convolve(_mo, np.ones(3) / 3, mode="same")
            _lo_i = max(2, int(round((sin + span_lo - _d0) * fps)))
            _hi_i = min(_n - 1, int(round((sin + span_hi - _d0) * fps)))
            if _hi_i - _lo_i < 3:
                return None
            _seg = _mo[_lo_i:_hi_i + 1]
            if float(_seg.max()) - float(np.median(_mo)) < 2.0:
                return None   # 平坦场景 (对话/静帧) — 无顶点可言
            return round(_d0 + (_lo_i + int(_seg.argmax())) / fps, 3)

        _shifted = []
        for _s in plan:
            if "twx" not in _s:
                continue
            _t = _s["twx"]
            if str(_t["src"]).endswith("lut.mp4"):
                continue   # 底片重定时 (叠化转场) — 内容固定不平移
            _t0, _t1 = _s["t0"], _s["t1"]
            _spd, _sin = _t["spd"], float(_t["sin"])
            _dur = _t1 - _t0
            _mode = _t.get("anchor_mode", "cut")
            if _mode == "mid":
                _foff = (_t["anchor"] - _t0) * _spd
            elif _mode == "end":
                _foff = _dur * _spd
            else:
                _foff = 0.0
            _fps, _sdur = _src_meta(_t["src"])
            if _fps <= 0:
                continue
            _apex = _motion_argmax(_t["src"], _sin, -0.2, _dur * _spd + 0.45, _fps, None)
            if _apex is None:
                continue
            _cur = _sin + _foff
            if abs(_apex - _cur) < 0.08:
                continue   # 顶点≈当前冻结内容 — 不动
            _sin_new = min(max(_apex - _foff, _sin - 0.3), _sin + 0.45)
            _sin_new = max(0.05, min(_sin_new, _sdur - _dur * _spd - 0.35))
            if abs(_sin_new - _sin) < 0.03:
                continue
            _t["sin"] = round(_sin_new, 3)
            _t["impact_shift"] = round(_sin_new - _sin, 3)
            _shifted.append((round(_t0, 2), _mode, round(_apex, 2), _t["impact_shift"]))
        if _shifted:
            print("定格顶点平移 (v15): " + ", ".join(
                f"t0={t} {m}@apex{a} shift{s:+.2f}s" for t, m, a, s in _shifted))
    # v6.1: Twixtor 源预裁 — startTime 巨偏移会把图层窗推出源时长 (AE钳位成零长层),
    # 预裁 [sin-0.5, sin+dur*spd+0.6] 小片段后 sin=0.5 片内偏移, startTime 偏移极小
    import subprocess as _sp
    import time as _time
    _btag = str(int(_time.time()) % 1000000)  # 构建级唯一后缀 — AE 进程持旧片段文件锁, 同名覆盖必败
    _twx_dir = run_dir / "polish" / "twx_src"
    _twx_dir.mkdir(parents=True, exist_ok=True)
    for _i, _s in enumerate(plan):
        if "twx" not in _s:
            continue
        _t = _s["twx"]
        # v12: 片段名编码镜头 t0 (旧序号名在 plan 插入新条目后位移, 会错用别的镜头旧片段)
        _clip = _twx_dir / f"t{_s['t0']:.3f}_{_btag}.mp4"
        # v6.2: lead 自适应 — 源尾不足时缩前导 (层需跨度 = lead/spd + 镜头长)
        _need = (_s["t1"] - _s["t0"]) + 0.03
        for _lead in (0.5, 0.2, 0.05):
            _have = 0.0
            if _clip.exists():
                _pr = _sp.run(["ffprobe", "-v", "error", "-show_entries",
                               "format=duration", "-of", "csv=p=0", str(_clip)],
                              capture_output=True, text=True, timeout=60)
                try:
                    _have = float(_pr.stdout.strip())
                except ValueError:
                    _have = 0.0
            if _have >= _lead / _t["spd"] + _need:
                break
            _ss = max(0.0, _t["sin"] - _lead)
            _dur = _need * _t["spd"] + _lead + 0.1
            _sp.run(["ffmpeg", "-y", "-ss", f"{_ss:.3f}", "-t", f"{_dur:.3f}",
                     "-i", _t["src"], "-c:v", "libx264", "-crf", "16", "-an",
                     str(_clip)], capture_output=True, timeout=300)
        if _clip.exists():
            _t["src"] = str(_clip).replace(chr(92), "/")
            _t["sin"] = _lead
    _, strong = _load_env()
    if inj_report is None:
        bursts = plan_bursts(plan, strong)
    else:
        # schema 注入模式: bursts 已由 schema_effects_to_plan 给出。
        # 此处若仍调 plan_bursts 会无条件覆盖, 把 burst_radial/burst_badtv
        # 的显式配置全部丢掉 — 正是"声明已应用、实际没上"的成因之一。
        print(f"[schema注入] 保留 schema bursts {len(bursts)} 条 (跳过 plan_bursts 内部规划)")
    # v10.1: 引擎烘的死帧段 (静态源在 1.1-1.5x 下仍 0 运动, 12.7s 后实测 12 处,
    # 最长 500ms — 用户反馈 22/25/27s "没有缓慢运动, 突兀") → S 层加慢推镜:
    # Scale 100→106% 线性, 节拍切点起止, 给静止画面节拍内的缓慢运镜
    import subprocess as _sp2
    import numpy as _np
    _r = _sp2.run(["ffmpeg", "-v", "error", "-i", str(run_dir / f"{tag}_lut.mp4"),
                   "-vf", "scale=160:90", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                  capture_output=True, timeout=600)
    _W, _H = 160, 90
    _n = len(_r.stdout) // (_W * _H)
    _fr = _np.frombuffer(_r.stdout[:_n * _W * _H],
                         dtype=_np.uint8).reshape(_n, _H, _W).astype(_np.float32)
    _d = _np.array([99.0] + [float(_np.abs(_fr[i] - _fr[i - 1]).mean())
                             for i in range(1, _n)])
    _drift_n = 0
    for _s in plan:
        if "twx" in _s or _s["t0"] < 12.7:
            continue
        _i0 = int(_s["t0"] * 24) + 1          # 跳过切点帧差
        _i1 = min(int(_s["t1"] * 24) - 1, _n - 1)
        if _i1 - _i0 >= 2 and float(_np.median(_d[_i0:_i1 + 1])) < 2.5 \
                and float(_np.max(_d[_i0:_i1 + 1])) < 8.0:
            _s["drift"] = 1.06
            _drift_n += 1
    print(f"死帧段慢推镜 (drift): {_drift_n} → "
          f"{[round(s['t0'], 2) for s in plan if 'drift' in s]}")
    # v10.2: 垃圾窗口救援 — 底片窗口内容为 源片水印卡/黑场 (mean luma<60 且整段死帧),
    # 任何速度曲线/推镜都救不了 (黑场上推镜不可见)。成因: 报告↔底片镜头-源映射漂移
    # (23.96 底片实拍 Nagi 源 intro 卡+黑场, 报告分配的五条悟@39.44 实际出现在 27.62)。
    # 救援 = 预烘焙恒速源覆盖层 (setpts 到镜头速度) + push 复刻; 源用显式映射
    # (23.96 ← 报告给 27.62 的 Nagi@8.41, 底片未用过), 其余垃圾窗口回落到报告自身分配。
    _luma = _fr.mean(axis=(1, 2))
    _rescue_dir = run_dir / "polish" / "rescue_src"
    _rescue_dir.mkdir(parents=True, exist_ok=True)
    _rescue_n = 0
    for _i, _s in enumerate(plan):
        if "twx" in _s or _s["t0"] < 12.7 or "rescue" in _s:
            continue
        _hit = RESCUE_MAP.get(round(_s["t0"], 3))
        if _hit is None:
            continue   # 映射不可靠 → 只做显式映射的救援, 不自动回落
        _i0 = int(_s["t0"] * 24) + 1
        _i1 = min(int(_s["t1"] * 24) - 1, _n - 1)
        if _i1 - _i0 < 2 or float(_np.median(_d[_i0:_i1 + 1])) >= 2.5 \
                or float(_np.mean(_luma[_i0:_i1 + 1])) >= 60.0:
            continue
        _rsrc, _rsin, _rspd = _hit
        # 文件名编码偏移 — AE 进程常锁住旧片段, 同名覆盖会瞬间失败 (Windows 文件锁,
        # 参见交接 §6.2), 换源后必须换文件名; 失败要暴露, 不许静默复用陈旧片段
        _rc = _rescue_dir / f"{_i:02d}_{int(round(_rsin * 10))}_{_btag}.mp4"
        _prc = _sp2.run(["ffmpeg", "-y", "-ss", f"{_rsin:.3f}",
                         "-t", f"{(_s['t1'] - _s['t0']) * _rspd + 0.2:.3f}", "-i", _rsrc,
                         "-vf", f"setpts=PTS/{_rspd:.4f}", "-c:v", "libx264", "-crf", "16",
                         "-an", str(_rc)], capture_output=True, timeout=300)
        if _prc.returncode == 0 and _rc.exists():
            _s["rescue"] = {"src": str(_rc).replace(chr(92), "/"), "push": 1.09}
            _s.pop("drift", None)
            _rescue_n += 1
        else:
            print(f"  rescue 烘焙失败 t0={_s['t0']}: "
                  f"{_prc.stderr.decode(errors='replace')[-160:]}")
    print(f"垃圾窗口救援 (rescue): {_rescue_n} → "
          f"{[round(s['t0'], 2) for s in plan if 'rescue' in s]}")
    # v24: flat 替换层 → setpts 预烘焙转换 — 平速重定时不需要 Twixtor 光流
    # (Twixtor 对部分新素材确定性崩溃 @1.4s)。clip 已按镜头速度重定时,
    # 层 startTime 回退 lead/spd 使 t0 对齐源 sin。
    for _s3 in plan:
        _tw = _s3.get("twx")
        if not _tw or _tw.get("anchor_mode") != "flat":
            continue
        _lead = float(_tw.get("sin", 0.2))
        _spd3 = float(_tw.get("spd", 1.0))
        _c2 = _rescue_dir / f"c{_s3['t0']:.3f}.mp4"
        _sp2.run(["ffmpeg", "-y", "-i", _tw["src"], "-vf",
                  f"setpts=PTS/{_spd3:.4f}", "-c:v", "libx264", "-crf", "16",
                  "-an", str(_c2)], capture_output=True, timeout=300)
        if _c2.exists() and _c2.stat().st_size > 0:
            _s3["rescue"] = {"src": str(_c2).replace(chr(92), "/"), "push": 1.09,
                             "st": round(_s3["t0"] - _lead / _spd3, 4)}
            del _s3["twx"]
    from collections import Counter
    cnt = Counter(f for s in plan for f in s["fx"])
    print(f"镜头效果: {len(plan)}/{len(segs)} ({len(plan)/len(segs):.0%})")
    for k, v in cnt.most_common():
        print(f"  {k}: {v}")
    print(f"Twixtor 慢镜: {sum(1 for s in plan if 'twx' in s)}")
    _anchored = [(s["t0"], s["twx"]["anchor_mode"], s["twx"].get("anchor"))
                 for s in plan if s.get("twx", {}).get("anchor_mode", "cut") != "cut"]
    if _anchored:
        print("锚点重锚 (v9): " + ", ".join(
            f"t0={t:.2f} {m}@{(a if a is not None else 0):.2f}" for t, m, a in _anchored))
    print(f"转场冲击层: {len(bursts)} (drop radial {sum(1 for b in bursts if b['t0']>=12.7)} / build badtv {sum(1 for b in bursts if b['t0']<12.7)})")
    _doses = [s["dose"] for s in plan if "dose" in s]
    if _doses:
        print(f"剂量范围: {min(_doses):.2f} - {max(_doses):.2f}")
    else:
        print("剂量范围: (plan 为空)")
    (ROOT / "tmp").mkdir(exist_ok=True)
    (run_dir / "polish").mkdir(exist_ok=True)
    (ROOT / "tmp" / "master_plan.json").write_text(
        json.dumps({"shots": plan, "bursts": bursts}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    jsx = build_jsx(run_dir, tag, plan, bursts)

    if args.dry_run:
        # 离线验证通道: 不碰 AE。AE 被其他会话占用时用它证明
        # schema→plan→JSX 链路已通, 而不需要抢 Bridge。
        jsx_p = ROOT / "tmp" / f"master_dryrun_{tag}.jsx"
        jsx_p.write_text(jsx, encoding="utf-8")
        print(f"[dry-run] JSX 已生成 {jsx_p} ({len(jsx):,} 字符) — 未调用 AE Bridge")
        print(f"[dry-run] plan={len(plan)} bursts={len(bursts)} "
              f"twx={sum(1 for s in plan if 'twx' in s)}")
        return

    import time
    sys.path.insert(0, str(ROOT))
    from ai.ae_render_channel import AERenderChannel
    ch = AERenderChannel(out_dir=str(run_dir / "polish"))
    res = ch._bridge_run_jsx(args={"script": jsx, "scriptContent": jsx}, timeout=300)
    print("bridge:", res)
    time.sleep(3)
    log = ROOT / "tmp" / "ae_master_build.txt"
    if log.exists():
        print("build:", log.read_text(encoding="utf-8")[:600])
    # Bridge 超时返回 None 时原本仅 print 就结束, 进程仍以 0 退出 —
    # 上层无法区分"建好了"与"根本没执行"。改为显式非零退出。
    if res is None:
        print("[ERR] Bridge 300s 无响应 (res=None) — AE 未执行 JSX, 不视为成功")
        sys.exit(4)
    if isinstance(res, dict) and res.get("status") not in (None, "success"):
        print(f"[ERR] Bridge 返回非 success 状态: {res.get('status')}")
        sys.exit(4)


if __name__ == "__main__":
    main()
