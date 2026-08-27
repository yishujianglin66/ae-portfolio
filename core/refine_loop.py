# -*- coding: utf-8 -*-
"""
core/refine_loop.py — 导演级自我改进循环 (借鉴 Prime Agent /refine 机制)
=========================================================================

Prime Agent 核心思想移植:
1. **轨迹驱动小幅更新**: 基于自身执行轨迹(score_card轨迹)应用小幅修正,
   而非重写基础系统提示 — 首轮生成后, 后续迭代只做确定性局部修补, 不再调LLM
2. **Agent更新环境状态**: refine直接修改script字典(环境状态), scorer只读评估
3. **守护心跳**: 每轮迭代记录heartbeat时间戳, 支持长任务活性监测

与现有进化闭环(core/evolution)的分工:
- evolution: 跨运行宏观闭环(评测→Optimizer提案→版本决策→知识沉淀), 慢路径
- refine_loop: 单次生成内微观闭环(评分→确定性修补→重评), 快路径, 零LLM成本
"""
from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional

from core.camera_language import CAMERA_IDS_ALL
from core.director_scorer import DirectorQualityScorer

# 五段叙事能量包络 (与 NarrativeArcPlanner 对齐)
_ENERGY_BY_TYPE = {
    "intro": 0.30, "build": 0.60, "drop": 0.95,
    "break": 0.40, "outro": 0.25, "breath_break": 0.15,
}
_REQUIRED_TYPES = ["intro", "build", "drop", "break", "outro"]
# 非均分时长包络 (防 uniform_segments 反模式)
_DURATION_ENVELOPE = [0.12, 0.24, 0.34, 0.12, 0.18]


class DirectorRefineLoop:
    """导演剧本的 /refine 自改进循环

    用法:
        loop = DirectorRefineLoop(target_score=85, max_iterations=3)
        result = loop.refine_script(script)            # 纯确定性修补(可测)
        result = loop.refine(prompt, analyses, style)  # 全流程(含首轮生成)
    """

    def __init__(
        self,
        generator: Any = None,
        scorer: Optional[DirectorQualityScorer] = None,
        target_score: float = 85.0,
        max_iterations: int = 3,
    ):
        self._generator = generator
        self._scorer = scorer or DirectorQualityScorer()
        self._target = float(target_score)
        self._max_iter = int(max_iterations)

    # ────────────────────────────────────────────────────────────
    #  快路径: 对已有剧本做确定性修补 (不调LLM)
    # ────────────────────────────────────────────────────────────

    def refine_script(
        self,
        script: Dict[str, Any],
        combo_stats: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """轨迹驱动的迭代修补

        Returns:
            {"script": 修补后剧本, "initial_score": float, "final_score": float,
             "iterations": int, "trajectory": [{step, score, weakest, actions}],
             "improved": bool, "heartbeats": [float]}
        """
        trajectory: List[Dict[str, Any]] = []
        heartbeats: List[float] = []

        card = self._scorer.score_card(
            script, combo_stats=combo_stats,
            evidence=self._build_evidence(script))
        initial = card["total_score"]

        prev = initial
        stalled = 0
        for step in range(1, self._max_iter + 1):
            heartbeats.append(time.time())
            if prev >= self._target:
                break
            weakest = self._weakest_dimension(card)
            actions = self._apply_refinements(script, weakest, card)
            if not actions:
                break  # 无可修补项, 提前收敛
            card = self._scorer.score_card(
                script, combo_stats=combo_stats,
                evidence=self._build_evidence(script))
            trajectory.append({
                "step": step, "score": card["total_score"],
                "weakest": weakest, "actions": actions,
            })
            if card["total_score"] <= prev + 0.01:
                stalled += 1
                if stalled >= 2:
                    break  # 连续两轮无增益, 止损
            else:
                stalled = 0
            prev = card["total_score"]

        return {
            "script": script,
            "initial_score": initial,
            "final_score": card["total_score"],
            "iterations": len(trajectory),
            "trajectory": trajectory,
            "improved": card["total_score"] > initial,
            "reached_target": card["total_score"] >= self._target,
            "heartbeats": heartbeats,
        }

    # ────────────────────────────────────────────────────────────
    #  全流程: 首轮生成 + 自改进
    # ────────────────────────────────────────────────────────────

    def refine(
        self,
        user_prompt: str,
        material_analyses: List[Dict],
        style: str = "cinematic",
        generator: Any = None,
    ) -> Dict[str, Any]:
        """生成剧本并自改进 (generator未注入时用规则fallback)"""
        gen = generator or self._generator
        if gen is not None:
            script = gen.generate_script(user_prompt, material_analyses, style)
        else:
            from ai.ai_director import ScriptGenerator
            script = ScriptGenerator().generate_script(
                user_prompt, material_analyses, style)
        result = self.refine_script(script)
        result["generator_used"] = "injected" if gen else "default"
        return result

    # ────────────────────────────────────────────────────────────
    #  评分与维度分析
    # ────────────────────────────────────────────────────────────

    def _build_evidence(self, script: Dict[str, Any]) -> Dict[str, Any]:
        """从剧本提取反模式证据 (与 scorer.score_anti_patterns 契约一致)"""
        segs = script.get("segments", [])
        movements = [
            (s.get("camera") or {}).get("camera_id")
            or (s.get("camera") or {}).get("movement", "")
            for s in segs
        ]
        movements = [m for m in movements if m]
        durs = [round(s.get("duration", 0), 2) for s in segs if s.get("duration")]
        cuts: List[float] = []
        for s in segs:
            cuts.extend(s.get("cut_times", []))
        beat_card = self._scorer.score_beat_alignment(
            cuts, script.get("bpm", 128))
        return {
            "has_ease": any(s.get("easing") for s in segs),
            "max_scale": max((s.get("max_scale", 100) for s in segs), default=100),
            "beat_ok": beat_card["score"] >= 99.0,
            "uniform_segments": bool(durs) and len(set(durs)) <= 1,
            "camera_unique": len(set(movements)),
        }

    def _weakest_dimension(self, card: Dict[str, Any]) -> str:
        metrics = card.get("metrics", {})
        dims = {
            "beat_alignment": metrics.get("beat_alignment", {}).get("score", 100),
            "camera_diversity": metrics.get("camera_diversity", {}).get("score", 100),
            "arc_completeness": metrics.get("arc_completeness", {}).get("score", 100),
            "combo_coverage": metrics.get("combo_coverage", {}).get("score", 100),
            "anti_patterns": metrics.get("anti_patterns", {}).get("score", 100),
        }
        return min(dims, key=lambda k: dims[k])

    # ────────────────────────────────────────────────────────────
    #  确定性修补动作 (小幅更新, 不重写生成逻辑)
    # ────────────────────────────────────────────────────────────

    def _apply_refinements(
        self, script: Dict[str, Any], weakest: str, card: Dict[str, Any]
    ) -> List[str]:
        """按最弱维度顺序执行修补; 每轮全维度扫一遍保证收敛"""
        actions: List[str] = []
        actions += self._refine_beat(script, card)
        actions += self._refine_camera(script, card)
        actions += self._refine_arc(script, card)
        actions += self._refine_anti(script, card)
        return actions

    def _refine_beat(self, script: Dict[str, Any], card: Dict) -> List[str]:
        """切点吸附BPM半拍网格 (防累积漂移: 逐点独立吸附)"""
        metrics = card.get("metrics", {})
        if metrics.get("beat_alignment", {}).get("score", 100) >= 99.0:
            return []
        bpm = script.get("bpm", 128)
        if bpm <= 0:
            return []
        beat_dur = 60.0 / bpm
        snapped = 0
        for seg in script.get("segments", []):
            new_cuts = []
            for c in seg.get("cut_times", []):
                half_units = c / beat_dur * 2
                new_c = round(half_units) / 2 * beat_dur
                if abs(new_c - c) > 1e-6:
                    snapped += 1
                new_cuts.append(round(new_c, 4))
            seg["cut_times"] = new_cuts
        return [f"beat_snap:{snapped}个切点吸附BPM网格"] if snapped else []

    def _refine_camera(self, script: Dict[str, Any], card) -> List[str]:
        """运镜去重+多样化注入 (CAMERA_IDS_ALL 12运镜池)"""
        segs = script.get("segments", [])
        movements = [
            (s.get("camera") or {}).get("camera_id")
            or (s.get("camera") or {}).get("movement", "")
            for s in segs
        ]
        actions = []
        # 连续三段同运镜 → 用未用过的运镜替换中段
        used = set(m for m in movements if m)
        for i in range(len(segs) - 2):
            a, b, c = movements[i], movements[i + 1], movements[i + 2]
            if a and a == b == c:
                pool = [m for m in CAMERA_IDS_ALL if m not in used] or \
                       [m for m in CAMERA_IDS_ALL if m != a]
                repl = pool[0]
                cam = segs[i + 1].setdefault("camera", {})
                cam["camera_id"] = repl
                cam["movement"] = repl
                movements[i + 1] = repl
                used.add(repl)
                actions.append(f"camera_dedupe:段{i+2}运镜替换为{repl}")
        # 种类不足6 → 从池里补足差异化运镜
        uniq = len(set(m for m in movements if m))
        if uniq < 6 and segs:
            pool = [m for m in CAMERA_IDS_ALL
                    if m not in set(movements)]
            for seg in segs:
                if uniq >= 6 or not pool:
                    break
                cam = seg.get("camera") or {}
                cur = cam.get("camera_id") or cam.get("movement", "")
                # 只替换重复出现的运镜, 保留首次出现
                if movements.count(cur) > 1:
                    repl = pool.pop(0)
                    cam["camera_id"] = repl
                    cam["movement"] = repl
                    seg["camera"] = cam
                    movements[segs.index(seg)] = repl
                    uniq += 1
                    actions.append(f"camera_inject:注入{repl}提升多样性")
        return actions

    def _refine_arc(self, script: Dict[str, Any], card) -> List[str]:
        """弧线补全: energy_target / breath_break / 非均分时长"""
        actions = []
        segs = script.get("segments", [])
        types = [s.get("type") for s in segs]
        # 1. energy_target 补全
        for seg in segs:
            t = seg.get("type")
            if t in _ENERGY_BY_TYPE and "energy_target" not in seg:
                seg["energy_target"] = _ENERGY_BY_TYPE[t]
                actions.append(f"arc_energy:段{seg.get('name','?')}补energy={_ENERGY_BY_TYPE[t]}")
        # 2. breath_break 喘息点 (drop之后插入)
        if "breath_break" not in types and "drop" in types:
            di = types.index("drop")
            total = script.get("total_duration", 30) or 30
            breath = {
                "name": "breath_break", "type": "breath_break",
                "duration": round(total * 0.08, 2),
                "energy_target": _ENERGY_BY_TYPE["breath_break"],
                "camera": {"camera_id": "pull", "movement": "pull",
                           "speed": "slow"},
                "mood": "喘息留白",
            }
            segs.insert(di + 1, breath)
            actions.append("arc_breath:drop后插入breath_break喘息点")
        # 3. 均分时长 → 能量包络重分配
        durs = [round(s.get("duration", 0), 2) for s in segs
                if s.get("type") in _REQUIRED_TYPES]
        if durs and len(set(durs)) <= 1 and segs:
            total = script.get("total_duration") or sum(durs) or 30
            idx = 0
            for seg in segs:
                if seg.get("type") in _REQUIRED_TYPES and idx < 5:
                    seg["duration"] = round(total * _DURATION_ENVELOPE[idx], 2)
                    idx += 1
            actions.append("arc_envelope:时长改为12/24/34/12/18能量包络")
        return actions

    def _refine_anti(self, script: Dict[str, Any], card) -> List[str]:
        """反模式修补: 缓动缺失 / 过大缩放"""
        actions = []
        segs = script.get("segments", [])
        if not any(s.get("easing") for s in segs):
            for seg in segs:
                seg["easing"] = "easeInOut"
            actions.append("anti_ease:全段补easeInOut缓动")
        for seg in segs:
            if seg.get("max_scale", 100) > 150:
                seg["max_scale"] = 150
                actions.append(f"anti_scale:段{seg.get('name','?')}缩放钳制至150")
        return actions


def get_refine_loop(**kwargs) -> DirectorRefineLoop:
    """工厂方法 (与项目get_xxx单例风格一致, 但每次新建避免状态污染)"""
    return DirectorRefineLoop(**kwargs)
