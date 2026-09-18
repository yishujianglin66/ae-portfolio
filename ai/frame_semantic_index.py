# -*- coding: utf-8 -*-
"""
帧级语义索引 — 素材镜头的向量化与语义检索
================================================
架构(零外部依赖、零未开通API依赖):
1. 镜头切分: OpenCV 场景变化检测 → 每素材切出若干镜头段
2. 语义标注: 复用 material_intel 缓存的 ip_timeline (Seed-1.6-Vision
   原生视频理解输出的逐段描述) — 每镜头获得中文语义描述
3. 视觉向量: 每镜头代表帧提取 颜色直方图(HSV 64维) + 边缘方向直方图(32维)
   + 亮度/饱和度/运动统计(8维) → L2归一化 → 104维视觉向量
4. 检索:
   a) 关键词/语义检索 — 对镜头描述+IP名做归一化子串/关键词匹配打分
   b) 视觉相似检索 — 以帧搜帧 (余弦相似度)
   c) 条件过滤 — IP/情绪/场景类型/运动强度

对外API:
  idx = FrameSemanticIndex()
  idx.build_from_library(video_paths, intel_cache_dir)   # 构建
  idx.save(path) / idx.load(path)
  results = idx.search_text("战斗 火焰 高燃")
  results = idx.search_by_frame(image_bgr)
  results = idx.filter(primary_ip="FATE", min_motion=5)
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ShotUnit:
    """镜头单元 — 检索的最小粒度"""
    video_path: str = ""
    filename: str = ""
    shot_id: int = 0
    start: float = 0.0
    end: float = 0.0
    frame_path: str = ""                 # 代表帧路径
    description: str = ""                # VLM语义描述
    ip_name: str = ""                    # 该镜头归属IP(canonical)
    characters: list[str] = field(default_factory=list)
    scene_type: str = "unknown"
    mood: str = "neutral"
    motion: float = 0.0                  # 镜头内平均运动强度
    brightness: float = 0.0
    saturation: float = 0.0
    vector: np.ndarray = field(default_factory=lambda: np.zeros(0))  # 视觉向量

    def to_dict(self) -> dict:
        return {
            "video_path": self.video_path, "filename": self.filename,
            "shot_id": self.shot_id, "start": round(self.start, 2),
            "end": round(self.end, 2), "frame_path": self.frame_path,
            "description": self.description, "ip_name": self.ip_name,
            "characters": self.characters, "scene_type": self.scene_type,
            "mood": self.mood, "motion": round(self.motion, 2),
            "brightness": round(self.brightness, 1),
            "saturation": round(self.saturation, 1),
            "vector": self.vector.tolist(),
        }

    @staticmethod
    def from_dict(d: dict) -> "ShotUnit":
        s = ShotUnit(**{k: v for k, v in d.items() if k != "vector"})
        s.vector = np.asarray(d.get("vector", []), dtype=np.float32)
        return s


def _extract_visual_vector(frame_bgr: np.ndarray) -> np.ndarray:
    """单帧视觉特征向量: HSV颜色直方图64 + 边缘方向32 + 统计8 = 104维"""
    import cv2
    h, w = frame_bgr.shape[:2]
    if max(h, w) > 384:
        scale = 384.0 / max(h, w)
        frame_bgr = cv2.resize(frame_bgr, (int(w * scale), int(h * scale)))

    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)
    # 颜色直方图: H(16) S(16) V(16) 各自独立归一化 → 48维
    hist_h = cv2.calcHist([hsv], [0], None, [16], [0, 180]).flatten()
    hist_s = cv2.calcHist([hsv], [1], None, [16], [0, 256]).flatten()
    hist_v = cv2.calcHist([hsv], [2], None, [16], [0, 256]).flatten()
    color_vec = np.concatenate([hist_h, hist_s, hist_v])
    color_vec = color_vec / (color_vec.sum() + 1e-8)

    # 边缘方向直方图: Sobel梯度方向 32 bins → 32维
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    mag = np.sqrt(gx ** 2 + gy ** 2)
    ang = np.arctan2(gy, gx)
    mask = mag > mag.mean()
    edge_vec, _ = np.histogram(ang[mask], bins=32, range=(-np.pi, np.pi))
    edge_vec = edge_vec.astype(np.float32)
    edge_vec = edge_vec / (edge_vec.sum() + 1e-8)

    # 统计: 亮度/饱和度均值方差 + 边缘密度等 → 8维
    stats = np.array([
        hsv[:, :, 2].mean() / 255.0, hsv[:, :, 2].std() / 128.0,
        hsv[:, :, 1].mean() / 255.0, hsv[:, :, 1].std() / 128.0,
        float(mask.mean()), mag.mean() / 255.0,
        (hsv[:, :, 0].std() / 90.0),  # 色相离散度
        (gray > 200).mean(),          # 高光占比
    ], dtype=np.float32)

    vec = np.concatenate([color_vec * 2.0, edge_vec * 2.0, stats])
    norm = np.linalg.norm(vec)
    return (vec / (norm + 1e-8)).astype(np.float32)


class FrameSemanticIndex:
    """帧级语义索引"""

    def __init__(self, cache_dir: str | None = None):
        self.cache_dir = Path(cache_dir) if cache_dir else _PROJECT_ROOT / "cache" / "frame_index"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.shots: list[ShotUnit] = []

    # ---------------- 构建 ----------------

    def build_from_library(self, video_paths: list[str],
                           intel_cache_dir: str | None = None,
                           shots_per_video: int = 8) -> int:
        """对素材库构建镜头索引。intel_cache_dir: material_intel缓存目录(提供语义描述)"""
        import cv2
        intel = self._load_intel_tags(intel_cache_dir)
        total = 0
        for i, vp in enumerate(video_paths):
            vp = str(vp)
            if not Path(vp).exists():
                continue
            try:
                n = self._index_one_video(vp, intel.get(Path(vp).name, {}),
                                          shots_per_video)
                total += n
                print(f"  [{i+1}/{len(video_paths)}] {Path(vp).name}: {n}镜头")
            except Exception as e:
                print(f"  [{i+1}/{len(video_paths)}] 失败 {Path(vp).name}: {e}")
        return total

    def _load_intel_tags(self, intel_cache_dir: str | None) -> dict[str, dict]:
        """读取material_intel缓存 → {文件名: cache_dict}"""
        out: dict[str, dict] = {}
        if not intel_cache_dir:
            return out
        cd = Path(intel_cache_dir)
        if not cd.exists():
            return out
        for f in cd.glob("*.json"):
            try:
                d = json.loads(f.read_text(encoding="utf-8"))
                if d.get("filename"):
                    out[d["filename"]] = d
            except Exception:
                continue
        return out

    def _index_one_video(self, video_path: str, intel: dict,
                         shots_per_video: int) -> int:
        import cv2
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"无法打开 {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total_frames <= 0:
            cap.release()
            return 0
        duration = total_frames / fps

        # 场景变化时间戳(来自intel缓存) 或 均匀切分
        scene_changes: list[float] = list(intel.get("scene_changes", []) or [])
        if len(scene_changes) < shots_per_video - 1:
            scene_changes = list(np.linspace(0, duration, shots_per_video + 1)[1:-1])
        boundaries = sorted(set([0.0] + [t for t in scene_changes if 0 < t < duration] + [duration]))

        timeline = intel.get("ip_timeline", []) or []
        fname = Path(video_path).name
        shot_dir = self.cache_dir / "frames"
        shot_dir.mkdir(parents=True, exist_ok=True)

        added = 0
        prev_gray = None
        key = re.sub(r"[^\w]", "_", Path(video_path).stem)[:40]
        for sid, (t0, t1) in enumerate(zip(boundaries[:-1], boundaries[1:])):
            if t1 - t0 < 0.15:
                continue
            # 镜头中点抽帧
            mid = (t0 + t1) / 2
            cap.set(cv2.CAP_PROP_POS_MSEC, mid * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            frame_path = shot_dir / f"{key}_s{sid:03d}.jpg"
            if not frame_path.exists():
                cv2.imwrite(str(frame_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 82])

            # 镜头内运动强度(抽3帧光流近似: 帧差)
            motion = self._estimate_motion(cap, t0, t1, fps)

            # 匹配时间线语义描述
            seg = self._match_timeline(timeline, mid)
            hsv_tmp = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            shot = ShotUnit(
                video_path=video_path, filename=fname, shot_id=sid,
                start=t0, end=t1, frame_path=str(frame_path),
                description=seg.get("description", "") if seg else "",
                ip_name=seg.get("ip_name", "") if seg else (intel.get("primary_ip", "")),
                characters=(seg or {}).get("characters", []),
                scene_type=intel.get("content", {}).get("scene_type", "unknown"),
                mood=intel.get("content", {}).get("mood", "neutral"),
                motion=motion,
                brightness=float(hsv_tmp[:, :, 2].mean()),
                saturation=float(hsv_tmp[:, :, 1].mean()),
                vector=_extract_visual_vector(frame),
            )
            self.shots.append(shot)
            added += 1
        cap.release()
        return added

    def _estimate_motion(self, cap, t0: float, t1: float, fps: float) -> float:
        import cv2
        diffs = []
        prev = None
        for frac in (0.2, 0.5, 0.8):
            cap.set(cv2.CAP_PROP_POS_MSEC, (t0 + (t1 - t0) * frac) * 1000)
            ok, frame = cap.read()
            if not ok or frame is None:
                continue
            gray = cv2.cvtColor(cv2.resize(frame, (160, 90)), cv2.COLOR_BGR2GRAY)
            if prev is not None:
                diffs.append(float(np.abs(gray.astype(np.float32) - prev.astype(np.float32)).mean()))
            prev = gray
        return float(np.mean(diffs)) if diffs else 0.0

    def _match_timeline(self, timeline: list[dict], t: float) -> dict | None:
        for seg in timeline:
            try:
                if float(seg.get("start", 0)) <= t <= float(seg.get("end", 1e9)):
                    return seg
            except Exception:
                continue
        return None

    # ---------------- 检索 ----------------

    def search_text(self, query: str, top_k: int = 10,
                    ip_filter: str = "") -> list[dict]:
        """语义关键词检索 — 对镜头描述/IP/角色/情绪做加权关键词匹配"""
        q_tokens = [t for t in re.split(r"[\s,，、;；]+", query.lower()) if t]
        scored = []
        for shot in self.shots:
            if ip_filter and shot.ip_name != ip_filter:
                continue
            hay = " ".join([shot.description, shot.ip_name, shot.mood,
                            shot.scene_type, shot.filename] + shot.characters).lower()
            score = sum((3.0 if tok in shot.description.lower() else
                         2.0 if tok in shot.ip_name.lower() else
                         1.0 if tok in hay else 0.0) for tok in q_tokens)
            if score > 0:
                scored.append((score, shot))
        scored.sort(key=lambda x: -x[0])
        return [self._shot_result(s, score=sc) for sc, s in scored[:top_k]]

    def search_by_frame(self, frame_bgr: np.ndarray, top_k: int = 10) -> list[dict]:
        """以帧搜帧 — 余弦相似度"""
        qv = _extract_visual_vector(frame_bgr)
        scored = []
        for shot in self.shots:
            if shot.vector.size == 0:
                continue
            sim = float(np.dot(qv, shot.vector))
            scored.append((sim, shot))
        scored.sort(key=lambda x: -x[0])
        return [self._shot_result(s, score=round(sc, 4)) for sc, s in scored[:top_k]]

    def filter(self, primary_ip: str = "", scene_type: str = "",
               mood: str = "", min_motion: float = 0.0,
               max_motion: float = 1e9) -> list[dict]:
        """条件过滤"""
        out = []
        for shot in self.shots:
            if primary_ip and shot.ip_name != primary_ip:
                continue
            if scene_type and shot.scene_type != scene_type:
                continue
            if mood and shot.mood != mood:
                continue
            if not (min_motion <= shot.motion <= max_motion):
                continue
            out.append(self._shot_result(shot))
        return out

    def _shot_result(self, shot: ShotUnit, score: float | None = None) -> dict:
        d = {
            "file": shot.filename, "shot_id": shot.shot_id,
            "start": shot.start, "end": shot.end,
            "ip": shot.ip_name, "description": shot.description,
            "characters": shot.characters, "motion": shot.motion,
            "frame": shot.frame_path,
        }
        if score is not None:
            d["score"] = score
        return d

    # ---------------- 持久化 ----------------

    def save(self, path: str) -> None:
        data = {"shots": [s.to_dict() for s in self.shots],
                "built_at": time.strftime("%Y-%m-%d %H:%M:%S")}
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    def load(self, path: str) -> bool:
        p = Path(path)
        if not p.exists():
            return False
        data = json.loads(p.read_text(encoding="utf-8"))
        self.shots = [ShotUnit.from_dict(d) for d in data.get("shots", [])]
        return True

    def stats(self) -> dict:
        ips: dict[str, int] = {}
        for s in self.shots:
            ips[s.ip_name or "(无)"] = ips.get(s.ip_name or "(无)", 0) + 1
        return {"total_shots": len(self.shots),
                "videos": len({s.filename for s in self.shots}),
                "ip_distribution": ips}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    lib = _PROJECT_ROOT / "data" / "real_amv_test"
    videos = sorted(str(p) for p in lib.glob("*.mp4"))
    idx = FrameSemanticIndex()
    n = idx.build_from_library(videos, intel_cache_dir=str(_PROJECT_ROOT / "cache" / "material_intel"))
    idx.save(str(_PROJECT_ROOT / "data" / "frame_semantic_index.json"))
    print(f"\n构建完成: {idx.stats()}")
    print("\n语义检索测试: '战斗 火焰'")
    for r in idx.search_text("战斗 火焰", top_k=5):
        print(f"  {r['file'][:40]} [{r['start']:.1f}-{r['end']:.1f}s] {r['ip']} :: {r['description'][:40]}")
