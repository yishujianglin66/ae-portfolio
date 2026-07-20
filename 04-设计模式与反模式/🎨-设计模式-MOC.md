---
tags: [MOC, 设计模式, 反模式]
---

# 设计模式与反模式

从 ae-vocal-remover 项目实战中提炼的 AE 插件开发最佳实践。

## 设计模式（10 个核心模式）

详见 [[design-patterns]]，按星级（1-5★）评定：

| 模式 | 星级 | 用途 |
|------|------|------|
| Poll Manager | ★★★★★ | 非阻塞异步轮询 |
| Bridge Protocol | ★★★★★ | OK/ERROR/PROGRESS token 通信 |
| Composite Module Loading | ★★★★ | try-catch $.evalFile + 命名空间合并 |
| Dual-Engine Fallback | ★★★★ | Demucs vs FFmpeg 双引擎降级 |
| ...共 10 个 | | |

## 反模式（14 个已记录）

详见 [[anti-patterns]]，按严重程度分级：

| 编号 | 严重度 | 问题 |
|------|--------|------|
| A1 | CRITICAL | STATE.outDir 竞态条件 |
| A2 | CRITICAL | confirm() 在 CEP 中不可用 |
| A3 | CRITICAL | Tab 3/4/5 缺少异步轮询 |
| A4 | CRITICAL | 同步 system.callSystem 阻塞 AE |
| ...共 14 个 | | |

## 效率提升

- [[snippet-productivity]] — 21 个代码片段，平均效率提升 78.6%，每天节省约 14 分钟

## 文档关系

- [[编码规范]] 定义规则 → [[anti-patterns]] 展示违规 → [[design-patterns]] 提供正确方案
- [[PHASE1_MAIN_REPORT]] 是原始分析 → 本目录是提炼后的精华

---

> 返回 → [[🏠-AE知识中心]]
