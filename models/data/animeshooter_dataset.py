"""
AnimeShooter 数据集适配器 (Step 4 素材源)

AnimeShooter (2025, CC BY-NC 4.0, 学术用途) 是多镜头动画数据集
(参考引导视频生成用), 29,428 个 YouTube 视频 ID + 逐视频 JSON 标注。

与 MovieShots 的关键区别:
  - MovieShots = 已有运镜标签 (movement 5 类) → 直接训练
  - AnimeShooter = **无运镜标签**, 只有镜头边界 (shot start/end) + 视觉描述
    → 本适配器的职责是把"镜头级候选"抽出来, 交给 VLM 预标注管线
    (docs/plans/2026-08-14-step4-anime-camera-dataset.md §3), 作为 Step 4
    的"镜头边界 + 视频素材源", 不是标签源。

数据结构 (实测 2026-08-14, HF qiulu66/AnimeShooter):
  - repo 文件: dataset_anime_shooter.zip (逐视频 JSON 标注 + 参考图),
    dataset_anime_shooter_audio.zip (音频标注), video_ids.txt (29,428 行 YouTube ID)
  - 源视频需用 yt-dlp 按 video_ids.txt 自行下载: {video_id}.mp4
  - 每个 JSON 标注字段:
      video ID (string) / url / fps (float) / segments (list)
      segments[]:
        start frame index / end frame index / story script / reference images
        story script:
          storyline (string)
          main characters[] / main scenes[]
          shots[]:
            start time ("MM:SS") / end time ("MM:SS")
            is_prologue_or_epilogue (bool)
            main characters[] (ID list) / scene (ID)
            visual annotation: {narrative caption, descriptive caption}

用途:
  1. 解析逐视频 JSON → 镜头级候选 (AnimeShotSample)
  2. 计算绝对时间 (segment frame index + fps + shot MM:SS)
  3. 导出统一 JSONL, movement_label 留空 (待 VLM 预标注)

参考 Antares 哲学: 高质量镜头边界 > 自己从头切镜头 (TransNetV2)。
"""
from __future__ import annotations

import json
import logging
import os
import zipfile
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from .dataset_base import BaseDataset, DatasetConfig, DatasetStats
except ImportError:  # 直接脚本运行
    from dataset_base import BaseDataset, DatasetConfig, DatasetStats

logger = logging.getLogger(__name__)

# 本项目统一 JSONL 的 schema 版本标记 (与 MovieShots JSONL 区分)
SCHEMA = "animeshooter_shot_candidate_v1"


def _parse_clock(t: str) -> float:
    """把 "MM:SS" 或 "HH:MM:SS" 转成秒。"""
    if t is None:
        return 0.0
    t = str(t).strip()
    if not t:
        return 0.0
    parts = t.split(":")
    try:
        if len(parts) == 3:
            h, m, s = (int(x) for x in parts)
            return h * 3600 + m * 60 + s
        if len(parts) == 2:
            m, s = (int(x) for x in parts)
            return m * 60 + s
        return float(parts[0])
    except (ValueError, TypeError):
        return 0.0


@dataclass
class AnimeShotSample:
    """AnimeShooter 单镜头候选 (无运镜标签, 待 VLM 预标注)。"""
    video_id: str                 # YouTube 视频 ID
    segment_idx: int              # 1-min 段索引 (0-based)
    shot_idx: int                 # 段内镜头索引 (0-based)
    start_time: str = ""          # 原始 "MM:SS" (段内相对)
    end_time: str = ""
    is_prologue_or_epilogue: bool = False
    characters: list[str] = field(default_factory=list)
    scene: str = ""
    narrative_caption: str = ""
    descriptive_caption: str = ""
    source: str = "animeshooter"
    # 计算字段
    fps: float = 0.0
    segment_start_frame: int = 0
    start_sec: float = 0.0        # 源视频绝对秒
    end_sec: float = 0.0
    duration_sec: float = 0.0
    video_path: str = ""          # 下载后填充
    movement_label: str | None = None  # 待 VLM 预标注 (None=未标)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": SCHEMA,
            "video_id": self.video_id,
            "segment_idx": self.segment_idx,
            "shot_idx": self.shot_idx,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "is_prologue_or_epilogue": self.is_prologue_or_epilogue,
            "characters": self.characters,
            "scene": self.scene,
            "narrative_caption": self.narrative_caption,
            "descriptive_caption": self.descriptive_caption,
            "source": self.source,
            "fps": self.fps,
            "segment_start_frame": self.segment_start_frame,
            "start_sec": round(self.start_sec, 3),
            "end_sec": round(self.end_sec, 3),
            "duration_sec": round(self.duration_sec, 3),
            "video_path": self.video_path,
            "movement_label": self.movement_label,
        }


def _iter_annotation_json(path: str) -> list[AnimeShotSample]:
    """读取单个 AnimeShooter 逐视频 JSON, 返回镜头候选列表。

    JSON 结构: {video_id or "video ID": {url, fps, segments: [...]}}
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # 顶层可能是 {video_id: {...}} 或直接 {...}
    if isinstance(data, dict):
        # 若只有一个 key 且 value 是 dict, 解包
        keys = [k for k in data.keys() if k not in ("url", "fps", "segments",
                                                     "video ID", "video_id")]
        if keys and isinstance(data.get(keys[0]), dict):
            data = data[keys[0]]

    video_id = str(data.get("video_id") or data.get("video ID") or
                   os.path.splitext(os.path.basename(path))[0])
    fps = float(data.get("fps") or 0.0)
    segments = data.get("segments") or []

    samples: list[AnimeShotSample] = []
    for si, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        seg_start_frame = int(seg.get("start frame index",
                                      seg.get("start_frame_index", 0)))
        story = seg.get("story script") or seg.get("story_script") or {}
        shots = story.get("shots") or []
        for shi, shot in enumerate(shots):
            if not isinstance(shot, dict):
                continue
            va = shot.get("visual annotation") or shot.get("visual_annotation") or {}
            rel_start = _parse_clock(shot.get("start time",
                                              shot.get("start_time", "0:00")))
            rel_end = _parse_clock(shot.get("end time", shot.get("end_time", "0:00")))
            # 段内相对时间 + 段起始帧 → 源视频绝对时间
            seg_start_sec = seg_start_frame / fps if fps > 0 else 0.0
            start_sec = seg_start_sec + rel_start
            end_sec = seg_start_sec + rel_end
            sample = AnimeShotSample(
                video_id=video_id,
                segment_idx=si,
                shot_idx=shi,
                start_time=str(shot.get("start time", shot.get("start_time", ""))),
                end_time=str(shot.get("end time", shot.get("end_time", ""))),
                is_prologue_or_epilogue=bool(
                    shot.get("is_prologue_or_epilogue", False)),
                characters=[str(c) for c in (shot.get("main characters") or [])],
                scene=str(shot.get("scene", "")),
                narrative_caption=str(va.get("narrative caption",
                                             va.get("narrative_caption", ""))),
                descriptive_caption=str(va.get("descriptive caption",
                                               va.get("descriptive_caption", ""))),
                fps=fps,
                segment_start_frame=seg_start_frame,
                start_sec=start_sec,
                end_sec=end_sec,
                duration_sec=round(max(0.0, end_sec - start_sec), 3),
            )
            samples.append(sample)
    return samples


def _iter_zip(path: str) -> list[AnimeShotSample]:
    """从 zip 内逐 JSON 解析 (dataset_anime_shooter.zip)。"""
    samples: list[AnimeShotSample] = []
    with zipfile.ZipFile(path) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".json"):
                continue
            with zf.open(name) as f:
                try:
                    data = json.load(f)
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    logger.warning("skip bad json %s: %s", name, exc)
                    continue
            samples.extend(_parse_json_obj(data, video_id_hint=os.path.basename(name)))
    return samples


def _parse_json_obj(data: dict[str, Any], video_id_hint: str = "") -> list[AnimeShotSample]:
    """从已加载的 JSON dict 解析 (复用 _iter_annotation_json 的核心逻辑)。"""
    if isinstance(data, dict):
        keys = [k for k in data.keys() if k not in ("url", "fps", "segments",
                                                     "video ID", "video_id")]
        if keys and isinstance(data.get(keys[0]), dict):
            data = data[keys[0]]

    video_id = str(data.get("video_id") or data.get("video ID") or
                   os.path.splitext(video_id_hint)[0])
    fps = float(data.get("fps") or 0.0)
    segments = data.get("segments") or []

    samples: list[AnimeShotSample] = []
    for si, seg in enumerate(segments):
        if not isinstance(seg, dict):
            continue
        seg_start_frame = int(seg.get("start frame index",
                                      seg.get("start_frame_index", 0)))
        story = seg.get("story script") or seg.get("story_script") or {}
        shots = story.get("shots") or []
        for shi, shot in enumerate(shots):
            if not isinstance(shot, dict):
                continue
            va = shot.get("visual annotation") or shot.get("visual_annotation") or {}
            rel_start = _parse_clock(shot.get("start time", shot.get("start_time", "0:00")))
            rel_end = _parse_clock(shot.get("end time", shot.get("end_time", "0:00")))
            seg_start_sec = seg_start_frame / fps if fps > 0 else 0.0
            start_sec = seg_start_sec + rel_start
            end_sec = seg_start_sec + rel_end
            samples.append(AnimeShotSample(
                video_id=video_id,
                segment_idx=si,
                shot_idx=shi,
                start_time=str(shot.get("start time", shot.get("start_time", ""))),
                end_time=str(shot.get("end time", shot.get("end_time", ""))),
                is_prologue_or_epilogue=bool(shot.get("is_prologue_or_epilogue", False)),
                characters=[str(c) for c in (shot.get("main characters") or [])],
                scene=str(shot.get("scene", "")),
                narrative_caption=str(va.get("narrative caption", va.get("narrative_caption", ""))),
                descriptive_caption=str(va.get("descriptive caption", va.get("descriptive_caption", ""))),
                fps=fps,
                segment_start_frame=seg_start_frame,
                start_sec=start_sec,
                end_sec=end_sec,
                duration_sec=round(max(0.0, end_sec - start_sec), 3),
            ))
    return samples


class AnimeShooterDataset(BaseDataset):
    """AnimeShooter 镜头级素材源数据集。

    加载逐视频 JSON 标注 (目录 / 单文件 / zip / JSONL),
    输出待标注的镜头候选 (AnimeShotSample)。
    """

    def __init__(self, config: DatasetConfig):
        super().__init__(config)

    # ── 加载 ────────────────────────────────────────────────────────────

    def load_data(self, data_path: str) -> list[AnimeShotSample]:
        samples: list[AnimeShotSample] = []

        if os.path.isdir(data_path):
            for fn in sorted(os.listdir(data_path)):
                if not fn.lower().endswith(".json"):
                    continue
                p = os.path.join(data_path, fn)
                try:
                    samples.extend(_iter_annotation_json(p))
                except Exception as exc:  # noqa: BLE001
                    logger.warning("skip %s: %s", fn, exc)
        elif data_path.lower().endswith(".zip"):
            samples = _iter_zip(data_path)
        elif data_path.endswith(".jsonl"):
            with open(data_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    d = json.loads(line)
                    d.pop("schema", None)
                    samples.append(AnimeShotSample(**{
                        k: d[k] for k in (
                            "video_id", "segment_idx", "shot_idx",
                            "start_time", "end_time", "is_prologue_or_epilogue",
                            "characters", "scene", "narrative_caption",
                            "descriptive_caption", "source", "fps",
                            "segment_start_frame", "start_sec", "end_sec",
                            "duration_sec", "video_path", "movement_label",
                        ) if k in d
                    }))
        else:
            samples = _iter_annotation_json(data_path)

        return samples

    # ── 预处理 / 校验 / 增强 ────────────────────────────────────────────

    def preprocess(self, data: list[AnimeShotSample]) -> list[AnimeShotSample]:
        """过滤无效镜头 (无时长 / 时长异常 0.3-60s)。"""
        out = []
        for s in data:
            if s.duration_sec <= 0:
                continue
            # 运镜候选: 0.3s 下限对齐 Step 4 §3 筛选, 上限放宽到 60s (段内)
            if s.duration_sec < 0.3:
                continue
            out.append(s)
        return out

    def validate_sample(self, sample: AnimeShotSample) -> bool:
        return sample.video_id != "" and sample.duration_sec > 0

    def augment_sample(self, sample: AnimeShotSample) -> list[AnimeShotSample]:
        """镜头候选不做增强 (运镜标注后由训练侧做视频变换)。"""
        return []

    # ── 导出 ────────────────────────────────────────────────────────────

    def to_jsonl(self, out_path: str, samples: list[AnimeShotSample] | None = None) -> int:
        """导出镜头候选 JSONL (movement_label 留 null, 供 VLM 预标注)。"""
        if samples is None:
            samples = self._train_data + self._val_data + self._test_data
        with open(out_path, "w", encoding="utf-8") as f:
            for s in samples:
                f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
        return len(samples)


def build_shot_stats(samples: list[AnimeShotSample]) -> dict[str, Any]:
    """统计镜头候选: 总量 / 视频数 / 平均时长 / 时长分布。"""
    from collections import Counter
    n_videos = len({s.video_id for s in samples})
    durations = [s.duration_sec for s in samples]
    avg = sum(durations) / len(durations) if durations else 0.0
    return {
        "n_shots": len(samples),
        "n_videos": n_videos,
        "avg_duration_sec": round(avg, 3),
        "duration_buckets": dict(Counter(
            "<1s" if d < 1 else ("1-3s" if d < 3 else ("3-8s" if d < 8 else ">=8s"))
            for d in durations)),
    }


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    base = sys.argv[1] if len(sys.argv) > 1 else r"D:\AE-Data\AnimeShooter"
    cfg = DatasetConfig(
        dataset_name="AnimeShooter",
        data_path=base,
        data_augmentation=False,
    )
    ds = AnimeShooterDataset(cfg)
    stats = ds.prepare()
    print(f"total={stats.total_samples} train={stats.train_samples} "
          f"val={stats.val_samples} test={stats.test_samples}")
    print("shot stats:", build_shot_stats(
        ds.get_train_data() + ds.get_val_data() + ds.get_test_data()))

    out = os.path.join(base, "animeshooter_shots.jsonl")
    n = ds.to_jsonl(out)
    print(f"exported {n} -> {out}")
