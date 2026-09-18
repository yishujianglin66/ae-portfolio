#!/usr/bin/env python3
"""
风格分类数据集构建器 - 从风格卡片生成训练数据
================================================
将 data/style_cards/*.json 转换为 JSONL 格式的风格分类训练集，
用于 LocalModelAdapter (BGE-Small-ZH / BGE-M3) 的风格检索与分类。

输出格式 (JSONL):
    {"text": "风格描述文本", "label": "style_id", "features": {...}, "source": "style_card"}
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STYLE_CARDS_DIR = PROJECT_ROOT / "data" / "style_cards"
STYLE_TEMPLATES_DIR = PROJECT_ROOT / "data" / "style_templates"
OUTPUT_DIR = PROJECT_ROOT / "data" / "style_dataset"


class StyleDatasetBuilder:
    """风格分类数据集构建器"""

    def __init__(self):
        self.samples: list[dict[str, Any]] = []

    def load_style_cards(self) -> list[dict[str, Any]]:
        """加载所有风格卡片"""
        cards = []
        if not STYLE_CARDS_DIR.exists():
            logger.warning(f"风格卡片目录不存在: {STYLE_CARDS_DIR}")
            return cards

        for fp in sorted(STYLE_CARDS_DIR.glob("*.json")):
            try:
                card = json.loads(fp.read_text(encoding="utf-8"))
                card["_source_file"] = fp.name
                cards.append(card)
            except Exception as e:
                logger.error(f"加载风格卡片失败 {fp.name}: {e}")

        logger.info(f"加载 {len(cards)} 个风格卡片")
        return cards

    def card_to_text(self, card: dict[str, Any]) -> str:
        """将风格卡片转换为可嵌入的文本描述"""
        parts = []

        # 名称和描述
        name = card.get("name", card.get("style_id", "unknown"))
        desc = card.get("description", "")
        parts.append(f"风格: {name}")
        if desc:
            parts.append(f"描述: {desc}")

        # 三旋钮参数
        vv = card.get("visual_variance")
        mi = card.get("motion_intensity")
        id_ = card.get("information_density")
        if vv is not None:
            parts.append(f"视觉变化度: {vv}/10")
        if mi is not None:
            parts.append(f"运动强度: {mi}/10")
        if id_ is not None:
            parts.append(f"信息密度: {id_}/10")

        # 运镜偏好
        preferred = card.get("preferred_cameras", [])
        if preferred:
            parts.append(f"推荐运镜: {', '.join(preferred)}")

        forbidden = card.get("forbidden_cameras", [])
        if forbidden:
            parts.append(f"禁用运镜: {', '.join(forbidden)}")

        # 反模式
        anti = card.get("anti_patterns", [])
        if anti:
            anti_text = "; ".join(
                f"{a.get('rule', '')}: {a.get('detail', '')}" for a in anti
            )
            parts.append(f"反模式: {anti_text}")

        # 调色参数
        cg = card.get("color_grade_params", [])
        if cg:
            effects = [e.get("effect", "") for e in cg]
            parts.append(f"调色效果: {', '.join(effects)}")

        # 粒子预设
        pp = card.get("particle_presets", [])
        if pp:
            parts.append(f"粒子预设: {', '.join(pp)}")

        # 文字特效
        tfx = card.get("text_fx", [])
        if tfx:
            engines = [t.get("engine", "") for t in tfx]
            parts.append(f"文字特效引擎: {', '.join(engines)}")

        return " | ".join(parts)

    def extract_features(self, card: dict[str, Any]) -> dict[str, Any]:
        """提取数值特征向量"""
        return {
            "visual_variance": card.get("visual_variance", 0),
            "motion_intensity": card.get("motion_intensity", 0),
            "information_density": card.get("information_density", 0),
            "target_beat_alignment": card.get("target_beat_alignment", 0.0),
            "target_camera_diversity": card.get("target_camera_diversity", 0.0),
            "max_material_reuse": card.get("max_material_reuse", 0.0),
            "min_temporal_energy": card.get("min_temporal_energy", 0.0),
            "num_preferred_cameras": len(card.get("preferred_cameras", [])),
            "num_anti_patterns": len(card.get("anti_patterns", [])),
            "num_color_effects": len(card.get("color_grade_params", [])),
            "num_particle_presets": len(card.get("particle_presets", [])),
            "num_text_fx": len(card.get("text_fx", [])),
        }

    def build_from_cards(self) -> list[dict[str, Any]]:
        """从风格卡片构建数据集"""
        cards = self.load_style_cards()
        samples = []

        for card in cards:
            style_id = card.get("style_id", "unknown")
            text = self.card_to_text(card)
            features = self.extract_features(card)

            # 主样本
            samples.append({
                "text": text,
                "label": style_id,
                "features": features,
                "source": "style_card",
                "source_file": card.get("_source_file", ""),
            })

            # 增强样本：仅描述
            desc = card.get("description", "")
            if desc:
                samples.append({
                    "text": f"风格: {card.get('name', style_id)} | 描述: {desc}",
                    "label": style_id,
                    "features": features,
                    "source": "style_card_desc_only",
                    "source_file": card.get("_source_file", ""),
                })

            # 增强样本：三旋钮 + 运镜
            knob_text = (
                f"风格: {card.get('name', style_id)} | "
                f"视觉变化度: {features['visual_variance']}/10 | "
                f"运动强度: {features['motion_intensity']}/10 | "
                f"信息密度: {features['information_density']}/10 | "
                f"推荐运镜: {', '.join(card.get('preferred_cameras', []))}"
            )
            samples.append({
                "text": knob_text,
                "label": style_id,
                "features": features,
                "source": "style_card_knobs",
                "source_file": card.get("_source_file", ""),
            })

        self.samples = samples
        logger.info(f"从风格卡片构建 {len(samples)} 个样本 ({len(cards)} 风格 × 3 增强)")
        return samples

    def build_from_templates(self) -> list[dict[str, Any]]:
        """从风格模板构建额外样本"""
        tpl_path = STYLE_TEMPLATES_DIR / "templates.json"
        if not tpl_path.exists():
            logger.info("风格模板文件不存在，跳过")
            return []

        try:
            tpl_data = json.loads(tpl_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"加载风格模板失败: {e}")
            return []

        samples = []
        templates = tpl_data if isinstance(tpl_data, list) else tpl_data.get("templates", {})

        # templates 可能是 dict (key=style_id) 或 list
        if isinstance(templates, dict):
            items = [(sid, t) for sid, t in templates.items()]
        else:
            items = [(t.get("style_id", t.get("name", "unknown")), t) for t in templates]

        for style_id, tpl in items:
            if not isinstance(tpl, dict):
                continue
            text_parts = [f"模板风格: {tpl.get('name', style_id)}"]

            if tpl.get("desc"):
                text_parts.append(f"描述: {tpl['desc']}")
            if tpl.get("mood"):
                text_parts.append(f"氛围: {', '.join(tpl['mood'])}")
            if tpl.get("color_grade"):
                effects = [e.get("effect", "") for e in tpl["color_grade"]]
                text_parts.append(f"调色: {', '.join(effects)}")
            if tpl.get("particles"):
                ptypes = [p.get("type", p.get("action", "")) for p in tpl["particles"]]
                text_parts.append(f"粒子: {', '.join(ptypes)}")
            if tpl.get("text_fx"):
                engines = [t.get("engine", "") for t in tpl["text_fx"]]
                text_parts.append(f"文字引擎: {', '.join(engines)}")

            samples.append({
                "text": " | ".join(text_parts),
                "label": style_id,
                "features": {},
                "source": "style_template",
                "source_file": "templates.json",
            })

        logger.info(f"从风格模板构建 {len(samples)} 个样本")
        return samples

    def save(self, filename: str = "style_dataset.jsonl") -> str:
        """保存数据集"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        filepath = OUTPUT_DIR / filename

        with open(filepath, "w", encoding="utf-8") as f:
            for sample in self.samples:
                f.write(json.dumps(sample, ensure_ascii=False) + "\n")

        logger.info(f"风格数据集已保存: {filepath} ({len(self.samples)} 样本)")
        return str(filepath)

    def save_stats(self) -> str:
        """保存统计信息"""
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        label_counts: dict[str, int] = {}
        source_counts: dict[str, int] = {}
        for s in self.samples:
            label = s.get("label", "unknown")
            source = s.get("source", "unknown")
            label_counts[label] = label_counts.get(label, 0) + 1
            source_counts[source] = source_counts.get(source, 0) + 1

        stats = {
            "total_samples": len(self.samples),
            "unique_styles": len(label_counts),
            "labels": label_counts,
            "sources": source_counts,
        }

        filepath = OUTPUT_DIR / "style_dataset_stats.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

        logger.info(f"统计信息已保存: {filepath}")
        return str(filepath)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    builder = StyleDatasetBuilder()

    logger.info("=== 从风格卡片构建 ===")
    builder.build_from_cards()

    logger.info("=== 从风格模板构建 ===")
    tpl_samples = builder.build_from_templates()
    builder.samples.extend(tpl_samples)

    logger.info(f"=== 总计: {len(builder.samples)} 样本 ===")

    builder.save()
    builder.save_stats()

    logger.info("=== 风格数据集构建完成 ===")


if __name__ == "__main__":
    main()
