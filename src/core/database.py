# -*- coding: utf-8 -*-
"""
DATABASE.PY - Gerenciador de Banco de Dados (Versão Atualizada)
================================================================
Banco SQLite para gerenciar livros do Project Gutenberg.

Inclui:
- Campo 'processado' para tracking de livros já processados
- Métodos para API REST
- Estatísticas avançadas
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
from dataclasses import dataclass, asdict

import requests
from tqdm import tqdm

# Importa configurações
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    DATABASE_PATH, DATA_DIR, GUTENBERG_CSV_URL,
    LOG_DIR, CALIBRE_DIR
)

# ============================================================================
# LOGGING
# ============================================================================

LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(LOG_DIR / "database.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class Author:
    id: int
    name: str
    name_normalized: str
    birth_year: Optional[int]
    death_year: Optional[int]
    books_count: int = 0

    def is_public_domain(self) -> bool:
        if self.death_year is None:
            return False
        return (datetime.now().year - self.death_year) >= 70

    def to_dict(self) -> dict:
        d = asdict(self)
        d['is_public_domain'] = self.is_public_domain()
        return d

@dataclass
class Book:
    id: str
    title: str
    title_normalized: str
    author_id: int
    author_name: str
    language: str
    issued: str
    source: str
    epub_url: str
    txt_url: str
    downloaded: bool
    processado: bool  # NOVO CAMPO
    processado_em: Optional[str]  # Data do processamento
    docx_path: Optional[str]  # Caminho do DOCX gerado

    def to_dict(self) -> dict:
        return asdict(self)

# ============================================================================
# DATABASE MANAGER
# ============================================================================

class BooksDatabase:
    """Gerenciador do banco de dados SQLite."""

    def __init__(self, db_path: Path = DATABASE_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = None

    def connect(self):
        """Conecta ao banco."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
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

        # Tabela de livros (COM CAMPO PROCESSADO)
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
                processado INTEGER DEFAULT 0,
                processado_em TEXT,
                docx_path TEXT,
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

        # Índices
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_authors_name ON authors(name_normalized)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_authors_death ON authors(death_year)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_title ON books(title_normalized)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_author ON books(author_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_language ON books(language)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_downloaded ON books(downloaded)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_books_processado ON books(processado)')

        self.conn.commit()
        logger.info("Tabelas criadas/verificadas")

    def migrate_add_processado(self):
        """Adiciona campo processado se não existir (migration)."""
        cursor = self.conn.cursor()

        # Verifica se a coluna existe
        cursor.execute("PRAGMA table_info(books)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'processado' not in columns:
            logger.info("Adicionando coluna 'processado' à tabela books...")
            cursor.execute('ALTER TABLE books ADD COLUMN processado INTEGER DEFAULT 0')
            self.conn.commit()
            logger.info("Coluna 'processado' adicionada")

        if 'processado_em' not in columns:
            logger.info("Adicionando coluna 'processado_em' à tabela books...")
            cursor.execute('ALTER TABLE books ADD COLUMN processado_em TEXT')
            self.conn.commit()
            logger.info("Coluna 'processado_em' adicionada")

        if 'docx_path' not in columns:
            logger.info("Adicionando coluna 'docx_path' à tabela books...")
            cursor.execute('ALTER TABLE books ADD COLUMN docx_path TEXT')
            self.conn.commit()
            logger.info("Coluna 'docx_path' adicionada")

    def normalize_text(self, text: str) -> str:
        """Normaliza texto para busca."""
        if not text:
            return ""
        import unicodedata
        text = unicodedata.normalize('NFKD', text)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        return text.lower().strip()

    def parse_author_string(self, author_str: str) -> Tuple[str, Optional[int], Optional[int]]:
        """Parse string de autor do Gutenberg."""
        if not author_str:
            return "Unknown", None, None

        match = re.search(r'(\d{4})\s*-\s*(\d{4})?', author_str)
        birth_year = None
        death_year = None

        if match:
            birth_year = int(match.group(1))
            if match.group(2):
                death_year = int(match.group(2))

        name = re.sub(r',?\s*\d{4}\s*-\s*\d{4}?', '', author_str).strip()
        name = re.sub(r',?\s*-\s*$', '', name).strip()

        if ',' in name:
            parts = name.split(',', 1)
            if len(parts) == 2:
                name = f"{parts[1].strip()} {parts[0].strip()}"

        return name, birth_year, death_year

    def get_or_create_author(self, name: str, birth_year: int = None, death_year: int = None) -> int:
        """Obtém ou cria autor, retorna ID."""
        cursor = self.conn.cursor()
        name_norm = self.normalize_text(name)

        cursor.execute('SELECT id FROM authors WHERE name_normalized = ?', (name_norm,))
        row = cursor.fetchone()

        if row:
            if birth_year or death_year:
                cursor.execute('''
                    UPDATE authors SET
                        birth_year = COALESCE(birth_year, ?),
                        death_year = COALESCE(death_year, ?)
                    WHERE id = ?
                ''', (birth_year, death_year, row['id']))
            return row['id']

        cursor.execute('''
            INSERT INTO authors (name, name_normalized, birth_year, death_year)
            VALUES (?, ?, ?, ?)
        ''', (name, name_norm, birth_year, death_year))

        return cursor.lastrowid

    def add_book(self, book_id: str, title: str, author_id: int, language: str,
                 issued: str, subjects: List[str] = None, source: str = "gutenberg"):
        """Adiciona livro ao banco."""
        cursor = self.conn.cursor()

        epub_url = f"https://www.gutenberg.org/ebooks/{book_id}.epub.images"
        txt_url = f"https://www.gutenberg.org/ebooks/{book_id}.txt.utf-8"

        try:
            cursor.execute('''
                INSERT OR IGNORE INTO books
                (id, title, title_normalized, author_id, language, issued, source, epub_url, txt_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (book_id, title, self.normalize_text(title), author_id,
                  language, issued, source, epub_url, txt_url))

            if subjects:
                for subject in subjects:
                    if subject and subject.strip():
                        # Simplificado - não cria subjects separadamente
                        pass

        except sqlite3.IntegrityError:
            pass

    # =========================================================================
    # MÉTODOS DE PROCESSAMENTO
    # =========================================================================

    def mark_as_processed(self, book_id: str, docx_path: str = None):
        """Marca livro como processado."""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE books SET
                processado = 1,
                processado_em = ?,
                docx_path = ?
            WHERE id = ?
        ''', (datetime.now().isoformat(), docx_path, book_id))
        self.conn.commit()
        logger.info(f"Livro {book_id} marcado como processado")

    def unmark_processed(self, book_id: str):
        """Desmarca livro como processado."""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE books SET
                processado = 0,
                processado_em = NULL,
                docx_path = NULL
            WHERE id = ?
        ''', (book_id,))
        self.conn.commit()

    def mark_downloaded(self, book_id: str):
        """Marca livro como baixado."""
        cursor = self.conn.cursor()
        cursor.execute('UPDATE books SET downloaded = 1 WHERE id = ?', (book_id,))
        self.conn.commit()

    # =========================================================================
    # CONSULTAS
    # =========================================================================

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

        cursor.execute('SELECT COUNT(*) FROM books WHERE processado = 1')
        stats['processed_books'] = cursor.fetchone()[0]

        current_year = datetime.now().year
        cursor.execute(f'''
            SELECT COUNT(*) FROM authors
            WHERE death_year IS NOT NULL AND death_year <= {current_year - 70}
        ''')
        stats['public_domain_authors'] = cursor.fetchone()[0]

        cursor.execute('SELECT COUNT(DISTINCT language) FROM books')
        stats['languages'] = cursor.fetchone()[0]

        # Top idiomas
        cursor.execute('''
            SELECT language, COUNT(*) as cnt
            FROM books
            GROUP BY language
            ORDER BY cnt DESC
            LIMIT 10
        ''')
        stats['top_languages'] = [{'language': r[0], 'count': r[1]} for r in cursor.fetchall()]

        return stats

    def search_books(self, query: str = None, language: str = None,
                     public_domain_only: bool = False, processed: bool = None,
                     downloaded: bool = None, limit: int = 100, offset: int = 0) -> List[Dict]:
        """Busca livros com filtros."""
        cursor = self.conn.cursor()

        sql = '''
            SELECT b.id, b.title, b.language, b.epub_url, b.txt_url,
                   b.downloaded, b.processado, b.processado_em, b.docx_path,
                   a.name as author_name, a.death_year
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.id
            WHERE 1=1
        '''
        params = []

        if query:
            query_norm = self.normalize_text(query)
            sql += ' AND (b.title_normalized LIKE ? OR a.name_normalized LIKE ?)'
            params.extend([f'%{query_norm}%', f'%{query_norm}%'])

        if language:
            sql += ' AND b.language = ?'
            params.append(language)

        if public_domain_only:
            current_year = datetime.now().year
            sql += f' AND a.death_year IS NOT NULL AND a.death_year <= {current_year - 70}'

        if processed is not None:
            sql += ' AND b.processado = ?'
            params.append(1 if processed else 0)

        if downloaded is not None:
            sql += ' AND b.downloaded = ?'
            params.append(1 if downloaded else 0)

        sql += ' ORDER BY a.name, b.title LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_book_by_id(self, book_id: str) -> Optional[Dict]:
        """Retorna um livro pelo ID."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT b.*, a.name as author_name, a.death_year
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.id
            WHERE b.id = ?
        ''', (book_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_authors(self, query: str = None, public_domain_only: bool = False,
                    limit: int = 100, offset: int = 0) -> List[Dict]:
        """Retorna autores."""
        cursor = self.conn.cursor()

        sql = '''
            SELECT id, name, birth_year, death_year, books_count
            FROM authors
            WHERE books_count > 0
        '''
        params = []

        if query:
            sql += ' AND name_normalized LIKE ?'
            params.append(f'%{self.normalize_text(query)}%')

        if public_domain_only:
            current_year = datetime.now().year
            sql += f' AND death_year IS NOT NULL AND death_year <= {current_year - 70}'

        sql += ' ORDER BY books_count DESC LIMIT ? OFFSET ?'
        params.extend([limit, offset])

        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def get_books_by_author(self, author_id: int = None, author_name: str = None,
                            limit: int = 100) -> List[Dict]:
        """Retorna livros de um autor."""
        cursor = self.conn.cursor()

        if author_name and not author_id:
            cursor.execute(
                'SELECT id FROM authors WHERE name_normalized LIKE ?',
                (f'%{self.normalize_text(author_name)}%',)
            )
            row = cursor.fetchone()
            if row:
                author_id = row[0]
            else:
                return []

        cursor.execute('''
            SELECT b.*, a.name as author_name
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.id
            WHERE b.author_id = ?
            ORDER BY b.title
            LIMIT ?
        ''', (author_id, limit))

        return [dict(row) for row in cursor.fetchall()]

    def get_pending_books(self, language: str = None, limit: int = 100) -> List[Dict]:
        """Retorna livros pendentes (baixados mas não processados)."""
        cursor = self.conn.cursor()

        sql = '''
            SELECT b.*, a.name as author_name
            FROM books b
            LEFT JOIN authors a ON b.author_id = a.id
            WHERE b.downloaded = 1 AND b.processado = 0
        '''
        params = []

        if language:
            sql += ' AND b.language = ?'
            params.append(language)

        sql += ' ORDER BY a.name, b.title LIMIT ?'
        params.append(limit)

        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]

    def update_author_counts(self):
        """Atualiza contagem de livros por autor."""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE authors SET books_count = (
                SELECT COUNT(*) FROM books WHERE books.author_id = authors.id
            )
        ''')
        self.conn.commit()

    def get_languages(self) -> List[Dict]:
        """Retorna lista de idiomas com contagem."""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT language, COUNT(*) as count
            FROM books
            GROUP BY language
            ORDER BY count DESC
        ''')
        return [{'code': r[0], 'count': r[1]} for r in cursor.fetchall()]


# ============================================================================
# IMPORTAÇÃO DO GUTENBERG
# ============================================================================

def download_gutenberg_catalog(force: bool = False) -> bool:
    """Baixa o catálogo do Gutenberg."""
    csv_path = DATA_DIR / "pg_catalog.csv"
    gz_path = DATA_DIR / "pg_catalog.csv.gz"

    if csv_path.exists() and not force:
        age = datetime.now().timestamp() - csv_path.stat().st_mtime
        if age < 7 * 24 * 3600:
            logger.info(f"Catálogo existente: {csv_path}")
            return True

    logger.info("Baixando catálogo do Project Gutenberg...")

    try:
        response = requests.get(
            GUTENBERG_CSV_URL,
            stream=True,
            headers={'User-Agent': 'BooksKDP/1.0'},
            timeout=60
        )
        total = int(response.headers.get('content-length', 0))

        with open(gz_path, 'wb') as f:
            with tqdm(total=total, unit='B', unit_scale=True, desc="Baixando") as pbar:
                for chunk in response.iter_content(8192):
                    f.write(chunk)
                    pbar.update(len(chunk))

        logger.info("Descompactando...")
        with gzip.open(gz_path, 'rb') as f_in:
            with open(csv_path, 'wb') as f_out:
                f_out.write(f_in.read())

        gz_path.unlink(missing_ok=True)
        logger.info(f"Catálogo salvo: {csv_path}")
        return True

    except Exception as e:
        logger.error(f"Erro ao baixar: {e}")
        return False


def import_gutenberg_to_sqlite(force: bool = False):
    """Importa catálogo CSV para SQLite."""
    db = BooksDatabase()
    csv_path = DATA_DIR / "pg_catalog.csv"

    with db:
        db.create_tables()
        db.migrate_add_processado()

        if not force:
            stats = db.get_stats()
            if stats['total_books'] > 50000:
                logger.info(f"Banco já populado: {stats['total_books']} livros")
                return True

        if not csv_path.exists():
            if not download_gutenberg_catalog():
                return False

        logger.info("Importando catálogo para SQLite...")

        with open(csv_path, 'r', encoding='utf-8', errors='ignore') as f:
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

                    author_name, birth_year, death_year = db.parse_author_string(author_str)
                    author_id = db.get_or_create_author(author_name, birth_year, death_year)

                    db.add_book(
                        book_id=book_id,
                        title=title,
                        author_id=author_id,
                        language=language,
                        issued=issued,
                        subjects=[s.strip() for s in subjects if s.strip()]
                    )

                    count += 1

                    if count % 1000 == 0:
                        db.conn.commit()

                except Exception:
                    continue

        db.conn.commit()

        logger.info("Atualizando contagens...")
        db.update_author_counts()

        stats = db.get_stats()
        logger.info(f"\n{'='*50}")
        logger.info("IMPORTAÇÃO CONCLUÍDA!")
        logger.info(f"Livros: {stats['total_books']:,}")
        logger.info(f"Autores: {stats['total_authors']:,}")
        logger.info(f"Autores em domínio público: {stats['public_domain_authors']:,}")
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
    parser.add_argument('--migrate', action='store_true',
                       help='Executa migrations (adiciona campos novos)')
    parser.add_argument('--search', type=str, help='Busca livros')
    parser.add_argument('--pending', action='store_true', help='Lista livros pendentes')

    args = parser.parse_args()

    if args.do_import:
        import_gutenberg_to_sqlite(force=args.force)
        return 0

    if args.migrate:
        with BooksDatabase() as db:
            db.migrate_add_processado()
        logger.info("Migration concluída")
        return 0

    if args.stats:
        with BooksDatabase() as db:
            stats = db.get_stats()
            print("\n" + "="*50)
            print("ESTATÍSTICAS DO BANCO")
            print("="*50)
            for key, value in stats.items():
                if isinstance(value, list):
                    continue
                print(f"{key}: {value:,}" if isinstance(value, int) else f"{key}: {value}")
            print("="*50)
        return 0

    if args.search:
        with BooksDatabase() as db:
            books = db.search_books(args.search, limit=20)
            print(f"\nResultados para '{args.search}':")
            for b in books:
                status = "[P]" if b.get('processado') else "[ ]"
                print(f"{status} {b['title'][:50]} - {b['author_name']}")
        return 0

    if args.pending:
        with BooksDatabase() as db:
            books = db.get_pending_books(limit=20)
            print(f"\nLivros pendentes de processamento:")
            for b in books:
                print(f"  {b['id']}: {b['title'][:50]}")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
