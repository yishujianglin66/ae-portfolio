"""models/camera/videomae_camera.py — VideoMAE-MovieShots 运镜分类器适配器

把现成 VideoMAE 微调模型 (gullalc/videomae-base-finetuned-kinetics-
movieshots-movement, MIT, 91.35% acc) 接入导演管线 T3 运镜感知:

  - 懒加载本地权重 (D:\\AE-Data\\Models\\VideoMAE-MovieShots\\movement)
  - cv2 均匀采样 16 帧 (不依赖 decord, 兼容项目 Python 3.11 环境)
  - MovieShots 5 类 → 项目 CAMERA_LABELS 映射
  - 低置信度返回 None → 调用方回退光流规则分类器
  - 输出可被 ai/camera_decision.SourceCameraInventory.inject() 直接消费

与 verify_movieshots_videomae.py (脚本版) 的区别: 本模块是**可复用组件**,
供 production_director 在管线内调用, 而非一次性验证脚本。

用法:
    from models.camera.videomae_camera import get_videomae_classifier
    clf = get_videomae_classifier()
    if clf.available():
        res = clf.classify("素材.mp4")
        if res:
            inv.inject("素材.mp4", label=res["label"], confidence=res["confidence"])
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
from core.torch_runtime import infer_ctx

logger = logging.getLogger(__name__)

# 默认本地权重目录 (verify_movieshots_videomae.py 已下载)
DEFAULT_MODEL_DIR = r"D:\AE-Data\Models\VideoMAE-MovieShots\movement"
_MODEL_ID = "gullalc/videomae-base-finetuned-kinetics-movieshots-movement"

# 采样参数
N_FRAMES = 16
FRAME_SIZE = 224

# MovieShots 运镜 5 类 → 项目 CAMERA_LABELS 映射
# (与 models/train_movieshots_camera.py 的映射约定一致)
MOVIESHOTS_TO_PROJECT: Dict[str, str] = {
    "Static": "static",
    "Motion": "pan_left",
    "Pull": "zoom_out",
    "Push": "zoom_in",
    "Multi_movement": "complex",
}

# 项目标签 → MovieShots 标签 (反向)
PROJECT_TO_MOVIESHOTS: Dict[str, str] = {
    v: k for k, v in MOVIESHOTS_TO_PROJECT.items()
}

# Kandinsky VideoMAE-large 18 运镜类 → 项目 CAMERA_LABELS 映射
# (ai-forever/kandinsky-videomae-large-camera-motion, 多标签头)
KANDINSKY_DEFAULT_MODEL_DIR = (
    r"D:\AE-Data\Models\VideoMAE-MovieShots\kandinsky-large")
KANDINSKY_TO_PROJECT: Dict[str, str] = {
    "arc_left": "orbit", "arc_right": "orbit",
    "dolly_in": "push", "dolly_out": "zoom_out",
    "pan_left": "pan_left", "pan_right": "pan_right",
    "pedestal_down": "tilt_down", "pedestal_up": "tilt_up",
    "roll_left": "orbit", "roll_right": "orbit",
    "static": "static",
    "tilt_down": "tilt_down", "tilt_up": "tilt_up",
    "truck_left": "pan_left", "truck_right": "pan_right",
    "undefined": "unknown",
    "zoom_in": "zoom_in", "zoom_out": "zoom_out",
    "pov": "complex", "shake": "complex", "track": "complex",
}


def _read_frames_cv2(video_path: str, n_frames: int = N_FRAMES,
                     size: int = FRAME_SIZE):
    """用 cv2 均匀采样 n_frames 帧 → (T, C, H, W) float32 0-255 张量。

    返回 None 表示视频不可读/过短。
    """
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 2:
            return None
        if total <= n_frames:
            idxs = list(range(total))
        else:
            step = (total - 1) / (n_frames - 1)
            idxs = [round(i * step) for i in range(n_frames)]
        frames = []
        for i in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, frame = cap.read()
            if not ok:
                continue
            frame = cv2.resize(frame, (size, size))
            frames.append(frame)  # (H, W, C) BGR
        if len(frames) < 2:
            return None
        # 补齐到精确 n_frames (VideoMAE 位置嵌入要求固定帧数, 实测读帧失败
        # 导致帧数不足时 kandinsky 报 tensor 尺寸失配 1372 vs 1568)
        if len(frames) < n_frames:
            last = frames[-1]
            while len(frames) < n_frames:
                frames.append(last)
        arr = np.stack(frames).astype(np.float32)  # (T,H,W,C)
        arr = arr[..., ::-1]  # BGR → RGB
        # 连续内存: 翻转视图带负步长, torch 不接受 (实测报错 negative strides)
        arr = np.ascontiguousarray(np.transpose(arr, (0, 3, 1, 2)))  # (T,C,H,W)
        return arr
    finally:
        cap.release()


class VideoMAECameraClassifier:
    """VideoMAE-MovieShots 运镜分类器 (懒加载, 线程安全欠考虑, 单例使用)。

    支持两种模型头:
      - 单标签 (gullalc 5 类): softmax + argmax
      - 多标签 (kandinsky-large 18 类): sigmoid + 阈值, 取最高分有效类
    """

    def __init__(self, model_dir: str = DEFAULT_MODEL_DIR,
                 conf_threshold: float = 0.45,
                 device: Optional[str] = None,
                 multilabel: bool = False,
                 label_map: Optional[Dict[str, str]] = None,
                 sigmoid_threshold: float = 0.5) -> None:
        self.model_dir = model_dir
        self.conf_threshold = conf_threshold
        self._device = device
        self.multilabel = multilabel
        self.label_map = label_map or {}
        self.sigmoid_threshold = sigmoid_threshold
        self._proc = None
        self._model = None
        self._labels: Optional[list] = None
        self._load_error: Optional[str] = None
        self._n_infer = 0
        self._total_infer_sec = 0.0

    # ── 加载 ──────────────────────────────────────────────

    def _pick_device(self) -> str:
        if self._device:
            return self._device
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:  # noqa: BLE001
            pass
        return "cpu"

    def _ensure_loaded(self) -> bool:
        """懒加载模型, 失败记 error 不抛异常。"""
        if self._model is not None:
            return True
        if self._load_error:
            return False
        if not os.path.isdir(self.model_dir):
            self._load_error = f"model dir not found: {self.model_dir}"
            logger.warning("[VideoMAE] %s", self._load_error)
            return False
        try:
            from transformers import (
                VideoMAEForVideoClassification,
                VideoMAEImageProcessor,
            )
            import torch

            self._proc = VideoMAEImageProcessor.from_pretrained(self.model_dir)
            self._model = VideoMAEForVideoClassification.from_pretrained(
                self.model_dir)
            self._model.eval()
            self._model.to(self._pick_device())
            cfg = self._model.config
            if hasattr(cfg, "id2label") and cfg.id2label:
                self._labels = [cfg.id2label[i] for i in sorted(cfg.id2label)]
            else:
                self._labels = list(MOVIESHOTS_TO_PROJECT.keys())
            logger.info("[VideoMAE] loaded %s, device=%s, labels=%s",
                        Path(self.model_dir).name,
                        next(self._model.parameters()).device, self._labels)
            return True
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)
            logger.warning("[VideoMAE] load failed: %s", exc)
            return False

    def available(self) -> bool:
        """模型目录存在即视为可用 (不强制加载, 供管线预检)。"""
        return os.path.isdir(self.model_dir) and self._load_error is None

    # ── 推理 ──────────────────────────────────────────────

    def classify(self, video_path: str) -> Optional[Dict[str, Any]]:
        """对单个视频做运镜分类。

        Returns:
            None — 模型不可用/视频不可读/低置信度 (调用方应回退规则分类器)
            Dict — {"label": 项目运镜标签, "confidence": 0-1,
                    "raw_label": 模型原始标签, "infer_seconds": float,
                    "all_labels": [(原始标签, 置信度), ...] (多标签模型时)}
        """
        if not self._ensure_loaded():
            return None
        frames = _read_frames_cv2(video_path)
        if frames is None:
            return None
        try:
            import torch

            inputs = self._proc(frames, return_tensors="pt")
            device = next(self._model.parameters()).device
            inputs = {k: v.to(device) for k, v in inputs.items()}
            t0 = time.time()
            with infer_ctx(str(device)):
                logits = self._model(**inputs).logits
            elapsed = time.time() - t0
            self._n_infer += 1
            self._total_infer_sec += elapsed

            if self.multilabel:
                return self._classify_multilabel(logits[0], elapsed, video_path)

            probs = torch.softmax(logits, dim=-1)[0]
            top_idx = int(probs.argmax().item())
            conf = float(probs[top_idx].item())
            raw_label = self._labels[top_idx] if top_idx < len(self._labels) else "Unknown"
            if conf < self.conf_threshold:
                logger.info("[VideoMAE] low conf %.3f for %s → fallback to rule",
                            conf, Path(video_path).name)
                return None
            return {
                "label": self.label_map.get(raw_label, MOVIESHOTS_TO_PROJECT.get(raw_label, "complex")),
                "confidence": round(conf, 4),
                "raw_label": raw_label,
                "infer_seconds": round(elapsed, 3),
            }
        except Exception as exc:  # noqa: BLE001
            logger.warning("[VideoMAE] classify failed %s: %s",
                           Path(video_path).name, exc)
            return None

    def _classify_multilabel(self, logits, elapsed: float,
                             video_path: str) -> Optional[Dict[str, Any]]:
        """多标签头 (kandinsky-large): sigmoid 阈值 → 取最高分有效类。

        未定义类 (undefined) 或全部低于阈值 → None (回退规则分类器)。
        """
        import torch

        probs = torch.sigmoid(logits)
        above = [(i, float(probs[i].item())) for i in range(len(probs))
                 if float(probs[i].item()) >= self.sigmoid_threshold]
        if not above:
            logger.info("[VideoMAE-kandinsky] no class above %.2f for %s → fallback",
                        self.sigmoid_threshold, Path(video_path).name)
            return None
        above.sort(key=lambda x: x[1], reverse=True)
        top_idx, conf = above[0]
        raw_label = self._labels[top_idx] if top_idx < len(self._labels) else "Unknown"
        mapped = self.label_map.get(raw_label)
        if mapped is None or mapped == "unknown":
            # 模型判断"未定义运镜" → 不回退规则, 直接放弃注入
            return None
        return {
            "label": mapped,
            "confidence": round(conf, 4),
            "raw_label": raw_label,
            "infer_seconds": round(elapsed, 3),
            "all_labels": [
                (self._labels[i], round(float(probs[i].item()), 4))
                for i, _ in above[:3]
            ],
        }

    def batch_classify(self, video_paths) -> Dict[str, Optional[Dict[str, Any]]]:
        """批量分类。返回 {path: result|None}。"""
        return {p: self.classify(p) for p in video_paths}

    def stats(self) -> Dict[str, Any]:
        return {
            "loaded": self._model is not None,
            "n_infer": self._n_infer,
            "avg_infer_sec": (
                round(self._total_infer_sec / self._n_infer, 3)
                if self._n_infer else None),
            "model_dir": self.model_dir,
            "load_error": self._load_error,
        }


# 模块级单例
_SINGLETON: Optional[VideoMAECameraClassifier] = None
_KANDINSKY_SINGLETON: Optional[VideoMAECameraClassifier] = None


def get_videomae_classifier(**kwargs) -> VideoMAECameraClassifier:
    """获取模块级单例 (参数只在首次创建时生效)。"""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = VideoMAECameraClassifier(**kwargs)
    return _SINGLETON


def get_kandinsky_classifier(**kwargs) -> VideoMAECameraClassifier:
    """获取 kandinsky-videomae-large (18 类多标签) 分类器单例。"""
    global _KANDINSKY_SINGLETON
    if _KANDINSKY_SINGLETON is None:
        defaults = dict(
            model_dir=KANDINSKY_DEFAULT_MODEL_DIR,
            multilabel=True,
            label_map=KANDINSKY_TO_PROJECT,
            sigmoid_threshold=0.5,
        )
        defaults.update(kwargs)
        _KANDINSKY_SINGLETON = VideoMAECameraClassifier(**defaults)
    return _KANDINSKY_SINGLETON


def classify_cascade(video_path: str) -> Optional[Dict[str, Any]]:
    """三级级联运镜分类 (2026-08-14 A/B 评估结论):

    1. kandinsky-large (18 类, 高精度低召回): 有标签直接用
       — A/B 实测其有效样本置信中位 0.99, 且不会把静态素材误标 pan_left
         (base 版 68% 素材被误标 pan_left)
    2. gullalc base (5 类, 高召回): kandinsky 拒绝时兜底
    3. 两者都拒绝 → 返回 None (调用方回退光流规则分类器)

    返回结构与 classify() 一致, 多一个 "stage" 字段 ("kandinsky"/"base")。
    """
    kand = get_kandinsky_classifier()
    if kand.available():
        r = kand.classify(video_path)
        if r:
            r["stage"] = "kandinsky"
            return r
    base = get_videomae_classifier()
    if base.available():
        r = base.classify(video_path)
        if r:
            r["stage"] = "base"
            return r
    return None
