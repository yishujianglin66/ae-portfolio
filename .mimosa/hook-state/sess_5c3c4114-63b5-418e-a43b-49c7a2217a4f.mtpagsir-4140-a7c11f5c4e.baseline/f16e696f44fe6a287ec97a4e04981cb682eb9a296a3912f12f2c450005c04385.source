"""
测试效果总数 - 快速验证 5000+ 效果目标
=====================================
"""
from __future__ import annotations

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
    logger.info("效果数量测试 - 验证 5000+ 目标")
    logger.info("=" * 60)

    from knowledge_base.kb_scanner import KBScanner

    scanner = KBScanner()

    logger.info("")
    logger.info("[1/3] 扫描知识库...")
    kb_effects = scanner.scan_knowledge_base()
    logger.info(f"  知识库效果数: {len(kb_effects)}")

    logger.info("")
    logger.info("[2/3] 生成模拟插件效果...")

    plugin_effects_db = scanner._get_plugin_effects_database()
    total_generated = 0
    plugin_stats = {}

    for pkg_name, effect_list in plugin_effects_db.items():
        count = len(effect_list)
        total_generated += count
        plugin_stats[pkg_name] = count
        logger.debug(f"  {pkg_name}: {count} 个")

    logger.info(f"  生成的插件效果总数: {total_generated}")

    logger.info("")
    logger.info("[3/3] 合并统计...")

    scanner._generate_plugin_effects()
    total_effects = len(scanner._effects)

    category_stats = {}
    source_stats = {}

    for key, effect in scanner._effects.items():
        cat = effect.category or "other"
        category_stats[cat] = category_stats.get(cat, 0) + 1

        src = effect.source or "unknown"
        source_stats[src] = source_stats.get(src, 0) + 1

    elapsed = time.time() - start_time

    logger.info("")
    logger.info("=" * 60)
    logger.info("统计汇总")
    logger.info("=" * 60)
    logger.info(f"  效果总数: {total_effects}")
    logger.info(f"  分类数: {len(category_stats)}")
    logger.info(f"  插件包数: {len(plugin_stats)}")
    logger.info(f"  耗时: {round(elapsed, 2)} 秒")
    logger.info("")

    logger.info("按分类统计:")
    sorted_cats = sorted(category_stats.items(), key=lambda x: -x[1])
    for cat, count in sorted_cats:
        pct = round(count / total_effects * 100, 1)
        logger.info(f"  {cat:15s}: {count:5d} ({pct:5.1f}%)")

    logger.info("")
    logger.info("按来源统计:")
    for src, count in sorted(source_stats.items(), key=lambda x: -x[1]):
        pct = round(count / total_effects * 100, 1)
        logger.info(f"  {src:15s}: {count:5d} ({pct:5.1f}%)")

    logger.info("")
    logger.info("按插件包统计 (Top 15):")
    sorted_pkgs = sorted(plugin_stats.items(), key=lambda x: -x[1])
    for i, (pkg, count) in enumerate(sorted_pkgs[:15]):
        pct = round(count / total_generated * 100, 1)
        logger.info(f"  {i+1:2d}. {pkg:35s}: {count:5d} ({pct:5.1f}%)")

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"效果覆盖率目标: 5000+  →  当前: {total_effects}")
    if total_effects >= 5000:
        logger.success("✓ 已达到 5000+ 效果覆盖率目标!")
    else:
        logger.warning(f"✗ 距离目标还差 {5000 - total_effects} 个效果")
    logger.info("=" * 60)

    return total_effects


if __name__ == "__main__":
    main()
