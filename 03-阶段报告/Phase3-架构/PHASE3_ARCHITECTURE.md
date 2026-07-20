# Phase 3 Architecture — 统一操作面板开发

> **项目**: AE StudioKit Enterprise Upgrade  
> **阶段**: 第三阶段  
> **日期**: 2026-06-05  
> **状态**: ✅ 实现完成  
> **产出**: 架构设计文档 + CEP 面板代码

---

## 1. 概述

Phase 3 创建一个统一的 CEP 操作面板，集成 Phase 2 完成的 8 个原子功能模块（F1-F8）。面板作为 AE 扩展的第二个入口（"AE StudioKit - Studio Kit"），与生产环境的 12 标签主面板并存，共享同一个 ExtendScript 后端。

### 1.1 目标

| 目标 | 描述 |
|------|------|
| 统一入口 | 一个面板操作所有 8 个 F 模块 |
| 双模支持 | 同步模块即时返回，异步模块 Submit-Poll-Complete |
| 零侵入 | 不修改生产面板，通过第二 DispatchInfo 共存 |
| 可测试 | 每个模块独立标签，独立运行，独立结果显示 |

### 1.2 非目标

- 不替换或重构现有的 12 标签生产面板
- 不改变 F 模块的核心功能逻辑
- 不引入新的构建系统或依赖

---

## 2. 架构设计

### 2.1 四层架构

```
┌─────────────────────────────────────────────────────────────┐
│  L1: CEP Panel (client/studio-kit/)                        │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  index.html  — 8-tab UI (F1-F8)                     │  │
│  │  studio-kit.js — Panel logic, aeCall, PollManager    │  │
│  │  + ../style.css (共享主题)                           │  │
│  │  + ../CSInterface.js (CEP polyfill)                 │  │
│  │  + ../poll-manager.js (异步轮询)                     │  │
│  └──────────────┬───────────────────────────────────────┘  │
│                 │ CSInterface.evalScript()                  │
│                 │ "AEStudioKit.dispatch('studioKit', ...)"  │
├─────────────────┼───────────────────────────────────────────┤
│  L2: Dispatcher (host/index.jsx)                           │
│  ┌──────────────┴──────────────────────────────────────┐  │
│  │  AEStudioKit.dispatch("studioKit", params)          │  │
│  │    → studioKitDispatch(module, action, params)       │  │
│  └──────────────┬───────────────────────────────────────┘  │
├─────────────────┼───────────────────────────────────────────┤
│  L3: Bridge (host/studio-kit-bridge.jsx)                   │
│  ┌──────────────┴──────────────────────────────────────┐  │
│  │  加载 7 个 JSX 模块 (F1-F4, F6-F8)                 │  │
│  │  包装 F5 Python CLI                                  │  │
│  │  studioKitDispatch("F1", "classify", {}) → JSON     │  │
│  └──────────────┬───────────────────────────────────────┘  │
├─────────────────┼───────────────────────────────────────────┤
│  L4: F Modules (test-suites/F*-*/*.jsx)                    │
│  ┌──────────────┴──────────────────────────────────────┐  │
│  │  F#_dispatch(action, params) → {success, data}       │  │
│  │  $.global.F#_dispatch = F#_dispatch (export)        │  │
│  │  _STUDIO_KIT_SKIP_RUN guard (skip auto-exec)        │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 通信协议

```
Panel                    ExtendScript                  F Module
  │                          │                            │
  │  aeCall('studioKit',     │                            │
  │    {module:'F1',         │                            │
  │     action:'classify',   │                            │
  │     params:{}})          │                            │
  │─────────────────────────►│                            │
  │                          │ studioKitDispatch(         │
  │                          │   'F1','classify',{})      │
  │                          │───────────────────────────►│
  │                          │                            │ F1_dispatch(
  │                          │                            │   'classify',{})
  │                          │                            │──→ runF1...
  │                          │          {success:true,    │
  │                          │           layerCount:5,    │
  │                          │           results:[...]}   │
  │                          │◄───────────────────────────│
  │                          │ JSON.stringify({           │
  │                          │   success:true,            │
  │                          │   data:{layerCount:5,...}  │
  │                          │ })                         │
  │  {success:true,          │                            │
  │   data:{layerCount:5,    │                            │
  │   results:[...]}}        │                            │
  │◄─────────────────────────│                            │
```

### 2.3 模块加载策略

**问题**: F 模块使用 IIFE 包装，内部定义的 `F#_dispatch` 函数在 IIFE 执行后不可从外部访问。同时，IIFE 会自动执行模块的主逻辑（如 `runF1LayerTypeDetection()`），产生副作用。

**解决方案**: 双重改造

1. **全局导出**: 在每个 IIFE 内部添加 `$.global.F#_dispatch = F#_dispatch;`
2. **执行守卫**: 将自动执行逻辑包裹在 `if (typeof $.global._STUDIO_KIT_SKIP_RUN === 'undefined')` 中
3. **Bridge 设置标志**: 加载前设置 `$.global._STUDIO_KIT_SKIP_RUN = true`

```javascript
// bridge 加载前
$.global._STUDIO_KIT_SKIP_RUN = true;

// 加载 F1 — IIFE 执行但跳过 auto-run
$.evalFile('test-suites/F1-layer-type/F1_layer_type.jsx');
// F1_dispatch 现在可通过 $.global.F1_dispatch 访问

// 独立运行时 — 标志未定义, auto-run 正常执行
```

---

## 3. 文件清单

### 3.1 新增文件

| 文件 | 行数 | 用途 |
|------|------|------|
| `host/studio-kit-bridge.jsx` | ~290 | F1-F8 统一调度桥接层 |
| `client/studio-kit/index.html` | ~340 | 8 标签面板 UI |
| `client/studio-kit/studio-kit.js` | ~450 | 面板逻辑 (aeCall, PollManager, tab切换) |
| `docs/phase3/PHASE3_ARCHITECTURE.md` | 本文档 | 架构设计文档 |

### 3.2 修改文件

| 文件 | 修改内容 | 变化量 |
|------|----------|--------|
| `CSXS/manifest.xml` | 添加第二 `<DispatchInfo>`: "AE StudioKit - Studio Kit" | +22 行 |
| `host/index.jsx` | 加载 bridge + 添加 `studioKit` dispatch case | +12 行 |
| `test-suites/F1-layer-type/F1_layer_type.jsx` | 添加 `$.global.F1_dispatch` 导出 + `_STUDIO_KIT_SKIP_RUN` 守卫 | +8 行 |
| `test-suites/F2-text-anim/F2_text_anim.jsx` | 添加 `$.global.F2_dispatch` 导出 + `_STUDIO_KIT_SKIP_RUN` 守卫 | +8 行 |
| `test-suites/F3-preset-file/F3_apply_preset.jsx` | 添加 `$.global.F3_dispatch` 导出 + `_STUDIO_KIT_SKIP_RUN` 守卫 | +8 行 |
| `test-suites/F4-audio-extract/F4_extract_audio.jsx` | 添加 `$.global.F4_dispatch` 导出 + `_STUDIO_KIT_SKIP_RUN` 守卫 | +8 行 |
| `test-suites/F6-import-audio/F6_import_audio.jsx` | 添加 `$.global.F6_dispatch` 导出 + `_STUDIO_KIT_SKIP_RUN` 守卫 | +8 行 |
| `test-suites/F7-download/F7_download.jsx` | 添加 `$.global.F7_dispatch` 导出 + `_STUDIO_KIT_SKIP_RUN` 守卫 | +8 行 |
| `test-suites/F8-topaz-detect/F8_topaz_detect.jsx` | 添加 `$.global.F8_dispatch` 导出 + `_STUDIO_KIT_SKIP_RUN` 守卫 | +8 行 |

---

## 4. 面板 UI 设计

### 4.1 布局

```
┌──────────────────────────────────┐
│  AE StudioKit PHASE 3    ● Ready │  ← 顶部状态栏
├──────────────────────────────────┤
│ F1 图层 │ F2 动画 │ F3 预设 │... │  ← 8 标签导航
├──────────────────────────────────┤
│                                  │
│  ┌────────────────────────────┐  │
│  │ F# 模块名称                │  │  ← 功能卡片
│  │ 描述文本                   │  │
│  │ [参数输入区]               │  │
│  │ [运行按钮]                 │  │
│  │ ▓▓▓▓▓▓▓▓▓░░░░ 45%        │  │  ← 进度条 (async)
│  │ { JSON 结果 }              │  │  ← 结果区
│  └────────────────────────────┘  │
│                                  │
├──────────────────────────────────┤
│ [10:30:45] Bridge Ready          │  ← 日志区
└──────────────────────────────────┘
```

### 4.2 8 标签规格

| 标签 | 模块 | 模式 | 操作 |
|------|------|------|------|
| **F1 图层识别** | 图层类型检测 | 同步 | classify / classifyAll |
| **F2 文字动画** | 入场动画 | 同步 | apply (fadeIn/scalePop/slideLeft) / listAnims |
| **F3 预设文件** | JSON 预设应用 | 同步 | apply (文件) / listTestPresets |
| **F4 音频提取** | FFmpeg 提取 | **异步** | extractAsync (Submit→Poll→Complete) / extract (sync fallback) |
| **F5 人声分离** | Python CLI | **异步** | submitAsync / separate (sync) |
| **F6 音频导入** | 文件导入 AE | 同步 | import / importAndAdd / replaceSource |
| **F7 文件下载** | PowerShell/curl | **异步** | downloadAsync / download (sync) |
| **F8 Topaz检测** | 扫描已安装 | 同步 | detect |

### 4.3 异步操作流

```
用户点击 "提取音频 (异步)"
  │
  ├─► runAsync('F4', params, btnId)
  │     │
  │     ├─► aeCall('studioKit', {module:'F4', action:'extractAsync', ...})
  │     │     └─► CSInterface.evalScript → bridge → F4_dispatch('extractAsync', ...)
  │     │           └─► 返回 {success:true, data:{jobId:"xxx"}}
  │     │
  │     ├─► PollManager.start(jobId, {
  │     │       checkAction: 'studioKit',
  │     │       checkParams: {module:'F4', action:'checkStatus', params:{jobId}},
  │     │       onProgress: updateProgress,
  │     │       onComplete: showResult,
  │     │       onError: showError
  │     │   })
  │     │
  │     └─► [每 2 秒轮询]
  │           aeCall → bridge → F4_dispatch('checkStatus', {jobId})
  │             → {status:'processing', progress:45}
  │             → {status:'processing', progress:78}
  │             → {status:'completed', outputPath:'...'}
  │                 └─► onComplete → 显示结果
```

---

## 5. 设计模式应用

### 5.1 复用的 Phase 1 设计模式

| 模式 | 应用位置 | 说明 |
|------|----------|------|
| **DP-01** Submit-Poll-Complete | F4/F5/F7 异步操作 | 唯一的非阻塞 ExtendScript 异步模型 |
| **DP-02** PollManager | `poll-manager.js` | 客户端统一轮询 (复用现有 338 行实现) |
| **DP-03** 模块守护加载 | Bridge `safeLoadModule()` | 每个模块独立 try/catch，graceful degradation |
| **DP-05** 结构化错误 | 所有 dispatch 返回 | 统一 `{success, data, error}` 格式 |
| **DP-18** CSS 变量主题 | 复用 `style.css` | 暗色/亮色主题自动切换 |
| **DP-20** Toast 通知 | `skToast()` | 3 秒自动消失的非阻塞通知 |
| **DP-24** SPI 单一入口 | `studioKitDispatch()` | 所有 8 模块通过一个函数路由 |

### 5.2 Phase 2 资产复用

| 资产 | 来源 | 用途 |
|------|------|------|
| PollManager | `client/poll-manager.js` | F4/F5/F7 异步轮询 |
| 共享主题 CSS | `client/style.css` | 面板视觉一致性 |
| CSInterface polyfill | `client/CSInterface.js` | 非 CEP 环境开发 |
| F#_dispatch 接口 | Phase 2 产物 | 所有模块操作入口 |

---

## 6. 技术约束合规

| 约束 | 合规方式 |
|------|----------|
| **CEP Chromium 74** (ES5) | `studio-kit.js` 全部使用 `var`/`function`, 无 `let`/`const`/`=>`/模板字符串/`fetch` |
| **ExtendScript ES3** | Bridge `.jsx` 使用 `var`/`function`，BOM UTF-8 |
| **无 fetch** | 通过 CSInterface.evalScript 桥接，不直接 HTTP |
| **无 confirm** | 自定义 toast 通知替代 |
| **无 gap** | 使用 `margin` 替代 CSS `gap` |
| **UTF-8 BOM** | Bridge 文件首行 BOM（AE 要求） |

---

## 7. F5 特殊处理

F5 是唯一的 Python CLI 模块（非 JSX）。Bridge 通过 `system.callSystem()` 包装：

```javascript
// 同步: 直接调用 Python 并解析 JSON stdout
python F5_vocal_separate.py input.wav --json-only

// 异步: 使用 --job-id 启动后台线程
python F5_vocal_separate.py input.wav --job-id F5_xxx &

// 轮询: 读取状态文件
// ~/Desktop/VocalSep5_Output/.job_F5_xxx.json
// {status: "processing"|"completed"|"failed", progress: 0-100}
```

---

## 8. 测试要点

### 8.1 桥接测试

```javascript
// 在 CEP 面板控制台:
aeCall('studioKit', {module:'F8', action:'detect', params:{}}, function(r) {
    console.log(JSON.stringify(r, null, 2));
});
// 预期: {success:true, data:{installed:true/false, path:"...", version:"..."}}
```

### 8.2 各模块冒烟测试

| 模块 | 测试条件 | 预期结果 |
|------|----------|----------|
| F1 | 合成中有选中图层 | 返回图层类型分类结果 |
| F2 | 选中文字图层 | 在时间轴创建 Animator 关键帧 |
| F3 | 选中文字图层 | 从 JSON 预设应用动画 |
| F4 | 选中含音频图层 | 异步提取 WAV 到桌面 |
| F5 | 提供 WAV 文件路径 | 生成 vocals + instrumental 文件 |
| F6 | 提供音频文件路径 | 导入到项目面板 |
| F7 | 提供有效 URL | 下载文件到指定目录 |
| F8 | 任意条件 | 检测 Topaz 安装状态 |

---

## 9. 版本历史

| 版本 | 日期 | 作者 | 变更 |
|------|------|------|------|
| 1.0.0 | 2026-06-05 | AE StudioKit Team | 初始架构设计与实现 |

---

## 附录 A: studioKitDispatch 完整签名

```javascript
/**
 * @param {string} fModule  — 'F1'|'F2'|'F3'|'F4'|'F5'|'F6'|'F7'|'F8'
 * @param {string} action   — 模块特定操作
 * @param {Object} params   — 操作参数
 * @returns {string}        — JSON: {success:bool, data?:any, error?:string}
 */
function studioKitDispatch(fModule, action, params)
```

## 附录 B: F#_dispatch 操作速查

| 模块 | 操作 | 参数 | 模式 |
|------|------|------|------|
| F1 | `classify` | — | Sync |
| F1 | `classifyAll` | — | Sync |
| F2 | `apply` | `{animationType, duration, intensity, charMode}` | Sync |
| F2 | `listAnims` | — | Sync |
| F3 | `apply` | `{presetPath, overrideDuration}` | Sync |
| F3 | `applyFromJSON` | `{preset, overrideDuration}` | Sync |
| F3 | `listTestPresets` | — | Sync |
| F4 | `extract` | `{filePath}` | Sync |
| F4 | `extractAsync` | `{inputFile, outputPath, inPoint, duration, format, sampleRate}` | **Async** |
| F4 | `checkStatus` | `{jobId}` | Poll |
| F5 | `separate` | `{audioPath, mode, engine}` | Sync |
| F5 | `submitAsync` | `{audioPath, mode, engine, outdir}` | **Async** |
| F5 | `check` | `{jobId, outdir}` | Poll |
| F6 | `import` | `{filePath}` | Sync |
| F6 | `importAndAdd` | `{filePath, addToTop}` | Sync |
| F6 | `replaceSource` | `{filePath}` | Sync |
| F6 | `importBatch` | `{files:[...]}` | Sync |
| F7 | `download` | `{url, saveDir, fileName}` | Sync |
| F7 | `downloadAsync` | `{url, saveDir, fileName}` | **Async** |
| F7 | `checkStatus` | `{jobId}` | Poll |
| F8 | `detect` | `{customPaths}` | Sync |
