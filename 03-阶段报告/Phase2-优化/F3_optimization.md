# F3 优化设计书 — 预设文件系统升级

> **模块**: F3 — JSON 预设文件驱动动画
> **优先级**: 🟡 P1
> **日期**: 2026-06-05

## 变更摘要

| 维度 | 优化前 | 优化后 |
|------|--------|--------|
| JSON polyfill | 95 行内联 (3× 重复) | 1 行加载共享模块 |
| Animator API | 53 行重复 F2 | 调用共享 AnimatorAPI |
| 关键帧缓动 | 不支持 | ✅ easeIn/easeOut 支持 |
| Logger 加载 | 15 行重复 | 3 行 ModuleLoader |
| CEP 接口 | 无 | `F3_dispatch('apply'/'applyFromJSON')` |

## 关键改动

1. **JSON polyfill 去重**: 加载 `_shared/AEStudioKit_JSON.jsx`
2. **缓动支持**: `preset.animators[].selector.keyframes.start[].easeIn/easeOut`
3. **直接 JSON 应用**: `F3_dispatch('applyFromJSON', {preset: {...}})` 跳过文件读取
4. **Animator API 复用**: 同 F2 的共享模块调用模式

## 预设 JSON 格式 v2

```json
{
  "name": "fadeIn",
  "duration": 1.0,
  "animators": [{
    "selector": {
      "mode": 1,
      "smoothness": 40,
      "keyframes": {
        "start": [
          {"time": 0, "value": 0},
          {"time": 1, "value": 100, "easeIn": [0, 33.33], "easeOut": [0, 33.33]}
        ]
      }
    },
    "properties": [{"matchName": "ADBE Text Opacity", "value": 0}]
  }]
}
```
