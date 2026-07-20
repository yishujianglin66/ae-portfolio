$ErrorActionPreference = 'Continue'

# Load deduped install list
$installList = 'D:\AE-Work\fonts_to_install_dedup.txt'
if (-not (Test-Path $installList)) {
    Write-Error "Install list not found: $installList"
    exit 1
}

$fontsToInstall = @()
Get-Content -Path $installList -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line -and (Test-Path $line)) {
        $fontsToInstall += $line
    }
}

$total = $fontsToInstall.Count
Write-Output "Total fonts to install (deduped): $total"

# Log file
$logFile = 'D:\AE-Work\font_install_log_v4.txt'
$startTime = Get-Date
"[$startTime] Start installing $total deduped fonts" | Out-File -FilePath $logFile -Encoding UTF8

# Create Shell.Application instance
$shell = New-Object -ComObject Shell.Application
$fontsFolder = $shell.Namespace(0x14)
if ($null -eq $fontsFolder) {
    Write-Error "Failed to get Fonts namespace"
    exit 1
}

$success = 0
$failed = 0
$failedList = @()
$batchSize = 20
$counter = 0

foreach ($fontPath in $fontsToInstall) {
    $counter++
    try {
        # 0x1410 = 0x10 (no progress UI) + 0x400 (no confirm) + 0x1000 (no error UI)
        $fontsFolder.CopyHere($fontPath, 0x1410)
        $success++
    } catch {
        $failed++
        $errMsg = $_.Exception.Message
        $failedList += "$fontPath|$errMsg"
        "[$counter] FAILED: $fontPath - $errMsg" | Out-File -FilePath $logFile -Append -Encoding UTF8
    }

    # Progress every batch
    if ($counter % $batchSize -eq 0 -or $counter -eq $total) {
        $now = Get-Date
        $elapsed = ($now - $startTime).TotalSeconds
        $rate = if ($elapsed -gt 0) { [math]::Round($counter / $elapsed, 2) } else { 0 }
        $remaining = if ($rate -gt 0) { [math]::Round(($total - $counter) / $rate / 60, 1) } else { 0 }
        $msg = "[$now] Progress: $counter/$total | Success: $success | Failed: $failed | Rate: ${rate}/s | ETA: ${remaining}min"
        Write-Output $msg
        $msg | Out-File -FilePath $logFile -Append -Encoding UTF8
    }
}

$endTime = Get-Date
$totalTime = [math]::Round(($endTime - $startTime).TotalMinutes, 2)
$summary = "[$endTime] DONE. Total: $total | Success: $success | Failed: $failed | Time: ${totalTime}min"
Write-Output $summary
$summary | Out-File -FilePath $logFile -Append -Encoding UTF8

# Save failed list
if ($failedList.Count -gt 0) {
    $failedFile = 'D:\AE-Work\font_install_failed_v4.txt'
    $failedList | Out-File -FilePath $failedFile -Encoding UTF8
    Write-Output "Failed list saved: $failedFile"
}
