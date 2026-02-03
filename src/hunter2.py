#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HUNTER2 - Archive.org Book Hunter
==================================
Baixa livros do Internet Archive (archive.org)

Recursos:
- API do Archive.org para buscar livros
- Suporta múltiplos idiomas
- Baixa em formato TXT (preferencial)
- Fallback para PDF/EPUB com conversão
- Verifica duplicatas
- Barra de progresso

Fonte: https://archive.org
"""

import os
import re
import sys
import time
import json
import logging
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Set
from dataclasses import dataclass
from urllib.parse import quote

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
from config.settings import DATA_DIR, LOG_DIR

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
TXT_DIR = BASE_DIR / "txt"
TEMP_DIR = BASE_DIR / "temp_downloads"

# API do Archive.org
ARCHIVE_API = "https://archive.org/advancedsearch.php"
ARCHIVE_DOWNLOAD = "https://archive.org/download"
ARCHIVE_METADATA = "https://archive.org/metadata"

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) BookHunter2/1.0'
}

# Mapeamento de idiomas para o Archive.org
LANGUAGE_MAP = {
    'en': 'eng',
    'es': 'spa',
    'pt': 'por',
    'fr': 'fre',
    'de': 'ger',
    'it': 'ita',
    'ru': 'rus',
}

# Criar diretórios
for d in [TXT_DIR, TEMP_DIR, DATA_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Logging
LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"hunter2_{datetime.now().strftime('%Y%m%d')}.log"

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
class ArchiveBook:
    identifier: str
    title: str
    creator: str
    language: str
    year: Optional[str] = None
    formats: List[str] = None

    def __post_init__(self):
        if self.formats is None:
            self.formats = []

# ============================================================================
# FUNÇÕES DE UTILIDADE
# ============================================================================

def sanitize_name(name: str, max_len: int = 80) -> str:
    """Limpa nome para usar como arquivo/pasta."""
    if not name:
        return "Unknown"
    name = re.sub(r'[<>:"/\\|?*\n\r\t]', '', name)
    name = re.sub(r'\s+', ' ', name).strip()
    if len(name) > max_len:
        name = name[:max_len].rsplit(' ', 1)[0]
    return name or "Unknown"

def book_exists(author: str, title: str) -> bool:
    """Verifica se livro já existe em txt/."""
    author_clean = sanitize_name(author)
    title_clean = sanitize_name(title)

    author_dir = TXT_DIR / author_clean
    if not author_dir.exists():
        return False

    txt_file = author_dir / f"{title_clean}.txt"
    return txt_file.exists()

# ============================================================================
# ARCHIVE.ORG API
# ============================================================================

class ArchiveOrgHunter:
    """Caçador de livros do Archive.org."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.known_books: Set[str] = set()

    def search_books(self, language: str, limit: int = 50, page: int = 1) -> List[ArchiveBook]:
        """
        Busca livros no Archive.org.

        Args:
            language: Código do idioma (en, es, pt, etc.)
            limit: Número de resultados
            page: Página de resultados

        Returns:
            Lista de livros encontrados
        """
        # Mapeia idioma
        lang_code = LANGUAGE_MAP.get(language, language)

        # Parâmetros da busca
        params = {
            'q': f'mediatype:texts AND language:{lang_code} AND format:txt',
            'fl[]': ['identifier', 'title', 'creator', 'language', 'year'],
            'sort[]': 'downloads desc',  # Mais baixados primeiro
            'rows': limit,
            'page': page,
            'output': 'json'
        }

        try:
            logger.info(f"Buscando livros em {language.upper()} no Archive.org...")
            response = self.session.get(ARCHIVE_API, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            docs = data.get('response', {}).get('docs', [])

            books = []
            for doc in docs:
                # Extrai informações
                identifier = doc.get('identifier', '')
                title = doc.get('title', 'Unknown Title')
                creator = doc.get('creator', ['Unknown Author'])

                # Creator pode ser lista ou string
                if isinstance(creator, list):
                    creator = creator[0] if creator else 'Unknown Author'
                elif not creator:
                    creator = 'Unknown Author'

                # Language pode ser lista
                doc_lang = doc.get('language', [language])
                if isinstance(doc_lang, list):
                    doc_lang = doc_lang[0] if doc_lang else language

                year = doc.get('year')

                book = ArchiveBook(
                    identifier=identifier,
                    title=title,
                    creator=creator,
                    language=doc_lang,
                    year=year
                )
                books.append(book)

            logger.info(f"Encontrados {len(books)} livros em {language.upper()}")
            return books

        except Exception as e:
            logger.error(f"Erro ao buscar livros: {e}")
            return []

    def get_book_metadata(self, identifier: str) -> Optional[Dict]:
        """Obtém metadados completos de um livro."""
        try:
            url = f"{ARCHIVE_METADATA}/{identifier}"
            response = self.session.get(url, timeout=15)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Erro ao obter metadados de {identifier}: {e}")
            return None

    def download_txt(self, book: ArchiveBook) -> Optional[str]:
        """
        Baixa arquivo TXT de um livro.

        Returns:
            Conteúdo do arquivo TXT ou None
        """
        try:
            # Obtém metadados para encontrar arquivos
            metadata = self.get_book_metadata(book.identifier)
            if not metadata:
                return None

            files = metadata.get('files', [])

            # Procura arquivo TXT
            txt_files = [f for f in files if f.get('format') == 'Text' or f['name'].endswith('.txt')]

            if not txt_files:
                logger.debug(f"Nenhum TXT encontrado para {book.identifier}")
                return None

            # Pega o primeiro TXT
            txt_file = txt_files[0]
            filename = txt_file['name']

            # URL de download
            url = f"{ARCHIVE_DOWNLOAD}/{book.identifier}/{filename}"

            logger.debug(f"Baixando TXT: {url}")
            response = self.session.get(url, timeout=60)
            response.raise_for_status()

            # Tenta decodificar com diferentes encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']:
                try:
                    content = response.content.decode(encoding)
                    return content
                except UnicodeDecodeError:
                    continue

            # Se falhar, tenta forçar UTF-8 com erros
            return response.content.decode('utf-8', errors='replace')

        except Exception as e:
            logger.error(f"Erro ao baixar TXT de {book.identifier}: {e}")
            return None

    def save_book(self, book: ArchiveBook, content: str) -> bool:
        """Salva conteúdo do livro em arquivo."""
        try:
            author_clean = sanitize_name(book.creator)
            title_clean = sanitize_name(book.title)

            # Cria diretório do autor
            author_dir = TXT_DIR / author_clean
            author_dir.mkdir(exist_ok=True)

            # Salva arquivo
            txt_file = author_dir / f"{title_clean}.txt"

            with open(txt_file, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"✅ Salvo: {author_clean}/{title_clean}.txt")
            return True

        except Exception as e:
            logger.error(f"Erro ao salvar {book.title}: {e}")
            return False

    def hunt(self, languages: List[str], limit_per_lang: int = 50) -> Dict:
        """
        Caça livros em múltiplos idiomas.

        Args:
            languages: Lista de idiomas (ex: ['en', 'es'])
            limit_per_lang: Limite de livros por idioma

        Returns:
            Estatísticas de download
        """
        stats = {
            'downloaded': 0,
            'skipped': 0,
            'failed': 0,
            'total_found': 0
        }

        logger.info("="*60)
        logger.info("HUNTER2 - Archive.org")
        logger.info(f"Idiomas: {languages}")
        logger.info(f"Limite por idioma: {limit_per_lang}")
        logger.info("="*60)

        for lang in languages:
            logger.info(f"\n--- Idioma: {lang.upper()} ---")

            # Busca livros
            books = self.search_books(lang, limit=limit_per_lang)
            stats['total_found'] += len(books)

            if not books:
                logger.warning(f"Nenhum livro encontrado para {lang}")
                continue

            # Processa cada livro
            with tqdm(total=len(books), desc=f"Baixando {lang.upper()}") as pbar:
                for book in books:
                    pbar.set_description(f"{lang.upper()}: {book.title[:30]}")

                    # Verifica se já existe
                    if book_exists(book.creator, book.title):
                        stats['skipped'] += 1
                        pbar.update(1)
                        continue

                    # Baixa conteúdo
                    content = self.download_txt(book)

                    if content:
                        # Salva
                        if self.save_book(book, content):
                            stats['downloaded'] += 1
                        else:
                            stats['failed'] += 1
                    else:
                        stats['failed'] += 1

                    pbar.update(1)

                    # Rate limiting
                    time.sleep(0.5)

        # Resumo
        logger.info("\n" + "="*60)
        logger.info("RESUMO")
        logger.info(f"Encontrados: {stats['total_found']}")
        logger.info(f"Baixados: {stats['downloaded']}")
        logger.info(f"Pulados (já existem): {stats['skipped']}")
        logger.info(f"Falhas: {stats['failed']}")
        logger.info(f"Pasta: {TXT_DIR}")
        logger.info("="*60)

        return stats

# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Hunter2 - Baixa livros do Archive.org",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Baixar 50 livros em inglês
  python run_hunter2.py --languages en --limit 50

  # Baixar em múltiplos idiomas
  python run_hunter2.py --languages en es pt --limit 100

  # Baixar livros em francês
  python run_hunter2.py --languages fr --limit 200
"""
    )

    parser.add_argument('--languages', '-l', nargs='+', default=['en'],
                       help='Idiomas para buscar (en, es, pt, fr, de, it, ru)')
    parser.add_argument('--limit', '-n', type=int, default=50,
                       help='Número de livros por idioma (padrão: 50)')

    args = parser.parse_args()

    # Valida idiomas
    valid_langs = set(LANGUAGE_MAP.keys())
    invalid = set(args.languages) - valid_langs
    if invalid:
        logger.error(f"Idiomas inválidos: {invalid}")
        logger.error(f"Idiomas válidos: {sorted(valid_langs)}")
        return 1

    # Executa hunter
    hunter = ArchiveOrgHunter()
    stats = hunter.hunt(args.languages, args.limit)

    return 0 if stats['downloaded'] > 0 or stats['skipped'] > 0 else 1

if __name__ == "__main__":
    sys.exit(main())
