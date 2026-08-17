# PR MCP Bridge 开发进度与任务同步文档

> 最后更新：2026-07-24
> 当前阶段：Bridge v4 已验证可用，等待功能测试

---

## 一、项目背景与目标

为 Premiere Pro 建立自动化桥接系统，使得 Python 端可以通过 MCP 协议远程控制 PR 执行剪辑操作，包括：
- 序列创建、素材导入
- 轨道剪辑、转场添加
- 效果应用、调色
- 节拍同步自动剪辑
- 任意 JSX 脚本执行

---

## 二、技术演进历史

### v1 - v3：阻塞轮询（失败）
- 使用 `while` 循环 + `$.sleep()` 进行轮询
- **问题**：阻塞 PR 主线程，导致 PR 完全卡死，无法操作
- 尝试使用 `app.scheduleTask` 但在 PR 中不存在

### v4：`app.setTimeout` 非阻塞轮询（成功）
- 关键发现：PR 的 ExtendScript 环境提供 `app.setTimeout(callback, delay)`
- 通过递归调用 `app.setTimeout` 实现持续非阻塞轮询
- PR 完全不卡顿，UI 响应正常
- 轮询间隔：300ms

#### 核心实现
```javascript
function startPolling() {
    poll();
    app.setTimeout(startPolling, pollInterval);
}
```

---

## 三、Bridge v4 架构

### 文件位置
- **脚本路径**：`D:\Pr25\Adobe Premiere Pro 2025\Scripts\Startup\99_ae_kv_bridge_v4.jsx`
- **源文件**：`scripts/pr_bridge_v4.jsx`
- **通信目录**：`%TEMP%/ae_kv_pr_bridge/`

### 通信协议
```
Python 端写入 cmd_{id}.json  →  Bridge 轮询发现 → 执行命令
                                          ↓
Python 读取 result_{id}.json  ←  Bridge 写入结果
```

### 已支持命令
| 命令 | 说明 | 状态 |
|------|------|------|
| `ping` | 心跳检测 | ✅ 已验证 |
| `getInfo` | 获取 PR 基本信息 | ✅ 已验证 |
| `getProjectInfo` | 获取项目信息（序列列表） | ✅ 已验证 |
| `createSequence` | 创建新序列 | ✅ 代码实现，待验证 |
| `importMedia` | 导入素材文件 | ✅ 代码实现，待验证 |
| `addClipToTrack` | 添加素材到轨道 | ⏳ 通过 handler 实现 |
| `applyTransition` | 应用转场 | ⏳ 通过 handler 实现 |
| `addEffect` | 添加效果 | ⏳ 通过 handler 实现 |
| `saveProject` | 保存项目 | ✅ 代码实现，待验证 |
| `executeScript` | 执行任意 JSX 脚本 | ✅ 已验证 |
| `reloadHandlers` | 重新加载业务 handler | ✅ 代码实现，待验证 |

### Handler 机制
- Bridge 启动时自动加载 `bridge 目录/handler_*.jsx`
- 业务逻辑与核心桥接分离
- 支持运行时 `reloadHandlers` 动态更新，无需重启 PR

---

## 四、客户端封装

### 文件位置
`premiere_mcp_client.py`

### 使用方式
```python
from premiere_mcp_client import PremiereMCP

mcp = PremiereMCP()
result = mcp.ping()
result = mcp.get_info()
result = mcp.execute_script('app.project.name')
result = mcp.create_sequence("我的序列")
```

### 配置参数
- `bridge_dir`：桥接目录，默认 `%TEMP%/ae_kv_pr_bridge`
- `timeout`：命令超时时间，默认 30 秒
- `poll_interval`：结果轮询间隔，默认 0.3 秒

---

## 五、关键技术发现

### 1. PR ExtendScript 可用的异步方法
通过测试脚本 `scripts/test_settimeout.jsx` 验证：

| 方法 | 可用性 | 说明 |
|------|--------|------|
| `app.scheduleTask` | ❌ 不存在 | AE 中有，PR 中没有 |
| `app.setTimeout` | ✅ 可用 | 返回 undefined（无 ID） |
| `app.setInterval` | ❓ 未测试 | 可能存在 |

### 2. PR 启动脚本位置
```
D:\Pr25\Adobe Premiere Pro 2025\Scripts\Startup\
```
> 注意：不是安装根目录的 Startup，而是在 Scripts 子目录下

### 3. JSON 支持
PR 的 ExtendScript 环境**没有 JSON 对象**，需要手动 polyfill。

### 4. 事件系统
PR 支持丰富的事件监听：
- `onSequenceActivated`、`onActiveSequenceChanged`
- `onActiveSequenceStructureChanged`
- `onProjectChanged`、`onEncoderJobComplete` 等
- 通过 `app.addEventListener(eventName, callback)` 注册

---

## 六、当前进度

### ✅ 已完成
1. 确认 PR 安装路径：`D:\Pr25\Adobe Premiere Pro 2025\`
2. 发现 `app.setTimeout` 可用于非阻塞轮询
3. Bridge v4 核心功能开发完成
4. Bridge v4 部署到 PR Startup 目录
5. Ping 测试通过，响应正常
6. JSON polyfill 正常工作
7. Handler 动态加载机制实现

### 🔄 进行中
- Bridge v4 完整功能验证测试

### ⏳ 待完成
1. 验证 `createSequence`、`importMedia` 等核心命令
2. 补全 `addClipToTrack`、`applyTransition` 等业务 handler
3. 测试节拍剪辑脚本（`solo_leveling_pr_beat_edit.jsx`）
4. 与 solo_leveling_workflow.py 集成
5. 端到端风格化视频制作流程验证

---

## 七、下一步任务清单

### 任务 1：Bridge 功能全面验证
- 打开一个测试项目
- 测试 `createSequence` 命令
- 测试 `importMedia` 命令
- 测试 `executeScript` 复杂脚本
- 测试 `reloadHandlers` 动态加载

### 任务 2：业务 Handler 补全
- 创建 `handler_pr_track_operations.jsx`
  - `addClipToTrack`
  - `removeClipFromTrack`
  - `applyTransition`
  - `addEffect`
- 通过 `executeScript` + `registerHandler` 动态注册，无需重启 PR

### 任务 3：节拍剪辑自动化
- 准备测试音频（带节拍数据）
- 准备测试视频素材
- 通过 Bridge 执行节拍剪辑脚本
- 验证剪辑结果准确性

### 任务 4：工作流集成
- 在 `solo_leveling_workflow.py` 中集成 PR Bridge
- 实现 AE 合成 → 导出 → PR 剪辑 → 最终输出的完整链路
- 添加错误处理和重试机制

---

## 八、相关文件索引

| 文件 | 说明 |
|------|------|
| `scripts/pr_bridge_v4.jsx` | Bridge v4 主脚本源文件 |
| `scripts/handler_pr_business.jsx` | 业务 handler 示例 |
| `premiere_mcp_client.py` | Python 客户端 |
| `solo_leveling_pr_beat_edit.jsx` | 节拍剪辑脚本 |
| `scripts/test_settimeout.jsx` | setTimeout 测试脚本 |
| `scripts/test_schedule_task.jsx` | scheduleTask 测试（已废弃） |

---

## 九、调试技巧

### 查看 Bridge 日志
```
C:\Users\Administrator\AppData\Local\Temp\ae_kv_pr_bridge\bridge_log.txt
```

### 查看 Bridge 状态
```
C:\Users\Administrator\AppData\Local\Temp\ae_kv_pr_bridge\bridge_ready.txt
```

### 手动测试命令
直接在 bridge 目录中创建 `cmd_test.json`：
```json
{"action": "ping"}
```
观察是否生成 `result_test.json`。

### PR 不启动脚本排查
1. 确认文件在 `Scripts/Startup/` 目录下
2. 检查文件编码（UTF-8 BOM 可能有问题）
3. 查看 PR 首选项中是否启用了脚本

---

## 十、注意事项

1. **不要阻塞主线程**：PR 的 ExtendScript 中任何循环 + sleep 都会卡死 UI
2. **使用 setTimeout 递归**：正确的持续轮询方式
3. **命令文件执行后删除**：Bridge 处理完命令后会删除 cmd 文件，避免重复执行
4. **Handler 热更新**：新增业务逻辑优先写在 handler 文件中，通过 reloadHandlers 动态加载
5. **权限限制**：D 盘 PR 安装目录可能需要手动操作文件，自动化脚本可能被权限拦截

---

## 十一、同步说明

如果在另一个会话中继续此任务，请：
1. 先读取本文档了解当前进度
2. 检查 Bridge 是否运行中（查看 bridge_ready.txt）
3. 通过 `premiere_mcp_client.py` 发送 ping 测试连通性
4. 按"下一步任务清单"继续推进
5. 完成后更新本文档的进度状态
