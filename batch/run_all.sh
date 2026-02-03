#!/bin/bash
# ============================================================================
# RUN_ALL.SH - Executa todo o pipeline em paralelo (Linux/Mac)
# ============================================================================
# Uso:
#   ./run_all.sh
#   ./run_all.sh en es 20
#   ./run_all.sh en es ru 50 qwen2.5:14b
# ============================================================================

set -e  # Para em caso de erro

# Configurações padrão
LANGUAGES="${1:-en} ${2:-es}"
LIMIT="${3:-20}"
MODEL="${4:-qwen2.5:7b}"

# Remove espaços extras
LANGUAGES=$(echo "$LANGUAGES" | xargs)

echo "============================================================================"
echo "🚀 GOOGOLPLEX-BOOKS - PIPELINE COMPLETO"
echo "============================================================================"
echo "Idiomas: $LANGUAGES"
echo "Limite: $LIMIT livros por idioma"
echo "Modelo: $MODEL"
echo "============================================================================"
echo

# Executa script Python
python3 run_all.py --languages $LANGUAGES --limit "$LIMIT" --model "$MODEL"

if [ $? -eq 0 ]; then
    echo
    echo "============================================================================"
    echo "✅ SUCESSO: Pipeline concluído!"
    echo "============================================================================"
else
    echo
    echo "============================================================================"
    echo "❌ ERRO: Pipeline falhou!"
    echo "============================================================================"
    exit 1
fi
