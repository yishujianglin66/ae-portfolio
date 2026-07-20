# ============================================================
# AE-Knowledge-Vault Deployment Script
# Modes: local / docker / build / stop
# ============================================================

param(
    [Parameter(Position=0)]
    [string]$Mode = "local",

    [string]$Port = "8000",
    [string]$SecretKey = ""
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step($msg) {
    Write-Host "`n[*] $msg" -ForegroundColor Cyan
}

function Write-OK($msg) {
    Write-Host "    [OK] $msg" -ForegroundColor Green
}

function Write-Err($msg) {
    Write-Host "    [FAIL] $msg" -ForegroundColor Red
}

function Test-Command($cmd) {
    return [bool](Get-Command $cmd -ErrorAction SilentlyContinue)
}

# ============================================================
# Pre-check
# ============================================================
Write-Step "Environment Check"

if (Test-Command "py") {
    $pyVer = py -3.11 --version 2>&1
    Write-OK "Python: $pyVer"
} else {
    Write-Err "Python 3.11 not found (py launcher)"
    exit 1
}

if (Test-Command "node") {
    $nodeVer = node --version 2>&1
    Write-OK "Node.js: $nodeVer"
} else {
    Write-Err "Node.js not found"
    exit 1
}

# ============================================================
# Mode: local (dev)
# ============================================================
if ($Mode -eq "local") {
    Write-Step "Local Development Mode"

    # Check backend deps
    Write-Step "Checking Python dependencies"
    $deps = @("fastapi", "uvicorn", "pydantic", "psutil")
    foreach ($d in $deps) {
        $check = py -3.11 -c "import $d; print('ok')" 2>&1
        if ($check -ne "ok") {
            Write-Host "    Installing $d..."
            py -3.11 -m pip install $d -q
        }
    }
    Write-OK "Python dependencies ready"

    # Check frontend
    Write-Step "Checking frontend"
    $dashboardDir = Join-Path $ProjectRoot "ae-dashboard"
    if (-not (Test-Path (Join-Path $dashboardDir "node_modules"))) {
        Write-Host "    Installing frontend dependencies..."
        Push-Location $dashboardDir
        npm install
        Pop-Location
    }
    Write-OK "Frontend dependencies ready"

    # Start backend
    Write-Step "Starting backend API (port $Port)"
    $env:AEK_ENVIRONMENT = "development"
    $env:API_PORT = $Port
    if ($SecretKey) { $env:AE_VAULT_SECRET_KEY = $SecretKey }

    Start-Process -FilePath "py" -ArgumentList "-3.11", "api_server.py" -WorkingDirectory $ProjectRoot -NoNewWindow

    Start-Sleep -Seconds 3

    # Verify backend
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 5
        Write-OK "Backend health: $($health.status)"
    } catch {
        Write-Err "Backend startup failed"
        exit 1
    }

    # Start frontend dev server
    Write-Step "Starting frontend Dev Server (port 5173)"
    Start-Process -FilePath "npm" -ArgumentList "run", "dev" -WorkingDirectory $dashboardDir -NoNewWindow

    Start-Sleep -Seconds 2
    Write-OK "Frontend Dev Server started"

    Write-Host "`n========================================" -ForegroundColor Yellow
    Write-Host "  Local Dev Mode Started" -ForegroundColor Yellow
    Write-Host "  Backend API:  http://127.0.0.1:$Port" -ForegroundColor White
    Write-Host "  Frontend UI:  http://localhost:5173" -ForegroundColor White
    Write-Host "  Credentials:  admin / admin123" -ForegroundColor White
    Write-Host "========================================`n" -ForegroundColor Yellow
}

# ============================================================
# Mode: docker
# ============================================================
elseif ($Mode -eq "docker") {
    Write-Step "Docker Deployment Mode"

    if (-not (Test-Command "docker")) {
        Write-Err "Docker not found"
        exit 1
    }

    $dockerVer = docker --version 2>&1
    Write-OK "Docker: $dockerVer"

    # Build frontend
    Write-Step "Building frontend"
    Push-Location (Join-Path $ProjectRoot "ae-dashboard")
    npm run build
    Pop-Location
    Write-OK "Frontend build complete"

    # Set env
    if ($SecretKey) {
        $env:AE_VAULT_SECRET_KEY = $SecretKey
    }
    $env:EXPOSE_PORT = $Port

    # Docker Compose
    Write-Step "Starting Docker Compose"
    docker compose up -d --build

    Start-Sleep -Seconds 5

    # Verify
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 10
        Write-OK "Service health: $($health.status)"
    } catch {
        Write-Host "    Waiting for service..."
        Start-Sleep -Seconds 10
        try {
            $health = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health" -TimeoutSec 10
            Write-OK "Service health: $($health.status)"
        } catch {
            Write-Err "Service startup failed. Check: docker compose logs"
            exit 1
        }
    }

    Write-Host "`n========================================" -ForegroundColor Yellow
    Write-Host "  Docker Deployment Complete" -ForegroundColor Yellow
    Write-Host "  URL:          http://localhost:$Port" -ForegroundColor White
    Write-Host "  Credentials:  admin / admin123" -ForegroundColor White
    Write-Host "========================================`n" -ForegroundColor Yellow
}

# ============================================================
# Mode: build
# ============================================================
elseif ($Mode -eq "build") {
    Write-Step "Build Mode"

    # Build frontend
    Write-Step "Building frontend"
    Push-Location (Join-Path $ProjectRoot "ae-dashboard")
    npm run build
    Pop-Location

    $distPath = Join-Path $ProjectRoot "ae-dashboard\dist\index.html"
    if (Test-Path $distPath) {
        Write-OK "Frontend build success"
    } else {
        Write-Err "Frontend build failed"
        exit 1
    }

    # Test backend modules
    Write-Step "Testing backend modules"
    $modules = @("auth_system.py", "distributed_scheduler.py", "monitoring.py")
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    foreach ($mod in $modules) {
        $modPath = Join-Path $ProjectRoot $mod
        cmd /c "py -3.11 `"$modPath`" >nul 2>&1"
        $code = $LASTEXITCODE
        if ($code -eq 0) {
            Write-OK "$mod test passed"
        } else {
            Write-Err "$mod test failed (exit $code)"
            $ErrorActionPreference = $prevEAP
            exit 1
        }
    }

    # Verify config module
    Write-Step "Verifying config module"
    $cfgOut = cmd /c "py -3.11 -c `"from config import settings; print(settings.summary())`" 2>nul"
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Config module: $cfgOut"
    } else {
        Write-Err "Config module failed"
        $ErrorActionPreference = $prevEAP
        exit 1
    }
    $ErrorActionPreference = $prevEAP

    Write-Host "`n========================================" -ForegroundColor Yellow
    Write-Host "  Build Complete" -ForegroundColor Yellow
    Write-Host "  Frontend:  ae-dashboard/dist/" -ForegroundColor White
    Write-Host "  Backend:   all module tests passed" -ForegroundColor White
    Write-Host "========================================`n" -ForegroundColor Yellow
}

# ============================================================
# Mode: stop
# ============================================================
elseif ($Mode -eq "stop") {
    Write-Step "Stopping services"

    # Stop local processes
    $procs = Get-Process -Name "python" -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | Stop-Process -Force -ErrorAction SilentlyContinue
        Write-OK "Stopped Python processes"
    }

    # Stop Docker
    if (Test-Command "docker") {
        docker compose down 2>$null
        Write-OK "Stopped Docker services"
    }

    Write-OK "All services stopped"
}

else {
    Write-Host "Usage: .\deploy.ps1 [local|docker|build|stop] [-Port 8000] [-SecretKey xxx]" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  local   - Dev mode (backend + frontend dev server)" -ForegroundColor White
    Write-Host "  docker  - Docker Compose deployment" -ForegroundColor White
    Write-Host "  build   - Build frontend + test backend modules" -ForegroundColor White
    Write-Host "  stop    - Stop all services" -ForegroundColor White
}
