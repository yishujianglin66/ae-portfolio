"""cnn_scorer.py — CNN 深度调参器评分头（本地实时评分）

冻结 open_clip ViT-L-14 编码渲染帧 → 768 维嵌入 → Ridge 线性头 → 7 维评分预测。
⚠ 2026-08-27 事故: 本文件曾被 "rebuilt baseline" 残废版覆盖
  (score_video_mode 恒返回空 scores + 'scorer unavailable'), 生产混合评分静默失效。
  本版从开发会话记录完整重建。LOOCV 权威数字见
  docs/research/2026-08-16-cnn-param-tuner-foundation.md。

三种评分模式:
  local  : 7 维全本地预测（秒级, 完全离线; 但 composition/color_harmony 等维仅 0.44-0.65,
           只适合快速初筛）
  hybrid : 置信维(local) + 其余(qwen) — 迭代闭环默认, 省 qwen 调用同时保住弱维精度
  qwen   : 纯 API（评分真值来源, 采集/训练数据必须用它）

混合维度归属 (黄金基准 20→50 条专家真值, cnn 标定后每维 MAE):
  cnn 管 5 维: dynamism / text_read / texture / pacing / overall (本地免费且更准)
  qwen 管 2 维: composition / color_harmony (视觉细节维 qwen 更准)

训练（全量, 非 LOOCV）:
  python -m core.cnn_scorer --train

推理:
  python -m core.cnn_scorer --video output/xxx.mp4 [--mode local|hybrid]
"""
from __future__ import annotations

import json
import pickle
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT))

from core.torch_runtime import get_device, infer_ctx  # noqa: E402
from core.visual_scorer import score_video  # noqa: E402

SAMPLES = PROJECT / "data" / "param_tuning" / "train_samples.jsonl"
EMB = PROJECT / "data" / "param_tuning" / "clip_vitl14_emb.npz"
HEAD = PROJECT / "models" / "output" / "cnn_param_head.pkl"
CKPT = (Path.home() / ".cache/huggingface/hub/models--timm--vit_large_patch14_clip_224.openai"
        / "snapshots" / "18d0535469bb561bf468d76c1d73aa35156c922b" / "open_clip_model.safetensors")
TARGETS = ["score_dynamism", "score_composition", "score_color_harmony",
           "score_text_read", "score_texture", "score_pacing", "score_overall"]
# 混合评分维度归属 (黄金基准 50 条专家真值, 2026-08-16 cnn 标定后每维 MAE)
CONFIDENT_DIMS = {"score_dynamism": 0.88, "score_text_read": 0.78,
                  "score_texture": 0.82, "score_pacing": 0.75, "score_overall": 0.82}
N_FRAMES = 4  # 与采集/编码一致

_clip_model = None
_clip_preprocess = None
_head = None


# ── CLIP 编码 ─────────────────────────────────────────────────────

def _load_clip():
    """lazy 加载冻结 CLIP（本地权重, 离线）"""
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        import open_clip
        import torch
        _clip_model, _, _clip_preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained=str(CKPT),
            device=get_device())
        _clip_model.eval()
    return _clip_model, _clip_preprocess


def encode_frames(frame_paths: list[str]) -> np.ndarray:
    """4 帧 → 768 维嵌入（L2 归一化帧均值, 与 encode_tuning_frames.py 完全一致）"""
    import torch
    model, preprocess = _load_clip()
    from PIL import Image
    tensors = [preprocess(Image.open(p).convert("RGB")) for p in frame_paths]
    with infer_ctx():
        feats = model.encode_image(torch.stack(tensors).to(next(model.parameters()).device))
        feats = feats / feats.norm(dim=-1, keepdim=True).clamp_min(1e-8)
    emb = feats.cpu().numpy().mean(axis=0)
    emb = emb / (np.linalg.norm(emb) + 1e-8)
    return emb


def encode_video(video_path: str, n_frames: int = N_FRAMES) -> np.ndarray | None:
    """视频均匀抽 n_frames 帧 → 编码（与 collect_tuning_data 抽帧一致）"""
    import cv2
    cap = cv2.VideoCapture(video_path)
    emb = None
    try:
        if not cap.isOpened():
            return None
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if total < 1:
            return None
        n = min(n_frames, total)
        idxs = [int(i * (total - 1) / max(n - 1, 1)) for i in range(n)] if n > 1 else [0]
        with tempfile.TemporaryDirectory() as td:
            fps = []
            for gi in idxs:
                cap.set(cv2.CAP_PROP_POS_FRAMES, gi)
                ret, f = cap.read()
                if not ret:
                    continue
                fp = Path(td) / f"f{gi:04d}.jpg"
                cv2.imwrite(str(fp), f, [cv2.IMWRITE_JPEG_QUALITY, 85])
                fps.append(str(fp))
            # 帧必须在临时目录存活期内编码
            emb = encode_frames(fps) if fps else None
    finally:
        cap.release()
    return emb


# ── Ridge 头 ──────────────────────────────────────────────────────

def train_head() -> Path:
    """全量训练 Ridge 多输出头（7 目标独立回归）并保存。"""
    from sklearn.linear_model import Ridge
    if not EMB.exists():
        raise FileNotFoundError(f"无嵌入 {EMB}（先跑 scripts/encode_tuning_frames.py）")
    rows = [json.loads(l) for l in SAMPLES.read_text(encoding="utf-8").splitlines() if l.strip()]
    z = np.load(EMB)
    emb, sidx = z["emb"], z["sample_idx"]
    y = np.zeros((len(emb), len(TARGETS)))
    for j, t in enumerate(TARGETS):
        y[:, j] = [float(rows[i][t]) for i in sidx]
    head = Ridge(alpha=1.0)
    head.fit(emb, y)
    HEAD.parent.mkdir(parents=True, exist_ok=True)
    with open(HEAD, "wb") as f:
        pickle.dump({"model": head, "targets": TARGETS, "confident": CONFIDENT_DIMS,
                     "n": len(emb), "train_samples": str(SAMPLES)}, f)
    print(f"CNN 评分头已保存: {HEAD} | {len(emb)} 样本, 7 目标")
    return HEAD


def load_head():
    """lazy 加载 Ridge 头"""
    global _head
    if _head is None:
        if not HEAD.exists():
            raise FileNotFoundError(f"评分头不存在 {HEAD}（先 python -m core.cnn_scorer --train）")
        with open(HEAD, "rb") as f:
            _head = pickle.load(f)
    return _head


def _pred_to_scores(emb: np.ndarray) -> dict[str, float]:
    head = load_head()
    pred = head["model"].predict(emb.reshape(1, -1))[0]
    scores = {}
    cal = head.get("calibration")
    for t, v in zip(head["targets"], pred):
        if cal and t in cal:  # 黄金标定: gold ≈ slope*cnn + intercept (0-10 裁剪)
            c = cal[t]
            v = c["slope"] * float(v) + c["intercept"]
        scores[t] = round(float(v), 2)
    return scores


# ── 评分入口 ──────────────────────────────────────────────────────

def local_score(video_path: str) -> dict:
    """完全本地评分（7 维, 秒级, 无 API 依赖）。"""
    emb = encode_video(video_path)
    if emb is None:
        return {"error": "视频无法编码"}
    scores = _pred_to_scores(emb)
    return {"scores": scores, "overall": scores["score_overall"],
            "source": "cnn", "confident": list(CONFIDENT_DIMS)}


def hybrid_score(video_path: str) -> dict:
    """置信维本地 + 其余 qwen（迭代闭环默认）。每维标注来源。"""
    scores = {}
    source = {}
    emb = encode_video(video_path)
    local = None
    if emb is not None:
        local = _pred_to_scores(emb)
        for t in CONFIDENT_DIMS:
            scores[t] = local[t]
            source[t] = "cnn"
    # 弱维走 qwen 真值
    try:
        q = score_video(video_path, n_frames=N_FRAMES)
    except Exception as e:  # noqa: BLE001
        q = {"error": str(e)}
    if q.get("error"):
        # qwen 挂了 → 弱维也用本地预测兜底（宁可偏差不可阻塞闭环）
        if local is not None:
            for t in TARGETS:
                if t not in scores:
                    scores[t] = local[t]
                    source[t] = "cnn_fallback"
        return {"scores": scores, "overall": scores.get("score_overall", 0),
                "source": source, "error": q["error"]}
    qs = q.get("scores", {})
    for t in TARGETS:  # "score_dynamism"; qwen 返回的是无前缀键 "dynamism"
        if t not in scores:
            bare = t[len("score_"):]
            scores[t] = qs.get(bare, qs.get(t, 0))
            source[t] = "qwen"
    result = dict(q)
    result["scores"] = scores
    result["overall"] = scores.get("score_overall", q.get("overall", 0))
    result["source"] = source
    return result


def unload_clip():
    """释放懒加载的 CLIP ViT-L 与缓存显存 (评分后经验采集等步骤仍需 GPU)。"""
    global _clip_model, _clip_preprocess
    if _clip_model is None:
        return
    _clip_model = None
    _clip_preprocess = None
    try:
        import gc

        import torch
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def score_video_mode(video_path: str, mode: str = "hybrid") -> dict:
    """按模式分派评分（迭代闭环入口）。评分完即释放 CLIP 显存 —
    阶段⑤后还有经验采集等 GPU 步骤, ViT-L 常驻会挤爆 8GB 卡 (OOM 修复)。"""
    try:
        if mode == "qwen":
            return score_video(video_path, n_frames=N_FRAMES)
        if mode == "local":
            return local_score(video_path)
        return hybrid_score(video_path)
    finally:
        unload_clip()


def main() -> int:
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--train", action="store_true", help="全量训练并保存评分头")
    ap.add_argument("--video", default="")
    ap.add_argument("--mode", default="hybrid", choices=["local", "hybrid", "qwen"])
    args = ap.parse_args()
    if args.train:
        train_head()
    if args.video:
        r = score_video_mode(args.video, args.mode)
        print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
