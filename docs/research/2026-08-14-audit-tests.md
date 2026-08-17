# 测试套件健康度审计报告（2026-08-14）

> 审计对象：`tests/` 目录（1271 个文件）与 core/ai/pipeline/models/learning 核心模块的测试覆盖关系。
> 审计方式：只读审计 + 运行测试，未修改任何代码。
> 执行环境：Python 3.12.7（pytest 9.1.1 / pytest-asyncio 1.4.0 / pytest-timeout 2.4.0，**未安装 pytest-cov 与 coverage**）。

---

## 1. 测试收集总数

| 指标 | 数值 |
|---|---|
| `tests/` 文件总数 | 1271（其中 862 个 `.pyc` 缓存、319 个 `.py`、84 个媒体素材） |
| `test_*.py` 文件数 | **298** |
| pytest 收集用例总数 | **4984** |
| 被默认 marker 排除（slow / real_ae / real_pr / silhouette …） | 121 |
| 默认配置下实际可运行用例 | **4863** |
| 全量 collect-only 耗时 | **170 秒（约 2:50）** |

说明：`pyproject.toml` 的 `addopts` 已内置 `-m "not slow and not real_ae and not silhouette and …"` 与 `--timeout=30`、`--strict-markers`，因此下述抽样运行直接沿用项目默认 marker 过滤，未额外覆盖。

收集时出现的告警：`tests/test_video_generator.py::TestVideoGenerator` 因定义了 `__init__` 构造器，pytest 无法收集该类（`PytestCollectionWarning`）。

---

## 2. 抽样运行结果（4 个核心模块分组，全部通过）

| 分组 | 测试文件 | 结果 |
|---|---|---|
| 核心 core | test_event_bus / test_config_schema / test_exceptions / test_observability / test_memory_store / test_formal_spec / test_engine_registry | **332 passed**（1 warning，6.07s） |
| 管线 pipeline | test_pipeline_integration / test_phase2 / test_failure_recovery / test_phase4 / test_effect_composition_engine | **156 passed**（4 warnings，11.05s） |
| 学习 learning | test_p0_learning_loop / test_learning_bridge_gaps / test_feedback_api_gaps | **48 passed**（0.93s） |
| 模型 models | test_animeshooter_dataset / test_movieshots_dataset / test_model_pipeline_integration | **11 passed**（0.51s） |

**抽样合计：547 passed / 0 failed / 0 error**。抽样的核心单元测试质量良好、运行稳定。

---

## 3. 空文件 / 占位测试 / 重复测试文件

### 3.1 空文件与极小文件
- 0 字节空文件：**0 个**
- `< 100` 字节文件：**0 个**
- `< 300` 字节文件：**0 个**
- 最小测试文件约 500 字节（`test_direct_download.py` 502B、`test_run.py` 503B），但均非"空占位"，而是**脚本式文件**（见 3.3）。

### 3.2 重复测试文件
- 字节级完全相同的重复文件（MD5）：**0 个**
- 但存在 **版本迭代遗留的近重复文件**（同名/同域多版本并存，疑似被取代未删除）：

| 文件 | 大小 | 疑似关系 |
|---|---|---|
| test_aerender_v2.py | 28955 | 与 test_aerender 系列重复 |
| test_dof_params.py / test_dof_params2.py | 4056 / 3808 | 同名 v2 迭代 |
| test_puppet_style.py / test_puppet_style2.py / test_puppet_style_integration.py | 2300 / 4803 / — | 同名三版本 |
| test_e2e_pipeline_v2.py / test_e2e_pipeline_flow.py | 33897 / — | 管线 E2E 双版本 |
| test_silhouette_v2.py / test_silhouette_integration.py | 14670 / — | Silhouette 双版本 |
| test_video_effect_analyzer_v2.py | 13585 | v2 迭代 |
| test_v17_e2e.py / test_v17_full_pipeline.py | 22537 / 22514 | 同版本双文件（大小几乎相同） |
| test_text_integration_p2.py | 7610 | 分阶段重复 |
| test_opensource_e2e_v2.py / test_unified_v21_e2e.py | 15881 / 6108 | 版本号膨胀 |

### 3.3 关键发现：68 个"脚本式伪测试"（占 22.8%）

`test_*.py` 中 **68 个文件（298 个里的 22.8%）不包含任何 `def test_*` / `async def test_*` 测试函数**，pytest 收集它们时得到 0 条用例。它们本质是"以 `python test_x.py` 直接运行的脚本"，伪装成 pytest 测试：

- **纯脚本（`main()` / 顶层 `check()` 自定义断言）**：test_run.py、test_director_scorer.py、test_narrative_arc.py、test_p0_core_chain.py、test_p0_full_7stage_e2e.py、test_p0_full_pipeline_e2e.py、test_p0_e2e_real_mix.py、test_p2_bayesian.py、test_p1_vrs_cvonly.py、test_p1_kb_injection.py、test_master_rules.py、test_preview_inheritance.py、test_effect_composition_engine.py、test_model_pipeline_integration.py、test_ai_director_e2e.py、test_e2e_style_pipeline.py、test_e2e_silhouette_pipeline.py、test_vrs_integration.py、test_external_capability_integration.py、test_text_integration.py、test_text_integration_p2.py、test_v4_nlu_comparison.py、test_video_generator.py、test_hybrid_pipeline.py、test_pro_editing_features.py、test_pro_upgrade.py、test_full_style.py 等
- **真实网络/下载脚本（顶层发起网络请求）**：test_direct_download.py、test_douyin_api.py、test_douyin_browser.py、test_douyin_download.py、test_douyin_network.py、test_douyin_playwright.py、test_douyin_mobile.py、test_pw_direct.py、test_puppet_style.py、test_zhuangzhuang.py、test_edge_login.py
- **真实 AE/桥接下发脚本（顶层写文件/发命令）**：test_cam_props.py、test_dof_params.py、test_dof_params2.py、test_import_options.py、test_import_single.py、test_import_methods.py、test_simple_safe.py、test_inc_layers.py、test_inc_full.py、test_ae_bridge_render.py、test_ae_execute_stage.py、test_batch_keyframes.py、test_phase1_real_ae.py、test_phase2_real_ae.py、test_phase3_real_ae.py、test_real_e2e_all_modules.py、test_real_pipeline.py、test_p0_e2e_real_mix.py、test_real_mode.py、test_s1_s2_real.py、test_s3_ae_real.py、test_s4_s5_real.py、test_v17_full_pipeline.py
- **Silhouette `fx` 脚本（顶层 `addAction()`，非 pytest）**：test_roto_action.py、test_roto_e2e_final.py、test_roto_pipeline.py
- **其他打印/顶层实例化脚本**：test_dctl_lookup.py、test_debug_lua.py、test_safe_lut_path.py、test_effect_registry_root.py、test_mcp_bridge.py、test_output_registry.py

**风险**：其中部分文件的顶层可执行代码没有 `if __name__ == "__main__":` 保护（如 test_direct_download.py、test_douyin_*.py、test_dctl_lookup.py 等），pytest `--collect-only` 导入它们时会**真实触发下载、写文件、向 AE 桥接写命令等副作用**，这正是全量收集耗时 170 秒、且潜在挂起/污染环境的主要原因之一。

---

## 4. 无测试覆盖的高风险模块清单

> 判定标准：模块（core/ai/pipeline/models/learning 下的 `.py`，排除 `__init__.py`）在全部 `tests/*.py` 中**既无同名 `test_<module>.py`，也未被任何测试文件的 `import`/`from` 语句引用**。

| 包 | 模块总数 | 完全无测试引用 | 说明 |
|---|---|---|---|
| core | 84 | **21** | 多为真实核心库模块 |
| pipeline | 28 | **12** | 含旗舰主运行器与 4 个阶段 |
| models | 39 | **36** | 训练/评估/部署基础设施几乎零覆盖 |
| ai | 83 | **73** | 大部分为 `tXX_*.py` 训练脚本，但也含多个真实库模块 |
| learning | 10 | **6** | feedback/parameter_optimizer/result_verifier 等 |

### 4.1 core/（21 个完全无测试）
```
core/error_diagnostician.py        ← AE 崩溃根因诊断（高风险核心）
core/feedback_loop.py              ← 反馈闭环
core/meta_strategy_engine.py       ← 元策略引擎
core/optimal_combo_engine.py       ← 最优风格组合
core/style_presets.py / style_spec_extractor.py / style_feature_extractor.py / style_workflow_integration.py
core/music_dynamics.py / beat_strength_engine.py / template_rhythm.py
core/frame_extractor.py / vision_feature_layer.py / visual_inspector.py / post_enhancer.py
core/highlight_scorer.py / performance_baseline.py / workflow_tasks_video.py
core/evolution/protocol.py / core/evolution/capability_feedback.py
core/pipeline/models.py
```

### 4.2 pipeline/（12 个完全无测试）
```
pipeline/flagship_runner.py                 ← 旗舰管线主运行器（S0→S7）
pipeline/manga_pipeline.py / material_scanner.py / multi_thread_executor.py
pipeline/orchestration_interface.py / engine_task_dispatcher.py / vrs_effect_lander.py / presets.py
pipeline/stages/compiler.py / perception.py / planning.py / rendering.py   ← 4 个核心阶段
```

### 4.3 models/（36 个完全无测试 —— 训练/评估/部署全链路裸奔）
```
训练：models/training/trainer_base.py, lora_trainer.py, full_finetune_trainer.py,
     param_optim_trainer.py, jsx_code_trainer.py
评估：models/evaluation/evaluator_base.py, jsx_code_evaluator.py, style_classify_evaluator.py,
     benchmark.py, performance_benchmark.py, security_test.py, global_integration_test.py
部署：models/deployment/inference_server.py, model_registry.py, model_converter.py
数据：models/data/{dataset_base,jsx_code_dataset,param_optim_dataset,style_classify_dataset,
     data_preparator,prepare_jsx_data,prepare_training_data}.py
配置：models/configs/{jsx_code_config,param_optim_config,style_classify_config}.py
工具：models/utils/{metrics,tokenizer_utils,training_callbacks}.py
```

### 4.4 ai/（真实库模块中完全无测试的重点）
```
ai/deepseek_v4_client.py          ← DeepSeek 客户端（虽有 test_deepseek_v4_api.py，但它未引用本模块，测的是别的东西）
ai/vision_client.py / doubao_client.py / ai_video_generator.py / ai_chat_api.py
ai/local_model_hub.py / multimodal_director.py / material_intelligence.py
ai/production_scorer.py / shot_script.py / rhythm_reward.py
ai/style_resolve_pipeline.py / style_bridge.py / corpus_factory.py / clip_backbones.py / clip_ensemble.py
```
（其余 `ai/t7_*` ~ `ai/t39_*` 均为一次性训练/数据加工脚本，非可导入库模块，未计入"应补测"优先级。）

### 4.5 learning/（6 个完全无测试）
```
learning/feedback_loop_manager.py / feedback_manager.py / parameter_optimizer.py
learning/result_verifier.py / training_logger.py / training_state_manager.py
```

---

## 5. 覆盖率（fail_under=60）检查

- `pyproject.toml` 已配置 `[tool.coverage.report] fail_under = 60`（初始阈值）。
- 当前 Python 3.12 环境**未安装 `pytest-cov`，也未安装 `coverage`**（`pip list` 仅见 pytest / pytest-asyncio / pytest-timeout）。
- 因此**无法运行覆盖率验证，本次跳过**。达标与否未知。

**建议**：安装 `pytest-cov`（`python -m pip install pytest-cov`）后，在最小核心子集（如 `tests/test_event_bus.py tests/test_config_schema.py tests/test_exceptions.py`）上跑一次 `--cov=core --cov-report=term-missing`，确认核心路径覆盖率是否越过 60% 门槛。鉴于 models/pipeline 大面积零覆盖，整体达标风险高。

---

## 6. 结论与建议

1. **表面健康、暗藏结构债**：4984 条用例、抽样 547 条全绿，但其中 68 个（22.8%）`test_*.py` 是"伪测试"脚本，不贡献任何 pytest 用例，且部分在收集阶段即产生网络/文件/AE 桥接副作用，拉低收集速度、制造环境污染与偶发挂起风险。
2. **核心逻辑存在明显盲区**：core 有 21、pipeline 有 12、models 有 36 个模块完全无测试引用，且 models 的训练/评估/部署基础设施近乎全线裸奔。
3. **覆盖率为"纸面配置"**：fail_under=60 尚未被任何实际覆盖率运行校验过（环境缺 pytest-cov）。

### 最该优先补测试的 3 个模块
1. **`core/error_diagnostician.py`** — AE 崩溃根因诊断是项目高频痛点（仓库内大量 AE 崩溃排查文档），却零测试，风险最高。
2. **`pipeline/flagship_runner.py` + `pipeline/stages/{compiler,perception,planning,rendering}.py`** — 旗舰管线主运行器与 4 个核心阶段零测试，是最关键的执行链路盲区。
3. **`models/training/trainer_base.py` + `lora_trainer.py` + `full_finetune_trainer.py`** — 训练基础设施完全无测试，models 目录 36 个模块整体无覆盖，任何重构都可能静默破坏训练链路。

### 次要建议
- 把 68 个脚本式文件移出 `testpaths`（或改名去 `test_` 前缀 / 移入 `scripts/`），并给带顶层副作用的脚本补 `if __name__ == "__main__":` 保护，可将全量收集时间从 170s 大幅压缩并消除副作用。
- 清理 `test_*_v2.py` / `test_*2.py` / `test_v17_*` 等版本迭代遗留文件，明确保留版本。
- 安装 pytest-cov，建立覆盖率基线，让 fail_under=60 真正生效。
