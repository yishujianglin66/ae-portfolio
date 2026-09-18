# -*- coding: utf-8 -*-
"""HighlightScorer — 5维高光评分器 (v21a: motion + camera 2维先行)

借鉴 ai-montage-agent 设计思想:
  对素材的每个时间段从多维度打分, 解决 "素材选择盲目" 问题。
  
维度:
  1. motion       — 帧间运动强度 (像素差/光流)
  2. camera       — 全局运镜估计 (仿射变换幅度)
  3. scene_change — 场景切换次数 (画面突变)
  4. expression   — 人脸表情 (预留, 需face_detection)
  5. audio        — 音频能量 (预留, 需音轨提取)

用法:
    from core.highlight_scorer import HighlightScorer
    scorer = HighlightScorer(sample_fps=8, resize=(320, 180))
    score = scorer.score_segment("video.mp4", start_sec=5.0, end_sec=8.0)
    # score.total: 0.0 ~ 1.0 综合分
    # score.dimensions: {"motion": 0.7, "camera": 0.4, ...}
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger("highlight_scorer")


@dataclass
class SegmentScore:
    """单个视频片段的评分结果"""
    video_path: str
    start_sec: float
    end_sec: float
    # 各维度得分 (0-1归一化)
    motion: float = 0.0       # 运动强度
    camera: float = 0.0       # 运镜幅度
    scene_change: float = 0.0 # 场景切换密度
    expression: float = 0.0   # 表情丰富度 (预留)
    audio: float = 0.0        # 音频能量 (预留)
    # 加权总分
    total: float = 0.0
    # 元数据
    frame_count: int = 0
    duration_sec: float = 0.0
    compute_time_ms: float = 0.0
    # 证据链：评分依据日志
    reasoning_log: str = ""

    @property
    def dimensions(self) -> dict[str, float]:
        return {
            "motion": round(self.motion, 4),
            "camera": round(self.camera, 4),
            "scene_change": round(self.scene_change, 4),
            "expression": round(self.expression, 4),
            "audio": round(self.audio, 4),
        }


class HighlightScorer:
    """视频高光评分器 — 对素材片段进行多维度质量评分
    
    Parameters:
        sample_fps:  采样帧率 (降低计算量, 默认8fps)
        resize:      分析分辨率 (默认320x180)
        weights:     各维度权重 (默认: motion 0.35, camera 0.35, scene 0.15, expr 0.05, audio 0.10)
        motion_threshold: 场景切换检测阈值 (帧差>此值视为场景切换)
        cache_enabled: 是否缓存已计算的评分
    """

    DEFAULT_WEIGHTS = {
        "motion": 0.35,
        "camera": 0.35,
        "scene_change": 0.15,
        "expression": 0.05,
        "audio": 0.10,
    }

    def __init__(self, sample_fps: int = 8, resize: tuple[int, int] = (320, 180),
                 weights: dict[str, float] | None = None,
                 motion_threshold: float = 40.0,
                 cache_enabled: bool = True,
                 disk_cache_dir: str | None = None,
                 frame_extractor=None):
        self.sample_fps = sample_fps
        self.resize = resize
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.motion_threshold = motion_threshold
        self.cache_enabled = cache_enabled
        self._cache: dict[str, SegmentScore] = {}
        # v21d: 磁盘缓存 — 跨进程复用评分结果, 预扫描97s→秒级
        # 缓存键含 mtime+size+分析参数, 文件变更或参数变更自动失效
        self.disk_cache_dir = Path(disk_cache_dir) if disk_cache_dir else None
        if self.disk_cache_dir:
            self.disk_cache_dir.mkdir(parents=True, exist_ok=True)
        # P0: 可选SSIM自适应抽帧器 (core.frame_extractor.FrameExtractor)
        # 提供时 _sample_frames 改用抽帧保留帧 (跳过动漫一拍二/三重复帧),
        # 与抽帧器自身的磁盘缓存天然配合, 避免重复解码; None时保持均匀采样。
        self.frame_extractor = frame_extractor

    # ────────────────────────────────────────────────────────────────
    # 主接口: 对视频片段打分
    # ────────────────────────────────────────────────────────────────
    def score_segment(self, video_path: str, start_sec: float, end_sec: float) -> SegmentScore:
        """对视频指定时间段进行高光评分
        
        Args:
            video_path: 视频文件路径
            start_sec: 起始秒
            end_sec: 结束秒
            
        Returns:
            SegmentScore 包含各维度得分和加权总分
        """
        cache_key = f"{video_path}:{start_sec:.2f}-{end_sec:.2f}"
        if self.cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]

        t0 = time.time()
        frames, actual_start, actual_end = self._sample_frames(video_path, start_sec, end_sec)
        
        if len(frames) < 3:
            # 帧太少, 无法评分
            score = SegmentScore(
                video_path=video_path, start_sec=start_sec, end_sec=end_sec,
                total=0.0, frame_count=len(frames),
                duration_sec=end_sec - start_sec,
                compute_time_ms=(time.time() - t0) * 1000,
                reasoning_log="Insufficient frames for scoring"
            )
            return score

        # 维度1: 运动强度
        motion_score = self._compute_motion(frames)
        
        # 维度2: 运镜幅度 (全局运动估计)
        camera_score = self._compute_camera_movement(frames)
        
        # 维度3: 场景切换密度
        scene_score = self._compute_scene_changes(frames)
        
        # 维度4/5: 预留 (expression, audio)
        expression_score = 0.0
        audio_score = 0.0

        # 加权总分
        total = (
            motion_score * self.weights["motion"] +
            camera_score * self.weights["camera"] +
            scene_score * self.weights["scene_change"] +
            expression_score * self.weights["expression"] +
            audio_score * self.weights["audio"]
        )
        # 归一化到0-1
        total = np.clip(total, 0.0, 1.0)

        # Build evidence-based reasoning log
        reasoning_parts = []
        if motion_score > 0.5:
            reasoning_parts.append(f"High motion intensity ({motion_score:.2f})")
        if camera_score > 0.5:
            reasoning_parts.append(f"Strong camera movement ({camera_score:.2f})")
        if scene_score > 0.3:
            reasoning_parts.append(f"Frequent scene changes ({scene_score:.2f})")
        reasoning_log = "; ".join(reasoning_parts) if reasoning_parts else "Low visual activity detected"

        score = SegmentScore(
            video_path=video_path,
            start_sec=start_sec,
            end_sec=end_sec,
            motion=motion_score,
            camera=camera_score,
            scene_change=scene_score,
            expression=expression_score,
            audio=audio_score,
            total=float(total),
            frame_count=len(frames),
            duration_sec=end_sec - start_sec,
            compute_time_ms=(time.time() - t0) * 1000,
            reasoning_log=reasoning_log,
        )

        if self.cache_enabled:
            self._cache[cache_key] = score
        return score

    def score_all_segments(self, video_path: str, segment_duration: float = 2.0,
                           stride: float | None = None) -> list[SegmentScore]:
        """对整个视频按固定步长扫描打分
        
        Args:
            video_path: 视频文件路径
            segment_duration: 每个评分段落的时长 (秒)
            stride: 步进 (默认=segment_duration, 即不重叠)
            
        Returns:
            按时间排序的评分列表
        """
        if stride is None:
            stride = segment_duration

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频: {video_path}")
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps
        cap.release()

        scores = []
        t = 0.0
        while t + segment_duration <= duration:
            s = self.score_segment(video_path, t, t + segment_duration)
            scores.append(s)
            t += stride
        
        return scores

    # ────────────────────────────────────────────────
    # v21d: 磁盘缓存
    # ────────────────────────────────────────────────
    def _disk_cache_path(self, video_path: str, segment_duration: float,
                         stride: float) -> Path | None:
        """缓存文件路径: 内容hash包含文件标识+分析参数, 任一变更即失效"""
        if not self.disk_cache_dir:
            return None
        p = Path(video_path)
        try:
            st = p.stat()
        except OSError:
            return None
        key_src = f"{p.resolve()}|{st.st_mtime:.0f}|{st.st_size}|" \
                  f"fps={self.sample_fps}|rs={self.resize[0]}x{self.resize[1]}|" \
                  f"seg={segment_duration}|stride={stride}|thr={self.motion_threshold}"
        digest = hashlib.md5(key_src.encode("utf-8")).hexdigest()[:12]
        return self.disk_cache_dir / f"{p.stem}_{digest}.json"

    def load_disk_cache(self, video_path: str, segment_duration: float = 2.0,
                        stride: float | None = None) -> list[SegmentScore] | None:
        """从磁盘加载整视频评分缓存, 无缓存返回None"""
        if stride is None:
            stride = segment_duration
        path = self._disk_cache_path(video_path, segment_duration, stride)
        if path is None or not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scores = [SegmentScore(
                video_path=d["video_path"], start_sec=d["start_sec"],
                end_sec=d["end_sec"], motion=d.get("motion", 0.0),
                camera=d.get("camera", 0.0), scene_change=d.get("scene_change", 0.0),
                expression=d.get("expression", 0.0), audio=d.get("audio", 0.0),
                total=d.get("total", 0.0), frame_count=d.get("frame_count", 0),
                duration_sec=d.get("duration_sec", 0.0),
                reasoning_log=d.get("reasoning_log", ""),
            ) for d in data["scores"]]
            logger.info(f"磁盘缓存命中: {video_path} {len(scores)}段")
            return scores
        except (json.JSONDecodeError, KeyError, TypeError, OSError):
            return None

    def save_disk_cache(self, video_path: str, scores: list[SegmentScore],
                        segment_duration: float = 2.0,
                        stride: float | None = None) -> bool:
        """将整视频评分写入磁盘缓存"""
        if stride is None:
            stride = segment_duration
        path = self._disk_cache_path(video_path, segment_duration, stride)
        if path is None or not scores:
            return False
        try:
            data = {"video_path": video_path, "segment_duration": segment_duration,
                    "stride": stride,
                    "scores": [{k: getattr(s, k) for k in
                                ("video_path", "start_sec", "end_sec", "motion",
                                 "camera", "scene_change", "expression", "audio",
                                 "total", "frame_count", "duration_sec", "reasoning_log")}
                               for s in scores]}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            return True
        except OSError:
            return False

    def rank_segments(self, video_path: str, segment_duration: float = 2.0,
                      top_k: int = 10) -> list[SegmentScore]:
        """对视频段落按高光分排序, 返回Top-K"""
        all_scores = self.score_all_segments(video_path, segment_duration)
        return sorted(all_scores, key=lambda s: s.total, reverse=True)[:top_k]

    # ────────────────────────────────────────────────────────────────
    # 内部方法
    # ────────────────────────────────────────────────────────────────
    def _sample_frames(self, video_path: str, start_sec: float, end_sec: float) -> tuple[list[np.ndarray], float, float]:
        """从视频中采样帧 (按sample_fps, 缩小分辨率)

        P0: 若挂载 frame_extractor, 优先取SSIM自适应保留帧 (天然去重,
        命中抽帧磁盘缓存时零解码成本); 抽帧失败/为空时回退均匀采样。
        """
        if self.frame_extractor is not None:
            try:
                indices = self.frame_extractor.indices_within(video_path, start_sec, end_sec)
                if len(indices) >= 3:
                    cap = cv2.VideoCapture(video_path)
                    frames = []
                    for idx in indices:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
                        ret, frame = cap.read()
                        if ret:
                            frames.append(cv2.resize(frame, self.resize,
                                                     interpolation=cv2.INTER_AREA))
                    cap.release()
                    if len(frames) >= 3:
                        return frames, start_sec, end_sec
            except Exception as exc:  # 抽帧异常不阻塞评分
                logger.warning(f"frame_extractor采样失败, 回退均匀采样: {exc}")

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps

        # 钳制范围
        start_sec = max(0.0, min(start_sec, duration - 0.1))
        end_sec = min(end_sec, duration)

        frames = []
        frame_interval = max(1, int(fps / self.sample_fps))
        start_frame = int(start_sec * fps)
        end_frame = int(end_sec * fps)

        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        frame_idx = start_frame
        while frame_idx < end_frame:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_interval == 0:
                # 缩小
                frame_small = cv2.resize(frame, self.resize, interpolation=cv2.INTER_AREA)
                frames.append(frame_small)
            frame_idx += 1
        
        cap.release()
        return frames, start_sec, end_sec

    def _compute_motion(self, frames: list[np.ndarray]) -> float:
        """运动强度: 相邻帧像素差均值的归一化
        
        策略: 转为灰度 → 帧间绝对差 → 均值 → 归一化
        经验值: 静态画面~2-5, 中速运动~10-20, 快速打斗~30-60
        """
        if len(frames) < 2:
            return 0.0

        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        diffs = []
        for i in range(1, len(grays)):
            diff = cv2.absdiff(grays[i], grays[i - 1])
            diffs.append(float(np.mean(diff)))
        
        avg_diff = np.mean(diffs)
        # 归一化: 经验上60以上算极高, 用sigmoid压缩
        # score = 1 / (1 + exp(-(x - 20) / 10)) → 20时约0.5, 40时约0.9
        score = 1.0 / (1.0 + np.exp(-(avg_diff - 15.0) / 8.0))
        return float(np.clip(score, 0.0, 1.0))

    def _compute_camera_movement(self, frames: list[np.ndarray]) -> float:
        """运镜幅度: 通过帧间仿射变换估计全局运动
        
        策略: 相邻帧 → ORB特征 → 匹配 → 估计变换矩阵 → 提取平移/缩放幅度
        高幅度 = 运镜活跃 (推/拉/摇/移), 低幅度 = 静态/微动
        """
        if len(frames) < 3:
            return 0.0

        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        movements = []
        
        orb = cv2.ORB_create(nfeatures=100)
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

        for i in range(1, len(grays)):
            kp1, des1 = orb.detectAndCompute(grays[i - 1], None)
            kp2, des2 = orb.detectAndCompute(grays[i], None)
            
            if des1 is None or des2 is None or len(des1) < 5 or len(des2) < 5:
                movements.append(0.0)
                continue

            matches = bf.match(des1, des2)
            if len(matches) < 4:
                movements.append(0.0)
                continue

            matches = sorted(matches, key=lambda m: m.distance)[:20]
            pts1 = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            pts2 = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)

            # 估计仿射变换
            M, _ = cv2.estimateAffinePartial2D(pts1, pts2)
            if M is None:
                movements.append(0.0)
                continue

            # 平移分量
            tx, ty = M[0, 2], M[1, 2]
            translation = np.sqrt(tx**2 + ty**2)
            
            # 缩放分量 (对角线元素偏离1的程度)
            scale = abs(M[0, 0] - 1.0) + abs(M[1, 1] - 1.0)
            
            # 旋转分量 (非对角线)
            rotation = abs(M[0, 1]) + abs(M[1, 0])
            
            # 综合运动幅度 (像素级, 320x180空间)
            magnitude = translation + scale * 100 + rotation * 50
            movements.append(magnitude)

        if not movements:
            return 0.0

        avg_mag = np.mean(movements)
        # 归一化: 320x180空间中, 移动>10像素算较强
        score = 1.0 / (1.0 + np.exp(-(avg_mag - 8.0) / 5.0))
        return float(np.clip(score, 0.0, 1.0))

    def _compute_scene_changes(self, frames: list[np.ndarray]) -> float:
        """场景切换密度: 检测帧间突变 (镜头切换)
        
        策略: 直方图比较 + 帧差超阈值 → 场景切换计数 → 密度归一化
        """
        if len(frames) < 4:
            return 0.0

        grays = [cv2.cvtColor(f, cv2.COLOR_BGR2GRAY) for f in frames]
        scene_changes = 0

        for i in range(1, len(grays)):
            diff = cv2.absdiff(grays[i], grays[i - 1])
            mean_diff = np.mean(diff)
            if mean_diff > self.motion_threshold:
                scene_changes += 1

        # 密度: 场景切换数 / 帧数
        density = scene_changes / max(len(frames) - 1, 1)
        # 归一化: 2秒内1次切换(密度~0.06)算较高
        score = 1.0 / (1.0 + np.exp(-(density - 0.05) / 0.03))
        return float(np.clip(score, 0.0, 1.0))

    # ────────────────────────────────────────────────────────────────
    # 工具方法
    # ────────────────────────────────────────────────────────────────
    def clear_cache(self):
        """清除缓存"""
        self._cache.clear()

    def get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"无法打开视频: {video_path}")
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        cap.release()
        return total_frames / fps

    def __repr__(self) -> str:
        return (f"HighlightScorer(sample_fps={self.sample_fps}, "
                f"resize={self.resize}, cache={len(self._cache)} entries)")


# ────────────────────────────────────────────────────────────────────
# CLI 快速验证
# ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("用法: py core/highlight_scorer.py <video_path> [start] [end]")
        sys.exit(1)
    
    video = sys.argv[1]
    start = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
    end = float(sys.argv[3]) if len(sys.argv) > 3 else start + 2.0
    
    scorer = HighlightScorer()
    print(f"评分: {video} [{start:.1f}s - {end:.1f}s]")
    
    t0 = time.time()
    score = scorer.score_segment(video, start, end)
    elapsed = time.time() - t0
    
    print(f"  motion:       {score.motion:.4f}")
    print(f"  camera:       {score.camera:.4f}")
    print(f"  scene_change: {score.scene_change:.4f}")
    print(f"  total:        {score.total:.4f}")
    print(f"  frames:       {score.frame_count}")
    print(f"  耗时:         {elapsed*1000:.0f}ms")
