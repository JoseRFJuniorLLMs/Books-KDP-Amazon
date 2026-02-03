#!/bin/bash
# ============================================================================
# START_DAEMON.SH - Inicia Daemon 24/7 (Linux/Mac)
# ============================================================================
# Roda continuamente o dia todo sem supervisão
# ============================================================================

# Configurações (ajuste aqui)
LANGUAGES="en es"
BATCH_SIZE=50
MODEL="qwen2.5:7b"
CYCLE_DELAY=600

echo "============================================================================"
echo "🤖 DAEMON AUTÔNOMO 24/7 - Googolplex Books"
echo "============================================================================"
echo ""
echo "Este script vai rodar CONTINUAMENTE:"
echo "- Baixa livros automaticamente"
echo "- Traduz livros automaticamente"
echo "- Repete indefinidamente"
echo ""
echo "Para PARAR: Pressione Ctrl+C"
echo ""
echo "============================================================================"
echo ""

# Executa daemon
python3 run_daemon.py \
    --languages $LANGUAGES \
    --batch-size $BATCH_SIZE \
    --model $MODEL \
    --cycle-delay $CYCLE_DELAY

echo ""
echo "============================================================================"
echo "Daemon finalizado"
echo "============================================================================"
