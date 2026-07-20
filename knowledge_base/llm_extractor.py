"""
knowledge_base/llm_extractor.py - LLM 知识提取器 (Layer 2)

对非结构化段落调用 LLM 提取 AE 效果参数映射。
可选组件，离线模式（AEK_OFFLINE_MODE=1）下自动跳过。

用法：
    from knowledge_base.llm_extractor import LlmExtractor

    extractor = LlmExtractor()
    items = extractor.extract_effects(block, source_file="file.md")
    all_items = extractor.batch_extract_effects(blocks, source_file="file.md")
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from knowledge_base.types import BlockType, MdBlock, EffectMapping

logger = logging.getLogger(__name__)

# LLM 提取 prompt 模板
_EFFECT_EXTRACTION_PROMPT = """\
从以下文本中提取 AE (After Effects) 效果参数映射。
输出 JSON 数组，每个元素包含：
- keyword: 效果关键词（中文或英文）
- match_name: AE 内部 matchName（如 "ADBE Gaussian Blur 2"）
- category: 效果分类（如 blur, glow, particle, distort, color, transition 等）
- confidence: 置信度 (0-1)

如果没有找到效果映射，返回空数组 []。

文本：
{text}
"""


class LlmExtractor:
    """LLM 知识提取器。"""

    def __init__(self, llm_client: Optional[Any] = None) -> None:
        """初始化。

        Args:
            llm_client: LLM 客户端对象，需有 chat(prompt) -> str 方法。
                        为 None 时使用内置 llm_gateway。
        """
        self._llm_client = llm_client
        self._offline = os.environ.get("AEK_OFFLINE_MODE", "") == "1"

    def extract_effects(
        self,
        block: MdBlock,
        source_file: str = "",
    ) -> List[EffectMapping]:
        """从单个块中提取效果映射。

        仅处理 PARAGRAPH 和 LIST 类型的块。
        TABLE 和 CODE_BLOCK 已由规则引擎处理，跳过。

        Args:
            block: MdBlock
            source_file: 来源文件名

        Returns:
            EffectMapping 列表
        """
        # 跳过已由规则引擎处理的块类型
        if block.block_type not in (BlockType.PARAGRAPH, BlockType.LIST):
            return []

        # 离线模式跳过
        if self._offline:
            return []

        # 内容太短不提取
        if len(block.content.strip()) < 10:
            return []

        prompt = _EFFECT_EXTRACTION_PROMPT.format(text=block.content)
        response = self._call_llm(prompt)

        if not response:
            return []

        return self._parse_response(response, source_file)

    def batch_extract_effects(
        self,
        blocks: List[MdBlock],
        source_file: str = "",
    ) -> List[EffectMapping]:
        """批量提取多个块的效果映射。

        Args:
            blocks: MdBlock 列表
            source_file: 来源文件名

        Returns:
            EffectMapping 列表
        """
        all_items: List[EffectMapping] = []
        for block in blocks:
            items = self.extract_effects(block, source_file=source_file)
            all_items.extend(items)
        return all_items

    def _call_llm(self, prompt: str) -> str:
        """调用 LLM。

        Args:
            prompt: 提示文本

        Returns:
            LLM 响应文本
        """
        if self._offline:
            return ""

        if self._llm_client is not None:
            try:
                return str(self._llm_client.chat(prompt))
            except Exception as e:
                logger.warning("LLM call failed: %s", e)
                return ""

        # 尝试使用项目内置的 llm_gateway
        try:
            from llm_gateway import LLMGateway
            gw = LLMGateway()
            return str(gw.chat(prompt))
        except ImportError:
            logger.debug("llm_gateway not available, LLM extraction disabled")
            return ""
        except Exception as e:
            logger.warning("LLM gateway call failed: %s", e)
            return ""

    def _parse_response(self, response: str, source_file: str) -> List[EffectMapping]:
        """解析 LLM 响应为 EffectMapping 列表。

        Args:
            response: LLM 响应 JSON 文本
            source_file: 来源文件名

        Returns:
            EffectMapping 列表
        """
        try:
            data = json.loads(response)
        except json.JSONDecodeError:
            logger.warning("LLM response is not valid JSON: %s", response[:200])
            return []

        if not isinstance(data, list):
            return []

        items: List[EffectMapping] = []
        for entry in data:
            if not isinstance(entry, dict):
                continue

            keyword = str(entry.get("keyword", "")).strip()
            match_name = str(entry.get("match_name", "")).strip()
            if not keyword or not match_name:
                continue

            category = str(entry.get("category", "")).strip()
            confidence = float(entry.get("confidence", 0.8))

            items.append(EffectMapping(
                keyword=keyword,
                match_name=match_name,
                category=category,
                source_file=source_file,
                confidence=confidence,
                extracted_by="llm",
            ))

        return items
