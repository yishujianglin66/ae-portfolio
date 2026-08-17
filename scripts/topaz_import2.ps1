# Topaz video import with retry loop: try multiple trigger methods until
# file dialog (ListItem file list) appears, then send filename + Enter.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File topaz_import2.ps1
param([string]$FileName = "v22_solo_leveling_enhanced_rife_local.mp4")

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class UiIm2 {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
    public const uint LEFTDOWN = 0x02; public const uint LEFTUP = 0x04;
}
'@

$topazId = 33360
$proc = Get-Process -Id $topazId -ErrorAction SilentlyContinue
if (-not $proc) { Write-Output "ERR: no process $pid"; exit 1 }
[UiIm2]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 500

# ---- Find elements ----
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $topazId)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
if (-not $win) { Write-Output "ERR: no UIA window"; exit 1 }
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker

function Find-Named($el, $kw, $depth) {
    if ($depth -gt 7) { return $null }
    $c = $walker.GetFirstChild($el)
    while ($c -ne $null) {
        $n = $c.Current.Name -replace '\s',''
        if ($n -like ("*" + $kw + "*")) { return $c }
        $res = Find-Named $c $kw ($depth + 1)
        if ($res) { return $res }
        $c = $walker.GetNextSibling($c)
    }
    return $null
}

function Has-Dialog() {
    # file dialog present if any ListItem with video filename appears
    $items = $win.FindAll([System.Windows.Automation.TreeScope]::Descendants,
        (New-Object System.Windows.Automation.PropertyCondition(
            [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
            [System.Windows.Automation.ControlType]::ListItem)))
    foreach ($i in $items) {
        if ($i.Current.Name -match "v22_solo|\.mp4|\.mov") { return $true }
    }
    return $false
}

# ---- Attempt triggers until dialog appears ----
$methods = @("invoke", "legacy", "click")
$done = $false
foreach ($m in $methods) {
    if ($done) { break }
    $browse = Find-Named $win "浏览" 0
    if ($browse) {
        $r = $browse.Current.BoundingRectangle
        Write-Output "TRY $m (browse at $([int]$r.X),$([int]$r.Y))"
        if ($m -eq "invoke") {
            try { $browse.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke() } catch {}
        } elseif ($m -eq "legacy") {
            try { $browse.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern).DoDefaultAction() } catch {}
        } else {
            # physical coords = UIA bounding rect (already physical)
            [UiIm2]::SetCursorPos([int]$r.X + 40, [int]$r.Y + 20) | Out-Null
            Start-Sleep -Milliseconds 150
            [UiIm2]::mouse_event([UiIm2]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
            [UiIm2]::mouse_event([UiIm2]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
        }
        Start-Sleep -Seconds 4
        $done = Has-Dialog
        if ($done) { Write-Output "DIALOG APPEARED via $m" }
    } else {
        Write-Output "browse element not found"
    }
}

if (-not $done) {
    # last resort: click "来源" button (was reliable before)
    $src = Find-Named $win "来源" 0
    if ($src) {
        $r = $src.Current.BoundingRectangle
        Write-Output "TRY source-button at $([int]$r.X),$([int]$r.Y)"
        [UiIm2]::SetCursorPos([int]$r.X + 70, [int]$r.Y + 35) | Out-Null
        Start-Sleep -Milliseconds 150
        [UiIm2]::mouse_event([UiIm2]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
        [UiIm2]::mouse_event([UiIm2]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
        Start-Sleep -Seconds 4
        $done = Has-Dialog
    }
}

if (-not $done) { Write-Output "ERR: could not open file dialog"; exit 1 }

# ---- Type filename + Enter (modal dialog owns focus) ----
$wshell = New-Object -ComObject WScript.Shell
Start-Sleep -Milliseconds 500
$wshell.SendKeys($FileName)
Start-Sleep -Milliseconds 600
$wshell.SendKeys("{ENTER}")
Write-Output "SENT filename+ENTER"
Start-Sleep -Seconds 5
Write-Output "DONE"
