Add-Type @"
using System;
using System.Runtime.InteropServices;
using System.Text;
using System.Collections.Generic;
public class WindowChecker {
    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern int GetWindowTextLength(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    public static List<string> GetWindowsForPid(int pid) {
        var result = new List<string>();
        EnumWindows((hWnd, lParam) => {
            uint procId;
            GetWindowThreadProcessId(hWnd, out procId);
            if (procId == pid && IsWindowVisible(hWnd)) {
                int len = GetWindowTextLength(hWnd);
                if (len > 0) {
                    var sb = new StringBuilder(len + 1);
                    GetWindowText(hWnd, sb, sb.Capacity);
                    result.Add(hWnd.ToInt64() + " | " + sb.ToString());
                }
            }
            return true;
        }, IntPtr.Zero);
        return result;
    }
}
"@

$ae = Get-Process AfterFX -ErrorAction SilentlyContinue
if ($ae) {
    Write-Output "AE PID: $($ae.Id)"
    $windows = [WindowChecker]::GetWindowsForPid($ae.Id)
    if ($windows.Count -eq 0) {
        Write-Output "No visible windows for AE process"
    } else {
        Write-Output "AE visible windows:"
        foreach ($w in $windows) {
            Write-Output "  $w"
        }
    }
} else {
    Write-Output "AE not running"
}
