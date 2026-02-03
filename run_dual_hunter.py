#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN_DUAL_HUNTER.PY - Executa Hunter1 (Gutenberg) e Hunter2 (Archive.org)
==========================================================================
Baixa livros de ambas as fontes para maximizar variedade.

Uso:
    python run_dual_hunter.py --languages en es --limit 50
"""

import sys
import logging
from pathlib import Path
from datetime import datetime

# Adiciona src/ ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config.settings import LOG_DIR

# Logging
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"dual_hunter_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Dual Hunter - Baixa de Gutenberg + Archive.org",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Baixar de ambas as fontes
  python run_dual_hunter.py --languages en es --limit 50

  # Apenas Archive.org
  python run_dual_hunter.py --languages en --limit 100 --skip-gutenberg

  # Apenas Gutenberg
  python run_dual_hunter.py --languages en --limit 100 --skip-archive
"""
    )

    parser.add_argument('--languages', '-l', nargs='+', default=['en', 'es'],
                       help='Idiomas para buscar')
    parser.add_argument('--limit', '-n', type=int, default=50,
                       help='Número de livros por idioma por fonte')
    parser.add_argument('--skip-gutenberg', action='store_true',
                       help='Pular Project Gutenberg')
    parser.add_argument('--skip-archive', action='store_true',
                       help='Pular Archive.org')

    args = parser.parse_args()

    logger.info("="*70)
    logger.info("🎯 DUAL HUNTER - Gutenberg + Archive.org")
    logger.info("="*70)
    logger.info(f"Idiomas: {', '.join(args.languages)}")
    logger.info(f"Limite por fonte: {args.limit}")
    logger.info("="*70)

    total_stats = {
        'gutenberg': {'downloaded': 0, 'skipped': 0},
        'archive': {'downloaded': 0, 'skipped': 0}
    }

    # 1. Project Gutenberg
    if not args.skip_gutenberg:
        logger.info("\n" + "🔹"*35)
        logger.info("FONTE 1/2: Project Gutenberg")
        logger.info("🔹"*35)

        try:
            from hunter import BookHunter
            hunter1 = BookHunter()
            hunter1.update_catalog()

            for lang in args.languages:
                books = hunter1.get_books_by_language(lang, limit=args.limit * 2)
                logger.info(f"Processando {len(books)} livros de Gutenberg ({lang.upper()})...")

                count = 0
                for book in books:
                    if count >= args.limit:
                        break

                    if hunter1.book_exists(book.author, book.title):
                        total_stats['gutenberg']['skipped'] += 1
                        continue

                    if hunter1.download_and_extract(book):
                        total_stats['gutenberg']['downloaded'] += 1
                        count += 1

        except Exception as e:
            logger.error(f"Erro no Hunter Gutenberg: {e}")

    # 2. Archive.org
    if not args.skip_archive:
        logger.info("\n" + "🔹"*35)
        logger.info("FONTE 2/2: Archive.org")
        logger.info("🔹"*35)

        try:
            from hunter2 import ArchiveOrgHunter
            hunter2 = ArchiveOrgHunter()
            stats = hunter2.hunt(args.languages, args.limit)
            total_stats['archive']['downloaded'] = stats['downloaded']
            total_stats['archive']['skipped'] = stats['skipped']

        except Exception as e:
            logger.error(f"Erro no Hunter Archive.org: {e}")

    # Resumo Final
    logger.info("\n" + "="*70)
    logger.info("📊 RESUMO FINAL - DUAL HUNTER")
    logger.info("="*70)
    logger.info(f"Project Gutenberg:")
    logger.info(f"  • Baixados: {total_stats['gutenberg']['downloaded']}")
    logger.info(f"  • Pulados: {total_stats['gutenberg']['skipped']}")
    logger.info(f"")
    logger.info(f"Archive.org:")
    logger.info(f"  • Baixados: {total_stats['archive']['downloaded']}")
    logger.info(f"  • Pulados: {total_stats['archive']['skipped']}")
    logger.info(f"")
    logger.info(f"TOTAL:")
    logger.info(f"  • Baixados: {total_stats['gutenberg']['downloaded'] + total_stats['archive']['downloaded']}")
    logger.info(f"  • Pulados: {total_stats['gutenberg']['skipped'] + total_stats['archive']['skipped']}")
    logger.info("="*70)

    return 0

if __name__ == "__main__":
    sys.exit(main())
