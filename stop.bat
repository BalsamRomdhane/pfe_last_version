@echo off
chcp 65001 > nul
title Arrêt de la plateforme

echo.
echo  Arrêt de la plateforme ISO Compliance...
echo.

:: Tuer Django (port 8000)
echo [1/2] Arrêt du backend Django (port 8000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F > nul 2>&1
)
echo       [OK] Backend arrêté.

:: Tuer React (port 3000)
echo [2/2] Arrêt du frontend React (port 3000)...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":3000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%a /F > nul 2>&1
)
echo       [OK] Frontend arrêté.

echo.
echo  Plateforme arrêtée.
echo.
pause
