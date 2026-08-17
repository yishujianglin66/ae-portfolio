# Invoke a named element via any available pattern (Invoke/Legacy/Selection/Toggle).
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File invoke_named.ps1 -Name "4K增强"
param([string]$Name = "4K增强")

Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

$topazId = 33360
$root = [System.Windows.Automation.AutomationElement]::RootElement
$cond = New-Object System.Windows.Automation.PropertyCondition([System.Windows.Automation.AutomationElement]::ProcessIdProperty, $topazId)
$win = $root.FindFirst([System.Windows.Automation.TreeScope]::Children, $cond)
if (-not $win) { Write-Output "ERR: no window"; exit 1 }

$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker
$script:el = $null
function Find-Named($el, $kw, $depth) {
    if ($depth -gt 8 -or $script:el) { return }
    $c = $walker.GetFirstChild($el)
    while ($c -ne $null) {
        $n = $c.Current.Name
        if ($n -like "*$kw*") {
            $script:el = $c
            Write-Output ("FOUND: [" + $n + "] type=" + $c.Current.ControlType.ProgrammaticName)
            return
        }
        Find-Named $c $kw ($depth + 1)
        $c = $walker.GetNextSibling($c)
    }
}
Find-Named $win $Name 0
if (-not $script:el) { Write-Output "NOT_FOUND: $Name"; exit 1 }

$ok = $false
# Try SelectionItem (preset cards use this)
try {
    $p = $script:el.GetCurrentPattern([System.Windows.Automation.SelectionItemPattern]::Pattern)
    $p.Select()
    Write-Output "SELECTED via SelectionItemPattern"
    $ok = $true
} catch {}
if (-not $ok) {
    try {
        $script:el.GetCurrentPattern([System.Windows.Automation.InvokePattern]::Pattern).Invoke()
        Write-Output "INVOKED via InvokePattern"
        $ok = $true
    } catch {}
}
if (-not $ok) {
    try {
        $script:el.GetCurrentPattern([System.Windows.Automation.LegacyIAccessiblePattern]::Pattern).DoDefaultAction()
        Write-Output "INVOKED via LegacyIAccessible"
        $ok = $true
    } catch {}
}
if (-not $ok) {
    try {
        $script:el.GetCurrentPattern([System.Windows.Automation.TogglePattern]::Pattern).Toggle()
        Write-Output "TOGGLED via TogglePattern"
        $ok = $true
    } catch {}
}
if (-not $ok) { Write-Output "NO_PATTERN_AVAILABLE" }
