# -*- coding: utf-8 -*-
"""
HUNTER V3 - Caçador de Livros Inteligente
==========================================
Melhorias:
- Verifica se livro já existe em txt/ antes de baixar
- Baixa e extrai texto automaticamente
- Organiza por autor/título
- Atualiza banco de dados
- Barra de progresso

Fontes: Project Gutenberg, Gutendex API
"""

import os
import re
import sys
import csv
import gzip
import time
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Set
from dataclasses import dataclass

import requests
from tqdm import tqdm

# Extração de texto
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False

try:
    import ebooklib
    from ebooklib import epub
    from bs4 import BeautifulSoup
    HAS_EBOOKLIB = True
except ImportError:
    HAS_EBOOKLIB = False

# Configurações
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    DATABASE_PATH, DATA_DIR, LOG_DIR,
    CALIBRE_DIR
)

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
TXT_DIR = BASE_DIR / "txt"
TRANSLATED_DIR = BASE_DIR / "translated"
TEMP_DIR = BASE_DIR / "temp_downloads"

GUTENBERG_CSV = DATA_DIR / "pg_catalog.csv"
GUTENBERG_CSV_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"
GUTENDEX_API = "https://gutendex.com/books"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) BookHunter/3.0'
}

# Criar diretórios
for d in [TXT_DIR, TRANSLATED_DIR, TEMP_DIR, DATA_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"hunter_{datetime.now().strftime('%Y%m%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASS
# ============================================================================

@dataclass
class Book:
    id: str
    title: str
    author: str
    language: str
    formats: Dict[str, str]
    source: str = "gutenberg"

# ============================================================================
# FUNÇÕES DE UTILIDADE
# ============================================================================

def sanitize_name(name: str, max_len: int = 80) -> str:
    """Limpa nome para usar como arquivo/pasta."""
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if len(name) > max_len:
        name = name[:max_len].rsplit(' ', 1)[0]
    return name or "Unknown"


def normalize_for_search(text: str) -> str:
    """Normaliza texto para busca."""
    import unicodedata
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.lower().strip()

# ============================================================================
# VERIFICADOR DE LIVROS EXISTENTES
# ============================================================================

class ExistingBooksChecker:
    """Verifica livros já existentes em txt/ e translated/."""

    def __init__(self):
        self.existing_books: Set[str] = set()
        self.existing_by_author: Dict[str, Set[str]] = {}
        self._scan_directories()

    def _scan_directories(self):
        """Escaneia diretórios para encontrar livros existentes."""
        logger.info("Escaneando livros existentes...")

        for directory in [TXT_DIR, TRANSLATED_DIR]:
            if not directory.exists():
                continue

            for txt_file in directory.rglob("*.txt"):
                # Normaliza título para busca
                title_norm = normalize_for_search(txt_file.stem)
                self.existing_books.add(title_norm)

                # Agrupa por autor (pasta pai)
                author = txt_file.parent.name
                author_norm = normalize_for_search(author)

                if author_norm not in self.existing_by_author:
                    self.existing_by_author[author_norm] = set()
                self.existing_by_author[author_norm].add(title_norm)

        logger.info(f"Encontrados {len(self.existing_books)} livros existentes")

    def book_exists(self, title: str, author: str = None) -> bool:
        """Verifica se um livro já existe."""
        title_norm = normalize_for_search(title)

        # Busca exata
        if title_norm in self.existing_books:
            return True

        # Busca parcial (título contido)
        for existing in self.existing_books:
            # Se 80% do título bate
            if len(title_norm) > 10:
                if title_norm[:len(title_norm)//2] in existing or existing[:len(existing)//2] in title_norm:
                    return True

        # Busca por autor + título parcial
        if author:
            author_norm = normalize_for_search(author)
            for auth_key, titles in self.existing_by_author.items():
                if author_norm in auth_key or auth_key in author_norm:
                    for t in titles:
                        if title_norm[:20] in t or t[:20] in title_norm:
                            return True

        return False

    def add_book(self, title: str, author: str):
        """Registra um novo livro como existente."""
        title_norm = normalize_for_search(title)
        author_norm = normalize_for_search(author)

        self.existing_books.add(title_norm)

        if author_norm not in self.existing_by_author:
            self.existing_by_author[author_norm] = set()
        self.existing_by_author[author_norm].add(title_norm)

# ============================================================================
# EXTRAÇÃO DE TEXTO
# ============================================================================

def extract_text_from_epub(epub_path: Path) -> Optional[str]:
    """Extrai texto de EPUB."""
    if not HAS_EBOOKLIB:
        logger.warning("ebooklib não instalado")
        return None

    try:
        book = epub.read_epub(str(epub_path), options={'ignore_ncx': True})
        texts = []

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                soup = BeautifulSoup(item.get_content(), 'html.parser')
                for tag in soup(['script', 'style']):
                    tag.decompose()
                text = soup.get_text(separator='\n\n')
                if text.strip():
                    texts.append(text.strip())

        return '\n\n'.join(texts) if texts else None
    except Exception as e:
        logger.error(f"Erro EPUB: {e}")
        return None


def extract_text_from_pdf(pdf_path: Path) -> Optional[str]:
    """Extrai texto de PDF."""
    if not HAS_PYMUPDF:
        logger.warning("PyMuPDF não instalado")
        return None

    try:
        doc = fitz.open(str(pdf_path))
        texts = []

        for page in doc:
            text = page.get_text()
            if text.strip():
                texts.append(text.strip())

        doc.close()
        return '\n\n'.join(texts) if texts else None
    except Exception as e:
        logger.error(f"Erro PDF: {e}")
        return None


def extract_text_from_txt(txt_path: Path) -> Optional[str]:
    """Lê arquivo TXT."""
    try:
        # Tenta diferentes encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                with open(txt_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        return None
    except Exception as e:
        logger.error(f"Erro TXT: {e}")
        return None

# ============================================================================
# CATÁLOGO GUTENBERG
# ============================================================================

class GutenbergCatalog:
    """Gerencia catálogo do Project Gutenberg."""

    def __init__(self):
        self.books: Dict[str, Book] = {}
        self.authors: Dict[str, List[str]] = {}  # autor -> lista de book_ids

    def download_catalog(self, force: bool = False) -> bool:
        """Baixa catálogo CSV."""
        if GUTENBERG_CSV.exists() and not force:
            age = time.time() - GUTENBERG_CSV.stat().st_mtime
            if age < 7 * 24 * 3600:
                logger.info(f"Catálogo existente: {GUTENBERG_CSV.stat().st_size / 1024 / 1024:.1f} MB")
                return True

        logger.info("Baixando catálogo do Gutenberg...")
        gz_path = DATA_DIR / "pg_catalog.csv.gz"

        try:
            response = requests.get(GUTENBERG_CSV_URL, stream=True, headers=HEADERS, timeout=60)
            total = int(response.headers.get('content-length', 0))

            with open(gz_path, 'wb') as f:
                with tqdm(total=total, unit='B', unit_scale=True, desc="Baixando") as pbar:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            logger.info("Descompactando...")
            with gzip.open(gz_path, 'rb') as f_in:
                with open(GUTENBERG_CSV, 'wb') as f_out:
                    f_out.write(f_in.read())

            gz_path.unlink(missing_ok=True)
            return True
        except Exception as e:
            logger.error(f"Erro: {e}")
            return False

    def parse_author(self, author_str: str) -> str:
        """Extrai nome do autor."""
        if not author_str:
            return "Unknown"

        # Remove anos
        name = re.sub(r',?\s*\d{4}\s*-\s*\d{4}?', '', author_str).strip()
        name = re.sub(r',?\s*-\s*$', '', name).strip()

        # Reorganiza "Sobrenome, Nome" para "Nome Sobrenome"
        if ',' in name:
            parts = name.split(',', 1)
            if len(parts) == 2:
                name = f"{parts[1].strip()} {parts[0].strip()}"

        return name

    def load_catalog(self, languages: List[str] = None) -> bool:
        """Carrega catálogo filtrado por idiomas."""
        if not GUTENBERG_CSV.exists():
            if not self.download_catalog():
                return False

        logger.info(f"Carregando catálogo (idiomas: {languages or 'todos'})...")

        try:
            with open(GUTENBERG_CSV, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)

                for row in tqdm(reader, desc="Processando", unit=" livros"):
                    try:
                        if row.get('Type') != 'Text':
                            continue

                        book_id = row.get('Text#', '')
                        title = row.get('Title', '').strip()
                        author_str = row.get('Authors', '').strip()
                        language = row.get('Language', 'en').strip()

                        if not book_id or not title:
                            continue

                        # Filtra por idioma
                        if languages and language not in languages:
                            continue

                        author = self.parse_author(author_str)

                        formats = {
                            'epub': f"https://www.gutenberg.org/ebooks/{book_id}.epub.images",
                            'txt': f"https://www.gutenberg.org/ebooks/{book_id}.txt.utf-8",
                        }

                        book = Book(
                            id=book_id,
                            title=title,
                            author=author,
                            language=language,
                            formats=formats
                        )

                        self.books[book_id] = book

                        if author not in self.authors:
                            self.authors[author] = []
                        self.authors[author].append(book_id)

                    except Exception:
                        continue

            logger.info(f"Carregados: {len(self.books)} livros, {len(self.authors)} autores")
            return True
        except Exception as e:
            logger.error(f"Erro: {e}")
            return False

    def get_books_by_language(self, language: str, limit: int = None) -> List[Book]:
        """Retorna livros de um idioma."""
        books = [b for b in self.books.values() if b.language == language]
        if limit:
            books = books[:limit]
        return books

# ============================================================================
# HUNTER PRINCIPAL
# ============================================================================

class SmartHunter:
    """Caçador inteligente que verifica existência antes de baixar."""

    def __init__(self):
        self.catalog = GutenbergCatalog()
        self.checker = ExistingBooksChecker()
        self.stats = {"downloaded": 0, "skipped": 0, "failed": 0, "extracted": 0}

    def download_and_extract(self, book: Book) -> bool:
        """Baixa livro e extrai texto para txt/."""
        author_clean = sanitize_name(book.author)
        title_clean = sanitize_name(book.title)

        # Verifica se já existe
        if self.checker.book_exists(book.title, book.author):
            logger.debug(f"Já existe: {title_clean}")
            self.stats["skipped"] += 1
            return False

        # Pasta de destino
        output_dir = TXT_DIR / author_clean
        output_dir.mkdir(parents=True, exist_ok=True)
        txt_path = output_dir / f"{title_clean}.txt"

        if txt_path.exists():
            self.stats["skipped"] += 1
            return False

        logger.info(f"Baixando: {title_clean[:50]}...")

        # Tenta baixar TXT direto primeiro (mais rápido)
        if 'txt' in book.formats:
            text = self._download_and_read_txt(book.formats['txt'])
            if text and len(text) > 1000:
                with open(txt_path, 'w', encoding='utf-8') as f:
                    f.write(text)
                self.checker.add_book(book.title, book.author)
                self.stats["downloaded"] += 1
                self.stats["extracted"] += 1
                logger.info(f"✓ {author_clean}/{title_clean}.txt ({len(text):,} chars)")
                return True

        # Tenta EPUB
        if 'epub' in book.formats and HAS_EBOOKLIB:
            temp_epub = TEMP_DIR / f"{book.id}.epub"
            if self._download_file(book.formats['epub'], temp_epub):
                text = extract_text_from_epub(temp_epub)
                temp_epub.unlink(missing_ok=True)

                if text and len(text) > 1000:
                    with open(txt_path, 'w', encoding='utf-8') as f:
                        f.write(text)
                    self.checker.add_book(book.title, book.author)
                    self.stats["downloaded"] += 1
                    self.stats["extracted"] += 1
                    logger.info(f"✓ {author_clean}/{title_clean}.txt ({len(text):,} chars)")
                    return True

        self.stats["failed"] += 1
        return False

    def _download_and_read_txt(self, url: str) -> Optional[str]:
        """Baixa e lê TXT diretamente."""
        try:
            response = requests.get(url, headers=HEADERS, timeout=60, allow_redirects=True)
            if response.status_code == 200:
                return response.text
        except Exception as e:
            logger.debug(f"Erro TXT: {e}")
        return None

    def _download_file(self, url: str, output_path: Path) -> bool:
        """Baixa arquivo."""
        try:
            response = requests.get(url, headers=HEADERS, stream=True, timeout=120, allow_redirects=True)
            if response.status_code != 200:
                return False

            with open(output_path, 'wb') as f:
                for chunk in response.iter_content(8192):
                    f.write(chunk)

            return output_path.exists() and output_path.stat().st_size > 1000
        except Exception as e:
            logger.debug(f"Erro download: {e}")
            return False

    def hunt_by_language(self, languages: List[str], limit_per_lang: int = 100):
        """Caça livros por idioma."""
        logger.info("="*60)
        logger.info(f"HUNTER V3 - Caçando livros")
        logger.info(f"Idiomas: {languages}")
        logger.info(f"Limite por idioma: {limit_per_lang}")
        logger.info("="*60)

        # Carrega catálogo filtrado
        if not self.catalog.load_catalog(languages=languages):
            logger.error("Falha ao carregar catálogo")
            return

        for lang in languages:
            books = self.catalog.get_books_by_language(lang, limit=limit_per_lang * 2)

            logger.info(f"\n--- Idioma: {lang.upper()} ({len(books)} disponíveis) ---")

            downloaded = 0
            with tqdm(total=limit_per_lang, desc=f"[{lang}]", unit="livro") as pbar:
                for book in books:
                    if downloaded >= limit_per_lang:
                        break

                    if self.download_and_extract(book):
                        downloaded += 1
                        pbar.update(1)

                    time.sleep(0.5)  # Rate limiting

        # Resumo
        logger.info("\n" + "="*60)
        logger.info("RESUMO")
        logger.info(f"Baixados: {self.stats['downloaded']}")
        logger.info(f"Extraídos: {self.stats['extracted']}")
        logger.info(f"Pulados (já existem): {self.stats['skipped']}")
        logger.info(f"Falhas: {self.stats['failed']}")
        logger.info(f"Pasta: {TXT_DIR}")
        logger.info("="*60)

    def hunt_author(self, author_name: str, limit: int = 20):
        """Caça livros de um autor específico."""
        logger.info(f"Buscando livros de: {author_name}")

        # Carrega catálogo completo
        if not self.catalog.load_catalog():
            return

        # Busca autor
        books = []
        author_lower = author_name.lower()

        for author, book_ids in self.catalog.authors.items():
            if author_lower in author.lower():
                for bid in book_ids:
                    if bid in self.catalog.books:
                        books.append(self.catalog.books[bid])

        if not books:
            logger.warning(f"Nenhum livro encontrado para: {author_name}")
            return

        logger.info(f"Encontrados {len(books)} livros")

        downloaded = 0
        with tqdm(total=min(limit, len(books)), desc=author_name[:20], unit="livro") as pbar:
            for book in books[:limit * 2]:
                if downloaded >= limit:
                    break

                if self.download_and_extract(book):
                    downloaded += 1
                    pbar.update(1)

                time.sleep(0.5)

        logger.info(f"Baixados: {downloaded} de {author_name}")

# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="HUNTER V3 - Caçador Inteligente de Livros")
    parser.add_argument('--languages', '-L', nargs='+', default=['en', 'es', 'ru'],
                       help='Idiomas para baixar (en, es, ru, fr, de, pt)')
    parser.add_argument('--limit', '-l', type=int, default=50,
                       help='Limite de livros por idioma')
    parser.add_argument('--author', '-a', type=str,
                       help='Baixa livros de um autor específico')
    parser.add_argument('--init', action='store_true',
                       help='Apenas baixa/atualiza catálogo')

    args = parser.parse_args()

    hunter = SmartHunter()

    if args.init:
        hunter.catalog.download_catalog(force=True)
        return 0

    if args.author:
        hunter.hunt_author(args.author, limit=args.limit)
    else:
        hunter.hunt_by_language(args.languages, limit_per_lang=args.limit)

    return 0


if __name__ == "__main__":
    sys.exit(main())
