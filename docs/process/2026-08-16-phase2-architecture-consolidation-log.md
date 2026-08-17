# 2026-08-16 阶段2架构收敛执行记录

> 承接 `docs/research/2026-08-16-full-project-audit.md` 阶段2方案。全程约束：
> 不碰并行流的 visual_scorer/collect_tuning_data（代理直连修复未提交）；
> 根目录 JSX 迁移等外部 AE 启动器引用链就绪。每批全量套件门禁 5029 passed / 0 failed。

## 批1（493f06e / 31da12c / c3a3b0b）

### synthesis_orchestrator 拆分 + JS 注入转义（refactor(core)）
- `_build_layer` 巨石（6 路 elif + 内嵌模板 JSX）→ 新建 `core/layer_builders.py`：
  按类型一个构建函数 + `LAYER_BUILDERS` 注册表；orchestrator 回归
  校验→预备→编排→build→发送 纯管线
- 新增 `js_str()` 转义：comp_name/layer.id/text/报错路径此前直插 JS 字符串，
  含引号/反斜杠即生成非法 JSX（实测 `addComp("Weird"Comp\Name"...)` 字面崩溃）
- 验证：基线等价法（tmp/refactor_baseline/gen_baseline.py，重构前存基线→
  重构后逐字节 diff）——6 模板工厂 + dry_run 零差异；含特殊字符合成树差异
  恰好 5 处转义行且过 node 语法门禁；43/43 模块级验收断言全绿
- **新发现（未改行为，待产品决策）**：jsx_keyframe_animator 入场动画
  含未固定种子随机抖动，同树 JSX 跨进程不可复现（cyberpunk 模板可见）

### plugin_fx_templates 参数索引收口
- `_PART_IDX` 死字典（定义后正文全用裸数字）落地为正文唯一事实源
- 96/97 矛盾用真机产物考证结案：96="Particle Type"（英文组标签不可设值）、
  97="粒子类型"（枚举 1-6，真机验证 1=Sprite）→ ptype 96→97
- 18/19：18="位置"组、19="位置XY"点，注释消歧
- 输出与基线逐字节一致（只常量化，值不变）

### adobe_mcp_adapter 三处实 bug（fix(integrations)）
1. 幽灵环境变量 AEKV_ROOT → AEKV_PROJECT_ROOT → 项目根
2. 跨应用 JSX 全发 AE 专属桥 → 非 AE 目标显式失败并指向 bridges/*_client
3. 陈旧结果竞态 → 发送前 unlink 结果文件
- 名不副实的 `_execute_jsx_via_powershell`（从未用过 PowerShell）更名
  `_execute_jsx_via_ae_bridge`
- 桥目录治理：删 .media-encoder-mcp-bridge(连字符版,零引用)/空 ae-mcp-bridge/
  /空 bridges/.photoshop-mcp-bridge；**保留 bridges/.ae-mcp-bridge**（实测
  当日仍被写入, adobe_universal_bridge 在用）+ 补 ignore
- knowledge_base/ 标 deprecated（knowledge/ 为主线的依据写入 docstring）

## 批2（6dfeb2d / b539599）

### scripts 反转依赖治理（审计 P1 核心项）
- material_searcher → integrations/（1189 行）、render_cleanup → core/（270 行），
  均为纯 stdlib 自包含
- 生产方 import 直改新路径：production_director / frontier_system /
  daily_disk_cleanup（消除"核心反向 import scripts"倒挂）
- 原路径留 DeprecationWarning 垫片；新路径/垫片/旧 sys.path 三通路验证通过

### au_bridge_client 路径修复
- 默认桥目录与 _load_secret 曾指向不存在的 bridges/.au-mcp-bridge → 项目根
- **判断**：AE 家族已有 ae.ae_bridge_base 基类，未另造"第 6 套 bridge_base"

### 字体两套标 deprecated
- font_manager/font_scanner 已无生产消费方（仅测试引用）→ 指向 font_style_map

### camera_classifier 内部去重（refactor(camera)）
- 读帧两函数 90% 重复 → 抽 _sample_frames；投票+平局守卫+置信公式双份 →
  抽 _aggregate_votes；块缓存指纹 10→16 位 + entry _v schema 版本守卫
- 37 分类器/决策测试全绿 + 聚合行为抽查

## 批3（643d364）

### 效果参数寻址统一注册表（refactor(core)）
- 新建 core/effect_registry.py：整数位置索引（原 MATCH_PARAM_MAP）+
  AVID 索引（原 _EFFECT_PARAM_INDEX）+ AVID 兜底（原 _EFFECT_DEFAULTS）
- **关键设计**：两种维度不合并值（位置随版本/语言漂移，AVID 稳定），
  仅收拢同一知识到一处并明确边界；名称层 data/fx_registry.json 保持数据文件
- jsx_generator 私有名零残留；registry 行为等价抽查 + 89 相关测试全绿

### 小修
- beat_strength_engine CLI 硬编码小写绝对路径 → __file__ 相对 + 补 Path import
  （此前编译可过但 CLI 运行必 NameError）
- core/__init__ 修正陈旧模块清单（cache_manager/hybrid_retriever/
  model_router/exceptions 从未存在；补新模块）

## 核查无改动项
- quality-gate.yml 引用的 scripts/ci_e2e_pipeline.py / scripts/ci_quality_gate.py
  / config/quality_gate_thresholds.json 全部存在，无迁移波及
- conftest 排除表 24 条 0 真实死条目（CRLF 安全复查）

## 遗留（见各自提交信息与体检报告）
- visual_scorer 收口进 llm_gateway：等并行流代理直连修复提交后
- 根目录 JSX 迁移：需先改 AE 启动器引用链（mcp_bridge_panel/z_mcp_bridge_loader）
- llm_gateway qwen provider 注册：visual_scorer 收口的前置
- 入场动画随机种子可复现化：待产品决策（创作特性 or 缺陷）
- git filter-repo 清 680MB 历史：待用户确认（有远程需强推）
- pre-commit 钩子：代理恢复后 `python -m pre_commit install`
