# Click at screen coordinates after activating a window by PID.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File ui_click.ps1 <PID> <X> <Y> [doubleclick]
param(
    [int]$ProcId = 33360,
    [int]$X,
    [int]$Y,
    [switch]$Dbl
)

Add-Type @"
using System;
using System.Runtime.InteropServices;
public class Win32Click {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool SetCursorPos(int x, int y);
    [DllImport("user32.dll")] public static extern void mouse_event(uint flags, uint dx, uint dy, uint data, UIntPtr extra);
    [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
    public const uint LEFTDOWN = 0x02;
    public const uint LEFTUP = 0x04;
}
"@

$proc = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
if (-not $proc) { Write-Output "NO_PROC $ProcId"; exit 1 }
[Win32Click]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 400

# 若窗口未激活，用 AppActivate 兜底
$fg = [Win32Click]::GetForegroundWindow()
if ($fg -ne $proc.MainWindowHandle) {
    $wshell = New-Object -ComObject WScript.Shell
    $wshell.AppActivate($proc.Id) | Out-Null
    Start-Sleep -Milliseconds 400
}

[Win32Click]::SetCursorPos($X, $Y) | Out-Null
Start-Sleep -Milliseconds 150
if ($Dbl) {
    [Win32Click]::mouse_event([Win32Click]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    [Win32Click]::mouse_event([Win32Click]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
    Start-Sleep -Milliseconds 60
    [Win32Click]::mouse_event([Win32Click]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    [Win32Click]::mouse_event([Win32Click]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
} else {
    [Win32Click]::mouse_event([Win32Click]::LEFTDOWN, 0, 0, 0, [UIntPtr]::Zero)
    [Win32Click]::mouse_event([Win32Click]::LEFTUP, 0, 0, 0, [UIntPtr]::Zero)
}
Write-Output "CLICKED $X,$Y pid=$ProcId"
