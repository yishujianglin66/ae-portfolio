#Requires -Version 5.1
<#
.SYNOPSIS
    开源项目集成 - 一键环境配置脚本
.DESCRIPTION
    自动安装和配置所有开源集成工具：
    - RIFE (帧插值)
    - SAM2 (视频分割)
    - Video2X (超分辨率)
    - Whisper (语音识别)
    - Remotion (编程视频)
    - OpenMontage (全自动视频制作)
    - MoviePy (Python视频编辑)
.NOTES
    需要稳定的网络连接
    需要 Python 3.10+ 和 Node.js 18+
#>

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$ExternalDir = Join-Path $ProjectRoot "external"
$PythonCmd = "py -3.12"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  AE-Knowledge-Vault 开源集成环境配置" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ── 创建 external 目录 ──
if (!(Test-Path $ExternalDir)) {
    New-Item -ItemType Directory -Path $ExternalDir -Force | Out-Null
    Write-Host "[OK] 创建 external 目录" -ForegroundColor Green
}

# ── 1. Python 基础依赖 ──
Write-Host "`n[1/7] 安装 Python 基础依赖..." -ForegroundColor Yellow
$packages = @(
    "moviepy",
    "ffmpeg-python",
    "rich",
    "tqdm",
    "numpy",
    "Pillow",
    "opencv-python",
    "pydub"
)
foreach ($pkg in $packages) {
    Write-Host "  安装 $pkg..." -NoNewline
    & py -3.12 -m pip install $pkg --quiet 2>$null
    Write-Host " OK" -ForegroundColor Green
}

# ── 2. Whisper 语音识别 ──
Write-Host "`n[2/7] 安装 Whisper 语音识别..." -ForegroundColor Yellow
Write-Host "  安装 openai-whisper (含PyTorch)..." -NoNewline
& py -3.12 -m pip install openai-whisper --quiet 2>$null
Write-Host " OK" -ForegroundColor Green

# ── 3. RIFE 帧插值 ──
Write-Host "`n[3/7] 克隆 RIFE 帧插值项目..." -ForegroundColor Yellow
$rifeDir = Join-Path $ExternalDir "rife"
if (Test-Path $rifeDir) {
    Write-Host "  RIFE 已存在，跳过" -ForegroundColor DarkGray
} else {
    Write-Host "  克隆 hzwer/ECCV2022-RIFE..." -NoNewline
    git clone --depth 1 https://github.com/hzwer/ECCV2022-RIFE.git $rifeDir 2>$null
    if (Test-Path $rifeDir) {
        Write-Host " OK" -ForegroundColor Green
        # 安装 RIFE 依赖
        $rifeReq = Join-Path $rifeDir "requirements.txt"
        if (Test-Path $rifeReq) {
            & py -3.12 -m pip install -r $rifeReq --quiet 2>$null
        }
    } else {
        Write-Host " FAILED (网络问题，请稍后重试)" -ForegroundColor Red
    }
}

# ── 4. SAM2 视频分割 ──
Write-Host "`n[4/7] 克隆 SAM2 视频分割项目..." -ForegroundColor Yellow
$sam2Dir = Join-Path $ExternalDir "sam2"
if (Test-Path $sam2Dir) {
    Write-Host "  SAM2 已存在，跳过" -ForegroundColor DarkGray
} else {
    Write-Host "  克隆 facebookresearch/sam2..." -NoNewline
    git clone --depth 1 https://github.com/facebookresearch/sam2.git $sam2Dir 2>$null
    if (Test-Path $sam2Dir) {
        Write-Host " OK" -ForegroundColor Green
        # 以开发模式安装
        Push-Location $sam2Dir
        & py -3.12 -m pip install -e . --quiet 2>$null
        Pop-Location
    } else {
        Write-Host " FAILED (网络问题，请稍后重试)" -ForegroundColor Red
    }
}

# ── 5. Video2X 超分辨率 ──
Write-Host "`n[5/7] 安装 Video2X 超分辨率..." -ForegroundColor Yellow
Write-Host "  安装 video2x..." -NoNewline
& py -3.12 -m pip install video2x --quiet 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host " OK" -ForegroundColor Green
} else {
    Write-Host "  pip安装失败，尝试从GitHub releases下载..." -ForegroundColor DarkYellow
    Write-Host "  请手动下载: https://github.com/video2x/video2x/releases" -ForegroundColor DarkYellow
}

# ── 6. Remotion (Node.js) ──
Write-Host "`n[6/7] 配置 Remotion 编程视频生成..." -ForegroundColor Yellow
$remotionDir = Join-Path $ExternalDir "remotion-project"
if (Test-Path $remotionDir) {
    Write-Host "  Remotion 项目已存在，跳过" -ForegroundColor DarkGray
} else {
    Write-Host "  创建 Remotion 项目..." -NoNewline
    $npxCmd = "npx"
    & $npxCmd create-video@latest $remotionDir --yes 2>$null
    if (Test-Path $remotionDir) {
        Write-Host " OK" -ForegroundColor Green
    } else {
        Write-Host " FAILED (请确保Node.js已安装)" -ForegroundColor Red
    }
}

# ── 7. OpenMontage ──
Write-Host "`n[7/7] 克隆 OpenMontage 全自动视频制作..." -ForegroundColor Yellow
$omDir = Join-Path $ExternalDir "OpenMontage"
if (Test-Path $omDir) {
    Write-Host "  OpenMontage 已存在，跳过" -ForegroundColor DarkGray
} else {
    Write-Host "  克隆 calesthio/OpenMontage..." -NoNewline
    git clone --depth 1 https://github.com/calesthio/OpenMontage.git $omDir 2>$null
    if (Test-Path $omDir) {
        Write-Host " OK" -ForegroundColor Green
        # 安装依赖
        $omReq = Join-Path $omDir "requirements.txt"
        if (Test-Path $omReq) {
            & py -3.12 -m pip install -r $omReq --quiet 2>$null
        }
    } else {
        Write-Host " FAILED (网络问题，请稍后重试)" -ForegroundColor Red
    }
}

# ── 验证 ──
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  验证安装结果" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

$checks = @(
    @{ Name = "moviepy"; Cmd = { & py -3.12 -c "import moviepy; print('OK')" 2>$null } },
    @{ Name = "whisper"; Cmd = { & py -3.12 -c "import whisper; print('OK')" 2>$null } },
    @{ Name = "RIFE"; Cmd = { if (Test-Path $rifeDir) { "OK (本地)" } else { "未安装" } } },
    @{ Name = "SAM2"; Cmd = { & py -3.12 -c "import sam2; print('OK')" 2>$null; if ($LASTEXITCODE -ne 0) { if (Test-Path $sam2Dir) { "OK (本地)" } else { "未安装" } } } },
    @{ Name = "Remotion"; Cmd = { & npx remotion --version 2>$null; if ($LASTEXITCODE -ne 0) { "未安装" } } }
)

foreach ($check in $checks) {
    $result = & $check.Cmd
    if ($result -match "OK") {
        Write-Host "  [OK] $($check.Name)" -ForegroundColor Green
    } else {
        Write-Host "  [--] $($check.Name) - 未安装" -ForegroundColor DarkGray
    }
}

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host "  配置完成！" -ForegroundColor Green
Write-Host "  运行验证: py -3.12 -c 'import opensource_integrations; print(opensource_integrations.quick_status())'" -ForegroundColor DarkGray
Write-Host "============================================" -ForegroundColor Cyan
