#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MÓDULO 5: ENRICHER (Enriquecedor de Vocabulário)
================================================
Adiciona 100 palavras em inglês traduzidas no contexto de livros PT/ES/FR.

Objetivo: Aprendizado ativo de inglês através de leitura.

Uso:
    python -m src.pipeline.enricher --input books/txt/pt --output books/docx/pt/enriched --words 100

Entrada:
    books/txt/{pt,es,fr}/

Saída:
    books/docx/{pt,es,fr}/enriched/

Formato de saída:
    "palavra" → "palavra (word)"
    + Glossário no final do documento
"""

import os
import re
import json
import sqlite3
import hashlib
import argparse
import zipfile
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed

# Stopwords por idioma
STOPWORDS = {
    'pt': {
        'a', 'o', 'e', 'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
        'um', 'uma', 'uns', 'umas', 'por', 'para', 'com', 'sem', 'sob', 'sobre',
        'que', 'se', 'não', 'mais', 'mas', 'como', 'foi', 'ser', 'são', 'está',
        'ter', 'tem', 'tinha', 'teve', 'isso', 'isto', 'esse', 'essa', 'este', 'esta',
        'ele', 'ela', 'eles', 'elas', 'eu', 'tu', 'você', 'nós', 'vós', 'vocês',
        'meu', 'minha', 'seu', 'sua', 'nosso', 'nossa', 'ao', 'aos', 'às', 'pelo',
        'pela', 'pelos', 'pelas', 'lhe', 'lhes', 'me', 'te', 'nos', 'vos', 'si',
        'já', 'ainda', 'também', 'só', 'bem', 'muito', 'pouco', 'tão', 'assim',
        'quando', 'onde', 'porque', 'porquê', 'qual', 'quais', 'quem', 'quanto',
        'entre', 'depois', 'antes', 'durante', 'sempre', 'nunca', 'agora', 'então',
        'aqui', 'ali', 'lá', 'cá', 'aí', 'ora', 'pois', 'logo', 'enfim', 'portanto',
        'até', 'desde', 'contra', 'perante', 'ante', 'após', 'segundo', 'conforme',
        'mediante', 'durante', 'exceto', 'salvo', 'fora', 'afora', 'dentro', 'além'
    },
    'es': {
        'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del', 'al',
        'y', 'e', 'o', 'u', 'que', 'en', 'a', 'por', 'para', 'con', 'sin', 'sobre',
        'se', 'no', 'más', 'pero', 'como', 'fue', 'ser', 'son', 'está', 'estar',
        'su', 'sus', 'lo', 'le', 'les', 'me', 'te', 'nos', 'os', 'mi', 'tu',
        'yo', 'tú', 'él', 'ella', 'usted', 'nosotros', 'vosotros', 'ellos', 'ellas',
        'este', 'esta', 'estos', 'estas', 'ese', 'esa', 'esos', 'esas', 'aquel',
        'había', 'han', 'hay', 'he', 'ha', 'hemos', 'tienen', 'tiene', 'tengo',
        'ya', 'también', 'muy', 'mucho', 'poco', 'tan', 'así', 'bien', 'mal',
        'cuando', 'donde', 'porque', 'cual', 'quien', 'cuanto', 'como', 'si',
        'entre', 'después', 'antes', 'durante', 'siempre', 'nunca', 'ahora', 'entonces'
    },
    'fr': {
        'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'au', 'aux', 'et', 'ou',
        'que', 'qui', 'en', 'à', 'par', 'pour', 'avec', 'sans', 'sur', 'sous',
        'se', 'ne', 'pas', 'plus', 'mais', 'comme', 'était', 'être', 'sont', 'est',
        'son', 'sa', 'ses', 'leur', 'leurs', 'ce', 'cette', 'ces', 'mon', 'ma', 'mes',
        'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles', 'me', 'te',
        'lui', 'y', 'en', 'dont', 'où', 'quand', 'si', 'bien', 'très', 'peu',
        'tout', 'tous', 'toute', 'toutes', 'autre', 'autres', 'même', 'aussi',
        'donc', 'car', 'ni', 'puis', 'encore', 'déjà', 'jamais', 'toujours', 'ici',
        'là', 'avant', 'après', 'pendant', 'depuis', 'entre', 'vers', 'chez', 'dans'
    }
}

# Template DOCX
DOCUMENT_XML_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
{content}
<w:sectPr>
<w:pgSz w:w="8640" w:h="12960"/>
<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>
</w:sectPr>
</w:body>
</w:document>'''

CONTENT_TYPES_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

RELS_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

DOCUMENT_RELS_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

STYLES_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:styleId="Title">
<w:name w:val="Title"/>
<w:pPr><w:jc w:val="center"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="48"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
<w:name w:val="Heading 1"/>
<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="32"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Glossary">
<w:name w:val="Glossary"/>
<w:pPr><w:spacing w:after="100"/></w:pPr>
<w:rPr><w:sz w:val="22"/><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Normal">
<w:name w:val="Normal"/>
<w:pPr><w:spacing w:after="200" w:line="276" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>
<w:rPr><w:sz w:val="24"/><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/></w:rPr>
</w:style>
</w:styles>'''


class TranslationCache:
    """Cache SQLite para traduções."""

    def __init__(self, cache_path: Path = Path("data/translation_cache.db")):
        self.cache_path = cache_path
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS translations (
                    word TEXT,
                    source_lang TEXT,
                    target_lang TEXT,
                    translation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (word, source_lang, target_lang)
                )
            ''')

    def get(self, word: str, source_lang: str, target_lang: str = 'en') -> Optional[str]:
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute(
                'SELECT translation FROM translations WHERE word=? AND source_lang=? AND target_lang=?',
                (word.lower(), source_lang, target_lang)
            )
            row = cursor.fetchone()
            return row[0] if row else None

    def set(self, word: str, source_lang: str, translation: str, target_lang: str = 'en'):
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO translations (word, source_lang, target_lang, translation) VALUES (?, ?, ?, ?)',
                (word.lower(), source_lang, target_lang, translation)
            )


class VocabularyEnricher:
    """Enriquece livros com vocabulário em inglês."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        source_lang: str = 'pt',
        num_words: int = 100,
        max_workers: int = 4,
        use_api: bool = False,
        api_key: str = ""
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.source_lang = source_lang
        self.num_words = num_words
        self.max_workers = max_workers
        self.use_api = use_api
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")

        self.cache = TranslationCache()
        self.stopwords = STOPWORDS.get(source_lang, set())

        self.enriched = 0
        self.failed = 0
        self.stats = {"started": datetime.now().isoformat(), "books": []}

        # Dicionário básico offline (fallback)
        self.offline_dict = self._load_offline_dict()

    def _load_offline_dict(self) -> Dict[str, str]:
        """Carrega dicionário offline básico."""
        # Dicionário básico PT->EN (pode ser expandido)
        basic_dict = {
            # Português
            'pt': {
                'amor': 'love', 'vida': 'life', 'tempo': 'time', 'mundo': 'world',
                'homem': 'man', 'mulher': 'woman', 'casa': 'house', 'dia': 'day',
                'noite': 'night', 'água': 'water', 'terra': 'earth', 'fogo': 'fire',
                'ar': 'air', 'sol': 'sun', 'lua': 'moon', 'estrela': 'star',
                'olhos': 'eyes', 'mãos': 'hands', 'coração': 'heart', 'alma': 'soul',
                'mente': 'mind', 'corpo': 'body', 'sangue': 'blood', 'morte': 'death',
                'guerra': 'war', 'paz': 'peace', 'rei': 'king', 'rainha': 'queen',
                'filho': 'son', 'filha': 'daughter', 'pai': 'father', 'mãe': 'mother',
                'irmão': 'brother', 'irmã': 'sister', 'amigo': 'friend', 'inimigo': 'enemy',
                'livro': 'book', 'palavra': 'word', 'história': 'history', 'verdade': 'truth',
                'mentira': 'lie', 'força': 'strength', 'poder': 'power', 'beleza': 'beauty',
                'felicidade': 'happiness', 'tristeza': 'sadness', 'medo': 'fear', 'coragem': 'courage',
                'esperança': 'hope', 'fé': 'faith', 'deus': 'god', 'céu': 'sky',
                'inferno': 'hell', 'anjo': 'angel', 'demônio': 'demon', 'espírito': 'spirit',
                'grande': 'big', 'pequeno': 'small', 'bom': 'good', 'mau': 'bad',
                'novo': 'new', 'velho': 'old', 'jovem': 'young', 'belo': 'beautiful',
                'feio': 'ugly', 'forte': 'strong', 'fraco': 'weak', 'rico': 'rich',
                'pobre': 'poor', 'feliz': 'happy', 'triste': 'sad', 'certo': 'right',
                'errado': 'wrong', 'claro': 'clear', 'escuro': 'dark', 'quente': 'hot',
                'frio': 'cold', 'alto': 'tall', 'baixo': 'short', 'longo': 'long',
                'curto': 'short', 'largo': 'wide', 'estreito': 'narrow', 'pesado': 'heavy',
                'leve': 'light', 'duro': 'hard', 'mole': 'soft', 'seco': 'dry',
                'molhado': 'wet', 'limpo': 'clean', 'sujo': 'dirty', 'cheio': 'full',
                'vazio': 'empty', 'aberto': 'open', 'fechado': 'closed', 'vivo': 'alive',
                'morto': 'dead', 'só': 'alone', 'junto': 'together', 'perto': 'near',
                'longe': 'far', 'dentro': 'inside', 'fora': 'outside', 'acima': 'above',
                'abaixo': 'below', 'frente': 'front', 'trás': 'back', 'lado': 'side',
                'ver': 'see', 'ouvir': 'hear', 'falar': 'speak', 'dizer': 'say',
                'fazer': 'do', 'dar': 'give', 'tomar': 'take', 'ir': 'go',
                'vir': 'come', 'saber': 'know', 'pensar': 'think', 'sentir': 'feel',
                'querer': 'want', 'poder': 'can', 'dever': 'must', 'precisar': 'need',
                'amar': 'love', 'odiar': 'hate', 'viver': 'live', 'morrer': 'die',
                'nascer': 'born', 'crescer': 'grow', 'comer': 'eat', 'beber': 'drink',
                'dormir': 'sleep', 'acordar': 'wake', 'andar': 'walk', 'correr': 'run',
                'voar': 'fly', 'nadar': 'swim', 'cair': 'fall', 'subir': 'climb',
                'abrir': 'open', 'fechar': 'close', 'começar': 'start', 'terminar': 'finish',
                'encontrar': 'find', 'perder': 'lose', 'ganhar': 'win', 'trabalhar': 'work',
                'jogar': 'play', 'ler': 'read', 'escrever': 'write', 'cantar': 'sing',
                'dançar': 'dance', 'rir': 'laugh', 'chorar': 'cry', 'gritar': 'shout',
            },
            # Espanhol
            'es': {
                'amor': 'love', 'vida': 'life', 'tiempo': 'time', 'mundo': 'world',
                'hombre': 'man', 'mujer': 'woman', 'casa': 'house', 'día': 'day',
                'noche': 'night', 'agua': 'water', 'tierra': 'earth', 'fuego': 'fire',
                'aire': 'air', 'sol': 'sun', 'luna': 'moon', 'estrella': 'star',
                'ojos': 'eyes', 'manos': 'hands', 'corazón': 'heart', 'alma': 'soul',
                'mente': 'mind', 'cuerpo': 'body', 'sangre': 'blood', 'muerte': 'death',
                'guerra': 'war', 'paz': 'peace', 'rey': 'king', 'reina': 'queen',
                'hijo': 'son', 'hija': 'daughter', 'padre': 'father', 'madre': 'mother',
                'hermano': 'brother', 'hermana': 'sister', 'amigo': 'friend', 'enemigo': 'enemy',
                'libro': 'book', 'palabra': 'word', 'historia': 'history', 'verdad': 'truth',
                'grande': 'big', 'pequeño': 'small', 'bueno': 'good', 'malo': 'bad',
                'nuevo': 'new', 'viejo': 'old', 'joven': 'young', 'bello': 'beautiful',
            },
            # Francês
            'fr': {
                'amour': 'love', 'vie': 'life', 'temps': 'time', 'monde': 'world',
                'homme': 'man', 'femme': 'woman', 'maison': 'house', 'jour': 'day',
                'nuit': 'night', 'eau': 'water', 'terre': 'earth', 'feu': 'fire',
                'air': 'air', 'soleil': 'sun', 'lune': 'moon', 'étoile': 'star',
                'yeux': 'eyes', 'mains': 'hands', 'coeur': 'heart', 'âme': 'soul',
                'esprit': 'mind', 'corps': 'body', 'sang': 'blood', 'mort': 'death',
                'guerre': 'war', 'paix': 'peace', 'roi': 'king', 'reine': 'queen',
                'fils': 'son', 'fille': 'daughter', 'père': 'father', 'mère': 'mother',
                'frère': 'brother', 'soeur': 'sister', 'ami': 'friend', 'ennemi': 'enemy',
                'livre': 'book', 'mot': 'word', 'histoire': 'history', 'vérité': 'truth',
                'grand': 'big', 'petit': 'small', 'bon': 'good', 'mauvais': 'bad',
                'nouveau': 'new', 'vieux': 'old', 'jeune': 'young', 'beau': 'beautiful',
            }
        }
        return basic_dict.get(self.source_lang, {})

    def is_valid_word(self, word: str) -> bool:
        """Verifica se é uma palavra válida para tradução."""
        if len(word) < 3:
            return False
        if word.lower() in self.stopwords:
            return False
        if not word.isalpha():
            return False
        if word.isupper() and len(word) > 2:  # Siglas
            return False
        return True

    def get_top_words(self, text: str) -> List[Tuple[str, int]]:
        """Extrai as N palavras mais frequentes."""
        # Tokenização simples
        words = re.findall(r'\b[a-záàâãéèêíìîóòôõúùûçñ]+\b', text.lower())

        # Filtrar palavras válidas
        valid_words = [w for w in words if self.is_valid_word(w)]

        # Contar frequência
        counter = Counter(valid_words)

        # Retornar top N
        return counter.most_common(self.num_words)

    def translate_word(self, word: str) -> Optional[str]:
        """Traduz uma palavra para inglês."""
        word_lower = word.lower()

        # 1. Verificar cache
        cached = self.cache.get(word_lower, self.source_lang)
        if cached:
            return cached

        # 2. Verificar dicionário offline
        if word_lower in self.offline_dict:
            translation = self.offline_dict[word_lower]
            self.cache.set(word_lower, self.source_lang, translation)
            return translation

        # 3. Se API habilitada, usar Gemini
        if self.use_api and self.api_key:
            translation = self._translate_with_api(word_lower)
            if translation:
                self.cache.set(word_lower, self.source_lang, translation)
                return translation

        return None

    def _translate_with_api(self, word: str) -> Optional[str]:
        """Traduz usando Gemini API."""
        import aiohttp
        import asyncio

        async def fetch():
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
            prompt = f"Translate the {self.source_lang} word '{word}' to English. Reply with ONLY the English word, nothing else."

            async with aiohttp.ClientSession() as session:
                async with session.post(url, json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0, "maxOutputTokens": 50}
                }) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
            return None

        try:
            return asyncio.run(fetch())
        except:
            return None

    @staticmethod
    def escape_xml(text: str) -> str:
        """Escapa caracteres para XML."""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))

    def enrich_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        """Enriquece o texto com traduções."""
        # Obter palavras mais frequentes
        top_words = self.get_top_words(text)

        # Traduzir cada palavra
        translations = {}
        for word, count in top_words:
            translation = self.translate_word(word)
            if translation and translation != word:
                translations[word] = translation

        # Substituir no texto (case-insensitive)
        enriched_text = text
        for word, translation in translations.items():
            # Padrão para encontrar a palavra (preservando case)
            pattern = re.compile(r'\b(' + re.escape(word) + r')\b', re.IGNORECASE)

            def replacer(match):
                original = match.group(1)
                return f"{original} ({translation})"

            # Substituir apenas a primeira ocorrência de cada palavra
            enriched_text = pattern.sub(replacer, enriched_text, count=1)

        return enriched_text, translations

    def create_glossary_xml(self, translations: Dict[str, str]) -> str:
        """Cria seção de glossário em XML."""
        glossary_items = []

        # Título do glossário
        glossary_items.append('''<w:p>
<w:r><w:br w:type="page"/></w:r>
</w:p>
<w:p>
<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
<w:r><w:t>GLOSSARY / GLOSSÁRIO</w:t></w:r>
</w:p>
<w:p>
<w:pPr><w:pStyle w:val="Normal"/></w:pPr>
<w:r><w:rPr><w:i/></w:rPr><w:t>100 most frequent words translated to English</w:t></w:r>
</w:p>
<w:p/>''')

        # Ordenar alfabeticamente
        sorted_translations = sorted(translations.items())

        for word, translation in sorted_translations:
            escaped_word = self.escape_xml(word)
            escaped_trans = self.escape_xml(translation)
            glossary_items.append(f'''<w:p>
<w:pPr><w:pStyle w:val="Glossary"/></w:pPr>
<w:r><w:rPr><w:b/></w:rPr><w:t>{escaped_word}</w:t></w:r>
<w:r><w:t xml:space="preserve"> → </w:t></w:r>
<w:r><w:rPr><w:i/><w:color w:val="0066CC"/></w:rPr><w:t>{escaped_trans}</w:t></w:r>
</w:p>''')

        return '\n'.join(glossary_items)

    def text_to_docx_xml(self, text: str, translations: Dict[str, str]) -> str:
        """Converte texto enriquecido para XML do DOCX."""
        paragraphs = text.split('\n\n')
        xml_parts = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Processar texto com traduções destacadas
            # Encontrar padrões "palavra (translation)"
            pattern = r'(\S+)\s+\(([a-z]+)\)'

            def highlight_translation(match):
                original = self.escape_xml(match.group(1))
                trans = self.escape_xml(match.group(2))
                return f'</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>{original}</w:t></w:r><w:r><w:rPr><w:i/><w:color w:val="0066CC"/></w:rPr><w:t> ({trans})</w:t></w:r><w:r><w:t>'

            processed_para = re.sub(pattern, highlight_translation, self.escape_xml(para))

            # Detectar capítulos
            is_chapter = (
                para.upper().startswith('CHAPTER') or
                para.upper().startswith('CAPÍTULO') or
                para.upper().startswith('CHAPITRE') or
                para.upper().startswith('PARTE') or
                re.match(r'^[IVXLC]+\.?\s', para)
            )

            if is_chapter:
                xml_parts.append(f'''<w:p>
<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
<w:r><w:t>{self.escape_xml(para)}</w:t></w:r>
</w:p>''')
            else:
                xml_parts.append(f'''<w:p>
<w:pPr><w:pStyle w:val="Normal"/></w:pPr>
<w:r><w:t>{processed_para}</w:t></w:r>
</w:p>''')

        # Adicionar glossário
        glossary = self.create_glossary_xml(translations)
        xml_parts.append(glossary)

        return '\n'.join(xml_parts)

    def create_docx(self, text: str, translations: Dict[str, str], output_path: Path, title: str) -> bool:
        """Cria arquivo DOCX enriquecido."""
        try:
            # Converter para XML
            body_content = self.text_to_docx_xml(text, translations)

            # Página de título
            title_escaped = self.escape_xml(title)
            lang_name = {'pt': 'Português', 'es': 'Español', 'fr': 'Français'}.get(self.source_lang, self.source_lang)

            title_page = f'''<w:p>
<w:pPr><w:pStyle w:val="Title"/><w:spacing w:before="2000"/></w:pPr>
<w:r><w:t>{title_escaped}</w:t></w:r>
</w:p>
<w:p>
<w:pPr><w:jc w:val="center"/><w:spacing w:before="300"/></w:pPr>
<w:r><w:rPr><w:i/><w:sz w:val="24"/></w:rPr><w:t>{lang_name} + English Vocabulary</w:t></w:r>
</w:p>
<w:p>
<w:pPr><w:jc w:val="center"/><w:spacing w:before="200"/></w:pPr>
<w:r><w:rPr><w:sz w:val="20"/><w:color w:val="666666"/></w:rPr><w:t>{len(translations)} words enriched for active learning</w:t></w:r>
</w:p>
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
'''

            # Documento completo
            document_xml = DOCUMENT_XML_TEMPLATE.format(content=title_page + body_content)

            # Criar DOCX
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', CONTENT_TYPES_XML)
                zf.writestr('_rels/.rels', RELS_XML)
                zf.writestr('word/_rels/document.xml.rels', DOCUMENT_RELS_XML)
                zf.writestr('word/document.xml', document_xml)
                zf.writestr('word/styles.xml', STYLES_XML)

            return True

        except Exception as e:
            print(f"[ERRO] Criar DOCX: {e}")
            return False

    def process_file(self, filepath: Path) -> Optional[Dict]:
        """Processa um arquivo."""
        try:
            print(f"[...] Processando: {filepath.name}")

            # Ler conteúdo
            content = filepath.read_text(encoding='utf-8', errors='ignore')

            # Extrair título (primeira linha não vazia)
            lines = content.split('\n')
            title = next((l.strip() for l in lines if l.strip()), filepath.stem)

            # Enriquecer texto
            enriched_text, translations = self.enrich_text(content)

            if not translations:
                print(f"[SKIP] {filepath.name} - Nenhuma tradução encontrada")
                return None

            # Nome do arquivo de saída
            output_name = filepath.stem + "_enriched.docx"
            output_path = self.output_dir / output_name

            # Criar DOCX
            if self.create_docx(enriched_text, translations, output_path, title):
                print(f"[OK] {filepath.name} -> {output_name} ({len(translations)} palavras)")
                return {
                    "source": str(filepath),
                    "output": str(output_path),
                    "title": title,
                    "words_enriched": len(translations),
                    "translations": translations
                }
            else:
                return None

        except Exception as e:
            print(f"[ERRO] {filepath.name}: {e}")
            return None

    def run(self, limit: int = 0) -> List[Dict]:
        """Executa enriquecimento de livros."""
        print(f"=== ENRICHER ===")
        print(f"Idioma: {self.source_lang} -> EN")
        print(f"Palavras: {self.num_words}")
        print(f"Entrada: {self.input_dir}")
        print(f"Saída: {self.output_dir}")
        print(f"API: {'Habilitada' if self.use_api and self.api_key else 'Desabilitada (offline)'}")
        print()

        # Criar pasta de saída
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Listar arquivos
        files = list(self.input_dir.glob("**/*.txt"))
        if limit > 0:
            files = files[:limit]

        print(f"Arquivos encontrados: {len(files)}")
        print()

        # Processar
        results = []
        for filepath in files:
            result = self.process_file(filepath)
            if result:
                results.append(result)
                self.enriched += 1
            else:
                self.failed += 1

        self.stats["books"] = results
        self.stats["finished"] = datetime.now().isoformat()
        self.stats["enriched"] = self.enriched
        self.stats["failed"] = self.failed

        # Salvar estatísticas
        stats_file = self.output_dir / "enricher_stats.json"
        stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        print()
        print(f"=== CONCLUÍDO ===")
        print(f"Enriquecidos: {self.enriched}")
        print(f"Falhas: {self.failed}")

        return results


def main():
    parser = argparse.ArgumentParser(description="Enriquecer livros com vocabulário em inglês")
    parser.add_argument("--input", default="books/txt/pt", help="Pasta de entrada")
    parser.add_argument("--output", default="books/docx/pt/enriched", help="Pasta de saída")
    parser.add_argument("--lang", default="pt", choices=['pt', 'es', 'fr'], help="Idioma de origem")
    parser.add_argument("--words", type=int, default=100, help="Número de palavras para enriquecer")
    parser.add_argument("--limit", type=int, default=0, help="Limite de arquivos (0=todos)")
    parser.add_argument("--workers", type=int, default=4, help="Processos paralelos")
    parser.add_argument("--use-api", action="store_true", help="Usar API para traduções extras")
    parser.add_argument("--api-key", help="Gemini API Key")

    args = parser.parse_args()

    enricher = VocabularyEnricher(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        source_lang=args.lang,
        num_words=args.words,
        max_workers=args.workers,
        use_api=args.use_api,
        api_key=args.api_key or ""
    )
    enricher.run(args.limit)


if __name__ == "__main__":
    main()
