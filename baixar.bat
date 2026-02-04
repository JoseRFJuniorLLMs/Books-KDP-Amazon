@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ============================================================================
echo  BooksKDP - Download de Modelos para Modo Local
echo ============================================================================
echo.

:: Diretorio base
set BASE_DIR=%~dp0
cd /d %BASE_DIR%

:: ============================================================================
:: 1. OLLAMA + MODELO
:: ============================================================================
echo [1/4] OLLAMA + MODELO qwen2.5:14b
echo ----------------------------------------------------------------------------

where ollama >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Ollama nao encontrado. Baixando instalador...
    echo.
    echo     Acesse: https://ollama.ai/download
    echo     Ou execute: winget install Ollama.Ollama
    echo.
    pause
    start https://ollama.ai/download
    goto :ollama_done
)

echo [OK] Ollama instalado
echo [*] Baixando modelo qwen2.5:14b (8GB)...
ollama pull qwen2.5:14b

echo [*] Iniciando Ollama em background...
start /B ollama serve

:ollama_done
echo.

:: ============================================================================
:: 2. LANGUAGETOOL (Docker)
:: ============================================================================
echo [2/4] LANGUAGETOOL (Docker)
echo ----------------------------------------------------------------------------

where docker >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [!] Docker nao encontrado.
    echo     Instale Docker Desktop: https://docker.com/products/docker-desktop
    echo.
    goto :languagetool_done
)

echo [OK] Docker instalado
echo [*] Baixando imagem LanguageTool...
docker pull erikvl87/languagetool

echo [*] Iniciando container na porta 8010...
docker stop languagetool 2>nul
docker rm languagetool 2>nul
docker run -d --name languagetool -p 8010:8010 erikvl87/languagetool

echo [OK] LanguageTool rodando em http://localhost:8010

:languagetool_done
echo.

:: ============================================================================
:: 3. COMFYUI
:: ============================================================================
echo [3/4] COMFYUI
echo ----------------------------------------------------------------------------

if exist "ComfyUI" (
    echo [OK] ComfyUI ja existe
    cd ComfyUI
    echo [*] Atualizando...
    git pull
) else (
    echo [*] Clonando ComfyUI...
    git clone https://github.com/comfyanonymous/ComfyUI.git
    cd ComfyUI
)

echo [*] Instalando dependencias Python...
pip install -r requirements.txt -q

cd /d %BASE_DIR%
echo.

:: ============================================================================
:: 4. MODELO SDXL
:: ============================================================================
echo [4/4] MODELO SDXL
echo ----------------------------------------------------------------------------

set MODELS_DIR=ComfyUI\models\checkpoints
if not exist "%MODELS_DIR%" mkdir "%MODELS_DIR%"

set SDXL_FILE=%MODELS_DIR%\sdxl_base_1.0.safetensors

if exist "%SDXL_FILE%" (
    echo [OK] Modelo SDXL ja existe
) else (
    echo [*] Baixando SDXL Base 1.0 (6.5GB)...
    echo     Isso pode demorar alguns minutos...
    echo.

    where curl >nul 2>&1
    if %ERRORLEVEL% EQU 0 (
        curl -L -o "%SDXL_FILE%" "https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors"
    ) else (
        echo [!] curl nao encontrado. Baixe manualmente:
        echo     URL: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0
        echo     Salve em: %SDXL_FILE%
        start https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/tree/main
    )
)

echo.

:: ============================================================================
:: RESUMO
:: ============================================================================
echo ============================================================================
echo  RESUMO
echo ============================================================================
echo.

:: Verificar Ollama
where ollama >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    echo [OK] Ollama instalado
    ollama list 2>nul | findstr "qwen2.5:14b" >nul
    if %ERRORLEVEL% EQU 0 (
        echo [OK] Modelo qwen2.5:14b baixado
    ) else (
        echo [!!] Modelo qwen2.5:14b NAO encontrado
    )
) else (
    echo [!!] Ollama NAO instalado
)

:: Verificar Docker/LanguageTool
where docker >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    docker ps | findstr "languagetool" >nul
    if %ERRORLEVEL% EQU 0 (
        echo [OK] LanguageTool rodando
    ) else (
        echo [!!] LanguageTool NAO rodando
    )
) else (
    echo [!!] Docker NAO instalado
)

:: Verificar ComfyUI
if exist "ComfyUI\main.py" (
    echo [OK] ComfyUI instalado
) else (
    echo [!!] ComfyUI NAO instalado
)

:: Verificar SDXL
if exist "%SDXL_FILE%" (
    echo [OK] Modelo SDXL baixado
) else (
    echo [!!] Modelo SDXL NAO encontrado
)

echo.
echo ============================================================================
echo  PROXIMOS PASSOS
echo ============================================================================
echo.
echo  1. Copiar config:     copy .env-local .env
echo  2. Iniciar ComfyUI:   cd ComfyUI ^&^& python main.py --listen
echo  3. Testar setup:      python scripts\setup_local.py
echo  4. Rodar pipeline:    python -m src.pipeline.smart_processor --input books\txt\other --output books --limit 1
echo.
echo ============================================================================

pause
