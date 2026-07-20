"""
aep_analyzer - AEP 工程分析器

从 AE 项目文件中提取结构、效果、关键帧、表达式等数据，
用于知识学习和效果配方逆向分析。

用法：
    from aep_analyzer import AEPAnalyzer

    analyzer = AEPAnalyzer()
    report = analyzer.analyze_via_mcp()  # 通过 MCP 桥接分析当前打开的项目
    knowledge = analyzer.extract_knowledge(report)
"""
from aep_analyzer.analyzer import AEPAnalyzer
from aep_analyzer.knowledge_extractor import KnowledgeExtractor
from aep_analyzer.report import ReportGenerator

__all__ = [
    "AEPAnalyzer",
    "KnowledgeExtractor",
    "ReportGenerator",
]
