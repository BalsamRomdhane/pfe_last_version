# ============================================================
#  Enterprise ISO Compliance Platform — PowerShell Launcher
#  Usage : .\start.ps1
#          .\start.ps1 -SkipMigrate
#          .\start.ps1 -BackendOnly
#          .\start.ps1 -FrontendOnly
# ============================================================
param(
    [switch]$SkipMigrate,
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$BackendPort   = 8000,
    [int]$FrontendPort  = 3000
)

$ErrorActionPreference = "Stop"
$Root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend  = Join-Path $Root "backend"
$Frontend = Join-Path $Root "frontend"
$Venv     = Join-Path $Backend ".venv\Scripts"
$Python   = Join-Path $Venv "python.exe"
$Pip      = Join-Path $Venv "pip.exe"

# ── Couleurs ──────────────────────────────────────────────────────────────
function Write-Step  { param($n, $msg) Write-Host "[$n] " -NoNewline -ForegroundColor Cyan;  Write-Host $msg }
function Write-OK    { param($msg)     Write-Host "    [OK] " -NoNewline -ForegroundColor Green;  Write-Host $msg }
function Write-Warn  { param($msg)     Write-Host "    [!]  " -NoNewline -ForegroundColor Yellow; Write-Host $msg }
function Write-Fail  { param($msg)     Write-Host "    [ERR] " -NoNewline -ForegroundColor Red;   Write-Host $msg }
function Write-Box   { param($lines)
    $w = ($lines | Measure-Object -Maximum -Property Length).Maximum + 4
    $bar = "═" * $w
    Write-Host "  ╔$bar╗" -ForegroundColor Magenta
    foreach ($l in $lines) {
        $pad = " " * ($w - $l.Length - 2)
        Write-Host "  ║  $l$pad  ║" -ForegroundColor Magenta
    }
    Write-Host "  ╚$bar╝" -ForegroundColor Magenta
}

Clear-Host
Write-Box @(
    "Enterprise ISO Compliance Platform",
    "Backend: Django 5  |  Frontend: React 19",
    "AI: Ollama · FAISS · SentenceTransformers"
)
Write-Host ""

# ── Étape 1 : Python venv ─────────────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Step "1/5" "Vérification de l'environnement Python..."

    if (-not (Test-Path $Python)) {
        Write-Warn "Venv absent — création..."
        & python -m venv "$Backend\.venv"
        if ($LASTEXITCODE -ne 0) { Write-Fail "Impossible de créer le venv. Python installé ?"; exit 1 }

        Write-Warn "Installation des dépendances Python..."
        & $Pip install -r "$Backend\requirements.txt" --quiet
        if ($LASTEXITCODE -ne 0) { Write-Fail "pip install a échoué."; exit 1 }
        Write-OK "Dépendances installées."
    } else {
        Write-OK "Venv Python prêt  ($Python)"
    }

    # ── Étape 2 : Django migrate ──────────────────────────────────────────
    if (-not $SkipMigrate) {
        Write-Step "2/5" "Migration de la base de données..."
        Push-Location $Backend
        try {
            & $Python manage.py migrate --run-syncdb 2>&1 | Where-Object { $_ -match "Applying|Error" } | ForEach-Object { Write-Host "    $_" }
            Write-OK "Base de données synchronisée."
        } catch {
            Write-Warn "migrate a retourné une erreur (non bloquant): $_"
        } finally {
            Pop-Location
        }
    } else {
        Write-Step "2/5" "Migration ignorée (--SkipMigrate)."
    }
}

# ── Étape 3 : Node modules ────────────────────────────────────────────────
if (-not $BackendOnly) {
    Write-Step "3/5" "Vérification des dépendances Node.js..."
    if (-not (Test-Path (Join-Path $Frontend "node_modules"))) {
        Write-Warn "node_modules absent — npm install en cours..."
        Push-Location $Frontend
        & npm install --silent
        Pop-Location
        if ($LASTEXITCODE -ne 0) { Write-Fail "npm install a échoué."; exit 1 }
        Write-OK "Dépendances Node installées."
    } else {
        Write-OK "Node modules prêts."
    }
}

# ── Étape 4 : Démarrage Backend ───────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Step "4/5" "Démarrage du backend Django sur le port $BackendPort..."
    $backendCmd = "chcp 65001 > nul 2>&1; Set-Location '$Backend'; & '$Python' manage.py runserver 0.0.0.0:$BackendPort"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $backendCmd `
        -WindowStyle Normal
    Start-Sleep -Seconds 2
    Write-OK "Backend lancé  → http://localhost:$BackendPort"
}

# ── Étape 5 : Démarrage Frontend ──────────────────────────────────────────
if (-not $BackendOnly) {
    Write-Step "5/5" "Démarrage du frontend React sur le port $FrontendPort..."
    $env:PORT           = $FrontendPort
    $env:BROWSER        = "none"   # ne pas ouvrir auto le navigateur
    $frontendCmd = "chcp 65001 > nul 2>&1; Set-Location '$Frontend'; `$env:PORT='$FrontendPort'; `$env:BROWSER='none'; npm start"
    Start-Process powershell -ArgumentList "-NoExit", "-Command", $frontendCmd `
        -WindowStyle Normal
    Start-Sleep -Seconds 3
    Write-OK "Frontend lancé → http://localhost:$FrontendPort"
}

# ── Résumé ────────────────────────────────────────────────────────────────
Write-Host ""
Write-Box @(
    "  Plateforme en cours de démarrage...",
    "",
    "  Frontend  ->  http://localhost:$FrontendPort",
    "  Backend   ->  http://localhost:$BackendPort",
    "  Admin     ->  http://localhost:$BackendPort/admin",
    "  API       ->  http://localhost:$BackendPort/api/",
    "  AI Insight->  http://localhost:$FrontendPort/#/ai-insights",
    "",
    "  Fermez les fenêtres PowerShell pour tout arrêter."
)

# Ouvrir le navigateur après 5s
Write-Host ""
Write-Host "  Ouverture du navigateur dans 5 secondes..." -ForegroundColor DarkGray
Start-Sleep -Seconds 5
Start-Process "http://localhost:$FrontendPort"
