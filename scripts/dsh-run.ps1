<#
.SYNOPSIS
  DeepSeek Harness headless 模式包装脚本 — 将 DSH Agent 并入自动化管线。
.DESCRIPTION
  在项目目录启动一次性 Agent 会话: 执行任务 -> 打印最终答案 -> 退出。
  工作区 = 本项目根目录 (temp 在工作区外, 满足 Windows ACL 沙箱约束)。
  注意: 项目 .env 不得包含 DEEPSEEK_BASE_URL 等网络类变量 (DSH 安全策略)。
.EXAMPLE
  .\scripts\dsh-run.ps1 "跑 tests/test_camera_classifier.py 并修复失败"
.EXAMPLE
  .\scripts\dsh-run.ps1 "分析 core/content_metrics.py 的 camera_diversity_score 逻辑"
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Task
)

$ErrorActionPreference = "Stop"
$dsh = "C:\Users\Administrator\AppData\Roaming\npm\dsh.cmd"
$projectRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path $dsh)) {
    Write-Error "dsh.cmd not found: $dsh (npm i -g @deepseek-ai/dsh)"
}

Push-Location $projectRoot
try {
    & $dsh --profile headless $Task
} finally {
    Pop-Location
}
