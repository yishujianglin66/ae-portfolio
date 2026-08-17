# Diagnose current Topaz window state via UIA tree dump
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, 33360)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
if (-not $win) { Write-Output "NO_WIN"; exit 1 }
$r = $win.Current.BoundingRectangle
Write-Output ("WIN: [" + $win.Current.Name + "] rect X=" + [int]$r.X + " Y=" + [int]$r.Y + " W=" + [int]$r.Width + " H=" + [int]$r.Height)

$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
function Walk($el, $depth) {
    if ($depth -gt 4) { return }
    $c = $walker.GetFirstChild($el)
    while ($c -ne $null) {
        $nm = $c.Current.Name
        $tp = $c.Current.ControlType.ProgrammaticName -replace "ControlType.",""
        if ($nm.Length -gt 0) {
            $cr = $c.Current.BoundingRectangle
            $loc = ""
            if ($cr.Width -gt 0) { $loc = " @(" + [int]$cr.X + "," + [int]$cr.Y + ")" }
            Write-Output (("  " * $depth) + "[" + $tp + "] " + $nm + $loc)
        }
        Walk $c ($depth + 1)
        $c = $walker.GetNextSibling($c)
    }
}
Walk $win 0
