#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MÓDULO 1: DOWNLOADER
====================
Baixa livros do Project Gutenberg de forma paralela.

Uso:
    python -m src.pipeline.downloader --limit 100 --workers 4

Saída:
    books/raw/{idioma}/
"""

import os
import sys
import json
import asyncio
import aiohttp
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

# Configurações
BASE_URL = "https://www.gutenberg.org"
CATALOG_URL = f"{BASE_URL}/cache/epub/feeds/pg_catalog.csv"
OUTPUT_DIR = Path("books/raw")
MAX_CONCURRENT = 10


class BookDownloader:
    """Baixador de livros paralelo."""

    def __init__(self, output_dir: Path = OUTPUT_DIR, max_concurrent: int = MAX_CONCURRENT):
        self.output_dir = output_dir
        self.max_concurrent = max_concurrent
        self.session: Optional[aiohttp.ClientSession] = None
        self.downloaded = 0
        self.failed = 0
        self.stats = {"started": datetime.now().isoformat(), "books": []}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    def detect_language(self, text: str) -> str:
        """Detecta idioma baseado em padrões."""
        text_lower = text.lower()

        # Padrões simples de detecção
        if any(w in text_lower for w in ['the ', 'and ', 'of ', 'to ', 'in ']):
            return 'en'
        elif any(w in text_lower for w in ['de ', 'que ', 'para ', 'com ', 'não ']):
            return 'pt'
        elif any(w in text_lower for w in ['el ', 'la ', 'que ', 'de ', 'en ', 'los ']):
            return 'es'
        elif any(w in text_lower for w in ['и ', 'в ', 'на ', 'с ', 'что ']):
            return 'ru'
        elif any(w in text_lower for w in ['le ', 'la ', 'de ', 'et ', 'les ']):
            return 'fr'
        elif any(w in text_lower for w in ['der ', 'die ', 'und ', 'in ', 'den ']):
            return 'de'
        return 'other'

    async def download_book(self, book_id: int, semaphore: asyncio.Semaphore) -> Optional[Dict]:
        """Baixa um livro específico."""
        async with semaphore:
            try:
                # Tentar diferentes formatos
                urls = [
                    f"{BASE_URL}/cache/epub/{book_id}/pg{book_id}.txt",
                    f"{BASE_URL}/files/{book_id}/{book_id}-0.txt",
                    f"{BASE_URL}/files/{book_id}/{book_id}.txt",
                ]

                for url in urls:
                    try:
                        async with self.session.get(url, timeout=30) as resp:
                            if resp.status == 200:
                                content = await resp.text(errors='ignore')

                                # Detectar idioma
                                lang = self.detect_language(content[:5000])

                                # Criar pasta do idioma
                                lang_dir = self.output_dir / lang
                                lang_dir.mkdir(parents=True, exist_ok=True)

                                # Salvar arquivo
                                filename = f"pg{book_id}.txt"
                                filepath = lang_dir / filename
                                filepath.write_text(content, encoding='utf-8')

                                self.downloaded += 1
                                print(f"[OK] {book_id} -> {lang}/{filename}")

                                return {
                                    "id": book_id,
                                    "file": str(filepath),
                                    "lang": lang,
                                    "size": len(content)
                                }
                    except Exception:
                        continue

                self.failed += 1
                return None

            except Exception as e:
                self.failed += 1
                print(f"[ERRO] {book_id}: {e}")
                return None

    async def download_batch(self, book_ids: List[int]) -> List[Dict]:
        """Baixa um lote de livros em paralelo."""
        semaphore = asyncio.Semaphore(self.max_concurrent)
        tasks = [self.download_book(bid, semaphore) for bid in book_ids]
        results = await asyncio.gather(*tasks)
        return [r for r in results if r]

    async def run(self, start_id: int = 1, limit: int = 100):
        """Executa o download de livros."""
        print(f"=== DOWNLOADER ===")
        print(f"Baixando {limit} livros a partir do ID {start_id}")
        print(f"Concorrência: {self.max_concurrent}")
        print(f"Saída: {self.output_dir}")
        print()

        book_ids = list(range(start_id, start_id + limit))
        results = await self.download_batch(book_ids)

        self.stats["books"] = results
        self.stats["finished"] = datetime.now().isoformat()
        self.stats["downloaded"] = self.downloaded
        self.stats["failed"] = self.failed

        # Salvar estatísticas
        stats_file = self.output_dir / "download_stats.json"
        stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        print()
        print(f"=== CONCLUÍDO ===")
        print(f"Baixados: {self.downloaded}")
        print(f"Falhas: {self.failed}")

        return results


async def main():
    parser = argparse.ArgumentParser(description="Baixar livros do Project Gutenberg")
    parser.add_argument("--start", type=int, default=1, help="ID inicial")
    parser.add_argument("--limit", type=int, default=100, help="Quantidade de livros")
    parser.add_argument("--workers", type=int, default=10, help="Downloads paralelos")
    parser.add_argument("--output", default="books/raw", help="Pasta de saída")

    args = parser.parse_args()

    async with BookDownloader(Path(args.output), args.workers) as downloader:
        await downloader.run(args.start, args.limit)


if __name__ == "__main__":
    asyncio.run(main())
