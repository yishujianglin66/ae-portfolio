$ErrorActionPreference = 'Continue'

# Load uninstalled fonts list
$uninstalledFile = 'D:\AE-Work\uninstalled_fonts.txt'
if (-not (Test-Path $uninstalledFile)) {
    Write-Error "Uninstalled fonts list not found: $uninstalledFile"
    exit 1
}

$fontsToInstall = @()
Get-Content -Path $uninstalledFile -Encoding UTF8 | ForEach-Object {
    $line = $_.Trim()
    if ($line -and (Test-Path $line)) {
        $fontsToInstall += $line
    }
}

$total = $fontsToInstall.Count
Write-Output "Total fonts to install: $total"

# Log file
$logFile = 'D:\AE-Work\font_install_log_v3.txt'
$startTime = Get-Date
"[$startTime] Start installing $total fonts" | Out-File -FilePath $logFile -Encoding UTF8

# Create Shell.Application instance
$shell = New-Object -ComObject Shell.Application
$fontsFolder = $shell.Namespace(0x14)
if ($null -eq $fontsFolder) {
    Write-Error "Failed to get Fonts namespace"
    exit 1
}

$success = 0
$failed = 0
$batchSize = 50
$counter = 0

foreach ($fontPath in $fontsToInstall) {
    $counter++
    try {
        # CopyHere with flags: 0x10 = no progress UI, 0x400 = no confirm, 0x1000 = no error UI
        $fontsFolder.CopyHere($fontPath, 0x1410)
        $success++
    } catch {
        $failed++
        $errMsg = $_.Exception.Message
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
