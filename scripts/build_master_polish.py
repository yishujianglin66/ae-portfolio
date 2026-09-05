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

用法: python scripts/build_master_polish.py <run_dir> <tag> [--bgm xx.mp3]
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

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
}

ENV_DECAY_S = 0.16   # 包络衰减时长 (~3帧@24fps)
ENV_TAIL = 0.45      # 衰减后保持比例

# Twixtor 连续速度曲线 (2026-09-05 #10): (时长占比, 相对速度)
# 快进冲入→急减速→冻结在拍点(顶尖慢镜招牌)。梯形积分归一=1 保平均速度不变, 落拍不漂。
TWX_SPEED_PROFILE = [(0.0, 0.18), (0.55, 0.50), (1.0, 1.05)]


def _load_env():
    p = ROOT / "tmp" / "music_envelope.json"
    d = json.loads(p.read_text(encoding="utf-8"))
    times, env = d["env_times"], d["env"]
    def at(t):
        i = min(range(len(times)), key=lambda k: abs(times[k] - t))
        return env[i]
    return at, d["strong"]


def plan_effects(segs):
    """v4 = v3.1 骨架 (段落相对能量/轮换禁重复/呼吸留白) + 连续剂量 + 冲击层"""
    import statistics
    env_at, strong = _load_env()
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
            plan.append(entry)
    return plan


def plan_bursts(plan, strong):
    """转场冲击层: 强鼓点上的切点 → 顶层 2-4 帧 burst (drop radial / build badtv)"""
    cuts = [p["t0"] for p in plan if p["t0"] > 0.3]
    on_strong = lambda t: any(abs(t - st) <= 0.080 for st in strong)
    bursts = []
    for zone, cap, rec, dur in (("drop", 12, "burst_radial", 0.15), ("build", 6, "burst_badtv", 0.10)):
        picked = []
        for t in cuts:
            if zone == "drop" and not (12.7 <= t < 27.0):
                continue
            if zone == "build" and not (0.3 <= t < 12.7):
                continue
            if not on_strong(t):
                continue
            if picked and t - picked[-1] < 0.8:   # 最小间隔防连爆
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
    def _twx_curve(t0, t1, sin, spd):
        """连续速度曲线关键帧 [[comp_time, speed_pct], ...]

        v7 修复卡点漂移 (用户反馈: 曲线版卡点对不上):
        ① 相位锚 — startTime=t0-sin/spd 按恒速校准, 曲线版预卷段速度若≠spd,
          积分模型下起点漂移 sin×(v0/spd-1) (v1 用 123% 开头 → 偏 0.62s)。
          预卷段写两个恒速 spd 关键帧钉死相位 (对积分/逐点模型都成立)。
        ② 曲线反转 — 冻结对齐切点 (音乐坠落点画面速停), 向下一拍渐加速放出。
        """
        dur = t1 - t0
        fr = [p[0] for p in TWX_SPEED_PROFILE]
        rs = [p[1] for p in TWX_SPEED_PROFILE]
        integ = sum((rs[i] + rs[i + 1]) / 2 * (fr[i + 1] - fr[i])
                    for i in range(len(fr) - 1))
        k = spd / integ   # 归一使曲线段平均速度=spd (时长占比梯形积分)
        t_pre = t0 - sin / spd
        eps = 1.0 / 24    # 锚末端留 1 帧过渡到曲线首值, 起点误差 <0.2 帧
        return [[round(t_pre, 3), spd * 100],
                [round(t0 - eps, 3), spd * 100]] + \
               [[round(t0 + f * dur, 3), round(r * k * 100, 2)]
                for f, r in TWX_SPEED_PROFILE]

    def _shot_js(s):
        d = {"t0": s["t0"], "t1": s["t1"], "r": [_fx_js(f, s["dose"]) for f in s["fx"]]}
        if "twx" in s:
            d["twx"] = {"src": s["twx"]["src"].replace(chr(92), "/"),
                        "sin": s["twx"]["sin"], "spd": s["twx"]["spd"], "zp": s["twx"]["zp"],
                        "curve": _twx_curve(s["t0"], s["t1"], s["twx"]["sin"], s["twx"]["spd"])}
        return d
    shots_js = json.dumps([_shot_js(s) for s in plan], separators=(",", ":"))
    bursts_js = json.dumps(
        [{"t0": b["t0"], "t1": b["t1"], "r": [_fx_js(f, b["dose"]) for f in b["fx"]]}
         for b in bursts], separators=(",", ":"))
    return f"""
(function(){{
  var rep = "start";
  var DECAY = {ENV_DECAY_S}, TAIL = {ENV_TAIL};
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
      if (sh.twx) {{
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
      }}
      for (var j = 0; j < sh.r.length; j++) applyFx(ly, sh.r[j], sh.t0);
    }}
    var bursts = {bursts_js};
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


def main():
    run_dir = ROOT / sys.argv[1]
    tag = sys.argv[2]
    pr = json.loads((run_dir / "production_report.json").read_text(encoding="utf-8"))
    segs = pr["script"]["segments"]
    plan = plan_effects(segs)
    ov_p = ROOT / "tmp" / "dose_overrides.json"
    if ov_p.exists():
        ov = {float(k): v for k, v in json.loads(ov_p.read_text(encoding="utf-8")).items()}
        for s in plan:
            for kt, m in ov.items():
                if abs(s["t0"] - kt) < 0.05:
                    s["dose"] = round(min(s["dose"] * m, 3.5), 3)
    # v6.1: Twixtor 源预裁 — startTime 巨偏移会把图层窗推出源时长 (AE钳位成零长层),
    # 预裁 [sin-0.5, sin+dur*spd+0.6] 小片段后 sin=0.5 片内偏移, startTime 偏移极小
    import subprocess as _sp
    _twx_dir = run_dir / "polish" / "twx_src"
    _twx_dir.mkdir(parents=True, exist_ok=True)
    for _i, _s in enumerate(plan):
        if "twx" not in _s:
            continue
        _t = _s["twx"]
        _clip = _twx_dir / f"{_i:02d}.mp4"
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
    bursts = plan_bursts(plan, strong)
    from collections import Counter
    cnt = Counter(f for s in plan for f in s["fx"])
    print(f"镜头效果: {len(plan)}/{len(segs)} ({len(plan)/len(segs):.0%})")
    for k, v in cnt.most_common():
        print(f"  {k}: {v}")
    print(f"Twixtor 慢镜: {sum(1 for s in plan if 'twx' in s)}")
    print(f"转场冲击层: {len(bursts)} (drop radial {sum(1 for b in bursts if b['t0']>=12.7)} / build badtv {sum(1 for b in bursts if b['t0']<12.7)})")
    print(f"剂量范围: {min(s['dose'] for s in plan):.2f} - {max(s['dose'] for s in plan):.2f}")
    (ROOT / "tmp").mkdir(exist_ok=True)
    (run_dir / "polish").mkdir(exist_ok=True)
    (ROOT / "tmp" / "master_plan.json").write_text(
        json.dumps({"shots": plan, "bursts": bursts}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    jsx = build_jsx(run_dir, tag, plan, bursts)

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


if __name__ == "__main__":
    main()
