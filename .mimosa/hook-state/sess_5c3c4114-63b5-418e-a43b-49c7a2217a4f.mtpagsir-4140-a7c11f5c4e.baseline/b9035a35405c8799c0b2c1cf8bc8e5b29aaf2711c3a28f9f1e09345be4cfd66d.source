# -*- coding: utf-8 -*-
"""harvest_experience.py — 自进化层1: 经验采集 (2026-09-04)

每版渲染自动记录四元组进 data/evolution/render_history.jsonl:
  配方快照(验证卡) + 行为指纹(速度/运镜/间隔分布) + 闸门指标 + 用户判定槽
用户判定用 --verdict 回填; 积累的正负样本供层2参数寻优/模型重训消费。

用法:
  python scripts/harvest_experience.py output/unified_run50 run50 --bgm xx.mp3 \
      [--verdict "对了"]
"""
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
HIST = PROJ / "data" / "evolution" / "render_history.jsonl"
CARD = PROJ / "data" / "style_cards" / "beat_grammar_validated_v1.json"


def behavior_fingerprint(run_dir, tag):
    pr = json.loads((Path(run_dir) / "production_report.json").read_text(encoding="utf-8"))
    segs = sorted(pr["script"]["segments"], key=lambda s: s["start_time"])
    burst = [s for s in segs if 13 <= s["start_time"] < 30]
    gaps = [burst[i+1]["start_time"] - burst[i]["start_time"]
            for i in range(len(burst) - 1)] if len(burst) > 1 else []
    sp_all = [round(s.get("speed", 1.0), 2) for s in segs]
    sp_b = [round(s.get("speed", 1.0), 2) for s in burst]
    jumps = sum(1 for i in range(len(sp_b)-1) if abs(sp_b[i+1]-sp_b[i]) >= 0.4)
    return {
        "n_shots": len(segs),
        "cam_dist": dict(Counter(str(s.get("zoompan_effect")) for s in segs)),
        "speed_dist": dict(Counter(sp_all)),
        "burst_speed_dist": dict(Counter(sp_b)),
        "burst_cuts_per_s": round(1 / (sum(gaps) / len(gaps)), 2) if gaps else 0,
        "burst_interval_tiers": len(set(round(g, 1) for g in gaps)),
        "burst_speed_jumps": jumps,
        "avg_shot_dur": round(sum(s["duration"] for s in segs) / len(segs), 3),
    }


def gate_metrics(run_dir, tag, bgm):
    cmd = [sys.executable, str(PROJ / "scripts" / "render_gate.py"),
           str(run_dir), tag] + (["--bgm", bgm] if bgm else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=900,
                       encoding="utf-8", errors="replace")
    import re
    checks = re.findall(r"\[(PASS|FAIL)\] ([^:]+): (.+)", r.stdout)
    return {"pass": sum(1 for c, _, _ in checks if c == "PASS"),
            "total": len(checks),
            "detail": {n.strip(): d.strip() for _, n, d in checks},
            "accepted": "ACCEPT" in r.stdout}


def main():
    run_dir, tag = sys.argv[1], sys.argv[2]
    verdict = (sys.argv[sys.argv.index("--verdict") + 1]
               if "--verdict" in sys.argv else "待判定")
    bgm = (sys.argv[sys.argv.index("--bgm") + 1] if "--bgm" in sys.argv else None)
    rec = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "tag": tag,
        "verdict": verdict,
        "grammar_card": (json.loads(CARD.read_text(encoding="utf-8"))
                         .get("version", "?")) if CARD.exists() else "?",
        "behavior": behavior_fingerprint(run_dir, tag),
        "gate": gate_metrics(run_dir, tag, bgm),
    }
    HIST.parent.mkdir(parents=True, exist_ok=True)
    with open(HIST, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[采集] {tag} 判定={verdict} 闸门={rec['gate']['pass']}/{rec['gate']['total']}"
          f" 快切={rec['behavior']['burst_cuts_per_s']}切/s 跳变={rec['behavior']['burst_speed_jumps']}")


if __name__ == "__main__":
    main()
