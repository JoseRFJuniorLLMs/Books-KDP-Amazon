@echo off
REM ============================================================================
REM RUN_ALL.BAT - Executa todo o pipeline em paralelo (Windows)
REM ============================================================================
REM Uso:
REM   run_all.bat
REM   run_all.bat en es 20
REM ============================================================================

setlocal EnableDelayedExpansion

REM Configurações padrão
set LANGUAGES=%1 %2
set LIMIT=%3
set MODEL=qwen2.5:7b

if "%LANGUAGES%"==" " set LANGUAGES=en es
if "%LIMIT%"=="" set LIMIT=20

echo ============================================================================
echo GOOGOLPLEX-BOOKS - PIPELINE COMPLETO
echo ============================================================================
echo Idiomas: %LANGUAGES%
echo Limite: %LIMIT% livros por idioma
echo Modelo: %MODEL%
echo ============================================================================
echo.

REM Executa script Python
python run_all.py --languages %LANGUAGES% --limit %LIMIT% --model %MODEL%

if errorlevel 1 (
    echo.
    echo ============================================================================
    echo ERRO: Pipeline falhou!
    echo ============================================================================
    pause
    exit /b 1
)

echo.
echo ============================================================================
echo SUCESSO: Pipeline concluido!
echo ============================================================================
pause
