# Full Topaz import automation:
#  1. DPI-scaled click on "browse video" (1602,1280 = logical 1068,853 x1.5 @150%)
#  2. Wait for Win32 Open dialog
#  3. UIA: find FileName edit box, set value via ValuePattern
#  4. UIA: invoke "Open" button
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File topaz_import.ps1 -Path "D:\x\y.mp4"
param([string]$Path)

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class UiImp {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
    public const uint LEFTDOWN = 0x02; public const uint LEFTUP = 0x04;
}
'@

$topazPid = 33360

# 1. Activate Topaz
$proc = Get-Process -Id $topazPid
[UiImp]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 600

# 1b. Trigger browse via UIA InvokePattern (more reliable than coordinate click)
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $topazPid)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$script:target = $null
function Find-Browse($el, $depth) {
    if ($depth -gt 6 -or $script:target) { return }
    $c = $walker.GetFirstChild($el)
    while ($c -ne $null) {
        $n = $c.Current.Name -replace '\s',''
        if ($n -like '*浏览*') { $script:target = $c; return }
        Find-Browse $c ($depth + 1)
        $c = $walker.GetNextSibling($c)
    }
}
Find-Browse $win 0
if ($script:target) {
    $invoked = $false
    try { $script:target.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke(); $invoked = $true } catch {}
    if (-not $invoked) {
        try { $script:target.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern).DoDefaultAction(); $invoked = $true } catch {}
    }
    Write-Output "STEP1 browse invoked=$invoked"
} else {
    Write-Output "ERR: browse not found"
    exit 1
}
Start-Sleep -Seconds 3

# 2. Find the Open dialog (top-level window with "打开" or explorer.exe child)
$dlg = $null
$root = [System.Windows.Automation.AutomationElement]::RootElement
$allWins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
foreach ($w in $allWins) {
    $n = $w.Current.Name
    if ($n -match "打开|Open|选择|Select" -or $w.Current.ClassName -match "#32770|Dialog") {
        $dlg = $w
        Write-Output "STEP2 dialog: [$n] class=[$($w.Current.ClassName)]"
        break
    }
}
if (-not $dlg) { Write-Output "ERR: no dialog"; exit 1 }

# 3. Find FileName Edit box
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$edit = $null
function FindEdit($el, $depth) {
    if ($depth -gt 6 -or $script:edit) { return }
    $c = $walker.GetFirstChild($el)
    while ($c -ne $null) {
        $t = $c.Current.ControlType.ProgrammaticName
        if ($t -eq "ControlType.Edit") {
            $script:edit = $c
            Write-Output "STEP3 edit: name=[$($c.Current.Name)]"
            return
        }
        FindEdit $c ($depth + 1)
        $c = $walker.GetNextSibling($c)
    }
}
FindEdit $dlg 0
if (-not $edit) { Write-Output "ERR: no edit box"; exit 1 }

# 4. Set value in edit box
try {
    $vp = $edit.GetCurrentPattern([System.Windows.Automation.ValuePattern]::Pattern)
    $vp.SetValue($Path)
    Write-Output "STEP4 set value: $Path"
} catch {
    Write-Output ("ERR set: " + $_.Exception.Message); exit 1
}
Start-Sleep -Milliseconds 400

# 5. Find and invoke "Open" button
$btn = $null
function FindBtn($el, $depth) {
    if ($depth -gt 6 -or $script:btn) { return }
    $c = $walker.GetFirstChild($el)
    while ($c -ne $null) {
        $t = $c.Current.ControlType.ProgrammaticName
        $n = $c.Current.Name
        if ($t -eq "ControlType.Button" -and ($n -match "打开|Open|确定")) {
            $script:btn = $c
            Write-Output "STEP5 button: [$n]"
            return
        }
        FindBtn $c ($depth + 1)
        $c = $walker.GetNextSibling($c)
    }
}
FindBtn $dlg 0
if (-not $btn) {
    # fallback: send Enter
    Write-Output "no button, sending Enter"
    $wshell = New-Object -ComObject WScript.Shell
    $wshell.AppActivate($dlg.Current.ProcessId) | Out-Null
    Start-Sleep -Milliseconds 300
    $wshell.SendKeys("{ENTER}")
} else {
    try {
        $btn.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
        Write-Output "STEP6 invoked Open"
    } catch {
        Write-Output ("ERR invoke: " + $_.Exception.Message)
    }
}
Write-Output "DONE"
