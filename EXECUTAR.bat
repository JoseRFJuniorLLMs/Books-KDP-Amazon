@echo off
chcp 65001 >nul
title Googolplex-Books - Menu Principal
color 0A

:menu
cls
echo.
echo  ╔══════════════════════════════════════════════════════════════════╗
echo  ║           GOOGOLPLEX-BOOKS - SISTEMA DE LIVROS                   ║
echo  ╠══════════════════════════════════════════════════════════════════╣
echo  ║                                                                  ║
echo  ║  [1] DAEMON COMPLETO (Download + Traducao + DOCX + Capas)        ║
echo  ║  [2] DOWNLOAD RAPIDO (massivo paralelo, 15 threads)             ║
echo  ║  [3] Apenas TRADUCAO para Portugues                              ║
echo  ║  [4] Apenas gerar DOCX dos traduzidos                            ║
echo  ║  [5] Apenas gerar CAPAS com IA                                   ║
echo  ║                                                                  ║
echo  ╠══════════════════════════════════════════════════════════════════╣
echo  ║  [6] Ver STATUS (livros baixados/traduzidos)                     ║
echo  ║  [7] Auto Git Push (commit automatico)                           ║
echo  ║  [8] Abrir pasta dos livros                                      ║
echo  ║                                                                  ║
echo  ║  [0] SAIR                                                        ║
echo  ║                                                                  ║
echo  ╚══════════════════════════════════════════════════════════════════╝
echo.
set /p opcao="  Escolha uma opcao: "

if "%opcao%"=="1" goto daemon
if "%opcao%"=="2" goto download
if "%opcao%"=="3" goto traducao
if "%opcao%"=="4" goto docx
if "%opcao%"=="5" goto capas
if "%opcao%"=="6" goto status
if "%opcao%"=="7" goto git
if "%opcao%"=="8" goto pasta
if "%opcao%"=="0" goto sair

echo.
echo  Opcao invalida!
timeout /t 2 >nul
goto menu

:daemon
cls
echo.
echo  Iniciando DAEMON COMPLETO...
echo  (Ctrl+C para parar)
echo.
python run_daemon.py --languages en es --batch-size 50
pause
goto menu

:download
cls
echo.
echo  DOWNLOAD MASSIVO PARALELO (15 threads)
echo  Baixando 500 livros por idioma...
echo.
python run_hunter_fast.py --languages en es --limit 500 --workers 15
pause
goto menu

:traducao
cls
echo.
echo  Traduzindo livros para Portugues...
echo.
python run_translator.py --languages en es
pause
goto menu

:docx
cls
echo.
echo  Gerando DOCX dos livros traduzidos...
echo.
python src/processor.py --batch
pause
goto menu

:capas
cls
echo.
echo  Gerando CAPAS com IA...
echo  (Precisa configurar API keys no .env)
echo.
python src/cover_generator.py --batch
pause
goto menu

:status
cls
echo.
echo  ═══════════════════════════════════════════════════════════════════
echo                         STATUS DO SISTEMA
echo  ═══════════════════════════════════════════════════════════════════
echo.
for /f %%a in ('powershell -Command "(Get-ChildItem txt -Recurse -Filter *.txt).Count"') do set TXT=%%a
for /f %%a in ('powershell -Command "(Get-ChildItem translated -Recurse -Filter *_pt.txt).Count"') do set PT=%%a
for /f %%a in ('powershell -Command "(Get-ChildItem docx -Recurse -Filter *.docx).Count"') do set DOCX=%%a
echo   Livros baixados (txt):      %TXT%
echo   Traduzidos (portugues):     %PT%
echo   DOCX gerados:               %DOCX%
echo.
echo  ═══════════════════════════════════════════════════════════════════
pause
goto menu

:git
cls
echo.
echo  Iniciando Auto Git Push...
echo.
python auto_git_push.py
pause
goto menu

:pasta
explorer txt
goto menu

:sair
echo.
echo  Ate logo!
timeout /t 2 >nul
exit
