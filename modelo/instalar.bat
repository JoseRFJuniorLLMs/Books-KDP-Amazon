@echo off
chcp 65001 > nul
title FAZ.PY - Instalação

echo ============================================================
echo    FAZ.PY - Instalador do Ambiente
echo ============================================================
echo.

REM Verifica Python
python --version > nul 2>&1
if errorlevel 1 (
    echo [ERRO] Python nao encontrado!
    echo Instale Python 3.9+ de: https://python.org
    pause
    exit /b 1
)

echo [OK] Python encontrado
echo.

REM Instala dependencias
echo Instalando dependencias Python...
pip install -r requirements.txt -q

echo.
echo [OK] Dependencias instaladas
echo.

REM Executa setup
echo Executando setup do modelo...
python setup_modelo.py

echo.
echo ============================================================
echo    Instalacao concluida!
echo ============================================================
echo.
echo Para processar livros:
echo    python faz.py --input arquivo.txt
echo    python faz.py  (processa todos em txt/)
echo.
pause
