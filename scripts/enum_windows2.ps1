# Enumerate visible windows with class names. Optionally filter.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File enum_windows2.ps1 [-Pattern "Dialog"]
param([string]$Pattern = "")

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinEnum2 {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
}
'@

$sb = New-Object System.Text.StringBuilder 512
$cb2 = New-Object System.Text.StringBuilder 256
$items = New-Object System.Collections.ArrayList
$cb = [WinEnum2+EnumWindowsProc]{
    param($h, $lp)
    if ([WinEnum2]::IsWindowVisible($h)) {
        [WinEnum2]::GetWindowText($h, $sb, 512) | Out-Null
        [WinEnum2]::GetClassName($h, $cb2, 256) | Out-Null
        $t = $sb.ToString()
        $c = $cb2.ToString()
        $p = 0
        [WinEnum2]::GetWindowThreadProcessId($h, [ref]$p) | Out-Null
        $script:items.Add("PID=$p CLS=[$c] T=[$t]") | Out-Null
    }
    return $true
}
[WinEnum2]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
foreach ($i in $items) {
    if ($Pattern -eq "" -or $i -like "*$Pattern*") {
        Write-Output $i
    }
}
