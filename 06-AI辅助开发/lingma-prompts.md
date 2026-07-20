# Lingma AI 协作提示词库

> **文档目的**: 收录经过测试验证的 Lingma AI 精确提示词，覆盖 AE 扩展开发的 15+ 典型场景。每个提示词均经过实际测试，确保输出符合项目规范。
>
> **使用方式**: 在 Lingma 对话框中直接粘贴提示词，根据需要修改 `【】` 中的占位符。
>
> **关联文档**: [Lingma协作指南](./Lingma协作指南.md) | [编码规范](./编码规范.md)
>
> **最后更新**: 2026-06-10

---

## 1. 文字动画生成

### 提示词
```
为当前选中文字图层添加一个缓入缩放动画，持续 1 秒：
- 从缩放 0% 到 100%，使用 easeInOut 缓动
- 同时透明度从 0% 到 100%
- 使用 app.scheduleTask 异步应用，避免 UI 阻塞
- 函数返回 { success: Boolean, error: String }
- 使用 var 声明变量（ES3 兼容）
- 用 comp.selectedLayers 获取选中图层
- 包含完整 try/catch
```

### 期望输出
- 一个 `applyFadeInScale(layer, duration)` ExtendScript 函数
- 使用 `property.setValueAtTime()` 设置关键帧
- 使用 `scheduleTask` 分步执行
- 返回标准 `{ success, error, code }` 对象

---

## 2. 错误修复

### 提示词
```
解释此 ExtendScript 错误并自动修复：
"Unable to execute script at line 12. ReferenceError: app.refresh is not a function"

项目约束：
- AE 扩展开发，使用 ExtendScript ES3
- app.refresh 已废弃，正确 API 是 app.redraw()
- 同时扫描文件中所有 app.refresh 出现并全部替换
```

### 期望输出
- 错误原因分析：app.refresh 在 AE 中不是有效 API
- 将所有 `app.refresh()` 替换为 `app.redraw()`
- 展示修改前后对比

---

## 3. 重构建议

### 提示词
```
将以下 ExtendScript 同步循环改为 app.scheduleTask 异步模式：

【粘贴同步循环代码】

要求：
- 每处理 10 个图层调用一次 app.redraw()
- 使用 chunkSize=5 分片
- 添加进度回调 onProgress(pct, msg)
- 保留原始功能逻辑不变
- 添加取消支持 (cancel flag)
```

### 期望输出
- 重构后的函数，使用 scheduleTask 递归分片
- 保留原始处理逻辑
- 增加进度和取消机制

---

## 4. 批量操作

### 提示词
```
生成一个 ExtendScript 函数 batchExportSelectedLayersAsPNG：
- 遍历所有选中图层
- 每个图层渲染当前帧并导出为 PNG 到 _storage/output/
- 文件名格式: {图层名}_{帧号}.png
- 使用 scheduleTask 分片，每片 3 个图层
- 显示进度条 (通过 $.writeln 输出百分比)
- 错误跳过：单个图层导出失败不影响其余
- 完成时 alert 总结 (成功/失败数量)

要求 ES3 语法，所有路径使用反斜杠转义。
```

### 期望输出
- 完整的 `batchExportSelectedLayersAsPNG()` 函数
- 含进度输出和错误收集
- ES3 兼容语法

---

## 5. CEP 模板

### 提示词
```
生成一个符合 CEP 12 规范的 manifest.xml：
- 扩展名称: StudioKit
- 扩展 ID: com.aestudiokit.panel
- 支持 AE 版本: 16.0 - 99.9
- 包含两个标签页: 文字特效 (text-fx), 音频处理 (audio)
- 面板入口 HTML: client/index.html
- 脚本路径: host/index.jsx
- 使用 CSXS 12 schema
```

### 期望输出
- 完整的 XML manifest 文件
- 正确的命名空间和版本声明
- DispatchInfo 列表

---

## 6. 对象查询

### 提示词
```
根据 AE ExtendScript 对象模型，编写两个函数：

1. doesLayerHaveAudio(layer) — 判断图层是否包含音频轨道
   - 先检查 layer 是否为 AVLayer
   - 使用 hasAudio 属性
   - 返回 Boolean

2. getLayerAudioDuration(layer) — 获取音频时长
   - 通过 mainSource.duration 获取
   - 返回秒数 (Number)
   - 无音频时返回 0

要求：
- ES3 语法 (var, function)
- 完整 try/catch
- JSDoc 注释
```

### 期望输出
- 两个完整的工具函数
- 含类型检查和边界处理
- JSDoc 注释

---

## 7. 代码解释

### 提示词
```
解释以下 ExtendScript 函数的工作原理，并指出潜在的性能瓶颈和改进建议：

【粘贴需要分析的代码】

分析维度：
1. 功能流程图 (文字描述)
2. 潜在的性能问题 (阻塞点、重复调用、内存泄漏)
3. 改进建议 (异步化、缓存、合并操作)
4. AE API 使用的正确性
```

### 期望输出
- 结构化的分析报告
- 每个问题点配行号和代码片段
- 具体的修复建议

---

## 8. 性能优化

### 提示词
```
优化以下 ExtendScript 图层遍历代码：
- 使用缓存减少 app.project.item 的重复调用
- 合并多次 loop 为单次遍历
- 将 instanceof 检查集中到 switch-like 结构

【粘贴图层遍历代码】

约束：
- 保持 ES3 兼容
- 不改变功能逻辑
- 添加注释说明为什么这样优化
```

### 期望输出
- 优化后的代码
- 优化前后性能对比说明
- 每个优化点的注释

---

## 9. 测试生成

### 提示词
```
为以下 ExtendScript 函数生成边界测试用例：

【粘贴 applyTextPreset 函数签名和逻辑描述】

测试用例要求覆盖：
1. 正常场景：选中文字图层，传入有效预设
2. 边界场景：无文字图层选中 (应返回错误)
3. 边界场景：多选图层 (应处理第一个文字图层)
4. 异常场景：空名称图层
5. 异常场景：预设数据为 null/undefined
6. 异常场景：预设数据格式错误 (缺少必要字段)

每个测试用例格式:
- 名称
- 前置条件
- 输入
- 期望输出
- 验证方法
```

### 期望输出
- 6+ 个结构化测试用例
- 含前置条件/输入/期望输出/验证方法

---

## 10. API 迁移

### 提示词
```
将以下使用 ScriptUI 的旧版 ExtendScript 代码转换为 CEP HTML 面板代码：

【粘贴 ScriptUI 代码】

要求：
1. UI 层 (HTML/CSS): 创建等效的 CEP 面板界面
2. 逻辑层 (JS): 使用 CSInterface.evalScript 调用后端
3. 后端 (JSX): 保留核心逻辑，添加 cepDispatch 接口
4. 样式: 深色主题，匹配 AE 面板
5. 所有通信使用 JSON 格式
```

### 期望输出
- 三部分代码 (HTML/CSS, JS, JSX)
- 通信流程说明
- 与原 ScriptUI 版的功能对比

---

## 11. 模型集成

### 提示词
```
编写 Python 函数调用 Real-ESRGAN ONNX 模型进行超分辨率：
- 输入: 图片路径 (str)
- 输出: 超分辨率图片路径 (str) + JSON 状态
- 使用 ONNX Runtime 推理
- 模型路径: _storage/models/realesrgan.onnx
- 自动处理 CUDA/CPU 回退
- 返回格式: {"status": "ok", "output": "path", "time_ms": 1234}
- 错误时: {"status": "error", "message": "..."}
- 包含完整 try/catch 和日志

Python 3.9+ 兼容，使用 pathlib 处理路径。
```

### 期望输出
- 完整的 Python 函数
- ONNX 推理代码
- GPU/CPU 自动切换逻辑

---

## 12. FFmpeg 命令

### 提示词
```
生成从视频提取音频、人声分离、并导出人声和伴奏的完整 ffmpeg + demucs 命令行：

步骤:
1. 从视频提取音频为 WAV (16kHz, mono)
2. 使用 demucs 分离人声和伴奏
3. 输出到 _storage/output/ 目录

ffmpeg 参数要求:
- 音频编码: pcm_s16le
- 采样率: 44100
- 声道: stereo
- 不重新编码视频

生成一个可直接在 Windows 命令行运行的完整命令链。
```

### 期望输出
- 完整的命令链
- 参数说明注释
- 输出文件命名规则

---

## 13. 依赖检查

### 提示词
```
生成一个 ExtendScript 函数 checkSystemRequirements()：

检查项:
1. Python 3.9+ 是否安装并在 PATH 中
2. FFmpeg 是否安装 (或项目内置)
3. 磁盘空间 (至少 2GB 可用)
4. AE 版本是否 ≥ 16 (2020+)

返回格式:
{
    success: Boolean,
    checks: {
        python: { ok: Boolean, version: String, path: String },
        ffmpeg: { ok: Boolean, version: String, path: String },
        diskSpace: { ok: Boolean, freeGB: Number },
        aeVersion: { ok: Boolean, version: String }
    },
    allPassed: Boolean
}

使用 system.callSystem 检测外部依赖，ES3 语法。
```

### 期望输出
- 完整的检查函数
- 每项检查的独立错误处理
- 结构化返回对象

---

## 14. 安全审计

### 提示词
```
扫描以下 ExtendScript 代码，报告潜在的安全问题：

【粘贴代码】

检查清单:
1. system.callSystem 调用中是否有未过滤的用户输入
2. 是否有 eval() 或类似动态执行
3. 文件路径是否硬编码或可被注入
4. Socket 连接是否有认证机制
5. 日志中是否可能泄露敏感路径/密钥

对每个问题提供:
- 风险等级 (高/中/低)
- 问题位置 (行号)
- 攻击场景描述
- 修复建议
```

### 期望输出
- 安全审计报告
- 按风险等级排序的问题清单
- 具体修复方案

---

## 15. 文档生成

### 提示词
```
根据当前项目中所有函数的 JSDoc 注释，生成 API 参考文档 (Markdown 格式)。

要求:
1. 按模块分组 (图层操作 / 文字动画 / 音频处理 / 视频增强 / 工具)
2. 每个函数包含: 签名、参数表、返回值、示例、错误码
3. 在文档开头添加目录
4. 标注每个函数的 AE 版本兼容性
5. 标注哪些函数是异步的 (使用 scheduleTask)

扫描范围: host/ 目录下所有 .jsx 文件
```

### 期望输出
- 结构化的 API 参考文档
- 按模块分组
- 含目录和交叉引用

---

## 提示词编写原则

1. **精确约束**: 明确指定 ES3/ES5 语法要求
2. **输出格式**: 指定期望的代码结构和返回格式
3. **上下文注入**: 提供项目规范的关键约束
4. **反模式告知**: 明确列出禁止使用的 API (如 app.refresh)
5. **分段复杂任务**: 复杂任务拆分为多个小提示词，逐步构建

---

> **维护**: 每新增一个经过验证的提示词，请追加到此文档并标注测试日期和结果。
