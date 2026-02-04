#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MÓDULO 2: TRANSLATOR (Cloud Translation API)
=============================================
Traduz livros usando Google Cloud Translation API (rápido e barato).

Uso:
    python -m src.pipeline.translator --input books/txt/en --output books/txt/pt --workers 10
"""

import asyncio
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import json

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Configuracao centralizada
from config.settings import PROJECT_ID, INPUT_TXT_DIR, TRANSLATED_DIR

# Google Cloud Translation
from google.cloud import translate_v2 as translate

INPUT_DIR = INPUT_TXT_DIR
OUTPUT_DIR = TRANSLATED_DIR
MAX_WORKERS = 10
CHUNK_SIZE = 5000  # Cloud Translation limite ~5000 chars


class BookTranslator:
    """Tradutor usando Cloud Translation API."""

    def __init__(
        self,
        input_dir: Path = INPUT_DIR,
        output_dir: Path = OUTPUT_DIR,
        target_lang: str = "pt",
        max_workers: int = MAX_WORKERS
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.target_lang = target_lang
        self.max_workers = max_workers
        self.client = translate.Client()
        self.translated = 0
        self.failed = 0
        self.stats = {"started": datetime.now().isoformat(), "books": []}

    def detect_language(self, text: str) -> str:
        """Detecta idioma do texto."""
        try:
            result = self.client.detect_language(text[:1000])
            return result["language"]
        except:
            return "en"

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

        return chunks if chunks else [text]

    def translate_chunk(self, text: str, source_lang: str = None) -> str:
        """Traduz um chunk usando Cloud Translation API."""
        try:
            result = self.client.translate(
                text,
                target_language=self.target_lang,
                source_language=source_lang,
                format_="text"
            )
            return result["translatedText"]
        except Exception as e:
            print(f"    Erro: {e}")
            return text  # Retorna original se falhar

    def translate_book(self, filepath: Path) -> Optional[Dict]:
        """Traduz um livro completo."""
        try:
            print(f"[...] {filepath.name[:50]}")

            # Lê arquivo
            content = filepath.read_text(encoding='utf-8', errors='ignore')

            if len(content) < 500:
                print(f"      Muito curto, pulando")
                return None

            # Detecta idioma
            source_lang = self.detect_language(content)
            print(f"      Idioma: {source_lang}")

            # Se já é PT, não traduz
            if source_lang == self.target_lang:
                print(f"      Já está em {self.target_lang}, copiando")
                self.output_dir.mkdir(parents=True, exist_ok=True)
                output_path = self.output_dir / filepath.name
                output_path.write_text(content, encoding='utf-8')
                self.translated += 1
                return {"source": str(filepath), "output": str(output_path), "translated": False}

            # Divide em chunks
            chunks = self.split_into_chunks(content)
            print(f"      {len(chunks)} chunks")

            # Traduz cada chunk
            translated_chunks = []
            for i, chunk in enumerate(chunks):
                translated = self.translate_chunk(chunk, source_lang)
                translated_chunks.append(translated)

                if (i + 1) % 10 == 0:
                    print(f"      Chunk {i+1}/{len(chunks)}")

            # Junta chunks
            full_translation = '\n\n'.join(translated_chunks)

            # Salva
            self.output_dir.mkdir(parents=True, exist_ok=True)
            output_name = filepath.stem + f"_{self.target_lang}.txt"
            output_path = self.output_dir / output_name
            output_path.write_text(full_translation, encoding='utf-8')

            self.translated += 1
            print(f"[OK] {output_name}")

            return {
                "source": str(filepath),
                "output": str(output_path),
                "source_lang": source_lang,
                "chunks": len(chunks),
                "size": len(full_translation),
                "translated": True
            }

        except Exception as e:
            self.failed += 1
            print(f"[ERRO] {filepath.name}: {e}")
            return None

    def run(self, source_lang: str = None, limit: int = 0) -> List[Dict]:
        """Executa tradução de livros."""
        print("=" * 60)
        print("TRANSLATOR - Cloud Translation API")
        print("=" * 60)
        print(f"Entrada: {self.input_dir}")
        print(f"Saída: {self.output_dir}")
        print(f"Idioma alvo: {self.target_lang}")
        print(f"Workers: {self.max_workers}")
        print()

        # Lista arquivos
        if source_lang:
            source_dir = self.input_dir / source_lang
        else:
            source_dir = self.input_dir

        files = list(source_dir.rglob("*.txt"))

        # Filtra já traduzidos
        existing = set(f.stem for f in self.output_dir.glob("*.txt")) if self.output_dir.exists() else set()
        files = [f for f in files if f.stem not in existing and f"{f.stem}_{self.target_lang}" not in existing]

        if limit > 0:
            files = files[:limit]

        print(f"Arquivos para traduzir: {len(files)}")
        print()

        # Traduz em paralelo
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            results = list(executor.map(self.translate_book, files))

        results = [r for r in results if r]

        # Estatísticas
        self.stats["books"] = results
        self.stats["finished"] = datetime.now().isoformat()
        self.stats["translated"] = self.translated
        self.stats["failed"] = self.failed

        # Salva estatísticas
        self.output_dir.mkdir(parents=True, exist_ok=True)
        stats_file = self.output_dir / "translation_stats.json"
        stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        print()
        print("=" * 60)
        print(f"Traduzidos: {self.translated}")
        print(f"Falhas: {self.failed}")
        print("=" * 60)

        return results


# Wrapper async para compatibilidade com orchestrator
async def run_async(translator, source_lang, limit):
    return translator.run(source_lang, limit)


def main():
    parser = argparse.ArgumentParser(description="Traduzir livros (Cloud Translation API)")
    parser.add_argument("--input", default="books/txt", help="Pasta de entrada")
    parser.add_argument("--output", default="books/txt/pt", help="Pasta de saída")
    parser.add_argument("--lang", default=None, help="Idioma de origem (None=todos)")
    parser.add_argument("--target", default="pt", help="Idioma alvo")
    parser.add_argument("--limit", type=int, default=0, help="Limite de livros")
    parser.add_argument("--workers", type=int, default=10, help="Traduções paralelas")

    args = parser.parse_args()

    translator = BookTranslator(
        Path(args.input),
        Path(args.output),
        args.target,
        args.workers
    )
    translator.run(args.lang, args.limit)


if __name__ == "__main__":
    main()
