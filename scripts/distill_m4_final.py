"""M4 收尾蒸馏: 4层链路全链路验收经验（6空帧bug修复 + fast断链 + AE验证规程）写入自进化知识库。"""
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
RUN_ID = f"m4_final_20260814_{int(time.time())}"

qc = {}
try:
    qc = json.loads((ROOT / "output" / "step2_locator" / "qc_report_m4.json").read_text(encoding="utf-8"))
except Exception:
    pass

# ============ accept ============
sink.record_lesson(
    scope=SCOPE, decision="accept", score=88.0, run_id=RUN_ID,
    adjustments={
        "method": "L2A stab 链在 fast 帧断裂（prev_stab=None，本帧直出）",
        "reason": "硬切/快运动处光流 warp 先验失效；且 fast 大 mask 经 0.5/0.5 融合拖入后续 static 帧产生大面积半透明拖影",
        "evidence": "M4 inline 全链路 6 空帧根因之一；修复后 nonempty 494→500",
    },
    notes=["fast 权重 (0.75,0.25) 仍不够：切点两侧内容无关，链必须断，权重再偏 raw 也无法消除拖影。"],
)
sink.record_lesson(
    scope=SCOPE, decision="accept", score=85.0, run_id=RUN_ID,
    adjustments={
        "method": "refine_mask_edge 入口软输入二值化 (mask>64 → 0/255)",
        "reason": "stab 融合输出是软 alpha；guided filter + threshold(127) 假设二值输入，软 mask 大片 127 附近值 → guided 输出 p50=73 → 阈值塌缩整帧清空",
        "evidence": "g2007 stab=167371 像素 → refined=0 复现；二值化防御后 refined=29245",
    },
    notes=["正确顺序不变：Tier1 → 时序稳定(软) → 二值化 → 空间精修 → 羽化重建软边。"],
)
sink.record_lesson(
    scope=SCOPE, decision="accept", score=82.0, run_id=RUN_ID,
    adjustments={
        "method": "AE 真机 alpha 验证规程（M4-B 通过）",
        "checklist": "JSX return JSON.stringify / 中文用\\u转义 / applyTemplate 枚举候选含中文名(无损) / addSolid 后 moveToEnd / 渲染前删旧输出文件防覆盖对话框 / AE 渲染期间 scheduleTask 轮询暂停是正常的",
        "evidence": "MOV argb qtrle 正确解释 STRAIGHT(5412)，人物区透出橙色底，占比与 ffmpeg 读到的 alpha 面积吻合(59.6% vs 59.8%)",
    },
    notes=["footage.alphaMode 在 AE2025 是 undefined，正确 API 是 footage.mainSource.alphaMode。"],
)
sink.record_lesson(
    scope=SCOPE, decision="accept", score=80.0, run_id=RUN_ID,
    adjustments={
        "method": "make_one_mov_pipeline --engine enhanced（4层链路一键出 MOV+QC）",
        "evidence": "DL_黑岩射手 2000-2500 → 472MB qtrle argb MOV, QC PASS 6/6, 49s(复用mask)",
        "pitfalls_fixed": "step3 mask 索引需全局帧号对齐(start_frame+i)；skip 判断按段帧数；step4 emoji 打印 GBK 崩溃→stdout.reconfigure",
    },
    notes=["enhanced 引擎 mask 文件名为全局帧号 mask_02000.png，与老 auto_frame 链路 0 起不同。"],
)

# ============ rollback ============
sink.record_lesson(
    scope=SCOPE, decision="rollback", score=20.0, run_id=RUN_ID,
    adjustments={
        "broken_pattern": "stab 软 mask 直接进 guided filter（不先二值化）",
        "reason": "软 alpha 大片值≈127，guided 输出压到 p50=73，threshold(127) 后整帧清空 → 6 个 static KF 帧空 mask",
    },
    notes=["与 M2 蒸馏的'软输入'教训互补：时序稳定引入的软值必须在空间精修入口离散化。"],
)
sink.record_lesson(
    scope=SCOPE, decision="rollback", score=25.0, run_id=RUN_ID,
    adjustments={
        "broken_pattern": "AE comp.layers.addSolid 后不 moveToEnd",
        "reason": "add()/addSolid 均加到图层栈顶部，橙色底盖住 MOV → 渲染全屏纯橙，误判 alpha 全 0",
    },
    notes=["先 addSolid 再 add(footage) 或 addSolid 后 moveToEnd()。"],
)
sink.record_lesson(
    scope=SCOPE, decision="rollback", score=30.0, run_id=RUN_ID,
    adjustments={
        "broken_pattern": "PowerShell Get-Content(GBK) 读 UTF-8 params 再派生 JSON",
        "reason": "中文路径'黑岩射手'被 GBK 误读为乱码字节写回 → cv2.VideoCapture 打开失败 read 0 frames",
    },
    notes=["派生含中文路径的 JSON 必须用 UTF-8 端到端（write 工具或 -Encoding UTF8 + utf8-sig 读），禁止 Get-Content 默认编码中转。"],
)

stats = sink.stats()
print(json.dumps({
    "ok": True, "run_id": RUN_ID, "scope": SCOPE,
    "by_scope_count": stats["by_scope"].get(SCOPE, 0),
    "total_lessons": stats["total_lessons"],
}, ensure_ascii=False, indent=2))
