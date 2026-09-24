"""induct_candidate_rules.py — R8③ 首轮候选规则归纳（2026-09-19）。

定位
----
R8③（DSPy GEPA 归纳路径）的数据前置是 `data/evolution/acceptance_log.jsonl`
≥30 条 —— 现已达成（34 条）。本脚本执行**首轮候选规则生成**：把验收日志里反复
出现的听感主题归纳成规则候选，交给规则库正常生命周期（seed → vote）走。

设计红线（对齐 rule_registry 的治理约束）
----------------------------------------
1. **候选不直接入池**：候选写入固定的 `data/rules/candidates_round1.jsonl`，
   只有经 `rule_registry` 投票才转正 —— 归纳产物不得绕过治理。
2. **无量化证据不得 active**：`rule_registry.validate_schema` 硬要求
   `evidence.gate_score_delta`。本脚本**只填实测到的 delta**（`MEASURED` 表，
   每条都带报告路径与可比数值）；测不到的一律留空并给出 `evidence_gap`
   （该测哪个指标 + 怎么测），标记 `blocked_pending_measurement`。
   **绝不编造数字**。
3. **与在库规则去重**：命中在库规则的注入点+主题词的候选标 `covered_by`，
   避免"同一件事两条规则"。
4. **落盘位置固定**：输出路径为模块常量（无路径类参数），且用原子写
   （临时文件 + `os.replace`），不会半途留下残缺文件。

主题表来源：run53 十轮精修的返工清单（acceptance_log 前 10 条）+ render_history
的否决条目 + 2026-09-19 运镜线三轮听感。每条主题都指向它在日志中的原话。

用法:
  python scripts/induct_candidate_rules.py            # 写 data/rules/candidates_round1.jsonl
  python scripts/induct_candidate_rules.py --dry-run  # 只打印不落盘
  python scripts/induct_candidate_rules.py --report   # 额外写 reports/candidates_round1.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJ))

LOG = PROJ / "data" / "evolution" / "acceptance_log.jsonl"
OUT_FILE = PROJ / "data" / "rules" / "candidates_round1.jsonl"
REPORT_FILE = PROJ / "reports" / "candidates_round1.json"

# ── 实测证据表（只放**真的量过**的数据；每条带证据来源）──────────────
# outcome: "pass" = 实测支持该陈述（可转正）; "fail" = 实测反例（保留数值但不可转正,
#           见 evidence_gap.failed_measurement —— 规则陈述需修订或下线）。
# 来源: reports/candidate_metrics_round1.json (2026-09-19, 基于 v9 定稿实测)
MEASURED: dict[str, dict] = {
    "camera_punch_beat": {
        "outcome": "pass",
        "gate_score_delta": "+68.5pp 撞点强鼓点占比 (31.5%→100.0%)",
        "metrics": {"strong_drum_punch_pct": {"before": 0.315, "after": 1.0},
                    "envelope_duty_pct": {"before": 0.92, "after": 0.39}},
        "evidence_path": "reports/punch_beat_27s_v9.json",
    },
    "impact_violin_follow": {
        "outcome": "pass",
        "gate_score_delta": "全曲跟随小提琴重音: 铺垫 0→0.64 次/秒, 撞击 20→36 次",
        "metrics": {"punch_per_sec_build": {"before": 0.0, "after": 0.64},
                    "punch_total": {"before": 20, "after": 36}},
        "evidence_path": "reports/punch_beat_27s_v9.json",
    },
    "cut_soft": {
        "outcome": "pass",
        "gate_score_delta": "+10.1pp 切点强锚命中 (5.5%→15.6%)",
        "metrics": {"strong_anchor_hit": {"before": 0.055, "after": 0.156}},
        "evidence_path": "03-阶段报告/踩点修复与合成丢帧根因报告_2026-09-19.md",
    },
    "av_length_integrity": {
        "outcome": "pass",
        "gate_score_delta": "视频流补齐 1.67s (25.33s→27.00s, 648 帧)",
        "metrics": {"video_frames": {"before": 608, "after": 648}},
        "evidence_path": "03-阶段报告/踩点修复与合成丢帧根因报告_2026-09-19.md",
    },
    "material_scarce": {
        "outcome": "pass",
        "gate_score_delta": "素材池 7→13 源（日志记载的扩源修复），v9 实测 13 ✓",
        "metrics": {"source_count": {"before": 7, "after": 13, "threshold_min": 13}},
        "evidence_path": "reports/candidate_metrics_round1.json",
    },
    "black_frame_watermark": {
        "outcome": "pass",
        "gate_score_delta": "v9 全片 648 帧黑/白场帧 0；交付规格台标检测 PASS",
        "metrics": {"black_frame_count": {"value": 0, "threshold_max": 0}},
        "evidence_path": "reports/candidate_metrics_round1.json",
    },
    "dead_moment": {
        "outcome": "pass",
        "gate_score_delta": "最低 1s 窗口运动能量/全片中位 = 0.556（阈值 ≥0.35）",
        "metrics": {"motion_floor_over_median": {"value": 0.556, "threshold_min": 0.35}},
        "evidence_path": "reports/candidate_metrics_round1.json",
    },
    "slowmo_uniform": {
        "outcome": "pass",
        "gate_score_delta": "44 个慢镜段内运动能量峰值/中位 = 35.7（有强对比，非匀速死水）",
        "metrics": {"slowmo_peak_over_median": {"value": 35.66, "segment_count": 44}},
        "evidence_path": "reports/candidate_metrics_round1.json",
    },
    "curve_beat_drift": {
        "outcome": "pass",
        "gate_score_delta": "曲线段边界切点强锚命中 28.6% vs 非曲线段 13.9% —— 曲线不拖踩点反更准",
        "metrics": {"curve_boundary_strong_hit": {"value": 0.2857, "n": 14},
                    "other_strong_hit": {"value": 0.1392, "n": 79}},
        "evidence_path": "reports/candidate_metrics_round1.json",
    },
    "source_repeat": {
        # 实测反例: 单源占比 10.0% > 陈述的 ≤8%。保留数值但不可转正 ——
        # 陈述需修订（阈值或按片长缩放），或承认这是 27s 片的真实缺陷。
        "outcome": "fail",
        "gate_score_delta": "",
        "metrics": {"single_source_share_pct": {"value": 10.0, "threshold_max": 8.0,
                                                "top_source": "alya-05.mp4"},
                    "max_consecutive_same_source": {"value": 2}},
        "evidence_path": "reports/candidate_metrics_round1.json",
    },
    "flash_overdense": {
        # 判据必须用项目自己的 C4 口径（fade 到纯白/纯黑 → luma<6 或 >249），
        # 否则会把"亮镜头"误计成闪帧：粗代理指标给出 66 事件/2.44 每秒（假阳性），
        # C4 严格判据给出 0 帧。留此备注以免下次又用代理指标误判。
        "outcome": "pass",
        "gate_score_delta": "C4 严格判据闪帧 0 个 / 648 帧 (0.00/秒, 阈值 ≤3/秒)",
        "metrics": {"flash_frames_c4": {"value": 0, "threshold_max_per_sec": 3.0},
                    "_proxy_caveat": {"proxy_events": 66, "proxy_per_sec": 2.44,
                                      "note": "粗代理(切点邻域亮度极值)会把亮镜头误计为闪帧, 不可用于判据"}},
        "evidence_path": "reports/candidate_metrics_round1.json",
    },
    "color_not_engaging": {
        # 陈述是"禁止全片单一 LUT" —— 实测按 mood 派发了 3 档 (intro/build/drop),
        # 且实测域差与预设意图一致 (sat 1.35→1.50 即约 +11%, 实测 sat 域差 +12% 相对值)。
        "outcome": "pass",
        "gate_score_delta": "3 档按 mood 派发 (sat 1.35/1.40/1.50, contrast 1.04/1.06/1.08)；实测 sat 域差 0.03、contrast 域差 4.18，与预设意图一致",
        "metrics": {"sat_range_across_moods": {"value": 0.03},
                    "contrast_range_across_moods": {"value": 4.18},
                    "grades_dispatched": {"value": 3, "moods": ["intro", "build", "drop"]}},
        "evidence_path": "reports/candidate_metrics_round1.json",
    },
}

# ── 主题表（关键词 → 规则候选）────────────────────────────────────────
THEMES: list[dict] = [
    {
        "theme_id": "slowmo_uniform",
        "keywords": ["慢镜匀速", "无冲击", "慢镜"],
        "statement": "慢镜不得匀速播放：变速曲线须有快慢对比（慢放落拍），"
                     "匀速慢镜读作'卡住'而非'蓄力'",
        "form": "curve", "inject_point": "speed_curve",
        "applicability": {"duration_range": [15, 45],
                          "style": ["amv_highenergy", "燃向"],
                          "exceptions": "抒情段可保留匀速慢镜（能量 < 0.3）"},
        "metric": "slowmo_impact_ratio (慢镜段内帧间运动能量峰值/中位)",
        "measure_cmd": "python scripts/beat_anchor_check.py --video <mp4>",
    },
    {
        "theme_id": "cut_soft",
        "keywords": ["切点软", "切点漂移"],
        "statement": "切点必须锚定鼓点真值：软切（偏离重音 >80ms）视为缺陷，"
                     "修复路径必须保节拍（不得以丢弃踩点刀为代价）",
        "form": "constraint", "inject_point": "cut_anchor",
        "applicability": {"duration_range": [15, 45], "style": ["amv_highenergy"]},
        "metric": "strong_anchor_hit_rate",
        "measure_cmd": "python scripts/beat_anchor_check.py --video <mp4>",
    },
    {
        "theme_id": "source_repeat",
        "keywords": ["源重复", "镜头重复", "重复出境"],
        "statement": "单源占比 ≤8%，同源镜头不得连续出境；"
                     "替换优先级 = 同源未用区间 > 新源",
        "form": "dosage", "inject_point": "material_assign",
        "applicability": {"duration_range": [15, 60]},
        "metric": "single_source_share_pct, consecutive_same_source_runs",
        "measure_cmd": "python scripts/verify_v5_static.py --dir output/unified_<tag>",
    },
    {
        "theme_id": "material_scarce",
        "keywords": ["素材少"],
        "statement": "素材池源数 ≥13（低于此值重复感无法靠算法弥补）",
        "form": "dosage", "inject_point": "material_assign",
        "applicability": {"duration_range": [15, 60]},
        "metric": "source_count",
        "measure_cmd": "python scripts/reference_stats.py",
    },
    {
        "theme_id": "curve_beat_drift",
        "keywords": ["卡点漂移", "没对上"],
        "statement": "变速曲线不得引入相位漂移：子段边界吸附律动拍点，"
                     "曲线均值 = 段速度（跨度守恒）",
        "form": "curve", "inject_point": "speed_curve",
        "applicability": {"duration_range": [15, 45], "style": ["amv_highenergy"]},
        "metric": "beat_hit_rate (曲线段与非曲线段分组)",
        "measure_cmd": "python scripts/beat_anchor_check.py --video <mp4>",
    },
    {
        "theme_id": "flash_overdense",
        "keywords": ["连续闪动", "闪帧"],
        "statement": "闪帧只留乐句重音：连续闪动 ≥3 次/秒 视为疲劳缺陷",
        "form": "dosage", "inject_point": "effect_map",
        "applicability": {"duration_range": [15, 45]},
        "metric": "flash_per_sec",
        "measure_cmd": "python scripts/cut_visibility_v2.py --video <mp4>",
    },
    {
        "theme_id": "dead_moment",
        "keywords": ["死滞"],
        "statement": "禁止死滞段：任一秒窗口内运动能量不得低于全片中位数的 35%",
        "form": "dosage", "inject_point": "speed_curve",
        "applicability": {"duration_range": [15, 60]},
        "metric": "motion_energy_floor_ratio",
        "measure_cmd": "python scripts/beat_anchor_check.py --video <mp4>",
    },
    {
        "theme_id": "black_frame_watermark",
        "keywords": ["黑场", "水印"],
        "statement": "成片不得含黑场/水印卡：交付前逐帧亮度下界与边缘稳定性必须过检",
        "form": "constraint", "inject_point": "transition",
        "applicability": {"duration_range": [15, 600]},
        "metric": "black_frame_count, watermark_confidence",
        "measure_cmd": "python scripts/check_delivery_spec.py <mp4>",
    },
    {
        "theme_id": "freeze_plain_frame",
        "keywords": ["定格", "平淡帧"],
        "statement": "定格帧必须落在视觉顶点（构图/情绪峰值），不得停在平淡帧",
        "form": "mapping", "inject_point": "effect_map",
        "applicability": {"duration_range": [15, 45]},
        "metric": "freeze_frame_peak_score",
        "measure_cmd": "python scripts/cut_visibility_v2.py --video <mp4>",
    },
    {
        "theme_id": "color_not_engaging",
        "keywords": ["调色", "引人入胜"],
        "statement": "调色分段化：按能量段给不同对比/饱和/阴影，禁止全片单一 LUT",
        "form": "dosage", "inject_point": "effect_map",
        "applicability": {"duration_range": [15, 60]},
        "metric": "color_harmony_score (分段方差)",
        "measure_cmd": "python scripts/unified_edit.py --score-only <mp4>",
    },
    {
        "theme_id": "camera_punch_beat",
        "keywords": ["拉镜", "动感", "撞击", "不踩点"],
        "statement": "脉冲运镜撞击必须落在感知重音上：强鼓点(≥0.5) ∪ 小提琴重音"
                     "(≥0.85)，且相邻撞击间隔 ≥ 包络帧数（不重叠）",
        "form": "constraint", "inject_point": "effect_map",
        "applicability": {"duration_range": [15, 45],
                          "style": ["amv_highenergy", "燃向"],
                          "exceptions": "MASTER_PUNCH_MELODY_SCOPE=off 可退回纯打击乐"},
        "metric": "strong_drum_punch_pct, envelope_duty_pct",
        "measure_cmd": "python scripts/punch_beat_check.py --dir output/unified_<tag>",
    },
    {
        "theme_id": "impact_violin_follow",
        "keywords": ["小提琴", "冲击力不到位", "不够"],
        "statement": "运镜须跟随小提琴节奏变换：旋律锚按强度门槛(≥0.85 ≈ P80)接入"
                     "撞击，覆盖铺垫与爆发两段；撞击包络 ≤ 节拍间隔（快起快回）",
        "form": "dosage", "inject_point": "effect_map",
        "applicability": {"duration_range": [15, 45],
                          "exceptions": "全量旋律锚(4.4-5.9/s)不得接入，必然重叠"},
        "metric": "punch_per_sec_build, punch_total",
        "measure_cmd": "python scripts/punch_beat_check.py --dir output/unified_<tag>",
    },
    {
        "theme_id": "av_length_integrity",
        "keywords": ["时长", "提前结束", "缺帧"],
        "statement": "成片视频流帧数必须 == Σ round(段时长×帧率)：曲线子片段按边界帧号"
                     "差分分配，段级对账在段末补齐（不动切点位置）",
        # inject_point 必须落在 rule_registry.INJECT_POINTS 内（契约测试会拦）：
        # 帧数完整性作用于合成出的时间线，registry 现有的最近接点是 effect_map
        "form": "constraint", "inject_point": "effect_map",
        "applicability": {"duration_range": [5, 600]},
        "metric": "video_frames",
        "measure_cmd": "python scripts/check_delivery_spec.py <mp4>",
    },
]


def _atomic_write_jsonl(rows: list[dict]) -> None:
    """原子写：先写同目录临时文件再 os.replace，避免半截文件。"""
    tmp = OUT_FILE.with_name(OUT_FILE.name + ".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                   encoding="utf-8")
    os.replace(tmp, OUT_FILE)


def _log_rows() -> list[dict]:
    if not LOG.exists():
        return []
    out = []
    for ln in LOG.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except json.JSONDecodeError:
                continue
    return out


def mine(theme: dict, rows: list[dict]) -> dict:
    """在验收日志里检索该主题的证据条目。"""
    hits = []
    for r in rows:
        blob = f"{r.get('verdict', '')} {r.get('notes', '')} {r.get('issues', '')}"
        if any(k in blob for k in theme["keywords"]):
            hits.append({
                "run_tag": r.get("run_tag"),
                "ts": r.get("ts"),
                "kind": (str(r.get("notes", "")).split("]")[0].lstrip("[") or "?"),
                "verdict": str(r.get("verdict", ""))[:60],
                "source": r.get("source"),
            })
    kinds = Counter(h["kind"] for h in hits)
    return {"n_evidence": len(hits), "by_kind": dict(kinds),
            "source_runs": sorted({h["run_tag"] for h in hits if h["run_tag"]}),
            "hits": hits}


# 覆盖判别词：命中在库规则 statement 即认为该主题已被治理（按主题给判别词，
# 而不是拿整条关键词短语去匹配 —— 规则陈述的措辞与日志原话必然不同）。
DEDUPE_KEYS: dict[str, list[str]] = {
    "cut_soft": ["切点", "锚"],
    "curve_beat_drift": ["切点", "网格", "锚"],
    "camera_punch_beat": ["运镜", "撞击", "脉冲"],
    "impact_violin_follow": ["运镜", "撞击", "旋律"],
    "av_length_integrity": ["帧", "时长"],
    "slowmo_uniform": ["变速", "慢"],
    "source_repeat": ["源", "重复"],
    "material_scarce": ["素材", "源"],
    "flash_overdense": ["闪"],
    "dead_moment": ["死滞", "能量"],
}


def live_rules() -> list[dict]:
    try:
        from scripts.rule_registry import load_ruleset
        return load_ruleset()
    except Exception:  # noqa: BLE001
        return []


def build_candidates() -> tuple[list[dict], list[dict]]:
    rows = _log_rows()
    rules = live_rules()
    cands, blocked = [], []
    for i, t in enumerate(THEMES, start=1):
        ev = mine(t, rows)
        rid = f"R-2026-9{i:03d}"
        covered = None
        keys = DEDUPE_KEYS.get(t["theme_id"], t["keywords"][:2])
        for r in rules:
            if r.get("inject_point") != t["inject_point"]:
                continue
            stmt = str(r.get("statement", ""))
            if any(k in stmt for k in keys):
                covered = r.get("rule_id")
                break
        meas = MEASURED.get(t["theme_id"])
        passed = bool(meas) and meas.get("outcome") == "pass"
        rec = {
            "rule_id": rid,
            "statement": t["statement"],
            "form": t["form"],
            "inject_point": t["inject_point"],
            "applicability": t["applicability"],
            "confidence": round(min(0.9, 0.4 + 0.12 * ev["n_evidence"]), 2),
            "status": "standby",
            "votes": {"up": 0, "down": 0},
            "evidence": {
                "source_runs": ev["source_runs"],
                "n_evidence": ev["n_evidence"],
                "by_kind": ev["by_kind"],
                # 实测反例 (outcome=fail) 不给 gate_score_delta —— 过不了闸门,
                # 数值保留在 evidence_gap.failed_measurement 里供修订陈述用。
                "gate_score_delta": (meas or {}).get("gate_score_delta", "") if passed else "",
                "metrics": (meas or {}).get("metrics", {}),
                "evidence_path": (meas or {}).get("evidence_path", ""),
            },
            "induction": {
                "round": 1,
                "theme_id": t["theme_id"],
                "method": "acceptance_log 主题归纳 + 实测证据回填",
                "sample_verdicts": [h["verdict"] for h in ev["hits"][:3]],
                "covered_by": covered,
            },
        }
        if not passed:
            gap = {
                "status": ("failed_threshold" if meas else
                           "blocked_pending_measurement"),
                "metric": t["metric"],
                "measure_cmd": t["measure_cmd"],
            }
            if meas:      # 实测反例: 数值与阈值都要留档, 否则等于白测
                _m = json.dumps(meas["metrics"], ensure_ascii=False)
                gap["why"] = f"实测不满足陈述: {_m} —— 陈述需修订或下线"
                gap["failed_measurement"] = meas["metrics"]
                gap["evidence_path"] = meas["evidence_path"]
            else:
                gap["why"] = "无实测 gate_score_delta → rule_registry 闸门不允许转 active"
            rec["evidence_gap"] = gap
            blocked.append(rec)
        cands.append(rec)
    return cands, blocked


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印不落盘")
    ap.add_argument("--report", action="store_true",
                    help="额外写 reports/candidates_round1.json")
    args = ap.parse_args()

    cands, blocked = build_candidates()
    rows = _log_rows()
    if not rows:
        print(f"验收日志为空: {LOG}")
        return 2

    print(f"\n=== R8③ 首轮候选规则归纳 (日志 {len(rows)} 条) ===")
    print(f"{'rule_id':<13}{'theme':<24}{'证据':<6}{'覆盖':<14}证据状态")
    for c in cands:
        ind = c["induction"]
        if c["evidence"].get("gate_score_delta"):
            st = "可转正(有实测 delta)"
        elif c.get("evidence_gap", {}).get("status") == "failed_threshold":
            st = "实测反例(陈述需修订)"
        else:
            st = "待测量"
        print(f"{c['rule_id']:<13}{ind['theme_id']:<24}"
              f"{c['evidence']['n_evidence']:<6}"
              f"{(ind['covered_by'] or '-'):<14}{st}")
    print(f"\n候选 {len(cands)} 条 | 有实测证据 {len(cands)-len(blocked)} 条 | "
          f"待测量 {len(blocked)} 条")
    if blocked:
        print("\n待测量候选所需指标（不编造数字）:")
        for c in blocked:
            print(f"  {c['rule_id']} {c['induction']['theme_id']}: "
                  f"{c['evidence_gap']['metric']}")

    if args.dry_run:
        print("\n[dry-run] 未写入")
        return 0
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_jsonl(cands)
    print(f"\n→ {OUT_FILE} ({len(cands)} 条)")
    if args.report:
        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(json.dumps(
            {"log_entries": len(rows), "candidates": cands,
             "blocked": [c["rule_id"] for c in blocked]},
            ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"→ {REPORT_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
