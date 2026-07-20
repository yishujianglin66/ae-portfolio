# F7 优化设计书 — 异步文件下载

> **模块**: F7 — 文件下载 + 打开文件夹
> **优先级**: 🔴 P0 (AP-001 同步阻塞)
> **日期**: 2026-06-05

---

## 1. 问题诊断

### 核心问题

```javascript
// F7_download.jsx:157 — AP-001 反模式
var result = system.callSystem(cmd);  // ❌ AE UI 冻结 10s-5min
```

当下载大文件 (>50MB) 时, PowerShell Invoke-WebRequest 或 curl 都会阻塞 AE 主线程数分钟。

### 优化目标

1. Logger 加载 → ModuleLoader (3 行)
2. 同步下载 → 异步 PowerShell Job + 轮询
3. 添加进度显示
4. 添加 CEP dispatch 接口
5. 保留同步模式作为回退

---

## 2. 异步架构

```
PowerShell Start-Job (后台进程)
       │
       ├── 写入进度文件: %TEMP%/f7_download_progress_<jobId>.txt
       │
F7_PollDownload (app.scheduleTask, 每 1s)
       │
       ├── 读取进度文件 → 更新进度
       │
       └── 完成 → 取消轮询 → openFolder()
```

---

## 3. 测试验收

- [ ] 下载 10MB 测试文件 → AE UI 保持响应
- [ ] 进度每 1s 更新
- [ ] 下载完成自动打开文件夹
- [ ] 网络断开 → 超时提示
- [ ] URL 无效 → 友好错误提示
