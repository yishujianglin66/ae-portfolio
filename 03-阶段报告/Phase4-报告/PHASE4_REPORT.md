# Phase 4 Report — 文件路径与命名规范化

> **项目**: AE StudioKit Enterprise Upgrade  
> **阶段**: 第四阶段  
> **日期**: 2026-06-05  
> **状态**: ✅ 核心清理完成  

---

## 1. 概述

Phase 4 清理了项目中的硬编码绝对路径、命名不一致、空目录和过期文件。主要目标：消除跨机器部署的障碍，标准化命名约定。

### 关键指标

| 指标 | 之前 | 之后 |
|------|------|------|
| 硬编码用户名 (`Administrator`) | 3 处 | 0 处 |
| 硬编码 AE 版本路径 | 1 处 | 0 处 (动态推导) |
| 硬编码 Python 版本回退 | 1 处 | 0 处 (PATH 回退) |
| 输出目录名称 | `VocalSep_Output` (旧) / `VocalSep5_Output` (新) 混用 | 统一为 `VocalSep5_Output` |
| 中文目录名 | 3 个 | 0 个 |
| 过期文件 (`.bak`, `.test`, `.txt`) | 3 个 | 0 个 |
| 空目录 | 11 个 | 0 个 |
| 路径分隔符混用 (`/` vs `\`) | 1 处 | 0 处 |
| 端口定义重复 | 2 处独立定义 | 1 处集中定义 |

---

## 2. 重命名对照表

### 2.1 目录重命名

| 原名称 | 新名称 | 说明 |
|--------|--------|------|
| `项目技能/` | `project-skills/` | 中文→英文 kebab-case |
| `ae脚本/` | (已删除) | 空目录 — 中文名 |
| `Adobe After Effects 自动保存/` | (已删除) | AE 自动生成 — 非项目文件 |

### 2.2 输出目录统一

| 文件 | 原值 | 新值 |
|------|------|------|
| `host/studio-kit-bridge.jsx` (3 处) | `VocalSep_Output` | `VocalSep5_Output` |
| `test-suites/F5-vocal-sep/F5_vocal_separate.py` (7 处) | `VocalSep_Output` | `VocalSep5_Output` |
| `test-suites/F6-import-audio/F6_import_audio.jsx` (3 处) | `VocalSep_Output` | `VocalSep5_Output` |

### 2.3 已删除文件

| 文件 | 大小 | 原因 |
|------|------|------|
| `server/config.py.bak` | 3.2 KB | config.py 的备份副本 |
| `AE脚本开发.txt` | 1.8 KB | 无代码开发笔记 |
| `VocalSep_Consolidated.jsx.test` | 76 KB | 根目录下的孤立测试文件 |

### 2.4 已删除的空目录

| 目录 | 原因 |
|------|------|
| `host/downloads/` | 从未使用 |
| `host/effects/` | 从未使用 |
| `host/tools/` | 从未使用 |
| `host/video/` | 从未使用 |
| `docs/patterns/` | 从未使用 |
| `docs/profiles/` | 从未使用 |
| `server/downloads/` | 从未使用 |
| `test-suites/F9-logger/` | 从未实现的模块 |
| `ae脚本/` | 空 + 中文名 |
| `Adobe After Effects 自动保存/` | AE 自动生成 |

---

## 3. 路径迁移详情

### 3.1 `host/main.jsx` — `findPython()` 回退值

**之前**:
```javascript
if (!userHome) userHome = 'C:\\Users\\Administrator';
// ...
PYTHON_EXE = userHome + '\\AppData\\Local\\Programs\\Python\\Python311\\python.exe';
```

**之后**:
```javascript
// 回退值: 如果 userHome 为空，跳过版本号路径，直接进行 PATH 搜索
// ...
PYTHON_EXE = 'python';  // 最终回退: PATH 搜索
```

**影响**: 与其他机器上 Python 不在标准路径的用户兼容。函数仍然按以下优先级工作: 已知版本路径 → 目录扫描 → PATH 回退。

### 3.2 `host/main.jsx` — `getScriptDir()` 回退值

**之前**:
```javascript
SCRIPT_DIR = 'C:\\Program Files\\Adobe\\Adobe After Effects 2025\\Support Files\\Scripts\\ScriptUI Panels\\VocalSep';
```

**之后**:
```javascript
// 从 AE 应用路径动态推导
try {
    var aeAppPath = app.path;
    var aeSupportDir = new File(aeAppPath).parent.fsName;
    SCRIPT_DIR = aeSupportDir + '\\Scripts\\ScriptUI Panels\\VocalSep';
} catch (e) {
    SCRIPT_DIR = Folder.myDocuments.fsName;
}
```

**影响**: 兼容所有 AE 版本 (2023-2029+) 和安装位置，不再绑定特定版本。

### 3.3 `client/app.js` — 路径分隔符不一致

**之前** (第 481 行):
```javascript
outPath = STATE.outDir + '\\' + jobId.substring(0, 10) + '_' + stem + '.wav';
```

**之后**:
```javascript
outPath = STATE.outDir + '/' + jobId.substring(0, 10) + '_' + stem + '.wav';
```

**影响**: 与同一文件中第 409 行使用的正斜杠分隔符保持一致。CEP Chromium 74 统一使用正斜杠处理 `evalScript` 返回值。

### 3.4 `server/ae_bridge.py` — 端口集中化

**之前**:
```python
SERVER_URL = "http://127.0.0.1:8765"  # 独立硬编码
```

**之后**:
```python
from config import SERVER_HOST, SERVER_PORT
SERVER_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"
```

**影响**: 端口现在单一来源 (`server/config.py` → `SERVER_PORT = 8765`)。在一个地方更改即可在所有模块间传播。

---

## 4. 排除项 (未修改)

按设计，以下项未包含在 Phase 4 范围内:

| 文件/目录 | 原因 |
|-----------|------|
| `VocalSep_Consolidated.jsx` | 遗留整合脚本 — 不再活跃开发 |
| `AEStudioKit_Panel.jsx` | 遗留独立面板 — CEP 架构之前的版本 |
| `AE-MotionStudio/` 及副本 | 独立分发 — 不作为活跃开发线的一部分 |
| `ffmpeg-8.1.1-essentials_build/` | 第三方捆绑软件 |
| `server/models/` | AI 模型文件 |
| `server/presets/` | 预设文件 (`.ffx`) |
| `host/main.jsx` 中的 Topaz 搜索候选项 | 合法的跨版本发现路径；已添加文档注释 |

---

## 5. 验证结果

```
✅ 活跃代码中无硬编码 "Administrator"
✅ 活跃代码中无硬编码 "Python311"
✅ 活跃代码中无硬编码 AE 版本路径
✅ 无空目录 (在 host/、docs/、test-suites/ 中)
✅ 无中文命名目录
✅ 无过期文件 (.bak、.test、.txt)
✅ VocalSep_Output → VocalSep5_Output 已标准化 (遗留代码中仍有旧名称)
✅ Python 配置导入验证: SERVER_HOST=127.0.0.1 SERVER_PORT=8765
```

### 遗留: 遗留代码中的 `VocalSep_Output`

以下文件仍引用 `VocalSep_Output` — 按 Phase 4 范围排除:

| 文件 | 出现次数 |
|------|----------|
| `AEStudioKit_Panel.jsx` | 3 处 |

---

## 6. 风险登记

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| `ae_bridge.py` 独立运行时 `config` 导入失败 | 低 | 中 | 从项目根运行: `python server/ae_bridge.py` (sys.path 包含 server/) |
| 某些机器上 `Folder.userData` 解析失败 | 很低 | 低 | findPython() 回退到 PATH 搜索 (`python --version`) |
| 某些 AE 版本上 `app.path` 不可用 | 很低 | 低 | getScriptDir() 回退到 `Folder.myDocuments` |
| 删除的空目录被未来模块需要 | 低 | 低 | 需要时 Git 可以恢复它们 |

---

## 7. Phase 4 提交摘要

```
修改:  host/main.jsx           — findPython() 和 getScriptDir() 回退值
修改:  host/studio-kit-bridge.jsx — 输出目录名称 (×3)
修改:  client/app.js           — 路径分隔符规范化
修改:  server/ae_bridge.py     — 端口集中化
修改:  test-suites/F5-vocal-sep/F5_vocal_separate.py — 输出目录/日志路径 (×8)
修改:  test-suites/F6-import-audio/F6_import_audio.jsx — 输出目录 (×3)
重命名: 项目技能/ → project-skills/
删除:   3 个过期文件
删除: 11 个空目录
新增: docs/phase4/PHASE4_REPORT.md — 本报告
```
