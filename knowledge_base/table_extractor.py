"""
knowledge_base/table_extractor.py - 表格提取器 (Layer 2)

从 MdBlock 中提取表格数据，转为 List[TableRow]。
支持管道符转义、粗体标记清理、空格归一化。

用法：
    from knowledge_base.table_extractor import TableExtractor

    extractor = TableExtractor()
    rows = extractor.extract(table_block)
    all_rows = extractor.extract_all(blocks)
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from knowledge_base.types import BlockType, MdBlock, TableRow


class TableExtractor:
    """表格提取器 - 从 TABLE 类型的 MdBlock 中提取结构化数据。"""

    # 去除粗体/斜体标记
    _BOLD_RE = re.compile(r"\*{1,3}([^*]+)\*{1,3}")
    _ITALIC_RE = re.compile(r"_([^_]+)_")
    # 转义管道符
    _ESCAPED_PIPE_RE = re.compile(r"\\\|")
    _PIPE_PLACEHOLDER = "\x00PIPE\x00"

    def extract(self, block: MdBlock) -> list[TableRow]:
        """从单个 TABLE 块中提取行数据。

        Args:
            block: BlockType.TABLE 类型的 MdBlock

        Returns:
            TableRow 列表。非 TABLE 块返回空列表。
        """
        if block.block_type != BlockType.TABLE:
            return []

        lines = block.content.strip().split("\n")
        if len(lines) < 2:
            return []

        # 解析表头
        header_line = lines[0].strip()
        headers = self._parse_row(header_line)
        if not headers:
            return []

        # 跳过分隔行（第二行）
        data_start = 1
        if len(lines) > 1 and self._is_separator(lines[1].strip()):
            data_start = 2

        # 解析数据行
        rows: list[TableRow] = []
        for line in lines[data_start:]:
            line = line.strip()
            if not line or self._is_separator(line):
                continue
            cells = self._parse_row(line)
            if not cells:
                continue

            # 构建 columns 字典
            columns: dict[str, str] = {}
            for idx, header in enumerate(headers):
                if idx < len(cells):
                    columns[header] = cells[idx]
                else:
                    columns[header] = ""
            rows.append(TableRow(columns=columns))

        return rows

    def extract_all(self, blocks: list[MdBlock]) -> list[list[TableRow]]:
        """从多个块中提取所有表格。

        Args:
            blocks: MdBlock 列表

        Returns:
            每个表格对应一个 List[TableRow]，外层列表按出现顺序排列
        """
        result: list[list[TableRow]] = []
        for block in blocks:
            if block.block_type == BlockType.TABLE:
                rows = self.extract(block)
                if rows:
                    result.append(rows)
        return result

    def _parse_row(self, line: str) -> list[str]:
        """解析表格行，返回单元格内容列表。"""
        # 处理转义管道符
        line = self._ESCAPED_PIPE_RE.sub(self._PIPE_PLACEHOLDER, line)

        # 去除首尾管道符
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]

        # 按管道符分割
        cells = line.split("|")

        # 清理每个单元格
        result: list[str] = []
        for cell in cells:
            # 恢复转义管道符
            cell = cell.replace(self._PIPE_PLACEHOLDER, "|")
            # 去除粗体/斜体标记
            cell = self._BOLD_RE.sub(r"\1", cell)
            cell = self._ITALIC_RE.sub(r"\1", cell)
            # 去除首尾空格
            cell = cell.strip()
            result.append(cell)

        return result

    def _is_separator(self, line: str) -> bool:
        """判断是否为表格分隔行。"""
        # 分隔行格式: |---|---|---|
        if not line.startswith("|"):
            return False
        # 去除管道符后应只剩 -、:、空格
        content = line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")
        return len(content) == 0
