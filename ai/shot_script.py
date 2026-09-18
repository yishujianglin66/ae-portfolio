# -*- coding: utf-8 -*-
"""T15: ShotScript标准协议 — 镜头脚本JSON schema与校验器。

ShotScript是导演系统(multimodal_director)的标准化输出，人可读可回放，
可直接驱动ResolveExecutor(T16)和AEExecutor(T17)执行。

Schema:
{
  "version": "1.0",
  "metadata": {
    "title": str,
    "bgm": str,
    "theme": str,
    "duration_target": float,
    "created": ISO timestamp,
    "director_version": str
  },
  "shots": [
    {
      "shot_id": int,
      "source_video": str,           # 素材文件名
      "in_tc": float,                # 入点(秒)
      "out_tc": float,               # 出点(秒)
      "duration": float,             # 时长(秒)
      "speed_curve": [               # 变速曲线(分段)
        {"start": 0.0, "end": 0.5, "speed": 1.0},
        {"start": 0.5, "end": 1.0, "speed": 0.5}
      ],
      "transition": {                # 转场(可选)
        "type": "cut|dissolve|wipe",
        "duration": 0.5
      },
      "ip": str,                     # IP名(canonical)
      "characters": [str],           # 角色列表
      "mood": str,                   # 情绪标签
      "scene_type": str,             # 场景类型
      "text_overlay": {              # 文字叠加(可选, 驱动AE)
        "text": str,
        "font": str,
        "animation": str,            # 动画预设名
        "position": "top|center|bottom",
        "start": float,              # 相对镜头入点
        "duration": float
      },
      "cdl": {                       # CDL调色意图(可选, 驱动Resolve)
        "slope": [r, g, b],
        "offset": [r, g, b],
        "power": [r, g, b]
      },
      "lut": str,                    # LUT文件名(可选)
      "aesthetic_score": float,      # 美学分(0-1)
      "rhythm_score": float          # 节奏分(0-1)
    }
  ],
  "global_settings": {
    "resolution": "1920x1080",
    "fps": 30,
    "color_space": "Rec.709"
  }
}
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.stdout.reconfigure(encoding="utf-8")
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class SpeedSegment:
    """变速曲线分段"""
    start: float = 0.0      # 相对镜头入点(0-1)
    end: float = 1.0
    speed: float = 1.0      # 速度倍率

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "SpeedSegment":
        return SpeedSegment(**d)


@dataclass
class Transition:
    """转场"""
    type: str = "cut"       # cut|dissolve|wipe
    duration: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Transition":
        return Transition(**d)


@dataclass
class TextOverlay:
    """文字叠加(驱动AE文字动画)"""
    text: str = ""
    font: str = "Source Han Sans CN Bold"
    animation: str = "typewriter"    # typewriter|fade|slide|bounce
    position: str = "bottom"         # top|center|bottom
    start: float = 0.0               # 相对镜头入点(秒)
    duration: float = 2.0

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "TextOverlay":
        return TextOverlay(**d)


@dataclass
class CDL:
    """ASC CDL调色参数"""
    slope: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])
    offset: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    power: list[float] = field(default_factory=lambda: [1.0, 1.0, 1.0])

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "CDL":
        return CDL(**d)


@dataclass
class ShotUnit:
    """镜头单元 — ShotScript的最小执行单位"""
    shot_id: int = 0
    source_video: str = ""
    in_tc: float = 0.0
    out_tc: float = 0.0
    duration: float = 0.0
    speed_curve: list[SpeedSegment] = field(default_factory=list)
    transition: Transition | None = None
    ip: str = ""
    characters: list[str] = field(default_factory=list)
    mood: str = "neutral"
    scene_type: str = "unknown"
    text_overlay: TextOverlay | None = None
    cdl: CDL | None = None
    lut: str = ""
    aesthetic_score: float = 0.0
    rhythm_score: float = 0.0

    def to_dict(self) -> dict:
        d = {
            "shot_id": self.shot_id,
            "source_video": self.source_video,
            "in_tc": round(self.in_tc, 3),
            "out_tc": round(self.out_tc, 3),
            "duration": round(self.duration, 3),
            "speed_curve": [s.to_dict() for s in self.speed_curve],
            "ip": self.ip,
            "characters": self.characters,
            "mood": self.mood,
            "scene_type": self.scene_type,
            "aesthetic_score": round(self.aesthetic_score, 3),
            "rhythm_score": round(self.rhythm_score, 3),
        }
        if self.transition:
            d["transition"] = self.transition.to_dict()
        if self.text_overlay:
            d["text_overlay"] = self.text_overlay.to_dict()
        if self.cdl:
            d["cdl"] = self.cdl.to_dict()
        if self.lut:
            d["lut"] = self.lut
        return d

    @staticmethod
    def from_dict(d: dict) -> "ShotUnit":
        shot = ShotUnit(
            shot_id=d.get("shot_id", 0),
            source_video=d.get("source_video", ""),
            in_tc=d.get("in_tc", 0.0),
            out_tc=d.get("out_tc", 0.0),
            duration=d.get("duration", 0.0),
            ip=d.get("ip", ""),
            characters=d.get("characters", []),
            mood=d.get("mood", "neutral"),
            scene_type=d.get("scene_type", "unknown"),
            lut=d.get("lut", ""),
            aesthetic_score=d.get("aesthetic_score", 0.0),
            rhythm_score=d.get("rhythm_score", 0.0),
        )
        if "speed_curve" in d:
            shot.speed_curve = [SpeedSegment.from_dict(s) for s in d["speed_curve"]]
        if "transition" in d:
            shot.transition = Transition.from_dict(d["transition"])
        if "text_overlay" in d:
            shot.text_overlay = TextOverlay.from_dict(d["text_overlay"])
        if "cdl" in d:
            shot.cdl = CDL.from_dict(d["cdl"])
        return shot


@dataclass
class ShotScriptMetadata:
    """ShotScript元数据"""
    title: str = ""
    bgm: str = ""
    theme: str = ""
    duration_target: float = 0.0
    created: str = ""
    director_version: str = "1.0"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "ShotScriptMetadata":
        return ShotScriptMetadata(**d)


@dataclass
class GlobalSettings:
    """全局设置"""
    resolution: str = "1920x1080"
    fps: int = 30
    color_space: str = "Rec.709"

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "GlobalSettings":
        return GlobalSettings(**d)


@dataclass
class ShotScript:
    """镜头脚本 — 导演系统输出，执行器输入"""
    metadata: ShotScriptMetadata = field(default_factory=ShotScriptMetadata)
    shots: list[ShotUnit] = field(default_factory=list)
    global_settings: GlobalSettings = field(default_factory=GlobalSettings)

    def to_dict(self) -> dict:
        return {
            "version": "1.0",
            "metadata": self.metadata.to_dict(),
            "shots": [s.to_dict() for s in self.shots],
            "global_settings": self.global_settings.to_dict(),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)

    def save(self, path: Path) -> None:
        path.write_text(self.to_json(), encoding="utf-8")

    @staticmethod
    def from_dict(d: dict) -> "ShotScript":
        script = ShotScript(
            metadata=ShotScriptMetadata.from_dict(d.get("metadata", {})),
            global_settings=GlobalSettings.from_dict(d.get("global_settings", {})),
        )
        script.shots = [ShotUnit.from_dict(s) for s in d.get("shots", [])]
        return script

    @staticmethod
    def load(path: Path) -> "ShotScript":
        d = json.loads(path.read_text(encoding="utf-8"))
        return ShotScript.from_dict(d)

    # ---------------- 校验 ----------------

    def validate(self) -> list[str]:
        """校验ShotScript完整性，返回错误列表(空=通过)"""
        errors = []
        if not self.shots:
            errors.append("shots列表为空")
        total_duration = 0.0
        for i, shot in enumerate(self.shots):
            if not shot.source_video:
                errors.append(f"shot[{i}] source_video为空")
            if shot.in_tc >= shot.out_tc:
                errors.append(f"shot[{i}] in_tc({shot.in_tc}) >= out_tc({shot.out_tc})")
            if shot.duration <= 0:
                errors.append(f"shot[{i}] duration <= 0")
            if shot.speed_curve:
                # 检查变速曲线覆盖完整性
                if shot.speed_curve[0].start > 0.01:
                    errors.append(f"shot[{i}] speed_curve未从0开始")
                if shot.speed_curve[-1].end < 0.99:
                    errors.append(f"shot[{i}] speed_curve未覆盖到1.0")
            total_duration += shot.duration
        # 时长偏差检查
        if self.metadata.duration_target > 0:
            deviation = abs(total_duration - self.metadata.duration_target)
            if deviation > self.metadata.duration_target * 0.2:
                errors.append(f"总时长{total_duration:.1f}s与目标{self.metadata.duration_target:.1f}s偏差>20%")
        return errors

    # ---------------- 统计 ----------------

    def summary(self) -> dict:
        """生成ShotScript统计摘要"""
        ips = {}
        moods = {}
        total_duration = 0.0
        for shot in self.shots:
            ips[shot.ip] = ips.get(shot.ip, 0) + 1
            moods[shot.mood] = moods.get(shot.mood, 0) + 1
            total_duration += shot.duration
        return {
            "shot_count": len(self.shots),
            "total_duration": round(total_duration, 2),
            "ip_distribution": ips,
            "mood_distribution": moods,
            "has_text_overlay": sum(1 for s in self.shots if s.text_overlay),
            "has_cdl": sum(1 for s in self.shots if s.cdl),
            "has_lut": sum(1 for s in self.shots if s.lut),
        }


# ---------------- 便捷构造 ----------------

def create_shot_script(
    title: str = "",
    bgm: str = "",
    theme: str = "",
    duration_target: float = 0.0,
) -> ShotScript:
    """创建空ShotScript"""
    return ShotScript(
        metadata=ShotScriptMetadata(
            title=title,
            bgm=bgm,
            theme=theme,
            duration_target=duration_target,
            created=datetime.now().isoformat(),
            director_version="1.0",
        )
    )


# ---------------- CLI ----------------

if __name__ == "__main__":
    # 自检: 构造示例ShotScript并校验
    script = create_shot_script(
        title="测试镜头脚本",
        bgm="test_bgm.mp3",
        theme="高燃混剪",
        duration_target=90.0,
    )
    # 添加示例镜头
    shot1 = ShotUnit(
        shot_id=1,
        source_video="BV1Hf4y1r7qT_无限滑板前方高燃.mp4",
        in_tc=10.5,
        out_tc=15.2,
        duration=4.7,
        speed_curve=[SpeedSegment(0.0, 1.0, 1.0)],
        ip="无限滑板",
        characters=[],
        mood="intense",
        scene_type="action",
        aesthetic_score=0.85,
        rhythm_score=0.92,
    )
    script.shots.append(shot1)

    # 校验
    errors = script.validate()
    print(f"ShotScript自检: {len(script.shots)}镜头 | 校验{'通过' if not errors else '失败'}")
    if errors:
        for e in errors:
            print(f"  ❌ {e}")
    else:
        print(f"  摘要: {script.summary()}")
        print(f"  JSON前200字: {script.to_json()[:200]}...")
