@echo off
echo Iniciando monitoramento de arquivos na pasta txt...
powershell -ExecutionPolicy Bypass -File "%~dp0MonitorTxt.ps1"
pause
