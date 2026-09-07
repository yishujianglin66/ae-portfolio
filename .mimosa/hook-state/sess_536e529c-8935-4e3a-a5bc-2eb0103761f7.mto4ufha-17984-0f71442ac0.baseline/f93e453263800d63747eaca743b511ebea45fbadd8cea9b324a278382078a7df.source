"""mine_human_projects.py — 人工 AE 工程节奏挖掘（10 套成品 → 节奏模式库）

解析 tutorials 的 10 套人工 .aep: 合成层数/时长/关键帧密度/变速/文字层。
产出"节奏模式库" (data/human_rhythm/patterns.json):
  - 每套: 层数, 时长, 每秒切点数(层入场时间聚类), 文字层占比, 效果密度
  - 总表: 人工成片的节奏分布 → 自动导演的量化参考

用法 (需 AE 桥接在跑):
  python scripts/mine_human_projects.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.ae_bridge_runner import send_jsx_and_wait  # noqa: E402

AEP_ROOT = Path(r"D:\AE-Work\resources\projects\AE新手10套")
OUT = PROJECT / "data" / "human_rhythm" / "patterns.json"

JSX_TMPL = """
(function() {{
  var _result = {{}};
  var _repF = new File('{report_js}');
  _repF.encoding = 'UTF-8';
  var _write = function() {{
    if (_repF.open('w')) {{ _repF.write(JSON.stringify(_result)); _repF.close(); }}
  }};
  // 打开工程 (只读; app.open 是 AE 全局函数, 比 project.open 兼容性好)
  var f = new File('{aep_js}');
  var proj = null;
  try {{ proj = app.open(f); }} catch (e0) {{ _result.error = 'open: ' + e0.toString(); _write(); return; }}
  if (!proj) {{ if (!_result.error) _result.error = 'open returned null'; _write(); return; }}
  var comps = [];
  for (var i = 1; i <= proj.numItems; i++) {{
    var it = proj.item(i);
    if (it.typeName !== 'Composition') continue;
    var layers = [];
    for (var k = 1; k <= it.numLayers; k++) {{
      var ly = it.layer(k);
      var info = {{
        name: ly.name, t0: ly.startTime, dur: ly.outPoint - ly.startTime,
        isAV: ly instanceof AVLayer && ly.source ? ly.source.typeName : '',
      }};
      // 关键帧计数 (仅 Transform 组 — 全属性遍历对 16MB 大工程太慢)
      var kf = 0;
      try {{
        var tr = ly.property('ADBE Transform Group');
        if (tr) {{
          for (var p = 1; p <= tr.numProperties; p++) {{
            var pr = tr.property(p);
            if (pr && pr.numKeys) kf += pr.numKeys;
          }}
        }}
      }} catch (e) {{}}
      info.keyframes = kf;
      layers.push(info);
    }}
    comps.push({{
      name: it.name, dur: it.duration, fps: it.frameRate,
      w: it.width, h: it.height, numLayers: it.numLayers, layers: layers,
    }});
  }}
  _result.comps = comps;
  _write();
  // 关闭不保存
  proj.close(CloseOptions.DO_NOT_SAVE_CHANGES);
}})();
"""


def main() -> int:
    aeps = sorted(AEP_ROOT.glob("*/*.aep")) if AEP_ROOT.exists() else []
    if not aeps:
        print(f"工程目录不存在或无 aep: {AEP_ROOT}")
        return 1
    print(f"人工工程 {len(aeps)} 套")

    all_patterns = []
    for aep in aeps:
        case = aep.parent.name
        print(f"\n=== {case} ===")
        aep_js = str(aep).replace("\\", "/")
        jsx = JSX_TMPL.format(aep_js=aep_js, report_js=str(
            PROJECT / "output" / "human_rhythm_probe.json").replace("\\", "/"))
        try:
            r = send_jsx_and_wait(jsx, str(PROJECT / "output" / "human_rhythm_probe.json"),
                                  timeout=300)
        except TimeoutError:
            print("  桥接超时, 跳过")
            continue
        if r.get("error"):
            print(f"  {r['error']}")
            continue
        for c in r.get("comps", []):
            if c["dur"] < 5:  # 跳过琐碎合成
                continue
            layers = c["layers"]
            n_text = sum(1 for ly in layers if "text" in str(ly.get("isAV", "")).lower()
                         or "文字" in ly["name"] or "text" in ly["name"].lower())
            kf_total = sum(ly["keyframes"] for ly in layers)
            # 切点: 层 startTime 聚类 (>0.3s 间隔算新切点)
            starts = sorted(set(round(ly["t0"], 2) for ly in layers if ly["t0"] >= 0))
            cuts = 0
            prev = -1
            for s in starts:
                if prev < 0 or s - prev > 0.3:
                    cuts += 1
                    prev = s
            pat = {
                "case": case, "comp": c["name"], "dur_s": round(c["dur"], 2),
                "fps": c["fps"], "res": f"{c['w']}x{c['h']}",
                "num_layers": c["numLayers"], "text_layers": n_text,
                "kf_total": kf_total, "kf_per_s": round(kf_total / max(c["dur"], 1), 1),
                "cuts_est": cuts, "cuts_per_s": round(cuts / max(c["dur"], 1), 3),
            }
            all_patterns.append(pat)
            print(f"  {c['name']}: {c['dur']:.1f}s {c['numLayers']}层 "
                  f"{kf_total}kf ({pat['kf_per_s']}/s) ~{cuts}切点 ({pat['cuts_per_s']}/s)")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(all_patterns, ensure_ascii=False, indent=1), encoding="utf-8")
    if all_patterns:
        avg = lambda k: round(sum(p[k] for p in all_patterns) / len(all_patterns), 2)  # noqa: E731
        print(f"\n=== 人工节奏总表 ({len(all_patterns)} 合成) ===")
        print(f"平均时长 {avg('dur_s')}s | 层数 {avg('num_layers')} | "
              f"关键帧密度 {avg('kf_per_s')}/s | 切点密度 {avg('cuts_per_s')}/s | "
              f"文字层占比 {round(sum(p['text_layers'] for p in all_patterns) / max(sum(p['num_layers'] for p in all_patterns), 1) * 100, 1)}%")
    print(f"落盘: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
