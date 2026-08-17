# Send keystrokes to a window by PID. Handle special chars for SendKeys.
# Usage: powershell -NoProfile -ExecutionPolicy Bypass -File sendkeys.ps1 -ProcId 24592 -Keys "^l"
param(
    [int]$ProcId = 24592,
    [string]$Keys
)

$proc = Get-Process -Id $ProcId -ErrorAction SilentlyContinue
if (-not $proc) { Write-Output "NO_PROC $ProcId"; exit 1 }

$wshell = New-Object -ComObject WScript.Shell
$wshell.AppActivate($ProcId) | Out-Null
Start-Sleep -Milliseconds 500
$wshell.SendKeys($Keys)
Write-Output "SENT: $Keys"
