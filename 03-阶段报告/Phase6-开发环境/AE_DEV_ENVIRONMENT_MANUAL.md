# VSCode + After Effects 开发环境标准化手册

> **版本**: 1.0.0
> **生效日期**: 2026-06-10
> **适用范围**: AE StudioKit 企业级扩展开发团队
> **目标**: 任何新开发者按此手册 30 分钟内可搭建完整开发环境并开始调试

---

## 目录

1. [环境要求](#1-环境要求)
2. [快速开始 (30 分钟)](#2-快速开始-30-分钟)
3. [插件安装与配置](#3-插件安装与配置)
4. [每日开发工作流](#4-每日开发工作流)
5. [调试指南](#5-调试指南)
6. [代码规范](#6-代码规范)
7. [提交前检查](#7-提交前检查)
8. [常见问题 FAQ](#8-常见问题-faq)
9. [附录：配置文件完整列表](#9-附录配置文件完整列表)

---

## 1. 环境要求

### 1.1 硬件

| 组件 | 最低要求 | 推荐配置 |
|------|----------|----------|
| CPU | Intel i5 / AMD Ryzen 5 | Intel i7 / AMD Ryzen 7 |
| RAM | 16 GB | 32 GB |
| GPU | NVIDIA GTX 1060 (6 GB VRAM) | NVIDIA RTX 4060 (8 GB VRAM) |
| 磁盘 | SSD 256 GB | SSD 512 GB + HDD 1 TB |
| 显示器 | 1920×1080 | 2560×1440 (双屏) |

### 1.2 软件

| 软件 | 版本要求 | 说明 |
|------|----------|------|
| **Windows** | 10/11 Pro (x64) | — |
| **After Effects** | 2025 (v25.x) 推荐 / 2023-2024 兼容 | 注册表显示 HKLM 22/23/25 |
| **VSCode** | 1.122+ | — |
| **Git** | 2.54+ | — |
| **Node.js** | v22+ | AE-MotionStudio 构建需要 |
| **Python** | 3.10–3.13 | GPU 服务器需要 |
| **FFmpeg** | 8.1.1 | 项目已捆绑 |

### 1.3 VSCode 插件 (4 个必备)

| # | 插件 ID | 用途 | 状态 (2026-06-10) |
|---|---------|------|-------------------|
| 1 | `adobe.extendscript-debug` | ExtendScript 调试器 (断点/变量/堆栈) | ✅ 已安装 v2.1.0 |
| 2 | `voidgazer.ae-jsx-runner` | 一键发送 .jsx 到 AE 执行 | ❌ 需安装 |
| 3 | `adpyke.js-jsx-snippets` | ExtendScript 代码片段库 | ❌ 需安装 |
| 4 | `alibaba-cloud.tongyi-lingma` | 通义灵码 AI 编程助手 | ❌ 需安装 |

---

## 2. 快速开始 (30 分钟)

### 步骤 1: 克隆项目 (2 分钟)

```bash
cd ~/Desktop
# 项目已存在于 skills/ae-vocal-remover/
# 如需要重新克隆:
# git clone <repo-url> skills
```

### 步骤 2: 打开工作区 (1 分钟)

```bash
# 双击工作区文件
start AE-Extension-Dev.code-workspace
```

或在 VSCode 中: `文件 → 打开工作区 → 选择 AE-Extension-Dev.code-workspace`

### 步骤 3: 安装必备插件 (5 分钟)

```bash
# 在 VSCode 终端执行:
code --install-extension voidgazer.ae-jsx-runner
code --install-extension adpyke.js-jsx-snippets
code --install-extension alibaba-cloud.tongyi-lingma
```

或手动: `Ctrl+Shift+X` → 搜索插件名 → 安装

### 步骤 4: 启用 CEP 调试模式 (1 分钟)

```powershell
# 以管理员身份在 PowerShell 中执行:
reg add "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_DWORD /d 1 /f

# 验证:
reg query "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode
# 应输出: PlayerDebugMode    REG_DWORD    0x1
```

### 步骤 5: 部署 CEP 扩展 (2 分钟)

```bash
# 在 VSCode 终端执行 (或使用 Ctrl+Shift+P → Tasks: Run Task → 📦 部署到 CEP)
cep_dir="$APPDATA/Adobe/CEP/extensions/ae-vocal-remover"
mkdir -p "$cep_dir/host/text-fx" "$cep_dir/host/vocal" "$cep_dir/host/bridge" "$cep_dir/host/utils" "$cep_dir/client" "$cep_dir/CSXS"

# 复制文件
cp host/*.jsx "$cep_dir/host/"
cp host/text-fx/*.jsx "$cep_dir/host/text-fx/"
cp host/vocal/*.jsx "$cep_dir/host/vocal/"
cp host/bridge/*.jsx "$cep_dir/host/bridge/"
cp host/utils/*.jsx "$cep_dir/host/utils/"
cp client/CSInterface.js "$cep_dir/client/"
cp CSXS/manifest.xml "$cep_dir/CSXS/"
```

### 步骤 6: 启动 Python 服务器 (2 分钟)

```bash
cd server
# 安装依赖 (首次):
# bash install_deps.bat

# 启动服务器:
python server.py
# 或: bash start_server.bat
# 或: Ctrl+Shift+P → Tasks: Run Task → 🧪 运行 Python 服务器
```

验证: `curl http://127.0.0.1:8765/health` → `{"status":"ok"}`

### 步骤 7: 启动 After Effects (3 分钟)

1. 启动 AE 2025
2. 打开 CEP 面板: `窗口 → 扩展 → AE StudioKit`
3. 如无此菜单项: CEP PlayerDebugMode 未设置 → 返回步骤 4

### 步骤 8: 验证连接 (3 分钟)

在 VSCode 中创建测试文件 `test-connection.jsx`:

```javascript
// test-connection.jsx
alert("✅ VSCode 与 AE 已连接！\n时间: " + (new Date()).toString());
$.writeln("=== 连接测试成功 ===");
```

1. 按 `F5` → 选择 "🚀 AE — 启动并调试当前 JSX"
2. AE 应弹出对话框
3. VSCode 调试控制台应显示 `=== 连接测试成功 ===`

### 步骤 9: 配置 Git 用户 (1 分钟)

```bash
git config user.name "你的名字"
git config user.email "你的邮箱"
```

### 步骤 10: 🎯 开始编码！

```
⏱ 总耗时: ≤30 分钟
✅ 环境就绪: VSCode + AE 2025 + CEP 面板 + 调试器
🚀 下一步: Ctrl+Alt+R 运行脚本 / F5 启动调试
```

---

## 3. 插件安装与配置

### 3.1 ExtendScript Debugger (`adobe.extendscript-debug`)

**状态**: ✅ 已安装 v2.1.0

**功能**:
- ExtendScript 断点调试
- 变量监视与修改
- 调用堆栈导航
- 条件断点与日志断点
- 未捕获异常自动中断

**launch.json** 已配置 5 种调试模式 (详见 [.vscode/launch.json](../../.vscode/launch.json)):
1. 🚀 启动并调试当前 JSX (`stopOnEntry: true`)
2. 🔗 附加到已运行脚本
3. ▶️ 直接运行不调试
4. 🏠 调试 CEP Host (index.jsx)
5. 🧩 调试特定 F 模块

**设置** (在 `.vscode/settings.json`):
```json
{
    "extendscript.debug.breakOnCaughtExceptions": false,
    "extendscript.debug.breakOnUncaughtExceptions": true,
    "extendscript.debug.showExceptionStack": true
}
```

**常见问题**: 调试器无法连接 AE
- 确保 AE 已启动
- 检查 TCP 端口 8090 未被占用: `netstat -ano | findstr :8090`
- 重启 VSCode 和 AE

### 3.2 AE JSX Runner (`voidgazer.ae-jsx-runner`)

**状态**: ⬜ 待安装

**功能**: 将 .jsx 文件一键发送到 AE 执行 (无需启动调试器)

**安装**:
```bash
code --install-extension voidgazer.ae-jsx-runner
```

**配置** (在 `.vscode/settings.json`):
```json
{
    "aeRunner.aePath": "C:\\Program Files\\Adobe\\Adobe After Effects 2025\\Support Files\\AfterFX.exe",
    "aeRunner.targetApp": "aftereffects",
    "aeRunner.port": 8089,
    "aeRunner.saveBeforeRun": true,
    "aeRunner.encoding": "utf8"
}
```

**快捷键** (在 `keybindings.json`):
```json
[
    { "key": "ctrl+alt+r", "command": "ae-runner.runFile" },
    { "key": "ctrl+alt+s", "command": "ae-runner.runSelection" }
]
```

**AE 端配合**:
- 方法 A: 在 AE 中运行 `vscode-bridge.jsx` (插件自带)
- 方法 B: 使用 CEP 面板的 CSInterface.evalScript() (本项目的桥接方式)

**故障排除**:
| 症状 | 解决方案 |
|------|----------|
| 无法连接 AE | AE 未启动 / 防火墙阻止 TCP 8089 |
| 脚本无效果 | AE bridge 脚本未运行 / 权限不足 |
| 中文乱码 | 设置 `"aeRunner.encoding": "utf8"` + 确保文件 BOM |

### 3.3 JS JSX Snippets (`adpyke.js-jsx-snippets`)

**状态**: ⬜ 待安装

**功能**: ExtendScript 代码片段库 + 项目自定义片段

**安装**:
```bash
code --install-extension adpyke.js-jsx-snippets
```

**项目自定义片段**: [.vscode/ae-extendscript.code-snippets](../../.vscode/ae-extendscript.code-snippets)

**常用片段速查**:

| 前缀 | 功能 | 展开内容 |
|------|------|----------|
| `ae-layer-loop` | 图层遍历 | TextLayer/AVLayer 类型判断 + try/catch + 日志 |
| `ae-schedule-task` | 异步分片 | scheduleTask 非阻塞执行 |
| `ae-cs-eval` | CEP 桥接 | CSInterface.evalScript 封装 + JSON 解析 |
| `ae-log-storage` | 文件日志 | 桌面诊断日志写入 |
| `ae-fmodule-dispatch` | F 模块接口 | $.global.F#\_dispatch 导出模板 |
| `ae-utils-init` | 安全命名空间 | Utils = {} → Utils.log = fn |
| `ae-dispatch-router` | cepDispatch | 完整路由模板 |
| `ae-property-safe` | 安全属性访问 | instanceof → matchName → 遍历回退 |
| `ae-comp-create` | 创建合成 | app.project.items.addComp() |
| `ae-import` | 导入文件 | ImportOptions 模板 |

### 3.4 Lingma / 通义灵码 (`alibaba-cloud.tongyi-lingma`)

**状态**: ⬜ 待安装

**功能**: AI 代码补全、错误解释、重构建议、自然语言生成代码

**安装**:
```bash
code --install-extension alibaba-cloud.tongyi-lingma
```

**安全规则** (⛔ 必须遵守):
1. **禁止上传完整项目** — 仅发送 ≤200 行局部片段
2. **禁止包含 API 密钥** — mvsep.com key 等
3. **禁止包含内网地址** — 服务器 IP、数据库连接串
4. **路径需脱敏** — `C:\Users\Administrator\...` → `~/...`

**推荐提示词** (详见 [PHASE5_LINGMA_AI_RULES.md](./PHASE5_LINGMA_AI_RULES.md)):
- "根据 AE ExtendScript 模型，为选中文字图层添加淡入动画，使用 ES3 语法"
- "解释这段代码在 AE 中抛出 TypeError 的原因"
- "将同步循环重构为 scheduleTask 异步模式"

---

## 4. 每日开发工作流

### 4.1 10 分钟启动清单

```
00:00  打开 VSCode 工作区 (双击 AE-Extension-Dev.code-workspace)
00:30  确认 4 个插件已激活 (扩展侧边栏)
01:00  启动 AE 2025 → 打开 CEP 面板
03:00  健康检查: curl http://127.0.0.1:8765/health
05:00  git checkout -b feature/xxx
07:00  打开目标 .jsx，Ctrl+Alt+R 快速测试
10:00  🎯 进入编码状态
```

### 4.2 快捷键参考

| 快捷键 | 功能 | 使用频率 |
|--------|------|----------|
| `F5` | 启动调试 (含断点) | ⭐⭐⭐⭐⭐ |
| `F10` | 单步跳过 | ⭐⭐⭐⭐⭐ |
| `F11` | 单步进入 | ⭐⭐⭐⭐ |
| `Shift+F5` | 停止调试 | ⭐⭐⭐⭐ |
| `F9` | 切换断点 | ⭐⭐⭐⭐⭐ |
| `Ctrl+Alt+R` | 运行当前 .jsx | ⭐⭐⭐⭐ |
| `Ctrl+Alt+S` | 运行选中代码 | ⭐⭐⭐ |
| `Ctrl+Shift+B` | 提交前检查 | ⭐⭐⭐ |
| `Ctrl+Shift+P` → `Tasks` | 选择构建任务 | ⭐⭐ |

### 4.3 开发-测试循环

```
编写代码 → Ctrl+S → F5 (调试) 或 Ctrl+Alt+R (运行)
    │                    │
    └──── 观察结果 ──────┘
         ├─ 成功: 继续下一个功能
         └─ 失败:
              ├─ F9 设断点 → F5 → 单步跟踪
              ├─ 调试控制台测试修复
              └─ 修复 → 重新运行
```

---

## 5. 调试指南

### 5.1 调试黄金法则

遇到 "脚本无响应、无输出、图层无变化" 时，按以下步骤:

1. **复现** — 确认问题稳定可复现
2. **二分法缩小** — 注释掉后半段代码定位故障区
3. **断点定位** — F9 设断点 → F5 → F10 单步
4. **检查 AE 状态** — 调试控制台: `app.project.activeItem`
5. **修复 → 验证** — 取消断点 → 确认修复

### 5.2 条件断点与日志断点

| 类型 | 设置方式 | 效果 | 示例 |
|------|----------|------|------|
| 条件断点 | 行号右键 → Conditional BP | 仅条件满足时暂停 | `layer.name === "target"` |
| 日志断点 | 行号右键 → Logpoint | 输出变量值 (不暂停) | `图层{i}: {layer.name}` |

**日志断点优于 $.writeln()**: 无需修改代码、即时清除、零性能开销

### 5.3 异常捕获

配置 `.vscode/settings.json`:
```json
"extendscript.debug.breakOnUncaughtExceptions": true
```

异常时自动暂停 → 变量面板 → 调用堆栈 → 定位根因

### 5.4 CEP 面板调试技巧

1. **面板日志**: 桌面 `cep_init_debug.log`
2. **ExtendScript 日志**: `$.writeln()` 输出到 ESTK 控制台
3. **面板终端**: AE → 窗口 → 扩展 → AE StudioKit → 按 F12 (Chromium DevTools)
4. **Bridge 诊断**: `client/test-bridge.html` 测试 evalScript 通信

---

## 6. 代码规范

### 6.1 ExtendScript (host/*.jsx)

| 规则 | 说明 |
|------|------|
| **仅 ES3 语法** | 禁止 const/let/箭头函数/模板字符串/class |
| **UTF-8 BOM 必须** | 文件首 3 字节 = `EF BB BF` |
| **类型守卫** | `typeof X === "undefined"` 检查 |
| **异步长操作** | `scheduleTask()` 分段执行，每段 ≤3 秒 |
| **安全赋值** | 先创建对象再赋值方法: `Utils = {}; Utils.log = fn;` |
| **错误处理** | 所有顶层 try-catch，`$.writeln()` 备用日志 |

### 6.2 CEP 面板 (client/*.js)

| 规则 | 说明 |
|------|------|
| **仅 ES5 语法** | 禁止 const/let/箭头/class/模板字符串/fetch |
| **XMLHttpRequest** | 替代 fetch |
| **Flexbox margin** | 替代 CSS gap (Chromium 74 不支持) |
| **IIFE 包装** | `(function(){'use strict';...})()` |
| **evalScript 检查** | 所有返回值检查 null |

### 6.3 Python (server/*.py)

| 规则 | 说明 |
|------|------|
| **类型注解** | 推荐使用 |
| **统一端口** | 从 config.py 导入 |
| **错误协议** | `OK:<JSON>` / `ERROR:<msg>` / `PROGRESS:<pct>` |

### 6.4 BOM 检查命令

```bash
# 检查单个文件
xxd -l 3 -p file.jsx  # 应返回 "efbbbf"

# 批量检查
for f in $(find host/ -name "*.jsx"); do
    if [ "$(xxd -l 3 -p "$f")" != "efbbbf" ]; then
        echo "❌ 缺少 BOM: $f"
    fi
done
```

### 6.5 废弃 API 检测

| API | 状态 | 替代 |
|-----|------|------|
| `app.refresh()` | 🔴 不存在 | `app.redraw()` |
| `confirm()` | 🟡 CEP 不可用 | 自定义 UI 模态框 |
| 同步 `system.callSystem()` | 🟡 长操作阻塞 | 异步 submit/poll/download |
| `cep_node.EvalScript()` | 🔴 已废弃 | `window.__adobe_cep__.evalScript()` |

---

## 7. 提交前检查

### 7.1 自动检查 (Ctrl+Shift+B)

运行默认构建任务 "🚀 全量提交前检查"，自动执行:

1. ✅ **UTF-8 BOM 检查** — 所有 .jsx 必须有 BOM
2. 🔍 **ES6 语法扫描** — 检测 const/let/=>/class
3. ⚠️ **废弃 API 扫描** — app.refresh / Socket / confirm()

### 7.2 手动检查清单

```
提交前确认:
[ ] 所有 .jsx 文件有 UTF-8 BOM
[ ] 无 const/let/箭头函数/class (ExtendScript ES3)
[ ] 无 app.refresh() (已改为 app.redraw())
[ ] 无 confirm() (已改为自定义模态框)
[ ] 长操作使用异步 submit/check/download
[ ] 所有 Utils 赋值前创建了 Utils = {}
[ ] 路径从 config 导入 (非硬编码)
[ ] 面板 CSInterface.js 先检查 __adobe_cep__
```

---

## 8. 常见问题 FAQ

### Q1: AE 中找不到扩展面板菜单

**原因**: CEP PlayerDebugMode 未启用

**解决方案**:
```powershell
reg add "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_DWORD /d 1 /f
```
完全退出 AE 并重新启动。

### Q2: evalScript 返回 null

**原因**: CSInterface.js polyfill 使用废弃的 `cep_node.EvalScript()`

**解决方案**: 确保 `client/CSInterface.js` 优先使用 `window.__adobe_cep__.evalScript()`

### Q3: ExtendScript 初始化报 TypeError: undefined 不是对象

**原因**: 尝试给不存在的对象赋值方法 (`UndefinedObj.method = fn`)

**解决方案**: 始终先创建对象再赋值:
```javascript
if (typeof AEStudioKit.Utils === "undefined") {
    AEStudioKit.Utils = {};           // ← 先创建对象!
    AEStudioKit.Utils.log = fn;      //  再赋值方法
}
```

### Q4: $.evalFile 崩溃 ExtendScript 引擎

**原因**: 被加载的 .jsx 文件中有硬解析错误

**解决方案**:
1. 检查文件是否有 UTF-8 BOM
2. 检查是否有 ES6+ 语法
3. 使用二分法注释定位崩溃文件
4. 使用空壳 stub 测试 `$.evalFile` 本身是否正常

### Q5: AE 界面卡住不动

**原因**: 同步 `system.callSystem()` 长时间阻塞

**解决方案**: 改造为异步 submit → poll → download 模式，或用 `scheduleTask()` 分片

### Q6: 脚本无错误但图层无变化

**调试流程**:
1. 检查 `app.project.activeItem` 是否为有效 CompItem
2. 检查 `comp.selectedLayers.length` 是否 > 0
3. 检查图层类型: `layer instanceof TextLayer`
4. 在目标函数入口设断点，确认代码被执行

### Q7: 中文注释在 AE 中显示乱码

**原因**: .jsx 文件缺少 UTF-8 BOM

**解决方案**:
```bash
printf '\xef\xbb\xbf' | cat - file.jsx > file-fixed.jsx
```

### Q8: JavaScript 文件保存后没有触发 Live Reload

**说明**: CEP 面板不支持 Live Reload。每次修改代码后需要:
1. 在 AE 面板中按 F5 刷新
2. 或关闭重开扩展面板
3. ExtendScript 文件修改后需重启 AE 或重新 evalFile

### Q9: 如何调试面板 HTML/JS?

在 AE 扩展面板中按 `F12` 打开 Chromium DevTools (需 PlayerDebugMode 启用)。

### Q10: 两个 Python 服务器端口冲突?

| 服务器 | 端口 | 框架 |
|--------|------|------|
| v4.0 主项目 | `8765` | FastAPI |
| AE-MotionStudio | `54321` | Flask |

两个端口独立，可同时运行。

---

## 9. 附录：配置文件完整列表

### 项目配置文件位置

```
skills/
├── AE-Extension-Dev.code-workspace      # 工作区文件 (推荐入口)
└── ae-vocal-remover/
    ├── .vscode/
    │   ├── settings.json                 # 项目设置
    │   ├── launch.json                   # 调试配置 (5 种模式)
    │   ├── tasks.json                    # 构建任务 (BOM/ES6/API 检查)
    │   └── ae-extendscript.code-snippets # 项目代码片段
    ├── docs/phase6-dev-environment/
    │   ├── AE_DEV_ENVIRONMENT_MANUAL.md  # 📖 本手册
    │   ├── PHASE1_ENVIRONMENT_DETECTION.md # 环境检测报告
    │   ├── PHASE2_JSX_RUNNER_CONFIG.md   # AE Runner 配置
    │   ├── PHASE3_EXTENDSCRIPT_DEBUGGER.md # 调试器深度集成
    │   ├── PHASE4_JSX_SNIPPETS.md        # 代码片段指南
    │   ├── PHASE5_LINGMA_AI_RULES.md     # AI 助手规则
    │   └── PHASE6_UNIFIED_WORKFLOW.md    # 统一工作流
    └── .claude/
        └── CLAUDE.md                     # 项目开发指南
```

### 环境变量参考

```bash
# CEP 扩展部署路径
%APPDATA%/Adobe/CEP/extensions/ae-vocal-remover/

# AE 安装路径
C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\

# Python 服务器
http://127.0.0.1:8765  (v4.0 FastAPI)
http://127.0.0.1:54321 (MotionStudio Flask)

# 调试端口
TCP 8090 — ExtendScript Debugger
TCP 8089 — AE JSX Runner Bridge
```

### 重要注册表项

```
HKCU\Software\Adobe\CSXS.12\PlayerDebugMode = 1  (必须)
```

---

> 📖 **相关文档**:
> - 项目审计: `AUDIT_REPORT.md`
> - 项目开发指南: `.claude/CLAUDE.md`
> - 架构设计: `docs/phase3/PHASE3_ARCHITECTURE.md`
> - 测试规格: `docs/phase5/PHASE5_TEST_SPEC.md`
>
> 📧 **技术支持**: 查阅 FAQ §8 或检查桌面诊断日志 `cep_init_debug.log`

---

> **文档版本历史**
> - v1.0.0 (2026-06-10): 初始发布 — 包含四个插件配置、完整工作流、30分钟快速启动指南
