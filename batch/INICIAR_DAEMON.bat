@echo off
echo ============================================================================
echo DAEMON 24/7 - Baixa e traduz CONTINUAMENTE
echo ============================================================================
echo.
echo Este script vai rodar INDEFINIDAMENTE:
echo - Baixa 50 livros
echo - Traduz todos
echo - Aguarda 10 minutos
echo - REPETE (loop infinito)
echo.
echo Para PARAR: Pressione Ctrl+C
echo.
pause

cd /d "%~dp0"
"C:\Users\juliu\AppData\Local\Python\bin\python.exe" run_daemon.py --languages en es --batch-size 50 --model "bigllama/mistralv01-7b:latest"

pause
