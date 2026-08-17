# Probe Topaz Video AI UIA control tree readability
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File probe_topaz_uia.ps1
$ErrorActionPreference = "Continue"

$proc = Get-Process | Where-Object { $_.MainWindowTitle -match "Topaz" }
if (-not $proc) {
    Write-Output "NO_TOPAZ_WINDOW"
    exit 1
}
Write-Output ("FOUND: {0} PID={1} TITLE='{2}'" -f $proc.ProcessName, $proc.Id, $proc.MainWindowTitle)

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition(
    [System.Windows.Automation.AutomationElement]::ProcessIdProperty, $proc.Id)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)

if (-not $win) {
    Write-Output "UIA_WINDOW_NOT_FOUND"
    exit 1
}
Write-Output ("UIA_WINDOW_OK: Name='{0}'" -f $win.Current.Name)

function Dump-Controls($el, $depth, $maxDepth) {
    if ($depth -gt $maxDepth) { return }
    $walk = [System.Windows.Automation.TreeWalker]::ControlViewWalker
    $child = $walk.GetFirstChild($el)
    while ($child -ne $null) {
        $name = $child.Current.Name
        $type = $child.Current.ControlType.ProgrammaticName -replace "ControlType.",""
        $show = $name.Length -gt 0 -or $type -match "Button|Edit|ComboBox|List|Menu|Tab|Tree|ListItem"
        if ($show) {
            $indent = "  " * $depth
            $rect = $child.Current.BoundingRectangle
            $loc = ""
            if ($rect.Width -gt 0) { $loc = " @(" + [int]$rect.X + "," + [int]$rect.Y + ")" }
            Write-Output ($indent + "[" + $type + "] " + $name + $loc)
        }
        Dump-Controls $child ($depth + 1) $maxDepth
        $child = $walk.GetNextSibling($child)
    }
}

Write-Output "---- UIA control tree (ControlView, depth 3) ----"
Dump-Controls $win 0 3
Write-Output "---- done ----"
