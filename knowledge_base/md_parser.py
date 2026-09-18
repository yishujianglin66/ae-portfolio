"""
knowledge_base/md_parser.py - Markdown AST 解析器 (Layer 1)

纯规则引擎，将 Markdown 文本解析为 MdBlock 列表。
无 LLM 依赖，支持中文内容。

用法：
    from knowledge_base.md_parser import MdParser

    parser = MdParser()
    blocks = parser.parse("# Title\\n\\nParagraph\\n\\n| A | B |\\n|---|---|\\n| 1 | 2 |")
    blocks = parser.parse_file("path/to/file.md")
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List

from knowledge_base.types import BlockType, MdBlock


class MdParser:
    """Markdown 解析器 - 将 md 文本解析为 MdBlock 列表。"""

    # 正则模式
    _HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")
    _CODE_FENCE_RE = re.compile(r"^```(\w*)$")
    _TABLE_ROW_RE = re.compile(r"^\|(.+)\|$")
    _TABLE_SEP_RE = re.compile(r"^\|[\s\-:|]+\|$")
    _HR_RE = re.compile(r"^(?:---+|\*\*\*+|___+)\s*$")
    _UL_RE = re.compile(r"^[\s]*[-*+]\s+(.+)$")
    _OL_RE = re.compile(r"^[\s]*\d+\.\s+(.+)$")

    def parse(self, text: str) -> list[MdBlock]:
        """解析 Markdown 文本为 MdBlock 列表。

        Args:
            text: Markdown 格式文本

        Returns:
            MdBlock 列表，按原文顺序排列
        """
        if not text or not text.strip():
            return []

        blocks: list[MdBlock] = []
        lines = text.split("\n")
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]
            stripped = line.strip()

            # 空行跳过
            if not stripped:
                i += 1
                continue

            # 代码块 ```
            m_code = self._CODE_FENCE_RE.match(stripped)
            if m_code:
                lang = m_code.group(1) or ""
                code_lines: list[str] = []
                i += 1
                while i < n:
                    if self._CODE_FENCE_RE.match(lines[i].strip()):
                        i += 1
                        break
                    code_lines.append(lines[i])
                    i += 1
                blocks.append(MdBlock(
                    block_type=BlockType.CODE_BLOCK,
                    content="\n".join(code_lines),
                    metadata={"language": lang},
                ))
                continue

            # 标题 #
            m_heading = self._HEADING_RE.match(stripped)
            if m_heading:
                level = len(m_heading.group(1))
                title = m_heading.group(2).strip()
                blocks.append(MdBlock(
                    block_type=BlockType.HEADING,
                    content=title,
                    level=level,
                ))
                i += 1
                continue

            # 水平线 ---
            if self._HR_RE.match(stripped):
                blocks.append(MdBlock(block_type=BlockType.HR, content=""))
                i += 1
                continue

            # 表格 | ... | ... |
            if self._TABLE_ROW_RE.match(stripped):
                table_lines: list[str] = [stripped]
                i += 1
                while i < n and self._TABLE_ROW_RE.match(lines[i].strip()):
                    table_lines.append(lines[i].strip())
                    i += 1
                blocks.append(MdBlock(
                    block_type=BlockType.TABLE,
                    content="\n".join(table_lines),
                ))
                continue

            # 列表 - item 或 1. item
            if self._UL_RE.match(stripped) or self._OL_RE.match(stripped):
                list_lines: list[str] = [stripped]
                i += 1
                while i < n:
                    s = lines[i].strip()
                    if not s:
                        break
                    if self._UL_RE.match(s) or self._OL_RE.match(s):
                        list_lines.append(s)
                        i += 1
                    else:
                        break
                blocks.append(MdBlock(
                    block_type=BlockType.LIST,
                    content="\n".join(list_lines),
                ))
                continue

            # 段落（收集连续非空行）
            para_lines: list[str] = [stripped]
            i += 1
            while i < n:
                s = lines[i].strip()
                if not s:
                    break
                # 遇到特殊行则中断段落
                if (
                    self._HEADING_RE.match(s)
                    or self._CODE_FENCE_RE.match(s)
                    or self._HR_RE.match(s)
                    or self._TABLE_ROW_RE.match(s)
                    or self._UL_RE.match(s)
                    or self._OL_RE.match(s)
                ):
                    break
                para_lines.append(s)
                i += 1

            blocks.append(MdBlock(
                block_type=BlockType.PARAGRAPH,
                content=" ".join(para_lines),
            ))

        return blocks

    def parse_file(self, file_path: str) -> list[MdBlock]:
        """从文件解析 Markdown。

        Args:
            file_path: md 文件路径

        Returns:
            MdBlock 列表
        """
        path = Path(file_path)
        text = path.read_text(encoding="utf-8")
        return self.parse(text)
