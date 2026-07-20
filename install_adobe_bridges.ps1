# ================================================================
# Adobe MCP Bridge 一键安装脚本
# 将 JSX Listener 安装到所有已安装 Adobe 软件的 Startup 目录
# 需要管理员权限运行
# ================================================================

#Requires -RunAsAdministrator

$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\Users\Administrator\Desktop\AE-Knowledge-Vault"
$Python = "C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Adobe MCP Bridge 安装器" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 运行检测和安装
& $Python -c "
import sys; sys.path.insert(0, '$ProjectRoot')
from adobe_mcp_manager import AdobeMCPManager

m = AdobeMCPManager('$ProjectRoot')
m.detect_all()

installed = m.get_installed_apps()
if not installed:
    print('未检测到任何 Adobe 软件!')
    sys.exit(0)

print(f'检测到 {len(installed)} 个 Adobe 软件:')
for app in installed:
    info = m.installed_apps[app]
    status = '运行中' if info['running'] else '未运行'
    print(f'  [{info[\"short\"]}] {info[\"name\"]} ({status})')

print()
print('安装 Startup Listener...')
results = m.install_all()
for app, ok in results.items():
    status = 'OK' if ok else 'FAIL'
    print(f'  {app}: {status}')

print()
print('安装完成!')
print('重启 Adobe 软件后 Listener 将自动加载。')
"

Write-Host ""
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
