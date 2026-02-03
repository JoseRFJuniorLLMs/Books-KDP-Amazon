#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MÓDULO 4: CLEANER
=================
Limpa e organiza arquivos processados.

Uso:
    python -m src.pipeline.cleaner --mode organize
    python -m src.pipeline.cleaner --mode validate
    python -m src.pipeline.cleaner --mode cleanup

Funções:
    - organize: Move arquivos para pastas corretas por idioma
    - validate: Valida domínio público
    - cleanup: Remove arquivos temporários e duplicados
"""

import os
import re
import json
import shutil
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Set
from datetime import datetime
from collections import defaultdict

# Configuração
BOOKS_DIR = Path("books")
LANG_PATTERNS = {
    'en': ['the ', 'and ', 'of ', 'to ', 'in ', 'that ', 'was ', 'for '],
    'pt': ['de ', 'que ', 'para ', 'com ', 'não ', 'uma ', 'por ', 'mais '],
    'es': ['el ', 'la ', 'que ', 'de ', 'en ', 'los ', 'las ', 'por '],
    'ru': ['и ', 'в ', 'на ', 'с ', 'что ', 'как ', 'это ', 'для '],
    'fr': ['le ', 'la ', 'de ', 'et ', 'les ', 'des ', 'que ', 'qui '],
    'de': ['der ', 'die ', 'und ', 'in ', 'den ', 'von ', 'ist ', 'das '],
}


class BookCleaner:
    """Limpeza e organização de livros."""

    def __init__(self, books_dir: Path = BOOKS_DIR):
        self.books_dir = books_dir
        self.stats = {
            "started": datetime.now().isoformat(),
            "organized": 0,
            "validated": 0,
            "cleaned": 0,
            "duplicates": 0,
            "errors": 0
        }

    def detect_language(self, text: str) -> str:
        """Detecta idioma do texto."""
        text_lower = text.lower()[:10000]
        scores = {}

        for lang, patterns in LANG_PATTERNS.items():
            score = sum(1 for p in patterns if p in text_lower)
            scores[lang] = score

        if max(scores.values()) == 0:
            return 'other'

        return max(scores, key=scores.get)

    def get_file_hash(self, filepath: Path) -> str:
        """Calcula hash MD5 do arquivo."""
        content = filepath.read_bytes()
        return hashlib.md5(content).hexdigest()

    def organize_by_language(self) -> Dict[str, int]:
        """Organiza arquivos por idioma."""
        print("=== ORGANIZANDO POR IDIOMA ===")
        organized = defaultdict(int)

        for book_type in ['txt', 'raw']:
            type_dir = self.books_dir / book_type

            if not type_dir.exists():
                continue

            # Encontrar arquivos soltos (não em subpastas de idioma)
            for filepath in type_dir.glob("*.txt"):
                content = filepath.read_text(encoding='utf-8', errors='ignore')
                lang = self.detect_language(content)

                # Mover para pasta do idioma
                dest_dir = type_dir / lang
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / filepath.name

                if not dest_path.exists():
                    shutil.move(str(filepath), str(dest_path))
                    organized[lang] += 1
                    print(f"[MOVIDO] {filepath.name} -> {lang}/")
                else:
                    # Arquivo já existe, remover duplicata
                    filepath.unlink()
                    self.stats["duplicates"] += 1

        self.stats["organized"] = sum(organized.values())
        return dict(organized)

    def find_duplicates(self) -> List[tuple]:
        """Encontra arquivos duplicados."""
        print("=== BUSCANDO DUPLICATAS ===")
        hashes = defaultdict(list)
        duplicates = []

        for filepath in self.books_dir.rglob("*.txt"):
            file_hash = self.get_file_hash(filepath)
            hashes[file_hash].append(filepath)

        for file_hash, files in hashes.items():
            if len(files) > 1:
                duplicates.append((file_hash, files))
                print(f"[DUPLICATA] {len(files)} cópias: {files[0].name}")

        return duplicates

    def remove_duplicates(self, duplicates: List[tuple]) -> int:
        """Remove arquivos duplicados mantendo um."""
        removed = 0

        for file_hash, files in duplicates:
            # Manter o primeiro, remover os outros
            for filepath in files[1:]:
                try:
                    filepath.unlink()
                    removed += 1
                    print(f"[REMOVIDO] {filepath}")
                except Exception as e:
                    print(f"[ERRO] Não foi possível remover {filepath}: {e}")
                    self.stats["errors"] += 1

        self.stats["duplicates"] = removed
        return removed

    def cleanup_temp_files(self) -> int:
        """Remove arquivos temporários."""
        print("=== LIMPANDO TEMPORÁRIOS ===")
        patterns = [
            "*.tmp", "*.bak", "*.log", "*.pyc",
            "__pycache__", ".DS_Store", "Thumbs.db",
            "*.db", "*.cache"
        ]

        removed = 0
        for pattern in patterns:
            for filepath in self.books_dir.rglob(pattern):
                try:
                    if filepath.is_file():
                        filepath.unlink()
                    elif filepath.is_dir():
                        shutil.rmtree(filepath)
                    removed += 1
                    print(f"[LIMPO] {filepath}")
                except Exception as e:
                    print(f"[ERRO] {filepath}: {e}")

        self.stats["cleaned"] = removed
        return removed

    def validate_public_domain(self) -> List[Dict]:
        """Valida se livros são de domínio público (autor morto há +70 anos)."""
        print("=== VALIDANDO DOMÍNIO PÚBLICO ===")
        # Limite: autores que morreram antes de 1954 (70+ anos)
        DEATH_YEAR_LIMIT = 1954

        # Padrões para extrair datas
        date_patterns = [
            r'\b(1[0-9]{3})\s*[-–]\s*(1[0-9]{3})\b',  # 1800-1900
            r'died\s+(1[0-9]{3})',
            r'd\.\s*(1[0-9]{3})',
        ]

        validated = []
        suspicious = []

        for filepath in self.books_dir.rglob("*.txt"):
            try:
                content = filepath.read_text(encoding='utf-8', errors='ignore')[:5000]

                death_year = None
                for pattern in date_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        years = match.groups()
                        death_year = int(years[-1]) if years else None
                        break

                status = {
                    "file": str(filepath),
                    "death_year": death_year,
                    "public_domain": death_year is None or death_year < DEATH_YEAR_LIMIT
                }

                if status["public_domain"]:
                    validated.append(status)
                else:
                    suspicious.append(status)
                    print(f"[SUSPEITO] {filepath.name} - morte em {death_year}")

            except Exception as e:
                print(f"[ERRO] {filepath.name}: {e}")
                self.stats["errors"] += 1

        self.stats["validated"] = len(validated)
        return {"validated": validated, "suspicious": suspicious}

    def generate_report(self) -> str:
        """Gera relatório de limpeza."""
        self.stats["finished"] = datetime.now().isoformat()

        report = f"""
=== RELATÓRIO DE LIMPEZA ===
Data: {self.stats['finished']}

Organizados por idioma: {self.stats['organized']}
Validados (domínio público): {self.stats['validated']}
Temporários limpos: {self.stats['cleaned']}
Duplicatas removidas: {self.stats['duplicates']}
Erros: {self.stats['errors']}
"""
        return report

    def run(self, mode: str = "all") -> Dict:
        """Executa limpeza."""
        print(f"=== CLEANER - Modo: {mode} ===")
        print(f"Diretório: {self.books_dir}")
        print()

        results = {}

        if mode in ["organize", "all"]:
            results["organized"] = self.organize_by_language()

        if mode in ["duplicates", "all"]:
            duplicates = self.find_duplicates()
            results["duplicates_found"] = len(duplicates)
            if duplicates:
                results["duplicates_removed"] = self.remove_duplicates(duplicates)

        if mode in ["cleanup", "all"]:
            results["cleaned"] = self.cleanup_temp_files()

        if mode in ["validate", "all"]:
            results["validation"] = self.validate_public_domain()

        # Gerar relatório
        report = self.generate_report()
        print(report)

        # Salvar estatísticas
        stats_file = self.books_dir / "cleaner_stats.json"
        stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        return results


def main():
    parser = argparse.ArgumentParser(description="Limpar e organizar livros")
    parser.add_argument("--mode", choices=["organize", "duplicates", "cleanup", "validate", "all"],
                       default="all", help="Modo de operação")
    parser.add_argument("--dir", default="books", help="Diretório de livros")

    args = parser.parse_args()

    cleaner = BookCleaner(Path(args.dir))
    cleaner.run(args.mode)


if __name__ == "__main__":
    main()
