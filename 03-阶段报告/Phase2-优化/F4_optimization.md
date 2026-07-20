# F4 优化设计书 — 异步音频提取

> **模块**: F4 — 从音频图层提取音频轨道为 WAV
> **优先级**: 🔴 P0 (AP-001 同步阻塞)
> **日期**: 2026-06-05

---

## 1. 问题诊断

### 1.1 核心问题: 同步 system.callSystem() 阻塞 AE UI

```javascript
// F4_extract_audio.jsx:252 — AP-001 反模式
var execResult = system.callSystem(cmd);  // ❌ AE UI 冻结 5-30s
```

### 1.2 影响范围

- 所有 FFmpeg 操作 (提取/转换) 会让 AE 无响应 5-30 秒
- 操作系统将 AE 标记为"无响应"
- 用户无法执行任何其他操作

### 1.3 附属问题

| 问题 | 严重性 | 描述 |
|------|--------|------|
| Logger 重复 | 🟡 | 15 行 Logger 加载模式重复 |
| findFFmpeg 重复 | 🟡 | 与 F5/config.py/server.py 多处重复 |
| 硬编码 Desktop | 🟡 | 输出路径不可配置 |
| 无 CEP 接口 | 🟢 | 无法从面板调用 |

---

## 2. 优化方案

### 2.1 架构: Submit → Poll → Complete 三元组

```
F4_extract_audio.jsx (ExtendScript)
  │
  ├── f4Submit(inputFile, outputDir, options)
  │     └→ 启动后台 Python/FFmpeg → 返回 jobId
  │
  ├── f4CheckStatus(jobId)
  │     └→ 查询进度 → 返回 {status, progress, message}
  │
  └── f4GetOutput(jobId)
        └→ 返回输出文件路径 → 导入 AE
```

### 2.2 实现策略

**方案 A (推荐)**: 复用现有 ae_bridge.py → FastAPI 异步端点
  优点: 与调试阶段新增的 `/tools/async/*` 端点无缝衔接
  缺点: 需要服务器运行

**方案 B**: 纯 ExtendScript + `app.scheduleTask()`
  优点: 无需服务器
  缺点: 进度检测复杂，跨平台差

**选择: 方案 A** — 项目已有完善的 Submit-Poll 基础设施。

### 2.3 代码变更清单

#### 变更 1: Logger 加载去重
```diff
- // 18 行 try/catch evalFile + fallback
+ var scriptDir = new File($.fileName).parent.fsName;
+ $.evalFile(scriptDir + '/../_shared/AEStudioKit_ModuleLoader.jsx');
+ var LOG = AEStudioKit.Loader.loadLogger(scriptDir);
```

#### 变更 2: findFFmpeg 提取到共享
使用项目已有的 `ae_bridge.py` 中的 FFmpeg 定位逻辑。

#### 变更 3: 异步执行 (核心)
```javascript
function runF4AudioExtract() {
    // ... 验证逻辑不变 ...
    
    // 改用异步提交
    var jobId = f4SubmitExtraction(sourceFile.fsName, outputPath, {
        inPoint: inPoint,
        duration: duration,
        format: 'wav',
        sampleRate: 44100
    });
    
    if (jobId) {
        // 注册轮询
        app.scheduleTask('F4_PollExtraction', 2000, true);
        STATE.f4JobId = jobId;
        STATE.f4OutputPath = outputPath;
    }
}

function F4_PollExtraction() {
    var status = f4CheckStatus(STATE.f4JobId);
    if (status.done) {
        app.cancelTask(taskId);
        f4OnComplete(status);
    }
}
```

#### 变更 4: 添加 CEP dispatch 接口
```javascript
function F4_dispatch(action, params) {
    switch (action) {
        case 'extract': return runF4AudioExtract(params);
        case 'check': return f4CheckStatus(params.jobId);
        case 'download': return f4GetOutput(params.jobId);
    }
}
```

---

## 3. 兼容性

| 维度 | 状态 |
|------|------|
| AE 版本 | ✅ AE 2023-2025 兼容 |
| ES3 语法 | ✅ 仅 var/function/字符串拼接 |
| 回退兼容 | ✅ 保留同步模式作为 fallback |
| UTF-8 BOM | ✅ 必须 |
| 依赖 | FFmpeg (已有), Python 服务 (已有) |

---

## 4. 测试验收

- [ ] 选中音频图层 → 异步提取 → AE UI 保持响应
- [ ] 进度日志实时更新
- [ ] 提取完成自动弹窗通知
- [ ] 源文件不存在 → 友好错误提示 (不崩溃)
- [ ] FFmpeg 未找到 → 友好提示
- [ ] 超大文件 (>500MB) → 超时处理
