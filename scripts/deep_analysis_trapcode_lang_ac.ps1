# Deep analysis: Trapcode installation, Chinese UI, AfterCodecs
$ErrorActionPreference = 'Continue'

$output = @()
$aeRoot = "C:\Program Files\Adobe\Adobe After Effects 2025"

$output += "=== AE 2025 深度分析：Trapcode / 中英文 / AfterCodecs ==="
$output += ""

# 1. Trapcode 深度扫描
$output += "=== 1. Trapcode Suite 深度安装扫描 ==="
$pluginsDir = Join-Path $aeRoot "Support Files\Plug-ins"

# 搜索所有 Red Giant / Trapcode 相关文件
$output += "  --- 搜索 Red Giant / Trapcode 相关文件 ---"
$rgFiles = Get-ChildItem $pluginsDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match 'Trapcode|trapcode|Red Giant|red giant|RG_|Particular|Form|Shine|Starglow|Lux|Mir|Tao|Echospace|3D Stroke|Sound Keys|Grow Bounds|Horizon|Geo'
}
$output += "  找到 $($rgFiles.Count) 个相关文件"
$rgFiles | ForEach-Object {
    $rel = $_.FullName.Replace($pluginsDir, "")
    $sizeKB = [math]::Round($_.Length / 1KB, 2)
    $output += "    $rel ($sizeKB KB)"
}
$output += ""

# 检查公共插件目录（Common Files 也可能存 Red Giant 插件）
$output += "  --- 搜索 Common Files 中的 Red Giant ---"
$commonPluginPaths = @(
    "C:\Program Files\Adobe\Common\Plug-ins\7.0\MediaCore",
    "C:\Program Files\Red Giant",
    "C:\Program Files\Maxon"
)
foreach ($cp in $commonPluginPaths) {
    if (Test-Path $cp) {
        $files = Get-ChildItem $cp -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $_.Extension -in '.aex', '.plugin', '.dll', '.exe'
        }
        $output += "  $cp : $($files.Count) 个文件"
        $trapFiles = $files | Where-Object { $_.Name -match 'Trapcode|trapcode|Particular|Form|Shine|Starglow' }
        if ($trapFiles) {
            $trapFiles | ForEach-Object {
                $output += "    $($_.Name) ($([math]::Round($_.Length / 1KB, 2)) KB)"
            }
        }
    }
}
$output += ""

# 检查注册表
$output += "  --- 注册表检查 Trapcode ---"
$regPaths = @(
    "HKLM:\SOFTWARE\Red Giant",
    "HKLM:\SOFTWARE\Maxon",
    "HKCU:\SOFTWARE\Red Giant"
)
foreach ($rp in $regPaths) {
    if (Test-Path $rp) {
        $output += "  $rp 存在"
        $subkeys = Get-ChildItem $rp -ErrorAction SilentlyContinue | Select-Object -First 10
        $subkeys | ForEach-Object {
            $output += "    $($_.PSChildName)"
        }
    }
}
$output += ""

# 2. 中英文界面检查
$output += "=== 2. 中英文界面状态分析 ==="

# AE 语言配置
$aeAppData = "$env:APPDATA\Adobe\After Effects"
if (Test-Path $aeAppData) {
    $output += "  AE 用户配置目录: $aeAppData"
    $versions = Get-ChildItem $aeAppData -Directory -ErrorAction SilentlyContinue
    foreach ($v in $versions) {
        $output += "    版本目录: $($v.Name)"
        # 查找语言配置
        $prefsDir = Join-Path $v.FullName "Prefs"
        if (Test-Path $prefsDir) {
            $output += "      Prefs 目录存在"
            $langFiles = Get-ChildItem $prefsDir -Filter "*lang*" -ErrorAction SilentlyContinue
            $langFiles | ForEach-Object {
                $output += "        $($_.Name)"
            }
        }
    }
}
$output += ""

# AE 安装目录的语言资源
$output += "  --- AE 安装目录语言资源 ---"
$resDir = Join-Path $aeRoot "Support Files\AMT"
if (Test-Path $resDir) {
    $langDirs = Get-ChildItem $resDir -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^[a-z]{2}_[A-Z]{2}$|^zh_|^en_' }
    $langDirs | ForEach-Object {
        $output += "    $($_.Name)"
    }
}

# 检查 application.xml
$appXml = Join-Path $aeRoot "Support Files\AMT\application.xml"
if (Test-Path $appXml) {
    [xml]$xml = Get-Content $appXml
    $langs = $xml.Application.Resources.SupportedLanguages.Language
    $output += "  支持语言: $langs"
}
$output += ""

# 检查安装的语言包
$output += "  --- 已安装语言包（AMT Languages）---"
$langPackDir = Join-Path $aeRoot "Support Files\AMT\Languages"
if (Test-Path $langPackDir) {
    Get-ChildItem $langPackDir -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        $output += "    $($_.Name)"
    }
}
$output += ""

# 3. AfterCodecs 检查
$output += "=== 3. AfterCodecs 安装状态 ==="

# 检查插件目录
$acFiles = Get-ChildItem $pluginsDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match 'AfterCodecs|aftercodecs|After_Codecs|autokroma'
}
$output += "  插件目录 AfterCodecs 文件: $($acFiles.Count)"
$acFiles | ForEach-Object {
    $rel = $_.FullName.Replace($pluginsDir, "")
    $output += "    $rel ($([math]::Round($_.Length / 1KB, 2)) KB)"
}

# 检查脚本目录
$scriptsDir = Join-Path $aeRoot "Support Files\Scripts"
$acScripts = Get-ChildItem $scriptsDir -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match 'AfterCodecs|aftercodecs|After_Codecs'
}
$output += "  脚本目录 AfterCodecs 文件: $($acScripts.Count)"
$acScripts | ForEach-Object {
    $rel = $_.FullName.Replace($scriptsDir, "")
    $output += "    $rel"
}

# 检查 Common Files
$acCommon = Get-ChildItem "C:\Program Files\Adobe\Common\Plug-ins" -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match 'AfterCodecs|aftercodecs|autokroma'
}
$output += "  Common AfterCodecs: $($acCommon.Count)"

# 检查 Autokroma 目录
$autokromaPath = "C:\Program Files (x86)\Autokroma"
if (-not (Test-Path $autokromaPath)) {
    $autokromaPath = "C:\Program Files\Autokroma"
}
if (Test-Path $autokromaPath) {
    $output += "  Autokroma 目录存在: $autokromaPath"
    Get-ChildItem $autokromaPath -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 10 | ForEach-Object {
        $output += "    $($_.Name)"
    }
} else {
    $output += "  Autokroma 目录不存在（AfterCodecs 未安装）"
}
$output += ""

# 4. PR 状态（AfterCodecs for PR）
$output += "=== 4. Premiere Pro & AME 状态 ==="
$prPaths = @(
    "C:\Program Files\Adobe\Adobe Premiere Pro 2025",
    "D:\Me\Adobe Media Encoder 2025"
)
foreach ($prp in $prPaths) {
    if (Test-Path $prp) {
        $output += "  $prp 存在"
        $prPlugins = Join-Path $prp "Plug-ins\Common"
        if (Test-Path $prPlugins) {
            $acPR = Get-ChildItem $prPlugins -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
                $_.Name -match 'AfterCodecs|aftercodecs'
            }
            $output += "    AfterCodecs: $($acPR.Count) 个文件"
        }
    }
}
$output += ""

# 5. 汉化补丁/中文语言包检查
$output += "=== 5. 汉化/中文语言包痕迹检查 ==="

# 搜索汉化相关文件
$cnFiles = Get-ChildItem $aeRoot -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
    $_.Name -match '中文|汉化|Chinese|zh_CN|zh_TW|cn_' -or $_.Directory.Name -match '中文|汉化|Chinese|zh_CN'
} | Select-Object -First 20
$output += "  中文/汉化相关文件: $($cnFiles.Count) 个"
$cnFiles | ForEach-Object {
    $rel = $_.FullName.Replace($aeRoot, "")
    $output += "    $rel"
}
$output += ""

# 保存
$outputFile = "D:\AE-Work\ae_deep_analysis_trapcode_lang_ac.txt"
$output | Out-File -FilePath $outputFile -Encoding UTF8
Write-Output "Analysis complete. Saved to $outputFile"
Write-Output "Total lines: $($output.Count)"
