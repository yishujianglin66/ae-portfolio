# 第二阶段：Adobe AE jsx & .tsx Runner 配置与连接

> **插件**: voidgazer.ae-jsx-runner
> **功能**: 将 .jsx/.jsxbin 脚本从 VSCode 直接发送到 After Effects 执行
> **目标**: 实现一键运行-调试闭环

---

## 2.1 插件核心功能

Adobe AE jsx & .tsx Runner 通过 TCP 套接字连接 After Effects，将脚本内容发送到 AE 的 ExtendScript 引擎执行，并在 VSCode 的输出面板显示结果。

### 工作原理

```
VSCode (编辑 .jsx)
    │
    ├─ 快捷键/命令面板触发
    │
    ├─ 插件通过 TCP :8089 连接 AE
    │
    ▼
After Effects (ExtendScript 引擎)
    │
    ├─ 接收脚本内容
    ├─ 执行 $.evalFile() 或直接 eval()
    │
    ▼
结果返回 VSCode 输出面板
```

### 支持的功能

| 功能 | 说明 |
|------|------|
| 运行当前文件 | 将当前打开的 .jsx 发送到 AE 执行 |
| 运行选中代码 | 仅发送选中的代码片段 |
| 运行并输出到 AE 控制台 | 结果显示在 AE 的 ExtendScript 控制台 |
| 目标应用选择 | 支持 AE / Photoshop / Illustrator |

## 2.2 插件安装与配置

### 安装

```bash
code --install-extension voidgazer.ae-jsx-runner
```

或在 VSCode 扩展面板搜索 `ae jsx runner`。

### VSCode 端配置 (settings.json)

```json
{
    // ========================================
    // AE JSX Runner 核心配置
    // ========================================

    // After Effects 可执行文件路径
    "aeRunner.aePath": "C:\\Program Files\\Adobe\\Adobe After Effects 2025\\Support Files\\AfterFX.exe",

    // 目标应用 (aftereffects / photoshop / illustrator)
    "aeRunner.targetApp": "aftereffects",

    // TCP 端口 (需与 AE 端脚本配合)
    "aeRunner.port": 8089,

    // 是否在运行前自动保存文件
    "aeRunner.saveBeforeRun": true,

    // 是否在 AE 控制台显示输出
    "aeRunner.showOutput": true,

    // 运行后是否聚焦到 AE
    "aeRunner.focusAfterEffects": false,

    // 默认编码
    "aeRunner.encoding": "utf8"
}
```

### AE 端配置

**方法一：安装 VSCode Bridge 脚本（推荐）**

此方法需要在 AE 中加载一个监听脚本，该脚本在后台等待 VSCode 的连接。

1. 下载 `vscode-bridge.jsx` 脚本（插件安装后自动包含）
2. 将脚本复制到 AE Scripts 目录：
   ```
   %PROGRAMFILES%\Adobe\Adobe After Effects 2025\Support Files\Scripts\ScriptUI Panels\
   ```
3. 在 AE 中：`文件 → 脚本 → 运行脚本文件`，选择并运行 `vscode-bridge.jsx`
4. 脚本将持续在后台监听 TCP 端口 8089

**方法二：使用 CEP 面板桥接（备选）**

如果本项目的 CEP 扩展面板已经工作（`cs.evalScript` 通信正常），可以直接利用现有的 CEP 桥接：

1. 确保 CEP PlayerDebugMode 已启用（见第一阶段 1.5）
2. 面板中的 `CSInterface.js` 已配置 `window.__adobe_cep__.evalScript` 桥接
3. VSCode 通过面板的 evalScript 功能间接与 AE 通信

**方法三：基于文件的热加载（兜底方案）**

如果 TCP 连接不可行，使用文件监听模式：

1. VSCode 保存 .jsx 到 AE 的 Scripts 目录
2. AE 通过 `$.evalFile()` 自动检测文件变更并重新加载

## 2.3 测试连接

### 测试脚本：`test-connection.jsx`

```javascript
// test-connection.jsx — 验证 VSCode 与 AE 连接
alert("✅ VSCode 与 AE 已连接！\n\n时间: " + (new Date()).toString());
$.writeln("=== VSCode → AE 连接测试成功 ===");
```

### 运行步骤

1. 在 VSCode 中打开 `test-connection.jsx`
2. 右键选择 `AE Runner: Run Current File` 或按快捷键 `Ctrl+Alt+R`
3. 预期结果：AE 弹出对话框显示 "VSCode 与 AE 已连接！"
4. VSCode 输出面板显示 `=== VSCode → AE 连接测试成功 ===`

### 故障排除清单

| 症状 | 可能原因 | 解决方案 |
|------|----------|----------|
| "无法连接到 AE" | AE 未启动或 bridge 脚本未运行 | 1. 确认 AE 已启动 <br> 2. 在 AE 中运行 `vscode-bridge.jsx` <br> 3. 检查端口 8089 是否被占用 |
| "连接超时" | 防火墙阻止 TCP 8089 | 1. Windows 防火墙 → 允许应用 <br> 2. 添加入站规则允许 TCP 8089 <br> 3. `netsh advfirewall firewall add rule name="AE Bridge" dir=in action=allow protocol=TCP localport=8089` |
| 脚本执行但无效果 | ExtendScript 引擎未初始化 | 1. 检查 AE ExtendScript 工具包 <br> 2. 重启 AE |
| 中文乱码 | 编码不匹配 | 1. 确保文件为 UTF-8 BOM <br> 2. 在 settings.json 中设置 `"aeRunner.encoding": "utf8"` |
| "app 未定义" | 脚本不在 AE 上下文中执行 | 确认 bridge 脚本在 AE 内部运行，而非外部 Node.js |
| 插件无响应 | 插件版本与 VSCode 不兼容 | 1. 更新 VSCode <br> 2. 更新插件到最新版本 <br> 3. 查看 VSCode 开发者控制台 (Ctrl+Shift+I) |

### 端口检查命令

```bash
# 检查端口 8089 是否被占用
netstat -ano | findstr :8089

# 测试 TCP 连接
powershell "Test-NetConnection -ComputerName localhost -Port 8089"
```

## 2.4 标准化操作流程 (SOP)

### 日常开发流程：一键执行脚本

```
┌─────────────────────────────────────────────────────────────┐
│  步骤 1: 启动环境                                            │
│  ├─ 打开 VSCode + AE 2025                                    │
│  └─ 确认 AE 中已运行 bridge 脚本 (或面板已打开)               │
│                                                              │
│  步骤 2: 编辑脚本                                            │
│  ├─ 在 VSCode 中打开目标 .jsx 文件                           │
│  └─ 确保文件以 UTF-8 BOM 编码保存                            │
│                                                              │
│  步骤 3: 执行                                                │
│  ├─ 快捷键: Ctrl+Alt+R (运行整个文件)                         │
│  ├─ 或: Ctrl+Alt+S (运行选中的代码片段)                       │
│  └─ 或: 右键 → "AE Runner: Run Current File"                │
│                                                              │
│  步骤 4: 观察结果                                            │
│  ├─ AE 对话框/控制台: 查看 UI 效果                           │
│  ├─ VSCode 输出面板: 查看 $.writeln() 输出                  │
│  └─ 如果有错误: 查看下方 "调试" 流程                         │
│                                                              │
│  步骤 5: 迭代                                                │
│  └─ 修改代码 → Ctrl+S → Ctrl+Alt+R → 观察 → 重复             │
└─────────────────────────────────────────────────────────────┘
```

### 快捷键绑定 (keybindings.json)

```json
[
    {
        "key": "ctrl+alt+r",
        "command": "ae-runner.runFile",
        "when": "editorLangId == 'javascript' && resourceExtname == '.jsx'"
    },
    {
        "key": "ctrl+alt+s",
        "command": "ae-runner.runSelection",
        "when": "editorLangId == 'javascript' && resourceExtname == '.jsx'"
    },
    {
        "key": "ctrl+alt+e",
        "command": "ae-runner.runInExtendScriptConsole",
        "when": "editorLangId == 'javascript' && resourceExtname == '.jsx'"
    }
]
```

### 命令面板入口

| 命令 | 快捷键 | 用途 |
|------|--------|------|
| `AE Runner: Run Current File` | `Ctrl+Alt+R` | 运行整个文件 |
| `AE Runner: Run Selected Code` | `Ctrl+Alt+S` | 运行选中代码 |
| `AE Runner: Run in ExtendScript Toolkit` | `Ctrl+Alt+E` | 在 ESTK 中运行 |
| `AE Runner: Kill Running Script` | `Ctrl+Alt+K` | 终止运行中的脚本 |

## 2.5 最佳实践

1. **运行前自动保存**: 始终启用 `"aeRunner.saveBeforeRun": true`，避免发送未保存的旧版本
2. **片段优先测试**: 大脚本先选中关键片段测试，确认逻辑正确后再运行完整文件
3. **日志标准格式**: 使用 `$.writeln("[TAG] message")` 格式，便于过滤输出
4. **避免长时间阻塞**: CEP 环境中同步操作不应超过 3 秒；长时间操作使用 `scheduleTask()` 异步
5. **文件编码检查**: 每个 .jsx 文件第一字节必须是 `0xEF 0xBB 0xBF` (UTF-8 BOM)

### 编码检查脚本

```bash
# 检查所有 .jsx 文件是否有 BOM
for f in $(find . -name "*.jsx" -type f); do
    if [ "$(xxd -l 3 -p "$f")" != "efbbbf" ]; then
        echo "❌ 缺少 BOM: $f"
    fi
done
```

---

> **下一阶段**: [PHASE3_EXTENDSCRIPT_DEBUGGER.md](./PHASE3_EXTENDSCRIPT_DEBUGGER.md)
