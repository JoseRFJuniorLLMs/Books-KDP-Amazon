@echo off
REM ============================================================================
REM START_DAEMON.BAT - Inicia Daemon 24/7 (Windows)
REM ============================================================================
REM Roda continuamente o dia todo sem supervisão
REM ============================================================================

setlocal EnableDelayedExpansion

echo ============================================================================
echo DAEMON AUTONOMO 24/7 - Googolplex Books
echo ============================================================================
echo.
echo Este script vai rodar CONTINUAMENTE:
echo - Baixa livros automaticamente
echo - Traduz livros automaticamente
echo - Repete indefinidamente
echo.
echo Para PARAR: Pressione Ctrl+C
echo.
echo ============================================================================
echo.

REM Configurações (ajuste aqui)
set LANGUAGES=en es
set BATCH_SIZE=50
set MODEL=qwen2.5:7b
set CYCLE_DELAY=600

REM Executa daemon
python run_daemon.py --languages %LANGUAGES% --batch-size %BATCH_SIZE% --model %MODEL% --cycle-delay %CYCLE_DELAY%

echo.
echo ============================================================================
echo Daemon finalizado
echo ============================================================================
pause
