# 复制 AE MCP Bridge 脚本到 AE 脚本目录（提权版）
param(
    [string]$Source = "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\ae-mcp-server\scripts",
    [string]$Dest = "C:\Program Files\Adobe\Adobe After Effects 2025\Support Files\Scripts\ae-mcp-bridge"
)

if (-not (Test-Path $Source)) {
    Write-Host "Source not found: $Source" -ForegroundColor Red
    exit 1
}

if (Test-Path $Dest) {
    Remove-Item -Recurse -Force $Dest
}

Copy-Item -Path $Source -Destination $Dest -Recurse -Force

$count = (Get-ChildItem -Path $Dest -Recurse -File | Where-Object { $_.Extension -eq ".jsx" }).Count
Write-Host "Copied $count JSX files to: $Dest" -ForegroundColor Green
exit 0
