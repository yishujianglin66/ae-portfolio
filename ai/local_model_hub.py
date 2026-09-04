# -*- coding: utf-8 -*-
"""LocalModelHub — 本地训练产物统一加载层
=================================================
解决诊断报告 P0-1 断链: 训练产物(.pt/.pkl)此前只被 tNN_* 实验脚本消费,
生产管线(production_director)从未加载。本模块提供懒加载单例,
让导演系统以最小侵入方式消费真实训练产物。

已接入产物:
- models/scene_classifier_v1.pt  ResNet18 7类场景分类 (T27b训练)
  → classify_video_scene(): 素材场景打标, 增强 MaterialIntelTag.content.scene_type
- models/rhythm_reward.pkl       GradientBoosting 节奏奖励模型 (P3.1训练)
  → score_cut_plan(): 多切点方案择优, 预测踩拍质量

所有接口在权重缺失/依赖缺失时优雅降级(返回 None / 0.0), 绝不抛异常中断渲染。
"""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Dict, List, Optional

from core.torch_runtime import infer_ctx

ROOT = Path(__file__).resolve().parent.parent
SCENE_CKPT = ROOT / "models" / "scene_classifier_v1.pt"
RHYTHM_PKL = ROOT / "models" / "rhythm_reward.pkl"

# 训练类别 → ContentTag.scene_type 词表映射
# 训练词表: landscape/battle/emotional/dialog/daily/ceremony/comedy
# 素材标签词表: battle/action/closeup/landscape/indoor/dialogue/unknown
SCENE_TO_CONTENT_TAG = {
    "battle": "battle",
    "landscape": "landscape",
    "dialog": "dialogue",
    "emotional": "closeup",
    "daily": "indoor",
    "ceremony": "landscape",
    "comedy": "dialogue",
}


class LocalModelHub:
    """懒加载单例 — 首次调用时才加载权重, 线程安全"""

    _instance: Optional["LocalModelHub"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self._scene_model = None
        self._scene_classes: List[str] = []
        self._scene_transform = None
        self._scene_load_failed = False
        self._rhythm_bundle = None
        self._rhythm_load_failed = False

    # ---------------- 场景分类器 ----------------

    def scene_classifier_available(self) -> bool:
        return SCENE_CKPT.exists() and not self._scene_load_failed

    def _load_scene_model(self):
        if self._scene_model is not None or self._scene_load_failed:
            return
        try:
            import torch
            from torch import nn
            from torchvision import models, transforms
            ckpt = torch.load(SCENE_CKPT, map_location="cpu", weights_only=False)
            config = ckpt.get("config", {})
            n_classes = config.get("n_classes", 7)
            base = models.resnet18(weights=None)
            base.fc = nn.Linear(base.fc.in_features, n_classes)
            base.load_state_dict(ckpt["model_state"])
            self._scene_model = base.eval()
            self._scene_classes = ckpt.get("scene_classes", [])
            self._scene_transform = transforms.Compose([
                transforms.Resize((224, 224)),
                transforms.ToTensor(),
                transforms.Normalize(mean=[0.485, 0.456, 0.406],
                                     std=[0.229, 0.224, 0.225]),
            ])
        except Exception as e:
            print(f"[LocalModelHub] 场景分类器加载失败, 降级跳过: {e}")
            self._scene_load_failed = True

    def classify_video_scene(self, video_path: str,
                             n_frames: int = 8) -> Optional[Dict]:
        """对视频均匀采样n帧做场景分类, 返回主导场景。

        Returns:
            {"scene": 训练类别, "content_scene": ContentTag词表映射,
             "confidence": 主导类别占比, "distribution": {类别: 占比}}
            权重缺失/失败时返回 None。
        """
        if not self.scene_classifier_available():
            return None
        self._load_scene_model()
        if self._scene_model is None:
            return None
        try:
            import cv2
            import torch
            from PIL import Image
            import numpy as np

            cap = cv2.VideoCapture(str(video_path))
            total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total <= 0:
                cap.release()
                return None
            idxs = np.linspace(0, total - 1, min(n_frames, total)).astype(int)
            votes: Dict[str, int] = {}
            probs_sum: Dict[str, float] = {}
            for fi in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(fi))
                ok, frame = cap.read()
                if not ok or frame is None:
                    continue
                img = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                with infer_ctx():
                    logits = self._scene_model(self._scene_transform(img).unsqueeze(0))
                    prob = torch.softmax(logits, dim=1)[0]
                top = int(prob.argmax())
                label = self._scene_classes[top]
                votes[label] = votes.get(label, 0) + 1
                probs_sum[label] = probs_sum.get(label, 0.0) + float(prob[top])
            cap.release()
            if not votes:
                return None
            n_voted = sum(votes.values())
            best = max(votes, key=votes.get)
            return {
                "scene": best,
                "content_scene": SCENE_TO_CONTENT_TAG.get(best, "unknown"),
                "confidence": votes[best] / n_voted,
                "distribution": {k: round(v / n_voted, 3) for k, v in votes.items()},
            }
        except Exception as e:
            print(f"[LocalModelHub] 场景推理失败({Path(video_path).name}), 降级跳过: {e}")
            return None

    # ---------------- 节奏奖励模型 ----------------

    def rhythm_scorer_available(self) -> bool:
        return RHYTHM_PKL.exists() and not self._rhythm_load_failed

    def _load_rhythm_bundle(self):
        if self._rhythm_bundle is not None or self._rhythm_load_failed:
            return
        try:
            import pickle
            bundle = pickle.loads(RHYTHM_PKL.read_bytes())
            if isinstance(bundle, dict):
                self._rhythm_bundle = (bundle["regressor"], bundle["calibrator"])
            else:
                self._rhythm_bundle = (bundle, None)
        except Exception as e:
            print(f"[LocalModelHub] 节奏奖励模型加载失败, 降级跳过: {e}")
            self._rhythm_load_failed = True

    def score_cut_plan(self, cuts: List[float], beats: List[float],
                       duration: float) -> float:
        """对候选切点方案打分(预测踩拍质量, 0~1)。
        与 ai.rhythm_reward.score_plan 逻辑一致, 但缓存模型避免重复IO。
        cuts/beats 必须在同一时间坐标系(通常为BGM绝对时间)。
        """
        if not self.rhythm_scorer_available():
            return 0.0
        self._load_rhythm_bundle()
        if self._rhythm_bundle is None:
            return 0.0
        try:
            import numpy as np
            from ai.rhythm_reward import cut_features, FEATURE_KEYS
            model, calib = self._rhythm_bundle
            feats = cut_features(list(cuts), list(beats), float(duration))
            x = np.array([[feats[k] for k in FEATURE_KEYS]])
            raw = float(model.predict(x)[0])
            if calib is not None:
                raw = float(calib.predict(np.array([raw]))[0])
            return raw
        except Exception as e:
            print(f"[LocalModelHub] 节奏打分失败, 降级跳过: {e}")
            return 0.0

    def status(self) -> Dict:
        """诊断用: 各产物接入状态"""
        return {
            "scene_classifier": {
                "path": str(SCENE_CKPT),
                "exists": SCENE_CKPT.exists(),
                "loaded": self._scene_model is not None,
            },
            "rhythm_reward": {
                "path": str(RHYTHM_PKL),
                "exists": RHYTHM_PKL.exists(),
                "loaded": self._rhythm_bundle is not None,
            },
        }


def get_hub() -> LocalModelHub:
    return LocalModelHub()
