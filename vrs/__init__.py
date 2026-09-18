"""
VRS - Video Reverse-engineering System
=======================================

视频效果逆向分析系统 v2.0

子模块：
- vrs_orchestrator: 主编排器（端到端入口）
- video_effect_analyzer_v2: CV + VISION LLM 混合分析 (v2)
- video_effect_analyzer_v1: 纯 CV 分析 (v1)
- video_reverse_engine: 技术逆向分析引擎
- video_reproduce_pipeline: 逆向复现管线编排器
- vrs_knowledge_rag: 知识库 RAG 增强
- vrs_structure_inferrer: 合成结构推断引擎
- vrs_compiler_bridge: 编译器桥接（生成 AE 脚本/MCP 命令）
- vrs_audio_sync_analyzer: 音画同步分析
- vrs_iteration_optimizer: 迭代优化器
"""

from vrs.video_effect_analyzer_v1 import VideoEffectAnalyzer
from vrs.video_effect_analyzer_v2 import VideoEffectAnalyzerV2
from vrs.video_reproduce_pipeline import VideoReproducePipeline
from vrs.video_reverse_engine import VideoReverseEngine
from vrs.vrs_audio_sync_analyzer import AudioSyncAnalyzer
from vrs.vrs_compiler_bridge import VRCompilerBridge
from vrs.vrs_iteration_optimizer import IterationOptimizer
from vrs.vrs_knowledge_rag import KnowledgeRAG
from vrs.vrs_orchestrator import VRSOrchestrator
from vrs.vrs_structure_inferrer import CompositionStructureInferrer

__all__ = [
    "VRSOrchestrator",
    "VideoEffectAnalyzerV2",
    "VideoEffectAnalyzer",
    "VideoReverseEngine",
    "VideoReproducePipeline",
    "KnowledgeRAG",
    "CompositionStructureInferrer",
    "VRCompilerBridge",
    "AudioSyncAnalyzer",
    "IterationOptimizer",
]
