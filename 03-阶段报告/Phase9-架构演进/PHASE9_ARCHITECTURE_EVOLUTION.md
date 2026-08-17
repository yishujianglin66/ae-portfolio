# P1-P4 架构演进阶段报告

## 项目背景
本报告记录 AE Knowledge Vault 项目基于 Antares 精悍够用哲学和 Runta 安全执行层理念的架构演进工作，涵盖四个阶段（P1-P4）的完整实施内容。

---

## Phase 1: 分层路由架构（Antares 哲学落地）

### 目标
将轻量级垂直模型与通用大模型分层路由，在代码生成、风格分析等特定场景优先调用高效小模型，降低成本并提升响应速度。

### 核心改动

**文件: [core/llm_gateway.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/core/llm_gateway.py)**

1. **ModelTier 枚举**（三层模型档位）:
   - TIER_1_LOCAL_SPECIALIZED: 本地垂直小模型（5M-50M参数）
   - TIER_2_MIDTIER_GENERAL: 中端通用模型
   - TIER_3_FLAGSHIP_REASONING: 旗舰推理模型

2. **TASK_TIER_MAP**（8种任务类型映射）:
   - INTENT_CLASSIFICATION → TIER_1 (意图识别)
   - STYLE_ANALYSIS → TIER_1 (风格分析)
   - PARAMETER_OPTIMIZATION → TIER_1 (参数优化)
   - CODE_GENERATION → TIER_2 (代码生成)
   - GENERAL → TIER_2 (常规任务)
   - QUALITY_REVIEW → TIER_3 (质量审核)
   - COMPLEX_ANALYSIS → TIER_3 (复杂分析)
   - DEEP_REASONING → TIER_3 (深度推理)

3. **LLMConfig 扩展**:
   - enable_tiered_routing: 启用分层路由
   - prefer_small_model: 优先使用小模型
   - tier_config: 各档位配置（API URL、密钥、成本系数）

4. **LLMResponse 扩展**:
   - tier: 当前使用的模型档位
   - cost_usd: 本次调用成本（美元）
   - tier_upgraded: 是否发生档位升级

5. **成本计算方法**:
   - `_calculate_cost(input_tokens, output_tokens, tier)`: 根据档位成本系数计算

6. **分层统计方法**:
   - `get_tier_stats()`: 返回各档位调用次数、总成本等统计信息

### 设计原则
- **Antares 哲学**: 精悍够用，小模型能搞定的绝不劳烦大模型
- **配置化**: 新增模型只需修改配置，无需改动核心代码
- **成本透明**: 每次调用实时计算成本，支持事后分析

---

## Phase 2: 置信度级联路由（智能升级机制）

### 目标
实现"小模型先上，置信度不够自动升级大模型"的级联调用机制，在保证质量的同时最大化成本效益。

### 核心改动

**文件: [core/llm_gateway.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/core/llm_gateway.py)**

1. **ConfidenceLevel 枚举**（五级置信度）:
   - very_low: 0-0.2
   - low: 0.2-0.4
   - medium: 0.4-0.6
   - high: 0.6-0.8
   - very_high: 0.8-1.0

2. **LLMConfig 级联配置**:
   - enable_cascade: 启用级联路由
   - cascade_confidence_threshold: 置信度阈值（默认0.7）
   - cascade_max_upgrades: 最大升级次数（默认2次）

3. **LLMResponse 置信度字段**:
   - confidence: 置信度数值（0-1）
   - confidence_level: 置信度级别（枚举）
   - confidence_reason: 置信度推断原因
   - cascade_path: 级联路径记录（如 ["tier1", "tier2"]）
   - upgrade_count: 升级次数
   - saved_cost_usd: 相比直接用旗舰模型节省的成本

4. **核心方法**:
   - `chat_with_cascade(task_type, message, ...)`: 级联调用入口
   - `_extract_confidence(content, tier, task_type)`: 多维度置信度提取
   - `_should_upgrade(response, current_tier, task_type, upgrade_count)`: 判断是否升级
   - `_validate_response_quality(response, task_type)`: 响应质量验证
   - `_calculate_savings(original_cost, actual_cost)`: 计算成本节省

5. **置信度提取策略**:
   - 显式提取: 从响应中寻找 "confidence: 0.95" 等模式
   - 结构化推断: 根据响应格式（代码块、列表、引用等）推断置信度
   - 长度分析: 过短或过长的响应可能表示不确定
   - 任务类型调整: 不同任务类型对置信度要求不同

### 级联流程
```
用户请求 → TIER_1（小模型）→ 置信度评估
                ↓ 置信度 < 0.7
            TIER_2（中端）→ 置信度评估
                ↓ 置信度 < 0.7
            TIER_3（旗舰）→ 最终响应
```

---

## Phase 3: Agent 安全执行层（Runta 架构集成）

### 目标
将 Runta 的 Agent 安全执行层理念融入工作流编排器，为自动化 AE 合成流水线增加行为审计与沙箱隔离能力。

### 核心改动

**文件: [core/security.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/core/security.py)**

1. **安全级别枚举 (SecurityLevel)**:
   - SAFE: 安全（仅读取）
   - LOW: 低风险（简单写入）
   - MEDIUM: 中风险（代码执行）
   - HIGH: 高风险（系统调用）
   - CRITICAL: 临界（管理员操作）

2. **权限类型枚举 (PermissionType)**:
   - FILE_READ, FILE_WRITE, FILE_EXECUTE
   - NETWORK_ACCESS, SYSTEM_CALL, PROCESS_CONTROL, CONFIG_MODIFY

3. **数据结构**:
   - SecurityContext: 随任务传递的安全上下文
   - AuditLogEntry: 审计日志条目（不可篡改）
   - SecurityScanResult: 安全扫描结果

4. **SecurityManager 核心方法**:
   - `scan_code(code, code_type)`: 危险模式检测（JSX/Shell/路径遍历）
   - `check_permission(context, required)`: 权限校验
   - `validate_path(path, allowed_paths)`: 路径校验（防路径遍历）
   - `log_audit(entry)`: 记录审计日志
   - `check_circuit_breaker()`: 熔断状态检查
   - `reset_circuit_breaker()`: 重置熔断器

5. **危险模式规则**:
   - JSX: eval(), Function(), execCommand(), app.system(), File写操作, Folder.fs
   - Shell: rm -rf, format, del /s/q, reg add, shutdown /s
   - 路径遍历: ../.., %2e%2e%2f

**文件: [core/workflow_orchestrator.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/core/workflow_orchestrator.py)**

1. **TaskDefinition 安全字段**:
   - security_level: 安全级别
   - required_permissions: 所需权限列表
   - enable_audit: 是否启用审计
   - sandboxed: 是否沙箱隔离

2. **TaskInstance 安全字段**:
   - security_context: 安全上下文
   - audit_entries: 审计条目列表

3. **WorkflowContext 安全字段**:
   - security_manager: 安全管理器实例
   - security_level: 工作流安全级别
   - audit_log: 审计日志

4. **安全方法**:
   - `set_security_level(level)`: 设置工作流安全级别
   - `get_security_manager()`: 获取安全管理器
   - `_enforce_security(task)`: 任务执行前安全检查
   - `_audit_task_start(task)`: 任务开始审计
   - `_audit_task_complete(task, result)`: 任务完成审计
   - `_audit_task_failed(task, error)`: 任务失败审计

**文件: [core/observability.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/core/observability.py)**

1. **新增安全指标**:
   - security_violations_total: 安全违规总数
   - audit_log_entries_total: 审计日志条目总数
   - circuit_breaker_status: 熔断器状态

---

## Phase 4: 垂直小模型训练框架

### 目标
构建完整的垂直小模型训练管线，支持风格分类、JSX代码生成、参数优化等特定场景的精悍模型训练与部署。

### 核心改动

**目录: [models/](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/)**

#### 1. 模型配置 (models/configs/)

**[style_classify_config.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/configs/style_classify_config.py)**
- 目标参数量: 5M
- 任务类型: 风格分类（10类）
- LoRA 参数: r=8, alpha=16
- 训练超参: epochs=3, batch_size=8, lr=2e-5

**[jsx_code_config.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/configs/jsx_code_config.py)**
- 目标参数量: 50M
- 任务类型: JSX代码生成
- LoRA 参数: r=16, alpha=32
- 训练超参: epochs=5, batch_size=4, lr=1e-5

**[param_optim_config.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/configs/param_optim_config.py)**
- 目标参数量: 10M
- 任务类型: AE参数优化预测
- LoRA 参数: r=8, alpha=16
- 训练超参: epochs=3, batch_size=16, lr=2e-5

#### 2. 数据集 (models/data/)

**[dataset_base.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/data/dataset_base.py)**
- BaseDataset 抽象基类
- 统一数据接口: load(), split(), get_item()

**[jsx_code_dataset.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/data/jsx_code_dataset.py)**
- JSX代码数据集
- 支持从JSONL加载
- 数据增强: 变量名替换、注释增减
- 语法校验过滤

**[style_classify_dataset.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/data/style_classify_dataset.py)**
- 风格分类数据集
- 支持从风格指纹JSON加载
- 数据增强: 噪声注入、参数微调

#### 3. 训练器 (models/training/)

**[trainer_base.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/training/trainer_base.py)**
- BaseTrainer 抽象基类
- TrainingConfig 数据类（19个配置字段）
- TrainingResult 数据类

**[lora_trainer.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/training/lora_trainer.py)**
- LoRA微调训练器
- 封装LoRA配置和训练流程

#### 4. 评估器 (models/evaluation/)

**[evaluator_base.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/evaluation/evaluator_base.py)**
- BaseEvaluator 抽象基类

**[jsx_code_evaluator.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/evaluation/jsx_code_evaluator.py)**
- JSX代码评估器
- 评估指标: 语法正确率、功能正确率、代码质量、BLEU/CodeBLEU

**[style_classify_evaluator.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/evaluation/style_classify_evaluator.py)**
- 风格分类评估器
- 评估指标: 准确率、精确率/召回率/F1、混淆矩阵、Top-K准确率

**[benchmark.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/evaluation/benchmark.py)**
- BenchmarkSuite 基准测试套件
- 支持标准测试集管理、多模型对比、评估报告生成、成本-效果分析

#### 5. 部署 (models/deployment/)

**[model_registry.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/deployment/model_registry.py)**
- 模型注册中心
- 支持模型版本管理、元数据记录、模型上线/下线、A/B测试支持

**[inference_server.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/deployment/inference_server.py)**
- 推理服务封装
- 提供统一的推理接口，支持批量推理、性能优化
- 与llm_gateway的适配层预留

#### 6. 工具集 (models/utils/)

**[metrics.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/utils/metrics.py)**
- 评估指标集合
- 包含准确率、精确率、召回率、F1、BLEU、CodeBLEU、参数量统计、推理速度基准
- **cost_effectiveness_ratio**: 成本效益比（Antares哲学核心指标）

**[tokenizer_utils.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/utils/tokenizer_utils.py)**
- 分词器工具，支持HuggingFace Tokenizer和simple分词器

**[training_callbacks.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/models/utils/training_callbacks.py)**
- 训练回调集合: LoggingCallback、EarlyStoppingCallback、CheckpointCallback、MetricsCallback

---

## 全局集成测试

**文件: [test_full_integration.py](file:///c:/Users/Administrator/Desktop/AE-Knowledge-Vault/test_full_integration.py)**

### 测试结果
```
测试完成: 4/4 Phase 通过
耗时: 1.27s

phase1: ✓ 通过  （6项验证）
phase2: ✓ 通过  （8项验证）
phase3: ✓ 通过  （12项验证）
phase4: ✓ 通过  （9项验证）
```

### 测试覆盖点

**Phase 1**:
- ModelTier 枚举验证
- TASK_TIER_MAP 验证
- LLMConfig 新字段验证
- LLMResponse 新字段验证
- 分层统计可用
- 成本计算

**Phase 2**:
- ConfidenceLevel 枚举验证
- LLMResponse 置信度字段
- LLMConfig 级联配置
- 网关级联方法存在性
- 显式置信度提取
- 结构化置信度推断
- 升级判断逻辑
- 质量验证

**Phase 3**:
- SecurityLevel/PermissionType 枚举
- SecurityManager 初始化
- 危险JSX扫描（eval/app.system/File写）
- 安全JSX扫描
- 危险Shell扫描
- 内容哈希
- 审计日志记录
- 熔断器触发/重置
- TaskDefinition 安全字段
- WorkflowOrchestrator 安全方法

**Phase 4**:
- TrainingConfig 字段
- 三个模型配置验证
- 评估指标计算（acc/precision/recall/f1）
- 成本效益比计算
- ModelRegistry
- InferenceServer
- BenchmarkSuite

---

## 架构总览图

```
┌─────────────────────────────────────────────────────────┐
│                  AE Knowledge Vault                      │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  Phase 4: 垂直小模型训练框架                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
│  │ 风格分类  │  │ JSX代码  │  │ 参数优化  │ ← 5M-50M    │
│  │  (5M)    │  │  (50M)   │  │  (10M)   │   精悍小模型  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘              │
│       │              │              │                    │
├───────┴──────────────┴──────────────┴───────────────────┤
│                                                          │
│  Phase 1+2: LLM 网关 - 分层 + 级联路由                   │
│  ┌─────────┐  置信度  ┌─────────┐  置信度  ┌─────────┐ │
│  │ TIER_1  │ ──────→  │ TIER_2  │ ──────→  │ TIER_3  │ │
│  │ 小模型   │  不够升级  │ 中端通用  │  不够升级  │ 旗舰推理  │ │
│  └─────────┘          └─────────┘          └─────────┘ │
│       ↑ 成本节省追踪 + 健康检查 + 自动降级                │
├───────┴──────────────────────────────────────────────────┤
│                                                          │
│  Phase 3: Agent 安全执行层                               │
│  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐        │
│  │ 安全分级 │  │ 行为审计 │  │ 输出扫描 │  │ 熔断机制 │        │
│  └───┬────┘  └───┬────┘  └───┬────┘  └───┬────┘        │
│      └───────────┴────────────┴────────────┘             │
│                           ↑                              │
│              Workflow Orchestrator 集成                  │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

## 与现有系统的兼容性

### 向后兼容
- 所有现有代码无需修改，新功能为可选配置
- 未启用分层路由时，行为与之前一致
- 未提供provenance元数据时，compiler行为不变

### 接口一致性
- 统一的execute()入口（引擎层）
- 统一的chat()/chat_with_cascade()接口（LLM网关）
- 统一的安全上下文传递（工作流层）

---

## 下一步建议

### 短期（1-2周）
1. 部署实际的垂直小模型（如风格分类模型）到TIER_1
2. 集成JiuwenSwarm多智能体协同框架
3. 完善数据准备管线（收集真实训练数据）

### 中期（1个月）
1. 端到端性能基准测试
2. 实际成本对比验证（小模型 vs 大模型）
3. 安全执行层实战测试（模拟危险JSX攻击）

### 长期（3个月）
1. 构建完整的小模型生态（更多垂直场景）
2. 实现模型自动蒸馏与部署
3. 建立模型质量监控与自动降级机制