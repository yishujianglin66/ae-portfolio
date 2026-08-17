# ============================================================
# Premiere Pro 菜单项扫描脚本
# ============================================================

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
$prWindow = [System.Windows.Automation.AutomationElement]::FromHandle($prProcess.MainWindowHandle)

if (-not $prWindow) {
    Write-Log "UIAutomation 连接失败" "ERROR"
    exit 1
}

Write-Log "UIAutomation 连接成功"

# 激活窗口
$prWindow.SetFocus()
Start-Sleep -Milliseconds 500

# 查找菜单栏
Write-Log "查找菜单栏..."
$menuBarCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::MenuBar
)
$menuBars = $prWindow.FindAll([System.Windows.Automation.TreeScope]::Descendants, $menuBarCondition)
Write-Log "找到 $($menuBars.Count) 个菜单栏"

# 扫描所有菜单项
Write-Log "扫描所有菜单项..."
$menuItemCondition = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
    [System.Windows.Automation.ControlType]::MenuItem
)
$allMenuItems = $prWindow.FindAll([System.Windows.Automation.TreeScope]::Descendants, $menuItemCondition)

$names = @()
foreach ($item in $allMenuItems) {
    $name = $item.Current.Name
    if ($name -and $name -ne "") {
        $names += $name
    }
}

$uniqueNames = $names | Select-Object -Unique | Sort-Object
Write-Log "找到 $($uniqueNames.Count) 个唯一菜单项:"
foreach ($n in $uniqueNames) {
    Write-Log "  - $n"
}

# 查找 Script 相关的项
Write-Log "`n查找脚本相关菜单项:"
$scriptMenus = $uniqueNames | Where-Object { $_ -match "脚本|Script|script" }
foreach ($n in $scriptMenus) {
    Write-Log "  - $n"
}

# 保存结果
$result = @{
    windowTitle = $prProcess.MainWindowTitle
    menuBarCount = $menuBars.Count
    totalMenuItems = $allMenuItems.Count
    uniqueMenuItems = $uniqueNames
    scriptRelated = @($scriptMenus)
    timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
}
$result | ConvertTo-Json -Depth 3 | Out-File "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\output\pr_menu_scan_result.json" -Encoding UTF8

Write-Log "`n结果已保存到 output\pr_menu_scan_result.json"
