"""models/anime_camera_classifier.py - 动漫运镜分类器 (A5 生产接入)

两级架构 (Step 4 最终方案):
  L1: VideoMAE-LoRA 粗分类 (4 类: Static/Motion/Pull/Push) + 逐类调优阈值
  L2: 粗类为 Motion 时, 用光流规则细分方向 (pan_left/pan_right/tilt/orbit)
  → 输出项目 CAMERA_LABELS (13 类) 之一 + 置信度

接入点: ai/camera_decision.py SourceCameraInventory.inject()
降级链: LoRA(GPU) → 光流规则(CPU) → unknown

用法:
  from models.anime_camera_classifier import AnimeCameraClassifier
  clf = AnimeCameraClassifier()
  r = clf.classify_video("素材.mp4")
  # r = {"label": "pan_left", "coarse": "Motion", "confidence": 0.72, "source": "videomae-lora"}
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

MODEL_DIR = r"D:\AE-Data\Models\VideoMAE-MovieShots\movement"
# 生产默认: v3b (fine 10 类, 粗4类口径 0.7729 > v1 0.7172, 直接输出方向无需光流细分)
DEFAULT_LORA_DIR = str(PROJECT_ROOT / "models" / "output" / "anime_camera_lora_v3")
DEFAULT_THRESHOLDS = str(PROJECT_ROOT / "models" / "output" / "thresholds_tuned.json")

NUM_FRAMES = 16
IMG_SIZE = 224
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

COARSE_LABELS = ["Static", "Motion", "Pull", "Push"]

# Motion 粗类 → 光流规则方向 → 项目标签
RULE_TO_PROJECT = {
    "static": "static",
    "pan_left": "pan_left", "pan_right": "pan_right",
    "tilt_up": "tilt_up", "tilt_down": "tilt_down",
    "zoom_in": "zoom_in", "zoom_out": "zoom_out",
    "zoom_back": "zoom_back", "diag_pan": "diag_pan",
    "orbit": "orbit", "push": "push",
    "complex": "complex", "unknown": "pan_left",
}


class AnimeCameraClassifier:
    """动漫运镜分类器 (自动识别 fine/coarse schema + 阈值校准 + 光流降级)。"""

    def __init__(self, lora_dir: str = DEFAULT_LORA_DIR,
                 thresholds_path: Optional[str] = None,
                 model_dir: str = MODEL_DIR):
        self.lora_dir = lora_dir
        self.model_dir = model_dir
        self.labels = self._load_meta_labels()
        self.schema = "fine" if len(self.labels) >= 8 else "coarse"
        if thresholds_path is None:
            thresholds_path = str(Path(lora_dir) / "thresholds_tuned.json")
        self.thresholds = self._load_thresholds(thresholds_path)
        self._model = None
        self._device = None

    def _load_meta_labels(self) -> List[str]:
        meta = Path(self.lora_dir) / "meta.json"
        if meta.exists():
            try:
                data = json.loads(meta.read_text(encoding="utf-8"))
                if isinstance(data.get("labels"), list):
                    return [str(x) for x in data["labels"]]
            except (json.JSONDecodeError, OSError):
                pass
        return COARSE_LABELS

    @staticmethod
    def _load_thresholds(path: str) -> Dict[str, float]:
        p = Path(path)
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                return {k: float(v) for k, v in data.get("thresholds", {}).items()}
            except (json.JSONDecodeError, OSError):
                pass
        return {"Static": 0.5, "Motion": 0.45, "Pull": 0.15, "Push": 0.45}

    def _ensure_model(self) -> bool:
        """懒加载 LoRA 模型 (GPU 可用时), 失败返回 False 走降级。"""
        if self._model is not None:
            return True
        try:
            import torch
            from transformers import VideoMAEForVideoClassification
            from peft import PeftModel
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            # fine schema: 分类头是训练时 num_labels 重建的 (不在基座 ckpt),
            # 训练脚本用 modules_to_save=["classifier"] 存进 adapter;
            # 这里必须同样以 num_labels 重建 base, 否则 4 类头与 10 类 adapter 不匹配
            if self.schema == "fine":
                base = VideoMAEForVideoClassification.from_pretrained(
                    self.model_dir, local_files_only=True,
                    num_labels=len(self.labels), ignore_mismatched_sizes=True)
            else:
                base = VideoMAEForVideoClassification.from_pretrained(
                    self.model_dir, local_files_only=True)
            base.to(self._device)
            self._model = PeftModel.from_pretrained(base, self.lora_dir)
            self._model.to(self._device)
            self._model.eval()
            logger.info("AnimeCameraClassifier 就绪 (device=%s, schema=%s, %d 类)",
                        self._device, self.schema, len(self.labels))
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("LoRA 加载失败, 走光流规则降级: %s", exc)
            self._model = None
            return False

    def _predict(self, video_path: str) -> Optional[Dict[str, Any]]:
        """LoRA 前向 (手动归一化 + 逐类阈值)。"""
        if not self._ensure_model():
            return None
        import torch
        from decord import VideoReader, cpu
        try:
            vr = VideoReader(video_path, ctx=cpu(0))
            n = len(vr)
            if n < 2:
                return None
            if n <= NUM_FRAMES:
                idxs = list(range(n))
            else:
                step = (n - 1) / (NUM_FRAMES - 1)
                idxs = [round(i * step) for i in range(NUM_FRAMES)]
            frames = vr.get_batch(idxs).asnumpy().astype(np.float32).transpose(0, 3, 1, 2)
            if frames.shape[0] < NUM_FRAMES:
                rep = (NUM_FRAMES + frames.shape[0] - 1) // frames.shape[0]
                frames = np.tile(frames, (rep, 1, 1, 1))[:NUM_FRAMES]
        except Exception:  # noqa: BLE001
            return None

        from torchvision.transforms import v2
        x = v2.Resize((IMG_SIZE, IMG_SIZE))(torch.from_numpy(frames)).float() / 255.0
        mean = torch.tensor(MEAN).view(1, 3, 1, 1)
        std = torch.tensor(STD).view(1, 3, 1, 1)
        x = ((x - mean) / std).unsqueeze(0).to(self._device)
        with torch.no_grad():
            logits = self._model(pixel_values=x).logits[0]
        probs = torch.softmax(logits, dim=-1).cpu().numpy()

        # 阈值化: 高于阈值的类取概率最大者, 全低于 → majority
        thresh = np.array([self.thresholds.get(l, 0.4) for l in self.labels])
        above = np.where(probs >= thresh)[0]
        if len(above) == 0:
            pred = int(probs.argmax())
        else:
            pred = int(above[np.argmax(probs[above])])
        return {"label": self.labels[pred],
                "confidence": float(probs[pred]),
                "probs": {self.labels[i]: float(probs[i]) for i in range(len(self.labels))}}

    def classify_video(self, video_path: str) -> Dict[str, Any]:
        """完整分类: LoRA (fine 直接输出 / coarse 加光流细分) + 降级链。"""
        if not Path(video_path).exists():
            # 快速失败: 不存在的文件不得触发模型加载
            # (实测 from_pretrained 首次加载 30s+, 曾拖死全量 pytest 会话)
            return {"label": "unknown", "coarse": None,
                    "confidence": 0.0, "source": "unknown"}
        result = self._predict(video_path)

        if result is None:
            # 降级: 纯光流规则
            try:
                from core.camera_movement_classifier import classify_video as rule_classify
                r = rule_classify(video_path)
                return {"label": r["dominant"], "coarse": None,
                        "confidence": r["confidence"], "source": "flow_rule_degraded"}
            except Exception:  # noqa: BLE001
                return {"label": "unknown", "coarse": None,
                        "confidence": 0.0, "source": "unknown"}

        label = result["label"]
        conf = result["confidence"]
        if self.schema == "fine":
            # fine 模式: 直接输出细方向 (无光流细分)
            return {"label": label, "coarse": None,
                    "confidence": conf, "source": "videomae-lora-fine"}

        # coarse 模式: Motion → 光流细分
        if label == "Motion":
            try:
                from core.camera_movement_classifier import classify_video as rule_classify
                r = rule_classify(video_path)
                fine = RULE_TO_PROJECT.get(r["dominant"], "pan_left")
                return {"label": fine, "coarse": label,
                        "confidence": round(conf * max(0.5, r["confidence"]), 4),
                        "source": "videomae-lora+flow"}
            except Exception:  # noqa: BLE001
                return {"label": "pan_left", "coarse": label,
                        "confidence": conf, "source": "videomae-lora"}
        if label == "Static":
            return {"label": "static", "coarse": label,
                    "confidence": conf, "source": "videomae-lora"}
        if label == "Pull":
            return {"label": "zoom_out", "coarse": label,
                    "confidence": conf, "source": "videomae-lora"}
        return {"label": "zoom_in", "coarse": label,
                "confidence": conf, "source": "videomae-lora"}


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    clf = AnimeCameraClassifier()
    for v in sys.argv[1:]:
        print(v, "->", clf.classify_video(v))
