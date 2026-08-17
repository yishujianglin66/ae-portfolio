# -*- coding: utf-8 -*-
r"""T30c: 素材→场景→情绪匹配矩阵 — 基于65,714帧VLM标注的共现统计。

为导演系统提供数据驱动的素材匹配决策:
  - 给定场景类型 → 推荐最佳情绪组合
  - 给定情绪 → 推荐最佳场景类型
  - 给定IP → 获取该IP的场景/情绪分布特征
  - 场景×情绪兼容性评分

数据来源: Qwen3-VL-8B 对进击的巨人65,714帧的全量标注
共现矩阵: 20组 scene×mood 组合

用法:
    from ai.t30c_scene_mood_matrix import SceneMoodMatrix
    matrix = SceneMoodMatrix()
    moods = matrix.recommend_moods("battle", top_k=3)
    scenes = matrix.recommend_scenes("hot", top_k=3)
    profile = matrix.get_ip_profile("进击的巨人")
    compat = matrix.compatibility("battle", "hot")
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PROTO_V2 = ROOT / "data" / "ip_prototypes_v2.json"


def _log(msg: str):
    print(f"[T30c] {msg}", flush=True)


class SceneMoodMatrix:
    """素材→场景→情绪匹配矩阵。

    基于VLM全量标注的共现统计，为导演系统提供数据驱动的素材匹配决策。
    """

    def __init__(self, proto_v2_path: Optional[str] = None):
        path = Path(proto_v2_path) if proto_v2_path else PROTO_V2
        self._raw: dict = {}
        self._scene_mood: Dict[str, Dict[str, int]] = {}   # scene → {mood → count}
        self._mood_scene: Dict[str, Dict[str, int]] = {}   # mood → {scene → count}
        self._scene_totals: Dict[str, int] = {}
        self._mood_totals: Dict[str, int] = {}
        self._ip_profiles: Dict[str, dict] = {}
        self._total_frames = 0
        self._load(path)

    # ── 数据加载 ──────────────────────────────────────────

    def _load(self, path: Path):
        if not path.exists():
            _log(f"WARNING: {path} not found, using empty matrix")
            return
        data = json.loads(path.read_text(encoding="utf-8"))

        # 1. 共现矩阵
        for item in data.get("scene_mood_matrix", []):
            scene, mood, count = item["scene"], item["mood"], item["count"]
            self._scene_mood.setdefault(scene, {})[mood] = count
            self._mood_scene.setdefault(mood, {})[scene] = count
            self._scene_totals[scene] = self._scene_totals.get(scene, 0) + count
            self._mood_totals[mood] = self._mood_totals.get(mood, 0) + count
            self._total_frames += count

        # 2. IP维度统计
        prototypes = data.get("ip_prototypes", data.get("prototypes", {}))
        if isinstance(prototypes, dict):
            for ip_key, ip_data in prototypes.items():
                profile = {
                    "name": ip_data.get("name_cn", ip_key),
                    "name_en": ip_data.get("name_en", ""),
                    "tier": ip_data.get("tier", ""),
                    "vlm_frame_count": ip_data.get("vlm_frame_count", 0),
                    "scene_dist": ip_data.get("vlm_scene_dist", {}),
                    "mood_dist": ip_data.get("vlm_mood_dist", {}),
                    "top_characters": ip_data.get("vlm_top_characters", []),
                }
                if profile["vlm_frame_count"] > 0:
                    self._ip_profiles[ip_key] = profile

        _log(f"匹配矩阵加载: {len(self._scene_mood)}场景×{len(self._mood_scene)}情绪, "
             f"{self._total_frames}帧, {len(self._ip_profiles)}个IP有VLM数据")

    # ── 核心查询 ──────────────────────────────────────────

    def recommend_moods(self, scene_type: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """给定场景类型 → 推荐最佳情绪组合(按条件概率降序)。

        Returns:
            [(mood, probability), ...]  top_k个最佳情绪
        """
        mood_counts = self._scene_mood.get(scene_type, {})
        total = self._scene_totals.get(scene_type, 0)
        if total == 0:
            return []
        ranked = sorted(mood_counts.items(), key=lambda x: -x[1])
        return [(m, c / total) for m, c in ranked[:top_k]]

    def recommend_scenes(self, mood: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """给定情绪 → 推荐最佳场景类型(按条件概率降序)。

        Returns:
            [(scene, probability), ...]  top_k个最佳场景
        """
        scene_counts = self._mood_scene.get(mood, {})
        total = self._mood_totals.get(mood, 0)
        if total == 0:
            return []
        ranked = sorted(scene_counts.items(), key=lambda x: -x[1])
        return [(s, c / total) for s, c in ranked[:top_k]]

    def compatibility(self, scene: str, mood: str) -> float:
        """场景×情绪兼容性评分 (0~1)。

        基于PMI(Pointwise Mutual Information)思想:
          compat = P(scene,mood) / (P(scene) * P(mood))
        归一化到 [0, 1] 范围。
        >0.5 表示正相关(比随机期望更常共现)
        <0.5 表示负相关(比随机期望更少共现)
        """
        if self._total_frames == 0:
            return 0.5
        joint = self._scene_mood.get(scene, {}).get(mood, 0)
        p_joint = joint / self._total_frames
        p_scene = self._scene_totals.get(scene, 0) / self._total_frames
        p_mood = self._mood_totals.get(mood, 0) / self._total_frames
        if p_scene == 0 or p_mood == 0:
            return 0.0
        pmi_raw = p_joint / (p_scene * p_mood)
        # 归一化: PMI范围 [0, 1/min(p_scene,p_mood)], 映射到 [0, 1]
        max_pmi = 1.0 / min(p_scene, p_mood) if min(p_scene, p_mood) > 0 else 1
        return min(1.0, pmi_raw / max_pmi) if max_pmi > 0 else 0.0

    def get_ip_profile(self, ip_name: str) -> Optional[dict]:
        """获取指定IP的场景/情绪分布特征。

        Args:
            ip_name: IP的key名(如 'attack_on_titan')或中文名

        Returns:
            dict with keys: name, scene_dist, mood_dist, top_characters, vlm_frame_count
            None if not found
        """
        # 精确匹配
        if ip_name in self._ip_profiles:
            return self._ip_profiles[ip_name]
        # 中文名模糊匹配
        for key, prof in self._ip_profiles.items():
            if prof["name"] == ip_name or prof.get("name_en", "").lower() == ip_name.lower():
                return prof
        return None

    def list_ips_with_vlm(self) -> List[str]:
        """列出所有有VLM数据的IP"""
        return list(self._ip_profiles.keys())

    def scene_mood_table(self) -> Dict[str, Dict[str, float]]:
        """返回完整的场景→情绪概率分布表(归一化)。

        Returns:
            {scene: {mood: probability, ...}, ...}
        """
        result = {}
        for scene, mood_counts in self._scene_mood.items():
            total = self._scene_totals.get(scene, 0)
            if total > 0:
                result[scene] = {m: c / total for m, c in mood_counts.items()}
        return result

    def best_scene_mood_pairs(self, top_k: int = 10) -> List[Tuple[str, str, float]]:
        """返回共现频率最高的场景×情绪组合。

        Returns:
            [(scene, mood, probability), ...]
        """
        pairs = []
        for scene, mood_counts in self._scene_mood.items():
            for mood, count in mood_counts.items():
                pairs.append((scene, mood, count / self._total_frames))
        pairs.sort(key=lambda x: -x[2])
        return pairs[:top_k]


def demo():
    """演示: 匹配矩阵查询能力"""
    _log("=" * 60)
    _log("T30c: 素材→场景→情绪匹配矩阵演示")
    _log("=" * 60)

    matrix = SceneMoodMatrix()

    # 1. 场景→情绪推荐
    _log("\n[1] 场景→情绪推荐:")
    for scene in ["battle", "emotional", "dialog", "daily", "landscape"]:
        moods = matrix.recommend_moods(scene, top_k=3)
        mood_str = ", ".join(f"{m}({p:.1%})" for m, p in moods)
        _log(f"  {scene:10s} → {mood_str}")

    # 2. 情绪→场景推荐
    _log("\n[2] 情绪→场景推荐:")
    for mood in ["hot", "tense", "warm", "sad"]:
        scenes = matrix.recommend_scenes(mood, top_k=3)
        scene_str = ", ".join(f"{s}({p:.1%})" for s, p in scenes)
        _log(f"  {mood:10s} → {scene_str}")

    # 3. 兼容性评分 Top10
    _log("\n[3] 共现频率Top10:")
    for scene, mood, prob in matrix.best_scene_mood_pairs(10):
        compat = matrix.compatibility(scene, mood)
        _log(f"  {scene}+{mood}: 占比{prob:.1%}, 兼容性{compat:.3f}")

    # 4. IP维度统计(前5个)
    _log("\n[4] IP维度统计(前5):")
    ips = matrix.list_ips_with_vlm()[:5]
    for ip_key in ips:
        prof = matrix.get_ip_profile(ip_key)
        if prof:
            scene_d = prof.get("scene_dist", {})
            top_scene = max(scene_d, key=scene_d.get) if scene_d else "N/A"
            _log(f"  {prof['name']:15s} ({prof['vlm_frame_count']:5d}帧) "
                 f"主场景={top_scene}")


if __name__ == "__main__":
    demo()
