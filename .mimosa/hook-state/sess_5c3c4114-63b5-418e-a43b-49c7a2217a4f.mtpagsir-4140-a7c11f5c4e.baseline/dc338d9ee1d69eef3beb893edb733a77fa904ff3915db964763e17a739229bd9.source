# -*- coding: utf-8 -*-
"""T2: 统一评测框架 accept_runner — 一条命令跑全部验收, 自动存档+bootstrap CI。

用法: python -m ai.accept_runner [--quick]
输出: reports/accept_{date}.json
验收项:
  1. ip_proto_classifier v1口径(回归红线: 12/12)
  2. ip_proto_classifier v2口径(若存在benchmark_golden_v2.json)
  3. production_scorer 22素材验收
  4. e2e闭环(tmp/p33_e2e.py, 若存在)
关键指标附 bootstrap 95% CI (n=1000)。
"""
import json
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable


def bootstrap_ci(ok: int, n: int, n_boot: int = 1000, seed: int = 42):
    """二项通过率的bootstrap 95% CI。"""
    if n == 0:
        return (0.0, 0.0)
    import numpy as np
    rng = np.random.default_rng(seed)
    arr = np.array([1] * ok + [0] * (n - ok))
    rates = []
    for _ in range(n_boot):
        rates.append(rng.choice(arr, size=n, replace=True).mean())
    lo, hi = np.percentile(rates, [2.5, 97.5])
    return (round(float(lo), 4), round(float(hi), 4))


def run_ip_accept(golden_flag: str = "") -> dict:
    cmd = [PY, "-m", "ai.ip_proto_classifier", "--accept"]
    if golden_flag:
        cmd += ["--golden", golden_flag]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=ROOT, timeout=3600)
    rep_path = ROOT / "reports" / "ip_proto_report.json"
    if not rep_path.exists():
        return {"error": "no_report", "stderr_tail": r.stderr[-500:]}
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    acc = rep.get("accept", {})
    tot = sum(v["tot"] for v in acc.values() if isinstance(v, dict) and "tot" in v)
    ok = sum(v["ok"] for v in acc.values() if isinstance(v, dict) and "ok" in v)
    return {"segments": {k: v for k, v in acc.items() if isinstance(v, dict)},
            "pass_rate": round(ok / tot, 4) if tot else 0, "ok": ok, "tot": tot,
            "legacy_acc": acc.get("legacy_ip_matches_acc"),
            "ci95": bootstrap_ci(ok, tot)}


def _parse_ratio(v):
    """解析 '16/22' 或 {'ok':16,'tot':22} → (ok, tot)"""
    if isinstance(v, dict):
        return int(v.get("ok", 0)), int(v.get("tot", 0))
    if isinstance(v, str) and "/" in v:
        a, b = v.split("/")[:2]
        return int(a), int(b)
    return 0, 0


def run_scorer() -> dict:
    r = subprocess.run([PY, "-m", "ai.production_scorer", "--demo"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", cwd=ROOT, timeout=3600)
    rep_path = ROOT / "reports" / "production_scorer_report.json"
    if not rep_path.exists():
        return {"error": "no_report", "stderr_tail": r.stderr[-500:]}
    rep = json.loads(rep_path.read_text(encoding="utf-8"))
    out = {}
    # v1口径: 实际键名为 accept_A_real_beats_grid_and_random / accept_B_real_beats_overdense
    for key, src in (("A_real_vs_grid_random", "accept_A_real_beats_grid_and_random"),
                     ("B_real_vs_overdense", "accept_B_real_beats_overdense")):
        if src in rep:
            ok, tot = _parse_ratio(rep[src])
            out[key] = {"ok": ok, "tot": tot,
                        "ci95": bootstrap_ci(ok, tot) if tot else None}
    # v2口径: production_scorer_v2_report.json 的 accept_A/accept_B (dict格式)
    rep2_path = ROOT / "reports" / "production_scorer_v2_report.json"
    if rep2_path.exists():
        rep2 = json.loads(rep2_path.read_text(encoding="utf-8"))
        for key, src in (("A_v2", "accept_A"), ("B_v2", "accept_B")):
            if src in rep2:
                ok, tot = _parse_ratio(rep2[src])
                out[key] = {"ok": ok, "tot": tot,
                            "ci95": bootstrap_ci(ok, tot) if tot else None}
    out["_raw_keys"] = list(rep.keys())
    return out


def run_e2e() -> dict:
    p = ROOT / "tmp" / "p33_e2e.py"
    if not p.exists():
        return {"skipped": "p33_e2e.py不存在"}
    r = subprocess.run([PY, str(p)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", cwd=ROOT, timeout=3600)
    tail = (r.stdout or "")[-800:]
    passed = r.returncode == 0 and ("FAIL" not in tail.upper().split("RESULT")[-1])
    return {"returncode": r.returncode, "passed": passed, "stdout_tail": tail}


def main(quick: bool = False):
    t0 = time.time()
    results = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S"), "quick": quick}
    print("[accept] 1/4 ip_proto v1口径(回归红线)...", flush=True)
    results["ip_proto_v1"] = run_ip_accept()
    if not quick:
        v2 = ROOT / "data" / "benchmark_golden_v2.json"
        if v2.exists():
            print("[accept] 2/4 ip_proto v2口径...", flush=True)
            results["ip_proto_v2"] = run_ip_accept("v2")
        print("[accept] 3/4 production_scorer...", flush=True)
        results["production_scorer"] = run_scorer()
        print("[accept] 4/4 e2e闭环...", flush=True)
        results["e2e"] = run_e2e()
    # 回归红线判定
    v1 = results.get("ip_proto_v1", {})
    results["regression_gate"] = {
        "v1_baseline_12_12": v1.get("ok") == 12 and v1.get("tot") == 12}
    results["duration_s"] = round(time.time() - t0, 1)
    out = ROOT / "reports" / f"accept_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results["regression_gate"], ensure_ascii=False))
    print(f"[accept] 完成 {results['duration_s']}s -> {out}")


if __name__ == "__main__":
    main(quick="--quick" in sys.argv)
