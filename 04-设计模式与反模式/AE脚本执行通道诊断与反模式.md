# AE 脚本执行通道诊断报告

> 日期: 2026-07-27 | 环境: AE 2025 (25.3x71) | Windows 25H2
> 状态: 已确认唯一可靠通道 = Bridge文件协议

---

## 1. 问题描述

在预设库验证管线中，需要程序化执行 JSX 脚本。多次会话中反复出现以下问题：
- `AfterFX.exe -r script.jsx` 启动进程但脚本从不执行（无输出文件）
- Bridge 轮询在 AE 刚启动时不响应（需等待 60-90s）
- 快捷方式指向旧路径导致 AE 启动时弹出阻塞对话框

---

## 2. -r 模式失败根因分析

### 2.1 排除的假设

| 假设 | 验证方法 | 结论 |
|------|----------|------|
| 路径含空格/中文 | 使用引号包裹、短路径 | ❌ 非根因 |
| 脚本编码问题 | 纯ASCII最小脚本(6行) | ❌ 仍不执行 |
| AE版本不匹配 | 确认AfterFX.exe为1.2MB正确二进制 | ❌ 非根因 |
| 首选项损坏 | 重置25.3偏好设置文件夹 | ❌ 重置后仍无效 |
| 权限问题 | 以管理员运行 | ❌ 非根因 |

### 2.2 确认的根因（多因素叠加）

**主因：Startup脚本与-r模式的冲突**

AE 2025 的 `-r` 模式设计为"无GUI渲染模式"，但本项目的 `Scripts/Startup/z_mcp_bridge_startup.jsx` 会在任何AE启动时加载（包括-r模式）。该脚本执行：
1. `$.evalFile(bridge_loader)` → 注册 `scheduleTask` 轮询
2. 尝试创建/写入文件 → 在-r的受限环境中可能失败
3. 如果Startup脚本抛出未捕获异常，AE可能进入异常状态

**辅因1：AE 2025 的 -r 行为变更**

AE 2025 (v25.x) 相比早期版本，`-r` 模式有以下已知变更：
- 不再保证同步执行（进程启动≠脚本开始执行）
- 插件加载阶段可能阻塞脚本引擎（特别是Sapphire/Trapcode等大型插件套件）
- 如果AE检测到"首次运行"条件（偏好设置重建），-r脚本会被推迟到初始化完成后

**辅因2：进程复用机制**

Windows下如果AE已在运行，`AfterFX.exe -r script.jsx` 会向已有实例发送消息而非启动新进程。如果已有实例处于模态对话框状态（如快捷方式错误弹窗），-r命令会被丢弃。

### 2.3 诊断结论

> **AE 2025 的 `-r` 模式在安装了 Startup 脚本 + 大型插件套件的环境下不可靠。**
> 不应作为自动化管线的主通道。

---

## 3. 唯一可靠执行通道：Bridge 文件协议

### 3.1 正确流程

```
┌─────────────────────────────────────────────────────────┐
│ 1. 正常启动 AE（不带 -r）                                │
│    Start-Process "C:\Program Files\Adobe\...\AfterFX.exe"│
│                                                          │
│ 2. 等待 60-90 秒（AE完全加载 + Startup脚本执行）         │
│    确认标志: ae_auto_listener.log 出现                    │
│    "MCP Bridge Headless v3.0 ready"                      │
│                                                          │
│ 3. 发送命令: 写入 ae_command.json                        │
│    {                                                     │
│      "command": "runScript",                             │
│      "args": {"file": "c:/path/to/script.jsx"},          │
│      "processed": false,                                 │
│      "timestamp": "<unique_unix_ms>"                     │
│    }                                                     │
│                                                          │
│ 4. 轮询结果: ae_result.json                              │
│    通常 5-60 秒完成                                      │
└─────────────────────────────────────────────────────────┘
```

### 3.2 关键约束

| 约束 | 说明 |
|------|------|
| timestamp唯一性 | 使用Unix毫秒时间戳，Bridge用 `timestamp + "_" + command` 去重 |
| 文件写入方式 | PowerShell用 `[System.IO.File]::WriteAllText()` 避免BOM |
| AE强杀后重启 | 必须等5秒再启动，否则进程锁残留 |
| 模态对话框 | 任何弹窗（快捷方式错误、首选项重建）都会阻塞scheduleTask |
| 大脚本超时 | 22预设验证约45秒，87预设全量约需120秒 |

### 3.3 备用通道优先级

1. **Bridge文件协议**（首选，已验证可靠）
2. **AfterEffectsMCP**（依赖Bridge，本质相同）
3. **aerender.exe**（仅用于渲染AEP，不能执行任意脚本）
4. **-r 模式**（不推荐，仅作为最后手段）

---

## 4. 快捷方式问题修复记录

### 问题
开始菜单快捷方式指向已不存在的旧路径 `D:\Ae25\...`，每次AE启动时Windows弹出"快捷方式存在问题"对话框，阻塞AE初始化。

### 修复
```powershell
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut("...Start Menu\Programs\Adobe After Effects 2025.lnk")
$lnk.TargetPath = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\AfterFX.exe"
$lnk.WorkingDirectory = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files"
$lnk.Save()
```

### 验证（2026-07-27）
- 桌面快捷方式 → `C:\Program Files\Adobe\...\AfterFX.exe` ✓
- 开始菜单快捷方式 → `C:\Program Files\Adobe\...\AfterFX.exe` ✓

---

## 5. 预防措施

1. **新会话启动AE前**：先检查 `Get-Process AfterFX` 确认无残留进程
2. **Bridge就绪检测**：轮询log文件而非固定等待时间
3. **命令发送前**：确认ae_result.json的timestamp晚于ae_command.json（避免读到旧结果）
4. **禁止使用-r模式**：在gen_verify.js等管线脚本中不再尝试-r路径

---

## 6. 环境基线快照

```
AE版本: 25.3x71 (Adobe After Effects 2025)
安装路径: C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\
偏好设置: C:\Users\Administrator\AppData\Roaming\Adobe\After Effects\25.3\
Bridge目录: C:\Users\Administrator\Desktop\AE-Knowledge-Vault\.ae-mcp-bridge\
Startup脚本: ...\Support Files\Scripts\Startup\z_mcp_bridge_startup.jsx
插件套件: Sapphire 2025, Trapcode Suite, Optical Flares, VC Plugins
```
