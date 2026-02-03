# -*- coding: utf-8 -*-
"""
DATABASE CENTRALIZADO - BooksKDP
================================
Gerencia todos os dados do pipeline de produção de livros.

Uso:
    from database import db

    # Registrar livro
    db.registrar_livro(titulo="O Quarto Caminho", autor="Ouspensky", idioma="pt")

    # Atualizar status
    db.atualizar_status(livro_id, "docx_gerado", docx_path="/path/to/file.docx")

    # Estatísticas
    stats = db.estatisticas()
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Any
from contextlib import contextmanager

# Caminho do banco
DB_PATH = Path(__file__).parent / "data" / "kdp_producao.db"


class KDPDatabase:
    """Banco de dados centralizado para produção KDP."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    @contextmanager
    def _conn(self):
        """Context manager para conexões."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        """Inicializa o banco de dados."""
        with self._conn() as conn:
            conn.executescript('''
                -- Livros em produção
                CREATE TABLE IF NOT EXISTS livros (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    titulo TEXT NOT NULL,
                    titulo_original TEXT,
                    autor TEXT NOT NULL,
                    idioma_original TEXT,
                    idioma_final TEXT DEFAULT 'pt',
                    genero TEXT,
                    categoria TEXT,

                    -- Arquivos fonte
                    txt_path TEXT,
                    txt_size INTEGER,
                    txt_chars INTEGER,

                    -- Status do pipeline
                    status TEXT DEFAULT 'pendente',
                    ocr_corrigido INTEGER DEFAULT 0,
                    traduzido INTEGER DEFAULT 0,
                    notas_geradas INTEGER DEFAULT 0,
                    docx_gerado INTEGER DEFAULT 0,
                    capa_gerada INTEGER DEFAULT 0,
                    publicado INTEGER DEFAULT 0,

                    -- Caminhos de saída
                    docx_path TEXT,
                    capa_path TEXT,

                    -- Metadados
                    num_paginas INTEGER,
                    num_palavras INTEGER,
                    num_notas INTEGER,

                    -- Timestamps
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processado_em TIMESTAMP,
                    publicado_em TIMESTAMP,

                    -- Referência ao books.db original
                    book_id_original TEXT,

                    UNIQUE(titulo, autor)
                );

                -- Cache de correções OCR
                CREATE TABLE IF NOT EXISTS correcoes_ocr (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    texto_hash TEXT UNIQUE NOT NULL,
                    texto_original TEXT,
                    texto_corrigido TEXT,
                    modelo TEXT,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Cache de traduções
                CREATE TABLE IF NOT EXISTS traducoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    texto_hash TEXT UNIQUE NOT NULL,
                    idioma_origem TEXT,
                    idioma_destino TEXT DEFAULT 'pt',
                    texto_original TEXT,
                    texto_traduzido TEXT,
                    modelo TEXT,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Cache de notas de rodapé
                CREATE TABLE IF NOT EXISTS notas_rodape (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    termo TEXT UNIQUE NOT NULL,
                    tipo TEXT,
                    explicacao TEXT,
                    modelo TEXT,
                    verificado INTEGER DEFAULT 0,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Histórico de capas geradas
                CREATE TABLE IF NOT EXISTS capas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    livro_id INTEGER,
                    prompt TEXT,
                    estilo TEXT,
                    modelo TEXT DEFAULT 'flux-dev',
                    caminho TEXT,
                    width INTEGER,
                    height INTEGER,
                    aprovada INTEGER DEFAULT 0,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (livro_id) REFERENCES livros(id)
                );

                -- Log de processamento
                CREATE TABLE IF NOT EXISTS log_processamento (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    livro_id INTEGER,
                    etapa TEXT,
                    status TEXT,
                    mensagem TEXT,
                    duracao_ms INTEGER,
                    criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (livro_id) REFERENCES livros(id)
                );

                -- Configurações
                CREATE TABLE IF NOT EXISTS configuracoes (
                    chave TEXT PRIMARY KEY,
                    valor TEXT,
                    atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                -- Índices
                CREATE INDEX IF NOT EXISTS idx_livros_status ON livros(status);
                CREATE INDEX IF NOT EXISTS idx_livros_idioma ON livros(idioma_original);
                CREATE INDEX IF NOT EXISTS idx_log_livro ON log_processamento(livro_id);
            ''')

    # =========================================================================
    # LIVROS
    # =========================================================================

    def registrar_livro(self, titulo: str, autor: str, idioma_original: str = None,
                        txt_path: str = None, genero: str = None, **kwargs) -> int:
        """Registra um novo livro para produção."""
        with self._conn() as conn:
            try:
                cur = conn.execute('''
                    INSERT INTO livros (titulo, autor, idioma_original, txt_path, genero)
                    VALUES (?, ?, ?, ?, ?)
                ''', (titulo, autor, idioma_original, txt_path, genero))
                return cur.lastrowid
            except sqlite3.IntegrityError:
                # Já existe, retorna ID existente
                cur = conn.execute(
                    'SELECT id FROM livros WHERE titulo = ? AND autor = ?',
                    (titulo, autor)
                )
                return cur.fetchone()['id']

    def atualizar_livro(self, livro_id: int, **campos) -> bool:
        """Atualiza campos de um livro."""
        if not campos:
            return False

        campos['atualizado_em'] = datetime.now().isoformat()

        sets = ', '.join(f'{k} = ?' for k in campos.keys())
        values = list(campos.values()) + [livro_id]

        with self._conn() as conn:
            conn.execute(f'UPDATE livros SET {sets} WHERE id = ?', values)
            return True

    def buscar_livro(self, livro_id: int = None, titulo: str = None) -> Optional[Dict]:
        """Busca um livro por ID ou título."""
        with self._conn() as conn:
            if livro_id:
                cur = conn.execute('SELECT * FROM livros WHERE id = ?', (livro_id,))
            elif titulo:
                cur = conn.execute('SELECT * FROM livros WHERE titulo LIKE ?', (f'%{titulo}%',))
            else:
                return None

            row = cur.fetchone()
            return dict(row) if row else None

    def listar_livros(self, status: str = None, idioma: str = None,
                      limite: int = 100, offset: int = 0) -> List[Dict]:
        """Lista livros com filtros."""
        query = 'SELECT * FROM livros WHERE 1=1'
        params = []

        if status:
            query += ' AND status = ?'
            params.append(status)
        if idioma:
            query += ' AND idioma_original = ?'
            params.append(idioma)

        query += ' ORDER BY criado_em DESC LIMIT ? OFFSET ?'
        params.extend([limite, offset])

        with self._conn() as conn:
            cur = conn.execute(query, params)
            return [dict(row) for row in cur.fetchall()]

    def livros_pendentes(self, etapa: str = None) -> List[Dict]:
        """Retorna livros pendentes de processamento."""
        with self._conn() as conn:
            if etapa == 'ocr':
                cur = conn.execute('SELECT * FROM livros WHERE ocr_corrigido = 0 AND txt_path IS NOT NULL')
            elif etapa == 'traducao':
                cur = conn.execute('SELECT * FROM livros WHERE traduzido = 0 AND idioma_original != "pt"')
            elif etapa == 'notas':
                cur = conn.execute('SELECT * FROM livros WHERE notas_geradas = 0')
            elif etapa == 'docx':
                cur = conn.execute('SELECT * FROM livros WHERE docx_gerado = 0')
            elif etapa == 'capa':
                cur = conn.execute('SELECT * FROM livros WHERE capa_gerada = 0')
            else:
                cur = conn.execute('SELECT * FROM livros WHERE status = "pendente"')

            return [dict(row) for row in cur.fetchall()]

    # =========================================================================
    # CACHE
    # =========================================================================

    def get_correcao(self, texto_hash: str) -> Optional[str]:
        """Busca correção OCR em cache."""
        with self._conn() as conn:
            cur = conn.execute(
                'SELECT texto_corrigido FROM correcoes_ocr WHERE texto_hash = ?',
                (texto_hash,)
            )
            row = cur.fetchone()
            return row['texto_corrigido'] if row else None

    def set_correcao(self, texto_hash: str, original: str, corrigido: str, modelo: str):
        """Salva correção OCR no cache."""
        with self._conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO correcoes_ocr
                (texto_hash, texto_original, texto_corrigido, modelo)
                VALUES (?, ?, ?, ?)
            ''', (texto_hash, original, corrigido, modelo))

    def get_traducao(self, texto_hash: str) -> Optional[str]:
        """Busca tradução em cache."""
        with self._conn() as conn:
            cur = conn.execute(
                'SELECT texto_traduzido FROM traducoes WHERE texto_hash = ?',
                (texto_hash,)
            )
            row = cur.fetchone()
            return row['texto_traduzido'] if row else None

    def set_traducao(self, texto_hash: str, original: str, traduzido: str,
                     idioma_origem: str, modelo: str):
        """Salva tradução no cache."""
        with self._conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO traducoes
                (texto_hash, texto_original, texto_traduzido, idioma_origem, modelo)
                VALUES (?, ?, ?, ?, ?)
            ''', (texto_hash, original, traduzido, idioma_origem, modelo))

    def get_nota(self, termo: str) -> Optional[str]:
        """Busca nota de rodapé em cache."""
        with self._conn() as conn:
            cur = conn.execute(
                'SELECT explicacao FROM notas_rodape WHERE termo = ?',
                (termo.lower(),)
            )
            row = cur.fetchone()
            return row['explicacao'] if row else None

    def set_nota(self, termo: str, tipo: str, explicacao: str, modelo: str):
        """Salva nota de rodapé no cache."""
        with self._conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO notas_rodape (termo, tipo, explicacao, modelo)
                VALUES (?, ?, ?, ?)
            ''', (termo.lower(), tipo, explicacao, modelo))

    # =========================================================================
    # CAPAS
    # =========================================================================

    def registrar_capa(self, livro_id: int, prompt: str, caminho: str,
                       estilo: str = None, modelo: str = 'flux-dev',
                       width: int = 1600, height: int = 2560) -> int:
        """Registra uma capa gerada."""
        with self._conn() as conn:
            cur = conn.execute('''
                INSERT INTO capas (livro_id, prompt, estilo, modelo, caminho, width, height)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (livro_id, prompt, estilo, modelo, caminho, width, height))
            return cur.lastrowid

    def listar_capas(self, livro_id: int = None) -> List[Dict]:
        """Lista capas geradas."""
        with self._conn() as conn:
            if livro_id:
                cur = conn.execute('SELECT * FROM capas WHERE livro_id = ?', (livro_id,))
            else:
                cur = conn.execute('SELECT * FROM capas ORDER BY criado_em DESC')
            return [dict(row) for row in cur.fetchall()]

    # =========================================================================
    # LOG
    # =========================================================================

    def log(self, livro_id: int, etapa: str, status: str,
            mensagem: str = None, duracao_ms: int = None):
        """Registra entrada no log de processamento."""
        with self._conn() as conn:
            conn.execute('''
                INSERT INTO log_processamento (livro_id, etapa, status, mensagem, duracao_ms)
                VALUES (?, ?, ?, ?, ?)
            ''', (livro_id, etapa, status, mensagem, duracao_ms))

    # =========================================================================
    # ESTATÍSTICAS
    # =========================================================================

    def estatisticas(self) -> Dict[str, Any]:
        """Retorna estatísticas gerais."""
        with self._conn() as conn:
            stats = {}

            # Total de livros
            stats['total_livros'] = conn.execute('SELECT COUNT(*) FROM livros').fetchone()[0]

            # Por status
            cur = conn.execute('SELECT status, COUNT(*) as n FROM livros GROUP BY status')
            stats['por_status'] = {row['status']: row['n'] for row in cur.fetchall()}

            # Por idioma
            cur = conn.execute('SELECT idioma_original, COUNT(*) as n FROM livros GROUP BY idioma_original')
            stats['por_idioma'] = {row['idioma_original'] or 'desconhecido': row['n'] for row in cur.fetchall()}

            # Pipeline
            stats['ocr_corrigidos'] = conn.execute('SELECT COUNT(*) FROM livros WHERE ocr_corrigido = 1').fetchone()[0]
            stats['traduzidos'] = conn.execute('SELECT COUNT(*) FROM livros WHERE traduzido = 1').fetchone()[0]
            stats['com_notas'] = conn.execute('SELECT COUNT(*) FROM livros WHERE notas_geradas = 1').fetchone()[0]
            stats['docx_gerados'] = conn.execute('SELECT COUNT(*) FROM livros WHERE docx_gerado = 1').fetchone()[0]
            stats['capas_geradas'] = conn.execute('SELECT COUNT(*) FROM livros WHERE capa_gerada = 1').fetchone()[0]
            stats['publicados'] = conn.execute('SELECT COUNT(*) FROM livros WHERE publicado = 1').fetchone()[0]

            # Cache
            stats['cache_correcoes'] = conn.execute('SELECT COUNT(*) FROM correcoes_ocr').fetchone()[0]
            stats['cache_traducoes'] = conn.execute('SELECT COUNT(*) FROM traducoes').fetchone()[0]
            stats['cache_notas'] = conn.execute('SELECT COUNT(*) FROM notas_rodape').fetchone()[0]

            # Capas
            stats['total_capas'] = conn.execute('SELECT COUNT(*) FROM capas').fetchone()[0]

            return stats

    def relatorio(self) -> str:
        """Gera relatório formatado."""
        stats = self.estatisticas()

        lines = [
            "=" * 50,
            "RELATÓRIO DE PRODUÇÃO KDP",
            "=" * 50,
            "",
            f"Total de livros: {stats['total_livros']}",
            "",
            "Por status:",
        ]

        for status, count in stats.get('por_status', {}).items():
            lines.append(f"  {status}: {count}")

        lines.extend([
            "",
            "Pipeline:",
            f"  OCR corrigidos:  {stats['ocr_corrigidos']}",
            f"  Traduzidos:      {stats['traduzidos']}",
            f"  Com notas:       {stats['com_notas']}",
            f"  DOCX gerados:    {stats['docx_gerados']}",
            f"  Capas geradas:   {stats['capas_geradas']}",
            f"  Publicados:      {stats['publicados']}",
            "",
            "Cache:",
            f"  Correções OCR:   {stats['cache_correcoes']}",
            f"  Traduções:       {stats['cache_traducoes']}",
            f"  Notas rodapé:    {stats['cache_notas']}",
            "",
            "=" * 50,
        ])

        return "\n".join(lines)


# Instância global
db = KDPDatabase()


# ============================================================================
# CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gerenciador de banco de dados KDP")
    parser.add_argument('--stats', action='store_true', help='Mostra estatísticas')
    parser.add_argument('--pendentes', type=str, help='Lista pendentes (ocr/traducao/notas/docx/capa)')
    parser.add_argument('--importar-txt', type=Path, help='Importa livros de pasta txt/')

    args = parser.parse_args()

    if args.stats:
        print(db.relatorio())

    elif args.pendentes:
        livros = db.livros_pendentes(args.pendentes)
        print(f"Pendentes ({args.pendentes}): {len(livros)}")
        for l in livros[:10]:
            print(f"  - {l['titulo']} ({l['autor']})")

    elif args.importar_txt:
        from organizar_livros import scan_txt_folder, detect_language

        print("Importando livros...")
        results = scan_txt_folder()
        count = 0

        for lang, folders in results.items():
            for folder in folders:
                txt_files = list(folder.glob("*.txt"))
                if txt_files:
                    main_file = max(txt_files, key=lambda f: f.stat().st_size)
                    db.registrar_livro(
                        titulo=folder.name,
                        autor="Desconhecido",
                        idioma_original=lang,
                        txt_path=str(main_file)
                    )
                    count += 1

        print(f"Importados: {count} livros")

    else:
        parser.print_help()
