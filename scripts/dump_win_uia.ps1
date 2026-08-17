# Dump UIA tree of a specific window by PID + class name fragment.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File dump_win_uia.ps1 -ProcId 24592 -Class "Xaml"
param(
    [int]$ProcId = 24592,
    [string]$Class = "Xaml"
)

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$all = $root.FindAll([System.Windows.Automation.TreeScope]::Children, [System.Windows.Automation.Condition]::TrueCondition)
$found = $null
foreach ($w in $all) {
    $procId = $w.Current.ProcessId
    if ($procId -eq $ProcId -and $w.Current.ClassName -like "*$Class*") {
        $found = $w
        Write-Output ("WIN: [" + $w.Current.Name + "] cls=[" + $w.Current.ClassName + "]")
        break
    }
}
if (-not $found) { Write-Output "WIN_NOT_FOUND"; exit 1 }

$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
function Walk($el, $depth) {
    if ($depth -gt 8) { return }
    $c = $walker.GetFirstChild($el)
    while ($c -ne $null) {
        $tp = $c.Current.ControlType.ProgrammaticName -replace "ControlType.",""
        $nm = $c.Current.Name
        $r = $c.Current.BoundingRectangle
        $loc = ""
        if ($r.Width -gt 0) { $loc = " @(" + [int]$r.X + "," + [int]$r.Y + ")" }
        if ($tp -in @("Edit","Button","ListItem","TreeItem") -or $nm.Length -gt 0) {
            Write-Output (("  " * $depth) + "[" + $tp + "] " + $nm + $loc)
        }
        Walk $c ($depth + 1)
        $c = $walker.GetNextSibling($c)
    }
}
Walk $found 0
Write-Output "DONE"
