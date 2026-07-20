# F2 优化设计书 — Animator API 去重 + CEP 集成

> **模块**: F2 — 文字图层基础动画应用
> **优先级**: 🟡 P1
> **日期**: 2026-06-05

## 变更摘要

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| Logger 加载 | 50 行重复+回退 | 3 行 ModuleLoader |
| Animator API | 127 行内联 | 调用共享 AnimatorAPI (回退兼容) |
| CEP 接口 | 无 | `F2_dispatch('apply'/'listAnims')` |
| CONFIG | 仅硬编码 | params 参数覆盖支持 |

## 关键改动

1. **Logger 去重**: `AEStudioKit.Loader.loadLogger(scriptDir)` 替代 50 行重复
2. **Animator API**: 优先调用 `AnimAPI.addAnimator()` 等, 不可用时回退
3. **CEP dispatch**: `F2_dispatch('apply', {animationType, duration, intensity})`
4. **列表查询**: `F2_dispatch('listAnims')` 返回可用动画类型

## 兼容性

- ✅ ES3 语法完整保留
- ✅ 独立运行 (AnimAPI 不可用时自动回退)
- ✅ 向后兼容 (CONFIG 硬编码仍有效)
