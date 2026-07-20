# F6 优化设计书 — 批量音频导入

> **模块**: F6 — 处理后音频导入 AE
> **优先级**: 🟢 P2
> **日期**: 2026-06-05

## 变更摘要

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| Logger 加载 | 15 行重复 | 3 行 ModuleLoader |
| 批量导入 | 不支持 | `F6_dispatch('importBatch', {files: [...]})` |
| CEP 接口 | 无 | `F6_dispatch('import'/'importAndAdd'/'replaceSource'/'importBatch')` |
