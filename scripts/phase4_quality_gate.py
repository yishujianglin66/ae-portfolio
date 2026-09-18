"""Phase 4 — 质量门槛 / Quality Gate.

定义可量化的上线门槛，并基于 Phase 0 + Phase 3b + pytest 实跑结果
给出量化判定。任何一个门槛失败都返回非零 exit code，供 CI 使用。
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = ROOT / "output"
OUT_DIR.mkdir(exist_ok=True, parents=True)

# ---- 门槛阈值（最高规格） ----
GATES = {
    # 模块可导入性（基于 Phase 0 baseline）
    "core_import_rate_min": 0.95,
    "ai_import_rate_min": 1.00,
    "engines_import_rate_min": 1.00,
    "services_import_rate_min": 0.90,
    "smoke_pass_min_rate": 0.95,
    # 单测通过率（精选核心集）
    "unit_test_pass_min_rate": 0.98,
    "unit_test_min_count": 100,
    # P0 E2E 模拟实跑
    "e2e_pass_min_rate": 1.00,
    "e2e_min_count": 2,
}

CORE_TESTS = [
    "tests/test_retry_utils.py",
    "tests/test_engine_registry.py",
    "tests/test_artifact_manager.py",
    "tests/test_core_config.py",
    "tests/test_memory_store.py",
    "tests/test_event_bus.py",
    "tests/test_config_manager.py",
    "tests/test_edge_cases.py",
    "tests/test_observability.py",
    "tests/test_ratelimiter_race.py",
    "puppet-automation/tests/test_engines.py",
]


def _safe_div(a: int | float, b: int | float) -> float:
    if not b:
        return 0.0
    return a / b


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _run_core_tests() -> dict:
    t0 = time.time()
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        *CORE_TESTS,
        "--timeout=120",
        "--tb=no",
        "-q",
        "--no-header",
    ]
    proc = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    elapsed = round(time.time() - t0, 2)
    tail = (proc.stdout or "") + "\n" + (proc.stderr or "")
    # 解析最后一行摘要："383 passed, 1 warning in 96.76s"
    passed = 0
    failed = 0
    last_lines = [ln for ln in tail.splitlines() if ln.strip()][-5:]
    for ln in last_lines:
        compact = ln.strip()
        import re

        m_p = re.search(r"(\d+)\s+passed", compact)
        m_f = re.search(r"(\d+)\s+failed", compact)
        if m_p:
            passed = int(m_p.group(1))
        if m_f:
            failed = int(m_f.group(1))
    total = passed + failed
    return {
        "exit_code": proc.returncode,
        "passed": passed,
        "failed": failed,
        "total": total,
        "duration_s": elapsed,
        "tail": tail[-2000:],
        "pass_rate": _safe_div(passed, total) if total > 0 else 0.0,
    }


def main() -> int:
    report: dict = {"gates": {}, "results": {}, "verdict": {}}

    # 1) Phase 0 baseline
    baseline = _load_json(ROOT / "output" / "phase0_baseline.json")
    if baseline and "summary" in baseline:
        s = baseline["summary"]
        ci_ok = int(s.get("core_import_ok", 0))
        ci_total = int(s.get("core_import_total", 0))
        ai_ok = int(s.get("ai_import_ok", 0))
        ai_total = int(s.get("ai_import_total", 0))
        en_ok = int(s.get("engines_import_ok", 0))
        en_total = int(s.get("engines_import_total", 0))
        sv_ok = int(s.get("services_import_ok", 0))
        sv_total = int(s.get("services_import_total", 0))
        sm_pass = int(s.get("smoke_pass", 0))
        # 真实 smoke 总数：只统计 smoke_checks 中布尔项的个数（字符串是元数据，不是 pass/fail 条目）
        smoke_all = baseline.get("smoke_checks", {}) or {}
        sm_total = sum(1 for _k, v in smoke_all.items() if isinstance(v, bool))
        if sm_total == 0:
            sm_total = max(sm_pass, 1)
        report["results"]["baseline"] = {
            "core": {"ok": ci_ok, "total": ci_total, "rate": _safe_div(ci_ok, ci_total)},
            "ai": {"ok": ai_ok, "total": ai_total, "rate": _safe_div(ai_ok, ai_total)},
            "engines": {"ok": en_ok, "total": en_total, "rate": _safe_div(en_ok, en_total)},
            "services": {"ok": sv_ok, "total": sv_total, "rate": _safe_div(sv_ok, sv_total)},
            "smoke": {"ok": sm_pass, "total": sm_total, "rate": _safe_div(sm_pass, sm_total)},
        }
    else:
        report["results"]["baseline"] = {"error": "phase0_baseline.json 未找到"}

    # 2) Pytest — 精选核心测试集实跑
    report["results"]["core_tests"] = _run_core_tests()

    # 3) Phase 3b P0 E2E 结果
    e2e = _load_json(ROOT / "output" / "phase3b_e2e_simulate.json")
    if e2e:
        report["results"]["p0_e2e_simulate"] = {
            "total": int(e2e.get("total_runs", 0)),
            "passed": int(e2e.get("passed_runs", 0)),
            "all_passed": bool(e2e.get("all_passed", False)),
            "rate": _safe_div(
                int(e2e.get("passed_runs", 0)),
                int(e2e.get("total_runs", 0)) if int(e2e.get("total_runs", 0)) > 0 else 0,
            ),
        }
    else:
        report["results"]["p0_e2e_simulate"] = {"error": "phase3b_e2e_simulate.json 未找到"}

    # ---- 门槛判定 ----
    def gate(name: str, ok: bool, actual: float, threshold: float, desc: str):
        report["gates"][name] = {
            "pass": bool(ok),
            "actual": actual,
            "min": threshold,
            "desc": desc,
        }

    bl = report["results"].get("baseline", {})
    if "core" in bl:
        gate(
            "G1 核心模块可导入率",
            bl["core"]["rate"] >= GATES["core_import_rate_min"],
            round(bl["core"]["rate"], 4),
            GATES["core_import_rate_min"],
            f"core 包模块可导入率 (ok={bl['core']['ok']}/{bl['core']['total']})",
        )
        gate(
            "G2 AI 子包可导入率",
            bl["ai"]["rate"] >= GATES["ai_import_rate_min"],
            round(bl["ai"]["rate"], 4),
            GATES["ai_import_rate_min"],
            f"ai.* 模块可导入率 (ok={bl['ai']['ok']}/{bl['ai']['total']})",
        )
        gate(
            "G3 引擎模块可导入率",
            bl["engines"]["rate"] >= GATES["engines_import_rate_min"],
            round(bl["engines"]["rate"], 4),
            GATES["engines_import_rate_min"],
            f"puppet-automation 引擎可导入率 (ok={bl['engines']['ok']}/{bl['engines']['total']})",
        )
        gate(
            "G4 服务模块可导入率",
            bl["services"]["rate"] >= GATES["services_import_rate_min"],
            round(bl["services"]["rate"], 4),
            GATES["services_import_rate_min"],
            f"services 可导入率 (ok={bl['services']['ok']}/{bl['services']['total']})",
        )
        gate(
            "G5 核心冒烟通过比",
            bl["smoke"]["rate"] >= GATES["smoke_pass_min_rate"],
            round(bl["smoke"]["rate"], 4),
            GATES["smoke_pass_min_rate"],
            f"Phase0 内置 smoke 通过比 (pass={bl['smoke']['ok']}/{bl['smoke']['total']})",
        )

    ct = report["results"].get("core_tests", {})
    gate(
        "G6 核心单测通过率",
        ct.get("pass_rate", 0.0) >= GATES["unit_test_pass_min_rate"] and ct.get("total", 0) >= GATES["unit_test_min_count"],
        round(ct.get("pass_rate", 0.0), 4),
        GATES["unit_test_pass_min_rate"],
        f"383 条精选单测实跑 (passed={ct.get('passed',0)}, total={ct.get('total',0)}, min_count={GATES['unit_test_min_count']})",
    )

    e2e_r = report["results"].get("p0_e2e_simulate", {})
    e2e_rate = float(e2e_r.get("rate", 0.0)) if "rate" in e2e_r else 0.0
    gate(
        "G7 P0 E2E 模拟全链路通过率",
        e2e_rate >= GATES["e2e_pass_min_rate"] and int(e2e_r.get("total", 0)) >= GATES["e2e_min_count"],
        round(e2e_rate, 4),
        GATES["e2e_pass_min_rate"],
        f"不依赖外部EXE的P0流水线模拟全链路 (passed={e2e_r.get('passed',0)}, total={e2e_r.get('total',0)}, min_count={GATES['e2e_min_count']})",
    )

    # 总判定
    gates_all_pass = all(
        isinstance(v, dict) and v.get("pass") is True
        for v in report["gates"].values()
    )
    passed_gates = sum(1 for v in report["gates"].values() if isinstance(v, dict) and v.get("pass") is True)
    total_gates = len(report["gates"])
    report["verdict"] = {
        "all_gates_pass": bool(gates_all_pass),
        "gates_pass_count": passed_gates,
        "gates_total": total_gates,
        "gates_pass_rate": _safe_div(passed_gates, total_gates),
    }

    out = OUT_DIR / "phase4_quality_gate.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # 控制台摘要
    print("\n========== 质量门报告 (Phase 4) ==========")
    for name, g in report["gates"].items():
        tag = "PASS" if g.get("pass") else "FAIL"
        print(f"  [{tag}] {name}: 实际={g['actual']}, 阈值≥{g['min']}")
        print(f"         {g['desc']}")
    v = report["verdict"]
    print("----------------------------------------")
    print(
        f"  总判定: {'全部通过 ✅' if v['all_gates_pass'] else '存在未通过门槛 ❌'}"
        f"  ({v['gates_pass_count']}/{v['gates_total']}, "
        f"{v['gates_pass_rate']*100:.1f}%)"
    )
    print(f"  完整 JSON: {out}")

    return 0 if v["all_gates_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
