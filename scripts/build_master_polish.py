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
    "badtv_hard": [("GUTS BadTV", [("GUTS BadTV-0001", 6)])],
    "fmb":      [("CC Force Motion Blur", [("CC Force Motion Blur-0001", 18)])],
    "fmb_light": [("CC Force Motion Blur", [("CC Force Motion Blur-0001", 14)])],
    "glitch":   [("AESweetsGlitch7in1", [])],  # 默认即 23.6dB 数字故障
}


def plan_effects(segs):
    """按镜头字段 (mood/speed/zoompan/energy) 生成每镜头效果配方"""
    import statistics
    ens = [s.get("energy", 0.4) for s in segs]
    e75 = statistics.quantiles(ens, n=4)[2]
    e_med = statistics.median(ens)
    drop_n = 0
    plan = []
    for s in segs:
        t0 = round(float(s["start_time"]), 3)
        t1 = round(float(s.get("end_time", t0 + 0.25)), 3)
        spd = float(s.get("speed", 1.0))
        mood = s.get("mood", "build")
        en = float(s.get("energy", 0.4))
        zp = s.get("zoompan_effect") or ""
        fx = []
        if mood == "intro":
            fx = []  # 克制
        elif t0 >= 27.0:
            if spd <= 0.55:
                fx = ["bloom_soft"]
        elif mood == "drop":
            drop_n += 1
            if spd <= 0.55:
                # 变速停顿慢镜: bloom + 微散景
                fx = ["bloom", "bokeh"] if en >= e_med else ["bloom"]
            elif spd >= 1.5 and en >= e75:
                fx = ["badtv"]
                # 高潮核心 (22.1-24.6) 最强 3 镜上重锤
                if 22.1 <= t0 <= 24.6 and en >= e75:
                    fx = ["badtv_hard"]
            elif drop_n % 9 == 4:
                fx = ["glitch"]  # 节制: 每9镜一个数字故障强调
            elif spd >= 1.1:
                fx = ["fmb"]
        else:  # build
            if spd >= 1.5 and en >= e_med:
                fx = ["fmb_light"]
            elif spd <= 0.55:
                fx = ["bloom_soft"]
        if fx:
            plan.append({"t0": t0, "t1": t1, "fx": fx, "spd": spd, "en": round(en, 2), "zp": zp})
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
