# -*- coding: utf-8 -*-
"""DirectorQualityScorer — 导演输出质量五项基准评分卡 (T4)

五项基准 (行业标杆量化):
1. beat_alignment  节拍误差 < 1帧 (切点到最近拍/半拍网格)
2. camera_diversity 运镜多样性 ≥6种 + 无连续3段同运镜
3. arc_completeness 弧线完整度 (五段+能量包络+breath break)
4. combo_coverage   三维组合多样性 ≥70% (特效×动画×字体)
5. anti_patterns    反模式扣分 (master_rules.json anti_patterns)

输出: scorecard dict + 人类可读报告, 供 CI/验收消费。
"""
import json
import os
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MASTER_RULES_PATH = os.path.join(ROOT, "config", "master_rules.json")

BASELINE = {
    "beat_error_frames": 1.0,      # 节拍误差阈值(帧)
    "camera_min_unique": 6,        # 运镜种类下限
    "combo_diversity_min": 0.70,   # 三维组合多样性下限
    "arc_min_ratio": 0.8,          # 弧线完整度下限
}


class DirectorQualityScorer:
    """对导演产出的 script/stats 做五项量化评分 (0-100)"""

    def __init__(self, rules: Optional[Dict[str, Any]] = None):
        if rules is None:
            with open(MASTER_RULES_PATH, encoding="utf-8") as f:
                rules = json.load(f)
        self.rules = rules

    # ── 单项1: 节拍对齐 ─────────────────────────────────────
    def score_beat_alignment(self, cut_times: List[float], bpm: float,
                             fps: int = 30) -> Dict[str, Any]:
        """切点到最近拍/半拍网格的最大误差(帧), <1帧为满分"""
        if bpm <= 0 or not cut_times:
            return {"score": 0.0, "max_error_frames": None,
                    "detail": "no cuts or bpm"}
        beat_dur = 60.0 / bpm
        errors = []
        for c in cut_times:
            half_units = c / beat_dur * 2
            err_s = abs(half_units - round(half_units)) / 2 * beat_dur
            errors.append(err_s * fps)
        max_err = max(errors)
        avg_err = sum(errors) / len(errors)
        # 满分条件: 最大误差<1帧; 线性衰减到3帧归零
        if max_err <= BASELINE["beat_error_frames"]:
            score = 100.0
        else:
            score = max(0.0, 100.0 - (max_err - 1.0) * 50.0)
        return {"score": round(score, 1),
                "max_error_frames": round(max_err, 3),
                "avg_error_frames": round(avg_err, 3),
                "cut_count": len(cut_times)}

    # ── 单项2: 运镜多样性 ───────────────────────────────────
    def score_camera_diversity(self, movements: List[str]) -> Dict[str, Any]:
        """运镜种类≥6满分; 连续3段同运镜扣分"""
        if not movements:
            return {"score": 0.0, "unique": 0, "detail": "no movements"}
        unique = len(set(movements))
        score = min(100.0, unique / BASELINE["camera_min_unique"] * 100.0)
        # 连续3段同运镜检测
        triple = any(movements[i] == movements[i+1] == movements[i+2]
                     for i in range(len(movements) - 2))
        if triple:
            score = max(0.0, score - 30.0)
        return {"score": round(score, 1), "unique": unique,
                "has_triple_repeat": triple,
                "movements_used": sorted(set(movements))}

    # ── 单项3: 弧线完整度 ───────────────────────────────────
    def score_arc_completeness(self, segments: List[Dict]) -> Dict[str, Any]:
        """五段齐全+能量字段+breath break+时长比符合包络"""
        if not segments:
            return {"score": 0.0, "detail": "no segments"}
        types = [s.get("type") for s in segments]
        required = ["intro", "build", "drop", "break", "outro"]
        found = [t for t in required if t in types]
        ratio = len(found) / len(required)
        score = ratio * 60.0  # 五段齐全=60分
        # 能量字段 (+15)
        has_energy = all("energy_target" in s for s in segments
                         if s.get("type") in required)
        if has_energy and found:
            score += 15.0
        # breath break 喘息点 (+10)
        if "breath_break" in types:
            score += 10.0
        # 非均分: 时长比不全相等 (+15)
        durs = [s.get("duration", 0) for s in segments
                if s.get("type") in required]
        if durs and len(set(round(d, 2) for d in durs)) > 1:
            score += 15.0
        return {"score": round(min(100.0, score), 1),
                "segments_found": found, "has_energy": has_energy,
                "has_breath_break": "breath_break" in types,
                "non_uniform": bool(durs) and
                len(set(round(d, 2) for d in durs)) > 1}

    # ── 单项4: 三维组合覆盖率 ───────────────────────────────
    def score_combo_coverage(self, combo_stats: Dict[str, Any]) -> Dict[str, Any]:
        """特效×动画×字体组合多样性 ≥70% 满分"""
        total = combo_stats.get("total_combo_uses", 0)
        unique = combo_stats.get("unique_combos", 0)
        if total <= 0:
            return {"score": 0.0, "diversity": 0.0, "detail": "no combos"}
        diversity = unique / total
        if diversity >= BASELINE["combo_diversity_min"]:
            score = 100.0
        else:
            score = diversity / BASELINE["combo_diversity_min"] * 100.0
        return {"score": round(score, 1), "diversity": round(diversity, 3),
                "unique": unique, "total": total}

    # ── 单项5: 反模式检测 ───────────────────────────────────
    def score_anti_patterns(self, evidence: Dict[str, Any]) -> Dict[str, Any]:
        """依据 master_rules.anti_patterns 扣分 (100分起扣)

        evidence 字段: has_ease(bool) / max_scale(float) /
        beat_ok(bool) / uniform_segments(bool) / camera_unique(int)
        """
        ap = {k: v for k, v in self.rules.get("anti_patterns", {}).items()
              if not k.startswith("_")}
        penalty = 0
        hits = []
        if not evidence.get("has_ease", False):
            penalty += ap["linear_easing_everywhere"]["penalty"]
            hits.append("linear_easing_everywhere")
        if evidence.get("max_scale", 100) > 150:
            penalty += ap["oversized_zoom"]["penalty"]
            hits.append("oversized_zoom")
        if not evidence.get("beat_ok", False):
            penalty += ap["no_beat_alignment"]["penalty"]
            hits.append("no_beat_alignment")
        if evidence.get("uniform_segments", False):
            penalty += ap["uniform_segments"]["penalty"]
            hits.append("uniform_segments")
        if evidence.get("camera_unique", 0) < 3:
            penalty += ap["camera_monotony"]["penalty"]
            hits.append("camera_monotony")
        return {"score": max(0.0, 100.0 - penalty), "penalty": penalty,
                "hits": hits}

    # ── 总评 ────────────────────────────────────────────────
    def score_card(self, script: Dict[str, Any],
                   combo_stats: Optional[Dict[str, Any]] = None,
                   evidence: Optional[Dict[str, Any]] = None,
                   fps: int = 30) -> Dict[str, Any]:
        """一次调用产出五项+总分 (权重 25/20/20/15/20)"""
        bpm = script.get("bpm", 128)
        cuts = []
        movements = []
        segments = script.get("segments", [])
        for s in segments:
            cuts.extend(s.get("cut_times", []))
            cam = s.get("camera", {})
            mv = cam.get("camera_id") or cam.get("movement", "")
            if mv:
                movements.append(mv)
        m1 = self.score_beat_alignment(cuts, bpm, fps)
        m2 = self.score_camera_diversity(movements)
        m3 = self.score_arc_completeness(segments)
        m4 = self.score_combo_coverage(combo_stats or {})
        m5 = self.score_anti_patterns(evidence or {})
        weights = {"beat_alignment": 0.25, "camera_diversity": 0.20,
                   "arc_completeness": 0.20, "combo_coverage": 0.15,
                   "anti_patterns": 0.20}
        metrics = {"beat_alignment": m1, "camera_diversity": m2,
                   "arc_completeness": m3, "combo_coverage": m4,
                   "anti_patterns": m5}
        total = sum(metrics[k]["score"] * w for k, w in weights.items())
        passed = all([
            m1["score"] >= 80, m2["score"] >= 60, m3["score"] >= 80,
            m4["score"] >= 60, m5["score"] >= 60])
        return {"total_score": round(total, 1), "passed": passed,
                "metrics": metrics, "weights": weights,
                "baseline": BASELINE}

    @staticmethod
    def format_report(card: Dict[str, Any]) -> str:
        lines = [f"DirectorQualityScorer 总分: {card['total_score']}/100 "
                 f"({'达标' if card['passed'] else '未达标'})"]
        for k, m in card["metrics"].items():
            lines.append(f"  {k:<18} {m['score']:>5.1f}")
        return "\n".join(lines)
