# -*- coding: utf-8 -*-
"""T5/T6: BackboneRegistry — CLIP双底座统一接口与集成仲裁。

底座:
  laion   — CLIP-ViT-B-32-laion2B (open_clip, 英文文本空间)
  cclip   — chinese-clip-vit-base-patch16 (transformers, 中文文本空间, 救国产IP)
统一接口: encode_images(paths)->np[N,D], encode_texts(texts)->np[M,D] (各自L2归一化)
集成: 帧级分数加权融合, 权重在黄金集上网格搜索(T6)。
懒加载: 首次使用才载入显存; 缓存键含底座标签, 与ip_proto_classifier缓存目录共用。
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import numpy as np
import torch

from core.torch_runtime import get_device, infer_ctx

ROOT = Path(__file__).resolve().parent.parent
CCLIP_DIR = Path(r"D:\ms_cache\models\AI-ModelScope--chinese-clip-vit-base-patch16\snapshots\master")
BGE_M3_DIR = Path(r"D:\ms_cache\models\BAAI--bge-m3\snapshots\master")
DEVICE = get_device()

# 底座标签映射(缓存键 + 底座切换)
BB_TAGS = {"laion": "laion-vitb32", "laion-l": "laion-vitl14", "cclip": "cclip-vitb16"}

# 中文文本提示(chinese-clip原生中文空间, 无需英文别名)
CN_PROMPTS = (
    "动画片《{}》的画面截图",
    "《{}》动漫中的一幕",
    "{}动画角色",
)
EN_PROMPTS = (
    "a screenshot from the anime {}",
    "a scene from {} anime series",
    "{} anime character",
)


class _LaionBackbone:
    tag = "laion-vitb32"
    dim = 512

    def __init__(self):
        import open_clip
        ckpt = ROOT / "models" / "ms_cache" / "models" / \
            "laion--CLIP-ViT-B-32-laion2B-s34B-b79K" / "snapshots" / "master" / \
            "open_clip_pytorch_model.bin"
        self.model, _, self.pre = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained=str(ckpt))
        self.tok = open_clip.get_tokenizer("ViT-B-32")
        self.model.eval().to(DEVICE)

    def encode_images(self, paths: List[Path]) -> np.ndarray:
        from PIL import Image
        outs = []
        for i in range(0, len(paths), 64):
            ts = []
            for p in paths[i:i + 64]:
                try:
                    ts.append(self.pre(Image.open(p).convert("RGB")))
                except Exception:
                    ts.append(self.pre(Image.new("RGB", (224, 224))))
            x = torch.stack(ts).to(DEVICE)
            with infer_ctx(DEVICE):
                v = self.model.encode_image(x)
            outs.append((v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9))
                        .float().cpu().numpy())
        return np.concatenate(outs, 0)

    def encode_texts(self, texts: List[str]) -> np.ndarray:
        t = self.tok(texts).to(DEVICE)
        with infer_ctx(DEVICE):
            v = self.model.encode_text(t)
        return (v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9)).float().cpu().numpy()

    def class_texts(self, name_en: str) -> List[str]:
        return [p.format(name_en) for p in EN_PROMPTS]


class _CnClipBackbone:
    tag = "cclip-vitb16"
    dim = 512

    def __init__(self):
        from transformers import ChineseCLIPModel, ChineseCLIPProcessor
        d = CCLIP_DIR if CCLIP_DIR.exists() else "AI-ModelScope/chinese-clip-vit-base-patch16"
        self.model = ChineseCLIPModel.from_pretrained(d).eval().to(DEVICE)
        self.proc = ChineseCLIPProcessor.from_pretrained(d)

    @staticmethod
    def _as_tensor(v):
        if isinstance(v, torch.Tensor):
            return v
        for attr in ("text_embeds", "image_embeds", "pooler_output", "last_hidden_state"):
            t = getattr(v, attr, None)
            if isinstance(t, torch.Tensor):
                return t[:, 0] if attr == "last_hidden_state" and t.dim() == 3 else t
        raise TypeError(f"无法解析模型输出: {type(v)}")

    def encode_images(self, paths: List[Path]) -> np.ndarray:
        from PIL import Image
        outs = []
        for i in range(0, len(paths), 32):
            imgs = []
            for p in paths[i:i + 32]:
                try:
                    imgs.append(Image.open(p).convert("RGB"))
                except Exception:
                    imgs.append(Image.new("RGB", (224, 224)))
            inputs = self.proc(images=imgs, return_tensors="pt").to(DEVICE)
            with infer_ctx(DEVICE):
                v = self._as_tensor(self.model.get_image_features(**inputs))
            outs.append((v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9))
                        .float().cpu().numpy())
        return np.concatenate(outs, 0)

    def encode_texts(self, texts: List[str]) -> np.ndarray:
        outs = []
        for i in range(0, len(texts), 64):
            inputs = self.proc(text=texts[i:i + 64], return_tensors="pt",
                               padding=True, truncation=True).to(DEVICE)
            with infer_ctx(DEVICE):
                v = self._as_tensor(self.model.get_text_features(**inputs))
            outs.append((v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9))
                        .float().cpu().numpy())
        return np.concatenate(outs, 0)

    def class_texts(self, name_cn: str) -> List[str]:
        return [p.format(name_cn) for p in CN_PROMPTS]


class _LaionLargeBackbone:
    """CLIP ViT-L-14 (openai底座, 768维, 更强细粒度区分力)"""
    tag = "laion-vitl14"
    dim = 768

    def __init__(self):
        import open_clip
        self.model, _, self.pre = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained="openai")
        self.tok = open_clip.get_tokenizer("ViT-L-14")
        self.model.eval().to(DEVICE)

    def encode_images(self, paths: List[Path]) -> np.ndarray:
        from PIL import Image
        outs = []
        for i in range(0, len(paths), 32):
            ts = []
            for p in paths[i:i + 32]:
                try:
                    ts.append(self.pre(Image.open(p).convert("RGB")))
                except Exception:
                    ts.append(self.pre(Image.new("RGB", (224, 224))))
            x = torch.stack(ts).to(DEVICE)
            with infer_ctx(DEVICE):
                v = self.model.encode_image(x)
            outs.append((v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9))
                        .float().cpu().numpy())
        return np.concatenate(outs, 0)

    def encode_texts(self, texts: List[str]) -> np.ndarray:
        t = self.tok(texts).to(DEVICE)
        with infer_ctx(DEVICE):
            v = self.model.encode_text(t)
        return (v / v.norm(dim=-1, keepdim=True).clamp_min(1e-9)).float().cpu().numpy()

    def class_texts(self, name_en: str) -> List[str]:
        return [p.format(name_en) for p in EN_PROMPTS]


class BackboneRegistry:
    """懒加载多底座注册表 (laion / laion-l / cclip)"""

    _BUILDERS = None

    def __init__(self):
        self._inst: Dict[str, object] = {}

    def get(self, name: str):
        if name not in self._inst:
            if BackboneRegistry._BUILDERS is None:
                BackboneRegistry._BUILDERS = {
                    "laion": _LaionBackbone,
                    "laion-l": _LaionLargeBackbone,
                    "cclip": _CnClipBackbone,
                }
            cls = BackboneRegistry._BUILDERS.get(name)
            if cls is None:
                raise ValueError(f"Unknown backbone: {name}. Available: {list(BackboneRegistry._BUILDERS)}")
            self._inst[name] = cls()
        return self._inst[name]

    def class_protos(self, name: str, ip: str, aliases: Dict[str, str]) -> np.ndarray:
        """类文本原型: laion用英文别名, cclip用中文名(中文空间原生优势)"""
        bb = self.get(name)
        if name == "cclip":
            texts = bb.class_texts(ip)
        else:
            texts = bb.class_texts(aliases.get(ip, ip))
        v = bb.encode_texts(texts)
        return v.mean(0)


def ensemble_frame_scores(scores_by_bb: Dict[str, Dict[str, float]],
                          weights: Dict[str, float]) -> List[tuple]:
    """T6: 帧级多底座分数加权融合 → [(ip, fused)] 降序"""
    fused: Dict[str, float] = {}
    wsum = sum(weights.values())
    for bb, scores in scores_by_bb.items():
        w = weights.get(bb, 0.0) / wsum
        for ip, s in scores.items():
            fused[ip] = fused.get(ip, 0.0) + w * s
    return sorted(fused.items(), key=lambda kv: -kv[1])


if __name__ == "__main__":
    # 自检: 两底座编码冒烟
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    reg = BackboneRegistry()
    for name in ("laion", "laion-l", "cclip"):
        bb = reg.get(name)
        v = bb.encode_texts(["a test image", "测试文本"] if name != "cclip"
                            else ["测试文本", "动画截图"])
        print(f"[backbone] {name} dim={v.shape[1]} norm={np.linalg.norm(v[0]):.3f} OK")
