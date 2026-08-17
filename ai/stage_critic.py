# -*- coding: utf-8 -*-
"""渲染阶段自评 (StageCritic) — TEMPO 式中途价值估计 (2026-08-16)

借鉴小红书 dots 实验室 TEMPO: 长轨迹切 macro-step, 每阶段末 actor→critic 切换,
用推理估计"当前状态未来能获得多少回报", 作为未完轨迹的评估信号。

本项目映射: 渲染管线天然 macro-step (1.1节拍→1.3素材→1.4选材→2分镜→3渲染→4复核),
每阶段结束调用本模块自评, 输出进:
    - production_report.stage_self_critique  (终报可见)
    - run_notes.jsonl  (结构化轨迹, 供下一阶段 prompt 注入 + 未来 RL 训练)

成本: 默认走 doubao flash 档 (deepseek-v4-flash-ga), 单次 <1 分钱。
失败静默: 任何异常返回 None, 绝不阻断渲染主流程。

用法:
    from ai.stage_critic import StageCritic
    critic = StageCritic()
    note = await critic.critique(
        stage="1.4_selection",
        stage_summary="匹配 5/7 素材, 排除 2 个教程录屏",
        decisions="按燃向氛围排序, 覆盖度 1.3x",
        goal="进击的巨人高燃混剪 60s",
    )
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
NOTES_FILE = _PROJECT_ROOT / "tmp" / "run_notes.jsonl"

CRITIC_PROMPT = """你是视频渲染流水线的阶段评审员 (StageCritic)。
当前渲染任务的最终目标: {goal}

刚完成的阶段: {stage}
阶段产物摘要: {stage_summary}
本阶段关键决策: {decisions}

请评估: 以当前中间状态出发, 最终成片能达到目标质量的期望值是多少?
只输出 JSON, 不要其他文字:
{{
  "value": 0到10之间的数,
  "rationale": "一句话理由",
  "risks": ["风险1", "风险2"]
}}"""


class StageCritic:
    """渲染阶段自评器 — 调 LLM 估计阶段价值, 结果写 run_notes.jsonl。"""

    def __init__(self, notes_file: Optional[Path] = None):
        self._notes_file = notes_file or NOTES_FILE

    async def critique(
        self,
        stage: str,
        stage_summary: str,
        decisions: str,
        goal: str,
        provider: str = "doubao",
        model_type: str = "flash",
    ) -> Optional[Dict[str, Any]]:
        """自评单个阶段。返回 {stage, value, rationale, risks, timestamp} 或 None。"""
        try:
            from core.llm_gateway import llm_gateway
            # force=True: 加载 .env 并重新装配 providers (独立调用时环境未必已加载)
            llm_gateway.ensure_configured(force=True)

            prompt = CRITIC_PROMPT.format(
                goal=goal[:500], stage=stage,
                stage_summary=stage_summary[:800], decisions=decisions[:500],
            )
            resp = await llm_gateway.chat_with_provider(
                prompt=prompt,
                provider=provider,
                model_type=model_type,
                system_prompt="你是严谨的阶段评审员, 只输出 JSON。",
                temperature=0.3,
                max_tokens=300,
            )
            if not resp.success:
                return None

            content = (resp.content or "").strip()
            # 容错: 剥离 ```json 围栏
            if content.startswith("```"):
                content = content.strip("`")
                if content.startswith("json"):
                    content = content[4:]
            data = json.loads(content)
            value = max(0.0, min(10.0, float(data.get("value", 5.0))))
            note = {
                "stage": stage,
                "value": round(value, 2),
                "rationale": str(data.get("rationale", ""))[:300],
                "risks": [str(r)[:120] for r in data.get("risks", [])][:5],
                "timestamp": time.time(),
            }
            self._append_note(note)
            return note
        except Exception as e:
            # 自评失败静默: 不阻断渲染, 但记录到 notes (value=None 表示自评缺失)
            try:
                self._append_note({
                    "stage": stage, "value": None,
                    "rationale": f"[critic-failed] {type(e).__name__}",
                    "risks": [], "timestamp": time.time(),
                })
            except OSError:
                pass
            return None

    def _append_note(self, note: Dict[str, Any]) -> None:
        try:
            os.makedirs(self._notes_file.parent, exist_ok=True)
            with open(self._notes_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(note, ensure_ascii=False) + "\n")
        except OSError:
            pass

    @staticmethod
    def load_notes(notes_file: Optional[Path] = None,
                   max_notes: int = 10) -> list:
        """读最近 N 条 notes (供下一阶段 prompt 注入)。"""
        f = notes_file or NOTES_FILE
        if not f.exists():
            return []
        notes = []
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    notes.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        except OSError:
            return []
        return notes[-max_notes:]
