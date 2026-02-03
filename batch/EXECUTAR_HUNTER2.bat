@echo off
chcp 65001 > nul
title Hunter2 - Archive.org Book Downloader

echo ========================================
echo 📚 HUNTER2 - Archive.org
echo ========================================
echo.
echo Baixa livros do Internet Archive
echo (archive.org)
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

REM Pergunta idiomas
echo Escolha os idiomas (separados por espaço):
echo   en = Inglês
echo   es = Espanhol
echo   pt = Português
echo   fr = Francês
echo   de = Alemão
echo   it = Italiano
echo   ru = Russo
echo.
set /p LANGS="Idiomas (padrão: en es): "
if "%LANGS%"=="" set LANGS=en es

REM Pergunta quantidade
set /p LIMIT="Quantos livros por idioma? (padrão: 50): "
if "%LIMIT%"=="" set LIMIT=50

echo.
echo ========================================
echo Configuração:
echo   Idiomas: %LANGS%
echo   Limite: %LIMIT% por idioma
echo ========================================
echo.
echo 🚀 Iniciando download...
echo.

python run_hunter2.py --languages %LANGS% --limit %LIMIT%

echo.
echo ========================================
echo Download concluído!
echo ========================================
pause
