"""M2 蒸馏: Layer2A 光流 warp 时序稳定 (motion_matting) 经验写入自进化知识库。

方案文档 §8.3: M2 时序稳定验收后必跑一次, scope=motion_matting
验收: 2+ 条 accept + 1 条 rollback; sink.experience_text("motion_matting") 可读回
"""
from __future__ import annotations
import sys, time, json
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(ROOT))

from core.evolution.knowledge_sink import KnowledgeSink

sink = KnowledgeSink()
SCOPE = "motion_matting"
RUN_ID = f"m2_temporal_stabilize_{int(time.time())}"

qc = {}
try:
    qc = json.loads((ROOT / "output" / "step2_locator" / "qc_report_m2.json").read_text(encoding="utf-8"))
except Exception:
    pass
j500_a = qc.get("J500_A")
j500_b = qc.get("J500_B")
ttest = qc.get("pairwise_iou_ttest") or {}

# ============================================================
# accept
# ============================================================
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=94.0,
    run_id=RUN_ID,
    adjustments={
        "method": "RIFE warplayer.warp 双线性 + Farneback flow_cache(1/4分辨率)",
        "fusion": "Mask_N_stab = w_raw*Mask_N + w_prev*Warp(Mask_{N-1}->N)",
        "weights_by_level": "static(0.5/0.5) mid(0.6/0.4) fast(0.75/0.25)",
        "insert_point": "Tier1 输出之后、Tier2 refine_mask_edge 之前（先时序后空间）",
        "J500_baseline": j500_a,
        "J500_warp": j500_b,
        "ttest_mean_diff": ttest.get("mean_diff_B_minus_A"),
        "ttest_p": ttest.get("p_value"),
    },
    notes=[
        "warp 融合对边缘提供强先验：即使 SAM2 本帧偏 1-2px，上一帧的 warp 会把边缘拉回平滑轨迹。",
        "flow_cache 语义 flow_cache[fi]=flow(fi-1→fi)：稳定帧 fi 直接取 fi 的 flow，不需反向计算。",
        "1/4 分辨率 flow 放大回全分辨率必须乘以 (1/scale)，否则位移量缩小 4 倍，warp 几乎不移动。",
        "fast 级别权重更偏 raw(0.75) 防旧帧拖影；static 级别 0.5/0.5 最强平滑。",
    ],
)
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=80.0,
    run_id=RUN_ID,
    adjustments={
        "standalone": "scripts/stabilize_temporal.py 独立脚本（venv-sam2 python，需 torch+cuda）",
        "demo": "3 帧 demo 0.7s 验证通过（轮廓保持、边缘融合生效）",
    },
    notes=[
        "稳定链用上一帧的『已稳定』mask 作 warp 源（链式），比用原始 mask 平滑更强。",
        "warplayer.warp 需要 CUDA；py -3.12 无 torch，独立脚本必须用 D:\\AE-Work\\venv-sam2\\Scripts\\python.exe。",
    ],
)

# ============================================================
# rollback
# ============================================================
sink.record_lesson(
    scope=SCOPE,
    decision="rollback",
    score=50.0,
    run_id=RUN_ID,
    adjustments={
        "broken_pattern": "直接对 1/4 分辨率 flow 做 warp（不放大不乘 1/scale）",
        "reason": "位移量缩小 4 倍 → warp 几乎无效，融合退化为简单加权平均",
    },
    notes=[
        "正确姿势: flow_full = cv2.resize(flow_small, (W,H), INTER_LINEAR) * (1/scale)。",
    ],
)
sink.record_lesson(
    scope=SCOPE,
    decision="rollback",
    score=45.0,
    run_id=RUN_ID,
    adjustments={
        "broken_pattern": "在 Tier2 空间平滑之后再补时序稳定",
        "reason": "Tier2 的空间平滑（GuidedFilter/形态学）会把单帧细节磨掉，时序信息来源被破坏",
    },
    notes=[
        "顺序必须是: Tier1 mask → 时序稳定(warp) → Tier2 空间精修。方案 §4A.3 明确。",
    ],
)

stats = sink.stats()
readback = sink.experience_text(SCOPE, limit=10)
print(json.dumps({
    "ok": True,
    "run_id": RUN_ID,
    "scope": SCOPE,
    "by_scope_count": stats["by_scope"].get(SCOPE, 0),
    "total_lessons": stats["total_lessons"],
    "readback_lines": readback.count("\n") + 1 if readback else 0,
}, ensure_ascii=False, indent=2))
