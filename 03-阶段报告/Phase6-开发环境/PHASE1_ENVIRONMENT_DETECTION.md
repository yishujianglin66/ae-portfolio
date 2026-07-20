# 第一阶段：插件安装与环境检测报告

> **生成日期**: 2026-06-10
> **检测对象**: VSCode + After Effects 开发环境
> **目标**: 确认四个插件安装状态，建立基线配置

---

## 1.1 系统环境基线

| 检测项 | 结果 | 备注 |
|--------|------|------|
| **操作系统** | Windows 11 Pro (build 22631) | x64 |
| **VSCode 版本** | 1.122.1 (x64) | 最新稳定版 |
| **Node.js** | v22.22.3 | — |
| **Git** | 2.54.0.windows.1 | — |
| **Shell 环境** | MINGW64 (MSYS2) | bash 可用 |

## 1.2 After Effects 安装状态

| 版本 | 安装路径 | AfterFX.exe | 注册表条目 |
|------|----------|-------------|-------------|
| **AE 2025** (v25.x) | `C:\Program Files\Adobe\Adobe After Effects 2025` | ✅ 存在 | HKLM 25.0, HKCU 25.3 |
| **AE 2024** (v24.x) | 未安装独立目录 | — | HKCU 24.0 |
| **AE 2023** (v23.x) | 未安装独立目录 | — | HKLM 23.0, HKCU 23.0 |
| **AE 2022** (v22.x) | 未安装独立目录 | — | HKLM 22.0, HKCU 22.5 |

**结论**: 主要开发目标为 **AE 2025 (v25.x)**，注册表含 4 个版本的残留条目。

## 1.3 VSCode 插件安装状态

### 检查方法

在 VSCode 中按 `Ctrl+Shift+X` 打开扩展面板，搜索插件名称。或使用 CLI：

```bash
code --list-extensions | grep -iE "extendscript|jsx|lingma"
```

### 检测结果

| # | 插件名称 | 插件 ID | 状态 | 说明 |
|---|----------|---------|------|------|
| 1 | **ExtendScript Debugger** | `adobe.extendscript-debug` | ✅ 已安装 (v2.1.0) | Adobe 官方调试器 |
| 2 | **Adobe AE jsx & .tsx Runner** | `voidgazer.ae-jsx-runner` | ❌ **未安装** | 需从市场安装 |
| 3 | **JS JSX Snippets** | `adpyke.js-jsx-snippets` | ❌ **未安装** | 需从市场安装 |
| 4 | **Lingma (通义灵码)** | `alibaba-cloud.tongyi-lingma` | ❌ **未安装** | 阿里云 AI 编程助手 |

### 安装命令

在 VSCode 终端中执行以下命令安装缺失的插件：

```bash
# 安装 AE JSX Runner
code --install-extension voidgazer.ae-jsx-runner

# 安装 JS JSX Snippets
code --install-extension adpyke.js-jsx-snippets

# 安装 Lingma (通义灵码)
code --install-extension alibaba-cloud.tongyi-lingma
```

或通过 VSCode 扩展面板 (Ctrl+Shift+X) 搜索上述插件名称并点击安装。

## 1.4 旧版冲突检测

| 潜在冲突 | 状态 | 解决方案 |
|----------|------|----------|
| ExtendScript Debugger (Adobe 官方) | ✅ 唯一调试器，无冲突 | — |
| 其他 AE 脚本运行器 (如 `ae-script-runner`) | ✅ 未检测到 | 如果安装，禁用一个 |
| After Effects 相关扩展 | ✅ 无冲突 | — |
| 多个 ExtendScript 语言支持 | ✅ 无冲突 | — |

**冲突处理规则**:
1. 仅保留一个 AE 脚本运行器（推荐 `voidgazer.ae-jsx-runner`）
2. ExtendScript Debugger 必须为 Adobe 官方版本 (`adobe.extendscript-debug`)
3. 不同版本的同类插件需禁用旧版

## 1.5 CEP 开发环境检测

| 检测项 | 状态 | 操作 |
|--------|------|------|
| `CSXS.12` PlayerDebugMode (HKCU) | ❌ **未设置** | **必须启用** — CEP 扩展面板无法加载到 AE 中 |
| CEP 扩展部署路径 | ✅ `%APPDATA%/Adobe/CEP/extensions/` 存在 | ae-vocal-remover 已部署 |

### 🔴 紧急修复：启用 CEP 调试模式

**没有此设置，未签名的 CEP 扩展无法在 AE 中加载！**

```powershell
# 以管理员身份在 PowerShell 中执行：
reg add "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode /t REG_DWORD /d 1 /f
```

验证：
```powershell
reg query "HKCU\Software\Adobe\CSXS.12" /v PlayerDebugMode
# 应输出: PlayerDebugMode    REG_DWORD    0x1
```

## 1.6 环境基线总结

### 状态评估：⚠️ 基础可用，需补充配置

| 组件 | 完成度 | 需要操作 |
|------|--------|----------|
| VSCode + 基础工具链 | 100% | 无 |
| ExtendScript Debugger | 100% | 已安装，需配置 launch.json（见第三阶段） |
| AE JSX Runner | 0% | 需安装插件 |
| JS JSX Snippets | 0% | 需安装插件 |
| Lingma AI Assistant | 0% | 需安装插件 |
| CEP PlayerDebugMode | 0% | 🔴 必须启用（见 1.5） |
| AE 2025 目标环境 | 100% | 已确认 |

### 下一步行动（按优先级）

1. 🔴 **立即**: 启用 CEP PlayerDebugMode (`reg add ...`)
2. 🟡 **安装前**: 安装缺失的 3 个 VSCode 插件
3. 🟢 **配置**: 进入第二阶段 — AE JSX Runner 连接配置

---

> **下一阶段**: [PHASE2_JSX_RUNNER_CONFIG.md](./PHASE2_JSX_RUNNER_CONFIG.md)
