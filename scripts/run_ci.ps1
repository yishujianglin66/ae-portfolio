# CI Pipeline - Local Run Script
# 本地运行完整的 CI 检查流程
# 用法: .\scripts\run_ci.ps1

param(
    [string]$Stage = "all",
    [switch]$Verbose
)

$ErrorActionPreference = "Continue"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$TotalPassed = 0
$TotalFailed = 0
$TotalSkipped = 0

function Write-Step($name) {
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "  $name" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
}

function Write-Result($status, $message) {
    switch ($status) {
        "PASS" { Write-Host "[PASS] $message" -ForegroundColor Green; $script:TotalPassed++ }
        "FAIL" { Write-Host "[FAIL] $message" -ForegroundColor Red; $script:TotalFailed++ }
        "SKIP" { Write-Host "[SKIP] $message" -ForegroundColor Yellow; $script:TotalSkipped++ }
        "INFO" { Write-Host "[INFO] $message" -ForegroundColor White }
    }
}

function Test-PythonAvailable {
    try {
        $pythonVer = python --version 2>&1
        return $true
    } catch {
        return $false
    }
}

function Test-NodeAvailable {
    try {
        $nodeVer = node --version 2>&1
        return $true
    } catch {
        return $false
    }
}

# ========== Stage 1: Python Tests ==========
function Run-PythonTests {
    Write-Step "Stage 1: Python Tests"

    if (-not (Test-PythonAvailable)) {
        Write-Result "SKIP" "Python not available"
        return
    }

    $pythonVer = python --version 2>&1
    Write-Result "INFO" "Python version: $pythonVer"

    # 运行单元测试
    $testDir = Join-Path $ProjectRoot "tests"
    if (Test-Path $testDir) {
        $testFiles = Get-ChildItem $testDir -Filter "test_*.py"
        if ($testFiles.Count -gt 0) {
            Write-Result "INFO" "Found $($testFiles.Count) Python test files"

            # 检查 pytest
            $pytestAvailable = $false
            try {
                pytest --version 2>&1 | Out-Null
                $pytestAvailable = $true
            } catch {}

            if ($pytestAvailable) {
                Push-Location $ProjectRoot
                try {
                    pytest tests/ -v --tb=short 2>&1 | ForEach-Object {
                        if ($Verbose) { Write-Host "  $_" }
                    }
                    if ($LASTEXITCODE -eq 0) {
                        Write-Result "PASS" "All Python tests passed"
                    } else {
                        Write-Result "FAIL" "Python tests failed (exit code: $LASTEXITCODE)"
                    }
                } finally {
                    Pop-Location
                }
            } else {
                Write-Result "SKIP" "pytest not installed (run: pip install pytest)"
            }
        } else {
            Write-Result "SKIP" "No Python test files found"
        }
    } else {
        Write-Result "SKIP" "tests/ directory not found"
    }

    # 配置模块测试
    $configTest = Join-Path $ProjectRoot "config\config_manager.py"
    if (Test-Path $configTest) {
        Write-Result "INFO" "Testing config module import..."
        Push-Location $ProjectRoot
        try {
            python -c "from config.config_manager import get_config, get_secret; print('Config loaded OK')" 2>&1 | ForEach-Object {
                if ($Verbose) { Write-Host "  $_" }
            }
            if ($LASTEXITCODE -eq 0) {
                Write-Result "PASS" "Config module imports successfully"
            } else {
                Write-Result "FAIL" "Config module import failed"
            }
        } finally {
            Pop-Location
        }
    }

    # 签名模块测试
    $sigTest = Join-Path $ProjectRoot "config\mcp_signature.py"
    if (Test-Path $sigTest) {
        Write-Result "INFO" "Testing MCP signature module..."
        Push-Location $ProjectRoot
        try {
            python -c "
from config.mcp_signature import sign_command, verify_command, generate_secret
import json

secret = generate_secret()
cmd = {'command': 'test', 'data': 'hello world'}
signed = sign_command(cmd, secret)
valid = verify_command(signed, secret)
assert valid, 'Signature verification failed'

invalid_signed = dict(signed)
invalid_signed['command'] = 'tampered'
invalid = verify_command(invalid_signed, secret)
assert not invalid, 'Tampered command should fail verification'

print('Signature tests passed')
" 2>&1 | ForEach-Object {
                if ($Verbose) { Write-Host "  $_" }
            }
            if ($LASTEXITCODE -eq 0) {
                Write-Result "PASS" "MCP signature module works correctly"
            } else {
                Write-Result "FAIL" "MCP signature module test failed"
            }
        } finally {
            Pop-Location
        }
    }
}

# ========== Stage 2: TypeScript Compilation ==========
function Run-TypeScriptBuild {
    Write-Step "Stage 2: TypeScript Compilation"

    if (-not (Test-NodeAvailable)) {
        Write-Result "SKIP" "Node.js not available"
        return
    }

    $nodeVer = node --version 2>&1
    Write-Result "INFO" "Node.js version: $nodeVer"

    $compilerDir = Join-Path $ProjectRoot "compiler"
    if (Test-Path $compilerDir) {
        $pkgJson = Join-Path $compilerDir "package.json"
        if (Test-Path $pkgJson) {
            Write-Result "INFO" "Building compiler package..."

            $nodeModules = Join-Path $compilerDir "node_modules"
            if (-not (Test-Path $nodeModules)) {
                Write-Result "INFO" "Installing dependencies..."
                Push-Location $compilerDir
                try {
                    npm install 2>&1 | ForEach-Object {
                        if ($Verbose) { Write-Host "  $_" }
                    }
                } finally {
                    Pop-Location
                }
            }

            Push-Location $compilerDir
            try {
                npm run build 2>&1 | ForEach-Object {
                    if ($Verbose) { Write-Host "  $_" }
                }
                if ($LASTEXITCODE -eq 0) {
                    Write-Result "PASS" "TypeScript compilation succeeded"
                } else {
                    Write-Result "FAIL" "TypeScript compilation failed (exit code: $LASTEXITCODE)"
                }
            } finally {
                Pop-Location
            }
        }
    } else {
        Write-Result "SKIP" "compiler/ directory not found"
    }
}

# ========== Stage 3: JSX Syntax Check ==========
function Run-JSXCheck {
    Write-Step "Stage 3: JSX Syntax Check"

    $jsxCount = 0
    $evalIssues = @()

    Write-Result "INFO" "Scanning JSX files for security issues..."

    $skipDirs = @('.git', '__pycache__', 'node_modules', '.obsidian', '.trae', 'build')
    $allJsxFiles = Get-ChildItem $ProjectRoot -Filter "*.jsx" -Recurse | Where-Object {
        $relative = $_.FullName.Substring($ProjectRoot.Length)
        -not ($skipDirs | Where-Object { $relative -match [regex]::Escape($_) })
    }

    $jsxCount = $allJsxFiles.Count
    Write-Result "INFO" "Found $jsxCount JSX files"

    foreach ($file in $allJsxFiles) {
        try {
            $content = Get-Content $file.FullName -Raw -Encoding UTF8
            $relativePath = $file.FullName.Substring($ProjectRoot.Length + 1)

            # 检查 eval() 使用（排除安全的 JSON polyfill 和 scheduleTask）
            $evalMatches = [regex]::Matches($content, 'eval\s*\(')
            if ($evalMatches.Count -gt 0) {
                $isSafePolyfill = $content -match 'Safe JSON polyfill' -or $content -match '递归下降解析器'
                if (-not $isSafePolyfill) {
                    $scheduleTaskOnly = $true
                    foreach ($match in $evalMatches) {
                        $context = $content.Substring([Math]::Max(0, $match.Index - 50), [Math]::Min(100, $match.Index + 50 - [Math]::Max(0, $match.Index - 50)))
                        if ($context -notmatch 'scheduleTask') {
                            $scheduleTaskOnly = $false
                            break
                        }
                    }
                    if (-not $scheduleTaskOnly) {
                        $evalIssues += "$relativePath : $($evalMatches.Count) eval() call(s)"
                    }
                }
            }
        } catch {
            if ($Verbose) { Write-Result "INFO" "Error reading $($file.Name): $_" }
        }
    }

    if ($evalIssues.Count -eq 0) {
        Write-Result "PASS" "No unsafe eval() found in JSX files"
    } else {
        Write-Result "FAIL" "Found $($evalIssues.Count) JSX file(s) with unsafe eval():"
        foreach ($issue in $evalIssues) {
            Write-Host "    - $issue" -ForegroundColor Red
        }
    }
}

# ========== Stage 4: Security Scan ==========
function Run-SecurityScan {
    Write-Step "Stage 4: Security Scan"

    if (-not (Test-PythonAvailable)) {
        Write-Result "SKIP" "Python not available"
        return
    }

    Write-Result "INFO" "Scanning for hardcoded secrets and security issues..."

    Push-Location $ProjectRoot
    try {
        python -c "
import os
import re
import sys

def scan_for_secrets(root_dir):
    patterns = {
        'hardcoded_password': re.compile(r'password\s*=\s*[\"\\x27][^\"\\x27]+[\"\\x27]', re.IGNORECASE),
        'hardcoded_api_key': re.compile(r'(api_key|apikey|secret|token)\s*=\s*[\"\\x27][^\"\\x27]{10,}[\"\\x27]', re.IGNORECASE),
        'private_key': re.compile(r'-----BEGIN (RSA |EC |DSA )?PRIVATE KEY-----'),
        'aws_access_key': re.compile(r'AKIA[0-9A-Z]{16}'),
    }
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.obsidian', '.trae', 'build'}
    skip_ext = {'.md', '.txt', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.aep'}
    skip_files = {'.env.example', '.env.example'}

    issues = []
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith('.')]
        for filename in filenames:
            if filename in skip_files:
                continue
            ext = os.path.splitext(filename)[1].lower()
            if ext in skip_ext:
                continue
            filepath = os.path.join(dirpath, filename)
            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                for issue_name, pattern in patterns.items():
                    matches = pattern.findall(content)
                    if matches:
                        rel_path = os.path.relpath(filepath, root_dir)
                        # 排除 .env.example 中的示例值
                        if filename.endswith('.example'):
                            continue
                        issues.append((rel_path, issue_name, len(matches)))
            except Exception:
                pass
    return issues

issues = scan_for_secrets('.')
if issues:
    print('Security scan found potential issues:')
    for rel_path, issue_name, count in issues:
        print(f'  - {rel_path}: {count} {issue_name} match(es)')
    sys.exit(1)
else:
    print('Security scan passed: no obvious secrets found')
" 2>&1 | ForEach-Object {
            if ($Verbose -or $_ -match 'Security scan') { Write-Host "  $_" }
        }
        if ($LASTEXITCODE -eq 0) {
            Write-Result "PASS" "Security scan passed"
        } else {
            Write-Result "FAIL" "Security scan found potential issues"
        }
    } finally {
        Pop-Location
    }

    # 检查 .gitignore
    $gitignorePath = Join-Path $ProjectRoot ".gitignore"
    if (Test-Path $gitignorePath) {
        $gitignoreContent = Get-Content $gitignorePath -Raw
        if ($gitignoreContent -match 'cookies/') {
            Write-Result "PASS" ".gitignore includes cookies/ directory"
        } else {
            Write-Result "FAIL" ".gitignore missing cookies/ directory"
        }
        if ($gitignoreContent -match '\.env') {
            Write-Result "PASS" ".gitignore includes .env files"
        } else {
            Write-Result "FAIL" ".gitignore missing .env files"
        }
    } else {
        Write-Result "SKIP" ".gitignore not found"
    }
}

# ========== Main ==========
Write-Host ""
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "  AE-Knowledge-Vault CI Pipeline" -ForegroundColor Magenta
Write-Host "========================================" -ForegroundColor Magenta
Write-Host "Project: $ProjectRoot"
Write-Host "Stage: $Stage"

switch ($Stage) {
    "all" {
        Run-PythonTests
        Run-TypeScriptBuild
        Run-JSXCheck
        Run-SecurityScan
    }
    "python" { Run-PythonTests }
    "typescript" { Run-TypeScriptBuild }
    "jsx" { Run-JSXCheck }
    "security" { Run-SecurityScan }
    default {
        Write-Host "Unknown stage: $Stage" -ForegroundColor Red
        Write-Host "Valid stages: all, python, typescript, jsx, security"
        exit 1
    }
}

# ========== Summary ==========
Write-Step "Summary"
Write-Host "  Passed:  $TotalPassed" -ForegroundColor Green
Write-Host "  Failed:  $TotalFailed" -ForegroundColor Red
Write-Host "  Skipped: $TotalSkipped" -ForegroundColor Yellow
Write-Host ""

if ($TotalFailed -gt 0) {
    Write-Host "CI Pipeline FAILED" -ForegroundColor Red
    exit 1
} else {
    Write-Host "CI Pipeline PASSED" -ForegroundColor Green
    exit 0
}
