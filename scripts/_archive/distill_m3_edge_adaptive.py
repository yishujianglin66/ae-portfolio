"""M3 蒸馏: Layer 3 Tier2 边缘精修自适应参数 (edge_refine_tier2) 经验写入自进化知识库。

方案文档 §8.3: M3 参数自适应验收后必跑一次, scope=edge_refine_tier2
验收: 2+ 条 accept + 1 条 rollback; sink.experience_text("edge_refine_tier2") 可读回
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(ROOT))

from core.evolution.knowledge_sink import KnowledgeSink

sink = KnowledgeSink()
SCOPE = "edge_refine_tier2"
RUN_ID = f"m3_edge_adaptive_{int(time.time())}"

# ============================================================
# accept
# ============================================================
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=88.0,
    run_id=RUN_ID,
    adjustments={
        "signature": "refine_mask_edge(mask, guide_bgr, motion_level='static') 向后兼容",
        "param_table": (
            "static: r=4,close3x3x2,open2x2x1,feather5x5,min_area500 | "
            "mid: r=6,close5x5x3,feather5x5,min_area400 | "
            "fast: r=4,close5x5x3,feather3x3,min_area300"
        ),
        "rationale": "快运动 mask 易撕裂→更大 Close 核补断；快运动硬边防糊→羽化 3x3；碎片多→min_area 降低",
    },
    notes=[
        "static 行保持现状参数（r=4 是代码实际值，方案文档记的 r=8 与代码不符，以代码为准保证基线可比）。",
        "参数表 dict 替换 magic number，默认值 static 保证未启用 routing 的运行行为不变。",
    ],
)
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=75.0,
    run_id=RUN_ID,
    adjustments={
        "level_source": "motion_levels.json 的逐帧级别直接驱动 Tier2 参数查表",
    },
    notes=[
        "同一段内 static/mid/fast 各自用不同精修参数，A/B 对比才能看出自适应价值。",
    ],
)

# ============================================================
# rollback
# ============================================================
sink.record_lesson(
    scope=SCOPE,
    decision="rollback",
    score=42.0,
    run_id=RUN_ID,
    adjustments={
        "broken_pattern": "Guided Filter 用大 radius(8) 处理 fast 运动帧",
        "reason": "r=8 在快速运动时过度平滑锐利边缘，人物轮廓变糊",
    },
    notes=[
        "fast 用 r=4 贴合细节；radius 应随运动级别降低，不是升高。",
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
