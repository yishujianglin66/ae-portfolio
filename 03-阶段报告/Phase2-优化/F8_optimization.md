# F8 优化设计书 — 动态路径检测

> **模块**: F8 — Topaz Video AI 安装检测
> **优先级**: 🟢 P2
> **日期**: 2026-06-05

## 变更摘要

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| Logger 加载 | 15 行重复 | 3 行 ModuleLoader |
| 搜索路径 | 硬编码 C:/D: | 动态系统盘 + D/E/F 遍历 |
| 自定义路径 | 不支持 | `F8_SEARCH_PATHS` 外部注入 |
| CEP 接口 | 无 | `F8_dispatch('detect', {customPaths})` |
