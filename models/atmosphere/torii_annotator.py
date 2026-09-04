"""models/atmosphere/torii_annotator.py — ToriiGate-2B 动漫视频氛围标注器 (W6)

填补 W6 缺口 (视频级情绪/氛围识别 — 调研确认此前开源空白):
ToriiGate-v0.4-2B (Minthy/ToriiGate, Apache-2.0, Qwen2.5-VL 基座) 是
动漫专用视觉语言模型, 对动漫帧的内容理解/氛围/镜头语言有领域先验。

设计要点:
  - 视频 → cv2 均匀采样 max_frames 帧 (默认 4) → VLM 结构化 JSON 标注
  - 懒加载 + bf16 + low_cpu_mem_usage (适配 RTX 4060 8GB)
  - GPU 被占用/OOM/模型缺失 → available()=False, annotate()=None
    (调用方静默跳过, 绝不阻断管线)
  - energy 字段稳健解析 (实测模型会输出整句描述而非数字)
  - 输出 AtmosphereResult 可注入素材库标签 (material attribution)

用法:
    from models.atmosphere.torii_annotator import get_torii_annotator
    ann = get_torii_annotator()
    if ann.available():
        r = ann.annotate("素材.mp4")
        if r:
            print(r.atmosphere, r.energy)
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
from core.torch_runtime import infer_ctx

logger = logging.getLogger(__name__)

DEFAULT_MODEL_DIR = r"D:\AE-Data\Models\ToriiGate\ToriiGate-v0.4-2B"
_MODEL_ID = "Minthy/ToriiGate-v0.4-2B"

# 采样参数
MAX_FRAMES = 4
FRAME_SIZE = 448

# 氛围词汇表 (供下游标签对齐; 模型自由输出, 做归一化映射)
ATMOSPHERE_VOCAB = {
    "燃": "燃向", "燃向": "燃向", "热血": "燃向", "高燃": "燃向",
    "战斗": "战斗", "打斗": "战斗", "激战": "战斗",
    "抒情": "抒情", "治愈": "治愈", "温馨": "治愈",
    "日常": "日常", "搞笑": "搞笑", "喜剧": "搞笑",
    "悬疑": "悬疑", "暗黑": "暗黑", "压抑": "暗黑",
    "史诗": "史诗", "宏大": "史诗", "唯美": "唯美",
    # 英文输出兜底 (实测 ToriiGate 倾向英文回复)
    "action": "燃向", "exciting": "燃向", "intense": "燃向",
    "energetic": "燃向", "upbeat": "燃向", "dynamic": "燃向",
    "battle": "战斗", "fight": "战斗", "combat": "战斗",
    "emotional": "抒情", "sentimental": "抒情", "touching": "抒情",
    "sad": "抒情", "melancholy": "抒情", "bittersweet": "抒情",
    "healing": "治愈", "warm": "治愈", "soothing": "治愈",
    "cheerful": "治愈", "joyful": "治愈", "peaceful": "治愈",
    "calm": "治愈", "cozy": "治愈",
    "daily": "日常", "slice of life": "日常", "school": "日常",
    "funny": "搞笑", "comedy": "搞笑", "humor": "搞笑",
    "suspense": "悬疑", "mystery": "悬疑", "mysterious": "悬疑", "tense": "悬疑",
    "dark": "暗黑", "gloomy": "暗黑", "depressing": "暗黑",
    "epic": "史诗", "grand": "史诗", "majestic": "史诗",
    "beautiful": "唯美", "aesthetic": "唯美", "romantic": "唯美",
    "romance": "唯美", "elegant": "唯美",
}

_PROMPT_TEMPLATE = """你是动漫视频分析专家。下面是同一段动漫视频中均匀抽取的 {n} 帧画面, 请综合判断这段视频的整体氛围与情绪。

要求: 只输出一行 JSON, 每个字段的值最多 6 个字, 不要输出任何解释或多余文字, 不要用 markdown 代码块。
示例: {{"atmosphere":"燃向","emotion":"热血","energy":9,"scene_type":"战斗","shot_scale":"中景","confidence":0.9}}

请严格按示例格式输出:
{{
  "atmosphere": "燃向|战斗|抒情|治愈|日常|搞笑|悬疑|暗黑|史诗|唯美 之一",
  "emotion": "主要情绪 (最多6字)",
  "energy": 只填一个1到10的整数,
  "scene_type": "场景类型 (如: 战斗/对话/日常/风景/演出)",
  "shot_scale": "主要景别 (如: 特写/近景/中景/远景)",
  "confidence": 0.0到1.0的置信度
}}"""


@dataclass
class AtmosphereResult:
    """视频氛围标注结果。"""
    atmosphere: str = ""          # 归一化氛围标签
    emotion: str = ""             # 主要情绪
    energy: int = 5               # 1-10
    scene_type: str = ""
    shot_scale: str = ""
    confidence: float = 0.0
    raw: str = ""                 # 模型原始输出 (追溯)
    latency_sec: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "atmosphere": self.atmosphere, "emotion": self.emotion,
            "energy": self.energy, "scene_type": self.scene_type,
            "shot_scale": self.shot_scale, "confidence": self.confidence,
            "latency_sec": self.latency_sec,
        }


def _sample_frames(video_path: str, n: int = MAX_FRAMES,
                   size: int = FRAME_SIZE) -> Optional[List[Any]]:
    """cv2 均匀采样 n 帧 → PIL Image 列表 (RGB)。"""
    import cv2
    import numpy as np
    from PIL import Image

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 1:
            return None
        if total <= n:
            idxs = list(range(total))
        else:
            step = (total - 1) / (n - 1)
            idxs = [round(i * step) for i in range(n)]
        frames = []
        for i in idxs:
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, frame = cap.read()
            if not ok:
                continue
            frame = cv2.resize(frame, (size, size))
            frames.append(Image.fromarray(
                np.ascontiguousarray(frame[..., ::-1])))  # BGR→RGB PIL
        return frames or None
    finally:
        cap.release()


_ENERGY_WORD_MAP = {
    "极高": 9, "很强": 9, "high": 8, "高": 8, "强": 7,
    "medium": 5, "中": 5, "中等": 5, "一般": 5, "low": 3, "低": 3, "静": 2,
}


def _parse_energy(val: Any) -> int:
    """把 VLM 输出的 energy 字段稳健解析为 1-10 整数。

    模型可能输出: 整数 / 数字字符串 / 带数字的句子 / 纯文字描述。
    实测 ToriiGate 曾输出整句描述 (含数字或高/低词汇), 不允许因此崩溃。
    """
    if isinstance(val, (int, float)):
        try:
            return max(1, min(10, int(val)))
        except (TypeError, ValueError):
            pass
    s = str(val or "").strip()
    m = re.search(r"\d+(\.\d+)?", s)
    if m:
        try:
            return max(1, min(10, int(float(m.group(0)))))
        except ValueError:
            pass
    low = s.lower()
    # 长词优先 (如 "很强" 优先于 "强", "中等" 优先于 "中")
    for word, score in sorted(
            _ENERGY_WORD_MAP.items(), key=lambda kv: -len(kv[0])):
        if word.lower() in low:
            return score
    return 5


def _normalize_atmosphere(raw: str) -> str:
    """把模型自由输出归一化到氛围词汇表 (关键词命中优先, 长词优先)。"""
    if not raw:
        return ""
    low = raw.lower()
    for key in sorted(ATMOSPHERE_VOCAB, key=lambda k: -len(k)):
        if key.lower() in low:
            return ATMOSPHERE_VOCAB[key]
    # 无命中: 短文本原样保留, 长散文截断
    return raw[:12] if len(raw) <= 12 else raw[:12]


def _parse_json_response(content: str) -> Optional[Dict[str, Any]]:
    """从 VLM 输出提取 JSON (容忍 markdown 包裹与前后杂文)。"""
    if not content:
        return None
    text = content.strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        text = m.group(1)
    else:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            text = m.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


class ToriiAtmosphereAnnotator:
    """ToriiGate-2B 动漫视频氛围标注器 (懒加载, 优雅降级)。"""

    def __init__(self, model_dir: str = DEFAULT_MODEL_DIR,
                 max_frames: int = MAX_FRAMES,
                 device: Optional[str] = None,
                 conf_threshold: float = 0.4) -> None:
        self.model_dir = model_dir
        self.max_frames = max_frames
        self._device = device
        self.conf_threshold = conf_threshold
        self._processor = None
        self._model = None
        self._load_error: Optional[str] = None
        self._n_infer = 0
        self._total_sec = 0.0

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
        if self._model is not None:
            return True
        if self._load_error:
            return False
        if not os.path.isdir(self.model_dir):
            self._load_error = f"model dir not found: {self.model_dir}"
            logger.warning("[ToriiGate] %s", self._load_error)
            return False
        try:
            import torch
            from transformers import (
                AutoProcessor,
                Qwen2VLForConditionalGeneration,
            )

            device = self._pick_device()
            dtype = torch.bfloat16 if device == "cuda" else torch.float32
            self._model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_dir,
                torch_dtype=dtype,
                low_cpu_mem_usage=True,
                device_map="auto" if device == "cuda" else "cpu",
            )
            self._model.eval()
            self._processor = AutoProcessor.from_pretrained(self.model_dir)
            logger.info("[ToriiGate] loaded %s device=%s dtype=%s",
                        Path(self.model_dir).name, device, dtype)
            return True
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)
            logger.warning("[ToriiGate] load failed: %s", exc)
            return False

    def available(self) -> bool:
        """模型目录存在且无已知加载错误 (不强制加载)。"""
        return os.path.isdir(self.model_dir) and self._load_error is None

    # ── 推理 ──────────────────────────────────────────────

    def _build_messages(self, frames) -> List[Dict[str, Any]]:
        content: List[Dict[str, Any]] = [
            {"type": "image", "image": img} for img in frames
        ]
        content.append({"type": "text",
                        "text": _PROMPT_TEMPLATE.format(n=len(frames))})
        return [{"role": "user", "content": content}]

    def annotate(self, video_path: str) -> Optional[AtmosphereResult]:
        """对单个视频做氛围标注。

        Returns:
            None — 模型不可用/视频不可读/解析失败/低置信度
            AtmosphereResult — 氛围标签 + 情绪 + 能量 + 场景 + 景别
        """
        if not self._ensure_loaded():
            return None
        frames = _sample_frames(video_path, self.max_frames)
        if not frames:
            return None
        try:
            import torch

            device = next(self._model.parameters()).device
            messages = self._build_messages(frames)
            text = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            inputs = self._processor(
                text=[text], images=frames, return_tensors="pt")
            inputs = {k: (v.to(device) if hasattr(v, "to") else v)
                      for k, v in inputs.items()}

            t0 = time.time()
            with infer_ctx(device):
                out_ids = self._model.generate(
                    **inputs, max_new_tokens=384, do_sample=False)
            elapsed = time.time() - t0
            self._n_infer += 1
            self._total_sec += elapsed

            generated = out_ids[:, inputs["input_ids"].shape[1]:]
            raw = self._processor.batch_decode(
                generated, skip_special_tokens=True)[0].strip()
            data = _parse_json_response(raw)
            if not data:
                # 小 VLM 常见失败: 散文式输出/JSON 断裂 → 带纠错提示重试一次
                logger.info("[ToriiGate] unparseable (attempt 1) for %s: %.80s",
                            Path(video_path).name, raw)
                raw = self._retry_generate(inputs, frames)
                data = _parse_json_response(raw) if raw else None
            if not data:
                logger.info("[ToriiGate] unparseable (attempt 2) for %s → None",
                            Path(video_path).name)
                return None
            conf = float(data.get("confidence", 0.5) or 0.5)
            if conf < self.conf_threshold:
                return None
            _atmo = _normalize_atmosphere(str(data.get("atmosphere", "")))
            # 质量门: 归一化后仍不在词汇表内 (散文未命中关键词) → 拒绝
            if _atmo and _atmo not in ATMOSPHERE_VOCAB.values():
                logger.info("[ToriiGate] atmosphere 未归一化 (%.40s) → None",
                            _atmo)
                return None
            return AtmosphereResult(
                atmosphere=_atmo,
                emotion=str(data.get("emotion", "")),
                energy=_parse_energy(data.get("energy")),
                scene_type=str(data.get("scene_type", "")),
                shot_scale=str(data.get("shot_scale", "")),
                confidence=round(conf, 4),
                raw=raw,
                latency_sec=round(elapsed, 2),
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ToriiGate] annotate failed %s: %s",
                           Path(video_path).name, exc)
            return None

    def _retry_generate(self, inputs, frames) -> Optional[str]:
        """解析失败后的纠错重试: 追问一次, 要求只输出合法 JSON。"""
        try:
            import torch

            device = next(self._model.parameters()).device
            correction = (
                "你上次的回答不是合法 JSON。现在只输出一个 JSON 对象, "
                "格式严格如下, 每个字段最多 6 个字, 不要任何解释:\n"
                '{"atmosphere":"燃向","emotion":"热血","energy":9,'
                '"scene_type":"战斗","shot_scale":"中景","confidence":0.9}')
            messages = self._build_messages(frames)
            messages.append({"role": "assistant", "content": "..."})
            messages.append({"role": "user", "content": correction})
            text = self._processor.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True)
            retry_inputs = self._processor(
                text=[text], images=frames, return_tensors="pt")
            retry_inputs = {k: (v.to(device) if hasattr(v, "to") else v)
                            for k, v in retry_inputs.items()}
            t0 = time.time()
            with infer_ctx(str(device)):
                out_ids = self._model.generate(
                    **retry_inputs, max_new_tokens=384, do_sample=False)
            self._n_infer += 1
            self._total_sec += time.time() - t0
            return self._processor.batch_decode(
                out_ids[:, retry_inputs["input_ids"].shape[1]:],
                skip_special_tokens=True)[0].strip()
        except Exception as exc:  # noqa: BLE001
            logger.warning("[ToriiGate] retry failed: %s", exc)
            return None

    def batch_annotate(self, video_paths) -> Dict[str, Optional[AtmosphereResult]]:
        return {p: self.annotate(p) for p in video_paths}

    def stats(self) -> Dict[str, Any]:
        return {
            "loaded": self._model is not None,
            "n_infer": self._n_infer,
            "avg_latency_sec": (
                round(self._total_sec / self._n_infer, 2)
                if self._n_infer else None),
            "model_dir": self.model_dir,
            "load_error": self._load_error,
        }


_SINGLETON: Optional[ToriiAtmosphereAnnotator] = None


def get_torii_annotator(**kwargs) -> ToriiAtmosphereAnnotator:
    """获取模块级单例 (参数仅在首次创建时生效)。"""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = ToriiAtmosphereAnnotator(**kwargs)
    return _SINGLETON
