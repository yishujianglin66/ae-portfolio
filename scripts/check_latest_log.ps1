# Get the latest HDInstaller.log errors
$log = "C:\Users\Administrator\AppData\Local\Temp\CreativeCloud\ACC\AdobeDownload\HDInstaller.log"
if (Test-Path $log) {
    $lastWrite = (Get-Item $log).LastWriteTime
    Write-Output "Log last modified: $lastWrite"
    Write-Output ""
    Write-Output "=== Searching for ERROR / Error Code / Error_Subcode_Details ==="
    Get-Content $log -Encoding UTF8 | Select-String -Pattern "Error_Subcode_Details|errorCode|error code|Error 2|Error 146|146|无法移动|cannot move|failed to" | Select-Object -Last 30 | ForEach-Object {
        Write-Output $_.Line
    }
    Write-Output ""
    Write-Output "=== Last 80 lines of log ==="
    Get-Content $log -Tail 80 -Encoding UTF8 | ForEach-Object {
        Write-Output $_
    }
} else {
    Write-Output "Log file not found"
}
