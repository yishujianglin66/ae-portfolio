"""knowledge/style_card.py - 风格知识卡 schema

将风格模板从纯参数配方升级为结构化知识卡, 包含:
- 品味契约三旋钮(visual_variance/motion_intensity/information_density)
- 内容级质量目标(content_metrics 四指标)
- 运镜偏好池(与品味契约联动)
- 风格反模式(Anti-Pattern, 可机检)

用法:
    from knowledge.style_card import load_card, get_taste_profile

    card = load_card("amv_highenergy")
    taste = get_taste_profile("amv_highenergy")
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_CARD_DIR = Path(__file__).resolve().parent.parent / "data" / "style_cards"


@dataclass
class StyleCard:
    """风格知识卡 — 一个风格的完整治理结构。"""
    style_id: str
    name: str
    description: str = ""

    # 品味契约三旋钮
    visual_variance: int = 5
    motion_intensity: int = 5
    information_density: int = 5

    # 内容级质量目标 (content_metrics 四指标, 0-1)
    target_beat_alignment: float = 0.6
    target_camera_diversity: float = 0.5
    max_material_reuse: float = 0.3
    min_temporal_energy: float = 0.3

    # 运镜偏好
    preferred_cameras: List[str] = field(default_factory=list)
    forbidden_cameras: List[str] = field(default_factory=list)

    # 风格反模式 (可机检)
    anti_patterns: List[Dict[str, str]] = field(default_factory=list)

    # 关联的 AE 效果参数 (与 templates.json 对齐)
    color_grade_params: List[Dict[str, Any]] = field(default_factory=list)
    particle_presets: List[str] = field(default_factory=list)
    lut: Dict[str, Any] = field(default_factory=dict)   # {'theme': LUT主题, 'strength': 0-1}
    text_fx: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> StyleCard:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "style_id": self.style_id,
            "name": self.name,
            "description": self.description,
            "taste_profile": {
                "visual_variance": self.visual_variance,
                "motion_intensity": self.motion_intensity,
                "information_density": self.information_density,
            },
            "quality_targets": {
                "beat_alignment": self.target_beat_alignment,
                "camera_diversity": self.target_camera_diversity,
                "max_material_reuse": self.max_material_reuse,
                "min_temporal_energy": self.min_temporal_energy,
            },
            "camera_preferences": {
                "preferred": self.preferred_cameras,
                "forbidden": self.forbidden_cameras,
            },
            "anti_patterns": self.anti_patterns,
        }


def load_card(style_id: str) -> Optional[StyleCard]:
    """加载指定风格的知识卡。"""
    path = _CARD_DIR / f"{style_id}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return StyleCard.from_dict(data)
    except Exception as e:
        logger.warning(f"Failed to load style card {style_id}: {e}")
        return None


def list_cards() -> List[str]:
    """列出所有已注册的风格卡 ID。

    只返回符合 StyleCard 模式（含 style_id + name）的文件。
    目录里允许放非卡片的研究资产（如 handoff-2026-09-02 记录的
    beat_grammar_validated_v1.json——harvest_experience.py 按固定路径读取），
    它们不参与卡片注册与矩阵测试。
    """
    if not _CARD_DIR.exists():
        return []
    out = []
    for p in _CARD_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if isinstance(data, dict) and data.get("style_id") and data.get("name"):
            out.append(p.stem)
    return out


def get_taste_profile(style_id: str) -> Dict[str, int]:
    """快捷: 获取风格的品味三旋钮。"""
    card = load_card(style_id)
    if not card:
        return {"visual_variance": 5, "motion_intensity": 5, "information_density": 5}
    return {
        "visual_variance": card.visual_variance,
        "motion_intensity": card.motion_intensity,
        "information_density": card.information_density,
    }


def card_to_director_inputs(style_id: str) -> Dict[str, Any]:
    """把风格卡转换为导演输入 (taste_profile + style_spec)。

    这是风格卡 → 生产管线的消费桥 (2026-08-14 接线; 此前卡片仅被测试消费):
      ProductionDirector.render(style_id="amv_highenergy")
        → taste_profile 三旋钮 + 反模式
        → style_spec.camera_preferences (preferred/forbidden → T4 运镜池约束)

    Args:
        style_id: 风格卡 ID (data/style_cards/*.json)

    Returns:
        空 dict — 卡片不存在/加载失败 (调用方应回退默认品味)
    """
    card = load_card(style_id)
    if not card:
        return {}
    return {
        "taste_profile": {
            "visual_variance": card.visual_variance,
            "motion_intensity": card.motion_intensity,
            "information_density": card.information_density,
            "anti_patterns": [a.get("rule", "") for a in card.anti_patterns],
        },
        "style_spec": {
            "camera_preferences": {
                "preferred": list(card.preferred_cameras),
                "forbidden": list(card.forbidden_cameras),
            },
            "color_grade_params": list(card.color_grade_params),
            "particle_presets": list(card.particle_presets),
        },
    }


class StyleCardIntegration:
    """风格知识卡适配器 — 供 integration_registry 无参实例化。

    StyleCard 本身是需要 style_id/name 的数据类，不能直接被注册中心
    以 ``cls()`` 方式加载；本适配器遵循统一接口 (check_available /
    list_operations)，将全部风格卡暴露为只读查询操作。
    """

    TOOL_NAME = "style_card"
    SUPPORTED_OPERATIONS = {
        "list_cards": "列出全部已注册风格卡 ID",
        "load_card": "加载指定风格卡 (style_id)",
        "get_taste_profile": "获取风格品味三旋钮",
    }

    def check_available(self) -> bool:
        return len(list_cards()) > 0

    def list_operations(self) -> List[str]:
        return list(self.SUPPORTED_OPERATIONS.keys())

    def execute(self, op: str, params: Optional[Dict[str, Any]] = None):
        params = params or {}
        if op == "list_cards":
            return list_cards()
        if op == "load_card":
            card = load_card(params.get("style_id", ""))
            return card.to_dict() if card else None
        if op == "get_taste_profile":
            return get_taste_profile(params.get("style_id", ""))
        raise ValueError(f"Unknown operation: {op}")
