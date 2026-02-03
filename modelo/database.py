# -*- coding: utf-8 -*-
"""
DATABASE.PY - Banco de Dados SQLite para Livros
===============================================
Importa catálogos para SQLite para busca rápida e eficiente.

Tabelas:
- authors: Autores com informações de vida/morte
- books: Livros com metadados
- subjects: Assuntos/categorias
- book_subjects: Relação N:N entre livros e assuntos

Performance:
- CSV 89k linhas: ~30 segundos para carregar toda vez
- SQLite: ~0.01 segundos para qualquer busca
"""

import os
import re
import csv
import gzip
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass

import requests
from tqdm import tqdm

# ============================================================================
# CONFIGURAÇÃO
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "modelo" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_PATH = DATA_DIR / "books.db"
GUTENBERG_CSV = DATA_DIR / "pg_catalog.csv"
GUTENBERG_CSV_GZ = DATA_DIR / "pg_catalog.csv.gz"
GUTENBERG_CSV_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"

HEADERS = {'User-Agent': 'Mozilla/5.0 BookHunter/2.0'}

logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Author:
    id: int
    name: str
    birth_year: Optional[int]
    death_year: Optional[int]
    books_count: int = 0

    def is_public_domain(self) -> bool:
        if self.death_year is None:
            return False
        return (datetime.now().year - self.death_year) >= 70

@dataclass
class Book:
    id: str
    title: str
    author_id: int
    author_name: str
    language: str
    issued: str
    source: str

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class BooksDatabase:
    """Gerenciador do banco de dados SQLite."""

    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Conecta ao banco."""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        return self

    def close(self):
        """Fecha conexão."""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self.connect()

    def __exit__(self, *args):
        self.close()

    def create_tables(self):
        """Cria as tabelas do banco."""
        cursor = self.conn.cursor()

        # Tabela de autores
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS authors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                name_normalized TEXT,
                birth_year INTEGER,
                death_year INTEGER,
                nationality TEXT,
                books_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabela de livros
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                title_normalized TEXT,
                author_id INTEGER,
                language TEXT DEFAULT 'en',
                issued TEXT,
                source TEXT DEFAULT 'gutenberg',
                epub_url TEXT,
                pdf_url TEXT,
                txt_url TEXT,
                downloaded INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (author_id) REFERENCES authors(id)
            )
        ''')

        # Tabela de assuntos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                name_normalized TEXT
            )
        ''')

        # Relação livros-assuntos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS book_subjects (
                book_id TEXT,
                subject_id INTEGER,
                PRIMARY KEY (book_id, subject_id),
                FOREIGN KEY (book_id) REFERENCES books(id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id)
            )
        ''')

        # Índices para busca rápida
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name_normalized)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_authors_death ON authors(death_year)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title_normalized)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_author ON books(author_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_language ON books(language)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_downloaded ON books(downloaded)')

        self.conn.commit()
        logger.info("Tabelas criadas")

    def normalize_text(self, text: str) -> str:
        """Normaliza texto para busca."""
        if not text:
            return ""
        # Remove acentos, lowercase
        import unicodedata
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        return text.lower().strip()

    def parse_author_string(self, author_str: str) -> Tuple[str, Optional[int], Optional[int]]:
        """Parse string de autor do Gutenberg."""
        if not author_str:
            return "Unknown", None, None

        # Extrai anos
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

        # Reorganiza "Sobrenome, Nome"
        if ',' in name:
            parts = name.split(',', 1)
            if len(parts) == 2:
                name = f"{parts[1].strip()} {parts[0].strip()}"

        return name, birth_year, death_year

    def get_or_create_author(self, name: str, birth_year: int = None,
                            death_year: int = None) -> int:
        """Obtém ou cria autor, retorna ID."""
        cursor = self.conn.cursor()
        name_norm = self.normalize_text(name)

        # Tenta encontrar
        cursor.execute('SELECT id FROM authors WHERE name_normalized = ?', (name_norm,))
        row = cursor.fetchone()

        if row:
            # Atualiza anos se não tinha
            if birth_year or death_year:
                cursor.execute('''
                    UPDATE authors SET
                        birth_year = COALESCE(birth_year, ?),
                        death_year = COALESCE(death_year, ?)
                    WHERE id = ?
                ''', (birth_year, death_year, row['id']))
            return row['id']

        # Cria novo
        cursor.execute('''
            INSERT INTO authors (name, name_normalized, birth_year, death_year)
            VALUES (?, ?, ?, ?)
        ''', (name, name_norm, birth_year, death_year))

        return cursor.lastrowid

    def get_or_create_subject(self, name: str) -> int:
        """Obtém ou cria assunto, retorna ID."""
        cursor = self.conn.cursor()
        name_norm = self.normalize_text(name)

        cursor.execute('SELECT id FROM subjects WHERE name_normalized = ?', (name_norm,))
        row = cursor.fetchone()

        if row:
            return row['id']

        cursor.execute('''
            INSERT INTO subjects (name, name_normalized)
            VALUES (?, ?)
        ''', (name, name_norm))

        return cursor.lastrowid

    def add_book(self, book_id: str, title: str, author_id: int, language: str,
                issued: str, subjects: List[str] = None, source: str = "gutenberg"):
        """Adiciona livro ao banco."""
        cursor = self.conn.cursor()

        # URLs do Gutenberg
        epub_url = f"https://www.gutenberg.org/ebooks/{book_id}.epub.images"
        txt_url = f"https://www.gutenberg.org/ebooks/{book_id}.txt.utf-8"

        try:
            cursor.execute('''
                INSERT OR IGNORE INTO books
                (id, title, title_normalized, author_id, language, issued, source, epub_url, txt_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (book_id, title, self.normalize_text(title), author_id,
                  language, issued, source, epub_url, txt_url))

            # Adiciona assuntos
            if subjects:
                for subject in subjects:
                    if subject and subject.strip():
                        subject_id = self.get_or_create_subject(subject.strip())
                        cursor.execute('''
                            INSERT OR IGNORE INTO book_subjects (book_id, subject_id)
                            VALUES (?, ?)
                        ''', (book_id, subject_id))

        except sqlite3.IntegrityError:
            pass  # Livro já existe

    def update_author_counts(self):
        """Atualiza contagem de livros por autor."""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE authors SET books_count = (
                SELECT COUNT(*) FROM books WHERE books.author_id = authors.id
            )
        ''')
        self.conn.commit()

    # =========================================================================
    # CONSULTAS
    # =========================================================================

    def search_books(self, query: str, language: str = None,
                    public_domain_only: bool = True, limit: int = 100) -> List[Dict]:
        """Busca livros por título ou autor."""
        cursor = self.conn.cursor()
        query_norm = self.normalize_text(query)

        sql = '''
            SELECT b.id, b.title, b.language, b.epub_url, b.txt_url,
                   a.name as author_name, a.death_year
            FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE (b.title_normalized LIKE ? OR a.name_normalized LIKE ?)
        '''
        params = [f'%{query_norm}%', f'%{query_norm}%']

        if language:
            sql += ' AND b.language = ?'
            params.append(language)

        if public_domain_only:
            current_year = datetime.now().year
            sql += f' AND a.death_year IS NOT NULL AND a.death_year <= {current_year - 70}'

        sql += ' ORDER BY a.books_count DESC LIMIT ?'
        params.append(limit)

        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def search_author(self, query: str, public_domain_only: bool = True) -> List[Dict]:
        """Busca autores."""
        cursor = self.conn.cursor()
        query_norm = self.normalize_text(query)

        sql = '''
            SELECT id, name, birth_year, death_year, books_count
            FROM authors
            WHERE name_normalized LIKE ?
        '''
        params = [f'%{query_norm}%']

        if public_domain_only:
            current_year = datetime.now().year
            sql += f' AND death_year IS NOT NULL AND death_year <= {current_year - 70}'

        sql += ' ORDER BY books_count DESC LIMIT 50'

        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_top_authors(self, limit: int = 100, public_domain_only: bool = True) -> List[Dict]:
        """Retorna autores com mais livros."""
        cursor = self.conn.cursor()

        sql = '''
            SELECT id, name, birth_year, death_year, books_count
            FROM authors
            WHERE books_count > 0
        '''

        if public_domain_only:
            current_year = datetime.now().year
            sql += f' AND death_year IS NOT NULL AND death_year <= {current_year - 70}'

        sql += ' ORDER BY books_count DESC LIMIT ?'

        cursor.execute(sql, (limit,))
        return [dict(row) for row in cursor.fetchall()]

    def get_books_by_author(self, author_id: int = None, author_name: str = None,
                           limit: int = 100) -> List[Dict]:
        """Retorna livros de um autor."""
        cursor = self.conn.cursor()

        if author_name:
            # Busca autor primeiro
            authors = self.search_author(author_name)
            if not authors:
                return []
            author_id = authors[0]['id']

        cursor.execute('''
            SELECT b.id, b.title, b.language, b.epub_url, b.txt_url, b.downloaded,
                   a.name as author_name
            FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE b.author_id = ?
            ORDER BY b.title
            LIMIT ?
        ''', (author_id, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_not_downloaded(self, author_id: int = None, limit: int = 100) -> List[Dict]:
        """Retorna livros não baixados."""
        cursor = self.conn.cursor()

        sql = '''
            SELECT b.id, b.title, b.language, b.epub_url, b.txt_url,
                   a.name as author_name, a.death_year
            FROM books b
            JOIN authors a ON b.author_id = a.id
            WHERE b.downloaded = 0
        '''
        params = []

        if author_id:
            sql += ' AND b.author_id = ?'
            params.append(author_id)

        sql += ' ORDER BY a.books_count DESC LIMIT ?'
        params.append(limit)

        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def mark_downloaded(self, book_id: str):
        """Marca livro como baixado."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE books SET downloaded = 1 WHERE id = ?', (book_id,))
        self.conn.commit()

    def get_stats(self) -> Dict:
        """Retorna estatísticas do banco."""
        cursor = self.conn.cursor()

        stats = {}

        cursor.execute('SELECT COUNT(*) FROM books')
        stats['total_books'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM authors')
        stats['total_authors'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(*) FROM books WHERE downloaded = 1')
        stats['downloaded_books'] = cursor.fetchone()[0]

        current_year = datetime.now().year
        cursor.execute(f'''
            SELECT COUNT(*) FROM authors
            WHERE death_year IS NOT NULL AND death_year <= {current_year - 70}
        ''')
        stats['public_domain_authors'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT language) FROM books')
        stats['languages'] = cursor.fetchone()[0]

        return stats

# ============================================================================
# IMPORTAÇÃO DO GUTENBERG
# ============================================================================

def download_gutenberg_catalog():
    """Baixa o catálogo do Gutenberg."""
    if GUTENBERG_CSV.exists():
        age = datetime.now().timestamp() - GUTENBERG_CSV.stat().st_mtime
        if age < 7 * 24 * 3600:  # Menos de 7 dias
            logger.info(f"Catálogo existente: {GUTENBERG_CSV}")
            return True

    logger.info("Baixando catálogo do Project Gutenberg...")

    try:
        response = requests.get(GUTENBERG_CSV_URL, stream=True, headers=HEADERS, timeout=60)
        total = int(response.headers.get('content-length', 0))

        with open(GUTENBERG_CSV_GZ, 'wb') as f:
            with tqdm(total=total, unit='B', unit_scale=True, desc="Baixando") as pbar:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
                    pbar.update(len(chunk))

        # Descompacta
        with gzip.open(GUTENBERG_CSV_GZ, 'rb') as f_in:
            with open(GUTENBERG_CSV, 'wb') as f_out:
                f_out.write(f_in.read())

        GUTENBERG_CSV_GZ.unlink(missing_ok=True)
        logger.info(f"Catálogo salvo: {GUTENBERG_CSV}")
        return True

    except Exception as e:
        logger.error(f"Erro ao baixar: {e}")
        return False


def import_gutenberg_to_sqlite(force: bool = False):
    """Importa catálogo CSV para SQLite."""
    db = BooksDatabase()

    with db:
        # Cria tabelas primeiro
        db.create_tables()

        # Verifica se já tem dados
        if not force:
            stats = db.get_stats()
            if stats['total_books'] > 50000:
                logger.info(f"Banco já populado: {stats['total_books']} livros")
                return True

        # Baixa catálogo se necessário
        if not GUTENBERG_CSV.exists():
            if not download_gutenberg_catalog():
                return False

        # Cria tabelas
        db.create_tables()

        logger.info("Importando catálogo para SQLite...")

        with open(GUTENBERG_CSV, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            count = 0

            for row in tqdm(reader, desc="Importando", unit=" livros"):
                try:
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
                    author_name, birth_year, death_year = db.parse_author_string(author_str)

                    # Adiciona autor
                    author_id = db.get_or_create_author(author_name, birth_year, death_year)

                    # Adiciona livro
                    db.add_book(
                        book_id=book_id,
                        title=title,
                        author_id=author_id,
                        language=language,
                        issued=issued,
                        subjects=[s.strip() for s in subjects if s.strip()]
                    )

                    count += 1

                    # Commit a cada 1000
                    if count % 1000 == 0:
                        db.conn.commit()

                except Exception as e:
                    continue

        # Commit final
        db.conn.commit()

        # Atualiza contagens
        logger.info("Atualizando contagens...")
        db.update_author_counts()

        # Estatísticas
        stats = db.get_stats()
        logger.info(f"\n{'='*50}")
        logger.info("IMPORTAÇÃO CONCLUÍDA!")
        logger.info(f"Livros: {stats['total_books']}")
        logger.info(f"Autores: {stats['total_authors']}")
        logger.info(f"Autores em domínio público: {stats['public_domain_authors']}")
        logger.info(f"Idiomas: {stats['languages']}")
        logger.info(f"{'='*50}")

    return True


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Gerenciador de banco de dados de livros")
    parser.add_argument('--import', '-i', dest='do_import', action='store_true',
                       help='Importa catálogo do Gutenberg')
    parser.add_argument('--force', '-f', action='store_true',
                       help='Força reimportação')
    parser.add_argument('--stats', '-s', action='store_true',
                       help='Mostra estatísticas')
    parser.add_argument('--search', type=str, help='Busca livros')
    parser.add_argument('--author', '-a', type=str, help='Busca autor')
    parser.add_argument('--top', '-t', type=int, help='Lista top N autores')

    args = parser.parse_args()

    # Configura logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(message)s'
    )

    # Importar
    if args.do_import:
        import_gutenberg_to_sqlite(force=args.force)
        return 0

    # Estatísticas
    if args.stats:
        with BooksDatabase() as db:
            stats = db.get_stats()
            print("\n" + "="*50)
            print("ESTATÍSTICAS DO BANCO")
            print("="*50)
            for key, value in stats.items():
                print(f"{key}: {value:,}")
            print("="*50)
        return 0

    # Busca livros
    if args.search:
        with BooksDatabase() as db:
            books = db.search_books(args.search, limit=20)
            print(f"\nResultados para '{args.search}':")
            print("-"*60)
            for b in books:
                print(f"• {b['title'][:50]}")
                print(f"  Autor: {b['author_name']} | Idioma: {b['language']}")
        return 0

    # Busca autor
    if args.author:
        with BooksDatabase() as db:
            authors = db.search_author(args.author)
            print(f"\nAutores encontrados para '{args.author}':")
            print("-"*60)
            for a in authors:
                pd = "✓ DP" if a['death_year'] and (datetime.now().year - a['death_year']) >= 70 else ""
                print(f"• {a['name']} ({a['books_count']} livros) {pd}")
                if a['death_year']:
                    print(f"  Morte: {a['death_year']}")
        return 0

    # Top autores
    if args.top:
        with BooksDatabase() as db:
            authors = db.get_top_authors(limit=args.top)
            print(f"\nTop {args.top} autores em domínio público:")
            print("-"*60)
            for i, a in enumerate(authors, 1):
                print(f"{i:3}. {a['name'][:40]:<40} {a['books_count']:>5} livros")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
