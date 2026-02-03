@echo off
REM =============================================================================
REM CRIAR VM NO GCP - BooksKDP
REM =============================================================================

set PROJECT_ID=aurorav2-484411
set VM_NAME=bookskdp-processor
set ZONE=us-central1-a
set BUCKET=bookskdp-aurorav2-484411

echo.
echo ============================================
echo CRIANDO VM PARA PROCESSAMENTO
echo ============================================
echo Projeto: %PROJECT_ID%
echo VM: %VM_NAME%
echo Zone: %ZONE%
echo.

REM Configura projeto
gcloud config set project %PROJECT_ID%

REM Habilita APIs
echo [1/4] Habilitando APIs...
gcloud services enable compute.googleapis.com
gcloud services enable storage.googleapis.com

REM Cria bucket
echo [2/4] Criando bucket...
gsutil mb -l us-central1 gs://%BUCKET% 2>nul

REM Cria VM
echo [3/4] Criando VM...
gcloud compute instances create %VM_NAME% ^
    --project=%PROJECT_ID% ^
    --zone=%ZONE% ^
    --machine-type=e2-standard-4 ^
    --boot-disk-size=100GB ^
    --boot-disk-type=pd-ssd ^
    --image-family=debian-12 ^
    --image-project=debian-cloud ^
    --metadata-from-file=startup-script=startup.sh ^
    --scopes=cloud-platform ^
    --tags=http-server

echo.
echo [4/4] VM criada! O processamento iniciara automaticamente.
echo.
echo ============================================
echo COMANDOS UTEIS:
echo ============================================
echo.
echo Ver logs:
echo   gcloud compute ssh %VM_NAME% --zone=%ZONE% --command="tail -f /var/log/bookskdp.log"
echo.
echo Ver status:
echo   gsutil cat gs://%BUCKET%/status/complete.txt
echo.
echo Baixar resultados:
echo   gsutil -m cp -r gs://%BUCKET%/docx/* books/docx/gcp/
echo.
echo Deletar VM (apos completar):
echo   gcloud compute instances delete %VM_NAME% --zone=%ZONE% --quiet
echo.

pause
