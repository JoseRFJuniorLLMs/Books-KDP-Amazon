#!/bin/bash
# =============================================================================
# STARTUP SCRIPT - VM BooksKDP
# =============================================================================
# Processa livros que JÁ ESTÃO no bucket (não baixa do Gutenberg)

set -e

LOG_FILE="/var/log/bookskdp.log"
exec > >(tee -a $LOG_FILE) 2>&1

echo "=========================================="
echo "BOOKSKDP - Processando livros do bucket"
echo "Data: $(date)"
echo "=========================================="

# Variaveis
export PROJECT_ID="aurorav2-484411"
export BUCKET_NAME="bookskdp-aurorav2-484411"
export GEMINI_API_KEY="AQ.Ab8RN6JLHeepejU55fXlLZtg9eAwmK0aIf_JZeZ9xrE8_XtGgQ"

# 1. Instala dependencias
echo ""
echo "[1/5] Instalando dependencias..."
apt-get update -qq
apt-get install -y -qq python3-pip python3-venv git

# 2. Clona repositorio
echo ""
echo "[2/5] Clonando repositorio..."
cd /opt
rm -rf BooksKDP
git clone https://github.com/JoseRFJuniorLLMs/Books-KDP-Amazon.git BooksKDP
cd BooksKDP

# 3. Configura ambiente Python
echo ""
echo "[3/5] Configurando Python..."
python3 -m venv venv
source venv/bin/activate
pip install -q -r requirements.txt
pip install -q google-cloud-storage aiohttp google-auth

# 4. Baixa livros do bucket para processar localmente
echo ""
echo "[4/5] Baixando livros do bucket..."
mkdir -p books/txt
gsutil -m cp -r gs://$BUCKET_NAME/txt/* books/txt/

# Conta quantos livros
TOTAL=$(find books/txt -name "*.txt" | wc -l)
echo "Total de livros: $TOTAL"

# 5. Processa com o pipeline (enricher gera DOCX com vocabulário EN)
echo ""
echo "[5/6] Processando livros..."
python -m src.pipeline.orchestrator --step enrich --enrich-lang pt --enrich-words 100

# 6. Sobe resultados para bucket
echo ""
echo "[6/6] Salvando resultados no Cloud Storage..."
gsutil -m cp -r books/docx/* gs://$BUCKET_NAME/docx/

# Marca como completo
echo "COMPLETO - $(date) - $TOTAL livros" | gsutil cp - gs://$BUCKET_NAME/status/complete.txt

echo ""
echo "=========================================="
echo "PROCESSAMENTO COMPLETO!"
echo "Resultados em: gs://$BUCKET_NAME/docx/"
echo "=========================================="

# Auto-shutdown para economizar
echo "VM será desligada em 5 minutos..."
shutdown -h +5
