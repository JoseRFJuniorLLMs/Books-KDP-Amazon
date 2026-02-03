# -*- coding: utf-8 -*-
"""
VALIDAÇÃO DE DOMÍNIO PÚBLICO
============================
Verifica se livros estão em domínio público (autor morto há 70+ anos).
Remove livros que NÃO estão em domínio público.

Regra: Autor deve ter morrido antes de 1956 (70 anos antes de 2026)

Uso:
    python validar_dominio_publico.py --scan      # Apenas analisa
    python validar_dominio_publico.py --delete    # Remove livros não-públicos
"""

import os
import sys
import sqlite3
import shutil
import argparse
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

BASE_DIR = Path(__file__).parent
TXT_DIR = BASE_DIR / "txt"
DATA_DIR = BASE_DIR / "data"
BOOKS_DB = DATA_DIR / "books.db"
ARCHIVE_DIR = BASE_DIR / "archive" / "nao_dominio_publico"

# Ano limite para domínio público (morte do autor)
ANO_ATUAL = datetime.now().year
ANO_LIMITE = ANO_ATUAL - 70  # 2026 - 70 = 1956

# Autores conhecidos por NÃO estarem em domínio público
AUTORES_PROTEGIDOS = {
    'osho', 'rajneesh', 'bhagwan',
    'eckhart tolle',
    'deepak chopra',
    'paulo coelho',
    'james clear',
    'jordan peterson',
    'yuval harari',
    'stephen hawking',  # Morreu 2018
    'richard dawkins',
    'daniel goleman',
    'miguel nicolelis',
    'leonard mlodinow',
    # Adicione mais conforme necessário
}

# Padrões que indicam livro possivelmente protegido
PATTERNS_PROTEGIDOS = [
    r'(?i)copyright\s*©?\s*(19[6-9]\d|20[0-2]\d)',  # Copyright após 1960
    r'(?i)all rights reserved',
    r'(?i)proibida a reprodução',
    r'(?i)direitos reservados',
]

# =============================================================================
# CLASSES
# =============================================================================

@dataclass
class LivroAnalise:
    titulo: str
    pasta: str
    autor: str
    ano_morte: Optional[int]
    dominio_publico: bool
    motivo: str
    fonte: str  # 'database', 'nome', 'conteudo', 'desconhecido'

# =============================================================================
# FUNÇÕES
# =============================================================================

def carregar_autores_db() -> Dict[str, Tuple[str, Optional[int]]]:
    """Carrega autores do banco de dados."""
    autores = {}

    if not BOOKS_DB.exists():
        print(f"AVISO: Banco {BOOKS_DB} não encontrado")
        return autores

    conn = sqlite3.connect(BOOKS_DB)
    cur = conn.execute('SELECT name, name_normalized, death_year FROM authors')

    for row in cur:
        nome, nome_norm, ano_morte = row
        autores[nome_norm.lower()] = (nome, ano_morte)
        # Também adiciona variações
        partes = nome_norm.lower().split()
        if len(partes) >= 2:
            # Sobrenome
            autores[partes[-1]] = (nome, ano_morte)
            # Primeiro + último nome
            autores[f"{partes[0]} {partes[-1]}"] = (nome, ano_morte)

    conn.close()
    return autores

def extrair_autor_do_nome(nome_pasta: str) -> Optional[str]:
    """Tenta extrair nome do autor do nome da pasta."""
    # Padrões comuns
    patterns = [
        r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # Nome próprio no início
        r'[-_]([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)',  # Após hífen/underscore
        r'\[([^\]]+)\]',  # Entre colchetes
    ]

    for pattern in patterns:
        match = re.search(pattern, nome_pasta)
        if match:
            return match.group(1)

    return None

def verificar_conteudo_protegido(txt_path: Path) -> Tuple[bool, str]:
    """Verifica se o conteúdo tem indicadores de proteção."""
    try:
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as f:
            texto = f.read(10000)  # Primeiros 10k chars

        for pattern in PATTERNS_PROTEGIDOS:
            if re.search(pattern, texto):
                return True, f"Contém: {pattern}"

        # Verifica menção a autores protegidos
        texto_lower = texto.lower()
        for autor in AUTORES_PROTEGIDOS:
            if autor in texto_lower:
                return True, f"Autor protegido: {autor}"

    except Exception as e:
        pass

    return False, ""

def analisar_livro(pasta: Path, autores_db: Dict) -> LivroAnalise:
    """Analisa se um livro está em domínio público."""
    titulo = pasta.name

    # Procura arquivo TXT
    txt_files = list(pasta.glob("*.txt"))
    if not txt_files:
        return LivroAnalise(
            titulo=titulo, pasta=str(pasta), autor="?",
            ano_morte=None, dominio_publico=False,
            motivo="Sem arquivo TXT", fonte="erro"
        )

    txt_path = max(txt_files, key=lambda f: f.stat().st_size)

    # 1. Verifica por nome de autor conhecido protegido
    titulo_lower = titulo.lower()
    for autor_protegido in AUTORES_PROTEGIDOS:
        if autor_protegido in titulo_lower:
            return LivroAnalise(
                titulo=titulo, pasta=str(pasta), autor=autor_protegido,
                ano_morte=None, dominio_publico=False,
                motivo=f"Autor protegido: {autor_protegido}", fonte="nome"
            )

    # 2. Verifica conteúdo
    protegido, motivo_conteudo = verificar_conteudo_protegido(txt_path)
    if protegido:
        return LivroAnalise(
            titulo=titulo, pasta=str(pasta), autor="?",
            ano_morte=None, dominio_publico=False,
            motivo=motivo_conteudo, fonte="conteudo"
        )

    # 3. Tenta encontrar autor no banco de dados
    # Busca pelo nome da pasta
    for nome_db, (autor_nome, ano_morte) in autores_db.items():
        if nome_db in titulo_lower or titulo_lower in nome_db:
            if ano_morte:
                if ano_morte <= ANO_LIMITE:
                    return LivroAnalise(
                        titulo=titulo, pasta=str(pasta), autor=autor_nome,
                        ano_morte=ano_morte, dominio_publico=True,
                        motivo=f"Autor morreu em {ano_morte} (< {ANO_LIMITE})", fonte="database"
                    )
                else:
                    return LivroAnalise(
                        titulo=titulo, pasta=str(pasta), autor=autor_nome,
                        ano_morte=ano_morte, dominio_publico=False,
                        motivo=f"Autor morreu em {ano_morte} (> {ANO_LIMITE})", fonte="database"
                    )

    # 4. Tenta extrair autor do nome
    autor_extraido = extrair_autor_do_nome(titulo)
    if autor_extraido:
        autor_lower = autor_extraido.lower()
        if autor_lower in autores_db:
            autor_nome, ano_morte = autores_db[autor_lower]
            if ano_morte:
                dp = ano_morte <= ANO_LIMITE
                return LivroAnalise(
                    titulo=titulo, pasta=str(pasta), autor=autor_nome,
                    ano_morte=ano_morte, dominio_publico=dp,
                    motivo=f"Autor morreu em {ano_morte}", fonte="database"
                )

    # 5. Autores clássicos conhecidos (antes de 1900 = certamente público)
    autores_antigos = [
        'aristoteles', 'aristóteles', 'plato', 'platão', 'socrates', 'sócrates',
        'homer', 'homero', 'virgil', 'virgílio', 'dante', 'shakespeare',
        'cervantes', 'dostoevsky', 'dostoiévski', 'tolstoy', 'tolstói',
        'nietzsche', 'kant', 'hegel', 'marx', 'freud', 'jung',
        'dickens', 'austen', 'wilde', 'poe', 'twain',
        'goethe', 'schiller', 'voltaire', 'rousseau', 'montaigne',
        'machado de assis', 'eça de queirós', 'camões',
    ]
    for autor in autores_antigos:
        if autor in titulo_lower:
            return LivroAnalise(
                titulo=titulo, pasta=str(pasta), autor=autor,
                ano_morte=1900, dominio_publico=True,
                motivo="Autor clássico (pré-1900)", fonte="nome"
            )

    # 6. Desconhecido - assume NÃO público por segurança
    return LivroAnalise(
        titulo=titulo, pasta=str(pasta), autor="Desconhecido",
        ano_morte=None, dominio_publico=False,
        motivo="Autor não identificado - precisa verificação manual", fonte="desconhecido"
    )

def analisar_todos(limite: int = 0) -> List[LivroAnalise]:
    """Analisa todos os livros."""
    print("Carregando banco de dados de autores...")
    autores_db = carregar_autores_db()
    print(f"  {len(autores_db)} autores carregados")

    resultados = []
    pastas = [p for p in TXT_DIR.iterdir() if p.is_dir()]

    if limite > 0:
        pastas = pastas[:limite]

    print(f"\nAnalisando {len(pastas)} livros...")

    for pasta in pastas:
        resultado = analisar_livro(pasta, autores_db)
        resultados.append(resultado)

    return resultados

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Validação de Domínio Público")
    parser.add_argument('--scan', action='store_true', help='Apenas analisa')
    parser.add_argument('--delete', action='store_true', help='Remove livros não-públicos')
    parser.add_argument('--limit', type=int, default=0, help='Limite de livros')
    args = parser.parse_args()

    print("="*60)
    print("VALIDAÇÃO DE DOMÍNIO PÚBLICO")
    print("="*60)
    print(f"Ano limite: {ANO_LIMITE} (autor deve ter morrido antes)")
    print()

    resultados = analisar_todos(args.limit)

    # Estatísticas
    publicos = [r for r in resultados if r.dominio_publico]
    protegidos = [r for r in resultados if not r.dominio_publico]

    print(f"\n{'='*60}")
    print("RESUMO")
    print('='*60)
    print(f"Total analisados: {len(resultados)}")
    print(f"Domínio público: {len(publicos)} ({len(publicos)*100//len(resultados) if resultados else 0}%)")
    print(f"Protegidos/Incertos: {len(protegidos)}")

    # Por fonte
    por_fonte = {}
    for r in resultados:
        por_fonte[r.fonte] = por_fonte.get(r.fonte, 0) + 1
    print(f"\nPor fonte de verificação: {por_fonte}")

    # Lista protegidos
    print(f"\n{'='*60}")
    print("LIVROS A REMOVER (não domínio público):")
    print('='*60)
    for r in protegidos[:30]:
        print(f"  [{r.fonte}] {r.titulo[:50]}")
        print(f"      Motivo: {r.motivo}")

    if len(protegidos) > 30:
        print(f"  ... e mais {len(protegidos)-30} livros")

    # Salva resultado
    output = DATA_DIR / "dominio_publico.json"
    with open(output, 'w', encoding='utf-8') as f:
        json.dump([{
            'titulo': r.titulo,
            'pasta': r.pasta,
            'autor': r.autor,
            'ano_morte': r.ano_morte,
            'dominio_publico': r.dominio_publico,
            'motivo': r.motivo,
            'fonte': r.fonte
        } for r in resultados], f, ensure_ascii=False, indent=2)
    print(f"\nSalvo em: {output}")

    # Remove se solicitado
    if args.delete and protegidos:
        print(f"\n{'='*60}")
        print("REMOVENDO LIVROS NÃO-PÚBLICOS")
        print('='*60)

        ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

        removidos = 0
        for r in protegidos:
            pasta = Path(r.pasta)
            if pasta.exists():
                destino = ARCHIVE_DIR / pasta.name
                try:
                    shutil.move(str(pasta), str(destino))
                    removidos += 1
                    print(f"  Movido: {pasta.name}")
                except Exception as e:
                    print(f"  ERRO: {pasta.name} - {e}")

        print(f"\n{removidos} livros movidos para: {ARCHIVE_DIR}")

    elif protegidos and not args.delete:
        print(f"\nPara remover, execute: python validar_dominio_publico.py --delete")

if __name__ == "__main__":
    main()
