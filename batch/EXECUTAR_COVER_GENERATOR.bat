@echo off
chcp 65001 > nul
title Book Cover Generator

echo ========================================
echo 🎨 GERADOR DE CAPAS COM IA
echo ========================================
echo.
echo Este script gera capas de livros usando:
echo   - OpenAI DALL-E 3
echo   - Google Gemini Imagen
echo   - Stability AI
echo.
echo ========================================
echo.

REM Verifica se Python está instalado
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python não encontrado!
    pause
    exit /b 1
)

echo Escolha o modo:
echo   1 = Gerar capas para um livro específico
echo   2 = Gerar capas para TODOS os livros traduzidos
echo.
set /p MODE="Modo (1 ou 2): "

if "%MODE%"=="2" (
    echo.
    echo 🔄 Gerando capas para todos os livros traduzidos...
    echo Isso pode demorar bastante!
    echo.
    python src\cover_generator.py --batch
) else (
    echo.
    set /p BOOK_PATH="Caminho do arquivo TXT traduzido: "

    if exist "%BOOK_PATH%" (
        echo.
        echo 🎨 Gerando capas...
        python src\cover_generator.py --input "%BOOK_PATH%"
    ) else (
        echo ❌ Arquivo não encontrado!
    )
)

echo.
echo ========================================
echo Concluído!
echo ========================================
pause
