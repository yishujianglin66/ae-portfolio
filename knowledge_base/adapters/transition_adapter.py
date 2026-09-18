"""
knowledge_base/adapters/transition_adapter.py - 转场配方适配器 (Layer 4)

将知识库中解析的转场配方转换为与 TRANSITION_IMPL_MAP 兼容的 Dict[str, Dict[str, Any]] 格式。

用法：
    from knowledge_base.adapters.transition_adapter import TransitionAdapter

    adapter = TransitionAdapter()
    recipes = adapter.extract_from_blocks(blocks, source_file="file.md")
    trans_map = adapter.to_dict(recipes)
    merged = adapter.merge_with_fallback(recipes, fallback_map)
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from knowledge_base.table_extractor import TableExtractor
from knowledge_base.types import BlockType, MdBlock, TransitionRecipe


class TransitionAdapter:
    """转场配方适配器 - 输出与 TRANSITION_IMPL_MAP 兼容的格式。"""

    # 匹配 "**type**: display_name=xxx, effect=yyy" 格式
    _KV_LINE_RE = re.compile(
        r"[-*]?\s*\*{0,2}([^*\n:]+?)\*{0,2}\s*[:：]\s*(.+)"
    )

    # 常见列名变体（仅匹配转场专用列名，避免误匹配通用表格）
    _TYPE_COLS = {"转场类型", "transition_type", "transition"}
    # 类型列子串匹配：列名包含 '转场' 且包含分类/类型关键词之一
    _TYPE_SUBSTR_PRIMARY = "转场"
    _TYPE_SUBSTR_SECONDARY = ("类型", "分类", "type")
    _NAME_COLS = {"显示名", "display_name", "中文名", "场景转场"}
    _EFFECT_COLS = {"效果match", "effect_match"}
    # 效果列子串匹配：列名同时包含 'ae' 和以下关键词之一
    _EFFECT_SUBSTR_KEYWORDS = ("效果", "原子", "原生", "工程方案", "对应", "match", "名称")
    _PARAMS_COLS = {"参数", "params", "parameters", "参数与动画描述", "动画描述", "参数描述"}

    def __init__(self) -> None:
        self._table_extractor = TableExtractor()

    def extract_from_blocks(
        self,
        blocks: list[MdBlock],
        source_file: str = "",
    ) -> list[TransitionRecipe]:
        """从 MdBlock 列表中提取转场配方。

        扫描所有 TABLE 块，查找包含"类型"和"效果"列的表格。

        Args:
            blocks: MdBlock 列表
            source_file: 来源文件名

        Returns:
            TransitionRecipe 列表
        """
        recipes: list[TransitionRecipe] = []

        for block in blocks:
            if block.block_type != BlockType.TABLE:
                continue

            rows = self._table_extractor.extract(block)
            if not rows:
                continue

            headers = list(rows[0].columns.keys())
            type_col = self._find_type_column(headers)
            name_col = self._find_column(headers, self._NAME_COLS)
            effect_col = self._find_effect_column(headers)
            params_col = self._find_column(headers, self._PARAMS_COLS)

            # 必须同时有类型列和效果列才视为转场配方表
            if not type_col or not effect_col:
                continue

            for row in rows:
                trans_type = row.columns.get(type_col, "").strip()
                if not trans_type:
                    continue

                # 转为 snake_case
                trans_type = self._to_snake_case(trans_type)

                display_name = ""
                if name_col:
                    display_name = row.columns.get(name_col, "").strip()

                effect_match = ""
                if effect_col:
                    effect_match = row.columns.get(effect_col, "").strip()

                params: dict[str, Any] = {}
                if params_col:
                    params_str = row.columns.get(params_col, "").strip()
                    params = self._parse_params(params_str)

                recipes.append(TransitionRecipe(
                    transition_type=trans_type,
                    display_name=display_name,
                    effect_match=effect_match,
                    params=params,
                    source_file=source_file,
                ))

        return recipes

    def extract_from_text_blocks(
        self,
        blocks: list[MdBlock],
        source_file: str = "",
    ) -> list[TransitionRecipe]:
        """从文本块中提取转场配方。

        匹配格式：
            - **type**: display_name=xxx, effect=yyy

        Args:
            blocks: MdBlock 列表
            source_file: 来源文件名

        Returns:
            TransitionRecipe 列表
        """
        recipes: list[TransitionRecipe] = []

        for block in blocks:
            if block.block_type not in (BlockType.PARAGRAPH, BlockType.LIST):
                continue

            for line in block.content.split("\n"):
                m = self._KV_LINE_RE.search(line)
                if not m:
                    continue

                trans_type = m.group(1).strip()
                trans_type = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", trans_type)
                trans_type = self._to_snake_case(trans_type)

                rest = m.group(2).strip()
                display_name = ""
                effect_match = ""

                # 解析 display_name=xxx
                dm = re.search(r"display_name\s*=\s*([^,，]+)", rest)
                if dm:
                    display_name = dm.group(1).strip()

                # 解析 effect=xxx
                em = re.search(r"effect\s*=\s*(\S+)", rest)
                if em:
                    effect_match = em.group(1).strip()

                recipes.append(TransitionRecipe(
                    transition_type=trans_type,
                    display_name=display_name,
                    effect_match=effect_match,
                    source_file=source_file,
                ))

        return recipes

    def to_dict(self, recipes: list[TransitionRecipe]) -> dict[str, dict[str, Any]]:
        """转换为 Dict[str, Dict[str, Any]] 格式。

        Args:
            recipes: TransitionRecipe 列表

        Returns:
            与 TRANSITION_IMPL_MAP 格式兼容的字典
        """
        result: dict[str, dict[str, Any]] = {}
        for r in recipes:
            entry: dict[str, Any] = {
                "display_name": r.display_name,
                "effect_match": r.effect_match,
            }
            if r.params:
                entry["params"] = r.params
            if r.animate:
                entry["animate"] = r.animate
            result[r.transition_type] = entry
        return result

    def merge_with_fallback(
        self,
        kb_recipes: list[TransitionRecipe],
        fallback: dict[str, dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """合并知识库配方与硬编码 fallback。

        Args:
            kb_recipes: 从知识库提取的配方
            fallback: 硬编码 fallback

        Returns:
            合并后的字典
        """
        result: dict[str, dict[str, Any]] = dict(fallback)
        for r in kb_recipes:
            entry: dict[str, Any] = {
                "display_name": r.display_name,
                "effect_match": r.effect_match,
            }
            if r.params:
                entry["params"] = r.params
            if r.animate:
                entry["animate"] = r.animate
            result[r.transition_type] = entry
        return result

    @staticmethod
    def _to_snake_case(text: str) -> str:
        """将文本转为 snake_case。"""
        # 空格/连字符 -> 下划线
        text = re.sub(r"[\s\-]+", "_", text)
        # CamelCase -> snake_case
        text = re.sub(r"([a-z])([A-Z])", r"\1_\2", text)
        return text.lower().strip("_")

    @staticmethod
    def _parse_params(params_str: str) -> dict[str, Any]:
        """解析参数字符串 "key1=val1, key2=val2"。"""
        params: dict[str, Any] = {}
        if not params_str:
            return params

        for pair in params_str.split(","):
            pair = pair.strip()
            if "=" not in pair:
                continue
            key, val = pair.split("=", 1)
            key = key.strip()
            val = val.strip()
            # 尝试转为数值
            try:
                params[key] = int(val)
            except ValueError:
                try:
                    params[key] = float(val)
                except ValueError:
                    params[key] = val
        return params

    @staticmethod
    def _find_column(headers: list[str], candidates: set[str]) -> str | None:
        """在表头中查找匹配候选名称的列。"""
        for h in headers:
            if h.lower().strip() in candidates:
                return h
        return None

    def _find_effect_column(self, headers: list[str]) -> str | None:
        """查找效果列：先精确匹配，再子串匹配（ae + 关键词），最后宽松匹配任何AE列。"""
        # 精确匹配
        exact = self._find_column(headers, self._EFFECT_COLS)
        if exact:
            return exact
        # 子串匹配：列名包含 'ae' 且包含关键词之一
        for h in headers:
            low = h.lower().strip()
            if 'ae' in low and any(kw in low for kw in self._EFFECT_SUBSTR_KEYWORDS):
                return h
        # 宽松匹配：任何包含 'ae' 的列（排除“AE实现脚本”等纯代码列）
        for h in headers:
            low = h.lower().strip()
            if 'ae' in low and '脚本' not in low and 'script' not in low:
                return h
        return None

    def _find_type_column(self, headers: list[str]) -> str | None:
        """查找类型列：先精确匹配，再子串匹配（包含转场 + 分类/类型）。"""
        exact = self._find_column(headers, self._TYPE_COLS)
        if exact:
            return exact
        # 子串匹配：列名包含 '转场' 且包含分类/类型关键词
        for h in headers:
            low = h.lower().strip()
            if self._TYPE_SUBSTR_PRIMARY in low and any(
                kw in low for kw in self._TYPE_SUBSTR_SECONDARY
            ):
                return h
        # 宽松匹配：列名包含 '转场' 且不是纯描述列（排除“转场描述”“转场场景”等）
        for h in headers:
            low = h.lower().strip()
            if self._TYPE_SUBSTR_PRIMARY in low and not any(
                skip in low for skip in ("描述", "场景", "时长", "特点")
            ):
                return h
        return None
