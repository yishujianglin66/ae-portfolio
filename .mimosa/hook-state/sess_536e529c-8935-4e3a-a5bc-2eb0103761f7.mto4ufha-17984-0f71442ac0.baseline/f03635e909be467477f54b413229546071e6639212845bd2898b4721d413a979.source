#!/usr/bin/env python3
"""
多智能体协作系统 - 集成OpenSpace/JiuwenSwarm理念

设计原则：
1. 任务分发：将复杂任务拆分给多个专门智能体
2. 结果聚合：汇总各智能体输出形成最终结果
3. 协作模式：支持串行、并行、混合执行
4. 错误恢复：单个智能体失败不影响整体

智能体类型：
- StyleAnalysisAgent: 风格分析专家（TIER_1）
- CodeGenerationAgent: 代码生成专家（TIER_2）
- ParameterOptimizationAgent: 参数优化专家（TIER_1）
- QualityReviewAgent: 质量审核专家（TIER_3）

架构参考：
- OpenSpace/openspace/agents/multi_agent_orchestrator.py
- JiuwenSwarm 多智能体协作框架
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """智能体角色"""
    STYLE_ANALYSIS = "style_analysis"           # 风格分析（TIER_1）
    CODE_GENERATION = "code_generation"         # 代码生成（TIER_2）
    PARAMETER_OPTIMIZATION = "param_optim"      # 参数优化（TIER_1）
    QUALITY_REVIEW = "quality_review"           # 质量审核（TIER_3）
    COORDINATOR = "coordinator"                 # 协调者


class AgentStatus(Enum):
    """智能体状态"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class AgentConfig:
    """智能体配置"""
    role: AgentRole
    name: str
    description: str
    model_tier: int = 1  # 1=TIER_1, 2=TIER_2, 3=TIER_3
    max_retries: int = 2
    timeout_seconds: int = 60


@dataclass
class AgentResult:
    """智能体执行结果"""
    agent_name: str
    role: AgentRole
    success: bool = True
    content: str = ""
    data: Dict[str, Any] = field(default_factory=dict)
    latency_ms: float = 0.0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskDefinition:
    """任务定义"""
    task_id: str
    task_type: str
    description: str
    input_data: Dict[str, Any] = field(default_factory=dict)
    assigned_agents: List[AgentRole] = field(default_factory=list)
    execution_mode: str = "parallel"  # parallel, sequential, mixed
    dependencies: List[str] = field(default_factory=list)


class BaseAgent:
    """智能体基类"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.status = AgentStatus.IDLE
        self._execution_count = 0
        self._total_latency_ms = 0.0
    
    async def execute(self, task: TaskDefinition) -> AgentResult:
        """执行任务"""
        raise NotImplementedError
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        avg_latency = (
            self._total_latency_ms / self._execution_count
            if self._execution_count > 0 else 0
        )
        return {
            "name": self.config.name,
            "role": self.config.role.value,
            "status": self.status.value,
            "execution_count": self._execution_count,
            "avg_latency_ms": avg_latency,
        }


# ============================================================================
#  P2: 真实执行路径支撑函数（LLM opt-in + Prompt 外置）
# ============================================================================

def _agents_llm_enabled() -> bool:
    """全局开关: AE_AGENTS_USE_LLM=1 时 Agent 走真实 LLM 路径"""
    import os
    return os.environ.get("AE_AGENTS_USE_LLM", "") == "1"


def _task_llm_enabled(task: TaskDefinition) -> bool:
    """任务级开关: input_data["_use_llm"] 或全局开关"""
    return bool(task.input_data.get("_use_llm")) or _agents_llm_enabled()


def _load_agent_prompt(role_value: str) -> Tuple[str, str]:
    """加载外置 Prompt（Optimizer 可修改）

    Returns:
        (prompt_text, source) — source ∈ {"file", "builtin"}
    """
    try:
        from core.evolution.agent_assets import get_agent_asset_manager
        mgr = get_agent_asset_manager()
        return mgr.load_prompt(role_value), mgr.prompt_source(role_value)
    except Exception:
        return "", "builtin"


async def _call_agent_llm(
    task_type_name: str,
    system_prompt: str,
    message: str,
) -> Tuple[Optional[str], int, float]:
    """调用 LLMGateway（真实执行路径）

    Returns:
        (content, tokens_used, cost_usd)；失败时 (None, 0, 0.0)
    """
    try:
        from core.llm_gateway import LLMGateway, TaskType
        gateway = LLMGateway()
        task_type = getattr(TaskType, task_type_name, TaskType.GENERAL)
        resp = await gateway.chat_with_routing(
            message=message,
            task_type=task_type,
            system_prompt=system_prompt or "你是严格的输出器。",
            temperature=0.3,
            max_tokens=2048,
        )
        if resp is None or not getattr(resp, "success", False):
            return None, 0, 0.0
        content = getattr(resp, "content", "") or ""
        tokens = int(getattr(resp, "tokens_input", 0) or 0) + int(getattr(resp, "tokens_output", 0) or 0)
        cost = float(getattr(resp, "cost_usd", 0.0) or 0.0)
        return content, tokens, cost
    except Exception as e:
        logger.debug(f"Agent LLM 调用失败(将降级): {e}")
        return None, 0, 0.0


def _parse_json_content(content: str) -> Optional[Dict[str, Any]]:
    """从 LLM 输出解析 JSON 对象（容忍 markdown 包裹）"""
    if not content:
        return None
    text = content.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    import re
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            pass
    return None


class StyleAnalysisAgent(BaseAgent):
    """风格分析智能体"""
    
    def __init__(self):
        super().__init__(AgentConfig(
            role=AgentRole.STYLE_ANALYSIS,
            name="StyleAnalyzer",
            description="视频风格分析专家，提取色彩、节奏、构图等可量化参数",
            model_tier=1
        ))
    
    async def execute(self, task: TaskDefinition) -> AgentResult:
        """执行风格分析（P2: 真实 LLM 路径 + 确定性兜底）"""
        start_time = time.time()
        self.status = AgentStatus.RUNNING
        
        try:
            input_data = task.input_data
            metadata: Dict[str, Any] = {"execution_path": "fallback"}
            result_data: Optional[Dict[str, Any]] = None

            # P2: 真实执行路径 — LLM 风格分析（opt-in）
            if _task_llm_enabled(task):
                prompt, source = _load_agent_prompt(self.config.role.value)
                message = (
                    f"任务描述: {task.description}\n"
                    f"输入数据: {json.dumps(input_data, ensure_ascii=False, default=str)[:2000]}"
                )
                content, tokens, cost = await _call_agent_llm("VISION_UNDERSTANDING", prompt, message)
                parsed = _parse_json_content(content or "")
                if parsed and "style_tags" in parsed:
                    result_data = {
                        "style_tags": parsed.get("style_tags", []),
                        "color_profile": parsed.get("color_profile", {}),
                        "rhythm_profile": parsed.get("rhythm_profile", {}),
                        "ae_effect_presets": parsed.get("ae_effect_presets", []),
                    }
                    metadata.update({
                        "execution_path": "llm",
                        "prompt_source": source,
                        "tokens_used": tokens,
                        "cost_usd": cost,
                    })

            # 兜底: 确定性分析逻辑（原 mock 升级为降级路径）
            if result_data is None:
                # 这里应该调用 VideoStyleExtractor
                result_data = {
                    "style_tags": ["cinematic", "slow_cut"],
                    "color_profile": {
                        "brightness": 45.0,
                        "saturation": 35.0,
                        "warmth": 5.0,
                    },
                    "rhythm_profile": {
                        "cut_rate": 0.8,
                        "avg_shot_duration": 2.5,
                    },
                    "ae_effect_presets": [
                        {"effect": "ADBE Lumetri", "params": {"Exposure": 0.2}},
                        {"effect": "ADBE Sharpen", "params": {"Sharpen Amount": 25}},
                    ]
                }
            
            latency = (time.time() - start_time) * 1000
            self._execution_count += 1
            self._total_latency_ms += latency
            self.status = AgentStatus.COMPLETED
            
            return AgentResult(
                agent_name=self.config.name,
                role=self.config.role,
                success=True,
                content=f"风格分析完成，检测到风格: {result_data['style_tags']}",
                data=result_data,
                latency_ms=latency,
                metadata=metadata,
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            logger.error(f"风格分析失败: {e}")
            return AgentResult(
                agent_name=self.config.name,
                role=self.config.role,
                success=False,
                error=str(e)
            )


class CodeGenerationAgent(BaseAgent):
    """代码生成智能体"""
    
    def __init__(self):
        super().__init__(AgentConfig(
            role=AgentRole.CODE_GENERATION,
            name="CodeGenerator",
            description="JSX代码生成专家，根据风格参数生成AE脚本",
            model_tier=2
        ))
    
    async def execute(self, task: TaskDefinition) -> AgentResult:
        """执行代码生成（P2: 真实 LLM 路径 + 确定性兜底）"""
        start_time = time.time()
        self.status = AgentStatus.RUNNING
        
        try:
            input_data = task.input_data
            style_data = input_data.get("style_analysis", {})
            metadata: Dict[str, Any] = {"execution_path": "fallback"}
            jsx_code = ""

            # P2: 真实执行路径 — LLM 生成 JSX（opt-in）
            if _task_llm_enabled(task):
                prompt, source = _load_agent_prompt(self.config.role.value)
                message = (
                    f"任务描述: {task.description}\n"
                    f"风格分析结果: {json.dumps(style_data, ensure_ascii=False, default=str)[:2000]}\n"
                    "请生成 AE JSX 脚本。"
                )
                content, tokens, cost = await _call_agent_llm("GENERAL", prompt, message)
                code = (content or "").strip()
                # 合法性检查: 必须像 JSX 且无危险调用
                if code and ("app.project" in code or "addProperty" in code) and "eval(" not in code:
                    jsx_code = code
                    metadata.update({
                        "execution_path": "llm",
                        "prompt_source": source,
                        "tokens_used": tokens,
                        "cost_usd": cost,
                    })

            # 兜底: 基于风格数据的确定性生成
            if not jsx_code:
                jsx_code = self._generate_jsx(style_data)
            
            latency = (time.time() - start_time) * 1000
            self._execution_count += 1
            self._total_latency_ms += latency
            self.status = AgentStatus.COMPLETED
            
            return AgentResult(
                agent_name=self.config.name,
                role=self.config.role,
                success=True,
                content="JSX代码生成完成",
                data={"jsx_code": jsx_code, "code_length": len(jsx_code)},
                latency_ms=latency,
                metadata=metadata,
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            logger.error(f"代码生成失败: {e}")
            return AgentResult(
                agent_name=self.config.name,
                role=self.config.role,
                success=False,
                error=str(e)
            )
    
    def _generate_jsx(self, style_data: Dict[str, Any]) -> str:
        """生成JSX代码"""
        # 基于风格数据生成代码
        presets = style_data.get("ae_effect_presets", [])
        
        code_lines = [
            "// 自动生成的AE风格迁移脚本",
            "var comp = app.project.activeItem;",
            "var layer = comp.selectedLayers[0];",
            "",
        ]
        
        for preset in presets:
            effect = preset.get("effect", "")
            params = preset.get("params", {})
            
            code_lines.append(f"var effect = layer.Effects.addProperty('{effect}');")
            for param_name, param_value in params.items():
                code_lines.append(f"effect.property('{param_name}').setValue({param_value});")
            code_lines.append("")
        
        return "\n".join(code_lines)


class ParameterOptimizationAgent(BaseAgent):
    """参数优化智能体"""
    
    def __init__(self):
        super().__init__(AgentConfig(
            role=AgentRole.PARAMETER_OPTIMIZATION,
            name="ParamOptimizer",
            description="参数优化专家，调整效果参数达到最佳视觉效果",
            model_tier=1
        ))
    
    async def execute(self, task: TaskDefinition) -> AgentResult:
        """执行参数优化（P2: 真实 LLM 路径 + 确定性兜底）"""
        start_time = time.time()
        self.status = AgentStatus.RUNNING
        
        try:
            input_data = task.input_data
            metadata: Dict[str, Any] = {"execution_path": "fallback"}
            optimized_params: Optional[Dict[str, Any]] = None

            # P2: 真实执行路径 — LLM 参数寻优（opt-in）
            if _task_llm_enabled(task):
                prompt, source = _load_agent_prompt(self.config.role.value)
                message = (
                    f"任务描述: {task.description}\n"
                    f"当前参数与上下文: {json.dumps(input_data, ensure_ascii=False, default=str)[:2000]}\n"
                    '请输出 JSON 对象 {"参数名": 数值}。'
                )
                content, tokens, cost = await _call_agent_llm("PARAMETER_OPTIMIZATION", prompt, message)
                parsed = _parse_json_content(content or "")
                if parsed:
                    # 只保留数值型参数（安全过滤）
                    numeric = {
                        k: v for k, v in parsed.items()
                        if isinstance(v, (int, float)) and not isinstance(v, bool)
                    }
                    if numeric:
                        optimized_params = numeric
                        metadata.update({
                            "execution_path": "llm",
                            "prompt_source": source,
                            "tokens_used": tokens,
                            "cost_usd": cost,
                        })

            # 兜底: 默认参数集
            if optimized_params is None:
                optimized_params = {
                    "Glow Threshold": 45,
                    "Glow Radius": 20,
                    "Glow Intensity": 1.2,
                }
            
            latency = (time.time() - start_time) * 1000
            self._execution_count += 1
            self._total_latency_ms += latency
            self.status = AgentStatus.COMPLETED
            
            return AgentResult(
                agent_name=self.config.name,
                role=self.config.role,
                success=True,
                content="参数优化完成",
                data={"optimized_params": optimized_params},
                latency_ms=latency,
                metadata=metadata,
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            return AgentResult(
                agent_name=self.config.name,
                role=self.config.role,
                success=False,
                error=str(e)
            )


class QualityReviewAgent(BaseAgent):
    """质量审核智能体"""
    
    def __init__(self):
        super().__init__(AgentConfig(
            role=AgentRole.QUALITY_REVIEW,
            name="QualityReviewer",
            description="质量审核专家，检查生成代码的正确性和安全性",
            model_tier=3
        ))
    
    async def execute(self, task: TaskDefinition) -> AgentResult:
        """执行质量审核（P2: 确定性检查 + 可选 LLM 语义审核）"""
        start_time = time.time()
        self.status = AgentStatus.RUNNING
        
        try:
            input_data = task.input_data
            jsx_code = input_data.get("jsx_code", "")
            metadata: Dict[str, Any] = {"execution_path": "fallback"}
            
            # 确定性质量检查（始终执行，不受 LLM 开关影响）
            issues = []
            if "eval(" in jsx_code:
                issues.append("安全警告: 检测到eval()调用")
            if len(jsx_code) < 50:
                issues.append("代码过短，可能不完整")

            # P2: 真实执行路径 — LLM 语义审核（opt-in，仅补充问题清单）
            if _task_llm_enabled(task) and jsx_code:
                prompt, source = _load_agent_prompt(self.config.role.value)
                message = (
                    f"请审核以下 AE JSX 代码:\n```\n{jsx_code[:3000]}\n```\n"
                    '输出 JSON: {"issues": ["..."]}'
                )
                content, tokens, cost = await _call_agent_llm("QUALITY_REVIEW", prompt, message)
                parsed = _parse_json_content(content or "")
                if parsed and isinstance(parsed.get("issues"), list):
                    for issue in parsed["issues"][:5]:
                        text = str(issue)
                        if text and text not in issues:
                            issues.append(text)
                    metadata.update({
                        "execution_path": "llm+rules",
                        "prompt_source": source,
                        "tokens_used": tokens,
                        "cost_usd": cost,
                    })
            
            passed = len(issues) == 0
            
            latency = (time.time() - start_time) * 1000
            self._execution_count += 1
            self._total_latency_ms += latency
            self.status = AgentStatus.COMPLETED
            
            return AgentResult(
                agent_name=self.config.name,
                role=self.config.role,
                success=passed,
                content="质量审核完成" if passed else f"发现{len(issues)}个问题",
                data={"issues": issues, "passed": passed},
                latency_ms=latency,
                metadata=metadata,
            )
            
        except Exception as e:
            self.status = AgentStatus.FAILED
            return AgentResult(
                agent_name=self.config.name,
                role=self.config.role,
                success=False,
                error=str(e)
            )


class MultiAgentOrchestrator:
    """多智能体编排器"""
    
    def __init__(self):
        self.agents: Dict[AgentRole, BaseAgent] = {}
        self._register_default_agents()
    
    def _register_default_agents(self):
        """注册默认智能体"""
        self.agents[AgentRole.STYLE_ANALYSIS] = StyleAnalysisAgent()
        self.agents[AgentRole.CODE_GENERATION] = CodeGenerationAgent()
        self.agents[AgentRole.PARAMETER_OPTIMIZATION] = ParameterOptimizationAgent()
        self.agents[AgentRole.QUALITY_REVIEW] = QualityReviewAgent()
    
    def register_agent(self, role: AgentRole, agent: BaseAgent):
        """注册自定义智能体"""
        self.agents[role] = agent
    
    async def execute_task(self, task: TaskDefinition) -> Dict[str, AgentResult]:
        """执行任务"""
        results: Dict[str, AgentResult] = {}
        
        if task.execution_mode == "parallel":
            results = await self._execute_parallel(task)
        elif task.execution_mode == "sequential":
            results = await self._execute_sequential(task)
        else:
            results = await self._execute_mixed(task)
        
        return results
    
    async def _execute_parallel(self, task: TaskDefinition) -> Dict[str, AgentResult]:
        """并行执行"""
        results = {}

        # 记录 tasks 列表中每个位置对应的 role，避免索引错位
        task_role_map: List[AgentRole] = []
        tasks = []
        for role in task.assigned_agents:
            if role in self.agents:
                tasks.append(self.agents[role].execute(task))
                task_role_map.append(role)

        if tasks:
            agent_results = await asyncio.gather(*tasks, return_exceptions=True)

            for i, role in enumerate(task_role_map):
                result = agent_results[i]
                if isinstance(result, Exception):
                    results[role.value] = AgentResult(
                        agent_name=self.agents[role].config.name,
                        role=role,
                        success=False,
                        error=str(result)
                    )
                else:
                    results[role.value] = result

        return results
    
    async def _execute_sequential(self, task: TaskDefinition) -> Dict[str, AgentResult]:
        """串行执行"""
        results = {}
        
        for role in task.assigned_agents:
            if role in self.agents:
                result = await self.agents[role].execute(task)
                results[role.value] = result
                
                # 将结果传递给下一个智能体
                task.input_data[f"{role.value}_result"] = result.data
                
                # 如果失败，决定是否继续
                if not result.success:
                    logger.warning(f"智能体 {role.value} 执行失败")
                    break
        
        return results
    
    async def _execute_mixed(self, task: TaskDefinition) -> Dict[str, AgentResult]:
        """混合执行（部分并行、部分串行）"""
        # 简化实现：先并行执行分析类任务，再串行执行生成类任务
        analysis_roles = [AgentRole.STYLE_ANALYSIS, AgentRole.PARAMETER_OPTIMIZATION]
        generation_roles = [AgentRole.CODE_GENERATION, AgentRole.QUALITY_REVIEW]
        
        results = {}
        
        # 第一阶段：并行分析
        analysis_task = TaskDefinition(
            task_id=f"{task.task_id}_analysis",
            task_type="analysis",
            description="并行分析阶段",
            input_data=task.input_data.copy(),
            assigned_agents=[r for r in task.assigned_agents if r in analysis_roles],
            execution_mode="parallel"
        )
        analysis_results = await self._execute_parallel(analysis_task)
        results.update(analysis_results)
        
        # 第二阶段：串行生成
        for role in [r for r in task.assigned_agents if r in generation_roles]:
            if role in self.agents:
                # 将分析结果作为输入
                task.input_data.update({
                    k: v for k, v in results.items()
                    if "data" in results.get(k, {})
                })
                result = await self.agents[role].execute(task)
                results[role.value] = result
        
        return results
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取所有智能体统计"""
        return {
            role.value: agent.get_stats()
            for role, agent in self.agents.items()
        }

    async def produce(
        self,
        prompt: str = "",
        compose_type: str = "preview",
        output: str = "",
        audio_path: str = "",
        jsx: str = "",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """一站式产出入口 (UnifiedPipeline._execute_with_agents 调用)

        【P3-D 修复】历史缺陷: 本方法不存在 → AttributeError → 每次静默降级
        到 basic 执行，多智能体链路从未真正参与。

        编排: 风格分析 → 代码生成 → 参数优化 → 质量审核 (顺序执行)，
        聚合各阶段产出为 phases。本方法不自行渲染，
        返回 success 供调用方判断；失败时调用方可回退 basic 执行。
        """
        task = TaskDefinition(
            task_id=f"produce_{int(time.time() * 1000)}",
            task_type="produce",
            description=prompt or "produce",
            input_data={
                "prompt": prompt,
                "compose_type": compose_type,
                "output": output,
                "audio_path": audio_path,
                "jsx": jsx,
                **{k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool))},
            },
            assigned_agents=[
                AgentRole.STYLE_ANALYSIS,
                AgentRole.CODE_GENERATION,
                AgentRole.PARAMETER_OPTIMIZATION,
                AgentRole.QUALITY_REVIEW,
            ],
            execution_mode="sequential",
        )

        phases: Dict[str, Any] = {}
        success = True
        try:
            results = await self.execute_task(task)
            for role_value, res in results.items():
                phases[role_value] = {
                    "success": bool(res.success),
                    "data": res.data or {},
                    "error": res.error or "",
                }
                if not res.success:
                    success = False
        except Exception as e:  # 单智能体异常不应阻断产出入口
            logger.warning(f"produce 编排异常: {e}")
            success = False
            phases["orchestration_error"] = {"error": str(e)}

        phases["compose"] = {
            "output": output,
            "compose_type": compose_type,
            "success": success,
        }
        return {"success": success, "phases": phases, "output": output}


# 便捷函数
async def run_style_transfer_pipeline(video_path: str) -> Dict[str, Any]:
    """运行风格迁移流水线"""
    orchestrator = MultiAgentOrchestrator()
    
    task = TaskDefinition(
        task_id="style_transfer_001",
        task_type="style_transfer",
        description="视频风格分析→代码生成→质量审核",
        input_data={"video_path": video_path},
        assigned_agents=[
            AgentRole.STYLE_ANALYSIS,
            AgentRole.CODE_GENERATION,
            AgentRole.QUALITY_REVIEW
        ],
        execution_mode="sequential"
    )
    
    results = await orchestrator.execute_task(task)
    
    return {
        "success": all(r.success for r in results.values()),
        "results": {k: {"success": v.success, "content": v.content} for k, v in results.items()},
        "jsx_code": results.get("code_generation", {}).data.get("jsx_code", ""),
    }


if __name__ == "__main__":
    # 测试多智能体系统
    async def test():
        print("=" * 60)
        print("多智能体协作系统测试")
        print("=" * 60)
        
        orchestrator = MultiAgentOrchestrator()
        
        # 测试任务
        task = TaskDefinition(
            task_id="test_001",
            task_type="style_analysis",
            description="测试多智能体协作",
            input_data={"video_path": "test.mp4"},
            assigned_agents=[
                AgentRole.STYLE_ANALYSIS,
                AgentRole.CODE_GENERATION,
            ],
            execution_mode="sequential"
        )
        
        results = await orchestrator.execute_task(task)
        
        for role, result in results.items():
            status = "成功" if result.success else "失败"
            print(f"\n[{role}] {status}")
            print(f"  内容: {result.content[:50]}...")
            print(f"  延迟: {result.latency_ms:.0f}ms")
        
        print("\n统计信息:")
        stats = orchestrator.get_all_stats()
        for role, stat in stats.items():
            print(f"  {role}: {stat['execution_count']} 次执行")
    
    asyncio.run(test())


from core.llm_gateway import LLMGateway  # 暴露给 unittest.mock.patch 使用

class PlannerParseError(Exception):
    """规划结果解析异常"""
    pass


@dataclass
class SubTaskPlan:
    task_id: str
    description: str
    agent_role: AgentRole
    dependencies: List[str] = field(default_factory=list)
    input_hints: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReActStep:
    step: int
    thought: str
    action: str
    action_input: Dict[str, Any]
    observation: str = ""
    success: bool = True


class AgenticPlanner:
    """自主规划器：拆解高层任务为子任务图并执行，失败时反思重试"""

    _PLAN_PROMPT = """你是视频制作流水线的任务规划器。给定一个高层任务描述，把它拆成最多 6 个有序子任务，分配给下面 4 个专家智能体之一：
- STYLE_ANALYSIS: 风格分析、镜头语言、节奏结构
- CODE_GENERATION: 生成 AE JSX / Python 代码、脚本模板
- PARAMETER_OPTIMIZATION: 参数寻优、贝叶斯调参、数值匹配
- QUALITY_REVIEW: 质量检查、验收标准、合规性

规则：
1. task_id 用英文小写短横线，如 style-1 / code-2 / review-final
2. dependencies 只写前面已出现过的 task_id，入口任务写 []
3. 禁止生成不存在的 agent_role，必须是 4 个之一
4. QUALITY_REVIEW 必须是最后一个任务且依赖全部前置任务

只输出严格 JSON 数组，不要 markdown，不要任何额外文字。
"""

    _REFLECT_PROMPT = """你是视频制作流水线的任务规划器。任务执行失败了，请分析失败原因并重新规划任务。

高层任务：{high_level_task}
失败子任务：{failed_subtask_id}
错误信息：{error_msg}
旧的任务计划：
{old_plan_json}

请分析失败原因，然后输出修正后的新计划（JSON 数组，格式同规划阶段）。
只输出严格 JSON 数组，不要 markdown，不要任何额外文字。
"""

    # P1: 进化模式附加指令 — 评测驱动的改进任务（Optimizer-Evaluator 分离）
    _EVOLUTION_PROMPT_SUFFIX = """
【进化模式特殊规则】
当前是评测驱动的自进化任务（分析失分原因并改进）：
1. 第一个子任务必须是 STYLE_ANALYSIS：分析失分点与当前输出缺陷
2. 至少包含一个 PARAMETER_OPTIMIZATION 子任务：给出参数/配置改进建议
3. 若需要修改生成逻辑，加入 CODE_GENERATION 子任务
4. 最后必须由 QUALITY_REVIEW 验证改进效果（对应独立评测）
5. input_hints 中尽量携带评测分数/失分信息（如 score、checks）
"""

    def __init__(self, llm_gateway=None, orchestrator=None, max_reflect_attempts=2):
        self._llm_gateway = llm_gateway
        self._orchestrator = orchestrator
        self._multi_agent = MultiAgentOrchestrator()
        self._max_reflect_attempts = max_reflect_attempts

    def _get_llm(self):
        if self._llm_gateway is None:
            try:
                from core.llm_gateway import LLMGateway as _LLMGatewayCls
            except Exception:
                _LLMGatewayCls = globals().get("LLMGateway")
            if _LLMGatewayCls is None:
                raise ImportError("LLMGateway 不可用")
            self._llm_gateway = _LLMGatewayCls()
        return self._llm_gateway

    def _get_orchestrator(self):
        if self._orchestrator is None:
            from core.workflow_orchestrator import WorkflowOrchestrator
            self._orchestrator = WorkflowOrchestrator(max_concurrent_tasks=5, enable_security=False)
        return self._orchestrator

    async def auto_execute(self, high_level_task: str, global_input: Dict=None) -> Tuple[bool, Dict, List[ReActStep]]:
        global_input = global_input or {}
        react_trace: List[ReActStep] = []
        step_counter = 0
        success = False
        combined_results: Dict[str, Any] = {}

        step_counter += 1
        react_trace.append(ReActStep(
            step=step_counter,
            thought="收到高层任务，开始 LLM 拆解子任务图",
            action="decompose",
            action_input={"task": high_level_task[:80]},
        ))

        try:
            sub_tasks = await self.plan(high_level_task)
            react_trace[-1].observation = f"成功拆解出 {len(sub_tasks)} 个子任务"
            react_trace[-1].success = True
        except PlannerParseError as e:
            react_trace[-1].observation = f"规划解析失败: {e}"
            react_trace[-1].success = False
            return False, {}, react_trace

        current_plan = sub_tasks
        attempts = 0

        while attempts <= self._max_reflect_attempts:
            step_counter += 1
            react_trace.append(ReActStep(
                step=step_counter,
                thought=f"第 {attempts + 1} 次执行计划",
                action="call_agent",
                action_input={"plan_size": len(current_plan), "attempt": attempts + 1},
            ))

            ok, results = await self.execute_plan(current_plan, global_input)
            combined_results = results

            if ok:
                react_trace[-1].observation = "全部子任务执行成功"
                react_trace[-1].success = True
                step_counter += 1
                react_trace.append(ReActStep(
                    step=step_counter,
                    thought="计划执行完毕，汇总结果",
                    action="finalize",
                    action_input={"task_count": len(current_plan)},
                    observation=f"汇总 {len(results)} 个子任务结果",
                    success=True,
                ))
                success = True
                break

            failed_id = results.get("_failed_task_id", "")
            error_msg = results.get("_error", "unknown error")
            react_trace[-1].observation = f"子任务 {failed_id} 失败"
            react_trace[-1].success = False

            if attempts >= self._max_reflect_attempts:
                step_counter += 1
                react_trace.append(ReActStep(
                    step=step_counter,
                    thought="已达最大重试次数，放弃",
                    action="finalize",
                    action_input={"attempts": attempts + 1},
                    observation=f"最终失败: {error_msg[:80]}",
                    success=False,
                ))
                break

            attempts += 1
            step_counter += 1
            react_trace.append(ReActStep(
                step=step_counter,
                thought="任务失败，进入反思阶段",
                action="reflect",
                action_input={"failed_id": failed_id, "error": error_msg, "attempt": attempts},
            ))

            try:
                reflect_summary, new_plan = await self.reflect(
                    high_level_task, failed_id, error_msg, current_plan
                )
                current_plan = new_plan
                react_trace[-1].observation = f"反思完成: {reflect_summary[:80]}"
                react_trace[-1].success = True
            except Exception as e:
                react_trace[-1].observation = f"反思阶段异常: {e}"
                react_trace[-1].success = False
                break

        return success, combined_results, react_trace

    async def plan(self, high_level_task: str, mode: str = "default") -> List[SubTaskPlan]:
        """拆解高层任务为子任务图

        Args:
            high_level_task: 任务描述
            mode: "default" 常规模式；"evolution" 进化模式（评测驱动改进，
                  强制 分析→参数优化→质量验收 的结构）
        """
        llm = self._get_llm()
        prompt = self._PLAN_PROMPT
        if mode == "evolution":
            prompt += self._EVOLUTION_PROMPT_SUFFIX
        prompt += f"\n现在请规划以下任务：\n{high_level_task}"

        last_error = None
        for attempt in range(2):
            try:
                resp = await llm.chat_with_routing(
                    message=prompt,
                    task_type="complex_analysis",
                    system_prompt="你是严格的JSON输出器，只输出JSON数组，不要任何额外文字。",
                    temperature=0.2,
                )
                content = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
                content = content.strip()
                if content.startswith("```"):
                    content = content.strip("`")
                    if content.startswith("json"):
                        content = content[4:].strip()
                parsed = json.loads(content)
                if not isinstance(parsed, list):
                    raise ValueError("解析结果不是列表")
                sub_tasks: List[SubTaskPlan] = []
                for item in parsed:
                    role_val = item.get("agent_role", "")
                    if isinstance(role_val, str):
                        try:
                            role = AgentRole[role_val]
                        except KeyError:
                            raise ValueError(f"无效 agent_role: {role_val}")
                    else:
                        role = AgentRole(role_val)
                    if role not in (AgentRole.STYLE_ANALYSIS, AgentRole.CODE_GENERATION, AgentRole.PARAMETER_OPTIMIZATION, AgentRole.QUALITY_REVIEW):
                        raise ValueError(f"禁用的 agent_role: {role}")
                    sub_tasks.append(SubTaskPlan(
                        task_id=item["task_id"],
                        description=item.get("description", ""),
                        agent_role=role,
                        dependencies=list(item.get("dependencies", [])),
                        input_hints=dict(item.get("input_hints", {})),
                    ))
                return sub_tasks
            except Exception as e:
                last_error = e
        raise PlannerParseError(f"规划JSON解析失败: {last_error}")

    def build_workflow_tasks(self, sub_tasks: List[SubTaskPlan], global_input: Dict) -> List[Any]:
        from core.workflow_orchestrator import TaskDefinition as WF_TaskDefinition, TaskType as WF_TaskType

        task_defs = []
        for st in sub_tasks:
            role = st.agent_role
            hints = dict(st.input_hints)
            desc = st.description
            task_id = st.task_id
            deps = list(st.dependencies)

            def _make_runner(_task_id=task_id, _role=role, _hints=hints, _desc=desc):
                async def _runner(context=None, **kwargs):
                    task = TaskDefinition(
                        task_id=_task_id,
                        task_type=_role.value,
                        description=_desc,
                        input_data={**global_input, **_hints},
                        assigned_agents=[_role],
                        execution_mode="sequential",
                        dependencies=[],
                    )
                    for dep_key, dep_val in kwargs.items():
                        if dep_key.startswith("_") and dep_key.endswith("_result"):
                            task.input_data[dep_key] = dep_val
                    results = await self._multi_agent.execute_task(task)
                    role_key = _role.value
                    agent_res = results.get(role_key)
                    if agent_res is not None and not agent_res.success:
                        raise RuntimeError(f"子任务 {_task_id} 失败: {agent_res.error}")
                    return {
                        "task_id": _task_id,
                        "role": role_key,
                        "success": agent_res.success if agent_res else True,
                        "data": agent_res.data if agent_res else {},
                        "content": agent_res.content if agent_res else "",
                        "raw_results": {k: {"success": v.success, "data": v.data, "content": v.content} for k, v in results.items()},
                    }
                return _runner

            task_type_map = {
                AgentRole.STYLE_ANALYSIS: WF_TaskType.UNDERSTANDING,
                AgentRole.CODE_GENERATION: WF_TaskType.AE_COMPILE,
                AgentRole.PARAMETER_OPTIMIZATION: WF_TaskType.PARAM_MAPPING,
                AgentRole.QUALITY_REVIEW: WF_TaskType.FEEDBACK,
            }

            task_defs.append(WF_TaskDefinition(
                task_id=task_id,
                task_type=task_type_map.get(role, WF_TaskType.PLANNING),
                name=f"[{role.value}] {desc[:40]}",
                func=_make_runner(),
                args={},
                dependencies=deps,
                retry_count=0,
                skip_on_failure=False,
            ))
        return task_defs

    async def execute_plan(self, sub_tasks: List[SubTaskPlan], global_input: Dict) -> Tuple[bool, Dict]:
        orch = self._get_orchestrator()
        orch._tasks_def = []
        orch._task_dependencies = {}
        orch._task_dependents = {}
        orch._completed_tasks = set()
        orch._failed_tasks = set()

        task_defs = self.build_workflow_tasks(sub_tasks, global_input)
        orch.register_subtasks(task_defs)

        results_map = await orch.run_and_collect(global_input=global_input)

        combined: Dict[str, Any] = {}
        failed_task_id = ""
        first_error = ""

        for st in sub_tasks:
            tid = st.task_id
            res = results_map.get(tid)
            if res is None:
                combined[tid] = {"success": False, "error": "task_not_found"}
                if not failed_task_id:
                    failed_task_id = tid
                    first_error = "task_not_found"
                continue
            success = True
            if isinstance(res, dict):
                success = res.get("success", True)
                combined[tid] = res
            elif hasattr(res, "result"):
                inner = res.result
                if isinstance(inner, dict):
                    success = inner.get("success", True)
                combined[tid] = {"success": success, "result": inner} if isinstance(inner, dict) else {"success": success, "result": str(inner)}
            else:
                combined[tid] = {"success": True, "result": str(res)}
            if not success and not failed_task_id:
                failed_task_id = tid
                if isinstance(combined[tid], dict):
                    first_error = combined[tid].get("error", combined[tid].get("content", "failed"))

        all_ok = not failed_task_id
        if not all_ok:
            combined["_failed_task_id"] = failed_task_id
            combined["_error"] = first_error

        return all_ok, combined

    async def reflect(self, high_level_task: str, failed_subtask_id: str, error_msg: str, old_plan: List[SubTaskPlan]) -> Tuple[str, List[SubTaskPlan]]:
        llm = self._get_llm()
        old_plan_json = json.dumps([
            {
                "task_id": s.task_id,
                "description": s.description,
                "agent_role": s.agent_role.name,
                "dependencies": s.dependencies,
                "input_hints": s.input_hints,
            } for s in old_plan
        ], ensure_ascii=False, indent=2)
        prompt = self._REFLECT_PROMPT.format(
            high_level_task=high_level_task,
            failed_subtask_id=failed_subtask_id,
            error_msg=error_msg,
            old_plan_json=old_plan_json,
        )

        resp = await llm.chat_with_routing(
            message=prompt,
            task_type="deep_reasoning",
            system_prompt="你是严格的JSON输出器，先输出一句中文反思总结（200字内），然后输出JSON数组。",
            temperature=0.4,
        )
        content = resp if isinstance(resp, str) else getattr(resp, "content", str(resp))
        content = content.strip()

        summary = ""
        json_start = content.find("[")
        if json_start > 0:
            summary = content[:json_start].strip().rstrip(":：").strip()
            json_str = content[json_start:]
        else:
            json_str = content

        if json_str.startswith("```"):
            json_str = json_str.strip("`")
            if json_str.startswith("json"):
                json_str = json_str[4:].strip()

        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError:
            bracket_end = content.rfind("]")
            if json_start >= 0 and bracket_end > json_start:
                json_str = content[json_start:bracket_end + 1]
                parsed = json.loads(json_str)
            else:
                raise

        sub_tasks: List[SubTaskPlan] = []
        for item in parsed:
            role_val = item.get("agent_role", "")
            if isinstance(role_val, str):
                role = AgentRole[role_val]
            else:
                role = AgentRole(role_val)
            sub_tasks.append(SubTaskPlan(
                task_id=item["task_id"],
                description=item.get("description", ""),
                agent_role=role,
                dependencies=list(item.get("dependencies", [])),
                input_hints=dict(item.get("input_hints", {})),
            ))
        return summary or "已根据失败原因调整任务计划", sub_tasks
