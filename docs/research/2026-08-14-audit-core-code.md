# AE 五层管线核心代码健康审计报告

- 审计日期：2026-08-14
- 审计范围：core/、ae/ae_agent_pipeline.py、ai/、compiler/、pipeline/、models/data/animeshooter_dataset.py、frame_enhancement_pipeline.py、frontier_system.py
- 方法：py_compile（Python 3.12）语法检查 + AST 导入解析 + grep 占位符统计 + registry 与实际代码/文件比对
- 结论速览：**语法层面全部健康，TS 编译器实装良好；主要病灶在「sys.path 扁平导入」架构、双注册表不一致、以及少量未接线/未完成模块。**

---

## 一、导入健康度

### 1.1 语法编译（py_compile，18 个核心模块 + 11 个 pipeline 模块）

全部通过（OK），无 SyntaxError。核心五层基建（state_machine / event_bus / observability / workflow_orchestrator / llm_gateway）均非空壳，是真实实现。

### 1.2 损坏 / 脆弱的扁平 import（重点）

| 文件:行 | 问题 | 严重度 |
|---|---|---|
| `frontier_system.py:142/149/236/321/328/448` | 懒加载扁平导入 `aigc_generator`(在 ai/)、`material_searcher`(在 scripts/)、`color_grading_applier`(在 video/)、`cinematic_intelligence`(在 scene/)、`multimodal_director`(在 ai/)，但仅 `sys.path.insert(0, root)`（第44行），子包目录均不在 path → **5 处运行时必然 ModuleNotFoundError** | 高 |
| `ai/ai_agent.py:503/898/909` | `from tool_executor import ...`，但 tool_executor.py 在 `tools/` 而非 `ai/`，且无 sys.path 注入 → 工具执行静默降级为 error dict | 高 |
| `core/llm_gateway.py:1139` | `from kb_loader import KBLoader`，kb_loader 在 `knowledge/` 与 `knowledge_base/`，不在根目录；包在 try/except 里 → **知识库上下文注入功能永久静默失效**（非崩溃，更难发现） | 中高 |
| `ae/ae_agent_pipeline.py`（4981 行） | 数十处跨包懒加载扁平导入（adobe_suite_integration@bridges/、audio_analyzer_enhanced@analysis/、beat_keyframe_mapper@audio/ 等），无统一 path 引导；第584-589行自己注释承认「已迁移到 scripts/archive/（不在 sys.path）」→ 依赖特定 cwd/调用方式才能跑通 | 中高 |
| `pipeline/stages/planning.py:113` | `from frontier_system import FrontierSystem` → 规划阶段依赖了一个本身导入已损坏的根级脚本 | 中 |

> 反例（处理正确，可作范本）：`pipeline/unified_pipeline.py:1520` 先 `sys.path.insert(.../tools)` 再 `from system_memory import SystemMemory`；`models/data/animeshooter_dataset.py:48-50` 用「相对导入 + 扁平兜底」双保险。建议统一改成包路径导入（`from ai.aigc_generator import ...`）。

---

## 二、占位符 / 未完成模块分布

`pass` 绝大多数位于 try/except 兜底与监听器接口（如 `core/state_machine.py:166/169` 的 StateListener），属正常。真正的 `raise NotImplementedError`「框架式」未完成点：

| 文件:行 | 内容 |
|---|---|
| `ae/distributed_renderer.py:569/586` | OpenCue / Afanasy 渲染农场提交逻辑未接入（配了 endpoint 直接抛 NotImplementedError） |
| `ai/aigc_generator.py:161/165` | AIGC 生成子类方法未实现 |
| `integrations/kb_search_engine.py:85/89` | 知识库搜索后端未实现 |
| `integrations/opensource_integrations.py:84/90` | 开源集成适配器未实现 |
| `effects/effect_generators.py:95`、`tools/plugin_system.py:208/232/258/282` | 抽象基类方法（合法，插件接口） |
| `core/multi_agent_orchestrator.py:98`、`core/quality_gate.py:179` | 抽象基类方法（合法） |
| `tools/unified_tool_integrator.py:304`、`scripts/material_searcher.py:146` | 单一方法占位 |

**TS 编译器（compiler/src）完全健康**：index.ts 正确串联 validator→ir-builder→scheduler→codegen，无 TODO/FIXME/stub。dist/ 下 3 个散文件（ai-scheduler.js/.mjs、test_phase5.mjs）是手工产物，正式产物在 build/（esbuild 脚本已配置）。

---

## 三、循环依赖 / 架构耦合风险

- 无 Python 语法级循环 import 报错；风险集中在「扁平导入依赖 sys.path/cwd」这一非显式耦合上。
- **巨型上帝文件**（耦合与维护成本主因）：
  - `pipeline/unified_pipeline.py` **5325 行**
  - `ae/ae_agent_pipeline.py` **4981 行**
  - `core/llm_gateway.py` **3768 行**
  - `ai/production_director.py` **2852 行**
- 规划阶段（pipeline/stages/planning.py）反向依赖根级脚本 frontier_system.py，形成「包 → 根脚本 → 破损子包导入」的脆弱链。

---

## 四、注册表一致性核对

### 4.1 models/model_registry.json（多项不一致）

1. **计数错误**：`n_models: 6`，实际 7 个条目。
2. **schema 不一致**：前 6 条用 `id`，第 7 条 `movieshots_camera_clf` 用 `name`（第76行），消费方需兼容两种键。
3. **size_mb 失真**：`student_ip_classifier` 记为 `0.38` MB，实际文件 44.8 MB（44833314 字节）。
4. **产物路径错位**：`movieshots_camera_clf` 指向 `models/output/movieshots_smoke.pt`（smoke 测试产物，val_acc=1.0、n_train=320），而训练脚本 `models/train_movieshots_camera.py:13/367` 的正式产物 `models/movieshots_camera_clf.pt` **并不存在**——登记的是冒烟版而非真模型。
5. **登记了但未接线（未接线）**：该条目 note 声称「替代 core/camera_movement_classifier 规则判定」，但 `ai/camera_decision.py:20` 直接 `from core.camera_movement_classifier import ...`（光流规则版），**全项目无任何代码加载该模型**。
6. **双注册表体系并存**：JSON 版（models/model_registry.json，被 ai/t25_model_registry.py、models/train_movieshots_camera.py 读取）与代码版 `models/deployment/model_registry.py`（ModelRegistry 类，被 models/train_jsx_code.py、models/register_style_classifier.py、models/evaluation 使用）两套并存，口径易漂移。

### 4.2 data/capability_registry.json（虚胖 + 冷启动）

- 写入方：`core/evolution/capability_feedback.py`；现已回读（`pipeline/unified_pipeline.py:1495`，修复了「只写不读」断点）。
- 但数据冷启动严重：`run_history` 仅 1 条（2026-08-05，score 0.61），`edit_techniques` 5 项、`color_grading_styles` 中 4 项、多数预设 usages=0 → 注册表「名目齐全、实际无数据」，进化反馈闭环暂未积累出可指导决策的信号。

---

## 五、TOP 5 优先迭代（按 影响面 × 修复成本比 排序）

| # | 文件:行 | 问题（证据） | 建议修法 |
|---|---|---|---|
| 1 | `frontier_system.py:142-448` | 5 处子包扁平导入在运行时必失败，且被 planning 阶段引用 | 改用包路径导入（`from ai.aigc_generator import AIGCGenerator` 等），去掉对 cwd 的隐式依赖 |
| 2 | `ai/ai_agent.py:503/898/909` | `from tool_executor import ...` 指向 tools/ 但不在 path，工具执行静默失效 | 改为 `from tools.tool_executor import ...`，或仿 unified_pipeline.py:1520 先注入 path |
| 3 | `core/llm_gateway.py:1139` | `from kb_loader import KBLoader` 静默失败，KB 注入是死代码 | 改为 `from knowledge.kb_loader import KBLoader`（或 knowledge_base），并补一条可用性日志 |
| 4 | `models/model_registry.json` + `ai/camera_decision.py` | 键名不一致/n_models 错/size 失真/产物是 smoke；模型登记却未接线 | 统一 schema（id 键）、修正元数据；在 camera_decision 加「加载已注册 MLP 覆盖规则」的开关，或明确标注 pending |
| 5 | `ae/ae_agent_pipeline.py`（4981 行） | 上帝文件 + 数十处跨包懒加载扁平导入 | 中期：抽依赖注入引导层统一 sys.path；长期按 phase2-5 拆分子模块 |

> 附带建议：`ae/distributed_renderer.py:569/586`（农场提交）与 `integrations/kb_search_engine.py` 两个 NotImplementedError 占位，若近期无落地计划，应在入口处显式 `return unsupported` 而非抛异常，避免上游调用方误判为可用。

---

## 六、总体评分

- **语法/编译健康度**：✅ 优（全部通过）
- **TS 编译器成熟度**：✅ 优（结构清晰、无占位）
- **导入架构稳健性**：⚠️ 中（扁平导入 + sys.path 依赖，3 处静默/运行时失效）
- **注册表可信度**：❌ 弱（计数/键名/体积失真，关键模型未接线，数据冷启动）
- **可维护性（上帝文件）**：⚠️ 中（4 个 2800+ 行单文件，最长 5325 行）
