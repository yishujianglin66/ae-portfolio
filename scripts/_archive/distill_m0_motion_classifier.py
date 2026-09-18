"""M0 蒸馏: Layer 0 运动分级 (motion_classifier) 经验写入自进化知识库。

方案文档 §8.3: M0 运动分级验收后必跑一次, scope=motion_classifier
验收: 2+ 条 accept + 1 条 rollback; sink.experience_text("motion_classifier") 可读回
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
SCOPE = "motion_classifier"
RUN_ID = f"m0_motion_classifier_{int(time.time())}"

# ============================================================
# accept: 已生效的正确决策
# ============================================================
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=90.0,
    run_id=RUN_ID,
    adjustments={
        "method": "Farneback @ 1/4 分辨率 (320x180 for 1280x720)",
        "metric": "motion_energy = median(magnitude) / scale (全分辨率像素位移中值)",
        "thresholds": "static<5.0 / mid 5~20 / fast>20",
        "runtime": "500帧 17.2s < 20s (M0-C 达标)",
    },
    notes=[
        "Farneback 在 1/4 分辨率 (320x180) 算运动能量足够准且快，500帧总耗时 17.2s < 段时长 20s。",
        "小分辨率位移必须除以 scale(=0.25) 还原成全分辨率像素位移，阈值才与方案文档一致。",
        "基准段 2000~2500 分级结果: static=450 / mid=37 / fast=13 (三类均非零，M0-B 达标)。",
    ],
)
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=82.0,
    run_id=RUN_ID,
    adjustments={
        "smooth": "滑动中值平滑窗口=3 (默认开)",
        "purpose": "抑制单帧噪声导致 static/mid/fast 逐帧抖动 → 路由抖动",
    },
    notes=[
        "原始逐帧 median 在阈值边界(5.0/20.0)会来回翻转，路由会跟着抖。窗口3的中值平滑后分级稳定，代价可忽略。",
    ],
)
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=78.0,
    run_id=RUN_ID,
    adjustments={
        "flow_cache": "flow_cache/{fi:05d}.npy 每帧光流缓存 (段内索引 0..N-1)",
        "flow_semantics": "flow_cache[fi] = flow(fi-1 -> fi), flow_cache[0] = zeros",
        "reuse": "Layer 2A warp 直接复用，不重复计算光流",
    },
    notes=[
        "flow_cache 语义定义为 flow(fi-1→fi)，稳定帧 fi 时取 flow_cache[fi] 即可 warp 上一帧 mask。",
        "缓存的是 1/4 分辨率 flow；warp 前需 cv2.resize 放大并乘以 (1/scale) 还原全分辨率位移。",
    ],
)

# ============================================================
# rollback: 已踩过的坑，不要重犯
# ============================================================
sink.record_lesson(
    scope=SCOPE,
    decision="rollback",
    score=30.0,
    run_id=RUN_ID,
    adjustments={
        "broken_pattern": "用 py (3.14) 跑脚本",
        "actual_error": "Unable to create process using 'Python314\\python.exe' (启动器崩溃)",
    },
    notes=[
        "永远用 py -3.12。本机默认 py=3.14 解释器不可用（见 montage-card-point-rules.md §5）。",
    ],
)
sink.record_lesson(
    scope=SCOPE,
    decision="rollback",
    score=45.0,
    run_id=RUN_ID,
    adjustments={
        "broken_pattern": "在全分辨率 1280x720 做 Farneback 计算运动能量",
        "reason": "500 帧全分辨率光流预计 >20s，超出 M0-C 的 20s 预算",
    },
    notes=[
        "运动能量只需要中值统计，1/4 分辨率足够；全分辨率光流只留给 Layer 2A warp 需要时单独算。",
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
    "readback_preview": readback[:400],
}, ensure_ascii=False, indent=2))
