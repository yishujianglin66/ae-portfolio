# AE Bridge 自动化任务交接文档

**创建时间**: 2026-09-07 18:30  
**最后更新**: 2026-09-07 18:30  
**状态**: 阻塞 - AE 窗口被模态对话框阻塞

---

## 一、任务目标

将 139 个 premium beat-aligned effects（来自 `run53v43_effects_premium_v2.json`）通过 AE Bridge 自动化应用到视频项目，最终输出成品 MP4。

---

## 二、当前状态

### 2.1 已完成
- ✅ AE Bridge 文件轮询协议实现（`.ae-mcp-bridge/ae_command.json` → `ae_result.json`）
- ✅ Listener 脚本基础功能（`ae_mcp_auto_listener.jsx`）
- ✅ ComputerUse MCP 与 AE 交互（菜单导航、文件对话框）
- ✅ 脚本加载机制（通过 File > Scripts > 运行脚本文件）
- ✅ 139 个特效配置文件生成（`output/unified_run53/run53v43_effects_premium_v2.json`）
- ✅ AE 项目文件存在（`output/unified_run53/ae_shots.aep`）

### 2.2 待完成
- ❌ **阻塞**: AE 窗口被模态对话框阻塞，无法交互
- ❌ Listener 轮询机制未验证（`app.scheduleTask` 字符串评估可能无法访问 `$.global` 属性）
- ❌ 139 个特效未应用到项目
- ❌ 未执行 aerender 渲染
- ❌ 未输出最终 MP4

---

## 三、技术架构

### 3.1 AE Bridge 协议

```
Python 脚本 → 写入 ae_command.json → AE Listener 轮询 → 执行命令 → 写入 ae_result.json
```

**文件位置**:
- 命令文件: `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json`
- 结果文件: `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json`
- 日志文件: `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_auto_listener.log`

**命令格式**:
```json
{
  "command": "ping|getProjectInfo|listCompositions|executeAtomScript|...",
  "args": {},
  "timestamp": "2026-09-07T18:00:00.000Z",
  "processed": false
}
```

### 3.2 Listener 脚本

**文件**: `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/ae_mcp_auto_listener.jsx`

**关键函数**:
- `startMcpListener()`: 启动监听器，设置轮询
- `processCommand()`: 处理命令（第 1311 行开始）
- 支持的命令: `ping`, `getProjectInfo`, `listCompositions`, `createComposition`, `importFootage`, `executeAtomScript`, 等

**轮询机制**（最新修改，未验证）:
```javascript
// 内联轮询代码，避免 $.global 访问问题
var pollCode = "(function(){" +
    "var LOG='...'; var CMD='...'; var RES='...';" +
    // ... 完整轮询逻辑 ...
    "app.scheduleTask(arguments.callee.toString()+'()',500,false);" +
"})()";
app.scheduleTask(pollCode, 500, false);
```

### 3.3 Startup 延迟加载

**文件**: `C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Scripts/Startup/z_mcp_bridge_startup.jsx`

**机制**: AE 启动后延迟 5 秒加载 listener，避免 Startup 阶段 app/scheduleTask 未就绪。

**问题**: 多次 AE 重启后，Startup 脚本未执行（startup.log 无新条目）。

---

## 四、当前阻塞问题

### 4.1 AE 窗口被模态对话框阻塞

**现象**:
- AE 主窗口 (hwnd=6226104) 显示为 disabled
- 窗口尺寸仅 37x158（只有标题栏）
- 子元素包含一个"对话框"（element index 1），但 UIA 无法检查其内容
- 所有菜单交互、键盘输入均无效

**尝试的解决方案**（均失败）:
1. ❌ 按 Enter/Escape/Space/Tab - 无效
2. ❌ 按 Alt+Y - 无效
3. ❌ 点击屏幕坐标 (960, 620) - 无效
4. ❌ 发送 WM_CLOSE 消息 - 无效
5.  使用 UIA perform_secondary_action "Raise" - 无效
6. ❌ 检查注册表/偏好设置 - `Pref_SCRIPTING_FILE_NETWORK_SECURITY` 已设为 "1"

**可能原因**:
- 对话框是 AE 自定义绘制的模态对话框（DroverLord 窗口类），非标准 Windows 对话框
- 可能是脚本执行错误对话框
- 可能是"允许脚本写入文件"确认对话框（尽管偏好已启用）

### 4.2 Listener 轮询机制未验证

**问题**: `app.scheduleTask(string, delay, false)` 评估字符串时，可能无法访问 `$.global` 属性。

**尝试的解决方案**:
1. ❌ 使用 `$.global.__mcpCheckForCommands()` - 未触发
2. ✅ 改为内联完整代码字符串（最新修改，未测试）

---

## 五、关键文件清单

| 文件 | 路径 | 说明 |
|------|------|------|
| Listener 脚本 | `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/ae_mcp_auto_listener.jsx` | AE 端监听器 |
| Startup 脚本 | `C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/Scripts/Startup/z_mcp_bridge_startup.jsx` | AE 启动自动加载 |
| 命令文件 | `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_command.json` | Python→AE 命令通道 |
| 结果文件 | `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_result.json` | AE→Python 结果通道 |
| 日志文件 | `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/ae_auto_listener.log` | Listener 运行日志 |
| Startup 日志 | `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/.ae-mcp-bridge/startup.log` | Startup 加载日志 |
| 特效配置 | `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/unified_run53/run53v43_effects_premium_v2.json` | 139 个特效配置 |
| AE 项目 | `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/unified_run53/ae_shots.aep` | 当前 AE 项目 |
| Bridge 客户端 | `C:/Users/Administrator/Desktop/AE-Knowledge-Vault/ae/ae_mcp_client.py` | Python 端客户端 |

---

## 六、下一步建议

### 方案 A: 强制重启 AE（推荐）

1. **强制终止 AE 进程**:
   ```bash
   taskkill /IM AfterFX.exe /F
   ```
   如果失败，使用 Process Explorer 或重启电脑。

2. **清除 AppState 注册表**:
   ```bash
   reg delete "HKCU\Software\Adobe\After Effects\25.0" /v "AppState" /f
   reg delete "HKCU\Software\Adobe\After Effects\25.3" /v "AppState" /f
   ```

3. **清理桥接文件**:
   ```bash
   rm -f .ae-mcp-bridge/ae_command.json .ae-mcp-bridge/ae_result.json
   ```

4. **重启 AE**:
   ```bash
   "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/AfterFX.exe" "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/unified_run53/ae_shots.aep"
   ```

5. **等待 15 秒**，检查 `ae_auto_listener.log` 是否有新条目。

6. **发送 ping 测试**:
   ```json
   {"command":"ping","args":{},"timestamp":"...","processed":false}
   ```
   写入 `ae_command.json`，等待 3 秒，检查 `ae_result.json`。

### 方案 B: 如果 Startup 脚本仍不加载

手动加载脚本：
1. 使用 ComputerUse 打开 AE
2. File > Scripts > 运行脚本文件
3. 选择 `ae_mcp_auto_listener.jsx`
4. 检查日志确认加载成功

### 方案 C: 如果轮询仍不工作

修改 listener 脚本，使用 `$.evalFile()` 或 `eval()` 在启动时直接执行轮询代码，而不是依赖 `scheduleTask` 的字符串评估。

---

## 七、特效应用流程（Bridge 连通后）

1. **发送 executeAtomScript 命令**，应用每个特效：
   ```json
   {
     "command": "executeAtomScript",
     "args": {
       "script": "// 应用特效的 ExtendScript 代码"
     },
     "timestamp": "...",
     "processed": false
   }
   ```

2. **批量应用 139 个特效**（可能需要分批，避免 AE 崩溃）

3. **保存项目**:
   ```json
   {"command": "saveProject", "args": {}, ...}
   ```

4. **使用 aerender 渲染**:
   ```bash
   "C:/Program Files/Adobe/Adobe After Effects 2025/Support Files/aerender.exe" \
     -project "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/unified_run53/ae_shots.aep" \
     -comp "合成名称" \
     -output "C:/Users/Administrator/Desktop/AE-Knowledge-Vault/output/unified_run53/final.mp4"
   ```

---

## 八、已知问题与注意事项

1. **Bridge 每次 AE 会话只能处理 1-2 个命令**，之后需要删除旧命令/结果文件
2. **AE 窗口可访问性异常**: 主窗口 bounds 为 37x158（只有标题栏），但 accessibility tree 包含 67 个节点
3. **Startup 脚本可靠性差**: 多次 AE 重启后未执行
4. **`app.scheduleTask` 字符串评估**: 可能无法访问 `$.global` 属性，需使用内联代码
5. **`arguments.callee` 已弃用**: 在严格模式下可能不可用

---

## 九、快速验证命令

```bash
# 检查 AE 是否运行
tasklist | grep -i afterfx

# 检查 Listener 日志
tail -20 .ae-mcp-bridge/ae_auto_listener.log

# 发送 ping 测试
echo '{"command":"ping","args":{},"timestamp":"2026-09-07T18:30:00.000Z","processed":false}' > .ae-mcp-bridge/ae_command.json
sleep 3
cat .ae-mcp-bridge/ae_result.json

# 清除 AppState
reg delete "HKCU\Software\Adobe\After Effects\25.3" /v "AppState" /f
```

---

## 十、联系信息

- **项目路径**: `C:/Users/Administrator/Desktop/AE-Knowledge-Vault`
- **AE 版本**: Adobe After Effects 2025 (25.3x71)
- **平台**: Windows 10.0.26200 x64
- **Python 版本**: 待确认（使用 `python` 命令）

---

**交接人**: Qoder Agent  
**接收人**: 下一个会话/程序  
**期望行动**: 解决 AE 对话框阻塞问题，验证 Bridge 连通性，应用 139 个特效，输出最终视频
