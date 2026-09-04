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
    # 转场冲击层 (顶层短层)
    "burst_radial": {"m": "CC Radial Fast Blur", "ps": [("CC Radial Fast Blur-0002", 90)], "env": True},
    "burst_badtv":  {"m": "GUTS BadTV", "ps": [("GUTS BadTV-0001", 4.5)], "env": True},
}

ENV_DECAY_S = 0.16   # 包络衰减时长 (~3帧@24fps)
ENV_TAIL = 0.45      # 衰减后保持比例


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

    drop_n = build_fx_n = fast_streak = hard_used = 0
    last_fx = None
    plan = []

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
                    fx = ["radial_soft"] if fast_streak % 4 == 1 else ["fmb"]
            if fx and fx != ["fmb"]:
                fast_streak = 0
        else:  # build
            if spd >= 1.5 and en >= b_med:
                build_fx_n += 1
                cyc = build_fx_n % 4
                if cyc == 1:
                    fx = ["radial_soft"]
                elif cyc == 3:
                    fx = ["badtv_light"] if en >= max(b_med, d_med * 0.9) else ["radial_soft"]
            elif spd <= 0.55:
                fx = ["bloom_soft"]
        if fx:
            last_fx = fx[-1]
            dose = 0.65 + 0.7 * env_at(t0)   # 连续密度曲线
            plan.append({"t0": t0, "t1": t1, "fx": fx, "dose": round(dose, 3),
                         "en": round(en, 2), "env": round(env_at(t0), 2)})
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
        r = RECIPES[spec]
        ps = json.dumps([[p, round(v * dose, 4)] for p, v in r["ps"]],
                        separators=(",", ":"))
        return {"m": r["m"], "ps": json.loads(ps), "env": r["env"]}
    shots_js = json.dumps(
        [{"t0": s["t0"], "t1": s["t1"], "r": [_fx_js(f, s["dose"]) for f in s["fx"]]}
         for s in plan], separators=(",", ":"))
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
    for (var i = 0; i < shots.length; i++) {{
      var sh = shots[i];
      var ly = comp.layers.add(imp);
      ly.inPoint = sh.t0; ly.outPoint = sh.t1;
      ly.name = "S" + i;
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
    _, strong = _load_env()
    bursts = plan_bursts(plan, strong)
    from collections import Counter
    cnt = Counter(f for s in plan for f in s["fx"])
    print(f"镜头效果: {len(plan)}/{len(segs)} ({len(plan)/len(segs):.0%})")
    for k, v in cnt.most_common():
        print(f"  {k}: {v}")
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
