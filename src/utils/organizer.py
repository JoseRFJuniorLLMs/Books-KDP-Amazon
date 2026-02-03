# -*- coding: utf-8 -*-
"""
ORGANIZADOR DE LIVROS POR IDIOMA
================================
Analisa arquivos TXT e organiza por idioma detectado.

Uso:
    python organizar_livros.py --scan     # Apenas mostra estatísticas
    python organizar_livros.py --organize # Organiza os arquivos
"""

import os
import re
import shutil
import argparse
from pathlib import Path
from typing import Dict, List, Tuple
from collections import defaultdict

# Diretórios
BASE_DIR = Path(__file__).parent
TXT_DIR = BASE_DIR / "txt"
OUTPUT_DIRS = {
    'pt': BASE_DIR / "translated-portugues",
    'es': BASE_DIR / "translated-espanhol",
    'en': BASE_DIR / "translated-ingles",
    'fr': BASE_DIR / "translated-frances",
    'de': BASE_DIR / "translated-alemao",
    'ru': BASE_DIR / "translated-russo",
    'other': BASE_DIR / "translated-outros",
}

# Palavras características por idioma
LANG_WORDS = {
    'pt': ['que', 'não', 'para', 'uma', 'com', 'por', 'mais', 'como', 'seu', 'sua',
           'ele', 'ela', 'são', 'está', 'isso', 'este', 'essa', 'muito', 'também',
           'pode', 'fazer', 'tempo', 'ainda', 'bem', 'onde', 'depois', 'sobre',
           'mesmo', 'aos', 'já', 'porque', 'entre', 'quando', 'essa', 'você',
           'nós', 'eles', 'dela', 'nosso', 'nossa', 'seus', 'suas', 'havia', 'foram'],
    'es': ['que', 'los', 'las', 'una', 'para', 'con', 'por', 'más', 'como', 'pero',
           'sus', 'está', 'son', 'tiene', 'este', 'todo', 'esta', 'entre', 'cuando',
           'muy', 'sin', 'sobre', 'también', 'fue', 'había', 'hasta', 'desde', 'puede',
           'ser', 'estar', 'hacer', 'decir', 'tiempo', 'vida', 'hombre', 'mundo',
           'años', 'así', 'bien', 'parte', 'después', 'donde', 'ahora', 'entonces'],
    'en': ['the', 'and', 'that', 'have', 'for', 'not', 'with', 'you', 'this', 'but',
           'his', 'from', 'they', 'she', 'which', 'their', 'would', 'there', 'been',
           'have', 'many', 'some', 'them', 'these', 'than', 'first', 'other', 'into',
           'could', 'made', 'its', 'time', 'very', 'when', 'come', 'your', 'now',
           'then', 'each', 'being', 'most', 'people', 'over', 'such', 'great'],
    'fr': ['les', 'des', 'une', 'que', 'pour', 'dans', 'qui', 'sur', 'avec', 'sont',
           'par', 'mais', 'cette', 'vous', 'nous', 'elle', 'tout', 'bien', 'fait',
           'comme', 'était', 'être', 'avoir', 'leur', 'même', 'aussi', 'autres',
           'ces', 'peut', 'tous', 'ses', 'très', 'sans', 'donc', 'encore', 'entre',
           'sous', 'puis', 'fois', 'rien', 'dont', 'toujours', 'homme', 'monde'],
    'de': ['der', 'die', 'und', 'den', 'das', 'von', 'ist', 'des', 'auf', 'für',
           'mit', 'dem', 'nicht', 'sich', 'eine', 'ein', 'als', 'auch', 'nach',
           'wird', 'bei', 'oder', 'nur', 'werden', 'sind', 'war', 'haben', 'wie',
           'kann', 'wenn', 'aber', 'noch', 'sein', 'diese', 'aus', 'ihrer', 'ihren'],
    'ru': ['что', 'как', 'это', 'его', 'она', 'они', 'все', 'для', 'так', 'был',
           'при', 'уже', 'вот', 'меня', 'тебя', 'свой', 'есть', 'быть', 'были',
           'или', 'если', 'только', 'когда', 'можно', 'здесь', 'надо', 'себя'],
}


def detect_language(text: str) -> Tuple[str, Dict[str, int]]:
    """Detecta idioma do texto e retorna scores."""
    # Usa apenas primeiros 10000 caracteres
    sample = text[:10000].lower()

    scores = {}
    for lang, words in LANG_WORDS.items():
        score = sum(1 for w in words if f' {w} ' in f' {sample} ')
        scores[lang] = score

    # Retorna idioma com maior score
    if max(scores.values()) < 5:
        return 'other', scores

    return max(scores, key=scores.get), scores


def scan_txt_folder() -> Dict[str, List[Path]]:
    """Escaneia pasta txt/ e retorna arquivos por idioma."""
    results = defaultdict(list)

    for folder in TXT_DIR.iterdir():
        if not folder.is_dir():
            continue

        # Procura arquivos .txt na pasta
        txt_files = list(folder.glob("*.txt"))
        if not txt_files:
            continue

        # Usa o maior arquivo para detectar idioma
        main_file = max(txt_files, key=lambda f: f.stat().st_size)

        try:
            with open(main_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            if len(content) < 500:
                continue

            lang, _ = detect_language(content)
            results[lang].append(folder)

        except Exception as e:
            print(f"Erro ao ler {main_file}: {e}")

    return dict(results)


def print_stats(results: Dict[str, List[Path]]):
    """Mostra estatísticas dos idiomas detectados."""
    print("\n" + "="*60)
    print("ESTATÍSTICAS DE IDIOMAS")
    print("="*60)

    lang_names = {
        'pt': 'Português',
        'es': 'Espanhol',
        'en': 'Inglês',
        'fr': 'Francês',
        'de': 'Alemão',
        'ru': 'Russo',
        'other': 'Outros',
    }

    total = sum(len(v) for v in results.values())

    for lang, folders in sorted(results.items(), key=lambda x: -len(x[1])):
        name = lang_names.get(lang, lang.upper())
        count = len(folders)
        pct = (count / total * 100) if total > 0 else 0
        print(f"  {name:12} : {count:4} livros ({pct:5.1f}%)")

    print("-"*60)
    print(f"  {'TOTAL':12} : {total:4} livros")
    print()


def organize_files(results: Dict[str, List[Path]], copy_mode: bool = True):
    """Organiza arquivos por idioma."""
    print("\n" + "="*60)
    print("ORGANIZANDO ARQUIVOS")
    print("="*60)

    # Cria diretórios
    for folder in OUTPUT_DIRS.values():
        folder.mkdir(exist_ok=True)

    for lang, folders in results.items():
        output_dir = OUTPUT_DIRS.get(lang, OUTPUT_DIRS['other'])

        for folder in folders:
            dest = output_dir / folder.name

            if dest.exists():
                print(f"  [SKIP] {folder.name} (já existe)")
                continue

            try:
                if copy_mode:
                    shutil.copytree(folder, dest)
                else:
                    shutil.move(folder, dest)
                print(f"  [OK] {folder.name} → {output_dir.name}/")
            except Exception as e:
                print(f"  [ERRO] {folder.name}: {e}")

    print("\nConcluído!")


def main():
    parser = argparse.ArgumentParser(description="Organiza livros por idioma")
    parser.add_argument('--scan', action='store_true', help='Apenas escaneia e mostra estatísticas')
    parser.add_argument('--organize', action='store_true', help='Organiza arquivos por idioma')
    parser.add_argument('--move', action='store_true', help='Move arquivos (padrão: copia)')
    args = parser.parse_args()

    print("Escaneando pasta txt/...")
    results = scan_txt_folder()

    print_stats(results)

    if args.organize:
        organize_files(results, copy_mode=not args.move)
    elif not args.scan:
        print("Use --scan para ver estatísticas ou --organize para organizar")


if __name__ == "__main__":
    main()
