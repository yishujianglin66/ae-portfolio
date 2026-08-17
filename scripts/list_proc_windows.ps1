# List all windows (top-level + children) of a PID via EnumWindows + EnumChildWindows.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File list_proc_windows.ps1 -ProcId 33360
param([int]$ProcId = 33360)

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class ProcWin {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern bool EnumChildWindows(IntPtr h, EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
    public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
}
'@

$script:items = New-Object System.Collections.ArrayList

function DumpChildren($hwnd, $indent) {
    $cb = [ProcWin+EnumWindowsProc]{
        param($h, $lp)
        $cls = New-Object System.Text.StringBuilder 256
        $txt = New-Object System.Text.StringBuilder 512
        [ProcWin]::GetClassName($h, $cls, 256) | Out-Null
        [ProcWin]::GetWindowText($h, $txt, 512) | Out-Null
        $vis = [ProcWin]::IsWindowVisible($h)
        $script:items.Add(("  " * $indent) + "HWND=$h CLS=[" + $cls.ToString() + "] VIS=$vis T=[" + $txt.ToString() + "]") | Out-Null
        DumpChildren $h ($indent + 1)
        return $true
    }
    [ProcWin]::EnumChildWindows($hwnd, $cb, [IntPtr]::Zero) | Out-Null
}

$cbTop = [ProcWin+EnumWindowsProc]{
    param($h, $lp)
    $p = 0
    [ProcWin]::GetWindowThreadProcessId($h, [ref]$p) | Out-Null
    if ($p -eq $ProcId) {
        $cls = New-Object System.Text.StringBuilder 256
        $txt = New-Object System.Text.StringBuilder 512
        [ProcWin]::GetClassName($h, $cls, 256) | Out-Null
        [ProcWin]::GetWindowText($h, $txt, 512) | Out-Null
        $vis = [ProcWin]::IsWindowVisible($h)
        $script:items.Add(("TOP HWND=" + $h + " CLS=[" + $cls.ToString() + "] VIS=$vis T=[" + $txt.ToString() + "]")) | Out-Null
        DumpChildren $h 1
    }
    return $true
}
[ProcWin]::EnumWindows($cbTop, [IntPtr]::Zero) | Out-Null
foreach ($i in $script:items) { Write-Output $i }
