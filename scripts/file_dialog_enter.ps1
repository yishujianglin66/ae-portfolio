# Precise: find the CabinetWClass HWND in explorer PID, activate it,
# then type filename + Enter via SendKeys.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File file_dialog_enter.ps1 -ExplorerPid 24592 -FileName "x.mp4"
param(
    [int]$ExplorerPid = 24592,
    [string]$FileName = "v22_solo_leveling_enhanced_rife_local.mp4"
)

Add-Type -TypeDefinition @'
using System;
using System.Text;
using System.Runtime.InteropServices;
public class FdHelp {
    [DllImport("user32.dll")] public static extern bool EnumWindows(EnumWindowsProc cb, IntPtr lp);
    [DllImport("user32.dll")] public static extern int GetClassName(IntPtr h, StringBuilder s, int n);
    [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
    public delegate bool EnumWindowsProc(IntPtr h, IntPtr lp);
}
'@

$targetHwnd = [IntPtr]::Zero
$clsBuf = New-Object System.Text.StringBuilder 256
$cb = [FdHelp+EnumWindowsProc]{
    param($h, $lp)
    [FdHelp]::GetClassName($h, $clsBuf, 256) | Out-Null
    $p = 0
    [FdHelp]::GetWindowThreadProcessId($h, [ref]$p) | Out-Null
    if ($p -eq $ExplorerPid -and $clsBuf.ToString() -eq "CabinetWClass") {
        $script:hwnd = $h
        return $false  # stop enumerating
    }
    return $true
}
[FdHelp]::EnumWindows($cb, [IntPtr]::Zero) | Out-Null

if (-not $script:hwnd) { Write-Output "ERR: CabinetWClass not found in PID $ExplorerPid"; exit 1 }
Write-Output ("FOUND CabinetWClass hwnd=" + $script:hwnd)

[FdHelp]::ShowWindow($script:hwnd, 9) | Out-Null   # SW_RESTORE
Start-Sleep -Milliseconds 400
[FdHelp]::SetForegroundWindow($script:hwnd) | Out-Null
Start-Sleep -Milliseconds 600

$wshell = New-Object -ComObject WScript.Shell
$wshell.SendKeys("^l")                    # focus address/file-name bar
Start-Sleep -Milliseconds 700
$wshell.SendKeys($FileName)               # pure filename, no special chars
Start-Sleep -Milliseconds 500
$wshell.SendKeys("{ENTER}")
Write-Output "SENT filename + ENTER"
