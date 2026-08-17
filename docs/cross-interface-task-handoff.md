# AE-Knowledge-Vault
# 跨界面任务接续、开发同步与实时进展交接文档

> 文档用途：将当前对话已经完成的任务、代码变更、阶段状态、测试证据、异步执行链、协程关系、已知风险和下一步开发协议完整交接给另一个界面或另一个 AI 执行体。
>
> 使用方式：新界面打开本文件后，应先阅读“接续操作清单”，再按“恢复检查命令”核对工作区，最后按照“下一步执行顺序”继续开发。不得仅凭本文件中的测试数字推断当前工作区没有其他改动，必须以新的 `git status` 和实际文件内容为准。

---

## 0. 接续摘要

### 0.1 当前项目

- 项目：`AE-Knowledge-Vault`
- 工作区：`c:/Users/Administrator/Desktop/AE-Knowledge-Vault`
- 操作系统：Windows
- Shell：PowerShell
- 当前分支：`feat/project-consolidation-v1`
- HEAD 提交：`bf99595 fix: 转场映射KB提取修复+TS测试修正+dashboard编译+search() bug`
- HEAD 相对上游状态：开始本轮工作时分支领先 `origin/feat/project-consolidation-v1` 8 个提交。
- 本文档生成时没有执行提交、推送、重置或清理其他工作区改动。

### 0.2 本轮实际完成内容

本轮围绕 `docs/agent-safety-and-deep-reasoning-design-v2.md` 完成了三个阶段：

1. **Phase A：深度推理升级**
   - 在 `core/llm_gateway.py` 追加深度推理预算、升级决策、多轮记录、轨迹和策略。
   - 在 `core/config.py` 追加 `thinking_upgrade` 配置。
   - 新增 `tests/test_thinking_upgrade.py`。

2. **Phase B：L1-L5 安全护栏**
   - 在 `core/security.py` 追加风险等级、安全异常、风险评估、沙箱、审批和审计链。
   - 在 `core/workflow_orchestrator.py` 追加安全执行包装器，并通过类外入口绑定接入原有执行路径。
   - 新增 `tests/test_l1_l5_guard.py`。
   - 修复审计哈希使用非稳定字典字符串导致的链校验问题。

3. **Phase C：形式化规范层**
   - 新增 `core/formal_spec.py`。
   - 在 `pipeline/unified_pipeline.py` 追加阶段完成后的不变量校验入口绑定。
   - 新增 `tests/test_formal_spec.py`。

### 0.3 当前阶段结论

- Phase A：已完成。
- Phase B：已完成，优先级最高的安全护栏已接入。
- Phase C：已完成，形式化不变量层已接入。
- 指南没有定义 Phase D 及之后的编码阶段；第 7 章“未来 6 个月开发集成方向”属于路线图，不是当前已经完成的代码任务。
- 当前没有新的编码 Phase 在进行中；下一界面应先做完整回归和代码审查，再决定是否进入路线图任务。

---

## 1. 原始任务和执行约束

原始任务来自：`docs/agent-safety-and-deep-reasoning-design-v2.md`。

指南规定的核心约束如下：

1. 编码前先完整读取指定基线文件和对应结构。
2. 新代码采用追加式扩展。
3. 不主动重写已有类中的已有方法。
4. 每完成一个 Phase，运行该 Phase 对应 pytest。
5. 测试使用 mock，不真实调用 LLM、AE 或渲染环境。
6. 不确定时先确认，不凭空扩展文档语义。
7. 需要保持未启用新功能时的兼容路径。

本轮的执行策略：

- 新增类、数据结构和方法均追加在原文件末尾或新增文件中。
- 对已有执行入口采用“保存旧实现 + 绑定新包装器”的方式接入。
- 没有执行 `git commit`、`git push`、`git reset`、`git restore` 或删除用户文件。
- 由于工作区原本有大量与本轮无关的未提交变更，任何后续界面都必须避免对全仓库执行自动格式化、全量重写或批量清理。

---

## 2. 当前工作区变更边界

### 2.1 本轮已知相关文件

以下文件是本轮明确涉及的文件：

| 状态 | 文件 | 用途 |
|---|---|---|
| 修改 | `core/llm_gateway.py` | Phase A 策略和深度推理轨迹追加 |
| 修改 | `core/security.py` | Phase B L1-L5 组件追加 |
| 修改 | `core/workflow_orchestrator.py` | Phase B 执行入口和审批/沙箱/审计接入 |
| 修改 | `core/config.py` | Phase A `thinking_upgrade` 配置 |
| 修改 | `pipeline/unified_pipeline.py` | Phase C 阶段后不变量校验接入 |
| 新增 | `core/formal_spec.py` | Phase C 形式化不变量实现 |
| 新增 | `tests/test_thinking_upgrade.py` | Phase A 测试 |
| 新增 | `tests/test_l1_l5_guard.py` | Phase B 测试 |
| 新增 | `tests/test_formal_spec.py` | Phase C 测试 |
| 新增/已存在 | `docs/agent-safety-and-deep-reasoning-design-v2.md` | 实施指南，本轮以其为规范来源 |

本轮相关文件在交接时的 `git status --short` 结果为：

```text
 M core/config.py
 M core/llm_gateway.py
 M core/security.py
 M core/workflow_orchestrator.py
 M pipeline/unified_pipeline.py
?? core/formal_spec.py
?? docs/agent-safety-and-deep-reasoning-design-v2.md
?? tests/test_formal_spec.py
?? tests/test_l1_l5_guard.py
?? tests/test_thinking_upgrade.py
```

### 2.2 重要：其他工作区变更

当前工作区不只有上述 10 个文件发生变化。此前 `git status` 还显示了大量其他模块、脚本、配置、测试、桥接器和临时文件的修改/新增/删除，包括但不限于：

- `.ae-mcp-bridge/`
- `.premiere-mcp-bridge/`
- `ae/`
- `ae-dashboard/`
- `ai/`
- `bridges/`
- `compiler/`
- `config/`
- `core/` 中除本轮文件外的其他模块
- `scripts/`
- `tests/` 中大量既有新增测试
- `vrs/`
- 若干根目录脚本、缓存和验证文件

这些变化不能在本交接文档中归因于本轮，也不能被自动删除。新界面继续开发时必须：

1. 先执行 `git status --short`。
2. 只检查自己要改的文件。
3. 不使用 `git clean -fd`。
4. 不使用 `git restore .`。
5. 不将所有工作区变化混入本轮提交。
6. 如需提交，先按文件精确选择，并由用户明确要求后再提交。

---

## 3. 已读取的基线和规范

本轮已完整读取或核对以下文件/结构：

- `docs/agent-safety-and-deep-reasoning-design-v2.md`
- `core/llm_gateway.py`
- `core/security.py`
- `core/workflow_orchestrator.py`
- `core/config.py`
- `pipeline/unified_pipeline.py`
- `tests/test_security.py`
- `tests/test_security_fixes.py`
- `tests/test_workflow_orchestrator.py`

指南明确的原有核心结构：

- `core/llm_gateway.py`
  - `TaskType`
  - `ModelTier`
  - `TASK_TIER_MAP`
  - `LLMGateway.chat_with_routing()`
- `core/security.py`
  - `SecurityManager`
  - 原有安全扫描、路径校验、审计和熔断器逻辑
- `core/workflow_orchestrator.py`
  - `TaskDefinition`
  - `TaskInstance`
  - `WorkflowOrchestrator.run()`
  - `_execute_workflow()`
  - `_run_task()`
  - `_execute_task_func()`
- `pipeline/unified_pipeline.py`
  - `StageResult`
  - `run_all()`
  - `run_stage()`
  - `_run_stage()`

---

## 4. Phase A：深度推理升级

### 4.1 文件和代码位置

文件：`core/llm_gateway.py`

追加区起始位置约为第 2863 行，实际位置应以搜索结果为准：

```text
# Phase A: 深度推理升级（ThinkingUpgradePolicy）
```

追加的主要类型：

- `ThinkingBudget`
- `ThinkingUpgradeDecision`
- `ThinkingRound`
- `ThinkingTrace`
- `ThinkingUpgradePolicy`

### 4.2 `ThinkingBudget`

默认值：

- `max_rounds = 3`
- `max_tokens_per_round = 8000`
- `timeout_seconds = 300`
- `max_cost_usd = 0.5`

用途：限制多轮深度推理的轮数、单轮 token、超时和估算成本。

### 4.3 升级判断

入口：

```python
ThinkingUpgradePolicy.should_upgrade(
    task_type,
    prompt,
    context=None,
)
```

当前行为：

1. 如果任务已经属于 `ModelTier.TIER_3_FLAGSHIP_REASONING`，返回不升级，原因是 `already_tier3`。
2. 如果 prompt 命中复杂推理触发词，则候选升级。
3. 如果命中至少两个复杂度标记，也候选升级。
4. 估算成本超过预算时不升级，原因包含 `cost_exceeded`。
5. 其他普通任务不升级，原因是 `no_trigger`。
6. 升级后的任务类型标记为 `deep_reasoning`。

当前触发词包括但不限于：

- 三维、3d、坐标、校准、空间
- 形式化、formal、verify、验证、证明、prove、Lean
- 多步、step-by-step、reasoning chain、推理链
- 约束、constraint、boundary、边界、求解
- 对比分析、多镜头、多场景、同时考虑、综合评估

当前复杂度标记包括：

- 分析并对比
- 同时考虑
- 推导出
- 证明并生成
- 在多个约束下
- 边界条件
- 回归验证
- 交叉验证

### 4.4 多轮执行和协程关系

入口：

```python
await ThinkingUpgradePolicy.execute_with_thinking(
    prompt,
    original_task_type,
    context=None,
)
```

执行链：

1. 调用 `should_upgrade()`。
2. 从注入的 `LLMGateway` 获取网关；若没有注入，则创建 `LLMGateway()`。
3. 不升级时调用一次：
   - `await gateway.chat_with_routing(prompt, original_task_type)`
4. 升级时最多循环 `budget.max_rounds` 次。
5. 每一轮先调用旗舰推理任务：
   - `await gateway.chat_with_routing(current_prompt, TaskType.QUALITY_REVIEW, ...)`
6. 再调用自检任务：
   - `await gateway.chat_with_routing(check_prompt, TaskType.GENERAL, ...)`
7. 自检文本中包含 `PASS` 时结束。
8. 自检失败且未达到最大轮数时，构造带有“上一轮回答”和“发现问题”的修订 prompt，进入下一轮。
9. 最终返回：
   - `final_answer`
   - `ThinkingTrace`

协程说明：

- `execute_with_thinking()` 是异步协程。
- 同一轮的回答调用和自检调用是串行的，后者依赖前者输出。
- 多轮也是串行的，后一轮依赖上一轮自检结果。
- 当前没有在 Phase A 内使用 `asyncio.gather()` 并行推理，因为推理链具有前后依赖。
- 真实网关调用仍由 `LLMGateway.chat_with_routing()` 管理；测试使用 `FakeGateway`，不产生真实网络调用。

### 4.5 Phase A 测试

文件：`tests/test_thinking_upgrade.py`

覆盖内容：

1. 默认预算。
2. 三维/坐标校准触发升级。
3. 形式化验证触发升级。
4. 多个复杂度标记触发升级。
5. 普通 prompt 不升级。
6. 已经是 TIER3 时不重复升级。
7. 成本估算在预算内。
8. 自检通过时一轮结束。
9. 自检失败后重试并最终通过。
10. 预算轮数和成本上限。

---

## 5. Phase B：L1-L5 安全护栏

### 5.1 文件和类型

文件：`core/security.py`

追加区起始位置约为第 456 行：

```text
# Phase B: L1-L5 安全护栏（RiskGuard）
```

新增类型：

- `SecurityError`
- `RiskLevel`
- `RiskAssessment`
- `ApprovalRequest`
- `ApprovalResult`
- `RiskAssessor`
- `SandboxPolicy`
- `ApprovalPolicy`
- `AuditChain`

### 5.2 风险等级

`RiskLevel`：

- `L1_READONLY = 1`
- `L2_GENERATE = 2`
- `L3_OVERWRITE_SAFE = 3`
- `L4_DESTRUCTIVE = 4`
- `L5_EXTERNAL = 5`

风险映射重点：

- 感知、分类、理解、特征提取：L1
- 参数映射、AE 编译、JSX 生成、缓存写入：L2
- AE 执行、转码、调色、抠像：L3
- AE 渲染、导出、删除、覆盖：L4
- 外部 API、云渲染提交、付费购买：L5

### 5.3 `RiskAssessor`

入口：

```python
assessment = RiskAssessor(workspace_root).assess(task_type, task_args)
```

行为：

1. 先通过任务类型获取默认风险级别。
2. 默认未知任务为 L2。
3. 如果参数触及用户素材路径，例如：
   - `data/user_materials/`
   - `data/input/`
   - `output/final/`
   则至少提升至 L4。
4. 如果参数文本包含 `delete`、`remove`、`overwrite`、`truncate`，则至少提升至 L4。
5. 如果参数文本包含 `pay`、`purchase`、`subscribe`，则提升至 L5。
6. L3 及以上启用沙箱。
7. L4 及以上需要审批和审计链。
8. L5 需要二次确认。

### 5.4 `SandboxPolicy`

允许根目录：

- `<workspace>/data/sandbox`
- `<workspace>/output/temp`
- `<workspace>/data/cache`

禁止：

- 白名单外路径。
- `*.aep` 文件。
- `.env` 文件。
- `output/final/` 路径。

入口：

```python
await SandboxPolicy(workspace_root).wrap_execution(
    task_fn,
    task_args,
    assessment,
)
```

当前实现会：

1. 校验风险评估中提取的路径。
2. 违规时抛出 `SecurityError`。
3. 进入 `TemporaryDirectory` 临时目录上下文。
4. 执行任务函数。
5. 兼容同步返回值和异步返回值。

注意：当前实现是路径白名单和临时目录级别的沙箱封装，不是操作系统级容器隔离。后续若要满足真正的进程级资源限制，需要单独设计和测试，不能把当前实现描述成完整容器沙箱。

### 5.5 `ApprovalPolicy`

入口：

```python
result = await ApprovalPolicy(callback).request_approval(request)
```

审批请求包含：

- `request_id`
- `task_id`
- `task_type`
- `risk_level`
- `reasons`
- 脱敏后的参数预览
- 请求时间
- 超时秒数

默认回调：

- 未配置人工审批时返回拒绝。
- 拒绝原因是“未配置审批回调”。
- 因此生产接入前，L4/L5 任务会默认拒绝，不应被误认为已经具备真实人工交互界面。

### 5.6 `AuditChain`

文件格式：JSON Lines。

每条记录包括：

- `entry`
- `prev_hash`
- `current_hash`
- `timestamp`

哈希链规则：

```text
SHA256(prev_hash + canonical_json(entry) + timestamp)
```

当前使用 `json.dumps(..., sort_keys=True, separators=(",", ":"))` 生成稳定 entry 表示，避免写入后字典顺序变化造成误报。

入口：

```python
chain.append(audit_entry)
valid, violations = chain.verify_chain()
```

### 5.7 工作流执行接入

文件：`core/workflow_orchestrator.py`

原有执行链：

```text
WorkflowOrchestrator.run()
  -> _execute_workflow()
  -> asyncio.gather(*tasks_to_run, return_exceptions=True)
  -> _run_task(task_id)
  -> asyncio.wait_for(..., timeout=...)
  -> _execute_task_func(task_def, instance)
```

Phase B 追加后的接入：

```text
_run_task()
  -> _execute_task_func()
  -> 类外绑定后的 _execute_task_with_guard()
       -> RiskAssessor.assess()
       -> L4/L5: ApprovalPolicy.request_approval()
       -> L3+: SandboxPolicy.wrap_execution()
       -> 原始执行实现或 _execute_guarded_task_inner()
       -> L4+: AuditChain.append()
```

关键绑定位于 `core/workflow_orchestrator.py` 约第 1443 行：

```python
_WorkflowOrchestrator_legacy_execute_task_func = WorkflowOrchestrator._execute_task_func
WorkflowOrchestrator._execute_task_legacy = _WorkflowOrchestrator_legacy_execute_task_func
WorkflowOrchestrator._execute_task_func = WorkflowOrchestrator._execute_task_with_guard
```

这意味着：

- 绑定发生在模块加载完成后。
- 原始方法保存为 `_execute_task_legacy`。
- `_execute_task_with_guard()` 中的降级路径调用 `_execute_task_legacy()`，避免递归。
- `enable_security=False` 或 RiskGuard 初始化失败时，走原有执行逻辑。
- 工作流本身通过 `asyncio.gather()` 并行运行满足依赖条件的任务。
- 单任务通过 `asyncio.wait_for()` 承受原有超时配置。
- 同步任务函数由原有逻辑使用 `asyncio.to_thread()` 执行。
- Phase B 的沙箱内部执行也保留同步/异步两种函数形态。

### 5.8 Phase B 测试

文件：`tests/test_l1_l5_guard.py`

覆盖：

1. L1 直接执行。
2. L2 直接执行。
3. L3 沙箱执行。
4. L4 审批成功。
5. L4 审批拒绝并抛 `SecurityError`。
6. L5 缺少二次确认并抛 `SecurityError`。
7. 用户素材路径升级到 L4。
8. 删除关键字升级到 L4。
9. 付费关键字升级到 L5。
10. 沙箱白名单路径通过。
11. 沙箱黑名单路径拒绝。
12. 审计链追加。
13. 审计链校验。
14. 审计链篡改检测。
15. 工作流编排器集成。

---

## 6. Phase C：形式化规范层

### 6.1 文件和类型

文件：`core/formal_spec.py`

新增：

- `InvariantViolation`
- `Invariant`
- `FanPositionConstraint`
- `FFmpegParamBoundary`
- `AERenderTimeout`
- `FORMAL_INVARIANTS`
- `check_invariants()`

### 6.2 不变量规则

#### `FanPositionConstraint`

只检查 `context["ae_layers"]` 中 `type == "fan_blade"` 的图层：

- X：`-960 <= x <= 960`
- Y：`-540 <= y <= 540`
- rotation：`0 <= rotation < 360`

#### `FFmpegParamBoundary`

读取 `context["ffmpeg_params"]`：

- bitrate 最大 `50_000_000`
- framerate 范围 `[23.976, 120]`

#### `AERenderTimeout`

读取 `context["ae_render_time_ms"]`：

- 最大 `30_000ms`

#### 统一校验

```python
check_invariants(context, skip=False)
```

- 所有不变量通过：返回 `None`。
- 任一失败：抛出 `InvariantViolation`。
- `skip=True`：调试模式跳过全部不变量。

### 6.3 管线接入

文件：`pipeline/unified_pipeline.py`

原有链：

```text
run_all() / run_stage()
  -> _run_stage(stage_name)
```

追加绑定约第 4544 行：

```python
_UnifiedPipeline_legacy_run_stage = UnifiedPipeline._run_stage
UnifiedPipeline._run_stage = _run_stage_with_invariants
```

新包装器执行：

1. 调用保存的原始 `_run_stage`。
2. 获得 `StageResult`。
3. 创建形式化上下文：
   - `stage`
   - `result.data` 中的字段
   - `stage_result`
4. 调用 `check_invariants()`。
5. 如果配置含 `debug_skip_invariants=True`，跳过校验。
6. `core.formal_spec` 导入失败时仅记录 debug 日志并保持原流程。

注意：当前钩子接入的是 `UnifiedPipeline` 的实例方法；其他独立的 `ae/e2e_pipeline.py` 不是本轮 Phase C 的接入对象，后续若要统一，必须另开任务分析其 `PipelineContext` 和阶段生命周期。

### 6.4 Phase C 测试

文件：`tests/test_formal_spec.py`

覆盖：

- 扇叶位置约束通过。
- 扇叶位置违规。
- FFmpeg 参数通过。
- FFmpeg 参数违规。
- AE 渲染时间通过。
- AE 渲染时间违规。
- 多不变量组合通过。
- 违规异常类型和错误名称。
- `skip=True`。
- 三个不变量名称。

---

## 7. 测试和验证证据

### 7.1 测试解释器

系统默认命令 `python`、`py`、`pytest` 不可直接依赖；本轮使用仓库已有虚拟环境：

```powershell
& 'C:\Users\Administrator\Desktop\AE-Knowledge-Vault\puppet-automation\venv\Scripts\python.exe' -m pytest ...
```

新界面必须优先检查该解释器是否仍可用。

### 7.2 本轮新增测试结果

已执行并通过：

```text
Phase A: 10 passed
Phase B: 15 passed
Phase C: 10 passed
合计：35 passed
```

推荐重跑命令：

```powershell
& '.\puppet-automation\venv\Scripts\python.exe' -m pytest `
  '.\tests\test_thinking_upgrade.py' `
  '.\tests\test_l1_l5_guard.py' `
  '.\tests\test_formal_spec.py' -q
```

### 7.3 直接相关回归结果

已执行并通过：

- LLM 网关相关回归：`103 passed`
- 配置及管线配置回归：`181 passed`
- 工作流编排器回归：`55 passed`
- 核心修改文件 `py_compile` 通过
- 本轮涉及文件 linter 无诊断

推荐回归命令：

```powershell
& '.\puppet-automation\venv\Scripts\python.exe' -m pytest `
  '.\tests\test_llm_gateway.py' `
  '.\tests\test_llm_gateway_regression_gaps.py' `
  '.\tests\test_core_config.py' `
  '.\tests\test_config_schema.py' `
  '.\tests\test_pipeline_config_validation.py' `
  '.\tests\test_workflow_orchestrator.py' -q
```

### 7.4 尚未执行的验证

以下验证不属于本轮已完成证据，后续不能直接声称已经通过：

- 真实 LLM Provider 调用。
- 真实 AE/Adobe 应用调用。
- 真实 FFmpeg/DaVinci/渲染端到端调用。
- 真实人工审批 UI 或审批服务。
- 操作系统级沙箱、进程隔离和资源配额。
- 多界面实时消息传输。
- 另一界面读取本交接文档后的自动同步。

---

## 8. 跨界面接续操作协议

### 8.1 新界面第一轮必须做什么

新界面打开本文件后，不要立即改代码。按以下顺序执行：

#### 步骤 1：声明已恢复上下文

新界面应先确认它理解以下事实：

- 当前工作区路径。
- 当前分支。
- 本轮已完成 Phase A/B/C。
- 本轮相关的 10 个文件。
- 工作区存在大量其他未归因变更。
- 不得执行全局清理或全局格式化。

#### 步骤 2：执行状态检查

```powershell
Set-Location 'C:\Users\Administrator\Desktop\AE-Knowledge-Vault'
git branch --show-current
git status --short
```

#### 步骤 3：检查本轮文件

```powershell
git status --short -- `
  core/llm_gateway.py `
  core/security.py `
  core/workflow_orchestrator.py `
  core/config.py `
  core/formal_spec.py `
  pipeline/unified_pipeline.py `
  tests/test_thinking_upgrade.py `
  tests/test_l1_l5_guard.py `
  tests/test_formal_spec.py
```

#### 步骤 4：读取关键追加区

```powershell
Select-String -Path '.\core\llm_gateway.py' -Pattern 'Phase A|ThinkingUpgradePolicy'
Select-String -Path '.\core\security.py' -Pattern 'Phase B|RiskAssessor|AuditChain'
Select-String -Path '.\core\workflow_orchestrator.py' -Pattern 'execute_task_with_guard|legacy_execute_task_func'
Select-String -Path '.\core\formal_spec.py' -Pattern 'class Invariant|check_invariants'
Select-String -Path '.\pipeline\unified_pipeline.py' -Pattern 'run_stage_with_invariants|legacy_run_stage'
```

#### 步骤 5：重跑最小测试

```powershell
& '.\puppet-automation\venv\Scripts\python.exe' -m pytest `
  '.\tests\test_thinking_upgrade.py' `
  '.\tests\test_l1_l5_guard.py' `
  '.\tests\test_formal_spec.py' -q
```

只有最小测试通过后，才开始新功能开发。

### 8.2 新界面回复格式

为了让任务进展可同步，新界面每完成一个有意义动作，应按以下结构更新：

```markdown
## 进度更新
- 时间：YYYY-MM-DD HH:mm（本地时间）
- 当前阶段：Phase X / Review / Integration
- 当前任务：简短任务名
- 状态：未开始 / 进行中 / 已完成 / 阻塞

## 本次动作
- 读取了哪些文件
- 修改了哪些文件
- 新增或删除了什么
- 是否触及已有方法体

## 验证
- 执行命令
- 结果：passed / failed / blocked
- 测试数量
- 失败用例和完整原因

## 风险和待决事项
- 已知风险
- 是否需要用户决定

## 下一步
- 下一项具体动作
- 预计会触及的文件
```

### 8.3 实时同步状态文件协议

如果需要多个界面实时查看进展，应使用一个专门状态文件，不要让多个界面同时改同一个代码文件来传递状态。建议文件：

```text
.codebuddy/task-sync/ae-knowledge-vault-status.json
```

该文件当前尚未创建；只有用户明确要求启用文件型实时同步时，下一界面才创建它。

建议结构：

```json
{
  "schema_version": 1,
  "project": "AE-Knowledge-Vault",
  "workspace": "c:/Users/Administrator/Desktop/AE-Knowledge-Vault",
  "branch": "feat/project-consolidation-v1",
  "handoff_document": "docs/cross-interface-task-handoff.md",
  "updated_at": "2026-08-03T00:00:00+08:00",
  "active_phase": "completed",
  "active_task": null,
  "status": "ready_for_continuation",
  "completed_phases": ["A", "B", "C"],
  "tests": {
    "new_phase_tests": {"passed": 35, "failed": 0},
    "llm_regression": {"passed": 103, "failed": 0},
    "config_pipeline_regression": {"passed": 181, "failed": 0},
    "workflow_regression": {"passed": 55, "failed": 0}
  },
  "changed_files": [
    "core/llm_gateway.py",
    "core/security.py",
    "core/workflow_orchestrator.py",
    "core/config.py",
    "core/formal_spec.py",
    "pipeline/unified_pipeline.py",
    "tests/test_thinking_upgrade.py",
    "tests/test_l1_l5_guard.py",
    "tests/test_formal_spec.py"
  ],
  "blocking_issues": [],
  "next_action": "先重跑最小三阶段测试，再决定下一项路线图任务",
  "last_action": "完成 Phase A/B/C 并完成直接相关回归"
}
```

写入规则：

1. 一个界面只负责更新 `active_task`、`status`、`last_action` 和 `next_action`。
2. 不覆盖其他界面正在进行的任务字段。
3. 更新前先读取旧 JSON。
4. 写入前保留 `updated_at` 和 `history`。
5. 每次更新追加一条历史事件：

```json
{
  "time": "2026-08-03T00:00:00+08:00",
  "interface": "界面名称或会话标识",
  "action": "动作摘要",
  "status": "状态",
  "files": [],
  "tests": [],
  "blockers": []
}
```

### 8.4 并发编辑规则

多个界面同时开发时必须遵守：

- 同一文件同一时刻只能有一个界面负责写入。
- 另一个界面只能读取、审查或运行测试。
- 若两个任务需要修改同一文件，先拆分为不重叠追加区，或先完成一个任务再做另一个。
- 不用“最后写入者覆盖”解决冲突。
- 每次修改前必须重新读取目标文件；不得依赖旧上下文中的代码片段。
- 编辑失败后必须重新读取文件，再尝试下一次编辑。
- 任何绑定入口、类外 monkey patch、全局变量和配置默认值都属于高冲突区域，必须先通知其他界面。

### 8.5 实时进度的最小事件模型

每个任务事件至少包含：

- `event_id`
- `task_id`
- `parent_task_id`
- `phase`
- `status`
- `started_at`
- `updated_at`
- `owner`
- `files`
- `command`
- `test_result`
- `blockers`
- `next_action`

状态流转建议：

```text
pending
  -> in_progress
  -> waiting_for_test
  -> verifying
  -> completed
```

异常分支：

```text
in_progress -> blocked
verifying   -> failed
failed      -> fixing
fixing      -> verifying
```

禁止直接从 `pending` 写成 `completed`，必须留下至少一次 `in_progress` 记录。

---

## 9. 后续开发建议顺序

当前 Phase A/B/C 已完成，下一界面不要继续盲目添加 Phase D。建议顺序：

### 第一步：重新验证当前基线

- 重跑 35 项新增测试。
- 重跑 LLM、配置、管线和工作流回归。
- 检查当前工作区是否有其他界面新增变化。

### 第二步：做代码审查而不是立即扩展

重点审查：

1. `WorkflowOrchestrator._execute_task_func` 的类外绑定是否符合团队长期维护规范。
2. `SandboxPolicy` 是否满足项目实际安全边界。
3. `ApprovalPolicy` 是否需要真实 UI/API 回调。
4. `ThinkingUpgradePolicy` 的任务类型和真实模型层是否完全匹配。
5. `UnifiedPipeline` 阶段返回数据是否真的包含所有不变量需要的上下文。
6. 形式化校验失败时是否应阻止生产管线，还是仅阻止指定阶段。

### 第三步：确定下一项路线图任务

可选方向：

- 将 `ThinkingUpgradePolicy` 接入真实业务调用点。
- 设计人工审批接口和持久化审批状态。
- 将沙箱从路径校验升级为进程级隔离。
- 将形式化不变量接入 `ae/e2e_pipeline.py` 等其他管线。
- 增加跨界面状态文件和事件历史。
- 增加真实环境前的 dry-run / replay 测试。

每个方向都应作为独立任务建立独立测试，不要直接修改现有 Phase A/B/C 测试以掩盖不兼容。

---

## 10. 已知问题、限制和不能误判的事项

### 10.1 审批默认拒绝

L4/L5 在未配置 callback 时默认拒绝。这是安全默认值，不是测试失败。生产界面必须提供审批回调，否则高危任务无法执行。

### 10.2 沙箱不是完整 OS 隔离

当前沙箱主要实现：

- 路径白名单。
- 黑名单检查。
- 临时目录上下文。

尚未实现：

- 独立进程权限隔离。
- CPU、内存、网络系统级硬限制。
- Windows Job Object 或容器。
- 子进程逃逸检测。

### 10.3 深度推理目前是策略能力

Phase A 已提供策略和异步执行方法，但不能把它描述为所有生产 LLM 调用已经自动升级。要做到全链路自动接入，还需要找到业务调用点，并明确是否允许改变原有路由行为。

### 10.4 形式化规范上下文可能不完整

Phase C 包装器使用 `StageResult.data` 作为上下文来源。如果具体阶段没有写入 `ae_layers`、`ffmpeg_params` 或 `ae_render_time_ms`，对应不变量可能使用默认值而无法发现实际问题。后续应补充阶段数据契约。

### 10.5 入口绑定的维护风险

Phase B 和 Phase C 都使用了类外入口绑定。优点是遵守“追加式、不改旧方法体”；风险是：

- 模块导入顺序影响最终绑定。
- 静态阅读不容易看到真实执行入口。
- 其他模块若保存旧类方法引用，可能绕过新包装器。
- 热重载或重复导入时需要验证是否重复绑定。

后续重构前必须先补充行为测试和兼容方案，不能直接删除绑定。

### 10.6 测试结果不能替代真实环境验证

本轮测试主要是 mock 和本地逻辑验证。通过不代表 AE、外部 Provider、真实审批系统和渲染环境已经验证。

---

## 11. 新界面可直接使用的启动提示

将以下内容复制给另一个界面，可作为任务恢复提示：

```text
请继续开发 AE-Knowledge-Vault。先完整阅读：
1. docs/cross-interface-task-handoff.md
2. docs/agent-safety-and-deep-reasoning-design-v2.md

工作区：c:/Users/Administrator/Desktop/AE-Knowledge-Vault
分支：feat/project-consolidation-v1
当前已完成：Phase A 深度推理升级、Phase B L1-L5 安全护栏、Phase C 形式化规范层。

请先不要修改代码，先执行：
- git status --short
- git branch --show-current
- 使用 puppet-automation/venv/Scripts/python.exe 重跑：
  tests/test_thinking_upgrade.py
  tests/test_l1_l5_guard.py
  tests/test_formal_spec.py

注意：工作区有大量与本任务无关的未提交变更，不得执行 git clean、git restore .、全局格式化或批量重写。

完成验证后，请按文档的“后续开发建议顺序”进行代码审查，先明确下一项独立任务和测试范围，再开始追加式开发。每个动作都按文档的“实时同步更新格式”报告：文件、状态、命令、测试、阻塞项、下一步。
```

---

## 12. 交接完成判定

另一界面满足以下条件时，说明接续成功：

- 能复述当前分支和工作区路径。
- 能识别 Phase A/B/C 已完成。
- 能列出本轮 10 个相关文件。
- 能说明工作区存在其他未归因变更。
- 能解释 `WorkflowOrchestrator` 的协程执行链和入口绑定。
- 能解释 L4/L5 默认审批拒绝。
- 能解释审计链为什么使用规范化 JSON。
- 能说明 Phase C 只接入 `UnifiedPipeline`，不是所有管线。
- 能重新运行最小 35 项测试。
- 能在开始下一项任务前建立清晰的任务 ID、文件范围、测试范围和实时同步状态。

---

## 13. 文档维护规则

本文件是交接状态文档，不是永久不变的设计规范。每次后续开发完成后必须更新：

1. `当前阶段`。
2. `本轮实际完成内容`。
3. `工作区变更边界`。
4. `测试和验证证据`。
5. `已知问题、限制和不能误判的事项`。
6. `后续开发建议顺序`。
7. `实时同步状态文件`中的 `last_action`、`next_action` 和历史事件。

更新文档本身也属于代码库变更，应在进度事件中记录。

---

# 附录 A：2026-08-03 深度漏洞修复轮记录

> 本附录记录 Phase A/B/C 完成后的深度审查与漏洞修复轮，由后续界面在本轮基础上继续开发。

## A.1 本轮完成内容

以实验室/企业研发级别对 Phase A/B/C 追加代码做了深度审查（3 个并行审查子智能体）与修复（3 个并行修复子智能体，文件范围零冲突）。修复采用追加式扩展，未改动旧方法体（唯一例外：`chat_with_routing` 增加可选参数 `force_temperature`，向后兼容；`scan_path` 的 startswith 前缀绕过修复）。

## A.2 修复的漏洞汇总

### Phase A（深度推理，core/llm_gateway.py + core/config.py）
| 漏洞 | 修复 |
|------|------|
| thinking_upgrade 配置死代码、downgrade_on_failure 未兑现 | `ThinkingBudget.from_config()` + 配置注入 + 升级失败降级普通路径 |
| 预算/超时/成本未强制执行 | 每轮 `asyncio.wait_for` 超时 + 累计成本上限中止 + 估算公式修正（中文 token/输出 token/self-check） |
| `_gateway_or_create` 创建未配置网关 | 复用模块级已配置单例 |
| 触发词子串误匹配（prove/lean/formal 假阳性） | ASCII 词边界正则 |
| self-check PASS 判定不可靠（中文/假阳性/None 崩溃） | 中英文双判定 + 否定/假阳性词排除 + success 检查 |
| upgraded_task_type="deep_reasoning" 指向不存在枚举 | 改为 `TaskType.QUALITY_REVIEW.name` |
| temperature=0.7 被强制覆盖 | `chat_with_routing` 增 `force_temperature` 可选参数 |
| 审查轮模型弱于回答轮 | 审查轮改 TIER_3（QUALITY_REVIEW） |
| 循环异常裸抛无轨迹 | try/except + 部分轮次轨迹 + `ThinkingTrace.error` 字段 |
| 其他 | context 实际参与决策、新增顶层 `chat_with_thinking_upgrade()` 便捷入口、max_rounds=0 防护、审查耗时计入、L1/L2 注解与置信度接线 |

### Phase B（L1-L5 安全护栏，core/security.py + core/workflow_orchestrator.py）
| 漏洞 | 修复 |
|------|------|
| 风险映射缺口（15 个 TaskType 默认 L2，含付费生成） | 补齐全部 29 成员（runway/pika/flux3→L5）；未知类型默认 L3 fail-closed |
| 沙箱可被空路径/类型混淆绕过 | `_extract_paths` 递归提取（嵌套/Path/.env）+ sandbox_dir 注入 + 路径校验 |
| 用户素材"读取"被误升 L4 | 只读任务升 L3（沙箱防护），写操作升 L4 |
| AuditChain 多实例并发写破坏链 | 模块级共享锁 + append 前重读文件尾哈希 |
| 组件初始化失败 fail-open | enable_security=True 时初始化失败 raise RuntimeError |
| 审批超时无效 + 拒绝被当可重试失败 | `asyncio.wait_for` 超时；`except SecurityError` 直接 FAILED 不重试不走 fallback |
| 审计链只记录成功、duration 恒 0 | `_append_audit_entry` finally 全分支记录（completed/failed/denied）+ 自行计时 |
| 其他 | 入口绑定幂等防递归、`_sanitize_args` 递归脱敏、关键字词边界+动作键、verify_chain 截断检测、scan_path 前缀绕过修复、任务级 sandboxed/enable_audit 开关 |

### Phase C（形式化规范层，core/formal_spec.py + pipeline/unified_pipeline.py）
| 漏洞 | 修复 |
|------|------|
| 数据契约断裂（三不变量生产恒假阴性） | 真实阶段补写字段（execute→ae_layers、render→ffmpeg_params/ae_render_time_ms）+ 缺字段告警 |
| InvariantViolation 裸抛崩溃 | 包装为 `StageResult(FAILED, error="[invariants] ...")` |
| 非数字比较 TypeError | `_to_number`/`_parse_position` 类型归一化 |
| bitrate 单位不一致 | 支持 "192k"/"20M"/bps 整数统一换算 |
| ae_render_time_ms 缺字段默认 0 | 哨兵 + warning |
| check_invariants 短路 | 聚合全部违规一次性抛出 |
| 其他 | rotation 归一化（%360）、绑定幂等、键冲突顺序、ImportError 降级仅限 ModuleNotFoundError |

## A.3 本轮修改的文件（新增到上一轮 10 个文件之上）

| 状态 | 文件 |
|------|------|
| 修改 | `core/llm_gateway.py`、`core/security.py`、`core/workflow_orchestrator.py`、`core/config.py`、`pipeline/unified_pipeline.py`、`core/formal_spec.py` |
| 修改 | `tests/test_thinking_upgrade.py`、`tests/test_l1_l5_guard.py`、`tests/test_formal_spec.py` |

上一轮交接文档第 2.1 节列出的 10 个文件即本轮修复的全部文件；未新增文件。

## A.4 测试证据（2026-08-03 本机真实执行，venv Python 3.11.9）

```text
三阶段测试（原 35 → 现 75）:  75 passed        （新增 40 项，覆盖攻击路径/边界/集成）
LLM 网关+配置回归:            284 passed        （test_llm_gateway*, test_core_config*, test_config_schema*）
安全+编排回归:                130 passed        （test_security, test_security_fixes, test_workflow_orchestrator）
Pipeline 回归:                42 passed         （test_pipeline_execution/integration 等 6 个文件）
DAG/Failover/Provider 回归:   61 passed, 1 skipped
py_compile（6 个源码文件）:   全部通过
```

## A.5 本轮遗留风险（不能误判）

1. **成本估算与预算张力**：按修正后口径估算，3 轮旗舰推理约 $1.7，故 `config.py` 中 `max_cost_per_task_usd` 已从 0.5 上调至 2.0；`ThinkingBudget()` 数据类默认值仍为 0.5（仅从 config 读取时用 2.0）。若未来有业务代码直接构造 `ThinkingBudget()` 不传 config，升级路径会被 cost_exceeded 拦截。
2. **沙箱仍是路径级**：`_resource_limits` 未真正实施进程级 CPU/内存/网络限制（docstring 已声明）；跨进程并发写同一审计链文件仍有交错风险（锁为进程内单例）。
3. **verify_chain 截断检测依赖实例缓存**：整体"截断+伪造完整重写"仍需外部锚点（`expect_last_hash` 已提供能力）。
4. **execute 阶段 ae_layers 为空列表**：该阶段真实数据仅有 layers_created 计数，无结构化图层位置/旋转数据，每次 execute 完成会触发"未测量"warning（属预期语义，但会刷日志）。
5. **render 阶段 ffmpeg_params 为引擎常量映射**（-b:v 4M / fps=30），若未来引擎调整码率需同步更新 `_INVARIANT_FFMPEG_*` 常量。
6. **`chat_with_thinking_upgrade` 尚未接入编排器/API 层**（M8 只提供了顶层入口，生产集成属下一任务）。
7. 测试运行会向 `logs/audit_chain.jsonl` 追加真实审计记录（L4 集成测试场景），属既有行为。

## A.6 后续开发建议顺序（更新）

在上一轮第 9 章基础上，建议下一步按序：
1. 将 `chat_with_thinking_upgrade` 接入 `WorkflowOrchestrator` 任务执行链（用 config 的 `enabled` 控制，任务级可选）。
2. 为 `ApprovalPolicy` 设计真实人工审批 UI/API 回调（当前默认拒绝）。
3. 审计链外部锚点持久化（如 `logs/audit_chain.meta` 存链尾哈希），使截断检测可靠。
4. 将 Phase C 不变量接入 `ae/e2e_pipeline.py`（`PipelineContext` 独立，需另开任务分析其阶段生命周期）。
5. 补 execute 阶段结构化图层数据契约，消除 ae_layers 空列表告警。
6. 沙箱进程级隔离（Windows Job Object）作为独立任务。

## A.7 实时状态文件

`.codebuddy/task-sync/ae-knowledge-vault-status.json` 仍未创建；如启用文件型实时同步，`active_phase` 建议改为 `vulnerability-hardening-completed`，`next_action` 参考 A.6。

**文档结束。**
