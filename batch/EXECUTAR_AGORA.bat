@echo off
SETLOCAL EnableDelayedExpansion

echo ============================================================================
echo GOOGOLPLEX-BOOKS - EXECUTANDO TUDO EM PARALELO
echo ============================================================================
echo.

REM Muda para o diretório do script
cd /d "%~dp0"

echo Procurando Python...
echo.

REM Busca Python em locais comuns
set PYTHON_CMD=

REM Testa se 'python' funciona
python --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python
    goto :found
)

REM Testa 'py' launcher
py --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=py
    goto :found
)

REM Testa 'python3'
python3 --version >nul 2>&1
if %errorlevel% equ 0 (
    set PYTHON_CMD=python3
    goto :found
)

REM Busca em AppData
if exist "%LOCALAPPDATA%\Programs\Python\Python314\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python314\python.exe"
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python313\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    goto :found
)
if exist "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" (
    set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
    goto :found
)

REM Busca em C:\Python*
if exist "C:\Python314\python.exe" (
    set PYTHON_CMD="C:\Python314\python.exe"
    goto :found
)
if exist "C:\Python313\python.exe" (
    set PYTHON_CMD="C:\Python313\python.exe"
    goto :found
)
if exist "C:\Python312\python.exe" (
    set PYTHON_CMD="C:\Python312\python.exe"
    goto :found
)
if exist "C:\Python311\python.exe" (
    set PYTHON_CMD="C:\Python311\python.exe"
    goto :found
)

REM Busca em Program Files
if exist "C:\Program Files\Python314\python.exe" (
    set PYTHON_CMD="C:\Program Files\Python314\python.exe"
    goto :found
)
if exist "C:\Program Files\Python313\python.exe" (
    set PYTHON_CMD="C:\Program Files\Python313\python.exe"
    goto :found
)

REM Usa WHERE para buscar
for /f "delims=" %%i in ('where python 2^>nul') do (
    set PYTHON_CMD="%%i"
    goto :found
)

REM Python não encontrado
echo [ERRO] Python nao encontrado automaticamente!
echo.
echo Solucoes:
echo.
echo 1. Execute no CMD (nao PowerShell):
echo    cd d:\DEV\Googolplex-Books
echo    python run_all.py --languages en es --limit 20
echo.
echo 2. Ou adicione Python ao PATH do sistema
echo.
pause
exit /b 1

:found
echo [OK] Python encontrado: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

REM Verifica dependências
echo Verificando dependencias Python...
%PYTHON_CMD% -c "import requests, tqdm, langdetect" >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [AVISO] Dependencias nao encontradas!
    echo Instalando: pip install requests tqdm langdetect python-dotenv
    echo.
    %PYTHON_CMD% -m pip install requests tqdm langdetect python-dotenv
    echo.
)

echo ============================================================================
echo EXECUTANDO: run_all.py --languages en es --limit 20
echo ============================================================================
echo.
echo O que vai acontecer:
echo [1] Inicia Ollama automaticamente
echo [2] Baixa modelo + livros EM PARALELO (simultaneamente)
echo [3] Traduz todos os livros automaticamente
echo.
echo Isso pode demorar varios minutos. Aguarde...
echo.
echo ============================================================================
echo.

REM Executa o pipeline
%PYTHON_CMD% run_all.py --languages en es --limit 20

if %errorlevel% equ 0 (
    echo.
    echo ============================================================================
    echo [SUCESSO] Pipeline completado!
    echo ============================================================================
    echo.
    echo Verifique os resultados:
    echo - txt\       = Livros baixados
    echo - translated\ = Livros traduzidos
    echo.
    dir /s txt\*.txt 2>nul | find "File(s)"
    dir /s translated\*_pt.txt 2>nul | find "File(s)"
    echo.
) else (
    echo.
    echo ============================================================================
    echo [ERRO] Falha ao executar (codigo: %errorlevel%)
    echo ============================================================================
    echo.
    echo Possivel causa: Ollama nao esta rodando
    echo.
    echo Solucao:
    echo 1. Abra outro terminal
    echo 2. Execute: ollama serve
    echo 3. Execute este script novamente
    echo.
)

pause
