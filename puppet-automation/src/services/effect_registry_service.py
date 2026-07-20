"""
效果注册服务 - 统一管理 AE 效果映射、分类、推荐
=============================================

提供效果注册、分类搜索、场景推荐、导出等功能。
整合知识库效果 + 插件效果 + 硬编码映射，实现 5000+ 效果覆盖。

效果分类体系：
- color: 颜色/调色类
- blur: 模糊类
- distort: 扭曲类
- generate: 生成类
- keying: 抠像类
- stylize: 风格化类
- transition: 过渡/转场类
- particle: 粒子类
- light: 光效/发光类
- audio: 音频类
- matte: 遮罩类
- noise: 噪点类
- text: 文字类
- 3d: 三维类
- tracking: 追踪类
- utility: 实用工具类
- other: 其他类
"""
from __future__ import annotations

import json
import csv
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class EffectEntry:
    """效果条目。"""
    name: str
    match_name: str = ""
    category: str = "other"
    plugin_package: str = ""
    description: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    usage_scenarios: List[str] = field(default_factory=list)
    default_presets: List[Dict[str, Any]] = field(default_factory=list)
    source: str = ""
    confidence: float = 0.8

    def get(self, key: str, default: Any = "") -> Any:
        """兼容字典访问方式。"""
        if hasattr(self, key):
            return getattr(self, key)
        return default

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典。"""
        return {
            "name": self.name,
            "match_name": self.match_name,
            "display_name": self.name,
            "category": self.category,
            "plugin_package": self.plugin_package,
            "description": self.description,
            "params": self.params,
            "usage_scenarios": self.usage_scenarios,
            "default_presets": self.default_presets,
            "source": self.source,
            "confidence": self.confidence,
        }


class EffectRegistryService:
    """效果注册服务。

    统一管理所有效果的注册、查询、搜索和推荐。
    """

    def __init__(self) -> None:
        """初始化效果注册服务。"""
        self._effects: Dict[str, EffectEntry] = {}
        self._category_index: Dict[str, List[str]] = {}
        self._plugin_index: Dict[str, List[str]] = {}
        self._scenario_index: Dict[str, List[str]] = {}

        self._initialized = False
        logger.info("EffectRegistryService 初始化完成")

    # ========================================================================
    # 初始化与加载
    # ========================================================================

    def initialize(self, load_knowledge_base: bool = True) -> int:
        """初始化效果注册表。

        从硬编码映射、知识库、插件效果等多来源加载效果。

        Args:
            load_knowledge_base: 是否加载知识库效果

        Returns:
            加载的效果总数
        """
        if self._initialized:
            return len(self._effects)

        logger.info("开始初始化效果注册表...")

        count = 0

        try:
            from effect_registry import (
                KEYWORD_TO_EFFECT_MAP,
                EFFECT_PARAMS_DB,
                EFFECT_CATEGORIES,
            )

            for keyword, match_name in KEYWORD_TO_EFFECT_MAP.items():
                if match_name not in self._effects:
                    entry = EffectEntry(
                        name=keyword,
                        match_name=match_name,
                        category="other",
                        source="hardcoded",
                        confidence=0.9,
                    )

                    if match_name in EFFECT_PARAMS_DB:
                        param_data = EFFECT_PARAMS_DB[match_name]
                        entry.params = param_data.get("params", {})
                        entry.category = param_data.get("category", "other")

                    self._effects[match_name.lower()] = entry
                    count += 1

            for category, match_names in EFFECT_CATEGORIES.items():
                for mn in match_names:
                    key = mn.lower()
                    if key in self._effects:
                        self._effects[key].category = category

        except ImportError as e:
            logger.warning(f"硬编码效果映射加载失败: {e}")

        if load_knowledge_base:
            kb_count = self._load_from_knowledge_base()
            count += kb_count

        self._rebuild_indexes()
        self._initialized = True

        logger.info(f"效果注册表初始化完成，共 {len(self._effects)} 个效果")
        return len(self._effects)

    def _load_from_knowledge_base(self) -> int:
        """从知识库加载效果。

        Returns:
            新增的效果数量
        """
        try:
            import sys
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            sys.path.insert(0, str(project_root))

            from knowledge_base.kb_loader import KnowledgeBaseLoader

            loader = KnowledgeBaseLoader.get_instance()
            plugin_effects = loader.load_plugin_effects(generate_missing=True)

            added = 0
            for key, effect_info in plugin_effects.items():
                if key not in self._effects:
                    entry = EffectEntry(
                        name=effect_info.name,
                        match_name=effect_info.match_name,
                        category=effect_info.category,
                        plugin_package=effect_info.plugin_package,
                        description=effect_info.description,
                        params=effect_info.params,
                        usage_scenarios=effect_info.usage_scenarios,
                        default_presets=effect_info.default_presets,
                        source=effect_info.source,
                        confidence=effect_info.confidence,
                    )
                    self._effects[key] = entry
                    added += 1
                else:
                    existing = self._effects[key]
                    if effect_info.description and not existing.description:
                        existing.description = effect_info.description
                    if effect_info.params and not existing.params:
                        existing.params = effect_info.params
                    if effect_info.usage_scenarios:
                        for s in effect_info.usage_scenarios:
                            if s not in existing.usage_scenarios:
                                existing.usage_scenarios.append(s)
                    if effect_info.plugin_package and not existing.plugin_package:
                        existing.plugin_package = effect_info.plugin_package

            logger.info(f"知识库效果加载完成，新增 {added} 个")
            return added

        except Exception as e:
            logger.warning(f"知识库效果加载失败: {e}")
            return 0

    def _rebuild_indexes(self) -> None:
        """重建分类索引、插件索引和场景索引。"""
        self._category_index = {}
        self._plugin_index = {}
        self._scenario_index = {}

        for key, entry in self._effects.items():
            cat = entry.category or "other"
            if cat not in self._category_index:
                self._category_index[cat] = []
            self._category_index[cat].append(key)

            pkg = entry.plugin_package or "Unknown"
            if pkg not in self._plugin_index:
                self._plugin_index[pkg] = []
            self._plugin_index[pkg].append(key)

            for scenario in entry.usage_scenarios:
                s_key = scenario.lower()
                if s_key not in self._scenario_index:
                    self._scenario_index[s_key] = []
                self._scenario_index[s_key].append(key)

        logger.debug(
            f"索引重建完成: {len(self._category_index)} 个分类, "
            f"{len(self._plugin_index)} 个插件包, "
            f"{len(self._scenario_index)} 个场景"
        )

    # ========================================================================
    # 公共 API - 效果注册
    # ========================================================================

    def register_plugin_effects(
        self,
        effects: List[Dict[str, Any]],
        plugin_package: str = "",
    ) -> int:
        """批量注册插件效果。

        Args:
            effects: 效果列表，每个效果为字典
            plugin_package: 插件包名称

        Returns:
            新增的效果数量
        """
        if not self._initialized:
            self.initialize()

        added = 0

        for effect_data in effects:
            name = effect_data.get("name", "")
            match_name = effect_data.get("match_name", name)
            key = match_name.lower()

            if not name:
                continue

            if key not in self._effects:
                entry = EffectEntry(
                    name=name,
                    match_name=match_name,
                    category=effect_data.get("category", "other"),
                    plugin_package=plugin_package or effect_data.get("plugin_package", ""),
                    description=effect_data.get("description", ""),
                    params=effect_data.get("params", {}),
                    usage_scenarios=effect_data.get("usage_scenarios", []),
                    default_presets=effect_data.get("default_presets", []),
                    source="plugin",
                    confidence=effect_data.get("confidence", 0.7),
                )
                self._effects[key] = entry
                added += 1

        if added > 0:
            self._rebuild_indexes()

        logger.info(f"批量注册插件效果完成，新增 {added} 个")
        return added

    # ========================================================================
    # 公共 API - 效果查询
    # ========================================================================

    def get_effect(self, match_name: str) -> Optional[EffectEntry]:
        """根据 matchName 获取效果信息。

        Args:
            match_name: 效果 matchName

        Returns:
            EffectEntry 或 None
        """
        if not self._initialized:
            self.initialize()

        return self._effects.get(match_name.lower())

    def get_all_effects(self) -> List[EffectEntry]:
        """获取所有效果。

        Returns:
            EffectEntry 列表
        """
        if not self._initialized:
            self.initialize()

        return list(self._effects.values())

    def get_effect_count(self) -> int:
        """获取效果总数。

        Returns:
            效果总数
        """
        if not self._initialized:
            self.initialize()

        return len(self._effects)

    # ========================================================================
    # 公共 API - 分类搜索
    # ========================================================================

    def search_by_category(self, category: str) -> List[EffectEntry]:
        """按分类搜索效果。

        Args:
            category: 效果分类

        Returns:
            EffectEntry 列表
        """
        if not self._initialized:
            self.initialize()

        keys = self._category_index.get(category.lower(), [])
        return [self._effects[k] for k in keys if k in self._effects]

    def get_categories(self) -> List[str]:
        """获取所有分类。

        Returns:
            分类名称列表
        """
        if not self._initialized:
            self.initialize()

        return list(self._category_index.keys())

    def get_category_stats(self) -> Dict[str, int]:
        """获取分类统计。

        Returns:
            分类名称 -> 效果数量 字典
        """
        if not self._initialized:
            self.initialize()

        return {cat: len(keys) for cat, keys in self._category_index.items()}

    # ========================================================================
    # 公共 API - 场景推荐
    # ========================================================================

    def get_recommended_effects(
        self,
        scenario: str,
        limit: int = 10,
    ) -> List[EffectEntry]:
        """根据场景推荐效果。

        Args:
            scenario: 使用场景（如"调色"、"粒子特效"等）
            limit: 返回数量上限

        Returns:
            推荐的 EffectEntry 列表
        """
        if not self._initialized:
            self.initialize()

        scenario_lower = scenario.lower()
        matched_keys = set()

        for s_key, effect_keys in self._scenario_index.items():
            if scenario_lower in s_key or s_key in scenario_lower:
                matched_keys.update(effect_keys)

        if not matched_keys:
            keywords = scenario_lower.split()
            for keyword in keywords:
                for s_key, effect_keys in self._scenario_index.items():
                    if keyword in s_key:
                        matched_keys.update(effect_keys)
                        break

        if not matched_keys:
            category_map = {
                "调色": "color",
                "颜色": "color",
                "模糊": "blur",
                "扭曲": "distort",
                "粒子": "particle",
                "光效": "light",
                "发光": "light",
                "转场": "transition",
                "抠像": "keying",
                "风格化": "stylize",
                "文字": "text",
                "3d": "3d",
                "三维": "3d",
                "追踪": "tracking",
                "音频": "audio",
                "噪点": "noise",
                "遮罩": "matte",
            }

            for keyword, category in category_map.items():
                if keyword in scenario_lower:
                    cat_keys = self._category_index.get(category, [])
                    matched_keys.update(cat_keys[:limit])
                    break

        result = [self._effects[k] for k in matched_keys if k in self._effects]
        result.sort(key=lambda e: e.confidence, reverse=True)

        return result[:limit]

    # ========================================================================
    # 公共 API - 插件包查询
    # ========================================================================

    def get_plugin_packages(self) -> List[str]:
        """获取所有插件包名称。

        Returns:
            插件包名称列表
        """
        if not self._initialized:
            self.initialize()

        return list(self._plugin_index.keys())

    def get_effects_by_plugin(self, plugin_package: str) -> List[EffectEntry]:
        """按插件包获取效果。

        Args:
            plugin_package: 插件包名称

        Returns:
            EffectEntry 列表
        """
        if not self._initialized:
            self.initialize()

        keys = self._plugin_index.get(plugin_package, [])
        return [self._effects[k] for k in keys if k in self._effects]

    def get_plugin_stats(self) -> Dict[str, int]:
        """获取插件包统计。

        Returns:
            插件包名称 -> 效果数量 字典
        """
        if not self._initialized:
            self.initialize()

        return {pkg: len(keys) for pkg, keys in self._plugin_index.items()}

    # ========================================================================
    # 公共 API - 搜索
    # ========================================================================

    def search_effects(
        self,
        query: str = "",
        keyword: str = "",
        category: Optional[str] = None,
        plugin_package: Optional[str] = None,
        limit: int = 20,
    ) -> List[EffectEntry]:
        """搜索效果。

        按名称、描述、分类进行模糊搜索。

        Args:
            query: 搜索关键词（与 keyword 互斥，优先使用 query）
            keyword: 搜索关键词（query 的别名，向后兼容）
            category: 按分类过滤
            plugin_package: 按插件包过滤
            limit: 返回数量上限

        Returns:
            EffectEntry 列表
        """
        if not self._initialized:
            self.initialize()

        search_term = query or keyword
        query_lower = search_term.lower() if search_term else ""
        results = []

        for key, entry in self._effects.items():
            if category and entry.category.lower() != category.lower():
                continue
            if plugin_package and entry.plugin_package.lower() != plugin_package.lower():
                continue

            score = 0

            if query_lower:
                if query_lower in entry.name.lower():
                    score += 10
                if query_lower in entry.match_name.lower():
                    score += 8
                if query_lower in entry.description.lower():
                    score += 3
                if query_lower in entry.category.lower():
                    score += 5
                if query_lower in entry.plugin_package.lower():
                    score += 4

                for scenario in entry.usage_scenarios:
                    if query_lower in scenario.lower():
                        score += 3
                        break
            else:
                score = 1

            if score > 0:
                results.append((score, entry))

        results.sort(key=lambda x: x[0], reverse=True)
        return [entry for _, entry in results[:limit]]

    def get_scenarios(self) -> List[str]:
        """获取所有使用场景。

        Returns:
            场景名称列表
        """
        if not self._initialized:
            self.initialize()

        return list(self._scenario_index.keys())

    def get_effects_by_scenario(
        self,
        scenario: str,
        limit: int = 50,
    ) -> List[EffectEntry]:
        """根据场景获取效果。

        Args:
            scenario: 场景名称
            limit: 返回数量上限

        Returns:
            EffectEntry 列表
        """
        if not self._initialized:
            self.initialize()

        scenario_lower = scenario.lower()
        keys = self._scenario_index.get(scenario_lower, [])

        if not keys:
            # 模糊匹配
            for s_key, s_keys in self._scenario_index.items():
                if scenario_lower in s_key or s_key in scenario_lower:
                    keys = s_keys
                    break

        result = [self._effects[k] for k in keys if k in self._effects]
        result.sort(key=lambda e: e.confidence, reverse=True)
        return result[:limit]

    # ========================================================================
    # 公共 API - 导出
    # ========================================================================

    def export_effect_list(
        self,
        output_path: str | Path,
        format: str = "json",
    ) -> str:
        """导出效果清单。

        Args:
            output_path: 输出文件路径
            format: 导出格式（json/csv）

        Returns:
            输出文件路径
        """
        if not self._initialized:
            self.initialize()

        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)

        effects = self.get_all_effects()

        if format == "json":
            data = []
            for entry in effects:
                data.append({
                    "name": entry.name,
                    "match_name": entry.match_name,
                    "category": entry.category,
                    "plugin_package": entry.plugin_package,
                    "description": entry.description,
                    "params": entry.params,
                    "usage_scenarios": entry.usage_scenarios,
                    "default_presets": entry.default_presets,
                    "source": entry.source,
                    "confidence": entry.confidence,
                })

            output.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        elif format == "csv":
            with open(output, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "名称", "MatchName", "分类", "插件包",
                    "描述", "使用场景", "来源", "置信度"
                ])

                for entry in effects:
                    writer.writerow([
                        entry.name,
                        entry.match_name,
                        entry.category,
                        entry.plugin_package,
                        entry.description,
                        ", ".join(entry.usage_scenarios),
                        entry.source,
                        entry.confidence,
                    ])

        logger.info(f"效果清单已导出到: {output} ({format} 格式)")
        return str(output)

    # ========================================================================
    # 公共 API - 统计
    # ========================================================================

    def get_statistics(self) -> Dict[str, Any]:
        """获取效果统计信息。

        Returns:
            统计信息字典
        """
        if not self._initialized:
            self.initialize()

        return {
            "total": len(self._effects),
            "by_category": self.get_category_stats(),
            "by_plugin": self.get_plugin_stats(),
            "by_source": self._get_source_stats(),
            "categories": len(self._category_index),
            "plugin_packages": len(self._plugin_index),
        }

    def _get_source_stats(self) -> Dict[str, int]:
        """获取来源统计。"""
        stats: Dict[str, int] = {}
        for entry in self._effects.values():
            source = entry.source or "unknown"
            stats[source] = stats.get(source, 0) + 1
        return stats


_effect_registry_instance: Optional[EffectRegistryService] = None


def get_effect_registry() -> EffectRegistryService:
    """获取效果注册服务单例。

    Returns:
        EffectRegistryService 实例
    """
    global _effect_registry_instance
    if _effect_registry_instance is None:
        _effect_registry_instance = EffectRegistryService()
    return _effect_registry_instance
