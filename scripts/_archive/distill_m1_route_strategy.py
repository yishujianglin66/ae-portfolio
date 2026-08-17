"""M1 蒸馏: Layer 1 分层路由 (motion_matting) 经验写入自进化知识库。

方案文档 §8.3: M1 分层路由验收后必跑一次, scope=motion_matting
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
RUN_ID = f"m1_route_strategy_{int(time.time())}"

# 从 QC 报告读取实际指标（若存在）
qc = {}
try:
    qc = json.loads((ROOT / "output" / "step2_locator" / "qc_report_m1.json").read_text(encoding="utf-8"))
except Exception:
    pass
fr = (qc.get("A_run") or {}).get("fallback_rate_excl_routed") or (qc.get("A_run") or {}).get("fallback_rate")
gpu_ratio = qc.get("GPU_T_ratio_B_over_A")
switches = ((qc.get("A_run") or {}).get("motion_route") or {}).get("mode_switches")

# ============================================================
# accept: 已生效的正确决策
# ============================================================
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=93.0,
    run_id=RUN_ID,
    adjustments={
        "route_table": "static->video ki=8 / mid->video ki=4+thr0.4+连续2帧 / fast->auto_frame逐帧",
        "fallback_rate_excl_routed": fr,
        "mode_switches": switches,
        "gpu_time_ratio": gpu_ratio,
    },
    notes=[
        "fast 帧是「路由」不是「回退」：不计入 fallback_rate，单独 routed_fast_count 记录（否则 fast=13 帧直接 >2% 目标，数学上不可能达标）。",
        "[MOTION_ROUTE] 日志落盘 qc_routing_log.txt，mode 切换次数可直接 grep 统计。",
        "关键帧调度按级别自适应（KI_TABLE），fast 帧不设 KF 锚点（PIT-1），DYN-KF 加密也跳过 fast 帧。",
    ],
)
sink.record_lesson(
    scope=SCOPE,
    decision="accept",
    score=85.0,
    run_id=RUN_ID,
    adjustments={
        "mid_fallback": "面积<KF*0.4 且连续2帧命中才回退（防单帧噪声误触发）",
    },
    notes=[
        "mid 级别阈值收紧到 0.4 且要求连续 2 帧，避免人物转身/遮挡单帧面积骤降导致的过度回退。",
    ],
)

# ============================================================
# rollback: 已踩过的坑，不要重犯
# ============================================================
sink.record_lesson(
    scope=SCOPE,
    decision="rollback",
    score=40.0,
    run_id=RUN_ID,
    adjustments={
        "broken_pattern": "PowerShell '*>' 重定向 stderr 到日志文件 + SAM2 内部 tqdm 进度条",
        "actual_error": "OSError: [Errno 22] Invalid argument @ tqdm fp.write('\\r'...) — 传播 41% 处整段崩溃",
    },
    notes=[
        "Windows 下 tqdm 写 \\r 到重定向文件报 Errno 22。解法：启动前 $env:TQDM_DISABLE='1'（SAM2 propagate_in_video 的 tqdm 全部静音）。",
        "GPU 长任务日志必须用 TQDM_DISABLE=1，否则 PowerShell 重定向时随机崩溃。",
    ],
)
sink.record_lesson(
    scope=SCOPE,
    decision="rollback",
    score=35.0,
    run_id=RUN_ID,
    adjustments={
        "broken_pattern": "两个 SAM2 GPU 任务并发启动（RTX 4060 8GB 显存）",
        "reason": "两个 hiera_large 模型无法同时驻留显存 → OOM 风险，只能串行",
    },
    notes=[
        "单 GPU 环境 GPU 推理任务必须串行排队；先后台跑第一个，完成后（.ok 文件出现）再启动第二个。",
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
