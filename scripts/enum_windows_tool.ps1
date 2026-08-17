# Enumerate visible windows and match optional pattern.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File enum_windows_tool.ps1 [-Pattern "打开"]
param([string]$Pattern = "")

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class WinEnumTool {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
}
'@

$sb = New-Object System.Text.StringBuilder 512
$items = New-Object System.Collections.ArrayList
$cb = [WinEnumTool+EnumWindowsProc]{
    param($h, $lp)
    if ([WinEnumTool]::IsWindowVisible($h)) {
        [WinEnumTool]::GetWindowText($h, $sb, 512) | Out-Null
        $t = $sb.ToString()
        if ($t.Length -gt 0) {
            $p = 0
            [WinEnumTool]::GetWindowThreadProcessId($h, [ref]$p) | Out-Null
            $script:items.Add("PID=$p [$t]") | Out-Null
        }
    }
    return $true
}
[WinEnumTool]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null
foreach ($i in $items) {
    if ($Pattern -eq "" -or $i -like "*$Pattern*") {
        Write-Output $i
    }
}
