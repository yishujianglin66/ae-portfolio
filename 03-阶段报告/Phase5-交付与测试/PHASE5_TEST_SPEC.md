# Phase 5 Report — 集成测试规格说明书

> **项目**: AE StudioKit Enterprise Upgrade  
> **阶段**: 第五阶段  
> **日期**: 2026-06-05  
> **状态**: ✅ 完成  
> **覆盖**: 8 F 模块单元测试 + 4 层架构集成测试 + CEP 面板测试 + 回归测试

---

## 1. 概述

### 1.1 测试范围

本测试规格书覆盖 AE StudioKit 企业级升级项目所有 5 个阶段的产出物：

| 阶段 | 产出物 | 测试重点 |
|------|--------|----------|
| Phase 1 | 设计模式库 + 反模式清单 | 反模式回归验证 |
| Phase 2 | F1-F8 优化 + 3 共享模块 | 模块单元测试 + 异步验证 |
| Phase 3 | Studio Kit 统一面板 | 4 层架构集成测试 |
| Phase 4 | 路径规范化 | 跨环境兼容性测试 |
| Phase 5 | 测试规格与交付包 | 本文档自身的覆盖率验证 |

### 1.2 测试层次

```
┌─────────────────────────────────────────────────────────────┐
│  L4: 端到端测试 (E2E)                                        │
│  AE → Studio Kit 面板 → F 模块 → 结果验证                    │
├─────────────────────────────────────────────────────────────┤
│  L3: 集成测试                                                │
│  CEP Panel ↔ Dispatcher ↔ Bridge ↔ F Modules                │
├─────────────────────────────────────────────────────────────┤
│  L2: 模块测试                                                │
│  8 F 模块独立功能验证 (dispatch 接口)                        │
├─────────────────────────────────────────────────────────────┤
│  L1: 单元测试                                                │
│  共享模块 (ModuleLoader, AnimatorAPI, JSON) + 工具函数       │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 测试环境

| 组件 | 要求 | 备注 |
|------|------|------|
| AE 版本 | CC 2023–2025 (v16.0–99.0) | CSXS 12 |
| CEP 调试模式 | `PlayerDebugMode = 1` | 注册表键 HKCU\Software\Adobe\CSXS.12 |
| Python | 3.8+ (推荐 3.11) | PATH 可访问 `python` 命令 |
| FFmpeg | 8.1.1 捆绑版 或 系统安装 | `ffmpeg-8.1.1-essentials_build/bin/` |
| 磁盘空间 | ≥ 500 MB 可用 | 模型 ~1.24 GB + 输出缓存 |
| GPU (可选) | NVIDIA CUDA 兼容 | PyTorch Demucs 加速 |

---

## 2. L1 — 共享基础设施单元测试

### 2.1 ModuleLoader (`AEStudioKit_ModuleLoader.jsx`)

| ID | 测试项 | 输入 | 预期输出 | 优先级 |
|----|--------|------|----------|--------|
| U1.1 | `require('AEStudioKit_Logger')` 首次加载 | — | 返回 Logger 对象, `loaded: true` | 🔴 P0 |
| U1.2 | `require('AEStudioKit_Logger')` 重复加载 | — | 返回缓存对象, `loaded: true` (不重复执行) | 🟡 P1 |
| U1.3 | `require('NONEXISTENT')` | 不存在的模块名 | 抛出异常 `Module not found: NONEXISTENT` | 🟡 P1 |
| U1.4 | 模块注册表 `ModuleLoader.list()` | 已加载 3+ 模块 | 返回 `['AEStudioKit_Logger', 'AEStudioKit_AnimatorAPI', 'AEStudioKit_JSON', ...]` | 🟢 P2 |
| U1.5 | 循环依赖检测 | A → B → A | 抛出 `Circular dependency detected` | 🟡 P1 |

### 2.2 AnimatorAPI (`AEStudioKit_AnimatorAPI.jsx`)

| ID | 测试项 | 输入 | 预期输出 | 优先级 |
|----|--------|------|----------|--------|
| U2.1 | `AnimatorAPI.fadeIn(textLayer, dur)` | 有效文字图层, 1s | 不透明度关键帧: 0% → 100% | 🔴 P0 |
| U2.2 | `AnimatorAPI.fadeOut(textLayer, dur)` | 有效文字图层, 1s | 不透明度关键帧: 100% → 0% | 🔴 P0 |
| U2.3 | `AnimatorAPI.scale(textLayer, from, to, dur)` | 文字图层, 0→100, 1s | 缩放关键帧 | 🟡 P1 |
| U2.4 | `AnimatorAPI.position(textLayer, x, y, dur)` | 文字图层, 1920, 1080, 1s | 位置关键帧 | 🟡 P1 |
| U2.5 | `AnimatorAPI.rotation(textLayer, deg, dur)` | 文字图层, 360, 1s | 旋转关键帧 | 🟢 P2 |
| U2.6 | `AnimatorAPI.applyEasing(keyframes, type)` | `easeIn`, `easeOut`, `easeInOut` | 速度曲线正确设置 | 🟡 P1 |
| U2.7 | 空 layer 输入 | `null` | 静默返回 `false` (不崩溃) | 🟡 P1 |

### 2.3 JSON Polyfill (`AEStudioKit_JSON.jsx`)

| ID | 测试项 | 输入 | 预期输出 | 优先级 |
|----|--------|------|----------|--------|
| U3.1 | `JSON.parse('{"a":1}')` | 简单对象 | `{a: 1}` | 🔴 P0 |
| U3.2 | `JSON.parse('[1,2,3]')` | 数组 | `[1, 2, 3]` | 🔴 P0 |
| U3.3 | `JSON.stringify({a:1})` | 简单对象 | `'{"a":1}'` | 🔴 P0 |
| U3.4 | `JSON.parse('{invalid}')` | 无效 JSON | 抛出 SyntaxError | 🟡 P1 |
| U3.5 | 嵌套对象往返 | 深嵌套 `{a:{b:{c:3}}}` | `stringify → parse` 往返一致 | 🟡 P1 |
| U3.6 | Unicode 字符串 | `"你好世界"` | 正确编码/解码 | 🟡 P1 |
| U3.7 | 特殊字符转义 | `\n`, `\t`, `\"`, `\\` | 正确转义/反转义 | 🟢 P2 |

---

## 3. L2 — F 模块单元测试

### 3.1 F1 — 图层类型检测

| ID | 测试项 | 前置条件 | 输入 | 预期输出 | 优先级 |
|----|--------|----------|------|----------|--------|
| F1.1 | `dispatch('classify', {})` — 有效选中 | AE 中选中 1 个文字图层 | `{action:'classify'}` | `{success:true, data:{type:'text', name:'...'}}` | 🔴 P0 |
| F1.2 | `dispatch('classify', {})` — 无选中 | 无图层选中 | `{}` | `{success:true, data:{type:'none'}}` 或 `{success:false, error:'...'}` | 🔴 P0 |
| F1.3 | `dispatch('classify', {})` — 多图层 | 选中多个不同类型图层 | `{}` | 返回所有图层的类型数组 | 🟡 P1 |
| F1.4 | `dispatch('classifyAll', {})` | 合成中有多个图层 | `{}` | ⚠️ 已知: 代码有 TODO — `classifyAll` 目前仅处理选中图层, 未遍历全部 | 🟢 P2 |
| F1.5 | `dispatch('unknownAction', {})` | — | 未知 action | `{success:false, error:'Unknown action: unknownAction'}` | 🟡 P1 |

### 3.2 F2 — 文字动画

| ID | 测试项 | 前置条件 | 输入 | 预期输出 | 优先级 |
|----|--------|----------|------|----------|--------|
| F2.1 | `dispatch('apply', {animationType:'fadeIn', duration:1.0, intensity:0.5})` | AE 选中文字图层 | 有效参数 | `{success:true, data:{...}}` — 动画已应用 | 🔴 P0 |
| F2.2 | `dispatch('apply', {})` — 无选中 | 无文字图层选中 | 空参数 | `{success:false, error:'...'}` | 🔴 P0 |
| F2.3 | `dispatch('listAnims', {})` | — | `{}` | `{success:true, animations:['fadeIn','scalePop','slideLeft']}` — 注: F2 模块仅含 3 个基础动画, 30+ 预设位于 `host/text_engine.jsx` | 🟡 P1 |
| F2.4 | `dispatch('apply', {animationType:'scalePop'})` — 弹跳动画 | 文字图层 | 弹跳参数 | 关键帧曲线包含缓动 (easeIn/easeOut) | 🟡 P1 |
| F2.5 | `dispatch('apply', {charMode:2})` — 逐词动画 | 多词文字图层 | charMode=2 | 动画逐词应用 (非逐字) | 🟢 P2 |
| F2.6 | 边界值: `duration:0.01` | 文字图层 | 极短时长 | 不崩溃，动画仍应用 | 🟢 P2 |
| F2.7 | 边界值: `intensity:0` / `intensity:2.0` | 文字图层 | 极值强度 | 代码自动钳制到 [0,1] — 不崩溃 | 🟢 P2 |

### 3.3 F3 — 预设文件应用

| ID | 测试项 | 前置条件 | 输入 | 预期输出 | 优先级 |
|----|--------|----------|------|----------|--------|
| F3.1 | `dispatch('apply', {presetPath:'path/to/valid.ffx'})` | 有效 .ffx 文件存在 | 预设路径 | `{success:true, data:{...}}` — 预设已应用 | 🔴 P0 |
| F3.2 | `dispatch('apply', {presetPath:'nonexistent.ffx'})` | 文件不存在 | 无效路径 | `{success:false, error:'文件不存在: ...'}` | 🔴 P0 |
| F3.3 | `dispatch('apply', {presetPath:'...', overrideDuration:3.0})` | 预设时长 ≠ 3s | 覆盖时长 | 预设以 3 秒时长应用 | 🟡 P1 |
| F3.4 | `dispatch('applyFromJSON', {preset:{...}})` | 有效预设 JSON | 预设对象 | `{success:true}` — 无需文件读取 | 🟡 P1 |
| F3.5 | `dispatch('listTestPresets', {})` | — | `{}` | `{success:true, data:[{name:'fade_in',path:'...'},...]}` | 🟢 P2 |
| F3.6 | 非 .ffx 格式文件 | 无效预设格式 | `.txt` 文件路径 | `{success:false, error:'...'}` — 格式错误提示 | 🟡 P1 |

### 3.4 F4 — 音频提取

| ID | 测试项 | 前置条件 | 输入 | 预期输出 | 优先级 |
|----|--------|----------|------|----------|--------|
| F4.1 | `dispatch('extract', {filePath:'valid.mp4'})` — 同步 | 有效视频文件 | 文件路径 | `{success:true, data:{outputPath:'...'}}` | 🔴 P0 |
| F4.2 | `dispatch('extract', {filePath:'nonexistent.mp4'})` | 文件不存在 | 无效路径 | `{success:false, error:'...'}` | 🔴 P0 |
| F4.3 | `dispatch('extractAsync', {inputFile:'...', format:'wav'})` | 有效视频 | 异步参数 | `{success:true, data:{jobId:'F4_...', mode:'async'}}` | 🔴 P0 |
| F4.4 | `dispatch('checkStatus', {jobId:'F4_...'})` — 处理中 | 异步任务运行中 | jobId | `{status:'processing', progress:N}` | 🟡 P1 |
| F4.5 | `dispatch('checkStatus', {jobId:'F4_...'})` — 已完成 | 异步任务完成 | jobId | `{success:true, data:{status:'completed', outputPath:'...'}}` | 🟡 P1 |
| F4.6 | `dispatch('checkStatus', {jobId:'INVALID'})` | 无效 jobId | 错误参数 | `{status:'error', error:'Job not found'}` | 🟡 P1 |
| F4.7 | 提取格式选项: wav / mp3 / aiff | 有效视频 | 各格式 | 输出文件扩展名匹配 | 🟢 P2 |
| F4.8 | 采样率选项: 44100 / 48000 | 有效视频 | 各采样率 | 输出文件采样率匹配 | 🟢 P2 |

### 3.5 F5 — 人声分离 (Python CLI)

| ID | 测试项 | 前置条件 | 输入 | 预期输出 | 优先级 |
|----|--------|----------|------|----------|--------|
| F5.1 | `dispatch('separate', {audioPath:'...', mode:'both'})` — 同步 | 有效音频 + Python + FFmpeg | 同步分离参数 | `{success:true, data:{vocalsPath:'...', instrumentalPath:'...'}}` | 🔴 P0 |
| F5.2 | `dispatch('separate', {audioPath:'nonexistent.wav'})` | 文件不存在 | 无效路径 | `{success:false, error:'FileNotFoundError: ...'}` | 🔴 P0 |
| F5.3 | `dispatch('submitAsync', {audioPath:'...', mode:'vocals_only'})` | 有效音频 | 异步参数 | `{success:true, data:{jobId:'F5_...', mode:'async'}}` | 🔴 P0 |
| F5.4 | `dispatch('check', {jobId:'F5_...'})` — 处理中 | 异步运行中 | jobId | `{status:'processing', progress:N}` | 🟡 P1 |
| F5.5 | `dispatch('check', {jobId:'F5_...'})` — 已完成 | 异步完成 | jobId | `{success:true, data:{status:'completed', vocalsPath:'...'}}` | 🟡 P1 |
| F5.6 | `dispatch('separate', {...})` — Python 未安装 | 无 Python | — | `{success:false, error:'F5 sync separation failed: ...'}` | 🟡 P1 |
| F5.7 | 输出目录不存在时自动创建 | 输出目录缺失 | — | 目录自动创建，分离成功 | 🟡 P1 |
| F5.8 | 支持格式验证 | 各种音频格式 | wav/mp3/flac/m4a | 正确识别格式并处理 | 🟢 P2 |
| F5.9 | 最小文件大小验证 (< 0.01MB) | 极小文件 | < 10KB 文件 | `{success:false, error:'...文件太小...'}` | 🟢 P2 |
| F5.10 | 不同引擎 (demucs/ffmpeg/auto) | 有效音频 | 各引擎 | 正确切换引擎 | 🟢 P2 |
| F5.11 | FFmpeg 相位抵消降级 (无 Demucs) | 无 PyTorch | auto 引擎 | 自动降级到 ffmpeg_phase | 🟡 P1 |

### 3.6 F6 — 音频导入

| ID | 测试项 | 前置条件 | 输入 | 预期输出 | 优先级 |
|----|--------|----------|------|----------|--------|
| F6.1 | `dispatch('import', {filePath:'valid.wav'})` | 有效音频文件 | 文件路径 | `{success:true, data:{...}}` — 音频导入项目面板 | 🔴 P0 |
| F6.2 | `dispatch('import', {filePath:'nonexistent.wav'})` | 文件不存在 | 无效路径 | `{success:false, error:'...'}` | 🔴 P0 |
| F6.3 | `dispatch('importAndAdd', {filePath:'...', addToTop:true})` | 有效音频 + 合成打开 | 导入+添加参数 | 音频添加到合成顶部轨道 | 🔴 P0 |
| F6.4 | `dispatch('replaceSource', {filePath:'...'})` | 选定音频图层 | 替换参数 | 图层源替换为新文件 | 🟡 P1 |
| F6.5 | `dispatch('importBatch', {files:['a.wav','b.wav','c.wav']})` | 3 个有效音频 | 批量数组 | `{success:true, imported:N, results:[...]}` — 顶层 `imported` 计数, `results` 逐文件结果 | 🟡 P1 |
| F6.6 | `dispatch('importBatch', {files:['a.wav','INVALID','c.wav']})` | 第 2 个无效 | 部分失效数组 | 返回各项状态 (1 和 3 成功, 2 失败) | 🟡 P1 |
| F6.7 | 输出目录 `VocalSep5_Output` 中存在文件 | 标准化路径 | — | 文件正确定位并导入 | 🟢 P2 |

### 3.7 F7 — 文件下载

| ID | 测试项 | 前置条件 | 输入 | 预期输出 | 优先级 |
|----|--------|----------|------|----------|--------|
| F7.1 | `dispatch('download', {url:'...', saveDir:'...'})` — 同步 | 有效 URL + 网络 | 同步下载参数 | `{success:true}` — 注: 实际返回结构取决于 `runF7Download()` 内部实现 | 🔴 P0 |
| F7.2 | `dispatch('download', {url:'http://invalid.url/nonexistent'})` | 无效 URL | — | `{success:false, error:'...'}` | 🔴 P0 |
| F7.3 | `dispatch('downloadAsync', {url:'...', saveDir:'...'})` | 有效 URL | 异步参数 | `{success:true, data:{jobId:'F7_...', mode:'async'}}` | 🔴 P0 |
| F7.4 | `dispatch('checkStatus', {jobId:'F7_...'})` — 处理中 | 下载进行中 | jobId | `{status:'processing', progress:N}` | 🟡 P1 |
| F7.5 | `dispatch('checkStatus', {jobId:'F7_...'})` — 已完成 | 下载完成 | jobId | `{success:true, data:{status:'completed', filePath:'...'}}` | 🟡 P1 |
| F7.6 | 保存目录不存在时自动创建 | 新目录路径 | — | 自动创建目录 | 🟡 P1 |
| F7.7 | 文件名参数 `fileName` 指定 | 有效 URL | fileName='custom.wav' | 输出文件名为 `custom.wav` | 🟢 P2 |
| F7.8 | PowerShell Job 清理 | 下载完成后 | — | 标记文件正确清理, 无残留进程 | 🟡 P1 |

### 3.8 F8 — Topaz 检测

| ID | 测试项 | 前置条件 | 输入 | 预期输出 | 优先级 |
|----|--------|----------|------|----------|--------|
| F8.1 | `dispatch('detect', {})` | — | `{}` | `{success:true, data:{installed:bool, path:'...', version:'...'}}` | 🔴 P0 |
| F8.2 | `dispatch('detect', {customPaths:['D:\\topaz']})` | Topaz 安装在自定义路径 | 自定义搜索路径 | 搜索列表包含自定义路径, `data.installed` 反映是否找到 | 🟡 P1 |
| F8.3 | Topaz 未安装时 | — | `{}` | `{success:true, data:{installed:false, path:'', version:''}}` | 🟡 P1 |
| F8.4 | 多版本 Topaz (Video AI + Photo AI) | 两者都安装 | — | 两者都被检测到 | 🟢 P2 |

---

## 4. L3 — 4 层架构集成测试

### 4.1 L1→L2: CEP Panel → Dispatcher

| ID | 测试项 | 输入 | 预期输出 | 优先级 |
|----|--------|------|----------|--------|
| I1.1 | `aeCall('studioKit', {module:'F1', action:'classify', params:{}})` | 有效 studioKit action | CSInterface.evalScript 发送字符串 `"AEStudioKit.dispatch('studioKit', '...')"` | 🔴 P0 |
| I1.2 | CSInterface 不可用时 (非 CEP 环境) | — | `skLog('CEP bridge not available', 'error')`, callback(null) | 🟡 P1 |
| I1.3 | JSON 参数转义 — 含单引号 | `{name: "it's"}` | 单引号正确转义为 `\'` | 🟡 P1 |
| I1.4 | callback 为 null 时 | `aeCall('studioKit', {}, null)` | 静默返回 (不崩溃) | 🟢 P2 |
| I1.5 | evalScript 返回空字符串 | `result = ''` | `callback({success:true, data:{output:''}})` | 🟡 P1 |

### 4.2 L2→L3: Dispatcher → Bridge

| ID | 测试项 | 输入 | 预期输出 | 优先级 |
|----|--------|------|----------|--------|
| I2.1 | `AEStudioKit.dispatch('studioKit', {module:'F1', action:'classify', params:{}})` | studioKit dispatch | 路由到 `studioKitDispatch('F1', 'classify', {})` | 🔴 P0 |
| I2.2 | `AEStudioKit.dispatch('studioKit', {})` — 无 module | 空参数 | `studioKitDispatch('F1', '', {})` — 使用默认 F1 | 🟡 P1 |
| I2.3 | `AEStudioKit.dispatch('UNKNOWN', {})` | 未知 action | `{success:false, error:'未知操作: UNKNOWN', code:'E999'}` | 🔴 P0 |
| I2.4 | Bridge 未加载时 | studioKitDispatch 不存在 | `{success:false, error:'Studio Kit bridge not loaded', code:'E998'}` | 🟡 P1 |
| I2.5 | 参数为 JSON 字符串 | `'{"module":"F1"}'` | 正确解析为对象 | 🟡 P1 |
| I2.6 | 模块名 fallback: `params.module` vs `params.fModule` | `{fModule:'F2'}` | 正确识别 fModule 字段 | 🟢 P2 |

### 4.3 L3→L4: Bridge → F Modules

| ID | 测试项 | 输入 | 预期输出 | 优先级 |
|----|--------|------|----------|--------|
| I3.1 | `studioKitDispatch('F1', 'classify', {})` — 模块已加载 | F1 正常加载 | 调用 `$.global.F1_dispatch('classify', {})` | 🔴 P0 |
| I3.2 | `studioKitDispatch('F1', ..., ...)` — 模块未加载 | F1 加载失败 | `{success:false, error:'F1 module not loaded'}` | 🔴 P0 |
| I3.3 | `studioKitDispatch('F99', '...', {})` | 未知模块 | `{success:false, error:'Unknown module: F99', available:[...]}` | 🟡 P1 |
| I3.4 | 模块返回 `null` | F dispatch 返回 null | `{success:false, error:'Module returned null'}` | 🟡 P1 |
| I3.5 | 模块返回已有 `success:false` 的对象 | `{success:false, error:'xxx'}` | 保持原样 (不包装) | 🔴 P0 |
| I3.6 | 模块返回已有 `success:true` 的对象 | `{success:true, data:{...}}` | 保持原样 (不包装) | 🔴 P0 |
| I3.7 | 模块返回简单字符串 `"done"` | 字符串 | `{success:true, data:{output:'done'}}` | 🟡 P1 |
| I3.8 | 模块返回已是 JSON 字符串 | `'{"success":true}'` | 原样返回 (不二重包装) | 🟡 P1 |
| I3.9 | 模块抛出异常 | `throw Error(...)` | `{success:false, error:'studioKitDispatch[F#] error: ...'}` | 🟡 P1 |
| I3.10 | 参数为 JSON 字符串 — 解析 | `'"{\"key\":\"val\"}"'` | 正确解析为对象 | 🟡 P1 |

### 4.4 Studio Kit Bridge 自检

| ID | 测试项 | 输入 | 预期输出 | 优先级 |
|----|--------|------|----------|--------|
| I4.1 | `getLoadedModules()` — 全部加载 | 7/7 JSX 成功 | `['F1','F2','F3','F4','F5','F6','F7','F8']` | 🔴 P0 |
| I4.2 | `getLoadedModules()` — 部分失败 | F2 加载失败 | F2 不在列表中, 其余 7 个在 | 🟡 P1 |
| I4.3 | F5 始终在已加载列表中 | — | 'F5' 在返回数组中 (Python 不依赖 $.evalFile) | 🟡 P1 |
| I4.4 | `_STUDIO_KIT_SKIP_RUN = true` 守卫 | Bridge 加载 F 模块 | 模块不自动执行 `runF#*()` 函数 | 🔴 P0 |
| I4.5 | `safeLoadModule` 文件不存在 | 错误路径 | `$.writeln('[StudioKit] Failed to load ...')`, 返回 false | 🟡 P1 |
| I4.6 | Python 检测缓存 | 第二次调用 `_detectPython()` | 使用缓存值, 不重复执行 `system.callSystem` | 🟢 P2 |

---

## 5. L4 — 端到端 (E2E) 测试

### 5.1 Studio Kit 面板 — 初始化

| ID | 测试项 | 前置条件 | 预期结果 | 优先级 |
|----|--------|----------|----------|--------|
| E1.1 | 面板加载 | AE 中打开 Studio Kit 面板 | `skLog` 显示 "AE StudioKit Phase 3 — initializing..." | 🔴 P0 |
| E1.2 | Bridge 连接测试 (1.5s 后) | 面板加载完成 | `STATE.bridgeOk = true`, 状态指示灯绿 | 🔴 P0 |
| E1.3 | Bridge 连接失败 | host/index.jsx 加载失败 | `STATE.bridgeOk = false`, 状态指示灯红 | 🟡 P1 |
| E1.4 | 定期状态刷新 (30s) | 面板保持打开 | 每 30s 检查 bridgeOk 状态 | 🟢 P2 |
| E1.5 | beforeunload 清理 | 关闭面板 | `pollManager.stopAll()` 调用 | 🟡 P1 |

### 5.2 Studio Kit 面板 — 标签切换

| ID | 测试项 | 操作 | 预期结果 | 优先级 |
|----|--------|------|----------|--------|
| E2.1 | 点击 F2 标签 | 点击 "F2 Text Anim" 按钮 | F2 面板显示, 按钮高亮 | 🔴 P0 |
| E2.2 | 点击 F5 标签 | 点击 "F5 Vocal Sep" 按钮 | F5 面板显示, 其他隐藏 | 🔴 P0 |
| E2.3 | 切换标签日志 | 点击任意标签 | 日志显示 "Switched to tab: F#" | 🟢 P2 |

### 5.3 Studio Kit 面板 — 同步模块执行

| ID | 测试项 | 模块 | 操作 | 预期结果 | 优先级 |
|----|--------|------|------|----------|--------|
| E3.1 | F1 分类执行 | F1 | 选中图层, 点击 "Run" | 结果显示在结果区, 按钮恢复文本 | 🔴 P0 |
| E3.2 | F1 无选中 | F1 | 无选中, 点击 "Run" | 显示合理的错误/空结果 | 🔴 P0 |
| E3.3 | F2 应用动画 | F2 | 选中文字, 选择动画, 点击 "Apply" | 动画应用, 结果显示 | 🔴 P0 |
| E3.4 | F2 列出动画 | F2 | 点击 "List Anims" | 显示所有动画名称列表 | 🟡 P1 |
| E3.5 | F3 应用预设 | F3 | 输入预设路径, 点击 "Apply" | 预设应用, 结果显示 | 🔴 P0 |
| E3.6 | F3 列出预设 | F3 | 点击 "List Presets" | 显示预设列表 | 🟡 P1 |
| E3.7 | F6 导入音轨 | F6 | 有效路径, 点击 "Import" | 音频导入 AE, 结果显示 | 🔴 P0 |
| E3.8 | F8 检测 Topaz | F8 | 点击 "Detect" | 显示检测结果 (found:N) | 🔴 P0 |
| E3.9 | 按钮加载状态 | 任意同步 | 点击 → 处理中 → 完成 | "处理中..." → 禁用 → 恢复原文本 | 🟡 P1 |
| E3.10 | Bridge 通信失败 | 任意 | 模拟断连 | 显示 "Bridge communication failed" | 🟡 P1 |

### 5.4 Studio Kit 面板 — 异步模块执行

| ID | 测试项 | 模块 | 操作 | 预期结果 | 优先级 |
|----|--------|------|------|----------|--------|
| E4.1 | F4 异步提取 | F4 | 输入文件, 点击 "Extract Async" | Submit → jobId → 进度条 → 完成 | 🔴 P0 |
| E4.2 | F5 异步分离 | F5 | 输入音频路径, 点击 "Separate Async" | Submit → jobId → 进度条 → 完成 | 🔴 P0 |
| E4.3 | F7 异步下载 | F7 | 输入 URL, 点击 "Download Async" | Submit → jobId → 进度条 → 完成 | 🔴 P0 |
| E4.4 | 进度条显示 | F4/F5/F7 | 异步任务运行中 | `showProgress` → 进度条可见, 百分比更新 | 🔴 P0 |
| E4.5 | PollManager 轮询 (2s 间隔) | F4/F5/F7 | 异步任务 | 每 2s 调用 check 动作, 最多 150 次 = 5 min | 🟡 P1 |
| E4.6 | 异步完成回调 | F4/F5/F7 | 任务完成 | `onComplete` → 进度条隐藏 → 结果显示 | 🟡 P1 |
| E4.7 | 异步错误处理 | F4/F5/F7 | 提交失败 | `onError` → 进度条隐藏 → 错误显示 | 🟡 P1 |
| E4.8 | 同步回退 (无 jobId) | F4/F5/F7 | submit 返回已完成的 data | 直接显示结果 (不进入轮询) | 🟡 P1 |
| E4.9 | 按钮 Toast 通知 | 任意异步 | 完成/失败 | `skToast` 显示 "完成" / "失败:..." | 🟢 P2 |

### 5.5 Studio Kit 面板 — 输入验证

| ID | 测试项 | 模块 | 操作 | 预期结果 | 优先级 |
|----|--------|------|------|----------|--------|
| E5.1 | F5 空音频路径 | F5 | 路径为空, 点击执行 | `skToast('请输入音频文件路径', 'error')`, 不发送请求 | 🟡 P1 |
| E5.2 | F7 空 URL | F7 | URL 为空, 点击下载 | `skToast('请输入下载 URL', 'error')`, 不发送请求 | 🟡 P1 |
| E5.3 | F3 空预设路径 | F3 | 路径为空, 点击 Apply | 发送给 Bridge, 由 F3 返回错误 | 🟢 P2 |

### 5.6 AE Integration 端到端

| ID | 测试项 | 操作 | 预期结果 | 优先级 |
|----|--------|------|----------|--------|
| E6.1 | Manifest 双面板注册 | AE → 窗口 → 扩展 | 显示 "AE StudioKit" 和 "AE StudioKit - Studio Kit" 两个入口 | 🔴 P0 |
| E6.2 | 主面板正常工作 | 打开主面板 | 9 标签正常显示, 功能不受 Phase 3 影响 | 🔴 P0 |
| E6.3 | 双面板共存 | 同时打开两个面板 | 两个面板独立运行, 共享 host/index.jsx | 🟡 P1 |
| E6.4 | Studio Kit 面板尺寸 | 打开 Studio Kit | 初始 550×800, 最小 400×500 | 🟢 P2 |
| E6.5 | Studio Kit AutoVisible | 启动 AE | Studio Kit 不自动弹出 (AutoVisible=false) | 🟢 P2 |

---

## 6. Phase 4 回归测试 — 路径规范化

### 6.1 动态路径解析

| ID | 测试项 | 前置条件 | 预期结果 | 优先级 |
|----|--------|----------|----------|--------|
| R1.1 | `findPython()` — PATH 搜索 `python --version` | Python 在 PATH | 返回 `'python'` | 🔴 P0 |
| R1.2 | `findPython()` — 所有候选失败 | 无可用的 Python | 返回 `'python'` (最终回退) | 🟡 P1 |
| R1.3 | `getScriptDir()` — 正确 AE 路径 | AE 2023–2025 | 从 `app.path` 动态推导出正确的 Support Files 目录 | 🔴 P0 |
| R1.4 | `getScriptDir()` — `app.path` 不可用 | 异常情况 | 回退到 `Folder.myDocuments.fsName` | 🟡 P1 |
| R1.5 | 输出目录: `VocalSep5_Output` | 所有模块 | 所有输出写入 `VocalSep5_Output` (非旧 `VocalSep_Output`) | 🔴 P0 |
| R1.6 | 路径分隔符一致性 | CEP 面板 | `client/app.js` 使用 `/` (非 `\\`) | 🔴 P0 |
| R1.7 | 端口集中化 | Python 启动 | `ae_bridge.py` 从 `config.py` 导入 `SERVER_PORT=8765` | 🟡 P1 |

### 6.2 硬编码路径消除

| ID | 测试项 | 检查内容 | 预期结果 | 优先级 |
|----|--------|----------|----------|--------|
| R2.1 | 无硬编码用户名 | grep `Administrator` | 活跃代码中 0 匹配 | 🔴 P0 |
| R2.2 | 无硬编码 Python 版本 | grep `Python311` | 活跃代码中 0 匹配 | 🔴 P0 |
| R2.3 | 无硬编码 AE 版本 | grep `After Effects 2025` | 活跃代码中 0 匹配 | 🔴 P0 |
| R2.4 | F5 Python 输出目录 | `VocalSep_Output` 引用 | 0 匹配 (全部替换为 VocalSep5_Output) | 🟡 P1 |

### 6.3 文件清理

| ID | 测试项 | 检查内容 | 预期结果 | 优先级 |
|----|--------|----------|----------|--------|
| R3.1 | 无过期文件 | .bak/.test/.txt 残留 | 0 匹配 | 🟢 P2 |
| R3.2 | 无空目录 | host/docs/server/test-suites 下 | 0 匹配 | 🟢 P2 |
| R3.3 | 无中文目录名 | 项目根 | 0 匹配 (project-skills/ 使用英文) | 🟢 P2 |

---

## 7. Phase 1-3 回归测试 — 已知反模式

### 7.1 已修复反模式验证

| ID | 反模式 | 修复状态 | 验证方法 | 优先级 |
|----|--------|----------|----------|--------|
| AP1 | `app.refresh()` 调用 | ✅ v4.0 已替换为 `app.redraw()` | `grep "app.refresh"` → 0 结果 | 🔴 P0 |
| AP2 | 同步 `system.callSystem()` 用于长操作 | ✅ F4/F7 异步化 | F4/F7 150s+ 操作不阻塞 | 🔴 P0 |
| AP3 | `confirm()` 在 CEP 不可用 | ✅ 替换为 `showConfirm()` 自定义模态 | CEP 中确认操作正常弹出 | 🔴 P0 |
| AP4 | `STATE.outDir` 竞态条件 | ✅ `STATE.ready` 移入异步计数 | download 前 outDir 始终已定义 | 🔴 P0 |
| AP5 | `setInterval` 泄漏 | ✅ `beforeunload` 清理 | 面板关闭后无残留轮询 | 🟡 P1 |
| AP6 | F5 JSON 解析前空白 | ✅ trim whitespace | `--json-only` 输出正确解析 | 🟡 P1 |
| AP7 | `aeCall` TypeError on 非字符串 | ✅ typeof 守卫 | 非字符串返回值不崩溃 | 🟡 P1 |
| AP8 | `_logWarn` 在 catch 前定义 | ✅ 移至文件顶部 | 模块加载失败时日志正常工作 | 🟡 P1 |
| AP9 | `setButtonLoading` 文本丢失 | ✅ 先保存 data-original | 按钮文本正确恢复 | 🟡 P1 |
| AP10 | Bridge `var AEStudioKit` 阴影 | ✅ 使用 `$.global.AEStudioKit` | 全局命名空间不丢失 | 🟡 P1 |
| AP11 | 结果标准化掩盖 `success:false` | ✅ 检查 `'success' in result` | 模块错误正确传播 | 🟡 P1 |

### 7.2 代码质量检查

| ID | 检查项 | 方法 | 标准 | 优先级 |
|----|--------|------|------|--------|
| Q1 | 空 catch 块 | `grep "catch.*{}"` 或 `catch(e){}` | 0 匹配 (Phase 1 发现 37 处, 目标 ≤5) | 🟡 P1 |
| Q2 | UTF-8 BOM 编码 | 所有 .jsx 文件 | 100% BOM 标记 | 🟡 P1 |
| Q3 | ES5 合规 (client/) | 无 const/let/arrow/class/template literal/fetch | 0 匹配 | 🟡 P1 |
| Q4 | ES3 合规 (host/) | 同上 + 无 forEach/map/filter (无 polyfill 时) | 0 匹配 | 🟡 P1 |
| Q5 | 硬编码路径 | grep `C:\\` | ≤ 2 处 (仅合法搜索候选) | 🟡 P1 |
| Q6 | `$.evalFile` 错误处理 | 所有 evalFile 调用 | 100% 包裹在 try/catch 中 | 🟢 P2 |

---

## 8. 测试执行矩阵

### 8.1 执行优先级

| 优先级 | 说明 | 测试数量 | 所需环境 |
|--------|------|----------|----------|
| 🔴 P0 | 阻断性 — 发布阻塞 | 57 项 | AE + CEP + Python + FFmpeg |
| 🟡 P1 | 重要 — 发布前修复 | 66 项 | AE + CEP |
| 🟢 P2 | 低 — 发布后可修 | 28 项 | 部分需 AE, 部分可独立 |

### 8.2 测试环境依赖矩阵

| 测试类别 | AE 必需 | CEP 调试 | Python | FFmpeg | GPU | 网络 |
|----------|---------|----------|--------|--------|-----|------|
| 共享模块 (L1) | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| F1-F3, F6, F8 (同步) | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| F4 音频提取 | ✅ | ✅ | ❌ | ✅ | ❌ | ❌ |
| F5 人声分离 | ✅ | ✅ | ✅ | ✅ | 可选 | ❌ |
| F7 文件下载 | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| 面板集成 (L3) | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| E2E (L4) | ✅ | ✅ | ✅ | ✅ | 可选 | 部分 |
| 回归测试 | 部分 ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

### 8.3 无 AE 环境的测试

以下测试可在任何带有 ExtendScript Toolkit 的机器上执行 (不需要 AE GUI):

| 测试 | ID | 方法 |
|------|-----|------|
| 模块加载验证 | I3.1–I3.10 | ExtendScript Toolkit CC 中运行 `host/index.jsx` |
| Bridge 逻辑完整性 | I4.1–I4.6 | 直接执行 `studio-kit-bridge.jsx` 并检查全局变量 |
| JSON polyfill | U3.1–U3.7 | 任意 ES3 环境 |
| 路径规范化 | R2.1–R2.4 | 纯文本 grep 搜索 |
| 反模式验证 | AP1–AP11 | grep 搜索 + 代码审查 |
| 代码质量 | Q1–Q6 | grep 搜索 + 代码审查 |

---

## 9. 测试数据

### 9.1 推荐测试文件

| 用途 | 文件 | 规格 |
|------|------|------|
| 人声分离基础 | 人声+伴奏混音 WAV | 44.1kHz, 16bit, 立体声, 30-180s |
| 短音频边界测试 | 3s 片段 | 最短可处理时长 |
| 长音频压力测试 | 5min+ 歌曲 | 最大处理时长 |
| 视频音频提取 | MP4 含 AAC 音轨 | 1080p, 30s-2min |
| 格式验证 | MP3 320kbps, FLAC, M4A | 各格式代表性文件 |
| 下载测试 | 小文件 < 1MB | 公开 URL (如 GitHub release) |

### 9.2 测试预设

| 预设名称 | 类型 | 来源 |
|----------|------|------|
| `fade_in` | 入场 | F3 内建 |
| `scale_pop` | 弹跳 | F3 内建 |
| Saber 预设 (.ffx) | 光剑效果 | `server/presets/07_vc_saber/` |

---

## 10. 质量验收检查清单 (Go/No-Go)

### 10.1 阻断项 (Must Pass — 任一失败则阻塞发布)

- [ ] **G1**: 所有 57 项 P0 测试通过
- [ ] **G2**: 生产主面板 (12 标签) 不受 Studio Kit 影响 — 向后兼容
- [ ] **G3**: 双 DispatchInfo 面板共存, 互不干扰
- [ ] **G4**: 无硬编码用户名/版本路径 — 可在不同机器部署
- [ ] **G5**: 异步操作 (F4/F5/F7) 不阻塞 AE 主线程
- [ ] **G6**: `STATE.outDir` 竞态条件不再复现
- [ ] **G7**: `confirm()` 替换为自定义模态 — CEP Chromium 74 兼容
- [ ] **G8**: `setInterval` 无泄漏 — 面板关闭后轮询停止

### 10.2 重要项 (Should Pass — 尽可能通过)

- [ ] **S1**: 66 项 P1 测试通过率 ≥ 90%
- [ ] **S2**: F5 Python CLI `--json-only` 输出正确解析
- [ ] **S3**: 路径分隔符全部统一为 `/`
- [ ] **S4**: Python 端口从 `config.py` 集中管理
- [ ] **S5**: F6 批量导入正确处理部分失败场景
- [ ] **S6**: PollManager 轮询上限生效 (150 次 = 5 min)
- [ ] **S7**: Studio Kit 面板输入验证 (F5 空路径, F7 空 URL)

### 10.3 优化项 (Nice to Have)

- [ ] **N1**: 28 项 P2 测试通过率 ≥ 70%
- [ ] **N2**: 代码质量检查 (空 catch ≤ 5, 100% BOM, ES5/ES3 合规)
- [ ] **N3**: Studio Kit 面板响应式标签切换 < 100ms
- [ ] **N4**: 日志完整性 — 所有操作有 trace

---

## 11. 已知限制与豁免

### 11.1 测试覆盖豁免

以下场景不在 Phase 5 测试范围内：

| 项目 | 原因 |
|------|------|
| GPU Demucs 模型输出音质评估 | 需要人类听觉评估, 属于 QA 而非自动化测试 |
| LookAE 在线抓取成功率 | Cloudflare 拦截是已知问题, 已有 4 级降级 |
| MVSep 云端分离 | 依赖外部 API 可用性 |
| 跨平台测试 (macOS) | 当前仅 Windows 环境 |
| AE-MotionStudio 架构线 | 与主开发线独立的项目 |

### 11.2 已知未修复 Bug (Phase 5 排除)

| ID | 描述 | 影响 | 计划修复 |
|----|------|------|----------|
| M1 | join 命令文件句柄泄漏 | 多次拼接后内存问题 | 后续维护 |
| M2 | README 文档与代码不一致 | 用户困惑 | 后续维护 |
| M3 | 版本号不一致 (UI v5.0 vs 代码 v4.0) | 品牌混乱 | 架构决策后统一 |
| M4 | 云端分离硬编码 `.wav` 扩展名 | 非 WAV 格式文件名错误 | 后续维护 |

---

## 12. 测试环境搭建指南

### 12.1 快速环境配置

```bash
# 1. 开启 CEP 调试模式 (管理员终端)
REG ADD "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_DWORD /d 1 /f

# 2. 确认 Python 可用
python --version  # 应输出 Python 3.8+

# 3. 确认 FFmpeg 可用
ffmpeg-8.1.1-essentials_build\bin\ffmpeg.exe -version

# 4. 安装 Python 依赖 (可选 — GPU 分离)
pip install -r server/requirements.txt

# 5. 复制扩展到 CEP 目录
xcopy /E /I /Y ae-vocal-remover "%APPDATA%\Adobe\CEP\extensions\ae-vocal-remover\"

# 6. 启动 AE, 窗口 → 扩展 → AE StudioKit
# 7. 窗口 → 扩展 → AE StudioKit - Studio Kit
```

### 12.2 日志位置

| 日志 | 路径 |
|------|------|
| ExtendScript 调试 | AE → 首选项 → 脚本和表达式 → 启用日志 |
| Bridge 加载日志 | `$.writeln` 输出 → ExtendScript Toolkit 控制台 |
| Python F5 日志 | `~/Desktop/VocalSep5_Output/F5_vocal_sep.log` |
| CEP 面板日志 | Chrome DevTools (localhost: 在 CEP 面板按 F12) |
| Studio Kit 面板日志 | 面板内建日志区域 (`#skLog`) |

---

## 13. 测试报告模板

### 13.1 测试轮次记录

| 轮次 | 日期 | 执行人 | P0 通过/总数 | P1 通过/总数 | P2 通过/总数 | 新增 Bug | 状态 |
|------|------|--------|-------------|-------------|-------------|----------|------|
| 1 | | | /57 | /66 | /28 | | |
| 2 | | | /57 | /66 | /28 | | |
| 3 | | | /57 | /66 | /28 | | |

### 13.2 Bug 报告模板

```
ID: BUG-###
测试用例: [ID]
严重性: 🔴 CRITICAL / 🟠 HIGH / 🟡 MEDIUM / 🟢 LOW
模块: F# / Bridge / Panel
复现步骤:
  1.
  2.
  3.
预期结果:
实际结果:
环境: [AE版本, Python版本, OS]
截图/日志: [链接]
```

---

> **本文件是 AE StudioKit Enterprise Upgrade 项目的第五阶段可交付成果。**
> 
> **相关文档**:
> - [Phase 1 主报告](../phase1/PHASE1_MAIN_REPORT.md) — 设计模式库 + 反模式清单
> - [Phase 2 优化计划](../phase2/PHASE2_OPTIMIZATION_PLAN.md) — F 模块设计文档
> - [Phase 3 架构设计](../phase3/PHASE3_ARCHITECTURE.md) — 4 层架构 + 通信协议
> - [Phase 4 路径规范化](../phase4/PHASE4_REPORT.md) — 重命名对照表 + 迁移详情
> - [审计报告](../../AUDIT_REPORT.md) — 原始 Bug 注册表
