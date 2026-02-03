@echo off
chcp 65001 > nul
title FAZ.PY - Processador de Livros

echo ============================================================
echo    FAZ.PY - Processador de Livros para KDP
echo ============================================================
echo.

REM Verifica se Ollama esta rodando
curl -s http://localhost:11434/api/tags > nul 2>&1
if errorlevel 1 (
    echo [AVISO] Ollama nao esta rodando. Iniciando...
    start /B ollama serve
    timeout /t 5 /nobreak > nul
)

REM Executa o processador
if "%~1"=="" (
    echo Modo batch: processando todos os livros em txt/
    python faz.py
) else (
    echo Processando arquivo: %~1
    python faz.py --input "%~1"
)

echo.
echo ============================================================
echo    Processamento concluido!
echo ============================================================
pause
