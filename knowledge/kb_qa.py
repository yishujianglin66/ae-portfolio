#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知识库智能问答系统 (Knowledge Base QA System)
=============================================

利用 DeepSeek V4 的 1M 上下文窗口，直接读取整个知识库文档，
实现无需向量索引的智能问答系统。

特性:
- 无需 Embedding/向量数据库
- 支持模糊搜索和语义理解
- 可引用具体文档来源
- 支持多轮对话上下文

使用方式:
    from kb_qa import KnowledgeBaseQA

    qa = KnowledgeBaseQA()
    answer = qa.ask("AE中如何创建跟踪遮罩？")
    print(answer)
"""

import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    print("请安装 requests: py -3.11 -m pip install requests")
    sys.exit(1)

# ============================================================================
# 配置
# ============================================================================

API_BASE = "https://api.deepseek.com"
FLASH_MODEL = "deepseek-v4-flash"
PRO_MODEL = "deepseek-v4-pro"

# V4 上下文限制
MAX_CONTEXT_TOKENS = 1_000_000  # 1M
MAX_OUTPUT_TOKENS = 8_192
RESERVED_TOKENS = 20_000  # 预留给系统和用户输入

# 知识库目录
KB_ROOT = Path(__file__).parent
MOC_FILES = [
    "01-项目概览/📋-项目概览-MOC.md",
    "02-开发文档/📖-开发文档-MOC.md",
    "03-阶段报告/📊-阶段报告-MOC.md",
    "04-设计模式与反模式/🎨-设计模式-MOC.md",
    "05-测试套件/🧪-测试套件-MOC.md",
    "06-AI辅助开发/🤖-AI辅助开发-MOC.md",
    "07-MCP参考指南/🔗-MCP参考指南-MOC.md",
    "08-安装与部署/⚙️-安装部署-MOC.md",
    "09-计划文件/📝-计划文件-MOC.md",
    "10-风格化剪辑知识库/🎬-风格化剪辑知识库-MOC.md",
]

QA_SYSTEM_PROMPT = """你是AE-Knowledge-Vault项目的智能问答助手。

你的职责：
1. 基于提供的知识库文档回答用户问题
2. 准确引用来源（文件名和段落）
3. 如果知识库中没有相关信息，诚实告知
4. 提供可执行的代码示例或操作步骤

回答格式：
1. 直接回答问题
2. 引用来源：[文件名](路径)
3. 如有必要，补充代码示例

规则：
- 不要编造信息
- 优先使用知识库中的内容
- 代码示例使用 markdown 代码块
- 简洁清晰，避免冗长
"""


class KnowledgeBaseQA:
    """知识库智能问答系统"""

    def __init__(
        self,
        api_key: str | None = None,
        kb_root: str | None = None,
        model: str = "pro",
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY", "")
        if not self.api_key:
            raise ValueError("未设置 DEEPSEEK_API_KEY 环境变量")

        self.kb_root = Path(kb_root) if kb_root else KB_ROOT
        self.model_name = PRO_MODEL if model == "pro" else FLASH_MODEL

        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

        # 缓存
        self._cache_dir = self.kb_root / ".cache"
        self._cache_dir.mkdir(exist_ok=True)
        self._context_cache: str | None = None
        self._loaded_files: list[str] = []

    def scan_knowledge_base(self) -> dict[str, Any]:
        """扫描知识库，返回结构信息"""
        stats = {
            "total_files": 0,
            "total_size": 0,
            "total_tokens": 0,
            "by_directory": {},
            "moc_files": [],
            "md_files": [],
        }

        # 扫描所有.md文件
        for md_file in self.kb_root.rglob("*.md"):
            rel_path = md_file.relative_to(self.kb_root)
            size = md_file.stat().st_size
            tokens = size // 4  # 粗略估算

            stats["total_files"] += 1
            stats["total_size"] += size
            stats["total_tokens"] += tokens
            stats["md_files"].append(str(rel_path))

            # 按目录统计
            dir_name = rel_path.parts[0] if rel_path.parts else "root"
            if dir_name not in stats["by_directory"]:
                stats["by_directory"][dir_name] = {"files": 0, "size": 0}
            stats["by_directory"][dir_name]["files"] += 1
            stats["by_directory"][dir_name]["size"] += size

        # MOC文件
        for moc in MOC_FILES:
            moc_path = self.kb_root / moc
            if moc_path.exists():
                stats["moc_files"].append(moc)

        return stats

    def build_context(
        self,
        query: str | None = None,
        max_tokens: int = None,
        include_files: list[str] = None,
    ) -> str:
        """
        构建上下文，读取知识库文档

        Args:
            query: 用户查询（用于相关性过滤）
            max_tokens: 最大token数
            include_files: 强制包含的文件列表

        Returns:
            构建好的上下文字符串
        """
        max_tokens = max_tokens or (MAX_CONTEXT_TOKENS - RESERVED_TOKENS)

        # 尝试使用缓存
        cache_key = hashlib.md5(f"{query}:{max_tokens}".encode()).hexdigest()
        cache_file = self._cache_dir / f"context_{cache_key}.txt"

        if cache_file.exists():
            age = time.time() - cache_file.stat().st_mtime
            if age < 3600:  # 1小时缓存
                self._context_cache = cache_file.read_text(encoding="utf-8")
                return self._context_cache

        context_parts = []
        current_tokens = 0
        loaded = []

        # 优先加载MOC文件
        for moc_path in MOC_FILES:
            full_path = self.kb_root / moc_path
            if full_path.exists():
                content = full_path.read_text(encoding="utf-8")
                tokens = len(content) // 4

                if current_tokens + tokens > max_tokens:
                    continue

                context_parts.append(f"\n\n--- {moc_path} ---\n{content}")
                current_tokens += tokens
                loaded.append(str(full_path))

        # 如果有查询，做关键词匹配
        if query:
            keywords = self._extract_keywords(query)
            matched_files = self._search_by_keywords(keywords)

            for md_file in matched_files[:50]:  # 最多50个相关文件
                if current_tokens >= max_tokens:
                    break

                try:
                    content = md_file.read_text(encoding="utf-8")
                    tokens = len(content) // 4

                    if current_tokens + tokens > max_tokens:
                        # 截断
                        allowed = (max_tokens - current_tokens) * 4
                        content = content[:allowed] + "\n...[截断]"

                    context_parts.append(
                        f"\n\n--- {md_file.relative_to(self.kb_root)} ---\n{content}"
                    )
                    current_tokens += min(tokens, max_tokens - current_tokens)
                    loaded.append(str(md_file))
                except Exception:
                    continue

        # 强制包含指定文件
        if include_files:
            for inc_file in include_files:
                inc_path = self.kb_root / inc_file
                if inc_path.exists() and str(inc_path) not in loaded:
                    try:
                        content = inc_path.read_text(encoding="utf-8")
                        context_parts.append(
                            f"\n\n--- {inc_file} ---\n{content}"
                        )
                        loaded.append(str(inc_path))
                    except Exception:
                        continue

        self._context_cache = "\n".join(context_parts)
        self._loaded_files = loaded

        # 保存缓存
        try:
            cache_file.write_text(self._context_cache, encoding="utf-8")
        except Exception:
            pass

        return self._context_cache

    def ask(
        self,
        question: str,
        context: str | None = None,
        model: str | None = None,
        stream: bool = False,
    ) -> dict[str, Any]:
        """
        回答问题

        Args:
            question: 用户问题
            context: 自定义上下文（可选）
            model: 模型选择
            stream: 是否流式输出

        Returns:
            回答结果字典
        """
        # 构建上下文
        if context is None:
            context = self.build_context(query=question)

        model_name = FLASH_MODEL if model == "flash" else self.model_name

        messages = [
            {"role": "system", "content": QA_SYSTEM_PROMPT},
            {"role": "user", "content": f"知识库内容：\n{context}\n\n问题：{question}"},
        ]

        payload = {
            "model": model_name,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": MAX_OUTPUT_TOKENS,
        }

        start = time.time()

        if stream:
            return self._stream_response(payload)

        response = self._session.post(
            f"{API_BASE}/v1/chat/completions",
            json=payload,
            timeout=180,
        )
        response.raise_for_status()
        result = response.json()

        duration = time.time() - start

        if "choices" not in result or not result["choices"]:
            return {
                "success": False,
                "error": "API返回异常",
                "raw": result,
            }

        content = result["choices"][0]["message"]["content"]
        usage = result.get("usage", {})

        # 计算费用
        cost = self._calc_cost(usage, model_name)

        return {
            "success": True,
            "answer": content,
            "sources": self._extract_sources(content),
            "loaded_files": len(self._loaded_files),
            "duration": duration,
            "usage": usage,
            "cost": cost,
            "model": model_name,
        }

    def ask_simple(self, question: str) -> str:
        """简化接口：直接返回回答文本"""
        result = self.ask(question)
        return result.get("answer", result.get("error", "无回答"))

    def _search_by_keywords(self, keywords: list[str]) -> list[Path]:
        """关键词搜索"""
        matched = []

        for md_file in self.kb_root.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8").lower()
                score = sum(1 for kw in keywords if kw.lower() in content)
                if score > 0:
                    matched.append((md_file, score))
            except Exception:
                continue

        # 按匹配分数排序
        matched.sort(key=lambda x: x[1], reverse=True)
        return [m[0] for m in matched]

    def _extract_keywords(self, text: str) -> list[str]:
        """提取关键词"""
        # 停用词
        stop_words = {"的", "是", "在", "了", "和", "与", "或", "如何", "怎么", "什么", "为什么"}

        # 分词（简单按空格和标点）
        words = re.split(r'[\s\-\_\+\*\&\%\$\#\@\!\?\.\,\;\:\'\"。，；：？！""''（）【】]', text)

        keywords = []
        for w in words:
            w = w.strip()
            if len(w) >= 2 and w not in stop_words:
                keywords.append(w)

        return list(set(keywords))[:10]

    def _extract_sources(self, content: str) -> list[str]:
        """从回答中提取来源引用"""
        # 匹配 markdown 链接
        pattern = r'\[([^\]]+)\]\(([^)]+\.md)\)'
        matches = re.findall(pattern, content)
        return [m[1] for m in matches]

    def _stream_response(self, payload: dict):
        """流式响应"""
        payload["stream"] = True

        response = self._session.post(
            f"{API_BASE}/v1/chat/completions",
            json=payload,
            stream=True,
            timeout=180,
        )

        for line in response.iter_lines():
            if line:
                yield line.decode("utf-8")

    def _calc_cost(self, usage: dict, model: str) -> float:
        """计算费用"""
        if "pro" in model:
            in_price, out_price = 3, 6
        else:
            in_price, out_price = 1, 2

        prompt = usage.get("prompt_tokens", 0) / 1_000_000
        completion = usage.get("completion_tokens", 0) / 1_000_000
        return prompt * in_price + completion * out_price

    def get_stats(self) -> dict[str, Any]:
        """获取知识库统计"""
        return self.scan_knowledge_base()


# ============================================================================
# CLI 入口
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="知识库智能问答系统")
    parser.add_argument(
        "question",
        nargs="?",
        help="问题",
    )
    parser.add_argument(
        "--model", "-m",
        choices=["pro", "flash"],
        default="pro",
        help="模型选择",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="显示知识库统计",
    )
    parser.add_argument(
        "--file", "-f",
        action="append",
        help="强制包含的文件",
    )

    args = parser.parse_args()

    qa = KnowledgeBaseQA(model=args.model)

    if args.stats:
        stats = qa.scan_knowledge_base()
        print("知识库统计：")
        print(f"  总文件数: {stats['total_files']}")
        print(f"  总大小: {stats['total_size'] / 1024 / 1024:.2f} MB")
        print(f"  估算Token: {stats['total_tokens']:,}")
        print("\n目录分布：")
        for dir_name, info in stats["by_directory"].items():
            print(f"  {dir_name}: {info['files']} 文件, {info['size'] / 1024:.1f} KB")
        return

    if not args.question:
        print("用法：py -3.11 kb_qa.py \"AE中如何创建跟踪遮罩？\"")
        print("选项：")
        print("  --stats       显示知识库统计")
        print("  --model pro/flash  选择模型")
        print("  --file path   强制包含文件")
        return

    print(f"\n问题: {args.question}")
    print(f"模型: {args.model}")
    print("-" * 40)

    result = qa.ask(args.question, model=args.model)

    if result["success"]:
        print(result["answer"])
        print("\n---")
        print(f"加载文件: {result['loaded_files']}")
        print(f"耗时: {result['duration']:.1f}s")
        print(f"费用: ¥{result['cost']:.4f}")
    else:
        print(f"错误: {result.get('error', '未知错误')}")


if __name__ == "__main__":
    main()