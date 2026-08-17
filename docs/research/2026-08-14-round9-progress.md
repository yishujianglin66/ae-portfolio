# 2026-08-14 移交清单推进报告（第 9 轮）

> 承接 round-8 残余：画像驱动选材、UnifiedPipeline 继续分区、
> 全量回归复测、累计状态文档。

## ① 画像驱动选材决策 ✅

- 自由混剪分支新增 1.4b/1.4c：统一画像 `content=not_painting`（教程录屏）
  移入 excluded 桶（可观测不硬阻断）；theme 含燃/战斗时燃向/战斗氛围
  素材前置排序。画像从"报告字段"升级为"决策输入"。
- 逻辑单测 + 39 回归通过。

## ② UnifiedPipeline 继续分区 ✅

- `pipeline/unified_pipeline_verify.py`：`_run_verify` 方法体（255 行）
  提取为 `run_verify(self)` 模块函数，原方法薄委托；
  unified_pipeline 5394 → 5140 行；相关测试 84 通过。

## ③ 全量回归复测 ⚠️（发现标记债务）

- 定向套件 9 轮累计 400+ 用例全绿；覆盖率 77.58%。
- 全量单跑实测受阻：`test_opensource_e2e{,_v2}`（whisper 真实下载）、
  `test_v17_full_pipeline`、`test_p1_transition_e2e`（真实渲染）等
  **未标记真实执行测试**导致 30s 超时挂起——审计"标记债务"的实证。
  已记录为下一测试工程项（批量补 marker 即可恢复全量绿跑）。

## ④ 累计状态文档 ✅

- `docs/research/2026-08-14-cumulative-status.md`：九轮全景
  （感知/决策/工程三线成果 + 剩余项移交 + 协作纪要 + 回归基线）。

## 提交记录（本轮 4 个）

画像选材 | verify 拆分 | 累计状态文档 ×2（含回归基线修订）。

## 下一步

1. **测试标记债务批量修复**：给未标记真实执行测试补
   slow/integration/real_* marker（全量绿跑的前置）
2. UnifiedPipeline 剩余大方法（_run_execute_real_mix 545 行等）按
   run_verify(self) 模式继续拆
3. 画像驱动选材深化（content 标签进 IP 匹配/叙事角色）
4. UXP 面板 / Docker（外部依赖）
