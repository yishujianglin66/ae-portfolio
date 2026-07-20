# Whisper 离线/国内镜像安装脚本
# ================================
# 适用于无法翻墙的国内环境
# 使用清华/阿里云 PyPI 镜像源

param(
    [string]$Model = "base",  # tiny/base/small/medium/large
    [string]$ModelDir = "D:\AE-Work\models\whisper",
    [switch]$CpuOnly  # 无CUDA时使用CPU模式
)

$ErrorActionPreference = "Stop"

Write-Host "=== Whisper 国内镜像安装 ===" -ForegroundColor Cyan
Write-Host "模型: $Model" -ForegroundColor Yellow
Write-Host "模型目录: $ModelDir" -ForegroundColor Yellow
Write-Host ""

# 国内 PyPI 镜像
$PIP_MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
$TRUSTED_HOST = "pypi.tuna.tsinghua.edu.cn"

# 1. 安装 whisper 及依赖
Write-Host "[1/4] 安装 openai-whisper (使用清华镜像)..." -ForegroundColor Green
try {
    py -3.11 -m pip install -i $PIP_MIRROR --trusted-host $TRUSTED_HOST `
        openai-whisper torch torchaudio ffmpeg-python
    Write-Host "  安装成功" -ForegroundColor Green
} catch {
    Write-Host "  安装失败: $_" -ForegroundColor Red
    Write-Host "  请确保已安装 Python 3.11 和 pip" -ForegroundColor Yellow
    exit 1
}

# 2. 验证安装
Write-Host "[2/4] 验证安装..." -ForegroundColor Green
try {
    $whisperVersion = py -3.11 -c "import whisper; print(whisper.__version__)"
    Write-Host "  whisper 版本: $whisperVersion" -ForegroundColor Green
} catch {
    Write-Host "  验证失败: $_" -ForegroundColor Red
    exit 1
}

# 3. 预下载模型
Write-Host "[3/4] 预下载模型 ($Model)..." -ForegroundColor Green
$env:WHISPER_MODEL_DIR = $ModelDir
New-Item -ItemType Directory -Force -Path $ModelDir | Out-Null

try {
    py -3.11 -c "import whisper; whisper.load_model('$Model')"
    Write-Host "  模型下载成功" -ForegroundColor Green
} catch {
    Write-Host "  模型下载失败: $_" -ForegroundColor Red
    Write-Host "  可手动下载模型放到 $ModelDir" -ForegroundColor Yellow
}

# 4. 安装 ffmpeg (若未安装)
Write-Host "[4/4] 检查 ffmpeg..." -ForegroundColor Green
$ffmpegPath = Get-Command ffmpeg -ErrorAction SilentlyContinue
if (-not $ffmpegPath) {
    Write-Host "  ffmpeg 未安装，请安装到 C:\ffmpeg\bin\ffmpeg.exe" -ForegroundColor Yellow
    Write-Host "  下载地址: https://github.com/BtbN/FFmpeg-Builds/releases" -ForegroundColor Yellow
} else {
    Write-Host "  ffmpeg 已安装: $($ffmpegPath.Source)" -ForegroundColor Green
}

# 5. 验证完整功能
Write-Host ""
Write-Host "[验证] 测试转写功能..." -ForegroundColor Green
try {
    py -3.11 -c "
import whisper
import os
os.environ['WHISPER_MODEL_DIR'] = '$ModelDir'
model = whisper.load_model('$Model')
print('模型加载成功:', model.dims)
"
    Write-Host "  功能验证通过" -ForegroundColor Green
} catch {
    Write-Host "  验证失败: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== 安装完成 ===" -ForegroundColor Cyan
Write-Host "使用示例:" -ForegroundColor Yellow
Write-Host '  py -3.11 -c "import whisper; model = whisper.load_model(''base''); result = model.transcribe(''audio.mp3''); print(result[''text''])"'
Write-Host ""
Write-Host "模型存储位置: $ModelDir" -ForegroundColor Yellow