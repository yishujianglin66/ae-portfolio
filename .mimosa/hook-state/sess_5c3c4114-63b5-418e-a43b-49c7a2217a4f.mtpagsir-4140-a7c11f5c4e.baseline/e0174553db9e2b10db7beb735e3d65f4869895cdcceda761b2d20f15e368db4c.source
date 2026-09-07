# -*- coding: utf-8 -*-
r"""T30b: 场景感知评分器 — 在production_scorer基础上增加场景适配维度。

核心思想: 不同场景类型对剪辑方案有不同偏好
  - battle: 快切+高能量踩拍 → 偏好短镜头(0.3-2s), 高onset命中
  - dialog: 中等节奏+稳定 → 偏好中等镜头(1-4s), 适度踩拍
  - emotional: 慢节奏+情感渲染 → 偏好长镜头(2-8s), 低切点密度
  - daily: 轻松温暖 → 中等镜头, 低能量要求
  - landscape: 视觉留白 → 偏好长镜头(3-10s), 几乎不切

用法:
  from ai.t30b_scene_aware_scorer import SceneAwareScorer
  scorer = SceneAwareScorer()
  result = scorer.score(cuts, beats, duration, scene_type="battle", mood="hot")
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROTO_V2 = ROOT / "data" / "ip_prototypes_v2.json"

# 场景→理想镜头时长范围(秒)
SCENE_SHOT_PREFS = {
    "battle":    {"min": 0.3, "max": 2.0, "ideal": 0.8, "cut_density": 0.8},
    "dialog":    {"min": 1.0, "max": 4.0, "ideal": 2.5, "cut_density": 0.4},
    "emotional": {"min": 2.0, "max": 8.0, "ideal": 4.0, "cut_density": 0.2},
    "daily":     {"min": 1.5, "max": 5.0, "ideal": 3.0, "cut_density": 0.3},
    "landscape": {"min": 3.0, "max": 10.0, "ideal": 6.0, "cut_density": 0.1},
    "ceremony":  {"min": 1.5, "max": 6.0, "ideal": 3.5, "cut_density": 0.25},
    "comedy":    {"min": 0.5, "max": 3.0, "ideal": 1.5, "cut_density": 0.6},
}

# 场景→情绪→节奏权重调整
SCENE_MOOD_WEIGHTS = {
    "battle": {
        "hot":   {"rhythm": 0.35, "shot": 0.15, "energy": 0.25, "scene_fit": 0.25},
        "tense": {"rhythm": 0.30, "shot": 0.20, "energy": 0.20, "scene_fit": 0.30},
    },
    "dialog": {
        "tense": {"rhythm": 0.20, "shot": 0.30, "energy": 0.10, "scene_fit": 0.40},
        "warm":  {"rhythm": 0.15, "shot": 0.35, "energy": 0.10, "scene_fit": 0.40},
    },
    "emotional": {
        "hot":   {"rhythm": 0.20, "shot": 0.25, "energy": 0.15, "scene_fit": 0.40},
        "sad":   {"rhythm": 0.10, "shot": 0.35, "energy": 0.05, "scene_fit": 0.50},
        "warm":  {"rhythm": 0.15, "shot": 0.30, "energy": 0.10, "scene_fit": 0.45},
        "tense": {"rhythm": 0.20, "shot": 0.25, "energy": 0.15, "scene_fit": 0.40},
    },
    "daily": {
        "warm":  {"rhythm": 0.15, "shot": 0.35, "energy": 0.10, "scene_fit": 0.40},
        "hot":   {"rhythm": 0.25, "shot": 0.25, "energy": 0.20, "scene_fit": 0.30},
    },
    "landscape": {
        "warm":  {"rhythm": 0.10, "shot": 0.40, "energy": 0.05, "scene_fit": 0.45},
        "tense": {"rhythm": 0.15, "shot": 0.35, "energy": 0.10, "scene_fit": 0.40},
    },
}
# 默认权重(场景/情绪未知时)
DEFAULT_WEIGHTS = {"rhythm": 0.25, "shot": 0.25, "energy": 0.15, "scene_fit": 0.35}


def _log(msg):
    print(f"[T30b] {msg}", flush=True)


class SceneAwareScorer:
    """场景感知评分器: 在production_scorer基础上增加场景适配维度"""
    
    def __init__(self):
        self._proto_v2 = None
        self._scene_mood_matrix = {}
        self._load_proto_v2()
    
    def _load_proto_v2(self):
        """加载v2原型库获取共现矩阵"""
        if PROTO_V2.exists():
            data = json.loads(PROTO_V2.read_text(encoding="utf-8"))
            # 构建 scene → mood → 频率 映射
            for sm in data.get("scene_mood_matrix", []):
                scene = sm["scene"]
                if scene not in self._scene_mood_matrix:
                    self._scene_mood_matrix[scene] = {}
                self._scene_mood_matrix[scene][sm["mood"]] = sm["count"]
            _log(f"共现矩阵加载: {len(self._scene_mood_matrix)}个场景")
    
    def _get_weights(self, scene: str, mood: str) -> dict:
        """根据场景+情绪获取权重"""
        scene_w = SCENE_MOOD_WEIGHTS.get(scene, {})
        return scene_w.get(mood, DEFAULT_WEIGHTS.copy())
    
    def dim_scene_fit(self, cuts: List[float], duration: float,
                      scene_type: str, mood: str = "") -> float:
        """场景适配度: 切点模式是否符合该场景类型的理想特征。
        
        评估维度:
          1. 镜头时长是否在场景理想范围内
          2. 切点密度是否匹配场景偏好
          3. 镜头时长方差是否合理(同场景内应相对一致)
        """
        if not cuts or duration <= 0:
            return 0.5  # 无切点时给中间分
        
        prefs = SCENE_SHOT_PREFS.get(scene_type, SCENE_SHOT_PREFS["daily"])
        
        bounds = np.array([0.0] + sorted(c for c in cuts if 0 < c < duration) + [duration])
        shots = np.diff(bounds)
        if len(shots) == 0:
            return 0.5
        
        # 1. 镜头时长匹配度
        ideal = prefs["ideal"]
        min_s, max_s = prefs["min"], prefs["max"]
        shot_scores = []
        for s in shots:
            if min_s <= s <= max_s:
                # 在理想范围内, 按距离ideal的程度打分
                dist = abs(s - ideal) / max(ideal, 0.1)
                shot_scores.append(max(0.5, 1.0 - dist * 0.3))
            elif s < min_s:
                # 太短
                ratio = s / min_s
                shot_scores.append(max(0.1, ratio * 0.5))
            else:
                # 太长
                ratio = max_s / s
                shot_scores.append(max(0.1, ratio * 0.5))
        
        duration_score = np.mean(shot_scores)
        
        # 2. 切点密度匹配度
        actual_density = len(cuts) / duration  # 切点/秒
        target_density = prefs["cut_density"]
        density_ratio = min(actual_density, target_density) / max(actual_density, target_density, 0.01)
        density_score = max(0.2, density_ratio)
        
        # 3. 镜头一致性(CV不能太高也不能太低)
        cv = float(shots.std() / max(shots.mean(), 1e-6))
        if cv < 0.3:
            consistency = 0.7  # 过于机械均匀
        elif cv < 1.5:
            consistency = 1.0  # 自然变化
        else:
            consistency = max(0.3, 1.0 - (cv - 1.5) * 0.2)  # 过于不均匀
        
        return float(0.4 * duration_score + 0.3 * density_score + 0.3 * consistency)
    
    def score(self, cuts: List[float], beats: List[float], duration: float,
              scene_type: str = "", mood: str = "",
              wav_path: str = "") -> Dict[str, float]:
        """综合评分: 场景感知的多维度评分。
        
        Returns:
            dict with keys: rhythm, shot, energy, scene_fit, total, weights
        """
        from ai.production_scorer import dim_rhythm, dim_shot, energy_peak_rate
        
        weights = self._get_weights(scene_type, mood)
        
        # 维度1: 节奏
        rhythm = dim_rhythm(cuts, beats, duration) if beats else 0.5
        
        # 维度2: 镜头健康度
        shot = dim_shot(cuts, duration, beats, rhythm)
        
        # 维度3: 能量匹配
        energy = 0.5
        if wav_path and Path(wav_path).exists():
            try:
                energy = energy_peak_rate(cuts, wav_path)
            except Exception:
                pass
        
        # 维度4: 场景适配度
        scene_fit = 0.5
        if scene_type:
            scene_fit = self.dim_scene_fit(cuts, duration, scene_type, mood)
        
        # 加权总分
        total = (weights["rhythm"] * rhythm +
                 weights["shot"] * shot +
                 weights["energy"] * energy +
                 weights["scene_fit"] * scene_fit)
        
        return {
            "rhythm": round(rhythm, 4),
            "shot": round(shot, 4),
            "energy": round(energy, 4),
            "scene_fit": round(scene_fit, 4),
            "total": round(total, 4),
            "weights": weights,
            "scene": scene_type,
            "mood": mood,
        }
    
    def rank_plans(self, plans: Dict[str, dict], scene_type: str = "",
                   mood: str = "", wav_path: str = "") -> List[dict]:
        """对多个剪辑方案排序(场景感知版)。
        
        plans: {name: {"cuts": [...], "beats": [...], "duration": float}}
        Returns: sorted list of {name, scores}
        """
        results = []
        for name, plan in plans.items():
            scores = self.score(
                plan["cuts"], plan.get("beats", []),
                plan.get("duration", 0),
                scene_type=scene_type, mood=mood,
                wav_path=wav_path,
            )
            results.append({"name": name, "scores": scores})
        
        results.sort(key=lambda x: x["scores"]["total"], reverse=True)
        return results


def demo():
    """演示: 同一组切点在不同场景下的评分差异"""
    _log("=" * 60)
    _log("T30b: 场景感知评分器演示")
    _log("=" * 60)
    
    scorer = SceneAwareScorer()
    
    # 模拟3组切点方案 (120秒视频)
    duration = 120.0
    beats = [i * 0.5 for i in range(int(duration / 0.5))]  # 120BPM
    
    plans = {
        "快切AMV": {"cuts": list(np.arange(1, duration, 1.2)), "beats": beats, "duration": duration},
        "中等节奏": {"cuts": list(np.arange(2, duration, 3.0)), "beats": beats, "duration": duration},
        "慢节奏": {"cuts": list(np.arange(5, duration, 6.0)), "beats": beats, "duration": duration},
    }
    
    scenes = ["battle", "dialog", "emotional", "daily", "landscape"]
    
    for scene in scenes:
        _log(f"\n--- 场景: {scene} ---")
        ranked = scorer.rank_plans(plans, scene_type=scene, mood="hot")
        for r in ranked:
            s = r["scores"]
            _log(f"  {r['name']:8s} total={s['total']:.3f} "
                 f"(节奏={s['rhythm']:.2f} 镜头={s['shot']:.2f} "
                 f"能量={s['energy']:.2f} 场景适配={s['scene_fit']:.2f})")


if __name__ == "__main__":
    demo()
