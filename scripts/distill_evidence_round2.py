"""2026-08-14 二轮证据蒸馏：fallback 质量专项 + 时域平滑选型（SG vs 中值滤波）"""
from __future__ import annotations
import sys, time, json
from pathlib import Path

ROOT = Path(r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault")
sys.path.insert(0, str(ROOT))

from core.evolution.knowledge_sink import KnowledgeSink

sink = KnowledgeSink()
SCOPE = "motion_matting"
RUN_ID = f"evidence_round2_{int(time.time())}"

sink.record_lesson(
    scope=SCOPE, decision="accept", score=90.0, run_id=RUN_ID,
    adjustments={
        "finding": "37 次传播崩塌(fallback)对最终输出质量影响≈0",
        "evidence": "auto_frame 兜底 37/37 非空(面积均值 51.6%)；fallback 帧邻帧阶跃 p50=0.005 优于全段基线 p50=0.0148；对最终 J500(SG15) 贡献 0/37",
        "implication": "FR 指标衡量 Tier1 内部效率而非最终质量——兜底机制已消化崩塌代价，M1-C 重定标 FR≤8% 具备质量侧正当性",
    },
    notes=["fallback 帧输出面积偏大(51.6%)，若后续主观 MOS 发现过曝，可在 fallback 分支下调 YOLO conf。"],
)
sink.record_lesson(
    scope=SCOPE, decision="accept", score=88.0, run_id=RUN_ID,
    adjustments={
        "method": "时域中值滤波(窗口9) 替代 SG15 作为 mask 时域平滑生产参数",
        "scan": "J500/面积比: raw=21/1.00, SG5=12/1.43, SG9=6/2.09, SG15=1/2.74, MED5=5/1.13, MED7=3/1.19, MED9=2/1.19",
        "production": "scripts/median_smooth_masks.py --window 9 (J500=2 <3 达标, IoU 0.915, p=4.8e-25)",
    },
    notes=[
        "SG 多项式拟合阶跃信号产生过冲+斜坡，把移动路径涂成 mask（面积膨胀 1.4-2.7×，fast 段 IoU 掉到 0.19）。",
        "中值滤波保留真实出现的像素值：去毛刺不涂轨迹，面积比 1.13-1.19，fast IoU 保持 0.83+。",
        "对二值/软 mask 的时域去抖，中值滤波全面优于 SG。",
    ],
)
sink.record_lesson(
    scope=SCOPE, decision="rollback", score=30.0, run_id=RUN_ID,
    adjustments={
        "broken_pattern": "SG15 时域平滑作为生产参数（仅看 J500=1 就定案）",
        "reason": "fast 段质心漂移均值 80.9px(最大 362px)、面积膨胀 2.74×、10% 帧 IoU<0.19——'果冻拖影'代价被 J500 掩盖",
        "lesson": "时域平滑必须同时报 J500 与拖影(IoU/质心漂移/面积比)两个维度，单指标定案会翻车",
    },
    notes=[],
)

stats = sink.stats()
print(json.dumps({"ok": True, "run_id": RUN_ID,
                  "motion_matting": stats["by_scope"].get(SCOPE, 0),
                  "total_lessons": stats["total_lessons"]}, ensure_ascii=False, indent=2))
