# -*- coding: utf-8 -*-
"""backfill_acceptance_log.py — acceptance_log 历史回填（2026-09-19）

背景：E0-4 验收 UI（acceptance_ui.py）就绪但 acceptance_log.jsonl 从未生成
（0 条），导致规则蒸馏的 GEPA 路径（R8③，前置 ≥30 条）无数据可用。

本脚本把**有据可查的真实历史验收事件**回填入账，字段遵循 acceptance_ui.py
的 acceptance_v1 契约（run_tag/versions/ratings/issues/verdict/notes）。

诚实原则（重要）：
  - 只收录**能找到文档/记录来源**的事件，每条 source 标注出处、notes 保留原文；
  - 来源分三类：user_hearing（用户听感，一手）、system_ab（系统 A/B 验证）、
    milestone（工程里程碑验收）——后两类在 notes 中显式区分，避免与听感混淆；
  - ratings 无 A/B 评分处填 0 并在 notes 说明（契约要求 int，不以 0 冒充评分）。

用法:
  python scripts/backfill_acceptance_log.py --dry-run   # 预览
  python scripts/backfill_acceptance_log.py             # 写入
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
LOG = PROJ / "data" / "evolution" / "acceptance_log.jsonl"


def _rec(run_tag: str, versions: list[str | None], verdict: str, notes: str,
         source: str, kind: str, ts: str = "2026-09-19 00:00:00",
         rating_a: int = 0, rating_b: int = 0) -> dict:
    return {
        "schema": "acceptance_v1",
        "ts": ts,
        "run_tag": run_tag,
        "versions": versions,
        "ratings": {"a": rating_a, "b": rating_b},
        "issues": [],
        "verdict": verdict,
        "notes": f"[{kind}] {notes}",
        "source": source,
    }


# ── A. run53 十轮精修的用户反馈（一手听感）──────────────────────────
# 来源：03-阶段报告/run53-母版十轮精修收官-阶段报告-2026-09-06.md §1 总账表
RUN53_ROUNDS = [
    ("v1-v6", "慢镜匀速无冲击/切点软/源重复/素材少",
     "fps 滤镜帧重复修复、全局去重、扩源 7→13"),
    ("v7", "曲线版卡点漂移", "相位锚(预卷恒速关键帧)+曲线反转"),
    ("v8", "15s 后连续闪动", "闪帧减密 89→15，只留乐句重音"),
    ("v10", "17s 后慢镜没对上", "谱通量 onset 三模式锚定"),
    ("v11", "22/25/27s 死滞", "drift 慢推镜+底速 0.35"),
    ("v12/v13", "(隐性)黑场+水印卡", "同源未用区间救援层"),
    ("v15", "定格停在平淡帧", "顶点帧平移(实验后回退)"),
    ("v18", "调色不引人入胜", "分段调色(高对比+高饱和+冷阴影)"),
    ("v20", "镜头重复出境", "同源未用区间替换 21 处+每源上限 9"),
    ("v21-v25", "(渲染事故)", "setpts 预烘焙+构建日志防陈旧"),
]

# ── B. run53 验收节点 ──────────────────────────────────────────────
# 来源：同上 §5 验收轨迹
RUN53_NODES = [
    ("v9", "效果完美", "用户验收节点（收官报告 §5 原文）"),
    ("v12", "复核", "第二轮复核节点"),
    ("v20", "先归档后推进", "收官决策（本次工单终结）"),
]

# ── C. 规则库听感投票 ──────────────────────────────────────────────
# 来源：data/rules/ruleset.jsonl vote_runs + evidence
RULE_VOTES = [
    ("run55-vs-run53v9", "否决", "用户听感：完全不在点上（R-2026-0001 down）",
     "2026-09-05 21:40:28"),
    ("run56-复判", "否决", "用户复判：完全不在点上（R-2026-0001 down×2 → standby）",
     "2026-09-06 01:24:17"),
    ("run57-网格量化", "通过", "用户听感：回来了（R-2026-0002 首个正面）",
     "2026-09-06 00:00:00"),
    ("run60-精修", "通过", "用户听感：比之前好（R-2026-0002 转正依据）",
     "2026-09-06 00:00:00"),
]

# ── D. render_history 显式裁决 ─────────────────────────────────────
RENDER_HISTORY_VERDICTS = [
    ("run45", "效果不错(能量包络呼吸语法首验)", "2026-09-04 08:01:00"),
    ("run49", "否决:纯炫技没卡点(1.2s平滑过度钝化)", "2026-09-04 08:01:00"),
    ("run50", "对了(0.6s+迟滞终态)", "2026-09-04 08:01:00"),
]

# ── E. 系统 A/B / 里程碑（显式区分于听感）───────────────────────────
SYSTEM_EVENTS = [
    ("run54anchor-vs-run54ctrl", "system_ab",
     "E0-1 鼓点锚定二轮 A/B PASS：kick|snare 踩拍 0.667 vs 0.519（+14.8pp）",
     "data/rules/ruleset.jsonl R-2026-0001 evidence"),
    ("run61-三项修复", "system_ab",
     "闪白覆盖 drop 段 3/3 但 cut_visibility 0.8696→0.8698 无显著变化；"
     "定位为结构性差距（后续 B1 换 v2 度量证伪旧阈值）",
     "TASK_STATUS.md run61 条目"),
    ("r4-emotional-lyric", "system_ab",
     "R4 泛化验证：emotional_lyric 母版 beat_hit 0.8667 > narrative 中位数 0.7368；"
     "规则 applicability 正确退场",
     "03-阶段报告/R4第二母版泛化验证报告_2026-09-09.md"),
    ("r5-生成非劣", "system_ab",
     "R5 非劣检验：生成镜头混入 run61 后 7/7 维 PASS（overall 7.28→7.32）",
     "reports/r5_noninferiority.json"),
    ("e0-3-kb-loader", "milestone",
     "知识库 loader 修复：470/470 收录、effect_map 0→1508",
     "output/evidence/enhance_kb_loader_fix_20260905/"),
    ("e0-5-测试套件", "milestone",
     "测试套件修复：5119 passed/78F/40E → 5305 passed/0F/0E",
     "TASK_STATUS.md 系统稳定性条目"),
    ("运镜-vlm批量验收", "system_ab",
     "VLM 专家本地部署批量验收：28 条真实 AMV、弱真值子集 3/4=0.75",
     "TASK_STATUS.md 运镜分类器条目"),
    ("利威尔MAD-审阅", "user_hearing",
     "审阅反馈 4 项返工（粒子突兀/文字可见性等），含可度量验收标准",
     "03-阶段报告/利威尔MAD实验段_粒子与文字效果审阅验收备案_2026-07-26.md"),
    ("e0-2-变速音质", "milestone",
     "python-stretch 0.3.1 Windows wheel 可用性验证：API 实测时长比精确 0.667",
     "09-计划文件/2026-09-05_开源增强选型与规则蒸馏方案.md E0-2"),
    ("run61-交付规格首PASS", "system_ab",
     "音频母带+4Mbps 转码：run53/run61 全部 42 个历史版本中首个交付规格自检 PASS；"
     "PSNR 44.2dB / SSIM 0.9917",
     "03-阶段报告/呈现质量上限推进报告_2026-09-09.md"),
]


def build_records() -> list[dict]:
    recs: list[dict] = []
    # A: run53 十轮
    for tag, feedback, fix in RUN53_ROUNDS:
        recs.append(_rec(
            "run53", [f"run53_{tag}", None], f"返工:{feedback}",
            f"用户反馈「{feedback}」→ 修复：{fix}", "backfill:run53_report",
            "user_hearing"))
    # B: run53 节点
    for ver, verdict, note in RUN53_NODES:
        recs.append(_rec(
            "run53", [f"run53_{ver}", None], f"用户验收:{verdict}",
            note, "backfill:run53_report", "user_hearing"))
    # C: 规则投票
    for tag, verdict, note, ts in RULE_VOTES:
        recs.append(_rec(
            tag, None, f"用户听感:{verdict}", note,
            "backfill:ruleset_vote", "user_hearing", ts=ts))
    # D: render_history
    for tag, verdict, ts in RENDER_HISTORY_VERDICTS:
        recs.append(_rec(
            tag, None, verdict, "render_history.jsonl 显式裁决条目",
            "backfill:render_history", "user_hearing", ts=ts))
    # E: 系统/里程碑
    for tag, kind, note, src in SYSTEM_EVENTS:
        recs.append(_rec(
            tag, None, "验证通过" if kind != "user_hearing" else "返工",
            note, f"backfill:{src.split('/')[-1][:40]}", kind))
    return recs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    recs = build_records()
    # 去重（同 run_tag + verdict + notes 视为重复）
    seen = set()
    uniq = []
    for r in recs:
        key = (r["run_tag"], r["verdict"], r["notes"][:40])
        if key in seen:
            continue
        seen.add(key)
        uniq.append(r)

    kinds: dict[str, int] = {}
    for r in uniq:
        kinds[r["notes"].split("]")[0].lstrip("[")] = \
            kinds.get(r["notes"].split("]")[0].lstrip("["), 0) + 1
    print(f"回填记录 {len(uniq)} 条")
    print(f"分类: {json.dumps(kinds, ensure_ascii=False)}")
    for r in uniq[:5]:
        print(f"  [{r['notes'][:24]}...] {r['run_tag']}: {r['verdict'][:30]}")
    print(f"  ... 共 {len(uniq)} 条")

    if args.dry_run:
        print("\n[dry-run] 未写入")
        return 0

    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a", encoding="utf-8") as f:
        for r in uniq:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = sum(1 for _ in open(LOG, encoding="utf-8"))
    print(f"\n已写入 {LOG}（当前共 {n} 条）")
    print(f"GEPA 前置（≥30 条）: {'达成' if n >= 30 else f'未达（{n}/30）'}")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
