#!/bin/bash
# =============================================================================
# SUPER VM - Pipeline Completo com Cloud Translation + Imagen 3
# =============================================================================

set -e

LOG_FILE="/var/log/bookskdp.log"
exec > >(tee -a $LOG_FILE) 2>&1

echo "=========================================="
echo "BOOKSKDP - SUPER VM"
echo "Cloud Translation + Imagen 3 (nano)"
echo "Data: $(date)"
echo "=========================================="

# Variaveis
export PROJECT_ID="aurorav2-484411"
export BUCKET_NAME="bookskdp-aurorav2-484411"
export GEMINI_API_KEY="AQ.Ab8RN6JLHeepejU55fXlLZtg9eAwmK0aIf_JZeZ9xrE8_XtGgQ"
export GOOGLE_CLOUD_PROJECT="$PROJECT_ID"

# 1. Instala dependencias
echo ""
echo "[1/7] Instalando dependencias..."
apt-get update -qq
apt-get install -y -qq python3-pip python3-venv git

# 2. Clona repositorio
echo ""
echo "[2/7] Clonando repositorio..."
cd /opt
rm -rf BooksKDP
git clone https://github.com/JoseRFJuniorLLMs/Books-KDP-Amazon.git BooksKDP
cd BooksKDP

# 3. Configura ambiente Python
echo ""
echo "[3/7] Configurando Python..."
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements_cloud.txt

# 4. Baixa livros do bucket
echo ""
echo "[4/7] Baixando livros do bucket..."
mkdir -p books/txt
gsutil -m cp -r "gs://$BUCKET_NAME/txt/*" books/txt/ 2>/dev/null || true

# Conta quantos livros
TOTAL=$(find books/txt -name "*.txt" 2>/dev/null | wc -l)
echo "Total de livros: $TOTAL"

# 5. TRADUÇÃO (Cloud Translation API - rápido!)
echo ""
echo "[5/7] Traduzindo com Cloud Translation API..."
python -m src.pipeline.translator --input books/txt --output books/txt/pt --workers 10 --limit 0

# 6. PROCESSAMENTO
echo ""
echo "[6/7] Processando livros..."

# 6a. DOCX traduzidos simples
echo "  6a. Gerando DOCX traduzidos..."
python -m src.pipeline.generator --input books/txt/pt --output books/docx/pt

# 6b. DOCX com 100 palavras EN (enriched)
echo "  6b. Gerando DOCX com vocabulário EN..."
python -m src.pipeline.enricher --input books/txt/pt --output books/docx/pt/enriched --words 100

# 6c. CAPAS com Imagen 3 (nano) - 2 estilos
echo "  6c. Gerando capas (Imagen 3 nano)..."
python -m src.pipeline.cover_generator --input books/txt/pt --output books/covers --style artistic --limit 0 || true
python -m src.pipeline.cover_generator --input books/txt/pt --output books/covers --style modern --limit 0 || true

# 7. Upload resultados
echo ""
echo "[7/7] Salvando resultados no Cloud Storage..."
gsutil -m cp -r books/docx/* gs://$BUCKET_NAME/docx/ 2>/dev/null || true
gsutil -m cp -r books/covers/* gs://$BUCKET_NAME/covers/ 2>/dev/null || true

# Marca como completo
DOCX_COUNT=$(find books/docx -name "*.docx" 2>/dev/null | wc -l)
COVER_COUNT=$(find books/covers -name "*.png" 2>/dev/null | wc -l)
echo "COMPLETO - $(date) - $TOTAL livros, $DOCX_COUNT DOCX, $COVER_COUNT capas" | gsutil cp - gs://$BUCKET_NAME/status/complete.txt

echo ""
echo "=========================================="
echo "PROCESSAMENTO COMPLETO!"
echo "=========================================="
echo "Livros processados: $TOTAL"
echo "DOCX gerados: $DOCX_COUNT"
echo "Capas geradas: $COVER_COUNT"
echo "Resultados: gs://$BUCKET_NAME/"
echo "=========================================="

# Mantém VM rodando para verificação
echo ""
echo "VM continua ativa. Para desligar:"
echo "  gcloud compute instances stop bookskdp-super --zone=us-central1-a"
