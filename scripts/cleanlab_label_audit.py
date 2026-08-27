#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cleanlab_label_audit.py — 动漫运镜分类标签清洗 (Confident Learning + Datalab)

清洗 24k VLM 自动标注的 6 类运镜标签 (Qwen3-VL-30B 单标注器, 估计噪声率 30-50%)。

背景:
  - 标注器: Qwen3-VL-30B (SiliconFlow 免费 API), 单标注器无人工复核
  - 噪声来源: ShotBench (arXiv:2506.21356) 实证 VLM 动态运镜准确率 <40%
  - v4 训练在 val_acc=0.6047 饱和, 疑似标签噪声上限

清洗链路 (四步, 严格遵循证据闸门):
  Step 0  存在性闸门        打印真实标签分布 + 首行完整字段 + 各类样本数
                              (证据闸门 1/2: 落盘前先看真实数据, 禁止凭文件名推测)
  Step 1  Confident Learning StratifiedKFold(10) OOF 预测
                              检测器 = CLIP-ViT-B32 + LogisticRegression
                              (与 Qwen3-VL 标注器异构, 禁止复用 VLM confidence)
                              find_label_issues(return_indices_ranked_by='self_confidence')
  Step 2  Datalab 全数据体检 outliers / near-duplicates / IID 违反 / 低质图像
                              lab.find_issues(features=embeddings, pred_probs=pred_probs)
  Step 3  输出清洗后标签    clean_labels.jsonl (丢弃 top drop_ratio 可疑样本)
                              label_issues_report.json + datalab_report.json

用法:
  # 冒烟 (200 样本, 验证管线)
  py -3.12 scripts/cleanlab_label_audit.py --limit 200
  # 全量清洗 (丢弃最可疑 10%)
  py -3.12 scripts/cleanlab_label_audit.py
  # 自定义参数
  py -3.12 scripts/cleanlab_label_audit.py \\
      --labels D:\\AE-Data\\AnimeCamera\\vlm_labels.jsonl \\
      --out D:\\AE-Data\\AnimeCamera\\cleaned \\
      --drop-ratio 0.15 --clip-model ViT-B/32 --limit 0

依赖: cleanlab, scikit-learn, torch, transformers, PIL, numpy
参考: https://docs.cleanlab.ai/stable/index.html
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import contextlib
import re
import subprocess
import sys
import tempfile
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ─── 六类运镜 (与 train_anime_camera_v5.py SIX_LABELS / SIX_MAP 一致) ───
# v3 是 v1+v2+本地新标合并, 可能含细粒度方向, 需折叠到 6 类规范标签
SIX_MAP: Dict[str, Optional[str]] = {
    "static": "static",
    "pan_left": "pan_left", "pan_right": "pan_right",
    "tilt_up": "tilt_orbit", "tilt_down": "tilt_orbit", "orbit": "tilt_orbit",
    "zoom_in": "push_in", "push": "push_in",
    "zoom_out": "pull_out", "zoom_back": "pull_out",
    "complex": None,  # 复合运动, 不参与清洗
}
SIX_LABELS: List[str] = ["static", "pan_left", "pan_right", "tilt_orbit", "push_in", "pull_out"]
LABEL_TO_IDX: Dict[str, int] = {l: i for i, l in enumerate(SIX_LABELS)}

# ─── 抽帧配置 ───
FRAMES_PER_CLIP = 3            # 每镜头抽 3 帧 (25/50/75%), CLIP 嵌入取均值 → 1 条/镜头
FFMPEG = "ffmpeg"
# Windows 隐藏黑窗; Linux 无此属性用 0
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# ─── CLIP 模型名映射 (openai/clip-vit-base-patch32 对应 ViT-B/32) ───
CLIP_MODEL_MAP: Dict[str, str] = {
    "ViT-B/32": "openai/clip-vit-base-patch32",
    "ViT-B/16": "openai/clip-vit-base-patch16",
    "ViT-L/14": "openai/clip-vit-large-patch14",
}


def setup_logging() -> logging.Logger:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    return logging.getLogger("cleanlab_audit")


# ═══════════════════════════════════════════════════════════════════════
# Step 0: 存在性闸门 (证据闸门 1 + 2)
# ═══════════════════════════════════════════════════════════════════════
def load_labels(path: Path, limit: int, logger: logging.Logger) -> List[Dict[str, Any]]:
    """读取 jsonl 标签文件。支持单文件; 空/坏行跳过。"""
    if not path.exists():
        logger.error("标签文件不存在: %s", path)
        logger.error("请先生成 v3 合并标签, 或通过 --labels 指定其他路径。")
        sys.exit(2)
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    if limit > 0:
        rows = rows[:limit]
        logger.info("启用 --limit=%d 截断 (冒烟模式)", limit)
    logger.info("标签文件加载: %s -> %d 行", path, len(rows))
    return rows


def step0_existence_gate(rows: List[Dict[str, Any]], logger: logging.Logger) -> None:
    """证据闸门 1 (存在性) + 闸门 2 (首行证据): 打印真实标签分布与首行字段。"""
    n = len(rows)
    print("\n" + "=" * 70)
    print(f"[Step 0] 存在性闸门 — 真实标签分布 (n={n})")
    print("=" * 70)

    if n == 0:
        print("!! 标签文件为空, 无法继续。")
        sys.exit(2)

    # 闸门 2: 首行完整字段
    first = rows[0]
    print("\n[闸门 2] 首行完整字段:")
    for k, v in first.items():
        # 截断超长字段 (如 base64 帧), 避免刷屏
        sv = str(v)
        if len(sv) > 120:
            sv = sv[:120] + f"...(len={len(sv)})"
        print(f"  {k}: {sv}")

    # 原始 movement_label 分布 (未折叠, 看标注器实际输出)
    raw = Counter(r.get("movement_label", "<MISSING>") for r in rows)
    print("\n[原始 movement_label 分布] (折叠前, 真实标注器输出):")
    for k, c in sorted(raw.items(), key=lambda kv: -kv[1]):
        print(f"  {k:<14s} {c:>6d}  ({100 * c / n:5.1f}%)")

    # 折叠到 6 类后的分布
    folded: List[Optional[str]] = []
    for r in rows:
        folded.append(SIX_MAP.get(r.get("movement_label", ""), "__UNKNOWN__"))
    folded_counter = Counter(folded)
    print("\n[折叠后 6 类分布] (SIX_MAP 映射后):")
    for lab in SIX_LABELS + [None, "__UNKNOWN__"]:
        if lab in folded_counter:
            c = folded_counter[lab]
            tag = " (complex, 跳过)" if lab is None else (" (无法识别, 跳过)" if lab == "__UNKNOWN__" else "")
            print(f"  {str(lab):<14s} {c:>6d}  ({100 * c / n:5.1f}%){tag}")

    # confidence 统计
    confs = [float(r.get("confidence", 0.0)) for r in rows if "confidence" in r]
    if confs:
        confs_sorted = sorted(confs)
        print("\n[VLM confidence 统计] (注意: 本脚本不复用此值做检测, 仅诊断)")
        print(f"  min={confs_sorted[0]:.3f}  p25={confs_sorted[len(confs_sorted) // 4]:.3f}"
              f"  med={confs_sorted[len(confs_sorted) // 2]:.3f}"
              f"  p75={confs_sorted[3 * len(confs_sorted) // 4]:.3f}"
              f"  max={confs_sorted[-1]:.3f}")

    # clip_path 存在性抽检 (闸门 1: 落盘前看文件系统, 不是看 jsonl 字段)
    clip_paths = [r.get("clip_path", "") for r in rows]
    existing = sum(1 for cp in clip_paths if cp and Path(cp).exists())
    print(f"\n[闸门 1] clip_path 文件系统存在性: {existing}/{n} "
          f"({100 * existing / n:.1f}% 可读)")
    print("=" * 70 + "\n")


# ═══════════════════════════════════════════════════════════════════════
# 特征抽取: CLIP-ViT-B32 图像嵌入
# ═══════════════════════════════════════════════════════════════════════
def _probe_duration(clip_path: str) -> float:
    """ffmpeg 探测时长 (秒); 失败回退 2.0s。"""
    r = subprocess.run([FFMPEG, "-i", clip_path], capture_output=True,
                       creationflags=_NO_WINDOW)
    for line in r.stderr.decode("utf-8", errors="replace").splitlines():
        if "Duration" in line:
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", line)
            if m:
                return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    return 2.0


def extract_frames(clip_path: str, n_frames: int = FRAMES_PER_CLIP,
                   short_side: int = 336) -> List[bytes]:
    """抽 n 帧 JPEG (均匀采样时长, 含头不含尾 0..0.98), 返回字节列表。

    short_side=336 匹配 CLIP 默认输入, 减少后处理 resize 开销。
    """
    if not Path(clip_path).exists():
        return []
    dur = _probe_duration(clip_path)
    if dur <= 0:
        dur = 2.0
    ts = [dur * min(0.98, i / max(1, n_frames - 1)) for i in range(n_frames)]
    frames: List[bytes] = []
    tmp = Path(tempfile.mkdtemp(prefix="cla_frame_"))
    try:
        for i, t in enumerate(ts):
            out = tmp / f"f{i}.jpg"
            subprocess.run(
                [FFMPEG, "-y", "-ss", f"{t:.3f}", "-i", clip_path,
                 "-frames:v", "1", "-vf", f"scale=-2:{short_side}", "-q:v", "3",
                 str(out)],
                capture_output=True, creationflags=_NO_WINDOW,
            )
            if out.exists() and out.stat().st_size > 0:
                frames.append(out.read_bytes())
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return frames


def load_clip_model(model_alias: str, logger: logging.Logger) -> Tuple[Any, Any, str]:
    """加载 CLIP 模型与处理器 (transformers)。返回 (model, processor, device)。"""
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor
    except ImportError as exc:
        logger.error("缺少依赖 torch/transformers: %s", exc)
        logger.error("安装: py -3.12 -m pip install torch transformers")
        sys.exit(3)
    hf_name = CLIP_MODEL_MAP.get(model_alias, "openai/clip-vit-base-patch32")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info("加载 CLIP 模型 %s -> %s (device=%s)", model_alias, hf_name, device)
    model = CLIPModel.from_pretrained(hf_name).to(device)
    model.eval()
    processor = CLIPProcessor.from_pretrained(hf_name)
    return model, processor, device


def _compute_oklab_stats(img: "Image.Image") -> "np.ndarray":
    """对单张 PIL RGB 图像计算 OKLAB 简化色彩统计 (6 维: L/a/b 各 mean+std)。

    OKLAB 近似公式 (无需矩阵乘法, 纯线性组合):
      L = (0.25*R + 0.50*G + 0.25*B) / 255.0          -> [0, 1]
      a = (R - G) / 255.0                              -> [-1, 1]
      b = (B - (R + G) / 2.0) / 255.0                  -> [-1, 1]
    """
    import numpy as np

    arr = np.asarray(img.convert("RGB"), dtype=np.float32)  # (H, W, 3)
    R = arr[..., 0]
    G = arr[..., 1]
    B = arr[..., 2]
    L = (0.25 * R + 0.50 * G + 0.25 * B) / 255.0
    a_ch = (R - G) / 255.0
    b_ch = (B - (R + G) / 2.0) / 255.0
    return np.array([
        L.mean(), L.std(),
        a_ch.mean(), a_ch.std(),
        b_ch.mean(), b_ch.std(),
    ], dtype=np.float32)


def compute_clip_embeddings(
    rows: List[Dict[str, Any]],
    model_alias: str,
    logger: logging.Logger,
    batch_size: int = 32,
) -> "np.ndarray":
    """对每个镜头抽 FRAMES_PER_CLIP 帧 → CLIP 图像嵌入取均值 + OKLAB 色彩统计 → (N, 518) 特征矩阵。"""
    import numpy as np
    from PIL import Image
    import torch

    model, processor, device = load_clip_model(model_alias, logger)
    clip_dim = model.config.projection_dim
    oklab_dim = 6
    feat_dim = clip_dim + oklab_dim
    feats: List["np.ndarray"] = []
    n = len(rows)
    t0 = __import__("time").time()
    skipped = 0
    for i, r in enumerate(rows):
        clip_path = r.get("clip_path", "")
        frames = extract_frames(clip_path) if clip_path else []
        if not frames:
            feats.append(np.zeros(feat_dim, dtype=np.float32))
            skipped += 1
            continue
        imgs = [Image.open(io.BytesIO(b)).convert("RGB") for b in frames]
        with torch.no_grad():
            inputs = processor(images=imgs, return_tensors="pt").to(device)
            out = model.get_image_features(**inputs)
            # 兼容不同 transformers 版本: get_image_features 可能返回 Tensor 或 BaseModelOutput 对象
            if isinstance(out, torch.Tensor):
                img_embs = out
            elif hasattr(out, "image_embeds"):
                img_embs = out.image_embeds
            elif hasattr(out, "last_hidden_state"):
                img_embs = out.last_hidden_state[:, 0, :]
            else:
                # 兜底: 当 dict/list, 取第一个 tensor
                img_embs = out[0] if isinstance(out, (tuple, list)) else torch.zeros(len(imgs), clip_dim, device=device)
            clip_feat = img_embs.mean(dim=0).float().cpu().numpy()
        oklab_per_frame = np.stack([_compute_oklab_stats(im) for im in imgs], axis=0)
        oklab_feat = oklab_per_frame.mean(axis=0)
        feat = np.concatenate([clip_feat, oklab_feat], axis=0)
        norm = np.linalg.norm(feat)
        if norm > 0:
            feat = feat / norm
        feats.append(feat)
        if (i + 1) % 100 == 0 or (i + 1) == n:
            logger.info("  CLIP+OKLAB 嵌入: %d/%d (%.0fs, skip=%d)",
                        i + 1, n, __import__("time").time() - t0, skipped)
    logger.info("CLIP+OKLAB 嵌入完成: %d 条, 维度=%d (CLIP %d + OKLAB %d), 抽帧失败占位=%d",
                len(feats), feats[0].shape[0] if feats else 0, clip_dim, oklab_dim, skipped)
    return np.stack(feats, axis=0) if feats else np.zeros((0, feat_dim), dtype=np.float32)


# ═══════════════════════════════════════════════════════════════════════
# Step 1: Confident Learning — 异构检测器 OOF 预测 + 标签问题发现
# ═══════════════════════════════════════════════════════════════════════
def compute_oof_pred_probs(
    features: "np.ndarray",
    label_idx: List[int],
    n_splits: int,
    logger: logging.Logger,
) -> "np.ndarray":
    """StratifiedKFold(n_splits) OOF 预测概率。

    检测器 = LogisticRegression (在 CLIP 图像特征上), 与 Qwen3-VL 标注器异构:
      - Qwen3-VL: 多模态 VLM, 看视频帧 + 文本 prompt 生成方向
      - 本检测器: CLIP (图文对比预训练) 图像嵌入 + 线性分类头
    二者训练目标与架构均不同, 满足 Confident Learning 对"独立噪声"的假设。
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler

    n = len(label_idx)
    y = np.array(label_idx, dtype=int)
    n_classes = len(SIX_LABELS)
    pred_probs = np.zeros((n, n_classes), dtype=np.float32)

    # 类别太少无法分层时自动降折
    min_class = Counter(y.tolist()).most_common()[-1][1]
    effective_splits = n_splits if min_class >= n_splits else max(2, min_class)
    if effective_splits != n_splits:
        logger.warning("最小类样本数=%d < n_splits=%d, 降为 %d 折",
                       min_class, n_splits, effective_splits)

    skf = StratifiedKFold(n_splits=effective_splits, shuffle=True, random_state=42)
    for fold, (tr, te) in enumerate(skf.split(features, y)):
        scaler = StandardScaler()
        Xtr = scaler.fit_transform(features[tr])
        Xte = scaler.transform(features[te])
        try:
            # sklearn <1.5 旧签名 (带 multi_class)
            clf = LogisticRegression(
                max_iter=2000, C=1.0, class_weight="balanced",
                solver="lbfgs", multi_class="multinomial",
            )
        except TypeError:
            # sklearn >=1.5: multi_class 参数已移除, 默认自动 multomial 处理多类
            clf = LogisticRegression(
                max_iter=2000, C=1.0, class_weight="balanced",
                solver="lbfgs",
            )
        clf.fit(Xtr, y[tr])
        proba = clf.predict_proba(Xte)  # (n_te, n_classes)
        # 列对齐 (sklearn 可能省略无样本类)
        for j, cls in enumerate(clf.classes_):
            pred_probs[te, cls] = proba[:, j]
        logger.info("  OOF fold %d/%d: train=%d test=%d", fold + 1, effective_splits,
                    len(tr), len(te))

    # 行归一化 (防数值漂移)
    row_sum = pred_probs.sum(axis=1, keepdims=True)
    row_sum[row_sum == 0] = 1.0
    pred_probs = pred_probs / row_sum
    return pred_probs


def step1_confident_learning(
    rows: List[Dict[str, Any]],
    labels: List[str],
    pred_probs: "np.ndarray",
    logger: logging.Logger,
) -> Dict[str, Any]:
    """Confident Learning 第一轮: find_label_issues + get_label_quality_scores。"""
    import numpy as np
    from cleanlab.filter import find_label_issues
    from cleanlab.rank import get_label_quality_scores

    label_idx = [LABEL_TO_IDX[l] for l in labels]
    y = np.array(label_idx, dtype=int)

    # 1. 布尔 mask (默认 return_indices_ranked_by=None 返回 mask)
    issue_mask = find_label_issues(y, pred_probs)
    # 2. 按 self_confidence 升序的可疑索引 (最低 self_confidence 最可疑, 排前)
    issue_indices_ranked = find_label_issues(
        y, pred_probs, return_indices_ranked_by="self_confidence"
    )
    # 3. 每样本标签质量分
    quality_scores = get_label_quality_scores(y, pred_probs)
    # 4. 每样本 self_confidence (该样本被给标签的概率)
    self_conf = pred_probs[np.arange(len(y)), y]

    # 5. 估计联合分布 P(given, true) — 诊断系统性混淆
    joint = None
    try:
        from cleanlab.count import estimate_joint
        joint = estimate_joint(y, pred_probs).tolist()
    except Exception as exc:  # noqa: BLE001
        logger.warning("estimate_joint 失败: %s", exc)

    n_issue = int(issue_mask.sum())
    logger.info("[Step 1] Confident Learning 检出标签问题: %d/%d (%.1f%%)",
                n_issue, len(y), 100 * n_issue / max(1, len(y)))

    # 构建每样本详情 (rank: 0=最可疑)
    rank_of = {int(idx): r for r, idx in enumerate(issue_indices_ranked)}
    per_sample: List[Dict[str, Any]] = []
    for i, r in enumerate(rows):
        given = labels[i]
        pred_cls = int(pred_probs[i].argmax())
        per_sample.append({
            "shot_id": r.get("shot_id"),
            "clip_path": r.get("clip_path"),
            "anime": r.get("anime"),
            "given_label": given,
            "predicted_label": SIX_LABELS[pred_cls],
            "vlm_confidence": r.get("confidence"),
            "cleanlab_self_confidence": float(self_conf[i]),
            "cleanlab_quality_score": float(quality_scores[i]),
            "is_label_issue": bool(issue_mask[i]),
            "issue_rank": int(rank_of.get(i, -1)),
        })

    return {
        "per_sample": per_sample,
        "issue_indices_ranked": [int(i) for i in issue_indices_ranked],
        "n_issues": n_issue,
        "n_total": len(y),
        "issue_rate": n_issue / max(1, len(y)),
        "joint_distribution": joint,
        "joint_labels_given": SIX_LABELS,
        "joint_labels_true": SIX_LABELS,
    }


# ═══════════════════════════════════════════════════════════════════════
# Step 2: Datalab 全数据体检
# ═══════════════════════════════════════════════════════════════════════
def step2_datalab(
    rows: List[Dict[str, Any]],
    features: "np.ndarray",
    labels: List[str],
    pred_probs: "np.ndarray",
    logger: logging.Logger,
) -> Dict[str, Any]:
    """Datalab 全数据体检: outliers / near-duplicates / IID 违反 / 低质图像。"""
    import numpy as np
    from cleanlab import Datalab

    # Datalab 期望 label 列名 + 数据 dict; 额外带元信息便于追溯
    data = {
        "label": labels,
        "shot_id": [r.get("shot_id", "") for r in rows],
        "anime": [r.get("anime", "") for r in rows],
    }
    lab = Datalab(data=data, label_name="label")

    # 同时喂特征 (outlier / near_duplicate / non_iid) 与 OOF 概率 (label)
    lab.find_issues(features=features, pred_probs=pred_probs)

    # 1. 捕获 report() 文本输出
    report_buf = io.StringIO()
    with contextlib.redirect_stdout(report_buf):
        lab.report()
    report_text = report_buf.getvalue()
    print("\n" + "=" * 70)
    print("[Step 2] Datalab report (文本)")
    print("=" * 70)
    print(report_text)

    # 2. 汇总 issue_summary (DataFrame -> list of dict)
    summary: List[Dict[str, Any]] = []
    try:
        summary = lab.issue_summary.to_dict(orient="records")
    except Exception as exc:  # noqa: BLE001
        logger.warning("issue_summary 序列化失败: %s", exc)

    # 3. 逐 issue 类型抽取 get_issues() 明细
    issues_by_type: Dict[str, Any] = {}
    try:
        for issue_type in lab.list_possible_issue_types():
            try:
                df = lab.get_issues(issue_type=issue_type)
                issues_by_type[issue_type] = df.to_dict(orient="records")
            except Exception:  # noqa: BLE001
                # 未启用该 detector 静默跳过
                continue
    except Exception as exc:  # noqa: BLE001
        logger.warning("get_issues 枚举失败: %s", exc)

    # 兜底: 直接 lab.get_issues() (无参数) 返回全量 dict
    if not issues_by_type:
        try:
            all_issues = lab.get_issues()
            if hasattr(all_issues, "items"):
                for k, df in all_issues.items():
                    issues_by_type[k] = df.to_dict(orient="records")
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_issues() 兜底失败: %s", exc)

    n_issue_total = int(sum(1 for r in summary if r.get("num_issues")))
    logger.info("[Step 2] Datalab 扫描完成: %d 类 issue, 累计 %d 样本命中",
                len(summary), n_issue_total)

    return {
        "report_text": report_text,
        "issue_summary": summary,
        "issues_by_type": issues_by_type,
        "n_issue_types": len(summary),
    }


# ═══════════════════════════════════════════════════════════════════════
# Step 3: 输出清洗后标签 + 报告
# ═══════════════════════════════════════════════════════════════════════
def step3_write_outputs(
    rows: List[Dict[str, Any]],
    labels: List[str],
    cl_result: Dict[str, Any],
    datalab_result: Dict[str, Any],
    out_dir: Path,
    drop_ratio: float,
    logger: logging.Logger,
) -> Dict[str, Path]:
    """写 clean_labels.jsonl + label_issues_report.json + datalab_report.json。

    drop 逻辑: 按 cleanlab_quality_score 升序, 丢弃最低 floor(N*drop_ratio) 个。
    (最低 quality_score = 最可疑, 等价于 self_confidence 最低)
    """
    import numpy as np

    out_dir.mkdir(parents=True, exist_ok=True)
    per_sample = cl_result["per_sample"]
    n = len(per_sample)
    n_drop = int(np.floor(n * drop_ratio))
    # 按 quality_score 升序排 (越低越可疑)
    order = sorted(range(n), key=lambda i: per_sample[i]["cleanlab_quality_score"])
    drop_set = set(order[:n_drop])

    # 1. clean_labels.jsonl — 仅保留未丢弃样本 (保留原字段 + 附 cleanlab_score)
    clean_path = out_dir / "clean_labels.jsonl"
    n_kept = 0
    with clean_path.open("w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            if i in drop_set:
                continue
            out_row = dict(r)  # 保留原字段 (shot_id/movement_label/confidence/clip_path/anime)
            out_row["cleanlab_quality_score"] = round(
                per_sample[i]["cleanlab_quality_score"], 4)
            out_row["cleanlab_self_confidence"] = round(
                per_sample[i]["cleanlab_self_confidence"], 4)
            f.write(json.dumps(out_row, ensure_ascii=False) + "\n")
            n_kept += 1
    logger.info("[Step 3] 清洗后标签 -> %s (保留 %d, 丢弃 %d, ratio=%.2f)",
                clean_path, n_kept, n_drop, drop_ratio)

    # 2. label_issues_report.json — 详细 issue 报告 (含丢弃名单)
    issues_path = out_dir / "label_issues_report.json"
    dropped_detail = [per_sample[i] for i in order[:n_drop]]
    issues_report = {
        "summary": {
            "n_total": n,
            "n_label_issues": cl_result["n_issues"],
            "label_issue_rate": round(cl_result["issue_rate"], 4),
            "n_dropped": n_drop,
            "drop_ratio": drop_ratio,
            "detector": "CLIP-ViT-B32 + LogisticRegression (异构于 Qwen3-VL 标注器)",
            "oof_method": "StratifiedKFold(n_splits=10)",
        },
        "label_distribution_before": dict(Counter(labels)),
        "label_distribution_after": dict(
            Counter(labels[i] for i in range(n) if i not in drop_set)),
        "joint_distribution": cl_result["joint_distribution"],
        "joint_labels_given": cl_result["joint_labels_given"],
        "joint_labels_true": cl_result["joint_labels_true"],
        "dropped_samples": dropped_detail,
        "all_per_sample": per_sample,
    }
    issues_path.write_text(
        json.dumps(issues_report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("[Step 3] 标签问题报告 -> %s", issues_path)

    # 3. datalab_report.json — Datalab 完整报告 (若 Step 2 因缺依赖跳过则写占位说明)
    datalab_path = out_dir / "datalab_report.json"
    if datalab_result is None:
        datalab_report = {
            "skipped": True,
            "reason": "cleanlab[datalab] 可选依赖未安装 (或 Step 2 执行失败)，Datalab 体检模块已跳过。核心 Confident Learning 清洗不受影响。",
            "install_hint": "py -3.12 -m pip install 'cleanlab[datalab]'",
            "issue_summary": {},
            "issues_by_type": {},
            "report_text": "",
        }
        logger.warning("[Step 3] Datalab 模块不可用，写入占位报告 (核心 CL 清洗仍有效)")
    else:
        datalab_report = {
            "issue_summary": datalab_result["issue_summary"],
            "n_issue_types": datalab_result["n_issue_types"],
            "issues_by_type": datalab_result["issues_by_type"],
            "report_text": datalab_result["report_text"],
        }
    datalab_path.write_text(
        json.dumps(datalab_report, ensure_ascii=False, indent=2,
                   default=_json_default),
        encoding="utf-8")
    logger.info("[Step 3] Datalab 报告 -> %s", datalab_path)

    return {"clean_labels": clean_path, "issues_report": issues_path,
            "datalab_report": datalab_path}


def _json_default(obj: Any) -> Any:
    """JSON 序列化兜底: numpy 标量 / DataFrame 残留。"""
    try:
        import numpy as np
        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
    except ImportError:
        pass
    if isinstance(obj, (set,)):
        return list(obj)
    return str(obj)


# ═══════════════════════════════════════════════════════════════════════
# 主流程
# ═══════════════════════════════════════════════════════════════════════
def normalize_to_six(rows: List[Dict[str, Any]],
                     logger: logging.Logger) -> Tuple[List[Dict[str, Any]], List[str]]:
    """把 movement_label 折叠到 6 类规范标签 (SIX_MAP)。

    跳过 complex / 未知方向 / 无 clip_path 的样本, 并打印过滤统计。
    返回: (有效 rows, 6 类 label 列表)
    """
    kept: List[Dict[str, Any]] = []
    labels: List[str] = []
    skipped = Counter()
    for r in rows:
        d = r.get("movement_label", "")
        mapped = SIX_MAP.get(d)
        if d not in SIX_MAP:
            skipped["unknown_label"] += 1
            continue
        if mapped is None:
            skipped["complex"] += 1
            continue
        clip = r.get("clip_path", "")
        if not clip:
            skipped["no_clip_path"] += 1
            continue
        # 不在此处做 clip_path.exists() 过滤 — Step 0 已报告存在性, 此处保留全部
        # (缺失文件的样本 CLIP 抽帧时回退零向量, Datalab 会标为 outlier)
        kept.append(r)
        labels.append(mapped)
    logger.info("6 类规范化: 保留 %d, 跳过 %s", len(kept), dict(skipped))
    return kept, labels


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    logger = setup_logging()

    parser = argparse.ArgumentParser(
        description="动漫运镜分类标签清洗 (Confident Learning + Datalab)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--labels", type=str,
                        default=r"D:\AE-Data\AnimeCamera\vlm_labels.jsonl",
                        help="标签文件路径 (jsonl)")
    parser.add_argument("--out", type=str,
                        default=r"D:\AE-Data\AnimeCamera\cleaned",
                        help="输出目录")
    parser.add_argument("--drop-ratio", type=float, default=0.10,
                        help="丢弃比例 (默认 0.10, 即丢弃最可疑的 10%%)")
    parser.add_argument("--clip-model", type=str, default="ViT-B/32",
                        choices=list(CLIP_MODEL_MAP.keys()),
                        help="CLIP 模型 (默认 ViT-B/32)")
    parser.add_argument("--limit", type=int, default=0,
                        help="冒烟测试限制 (默认 0=全部)")
    parser.add_argument("--n-splits", type=int, default=10,
                        help="StratifiedKFold 折数 (默认 10)")
    args = parser.parse_args()

    labels_path = Path(args.labels)
    out_dir = Path(args.out)

    # ─── Step 0: 存在性闸门 ───
    rows = load_labels(labels_path, args.limit, logger)
    step0_existence_gate(rows, logger)

    # ─── 6 类规范化 ───
    kept, labels = normalize_to_six(rows, logger)
    if len(kept) < len(SIX_LABELS) * 2:
        logger.error("有效样本过少 (%d), 无法做 StratifiedKFold。退出。", len(kept))
        return 4

    # ─── Step 1: CLIP 特征 + OOF + Confident Learning ───
    print("\n" + "=" * 70)
    print("[Step 1] Confident Learning — 异构检测器 OOF 预测")
    print("=" * 70)
    features = compute_clip_embeddings(kept, args.clip_model, logger)
    pred_probs = compute_oof_pred_probs(features, [LABEL_TO_IDX[l] for l in labels],
                                        args.n_splits, logger)
    cl_result = step1_confident_learning(kept, labels, pred_probs, logger)

    # ─── Step 2: Datalab 全数据体检 (可选, 缺依赖自动跳过) ───
    print("\n" + "=" * 70)
    print("[Step 2] Datalab 全数据体检")
    print("=" * 70)
    try:
        datalab_result = step2_datalab(kept, features, labels, pred_probs, logger)
    except Exception as exc:
        logger.warning("Step 2 Datalab 跳过 (非致命, 核心 Confident Learning 清洗仍完成): %s: %s",
                       type(exc).__name__, str(exc)[:200])
        datalab_result = None

    # ─── Step 3: 输出 ───
    print("\n" + "=" * 70)
    print("[Step 3] 输出清洗后标签 + 报告")
    print("=" * 70)
    paths = step3_write_outputs(kept, labels, cl_result, datalab_result,
                                out_dir, args.drop_ratio, logger)

    # ─── 收尾汇总 ───
    print("\n" + "=" * 70)
    print("[完成] 清洗汇总")
    print("=" * 70)
    print(f"  原始样本: {len(rows)}")
    print(f"  6 类有效: {len(kept)}")
    print(f"  标签问题: {cl_result['n_issues']} "
          f"({100 * cl_result['issue_rate']:.1f}%)")
    print(f"  丢弃样本: {int(__import__('numpy').floor(len(kept) * args.drop_ratio))} "
          f"(drop_ratio={args.drop_ratio})")
    print(f"  清洗标签: {paths['clean_labels']}")
    print(f"  问题报告: {paths['issues_report']}")
    print(f"  Datalab : {paths['datalab_report']}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
