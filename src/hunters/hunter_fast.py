# -*- coding: utf-8 -*-
"""
HUNTER_FAST.PY - Download Massivo Paralelo
===========================================
Baixa livros em massa sem verificação prévia.
Depois remove duplicados.

Fluxo:
1. Baixa TUDO para raw/ (paralelo, 10+ threads)
2. Analisa duplicados por hash/título
3. Move únicos para txt/
4. Limpa raw/
"""

import os
import sys
import csv
import gzip
import shutil
import hashlib
import requests
import unicodedata
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from tqdm import tqdm

# Config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import BASE_DIR, DATA_DIR, LOG_DIR

# Diretórios
RAW_DIR = BASE_DIR / "raw"
TXT_DIR = BASE_DIR / "txt"
GUTENBERG_CSV = DATA_DIR / "pg_catalog.csv"
GUTENBERG_CSV_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"

# Criar diretórios
RAW_DIR.mkdir(parents=True, exist_ok=True)
TXT_DIR.mkdir(parents=True, exist_ok=True)

# Logging
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"hunter_fast_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

HEADERS = {'User-Agent': 'Mozilla/5.0 BookHunterFast/1.0'}

@dataclass
class Book:
    id: str
    title: str
    author: str
    language: str
    url: str = ""

def sanitize_name(name: str, max_len: int = 80) -> str:
    """Limpa nome para uso em arquivos."""
    if not name:
        return "Unknown"
    name = unicodedata.normalize('NFKD', name)
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len] if len(name) > max_len else name

def get_file_hash(filepath: Path) -> str:
    """Calcula hash MD5 do arquivo."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

class FastHunter:
    """Hunter com download massivo paralelo."""

    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.books: List[Book] = []
        self.downloaded: Set[str] = set()
        self.failed: Set[str] = set()

    def download_catalog(self) -> bool:
        """Baixa catálogo do Gutenberg."""
        if GUTENBERG_CSV.exists():
            age_days = (datetime.now().timestamp() - GUTENBERG_CSV.stat().st_mtime) / 86400
            if age_days < 7:
                logger.info(f"Catálogo existente ({GUTENBERG_CSV.stat().st_size / 1024 / 1024:.1f} MB)")
                return True

        logger.info("Baixando catálogo Gutenberg...")
        gz_path = DATA_DIR / "pg_catalog.csv.gz"

        try:
            response = requests.get(GUTENBERG_CSV_URL, stream=True, headers=HEADERS, timeout=120)
            total = int(response.headers.get('content-length', 0))

            with open(gz_path, 'wb') as f:
                with tqdm(total=total, unit='B', unit_scale=True, desc="Catálogo") as pbar:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            # Descompacta
            logger.info("Descompactando...")
            with gzip.open(gz_path, 'rb') as f_in:
                with open(GUTENBERG_CSV, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

            gz_path.unlink()
            logger.info(f"Catálogo pronto: {GUTENBERG_CSV.stat().st_size / 1024 / 1024:.1f} MB")
            return True

        except Exception as e:
            logger.error(f"Erro ao baixar catálogo: {e}")
            return False

    def load_books(self, languages: List[str], limit: int = 1000) -> List[Book]:
        """Carrega livros do catálogo filtrados por idioma."""
        if not GUTENBERG_CSV.exists():
            if not self.download_catalog():
                return []

        books = []
        lang_set = set(languages)

        logger.info(f"Carregando livros ({languages}, limite={limit})...")

        with open(GUTENBERG_CSV, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)

            for row in reader:
                if len(books) >= limit:
                    break

                lang = row.get('Language', '').split(';')[0].strip().lower()
                if lang not in lang_set:
                    continue

                book_type = row.get('Type', '').lower()
                if 'text' not in book_type:
                    continue

                book_id = row.get('Text#', '')
                title = row.get('Title', 'Unknown')
                author = row.get('Authors', 'Unknown').split(';')[0].strip()

                if not book_id or not title:
                    continue

                # URL do texto
                url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"

                books.append(Book(
                    id=book_id,
                    title=sanitize_name(title),
                    author=sanitize_name(author.split(',')[0]),
                    language=lang,
                    url=url
                ))

        logger.info(f"Carregados {len(books)} livros")
        return books

    def download_single(self, book: Book) -> Optional[Path]:
        """Baixa um único livro para raw/."""
        filename = f"{book.author}_{book.title}_{book.id}.txt"
        filepath = RAW_DIR / filename

        if filepath.exists():
            return filepath

        try:
            response = requests.get(book.url, headers=HEADERS, timeout=30)

            if response.status_code == 200:
                content = response.text

                # Verifica se é texto válido
                if len(content) < 1000:
                    return None

                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)

                return filepath

        except Exception:
            pass

        return None

    def download_massive(self, books: List[Book]) -> Dict:
        """Download massivo paralelo."""
        logger.info(f"Iniciando download massivo de {len(books)} livros ({self.max_workers} threads)...")

        stats = {'success': 0, 'failed': 0}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.download_single, book): book for book in books}

            with tqdm(total=len(books), desc="Baixando", unit="livro") as pbar:
                for future in as_completed(futures):
                    book = futures[future]
                    try:
                        result = future.result()
                        if result:
                            stats['success'] += 1
                            self.downloaded.add(book.id)
                        else:
                            stats['failed'] += 1
                            self.failed.add(book.id)
                    except Exception:
                        stats['failed'] += 1
                        self.failed.add(book.id)

                    pbar.update(1)

        logger.info(f"Download completo: {stats['success']} OK, {stats['failed']} falhas")
        return stats

    def analyze_duplicates(self) -> Dict:
        """Analisa arquivos em raw/ e identifica duplicados."""
        logger.info("Analisando duplicados...")

        files = list(RAW_DIR.glob("*.txt"))
        logger.info(f"Arquivos em raw/: {len(files)}")

        # Hash -> filepath
        hashes: Dict[str, Path] = {}
        # Título normalizado -> filepath
        titles: Dict[str, Path] = {}

        duplicates = []
        unique = []

        for filepath in tqdm(files, desc="Analisando", unit="arquivo"):
            file_hash = get_file_hash(filepath)

            # Extrai título do nome do arquivo
            parts = filepath.stem.split('_')
            title_norm = parts[1].lower() if len(parts) > 1 else filepath.stem.lower()

            # Verifica duplicado por hash
            if file_hash in hashes:
                duplicates.append(filepath)
                continue

            # Verifica duplicado por título similar
            if title_norm in titles:
                duplicates.append(filepath)
                continue

            hashes[file_hash] = filepath
            titles[title_norm] = filepath
            unique.append(filepath)

        logger.info(f"Únicos: {len(unique)}, Duplicados: {len(duplicates)}")

        return {
            'unique': unique,
            'duplicates': duplicates,
            'total': len(files)
        }

    def move_to_txt(self, unique_files: List[Path]) -> int:
        """Move arquivos únicos para txt/ organizando por autor."""
        logger.info(f"Movendo {len(unique_files)} arquivos para txt/...")

        moved = 0

        for filepath in tqdm(unique_files, desc="Movendo", unit="arquivo"):
            parts = filepath.stem.split('_')

            if len(parts) >= 2:
                author = parts[0]
                title = parts[1]
            else:
                author = "Unknown"
                title = filepath.stem

            # Cria pasta do autor
            author_dir = TXT_DIR / author
            author_dir.mkdir(exist_ok=True)

            # Move arquivo
            dest = author_dir / f"{title}.txt"

            if not dest.exists():
                shutil.move(str(filepath), str(dest))
                moved += 1

        logger.info(f"Movidos: {moved}")
        return moved

    def cleanup_raw(self):
        """Limpa pasta raw/."""
        logger.info("Limpando raw/...")

        for f in RAW_DIR.glob("*"):
            if f.is_file():
                f.unlink()

        logger.info("raw/ limpo")

    def hunt(self, languages: List[str], limit: int = 500) -> Dict:
        """Executa caçada completa."""
        logger.info("="*70)
        logger.info("HUNTER FAST - Download Massivo")
        logger.info("="*70)

        # 1. Carrega livros
        books = self.load_books(languages, limit)
        if not books:
            return {'error': 'Nenhum livro encontrado'}

        # 2. Download massivo
        download_stats = self.download_massive(books)

        # 3. Analisa duplicados
        analysis = self.analyze_duplicates()

        # 4. Move únicos para txt/
        moved = self.move_to_txt(analysis['unique'])

        # 5. Limpa raw/
        self.cleanup_raw()

        # Resumo
        logger.info("="*70)
        logger.info("RESUMO FINAL")
        logger.info("="*70)
        logger.info(f"Baixados: {download_stats['success']}")
        logger.info(f"Falhas: {download_stats['failed']}")
        logger.info(f"Duplicados removidos: {len(analysis['duplicates'])}")
        logger.info(f"Movidos para txt/: {moved}")
        logger.info("="*70)

        return {
            'downloaded': download_stats['success'],
            'failed': download_stats['failed'],
            'duplicates': len(analysis['duplicates']),
            'moved': moved
        }

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Hunter Fast - Download Massivo Paralelo")
    parser.add_argument('--languages', '-l', nargs='+', default=['en', 'es'],
                       help='Idiomas (en, es, pt, fr, de)')
    parser.add_argument('--limit', '-n', type=int, default=500,
                       help='Limite de livros')
    parser.add_argument('--workers', '-w', type=int, default=10,
                       help='Threads paralelas')

    args = parser.parse_args()

    hunter = FastHunter(max_workers=args.workers)
    hunter.hunt(args.languages, args.limit)

    return 0

if __name__ == "__main__":
    sys.exit(main())
