# Double-click a ListItem by name inside Topaz file dialog.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File dblclick_item.ps1 -ItemName "v22_solo_leveling_enhanced_rife_local"
param([string]$ItemName = "v22_solo_leveling_enhanced_rife_local")

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public class DblClick {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint f, uint dx, uint dy, uint d, UIntPtr e);
    public const uint LEFTDOWN = 0x02; public const uint LEFTUP = 0x04;
}
'@

$topazId = 33360
$proc = Get-Process -Id $topazId -ErrorAction SilentlyContinue
if (-not $proc) { Write-Output "ERR: no process"; exit 1 }
[DblClick]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 400

$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $topazId)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$script:item = $null

function Find-Item($el, $depth) {
    if ($depth -gt 7 -or $script:item) { return }
    $c = $walker.GetFirstChild($el)
    while ($c -ne $null) {
        $t = $c.Current.ControlType.ProgrammaticName
        $n = $c.Current.Name
        if ($t -eq "ControlType.ListItem" -and $n -match $ItemName) {
            $script:item = $c
            Write-Output ("FOUND item: [" + $n + "]")
            return
        }
        Find-Item $c ($depth + 1)
        $c = $walker.GetNextSibling($c)
    }
}
Find-Item $win 0
if (-not $script:item) { Write-Output "ITEM_NOT_FOUND"; exit 1 }

$r = $script:item.Current.BoundingRectangle
$cx = [int]$r.X + [int]($r.Width / 2)
$cy = [int]$r.Y + [int]($r.Height / 2)
Write-Output ("click at " + $cx + "," + $cy)

# double-click
[DblClick]::SetCursorPos($cx, $cy) | Out-Null
Start-Sleep -Milliseconds 200
[DblClick]::mouse_event([DblClick]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
[DblClick]::mouse_event([DblClick]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
Start-Sleep -Milliseconds 100
[DblClick]::mouse_event([DblClick]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
[DblClick]::mouse_event([DblClick]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
Write-Output "DBLCLICKED"
