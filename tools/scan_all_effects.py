"""
一键扫描所有效果 - 生成完整效果目录
=====================================

扫描插件 + 知识库 + 生成完整效果清单，输出统计信息。

用法：
    python tools/scan_all_effects.py [--output OUTPUT] [--format json|csv|both]
    python tools/scan_all_effects.py --stats-only
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger


def setup_logging() -> None:
    """配置日志输出。"""
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan>",
    )


def scan_all_effects(
    output_path: str = "",
    export_format: str = "json",
    stats_only: bool = False,
) -> dict[str, Any]:
    """一键扫描所有效果。

    Args:
        output_path: 输出文件路径
        export_format: 导出格式（json/csv/both）
        stats_only: 只输出统计信息

    Returns:
        统计信息字典
    """
    start_time = time.time()

    logger.info("=" * 60)
    logger.info("AE 效果全量扫描 - 开始")
    logger.info("=" * 60)

    from knowledge_base.kb_loader import KnowledgeBaseLoader
    from knowledge_base.kb_scanner import KBScanner

    scanner = KBScanner()

    logger.info("")
    logger.info("[1/4] 扫描知识库...")
    kb_effects = scanner.scan_knowledge_base()
    logger.info(f"  知识库效果数: {len(kb_effects)}")

    logger.info("")
    logger.info("[2/4] 扫描插件目录...")
    plugin_packages = scanner.scan_plugins(generate_missing=True)
    total_plugin_effects = sum(len(pkg.effects) for pkg in plugin_packages.values())
    logger.info(f"  插件包数量: {len(plugin_packages)}")
    logger.info(f"  插件效果数: {total_plugin_effects}")

    logger.info("")
    logger.info("[3/4] 加载知识库加载器并生成完整信息...")
    loader = KnowledgeBaseLoader.get_instance()
    full_effects = loader.load_plugin_effects(generate_missing=True)
    logger.info(f"  完整效果总数: {len(full_effects)}")

    logger.info("")
    logger.info("[4/4] 生成效果分类统计...")

    category_stats: dict[str, int] = {}
    plugin_stats: dict[str, int] = {}
    source_stats: dict[str, int] = {}

    for key, effect in full_effects.items():
        cat = effect.category or "other"
        category_stats[cat] = category_stats.get(cat, 0) + 1

        pkg = effect.plugin_package or "Unknown"
        plugin_stats[pkg] = plugin_stats.get(pkg, 0) + 1

        src = effect.source or "unknown"
        source_stats[src] = source_stats.get(src, 0) + 1

    elapsed = time.time() - start_time

    stats = {
        "total_effects": len(full_effects),
        "plugin_packages": len(plugin_packages),
        "categories": len(category_stats),
        "by_category": dict(sorted(category_stats.items(), key=lambda x: -x[1])),
        "by_plugin": dict(sorted(plugin_stats.items(), key=lambda x: -x[1])),
        "by_source": dict(sorted(source_stats.items(), key=lambda x: -x[1])),
        "elapsed_seconds": round(elapsed, 2),
    }

    logger.info("")
    logger.info("=" * 60)
    logger.info("扫描完成 - 统计汇总")
    logger.info("=" * 60)
    logger.info(f"  效果总数: {stats['total_effects']}")
    logger.info(f"  插件包数: {stats['plugin_packages']}")
    logger.info(f"  分类数: {stats['categories']}")
    logger.info(f"  耗时: {stats['elapsed_seconds']} 秒")
    logger.info("")

    logger.info("按分类统计:")
    for cat, count in stats["by_category"].items():
        pct = round(count / stats["total_effects"] * 100, 1)
        logger.info(f"  {cat:15s}: {count:5d} ({pct:5.1f}%)")

    logger.info("")
    logger.info("按来源统计:")
    for src, count in stats["by_source"].items():
        pct = round(count / stats["total_effects"] * 100, 1)
        logger.info(f"  {src:15s}: {count:5d} ({pct:5.1f}%)")

    logger.info("")
    logger.info("按插件包统计 (Top 15):")
    for i, (pkg, count) in enumerate(list(stats["by_plugin"].items())[:15]):
        pct = round(count / stats["total_effects"] * 100, 1)
        logger.info(f"  {i+1:2d}. {pkg:35s}: {count:5d} ({pct:5.1f}%)")

    if not stats_only:
        if not output_path:
            output_path = str(PROJECT_ROOT / "knowledge_base" / "effect_catalog.json")

        logger.info("")
        logger.info("=" * 60)
        logger.info("导出效果目录")
        logger.info("=" * 60)

        if export_format in ("json", "both"):
            json_path = output_path if output_path.endswith(".json") else output_path + ".json"
            _export_json(full_effects, json_path)
            logger.info(f"  JSON 导出: {json_path}")

        if export_format in ("csv", "both"):
            csv_path = output_path if output_path.endswith(".csv") else output_path + ".csv"
            _export_csv(full_effects, csv_path)
            logger.info(f"  CSV 导出: {csv_path}")

    logger.info("")
    logger.info("=" * 60)
    logger.info(f"效果覆盖率目标: 5000+  →  当前: {stats['total_effects']}")
    if stats["total_effects"] >= 5000:
        logger.success("✓ 已达到 5000+ 效果覆盖率目标!")
    else:
        logger.warning(f"✗ 距离目标还差 {5000 - stats['total_effects']} 个效果")
    logger.info("=" * 60)

    return stats


def _export_json(effects: dict[str, Any], output_path: str) -> None:
    """导出 JSON 格式。"""
    data = []
    for key, effect in effects.items():
        data.append({
            "name": effect.name,
            "match_name": effect.match_name,
            "category": effect.category,
            "plugin_package": effect.plugin_package,
            "description": effect.description,
            "params": effect.params,
            "usage_scenarios": effect.usage_scenarios,
            "default_presets": effect.default_presets,
            "source": effect.source,
            "confidence": effect.confidence,
        })

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _export_csv(effects: dict[str, Any], output_path: str) -> None:
    """导出 CSV 格式。"""
    import csv

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            "序号", "效果名称", "MatchName", "分类", "插件包",
            "描述", "使用场景", "来源", "置信度"
        ])

        for i, (key, effect) in enumerate(effects.items(), 1):
            writer.writerow([
                i,
                effect.name,
                effect.match_name,
                effect.category,
                effect.plugin_package,
                effect.description,
                ", ".join(effect.usage_scenarios),
                effect.source,
                effect.confidence,
            ])


def main() -> None:
    """主函数。"""
    setup_logging()

    import argparse

    parser = argparse.ArgumentParser(
        description="AE 效果全量扫描工具 - 生成 5000+ 效果目录",
    )
    parser.add_argument(
        "--output", "-o",
        default="",
        help="输出文件路径 (默认: knowledge_base/effect_catalog.json)",
    )
    parser.add_argument(
        "--format", "-f",
        choices=["json", "csv", "both"],
        default="json",
        help="导出格式 (默认: json)",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="只输出统计信息，不导出文件",
    )

    args = parser.parse_args()

    try:
        scan_all_effects(
            output_path=args.output,
            export_format=args.format,
            stats_only=args.stats_only,
        )
    except Exception as e:
        logger.error(f"扫描失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
