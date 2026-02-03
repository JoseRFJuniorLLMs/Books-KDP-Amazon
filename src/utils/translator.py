#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN_TRANSLATOR.PY - Tradutor Massivo de Livros (OLLAMA LOCAL)
==============================================================
Traduz livros de EN/ES/RU para PT-BR usando Ollama LOCAL (sem API externa).

Modelos rápidos recomendados:
- qwen2.5:7b (RECOMENDADO - rápido, melhor qualidade)
- gemma2:2b (MAIS RÁPIDO, menor qualidade)
- llama3.2:3b (rápido, boa qualidade)

Uso:
    python run_translator.py --languages en es --limit 10
    python run_translator.py --model qwen2.5:7b
"""

import os
import re
import sys
import time
import json
import hashlib
import sqlite3
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

from tqdm import tqdm
import requests

# Configurações
sys.path.insert(0, str(Path(__file__).parent))
from config.settings import DATA_DIR, BASE_DIR, OLLAMA_BASE_URL

# Paths
TXT_DIR = BASE_DIR / "txt"
TRANSLATED_DIR = BASE_DIR / "translated"
CACHE_DB = DATA_DIR / "translation_cache.db"

# Criar diretórios
TRANSLATED_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DB.parent.mkdir(parents=True, exist_ok=True)

# ============================================================================
# CACHE
# ============================================================================

class TranslationCache:
    """Cache SQLite para traduções."""

    def __init__(self, db_path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS translations (
                    hash TEXT PRIMARY KEY,
                    original TEXT,
                    translated TEXT,
                    source_lang TEXT,
                    model TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:32]

    def get(self, text: str) -> Optional[str]:
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute('SELECT translated FROM translations WHERE hash = ?',
                             (self._hash(text),))
            row = cur.fetchone()
            return row[0] if row else None

    def set(self, original: str, translated: str, lang: str, model: str):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT OR REPLACE INTO translations (hash, original, translated, source_lang, model)
                VALUES (?, ?, ?, ?, ?)
            ''', (self._hash(original), original, translated, lang, model))

# ============================================================================
# TRADUTOR OLLAMA LOCAL
# ============================================================================

LANG_NAMES = {
    'en': 'inglês',
    'es': 'espanhol',
    'ru': 'russo',
    'fr': 'francês',
    'de': 'alemão',
    'it': 'italiano',
    'pt': 'português'
}

class OllamaTranslator:
    """Tradutor usando Ollama LOCAL (sem API externa)."""

    def __init__(self, model_name: str = "qwen2.5:7b", base_url: str = None):
        """
        Inicializa tradutor local.

        Args:
            model_name: Nome do modelo Ollama (padrão: qwen2.5:7b, recomendado)
                       Opções: qwen2.5:7b, gemma2:2b, llama3.2:3b
            base_url: URL do Ollama (padrão: http://localhost:11434)
        """
        self.base_url = base_url or OLLAMA_BASE_URL
        self.model_name = model_name
        self.cache = TranslationCache(CACHE_DB)

        # Testa conexão
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise ConnectionError("Ollama não está rodando")

            # Verifica se modelo existe
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]

            if model_name not in model_names:
                print(f"⚠️ Modelo {model_name} não encontrado localmente")
                print(f"📥 Baixe com: ollama pull {model_name}")
                sys.exit(1)

            print(f"✅ Ollama LOCAL conectado: {self.base_url}")
            print(f"✅ Modelo: {model_name} (LOCAL, sem API)")

        except Exception as e:
            print(f"❌ Erro conectando ao Ollama: {e}")
            print(f"💡 Certifique-se que Ollama está rodando: ollama serve")
            sys.exit(1)

    def translate_chunk(self, chunk: str, source_lang: str, retries: int = 3) -> str:
        """Traduz um chunk usando Ollama LOCAL."""
        # Cache
        cached = self.cache.get(chunk)
        if cached:
            return cached

        lang_name = LANG_NAMES.get(source_lang, source_lang)

        prompt = f"""Traduza o texto abaixo de {lang_name} para português brasileiro.

REGRAS:
- Tradução fiel ao original
- Mantenha estrutura de parágrafos
- Preserve nomes próprios
- NÃO adicione comentários
- Retorne APENAS a tradução

TEXTO:
\"\"\"
{chunk}
\"\"\"

TRADUÇÃO:"""

        for attempt in range(retries):
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.2,
                            "num_predict": 8192,
                        }
                    },
                    timeout=120  # 2 minutos
                )

                if response.status_code == 200:
                    result = response.json()
                    translated = result.get('response', '').strip()

                    if translated:
                        self.cache.set(chunk, translated, source_lang, self.model_name)
                        return translated

            except Exception as e:
                if attempt < retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"⚠️ Erro: {e}")

        return chunk  # Fallback

# ============================================================================
# DETECÇÃO DE IDIOMA
# ============================================================================

try:
    from langdetect import detect as langdetect_detect

    def detect_language(text: str) -> str:
        try:
            sample = text[:5000]
            return langdetect_detect(sample)
        except:
            return 'unknown'

except ImportError:
    print("⚠️ langdetect não instalado. Instale com: pip install langdetect")

    def detect_language(text: str) -> str:
        """Fallback: detecta idioma por palavras comuns."""
        sample = text[:5000].lower()

        # Contadores
        en_words = ['the', 'and', 'of', 'to', 'in', 'is', 'that', 'for', 'it']
        es_words = ['el', 'la', 'de', 'que', 'y', 'en', 'los', 'del', 'las']
        ru_words = ['и', 'в', 'не', 'на', 'с', 'что', 'он', 'как', 'это']
        pt_words = ['de', 'e', 'que', 'o', 'a', 'do', 'da', 'em', 'os']

        en_count = sum(1 for w in en_words if f' {w} ' in sample)
        es_count = sum(1 for w in es_words if f' {w} ' in sample)
        ru_count = sum(1 for w in ru_words if w in sample)
        pt_count = sum(1 for w in pt_words if f' {w} ' in sample)

        counts = {'en': en_count, 'es': es_count, 'ru': ru_count, 'pt': pt_count}
        return max(counts, key=counts.get)

# ============================================================================
# CHUNKING
# ============================================================================

def create_chunks(text: str, max_chars: int = 2000) -> List[str]:
    """Divide texto em chunks menores para modelos locais."""
    paragraphs = text.split('\n\n')
    chunks = []
    current = ""

    for para in paragraphs:
        if len(current) + len(para) < max_chars:
            current += ('\n\n' if current else '') + para
        else:
            if current:
                chunks.append(current)
            current = para

    if current:
        chunks.append(current)

    return chunks

# ============================================================================
# TRADUÇÃO DE LIVROS
# ============================================================================

def find_books_to_translate(target_languages: set) -> List[Dict]:
    """Encontra livros que precisam tradução."""
    books = []

    if not TXT_DIR.exists():
        print(f"❌ Pasta não existe: {TXT_DIR}")
        return books

    for txt_file in TXT_DIR.rglob("*.txt"):
        # Já traduzido?
        relative = txt_file.relative_to(TXT_DIR)
        translated_path = TRANSLATED_DIR / relative.parent / f"{txt_file.stem}_pt.txt"

        if translated_path.exists():
            continue

        # Detecta idioma
        try:
            with open(txt_file, 'r', encoding='utf-8', errors='ignore') as f:
                sample = f.read(5000)

            lang = detect_language(sample)

            if lang in target_languages:
                books.append({
                    'path': txt_file,
                    'output': translated_path,
                    'lang': lang,
                    'size': txt_file.stat().st_size,
                    'name': txt_file.stem
                })
        except Exception as e:
            print(f"⚠️ Erro: {txt_file.name}: {e}")

    books.sort(key=lambda x: x['size'])
    return books

def translate_book(book: Dict, translator: OllamaTranslator) -> bool:
    """Traduz um livro completo."""
    try:
        # Lê
        with open(book['path'], 'r', encoding='utf-8', errors='ignore') as f:
            text = f.read()

        # Chunks
        chunks = create_chunks(text)

        print(f"\n📖 {book['name'][:50]}")
        print(f"   Idioma: {LANG_NAMES.get(book['lang'], book['lang'])}")
        print(f"   Chunks: {len(chunks)}")

        # Traduz
        translated_chunks = []
        with tqdm(total=len(chunks), desc="  Traduzindo", unit="chunk", leave=False) as pbar:
            for chunk in chunks:
                translated = translator.translate_chunk(chunk, book['lang'])
                translated_chunks.append(translated)
                pbar.update(1)

        # Salva
        final_text = '\n\n'.join(translated_chunks)
        book['output'].parent.mkdir(parents=True, exist_ok=True)

        with open(book['output'], 'w', encoding='utf-8') as f:
            f.write(final_text)

        print(f"   ✅ Salvo: {book['output'].relative_to(BASE_DIR)}")
        return True

    except Exception as e:
        print(f"\n❌ Erro: {book['name']}: {e}")
        return False

# ============================================================================
# MAIN
# ============================================================================

def main():
    # Fix Windows encoding
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

    parser = argparse.ArgumentParser(
        description="Tradutor Massivo - Ollama LOCAL (sem API)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modelos rápidos recomendados (do mais rápido para o mais lento):
  qwen2.5:7b     - RECOMENDADO (rápido, melhor qualidade)
  gemma2:2b      - MAIS RÁPIDO (menor qualidade)
  llama3.2:3b    - Rápido, boa qualidade
  qwen2.5:14b    - Lento, melhor qualidade

Instalar modelo:
  ollama pull qwen2.5:7b
"""
    )
    parser.add_argument('--languages', '-l', nargs='+', default=['en', 'es', 'ru'],
                       help='Idiomas para traduzir (en, es, ru, fr, de, it)')
    parser.add_argument('--limit', '-n', type=int, default=0,
                       help='Limite de livros (0 = todos)')
    parser.add_argument('--model', '-m', default='qwen2.5:7b',
                       help='Modelo Ollama (padrão: qwen2.5:7b, recomendado)')

    args = parser.parse_args()

    # Tradutor
    print("="*60)
    print("🚀 TRADUTOR LOCAL - OLLAMA (SEM API EXTERNA)")
    print("="*60)

    try:
        translator = OllamaTranslator(args.model)
    except Exception as e:
        print(f"❌ Erro ao iniciar tradutor: {e}")
        return 1

    # Busca livros
    target_langs = set(args.languages)
    books = find_books_to_translate(target_langs)

    if args.limit > 0:
        books = books[:args.limit]

    print(f"\n📚 LIVROS PARA TRADUZIR: {len(books)}")
    for lang in target_langs:
        count = len([b for b in books if b['lang'] == lang])
        lang_name = LANG_NAMES.get(lang, lang)
        print(f"  {lang_name}: {count}")

    if not books:
        print("\n✅ Nenhum livro para traduzir!")
        return 0

    # Tradução
    print("\n" + "="*60)
    print("🚀 INICIANDO TRADUÇÃO LOCAL")
    print(f"Modelo: {args.model} (LOCAL)")
    print("="*60)

    success = 0
    fail = 0
    start = time.time()

    for i, book in enumerate(books, 1):
        print(f"\n[{i}/{len(books)}]", end=" ")

        if translate_book(book, translator):
            success += 1
        else:
            fail += 1

    elapsed = time.time() - start

    print(f"\n\n" + "="*60)
    print("✅ TRADUÇÃO CONCLUÍDA!")
    print("="*60)
    print(f"Tempo: {elapsed/60:.1f} minutos")
    print(f"Sucesso: {success}")
    print(f"Falhas: {fail}")
    if success > 0:
        print(f"Velocidade: {success/(elapsed/60):.1f} livros/minuto")
    print(f"\n📁 Traduções em: {TRANSLATED_DIR}")

    return 0 if fail == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
