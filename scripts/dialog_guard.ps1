# AE dialog guard: auto-close "Boris FX - Continuum Error" popups every 10s
# Validated 2026-08-17: ESC + Enter closes it and AE continues.
$ErrorActionPreference = "SilentlyContinue"
Add-Type -AssemblyName Microsoft.VisualBasic, System.Windows.Forms
$log = "C:\Users\Administrator\Desktop\AE-Knowledge-Vault\tmp\dialog_guard.log"
$n = 0
while ($true) {
    $p = Get-Process AfterFX -ErrorAction SilentlyContinue
    if ($p -and $p.MainWindowTitle -match "Boris FX") {
        try {
            [Microsoft.VisualBasic.Interaction]::AppActivate($p.Id) | Out-Null
            Start-Sleep -Milliseconds 300
            [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
            Start-Sleep -Milliseconds 500
            [System.Windows.Forms.SendKeys]::SendWait('{ENTER}')
            $n++
            "$(Get-Date -Format 'HH:mm:ss') closed #$n [$($p.MainWindowTitle)]" | Out-File -Append -Encoding utf8 $log
        } catch {}
    }
    Start-Sleep -Seconds 10
}
