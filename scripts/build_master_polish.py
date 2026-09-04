# -*- coding: utf-8 -*-
"""镜头级 AE 精修 v2 — 逐镜头分段 + 按镜头设计插件 (2026-09-04)

设计原则 (用户 2026-09-04):
- 每个镜头单独切段成图层, 在总合成 MASTER 里逐镜头上插件
- 不做全片 adjustment 调色 (调色归达芬奇) — 只做运动/冲击/质感效果
- 插件全部取自本机已装库, 参数经 CAL 校准 (dB 标尺), 见 handoff-2026-09-04

镜头→插件映射 (克制优先, ~55% 镜头上效果):
- 决斗变速停顿 spd<=0.55  : Glo2 高光bloom(阈值0.8) + FastBokeh@1 散景
- 决斗快切 spd>=1.5 高能  : BadTV@2.5 模拟失真冲击 (能量前25%)
- 决斗快切 其余           : CC Force Motion Blur@18 运动模糊拖影
- build 快切              : CC Force Motion Blur@14 (轻)
- 每 9 个 drop 镜头       : Glitch7in1 数字故障强调
- 尾奏 t>=27 慢镜         : Glo2 bloom (更柔)
- intro                   : 无 (克制)
用法: python scripts/build_master_polish.py <run_dir> <tag>
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 校准过的效果配方 (matchName 设参, 单位=校准 dB 标尺)
RECIPES = {
    "bloom":    [("ADBE Glo2", [("ADBE Glo2-0002", 0.80),   # 阈值: 只晕高光
                                ("ADBE Glo2-0003", 6),      # 半径
                                ("ADBE Glo2-0004", 0.22)])],# 强度
    "bloom_soft": [("ADBE Glo2", [("ADBE Glo2-0002", 0.85),
                                  ("ADBE Glo2-0003", 5),
                                  ("ADBE Glo2-0004", 0.16)])],
    "bokeh":    [("RWB Fast Bokeh", [("RWB Fast Bokeh-0001", 1)])],
    "badtv":    [("GUTS BadTV", [("GUTS BadTV-0001", 2.5)])],
    "badtv_light": [("GUTS BadTV", [("GUTS BadTV-0001", 1.5)])],
    "badtv_hard": [("GUTS BadTV", [("GUTS BadTV-0001", 6)])],
    "fmb":      [("CC Force Motion Blur", [("CC Force Motion Blur-0001", 18)])],
    "fmb_light": [("CC Force Motion Blur", [("CC Force Motion Blur-0001", 14)])],
    "glitch":   [("AESweetsGlitch7in1", [])],   # 默认即 23.6dB 数字故障
    "radial":   [("CC Radial Fast Blur", [])],  # 默认 22.6dB 放射模糊推镜冲击 (v3)
}


def plan_effects(segs):
    """v3 (用户反馈 2026-09-04: 13s前无效果 + 效果重复疲劳)
    - 段落内相对能量: build/drop 各自取中位数, build 不再被全片中位数卡光
    - 效果轮换: 同一效果禁止连续两镜, 快切冲击位在 badtv/radial 间交替
    - 留白呼吸: drop 快切 fmb 只上隔镜, 避免拖影连成一片
    """
    import statistics
    build_en = [float(s.get("energy", 0.4)) for s in segs
                if s.get("mood") == "build" and float(s["start_time"]) < 27.0]
    drop_en = [float(s.get("energy", 0.4)) for s in segs if s.get("mood") == "drop"]
    b_med = statistics.median(build_en) if build_en else 0.4
    d_med = statistics.median(drop_en) if drop_en else 0.5
    d_q3 = statistics.quantiles(drop_en, n=4)[2] if len(drop_en) >= 4 else 0.6

    drop_n = 0        # drop 段镜头计数 (glitch 节拍器)
    build_fx_n = 0    # build 轮换计数
    fast_streak = 0   # drop 快切连续上效计数 (呼吸留白)
    hard_used = 0
    last_fx = None
    plan = []

    def _alt(*cands):
        """从候选里取第一个 != last_fx 的 (禁连续同款)"""
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
            fx = []  # 克制
        elif t0 >= 27.0:
            if spd <= 0.55:
                fx = ["bloom_soft"]
        elif mood == "drop":
            drop_n += 1
            if spd <= 0.55:
                # 变速停顿: bloom 恒上, bokeh 隔镜陪衬 (v3: 不再每镜双效果)
                fx = ["bloom", "bokeh"] if (drop_n % 2 == 0 and en >= d_med) else ["bloom"]
            elif en >= d_q3 and spd >= 1.5:
                # 强拍冲击: badtv/radial 交替 (v3 轮换)
                if 22.1 <= t0 <= 24.6 and hard_used < 3 and en >= d_q3:
                    fx = ["badtv_hard"]; hard_used += 1
                else:
                    fx = [_alt("badtv", "radial")]
            elif drop_n % 9 == 4:
                fx = ["glitch"]
            elif spd >= 1.1:
                # 普通快切: fmb 只上隔镜 (v3 呼吸留白)
                fast_streak += 1
                if fast_streak % 2 == 1:
                    fx = ["fmb"]
            if fx and fx != ["fmb"]:
                fast_streak = 0
        else:  # build (v3: 段内相对能量, 不再全片一刀切)
            if spd >= 1.5 and en >= b_med:
                build_fx_n += 1
                # 严格交替+留白: fmb → 空 → radial/badtv → 空 (v3.1)
                cyc = build_fx_n % 4
                if cyc == 1:
                    fx = ["fmb_light"]
                elif cyc == 3:
                    fx = ["badtv_light"] if en >= max(b_med, d_med * 0.9) else ["radial"]
                # cyc 2/4: 留白
            elif spd <= 0.55:
                fx = ["bloom_soft"]
        if fx:
            last_fx = fx[-1]
            plan.append({"t0": t0, "t1": t1, "fx": fx, "spd": spd,
                         "en": round(en, 2), "zp": s.get("zoompan_effect") or ""})
    return plan


def build_jsx(run_dir: Path, tag: str, plan):
    import json as _j
    vin = (run_dir / f"{tag}_lut.mp4").resolve().as_posix()
    aep = (run_dir / "polish" / "master.aep").as_posix()
    shots_js = _j.dumps(plan, ensure_ascii=False, separators=(",", ":"))
    recipes_js = _j.dumps({k: v for k, v in RECIPES.items()}, ensure_ascii=False,
                          separators=(",", ":"))
    return f"""
(function(){{
  var rep = "start";
  try {{
    app.project.close(CloseOptions.DO_NOT_SAVE_CHANGES);
    app.newProject();
    var imp = app.project.importFile(new ImportOptions(new File("{vin}")));
    var comp = app.project.items.addComp("MASTER", imp.width, imp.height,
        1.0, imp.duration, imp.frameRate);
    var shots = {shots_js};
    var REC = {recipes_js};
    // 底层 BASE: 完整素材 (无效果镜头透出, 绝不黑帧 — 2026-09-04 v2.1)
    var base = comp.layers.add(imp);
    base.name = "BASE";
    for (var i = 0; i < shots.length; i++) {{
      var sh = shots[i];
      var ly = comp.layers.add(imp);
      ly.inPoint = sh.t0;
      ly.outPoint = sh.t1;
      ly.name = "S" + i + "_" + sh.fx.join("+");
      for (var j = 0; j < sh.fx.length; j++) {{
        var r = REC[sh.fx[j]];
        for (var k = 0; k < r.length; k++) {{
          try {{
            var fx = ly.property("Effects").addProperty(r[k][0]);
            var ps = r[k][1];
            for (var m = 0; m < ps.length; m++) {{
              try {{ fx.property(ps[m][0]).setValue(ps[m][1]); }}
              catch(ep) {{ rep += "|P:" + i + ":" + ps[m][0]; }}
            }}
          }} catch(ea) {{ rep += "|A:" + i + ":" + r[k][0]; }}
        }}
      }}
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
    n_fx = len(plan)
    from collections import Counter
    cnt = Counter(f for s in plan for f in s["fx"])
    print(f"镜头效果计划: {n_fx}/{len(segs)} 镜头上效果 ({n_fx/len(segs):.0%})")
    for k, v in cnt.most_common():
        print(f"  {k}: {v} 镜")
    (ROOT / "tmp").mkdir(exist_ok=True)
    (run_dir / "polish").mkdir(exist_ok=True)
    (ROOT / "tmp" / "master_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
    jsx = build_jsx(run_dir, tag, plan)

    import time
    sys.path.insert(0, str(ROOT))
    from ai.ae_render_channel import AERenderChannel
    ch = AERenderChannel(out_dir=str(run_dir / "polish"))
    res = ch._bridge_run_jsx(args={"script": jsx, "scriptContent": jsx}, timeout=300)
    print("bridge:", res)
    time.sleep(3)
    log = ROOT / "tmp" / "ae_master_build.txt"
    if log.exists():
        print("build:", log.read_text(encoding="utf-8")[:800])


if __name__ == "__main__":
    main()
