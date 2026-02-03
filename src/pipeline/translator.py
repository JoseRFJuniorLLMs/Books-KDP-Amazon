#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MÓDULO 2: TRANSLATOR
====================
Traduz livros para português usando Gemini API.

Uso:
    python -m src.pipeline.translator --input books/raw/en --output books/txt/pt --workers 4

Entrada:
    books/raw/{idioma}/

Saída:
    books/txt/pt/
"""

import os
import sys
import json
import asyncio
import aiohttp
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Configuração
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
INPUT_DIR = Path("books/raw")
OUTPUT_DIR = Path("books/txt/pt")
MAX_CONCURRENT = 3
CHUNK_SIZE = 15000  # Caracteres por chunk


class BookTranslator:
    """Tradutor de livros paralelo usando Gemini."""

    def __init__(
        self,
        input_dir: Path = INPUT_DIR,
        output_dir: Path = OUTPUT_DIR,
        api_key: str = GEMINI_API_KEY,
        max_concurrent: int = MAX_CONCURRENT
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.api_key = api_key
        self.max_concurrent = max_concurrent
        self.session: Optional[aiohttp.ClientSession] = None
        self.translated = 0
        self.failed = 0
        self.stats = {"started": datetime.now().isoformat(), "books": []}

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, *args):
        if self.session:
            await self.session.close()

    def split_into_chunks(self, text: str, chunk_size: int = CHUNK_SIZE) -> List[str]:
        """Divide texto em chunks respeitando parágrafos."""
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = []
        current_size = 0

        for para in paragraphs:
            para_size = len(para)
            if current_size + para_size > chunk_size and current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size

        if current_chunk:
            chunks.append('\n\n'.join(current_chunk))

        return chunks

    async def translate_chunk(self, text: str, context: str = "") -> Optional[str]:
        """Traduz um chunk de texto usando Gemini."""
        if not self.api_key:
            print("[ERRO] GEMINI_API_KEY não configurada")
            return None

        prompt = f"""Traduza o seguinte texto para português brasileiro de forma fluente e natural.
Mantenha a formatação original (parágrafos, diálogos, etc).
NÃO adicione explicações ou comentários.
Apenas retorne o texto traduzido.

{context}

TEXTO PARA TRADUZIR:
{text}

TRADUÇÃO:"""

        try:
            async with self.session.post(
                f"{GEMINI_URL}?key={self.api_key}",
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "temperature": 0.3,
                        "maxOutputTokens": 8192
                    }
                },
                timeout=120
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    error = await resp.text()
                    print(f"[ERRO API] {resp.status}: {error[:200]}")
                    return None

        except Exception as e:
            print(f"[ERRO] Tradução falhou: {e}")
            return None

    async def translate_book(self, filepath: Path, semaphore: asyncio.Semaphore) -> Optional[Dict]:
        """Traduz um livro completo."""
        async with semaphore:
            try:
                print(f"[...] Traduzindo: {filepath.name}")

                # Ler arquivo
                content = filepath.read_text(encoding='utf-8', errors='ignore')

                # Dividir em chunks
                chunks = self.split_into_chunks(content)
                print(f"      {len(chunks)} chunks")

                # Traduzir cada chunk
                translated_chunks = []
                for i, chunk in enumerate(chunks):
                    context = f"Parte {i+1}/{len(chunks)} de um livro."
                    translated = await self.translate_chunk(chunk, context)

                    if translated:
                        translated_chunks.append(translated)
                        print(f"      Chunk {i+1}/{len(chunks)} OK")
                    else:
                        print(f"      Chunk {i+1}/{len(chunks)} FALHOU")
                        # Continuar com os outros chunks

                    # Rate limiting
                    await asyncio.sleep(1)

                if not translated_chunks:
                    self.failed += 1
                    return None

                # Juntar chunks traduzidos
                full_translation = '\n\n'.join(translated_chunks)

                # Criar pasta de saída
                self.output_dir.mkdir(parents=True, exist_ok=True)

                # Salvar
                output_name = filepath.stem + "_pt.txt"
                output_path = self.output_dir / output_name
                output_path.write_text(full_translation, encoding='utf-8')

                self.translated += 1
                print(f"[OK] {filepath.name} -> {output_name}")

                return {
                    "source": str(filepath),
                    "output": str(output_path),
                    "chunks": len(chunks),
                    "size": len(full_translation)
                }

            except Exception as e:
                self.failed += 1
                print(f"[ERRO] {filepath.name}: {e}")
                return None

    async def run(self, source_lang: str = "en", limit: int = 0):
        """Executa tradução de livros."""
        print(f"=== TRANSLATOR ===")
        print(f"Entrada: {self.input_dir / source_lang}")
        print(f"Saída: {self.output_dir}")
        print(f"Concorrência: {self.max_concurrent}")
        print()

        # Listar arquivos
        source_dir = self.input_dir / source_lang
        if not source_dir.exists():
            print(f"[ERRO] Pasta não encontrada: {source_dir}")
            return []

        files = list(source_dir.glob("*.txt"))
        if limit > 0:
            files = files[:limit]

        print(f"Arquivos encontrados: {len(files)}")
        print()

        # Traduzir em paralelo
        semaphore = asyncio.Semaphore(self.max_concurrent)
        tasks = [self.translate_book(f, semaphore) for f in files]
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r]

        self.stats["books"] = results
        self.stats["finished"] = datetime.now().isoformat()
        self.stats["translated"] = self.translated
        self.stats["failed"] = self.failed

        # Salvar estatísticas
        stats_file = self.output_dir / "translation_stats.json"
        stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        print()
        print(f"=== CONCLUÍDO ===")
        print(f"Traduzidos: {self.translated}")
        print(f"Falhas: {self.failed}")

        return results


async def main():
    parser = argparse.ArgumentParser(description="Traduzir livros para português")
    parser.add_argument("--input", default="books/raw", help="Pasta de entrada")
    parser.add_argument("--output", default="books/txt/pt", help="Pasta de saída")
    parser.add_argument("--lang", default="en", help="Idioma de origem")
    parser.add_argument("--limit", type=int, default=0, help="Limite de livros (0=todos)")
    parser.add_argument("--workers", type=int, default=3, help="Traduções paralelas")
    parser.add_argument("--api-key", help="Gemini API Key")

    args = parser.parse_args()

    api_key = args.api_key or os.getenv("GEMINI_API_KEY", "")

    async with BookTranslator(
        Path(args.input),
        Path(args.output),
        api_key,
        args.workers
    ) as translator:
        await translator.run(args.lang, args.limit)


if __name__ == "__main__":
    asyncio.run(main())
