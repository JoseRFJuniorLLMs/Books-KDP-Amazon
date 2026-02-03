#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN_HUNTER_INFINITE.PY - Download Infinito
===========================================
Baixa 1000 livros, repete infinitamente.

Uso:
    python run_hunter_infinite.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from hunter_fast import FastHunter
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s'
)
logger = logging.getLogger(__name__)

def main():
    cycle = 0
    total_downloaded = 0

    logger.info("="*70)
    logger.info("HUNTER INFINITO - Loop Eterno")
    logger.info("="*70)
    logger.info("Ctrl+C para parar")
    logger.info("="*70)

    while True:
        try:
            cycle += 1
            logger.info(f"\n{'='*70}")
            logger.info(f"CICLO {cycle} - Baixando 1000 livros...")
            logger.info(f"{'='*70}")

            hunter = FastHunter(max_workers=20)
            stats = hunter.hunt(['en', 'es', 'fr', 'de', 'pt'], limit=1000)

            downloaded = stats.get('downloaded', 0)
            total_downloaded += downloaded

            logger.info(f"\n{'='*70}")
            logger.info(f"CICLO {cycle} COMPLETO")
            logger.info(f"Este ciclo: {downloaded} livros")
            logger.info(f"Total acumulado: {total_downloaded} livros")
            logger.info(f"{'='*70}")

            # Pequena pausa entre ciclos
            logger.info("Aguardando 10s antes do próximo ciclo...")
            time.sleep(10)

        except KeyboardInterrupt:
            logger.info("\n\nParado pelo usuário!")
            logger.info(f"Total baixado: {total_downloaded} livros em {cycle} ciclos")
            break
        except Exception as e:
            logger.error(f"Erro no ciclo {cycle}: {e}")
            logger.info("Tentando novamente em 30s...")
            time.sleep(30)

if __name__ == "__main__":
    main()
