"""混合通道 J500 残余诊断结论蒸馏（2026-08-14 二轮）"""
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
RUN_ID = f"hybrid_j500_diag_{int(time.time())}"

sink.record_lesson(
    scope=SCOPE, decision="rollback", score=35.0, run_id=RUN_ID,
    adjustments={
        "broken_pattern": "对 RVM/SAM2 风格差异(面积 1-8% vs 30-80%)的拼接段期望 SG15 压平 J500 到 <3",
        "reason": "SG 斜坡(15帧窗口)上的逐帧差分仍 >0.5：2244→2245 Δ=0.546 命中；4 个残余跳变全部位于 RVM→SAM2 回退帧的阶跃斜坡上",
        "diagnosis": "RVM 保守输出(真实人物 ~5%)与 SAM2 伪影帧(80% 全幅)的 10× 面积阶跃，任何时域平滑都会在斜坡上产生可检测差分",
    },
    notes=[
        "crossfade 过渡会逐步把 RVM 段替换为 SAM2 段（RVM 权重→0），失去混合通道 FR 归零的意义，不值得。",
        "混合通道 J500=4 是结构下限；纯 SAM2+SG15 J500=1 才是质量指标的最优解。",
        "最终决策矩阵：质量→纯SAM2+SG15；FR口径/速度→RVM混合+SG15(接受J500=4)。",
    ],
)

stats = sink.stats()
print(json.dumps({"ok": True, "run_id": RUN_ID,
                  "motion_matting": stats["by_scope"].get(SCOPE, 0),
                  "total_lessons": stats["total_lessons"]}, ensure_ascii=False, indent=2))
