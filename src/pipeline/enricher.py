#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MÓDULO 5: ENRICHER (Enriquecedor de Vocabulário)
================================================
Adiciona 100 palavras em inglês com NOTAS DE RODAPÉ em livros PT/ES/FR.

Usa template.docx como matriz:
    - Páginas 1-2: Capa e ficha catalográfica (do template)
    - Página 3+: Conteúdo do livro com vocabulário

Uso:
    python -m src.pipeline.enricher --input books/txt/pt --output books/docx/pt/enriched --words 100

Template:
    templates/template.docx (criar no Word com páginas 1-2 formatadas)
"""

import os
import re
import json
import sqlite3
import argparse
import zipfile
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from datetime import datetime
from collections import Counter
from copy import deepcopy

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Configuracao centralizada
from config.settings import GEMINI_API_KEY, TEMPLATE_DOCX

# Namespaces OOXML
NS = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
    'ct': 'http://schemas.openxmlformats.org/package/2006/content-types',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
}

# Stopwords por idioma
STOPWORDS = {
    'pt': {
        'a', 'o', 'e', 'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
        'um', 'uma', 'uns', 'umas', 'por', 'para', 'com', 'sem', 'sob', 'sobre',
        'que', 'se', 'não', 'mais', 'mas', 'como', 'foi', 'ser', 'são', 'está',
        'ter', 'tem', 'tinha', 'teve', 'isso', 'isto', 'esse', 'essa', 'este', 'esta',
        'ele', 'ela', 'eles', 'elas', 'eu', 'tu', 'você', 'nós', 'vós', 'vocês',
        'meu', 'minha', 'seu', 'sua', 'nosso', 'nossa', 'ao', 'aos', 'às', 'pelo',
        'pela', 'pelos', 'pelas', 'lhe', 'lhes', 'me', 'te', 'vos', 'si',
        'já', 'ainda', 'também', 'só', 'bem', 'muito', 'pouco', 'tão', 'assim',
        'quando', 'onde', 'porque', 'porquê', 'qual', 'quais', 'quem', 'quanto',
        'entre', 'depois', 'antes', 'durante', 'sempre', 'nunca', 'agora', 'então',
        'aqui', 'ali', 'lá', 'cá', 'aí', 'ora', 'pois', 'logo', 'enfim', 'portanto',
    },
    'es': {
        'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del', 'al',
        'y', 'e', 'o', 'u', 'que', 'en', 'a', 'por', 'para', 'con', 'sin', 'sobre',
        'se', 'no', 'más', 'pero', 'como', 'fue', 'ser', 'son', 'está', 'estar',
        'su', 'sus', 'lo', 'le', 'les', 'me', 'te', 'nos', 'os', 'mi', 'tu',
    },
    'fr': {
        'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'au', 'aux', 'et', 'ou',
        'que', 'qui', 'en', 'à', 'par', 'pour', 'avec', 'sans', 'sur', 'sous',
        'se', 'ne', 'pas', 'plus', 'mais', 'comme', 'était', 'être', 'sont', 'est',
        'son', 'sa', 'ses', 'leur', 'leurs', 'ce', 'cette', 'ces', 'mon', 'ma', 'mes',
    }
}


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
                    word TEXT, source_lang TEXT, target_lang TEXT, translation TEXT,
                    PRIMARY KEY (word, source_lang, target_lang)
                )
            ''')

    def get(self, word: str, source_lang: str) -> Optional[str]:
        with sqlite3.connect(self.cache_path) as conn:
            cur = conn.execute(
                'SELECT translation FROM translations WHERE word=? AND source_lang=? AND target_lang=?',
                (word.lower(), source_lang, 'en')
            )
            row = cur.fetchone()
            return row[0] if row else None

    def set(self, word: str, source_lang: str, translation: str):
        with sqlite3.connect(self.cache_path) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO translations VALUES (?, ?, ?, ?)',
                (word.lower(), source_lang, 'en', translation)
            )


class TemplateManager:
    """Gerencia o template.docx base."""

    TEMPLATE_PATH = Path("templates/template.docx")

    # Estilos padrão para o template
    STYLES_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Georgia" w:hAnsi="Georgia" w:cs="Georgia"/>
<w:sz w:val="24"/><w:szCs w:val="24"/>
</w:rPr></w:rPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:styleId="Title">
<w:name w:val="Title"/>
<w:pPr><w:jc w:val="center"/><w:spacing w:before="3000" w:after="400"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="72"/><w:szCs w:val="72"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Subtitle">
<w:name w:val="Subtitle"/>
<w:pPr><w:jc w:val="center"/><w:spacing w:after="200"/></w:pPr>
<w:rPr><w:i/><w:sz w:val="32"/><w:szCs w:val="32"/><w:color w:val="666666"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Author">
<w:name w:val="Author"/>
<w:pPr><w:jc w:val="center"/><w:spacing w:before="1000"/></w:pPr>
<w:rPr><w:sz w:val="36"/><w:szCs w:val="36"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="CatalogInfo">
<w:name w:val="CatalogInfo"/>
<w:pPr><w:spacing w:after="100"/></w:pPr>
<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/><w:color w:val="444444"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
<w:name w:val="Heading 1"/>
<w:pPr><w:spacing w:before="400" w:after="200"/><w:keepNext/></w:pPr>
<w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Normal">
<w:name w:val="Normal"/>
<w:pPr><w:spacing w:after="200" w:line="288" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>
<w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Glossary">
<w:name w:val="Glossary"/>
<w:pPr><w:spacing w:after="60"/><w:ind w:left="400"/></w:pPr>
<w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/></w:rPr>
</w:style>
<w:style w:type="character" w:styleId="FootnoteReference">
<w:name w:val="Footnote Reference"/>
<w:rPr><w:vertAlign w:val="superscript"/><w:color w:val="0066CC"/><w:sz w:val="20"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="FootnoteText">
<w:name w:val="Footnote Text"/>
<w:pPr><w:spacing w:after="40"/></w:pPr>
<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/><w:color w:val="444444"/></w:rPr>
</w:style>
</w:styles>'''

    SETTINGS_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:defaultTabStop w:val="720"/>
<w:footnotePr><w:numFmt w:val="decimal"/></w:footnotePr>
</w:settings>'''

    CONTENT_TYPES_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>'''

    RELS_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    DOCUMENT_RELS_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>'''

    @classmethod
    def create_default_template(cls):
        """Cria template.docx padrão com páginas 1-2."""
        cls.TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Página 1: Capa com placeholders
        # Página 2: Ficha catalográfica
        # Marcador {{CONTENT}} indica onde inserir o conteúdo

        document_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:body>

<!-- ============== PÁGINA 1: CAPA ============== -->
<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>
<w:r><w:t>{{TITLE}}</w:t></w:r></w:p>

<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>
<w:r><w:t>{{SUBTITLE}}</w:t></w:r></w:p>

<w:p><w:pPr><w:pStyle w:val="Author"/></w:pPr>
<w:r><w:t>{{AUTHOR}}</w:t></w:r></w:p>

<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:before="2000"/></w:pPr>
<w:r><w:rPr><w:sz w:val="20"/><w:color w:val="888888"/></w:rPr>
<w:t>{{LANG_LABEL}}</w:t></w:r></w:p>

<w:p><w:r><w:br w:type="page"/></w:r></w:p>

<!-- ============== PÁGINA 2: FICHA CATALOGRÁFICA ============== -->
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
<w:r><w:t>Ficha Catalográfica</w:t></w:r></w:p>

<w:p><w:pPr><w:pStyle w:val="CatalogInfo"/></w:pPr>
<w:r><w:rPr><w:b/></w:rPr><w:t>Título: </w:t></w:r>
<w:r><w:t>{{TITLE}}</w:t></w:r></w:p>

<w:p><w:pPr><w:pStyle w:val="CatalogInfo"/></w:pPr>
<w:r><w:rPr><w:b/></w:rPr><w:t>Autor: </w:t></w:r>
<w:r><w:t>{{AUTHOR}}</w:t></w:r></w:p>

<w:p><w:pPr><w:pStyle w:val="CatalogInfo"/></w:pPr>
<w:r><w:rPr><w:b/></w:rPr><w:t>Idioma: </w:t></w:r>
<w:r><w:t>{{LANGUAGE}}</w:t></w:r></w:p>

<w:p><w:pPr><w:pStyle w:val="CatalogInfo"/></w:pPr>
<w:r><w:rPr><w:b/></w:rPr><w:t>Vocabulário: </w:t></w:r>
<w:r><w:t>{{WORD_COUNT}} palavras em inglês</w:t></w:r></w:p>

<w:p><w:pPr><w:pStyle w:val="CatalogInfo"/><w:spacing w:before="400"/></w:pPr>
<w:r><w:rPr><w:i/><w:sz w:val="16"/></w:rPr>
<w:t>Este livro é de domínio público. Edição preparada para aprendizado de inglês através de leitura ativa.</w:t></w:r></w:p>

<w:p><w:pPr><w:pStyle w:val="CatalogInfo"/></w:pPr>
<w:r><w:rPr><w:sz w:val="16"/><w:color w:val="888888"/></w:rPr>
<w:t>Gerado automaticamente por BooksKDP</w:t></w:r></w:p>

<w:p><w:r><w:br w:type="page"/></w:r></w:p>

<!-- ============== PÁGINA 3+: CONTEÚDO ============== -->
<!-- MARCADOR: O conteúdo do livro será inserido aqui -->
{{CONTENT}}

<w:sectPr>
<w:pgSz w:w="8640" w:h="12960"/>
<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="720" w:footer="720"/>
</w:sectPr>
</w:body>
</w:document>'''

        footnotes_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:footnote w:type="separator" w:id="-1">
<w:p><w:r><w:separator/></w:r></w:p>
</w:footnote>
<w:footnote w:type="continuationSeparator" w:id="0">
<w:p><w:r><w:continuationSeparator/></w:r></w:p>
</w:footnote>
</w:footnotes>'''

        with zipfile.ZipFile(cls.TEMPLATE_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('[Content_Types].xml', cls.CONTENT_TYPES_XML)
            zf.writestr('_rels/.rels', cls.RELS_XML)
            zf.writestr('word/_rels/document.xml.rels', cls.DOCUMENT_RELS_XML)
            zf.writestr('word/document.xml', document_xml)
            zf.writestr('word/styles.xml', cls.STYLES_XML)
            zf.writestr('word/settings.xml', cls.SETTINGS_XML)
            zf.writestr('word/footnotes.xml', footnotes_xml)

        print(f"[OK] Template criado: {cls.TEMPLATE_PATH}")
        return cls.TEMPLATE_PATH

    @classmethod
    def ensure_template(cls) -> Path:
        """Garante que o template existe."""
        if not cls.TEMPLATE_PATH.exists():
            cls.create_default_template()
        return cls.TEMPLATE_PATH


class VocabularyEnricher:
    """Enriquece livros com vocabulário em inglês usando notas de rodapé."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        source_lang: str = 'pt',
        num_words: int = 100,
        use_api: bool = False,
        api_key: str = ""
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.source_lang = source_lang
        self.num_words = num_words
        self.use_api = use_api
        self.api_key = api_key or GEMINI_API_KEY

        self.cache = TranslationCache()
        self.stopwords = STOPWORDS.get(source_lang, set())
        self.dictionary = self._load_dictionary()

        self.enriched = 0
        self.failed = 0
        self.stats = {"started": datetime.now().isoformat(), "books": []}

        # Garantir template
        TemplateManager.ensure_template()

    def _load_dictionary(self) -> Dict[str, str]:
        """Carrega dicionário de traduções."""
        dicts = {
            'pt': {
                'amor': 'love', 'vida': 'life', 'tempo': 'time', 'mundo': 'world',
                'homem': 'man', 'mulher': 'woman', 'casa': 'house', 'dia': 'day',
                'noite': 'night', 'água': 'water', 'terra': 'earth', 'fogo': 'fire',
                'ar': 'air', 'sol': 'sun', 'lua': 'moon', 'estrela': 'star',
                'olhos': 'eyes', 'olho': 'eye', 'mãos': 'hands', 'mão': 'hand',
                'coração': 'heart', 'alma': 'soul', 'mente': 'mind', 'corpo': 'body',
                'sangue': 'blood', 'morte': 'death', 'guerra': 'war', 'paz': 'peace',
                'rei': 'king', 'rainha': 'queen', 'príncipe': 'prince', 'princesa': 'princess',
                'filho': 'son', 'filha': 'daughter', 'pai': 'father', 'mãe': 'mother',
                'irmão': 'brother', 'irmã': 'sister', 'amigo': 'friend', 'inimigo': 'enemy',
                'livro': 'book', 'palavra': 'word', 'história': 'history', 'verdade': 'truth',
                'mentira': 'lie', 'força': 'strength', 'poder': 'power', 'beleza': 'beauty',
                'felicidade': 'happiness', 'tristeza': 'sadness', 'medo': 'fear',
                'coragem': 'courage', 'esperança': 'hope', 'fé': 'faith',
                'deus': 'god', 'céu': 'sky', 'inferno': 'hell',
                'anjo': 'angel', 'demônio': 'demon', 'espírito': 'spirit',
                'cidade': 'city', 'país': 'country', 'rua': 'street', 'caminho': 'path',
                'porta': 'door', 'janela': 'window', 'mesa': 'table', 'cadeira': 'chair',
                'cama': 'bed', 'quarto': 'room', 'sala': 'room', 'cozinha': 'kitchen',
                'comida': 'food', 'pão': 'bread', 'vinho': 'wine', 'carne': 'meat',
                'peixe': 'fish', 'fruta': 'fruit', 'árvore': 'tree', 'flor': 'flower',
                'mar': 'sea', 'rio': 'river', 'montanha': 'mountain', 'floresta': 'forest',
                'animal': 'animal', 'cão': 'dog', 'cachorro': 'dog', 'gato': 'cat',
                'cavalo': 'horse', 'pássaro': 'bird',
                'trabalho': 'work', 'dinheiro': 'money', 'ouro': 'gold', 'prata': 'silver',
                'roupa': 'clothes', 'vestido': 'dress', 'sapato': 'shoe',
                'batalha': 'battle', 'vitória': 'victory', 'derrota': 'defeat',
                'espada': 'sword', 'arma': 'weapon', 'escudo': 'shield',
                'nome': 'name', 'voz': 'voice', 'som': 'sound', 'música': 'music',
                'arte': 'art', 'pintura': 'painting', 'poesia': 'poetry',
                'sonho': 'dream', 'sonhos': 'dreams', 'desejo': 'desire', 'vontade': 'will',
                'razão': 'reason', 'pensamento': 'thought', 'ideia': 'idea',
                'segredo': 'secret', 'mistério': 'mystery', 'magia': 'magic',
                'destino': 'destiny', 'sorte': 'luck', 'acaso': 'chance',
                'início': 'beginning', 'fim': 'end', 'meio': 'middle',
                'momento': 'moment', 'hora': 'hour', 'minuto': 'minute',
                'semana': 'week', 'mês': 'month', 'ano': 'year', 'século': 'century',
                'passado': 'past', 'presente': 'present', 'futuro': 'future',
                'grande': 'big', 'pequeno': 'small', 'bom': 'good', 'mau': 'bad',
                'novo': 'new', 'velho': 'old', 'jovem': 'young', 'belo': 'beautiful',
                'feio': 'ugly', 'forte': 'strong', 'fraco': 'weak', 'rico': 'rich',
                'pobre': 'poor', 'feliz': 'happy', 'triste': 'sad', 'certo': 'right',
                'errado': 'wrong', 'claro': 'clear', 'escuro': 'dark', 'quente': 'hot',
                'frio': 'cold', 'alto': 'tall', 'baixo': 'short', 'longo': 'long',
                'curto': 'short', 'pesado': 'heavy', 'leve': 'light', 'duro': 'hard',
                'seco': 'dry', 'molhado': 'wet', 'limpo': 'clean', 'sujo': 'dirty',
                'cheio': 'full', 'vazio': 'empty', 'aberto': 'open', 'fechado': 'closed',
                'vivo': 'alive', 'morto': 'dead', 'perto': 'near', 'longe': 'far',
                'ser': 'be', 'estar': 'be', 'ter': 'have', 'fazer': 'do',
                'dizer': 'say', 'falar': 'speak', 'ver': 'see', 'ouvir': 'hear',
                'sentir': 'feel', 'pensar': 'think', 'saber': 'know', 'querer': 'want',
                'poder': 'can', 'dever': 'must', 'precisar': 'need',
                'dar': 'give', 'tomar': 'take', 'ir': 'go', 'vir': 'come',
                'andar': 'walk', 'correr': 'run', 'voar': 'fly', 'nadar': 'swim',
                'cair': 'fall', 'subir': 'climb', 'descer': 'descend',
                'abrir': 'open', 'fechar': 'close', 'começar': 'start', 'terminar': 'finish',
                'encontrar': 'find', 'perder': 'lose', 'ganhar': 'win',
                'trabalhar': 'work', 'jogar': 'play', 'brincar': 'play',
                'ler': 'read', 'escrever': 'write', 'cantar': 'sing', 'dançar': 'dance',
                'rir': 'laugh', 'chorar': 'cry', 'gritar': 'shout', 'chamar': 'call',
                'amar': 'love', 'odiar': 'hate', 'gostar': 'like',
                'viver': 'live', 'morrer': 'die', 'nascer': 'born', 'crescer': 'grow',
                'comer': 'eat', 'beber': 'drink', 'dormir': 'sleep', 'acordar': 'wake',
                'sonhar': 'dream', 'lembrar': 'remember', 'esquecer': 'forget',
                'esperar': 'wait', 'procurar': 'search', 'buscar': 'seek',
                'tentar': 'try', 'conseguir': 'achieve', 'deixar': 'leave',
                'ficar': 'stay', 'voltar': 'return', 'trazer': 'bring', 'levar': 'take',
                'olhar': 'look', 'tocar': 'touch', 'segurar': 'hold',
                'lutar': 'fight', 'matar': 'kill', 'salvar': 'save', 'ajudar': 'help',
                'criar': 'create', 'destruir': 'destroy', 'construir': 'build',
                'mudar': 'change', 'acreditar': 'believe', 'confiar': 'trust',
                'sempre': 'always', 'nunca': 'never', 'agora': 'now', 'hoje': 'today',
                'ontem': 'yesterday', 'amanhã': 'tomorrow', 'aqui': 'here', 'ali': 'there',
                # Palavras comuns em textos literários/filosóficos
                'estado': 'state', 'governo': 'government', 'pessoas': 'people', 'povo': 'people',
                'cidadão': 'citizen', 'cidadãos': 'citizens', 'democracia': 'democracy',
                'liberdade': 'freedom', 'justiça': 'justice', 'direito': 'right', 'direitos': 'rights',
                'dever': 'duty', 'deveres': 'duties', 'lei': 'law', 'leis': 'laws',
                'ordem': 'order', 'sociedade': 'society', 'natureza': 'nature', 'natural': 'natural',
                'todos': 'all', 'outros': 'others', 'outro': 'other', 'mesmo': 'same',
                'cada': 'each', 'apenas': 'only', 'ainda': 'still', 'muito': 'much',
                'parte': 'part', 'partes': 'parts', 'todo': 'whole', 'forma': 'form',
                'modo': 'way', 'maneira': 'manner', 'caso': 'case', 'coisa': 'thing',
                'coisas': 'things', 'fato': 'fact', 'fatos': 'facts', 'causa': 'cause',
                'efeito': 'effect', 'princípio': 'principle', 'fim': 'end', 'meio': 'means',
                'objeto': 'object', 'sujeito': 'subject', 'ação': 'action', 'movimento': 'movement',
                'lugar': 'place', 'lugares': 'places', 'espaço': 'space', 'tempo': 'time',
                'vezes': 'times', 'número': 'number', 'quantidade': 'quantity', 'qualidade': 'quality',
                'sentido': 'sense', 'significado': 'meaning', 'valor': 'value', 'importante': 'important',
                'necessário': 'necessary', 'possível': 'possible', 'impossível': 'impossible',
                'verdadeiro': 'true', 'falso': 'false', 'real': 'real', 'aparente': 'apparent',
                'primeiro': 'first', 'último': 'last', 'segundo': 'second', 'terceiro': 'third',
                'maior': 'greater', 'menor': 'lesser', 'melhor': 'better', 'pior': 'worse',
                'igual': 'equal', 'diferente': 'different', 'semelhante': 'similar', 'contrário': 'contrary',
                'exemplo': 'example', 'questão': 'question', 'problema': 'problem', 'solução': 'solution',
                'resposta': 'answer', 'pergunta': 'question', 'opinião': 'opinion', 'conhecimento': 'knowledge',
                'ciência': 'science', 'filosofia': 'philosophy', 'religião': 'religion', 'arte': 'art',
                'cultura': 'culture', 'educação': 'education', 'experiência': 'experience',
                'teoria': 'theory', 'prática': 'practice', 'método': 'method', 'sistema': 'system',
                'relação': 'relation', 'conexão': 'connection', 'união': 'union', 'separação': 'separation',
                'indivíduo': 'individual', 'grupo': 'group', 'classe': 'class', 'família': 'family',
                'comunidade': 'community', 'nação': 'nation', 'pátria': 'homeland', 'estrangeiro': 'foreigner',
                'guerra': 'war', 'paz': 'peace', 'conflito': 'conflict', 'acordo': 'agreement',
                'contrato': 'contract', 'promessa': 'promise', 'palavra': 'word', 'discurso': 'speech',
                'linguagem': 'language', 'escrita': 'writing', 'leitura': 'reading', 'texto': 'text',
                'autor': 'author', 'obra': 'work', 'livro': 'book', 'capítulo': 'chapter',
                'página': 'page', 'linha': 'line', 'parágrafo': 'paragraph', 'frase': 'sentence',
                'caráter': 'character', 'personalidade': 'personality', 'comportamento': 'behavior',
                'atitude': 'attitude', 'intenção': 'intention', 'vontade': 'will', 'desejo': 'desire',
                'paixão': 'passion', 'emoção': 'emotion', 'sentimento': 'feeling', 'afeto': 'affection',
                'prazer': 'pleasure', 'dor': 'pain', 'sofrimento': 'suffering', 'alegria': 'joy',
                'virtude': 'virtue', 'vício': 'vice', 'bem': 'good', 'mal': 'evil',
                'bondade': 'goodness', 'maldade': 'evil', 'inocência': 'innocence', 'culpa': 'guilt',
                'pecado': 'sin', 'salvação': 'salvation', 'perdão': 'forgiveness', 'castigo': 'punishment',
                'recompensa': 'reward', 'mérito': 'merit', 'glória': 'glory', 'honra': 'honor',
                'vergonha': 'shame', 'orgulho': 'pride', 'humildade': 'humility', 'vaidade': 'vanity',
                'sabedoria': 'wisdom', 'ignorância': 'ignorance', 'loucura': 'madness', 'sanidade': 'sanity',
                'consciência': 'consciousness', 'inconsciência': 'unconsciousness', 'memória': 'memory',
                'imaginação': 'imagination', 'fantasia': 'fantasy', 'realidade': 'reality',
                'existência': 'existence', 'essência': 'essence', 'substância': 'substance',
                'acidente': 'accident', 'necessidade': 'necessity', 'contingência': 'contingency',
                'eternidade': 'eternity', 'infinito': 'infinite', 'finito': 'finite', 'absoluto': 'absolute',
                'relativo': 'relative', 'universal': 'universal', 'particular': 'particular',
                'geral': 'general', 'específico': 'specific', 'abstrato': 'abstract', 'concreto': 'concrete',
            },
            'es': {
                'amor': 'love', 'vida': 'life', 'tiempo': 'time', 'mundo': 'world',
                'hombre': 'man', 'mujer': 'woman', 'casa': 'house', 'día': 'day',
                'noche': 'night', 'agua': 'water', 'tierra': 'earth', 'fuego': 'fire',
                'corazón': 'heart', 'alma': 'soul', 'mente': 'mind', 'cuerpo': 'body',
                'muerte': 'death', 'guerra': 'war', 'paz': 'peace',
                'rey': 'king', 'reina': 'queen', 'hijo': 'son', 'hija': 'daughter',
                'padre': 'father', 'madre': 'mother', 'hermano': 'brother',
                'amigo': 'friend', 'enemigo': 'enemy', 'libro': 'book',
                'grande': 'big', 'pequeño': 'small', 'bueno': 'good', 'malo': 'bad',
                'nuevo': 'new', 'viejo': 'old', 'joven': 'young', 'bello': 'beautiful',
                'fuerte': 'strong', 'débil': 'weak', 'feliz': 'happy', 'triste': 'sad',
                'ser': 'be', 'tener': 'have', 'hacer': 'do', 'decir': 'say',
                'ver': 'see', 'oír': 'hear', 'sentir': 'feel', 'pensar': 'think',
                'querer': 'want', 'poder': 'can', 'vivir': 'live', 'morir': 'die',
                'amar': 'love', 'siempre': 'always', 'nunca': 'never',
            },
            'fr': {
                'amour': 'love', 'vie': 'life', 'temps': 'time', 'monde': 'world',
                'homme': 'man', 'femme': 'woman', 'maison': 'house', 'jour': 'day',
                'nuit': 'night', 'eau': 'water', 'terre': 'earth', 'feu': 'fire',
                'coeur': 'heart', 'âme': 'soul', 'esprit': 'mind', 'corps': 'body',
                'mort': 'death', 'guerre': 'war', 'paix': 'peace',
                'roi': 'king', 'reine': 'queen', 'fils': 'son', 'fille': 'daughter',
                'père': 'father', 'mère': 'mother', 'frère': 'brother',
                'ami': 'friend', 'ennemi': 'enemy', 'livre': 'book',
                'grand': 'big', 'petit': 'small', 'bon': 'good', 'mauvais': 'bad',
                'nouveau': 'new', 'vieux': 'old', 'jeune': 'young', 'beau': 'beautiful',
                'fort': 'strong', 'faible': 'weak', 'heureux': 'happy', 'triste': 'sad',
                'être': 'be', 'avoir': 'have', 'faire': 'do', 'dire': 'say',
                'voir': 'see', 'entendre': 'hear', 'sentir': 'feel', 'penser': 'think',
                'vouloir': 'want', 'pouvoir': 'can', 'vivre': 'live', 'mourir': 'die',
                'aimer': 'love', 'toujours': 'always', 'jamais': 'never',
            }
        }
        return dicts.get(self.source_lang, {})

    def is_valid_word(self, word: str) -> bool:
        if len(word) < 3:
            return False
        if word.lower() in self.stopwords:
            return False
        if not word.isalpha():
            return False
        return True

    def get_top_words(self, text: str) -> List[Tuple[str, int]]:
        words = re.findall(r'\b[a-záàâãäéèêëíìîïóòôõöúùûüçñ]+\b', text.lower())
        valid_words = [w for w in words if self.is_valid_word(w)]
        return Counter(valid_words).most_common(self.num_words)

    def translate_word(self, word: str) -> Optional[str]:
        word_lower = word.lower()

        # Cache
        cached = self.cache.get(word_lower, self.source_lang)
        if cached:
            return cached

        # Dicionário
        if word_lower in self.dictionary:
            trans = self.dictionary[word_lower]
            self.cache.set(word_lower, self.source_lang, trans)
            return trans

        # API
        if self.use_api and self.api_key:
            trans = self._translate_with_api(word_lower)
            if trans:
                self.cache.set(word_lower, self.source_lang, trans)
                return trans

        return None

    def _translate_with_api(self, word: str) -> Optional[str]:
        try:
            import urllib.request
            import json as json_module

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent?key={self.api_key}"
            lang_names = {'pt': 'Portuguese', 'es': 'Spanish', 'fr': 'French'}
            lang_name = lang_names.get(self.source_lang, self.source_lang)

            data = {
                "contents": [{"parts": [{"text": f"Translate '{word}' from {lang_name} to English. Reply with ONLY the English word."}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 20}
            }

            req = urllib.request.Request(url, json_module.dumps(data).encode(), {'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json_module.loads(resp.read())
                return result["candidates"][0]["content"]["parts"][0]["text"].strip().lower()
        except:
            return None

    @staticmethod
    def escape_xml(text: str) -> str:
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))

    def extract_metadata(self, content: str) -> Tuple[str, str]:
        """Extrai título e autor do conteúdo."""
        lines = content.split('\n')[:50]
        title = "Sem Título"
        author = "Autor Desconhecido"

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.lower().startswith('title:'):
                title = line.split(':', 1)[1].strip()
            elif line.lower().startswith('author:'):
                author = line.split(':', 1)[1].strip()
            elif 'by ' in line.lower() and len(line) < 150:
                parts = re.split(r'\s+by\s+', line, flags=re.IGNORECASE)
                if len(parts) == 2:
                    if not title or title == "Sem Título":
                        title = parts[0].strip()
                    author = parts[1].strip()

        # Limpar título
        if len(title) > 100:
            title = title[:100] + "..."

        return title, author

    def build_content_xml(self, text: str, translations: Dict[str, str]) -> Tuple[str, str]:
        """Constrói o XML do conteúdo e das notas de rodapé."""
        paragraphs = text.split('\n\n')
        footnote_id = 1
        word_to_footnote = {}

        # Mapear palavras para IDs de nota
        for word in translations.keys():
            word_to_footnote[word.lower()] = footnote_id
            footnote_id += 1

        # === CONTEÚDO ===
        content_parts = []
        used_footnotes = set()

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Capítulo?
            is_chapter = (
                para.upper().startswith('CHAPTER') or
                para.upper().startswith('CAPÍTULO') or
                para.upper().startswith('CHAPITRE') or
                re.match(r'^[IVXLC]+[\.\s]', para.upper())
            )

            if is_chapter:
                content_parts.append(f'''<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
<w:r><w:t>{self.escape_xml(para)}</w:t></w:r></w:p>''')
                continue

            # Parágrafo normal com notas
            content_parts.append('<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>')

            tokens = re.split(r'(\s+)', para)
            for token in tokens:
                if not token:
                    continue

                match = re.match(r'^([a-záàâãäéèêëíìîïóòôõöúùûüçñA-ZÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ]+)(.*)$', token)

                if match:
                    word, punct = match.group(1), match.group(2)
                    word_lower = word.lower()

                    if word_lower in word_to_footnote and word_lower not in used_footnotes:
                        fn_id = word_to_footnote[word_lower]
                        used_footnotes.add(word_lower)

                        content_parts.append(f'<w:r><w:rPr><w:b/></w:rPr><w:t>{self.escape_xml(word)}</w:t></w:r>')
                        content_parts.append(f'<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="{fn_id}"/></w:r>')
                        if punct:
                            content_parts.append(f'<w:r><w:t>{self.escape_xml(punct)}</w:t></w:r>')
                    else:
                        content_parts.append(f'<w:r><w:t>{self.escape_xml(token)}</w:t></w:r>')
                else:
                    content_parts.append(f'<w:r><w:t xml:space="preserve">{self.escape_xml(token)}</w:t></w:r>')

            content_parts.append('</w:p>')

        # === GLOSSÁRIO ===
        content_parts.append('''<w:p><w:r><w:br w:type="page"/></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
<w:r><w:t>GLOSSARY / GLOSSÁRIO</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>
<w:r><w:rPr><w:i/><w:sz w:val="20"/></w:rPr>
<w:t>Alphabetical list of translated words / Lista alfabética de palavras traduzidas</w:t></w:r></w:p>
<w:p/>''')

        for word, trans in sorted(translations.items()):
            content_parts.append(f'''<w:p><w:pPr><w:pStyle w:val="Glossary"/></w:pPr>
<w:r><w:rPr><w:b/></w:rPr><w:t>{self.escape_xml(word)}</w:t></w:r>
<w:r><w:t xml:space="preserve"> → </w:t></w:r>
<w:r><w:rPr><w:i/><w:color w:val="0066CC"/></w:rPr><w:t>{self.escape_xml(trans)}</w:t></w:r></w:p>''')

        content_xml = '\n'.join(content_parts)

        # === NOTAS DE RODAPÉ ===
        fn_parts = ['''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>''']

        for word, trans in translations.items():
            fn_id = word_to_footnote[word.lower()]
            fn_parts.append(f'''<w:footnote w:id="{fn_id}">
<w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>
<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteRef/></w:r>
<w:r><w:t xml:space="preserve"> </w:t></w:r>
<w:r><w:rPr><w:b/></w:rPr><w:t>{self.escape_xml(word)}</w:t></w:r>
<w:r><w:t xml:space="preserve"> = </w:t></w:r>
<w:r><w:rPr><w:i/><w:color w:val="0066CC"/></w:rPr><w:t>{self.escape_xml(trans)}</w:t></w:r></w:p>
</w:footnote>''')

        fn_parts.append('</w:footnotes>')
        footnotes_xml = '\n'.join(fn_parts)

        return content_xml, footnotes_xml

    def create_docx(
        self,
        content: str,
        translations: Dict[str, str],
        output_path: Path,
        title: str,
        author: str
    ) -> bool:
        """Cria DOCX usando template do usuário.

        Estrutura do template:
        - Páginas 1-2: Intro (citações, etc.) - PRESERVAR
        - INSERIR CONTEÚDO DO LIVRO AQUI
        - Última página: Copyright + dados da livraria - PRESERVAR

        O conteúdo é inserido ANTES do parágrafo que contém "Copyright".
        """
        try:
            template_path = TemplateManager.TEMPLATE_PATH
            if not template_path.exists():
                template_path = TemplateManager.ensure_template()

            # Construir conteúdo e notas
            content_xml, footnotes_xml = self.build_content_xml(content, translations)

            # Criar DOCX copiando template e modificando
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(template_path, 'r') as template_zip:
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out_zip:

                    # Track se footnotes.xml já existe no template
                    has_footnotes = 'word/footnotes.xml' in template_zip.namelist()

                    # Copia todos os arquivos do template
                    for item in template_zip.namelist():
                        if item == 'word/document.xml':
                            # Modifica document.xml para injetar conteúdo
                            doc_xml = template_zip.read(item).decode('utf-8')

                            # Encontra o parágrafo que contém "Copyright" (início do back matter)
                            # Este é o marcador para inserir conteúdo ANTES dele
                            copyright_match = re.search(r'<w:p[^>]*>(?:(?!</w:p>).)*Copyright(?:(?!</w:p>).)*</w:p>', doc_xml, re.DOTALL)

                            if copyright_match:
                                # Injeta conteúdo ANTES do parágrafo de Copyright
                                insert_pos = copyright_match.start()

                                # Adiciona page break + conteúdo do livro + page break para o back matter
                                page_break = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
                                doc_xml = doc_xml[:insert_pos] + page_break + content_xml + '\n' + page_break + doc_xml[insert_pos:]
                            else:
                                # Fallback: procura sectPr
                                sectpr_match = re.search(r'(<w:sectPr[^>]*>)', doc_xml)
                                if sectpr_match:
                                    insert_pos = sectpr_match.start()
                                    page_break = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
                                    doc_xml = doc_xml[:insert_pos] + page_break + content_xml + '\n' + doc_xml[insert_pos:]
                                else:
                                    # Último fallback: antes de </w:body>
                                    doc_xml = doc_xml.replace('</w:body>', content_xml + '\n</w:body>')

                            out_zip.writestr(item, doc_xml.encode('utf-8'))

                        elif item == 'word/footnotes.xml':
                            # Substitui footnotes existente pelo nosso
                            out_zip.writestr(item, footnotes_xml)
                            has_footnotes = True

                        elif item == '[Content_Types].xml':
                            # Adiciona footnotes ao content types se necessário
                            ct_xml = template_zip.read(item).decode('utf-8')
                            if 'footnotes.xml' not in ct_xml:
                                ct_xml = ct_xml.replace(
                                    '</Types>',
                                    '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>\n</Types>'
                                )
                            out_zip.writestr(item, ct_xml.encode('utf-8'))

                        elif item == 'word/_rels/document.xml.rels':
                            # Adiciona relação para footnotes se necessário
                            rels_xml = template_zip.read(item).decode('utf-8')
                            if 'footnotes.xml' not in rels_xml:
                                # Encontra próximo rId disponível
                                ids = re.findall(r'rId(\d+)', rels_xml)
                                next_id = max(int(i) for i in ids) + 1 if ids else 10
                                new_rel = f'<Relationship Id="rId{next_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>\n'
                                rels_xml = rels_xml.replace('</Relationships>', new_rel + '</Relationships>')
                            out_zip.writestr(item, rels_xml.encode('utf-8'))

                        else:
                            # Copia arquivo sem modificação
                            out_zip.writestr(item, template_zip.read(item))

                    # Adiciona footnotes.xml se ainda não foi adicionado
                    if not has_footnotes:
                        out_zip.writestr('word/footnotes.xml', footnotes_xml)

            return True

        except Exception as e:
            print(f"[ERRO] Criar DOCX: {e}")
            import traceback
            traceback.print_exc()
            return False

    def process_file(self, filepath: Path) -> Optional[Dict]:
        """Processa um arquivo TXT."""
        try:
            print(f"[...] {filepath.name}")

            content = filepath.read_text(encoding='utf-8', errors='ignore')
            title, author = self.extract_metadata(content)

            if title == "Sem Título":
                title = filepath.stem.replace('_', ' ').replace('-', ' ').title()

            top_words = self.get_top_words(content)

            translations = {}
            for word, _ in top_words:
                trans = self.translate_word(word)
                if trans and trans.lower() != word.lower():
                    translations[word] = trans

            if not translations:
                print(f"[SKIP] {filepath.name} - Sem traduções")
                return None

            output_name = filepath.stem + "_enriched.docx"
            output_path = self.output_dir / output_name

            if self.create_docx(content, translations, output_path, title, author):
                print(f"[OK] {filepath.name} → {output_name} ({len(translations)} palavras)")
                return {
                    "source": str(filepath),
                    "output": str(output_path),
                    "title": title,
                    "author": author,
                    "words": len(translations)
                }

            return None

        except Exception as e:
            print(f"[ERRO] {filepath.name}: {e}")
            return None

    def run(self, limit: int = 0) -> List[Dict]:
        """Executa enriquecimento."""
        print(f"\n{'='*60}")
        print(f"ENRICHER - Template + Notas de Rodapé + Glossário")
        print(f"{'='*60}")
        print(f"Idioma: {self.source_lang.upper()} → EN")
        print(f"Palavras: {self.num_words}")
        print(f"Template: {TemplateManager.TEMPLATE_PATH}")
        print(f"Entrada: {self.input_dir}")
        print(f"Saída: {self.output_dir}")
        print(f"{'='*60}\n")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        files = list(self.input_dir.glob("**/*.txt"))
        if limit > 0:
            files = files[:limit]

        print(f"Arquivos: {len(files)}\n")

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

        stats_file = self.output_dir / "enricher_stats.json"
        stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        print(f"\n{'='*60}")
        print(f"CONCLUÍDO: {self.enriched} enriquecidos, {self.failed} falhas")
        print(f"{'='*60}\n")

        return results


def main():
    parser = argparse.ArgumentParser(description="Enriquecer livros com vocabulário inglês")
    parser.add_argument("--input", default="books/txt/pt", help="Pasta de entrada")
    parser.add_argument("--output", default="books/docx/pt/enriched", help="Pasta de saída")
    parser.add_argument("--lang", default="pt", choices=['pt', 'es', 'fr'], help="Idioma")
    parser.add_argument("--words", type=int, default=100, help="Número de palavras")
    parser.add_argument("--limit", type=int, default=0, help="Limite de arquivos")
    parser.add_argument("--use-api", action="store_true", help="Usar Gemini API")
    parser.add_argument("--api-key", help="Gemini API Key")

    args = parser.parse_args()

    enricher = VocabularyEnricher(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        source_lang=args.lang,
        num_words=args.words,
        use_api=args.use_api,
        api_key=args.api_key or ""
    )
    enricher.run(args.limit)


if __name__ == "__main__":
    main()
