$events = Get-WinEvent -LogName Application -MaxEvents 50 | Where-Object { $_.ProviderName -match 'Application Error|AfterEffects|Boris|Continuum|\.NET Runtime' }
foreach ($e in $events) {
    $msg = $e.Message
    if ($msg.Length -gt 400) { $msg = $msg.Substring(0, 400) }
    Write-Output "=== [$($e.TimeCreated)] $($e.ProviderName) / $($e.LevelDisplayName) ==="
    Write-Output $msg
    Write-Output ""
}
