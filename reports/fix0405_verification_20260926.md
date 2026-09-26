# FIX-04 / FIX-05 执行验证记录（伪造成功切断包 · 第二轮）

- 日期：2026-09-26（起始 HEAD `05ffc7d`；期间并行线持续活跃，全程定向操作）
- 方案出处：`09-计划文件/2026-09-26_全量问题修复执行方案.md` FIX-04 / FIX-05（审计 F4/F6）
- 判定：**FIX-04 READY｜FIX-05 READY**（全部真实执行验证）

## 1. FIX-04 — `core/multimodal_fusion_hub.py` 随机特征决策切断

| 变更 | 内容 |
|---|---|
| `_extract_from_video` / `_extract_from_images` | 文件大小启发式+随机嵌入路径 `available=True`→**False** + confidence 0.0 + docstring 记录 F4 背景与真实替代链路（models/ CNN） |
| `_extract_from_file`(audio) | bpm=120 常量+正弦式伪造 → available=False |
| visual/audio `extract()` 分发器 | 不再无条件覆盖 available=True；仅子路径真实计算（array 像素/信号路径）才放行——**真实轻计算路径不受损** |
| `get_fusion_hub` | 文件尾部 **3 份逐字重复 def**（后定义静默覆盖）去重为 1 |
| 融合层门控核验 | L723-841 本已按 `.available` 过滤模态并处理全不可用情形——标记 False 即真实退出决策；唯一消费端 `pipeline/unified_pipeline.py:2106`（try/except graceful，text 模态真实计算仍可用） |

## 2. FIX-05 — Mock 占位片入池封堵

| 变更 | 内容 |
|---|---|
| `ai/aigc_generator.py::MockAIGCAdapter` | `is_available()` 恒 True → **默认 False**，仅 `AEKV_AIGC_ALLOW_MOCK=1` 显式开启；禁用态 generate 不落盘、返回 success=False；开启态结果也永远带 `execution_path="simulated"`；修正注释错字"兆底" |
| `ai/ai_director.py` | 新增模块级 `_is_trusted_material_result()`（拒 success 无路径/source=="Mock"/simulated；历史未标记者暂按 real 兼容，注释写明由 FIX-09 收敛）；AIGC 素材入池循环改用该白名单，拒收时打 WARN 日志不再静默 |

## 3. 测试证据（真实输出）

```powershell
# 新增行为锁死测试（13 例：fake→unavailable / array 真路径仍流通 / Mock opt-in / 白名单值断言 / 去重守卫）
$ pytest tests/test_fake_success_packs_fix0405.py -q
# 既有相关套件回归（含被改写的 safety 测试）
$ pytest tests/test_fake_success_packs_fix0405.py tests/test_aigc_generator_safety.py tests/test_multimodal_fusion_hub.py tests/test_pro_upgrade.py -q --timeout=300
50 passed in 8.04s

$ ruff check --config ruff.toml ai/aigc_generator.py ai/ai_director.py core/multimodal_fusion_hub.py tests/...
All checks passed!
```

## 4. 过程中如实处理的三件事

1. **"测试锁桩"实锤并纠正**（矛盾 8/D5 的活案例）：`test_aigc_generator_safety.py` 原以
   `is_available() is True` 与注释"Mock 必须常备——无 key 兜底通道"钉住 F6 旧行为。
   已按新契约**加强**改写（默认 False + 禁用不落盘 + 开启也标 simulated），未删除任何检查。
2. **既有收集脆弱点上报**：`tests/test_real_e2e_all_modules.py` 收集期断言本地素材
   （`tests/data/real_amv_test` MP4=0 → Interrupted）。已用 `git stash` 在 HEAD 基线复现同错，
   **确证预存、与本包无关**；正是 FIX-16（conftest 治理）第 42 个候选，建议其模块级检查改 `pytest.skip`。
3. **写盘字符劣化自查**：编辑后扫描发现测试注释出现"兕底"劣化（2 处），已定点修复并
   程序化校验（U+5155 计数=0）；呼应 T1/GBK 编码族风险。

## 5. 行为变更影响（预期内）

- 无 API key 环境：`generate_supplementary` 不再自动产出蓝色占位片（返回空列表 + ERROR 日志），
  ai_director 素材池不再混入 Mock——演示需显式 `AEKV_AIGC_ALLOW_MOCK=1`。
- unified_pipeline analyze 阶段：video/audio 文件路径不再贡献融合权重（text 模态照常），
  全模态不可用时 graceful 返回 None——消除的是"随机数带 0.7 置信度参与剪辑决策"。
- 回退：单提交 revert 即可；未触碰并行线文件（`shot_graph*`/`data/*` 等仍在对方工作流中）。

## 6. 复跑指令

```powershell
cd C:\Users\Administrator\Desktop\AE-Knowledge-Vault
.venv\Scripts\python.exe -m pytest tests/test_fake_success_packs_fix0405.py tests/test_aigc_generator_safety.py tests/test_multimodal_fusion_hub.py -q --timeout=300 -p no:cacheprovider
```
