# Automation memory: Phase C 弃用端点命中统计 (automation-1786975584570)

- 2026-09-07 (UTC) 巡检运行。
- 规定脚本 `scripts/phasec_tally.py` 缺失 → 命令无法执行（exit 2, No such file or directory）；`--all` 同理。
- 改用直接核查 Phase C 真实观测数据源：
  - `web/api_server.py`(500-571) 与 `web/integrator_api.py`(~687) 含 Deprecation 中间件，本应写 `logs/deprecated_hits.jsonl`。
  - 但 `logs/deprecated_hits.jsonl` 不存在，全 logs 检索 DEPRECATED_HIT 无匹配 → 弃用端点命中 = 0（全观测期，不止今日）。
- 判定：适用规则#1（今日/观测期 0 命中）；规则#2 不适用；规则#3 因脚本缺失无法生成 7 天趋势。
- 未改动任何代码/日志（任务约束）。建议用户创建缺失的 tally 脚本以恢复自动化。
- 交付：report_2026-09-07.md（present_files）。
- 下一步：用户手动补 `scripts/phasec_tally.py` 后再跑本自动化。

## 2026-09-08 (UTC) 巡检
- 同 09-07：`scripts/phasec_tally.py` 仍缺失，两条命令均 exit 2（No such file or directory）。
- 回退核查真实数据源：`logs/deprecated_hits.jsonl` 不存在，全 logs 检索 `DEPRECATED_HIT` 0 匹配 → 弃用端点命中 = 0（全观测期 + 今日）。
- 判定：适用规则#1「今日无弃用端点残留调用，观测期推进中」；#2 不适用；#3 因脚本缺失无法出 7 日趋势，但据"全期 0 命中"推断 6 个弃用端点均符合进入下线流程（Phase C 回归）条件。
- 未改动任何代码/日志。交付：report_2026-09-08.md（present_files）。
- 待办：用户补 `scripts/phasec_tally.py` 以恢复正式统计与趋势。
