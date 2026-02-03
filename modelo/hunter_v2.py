# -*- coding: utf-8 -*-
"""
HUNTER V2 - Caçador de Livros com Base de Dados Real
=====================================================
Usa o catálogo OFICIAL do Project Gutenberg (89,000+ livros)
+ APIs do Open Library, Archive.org, Gutendex

Fontes de dados:
- Project Gutenberg CSV: https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz
- Gutendex API: https://gutendex.com/books
- Open Library API: https://openlibrary.org/developers/api
- Archive.org API: https://archive.org/advancedsearch.php

DOMÍNIO PÚBLICO garantido!
"""

import os
import re
import csv
import gzip
import sys
import time
import json
import logging
import hashlib
import urllib.request
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Set
from dataclasses import dataclass
from collections import defaultdict

import requests
from tqdm import tqdm

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
CALIBRE_DIR = BASE_DIR.parent / "CALIBRE"
DATA_DIR = BASE_DIR / "modelo" / "data"
LOG_DIR = BASE_DIR / "logs"
CACHE_DIR = BASE_DIR / "modelo" / "cache"

# Criar diretórios
for d in [CALIBRE_DIR, DATA_DIR, LOG_DIR, CACHE_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Arquivos de dados
GUTENBERG_CSV = DATA_DIR / "pg_catalog.csv"
GUTENBERG_CSV_GZ = DATA_DIR / "pg_catalog.csv.gz"
AUTHORS_DB = DATA_DIR / "authors.json"
BOOKS_DB = DATA_DIR / "books.json"
DOWNLOADED_LOG = LOG_DIR / "downloaded.log"

# URLs
GUTENBERG_CSV_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"
GUTENDEX_API = "https://gutendex.com/books"
OPENLIBRARY_API = "https://openlibrary.org"
ARCHIVE_API = "https://archive.org/advancedsearch.php"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) BookHunter/2.0',
}

# ============================================================================
# LOGGING
# ============================================================================

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
# DATA CLASSES
# ============================================================================

@dataclass
class Author:
    name: str
    birth_year: Optional[int] = None
    death_year: Optional[int] = None
    books_count: int = 0
    nationality: str = ""

    def is_public_domain(self) -> bool:
        """Verifica se o autor está em domínio público (morto há 70+ anos)."""
        if self.death_year is None:
            return False
        current_year = datetime.now().year
        return (current_year - self.death_year) >= 70

@dataclass
class Book:
    id: str
    title: str
    author: str
    language: str
    subjects: List[str]
    formats: Dict[str, str]  # formato -> URL
    source: str
    issued: str = ""

# ============================================================================
# GUTENBERG CATALOG MANAGER
# ============================================================================

class GutenbergCatalog:
    """Gerencia o catálogo do Project Gutenberg."""

    def __init__(self):
        self.books: Dict[str, Book] = {}
        self.authors: Dict[str, Author] = {}
        self.author_books: Dict[str, List[str]] = defaultdict(list)  # autor -> lista de book_ids

    def download_catalog(self, force: bool = False) -> bool:
        """Baixa o catálogo CSV do Gutenberg."""
        if GUTENBERG_CSV.exists() and not force:
            # Verifica se tem mais de 7 dias
            age = time.time() - GUTENBERG_CSV.stat().st_mtime
            if age < 7 * 24 * 3600:
                logger.info(f"Catálogo existente ({GUTENBERG_CSV.stat().st_size / 1024 / 1024:.1f} MB)")
                return True

        logger.info("Baixando catálogo do Project Gutenberg...")

        try:
            # Download com progresso
            response = requests.get(GUTENBERG_CSV_URL, stream=True, headers=HEADERS, timeout=60)
            total = int(response.headers.get('content-length', 0))

            with open(GUTENBERG_CSV_GZ, 'wb') as f:
                with tqdm(total=total, unit='B', unit_scale=True, desc="Baixando") as pbar:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                        pbar.update(len(chunk))

            # Descompacta
            logger.info("Descompactando...")
            with gzip.open(GUTENBERG_CSV_GZ, 'rb') as f_in:
                with open(GUTENBERG_CSV, 'wb') as f_out:
                    f_out.write(f_in.read())

            GUTENBERG_CSV_GZ.unlink()  # Remove arquivo compactado
            logger.info(f"Catálogo salvo: {GUTENBERG_CSV}")
            return True

        except Exception as e:
            logger.error(f"Erro ao baixar catálogo: {e}")
            return False

    def parse_author(self, author_str: str) -> Tuple[str, Optional[int], Optional[int]]:
        """
        Parse string de autor do Gutenberg.
        Formato: "Nome, Sobrenome, YYYY-YYYY" ou "Nome, Sobrenome"
        """
        if not author_str:
            return "Unknown", None, None

        # Extrai anos de vida
        match = re.search(r'(\d{4})\s*-\s*(\d{4})?', author_str)
        birth_year = None
        death_year = None

        if match:
            birth_year = int(match.group(1))
            if match.group(2):
                death_year = int(match.group(2))

        # Remove anos do nome
        name = re.sub(r',?\s*\d{4}\s*-\s*\d{4}?', '', author_str).strip()
        name = re.sub(r',?\s*-\s*$', '', name).strip()

        # Reorganiza "Sobrenome, Nome" para "Nome Sobrenome"
        if ',' in name:
            parts = name.split(',', 1)
            if len(parts) == 2:
                name = f"{parts[1].strip()} {parts[0].strip()}"

        return name, birth_year, death_year

    def load_catalog(self) -> bool:
        """Carrega o catálogo CSV."""
        if not GUTENBERG_CSV.exists():
            if not self.download_catalog():
                return False

        logger.info("Carregando catálogo...")

        try:
            with open(GUTENBERG_CSV, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)

                for row in tqdm(reader, desc="Processando", unit=" livros"):
                    try:
                        # Filtra apenas textos (não audiobooks, etc.)
                        if row.get('Type') != 'Text':
                            continue

                        book_id = row.get('Text#', '')
                        title = row.get('Title', '').strip()
                        author_str = row.get('Authors', '').strip()
                        language = row.get('Language', 'en').strip()
                        subjects = row.get('Subjects', '').split(';')
                        issued = row.get('Issued', '')

                        if not book_id or not title:
                            continue

                        # Parse autor
                        author_name, birth_year, death_year = self.parse_author(author_str)

                        # Adiciona autor se não existir
                        if author_name and author_name != "Unknown":
                            if author_name not in self.authors:
                                self.authors[author_name] = Author(
                                    name=author_name,
                                    birth_year=birth_year,
                                    death_year=death_year,
                                    books_count=0
                                )
                            self.authors[author_name].books_count += 1

                            # Atualiza anos se não tinha
                            if birth_year and not self.authors[author_name].birth_year:
                                self.authors[author_name].birth_year = birth_year
                            if death_year and not self.authors[author_name].death_year:
                                self.authors[author_name].death_year = death_year

                        # URLs de download do Gutenberg
                        formats = {
                            'epub': f"https://www.gutenberg.org/ebooks/{book_id}.epub.images",
                            'epub_no_images': f"https://www.gutenberg.org/ebooks/{book_id}.epub.noimages",
                            'kindle': f"https://www.gutenberg.org/ebooks/{book_id}.kf8.images",
                            'html': f"https://www.gutenberg.org/ebooks/{book_id}.html.images",
                            'txt': f"https://www.gutenberg.org/ebooks/{book_id}.txt.utf-8",
                        }

                        book = Book(
                            id=book_id,
                            title=title,
                            author=author_name,
                            language=language,
                            subjects=[s.strip() for s in subjects if s.strip()],
                            formats=formats,
                            source="gutenberg",
                            issued=issued
                        )

                        self.books[book_id] = book
                        self.author_books[author_name].append(book_id)

                    except Exception as e:
                        continue

            logger.info(f"Carregados: {len(self.books)} livros, {len(self.authors)} autores")
            return True

        except Exception as e:
            logger.error(f"Erro ao carregar catálogo: {e}")
            return False

    def save_databases(self):
        """Salva bases de dados processadas em JSON."""
        logger.info("Salvando bases de dados...")

        # Salva autores
        authors_data = {
            name: {
                'name': a.name,
                'birth_year': a.birth_year,
                'death_year': a.death_year,
                'books_count': a.books_count,
                'public_domain': a.is_public_domain()
            }
            for name, a in self.authors.items()
        }

        with open(AUTHORS_DB, 'w', encoding='utf-8') as f:
            json.dump(authors_data, f, ensure_ascii=False, indent=2)

        logger.info(f"Autores salvos: {AUTHORS_DB}")

    def get_public_domain_authors(self, min_books: int = 1) -> List[Author]:
        """Retorna autores em domínio público."""
        return [
            a for a in self.authors.values()
            if a.is_public_domain() and a.books_count >= min_books
        ]

    def get_books_by_author(self, author_name: str) -> List[Book]:
        """Retorna livros de um autor."""
        book_ids = self.author_books.get(author_name, [])
        return [self.books[bid] for bid in book_ids if bid in self.books]

    def search_books(self, query: str, language: str = None, limit: int = 100) -> List[Book]:
        """Busca livros por título ou autor."""
        query_lower = query.lower()
        results = []

        for book in self.books.values():
            if query_lower in book.title.lower() or query_lower in book.author.lower():
                if language and book.language != language:
                    continue
                results.append(book)
                if len(results) >= limit:
                    break

        return results

    def get_top_authors(self, limit: int = 100, public_domain_only: bool = True) -> List[Author]:
        """Retorna os autores com mais livros."""
        authors = list(self.authors.values())

        if public_domain_only:
            authors = [a for a in authors if a.is_public_domain()]

        authors.sort(key=lambda a: a.books_count, reverse=True)
        return authors[:limit]

# ============================================================================
# GUTENDEX API (Complementar)
# ============================================================================

class GutendexAPI:
    """API do Gutendex para buscas em tempo real."""

    BASE_URL = "https://gutendex.com/books"

    def search(self, query: str = None, author: str = None, language: str = None,
               topic: str = None, page: int = 1) -> List[Book]:
        """Busca livros na API."""
        params = {'page': page}

        if query:
            params['search'] = query
        if author:
            params['author'] = author
        if language:
            params['languages'] = language
        if topic:
            params['topic'] = topic

        try:
            response = requests.get(self.BASE_URL, params=params, headers=HEADERS, timeout=30)
            if response.status_code != 200:
                return []

            data = response.json()
            books = []

            for item in data.get('results', []):
                authors = item.get('authors', [])
                author_name = authors[0].get('name', 'Unknown') if authors else 'Unknown'

                # Pega URLs
                formats = {}
                for fmt, url in item.get('formats', {}).items():
                    if 'epub' in fmt.lower():
                        formats['epub'] = url
                    elif 'pdf' in fmt.lower():
                        formats['pdf'] = url
                    elif 'text/plain' in fmt.lower():
                        formats['txt'] = url

                if not formats:
                    continue

                books.append(Book(
                    id=str(item.get('id', '')),
                    title=item.get('title', 'Unknown'),
                    author=author_name,
                    language=item.get('languages', ['en'])[0] if item.get('languages') else 'en',
                    subjects=item.get('subjects', []),
                    formats=formats,
                    source="gutendex"
                ))

            return books

        except Exception as e:
            logger.error(f"Erro na API Gutendex: {e}")
            return []

# ============================================================================
# OPEN LIBRARY API
# ============================================================================

class OpenLibraryAPI:
    """API do Open Library para metadados e buscas."""

    BASE_URL = "https://openlibrary.org"

    def search_author(self, author_name: str, limit: int = 50) -> List[Dict]:
        """Busca obras de um autor."""
        try:
            params = {
                'author': author_name,
                'limit': limit,
                'has_fulltext': 'true'
            }

            response = requests.get(
                f"{self.BASE_URL}/search.json",
                params=params,
                headers=HEADERS,
                timeout=30
            )

            if response.status_code != 200:
                return []

            data = response.json()
            return data.get('docs', [])

        except Exception as e:
            logger.error(f"Erro na Open Library: {e}")
            return []

    def get_author_works(self, author_key: str) -> List[Dict]:
        """Obtém todas as obras de um autor pelo key."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/authors/{author_key}/works.json",
                headers=HEADERS,
                timeout=30
            )

            if response.status_code != 200:
                return []

            data = response.json()
            return data.get('entries', [])

        except Exception as e:
            logger.error(f"Erro ao buscar obras: {e}")
            return []

# ============================================================================
# DOWNLOADER
# ============================================================================

class BookDownloader:
    """Gerencia downloads de livros."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._load_downloaded()

    def _load_downloaded(self):
        """Carrega histórico de downloads."""
        self.downloaded = set()
        if DOWNLOADED_LOG.exists():
            with open(DOWNLOADED_LOG, 'r', encoding='utf-8') as f:
                for line in f:
                    parts = line.strip().split('|')
                    if parts:
                        self.downloaded.add(parts[0])

    def _mark_downloaded(self, book_id: str, path: Path):
        """Registra download."""
        with open(DOWNLOADED_LOG, 'a', encoding='utf-8') as f:
            f.write(f"{book_id}|{path}|{datetime.now().isoformat()}\n")
        self.downloaded.add(book_id)

    def _sanitize(self, name: str, max_len: int = 80) -> str:
        """Limpa nome para usar como arquivo/pasta."""
        # Remove caracteres inválidos
        name = re.sub(r'[<>:"/\\|?*\n\r\t]', '', name)
        # Remove espaços extras
        name = re.sub(r'\s+', ' ', name).strip()
        # Limita tamanho
        if len(name) > max_len:
            name = name[:max_len].rsplit(' ', 1)[0]
        return name or "Unknown"

    def download(self, book: Book, preferred_format: str = 'epub') -> Optional[Path]:
        """Baixa um livro."""
        # Verifica se já baixou
        if book.id in self.downloaded:
            logger.debug(f"Já baixado: {book.title}")
            return None

        # Escolhe formato
        url = None
        ext = preferred_format

        if preferred_format in book.formats:
            url = book.formats[preferred_format]
        elif 'epub' in book.formats:
            url = book.formats['epub']
            ext = 'epub'
        elif 'epub_no_images' in book.formats:
            url = book.formats['epub_no_images']
            ext = 'epub'
        elif 'txt' in book.formats:
            url = book.formats['txt']
            ext = 'txt'
        else:
            # Pega primeiro disponível
            for fmt, u in book.formats.items():
                url = u
                ext = fmt.split('_')[0]
                break

        if not url:
            logger.warning(f"Sem URL para: {book.title}")
            return None

        # Prepara caminhos
        author_clean = self._sanitize(book.author)
        title_clean = self._sanitize(book.title)

        author_dir = self.output_dir / author_clean
        author_dir.mkdir(exist_ok=True)

        filename = f"{title_clean}.{ext}"
        output_path = author_dir / filename

        # Evita sobrescrever
        if output_path.exists():
            self._mark_downloaded(book.id, output_path)
            return output_path

        logger.info(f"Baixando: {book.title[:50]}...")

        try:
            response = requests.get(url, headers=HEADERS, stream=True, timeout=120,
                                   allow_redirects=True)

            if response.status_code != 200:
                # Tenta URL alternativa
                if 'epub_no_images' in book.formats and url != book.formats['epub_no_images']:
                    url = book.formats['epub_no_images']
                    response = requests.get(url, headers=HEADERS, stream=True, timeout=120)

                if response.status_code != 200:
                    logger.warning(f"Falha no download: {response.status_code}")
                    return None

            # Download
            total = int(response.headers.get('content-length', 0))

            with open(output_path, 'wb') as f:
                if total > 0:
                    for chunk in response.iter_content(8192):
                        f.write(chunk)
                else:
                    f.write(response.content)

            # Verifica
            if output_path.exists() and output_path.stat().st_size > 1000:
                self._mark_downloaded(book.id, output_path)
                logger.info(f"✓ Salvo: {author_clean}/{filename}")
                return output_path
            else:
                output_path.unlink(missing_ok=True)
                return None

        except Exception as e:
            logger.error(f"Erro: {e}")
            output_path.unlink(missing_ok=True)
            return None

# ============================================================================
# HUNTER PRINCIPAL
# ============================================================================

class BookHunterV2:
    """Caçador de livros versão 2 - com base de dados real."""

    def __init__(self, output_dir: Path = CALIBRE_DIR):
        self.output_dir = output_dir
        self.catalog = GutenbergCatalog()
        self.gutendex = GutendexAPI()
        self.openlibrary = OpenLibraryAPI()
        self.downloader = BookDownloader(output_dir)

    def initialize(self) -> bool:
        """Inicializa carregando o catálogo."""
        return self.catalog.load_catalog()

    def list_top_authors(self, limit: int = 50, public_domain_only: bool = True):
        """Lista os autores com mais livros."""
        authors = self.catalog.get_top_authors(limit, public_domain_only)

        print("\n" + "="*70)
        print(f"{'AUTOR':<40} {'LIVROS':>8} {'MORTE':>8} {'DP':>4}")
        print("="*70)

        for a in authors:
            pd = "✓" if a.is_public_domain() else "✗"
            death = str(a.death_year) if a.death_year else "?"
            print(f"{a.name[:39]:<40} {a.books_count:>8} {death:>8} {pd:>4}")

        print("="*70)
        print(f"Total: {len(authors)} autores")

    def search_and_list(self, query: str, limit: int = 20):
        """Busca e lista livros."""
        books = self.catalog.search_books(query, limit=limit)

        if not books:
            # Tenta API Gutendex
            books = self.gutendex.search(query=query)

        print(f"\nResultados para '{query}':")
        print("-"*70)

        for i, book in enumerate(books[:limit], 1):
            print(f"{i:3}. {book.title[:50]}")
            print(f"     Autor: {book.author} | Idioma: {book.language}")

        return books

    def download_author_books(self, author_name: str, limit: int = 10,
                             language: str = None) -> Dict:
        """Baixa livros de um autor."""
        stats = {"success": 0, "failed": 0, "skipped": 0}

        # Busca livros
        books = self.catalog.get_books_by_author(author_name)

        if not books:
            # Busca aproximada
            for name in self.catalog.authors:
                if author_name.lower() in name.lower():
                    books = self.catalog.get_books_by_author(name)
                    if books:
                        logger.info(f"Encontrado como: {name}")
                        break

        if not books:
            # Tenta Gutendex
            books = self.gutendex.search(author=author_name)

        if not books:
            logger.warning(f"Nenhum livro encontrado para: {author_name}")
            return stats

        logger.info(f"Encontrados {len(books)} livros de {author_name}")

        # Filtra por idioma se especificado
        if language:
            books = [b for b in books if b.language == language]

        # Baixa
        for book in books[:limit]:
            result = self.downloader.download(book)

            if result:
                stats["success"] += 1
            elif book.id in self.downloader.downloaded:
                stats["skipped"] += 1
            else:
                stats["failed"] += 1

            time.sleep(1)  # Rate limiting

        return stats

    def hunt_top_authors(self, num_authors: int = 20, books_per_author: int = 5,
                        language: str = None):
        """Caça livros dos top autores em domínio público."""
        authors = self.catalog.get_top_authors(num_authors, public_domain_only=True)

        total_stats = {"success": 0, "failed": 0, "skipped": 0}

        logger.info(f"\n{'='*60}")
        logger.info(f"CAÇANDO TOP {num_authors} AUTORES")
        logger.info(f"{'='*60}\n")

        for author in tqdm(authors, desc="Autores"):
            logger.info(f"\n--- {author.name} ({author.books_count} livros) ---")

            stats = self.download_author_books(
                author.name,
                limit=books_per_author,
                language=language
            )

            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

            time.sleep(2)

        logger.info(f"\n{'='*60}")
        logger.info(f"CONCLUÍDO!")
        logger.info(f"Sucesso: {total_stats['success']}")
        logger.info(f"Falhas: {total_stats['failed']}")
        logger.info(f"Já baixados: {total_stats['skipped']}")
        logger.info(f"{'='*60}")

        return total_stats

    def hunt_russian_authors(self, books_per_author: int = 10):
        """Caça específica para autores russos."""
        russian_authors = [
            "Fyodor Dostoyevsky", "Dostoevsky", "Dostoievski",
            "Leo Tolstoy", "Tolstoi",
            "Anton Chekhov", "Tchekhov",
            "Nikolai Gogol", "Gogol",
            "Ivan Turgenev", "Turgenev",
            "Alexander Pushkin", "Pushkin",
            "Maxim Gorky", "Gorki",
            "Ivan Bunin",
            "Mikhail Bulgakov",
            "Leonid Andreyev",
            "Mikhail Lermontov",
            "Alexander Kuprin",
        ]

        total_stats = {"success": 0, "failed": 0, "skipped": 0}

        logger.info("\n" + "="*60)
        logger.info("CAÇANDO AUTORES RUSSOS!")
        logger.info("="*60)

        for author_query in russian_authors:
            logger.info(f"\n--- Buscando: {author_query} ---")

            stats = self.download_author_books(author_query, limit=books_per_author)

            for key in total_stats:
                total_stats[key] += stats.get(key, 0)

            time.sleep(2)

        return total_stats

# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="HUNTER V2 - Caçador de Livros com Base de Dados Real"
    )

    parser.add_argument('--init', action='store_true', help='Baixa/atualiza catálogo')
    parser.add_argument('--list-authors', '-la', type=int, metavar='N', help='Lista top N autores')
    parser.add_argument('--search', '-s', type=str, help='Busca livros')
    parser.add_argument('--author', '-a', type=str, help='Baixa livros de um autor')
    parser.add_argument('--russians', '-r', action='store_true', help='Baixa autores russos')
    parser.add_argument('--top', '-t', type=int, metavar='N', help='Baixa dos top N autores')
    parser.add_argument('--limit', '-l', type=int, default=10, help='Livros por autor')
    parser.add_argument('--language', type=str, help='Filtrar por idioma (en, pt, es, etc.)')
    parser.add_argument('--output', '-o', type=Path, default=CALIBRE_DIR)

    args = parser.parse_args()

    hunter = BookHunterV2(output_dir=args.output)

    # Inicializa
    if not hunter.initialize():
        logger.error("Falha ao inicializar. Execute com --init primeiro.")
        return 1

    # Lista autores
    if args.list_authors:
        hunter.list_top_authors(args.list_authors)
        return 0

    # Busca
    if args.search:
        hunter.search_and_list(args.search)
        return 0

    # Autor específico
    if args.author:
        hunter.download_author_books(args.author, limit=args.limit, language=args.language)
        return 0

    # Russos
    if args.russians:
        hunter.hunt_russian_authors(books_per_author=args.limit)
        return 0

    # Top autores
    if args.top:
        hunter.hunt_top_authors(num_authors=args.top, books_per_author=args.limit,
                               language=args.language)
        return 0

    # Sem argumentos
    parser.print_help()
    print("\nExemplos:")
    print("  python hunter_v2.py --list-authors 50")
    print("  python hunter_v2.py --search 'Crime and Punishment'")
    print("  python hunter_v2.py --author 'Dostoevsky' --limit 20")
    print("  python hunter_v2.py --russians --limit 15")
    print("  python hunter_v2.py --top 30 --limit 5")

    return 0


if __name__ == "__main__":
    sys.exit(main())
