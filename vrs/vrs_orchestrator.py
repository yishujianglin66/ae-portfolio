#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VRS 主编排器 v2.0 - Video Reverse-engineering System Orchestrator
==================================================================

VRS v2.0 端到端工作流入口，整合以下子模块：
1. video_effect_analyzer_v2.py    - CV + VISION 深度分析
2. vrs_knowledge_rag.py            - 知识库 RAG 增强
3. vrs_structure_inferrer.py       - 合成结构推断
4. vrs_compiler_bridge.py          - 编译器桥接（生成 AE 脚本/MCP 命令）
5. vrs_audio_sync_analyzer.py      - 音画同步分析（可选）
6. vrs_iteration_optimizer.py      - 迭代优化器（可选）

设计原则：
- 懒加载：所有子模块按需初始化，降低启动成本
- 容错降级：任一阶段失败不中断整个流程，记录 error 后继续
- 异步优先：所有 I/O 操作使用 async/await
- 流式支持：stream_reverse_engineer 提供进度回调

用法：
    # 仅分析
    python vrs_orchestrator.py --analyze path/to/video.mp4

    # 完整复现（含渲染）
    python vrs_orchestrator.py --reproduce path/to/video.mp4

    # 迭代复现
    python vrs_orchestrator.py --reproduce-iter path/to/video.mp4

    # 演示模式
    python vrs_orchestrator.py --demo
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, Optional

from loguru import logger

# 加载 .env 环境变量（确保 LLM 网关能读取到 API Key）
try:
    from dotenv import load_dotenv  # type: ignore
    # .env 文件位于项目根目录（vrs/ 的父目录），而非 vrs/ 子目录
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=True)  # 强制覆盖系统环境变量
except ImportError:
    pass

# =============================================================================
# 项目根目录与路径
# =============================================================================
# vrs_orchestrator.py 位于 vrs/ 子目录，_PROJECT_ROOT 指向 vrs/
# 同时需要把项目根目录（vrs/ 的父目录）加入 sys.path，
# 这样 vrs/__init__.py 中的 `from vrs.xxx import yyy` 才能正常工作。
_PROJECT_ROOT: Path = Path(__file__).resolve().parent
_PARENT_ROOT: Path = _PROJECT_ROOT.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))
if str(_PARENT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PARENT_ROOT))


# =============================================================================
# 默认配置与阶段定义
# =============================================================================

DEFAULT_OPTIONS: Dict[str, Any] = {
    "detail_level": "standard",        # quick/standard/full
    "enable_vision": True,             # 启用 VISION LLM
    "enable_rag": True,                # 启用知识库增强
    "enable_structure": True,          # 启用结构推断
    "enable_audio_sync": True,         # 启用音频同步分析
    "enable_iteration": False,         # 默认关闭迭代（成本高）
    "max_iterations": 5,               # 最大迭代次数
    "target_similarity": 0.85,         # 目标相似度
    "output_dir": "output/vrs",        # 输出目录
    "render": True,                    # 是否渲染
    "cleanup_temp": True,              # 清理临时文件
}

# 阶段定义：(stage_id, stage_name, weight) - weight 总和为 1.0
STAGES: List[tuple] = [
    ("cv_vision_analysis", "CV+VISION深度分析", 0.25),
    ("rag_enhancement", "知识库增强", 0.10),
    ("audio_sync_analysis", "音画同步分析", 0.15),
    ("structure_inference", "合成结构推断", 0.15),
    ("compilation", "编译生成AE脚本", 0.15),
    ("rendering", "渲染输出", 0.15),
    ("iteration_optimization", "迭代优化", 0.05),
]


# =============================================================================
# 主编排器
# =============================================================================

class VRSOrchestrator:
    """VRS v2.0 主编排器 - 端到端视频效果逆向分析与复现。

    整合 CV/VISION 分析、知识库 RAG、结构推断、编译器桥接、音画同步、
    迭代优化六大子模块，提供从分析到复现的完整工作流。

    所有子模块懒加载，首次使用时才初始化，降低启动成本。
    """

    VERSION: str = "2.0"

    def __init__(self, config: Optional[dict] = None) -> None:
        """初始化编排器。

        Args:
            config: 配置字典，覆盖 DEFAULT_OPTIONS。支持字段：
                - detail_level: 分析精度 quick/standard/full
                - enable_vision: 是否启用 VISION LLM
                - enable_rag: 是否启用知识库增强
                - enable_structure: 是否启用结构推断
                - enable_audio_sync: 是否启用音频同步分析
                - enable_iteration: 是否启用迭代优化
                - max_iterations: 最大迭代次数
                - target_similarity: 目标相似度
                - output_dir: 输出目录
                - render: 是否渲染
                - cleanup_temp: 是否清理临时文件
        """
        self.config: Dict[str, Any] = {**DEFAULT_OPTIONS, **(config or {})}

        # 子模块懒加载缓存
        self._analyzer_v2: Optional[Any] = None
        self._rag: Optional[Any] = None
        self._structure_inferrer: Optional[Any] = None
        self._compiler_bridge: Optional[Any] = None
        self._audio_sync_analyzer: Optional[Any] = None
        self._iteration_optimizer: Optional[Any] = None
        self._ae_engine: Optional[Any] = None

        # 模块可用性标记
        self._module_available: Dict[str, bool] = {
            "analyzer_v2": True,
            "rag": True,
            "structure_inferrer": True,
            "compiler_bridge": True,
            "audio_sync_analyzer": True,
            "iteration_optimizer": True,
            "ae_engine": True,
        }

        self._logger = logger.bind(module="VRS.Orchestrator")
        self._logger.info(f"VRSOrchestrator v{self.VERSION} 初始化完成")

    # -------------------------------------------------------------------------
    # 子模块懒加载
    # -------------------------------------------------------------------------

    def _get_analyzer_v2(self) -> Any:
        """懒加载 VideoEffectAnalyzerV2"""
        if self._analyzer_v2 is None:
            try:
                from vrs.video_effect_analyzer_v2 import VideoEffectAnalyzerV2
                self._analyzer_v2 = VideoEffectAnalyzerV2(
                    enable_vision=self.config.get("enable_vision", True),
                )
                self._logger.debug("VideoEffectAnalyzerV2 加载成功")
            except Exception as e:
                self._module_available["analyzer_v2"] = False
                self._logger.error(f"VideoEffectAnalyzerV2 加载失败: {e}")
                raise
        return self._analyzer_v2

    def _get_rag(self) -> Any:
        """懒加载 KnowledgeRAG"""
        if self._rag is None:
            try:
                from vrs.vrs_knowledge_rag import KnowledgeRAG
                self._rag = KnowledgeRAG()
                self._logger.debug("KnowledgeRAG 加载成功")
            except Exception as e:
                self._module_available["rag"] = False
                self._logger.error(f"KnowledgeRAG 加载失败: {e}")
                raise
        return self._rag

    def _get_structure_inferrer(self) -> Any:
        """懒加载 CompositionStructureInferrer"""
        if self._structure_inferrer is None:
            try:
                from vrs.vrs_structure_inferrer import CompositionStructureInferrer
                self._structure_inferrer = CompositionStructureInferrer()
                self._logger.debug("CompositionStructureInferrer 加载成功")
            except Exception as e:
                self._module_available["structure_inferrer"] = False
                self._logger.error(f"CompositionStructureInferrer 加载失败: {e}")
                raise
        return self._structure_inferrer

    def _get_compiler_bridge(self) -> Any:
        """懒加载 VRCompilerBridge"""
        if self._compiler_bridge is None:
            try:
                from vrs.vrs_compiler_bridge import VRCompilerBridge
                self._compiler_bridge = VRCompilerBridge()
                self._logger.debug("VRCompilerBridge 加载成功")
            except Exception as e:
                self._module_available["compiler_bridge"] = False
                self._logger.error(f"VRCompilerBridge 加载失败: {e}")
                raise
        return self._compiler_bridge

    def _get_audio_sync_analyzer(self) -> Optional[Any]:
        """懒加载 AudioSyncAnalyzer（可能不可用）"""
        if not self._module_available["audio_sync_analyzer"]:
            return None
        if self._audio_sync_analyzer is None:
            try:
                from vrs.vrs_audio_sync_analyzer import AudioSyncAnalyzer
                self._audio_sync_analyzer = AudioSyncAnalyzer()
                self._logger.debug("AudioSyncAnalyzer 加载成功")
            except Exception as e:
                self._module_available["audio_sync_analyzer"] = False
                self._logger.warning(f"AudioSyncAnalyzer 不可用，将跳过音画同步分析: {e}")
        return self._audio_sync_analyzer

    def _get_iteration_optimizer(self) -> Optional[Any]:
        """懒加载 IterationOptimizer（可能不可用）"""
        if not self._module_available["iteration_optimizer"]:
            return None
        if self._iteration_optimizer is None:
            try:
                from vrs.vrs_iteration_optimizer import IterationOptimizer
                self._iteration_optimizer = IterationOptimizer()
                self._logger.debug("IterationOptimizer 加载成功")
            except Exception as e:
                self._module_available["iteration_optimizer"] = False
                self._logger.warning(f"IterationOptimizer 不可用，将跳过迭代优化: {e}")
        return self._iteration_optimizer

    def _get_ae_engine(self) -> Optional[Any]:
        """懒加载 AEEngine（可能不可用）"""
        if not self._module_available["ae_engine"]:
            return None
        if self._ae_engine is None:
            try:
                # 优先从 puppet-automation 导入
                puppet_root = _PROJECT_ROOT / "puppet-automation"
                if str(puppet_root) not in sys.path:
                    sys.path.insert(0, str(puppet_root))
                from src.engines.ae.engine import AEEngine
                self._ae_engine = AEEngine()
                self._logger.debug("AEEngine 加载成功")
            except Exception as e:
                self._module_available["ae_engine"] = False
                self._logger.warning(f"AEEngine 不可用，渲染阶段将降级: {e}")
        return self._ae_engine

    # -------------------------------------------------------------------------
    # 工具方法
    # -------------------------------------------------------------------------

    def _prepare_output_dir(self, video_path: str) -> Path:
        """准备输出目录：output/vrs/{timestamp}/"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = Path(self.config.get("output_dir", "output/vrs")) / timestamp
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _save_json(self, data: Any, path: Path) -> None:
        """安全保存 JSON 文件"""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
        except Exception as e:
            self._logger.error(f"保存 JSON 失败 {path}: {e}")

    def _merge_options(self, options: Optional[dict]) -> Dict[str, Any]:
        """合并传入的 options 与默认配置"""
        return {**self.config, **(options or {})}

    # -------------------------------------------------------------------------
    # 主入口：端到端逆向分析
    # -------------------------------------------------------------------------

    async def reverse_engineer(
        self,
        video_path: str,
        options: Optional[dict] = None,
    ) -> Dict[str, Any]:
        """端到端视频效果逆向分析与复现。

        完整流程：
            1. CV+VISION 深度分析
            2. 知识库 RAG 增强
            3. 音频同步分析（可选）
            4. 合成结构推断
            5. 编译生成 AE 脚本
            6. 渲染输出
            7. 迭代优化（可选）

        Args:
            video_path: 视频文件路径
            options: 临时覆盖配置，字段见 DEFAULT_OPTIONS

        Returns:
            {
                analysis_report: 分析报告 (dict),
                structure_blueprint: 结构蓝图 (dict),
                ae_script_path: AE 脚本路径 (str),
                rendered_video_path: 渲染输出路径 (str|None),
                final_similarity: 最终相似度 (float),
                iterations: 迭代次数 (int),
                output_dir: 输出目录 (str),
                errors: 各阶段错误列表 (list),
            }
        """
        opts = self._merge_options(options)
        video_path = str(video_path)

        if not Path(video_path).exists():
            return {"success": False, "error": f"视频文件不存在: {video_path}"}

        output_dir = self._prepare_output_dir(video_path)
        self._logger.info(f"开始端到端逆向分析: {video_path}")
        self._logger.info(f"输出目录: {output_dir}")

        errors: List[Dict[str, str]] = []
        result: Dict[str, Any] = {
            "output_dir": str(output_dir),
            "video_path": video_path,
            "errors": errors,
            "iterations": 0,
            "final_similarity": 0.0,
        }

        # === 阶段 1: CV+VISION 深度分析 ===
        analysis_data = await self._stage_cv_vision_analysis(
            video_path, opts, output_dir, errors
        )

        # === 阶段 2: 知识库 RAG 增强 ===
        enhanced_data = await self._stage_rag_enhancement(
            analysis_data, opts, output_dir, errors
        )

        # === 阶段 3: 音画同步分析 ===
        audio_sync_data = await self._stage_audio_sync_analysis(
            video_path, opts, output_dir, errors
        )

        # === 阶段 4: 合成结构推断 ===
        structure_blueprint = await self._stage_structure_inference(
            enhanced_data, analysis_data, opts, output_dir, errors
        )

        # === 阶段 5: 编译生成 AE 脚本 ===
        compile_result = await self._stage_compilation(
            enhanced_data, opts, output_dir, errors
        )

        # === 阶段 6: 渲染输出 ===
        rendered_path = await self._stage_rendering(
            compile_result, opts, output_dir, errors
        )

        # === 阶段 7: 迭代优化 ===
        if opts.get("enable_iteration", False):
            iter_result = await self._stage_iteration_optimization(
                video_path, enhanced_data, opts, output_dir, errors
            )
            result["iterations"] = iter_result.get("iterations", 0)
            result["final_similarity"] = iter_result.get("final_similarity", 0.0)
            if iter_result.get("final_video_path"):
                rendered_path = iter_result["final_video_path"]
        else:
            result["iterations"] = 0
            result["final_similarity"] = 0.0

        # 汇总结果
        result.update({
            "success": True,
            "analysis_report": enhanced_data,
            "structure_blueprint": structure_blueprint,
            "ae_script_path": compile_result.get("script_path"),
            "rendered_video_path": rendered_path,
            "audio_sync": audio_sync_data,
            "compiler_input_path": compile_result.get("compiler_input_path"),
            "mcp_commands_path": compile_result.get("mcp_commands_path"),
        })

        # 生成综合报告
        report_path = output_dir / "10_final_report.md"
        try:
            report_md = self.generate_report(result)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_md)
            result["report_path"] = str(report_path)
        except Exception as e:
            self._logger.error(f"生成报告失败: {e}")
            errors.append({"stage": "report", "error": str(e)})

        # 清理临时文件
        if opts.get("cleanup_temp", True):
            self._cleanup_temp(output_dir)

        self._logger.info(f"端到端逆向分析完成，共 {len(errors)} 个错误")
        return result

    # -------------------------------------------------------------------------
    # 仅分析模式
    # -------------------------------------------------------------------------

    async def analyze_only(
        self,
        video_path: str,
        detail_level: str = "standard",
    ) -> Dict[str, Any]:
        """仅分析不复现（不渲染、不迭代）。

        适用于用户只想了解视频用了什么效果的场景。

        Args:
            video_path: 视频文件路径
            detail_level: 分析精度 quick/standard/full

        Returns:
            {
                cv_result: CV 分析结果,
                vision_result: VISION 分析结果,
                enhanced_result: RAG 增强后的结果,
                structure_blueprint: 结构蓝图,
                audio_sync: 音画同步分析,
                analysis_report: 综合分析报告,
            }
        """
        video_path = str(video_path)
        if not Path(video_path).exists():
            return {"success": False, "error": f"视频文件不存在: {video_path}"}

        output_dir = self._prepare_output_dir(video_path)
        errors: List[Dict[str, str]] = []
        opts = {**self.config, "detail_level": detail_level, "render": False, "enable_iteration": False}

        self._logger.info(f"仅分析模式: {video_path} (detail={detail_level})")

        # 阶段 1: CV+VISION 分析
        analysis_data = await self._stage_cv_vision_analysis(
            video_path, opts, output_dir, errors
        )

        # 阶段 2: RAG 增强
        enhanced_data = await self._stage_rag_enhancement(
            analysis_data, opts, output_dir, errors
        )

        # 阶段 3: 音画同步
        audio_sync_data = await self._stage_audio_sync_analysis(
            video_path, opts, output_dir, errors
        )

        # 阶段 4: 结构推断
        structure_blueprint = await self._stage_structure_inference(
            enhanced_data, analysis_data, opts, output_dir, errors
        )

        result = {
            "success": True,
            "cv_result": analysis_data.get("cv_result"),
            "vision_result": analysis_data.get("vision_result"),
            "enhanced_result": enhanced_data,
            "structure_blueprint": structure_blueprint,
            "audio_sync": audio_sync_data,
            "analysis_report": enhanced_data,
            "output_dir": str(output_dir),
            "errors": errors,
        }

        # 生成报告
        report_path = output_dir / "10_final_report.md"
        try:
            report_md = self.generate_report(result)
            with open(report_path, "w", encoding="utf-8") as f:
                f.write(report_md)
            result["report_path"] = str(report_path)
        except Exception as e:
            self._logger.error(f"生成报告失败: {e}")

        return result

    # -------------------------------------------------------------------------
    # 生成 AE 工程
    # -------------------------------------------------------------------------

    async def generate_ae_project(
        self,
        analysis_result: dict,
        output_dir: str,
    ) -> Dict[str, Any]:
        """从分析结果生成 AE 工程（不渲染）。

        输出：CompilerInput JSON、ExtendScript 脚本、MCP 命令序列。

        Args:
            analysis_result: 分析结果字典
            output_dir: 输出目录

        Returns:
            {
                compiler_input_path: 编译器输入 JSON 路径,
                script_path: ExtendScript 脚本路径,
                mcp_commands_path: MCP 命令序列 JSON 路径,
            }
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        errors: List[Dict[str, str]] = []

        compile_result = await self._stage_compilation(
            analysis_result, self.config, output_path, errors
        )

        return {
            "success": bool(compile_result.get("script_path") or compile_result.get("mcp_commands_path")),
            "compiler_input_path": compile_result.get("compiler_input_path"),
            "script_path": compile_result.get("script_path"),
            "mcp_commands_path": compile_result.get("mcp_commands_path"),
            "errors": errors,
        }

    # -------------------------------------------------------------------------
    # 带迭代的完整复现
    # -------------------------------------------------------------------------

    async def reproduce_with_iteration(
        self,
        reference_video: str,
        analysis_result: dict,
        max_iterations: int = 5,
    ) -> Dict[str, Any]:
        """带迭代优化的完整复现。

        Args:
            reference_video: 参考视频路径
            analysis_result: 初始分析结果
            max_iterations: 最大迭代次数

        Returns:
            {
                final_video_path: 最终视频路径,
                final_similarity: 最终相似度,
                iterations: 实际迭代次数,
                optimization_report: 优化报告,
            }
        """
        output_dir = self._prepare_output_dir(reference_video)
        errors: List[Dict[str, str]] = []
        opts = {
            **self.config,
            "enable_iteration": True,
            "max_iterations": max_iterations,
        }

        iter_result = await self._stage_iteration_optimization(
            reference_video, analysis_result, opts, output_dir, errors
        )

        return {
            "success": iter_result.get("final_video_path") is not None,
            "final_video_path": iter_result.get("final_video_path"),
            "final_similarity": iter_result.get("final_similarity", 0.0),
            "iterations": iter_result.get("iterations", 0),
            "optimization_report": iter_result.get("optimization_report"),
            "errors": errors,
        }

    # -------------------------------------------------------------------------
    # 流式版本
    # -------------------------------------------------------------------------

    async def stream_reverse_engineer(
        self,
        video_path: str,
        options: Optional[dict] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """流式版本：通过 async generator 逐步产出各阶段结果。

        用途：前端实时展示进度。

        Args:
            video_path: 视频文件路径
            options: 临时覆盖配置

        Yields:
            {stage, progress, result, message}
            - stage: 阶段 ID
            - progress: 0.0-1.0 累计进度
            - result: 当前阶段结果
            - message: 阶段说明
        """
        opts = self._merge_options(options)
        video_path = str(video_path)

        if not Path(video_path).exists():
            yield {
                "stage": "error",
                "progress": 0.0,
                "result": None,
                "message": f"视频文件不存在: {video_path}",
            }
            return

        output_dir = self._prepare_output_dir(video_path)
        errors: List[Dict[str, str]] = []
        cumulative_weight = 0.0

        self._logger.info(f"流式逆向分析启动: {video_path}")

        # 阶段 1: CV+VISION 分析
        yield {
            "stage": "cv_vision_analysis",
            "progress": cumulative_weight,
            "result": None,
            "message": "开始 CV+VISION 深度分析",
        }
        analysis_data = await self._stage_cv_vision_analysis(
            video_path, opts, output_dir, errors
        )
        cumulative_weight += STAGES[0][2]
        yield {
            "stage": "cv_vision_analysis",
            "progress": cumulative_weight,
            "result": {"cv_result": bool(analysis_data.get("cv_result")),
                       "vision_result": bool(analysis_data.get("vision_result"))},
            "message": "CV+VISION 分析完成",
        }

        # 阶段 2: RAG 增强
        yield {
            "stage": "rag_enhancement",
            "progress": cumulative_weight,
            "result": None,
            "message": "开始知识库增强",
        }
        enhanced_data = await self._stage_rag_enhancement(
            analysis_data, opts, output_dir, errors
        )
        cumulative_weight += STAGES[1][2]
        yield {
            "stage": "rag_enhancement",
            "progress": cumulative_weight,
            "result": {"enhanced": bool(enhanced_data)},
            "message": "知识库增强完成",
        }

        # 阶段 3: 音画同步
        yield {
            "stage": "audio_sync_analysis",
            "progress": cumulative_weight,
            "result": None,
            "message": "开始音画同步分析",
        }
        audio_sync_data = await self._stage_audio_sync_analysis(
            video_path, opts, output_dir, errors
        )
        cumulative_weight += STAGES[2][2]
        yield {
            "stage": "audio_sync_analysis",
            "progress": cumulative_weight,
            "result": {"audio_sync": bool(audio_sync_data)},
            "message": "音画同步分析完成",
        }

        # 阶段 4: 结构推断
        yield {
            "stage": "structure_inference",
            "progress": cumulative_weight,
            "result": None,
            "message": "开始合成结构推断",
        }
        structure_blueprint = await self._stage_structure_inference(
            enhanced_data, analysis_data, opts, output_dir, errors
        )
        cumulative_weight += STAGES[3][2]
        yield {
            "stage": "structure_inference",
            "progress": cumulative_weight,
            "result": {"layers": len(structure_blueprint.get("layers", []))},
            "message": "合成结构推断完成",
        }

        # 阶段 5: 编译
        yield {
            "stage": "compilation",
            "progress": cumulative_weight,
            "result": None,
            "message": "开始编译生成 AE 脚本",
        }
        compile_result = await self._stage_compilation(
            enhanced_data, opts, output_dir, errors
        )
        cumulative_weight += STAGES[4][2]
        yield {
            "stage": "compilation",
            "progress": cumulative_weight,
            "result": {"script_path": compile_result.get("script_path")},
            "message": "编译完成",
        }

        # 阶段 6: 渲染
        rendered_path = None
        if opts.get("render", True):
            yield {
                "stage": "rendering",
                "progress": cumulative_weight,
                "result": None,
                "message": "开始渲染输出",
            }
            rendered_path = await self._stage_rendering(
                compile_result, opts, output_dir, errors
            )
            cumulative_weight += STAGES[5][2]
            yield {
                "stage": "rendering",
                "progress": cumulative_weight,
                "result": {"rendered_video_path": rendered_path},
                "message": "渲染完成" if rendered_path else "渲染失败（已降级）",
            }
        else:
            cumulative_weight += STAGES[5][2]

        # 阶段 7: 迭代优化
        if opts.get("enable_iteration", False):
            yield {
                "stage": "iteration_optimization",
                "progress": cumulative_weight,
                "result": None,
                "message": "开始迭代优化",
            }
            iter_result = await self._stage_iteration_optimization(
                video_path, enhanced_data, opts, output_dir, errors
            )
            cumulative_weight += STAGES[6][2]
            if iter_result.get("final_video_path"):
                rendered_path = iter_result["final_video_path"]
            yield {
                "stage": "iteration_optimization",
                "progress": 1.0,
                "result": {
                    "iterations": iter_result.get("iterations", 0),
                    "final_similarity": iter_result.get("final_similarity", 0.0),
                    "final_video_path": rendered_path,
                },
                "message": "迭代优化完成",
            }
        else:
            cumulative_weight += STAGES[6][2]

        yield {
            "stage": "completed",
            "progress": 1.0,
            "result": {
                "output_dir": str(output_dir),
                "rendered_video_path": rendered_path,
                "errors": errors,
            },
            "message": f"全部阶段完成（{len(errors)} 个错误）",
        }

    # -------------------------------------------------------------------------
    # 报告生成
    # -------------------------------------------------------------------------

    def generate_report(self, result: dict) -> str:
        """生成 Markdown 格式的完整分析报告。

        包含：视频基本信息、检测到的效果清单、调色参数、结构蓝图、
        音画同步分析、复现结果、相似度评估。

        Args:
            result: reverse_engineer 或 analyze_only 的返回结果

        Returns:
            Markdown 格式字符串
        """
        lines: List[str] = []
        lines.append("# VRS v2.0 视频逆向分析报告")
        lines.append("")
        lines.append(f"- 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 视频路径: `{result.get('video_path', 'N/A')}`")
        lines.append(f"- 输出目录: `{result.get('output_dir', 'N/A')}`")
        lines.append("")

        # 错误汇总
        errors = result.get("errors", [])
        if errors:
            lines.append("## ⚠️ 阶段错误汇总")
            lines.append("")
            for err in errors:
                lines.append(f"- **{err.get('stage', 'unknown')}**: {err.get('error', '')}")
            lines.append("")

        # 视频基本信息
        analysis = result.get("analysis_report") or result.get("enhanced_result") or {}
        cv_result = result.get("cv_result") or analysis.get("cv_result") or {}
        basic_info = cv_result.get("basic_info") or analysis.get("basic_info") or {}

        lines.append("## 1. 视频基本信息")
        lines.append("")
        if basic_info:
            lines.append(f"- 分辨率: {basic_info.get('width', '?')}x{basic_info.get('height', '?')}")
            lines.append(f"- 帧率: {basic_info.get('fps', '?')} fps")
            lines.append(f"- 时长: {basic_info.get('duration', '?')} 秒")
            lines.append(f"- 总帧数: {basic_info.get('total_frames', '?')}")
        else:
            lines.append("（未获取到视频基本信息）")
        lines.append("")

        # 检测到的效果清单
        vision_result = result.get("vision_result") or analysis.get("vision_result") or {}
        # 兼容多种数据结构：
        #   - vision_result.effects = [...]
        #   - analysis.effects = [...]
        #   - cv_result.visual_effects = {"detected_effects": [...]} 或 [...]
        effects = (
            vision_result.get("effects")
            or analysis.get("effects")
            or []
        )
        if not effects:
            ve = cv_result.get("visual_effects") or {}
            if isinstance(ve, dict):
                effects = ve.get("detected_effects", [])
            elif isinstance(ve, list):
                effects = ve
        lines.append("## 2. 检测到的效果清单")
        lines.append("")
        if effects:
            lines.append("| # | 效果名 | 类型 | 强度 | 置信度 |")
            lines.append("|---|--------|------|------|--------|")
            for i, eff in enumerate(effects, 1):
                # 兼容 eff 为字符串的情况（降级保护）
                if isinstance(eff, str):
                    lines.append(f"| {i} | {eff} | - | - | - |")
                    continue
                if not isinstance(eff, dict):
                    continue
                name = eff.get("effect_name") or eff.get("name") or eff.get("type", "?")
                cat = eff.get("category") or eff.get("type", "?")
                intensity = eff.get("intensity", "?")
                confidence = eff.get("confidence", "?")
                lines.append(f"| {i} | {name} | {cat} | {intensity} | {confidence} |")
        else:
            lines.append("（未检测到明显效果）")
        lines.append("")

        # 调色参数
        color_grading = (
            analysis.get("color_grading")
            or cv_result.get("color_grading")
            or {}
        )
        lines.append("## 3. 调色参数")
        lines.append("")
        if color_grading:
            lines.append("```json")
            lines.append(json.dumps(color_grading, ensure_ascii=False, indent=2, default=str))
            lines.append("```")
        else:
            lines.append("（未检测到调色信息）")
        lines.append("")

        # 结构蓝图
        blueprint = result.get("structure_blueprint") or {}
        lines.append("## 4. 合成结构蓝图")
        lines.append("")
        if blueprint:
            comp = blueprint.get("composition", {})
            layers = blueprint.get("layers", [])
            lines.append(f"- 合成名: {comp.get('name', 'N/A')}")
            lines.append(f"- 分辨率: {comp.get('width', '?')}x{comp.get('height', '?')}")
            lines.append(f"- 帧率: {comp.get('fps', '?')} fps")
            lines.append(f"- 时长: {comp.get('duration', '?')} 秒")
            lines.append(f"- 图层数: {len(layers)}")
            lines.append("")
            if layers:
                lines.append("### 图层堆栈（从上到下）")
                lines.append("")
                lines.append("| # | 类型 | 名称 | 混合模式 |")
                lines.append("|---|------|------|----------|")
                for i, layer in enumerate(layers, 1):
                    ltype = layer.get("type", "?")
                    lname = layer.get("name", "?")
                    blend = layer.get("blend_mode", "NORMAL")
                    lines.append(f"| {i} | {ltype} | {lname} | {blend} |")
                lines.append("")
        else:
            lines.append("（未生成结构蓝图）")
        lines.append("")

        # 音画同步分析
        audio_sync = result.get("audio_sync") or {}
        lines.append("## 5. 音画同步分析")
        lines.append("")
        if audio_sync:
            lines.append("```json")
            lines.append(json.dumps(audio_sync, ensure_ascii=False, indent=2, default=str))
            lines.append("```")
        else:
            lines.append("（未执行音画同步分析或分析失败）")
        lines.append("")

        # 复现结果
        lines.append("## 6. 复现结果")
        lines.append("")
        script_path = result.get("ae_script_path")
        rendered_path = result.get("rendered_video_path")
        lines.append(f"- AE 脚本路径: `{script_path or 'N/A'}`")
        lines.append(f"- 渲染输出路径: `{rendered_path or 'N/A（未渲染）'}`")
        lines.append(f"- 迭代次数: {result.get('iterations', 0)}")
        lines.append(f"- 最终相似度: {result.get('final_similarity', 0.0):.4f}")
        lines.append("")

        # 复现文件清单
        lines.append("## 7. 输出文件清单")
        lines.append("")
        output_dir = result.get("output_dir")
        if output_dir:
            out_path = Path(output_dir)
            if out_path.exists():
                lines.append("```")
                for f in sorted(out_path.iterdir()):
                    size = f.stat().st_size if f.is_file() else 0
                    lines.append(f"{f.name}  ({size} bytes)")
                lines.append("```")
        lines.append("")

        lines.append("---")
        lines.append("*由 VRS v2.0 Orchestrator 自动生成*")

        return "\n".join(lines)

    # =========================================================================
    # 内部阶段实现
    # =========================================================================

    async def _stage_cv_vision_analysis(
        self,
        video_path: str,
        opts: dict,
        output_dir: Path,
        errors: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """阶段 1: CV+VISION 深度分析"""
        self._logger.info("阶段 1: CV+VISION 深度分析")
        try:
            analyzer = self._get_analyzer_v2()
            detail_level = opts.get("detail_level", "standard")
            result = await analyzer.analyze_video_deep(video_path, detail_level=detail_level)
            self._save_json(result, output_dir / "01_analysis_cv_vision.json")
            self._logger.info("CV+VISION 分析完成")
            return result
        except Exception as e:
            err_msg = f"CV+VISION 分析失败: {e}"
            self._logger.error(err_msg)
            errors.append({"stage": "cv_vision_analysis", "error": str(e)})
            # 降级：返回空结果
            return {"success": False, "error": str(e), "cv_result": {}, "vision_result": {}}

    async def _stage_rag_enhancement(
        self,
        analysis_data: Dict[str, Any],
        opts: dict,
        output_dir: Path,
        errors: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """阶段 2: 知识库 RAG 增强"""
        if not opts.get("enable_rag", True):
            self._logger.info("阶段 2: RAG 增强已禁用，跳过")
            return analysis_data

        self._logger.info("阶段 2: 知识库 RAG 增强")
        try:
            rag = self._get_rag()
            # 增强基于 vision_result
            vision_result = analysis_data.get("vision_result") or analysis_data
            enhanced = rag.enhance_analysis(vision_result)
            # 合并原始分析与增强结果
            merged = {**analysis_data, **enhanced} if isinstance(enhanced, dict) else analysis_data
            merged["rag_enhanced"] = True
            self._save_json(merged, output_dir / "02_analysis_enhanced.json")
            self._logger.info("RAG 增强完成")
            return merged
        except Exception as e:
            err_msg = f"RAG 增强失败: {e}"
            self._logger.warning(err_msg)
            errors.append({"stage": "rag_enhancement", "error": str(e)})
            # 降级：跳过增强，返回原始分析
            return analysis_data

    async def _stage_audio_sync_analysis(
        self,
        video_path: str,
        opts: dict,
        output_dir: Path,
        errors: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """阶段 3: 音画同步分析"""
        if not opts.get("enable_audio_sync", True):
            self._logger.info("阶段 3: 音画同步分析已禁用，跳过")
            return {}

        self._logger.info("阶段 3: 音画同步分析")
        analyzer = self._get_audio_sync_analyzer()
        if analyzer is None:
            errors.append({
                "stage": "audio_sync_analysis",
                "error": "AudioSyncAnalyzer 模块不可用",
            })
            return {}

        try:
            # 音频路径默认从视频提取（analyzer 内部处理）
            result = await analyzer.analyze_sync(video_path, audio_path=None)
            self._save_json(result, output_dir / "03_audio_sync.json")
            self._logger.info("音画同步分析完成")
            return result
        except Exception as e:
            err_msg = f"音画同步分析失败: {e}"
            self._logger.warning(err_msg)
            errors.append({"stage": "audio_sync_analysis", "error": str(e)})
            return {}

    async def _stage_structure_inference(
        self,
        enhanced_data: Dict[str, Any],
        analysis_data: Dict[str, Any],
        opts: dict,
        output_dir: Path,
        errors: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """阶段 4: 合成结构推断"""
        if not opts.get("enable_structure", True):
            self._logger.info("阶段 4: 结构推断已禁用，跳过")
            return {}

        self._logger.info("阶段 4: 合成结构推断")
        try:
            inferrer = self._get_structure_inferrer()
            vision_result = analysis_data.get("vision_result")
            blueprint = await inferrer.infer_structure(
                analysis_result=enhanced_data,
                vision_result=vision_result,
            )
            self._save_json(blueprint, output_dir / "04_structure_blueprint.json")
            self._logger.info("合成结构推断完成")
            return blueprint
        except Exception as e:
            err_msg = f"合成结构推断失败: {e}"
            self._logger.warning(err_msg)
            errors.append({"stage": "structure_inference", "error": str(e)})
            # 降级：返回简化结构
            return {
                "composition": {"name": "降级简化合成", "width": 1920, "height": 1080, "fps": 30, "duration": 10.0},
                "layers": [
                    {"type": "adjustment", "name": "调色层", "blend_mode": "NORMAL"},
                    {"type": "footage", "name": "主体层", "blend_mode": "NORMAL"},
                ],
                "operations": [],
                "degraded": True,
                "error": str(e),
            }

    async def _stage_compilation(
        self,
        enhanced_data: Dict[str, Any],
        opts: dict,
        output_dir: Path,
        errors: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """阶段 5: 编译生成 AE 脚本"""
        self._logger.info("阶段 5: 编译生成 AE 脚本")
        result: Dict[str, Any] = {
            "compiler_input_path": None,
            "script_path": None,
            "mcp_commands_path": None,
        }
        try:
            bridge = self._get_compiler_bridge()

            # 生成 CompilerInput
            compiler_input = bridge.convert_analysis_to_compiler_input(enhanced_data)
            input_path = output_dir / "05_compiler_input.json"
            self._save_json(compiler_input, input_path)
            result["compiler_input_path"] = str(input_path)

            # 尝试编译为 ExtendScript
            try:
                script_result = bridge.compile_to_script(compiler_input)
                script_content = (
                    script_result.get("script")
                    if isinstance(script_result, dict)
                    else None
                )
                if script_content:
                    script_path = output_dir / "06_ae_script.jsx"
                    with open(script_path, "w", encoding="utf-8") as f:
                        f.write(script_content)
                    result["script_path"] = str(script_path)
                    self._logger.info(f"AE 脚本生成完成: {script_path}")
            except Exception as e:
                self._logger.warning(f"编译为 ExtendScript 失败，降级为 MCP 命令: {e}")
                errors.append({"stage": "compilation.script", "error": str(e)})

            # 生成 MCP 命令序列（作为替代或补充）
            try:
                mcp_commands = bridge.compile_analysis_to_mcp_commands(enhanced_data)
                mcp_path = output_dir / "07_mcp_commands.json"
                self._save_json(mcp_commands, mcp_path)
                result["mcp_commands_path"] = str(mcp_path)
                self._logger.info(f"MCP 命令序列生成完成: {mcp_path}")
            except Exception as e:
                self._logger.warning(f"MCP 命令生成失败: {e}")
                errors.append({"stage": "compilation.mcp", "error": str(e)})

            # 如果脚本和 MCP 都失败，记录错误
            if not result["script_path"] and not result["mcp_commands_path"]:
                errors.append({
                    "stage": "compilation",
                    "error": "编译完全失败：既无脚本也无 MCP 命令",
                })

            return result
        except Exception as e:
            err_msg = f"编译阶段失败: {e}"
            self._logger.error(err_msg)
            errors.append({"stage": "compilation", "error": str(e)})
            return result

    async def _stage_rendering(
        self,
        compile_result: Dict[str, Any],
        opts: dict,
        output_dir: Path,
        errors: List[Dict[str, str]],
    ) -> Optional[str]:
        """阶段 6: 渲染输出"""
        if not opts.get("render", True):
            self._logger.info("阶段 6: 渲染已禁用，跳过")
            return None

        self._logger.info("阶段 6: 渲染输出")
        script_path = compile_result.get("script_path")
        if not script_path:
            err_msg = "渲染跳过：无可用 AE 脚本"
            self._logger.warning(err_msg)
            errors.append({"stage": "rendering", "error": err_msg})
            return None

        ae_engine = self._get_ae_engine()
        if ae_engine is None:
            errors.append({
                "stage": "rendering",
                "error": "AEEngine 不可用，请手动执行脚本: " + str(script_path),
            })
            return None

        try:
            # 读取脚本内容
            with open(script_path, "r", encoding="utf-8") as f:
                script_content = f.read()

            # 通过 AEEngine 执行脚本
            output_video = output_dir / "08_rendered_v1.mp4"
            engine_result = await ae_engine.run_script(script_content=script_content)

            if engine_result.success:
                self._logger.info(f"渲染完成: {output_video}")
                return str(output_video)
            else:
                err_msg = f"渲染失败: {getattr(engine_result, 'error', 'unknown')}"
                self._logger.error(err_msg)
                errors.append({
                    "stage": "rendering",
                    "error": err_msg + f"，请手动执行脚本: {script_path}",
                })
                return None
        except Exception as e:
            err_msg = f"渲染阶段失败: {e}"
            self._logger.error(err_msg)
            errors.append({
                "stage": "rendering",
                "error": f"{err_msg}，请手动执行脚本: {script_path}",
            })
            return None

    async def _stage_iteration_optimization(
        self,
        reference_video: str,
        analysis_data: Dict[str, Any],
        opts: dict,
        output_dir: Path,
        errors: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """阶段 7: 迭代优化"""
        self._logger.info("阶段 7: 迭代优化")
        optimizer = self._get_iteration_optimizer()
        if optimizer is None:
            errors.append({
                "stage": "iteration_optimization",
                "error": "IterationOptimizer 模块不可用，返回 v1 版本",
            })
            return {"iterations": 0, "final_similarity": 0.0, "final_video_path": None}

        try:
            max_iter = opts.get("max_iterations", 5)
            target_sim = opts.get("target_similarity", 0.85)
            result = await optimizer.optimize(
                reference=reference_video,
                initial_analysis=analysis_data,
                max_iterations=max_iter,
                target_similarity=target_sim,
            )

            # 保存迭代报告
            report_path = output_dir / "09_iteration_report.md"
            try:
                with open(report_path, "w", encoding="utf-8") as f:
                    f.write(f"# 迭代优化报告\n\n")
                    f.write(f"- 最大迭代次数: {max_iter}\n")
                    f.write(f"- 目标相似度: {target_sim}\n")
                    f.write(f"- 实际迭代次数: {result.get('iterations', 0)}\n")
                    f.write(f"- 最终相似度: {result.get('final_similarity', 0.0):.4f}\n")
                    f.write(f"- 最终视频: `{result.get('final_video_path', 'N/A')}`\n")
            except Exception as e:
                self._logger.warning(f"保存迭代报告失败: {e}")

            # 如果有最终视频，复制到 11_final_video.mp4
            final_video = result.get("final_video_path")
            if final_video and Path(final_video).exists():
                final_dest = output_dir / "11_final_video.mp4"
                try:
                    import shutil
                    shutil.copy2(final_video, final_dest)
                    result["final_video_path"] = str(final_dest)
                except Exception as e:
                    self._logger.warning(f"复制最终视频失败: {e}")

            self._logger.info(
                f"迭代优化完成: {result.get('iterations', 0)} 次, "
                f"相似度 {result.get('final_similarity', 0.0):.4f}"
            )
            return result
        except Exception as e:
            err_msg = f"迭代优化失败: {e}"
            self._logger.error(err_msg)
            errors.append({
                "stage": "iteration_optimization",
                "error": f"{err_msg}，返回 v1 版本",
            })
            return {"iterations": 0, "final_similarity": 0.0, "final_video_path": None}

    # -------------------------------------------------------------------------
    # 临时文件清理
    # -------------------------------------------------------------------------

    def _cleanup_temp(self, output_dir: Path) -> None:
        """清理临时文件（保留最终产物）"""
        try:
            # 保留所有以数字编号的最终产物，清理临时帧目录等
            temp_patterns = ["temp_", "tmp_", "frames_temp"]
            for item in output_dir.iterdir():
                if any(item.name.startswith(p) for p in temp_patterns):
                    if item.is_dir():
                        import shutil
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
            self._logger.debug("临时文件清理完成")
        except Exception as e:
            self._logger.warning(f"清理临时文件失败: {e}")


# =============================================================================
# CLI 入口
# =============================================================================

async def _cli_analyze(video_path: str, detail_level: str = "standard") -> None:
    """CLI: 仅分析模式"""
    orchestrator = VRSOrchestrator()
    result = await orchestrator.analyze_only(video_path, detail_level=detail_level)
    print(json.dumps({
        "success": result.get("success"),
        "output_dir": result.get("output_dir"),
        "report_path": result.get("report_path"),
        "errors": result.get("errors", []),
    }, ensure_ascii=False, indent=2, default=str))


async def _cli_reproduce(video_path: str, render: bool = True) -> None:
    """CLI: 完整复现模式"""
    orchestrator = VRSOrchestrator({"render": render, "enable_iteration": False})
    result = await orchestrator.reverse_engineer(video_path)
    print(json.dumps({
        "success": result.get("success"),
        "output_dir": result.get("output_dir"),
        "ae_script_path": result.get("ae_script_path"),
        "rendered_video_path": result.get("rendered_video_path"),
        "report_path": result.get("report_path"),
        "errors": result.get("errors", []),
    }, ensure_ascii=False, indent=2, default=str))


async def _cli_reproduce_iter(video_path: str, max_iter: int = 5) -> None:
    """CLI: 迭代复现模式"""
    orchestrator = VRSOrchestrator({
        "render": True,
        "enable_iteration": True,
        "max_iterations": max_iter,
    })
    result = await orchestrator.reverse_engineer(video_path)
    print(json.dumps({
        "success": result.get("success"),
        "output_dir": result.get("output_dir"),
        "rendered_video_path": result.get("rendered_video_path"),
        "iterations": result.get("iterations"),
        "final_similarity": result.get("final_similarity"),
        "report_path": result.get("report_path"),
        "errors": result.get("errors", []),
    }, ensure_ascii=False, indent=2, default=str))


async def _cli_demo() -> None:
    """CLI: 演示模式（用 output/test_sample.mp4）"""
    sample = _PROJECT_ROOT / "output" / "test_sample.mp4"
    if not sample.exists():
        print(f"演示视频不存在: {sample}")
        print("请先放置一个测试视频到该路径，或使用 --analyze <your_video> 指定路径")
        return

    print(f"=== VRS v2.0 演示模式 ===")
    print(f"视频: {sample}")
    print(f"模式: analyze_only（仅分析，不渲染不迭代）")
    print()

    orchestrator = VRSOrchestrator()
    result = await orchestrator.analyze_only(str(sample), detail_level="standard")

    print(f"分析完成: success={result.get('success')}")
    print(f"输出目录: {result.get('output_dir')}")
    print(f"报告路径: {result.get('report_path')}")
    if result.get("errors"):
        print(f"阶段错误数: {len(result['errors'])}")
        for err in result["errors"]:
            print(f"  - {err.get('stage')}: {err.get('error')}")


def _main() -> None:
    """CLI 入口"""
    parser = argparse.ArgumentParser(
        description="VRS v2.0 视频逆向分析编排器",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python vrs_orchestrator.py --analyze video.mp4
  python vrs_orchestrator.py --analyze video.mp4 --detail full
  python vrs_orchestrator.py --reproduce video.mp4
  python vrs_orchestrator.py --reproduce-iter video.mp4 --max-iter 5
  python vrs_orchestrator.py --demo
        """,
    )
    parser.add_argument("--analyze", metavar="PATH", help="仅分析模式：只分析不复现")
    parser.add_argument("--reproduce", metavar="PATH", help="完整复现模式（含渲染）")
    parser.add_argument("--reproduce-iter", metavar="PATH", help="迭代复现模式")
    parser.add_argument("--demo", action="store_true", help="演示模式（用 output/test_sample.mp4）")
    parser.add_argument("--detail", default="standard", choices=["quick", "standard", "full"],
                        help="分析精度（默认 standard）")
    parser.add_argument("--max-iter", type=int, default=5, help="最大迭代次数（默认 5）")
    parser.add_argument("--no-render", action="store_true", help="复现模式不渲染")

    args = parser.parse_args()

    # 配置 LLM 网关（从环境变量加载 API Key 和 Provider 配置）
    try:
        from core.llm_gateway import llm_gateway
        llm_gateway.configure_from_env()
        llm_gateway.configure_providers_from_env()
        logger.info(f"LLM 网关已配置: {llm_gateway.is_available()}")
    except Exception as e:
        logger.warning(f"LLM 网关配置失败: {e}")

    if args.demo:
        asyncio.run(_cli_demo())
    elif args.analyze:
        asyncio.run(_cli_analyze(args.analyze, detail_level=args.detail))
    elif args.reproduce:
        asyncio.run(_cli_reproduce(args.reproduce, render=not args.no_render))
    elif args.reproduce_iter:
        asyncio.run(_cli_reproduce_iter(args.reproduce_iter, max_iter=args.max_iter))
    else:
        parser.print_help()


if __name__ == "__main__":
    _main()
