# 2026-08-14 移交清单推进报告（第 11 轮）

> 承接 round-10 剩余：UnifiedPipeline 大方法续拆、画像选材深化、回归收尾。

## ① UnifiedPipeline 三方法批量拆分 ✅

- `pipeline/unified_pipeline_helpers.py`（901 行）：
  `run_learn(self)`（369 行）+ `build_effect_stack_from_vrs(self, ...)`
  （354 行）+ `run_stage(self, ...)`（178 行）。
- unified_pipeline **4607 → 3709 行**；累计 **5824 → 3709（拆出 2115 行）**，
  六大方法全部薄委托化。
- 修复批量拆分脚本的**行号漂移 bug**（低行号先替换导致后续区间错位 →
  改为高行号→低行号应用），及两处模块导入缺失（time / StageResult+StageStatus
  底部导入）。
- 相关测试 75/75 全绿。

## ② 画像驱动选材深化 ✅

- `_pick_by_narrative_role` 接入统一画像排序：角色氛围命中
  （爆发→燃向/战斗、收尾→抒情/治愈 等）前置，content=not_painting
  （教程录屏）垫底；画像单次加载缓存避免逐段读盘。
- 61 测试回归通过。

## ③ 全量回归（见运行结果）

- 预期保持 4952+ 全绿基线。

## 提交记录（本轮 4 个）

helpers 拆分 | time 导入修复 | StageResult/StageStatus 底部导入 |
画像角色排序。

## 下一步

1. UnifiedPipeline 主类（3709 行）继续审视剩余可拆区
2. content 标签进 IP 匹配（target_ip 模式同样排除教程录屏）
3. UXP 面板 / Docker（外部依赖）
