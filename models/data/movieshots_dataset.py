"""
MovieShots 运镜数据集适配器 (Step 3)

真实数据集实证 (2026-08-14 下载核实):
  - MovieShots (ECCV 2020, Rao et al.) 实际是 "46K shots / 7K 预告片",
    含两个标注维度:
      * scale (景别) 5 类: LS / FS / MS / CS / ECS
      * movement (运镜) 5 类: Static / Motion / Pull / Push / Multi_movement
    (调研文档曾写 "21,614 五分类", 实际 v1=33,653 + v3=13,204 + v2=606 补充,
     合计约 47K 条, 与论文 "46K shots" 一致)
  - 与项目 core/camera_movement_classifier.py 的 CAMERA_LABELS (13 类)
    映射关系 (关键!):
      MovieShots Static        -> static
      MovieShots Motion        -> pan/tilt/diag (平移旋转合并类, 细分类靠推理侧拆分)
      MovieShots Pull          -> zoom_out
      MovieShots Push          -> zoom_in / push
      MovieShots Multi_movement-> complex
  - 标注文件 (Google Drive, 已下载到 D:\\AE-Data\\MovieNet\\MovieShots):
      v1_full_trailer.json   7,848 预告片 / 33,653 shots (scale+movement 双标注)
      v1_split_trailer.json  3 部 7,848 shots 的 split 划分
      v2_full_trailer.json   533 预告片 / 606 条 push/pull 补充 (仅 movement)
      v3_full.json           10 部电影 / 13,204 shots (scale+movement, 全片)
      v3_split.json          6 条 split 划分
  - 视频: trailer.zip 16.9GB (v1, Google Drive 文件 ID 1-Yr1tq2WKrzmBetssdhImjXkLiOclB3G)
            trailer_v2.zip 757MB (v2, 文件 ID 1-9qpJS20w4L4s5MA123uCC6lIX4ENk7m)

用途:
  1. 把 MovieShots 标注整理为统一 JSONL (movement 标签 -> 项目标签映射)
  2. 训练轻量分类器 (替代 core/camera_movement_classifier.py 的光流规则)
  3. 输出可被 ai/camera_decision.py SourceCameraInventory.inject() 消费的标签

参考 Antares 哲学: 高质量标注 + 轻量模型 = 生产可用的运镜感知。
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from .dataset_base import BaseDataset, DatasetConfig, DatasetStats
except ImportError:  # 直接脚本运行 (python models/data/movieshots_dataset.py)
    from dataset_base import BaseDataset, DatasetConfig, DatasetStats

logger = logging.getLogger(__name__)

# ── 类别映射 ────────────────────────────────────────────────────────────

# MovieShots movement 原始标签 -> 项目 CAMERA_LABELS (core/camera_movement_classifier.py)
MOVEMENT_TO_PROJECT: Dict[str, str] = {
    "Static": "static",
    "Motion": "pan_left",        # 平移/旋转合并类: 细分类留待推理侧 (见 infer 模块)
    "Pull": "zoom_out",
    "Push": "zoom_in",
    "Multi_movement": "complex",
}

# MovieShots scale 标签 (景别, 可作辅助任务/特征)
SCALE_LABELS: List[str] = ["LS", "FS", "MS", "CS", "ECS"]

# 项目可用运镜标签全集 (与 CAMERA_LABELS 对齐)
PROJECT_CAMERA_LABELS: List[str] = [
    "static", "pan_left", "pan_right", "zoom_in", "zoom_out",
    "tilt_up", "tilt_down", "zoom_back", "diag_pan", "orbit",
    "push", "complex", "unknown",
]


@dataclass
class MovieShotSample:
    """MovieShots 单镜头样本 (统一结构)。"""
    movie_id: str          # trailer id / imdb id
    shot_idx: str          # 镜头序号 (JSON key, 如 "0003")
    movement_label: str    # 项目标签 (映射后)
    movement_raw: str      # 原始标签 (Static/Motion/...)
    movement_value: int    # 原始数值
    scale_label: Optional[str] = None   # 景别 (可选)
    scale_value: Optional[int] = None
    source: str = ""       # v1/v2/v3
    video_path: str = ""   # 对应视频/关键帧路径 (下载后填充)
    frame_indices: List[int] = field(default_factory=list)  # 镜头帧范围 (v3)


def _iter_movieshots_json(path: str) -> List[MovieShotSample]:
    """读取单个 MovieShots JSON, 返回样本列表。

    兼容三种结构:
      - v1/v2: {trailer_id: {shot_idx: {scale/movement}}}
      - v3:    {"full": {"movie": {imdb_id: {shot_idx: {scale/movement}}}}}
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # v3 结构归一化
    if isinstance(data, dict) and "full" in data and isinstance(data["full"], dict):
        inner = data["full"]
        # v3_full: {"full": {"movie": {...}}}
        if "movie" in inner and isinstance(inner["movie"], dict):
            movies = inner["movie"]
        else:
            movies = inner
    else:
        movies = data

    samples: List[MovieShotSample] = []
    for mid, shots in movies.items():
        if not isinstance(shots, dict):
            continue
        for sid, ann in shots.items():
            if not isinstance(ann, dict):
                continue
            mv = ann.get("movement")
            sc = ann.get("scale")
            sample = MovieShotSample(
                movie_id=str(mid),
                shot_idx=str(sid),
                movement_label=MOVEMENT_TO_PROJECT.get(
                    (mv or {}).get("label", ""), "unknown"),
                movement_raw=(mv or {}).get("label", ""),
                movement_value=(mv or {}).get("value", -1),
                scale_label=(sc or {}).get("label"),
                scale_value=(sc or {}).get("value"),
            )
            samples.append(sample)
    return samples


class MovieShotsDataset(BaseDataset):
    """MovieShots 运镜分类数据集。

    加载 v1/v2/v3 标注, 统一为 MovieShotSample,
    供训练/评估/注入使用。
    """

    def __init__(self, config: DatasetConfig):
        super().__init__(config)
        self._label_to_idx: Dict[str, int] = {}
        self._idx_to_label: Dict[int, str] = {}
        for idx, label in enumerate(PROJECT_CAMERA_LABELS):
            self._label_to_idx[label] = idx
            self._idx_to_label[idx] = label

    # ── 加载 ────────────────────────────────────────────────────────────

    def load_data(self, data_path: str) -> List[MovieShotSample]:
        """从目录或单文件加载标注。

        data_path 可以是:
          - 目录 (内含 v1_full_trailer.json 等)
          - 单个 JSON 文件
          - JSONL (本项目统一格式: 每行一个样本)
        """
        samples: List[MovieShotSample] = []

        if os.path.isdir(data_path):
            # 按优先级加载 v1/v2/v3
            candidates = [
                "v1_full_trailer.json",
                "v2_full_trailer.json",
                "v3_full.json",
            ]
            for fn in candidates:
                p = os.path.join(data_path, fn)
                if os.path.exists(p):
                    got = _iter_movieshots_json(p)
                    for s in got:
                        s.source = fn.split("_")[0]
                    samples.extend(got)
                    logger.info("Loaded %s: %d samples", fn, len(got))
        elif data_path.endswith(".jsonl"):
            with open(data_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    samples.append(MovieShotSample(**{
                        k: d[k] for k in (
                            "movie_id", "shot_idx", "movement_label",
                            "movement_raw", "movement_value",
                            "scale_label", "scale_value", "source",
                        ) if k in d
                    }))
        else:
            samples = _iter_movieshots_json(data_path)

        return samples

    # ── 预处理 / 校验 / 增强 ────────────────────────────────────────────

    def preprocess(self, data: List[MovieShotSample]) -> List[MovieShotSample]:
        """过滤掉 unknown / 无效样本。"""
        out = []
        for s in data:
            if s.movement_label in self._label_to_idx and s.movement_label != "unknown":
                out.append(s)
        return out

    def validate_sample(self, sample: MovieShotSample) -> bool:
        return sample.movement_label in self._label_to_idx and sample.movement_label != "unknown"

    def augment_sample(self, sample: MovieShotSample) -> List[MovieShotSample]:
        """运镜标签是离散类, 不做特征级增强 (样本级增强在训练侧做视频变换)。"""
        return []

    # ── 导出工具 ────────────────────────────────────────────────────────

    def to_jsonl(self, out_path: str, samples: Optional[List[MovieShotSample]] = None) -> int:
        """把样本集导出为 JSONL (本项目统一训练格式)。"""
        if samples is None:
            samples = self._train_data + self._val_data + self._test_data
        with open(out_path, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps({
                    "movie_id": s.movie_id,
                    "shot_idx": s.shot_idx,
                    "movement_label": s.movement_label,
                    "movement_raw": s.movement_raw,
                    "movement_value": s.movement_value,
                    "scale_label": s.scale_label,
                    "scale_value": s.scale_value,
                    "source": s.source,
                }, ensure_ascii=False) + "\n")
        return len(samples)


def build_label_stats(samples: List[MovieShotSample]) -> Dict[str, int]:
    """统计运镜标签分布。"""
    from collections import Counter
    return dict(Counter(s.movement_label for s in samples))


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    base = r"D:\AE-Data\MovieNet\MovieShots"
    cfg = DatasetConfig(
        dataset_name="MovieShots",
        data_path=base,
        data_augmentation=False,
    )
    ds = MovieShotsDataset(cfg)
    stats = ds.prepare()

    print(f"total={stats.total_samples} train={stats.train_samples} "
          f"val={stats.val_samples} test={stats.test_samples}")
    print("label dist:", build_label_stats(
        ds.get_train_data() + ds.get_val_data() + ds.get_test_data()))

    # 导出统一 JSONL
    out = os.path.join(base, "movieshots_unified.jsonl")
    n = ds.to_jsonl(out)
    print(f"exported {n} -> {out}")
