# deploy_e2e_tool.ps1
# 一键部署 create-e2e-music-video MCP工具到 after-effects-mcp-main
# 用法：在PowerShell中运行 .\deploy_e2e_tool.ps1

$ErrorActionPreference = "Stop"

$MCP_DIR = "c:\Users\Administrator\Desktop\after-effects-mcp-main"
$SRC_FILE = "$MCP_DIR\src\index.ts"
$SCRIPTS_DIR = "$MCP_DIR\src\scripts"
$VAULT_SCRIPT = "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\mcp-extension\scripts\createE2EMusicVideo.jsx"

Write-Host "=== E2E Music Video MCP Tool Deployment ===" -ForegroundColor Cyan

# Step 1: Copy JSX script
Write-Host "[1/4] Copying JSX script..." -ForegroundColor Yellow
if (Test-Path $VAULT_SCRIPT) {
    Copy-Item $VAULT_SCRIPT "$SCRIPTS_DIR\createE2EMusicVideo.jsx" -Force
    Write-Host "  OK: createE2EMusicVideo.jsx copied" -ForegroundColor Green
} else {
    Write-Host "  ERROR: Source script not found: $VAULT_SCRIPT" -ForegroundColor Red
    exit 1
}

# Step 2: Add to allowedScripts
Write-Host "[2/4] Adding to allowedScripts..." -ForegroundColor Yellow
$content = Get-Content $SRC_FILE -Raw -Encoding UTF8
if ($content -match '"createE2EMusicVideo"') {
    Write-Host "  SKIP: createE2EMusicVideo already in allowedScripts" -ForegroundColor DarkYellow
} else {
    $content = $content -replace '"setEffectKeyframes"\s*\n\s*\]', "`"setEffectKeyframes`",`n      `"createE2EMusicVideo`"`n    ]"
    Write-Host "  OK: createE2EMusicVideo added to allowedScripts" -ForegroundColor Green
}

# Step 3: Register new tool before main()
Write-Host "[3/4] Registering create-e2e-music-video tool..." -ForegroundColor Yellow
$toolCode = @'

// ============================================================================
// E2E Music Video Tool - One-click full composition creation
// ============================================================================

server.tool(
  "create-e2e-music-video",
  "一键创建完整音乐视频合成。包含帧序列导入、主体/披风层处理、粒子系统、背景大气、调色、摄像机节拍同步、BGM导入等全部步骤。使用AE内置效果(ADBE Color Key/ADBE Glo2/ADBE Ramp)确保兼容性。需要先在AE中运行mcp-bridge-auto.jsx监听",
  {
    compName: z.string().optional().default("E2E_音乐视频").describe("合成名称"),
    frameDir: z.string().optional().default("D:/AE-Work/视频素材库/frames").describe("帧序列目录"),
    bgmPath: z.string().optional().describe("背景音乐文件路径"),
    beatTimes: z.array(z.number()).optional().describe("节拍时间点数组（秒）"),
    energyPeaks: z.array(z.number()).optional().describe("能量峰值时间点数组（秒）"),
    peakValues: z.array(z.number()).optional().describe("能量峰值强度数组"),
    bpm: z.number().optional().default(0).describe("音乐BPM"),
    width: z.number().int().positive().optional().default(576).describe("合成宽度"),
    height: z.number().int().positive().optional().default(768).describe("合成高度"),
    duration: z.number().positive().optional().default(12).describe("合成时长（秒）"),
    fps: z.number().int().positive().optional().default(30).describe("帧率")
  },
  async ({ compName, frameDir, bgmPath, beatTimes, energyPeaks, peakValues, bpm, width, height, duration, fps }) => {
    try {
      clearResultsFile();
      writeCommandFile("createE2EMusicVideo", {
        compName: compName || "E2E_音乐视频",
        frameDir: frameDir || "D:/AE-Work/视频素材库/frames",
        bgmPath: bgmPath || "",
        beatTimes: beatTimes || [],
        energyPeaks: energyPeaks || [],
        peakValues: peakValues || [],
        bpm: bpm || 0,
        width: width || 576,
        height: height || 768,
        duration: duration || 12,
        fps: fps || 30
      });
      const result = await waitForBridgeResult("createE2EMusicVideo", 30000, 250);
      return { content: [{ type: "text", text: result }] };
    } catch (e) {
      return { content: [{ type: "text", text: `Error: ${String(e)}` }], isError: true };
    }
  }
);

'@

if ($content -match 'create-e2e-music-video') {
    Write-Host "  SKIP: Tool already registered" -ForegroundColor DarkYellow
} else {
    $insertPoint = "async function main() {"
    $content = $content -replace [regex]::Escape($insertPoint), "$toolCode`n$insertPoint"
    Write-Host "  OK: create-e2e-music-video tool registered" -ForegroundColor Green
}

Set-Content $SRC_FILE -Value $content -Encoding UTF8 -NoNewline

# Step 4: Build
Write-Host "[4/4] Building..." -ForegroundColor Yellow
Push-Location $MCP_DIR
try {
    & npm run build 2>&1 | Write-Host
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: Build successful" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Build exited with code $LASTEXITCODE" -ForegroundColor DarkYellow
    }
} finally {
    Pop-Location
}

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tool: create-e2e-music-video" -ForegroundColor White
Write-Host "Usage: In Trae chat, call create-e2e-music-video with optional parameters" -ForegroundColor White
Write-Host ""
Write-Host "Prerequisites:" -ForegroundColor Yellow
Write-Host "  1. Run mcp-bridge-auto.jsx in AE 2026" -ForegroundColor White
Write-Host "  2. Restart Trae MCP server (or reload window)" -ForegroundColor White
Write-Host "  3. Frame directory exists: D:/AE-Work/视频素材库/frames" -ForegroundColor White
