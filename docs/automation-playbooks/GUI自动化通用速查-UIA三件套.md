# GUI 自动化通用速查（UIA 三件套）

> **创建**: 2026-08-12 | **来源**: Topaz Video AI 自动化实测（见同目录 Topaz 手册）
> **适用**: 任何 Windows GUI 软件自动化（DaVinci Resolve / After Effects / Photoshop / Premiere…）
> **前置**: PowerShell 5.1+（Windows 自带），无需安装任何第三方工具
> **配套脚本**: `scripts/` 下 invoke_named.ps1 / dump_proc_uia.ps1 / sendkeys.ps1 / ui_click.ps1 等

---

## 0. 一句话核心

**用 InvokePattern 触发控件（不要用鼠标点击），用 UIA 读坐标，SendKeys 只用于键盘输入。** 这是从 Topaz 自动化中总结出的最稳组合。

---

## 1. 三件套技术（全是 Windows 通用 API）

| # | 技术 | 用途 | 关键点 |
|---|------|------|--------|
| 1 | **UIAutomation** | 读控件树 / 触发控件 | `InvokePattern` 最稳；控件可能是 Text 但照样支持 Invoke |
| 2 | **Win32 API** | 激活窗口 / 鼠标事件 | `SetForegroundWindow` + `SetCursorPos` + `mouse_event` |
| 3 | **WScript.Shell SendKeys** | 键盘输入 | 只输纯文件名/无特殊字符；路径用剪贴板粘贴避开转义 |

---

## 2. 万能探测脚本（先探测，后操作）

```powershell
# 1. 找进程 PID（窗口标题可能不含软件名！按进程名匹配）
Get-Process | Where-Object { $_.ProcessName -match 'Topaz|Resolve|AfterFX|Photoshop' }

# 2. dump 进程全部窗口的 UIA 树（找控件名 + 逻辑坐标）
powershell -ExecutionPolicy Bypass -File scripts/dump_proc_uia.ps1 -ProcId <PID>

# 3. 触发任意控件（多 pattern 自动尝试）
powershell -ExecutionPolicy Bypass -File scripts/invoke_named.ps1 -Name "导出"
```

---

## 3. 通用操作套路（5 步模板）

```text
1. 定位控件: dump_proc_uia.ps1 找到目标控件的 Name
2. 触发控件: invoke_named.ps1 -Name "xxx"      ← 首选，比点击稳
3. 文件对话框: 探测 ListItem → 双击文件          ← 比 SendKeys 输入路径稳
4. 键盘输入:   sendkeys.ps1 只输纯文件名
5. 长任务:     轮询 CPU 增长判断进行中，完成后内存骤降
```

---

## 4. 十三个通用坑（从 Topaz 实测提炼，适用于任何 GUI）

1. **窗口标题 ≠ 进程名**：`MainWindowTitle` 常是 `Video AI Beta 7 - Default`，按进程名匹配
2. **DPI 缩放**：UIA 逻辑坐标 ≠ 物理坐标（150% 时 ×1.5），坐标点击会偏 → **用 InvokePattern**
3. **PID 每次启动变化**：脚本参数化，先 `Get-Process` 查
4. **PowerShell 5.1 中文乱码**：含中文的 .ps1 必须存 **UTF-8 BOM**（`\xEF\xBB\xBF`）
5. **`$pid` 是保留变量**：改用 `$topazId`/`$procId` 等
6. **文件对话框可能内嵌在软件进程**（Qt/WinUI），不是独立 explorer 进程
7. **SendKeys 特殊字符转义**：`\` `+` `^` `%` `()` `{}` 有特殊含义，路径用剪贴板
8. **预设/卡片是 Text 控件但支持 InvokePattern**——别因为类型是 Text 就放弃触发
9. **渲染/长任务期间绝不触发 UI**：会中断，留中间产物
10. **探测到的坐标在窗口最小化/移动后失效**：每次操作前重新探测
11. **双重触发保险**：InvokePattern 失败 → LegacyIAccessible.DoDefaultAction → SelectionItem.Select → Toggle
12. **用 ListItem 双击代替"文件名输入+回车"**：对话框里更可靠
13. **结果验证用 ffprobe**：帧数/帧率/分辨率/音频流，别只看文件存在

---

## 5. 迁移到新软件（4 步方法论）

```text
1. 探测:   dump_proc_uia.ps1 -ProcId <PID>  → 看控件树可读性
   - 有 Name 的控件多 → UIA 自动化可行
   - 全是无名字控件（自绘 Canvas）→ 只能坐标点击或放弃
2. 定位:   找关键操作对应的控件 Name（导入/导出/设置）
3. 触发:   优先 InvokePattern；不行再坐标（记得 DPI 换算）
4. 沉淀:   成功后写进 docs/automation-playbooks/<软件名>.md（含踩坑表）
```

---

## 6. 脚本速查（scripts/，全部 UTF-8 BOM，参数化 PID）

| 脚本 | 功能 | 迁移用法 |
|------|------|---------|
| `invoke_named.ps1` | **万能触发**（多 pattern） | 改 PID，传控件名即可 |
| `dump_proc_uia.ps1` | dump 进程全部窗口 UIA 树 | 改 PID |
| `dump_topaz_tree.ps1` | dump 主窗口树（Topaz 专用） | 通用版看 dump_proc_uia |
| `dblclick_item.ps1` | 双击 ListItem（文件对话框） | 改 PID + ItemName |
| `sendkeys.ps1` | 发键盘（纯文件名） | 改 PID + Keys |
| `ui_click.ps1` | 坐标点击（物理坐标） | 改 PID + X/Y |
| `enum_windows2.ps1` | 枚举窗口+类名 | 通用 |
| `list_proc_windows.ps1` | 列进程全部窗口（含子窗口） | 改 PID |
| `topaz_import2.ps1` | Topaz 一键导入（示范完整流程） | 参考改造 |

---

## 7. 判断"能否自动化"的速测法

```powershell
# 2 分钟速测：软件打开后跑一次 dump，看命名控件数量
powershell -ExecutionPolicy Bypass -File scripts/dump_proc_uia.ps1 -ProcId <PID> | Select-String "\[Button\]|\[Edit\]|\[ComboBox\]" | Measure-Object
# ≥5 个命名控件 → 可自动化（InvokePattern 路线）
# <5 个 → 纯自绘界面，评估坐标点击或人工介入
```
