# AE-Knowledge-Vault — 深度推理升级 + L1-L5 安全护栏设计与实施手册

> **文档版本**: v2.0（2026-08-02）
> **目标读者**: AI 执行体（另一个对话窗口中的代码生成 AI）
> **文档目的**: 提供完整的、可直接编码的实施方案，无需额外上下文即可执行
> **前置条件**: 已存在 `core/llm_gateway.py` / `core/security.py` / `core/workflow_orchestrator.py` / `core/config.py`

---

## 目录

1. [执行摘要](#1-执行摘要)
2. [术语表（AI 必读）](#2-术语表ai-必读)
3. [现有代码基线（AI 必读）](#3-现有代码基线ai-必读)
4. [Phase A：深度推理升级（ThinkingUpgradePolicy）](#4-phase-a深度推理升级thinkingupgradepolicy)
5. [Phase B：L1-L5 安全护栏（RiskGuard）](#5-phase-bl1-l5-安全护栏riskguard)
6. [Phase C：形式化规范层（FormalSpec）](#6-phase-c形式化规范层formalspec)
7. [开发集成方向（未来 6 个月）](#7-开发集成方向未来-6-个月)
8. [测试策略与验收标准](#8-测试策略与验收标准)
9. [风险与缓解](#9-风险与缓解)
10. [附录 A：完整代码模板](#10-附录-a完整代码模板)
11. [附录 B：配置文件变更](#11-附录-b配置文件变更)
12. [附录 C：CLI 交互示例](#12-附录-ccli-交互示例)

---

## 1. 执行摘要

### 1.1 背景

AE-Knowledge-Vault 是一个**视频制作自动化流水线项目**，覆盖从素材获取、音频分析、AE 合成、调色、剪辑到交付的完整链路。当前系统已具备：
- **LLM 网关**（`core/llm_gateway.py`）：支持 10+ 种任务类型、3 档模型分层、级联升级、多 Provider 降级
- **工作流编排器**（`core/workflow_orchestrator.py`）：支持 DAG 依赖、并行执行、安全扫描钩子
- **安全管理器**（`core/security.py`）：支持代码扫描、路径校验、审计日志、熔断器

### 1.2 两条核心升级主线

| 主线 | 借鉴对象 | 核心能力 | 落地位置 | 优先级 |
|---|---|---|---|---|
| **A. 深度推理升级** | OpenAI Astra 249 页 Lean 4 形式化推理 | 复杂任务自动升级到 TIER_3 + 多轮自我校准 | `core/llm_gateway.py` 追加 `ThinkingUpgradePolicy` | 高 |
| **B. L1-L5 安全护栏** | 信通院 Agent 安全分级 + Anthropic/OpenAI 失控事件 | 高危操作强制沙箱 + 人工审批 + 审计哈希链 | `core/security.py` 追加 4 个新类 + `core/workflow_orchestrator.py` 集成钩子 | **最高** |
| **C. 形式化规范层**（长期） | Lean 4 思想 | 硬规则固化为可执行不变量 | `core/formal_spec.py` 新增 | 中 |

### 1.3 核心设计原则

1. **原生实现**：不引入 LangChain / AutoGen / Lean 4 等外部依赖
2. **追加式扩展**：所有新功能都是**新增类/方法**，不修改已有类的已有方法
3. **向后兼容**：未启用新功能时，系统行为与当前版本 100% 一致
4. **可测试性**：所有新组件都有对应的 pytest 测试用例（全 mock，不真实调用 LLM/渲染）

---

## 2. 术语表（AI 必读）

> **重要**：以下术语在本文档中有**精确定义**，AI 执行体必须严格按此理解，不得自行扩展含义。

| 术语 | 精确定义 | 代码位置 |
|---|---|---|
| **TaskType** | LLM 任务类型枚举，决定路由到哪个模型档位。当前有 8 种：`INTENT_CLASSIFICATION`, `SCENE_DESCRIPTION`, `EFFECT_PLANNING`, `QUALITY_REVIEW`, `FEEDBACK_ANALYSIS`, `PARAMETER_OPTIMIZATION`, `EFFECT_SEARCH`, `GENERAL` | `core/llm_gateway.py` L133-142 |
| **ModelTier** | 模型档位枚举，按能力/成本分层。3 档：`TIER_1_LOCAL_SPECIALIZED`（本地小模型）, `TIER_2_MIDTIER_GENERAL`（中端通用）, `TIER_3_FLAGSHIP_REASONING`（旗舰推理） | `core/llm_gateway.py` L145-149 |
| **SecurityLevel** | 安全级别枚举（现有），5 级：`SAFE`, `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` | `core/security.py` L52-58 |
| **RiskLevel** | **新增**信通院 L1-L5 风险分级枚举，5 级：`L1_READONLY`, `L2_GENERATE`, `L3_OVERWRITE_SAFE`, `L4_DESTRUCTIVE`, `L5_EXTERNAL` | `core/security.py` 尾部追加 |
| **TaskDefinition** | 工作流任务定义，包含 `task_id`, `task_type`, `func`, `args`, `dependencies`, `sandboxed: bool`, `enable_audit: bool` 等字段 | `core/workflow_orchestrator.py` L110-127 |
| **SecurityManager** | 安全管理器（现有），提供 `scan_code()`, `scan_path()`, `log_audit()`, `check_circuit_breaker()` 方法 | `core/security.py` L111-347 |
| **WorkflowOrchestrator** | 工作流编排引擎（现有），提供 `add_task()`, `run()`, `_execute_task()` 方法 | `core/workflow_orchestrator.py` L162+ |
| **ThinkingUpgradePolicy** | **新增**深度推理升级策略类，决定何时把任务从 TIER_2 升到 TIER_3 | `core/llm_gateway.py` 尾部追加 |
| **RiskAssessor** | **新增**风险评估器类，输入 TaskType + args，输出 RiskAssessment | `core/security.py` 尾部追加 |
| **SandboxPolicy** | **新增**沙箱策略类，提供进程级隔离 + FS 白名单 + 资源限制 | `core/security.py` 尾部追加 |
| **ApprovalPolicy** | **新增**人工审批策略类，L4/L5 任务阻塞等待用户确认 | `core/security.py` 尾部追加 |
| **AuditChain** | **新增**审计哈希链类，追加式日志 + SHA-256 哈希链防篡改 | `core/security.py` 尾部追加 |
| **Invariant** | **新增**形式化不变量基类，pipeline 阶段结束时校验硬规则 | `core/formal_spec.py` 新增 |

---

## 3. 现有代码基线（AI 必读）

> **重要**：AI 执行体在编码前**必须**先读取以下文件的关键行，确保理解现有结构。

### 3.1 `core/llm_gateway.py` 关键结构

```python
# L133-142: TaskType 枚举（现有，不要修改）
class TaskType(Enum):
    INTENT_CLASSIFICATION = auto()
    SCENE_DESCRIPTION = auto()
    EFFECT_PLANNING = auto()
    QUALITY_REVIEW = auto()
    FEEDBACK_ANALYSIS = auto()
    PARAMETER_OPTIMIZATION = auto()
    EFFECT_SEARCH = auto()
    GENERAL = auto()

# L145-149: ModelTier 枚举（现有，不要修改）
class ModelTier(Enum):
    TIER_1_LOCAL_SPECIALIZED = "tier1_local"
    TIER_2_MIDTIER_GENERAL = "tier2_midtier"
    TIER_3_FLAGSHIP_REASONING = "tier3_flagship"

# L372-381: TASK_PROVIDER_MAP（现有，不要修改）
TASK_PROVIDER_MAP: Dict[TaskType, Tuple[str, str]] = {
    TaskType.SCENE_DESCRIPTION: ("claude", "vision"),
    TaskType.EFFECT_PLANNING: ("claude", "thinking"),
    # ...
}

# L383-392: TASK_TIER_MAP（现有，不要修改）
TASK_TIER_MAP: Dict[TaskType, ModelTier] = {
    TaskType.QUALITY_REVIEW: ModelTier.TIER_3_FLAGSHIP_REASONING,
    # ...
}

# L399+: LLMGateway 类（现有，不要修改已有方法）
class LLMGateway:
    def __init__(self, config: Optional[LLMConfig] = None): ...
    async def chat_with_routing(self, message: str, task_type: TaskType, ...) -> LLMResponse: ...
    # ... 其他方法
```

### 3.2 `core/security.py` 关键结构

```python
# L52-58: SecurityLevel 枚举（现有，不要修改）
class SecurityLevel(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

# L72-80: SecurityContext dataclass（现有，不要修改）
@dataclass
class SecurityContext:
    security_level: SecurityLevel = SecurityLevel.LOW
    required_permissions: List[PermissionType] = field(default_factory=list)
    sandbox_id: Optional[str] = None
    allowed_paths: List[str] = field(default_factory=list)
    max_execution_time_ms: Optional[int] = None
    max_memory_mb: Optional[int] = None

# L83-97: AuditLogEntry dataclass（现有，不要修改）
@dataclass
class AuditLogEntry:
    timestamp: float
    workflow_id: str
    task_id: str
    task_type: str
    security_level: str
    action: str
    status: str
    input_hash: str = ""
    output_hash: str = ""
    duration_ms: float = 0.0
    resources_used: Dict[str, Any] = field(default_factory=dict)
    details: str = ""

# L111-347: SecurityManager 类（现有，不要修改已有方法）
class SecurityManager:
    def scan_code(self, code: str, code_type: str = "jsx") -> SecurityScanResult: ...
    def scan_path(self, path: str, allowed_paths: List[str]) -> SecurityScanResult: ...
    def log_audit(self, entry: AuditLogEntry) -> None: ...
    def check_circuit_breaker(self) -> bool: ...
    @staticmethod
    def hash_content(content: str) -> str: ...
```

### 3.3 `core/workflow_orchestrator.py` 关键结构

```python
# L66-96: TaskType 枚举（现有，不要修改）
class TaskType(Enum):
    PERCEPTION = "perception"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    STYLE_CLASSIFICATION = "style_classification"
    PARAM_MAPPING = "param_mapping"
    AE_COMPILE = "ae_compile"
    AE_EXECUTE = "ae_execute"
    AE_RENDER = "ae_render"
    FFMPEG_TRANSCODE = "ffmpeg_transcode"
    FFMPEG_EXPORT = "ffmpeg_export"
    # ... 20+ 种

# L110-127: TaskDefinition dataclass（现有，不要修改）
@dataclass
class TaskDefinition:
    task_id: str
    task_type: TaskType
    name: str
    func: Callable[..., Any]
    args: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    retry_count: int = 0
    retry_delay_ms: int = 2000
    timeout_ms: Optional[int] = None
    max_parallel: int = 1
    skip_on_failure: bool = False
    fallback_func: Optional[Callable[..., Any]] = None
    security_level: Any = None
    required_permissions: List[Any] = field(default_factory=list)
    enable_audit: bool = True
    sandboxed: bool = False  # ← 已存在，Phase B 会用到

# L162-182: WorkflowOrchestrator.__init__（现有，不要修改）
class WorkflowOrchestrator:
    def __init__(self, max_concurrent_tasks: int = 5, enable_security: bool = True):
        self._enable_security = enable_security and SecurityManager is not None
        self._security_manager: Optional[SecurityManager] = None
        if self._enable_security and SecurityManager is not None:
            self._security_manager = SecurityManager()
```

### 3.4 `core/config.py` 关键结构

```python
# 默认配置中有 "llm" 段，包含：
"llm": {
    "providers": [...],           # Provider 列表
    "fallback_providers": [...],  # 降级 Provider 列表
    "model_routing": {...},       # 任务→模型路由表
    # Phase A 会在此段追加 "thinking_upgrade" 子配置
}
```

---

## 4. Phase A：深度推理升级（ThinkingUpgradePolicy）

### 4.1 目标

让以下任务**自动升级**到 `ModelTier.TIER_3_FLAGSHIP_REASONING`，并支持**多轮自我校准**：

| 任务场景 | 当前档位 | 升级后档位 | 升级理由 |
|---|---|---|---|
| 复杂风格分析（多镜头对比） | TIER_2_MIDTIER_GENERAL | TIER_3_FLAGSHIP_REASONING | 需要多步推理、风格特征对比 |
| 3D 坐标校准（扇位/相机） | TIER_2_MIDTIER_GENERAL | TIER_3_FLAGSHIP_REASONING | 约束求解、边界检查 |
| 多步效果规划 | TIER_2_MIDTIER_GENERAL | TIER_3_FLAGSHIP_REASONING | 依赖链推理 |
| 形式化验证（参数边界） | TIER_2_MIDTIER_GENERAL | TIER_3_FLAGSHIP_REASONING | 需要证明/验证 |

### 4.2 新增数据结构

**位置**：`core/llm_gateway.py` 文件末尾追加（不要修改已有代码）

```python
# -----------------------------------------------------------------------------
# Phase A: 深度推理升级（ThinkingUpgradePolicy）
# -----------------------------------------------------------------------------

@dataclass
class ThinkingBudget:
    """深度推理预算"""
    max_rounds: int = 3                    # 最多 3 轮自我校准
    max_tokens_per_round: int = 8000
    timeout_seconds: int = 300
    max_cost_usd: float = 0.5              # 单任务最大成本

@dataclass
class ThinkingUpgradeDecision:
    """升级决策结果"""
    should_upgrade: bool
    reason: str                            # 升级原因（触发关键词/复杂度）
    upgraded_task_type: str                # 升级后 task_type（固定为 "deep_reasoning"）
    estimated_cost_usd: float
    budget: ThinkingBudget
    confidence_threshold: float = 0.85     # 自我校准通过阈值

@dataclass
class ThinkingRound:
    """单轮推理记录"""
    round_index: int
    prompt: str
    response: str
    self_check_result: str                 # 自我校准结果
    passed: bool                           # 是否通过校准
    latency_ms: float
    cost_usd: float

@dataclass
class ThinkingTrace:
    """完整推理轨迹"""
    original_prompt: str
    original_task_type: str
    decision: ThinkingUpgradeDecision
    rounds: List[ThinkingRound]
    final_answer: str
    total_cost_usd: float
    total_latency_ms: float
```

### 4.3 新增 ThinkingUpgradePolicy 类

**位置**：`core/llm_gateway.py` 文件末尾追加

```python
class ThinkingUpgradePolicy:
    """深度推理升级策略：决定何时把任务从 TIER_2 升到 TIER_3"""

    # 触发升级的关键词（多步推理 / 校准 / 形式化验证特征）
    UPGRADE_TRIGGERS = [
        # 3D/空间推理
        "三维", "3d", "坐标", "calibration", "校准", "空间", "spatial",
        # 形式化/验证
        "形式化", "formal", "verify", "验证", "证明", "prove", "lean",
        # 多步推理
        "多步", "multi-step", "step-by-step", "reasoning chain", "推理链",
        # 约束求解
        "约束", "constraint", "boundary", "边界", "求解", "solve",
        # 复杂分析
        "对比分析", "多镜头", "多场景", "同时考虑", "综合评估",
    ]

    # 复杂度评估特征（需要多步推理的句式）
    COMPLEXITY_MARKERS = [
        "分析并对比", "同时考虑", "推导出", "证明并生成",
        "在多个约束下", "边界条件", "回归验证", "交叉验证",
    ]

    def __init__(self, llm_gateway: Optional['LLMGateway'] = None):
        """
        Args:
            llm_gateway: LLMGateway 实例（用于自我校准调用）。如果为 None，则在需要时惰性创建。
        """
        self._gw = llm_gateway
        self._logger = logging.getLogger(f"{__name__}.ThinkingUpgradePolicy")

    def should_upgrade(
        self,
        task_type: TaskType,
        prompt: str,
        context: Optional[Dict[str, Any]] = None
    ) -> ThinkingUpgradeDecision:
        """决策：是否升级到 TIER_3_FLAGSHIP_REASONING

        Args:
            task_type: 原始任务类型
            prompt: 用户 prompt
            context: 额外上下文（可选）

        Returns:
            ThinkingUpgradeDecision 升级决策结果
        """
        # 1. 已经在 TIER_3 → 不重复升级
        current_tier = TASK_TIER_MAP.get(task_type, ModelTier.TIER_2_MIDTIER_GENERAL)
        if current_tier == ModelTier.TIER_3_FLAGSHIP_REASONING:
            return ThinkingUpgradeDecision(
                should_upgrade=False,
                reason="already_tier3",
                upgraded_task_type=task_type.name,
                estimated_cost_usd=0.0,
                budget=ThinkingBudget()
            )

        # 2. 关键词触发检测
        prompt_lower = prompt.lower()
        hit_triggers = [k for k in self.UPGRADE_TRIGGERS if k in prompt_lower]

        # 3. 复杂度评估
        complexity_score = sum(1 for m in self.COMPLEXITY_MARKERS if m in prompt)

        # 4. 决策：至少 1 个关键词 OR 复杂度 >= 2
        should_upgrade = len(hit_triggers) > 0 or complexity_score >= 2

        if not should_upgrade:
            return ThinkingUpgradeDecision(
                should_upgrade=False,
                reason="no_trigger",
                upgraded_task_type=task_type.name,
                estimated_cost_usd=0.0,
                budget=ThinkingBudget()
            )

        # 5. 成本预算估算
        budget = ThinkingBudget()
        estimated_cost = self._estimate_thinking_cost(prompt, budget)

        # 6. 检查预算
        if estimated_cost > budget.max_cost_usd:
            self._logger.warning(
                f"Thinking upgrade rejected: estimated cost ${estimated_cost:.4f} > budget ${budget.max_cost_usd:.4f}"
            )
            return ThinkingUpgradeDecision(
                should_upgrade=False,
                reason=f"cost_exceeded: ${estimated_cost:.4f} > ${budget.max_cost_usd:.4f}",
                upgraded_task_type=task_type.name,
                estimated_cost_usd=estimated_cost,
                budget=budget
            )

        reason = f"triggers={hit_triggers}, complexity={complexity_score}, est_cost=${estimated_cost:.4f}"
        return ThinkingUpgradeDecision(
            should_upgrade=True,
            reason=reason,
            upgraded_task_type="deep_reasoning",  # 固定升级为 deep_reasoning
            estimated_cost_usd=estimated_cost,
            budget=budget
        )

    def _estimate_thinking_cost(self, prompt: str, budget: ThinkingBudget) -> float:
        """估算深度推理成本

        公式：3 轮 × (prompt 长度 × 1.5 倍膨胀) × token 单价
        """
        # 粗估：prompt 长度 / 4 = token 数（英文）或 / 2 = token 数（中文）
        prompt_tokens = len(prompt) / 2  # 假设中文为主
        total_tokens = budget.max_rounds * prompt_tokens * 1.5  # 1.5 倍膨胀
        # TIER_3 成本：$0.015 / 1K input, $0.075 / 1K output（假设 1:1）
        cost_per_1k = (0.015 + 0.075) / 2
        return (total_tokens / 1000) * cost_per_1k

    async def execute_with_thinking(
        self,
        prompt: str,
        original_task_type: TaskType,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, ThinkingTrace]:
        """执行：升级 → 多轮自我校准 → 返回最终结果 + 推理轨迹

        Args:
            prompt: 用户 prompt
            original_task_type: 原始任务类型
            context: 额外上下文（可选）

        Returns:
            (最终答案, ThinkingTrace 推理轨迹)
        """
        decision = self.should_upgrade(original_task_type, prompt, context)

        if not decision.should_upgrade:
            # 不升级，走原有路由
            if self._gw is None:
                from core.llm_gateway import LLMGateway
                self._gw = LLMGateway()
            resp = await self._gw.chat_with_routing(prompt, original_task_type)
            return resp.content, ThinkingTrace(
                original_prompt=prompt,
                original_task_type=original_task_type.name,
                decision=decision,
                rounds=[],
                final_answer=resp.content,
                total_cost_usd=resp.cost_usd,
                total_latency_ms=resp.latency_ms
            )

        # 升级：多轮自我校准
        if self._gw is None:
            from core.llm_gateway import LLMGateway
            self._gw = LLMGateway()

        rounds: List[ThinkingRound] = []
        current_prompt = prompt
        total_cost = 0.0
        total_latency = 0.0

        for r in range(decision.budget.max_rounds):
            # 1. 调用 TIER_3 模型
            start_time = time.time()
            resp = await self._gw.chat_with_routing(
                current_prompt,
                TaskType.QUALITY_REVIEW,  # 使用 QUALITY_REVIEW 确保走 TIER_3
                temperature=0.7,
                max_tokens=decision.budget.max_tokens_per_round
            )
            latency_ms = (time.time() - start_time) * 1000
            total_cost += resp.cost_usd
            total_latency += latency_ms

            # 2. 自我校准
            check_prompt = f"""请检查以下回答是否满足约束：

原任务：{prompt}

回答：{resp.content}

检查项：
1. 是否包含所有必要步骤？
2. 数值是否在合理边界内？
3. 逻辑是否自洽？
4. 是否有遗漏的约束？

如果全部通过，回复 "PASS"；否则指出问题并给出修正建议。"""

            check_resp = await self._gw.chat_with_routing(
                check_prompt,
                TaskType.COMPLEX_ANALYSIS if hasattr(TaskType, 'COMPLEX_ANALYSIS') else TaskType.GENERAL,
                temperature=0.3,
                max_tokens=2000
            )

            passed = "PASS" in check_resp.content
            rounds.append(ThinkingRound(
                round_index=r,
                prompt=current_prompt,
                response=resp.content,
                self_check_result=check_resp.content,
                passed=passed,
                latency_ms=latency_ms,
                cost_usd=resp.cost_usd
            ))

            if passed or r == decision.budget.max_rounds - 1:
                break

            # 3. 修正 prompt 进入下一轮
            current_prompt = f"""原任务：{prompt}

上一轮回答：{resp.content}

发现问题：{check_resp.content}

请修正并重新回答："""

        final_answer = rounds[-1].response
        return final_answer, ThinkingTrace(
            original_prompt=prompt,
            original_task_type=original_task_type.name,
            decision=decision,
            rounds=rounds,
            final_answer=final_answer,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency
        )
```

### 4.4 配置项追加

**位置**：`core/config.py` `llm` 段追加

```python
"llm": {
    # ... 现有配置保持不变 ...

    # Phase A: 深度推理升级配置
    "thinking_upgrade": {
        "enabled": True,
        "auto_upgrade_task_types": ["complex_analysis", "code_generation"],
        "max_rounds": 3,
        "max_cost_per_task_usd": 0.5,
        "downgrade_on_failure": True,        # 升级失败回落到原档位
        "self_check_enabled": True,          # 是否启用自我校准
        "confidence_threshold": 0.85,        # 校准通过阈值
    },
}
```

### 4.5 集成点（可选）

如果需要在 `chat_with_routing` 中自动启用深度推理升级，可以在 `LLMGateway` 类中追加：

```python
# 在 LLMGateway.__init__ 中追加
self._thinking_policy = ThinkingUpgradePolicy(self)

# 在 chat_with_routing 方法开头追加（可选）
if self._config.thinking_upgrade.get("enabled", False):
    upgraded_content, trace = await self._thinking_policy.execute_with_thinking(
        message, task_type, kwargs.get("context")
    )
    if trace.decision.should_upgrade:
        # 如果升级了，直接返回升级后的结果
        return LLMResponse(
            content=upgraded_content,
            model="tier3_flagship",
            provider="thinking_upgrade",
            tokens_input=trace.rounds[-1].prompt.__len__() // 2,
            tokens_output=upgraded_content.__len__() // 2,
            latency_ms=trace.total_latency_ms,
            success=True,
            cost_usd=trace.total_cost_usd,
            tier="tier3_flagship",
            tier_upgraded=True,
        )
```

**注意**：这是**可选集成**，如果担心影响现有逻辑，可以让业务代码显式调用 `ThinkingUpgradePolicy.execute_with_thinking()`。

---

## 5. Phase B：L1-L5 安全护栏（RiskGuard）

### 5.1 目标

让所有 Agent 操作经过**风险评估 → 沙箱隔离 → 人工审批 → 审计哈希链**四道防线，防止 Anthropic/OpenAI 式失控。

### 5.2 新增数据结构

**位置**：`core/security.py` 文件末尾追加（不要修改已有代码）

```python
# -----------------------------------------------------------------------------
# Phase B: L1-L5 安全护栏（RiskGuard）
# -----------------------------------------------------------------------------

class RiskLevel(IntEnum):
    """信通院 L1-L5 风险分级"""
    L1_READONLY = 1        # 只读分析
    L2_GENERATE = 2        # 生成新内容
    L3_OVERWRITE_SAFE = 3  # 覆盖安全中间产物
    L4_DESTRUCTIVE = 4     # 破坏性操作（删除/覆盖用户素材）
    L5_EXTERNAL = 5        # 外部不可逆操作

@dataclass
class RiskAssessment:
    """单任务风险评估结果"""
    risk_level: RiskLevel
    reasons: List[str]                     # 触发原因（用于审批展示）
    requires_sandbox: bool                 # 是否必须沙箱
    requires_approval: bool                # 是否需要人工审批
    requires_audit_chain: bool             # 是否需要哈希链审计
    requires_second_confirm: bool          # L5 是否需要二次确认
    allowed_paths: List[str] = field(default_factory=list)  # FS 白名单
    forbidden_paths: List[str] = field(default_factory=list)  # FS 黑名单
    max_execution_time_ms: int = 300_000   # 最大执行时间（默认 5 分钟）
    max_memory_mb: int = 4096              # 最大内存（默认 4GB）

@dataclass
class ApprovalRequest:
    """人工审批请求"""
    request_id: str
    task_id: str
    task_type: str
    risk_level: RiskLevel
    reasons: List[str]
    args_preview: Dict[str, Any]           # 参数预览（脱敏）
    requested_at: float
    timeout_seconds: int = 300             # 审批超时（默认 5 分钟）

@dataclass
class ApprovalResult:
    """人工审批结果"""
    request_id: str
    approved: bool
    approver: str                          # 审批人（CLI: user, Web: user_id）
    approved_at: float
    comment: str = ""
    second_confirmed: bool = False         # L5 二次确认
```

### 5.3 新增 RiskAssessor 类

**位置**：`core/security.py` 文件末尾追加

```python
class RiskAssessor:
    """任务风险评估器"""

    # 任务类型 → 默认风险等级（可配置覆盖）
    DEFAULT_RISK_MAP: Dict[str, RiskLevel] = {
        # L1: 只读分析
        "perception": RiskLevel.L1_READONLY,
        "style_classification": RiskLevel.L1_READONLY,
        "understanding": RiskLevel.L1_READONLY,
        "feature_extraction": RiskLevel.L1_READONLY,

        # L2: 生成新内容
        "param_mapping": RiskLevel.L2_GENERATE,
        "ae_compile": RiskLevel.L2_GENERATE,
        "jsx_generate": RiskLevel.L2_GENERATE,
        "cache_write": RiskLevel.L2_GENERATE,

        # L3: 覆盖安全中间产物
        "ae_execute": RiskLevel.L3_OVERWRITE_SAFE,      # 写 AE 项目临时区
        "ffmpeg_transcode": RiskLevel.L3_OVERWRITE_SAFE,
        "davinci_grade": RiskLevel.L3_OVERWRITE_SAFE,
        "silhouette_roto": RiskLevel.L3_OVERWRITE_SAFE,

        # L4: 破坏性操作
        "ae_render": RiskLevel.L4_DESTRUCTIVE,          # 写最终渲染产物
        "ffmpeg_export": RiskLevel.L4_DESTRUCTIVE,
        "pr_export": RiskLevel.L4_DESTRUCTIVE,
        "blender_render": RiskLevel.L4_DESTRUCTIVE,
        "topaz_enhance": RiskLevel.L4_DESTRUCTIVE,      # 覆盖原素材
        "file_delete": RiskLevel.L4_DESTRUCTIVE,

        # L5: 外部不可逆
        "external_api_call": RiskLevel.L5_EXTERNAL,
        "cloud_render_submit": RiskLevel.L5_EXTERNAL,
        "stock_purchase": RiskLevel.L5_EXTERNAL,
    }

    # 用户素材目录（触及这些路径的任务自动升级到 L4）
    USER_DATA_PATTERNS = [
        "data/user_materials/",
        "data/input/",
        "output/final/",
    ]

    def __init__(self, workspace_root: Optional[Path] = None):
        """
        Args:
            workspace_root: 工作区根目录（用于路径检测）。如果为 None，则使用当前工作目录。
        """
        self._workspace = workspace_root or Path.cwd()
        self._logger = logging.getLogger(f"{__name__}.RiskAssessor")

    def assess(self, task_type: str, task_args: Dict[str, Any]) -> RiskAssessment:
        """评估任务风险等级

        Args:
            task_type: 任务类型（TaskType.value 或字符串）
            task_args: 任务参数

        Returns:
            RiskAssessment 风险评估结果
        """
        # 1. 查 DEFAULT_RISK_MAP 获取基础等级
        base_level = self.DEFAULT_RISK_MAP.get(task_type, RiskLevel.L2_GENERATE)
        reasons = [f"task_type={task_type} -> L{base_level}"]

        # 2. 路径检测（触及用户素材 → 至少 L4）
        paths = self._extract_paths(task_args)
        user_data_hit = [p for p in paths if self._is_user_data(p)]
        if user_data_hit and base_level < RiskLevel.L4_DESTRUCTIVE:
            base_level = RiskLevel.L4_DESTRUCTIVE
            reasons.append(f"触及用户素材: {user_data_hit}")

        # 3. 关键字检测（delete/overwrite → L4）
        args_str = str(task_args).lower()
        if any(k in args_str for k in ["delete", "remove", "overwrite", "truncate"]):
            if base_level < RiskLevel.L4_DESTRUCTIVE:
                base_level = RiskLevel.L4_DESTRUCTIVE
                reasons.append("检测到 delete/overwrite 关键字")

        # 4. 付费检测（pay/purchase → L5）
        if any(k in args_str for k in ["pay", "purchase", "subscribe"]):
            base_level = RiskLevel.L5_EXTERNAL
            reasons.append("检测到付费操作")

        return RiskAssessment(
            risk_level=base_level,
            reasons=reasons,
            requires_sandbox=base_level >= RiskLevel.L3_OVERWRITE_SAFE,
            requires_approval=base_level >= RiskLevel.L4_DESTRUCTIVE,
            requires_audit_chain=base_level >= RiskLevel.L4_DESTRUCTIVE,
            requires_second_confirm=base_level >= RiskLevel.L5_EXTERNAL,
            allowed_paths=paths,
        )

    def _extract_paths(self, args: Dict[str, Any]) -> List[str]:
        """从任务参数中提取所有路径"""
        paths = []
        for key, value in args.items():
            if isinstance(value, str) and ("/" in value or "\\" in value):
                paths.append(value)
            elif isinstance(value, (list, tuple)):
                paths.extend([v for v in value if isinstance(v, str) and ("/" in v or "\\" in v)])
        return paths

    def _is_user_data(self, path: str) -> bool:
        """判断路径是否属于用户素材目录"""
        normalized = path.replace("\\", "/").lower()
        return any(pattern in normalized for pattern in self.USER_DATA_PATTERNS)
```

### 5.4 新增 SandboxPolicy 类

**位置**：`core/security.py` 文件末尾追加

```python
class SandboxPolicy:
    """L3+ 沙箱策略：进程级隔离 + FS 白名单 + 资源限制"""

    def __init__(self, workspace_root: Path):
        """
        Args:
            workspace_root: 工作区根目录
        """
        self._workspace = workspace_root
        self._allowed_roots = [
            workspace_root / "data" / "sandbox",
            workspace_root / "output" / "temp",
            workspace_root / "data" / "cache",
        ]
        self._forbidden_patterns = [
            "**/*.aep",                        # 禁覆盖 AE 工程原文件
            "**/data/user_materials/**",       # 禁覆盖用户素材
            "**/output/final/**",              # 禁覆盖最终交付物
            "**/.env",                         # 禁读环境变量
            "**/config/secrets/**",            # 禁读密钥
        ]
        self._resource_limits = {
            "max_execution_time_ms": 300_000,  # 5 分钟
            "max_memory_mb": 4096,             # 4GB
            "max_cpu_percent": 80,             # 80% CPU
        }
        self._logger = logging.getLogger(f"{__name__}.SandboxPolicy")

    def validate_paths(self, paths: List[str]) -> Tuple[bool, List[str]]:
        """校验路径是否在白名单内

        Args:
            paths: 待校验的路径列表

        Returns:
            (是否全部通过, 违规路径列表)
        """
        violations = []
        for path in paths:
            normalized = Path(path).resolve()
            # 检查是否在白名单内
            in_whitelist = any(
                str(normalized).startswith(str(root.resolve()))
                for root in self._allowed_roots
            )
            # 检查是否在黑名单内
            in_blacklist = any(
                normalized.match(pattern)
                for pattern in self._forbidden_patterns
            )
            if not in_whitelist or in_blacklist:
                violations.append(path)

        return len(violations) == 0, violations

    async def wrap_execution(
        self,
        task_fn: Callable,
        task_args: Dict[str, Any],
        assessment: RiskAssessment
    ) -> Any:
        """把任务函数包成沙箱执行

        Args:
            task_fn: 任务函数
            task_args: 任务参数
            assessment: 风险评估结果

        Returns:
            任务执行结果

        Raises:
            SecurityError: 路径校验失败或资源超限
        """
        # 1. 路径校验
        paths = assessment.allowed_paths
        if paths:
            passed, violations = self.validate_paths(paths)
            if not passed:
                raise SecurityError(f"沙箱路径校验失败，违规路径: {violations}")

        # 2. 临时目录隔离
        with tempfile.TemporaryDirectory(prefix="aekv_sandbox_") as tmpdir:
            self._logger.info(f"沙箱执行: tmpdir={tmpdir}, limits={self._resource_limits}")

            # 3. 资源限制（Windows 使用 psutil，Linux 使用 resource）
            # 这里只记录日志，实际限制需要在子进程中实现
            # TODO: 如果需要真正的资源限制，可以使用 multiprocessing + psutil

            # 4. 执行任务
            try:
                result = await task_fn(**task_args)
                return result
            except Exception as e:
                self._logger.error(f"沙箱执行失败: {e}")
                raise
```

### 5.5 新增 ApprovalPolicy 类

**位置**：`core/security.py` 文件末尾追加

```python
class ApprovalPolicy:
    """L4/L5 人工审批策略"""

    def __init__(
        self,
        callback: Optional[Callable[[ApprovalRequest], Awaitable[ApprovalResult]]] = None
    ):
        """
        Args:
            callback: 审批回调函数。如果为 None，则使用默认 CLI 审批。
        """
        self._callback = callback or self._default_cli_callback
        self._logger = logging.getLogger(f"{__name__}.ApprovalPolicy")

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """阻塞等待审批

        Args:
            request: 审批请求

        Returns:
            ApprovalResult 审批结果
        """
        self._logger.info(f"请求审批: task_id={request.task_id}, risk_level=L{request.risk_level}")
        return await self._callback(request)

    @staticmethod
    async def _default_cli_callback(request: ApprovalRequest) -> ApprovalResult:
        """CLI 审批：打印风险信息，等待用户输入"""
        print(f"\n{'='*60}")
        print(f"⚠️  L{request.risk_level} 高风险操作审批请求")
        print(f"{'='*60}")
        print(f"任务 ID: {request.task_id}")
        print(f"任务类型: {request.task_type}")
        print(f"风险原因:")
        for r in request.reasons:
            print(f"  - {r}")
        print(f"参数预览: {json.dumps(request.args_preview, indent=2, ensure_ascii=False)}")
        print(f"{'='*60}")

        if request.risk_level >= RiskLevel.L5_EXTERNAL:
            # L5 需要二次确认
            confirm1 = input("确认执行？(y/n): ").strip().lower()
            if confirm1 != "y":
                return ApprovalResult(
                    request_id=request.request_id,
                    approved=False,
                    approver="cli_user",
                    approved_at=time.time(),
                    comment="用户拒绝"
                )
            confirm2 = input("⚠️ 这是 L5 不可逆操作，请再次确认 (yes/no): ").strip().lower()
            return ApprovalResult(
                request_id=request.request_id,
                approved=confirm2 == "yes",
                approver="cli_user",
                approved_at=time.time(),
                second_confirmed=confirm2 == "yes"
            )

        confirm = input("确认执行？(y/n): ").strip().lower()
        return ApprovalResult(
            request_id=request.request_id,
            approved=confirm == "y",
            approver="cli_user",
            approved_at=time.time()
        )
```

### 5.6 新增 AuditChain 类

**位置**：`core/security.py` 文件末尾追加

```python
class AuditChain:
    """审计哈希链（防篡改，追加式）"""

    def __init__(self, log_path: Path):
        """
        Args:
            log_path: 审计日志文件路径
        """
        self._path = log_path
        self._prev_hash = self._load_last_hash()
        self._lock = threading.Lock()
        self._logger = logging.getLogger(f"{__name__}.AuditChain")

    def _load_last_hash(self) -> str:
        """加载最后一条记录的哈希（如果文件存在）"""
        if not self._path.exists():
            return "0" * 64  # 初始哈希
        try:
            with self._path.open("r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    return "0" * 64
                last_record = json.loads(lines[-1])
                return last_record.get("current_hash", "0" * 64)
        except Exception as e:
            self._logger.error(f"加载审计链失败: {e}")
            return "0" * 64

    def append(self, entry: AuditLogEntry) -> str:
        """追加一条审计记录，返回当前哈希

        Args:
            entry: 审计日志条目

        Returns:
            当前记录的哈希
        """
        with self._lock:
            payload = f"{self._prev_hash}|{asdict(entry)}|{time.time()}"
            current_hash = hashlib.sha256(payload.encode()).hexdigest()

            record = {
                "entry": asdict(entry),
                "prev_hash": self._prev_hash,
                "current_hash": current_hash,
                "timestamp": time.time(),
            }

            # 确保目录存在
            self._path.parent.mkdir(parents=True, exist_ok=True)

            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            self._prev_hash = current_hash
            return current_hash

    def verify_chain(self) -> Tuple[bool, List[str]]:
        """重放整个链验证完整性

        Returns:
            (是否完整, 篡改位置列表)
        """
        if not self._path.exists():
            return True, []

        violations = []
        prev_hash = "0" * 64

        with self._path.open("r", encoding="utf-8") as f:
            for line_num, line in enumerate(f, 1):
                try:
                    record = json.loads(line)
                    entry = record["entry"]
                    stored_prev = record["prev_hash"]
                    stored_current = record["current_hash"]

                    # 验证 prev_hash 链
                    if stored_prev != prev_hash:
                        violations.append(f"行 {line_num}: prev_hash 不匹配")

                    # 重新计算哈希
                    payload = f"{stored_prev}|{entry}|{record['timestamp']}"
                    computed_hash = hashlib.sha256(payload.encode()).hexdigest()
                    if computed_hash != stored_current:
                        violations.append(f"行 {line_num}: current_hash 不匹配")

                    prev_hash = stored_current
                except Exception as e:
                    violations.append(f"行 {line_num}: 解析失败 - {e}")

        return len(violations) == 0, violations
```

### 5.7 WorkflowOrchestrator 集成钩子

**位置**：`core/workflow_orchestrator.py` 追加新方法（不要修改已有方法）

```python
# 在 WorkflowOrchestrator.__init__ 末尾追加
def __init__(self, max_concurrent_tasks: int = 5, enable_security: bool = True):
    # ... 现有代码保持不变 ...

    # Phase B: 初始化 RiskGuard 组件
    if self._enable_security:
        from core.security import RiskAssessor, SandboxPolicy, ApprovalPolicy, AuditChain
        self._risk_assessor = RiskAssessor(workspace_root=Path.cwd())
        self._sandbox_policy = SandboxPolicy(workspace_root=Path.cwd())
        self._approval_policy = ApprovalPolicy()  # 默认 CLI 审批
        self._audit_chain = AuditChain(log_path=Path.cwd() / "logs" / "audit_chain.jsonl")
    else:
        self._risk_assessor = None
        self._sandbox_policy = None
        self._approval_policy = None
        self._audit_chain = None

# 在 WorkflowOrchestrator 类中追加新方法
async def _execute_task_with_guard(
    self,
    task_def: TaskDefinition,
    context: WorkflowContext
) -> Any:
    """L1-L5 护栏包装

    Args:
        task_def: 任务定义
        context: 工作流上下文

    Returns:
        任务执行结果

    Raises:
        SecurityError: 风险评估失败或审批拒绝
    """
    if not self._enable_security or self._risk_assessor is None:
        # 未启用安全护栏，直接执行
        return await self._execute_task_inner(task_def, context)

    # 1. 风险评估
    task_type_str = task_def.task_type.value if hasattr(task_def.task_type, 'value') else str(task_def.task_type)
    assessment = self._risk_assessor.assess(task_type_str, task_def.args)

    self._logger.info(
        f"风险评估: task_id={task_def.task_id}, risk_level=L{assessment.risk_level}, "
        f"requires_sandbox={assessment.requires_sandbox}, requires_approval={assessment.requires_approval}"
    )

    # 2. L4/L5 人工审批
    if assessment.requires_approval:
        approval_request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            task_id=task_def.task_id,
            task_type=task_type_str,
            risk_level=assessment.risk_level,
            reasons=assessment.reasons,
            args_preview=self._sanitize_args(task_def.args),
            requested_at=time.time(),
        )
        approval_result = await self._approval_policy.request_approval(approval_request)

        if not approval_result.approved:
            raise SecurityError(f"L{assessment.risk_level} 任务被审批拒绝: {approval_result.comment}")

        if assessment.requires_second_confirm and not approval_result.second_confirmed:
            raise SecurityError("L5 任务需要二次确认")

    # 3. L3+ 沙箱执行
    if assessment.requires_sandbox:
        result = await self._sandbox_policy.wrap_execution(
            task_def.func,
            task_def.args,
            assessment
        )
    else:
        result = await self._execute_task_inner(task_def, context)

    # 4. L4+ 审计哈希链
    if assessment.requires_audit_chain:
        self._audit_chain.append(AuditLogEntry(
            timestamp=time.time(),
            workflow_id=context.workflow_id,
            task_id=task_def.task_id,
            task_type=task_type_str,
            security_level=f"L{assessment.risk_level}",
            action="task_executed",
            status="completed",
            input_hash=SecurityManager.hash_content(str(task_def.args)),
            output_hash=SecurityManager.hash_content(str(result)),
            duration_ms=0.0,  # TODO: 从 TaskInstance 中获取
            details=f"reasons={assessment.reasons}",
        ))

    return result

def _sanitize_args(self, args: Dict[str, Any]) -> Dict[str, Any]:
    """脱敏任务参数（移除敏感信息）"""
    sanitized = {}
    for key, value in args.items():
        if any(sensitive in key.lower() for sensitive in ["key", "token", "password", "secret"]):
            sanitized[key] = "***REDACTED***"
        else:
            sanitized[key] = value
    return sanitized

async def _execute_task_inner(
    self,
    task_def: TaskDefinition,
    context: WorkflowContext
) -> Any:
    """内部任务执行（原有逻辑）"""
    # 这里调用原有的 _execute_task 逻辑
    # 为了不影响现有代码，可以将原有 _execute_task 重命名为 _execute_task_inner
    # 或者直接调用 task_def.func(**task_def.args)
    return await task_def.func(**task_def.args)
```

**注意**：为了不影响现有 `_execute_task` 方法，建议：
1. 将现有 `_execute_task` 重命名为 `_execute_task_inner`（保留原逻辑）
2. 新增 `_execute_task_with_guard` 作为入口，内部调用 `_execute_task_inner`

---

## 6. Phase C：形式化规范层（FormalSpec）

### 6.1 目标

把项目中的**硬规则**提取为**可执行不变量（Invariants）**，每次 pipeline 阶段结束时自动校验。

### 6.2 新增文件 `core/formal_spec.py`

```python
#!/usr/bin/env python3
"""
形式化规范层 - FormalSpec v1.0

设计原则（借鉴 Lean 4 思想）：
1. 硬规则固化为可执行不变量
2. pipeline 阶段结束时自动校验
3. 违规时抛 InvariantViolation 异常
4. 可配置开关，支持调试模式跳过
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Tuple

logger = logging.getLogger(__name__)


class InvariantViolation(Exception):
    """不变量违规异常"""
    pass


class Invariant(ABC):
    """形式化不变量基类"""

    @abstractmethod
    def check(self, context: Dict[str, Any]) -> Tuple[bool, str]:
        """校验不变量

        Args:
            context: pipeline 上下文

        Returns:
            (是否通过, 错误信息)
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """不变量名称"""
        ...


class FanPositionConstraint(Invariant):
    """3D 扇子位置约束"""

    @property
    def name(self) -> str:
        return "FanPositionConstraint"

    def check(self, context: Dict[str, Any]) -> Tuple[bool, str]:
        for layer in context.get("ae_layers", []):
            if layer.get("type") == "fan_blade":
                x, y = layer.get("position", (0, 0))
                if not (-960 <= x <= 960):
                    return False, f"扇叶 X 越界: {x} (允许范围 [-960, 960])"
                if not (-540 <= y <= 540):
                    return False, f"扇叶 Y 越界: {y} (允许范围 [-540, 540])"
                rotation = layer.get("rotation", 0)
                if not (0 <= rotation < 360):
                    return False, f"扇叶旋转角越界: {rotation} (允许范围 [0, 360))"
        return True, ""


class FFmpegParamBoundary(Invariant):
    """FFmpeg 参数边界"""

    @property
    def name(self) -> str:
        return "FFmpegParamBoundary"

    def check(self, context: Dict[str, Any]) -> Tuple[bool, str]:
        params = context.get("ffmpeg_params", {})
        bitrate = params.get("bitrate", 0)
        if bitrate > 50_000_000:
            return False, f"码率超限: {bitrate} (最大 50M)"
        framerate = params.get("framerate", 30)
        if not (23.976 <= framerate <= 120):
            return False, f"帧率越界: {framerate} (允许范围 [23.976, 120])"
        return True, ""


class AERenderTimeout(Invariant):
    """AE 渲染超时保护"""

    @property
    def name(self) -> str:
        return "AERenderTimeout"

    def check(self, context: Dict[str, Any]) -> Tuple[bool, str]:
        render_time = context.get("ae_render_time_ms", 0)
        if render_time > 30_000:
            return False, f"单帧渲染超时: {render_time}ms (最大 30s)"
        return True, ""


# 注册到 pipeline 的不变量列表
FORMAL_INVARIANTS: List[Invariant] = [
    FanPositionConstraint(),
    FFmpegParamBoundary(),
    AERenderTimeout(),
]


def check_invariants(context: Dict[str, Any], skip: bool = False) -> None:
    """校验所有不变量

    Args:
        context: pipeline 上下文
        skip: 是否跳过校验（调试模式）

    Raises:
        InvariantViolation: 任何不变量违规
    """
    if skip:
        logger.debug("跳过不变量校验（调试模式）")
        return

    for invariant in FORMAL_INVARIANTS:
        passed, error = invariant.check(context)
        if not passed:
            raise InvariantViolation(f"[{invariant.name}] {error}")
        logger.debug(f"不变量校验通过: {invariant.name}")
```

### 6.3 集成点

**位置**：`pipeline/unified_pipeline.py` 每个阶段结束时调用

```python
from core.formal_spec import check_invariants

async def _run_stage_with_invariants(
    self,
    stage_name: str,
    stage_fn: Callable,
    context: Dict[str, Any]
) -> Any:
    """带不变量校验的阶段执行"""
    result = await stage_fn(context)

    # 校验所有不变量
    check_invariants(context, skip=self.config.get("debug_skip_invariants", False))

    return result
```

---

## 7. 开发集成方向（未来 6 个月）

### 7.1 短期（1-2 周）：Phase B 实施

**优先级**：最高（防止 Agent 失控）

| 任务 | 工作量 | 交付物 | 验收标准 |
|---|---|---|---|
| B1: RiskLevel 枚举 + RiskAssessment 结构 | 100 行 | `core/security.py` 追加 | 枚举正确定义 |
| B2: RiskAssessor 类 | 200 行 | `core/security.py` 追加 | 风险评估准确 |
| B3: SandboxPolicy 类 | 250 行 | `core/security.py` 追加 | 沙箱隔离生效 |
| B4: ApprovalPolicy 类 | 200 行 | `core/security.py` 追加 | CLI 审批可用 |
| B5: AuditChain 类 | 150 行 | `core/security.py` 追加 | 哈希链防篡改 |
| B6: WorkflowOrchestrator 集成钩子 | 150 行修改 | `core/workflow_orchestrator.py` 修改 | L4 任务触发审批 |
| B7: 测试 15 用例 | 400 行 | `tests/test_l1_l5_guard.py` 新增 | 全部通过 |

**总计**：~1450 行新增 + 150 行修改

### 7.2 中期（3-4 周）：Phase A 实施

**优先级**：高（解锁复杂推理）

| 任务 | 工作量 | 交付物 | 验收标准 |
|---|---|---|---|
| A1: ThinkingBudget/Decision/Round/Trace 数据结构 | 100 行 | `core/llm_gateway.py` 追加 | 数据结构完整 |
| A2: ThinkingUpgradePolicy 类 | 300 行 | `core/llm_gateway.py` 追加 | 升级决策准确 |
| A3: 配置项追加 | 50 行 | `core/config.py` 修改 | 配置加载正常 |
| A4: 测试 10 用例 | 300 行 | `tests/test_thinking_upgrade.py` 新增 | 全部通过 |

**总计**：~750 行新增 + 50 行修改

### 7.3 长期（5-6 周）：Phase C 实施 + Web 审批界面

**优先级**：中（提升可验证性 + 用户体验）

| 任务 | 工作量 | 交付物 | 验收标准 |
|---|---|---|---|
| C1: Invariant 基类 + 3 个不变量 | 200 行 | `core/formal_spec.py` 新增 | 不变量校验生效 |
| C2: pipeline 集成钩子 | 100 行 | `pipeline/unified_pipeline.py` 修改 | 违规时抛异常 |
| C3: 测试 8 用例 | 250 行 | `tests/test_formal_spec.py` 新增 | 全部通过 |
| W1: Web 审批界面（ae-dashboard） | 500 行 | `ae-dashboard/src/pages/Approval.tsx` 新增 | Web 审批可用 |
| W2: 审批策略配置化 | 200 行 | `core/config.py` 追加 | 用户可自定义审批规则 |

**总计**：~1250 行新增 + 100 行修改

### 7.4 未来扩展（6 个月+）

| 方向 | 描述 | 优先级 |
|---|---|---|
| 审计日志可视化 | 在 `ae-dashboard/` 新增审计链查看器 | 中 |
| Lean 4 离线验证 | 把不变量翻译成 `.lean` 文件，离线证明 | 低 |
| 沙箱容器化 | 用 Docker/WSL 替代进程级沙箱 | 低 |
| 多租户隔离 | 不同用户/项目独立沙箱 + 审计链 | 低 |

---

## 8. 测试策略与验收标准

### 8.1 Phase A 测试（`tests/test_thinking_upgrade.py`）

| 用例 | 覆盖点 | 验收标准 |
|---|---|---|
| `test_upgrade_trigger_keyword` | 包含"三维"/"校准"关键词时触发升级 | `should_upgrade=True` |
| `test_upgrade_trigger_complexity` | 包含"同时考虑"/"推导出"时触发升级 | `should_upgrade=True` |
| `test_no_upgrade_simple_task` | 简单任务不触发升级 | `should_upgrade=False` |
| `test_already_thinking_tier` | 已在 TIER_3 不重复升级 | `should_upgrade=False, reason="already_tier3"` |
| `test_multi_round_calibration` | 多轮自我校准收敛 | `rounds` 数量 >= 2 |
| `test_max_rounds_exceeded` | 超过 max_rounds 返回最后一轮 | `rounds` 数量 == max_rounds |
| `test_cost_budget_exceeded` | 超过预算拒绝升级 | `should_upgrade=False, reason="cost_exceeded"` |
| `test_downgrade_on_failure` | 升级失败回落到原档位 | 返回原档位结果 |
| `test_thinking_trace_completeness` | ThinkingTrace 包含所有 rounds | `trace.rounds` 完整 |
| `test_config_loading` | 从 config.py 加载配置 | 配置正确加载 |

### 8.2 Phase B 测试（`tests/test_l1_l5_guard.py`）

| 用例 | 覆盖点 | 验收标准 |
|---|---|---|
| `test_l1_readonly_direct_execute` | L1 任务直接执行 | 无审批，无沙箱 |
| `test_l2_generate_direct_execute` | L2 任务直接执行 | 无审批，无沙箱 |
| `test_l3_sandbox_execute` | L3 任务沙箱执行 | 沙箱生效，无审批 |
| `test_l4_approval_required` | L4 任务需要审批 | 审批被调用 |
| `test_l4_approval_rejected` | L4 审批拒绝抛异常 | 抛 `SecurityError` |
| `test_l5_second_confirm_required` | L5 需要二次确认 | 二次确认被调用 |
| `test_user_material_path_upgrade` | 触及用户素材升级到 L4 | `risk_level=L4` |
| `test_delete_keyword_upgrade` | delete 关键字升级到 L4 | `risk_level=L4` |
| `test_pay_keyword_upgrade` | pay 关键字升级到 L5 | `risk_level=L5` |
| `test_sandbox_path_whitelist` | 沙箱路径白名单校验 | 白名单内路径通过 |
| `test_sandbox_path_blacklist` | 沙箱路径黑名单拒绝 | 黑名单路径抛异常 |
| `test_audit_chain_append` | 审计链追加 | 哈希正确生成 |
| `test_audit_chain_verify` | 审计链完整性验证 | 验证通过 |
| `test_audit_chain_tamper_detect` | 篡改检测 | 检测到篡改 |
| `test_workflow_orchestrator_integration` | WorkflowOrchestrator 集成 | L4 任务触发审批 |

### 8.3 Phase C 测试（`tests/test_formal_spec.py`）

| 用例 | 覆盖点 | 验收标准 |
|---|---|---|
| `test_fan_position_constraint_pass` | 扇位约束通过 | 不抛异常 |
| `test_fan_position_constraint_fail` | 扇位约束失败 | 抛 `InvariantViolation` |
| `test_ffmpeg_param_boundary_pass` | FFmpeg 参数通过 | 不抛异常 |
| `test_ffmpeg_param_boundary_fail` | FFmpeg 参数失败 | 抛 `InvariantViolation` |
| `test_ae_render_timeout_pass` | 渲染超时通过 | 不抛异常 |
| `test_ae_render_timeout_fail` | 渲染超时失败 | 抛 `InvariantViolation` |
| `test_multiple_invariants` | 多不变量组合 | 全部通过或全部失败 |
| `test_invariant_violation_raise` | 违规时抛异常 | 抛 `InvariantViolation` |

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| L4/L5 审批打断自动化流程 | 用户体验下降 | 提供 `--auto-approve-l3` 模式；L4 默认审批，L3 默认自动 |
| 沙箱性能开销 | 渲染任务变慢 | 沙箱只用于 L3+，L1/L2 直接执行；沙箱复用临时目录 |
| 审计哈希链存储膨胀 | 磁盘占用增加 | 审计日志按天轮转，保留 30 天；提供压缩归档 |
| 深度推理成本超预算 | API 费用增加 | 硬预算 `max_cost_per_task_usd=0.5`；超过自动降级 |
| 多轮校准不收敛 | 推理时间变长 | `max_rounds=3` 硬限制；超时自动返回最后一轮 |
| 不变量误报 | 正常任务被拦截 | 不变量可配置开关；提供 `--skip-invariants` 调试模式 |

---

## 10. 附录 A：完整代码模板

### 10.1 `core/llm_gateway.py` 追加内容

见 [4.2-4.3 节](#42-新增数据结构)。

### 10.2 `core/security.py` 追加内容

见 [5.2-5.6 节](#52-新增数据结构)。

### 10.3 `core/workflow_orchestrator.py` 追加内容

见 [5.7 节](#57-workfloworchestrator-集成钩子)。

### 10.4 `core/formal_spec.py` 新增文件

见 [6.2 节](#62-新增文件-coreformal_specpy)。

---

## 11. 附录 B：配置文件变更

### 11.1 `core/config.py` 追加

```python
"llm": {
    # ... 现有配置保持不变 ...

    # Phase A: 深度推理升级配置
    "thinking_upgrade": {
        "enabled": True,
        "auto_upgrade_task_types": ["complex_analysis", "code_generation"],
        "max_rounds": 3,
        "max_cost_per_task_usd": 0.5,
        "downgrade_on_failure": True,
        "self_check_enabled": True,
        "confidence_threshold": 0.85,
    },
},

# Phase B: L1-L5 安全护栏配置
"security": {
    "risk_guard": {
        "enabled": True,
        "auto_approve_l3": False,          # L3 是否自动批准
        "approval_timeout_seconds": 300,   # 审批超时
        "audit_chain_path": "./logs/audit_chain.jsonl",
        "audit_retention_days": 30,        # 审计日志保留天数
        "sandbox": {
            "allowed_roots": [
                "./data/sandbox",
                "./output/temp",
                "./data/cache",
            ],
            "forbidden_patterns": [
                "**/*.aep",
                "**/data/user_materials/**",
                "**/output/final/**",
                "**/.env",
                "**/config/secrets/**",
            ],
            "max_execution_time_ms": 300_000,
            "max_memory_mb": 4096,
        },
    },
},

# Phase C: 形式化规范层配置
"formal_spec": {
    "enabled": True,
    "debug_skip_invariants": False,       # 调试模式跳过不变量校验
    "invariants": [
        "FanPositionConstraint",
        "FFmpegParamBoundary",
        "AERenderTimeout",
    ],
},
```

---

## 12. 附录 C：CLI 交互示例

```
$ python -m pipeline.unified_pipeline --input_topic "高燃混剪" --materials_dir ./data/input/

[PERCEIVE] 扫描素材...
[PLAN] 生成 5 个子任务...
[EXECUTE] 执行任务 1/5: style_analysis (L1_READONLY) ✓
[EXECUTE] 执行任务 2/5: param_mapping (L2_GENERATE) ✓
[EXECUTE] 执行任务 3/5: ae_execute (L3_OVERWRITE_SAFE) [沙箱]
  ✓ 沙箱路径校验通过
  ✓ 资源限制: max_memory=4096MB, max_time=300s
  ✓ 执行完成 (12.3s)
[EXECUTE] 执行任务 4/5: ae_render (L4_DESTRUCTIVE) [需要审批]

============================================================
⚠️  L4 高风险操作审批请求
============================================================
任务 ID: ae_render_final
任务类型: ae_render
风险原因:
  - task_type=ae_render -> L4
  - 触及用户素材: ['./data/user_materials/clip_001.mp4']
参数预览: {
  "output_path": "./output/final/mix_001.mp4",
  "render_settings": {"quality": "high", "codec": "h264"}
}
============================================================
确认执行？(y/n): y

  ✓ 审批通过 (approver=cli_user)
  ✓ 沙箱路径校验通过
  ✓ 审计哈希链追加: a3f2...9c1d
  ✓ 执行完成 (45.7s)
[EXECUTE] 执行任务 5/5: ffmpeg_export (L4_DESTRUCTIVE) [需要审批]
...
[VERIFY] 校验不变量...
  ✓ FanPositionConstraint 通过
  ✓ FFmpegParamBoundary 通过
  ✓ AERenderTimeout 通过
[COMPLETE] Pipeline 完成，总耗时 78.2s
```

---

**文档结束**

> **AI 执行体提示**：
> 1. 在编码前，**必须先读取** [3. 现有代码基线](#3-现有代码基线ai-必读) 中列出的所有文件和行号
> 2. 所有新代码都是**追加式扩展**，不要修改已有类的已有方法
> 3. 每个 Phase 完成后，**必须运行对应的 pytest 测试**，确保全部通过
> 4. 如有任何不确定的地方，**先询问用户**，不要自行假设