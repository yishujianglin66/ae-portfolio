"""
knowledge_base/kb_loader.py - 知识库门面 API (Layer 5)

单例类，整合 Layer 1-4 提供统一的知识加载接口。

用法：
    from knowledge_base.kb_loader import KnowledgeBaseLoader

    loader = KnowledgeBaseLoader.get_instance()
    effect_map = loader.get_effect_map()
    trans_map = loader.get_transition_map()
    presets = loader.get_color_presets()
    recipes = loader.get_style_recipes()
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from knowledge_base.types import (
    BlockType,
    MdBlock,
    EffectMapping,
    TransitionRecipe,
    ColorPreset,
    StyleRecipe,
)
from knowledge_base.md_parser import MdParser
from knowledge_base.table_extractor import TableExtractor
from knowledge_base.section_parser import SectionParser
from knowledge_base.kb_cache import KbCache
from knowledge_base.adapters.effect_adapter import EffectAdapter
from knowledge_base.adapters.transition_adapter import TransitionAdapter


# 默认知识库路径
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_KB_DIR = str(_PROJECT_ROOT / "10-风格化剪辑知识库")
_DEFAULT_CACHE_DIR = str(_PROJECT_ROOT / "data" / "kb_cache")


class KnowledgeBaseLoader:
    """知识库加载器 - 门面 API。

    单例模式，确保全库只解析一次。
    """

    _instance: Optional["KnowledgeBaseLoader"] = None

    def __init__(
        self,
        kb_dir: str = "",
        cache_dir: str = "",
    ) -> None:
        """初始化加载器。

        Args:
            kb_dir: 知识库目录路径（默认 10-风格化剪辑知识库/）
            cache_dir: 缓存目录路径（默认 data/kb_cache/）
        """
        self._kb_dir = kb_dir or _DEFAULT_KB_DIR
        self._cache_dir = cache_dir or _DEFAULT_CACHE_DIR

        self._parser = MdParser()
        self._table_extractor = TableExtractor()
        self._section_parser = SectionParser()
        self._effect_adapter = EffectAdapter()
        self._transition_adapter = TransitionAdapter()
        self._cache = KbCache(cache_dir=self._cache_dir)

        # 缓存解析结果
        self._file_blocks: Dict[str, List[MdBlock]] = {}
        self._effect_map: Optional[Dict[str, str]] = None
        self._transition_map: Optional[Dict[str, Dict[str, Any]]] = None
        self._color_presets: Optional[List[ColorPreset]] = None
        self._style_recipes: Optional[List[StyleRecipe]] = None

    @classmethod
    def get_instance(
        cls,
        kb_dir: str = "",
        cache_dir: str = "",
    ) -> "KnowledgeBaseLoader":
        """获取单例实例。

        Args:
            kb_dir: 知识库目录路径
            cache_dir: 缓存目录路径

        Returns:
            KnowledgeBaseLoader 实例
        """
        if cls._instance is None:
            cls._instance = cls(kb_dir=kb_dir, cache_dir=cache_dir)
        return cls._instance

    def list_files(self) -> List[str]:
        """列出知识库中所有 md 文件名。

        Returns:
            文件名列表
        """
        if not os.path.isdir(self._kb_dir):
            return []

        files: List[str] = []
        for name in sorted(os.listdir(self._kb_dir)):
            if name.endswith(".md"):
                files.append(name)
        return files

    def parse_file(self, filename: str) -> List[MdBlock]:
        """解析单个知识库文件。

        Args:
            filename: 文件名（相对于 kb_dir）

        Returns:
            MdBlock 列表
        """
        if filename in self._file_blocks:
            return self._file_blocks[filename]

        file_path = os.path.join(self._kb_dir, filename)
        if not os.path.isfile(file_path):
            return []

        # 检查缓存
        try:
            mtime = os.path.getmtime(file_path)
        except OSError:
            return []

        cached = self._cache.get(file_path, mtime=mtime)
        if cached is not None:
            # 从缓存恢复 MdBlock
            blocks = self._blocks_from_cache(cached)
            self._file_blocks[filename] = blocks
            return blocks

        # 解析文件
        blocks = self._parser.parse_file(file_path)
        self._file_blocks[filename] = blocks

        # 写入缓存
        cache_data = self._blocks_to_cache(blocks)
        self._cache.set(file_path, cache_data, mtime=mtime)

        return blocks

    def _parse_all_files(self) -> None:
        """解析所有知识库文件。"""
        for filename in self.list_files():
            self.parse_file(filename)

    def get_effect_map(
        self,
        fallback: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """获取效果映射字典。

        输出格式与 effect_registry.KEYWORD_TO_EFFECT_MAP 兼容。

        Args:
            fallback: 硬编码 fallback 映射（知识库映射优先）

        Returns:
            keyword -> matchName 字典
        """
        if self._effect_map is not None and fallback is None:
            return dict(self._effect_map)

        self._parse_all_files()

        all_mappings: List[EffectMapping] = []
        for filename, blocks in self._file_blocks.items():
            mappings = self._effect_adapter.extract_from_blocks(
                blocks, source_file=filename
            )
            all_mappings.extend(mappings)
            # 也从文本中提取
            text_mappings = self._effect_adapter.extract_from_text_blocks(
                blocks, source_file=filename
            )
            all_mappings.extend(text_mappings)

        if fallback:
            self._effect_map = self._effect_adapter.merge_with_fallback(
                all_mappings, fallback
            )
        else:
            self._effect_map = self._effect_adapter.to_dict(all_mappings)

        self._cache.save()
        return dict(self._effect_map)

    def get_transition_map(
        self,
        fallback: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """获取转场配方字典。

        输出格式与 transition_rebuilder.TRANSITION_IMPL_MAP 兼容。

        Args:
            fallback: 硬编码 fallback 配方

        Returns:
            transition_type -> recipe dict
        """
        if self._transition_map is not None and fallback is None:
            return dict(self._transition_map)

        self._parse_all_files()

        all_recipes: List[TransitionRecipe] = []
        for filename, blocks in self._file_blocks.items():
            recipes = self._transition_adapter.extract_from_blocks(
                blocks, source_file=filename
            )
            all_recipes.extend(recipes)
            # 注意：不从文本块提取转场配方，避免过度匹配非转场数据

        if fallback:
            self._transition_map = self._transition_adapter.merge_with_fallback(
                all_recipes, fallback
            )
        else:
            self._transition_map = self._transition_adapter.to_dict(all_recipes)

        self._cache.save()
        return dict(self._transition_map)

    def get_color_presets(self) -> List[ColorPreset]:
        """获取调色预设列表。

        Returns:
            ColorPreset 列表
        """
        if self._color_presets is not None:
            return list(self._color_presets)

        self._parse_all_files()
        # 调色预设提取（从表格中查找包含"预设名/参数/AE复刻"列的表格）
        self._color_presets = []
        # 暂不实现详细提取，返回空列表
        return list(self._color_presets)

    def get_style_recipes(self) -> List[StyleRecipe]:
        """获取风格配方列表。

        Returns:
            StyleRecipe 列表
        """
        if self._style_recipes is not None:
            return list(self._style_recipes)

        self._parse_all_files()
        self._style_recipes = []
        return list(self._style_recipes)

    # =========================================================================
    # 缓存序列化
    # =========================================================================

    @staticmethod
    def _blocks_to_cache(blocks: List[MdBlock]) -> Dict[str, Any]:
        """将 MdBlock 列表转为可 JSON 序列化的格式。"""
        return {
            "blocks": [
                {
                    "block_type": b.block_type.value,
                    "content": b.content,
                    "level": b.level,
                    "metadata": b.metadata,
                }
                for b in blocks
            ]
        }

    @staticmethod
    def _blocks_from_cache(data: Dict[str, Any]) -> List[MdBlock]:
        """从缓存数据恢复 MdBlock 列表。"""
        blocks: List[MdBlock] = []
        for item in data.get("blocks", []):
            try:
                bt = BlockType(item["block_type"])
            except ValueError:
                continue
            blocks.append(MdBlock(
                block_type=bt,
                content=item.get("content", ""),
                level=item.get("level", 0),
                metadata=item.get("metadata", {}),
            ))
        return blocks
