# ============================================================
#  Enterprise ISO Compliance Platform - PowerShell Launcher
#  Usage : .\start.ps1
#          .\start.ps1 -SkipMigrate
#          .\start.ps1 -BackendOnly
#          .\start.ps1 -FrontendOnly
# ============================================================
param(
    [switch]$SkipMigrate,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$BackendPort  = 8000,
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Continue"
$Root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Python   = Join-Path $Backend ".venv\Scripts\python.exe"
$Pip      = Join-Path $Backend ".venv\Scripts\pip.exe"

function Write-Step { param($n, $msg) Write-Host "[$n] $msg" -ForegroundColor Cyan }
function Write-OK   { param($msg)     Write-Host "    [OK] $msg" -ForegroundColor Green }
function Write-Warn { param($msg)     Write-Host "    [!]  $msg" -ForegroundColor Yellow }
function Write-Fail { param($msg)     Write-Host "    [ERR] $msg" -ForegroundColor Red }

Clear-Host
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Magenta
Write-Host "   Enterprise ISO Compliance Platform - Launcher  " -ForegroundColor Magenta
Write-Host "   Backend: Django 5  |  Frontend: React 19       " -ForegroundColor Magenta
Write-Host "   AI: Ollama - FAISS - SentenceTransformers      " -ForegroundColor Magenta
Write-Host "  ================================================" -ForegroundColor Magenta
Write-Host ""

# ── Step 1 : Python venv ──────────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Step "1/5" "Checking Python environment..."

    if (-not (Test-Path $Python)) {
        Write-Warn "Venv not found - creating..."
        & python -m venv "$Backend\.venv"
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "Cannot create venv. Is Python installed?"
            pause
            exit 1
        }
        Write-Warn "Installing Python dependencies..."
        & $Pip install -r "$Backend\requirements.txt" --quiet
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "pip install failed."
            pause
            exit 1
        }
        Write-OK "Dependencies installed."
    } else {
        Write-OK "Python venv ready."
    }

    # ── Step 2 : Django migrate ───────────────────────────────────────────
    if (-not $SkipMigrate) {
        Write-Step "2/5" "Running database migrations..."
        Push-Location $Backend
        try {
            & $Python manage.py migrate --run-syncdb 2>&1 | Where-Object { $_ -match "Applying|Error" } | ForEach-Object { Write-Host "    $_" }
            Write-OK "Database synchronized."
        } catch {
            Write-Warn "migrate returned an error (non-blocking): $_"
        } finally {
            Pop-Location
        }
    } else {
        Write-Step "2/5" "Skipping migrations (SkipMigrate flag set)."
    }
} else {
    Write-Step "1/5" "Backend skipped (FrontendOnly)."
    Write-Step "2/5" "Migrations skipped (FrontendOnly)."
}

# ── Step 3 : Node modules ─────────────────────────────────────────────────
if (-not $BackendOnly) {
    Write-Step "3/5" "Checking Node.js dependencies..."
    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Warn "node_modules not found - running npm install..."
        Push-Location $Frontend
        & npm install --silent
        Pop-Location
        if ($LASTEXITCODE -ne 0) {
            Write-Fail "npm install failed."
            pause
            exit 1
        }
        Write-OK "Node dependencies installed."
    } else {
        Write-OK "Node modules ready."
    }
} else {
    Write-Step "3/5" "Frontend skipped (BackendOnly)."
}

# ── Step 4 : Start Backend ────────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Step "4/5" "Starting Django backend on port $BackendPort..."
    $backendCmd = "Set-Location '$Backend'; & '$Python' manage.py runserver 0.0.0.0:$BackendPort"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd -WindowStyle Normal
    Start-Sleep -Seconds 2
    Write-OK "Backend started -> http://localhost:$BackendPort"
}

# ── Step 5 : Start Frontend ───────────────────────────────────────────────
if (-not $BackendOnly) {
    Write-Step "5/5" "Starting React frontend on port $FrontendPort..."
    $frontendCmd = "Set-Location '$Frontend'; `$env:PORT='$FrontendPort'; `$env:BROWSER='none'; npm start"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd -WindowStyle Normal
    Start-Sleep -Seconds 3
    Write-OK "Frontend started -> http://localhost:$FrontendPort"
}

# ── Summary ───────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Magenta
Write-Host "   Platform is starting up...                     " -ForegroundColor Magenta
Write-Host "                                                  " -ForegroundColor Magenta
Write-Host "   Frontend   ->  http://localhost:$FrontendPort              " -ForegroundColor White
Write-Host "   Backend    ->  http://localhost:$BackendPort              " -ForegroundColor White
Write-Host "   Admin      ->  http://localhost:$BackendPort/admin        " -ForegroundColor White
Write-Host "   API        ->  http://localhost:$BackendPort/api/         " -ForegroundColor White
Write-Host "   AI Insights->  http://localhost:$FrontendPort/#/ai-insights" -ForegroundColor Cyan
Write-Host "                                                  " -ForegroundColor Magenta
Write-Host "   Close the PowerShell windows to stop.         " -ForegroundColor DarkGray
Write-Host "  ================================================" -ForegroundColor Magenta
Write-Host ""

Write-Host "  Opening browser in 5 seconds..." -ForegroundColor DarkGray
Start-Sleep -Seconds 5
Start-Process "http://localhost:$FrontendPort"
exit 0
