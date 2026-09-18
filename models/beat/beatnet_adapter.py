"""models/beat/beatnet_adapter.py — BeatNetLite 节拍/下拍适配器

把 external/BeatNetLite (SOTA 节拍+下拍+速度+拍号联合跟踪, 仅 torch+librosa
依赖, CPU 3 分钟歌 2-4s) 包装为项目可用组件, 给卡点管线补"节拍+下拍+小节"
三层信号 (项目现有 rhythm_reward 主要靠 onset + kick/snare 分类, 缺少
可靠的下拍/拍号层)。

用法:
    from models.beat.beatnet_adapter import get_beatnet
    bn = get_beatnet()
    if bn.available():
        grid = bn.analyze("song.wav")
        print(grid.tempo, grid.meter, len(grid.beats), len(grid.downbeats))

依赖安装 (external/ 为本地约定目录, 不入库):
    git clone --depth 1 https://github.com/turbo/BeatNetLite.git external/BeatNetLite
(权重共 9MB, 随仓库克隆; 运行依赖 torch + librosa, 项目环境已具备)
"""
from __future__ import annotations

import logging
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_BEATNET_DIR = Path(__file__).resolve().parent.parent.parent / "external" / "BeatNetLite"

_MODEL_CHOICES = {
    "generic": 1,   # 通用模型 (默认)
    "east": 2,      # 非西方/东方音乐
    "carnatic": 3,  # 卡纳提克音乐
}


@dataclass
class BeatGridResult:
    """节拍网格结果。"""
    beats: list[float] = field(default_factory=list)       # 每拍时间 (s)
    downbeats: list[float] = field(default_factory=list)   # 小节第一拍 (s)
    beat_numbers: list[int] = field(default_factory=list)  # 每拍在小节内编号 (1=下拍)
    tempo: float = 0.0                                     # BPM 估计
    meter: int = 4                                         # 拍号分子 (4/4 → 4)
    latency_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "tempo": self.tempo, "meter": self.meter,
            "n_beats": len(self.beats), "n_downbeats": len(self.downbeats),
            "latency_sec": self.latency_sec,
        }

    def to_beatgrid(self) -> list[dict[str, Any]]:
        """转换为项目节奏管线的 beatgrid 消费格式。

        每拍一条: {time, beat_number, is_downbeat}
        (与 production_director._beatgrid 结构对齐, 供融合消费)
        """
        return [
            {
                "t": round(t, 3),
                "beat_number": n,
                "is_downbeat": n == 1,
            }
            for t, n in zip(self.beats, self.beat_numbers)
        ]


class BeatNetAdapter:
    """BeatNetLite 适配器 (懒加载, 优雅降级)。"""

    def __init__(self, model: str = "generic",
                 beatnet_dir: str | None = None) -> None:
        self.model = model
        self.beatnet_dir = Path(beatnet_dir) if beatnet_dir else _BEATNET_DIR
        self._bn = None
        self._load_error: str | None = None

    def available(self) -> bool:
        """模型权重与依赖齐备即视为可用。"""
        models_dir = self.beatnet_dir / "models"
        return models_dir.is_dir() and any(models_dir.glob("*.pt"))

    def _ensure_loaded(self) -> bool:
        if self._bn is not None:
            return True
        if self._load_error:
            return False
        if not self.available():
            self._load_error = f"BeatNetLite models not found: {self.beatnet_dir}"
            logger.warning("[BeatNet] %s", self._load_error)
            return False
        try:
            if str(self.beatnet_dir) not in sys.path:
                sys.path.insert(0, str(self.beatnet_dir))
            from BeatNetLite import BeatNetLite
            self._bn = BeatNetLite(_MODEL_CHOICES.get(self.model, 1))
            return True
        except Exception as exc:  # noqa: BLE001
            self._load_error = str(exc)
            logger.warning("[BeatNet] load failed: %s", exc)
            return False

    def analyze(self, audio_path: str) -> BeatGridResult | None:
        """对音频做节拍网格分析。

        Returns:
            None — 不可用/失败
            BeatGridResult — 每拍时间 + 下拍时间 + 拍号 + BPM
        """
        if not self._ensure_loaded():
            return None
        if not os.path.exists(audio_path):
            logger.warning("[BeatNet] audio not found: %s", audio_path)
            return None
        try:
            t0 = time.time()
            grid = self._bn.process(audio_path)
            elapsed = time.time() - t0

            import json
            if isinstance(grid, str):
                grid = json.loads(grid)
            items = sorted((float(k), int(v)) for k, v in grid.items())
            beats = [t for t, _ in items]
            numbers = [n for _, n in items]
            downbeats = [t for t, n in items if n == 1]

            # BPM: 相邻拍间隔中位数
            import statistics
            if len(beats) >= 2:
                gaps = [b - a for a, b in zip(beats[:-1], beats[1:])]
                med = statistics.median(g for g in gaps if g > 0.05)
                tempo = 60.0 / med if med > 0 else 0.0
            else:
                tempo = 0.0

            # 拍号: 下拍间隔 / 拍间隔 → 每小节拍数 (取众数)
            meter = 4
            if downbeats and len(beats) >= 2 and tempo > 0:
                db_gaps = [b - a for a, b in zip(downbeats[:-1], downbeats[1:])]
                if db_gaps:
                    beat_len = 60.0 / tempo
                    candidates = [max(2, min(12, round(g / beat_len)))
                                  for g in db_gaps]
                    meter = max(set(candidates), key=candidates.count)

            return BeatGridResult(
                beats=beats, downbeats=downbeats, beat_numbers=numbers,
                tempo=round(tempo, 1), meter=meter,
                latency_sec=round(elapsed, 2))
        except Exception as exc:  # noqa: BLE001
            logger.warning("[BeatNet] analyze failed %s: %s",
                           Path(audio_path).name, exc)
            return None


_SINGLETON: BeatNetAdapter | None = None


def get_beatnet(**kwargs) -> BeatNetAdapter:
    """获取模块级单例。"""
    global _SINGLETON
    if _SINGLETON is None:
        _SINGLETON = BeatNetAdapter(**kwargs)
    return _SINGLETON
