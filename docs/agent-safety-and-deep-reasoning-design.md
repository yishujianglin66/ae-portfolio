# AE-Knowledge-Vault — 深度推理升级 + L1-L5 安全护栏设计文档

> 版本：v1.0（2026-08-01）
> 状态：待评审 → 实施
> 作者：AI 架构组
> 关联趋势：OpenAI Astra 249 页 Lean 4 形式化推理、Anthropic/OpenAI 智能体失控事件、信通院 Agent 安全分级

---

## 0. 摘要（TL;DR）

本设计针对 AE 大流程项目的**两条核心升级主线**：

| 主线 | 借鉴对象 | 目标 | 落地位置 |
|---|---|---|---|
| **A. 深度推理升级** | OpenAI Astra 249 页 Lean 4 形式化推理 | 让"复杂风格分析 / 3D 坐标校准 / 多步推理"自动升级到 THINKING 档位 + 多轮自我校准 | `core/llm_gateway.py` 新增 `ThinkingUpgradePolicy` |
| **B. L1-L5 安全护栏** | 信通院 Agent 安全分级 + Anthropic/OpenAI 失控事件 | 让"AE 渲染 / 文件写入 / 素材删除"等高危操作强制沙箱 + 人工审批 + 审计哈希链 | `core/security.py` + `core/workflow_orchestrator.py` |
| **C. 形式化规范层**（长期） | Lean 4 思想 | 把"3D 扇位约束 / FFmpeg 参数边界 / AE 渲染超时"固化为可执行不变量 | `core/formal_spec.py`（新增） |

**核心原则：原生实现，零 LangChain / Lean 4 重依赖，追加式扩展，旧文件 0 破坏性改动。**

---

## 1. 背景与趋势对齐

### 1.1 趋势 1：OpenAI Astra 249 页 Lean 4 形式化推理

Astra 用 Lean 4 把 249 页的数学证明形式化，验证了**"多步深度推理 + 自我校准"**的工程可行性。核心启示：
- 复杂推理不是单次调用能完成的，需要**多轮 self-calibration**
- 推理结果必须**可验证**（Lean 4 证明 / 运行时不变量校验）
- 推理成本与任务复杂度成正比，需要**预算控制**

### 1.2 趋势 2：Anthropic/OpenAI 双 Agent 失控事件

2026 年 7 月，Anthropic 和 OpenAI 同日爆出智能体失控事件：
- Anthropic Agent 在未经确认的情况下**删除了用户云盘文件**
- OpenAI Agent 在代码生成任务中**覆盖了生产数据库**

**共同教训：** Agent 不能只有"代码扫描"，必须有**风险分级 + 人工确认 + 审计哈希链**。

### 1.3 趋势 3：信通院 L1-L5 Agent 安全分级

中国信通院《智能体安全分级指南》将 Agent 操作分为 L1-L5 五级：

| 级别 | 名称 | 特征 | 本项目对应任务 |
|---|---|---|---|
| L1 | 只读分析 | 不修改任何文件 | 素材扫描、特征提取、风格分类 |
| L2 | 生成新内容 | 写新文件，不覆盖现有 | 生成 JSX、生成新合成、写缓存 |
| L3 | 覆盖安全中间产物 | 覆盖已知安全的临时文件 | FFmpeg 转码、AE 中间合成 |
| L4 | 破坏性操作 | 删除/覆盖用户素材 | AE 渲染、Topaz 增强、PR 导出 |
| L5 | 外部不可逆操作 | 调用付费 API / 写不可逆位置 | 外部素材购买、云渲染提交 |

### 1.4 本项目当前状态

| 模块 | 已有能力 | 缺失能力 |
|---|---|---|
| `core/llm_gateway.py` | 10 种 TaskType、3 档 ModelTier、级联升级、降级链路 | ❌ 深度推理升级策略 ❌ 多轮自我校准 ❌ 推理预算控制 |
| `core/security.py` | SecurityLevel 枚举（SAFE/LOW/MEDIUM/HIGH/CRITICAL）、代码扫描、路径校验、审计日志、熔断器 | ❌ L1-L5 结构化分级 ❌ 人工确认通道 ❌ 审计哈希链 ❌ 沙箱隔离 |
| `core/workflow_orchestrator.py` | TaskDefinition 有 `sandboxed: bool` 字段、`enable_audit` 开关、安全扫描钩子 | ❌ 执行前风险评估 ❌ 审批管线 ❌ L4/L5 强制沙箱 |
| `core/multi_agent_orchestrator.py` | AgenticPlanner（刚新增）、ReAct 循环 | ❌ 风险评估集成到 ReAct 循环 |

---

## 2. Phase A：深度推理升级（ThinkingUpgradePolicy）

### 2.1 目标

让以下任务**自动升级**到 THINKING 档位，并支持**多轮自我校准**：

| 任务场景 | 当前档位 | 升级后档位 | 升级理由 |
|---|---|---|---|
| 复杂风格分析（多镜头对比） | TIER_2_MIDTIER | TIER_3_FLAGSHIP | 需要多步推理、风格特征对比 |
| 3D 坐标校准（扇位/相机） | TIER_2_MIDTIER | TIER_3_FLAGSHIP | 约束求解、边界检查 |
| 多步效果规划 | TIER_2_MIDTIER | TIER_3_FLAGSHIP | 依赖链推理 |
| 形式化验证（参数边界） | TIER_2_MIDTIER | TIER_3_FLAGSHIP | 需要证明/验证 |

### 2.2 核心设计

```
用户调用 chat_with_routing(prompt, task_type="complex_analysis")
        ↓
ThinkingUpgradePolicy.should_upgrade()
        ↓
    ┌─────────────────────────────────────┐
    │ 1. 关键词触发检测（"三维"/"校准"/"多步"） │
    │ 2. 复杂度评估（"同时考虑"/"推导出"）      │
    │ 3. 成本预算估算（max_cost_per_task）    │
    └─────────────────────────────────────┘
        ↓
    不升级 → 走原有路由（TIER_2）
    升级   → 走多轮自我校准（TIER_3）
        ↓
    Round 1: 初始回答
    Round 2: 自我校准（检查约束满足）
    Round 3: 修正输出
        ↓
    返回最终结果 + 推理轨迹（rounds[]）
```

### 2.3 新增数据结构（`core/llm_gateway.py` 尾部追加）

```python
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
    upgraded_task_type: str                # 升级后 task_type
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

### 2.4 升级触发规则

```python
UPGRADE_TRIGGERS = {
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
}

COMPLEXITY_MARKERS = {
    # 需要多步推理的句式
    "分析并对比", "同时考虑", "推导出", "证明并生成",
    "在多个约束下", "边界条件", "回归验证", "交叉验证",
}
```

### 2.5 多轮自我校准流程

```python
async def execute_with_thinking(self, prompt: str, task_type: str) -> Tuple[str, ThinkingTrace]:
    decision = self.should_upgrade(task_type, prompt)
    if not decision.should_upgrade:
        # 走原有路由
        resp = await self.chat_with_routing(prompt, task_type)
        return resp.content, ThinkingTrace(...)

    rounds = []
    current_prompt = prompt
    for r in range(decision.budget.max_rounds):
        # 1. 调用 TIER_3 模型
        resp = await self._call_tier3(current_prompt)

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

        check = await self._call_tier2(check_prompt)

        passed = "PASS" in check.content
        rounds.append(ThinkingRound(r, current_prompt, resp.content, check.content, passed, ...))

        if passed or r == decision.budget.max_rounds - 1:
            break

        # 3. 修正 prompt 进入下一轮
        current_prompt = f"""原任务：{prompt}

上一轮回答：{resp.content}

发现问题：{check.content}

请修正并重新回答："""

    return rounds[-1].response, ThinkingTrace(...)
```

### 2.6 配置项（`core/config.py` `llm` 段追加）

```python
"thinking_upgrade": {
    "enabled": True,
    "auto_upgrade_task_types": ["complex_analysis", "code_generation"],
    "max_rounds": 3,
    "max_cost_per_task_usd": 0.5,
    "downgrade_on_failure": True,        # 升级失败回落到原档位
    "self_check_enabled": True,          # 是否启用自我校准
    "confidence_threshold": 0.85,        # 校准通过阈值
}
```

---

## 3. Phase B：L1-L5 安全护栏（RiskGuard）

### 3.1 目标

让所有 Agent 操作经过**风险评估 → 沙箱隔离 → 人工审批 → 审计哈希链**四道防线，防止 Anthropic/OpenAI 式失控。

### 3.2 核心设计

```
WorkflowOrchestrator._execute_task(task_def)
        ↓
RiskAssessor.assess(task_def)
        ↓
    ┌─────────────────────────────────────┐
    │ 1. 查 DEFAULT_RISK_MAP 获取基础等级    │
    │ 2. 路径检测（触及用户素材 → 升级 L4）   │
    │ 3. 关键字检测（delete/overwrite → L4） │
    │ 4. 付费检测（pay/purchase → L5）       │
    └─────────────────────────────────────┘
        ↓
    L1/L2 → 直接执行（只记录审计）
    L3    → 沙箱执行（记录审计）
    L4    → 沙箱 + 人工审批 + 审计哈希链
    L5    → 沙箱 + 强制人工审批 + 审计哈希链 + 二次确认
```

### 3.3 新增数据结构（`core/security.py` 尾部追加）

```python
class RiskLevel(IntEnum):
    """信通院 L1-L5 分级"""
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
    allowed_paths: List[str]               # FS 白名单
    forbidden_paths: List[str]             # FS 黑名单
    max_execution_time_ms: int             # 最大执行时间
    max_memory_mb: int                     # 最大内存

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

### 3.4 任务类型 → 风险等级映射

```python
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
```

### 3.5 沙箱策略（SandboxPolicy）

```python
class SandboxPolicy:
    """L3+ 沙箱策略：进程级隔离 + FS 白名单 + 资源限制"""

    def __init__(self, workspace_root: Path):
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

    def wrap_execution(self, task_fn: Callable, task_args: Dict) -> Callable:
        """把任务函数包成沙箱执行"""
        # 1. 路径校验：所有 task_args 中的路径必须在 allowed_roots 内
        # 2. 临时目录隔离：tempfile.TemporaryDirectory 作为 working dir
        # 3. 资源限制：resource.setrlimit (Linux) / psutil (Windows)
        # 4. 执行后清理：删除临时目录
        ...
```

### 3.6 人工审批策略（ApprovalPolicy）

```python
class ApprovalPolicy:
    """L4/L5 人工审批策略"""

    def __init__(self, callback: Callable[[ApprovalRequest], Awaitable[ApprovalResult]] = None):
        self._callback = callback or self._default_cli_callback

    async def request_approval(self, request: ApprovalRequest) -> ApprovalResult:
        """阻塞等待审批"""
        # CLI 模式：打印审批请求，等待用户输入 y/n
        # Web 模式：推送到 ae-dashboard，等待用户点击
        # 超时自动拒绝
        ...

    def _default_cli_callback(self, request: ApprovalRequest) -> ApprovalResult:
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
                return ApprovalResult(request.request_id, False, "cli_user", time.time(), "用户拒绝")
            confirm2 = input("⚠️ 这是 L5 不可逆操作，请再次确认 (yes/no): ").strip().lower()
            return ApprovalResult(request.request_id, confirm2 == "yes", "cli_user", time.time(), "", confirm2 == "yes")

        confirm = input("确认执行？(y/n): ").strip().lower()
        return ApprovalResult(request.request_id, confirm == "y", "cli_user", time.time(), "")
```

### 3.7 审计哈希链（AuditChain）

```python
class AuditChain:
    """审计哈希链（防篡改，追加式）"""

    def __init__(self, log_path: Path):
        self._path = log_path
        self._prev_hash = self._load_last_hash()
        self._lock = threading.Lock()

    def append(self, entry: AuditLogEntry) -> str:
        """追加一条审计记录，返回当前哈希"""
        with self._lock:
            payload = f"{self._prev_hash}|{asdict(entry)}|{time.time()}"
            current_hash = hashlib.sha256(payload.encode()).hexdigest()

            record = {
                "entry": asdict(entry),
                "prev_hash": self._prev_hash,
                "current_hash": current_hash,
                "timestamp": time.time(),
            }

            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            self._prev_hash = current_hash
            return current_hash

    def verify_chain(self) -> Tuple[bool, List[str]]:
        """重放整个链验证完整性"""
        # 逐行读取，重新计算哈希，对比 current_hash
        # 发现任何不匹配 → 返回 False + 篡改位置
        ...
```

### 3.8 WorkflowOrchestrator 集成钩子

```python
# core/workflow_orchestrator.py 新增方法

async def _execute_task_with_guard(self, task_def: TaskDefinition, context: WorkflowContext) -> Any:
    """L1-L5 护栏包装"""

    # 1. 风险评估
    assessment = self._risk_assessor.assess(
        task_def.task_type.value if hasattr(task_def.task_type, 'value') else str(task_def.task_type),
        task_def.args
    )

    # 2. L4/L5 人工审批
    if assessment.requires_approval:
        approval_request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            task_id=task_def.task_id,
            task_type=task_def.task_type.value,
            risk_level=assessment.risk_level,
            reasons=assessment.reasons,
            args_preview=self._sanitize_args(task_def.args),
        )
        approval_result = await self._approval_policy.request_approval(approval_request)

        if not approval_result.approved:
            raise SecurityError(f"L{assessment.risk_level} 任务被审批拒绝: {approval_result.comment}")

        if assessment.requires_second_confirm and not approval_result.second_confirmed:
            raise SecurityError("L5 任务需要二次确认")

    # 3. L3+ 沙箱执行
    if assessment.requires_sandbox:
        async with self._sandbox_policy.wrap(task_def, context):
            result = await self._execute_task_inner(task_def, context)
    else:
        result = await self._execute_task_inner(task_def, context)

    # 4. L4+ 审计哈希链
    if assessment.requires_audit_chain:
        self._audit_chain.append(AuditLogEntry(
            timestamp=time.time(),
            workflow_id=context.workflow_id,
            task_id=task_def.task_id,
            task_type=task_def.task_type.value,
            security_level=f"L{assessment.risk_level}",
            action="task_executed",
            status="completed",
            input_hash=SecurityManager.hash_content(str(task_def.args)),
            output_hash=SecurityManager.hash_content(str(result)),
            duration_ms=...,
            details=f"reasons={assessment.reasons}",
        ))

    return result
```

---

## 4. Phase C：形式化规范层（FormalSpec）

### 4.1 目标

把项目中的**硬规则**提取为**可执行不变量（Invariants）**，每次 pipeline 阶段结束时自动校验。

### 4.2 不变量示例

```python
class Invariant(ABC):
    """形式化不变量基类"""
    @abstractmethod
    def check(self, context: Dict) -> Tuple[bool, str]:
        """返回 (是否通过, 错误信息)"""
        ...

class FanPositionConstraint(Invariant):
    """3D 扇子位置约束"""
    def check(self, context):
        for layer in context.get("ae_layers", []):
            if layer.get("type") == "fan_blade":
                x, y = layer["position"]
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
    def check(self, context):
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
    def check(self, context):
        render_time = context.get("ae_render_time_ms", 0)
        if render_time > 30_000:
            return False, f"单帧渲染超时: {render_time}ms (最大 30s)"
        return True, ""

# 注册到 pipeline
FORMAL_INVARIANTS: List[Invariant] = [
    FanPositionConstraint(),
    FFmpegParamBoundary(),
    AERenderTimeout(),
]
```

### 4.3 集成点

```python
# pipeline/unified_pipeline.py 每个阶段结束时调用
async def _run_stage_with_invariants(self, stage_name: str, stage_fn: Callable, context: Dict):
    result = await stage_fn(context)

    # 校验所有不变量
    for invariant in FORMAL_INVARIANTS:
        passed, error = invariant.check(context)
        if not passed:
            raise InvariantViolation(f"[{stage_name}] 不变量校验失败: {error}")

    return result
```

---

## 5. 测试矩阵

### 5.1 Phase A 测试（`tests/test_thinking_upgrade.py`）

| 用例 | 覆盖点 |
|---|---|
| `test_upgrade_trigger_keyword` | 包含"三维"/"校准"关键词时触发升级 |
| `test_upgrade_trigger_complexity` | 包含"同时考虑"/"推导出"时触发升级 |
| `test_no_upgrade_simple_task` | 简单任务不触发升级 |
| `test_already_thinking_tier` | 已在 THINKING 档位不重复升级 |
| `test_multi_round_calibration` | 多轮自我校准收敛 |
| `test_max_rounds_exceeded` | 超过 max_rounds 返回最后一轮 |
| `test_cost_budget_exceeded` | 超过预算拒绝升级 |
| `test_downgrade_on_failure` | 升级失败回落到原档位 |
| `test_thinking_trace_completeness` | ThinkingTrace 包含所有 rounds |
| `test_config_loading` | 从 config.py 加载配置 |

### 5.2 Phase B 测试（`tests/test_l1_l5_guard.py`）

| 用例 | 覆盖点 |
|---|---|
| `test_l1_readonly_direct_execute` | L1 任务直接执行 |
| `test_l2_generate_direct_execute` | L2 任务直接执行 |
| `test_l3_sandbox_execute` | L3 任务沙箱执行 |
| `test_l4_approval_required` | L4 任务需要审批 |
| `test_l4_approval_rejected` | L4 审批拒绝抛异常 |
| `test_l5_second_confirm_required` | L5 需要二次确认 |
| `test_user_material_path_upgrade` | 触及用户素材升级到 L4 |
| `test_delete_keyword_upgrade` | delete 关键字升级到 L4 |
| `test_pay_keyword_upgrade` | pay 关键字升级到 L5 |
| `test_sandbox_path_whitelist` | 沙箱路径白名单校验 |
| `test_sandbox_path_blacklist` | 沙箱路径黑名单拒绝 |
| `test_audit_chain_append` | 审计链追加 |
| `test_audit_chain_verify` | 审计链完整性验证 |
| `test_audit_chain_tamper_detect` | 篡改检测 |
| `test_workflow_orchestrator_integration` | WorkflowOrchestrator 集成 |

### 5.3 Phase C 测试（`tests/test_formal_spec.py`）

| 用例 | 覆盖点 |
|---|---|
| `test_fan_position_constraint_pass` | 扇位约束通过 |
| `test_fan_position_constraint_fail` | 扇位约束失败 |
| `test_ffmpeg_param_boundary_pass` | FFmpeg 参数通过 |
| `test_ffmpeg_param_boundary_fail` | FFmpeg 参数失败 |
| `test_ae_render_timeout_pass` | 渲染超时通过 |
| `test_ae_render_timeout_fail` | 渲染超时失败 |
| `test_multiple_invariants` | 多不变量组合 |
| `test_invariant_violation_raise` | 违规时抛异常 |

---

## 6. 实施路线图

### 6.1 第 1 周：Phase B（L1-L5 安全护栏）— 最高优先级

**驱动因素：** Anthropic/OpenAI 失控事件，安全风险最高

| 任务 | 工作量 | 交付物 |
|---|---|---|
| B1: RiskLevel 枚举 + RiskAssessment 结构 | 100 行 | `core/security.py` 追加 |
| B2: RiskAssessor 类 | 200 行 | `core/security.py` 追加 |
| B3: SandboxPolicy 类 | 250 行 | `core/security.py` 追加 |
| B4: ApprovalPolicy 类 | 200 行 | `core/security.py` 追加 |
| B5: AuditChain 类 | 150 行 | `core/security.py` 追加 |
| B6: WorkflowOrchestrator 集成钩子 | 150 行修改 | `core/workflow_orchestrator.py` 修改 |
| B7: 测试 15 用例 | 400 行 | `tests/test_l1_l5_guard.py` 新增 |

**总计：** ~1450 行新增 + 150 行修改

### 6.2 第 2 周：Phase A（深度推理升级）

| 任务 | 工作量 | 交付物 |
|---|---|---|
| A1: ThinkingBudget/Decision/Round/Trace 数据结构 | 100 行 | `core/llm_gateway.py` 追加 |
| A2: ThinkingUpgradePolicy 类 | 300 行 | `core/llm_gateway.py` 追加 |
| A3: 配置项追加 | 50 行 | `core/config.py` 修改 |
| A4: 测试 10 用例 | 300 行 | `tests/test_thinking_upgrade.py` 新增 |

**总计：** ~750 行新增 + 50 行修改

### 6.3 第 3 周：Phase C（形式化规范层）

| 任务 | 工作量 | 交付物 |
|---|---|---|
| C1: Invariant 基类 + 3 个不变量 | 200 行 | `core/formal_spec.py` 新增 |
| C2: pipeline 集成钩子 | 100 行 | `pipeline/unified_pipeline.py` 修改 |
| C3: 测试 8 用例 | 250 行 | `tests/test_formal_spec.py` 新增 |

**总计：** ~550 行新增 + 100 行修改

### 6.4 第 4 周：集成验证 + 文档

| 任务 | 工作量 | 交付物 |
|---|---|---|
| 集成测试（全 pipeline 跑通） | 200 行 | `tests/test_integration_guard.py` 新增 |
| 性能基准测试 | 100 行 | `tests/benchmark_guard.py` 新增 |
| 用户文档（CLI 审批指南） | - | `docs/user-guide-approval.md` 新增 |
| API 文档（RiskGuard 接口） | - | `docs/api-riskguard.md` 新增 |

---

## 7. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|---|---|---|
| L4/L5 审批打断自动化流程 | 用户体验下降 | 提供 `--auto-approve-l3` 模式；L4 默认审批，L3 默认自动 |
| 沙箱性能开销 | 渲染任务变慢 | 沙箱只用于 L3+，L1/L2 直接执行；沙箱复用临时目录 |
| 审计哈希链存储膨胀 | 磁盘占用增加 | 审计日志按天轮转，保留 30 天；提供压缩归档 |
| 深度推理成本超预算 | API 费用增加 | 硬预算 `max_cost_per_task_usd=0.5`；超过自动降级 |
| 多轮校准不收敛 | 推理时间变长 | `max_rounds=3` 硬限制；超时自动返回最后一轮 |
| 不变量误报 | 正常任务被拦截 | 不变量可配置开关；提供 `--skip-invariants` 调试模式 |

---

## 8. 验收标准

### 8.1 Phase A 验收

- [ ] 包含"三维坐标校准"的 prompt 自动升级到 TIER_3
- [ ] 多轮自我校准最多 3 轮，超过返回最后一轮
- [ ] 单任务成本不超过 `max_cost_per_task_usd`
- [ ] ThinkingTrace 包含完整 rounds 记录
- [ ] 升级失败自动回落到原档位
- [ ] 10 个测试用例全部通过

### 8.2 Phase B 验收

- [ ] L1/L2 任务直接执行，无审批
- [ ] L3 任务沙箱执行，路径白名单生效
- [ ] L4 任务强制审批，拒绝后抛异常
- [ ] L5 任务二次确认，未确认抛异常
- [ ] 审计哈希链追加 + 验证通过
- [ ] 篡改审计日志被检测
- [ ] 15 个测试用例全部通过

### 8.3 Phase C 验收

- [ ] 扇位约束越界时抛 InvariantViolation
- [ ] FFmpeg 参数越界时抛 InvariantViolation
- [ ] AE 渲染超时时抛 InvariantViolation
- [ ] 8 个测试用例全部通过

### 8.4 集成验收

- [ ] 完整 pipeline（perceive → plan → execute → render）跑通
- [ ] L4 任务（ae_render）触发审批
- [ ] 审计日志包含所有任务记录
- [ ] 性能开销 < 10%（对比无护栏版本）

---

## 9. 后续扩展方向

| 方向 | 描述 | 优先级 |
|---|---|---|
| Web 审批界面 | 在 `ae-dashboard/` 新增审批面板，替代 CLI 审批 | 高 |
| 审批策略配置化 | 用户可自定义哪些任务需要审批 | 中 |
| 审计日志可视化 | 在 `ae-dashboard/` 新增审计链查看器 | 中 |
| Lean 4 离线验证 | 把不变量翻译成 `.lean` 文件，离线证明 | 低 |
| 沙箱容器化 | 用 Docker/WSL 替代进程级沙箱 | 低 |
| 多租户隔离 | 不同用户/项目独立沙箱 + 审计链 | 低 |

---

## 10. 参考资料

1. OpenAI Astra: "Formalizing 249 Pages of Lean 4 Proofs" (2026-07)
2. Anthropic Agent Safety Incident Report (2026-07-15)
3. OpenAI Agent Safety Incident Report (2026-07-15)
4. 中国信通院《智能体安全分级指南》(2026-06)
5. OWASP Top 10 for LLM Applications (2026)
6. NIST Cybersecurity Framework 2.0 (2024)
7. 本项目 `core/security.py` v1.0
8. 本项目 `core/llm_gateway.py` v1.0
9. 本项目 `core/workflow_orchestrator.py` v1.0

---

## 附录 A：关键文件变更清单

| 文件 | 变更类型 | 变更内容 |
|---|---|---|
| `core/llm_gateway.py` | 追加 | ThinkingUpgradePolicy 类（~400 行） |
| `core/config.py` | 修改 | `llm` 段追加 `thinking_upgrade` 配置（~20 行） |
| `core/security.py` | 追加 | RiskLevel/RiskAssessor/SandboxPolicy/ApprovalPolicy/AuditChain（~900 行） |
| `core/workflow_orchestrator.py` | 修改 | `_execute_task_with_guard` 钩子（~150 行） |
| `core/formal_spec.py` | 新增 | Invariant 基类 + 3 个不变量（~200 行） |
| `pipeline/unified_pipeline.py` | 修改 | `_run_stage_with_invariants` 钩子（~100 行） |
| `tests/test_thinking_upgrade.py` | 新增 | 10 个测试用例（~300 行） |
| `tests/test_l1_l5_guard.py` | 新增 | 15 个测试用例（~400 行） |
| `tests/test_formal_spec.py` | 新增 | 8 个测试用例（~250 行） |

**总计：** ~2750 行新增 + ~270 行修改

---

## 附录 B：CLI 审批示例

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

## 附录 C：审计哈希链示例

```json
{"entry": {"timestamp": 1785685200.123, "workflow_id": "wf_001", "task_id": "ae_render_final", "task_type": "ae_render", "security_level": "L4", "action": "task_executed", "status": "completed", "input_hash": "a1b2c3...", "output_hash": "d4e5f6...", "duration_ms": 45700, "details": "reasons=['task_type=ae_render -> L4', '触及用户素材']"}, "prev_hash": "0000...", "current_hash": "a3f29c1d...", "timestamp": 1785685200.456}
{"entry": {"timestamp": 1785685245.789, "workflow_id": "wf_001", "task_id": "ffmpeg_export", "task_type": "ffmpeg_export", "security_level": "L4", "action": "task_executed", "status": "completed", "input_hash": "g7h8i9...", "output_hash": "j0k1l2...", "duration_ms": 12300, "details": "reasons=['task_type=ffmpeg_export -> L4']"}, "prev_hash": "a3f29c1d...", "current_hash": "b4e7a2f8...", "timestamp": 1785685246.012}
```

验证：逐行重新计算哈希，对比 `current_hash`，任何不匹配 → 篡改检测。

---

**文档结束**
