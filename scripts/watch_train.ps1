# watch_train.ps1 - Training Monitor
# Usage: powershell -ExecutionPolicy Bypass -File watch_train.ps1
# Ctrl+C to exit

$logFile = "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\logs\t32_balanced_train.log"
$errFile = "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\logs\t32_balanced_train_err.log"
$trainPid = 5992

while ($true) {
    Clear-Host
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  T32 LoRA Training Monitor $(Get-Date -Format 'HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan

    $p = Get-Process -Id $trainPid -ErrorAction SilentlyContinue
    if ($p -ne $null) {
        $cpuMin = [math]::Round($p.CPU / 60, 1)
        $memMB = [math]::Round($p.WorkingSet64 / 1MB, 0)
        Write-Host "  PID $trainPid | CPU ${cpuMin}min | MEM ${memMB}MB" -ForegroundColor Green
    }
    else {
        Write-Host "  PID $trainPid FINISHED" -ForegroundColor Yellow
    }

    try {
        $gpu = nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader 2>$null
        if ($gpu) {
            $parts = $gpu.Split(',') | ForEach-Object { $_.Trim() }
            Write-Host "  GPU: $($parts[0]) | VRAM $($parts[1])/$($parts[2]) | Temp $($parts[3])C" -ForegroundColor Green
        }
    }
    catch {
        Write-Host "  GPU: query failed" -ForegroundColor DarkGray
    }

    Write-Host ""

    if (Test-Path $logFile) {
        $lines = Get-Content $logFile -Tail 20
        $totalLines = (Get-Content $logFile).Count
        Write-Host "  Log ($totalLines lines):" -ForegroundColor Yellow
        foreach ($line in $lines) {
            if ($line -match 'Epoch|loss=|best') {
                Write-Host "  $line" -ForegroundColor White
            }
            elseif ($line -match 'LoRA|Dataset') {
                Write-Host "  $line" -ForegroundColor Magenta
            }
            else {
                Write-Host "  $line" -ForegroundColor Gray
            }
        }
    }

    if (Test-Path $errFile) {
        $errLines = Get-Content $errFile -Tail 3
        $hasError = $errLines | Where-Object { $_ -match 'Error|Exception|Traceback' }
        if ($hasError) {
            Write-Host ""
            Write-Host "  !! ERRORS DETECTED !!" -ForegroundColor Red
            foreach ($el in $errLines) {
                Write-Host "  $el" -ForegroundColor Red
            }
        }
    }

    $modelFile = "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\models\clip_lora_balanced_v1.pt"
    $bestFile = "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\models\clip_lora_balanced_best.pt"
    if (Test-Path $modelFile) {
        $sz = [math]::Round((Get-Item $modelFile).Length / 1MB, 1)
        Write-Host ""
        Write-Host "  Model saved: ${sz}MB" -ForegroundColor Green
    }
    if (Test-Path $bestFile) {
        $sz = [math]::Round((Get-Item $bestFile).Length / 1MB, 1)
        $tm = (Get-Item $bestFile).LastWriteTime.ToString("HH:mm:ss")
        Write-Host "  Best weights: ${sz}MB ($tm)" -ForegroundColor Green
    }

    Write-Host ""
    Write-Host "  Refreshing... (Ctrl+C to exit)" -ForegroundColor DarkGray
    Start-Sleep -Seconds 5
}
