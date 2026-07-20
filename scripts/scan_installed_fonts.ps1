$ErrorActionPreference = 'Stop'
$installed = @{}

# 1. 系统字体目录
$sysFontsDir = 'C:\Windows\Fonts'
if (Test-Path $sysFontsDir) {
    Get-ChildItem -Path $sysFontsDir -File -ErrorAction SilentlyContinue | ForEach-Object {
        $name = $_.Name.ToLower()
        if (-not $installed.ContainsKey($name)) {
            $installed[$name] = $_.FullName
        }
    }
}

# 2. 用户字体目录
$userFontsDir = "$env:LOCALAPPDATA\Microsoft\Windows\Fonts\"
if (Test-Path $userFontsDir) {
    Get-ChildItem -Path $userFontsDir -File -ErrorAction SilentlyContinue | ForEach-Object {
        $name = $_.Name.ToLower()
        if (-not $installed.ContainsKey($name)) {
            $installed[$name] = $_.FullName
        }
    }
}

# 3. 注册表字体项（含非文件名注册的字体）
try {
    $regPaths = @(
        'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts',
        'HKCU:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts'
    )
    foreach ($rp in $regPaths) {
        if (Test-Path $rp) {
            $props = Get-ItemProperty -Path $rp -ErrorAction SilentlyContinue
            if ($props) {
                $props.PSObject.Properties | Where-Object {
                    $_.Name -ne 'PSPath' -and $_.Name -ne 'PSParentPath' -and $_.Name -ne 'PSChildName' -and $_.Name -ne 'PSDrive' -and $_.Name -ne 'PSProvider'
                } | ForEach-Object {
                    $val = $_.Value
                    if ($val) {
                        $fname = Split-Path -Leaf $val
                        if (-not [string]::IsNullOrEmpty($fname)) {
                            $key = $fname.ToLower()
                            if (-not $installed.ContainsKey($key)) {
                                $installed[$key] = $val
                            }
                        }
                    }
                }
            }
        }
    }
} catch {}

Write-Output "已安装字体总数: $($installed.Count)"

# 输出前 30 个示例
Write-Output '---示例前 30 个已安装字体---'
$installed.Keys | Sort-Object | Select-Object -First 30 | ForEach-Object {
    Write-Output "  $_"
}

# 保存完整列表到 D:\AE-Work\installed_fonts.txt
$installed.Keys | Sort-Object | Out-File -FilePath 'D:\AE-Work\installed_fonts.txt' -Encoding UTF8
Write-Output '---'
Write-Output "完整列表已保存到 D:\AE-Work\installed_fonts.txt"
