@echo off
REM ============================================================================
REM RUN_NOW.BAT - Executa TUDO em paralelo AGORA
REM ============================================================================

echo ============================================================================
echo EXECUTANDO GOOGOLPLEX-BOOKS - PARALELO
echo ============================================================================
echo.

REM Executa via PowerShell
powershell -ExecutionPolicy Bypass -File "%~dp0RUN_NOW.ps1"

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo Erro ao executar
    echo ============================================================================
    pause
    exit /b 1
)

pause
