# Find XamlExplorerHostIslandWindow child HWND in explorer PID and activate it.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File focus_xaml_dialog.ps1 -ExplorerPid 24592
param([int]$ExplorerPid = 24592)

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class XamlFocus {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
}
'@

# First find the top-level explorer windows for this PID
$tops = New-Object System.Collections.ArrayList
$clsBuf = New-Object System.Text.StringBuilder 256
$cbTop = [XamlFocus+EnumWindowsProc]{
    param($h, $lp)
    $p = 0
    [XamlFocus]::GetWindowThreadProcessId($h, [ref]$p) | Out-Null
    if ($p -eq $ExplorerPid -and [XamlFocus]::IsWindowVisible($h)) {
        $script:tops.Add($h) | Out-Null
    }
    return $true
}
[XamlFocus]::EnumWindows($cbTop, [IntPtr]::Zero) | Out-Null

$script:xamlHwnd = [IntPtr]::Zero
foreach ($top in $tops) {
    $cbChild = [XamlFocus+EnumWindowsProc]{
        param($h, $lp)
        [XamlFocus]::GetClassName($h, $clsBuf, 256) | Out-Null
        if ($clsBuf.ToString() -like "*XamlExplorer*") {
            $script:xamlHwnd = $h
            return $false
        }
        return $true
    }
    [XamlFocus]::EnumChildWindows($top, $cbChild, [IntPtr]::Zero) | Out-Null
    if ($script:xamlHwnd -ne [IntPtr]::Zero) { break }
}

if ($script:xamlHwnd -eq [IntPtr]::Zero) {
    Write-Output "ERR: Xaml dialog child not found"
    exit 1
}
Write-Output ("FOUND Xaml dialog hwnd=" + $script:xamlHwnd)
[XamlFocus]::ShowWindow($script:xamlHwnd, 9) | Out-Null
Start-Sleep -Milliseconds 300
[XamlFocus]::SetForegroundWindow($script:xamlHwnd) | Out-Null
Start-Sleep -Milliseconds 600
Write-Output "FOCUSED"
