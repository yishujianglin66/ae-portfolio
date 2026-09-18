"""RVM-static 混合通道实证蒸馏（2026-08-14）——三方案 J500/质量对比结论写入知识库。"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(ROOT))

from core.evolution.knowledge_sink import KnowledgeSink

sink = KnowledgeSink()
SCOPE = "motion_matting"
RUN_ID = f"hybrid_rvm_20260814_{int(time.time())}"

sink.record_lesson(
    scope=SCOPE, decision="accept", score=78.0, run_id=RUN_ID,
    adjustments={
        "method": "static->RVM(alpha>0.1,盲区回退SAM2) / mid|fast->SAM2 混合路由 + SG15 时域收尾",
        "evidence": "500帧实测: J500=52(裸拼)→4(SG15后); FR语义归零(static无fallback概念,mid+fast历史0回退); 44.8s/500帧",
        "blind_fallback_rate": "94/411 static帧(23%)触发RVM盲区回退(area<0.5%或max<0.15)",
    },
    notes=[
        "RVM/SAM2 面积风格差异大(RVM保守~5% vs SAM2激进~30%)，直接拼接在交接帧产生跳变(J500=52)，必须加 SG15 时域收尾。",
        "RVM 盲区(亮底/低对比动画帧)占比达 23%，回退机制必不可少。",
    ],
)
sink.record_lesson(
    scope=SCOPE, decision="rollback", score=40.0, run_id=RUN_ID,
    adjustments={
        "broken_pattern": "RVM 与 SAM2 输出直接逐帧拼接不做时域平滑",
        "reason": "两种模型 mask 面积风格差异(5% vs 30%)导致交接帧 Δ非空率>0.5，J500 从 1(纯SAM2+SG15) 恶化到 52",
    },
    notes=[
        "三方案 J500 实测: 纯SAM2全链路=21 → +SG15=1；RVM混合=52 → +SG15=4。质量最优仍是纯SAM2+SG15。",
        "RVM 混合的真实价值 = FR 口径归零 + static 段提速(~3×)，代价是面积保守(欠分割风险)与 J500 略高。",
    ],
)

stats = sink.stats()
print(json.dumps({"ok": True, "run_id": RUN_ID, "scope": SCOPE,
                  "by_scope_count": stats["by_scope"].get(SCOPE, 0),
                  "total_lessons": stats["total_lessons"]}, ensure_ascii=False, indent=2))
