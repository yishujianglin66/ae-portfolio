# ============================================================================
# install.ps1 - Phase 2 & 3 MCP Extension Deployment
# Deploys 25 new MCP tools to after-effects-mcp-main project
#
# Usage:
#   cd c:\Users\Administrator\Desktop\AE-Knowledge-Vault\mcp-extension
#   .\install.ps1
#
# Parameters:
#   -Force   Skip backup confirmation
#   -DryRun  Show operations without executing
# ============================================================================

param(
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

# ============================================================================
# Path configuration
# ============================================================================
$extensionDir = "c:\Users\Administrator\Desktop\AE-Knowledge-Vault\mcp-extension"
$scriptsSourceDir = Join-Path $extensionDir "scripts"
$mcpProjectDir = "c:\Users\Administrator\Desktop\after-effects-mcp-main"
$scriptsTargetDir = Join-Path $mcpProjectDir "src\scripts"
$indexTsPath = Join-Path $mcpProjectDir "src\index.ts"
$backupPath = Join-Path $mcpProjectDir "src\index.ts.backup-phase2"
$inlineToolsPath = Join-Path $extensionDir "new-tools-inline.ts"

# 25 new JSX scripts (16 Phase 2 + 9 Phase 3)
$newScripts = @(
    "addEffectWithKeyframes.jsx",
    "setKeyframeEasing.jsx",
    "batchAddEffects.jsx",
    "setBlendMode.jsx",
    "setTrackMatte.jsx",
    "setParentLayer.jsx",
    "addAdjustmentLayer.jsx",
    "addPrecomp.jsx",
    "importFootage.jsx",
    "setMotionBlur.jsx",
    "addMaskWithShape.jsx",
    "executeAtomScript.jsx",
    "getEffectProperties.jsx",
    "setEffectKeyframes.jsx",
    "applyNewtonDynamics.jsx",
    "createE2EMusicVideo.jsx",
    "addTextLayer.jsx",
    "addShapeLayer.jsx",
    "addCamera.jsx",
    "addLight.jsx",
    "applyLUT.jsx",
    "enableTimeRemap.jsx",
    "applySaber.jsx",
    "applyParticular.jsx",
    "applyOpticalFlares.jsx"
)

# 25 new allowedScripts entries (16 Phase 2 + 9 Phase 3)
$newAllowedScriptsEntries = @(
    '      "addEffectWithKeyframes",'
    '      "setKeyframeEasing",'
    '      "batchAddEffects",'
    '      "setBlendMode",'
    '      "setTrackMatte",'
    '      "setParentLayer",'
    '      "addAdjustmentLayer",'
    '      "addPrecomp",'
    '      "importFootage",'
    '      "setMotionBlur",'
    '      "addMaskWithShape",'
    '      "executeAtomScript",'
    '      "getEffectProperties",'
    '      "setEffectKeyframes",'
    '      "applyNewtonDynamics",'
    '      "createE2EMusicVideo",'
    '      "addTextLayer",'
    '      "addShapeLayer",'
    '      "addCamera",'
    '      "addLight",'
    '      "applyLUT",'
    '      "enableTimeRemap",'
    '      "applySaber",'
    '      "applyParticular",'
    '      "applyOpticalFlares"'
)

# ============================================================================
# Helper functions
# ============================================================================
function Write-Step($step, $message) {
    Write-Host ""
    Write-Host "[$step] $message" -ForegroundColor Cyan
}

function Write-OK($message) {
    Write-Host "  [OK] $message" -ForegroundColor Green
}

function Write-Warn2($message) {
    Write-Host "  [!]  $message" -ForegroundColor Yellow
}

function Write-Err2($message) {
    Write-Host "  [X]  $message" -ForegroundColor Red
}

# ============================================================================
# Deployment start
# ============================================================================
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " Phase 2 & 3 MCP Extension Deployment" -ForegroundColor Cyan
Write-Host " Add 25 new MCP tools to after-effects-mcp-main" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

if ($DryRun) {
    Write-Warn2 "DRY RUN mode: operations shown, not executed"
}

# ============================================================================
# Step 1: Verify paths
# ============================================================================
Write-Step "1/6" "Verifying paths"

if (-not (Test-Path $mcpProjectDir)) {
    Write-Err2 "MCP project not found: $mcpProjectDir"
    exit 1
}
Write-OK "MCP project directory exists"

if (-not (Test-Path $scriptsTargetDir)) {
    Write-Err2 "scripts directory not found: $scriptsTargetDir"
    exit 1
}
Write-OK "scripts directory exists"

if (-not (Test-Path $indexTsPath)) {
    Write-Err2 "index.ts not found: $indexTsPath"
    exit 1
}
Write-OK "index.ts exists"

if (-not (Test-Path $scriptsSourceDir)) {
    Write-Err2 "Extension scripts source not found: $scriptsSourceDir"
    exit 1
}
Write-OK "Extension source directory exists"

if (-not (Test-Path $inlineToolsPath)) {
    Write-Err2 "new-tools-inline.ts not found: $inlineToolsPath"
    exit 1
}
Write-OK "new-tools-inline.ts exists"

# ============================================================================
# Step 2: Backup index.ts
# ============================================================================
Write-Step "2/6" "Backing up index.ts"

if (-not $Force -and (Test-Path $backupPath)) {
    $overwrite = Read-Host "Backup file exists. Overwrite? (y/N)"
    if ($overwrite -ne "y") {
        Write-Host "Deployment cancelled"
        exit 0
    }
}

if (-not $DryRun) {
    Copy-Item $indexTsPath $backupPath -Force
    Write-OK "Backed up to: $backupPath"
} else {
    Write-Warn2 "[DRY RUN] Would backup to: $backupPath"
}

# ============================================================================
# Step 3: Copy 25 JSX scripts
# ============================================================================
Write-Step "3/6" "Copying 25 new JSX scripts"

$copiedCount = 0
foreach ($script in $newScripts) {
    $srcPath = Join-Path $scriptsSourceDir $script
    $dstPath = Join-Path $scriptsTargetDir $script

    if (-not (Test-Path $srcPath)) {
        Write-Err2 "Source script not found: $srcPath"
        continue
    }

    if (-not $DryRun) {
        Copy-Item $srcPath $dstPath -Force
        $copiedCount++
        Write-OK "Copied: $script"
    } else {
        Write-Warn2 "[DRY RUN] Would copy: $script"
    }
}

if (-not $DryRun) {
    Write-Host "  Total copied: $copiedCount scripts" -ForegroundColor Green
}

# ============================================================================
# Step 4: Modify index.ts - Append allowedScripts entries
# ============================================================================
Write-Step "4/6" "Modifying index.ts - Appending allowedScripts entries"

$indexContent = Get-Content $indexTsPath -Raw -Encoding UTF8

# Check if already deployed
if ($indexContent -match "addEffectWithKeyframes") {
    Write-Warn2 "index.ts already contains Phase 2 entries, skipping allowedScripts modification"
} else {
    # Insert after "fixParticular" entry
    $fixParticularPattern = '("fixParticular")(\s*\r?\n\s*\];)'

    if ($indexContent -match $fixParticularPattern) {
        $newEntries = ($newAllowedScriptsEntries -join "`r`n")
        $replacement = '$1,' + "`r`n" + $newEntries + '$2'

        if (-not $DryRun) {
            $indexContent = $indexContent -replace $fixParticularPattern, $replacement
            Write-OK "Appended 25 entries to allowedScripts array"
        } else {
            Write-Warn2 "[DRY RUN] Would append 25 entries to allowedScripts array"
        }
    } else {
        Write-Err2 "Could not find 'fixParticular' marker in index.ts"
        Write-Host "  Please manually add these entries to allowedScripts array:" -ForegroundColor Yellow
        $newAllowedScriptsEntries | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    }
}

# ============================================================================
# Step 5: Modify index.ts - Append 25 tool registrations
# ============================================================================
Write-Step "5/6" "Modifying index.ts - Appending 25 tool registrations"

# Check if tools already added
if ($indexContent -match 'execute-atom-script') {
    Write-Warn2 "index.ts already contains tool registrations, skipping"
} else {
    $inlineContent = Get-Content $inlineToolsPath -Raw -Encoding UTF8

    # Remove leading comment lines (lines starting with //)
    $lines = $inlineContent -split "`r?`n"
    $filteredLines = @()
    $inCommentBlock = $false
    foreach ($line in $lines) {
        # Skip comment block markers
        if ($line -match '^\s*// ===') { continue }
        if ($line -match '^\s*//\s') { continue }
        $filteredLines += $line
    }
    $inlineContent = ($filteredLines -join "`r`n").TrimStart()

    # Build insertion block
    $timestamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    $insertBlock = "// ============================================================================`r`n"
    $insertBlock += "// Phase 2 & 3 Extension - 25 new MCP tool registrations`r`n"
    $insertBlock += "// Deployed: $timestamp`r`n"
    $insertBlock += "// ============================================================================`r`n`r`n"
    $insertBlock += $inlineContent
    $insertBlock += "`r`n"

    if (-not $DryRun) {
        # Append to end of file
        $indexContent = $indexContent.TrimEnd() + "`r`n`r`n" + $insertBlock
        Write-OK "Appended 25 tool registrations to end of index.ts"
    } else {
        Write-Warn2 "[DRY RUN] Would append 25 tool registrations to end of index.ts"
    }
}

# Save modified index.ts
if (-not $DryRun) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($indexTsPath, $indexContent, $utf8NoBom)
    Write-OK "index.ts saved"
}

# ============================================================================
# Step 6: Run npm run build to verify compilation
# ============================================================================
Write-Step "6/6" "Running npm run build to verify compilation"

if ($DryRun) {
    Write-Warn2 "[DRY RUN] Skipping build step"
} else {
    Push-Location $mcpProjectDir
    try {
        Write-Host "  Running: npm run build" -ForegroundColor Gray
        $buildOutput = & npm run build 2>&1

        $buildSuccess = $LASTEXITCODE -eq 0

        if ($buildSuccess) {
            Write-OK "TypeScript compilation successful"
            Write-Host "  Build output:" -ForegroundColor Gray
            $buildOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray }
        } else {
            Write-Err2 "TypeScript compilation failed"
            Write-Host "  Error output:" -ForegroundColor Red
            $buildOutput | ForEach-Object { Write-Host "    $_" -ForegroundColor Red }
            Write-Host ""
            Write-Host "Backup of original index.ts: $backupPath" -ForegroundColor Yellow
            Write-Host "Restore with:" -ForegroundColor Yellow
            Write-Host "  Copy-Item `"$backupPath`" `"$indexTsPath`" -Force" -ForegroundColor Yellow
            Pop-Location
            exit 1
        }
    } catch {
        Write-Err2 "Build exception: $_"
        Pop-Location
        exit 1
    }
    Pop-Location
}

# ============================================================================
# Deployment report
# ============================================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host " Phase 2 & 3 Deployment Complete" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Completed operations:" -ForegroundColor White
Write-Host "  1. Backed up index.ts to backup-phase2" -ForegroundColor White
Write-Host "  2. Copied $($newScripts.Count) JSX scripts to src/scripts/" -ForegroundColor White
Write-Host "  3. Appended 25 entries to allowedScripts array" -ForegroundColor White
Write-Host "  4. Appended 25 tool registrations to index.ts" -ForegroundColor White
if (-not $DryRun) {
    Write-Host "  5. npm run build succeeded" -ForegroundColor White
}
Write-Host ""
Write-Host "25 new MCP tools:" -ForegroundColor White
$toolNames = @(
    "add-effect-with-keyframes",
    "set-keyframe-easing",
    "batch-add-effects",
    "set-blend-mode",
    "set-track-matte",
    "set-parent-layer",
    "add-adjustment-layer",
    "add-precomp",
    "import-footage",
    "set-motion-blur",
    "add-mask-with-shape",
    "execute-atom-script",
    "get-effect-properties",
    "set-effect-keyframes",
    "apply-newton-dynamics",
    "create-e2e-music-video",
    "add-text-layer",
    "add-shape-layer",
    "add-camera",
    "add-light",
    "apply-lut",
    "enable-time-remap",
    "apply-saber",
    "apply-particular",
    "apply-optical-flares"
)
$toolNames | ForEach-Object { Write-Host "  - $_" -ForegroundColor White }
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "  1. Restart MCP Server (in Claude Desktop / Cursor config)" -ForegroundColor Cyan
Write-Host "  2. Open MCP Bridge Auto panel in After Effects" -ForegroundColor Cyan
Write-Host "  3. Test new tools (e.g., add-effect-with-keyframes)" -ForegroundColor Cyan
Write-Host ""
Write-Host "To rollback:" -ForegroundColor Yellow
Write-Host "  Copy-Item `"$backupPath`" `"$indexTsPath`" -Force" -ForegroundColor Yellow
Write-Host "  Then run: npm run build" -ForegroundColor Yellow
Write-Host ""
