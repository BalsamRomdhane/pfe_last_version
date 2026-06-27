@echo off
chcp 65001 > nul
title Enterprise ISO Compliance Platform

echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║     Enterprise ISO Compliance Platform — Launcher       ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

:: ── Chemins ───────────────────────────────────────────────────────────────
set ROOT=%~dp0
set BACKEND=%ROOT%backend
set FRONTEND=%ROOT%frontend
set VENV=%BACKEND%\.venv\Scripts

:: ── 1. Vérifier Python venv ───────────────────────────────────────────────
echo [1/5] Vérification de l'environnement Python...
if not exist "%VENV%\python.exe" (
    echo       [!] Venv absent — création en cours...
    python -m venv "%BACKEND%\.venv"
    if errorlevel 1 (
        echo       [ERREUR] Impossible de créer le venv. Python est-il installé ?
        pause & exit /b 1
    )
    echo       [!] Installation des dépendances...
    "%VENV%\pip.exe" install -r "%BACKEND%\requirements.txt" --quiet
)
echo       [OK] Environnement Python prêt.

:: ── 2. Vérifier Node modules ──────────────────────────────────────────────
echo [2/5] Vérification des dépendances Node.js...
if not exist "%FRONTEND%\node_modules" (
    echo       [!] node_modules absent — installation en cours...
    cd /d "%FRONTEND%"
    call npm install --silent
    if errorlevel 1 (
        echo       [ERREUR] npm install a échoué.
        pause & exit /b 1
    )
)
echo       [OK] Node modules prêts.

:: ── 3. Django migrate ─────────────────────────────────────────────────────
echo [3/5] Migration de la base de données...
cd /d "%BACKEND%"
"%VENV%\python.exe" manage.py migrate --run-syncdb 2>&1 | findstr /V "^$" | findstr /V "Applying\|OK\|No migrations"
echo       [OK] Base de données synchronisée.

:: ── 4. Lancer Django backend ──────────────────────────────────────────────
echo [4/5] Démarrage du backend Django (port 8000)...
start "Django Backend" cmd /k "chcp 65001 > nul && cd /d %BACKEND% && %VENV%\python.exe manage.py runserver 0.0.0.0:8000"
timeout /t 2 > nul

:: ── 5. Lancer React frontend ──────────────────────────────────────────────
echo [5/5] Démarrage du frontend React (port 3000)...
start "React Frontend" cmd /k "chcp 65001 > nul && cd /d %FRONTEND% && npm start"

:: ── Infos ──────────────────────────────────────────────────────────────────
echo.
echo  ╔══════════════════════════════════════════════════════════╗
echo  ║  🚀  Plateforme en cours de démarrage...                ║
echo  ║                                                          ║
echo  ║  Backend  →  http://localhost:8000                      ║
echo  ║  Frontend →  http://localhost:3000                      ║
echo  ║  Admin    →  http://localhost:8000/admin                ║
echo  ║  API docs →  http://localhost:8000/api/                 ║
echo  ║                                                          ║
echo  ║  Fermez les deux fenêtres pour arrêter.                 ║
echo  ╚══════════════════════════════════════════════════════════╝
echo.

pause
