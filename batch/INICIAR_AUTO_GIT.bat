@echo off
chcp 65001 > nul
title Auto Git Push - Commit automático de novos livros

echo ========================================
echo 🔄 AUTO GIT COMMIT/PUSH
echo ========================================
echo.
echo Este script monitora novos livros e faz
echo commit/push automaticamente.
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

REM Inicia auto-git
echo.
echo 🚀 Iniciando auto-git...
echo.
python auto_git_push.py --check-interval 30

echo.
echo ========================================
echo Auto-git finalizado
echo ========================================
pause
