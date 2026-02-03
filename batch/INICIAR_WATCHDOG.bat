@echo off
chcp 65001 > nul
title Watchdog Daemon - Auto-Restart Habilitado

echo ========================================
echo 👁️ WATCHDOG DAEMON - AUTO-RESTART
echo ========================================
echo.
echo Este script monitora o daemon e reinicia
echo automaticamente se ele cair.
echo.
echo Pressione Ctrl+C para parar
echo ========================================
echo.

REM Verifica se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python não encontrado!
    echo Por favor, instale Python primeiro.
    pause
    exit /b 1
)

REM Instala psutil se necessário
echo Verificando dependências...
python -c "import psutil" >nul 2>&1
if %errorlevel% neq 0 (
    echo 📦 Instalando psutil...
    pip install psutil
)

REM Inicia watchdog
echo.
echo 🚀 Iniciando watchdog...
echo.
python watchdog_daemon.py --languages en es --batch-size 50 --model bigllama/mistralv01-7b:latest

echo.
echo ========================================
echo Watchdog finalizado
echo ========================================
pause
