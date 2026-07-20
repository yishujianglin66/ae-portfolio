"""OpenMontage 流水线运行时。

加载并执行 OpenMontage 的 12 个工作流流水线（pipeline_defs/*.yaml）。
每个流水线包含多个阶段（research -> proposal -> script -> scene_plan ->
assets -> edit -> compose -> publish）。
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from loguru import logger


# OpenMontage 项目根目录（如果存在）
OPENMONTAGE_ROOT = Path(
    r"C:\Users\Administrator\Desktop\AE-Knowledge-Vault\external\OpenMontage"
)
PIPELINE_DEFS_DIR = OPENMONTAGE_ROOT / "pipeline_defs"


class PipelineStatus(str, Enum):
    """流水线状态。"""

    PENDING = "pending"
    RUNNING = "running"
    CHECKPOINT = "checkpoint"  # 等待人类审批
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class StageDefinition:
    """单个阶段定义（从 yaml manifest 解析）。"""

    name: str
    skill: Optional[str] = None
    produces: List[str] = field(default_factory=list)
    checkpoint_required: bool = False
    review_focus: List[str] = field(default_factory=list)
    success_criteria: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StageResult:
    """单个阶段的执行结果。"""

    stage_name: str
    status: PipelineStatus
    artifacts: Dict[str, Any] = field(default_factory=dict)
    started_at: float = 0.0
    finished_at: float = 0.0
    error: Optional[str] = None
    notes: str = ""

    @property
    def duration(self) -> float:
        return self.finished_at - self.started_at


@dataclass
class PipelineManifest:
    """流水线 manifest（从 yaml 加载）。"""

    name: str
    version: str
    description: str
    category: str
    stability: str
    stages: List[StageDefinition] = field(default_factory=list)
    reference_input_supported: bool = False
    required_skills: List[str] = field(default_factory=list)
    raw: Dict[str, Any] = field(default_factory=dict)


class OpenMontagePipelineRuntime:
    """OpenMontage 流水线运行时。

    负责加载 yaml manifest、编排阶段执行、产出 artifacts。
    """

    def __init__(self, pipeline_dir: Optional[Path] = None):
        self.pipeline_dir = pipeline_dir or PIPELINE_DEFS_DIR
        self._cache: Dict[str, PipelineManifest] = {}
        self._runs: Dict[str, List[StageResult]] = {}
        logger.info(f"OpenMontage 流水线运行时初始化: {self.pipeline_dir}")

    def list_pipelines(self) -> List[str]:
        """列出所有可用的流水线。"""
        if not self.pipeline_dir.exists():
            logger.warning(f"Pipeline 目录不存在: {self.pipeline_dir}")
            return []
        return sorted([p.stem for p in self.pipeline_dir.glob("*.yaml")])

    def load_pipeline(self, name: str) -> PipelineManifest:
        """加载单个流水线 manifest。"""
        if name in self._cache:
            return self._cache[name]

        path = self.pipeline_dir / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Pipeline manifest not found: {path}")

        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)

        manifest = PipelineManifest(
            name=raw.get("name", name),
            version=raw.get("version", "1.0"),
            description=raw.get("description", "").strip(),
            category=raw.get("category", "general"),
            stability=raw.get("stability", "experimental"),
            reference_input_supported=raw.get("reference_input", {}).get("supported", False),
            required_skills=raw.get("required_skills", []),
            raw=raw,
        )

        for stage_raw in raw.get("stages", []):
            manifest.stages.append(StageDefinition(
                name=stage_raw.get("name", ""),
                skill=stage_raw.get("skill"),
                produces=stage_raw.get("produces", []),
                checkpoint_required=stage_raw.get("checkpoint_required", False),
                review_focus=stage_raw.get("review_focus", []),
                success_criteria=stage_raw.get("success_criteria", []),
                raw=stage_raw,
            ))

        self._cache[name] = manifest
        logger.info(f"已加载流水线: {manifest.name} (v{manifest.version}, {len(manifest.stages)} 阶段)")
        return manifest

    def load_all(self) -> List[PipelineManifest]:
        """加载所有流水线。"""
        manifests = []
        for name in self.list_pipelines():
            try:
                manifests.append(self.load_pipeline(name))
            except Exception as e:
                logger.error(f"加载流水线 {name} 失败: {e}")
        logger.info(f"共加载 {len(manifests)} 个流水线")
        return manifests

    def get_pipeline_info(self, name: str) -> Dict[str, Any]:
        """获取流水线概要信息。"""
        manifest = self.load_pipeline(name)
        return {
            "name": manifest.name,
            "version": manifest.version,
            "category": manifest.category,
            "stability": manifest.stability,
            "stage_count": len(manifest.stages),
            "stages": [
                {
                    "name": s.name,
                    "produces": s.produces,
                    "checkpoint": s.checkpoint_required,
                }
                for s in manifest.stages
            ],
            "reference_input_supported": manifest.reference_input_supported,
            "required_skills": manifest.required_skills,
        }

    def run_stage(
        self,
        pipeline_name: str,
        stage_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> StageResult:
        """执行单个阶段（驱动 Agent 完成工作）。

        Args:
            pipeline_name: 流水线名
            stage_name: 阶段名
            context: 上下文（输入数据）

        Returns:
            StageResult
        """
        manifest = self.load_pipeline(pipeline_name)
        stage = next((s for s in manifest.stages if s.name == stage_name), None)
        if not stage:
            raise ValueError(f"Stage '{stage_name}' not found in pipeline '{pipeline_name}'")

        result = StageResult(
            stage_name=stage_name,
            status=PipelineStatus.RUNNING,
            started_at=time.time(),
        )
        context = context or {}

        try:
            artifacts = self._execute_stage_logic(manifest, stage, context)
            result.artifacts = artifacts
            result.status = (
                PipelineStatus.CHECKPOINT if stage.checkpoint_required
                else PipelineStatus.COMPLETED
            )
            result.notes = f"阶段 {stage_name} 完成，产出 {len(artifacts)} 个 artifact"
        except Exception as e:
            result.status = PipelineStatus.FAILED
            result.error = str(e)
            logger.error(f"阶段 {stage_name} 失败: {e}")
        finally:
            result.finished_at = time.time()

        run_id = f"{pipeline_name}:{int(time.time())}"
        self._runs.setdefault(run_id, []).append(result)
        return result

    def _execute_stage_logic(
        self,
        manifest: PipelineManifest,
        stage: StageDefinition,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """阶段执行逻辑（默认实现：返回结构化模板）。

        各阶段的具体业务逻辑由 Agent 驱动完成，这里提供结构化输出。
        """
        artifacts = {}
        for artifact_name in stage.produces:
            artifacts[artifact_name] = {
                "schema": artifact_name,
                "pipeline": manifest.name,
                "stage": stage.name,
                "context_keys": list(context.keys()),
                "review_focus": stage.review_focus,
                "success_criteria": stage.success_criteria,
                "generated_at": time.time(),
                "stub": True,  # 标记为占位，等待 Agent 填充实际数据
            }
        return artifacts

    def get_run_history(self, run_id: str) -> List[StageResult]:
        """获取运行历史。"""
        return self._runs.get(run_id, [])
