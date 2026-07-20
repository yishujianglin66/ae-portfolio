"""
生成完整效果目录 - effect_catalog.json
====================================
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger


def main():
    """主函数。"""
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )

    start_time = time.time()

    logger.info("=" * 60)
    logger.info("生成效果完整目录 - effect_catalog.json")
    logger.info("=" * 60)

    from knowledge_base.kb_scanner import KBScanner

    scanner = KBScanner()

    logger.info("")
    logger.info("[1/3] 扫描知识库...")
    kb_effects = scanner.scan_knowledge_base()
    logger.info(f"  知识库效果数: {len(kb_effects)}")

    logger.info("")
    logger.info("[2/3] 生成模拟插件效果...")
    scanner._generate_plugin_effects()
    total_effects = len(scanner._effects)
    logger.info(f"  总效果数: {total_effects}")

    logger.info("")
    logger.info("[3/3] 生成 effect_catalog.json...")

    effect_list = []
    for key, effect in scanner._effects.items():
        effect_dict = {
            "name": effect.name,
            "match_name": effect.match_name,
            "category": effect.category,
            "plugin_package": effect.plugin_package,
            "description": effect.description,
            "usage_scenarios": effect.usage_scenarios,
            "source": effect.source,
            "confidence": effect.confidence,
        }
        effect_list.append(effect_dict)

    stats = scanner.get_statistics()

    catalog = {
        "version": "1.0.0",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_effects": total_effects,
        "total_categories": len(stats["by_category"]),
        "total_plugin_packages": len(stats["by_plugin_package"]),
        "statistics": stats,
        "effects": effect_list,
    }

    output_path = PROJECT_ROOT / "knowledge_base" / "effect_catalog.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2)

    file_size = output_path.stat().st_size
    elapsed = time.time() - start_time

    logger.info("")
    logger.info("=" * 60)
    logger.info("生成完成")
    logger.info("=" * 60)
    logger.info(f"  输出文件: {output_path}")
    logger.info(f"  文件大小: {round(file_size / 1024, 2)} KB")
    logger.info(f"  效果总数: {total_effects}")
    logger.info(f"  分类数: {len(stats['by_category'])}")
    logger.info(f"  插件包数: {len(stats['by_plugin_package'])}")
    logger.info(f"  耗时: {round(elapsed, 2)} 秒")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
