# -*- coding: utf-8 -*-
"""
HUNTER_RUSSIAN.PY - Caçador de Livros Russos
=============================================
Baixa livros russos de múltiplas fontes:
1. Project Gutenberg (ru)
2. Archive.org (Russian texts)
3. Lib.ru (biblioteca russa)
4. Royallib.com mirrors
5. Az.lib.ru (Moshkov's library)

20+ threads paralelas, download massivo.
"""

import os
import sys
import re
import csv
import gzip
import shutil
import hashlib
import requests
import unicodedata
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from urllib.parse import urljoin, quote
from tqdm import tqdm
from bs4 import BeautifulSoup

# Config
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import BASE_DIR, DATA_DIR, LOG_DIR

# Diretórios
RAW_DIR = BASE_DIR / "raw_russian"
TXT_DIR = BASE_DIR / "txt"
RUSSIAN_DIR = TXT_DIR / "Russian"
GUTENBERG_CSV = DATA_DIR / "pg_catalog.csv"

# Criar diretórios
RAW_DIR.mkdir(parents=True, exist_ok=True)
RUSSIAN_DIR.mkdir(parents=True, exist_ok=True)

# Logging
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / f"hunter_russian_{datetime.now().strftime('%Y%m%d')}.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 RussianBookHunter/1.0',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate',
}

@dataclass
class RussianBook:
    id: str
    title: str
    author: str
    url: str
    source: str
    encoding: str = 'utf-8'

def sanitize_name(name: str, max_len: int = 80) -> str:
    """Limpa nome para uso em arquivos."""
    if not name:
        return "Unknown"
    name = unicodedata.normalize('NFKD', name)
    name = re.sub(r'[<>:"/\\|?*]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    return name[:max_len] if len(name) > max_len else name

def get_file_hash(filepath: Path) -> str:
    """Calcula hash MD5."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

class GutenbergRussianHunter:
    """Busca livros russos no Gutenberg."""

    def __init__(self):
        self.books: List[RussianBook] = []

    def load_books(self, limit: int = 500) -> List[RussianBook]:
        """Carrega livros russos do catálogo Gutenberg."""
        if not GUTENBERG_CSV.exists():
            logger.warning("Catálogo Gutenberg não encontrado")
            return []

        books = []

        with open(GUTENBERG_CSV, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)

            for row in reader:
                if len(books) >= limit:
                    break

                lang = row.get('Language', '').lower()
                if 'ru' not in lang and 'russian' not in lang:
                    continue

                book_type = row.get('Type', '').lower()
                if 'text' not in book_type:
                    continue

                book_id = row.get('Text#', '')
                title = row.get('Title', 'Unknown')
                author = row.get('Authors', 'Unknown').split(';')[0].strip()

                if not book_id:
                    continue

                url = f"https://www.gutenberg.org/cache/epub/{book_id}/pg{book_id}.txt"

                books.append(RussianBook(
                    id=f"gut_{book_id}",
                    title=sanitize_name(title),
                    author=sanitize_name(author.split(',')[0]),
                    url=url,
                    source='gutenberg'
                ))

        logger.info(f"Gutenberg: {len(books)} livros russos")
        return books

class ArchiveOrgRussianHunter:
    """Busca livros russos no Archive.org."""

    def __init__(self):
        self.base_url = "https://archive.org"
        self.search_url = "https://archive.org/advancedsearch.php"

    def search_books(self, limit: int = 500) -> List[RussianBook]:
        """Busca livros russos no Archive.org."""
        books = []

        queries = [
            'language:rus AND mediatype:texts',
            'language:russian AND mediatype:texts',
            'subject:russian literature AND mediatype:texts',
            'creator:Dostoevsky AND mediatype:texts',
            'creator:Tolstoy AND mediatype:texts',
            'creator:Chekhov AND mediatype:texts',
            'creator:Pushkin AND mediatype:texts',
            'creator:Gogol AND mediatype:texts',
            'creator:Turgenev AND mediatype:texts',
            'creator:Bulgakov AND mediatype:texts',
        ]

        for query in queries:
            if len(books) >= limit:
                break

            try:
                params = {
                    'q': query,
                    'fl[]': ['identifier', 'title', 'creator'],
                    'rows': min(200, limit - len(books)),
                    'page': 1,
                    'output': 'json'
                }

                response = requests.get(self.search_url, params=params, headers=HEADERS, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    docs = data.get('response', {}).get('docs', [])

                    for doc in docs:
                        identifier = doc.get('identifier', '')
                        title = doc.get('title', 'Unknown')
                        creator = doc.get('creator', ['Unknown'])

                        if isinstance(creator, list):
                            creator = creator[0] if creator else 'Unknown'

                        # URL para texto
                        url = f"https://archive.org/download/{identifier}/{identifier}_djvu.txt"

                        books.append(RussianBook(
                            id=f"arc_{identifier}",
                            title=sanitize_name(title[:80]),
                            author=sanitize_name(str(creator)[:50]),
                            url=url,
                            source='archive.org'
                        ))

            except Exception as e:
                logger.warning(f"Erro na busca Archive.org: {e}")

        logger.info(f"Archive.org: {len(books)} livros russos")
        return books

class LibRuHunter:
    """Busca livros em lib.ru (Moshkov's Library)."""

    def __init__(self):
        self.base_url = "http://lib.ru"
        self.categories = [
            "/LITRA/",
            "/PROZA/",
            "/POETRY/",
            "/RUFANT/",
            "/RUSS_DETEKTIW/",
        ]

    def get_books_from_page(self, url: str) -> List[RussianBook]:
        """Extrai links de livros de uma página."""
        books = []

        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.encoding = 'koi8-r'

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')

                for link in soup.find_all('a', href=True):
                    href = link['href']

                    if href.endswith('.txt') or href.endswith('.txt_Ascii'):
                        title = link.get_text(strip=True) or Path(href).stem
                        full_url = urljoin(url, href)

                        # Extrai autor do path se possível
                        parts = href.split('/')
                        author = parts[-2] if len(parts) > 1 else 'Unknown'

                        books.append(RussianBook(
                            id=f"lib_{hashlib.md5(full_url.encode()).hexdigest()[:8]}",
                            title=sanitize_name(title),
                            author=sanitize_name(author),
                            url=full_url,
                            source='lib.ru',
                            encoding='koi8-r'
                        ))

        except Exception as e:
            logger.debug(f"Erro em {url}: {e}")

        return books

    def search_books(self, limit: int = 300) -> List[RussianBook]:
        """Busca livros em lib.ru."""
        books = []

        for category in self.categories:
            if len(books) >= limit:
                break

            url = self.base_url + category
            found = self.get_books_from_page(url)
            books.extend(found[:limit - len(books)])

        logger.info(f"Lib.ru: {len(books)} livros russos")
        return books

class AzLibRuHunter:
    """Busca livros em az.lib.ru."""

    def __init__(self):
        self.base_url = "http://az.lib.ru"

    def search_books(self, limit: int = 200) -> List[RussianBook]:
        """Busca autores e livros em az.lib.ru."""
        books = []

        # Autores russos famosos
        authors = [
            'p/pushkin_a_s',
            'g/gogolx_n_w',
            't/tolstoj_lew_nikolaewich',
            'd/dostoewskij_f_m',
            'c/chehow_a_p',
            't/turgenew_i_s',
            'b/bunin_i_a',
            'b/bulgakow_m_a',
            'g/goncharow_i_a',
            'l/lermontow_m_ju',
        ]

        for author_path in authors:
            if len(books) >= limit:
                break

            try:
                url = f"{self.base_url}/{author_path}/"
                response = requests.get(url, headers=HEADERS, timeout=15)
                response.encoding = 'koi8-r'

                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')

                    for link in soup.find_all('a', href=True):
                        href = link['href']

                        if href.endswith('.shtml') and not href.startswith('http'):
                            title = link.get_text(strip=True)
                            if title and len(title) > 3:
                                # Converte para URL de texto
                                text_url = urljoin(url, href.replace('.shtml', '.txt'))

                                author_name = author_path.split('/')[-1].replace('_', ' ').title()

                                books.append(RussianBook(
                                    id=f"az_{hashlib.md5(text_url.encode()).hexdigest()[:8]}",
                                    title=sanitize_name(title),
                                    author=sanitize_name(author_name),
                                    url=text_url,
                                    source='az.lib.ru',
                                    encoding='koi8-r'
                                ))

            except Exception as e:
                logger.debug(f"Erro em az.lib.ru: {e}")

        logger.info(f"Az.lib.ru: {len(books)} livros russos")
        return books

class RussianHunter:
    """Agregador de todas as fontes russas."""

    def __init__(self, max_workers: int = 20):
        self.max_workers = max_workers
        self.gutenberg = GutenbergRussianHunter()
        self.archive = ArchiveOrgRussianHunter()
        self.libru = LibRuHunter()
        self.azlib = AzLibRuHunter()

    def collect_all_books(self, limit_per_source: int = 300) -> List[RussianBook]:
        """Coleta livros de todas as fontes."""
        all_books = []

        logger.info("Coletando livros de todas as fontes...")

        # Gutenberg
        all_books.extend(self.gutenberg.load_books(limit_per_source))

        # Archive.org
        all_books.extend(self.archive.search_books(limit_per_source))

        # Lib.ru
        all_books.extend(self.libru.search_books(limit_per_source))

        # Az.lib.ru
        all_books.extend(self.azlib.search_books(limit_per_source))

        # Remove duplicados por URL
        seen_urls = set()
        unique_books = []
        for book in all_books:
            if book.url not in seen_urls:
                seen_urls.add(book.url)
                unique_books.append(book)

        logger.info(f"Total coletado: {len(unique_books)} livros únicos")
        return unique_books

    def download_single(self, book: RussianBook) -> Optional[Path]:
        """Baixa um único livro."""
        filename = f"{book.author}_{book.title}_{book.id}.txt"
        filepath = RAW_DIR / filename

        if filepath.exists():
            return filepath

        try:
            response = requests.get(book.url, headers=HEADERS, timeout=30)

            if response.status_code == 200:
                # Tenta detectar encoding
                content = response.content

                # Tenta decodificar
                text = None
                for enc in [book.encoding, 'utf-8', 'koi8-r', 'cp1251', 'iso-8859-5']:
                    try:
                        text = content.decode(enc)
                        break
                    except:
                        continue

                if not text or len(text) < 500:
                    return None

                # Salva como UTF-8
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text)

                return filepath

        except Exception as e:
            logger.debug(f"Erro ao baixar {book.title}: {e}")

        return None

    def download_massive(self, books: List[RussianBook]) -> Dict:
        """Download massivo paralelo."""
        logger.info(f"Baixando {len(books)} livros russos ({self.max_workers} threads)...")

        stats = {'success': 0, 'failed': 0}
        downloaded_paths = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.download_single, book): book for book in books}

            with tqdm(total=len(books), desc="Baixando", unit="livro") as pbar:
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        if result:
                            stats['success'] += 1
                            downloaded_paths.append(result)
                        else:
                            stats['failed'] += 1
                    except Exception:
                        stats['failed'] += 1

                    pbar.update(1)

        logger.info(f"Download: {stats['success']} OK, {stats['failed']} falhas")
        return stats

    def analyze_and_move(self) -> Dict:
        """Analisa duplicados e move para pasta final."""
        files = list(RAW_DIR.glob("*.txt"))

        if not files:
            return {'moved': 0, 'duplicates': 0}

        logger.info(f"Analisando {len(files)} arquivos...")

        hashes: Dict[str, Path] = {}
        duplicates = []
        unique = []

        for filepath in tqdm(files, desc="Analisando", unit="arquivo"):
            file_hash = get_file_hash(filepath)

            if file_hash in hashes:
                duplicates.append(filepath)
            else:
                hashes[file_hash] = filepath
                unique.append(filepath)

        # Move únicos para pasta Russian
        moved = 0
        for filepath in tqdm(unique, desc="Movendo", unit="arquivo"):
            dest = RUSSIAN_DIR / filepath.name

            if not dest.exists():
                shutil.move(str(filepath), str(dest))
                moved += 1

        # Limpa raw
        for f in RAW_DIR.glob("*"):
            if f.is_file():
                f.unlink()

        logger.info(f"Movidos: {moved}, Duplicados: {len(duplicates)}")

        return {'moved': moved, 'duplicates': len(duplicates)}

    def hunt(self, limit_per_source: int = 300) -> Dict:
        """Executa caçada completa."""
        logger.info("="*70)
        logger.info("RUSSIAN BOOK HUNTER - Caçador de Livros Russos")
        logger.info("="*70)
        logger.info("Fontes: Gutenberg, Archive.org, Lib.ru, Az.lib.ru")
        logger.info("="*70)

        # 1. Coleta livros
        books = self.collect_all_books(limit_per_source)

        if not books:
            return {'error': 'Nenhum livro encontrado'}

        # 2. Download massivo
        download_stats = self.download_massive(books)

        # 3. Analisa e move
        move_stats = self.analyze_and_move()

        # Resumo
        logger.info("="*70)
        logger.info("RESUMO FINAL - LIVROS RUSSOS")
        logger.info("="*70)
        logger.info(f"Baixados: {download_stats['success']}")
        logger.info(f"Falhas: {download_stats['failed']}")
        logger.info(f"Duplicados: {move_stats['duplicates']}")
        logger.info(f"Salvos em txt/Russian/: {move_stats['moved']}")
        logger.info("="*70)

        return {
            'downloaded': download_stats['success'],
            'failed': download_stats['failed'],
            'duplicates': move_stats['duplicates'],
            'moved': move_stats['moved']
        }

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Russian Book Hunter")
    parser.add_argument('--limit', '-n', type=int, default=300,
                       help='Limite por fonte')
    parser.add_argument('--workers', '-w', type=int, default=20,
                       help='Threads paralelas')
    parser.add_argument('--loop', action='store_true',
                       help='Roda em loop infinito')

    args = parser.parse_args()

    if args.loop:
        cycle = 0
        total = 0

        while True:
            try:
                cycle += 1
                logger.info(f"\n=== CICLO {cycle} ===")

                hunter = RussianHunter(max_workers=args.workers)
                stats = hunter.hunt(args.limit)

                total += stats.get('moved', 0)
                logger.info(f"Total acumulado: {total} livros russos")

                logger.info("Aguardando 30s...")
                import time
                time.sleep(30)

            except KeyboardInterrupt:
                logger.info(f"\nParado! Total: {total} livros em {cycle} ciclos")
                break
    else:
        hunter = RussianHunter(max_workers=args.workers)
        hunter.hunt(args.limit)

    return 0

if __name__ == "__main__":
    sys.exit(main())
