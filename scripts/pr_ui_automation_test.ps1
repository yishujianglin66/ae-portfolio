# ============================================================
# 通过 UIAutomation 操作 Premiere Pro 菜单运行脚本
# ============================================================

param(
    [string]$ScriptPath = "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\pr_mcp_bridge.jsx"
)

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms

$ErrorActionPreference = "Continue"

function Write-Log {
    param([string]$Msg, [string]$Level = "INFO")
    Write-Host "[$Level] $Msg"
}

# 找到 PR 窗口
Write-Log "查找 Premiere Pro 窗口..."
$prProcess = Get-Process | Where-Object { $_.ProcessName -like "*Premiere*" -and $_.MainWindowTitle -ne "" } | Select-Object -First 1

if (-not $prProcess) {
    Write-Log "未找到 Premiere Pro 进程" "ERROR"
    exit 1
}

Write-Log "找到 PR 窗口: $($prProcess.MainWindowTitle)"

# 获取主窗口 AutomationElement
$root = [System.Windows.Automation.AutomationElement]::RootElement
$condition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::NameProperty,
    $prProcess.MainWindowTitle
)
$prWindow = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $condition)

if (-not $prWindow) {
    Write-Log "无法通过 UIAutomation 找到 PR 窗口，尝试进程 ID..."
    $prWindow = [System.Windows.Automation.AutomationElement]::FromHandle($prProcess.MainWindowHandle)
}

if (-not $prWindow) {
    Write-Log "UIAutomation 连接失败" "ERROR"
    exit 1
}

Write-Log "UIAutomation 连接成功"

# 激活窗口
$prWindow.SetFocus()
Start-Sleep -Milliseconds 500

# 方法: 尝试找到菜单栏并点击
Write-Log "尝试访问菜单栏..."

# 查找菜单栏
$menuBarCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::MenuBar
)
$menuBars = $prWindow.FindAll([System.Windows.Automation.TreeScope]::Descendants, $menuBarCondition)

Write-Log "找到 $($menuBars.Count) 个菜单栏"

if ($menuBars.Count -gt 0) {
    # 列出菜单栏中的所有菜单项
    $menuItems = $menuBars[0].FindAll(
        [System.Windows.Automation.TreeScope]::Children,
        [System.Windows.Automation.PropertyCondition]::TrueCondition
    )
    Write-Log "菜单项:"
    foreach ($item in $menuItems) {
        Write-Log "  - $($item.Current.Name)"
    }
}

# 备用方案: 直接用键盘快捷键
Write-Log "使用键盘快捷键方式..."

# 先按 ESC 关闭任何打开的菜单
[System.Windows.Forms.SendKeys]::SendWait("{ESC}")
Start-Sleep -Milliseconds 300
[System.Windows.Forms.SendKeys]::SendWait("{ESC}")
Start-Sleep -Milliseconds 500

# 尝试用 Alt+F 打开文件菜单
Write-Log "打开文件菜单..."
[System.Windows.Forms.SendKeys]::SendWait("%f")
Start-Sleep -Milliseconds 800

# 截图并检查当前状态
# 然后按向下键找到脚本选项

# 先保存当前状态到文件供调试
$debugInfo = @{
    windowTitle = $prProcess.MainWindowTitle
    menuBarCount = $menuBars.Count
    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
}
$debugInfo | ConvertTo-Json | Out-File "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\pr_debug_info.json" -Encoding UTF8

Write-Log "调试信息已保存"

# 列出所有可能的菜单项 (深度搜索前两层)
Write-Log "扫描所有菜单项名称..."
$allMenus = $prWindow.FindAll(
    [System.Windows.Automation.TreeScope]::Descendants,
    $(New-Object System.Windows.Automation.PropertyCondition(
        [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
        [System.Windows.Automation.ControlType]::MenuItem
    ))
)

$menuNames = @()
foreach ($m in $allMenus) {
    if ($m.Current.Name -and $m.Current.Name -ne "") {
        $menuNames += $m.Current.Name
    }
}
$uniqueMenus = $menuNames | Select-Object -Unique | Sort-Object
Write-Log "找到 $($uniqueMenus.Count) 个唯一菜单项:"
$uniqueMenus | ForEach-Object { Write-Log "  - $_" }

Write-Log "完成"
