# FIX-05 欠账清偿 D-3（全 Mock 场景端到端入池断言）

- 日期：2026-09-26｜项：方案 FIX-05（审计 F6/R2）｜状态：部分完成 → **READY（附一项明示挂账）**
- 前序：opt-in + 白名单单元级已在 `8ed5e08`；全仓回归在 `3ad4554`（D-1）

## 本项动作（行为不变的"可测化"重构，非新逻辑）

| 变更 | 说明 |
|---|---|
| `ai/ai_director.py` 抽出 `_ingest_aigc_results(aigc_results, material_files) -> (accepted, rejected)` | 原 Step4 内联循环逐字迁移（日志文案不变），返回值供断言；调用点单行替换 |
| `tests/test_fake_success_packs_fix0405.py` 追加 `TestAigcIngestEndToEnd` 2 例 | ① 全 Mock 结果（含旧行为下必然入池的 success=True+path 形态）→ 断言 `files==[]`、(0,2)；② 真源与 Mock 混合 → (1,1) 且仅真源入池（不误伤） |

## 真实验证输出

```powershell
$ .venv\Scripts\python.exe -m pytest tests/test_fake_success_packs_fix0405.py tests/test_aigc_generator_safety.py tests/test_auto_produce_honest_exit.py -q
53 passed in 4.93s
# ai_director 消费面全量（grep 证实仅两处引用）：
$ .venv\Scripts\python.exe -m pytest tests/test_pro_upgrade.py tests/test_fake_success_packs_fix0405.py -q
15 passed in 4.66s
$ .venv\Scripts\python.exe -m ruff check --config ruff.toml ai/ai_director.py tests/test_fake_success_packs_fix0405.py
All checks passed!
```

## FIX-05 验收栏终对账

- ① Mock 改降级语义 ✅（D-前）；② 消费端白名单 ✅；③ **端到端"Mock 永不进 material_files"断言 ✅（本次）**；
  ④ "真实 run 一条验证报告字段核验"——**明示挂账**：需一次真实出片（含 AIGC 触发路径），随下一次真 run 补验并回写本节；
  在此之前 FIX-05 判定为 READY(挂①项)。诚实边界：本断言覆盖"入池循环节"，未覆盖 `collect_materials` 全部署
  （其前置 LLM/搜索步骤与本缺陷无关且依赖外部服务，属过度 mock 区，不造覆盖假象）。
- 注：本次重构未跑全仓回归——影响域经 grep 证实仅 2 个测试消费者（15 passed 全覆盖）；
  下次全仓回归将随 FIX-03 批结束统一执行并在此登记。
