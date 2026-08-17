# Topaz Video AI 全自动操作手册（跨智能体交接）

> **创建**: 2026-08-12 | **来源**: 实测探索（AE-Knowledge-Vault v22 增强项目）
> **适用**: 任何具备文件读写 + PowerShell 执行能力的智能体（ZCode / Qoder / Trae / Claude-Code 等）
> **目标**: 让下一个智能体无需重复踩坑，直接复用脚本操控 Topaz 完成 导入→预设→导出→验证

---

## 0. 核心结论（先读这段）

1. **Topaz Video AI 是纯 GUI 应用，无 CLI**，但它的 UIA 控件树**完全可读**，可用 Windows 自动化全流程操控。
2. **操控它不需要任何"特殊能力"**——用的是三个 Windows 通用技术：
   - **UIAutomation**（读控件树、InvokePattern 触发控件）
   - **Win32 API**（SetForegroundWindow / SetCursorPos / mouse_event）
   - **WScript.Shell SendKeys**（键盘输入，含 Ctrl+L / Enter）
3. **最稳的触发方式是 InvokePattern，不是鼠标点击**——坐标点击受 DPI 缩放影响极不稳定。
4. **Topaz 是 Qt 应用**（窗口类 `Qt680QWindowIcon`），它的文件对话框是**内嵌 Win32 对话框**，属于 Topaz 进程内，不是独立 explorer 进程。
5. 渲染期间（CPU 持续增长）**绝对不要**再触发任何 UI 操作——会中断渲染并留下中间产物（本次实测踩坑）。

---

## 1. 环境与版本

| 项 | 值 |
|---|---|
| 软件 | Topaz Video AI Pro（BETA 版） |
| 版本 | v7.2.0.3（枫叶素材汉化中文版） |
| 进程名 | `Topaz Video AI BETA` |
| 窗口类 | `Qt680QWindowIcon`（主窗口）/ `TMainApp_QMLTYPE_816`（UIA 类） |
| 窗口标题 | `Video AI Beta 7 - Default`（导入视频后变为项目名） |
| 路径 | `D:\top\Topaz Video AI Pro\Topaz Video AI BETA.exe` |
| 屏幕 | 单屏 1707×1067，**DPI 150%** |

> ⚠️ **PID 会变**：Topaz 每次重启 PID 都不同。所有脚本里的硬编码 PID 需先查询：`Get-Process | Where ProcessName -match 'Topaz'`

---

## 2. 技术栈（三个通用 API，无私有依赖）

### 2.1 UIAutomation（读树 + 触发）
```powershell
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
# 按 PID 找窗口
$cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $topazId)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
# 遍历控件树找目标
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
# 触发（关键：InvokePattern 比点击稳）
$el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
```

### 2.2 Win32 API（激活窗口 + 鼠标）
```powershell
[DllImport("user32.dll")] SetForegroundWindow / SetCursorPos / mouse_event
```

### 2.3 SendKeys（键盘输入）
```powershell
$wshell = New-Object -ComObject WScript.Shell
$wshell.SendKeys("^l"); $wshell.SendKeys("filename"); $wshell.SendKeys("{ENTER}")
```

---

## 3. 完整操作流程（5 步，全部实测通过）

### 步骤 0：确认 Topaz 运行 + 拿 PID
```powershell
Get-Process | Where-Object { $_.ProcessName -match 'Topaz' } | Select Id, MainWindowTitle
```

### 步骤 1：导入视频（两个入口，都实测可用）
- **入口 A（推荐）**：UIA 找到「浏览视频」（Text 控件）→ InvokePattern 触发 → 等待 4s → 文件对话框出现（探测到 ListItem 即成功）
- **入口 B**：坐标点击「来源」按钮（右下角队列，坐标随 DPI 变，不稳）

文件对话框出现后，**双击文件列表项**（最可靠）：
```powershell
# dblclick_item.ps1 -ItemName "v22_solo_leveling_enhanced_rife_local"
# 用 UIA 找 ListItem → 取 BoundingRectangle 中心 → 双击（两次 mouse_event LEFTDOWN/UP）
```

### 步骤 2：选预设（InvokePattern，不依赖坐标）
预设是 **Text 控件**，但支持 InvokePattern：
```powershell
# invoke_named.ps1 -Name "4K增强 & 60帧"
# 可选预设: 4K增强 & 60帧 / 补帧 60帧 / 降噪 / 修复4K / 老电影4K画质 ...
```
> 新版 Topaz 7 首次导入会弹「您希望如何编辑？」引导——点「开始 编辑」进入编辑模式。

### 步骤 3：导出（先设输出目录，再开始导出）
```powershell
# 1) invoke_named.ps1 -Name "导出视频"      → 打开导出对话框
# 2) invoke_named.ps1 -Name "Browse"        → 打开输出目录选择
# 3) SendKeys ^l + 路径 + Enter             → 目录对话框内输入路径确认
# 4) invoke_named.ps1 -Name "开始导出"       → 启动渲染
```

### 步骤 4：监控渲染（后台轮询，勿打扰）
```bash
# 渲染中：CPU 持续增长（实测 1064→3148s / 30min）、内存 1.9GB
# 完成时：CPU 增量归零、内存骤降（1.9GB→491MB）
# 轮询输出：find D:/output_director/.../ -name "*.mp4" -mmin -60
```

### 步骤 5：验证产物
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,r_frame_rate,nb_frames -of default=nw=1 <输出.mp4>
# 实测: 24fps源 → 48fps(补帧60) → 120fps(4K增强&60帧) / 2334帧
```

---

## 4. 踩坑记录（最有价值的部分，共 12 坑）

| # | 坑 | 症状 | 解决方案 |
|---|----|------|---------|
| 1 | **PID 硬编码失效** | 脚本找不到窗口 | 每次先查 PID，脚本参数化 |
| 2 | **坐标点击受 DPI 影响** | UIA 逻辑坐标 × 150% ≠ 物理坐标，点击落空 | 用 InvokePattern 代替坐标点击；必须用坐标时用物理坐标 |
| 3 | **窗口标题无 "Topaz"** | `MainWindowTitle` 是 `Video AI Beta 7 - Default`，按标题匹配失败 | 按进程名匹配 |
| 4 | **PowerShell 5.1 中文乱码** | 无 BOM 的 UTF-8 脚本被按 GBK 读，中文字符串乱码导致匹配失败 | **所有含中文的 ps1 加 UTF-8 BOM**（`\xEF\xBB\xBF`） |
| 5 | **`$pid` 是保留变量** | `$pid = 33360` 报"无法覆盖只读变量" | 改用 `$topazId` 等变量名 |
| 6 | **`来源` ≠ 导入入口** | 右下角「来源」是队列按钮，点击不弹文件对话框 | 真正的导入是「浏览视频」（空态区） |
| 7 | **文件对话框是内嵌的** | 不属于独立 explorer 进程，`CabinetWClass`/`#32770` 匹配不到 | 对话框在 Topaz 进程内（Qt 内嵌 Win32 对话框），按 Topaz PID 找 |
| 8 | **SendKeys 路径反斜杠转义** | `D:\path\file.mp4` 被误解析 | 优先 UIA 双击文件；必须 SendKeys 时输入纯文件名 |
| 9 | **预设是 Text 控件无 Invoke？** | 以为 Text 不能触发 | Text 控件实际支持 InvokePattern，直接 Invoke 即可 |
| 10 | **导出需先设输出目录** | 直接点开始导出可能输出到默认目录 | 先 Browse 设目录（SendKeys Ctrl+L 输入路径 + Enter） |
| 11 | **渲染中途操作会中断** | 触发 UI 操作后渲染停止，留下中间产物 | 渲染期只读状态，绝不触发 UI；完成后才操作 |
| 12 | **中间产物残留** | 中断/多次导出留下 `*_1_iris3.mp4`、`*_apo8_ahq12.mp4` 等 | 无覆盖风险（独立命名），但需人工甄别哪份是完整渲染 |

---

## 5. 脚本清单（scripts/ 目录，全部 UTF-8 BOM）

| 脚本 | 功能 | 关键参数 |
|------|------|---------|
| `topaz_import2.ps1` | **一键导入**（探测浏览→Invoke→探测对话框→输入文件名） | `-FileName` |
| `invoke_named.ps1` | **万能触发**（Invoke/Legacy/Selection/Toggle 多 pattern 尝试） | `-Name` |
| `dump_topaz_tree.ps1` | dump 主窗口控件树（找预设/按钮坐标） | 无 |
| `dump_proc_uia.ps1` | dump 进程全部窗口 UIA（含对话框） | `-ProcId` |
| `dblclick_item.ps1` | 双击文件列表项（导入用） | `-ItemName` |
| `enum_windows2.ps1` | 枚举可见窗口 + 类名 | `-Pattern` |
| `list_proc_windows.ps1` | 列进程全部窗口（含子窗口） | `-ProcId` |
| `sendkeys.ps1` | 向进程发键盘 | `-ProcId -Keys` |
| `ui_click.ps1` | 坐标点击 | `-ProcId -X -Y` |
| `probe_topaz_uia.ps1` | 探测 Topaz UIA 可读性 | 无 |
| `file_dialog_enter.ps1` | 文件对话框输入文件名 | `-FileName` |
| `focus_xaml_dialog.ps1` | 聚焦 Xaml 对话框（Win11 特有，本次未用上） | `-ExplorerPid` |
| `paste_path.ps1` | 剪贴板粘贴路径（绕开 SendKeys 转义） | `-ProcId -Text` |
| `dump_win_uia.ps1` | dump 指定类名窗口的 UIA | `-ProcId -Class` |

---

## 6. 给其他智能体的快速上手指引

1. **复制 3 个核心脚本**：`topaz_import2.ps1` + `invoke_named.ps1` + `dump_topaz_tree.ps1`，改 `$topazId` 为实际 PID。
2. **先探测后操作**：用 `dump_topaz_tree.ps1` 看当前控件树（含坐标/名称），确认目标控件真实存在再触发。
3. **触发优先 InvokePattern**：`invoke_named.ps1 -Name "xxx"`，失败再考虑坐标点击（记得 DPI 换算）。
4. **文件对话框处理**：双击 ListItem 最稳；SendKeys 只输纯文件名。
5. **渲染期只读**：CPU 持续增长 = 渲染中，勿操作；CPU 归零 + 内存骤降 = 完成。
6. **产物验证**：ffprobe 看 帧数/帧率/分辨率/音频，确认完整再交付。

---

## 7. 与 ffmpeg 方案的对比结论（实测）

| 方案 | 帧率 | 帧数 | 耗时 | VMAF(保真) | 备注 |
|------|------|------|------|-----------|------|
| ffmpeg 直压 | 48fps | 929 | 秒级 | 92.0 | 基线 |
| ffmpeg 锐化2.0 | 48fps | 929 | 秒级 | **99.99** | 最保真、最快 |
| Topaz AI | **120fps** | **2334** | 30min | 78.5* | AI补帧+超分+增强 |

> *Topaz VMAF 低是"增强改变内容"的预期结果，不代表质量差；VMAF 衡量相似度而非观感。
> **决策建议**：快节奏卡点 → ffmpeg 锐化（快且保真）；追求极致流畅 → Topaz 120fps。

---

## 8. 本次实测产物（D:\output_director\solo_pilot\v22\）

| 文件 | 规格 | 说明 |
|------|------|------|
| `v22_solo_leveling.mp4` | 24fps/465帧 | 原始成片 |
| `v22_solo_leveling_enhanced_rife_local.mp4` | 48fps/929帧 | RIFE 本地补帧 |
| `v22_solo_leveling_enhanced_rife_local_douyin.mp4` | 48fps/8Mbps | ffmpeg 锐化1.0 分发版 |
| `v22_solo_leveling_sharp15_douyin.mp4` | 48fps/20.6MB | ffmpeg 锐化1.5 分发版 |
| `v22_solo_leveling_enhanced_rife_local_1_iris3.mp4` | 48fps/929帧/27.6MB | Topaz Iris 增强 |
| `v22_solo_leveling_enhanced_rife_local_apo8_ahq12.mp4` | **120fps/2334帧/213.6MB** | **Topaz 超分+补帧全家桶** |
