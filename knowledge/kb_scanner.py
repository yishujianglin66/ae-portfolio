"""
kb_scanner.py - 知识库多线程扫描器
=====================================
并行分析207个知识库文件，提取效果参数映射、转场配方、调色预设等结构化数据
"""
import glob
import json
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

KB_ROOT = r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\10-风格化剪辑知识库"
OUTPUT_DIR = r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output_kb_scan"

os.makedirs(OUTPUT_DIR, exist_ok=True)


class KBScanner:
    def __init__(self):
        self._files: list[str] = []
        self._results: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._total_files = 0
        self._processed = 0

    def discover_files(self) -> int:
        """发现所有MD知识库文件"""
        pattern = os.path.join(KB_ROOT, "**", "*.md")
        self._files = sorted(glob.glob(pattern, recursive=True))
        self._total_files = len(self._files)
        print(f"发现 {self._total_files} 个知识库文件")
        return self._total_files

    def _scan_file(self, filepath: str):
        """单文件扫描"""
        filename = os.path.basename(filepath)
        rel_path = os.path.relpath(filepath, KB_ROOT)
        
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            print(f"  [FAIL] {filename}: {e}")
            return

        stats = {
            "filename": filename,
            "rel_path": rel_path,
            "size": len(content),
            "lines": content.count("\n"),
        }

        # 提取表格数据（参数映射表）
        tables = self._extract_tables(content)
        if tables:
            stats["tables"] = len(tables)
            stats["table_rows"] = sum(len(t["rows"]) for t in tables)

        # 提取代码块（JSX/命令模板）
        code_blocks = self._extract_code_blocks(content)
        if code_blocks:
            stats["code_blocks"] = len(code_blocks)
            stats["code_languages"] = list(set(c["lang"] for c in code_blocks))

        # 提取效果名/关键词
        effects = self._extract_effects(content)
        if effects:
            stats["effects_found"] = len(effects)

        # 提取转场类型
        transitions = self._extract_transitions(content)
        if transitions:
            stats["transitions_found"] = len(transitions)

        # 提取调色预设
        color_presets = self._extract_color_presets(content)
        if color_presets:
            stats["color_presets"] = len(color_presets)

        # 提取关键词标签
        tags = self._extract_tags(content)
        if tags:
            stats["tags"] = tags

        with self._lock:
            self._results[filename] = stats
            self._processed += 1
            if self._processed % 20 == 0:
                print(f"  进度: {self._processed}/{self._total_files}")

    def _extract_tables(self, content: str) -> list[dict]:
        """提取Markdown表格"""
        tables = []
        table_pattern = re.compile(
            r'\|([^\n]+)\|\n\|[-:| ]+\|\n((?:\|[^\n]+\|\n?)+)',
            re.MULTILINE
        )
        for match in table_pattern.finditer(content):
            header = match.group(1).strip()
            rows_text = match.group(2)
            rows = [
                [cell.strip() for cell in row.split("|") if cell.strip()]
                for row in rows_text.strip().split("\n")
            ]
            tables.append({"header": header, "rows": rows})
        return tables

    def _extract_code_blocks(self, content: str) -> list[dict]:
        """提取代码块"""
        blocks = []
        code_pattern = re.compile(
            r'```(\w+)?\n([\s\S]*?)```',
            re.MULTILINE
        )
        for match in code_pattern.finditer(content):
            lang = match.group(1) or "text"
            code = match.group(2).strip()
            blocks.append({"lang": lang, "lines": code.count("\n") + 1})
        return blocks

    def _extract_effects(self, content: str) -> list[str]:
        """提取效果关键词"""
        effect_patterns = [
            r"ADBE [A-Za-z ]+",
            r"CC [A-Za-z ]+",
            r"TC [A-Za-z ]+",
            r"VC [A-Za-z ]+",
            r"BCC [A-Za-z_]+",
            r"RB [A-Za-z ]+",
        ]
        effects = set()
        for pattern in effect_patterns:
            for match in re.finditer(pattern, content):
                effects.add(match.group().strip())
        return list(effects)[:30]

    def _extract_transitions(self, content: str) -> list[str]:
        """提取转场类型"""
        transition_keywords = [
            "wipe", "dissolve", "fade", "glitch", "zoom",
            "flip", "slide", "push", "rotate", "spin",
            "cube", "page", "door", "card", "block",
            "ink", "light", "radial", "linear"
        ]
        transitions = set()
        for kw in transition_keywords:
            if kw.lower() in content.lower():
                transitions.add(kw)
        return list(transitions)

    def _extract_color_presets(self, content: str) -> list[str]:
        """提取调色预设名称"""
        presets = []
        preset_pattern = re.compile(r"([\u4e00-\u9fa5a-zA-Z]+[调色预设|预设|风格])")
        for match in preset_pattern.finditer(content):
            presets.append(match.group(1))
        return list(set(presets))[:20]

    def _extract_tags(self, content: str) -> list[str]:
        """提取YAML frontmatter中的tags"""
        tag_pattern = re.compile(r"tags:\s*(\[.*?\])", re.DOTALL)
        match = tag_pattern.search(content)
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        return []

    def scan_parallel(self, threads: int = 8) -> dict[str, Any]:
        """多线程扫描"""
        print(f"开始多线程扫描 (threads={threads})...")
        start = time.time()

        def worker(file_list):
            for f in file_list:
                self._scan_file(f)

        # 按文件大小排序（大文件先处理）
        files_with_size = [(f, os.path.getsize(f)) for f in self._files]
        files_with_size.sort(key=lambda x: -x[1])
        sorted_files = [f for f, _ in files_with_size]

        # 分配任务
        chunks = [[] for _ in range(threads)]
        for i, f in enumerate(sorted_files):
            chunks[i % threads].append(f)

        # 启动线程
        thread_list = []
        for i in range(threads):
            if chunks[i]:
                t = threading.Thread(target=worker, args=(chunks[i],))
                thread_list.append(t)
                t.start()

        # 等待完成
        for t in thread_list:
            t.join()

        elapsed = time.time() - start
        print(f"扫描完成! 耗时: {elapsed:.1f}s")
        return self._results

    def generate_report(self) -> str:
        """生成扫描报告"""
        report = {
            "total_files": self._total_files,
            "scanned_files": self._processed,
            "stats": {
                "total_size": sum(r["size"] for r in self._results.values()),
                "total_lines": sum(r["lines"] for r in self._results.values()),
                "files_with_tables": sum(1 for r in self._results.values() if "tables" in r),
                "files_with_code": sum(1 for r in self._results.values() if "code_blocks" in r),
                "files_with_effects": sum(1 for r in self._results.values() if "effects_found" in r),
            },
            "top_effect_files": [],
            "top_table_files": [],
            "files_by_category": {},
        }

        # 效果文件排名
        effect_files = sorted(
            [(k, v["effects_found"]) for k, v in self._results.items() if "effects_found" in v],
            key=lambda x: -x[1]
        )[:10]
        report["top_effect_files"] = effect_files

        # 表格文件排名
        table_files = sorted(
            [(k, v["tables"]) for k, v in self._results.items() if "tables" in v],
            key=lambda x: -x[1]
        )[:10]
        report["top_table_files"] = table_files

        # 按目录分类
        for filename, stats in self._results.items():
            rel_path = stats["rel_path"]
            category = os.path.dirname(rel_path) or "root"
            if category not in report["files_by_category"]:
                report["files_by_category"][category] = []
            report["files_by_category"][category].append(stats)

        return report


if __name__ == "__main__":
    scanner = KBScanner()
    scanner.discover_files()
    scanner.scan_parallel(threads=8)
    
    report = scanner.generate_report()
    
    report_path = os.path.join(OUTPUT_DIR, "kb_scan_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"报告已保存: {report_path}")

    # 打印摘要
    print("\n=== 扫描摘要 ===")
    print(f"总文件: {report['total_files']}")
    print(f"总代码行数: {report['stats']['total_lines']:,}")
    print(f"含表格文件: {report['stats']['files_with_tables']}")
    print(f"含代码块文件: {report['stats']['files_with_code']}")
    print(f"含效果映射文件: {report['stats']['files_with_effects']}")
    
    print("\n=== 效果映射最多的文件 ===")
    for filename, count in report["top_effect_files"]:
        print(f"  {count:>3} effects  -  {filename}")
    
    print("\n=== 表格最多的文件 ===")
    for filename, count in report["top_table_files"]:
        print(f"  {count:>3} tables  -  {filename}")
