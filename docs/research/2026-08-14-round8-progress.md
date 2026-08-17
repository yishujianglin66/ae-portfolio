# 2026-08-14 移交清单推进报告（第 8 轮）

> 承接 round-7 残余：统一画像接入选材、llm_gateway/unified_pipeline 拆分、
> use_beatnet 真机验证。

## ① 素材统一画像接入选材链路 ✅

- `ProductionDirector._load_atmosphere_annotations()` 升级：优先读
  `data/material_tags/unified_tags.json`（三源融合画像），回退散落标注。
- 报告 `material_attribution` 新增 `atmosphere` / `energy` / `content`
  三字段（64 素材画像可用）；27 测试回归通过。

## ② llm_gateway 第二批拆分 ✅（4607 → 4028 行）

- `core/thinking_upgrade_policy.py`（580 行）：ThinkingUpgradePolicy +
  chat_with_thinking_upgrade + ThinkingBudget/Trace/Round/Decision 入口。
- 循环导入治理：TaskType 经 `_TASK_TYPE_QUALITY_REVIEW()` 惰性解析，
  宿主符号（ModelTier/TASK_TIER_MAP/Thinking*）在模块底部导入
  （两种加载路径均验证安全）。
- 向后兼容：`from core.llm_gateway import ThinkingUpgradePolicy,
  chat_with_thinking_upgrade` 不变；**83 测试通过**。

## ③ unified_pipeline 拆分 ✅（5824 → 5388 行）

- `pipeline/adaptive_fallback.py`（437 行）：AdaptiveFallbackSelector +
  get_fallback_selector 单例；re-export 保持向后兼容。

## ④ use_beatnet 真机验证 ✅

- `render(use_beatnet=True)` 端到端跑通（成片 19s / quality 81.3）：
  报告 `metadata.beatnet_fusion` 完整写入——
  tempo 99.4 vs 100.0 BPM（差 0.6%，**一致**）、对齐率 62.5%（20/32 拍
  对齐 BeatNet 网格）、6 个下拍继承；Phase 1 日志打印三级信号摘要。
- material_attribution 三字段画像（atmosphere/energy/content）同步生效。

## 提交记录（本轮 2 个）

统一画像接入 | 双上帝文件拆分 + 修复。

## 下一步

1. UnifiedPipeline 主类 4799 行继续分区（perceive/execute/render 方法组）
2. 统一画像 → material_selection 决策（内容标签驱动选材）
3. UXP 面板骨架 / Docker 环境（外部依赖）
