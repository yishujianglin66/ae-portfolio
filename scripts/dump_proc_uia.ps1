# Dump UIA tree of ALL top-level windows in a process, looking for Edit/Button controls.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File dump_proc_uia.ps1 -ProcId 33360
param([int]$ProcId = 33360)

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $ProcId)
$wins = $root.FindAll([System.Windows.Automation.TreeScope]::Children, $cond)
Write-Output ("Topaz top-level UIA windows: " + $wins.Count)
foreach ($w in $wins) {
    Write-Output ("-- WIN: [" + $w.Current.Name + "] cls=[" + $w.Current.ClassName + "]")
    $walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
    function Walk($el, $depth, $maxD) {
        if ($depth -gt $maxD) { return }
        $c = $walker.GetFirstChild($el)
        while ($c -ne $null) {
            $tp = $c.Current.ControlType.ProgrammaticName -replace "ControlType.",""
            $nm = $c.Current.Name
            $r = $c.Current.BoundingRectangle
            $loc = ""
            if ($r.Width -gt 0) { $loc = " @(" + [int]$r.X + "," + [int]$r.Y + ")" }
            if ($tp -in @("Edit","Button","ComboBox","List","ListItem","Tree") -or $nm.Length -gt 0) {
                Write-Output (("  " * $depth) + "[" + $tp + "] " + $nm + $loc)
            }
            Walk $c ($depth + 1) $maxD
            $c = $walker.GetNextSibling($c)
        }
    }
    Walk $w 1 6
}
Write-Output "DONE"
