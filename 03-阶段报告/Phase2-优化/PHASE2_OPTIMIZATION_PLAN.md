# 第二阶段：F1-F8 原子模块优化计划

> **项目**: AE 扩展原子模块性能升级、面板集成与工程优化
> **阶段**: 第二阶段 — 原子模块优化
> **日期**: 2026-06-05
> **版本**: v1.0
> **基于**: 第一阶段遗产剖析 (55 文件, 24 设计模式, 37 反模式, 28 可复用资产)

---

## 执行摘要

第二阶段基于第一阶段识别的 37 个反模式和 28 个可复用资产，对 F1-F8 共 8 个原子功能单元进行系统性优化。优化分两个层面：

1. **跨模块共享基础设施** — 消除 6× 代码重复
2. **逐模块专项优化** — 异步化、模块化、CEP 集成

---

## 一、全局共享基础设施优化

### 1.1 新增共享模块

| # | 模块文件 | 消除重复 | 节省行数 |
|---|---------|----------|----------|
| G1 | `_shared/AEStudioKit_ModuleLoader.jsx` | Logger 加载 6× → 1× | ~108 行 |
| G2 | `_shared/AEStudioKit_AnimatorAPI.jsx` | Animator API 3× → 1× | ~120 行 |
| G3 | `_shared/AEStudioKit_JSON.jsx` | JSON polyfill 3× → 1× | ~150 行 |

### 1.2 优化前后对比

```
优化前:
  F1: 18行 Logger加载 + 自己的_safeGet
  F2: 50行 Logger加载/回退 + 127行 Animator API
  F3: 95行 JSON polyfill + 15行 Logger加载 + 53行 Animator API (重复!)
  F4: 15行 Logger加载
  F6: 15行 Logger加载
  F7: 15行 Logger加载
  F8: 15行 Logger加载
  重复总计: ~378 行 (占 F 模块总代码 ~15%)

优化后:
  所有模块: 3行 ModuleLoader 调用
  F2/F3: 3行 AnimatorAPI 调用
  F3: 1行 JSON polyfill 调用
  重复: 0 行
  净节省: ~350 行
```

---

## 二、F 模块逐项优化计划

### 优先级矩阵

| 优先级 | 模块 | 关键问题 | 风险 |
|--------|------|----------|------|
| 🔴 P0 | F4 — 音频提取 | AP-001 同步阻塞 (5-30s) | AE UI 冻结 |
| 🔴 P0 | F7 — 文件下载 | AP-001 同步阻塞 (10s-5min) | AE UI 冻结 |
| 🟡 P1 | F2 — 文字动画 | Animator API 重复、无 CEP 接口 | 维护成本 |
| 🟡 P1 | F3 — 预设文件 | JSON polyfill 重复、无缓动支持 | 功能缺陷 |
| 🟡 P1 | F5 — 人声分离 | 无进度回调、ffprobe 重复调用 | CEP 集成困难 |
| 🟢 P2 | F1 — 图层识别 | Logger 重复、硬编码路径 | 低 |
| 🟢 P2 | F6 — 音频导入 | Logger 重复、无批量导入 | 低 |
| 🟢 P2 | F8 — Topaz 检测 | 同步阻塞 (2-5s)、硬编码路径 | 低 |

---

## 三、逐模块优化规格

### F1 — 图层类型识别 (P2)

| 维度 | 当前状态 | 优化目标 |
|------|----------|----------|
| Logger 加载 | 18 行重复模式 | → 3 行 ModuleLoader |
| 硬编码路径 | `Folder.desktop` | → `Folder.temp` 降级 |
| CEP 接口 | 无 | → 添加 `F1.dispatch()` |
| `_detectAudio` | `.wav` 重复出现 | → 修正数组去重 |
| 代码行数 | 583 | → ~500 (净减 ~80) |

### F2 — 文字动画 (P1)

| 维度 | 当前状态 | 优化目标 |
|------|----------|----------|
| Logger 加载 | 50 行重复模式+回退 | → 3 行 ModuleLoader |
| Animator API | 127 行内联 | → 调用共享 AnimatorAPI |
| 动画注册表 | 硬编码 3 种 | → 外部可扩展 |
| CEP 接口 | 无 | → 添加 `F2.dispatch()` |
| CONFIG 配置 | 脚本内硬编码 | → 支持参数传入 |
| 代码行数 | 587 | → ~350 (净减 ~237) |

### F3 — 预设文件 (P1)

| 维度 | 当前状态 | 优化目标 |
|------|----------|----------|
| JSON polyfill | 95 行内联 | → 1 行加载共享模块 |
| Animator API | 53 行重复 F2 | → 调用共享 AnimatorAPI |
| 关键帧缓动 | 不支持 | → 预设 JSON 支持 easeIn/easeOut |
| Logger 加载 | 15 行重复 | → 3 行 ModuleLoader |
| CEP 接口 | 无 | → 添加 `F3.dispatch()` |
| 代码行数 | 487 | → ~250 (净减 ~237) |

### F4 — 音频提取 (P0) 🔴

| 维度 | 当前状态 | 优化目标 |
|------|----------|----------|
| **AP-001** | **同步 system.callSystem()** | → Submit-Poll-Complete 异步 |
| FFmpeg 查找 | 内联 findFFmpeg() | → 调用共享 FFmpegLocator |
| Logger 加载 | 15 行重复 | → 3 行 ModuleLoader |
| 输出路径 | 硬编码 Desktop | → 可配置 outputDir |
| CEP 接口 | 无 | → 添加 `F4.dispatch()` |
| **新增** | — | → 进度回调 + 取消支持 |
| 代码行数 | 301 | → ~250 (重构 +60, 删重复 -110) |

### F5 — 人声分离 (P1)

| 维度 | 当前状态 | 优化目标 |
|------|----------|----------|
| ffprobe 调用 | validate_input + is_stereo 各调一次 | → 缓存检测结果 |
| 进度报告 | 无 | → 添加 tqdm/回调钩子 |
| CEP 桥接 | 无 async 接口 | → 添加 `--job-id` + `--check` 模式 |
| 日志路径 | 硬编码 Desktop | → 可配置 LOG_PATH |
| 代码行数 | 487 | → ~520 (新增 async 模式 +50) |

### F6 — 音频导入 (P2)

| 维度 | 当前状态 | 优化目标 |
|------|----------|----------|
| Logger 加载 | 15 行重复 | → 3 行 ModuleLoader |
| 批量导入 | 仅单文件 | → 支持文件数组 |
| F5 耦合 | 硬编码假设 F5 输出路径 | → 解耦, 参数化 |
| CEP 接口 | 无 | → 添加 `F6.dispatch()` |
| 代码行数 | 193 | → ~180 |

### F7 — 文件下载 (P0) 🔴

| 维度 | 当前状态 | 优化目标 |
|------|----------|----------|
| **AP-001** | **同步 system.callSystem()** | → 异步下载 (PowerShell job) |
| 下载工具 | detectDownloader() 内联 | → 提取为共享函数 |
| Logger 加载 | 15 行重复 | → 3 行 ModuleLoader |
| 进度显示 | 无 | → PowerShell Write-Progress |
| CEP 接口 | 无 | → 添加 `F7.dispatch()` |
| 代码行数 | 197 | → ~230 (新增 async +40) |

### F8 — Topaz 检测 (P2)

| 维度 | 当前状态 | 优化目标 |
|------|----------|----------|
| system.callSystem() | 同步 2-5s 阻塞 | → 异步 PowerShell |
| 硬编码路径 | C:/Program Files, D:/top | → 注册表查询 + PATH 扫描 |
| Logger 加载 | 15 行重复 | → 3 行 ModuleLoader |
| CEP 接口 | 无 | → 添加 `F8.dispatch()` |
| 代码行数 | 171 | → ~170 |

---

## 四、实施路线

### 第一轮：共享基础设施建设 ✅

- [x] G1: `AEStudioKit_ModuleLoader.jsx` — 统一模块加载器
- [x] G2: `AEStudioKit_AnimatorAPI.jsx` — Text Animator 封装
- [x] G3: `AEStudioKit_JSON.jsx` — JSON polyfill

### 第二轮：P0 关键修复 (本阶段)

- [ ] F4: 异步音频提取 (消除 AP-001 阻塞)
- [ ] F7: 异步文件下载 (消除 AP-001 阻塞)

### 第三轮：P1 重要优化

- [ ] F2: Animator API 去重 + CEP 接口
- [ ] F3: JSON polyfill 去重 + 缓动支持
- [ ] F5: 进度回调 + CEP 桥接

### 第四轮：P2 收尾

- [ ] F1: Logger 去重 + CEP 接口
- [ ] F6: Logger 去重 + 批量导入
- [ ] F8: 异步检测 + 路径动态化

---

## 五、优化度量目标

| 指标 | 优化前 | 优化后目标 |
|------|--------|-----------|
| 代码重复行数 | ~378 行 | 0 行 |
| 同步阻塞点 | 3 (F4/F7/F8) | 0 |
| CEP 集成接口 | 0 个模块 | 8 个模块 |
| 硬编码路径 | ~12 处 | ≤2 处 (仅回退) |
| F 模块总行数 | ~2,500 | ~2,100 |
| ESLint/ES3 合规 | 100% | 100% (保持) |

---

## 六、交付物索引

| 文档 | 路径 | 说明 |
|------|------|------|
| 本计划 | `docs/phase2/PHASE2_OPTIMIZATION_PLAN.md` | 优化计划 (当前文件) |
| F4 优化设计书 | `docs/phase2/F4_optimization.md` | 异步音频提取 |
| F7 优化设计书 | `docs/phase2/F7_optimization.md` | 异步文件下载 |
| F2 优化设计书 | `docs/phase2/F2_optimization.md` | Animator API 去重 |
| F3 优化设计书 | `docs/phase2/F3_optimization.md` | 预设系统升级 |
| F5 优化设计书 | `docs/phase2/F5_optimization.md` | CEP 桥接 |
| F1 优化设计书 | `docs/phase2/F1_optimization.md` | 图层识别升级 |
| F6 优化设计书 | `docs/phase2/F6_optimization.md` | 批量导入 |
| F8 优化设计书 | `docs/phase2/F8_optimization.md` | 动态检测 |

---
**第二阶段进行中 — 共享基础设施已完成，进入逐模块优化。**
