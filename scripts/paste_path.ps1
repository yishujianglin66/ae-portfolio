# Set clipboard text then send Ctrl+L + Ctrl+V + Enter to a window by PID.
# Clipboard method avoids SendKeys escaping issues entirely.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File paste_path.ps1 -ProcId 24592 -Text "D:\path\file.mp4"
param(
    [int]$ProcId = 24592,
    [string]$Text
)

# 1. Set clipboard
Add-Type -AssemblyName System.Windows.Forms
$clip = New-Object System.Windows.Forms.DataObject
$clip.SetData([System.Windows.Forms.DataFormats]::UnicodeText, $Text)
[System.Windows.Forms.Clipboard]::SetDataObject($clip, $true)
Start-Sleep -Milliseconds 300

# 2. Activate window via SetForegroundWindow (more reliable than AppActivate)
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class FgWin {
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
    [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
}
"@
$proc = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
if (-not $proc) { Write-Output "NO_PROC $ProcId"; exit 1 }
[FgWin]::ShowWindow($proc.MainWindowHandle, 9) | Out-Null   # SW_RESTORE
[FgWin]::SetForegroundWindow($proc.MainWindowHandle) | Out-Null
Start-Sleep -Milliseconds 600

# 3. Send Ctrl+L, Ctrl+V, Enter
$wshell = New-Object -ComObject WScript.Shell
$wshell.SendKeys("^l")
Start-Sleep -Milliseconds 600
$wshell.SendKeys("^v")
Start-Sleep -Milliseconds 600
$wshell.SendKeys("{ENTER}")
Write-Output "PASTED & ENTERED"
