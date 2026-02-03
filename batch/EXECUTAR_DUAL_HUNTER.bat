@echo off
chcp 65001 > nul
title Dual Hunter - Gutenberg + Archive.org

echo ========================================
echo 🎯 DUAL HUNTER
echo ========================================
echo.
echo Baixa livros de DUAS fontes:
echo   1. Project Gutenberg
echo   2. Archive.org
echo.
echo Isso maximiza a variedade de livros!
echo ========================================
echo.

REM Verifica se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python não encontrado!
    pause
    exit /b 1
)

REM Pergunta idiomas
echo Escolha os idiomas (separados por espaço):
echo   en = Inglês
echo   es = Espanhol
echo   pt = Português
echo   fr = Francês
echo   de = Alemão
echo.
set /p LANGS="Idiomas (padrão: en es): "
if "%LANGS%"=="" set LANGS=en es

REM Pergunta quantidade
set /p LIMIT="Quantos livros por idioma POR FONTE? (padrão: 50): "
if "%LIMIT%"=="" set LIMIT=50

echo.
echo ========================================
echo Configuração:
echo   Idiomas: %LANGS%
echo   Limite: %LIMIT% por idioma POR fonte
echo   Total esperado: ~%LIMIT% x 2 fontes = até %LIMIT%00 livros novos
echo ========================================
echo.
echo 🚀 Iniciando download de ambas as fontes...
echo.

python run_dual_hunter.py --languages %LANGS% --limit %LIMIT%

echo.
echo ========================================
echo Download concluído!
echo ========================================
pause
