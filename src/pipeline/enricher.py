#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MÓDULO 5: ENRICHER (Enriquecedor de Vocabulário)
================================================
Adiciona 100 palavras em inglês com NOTAS DE RODAPÉ em livros PT/ES/FR.

Características:
    - Template DOCX externo customizável
    - Notas de rodapé discretas (não polui o texto)
    - Glossário alfabético no final
    - Cache de traduções (economia de API)

Uso:
    python -m src.pipeline.enricher --input books/txt/pt --output books/docx/pt/enriched --words 100

Entrada:
    books/txt/{pt,es,fr}/

Saída:
    books/docx/{pt,es,fr}/enriched/
"""

import os
import re
import json
import sqlite3
import hashlib
import argparse
import zipfile
import shutil
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Set
from datetime import datetime
from collections import Counter
from xml.etree import ElementTree as ET

# Namespaces do DOCX
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'wp': 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing',
}

# Registrar namespaces
for prefix, uri in NAMESPACES.items():
    ET.register_namespace(prefix, uri)

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
    },
    'es': {
        'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas', 'de', 'del', 'al',
        'y', 'e', 'o', 'u', 'que', 'en', 'a', 'por', 'para', 'con', 'sin', 'sobre',
        'se', 'no', 'más', 'pero', 'como', 'fue', 'ser', 'son', 'está', 'estar',
        'su', 'sus', 'lo', 'le', 'les', 'me', 'te', 'nos', 'os', 'mi', 'tu',
        'yo', 'tú', 'él', 'ella', 'usted', 'nosotros', 'vosotros', 'ellos', 'ellas',
    },
    'fr': {
        'le', 'la', 'les', 'un', 'une', 'des', 'de', 'du', 'au', 'aux', 'et', 'ou',
        'que', 'qui', 'en', 'à', 'par', 'pour', 'avec', 'sans', 'sur', 'sous',
        'se', 'ne', 'pas', 'plus', 'mais', 'comme', 'était', 'être', 'sont', 'est',
        'son', 'sa', 'ses', 'leur', 'leurs', 'ce', 'cette', 'ces', 'mon', 'ma', 'mes',
        'je', 'tu', 'il', 'elle', 'on', 'nous', 'vous', 'ils', 'elles', 'me', 'te',
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
                    word TEXT,
                    source_lang TEXT,
                    target_lang TEXT,
                    translation TEXT,
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

    def get_all(self, source_lang: str) -> Dict[str, str]:
        """Retorna todas as traduções do cache."""
        with sqlite3.connect(self.cache_path) as conn:
            cursor = conn.execute(
                'SELECT word, translation FROM translations WHERE source_lang=? AND target_lang=?',
                (source_lang, 'en')
            )
            return {row[0]: row[1] for row in cursor.fetchall()}


class DocxTemplate:
    """Gerenciador de template DOCX."""

    TEMPLATE_PATH = Path("templates/kdp_enriched_template.docx")

    # XML Templates
    CONTENT_TYPES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>'''

    RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    DOCUMENT_RELS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>
</Relationships>'''

    STYLES = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr>
<w:rFonts w:ascii="Georgia" w:hAnsi="Georgia" w:eastAsia="Georgia" w:cs="Georgia"/>
<w:sz w:val="24"/><w:szCs w:val="24"/>
<w:lang w:val="pt-BR"/>
</w:rPr></w:rPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:styleId="Title">
<w:name w:val="Title"/>
<w:pPr><w:jc w:val="center"/><w:spacing w:before="2000" w:after="400"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="56"/><w:szCs w:val="56"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Subtitle">
<w:name w:val="Subtitle"/>
<w:pPr><w:jc w:val="center"/><w:spacing w:after="200"/></w:pPr>
<w:rPr><w:i/><w:sz w:val="28"/><w:szCs w:val="28"/><w:color w:val="666666"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
<w:name w:val="Heading 1"/>
<w:pPr><w:spacing w:before="400" w:after="200"/><w:keepNext/></w:pPr>
<w:rPr><w:b/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading2">
<w:name w:val="Heading 2"/>
<w:pPr><w:spacing w:before="300" w:after="150"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="28"/><w:szCs w:val="28"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Normal">
<w:name w:val="Normal"/>
<w:pPr><w:spacing w:after="200" w:line="288" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>
<w:rPr><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Glossary">
<w:name w:val="Glossary"/>
<w:pPr><w:spacing w:after="80"/><w:ind w:left="400"/></w:pPr>
<w:rPr><w:sz w:val="22"/><w:szCs w:val="22"/><w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/></w:rPr>
</w:style>
<w:style w:type="character" w:styleId="FootnoteReference">
<w:name w:val="Footnote Reference"/>
<w:rPr><w:vertAlign w:val="superscript"/><w:color w:val="0066CC"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="FootnoteText">
<w:name w:val="Footnote Text"/>
<w:pPr><w:spacing w:after="40"/></w:pPr>
<w:rPr><w:sz w:val="18"/><w:szCs w:val="18"/><w:color w:val="444444"/></w:rPr>
</w:style>
</w:styles>'''

    SETTINGS = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:defaultTabStop w:val="720"/>
<w:characterSpacingControl w:val="doNotCompress"/>
<w:footnotePr><w:numFmt w:val="decimal"/></w:footnotePr>
</w:settings>'''

    FOOTNOTES_HEADER = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
             xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:footnote w:type="separator" w:id="-1">
<w:p><w:r><w:separator/></w:r></w:p>
</w:footnote>
<w:footnote w:type="continuationSeparator" w:id="0">
<w:p><w:r><w:continuationSeparator/></w:r></w:p>
</w:footnote>
'''

    FOOTNOTES_FOOTER = '''</w:footnotes>'''

    @classmethod
    def create_template(cls):
        """Cria o template DOCX se não existir."""
        if cls.TEMPLATE_PATH.exists():
            return

        cls.TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)

        with zipfile.ZipFile(cls.TEMPLATE_PATH, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('[Content_Types].xml', cls.CONTENT_TYPES)
            zf.writestr('_rels/.rels', cls.RELS)
            zf.writestr('word/_rels/document.xml.rels', cls.DOCUMENT_RELS)
            zf.writestr('word/styles.xml', cls.STYLES)
            zf.writestr('word/settings.xml', cls.SETTINGS)
            # Documento vazio será substituído
            zf.writestr('word/document.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body><w:p/></w:body></w:document>''')
            zf.writestr('word/footnotes.xml', cls.FOOTNOTES_HEADER + cls.FOOTNOTES_FOOTER)

        print(f"[OK] Template criado: {cls.TEMPLATE_PATH}")


class VocabularyEnricher:
    """Enriquece livros com vocabulário em inglês usando notas de rodapé."""

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

        # Carregar dicionário expandido
        self.dictionary = self._load_dictionary()

        # Criar template se necessário
        DocxTemplate.create_template()

    def _load_dictionary(self) -> Dict[str, str]:
        """Carrega dicionário de traduções."""
        # Dicionário expandido PT/ES/FR -> EN
        dicts = {
            'pt': {
                # Substantivos
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
                'deus': 'god', 'céu': 'sky', 'heaven': 'heaven', 'inferno': 'hell',
                'anjo': 'angel', 'demônio': 'demon', 'espírito': 'spirit',
                'cidade': 'city', 'país': 'country', 'rua': 'street', 'caminho': 'path',
                'porta': 'door', 'janela': 'window', 'mesa': 'table', 'cadeira': 'chair',
                'cama': 'bed', 'quarto': 'room', 'sala': 'room', 'cozinha': 'kitchen',
                'comida': 'food', 'pão': 'bread', 'vinho': 'wine', 'carne': 'meat',
                'peixe': 'fish', 'fruta': 'fruit', 'árvore': 'tree', 'flor': 'flower',
                'mar': 'sea', 'rio': 'river', 'montanha': 'mountain', 'floresta': 'forest',
                'animal': 'animal', 'cão': 'dog', 'cachorro': 'dog', 'gato': 'cat',
                'cavalo': 'horse', 'pássaro': 'bird', 'peixe': 'fish',
                'trabalho': 'work', 'dinheiro': 'money', 'ouro': 'gold', 'prata': 'silver',
                'roupa': 'clothes', 'vestido': 'dress', 'sapato': 'shoe',
                'guerra': 'war', 'batalha': 'battle', 'vitória': 'victory', 'derrota': 'defeat',
                'espada': 'sword', 'arma': 'weapon', 'escudo': 'shield',
                'nome': 'name', 'voz': 'voice', 'som': 'sound', 'música': 'music',
                'arte': 'art', 'pintura': 'painting', 'poesia': 'poetry',
                'sonho': 'dream', 'sonhos': 'dreams', 'desejo': 'desire', 'vontade': 'will',
                'razão': 'reason', 'pensamento': 'thought', 'ideia': 'idea',
                'segredo': 'secret', 'mistério': 'mystery', 'magia': 'magic',
                'destino': 'destiny', 'sorte': 'luck', 'acaso': 'chance',
                'início': 'beginning', 'fim': 'end', 'meio': 'middle',
                'momento': 'moment', 'hora': 'hour', 'minuto': 'minute', 'segundo': 'second',
                'semana': 'week', 'mês': 'month', 'ano': 'year', 'século': 'century',
                'passado': 'past', 'presente': 'present', 'futuro': 'future',
                # Adjetivos
                'grande': 'big', 'pequeno': 'small', 'bom': 'good', 'mau': 'bad',
                'novo': 'new', 'velho': 'old', 'jovem': 'young', 'belo': 'beautiful',
                'feio': 'ugly', 'forte': 'strong', 'fraco': 'weak', 'rico': 'rich',
                'pobre': 'poor', 'feliz': 'happy', 'triste': 'sad', 'certo': 'right',
                'errado': 'wrong', 'claro': 'clear', 'escuro': 'dark', 'quente': 'hot',
                'frio': 'cold', 'alto': 'tall', 'baixo': 'short', 'longo': 'long',
                'curto': 'short', 'largo': 'wide', 'estreito': 'narrow',
                'pesado': 'heavy', 'leve': 'light', 'duro': 'hard', 'mole': 'soft',
                'seco': 'dry', 'molhado': 'wet', 'limpo': 'clean', 'sujo': 'dirty',
                'cheio': 'full', 'vazio': 'empty', 'aberto': 'open', 'fechado': 'closed',
                'vivo': 'alive', 'morto': 'dead', 'só': 'alone', 'junto': 'together',
                'perto': 'near', 'longe': 'far', 'primeiro': 'first', 'último': 'last',
                'mesmo': 'same', 'outro': 'other', 'cada': 'each', 'todo': 'all',
                'nenhum': 'none', 'algum': 'some', 'muito': 'much', 'pouco': 'little',
                'doce': 'sweet', 'amargo': 'bitter', 'salgado': 'salty',
                'bonito': 'beautiful', 'lindo': 'beautiful', 'horrível': 'horrible',
                'terrível': 'terrible', 'maravilhoso': 'wonderful', 'incrível': 'incredible',
                'possível': 'possible', 'impossível': 'impossible',
                'fácil': 'easy', 'difícil': 'difficult', 'simples': 'simple',
                'profundo': 'deep', 'raso': 'shallow', 'sagrado': 'sacred',
                # Verbos
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
                'tentar': 'try', 'conseguir': 'achieve', 'alcançar': 'reach',
                'deixar': 'leave', 'ficar': 'stay', 'voltar': 'return',
                'trazer': 'bring', 'levar': 'take', 'pegar': 'grab',
                'olhar': 'look', 'observar': 'observe', 'assistir': 'watch',
                'tocar': 'touch', 'segurar': 'hold', 'soltar': 'release',
                'lutar': 'fight', 'matar': 'kill', 'salvar': 'save', 'ajudar': 'help',
                'criar': 'create', 'destruir': 'destroy', 'construir': 'build',
                'mudar': 'change', 'transformar': 'transform',
                'acreditar': 'believe', 'confiar': 'trust', 'duvidar': 'doubt',
                'existir': 'exist', 'parecer': 'seem', 'tornar': 'become',
                # Advérbios e outros
                'sempre': 'always', 'nunca': 'never', 'agora': 'now', 'hoje': 'today',
                'ontem': 'yesterday', 'amanhã': 'tomorrow', 'aqui': 'here', 'ali': 'there',
                'dentro': 'inside', 'fora': 'outside', 'acima': 'above', 'abaixo': 'below',
                'frente': 'front', 'trás': 'back', 'lado': 'side',
                'apenas': 'only', 'também': 'also', 'ainda': 'still', 'já': 'already',
                'talvez': 'maybe', 'certamente': 'certainly', 'realmente': 'really',
                'verdadeiramente': 'truly', 'simplesmente': 'simply',
            },
            'es': {
                'amor': 'love', 'vida': 'life', 'tiempo': 'time', 'mundo': 'world',
                'hombre': 'man', 'mujer': 'woman', 'casa': 'house', 'día': 'day',
                'noche': 'night', 'agua': 'water', 'tierra': 'earth', 'fuego': 'fire',
                'aire': 'air', 'sol': 'sun', 'luna': 'moon', 'estrella': 'star',
                'ojos': 'eyes', 'ojo': 'eye', 'manos': 'hands', 'mano': 'hand',
                'corazón': 'heart', 'alma': 'soul', 'mente': 'mind', 'cuerpo': 'body',
                'sangre': 'blood', 'muerte': 'death', 'guerra': 'war', 'paz': 'peace',
                'rey': 'king', 'reina': 'queen', 'hijo': 'son', 'hija': 'daughter',
                'padre': 'father', 'madre': 'mother', 'hermano': 'brother', 'hermana': 'sister',
                'amigo': 'friend', 'enemigo': 'enemy', 'libro': 'book', 'palabra': 'word',
                'ciudad': 'city', 'país': 'country', 'camino': 'path', 'puerta': 'door',
                'grande': 'big', 'pequeño': 'small', 'bueno': 'good', 'malo': 'bad',
                'nuevo': 'new', 'viejo': 'old', 'joven': 'young', 'bello': 'beautiful',
                'fuerte': 'strong', 'débil': 'weak', 'rico': 'rich', 'pobre': 'poor',
                'feliz': 'happy', 'triste': 'sad', 'cierto': 'true', 'falso': 'false',
                'ser': 'be', 'estar': 'be', 'tener': 'have', 'hacer': 'do',
                'decir': 'say', 'hablar': 'speak', 'ver': 'see', 'oír': 'hear',
                'sentir': 'feel', 'pensar': 'think', 'saber': 'know', 'querer': 'want',
                'poder': 'can', 'deber': 'must', 'necesitar': 'need',
                'dar': 'give', 'tomar': 'take', 'ir': 'go', 'venir': 'come',
                'vivir': 'live', 'morir': 'die', 'nacer': 'born', 'crecer': 'grow',
                'comer': 'eat', 'beber': 'drink', 'dormir': 'sleep',
                'amar': 'love', 'odiar': 'hate', 'siempre': 'always', 'nunca': 'never',
            },
            'fr': {
                'amour': 'love', 'vie': 'life', 'temps': 'time', 'monde': 'world',
                'homme': 'man', 'femme': 'woman', 'maison': 'house', 'jour': 'day',
                'nuit': 'night', 'eau': 'water', 'terre': 'earth', 'feu': 'fire',
                'air': 'air', 'soleil': 'sun', 'lune': 'moon', 'étoile': 'star',
                'yeux': 'eyes', 'oeil': 'eye', 'mains': 'hands', 'main': 'hand',
                'coeur': 'heart', 'âme': 'soul', 'esprit': 'mind', 'corps': 'body',
                'sang': 'blood', 'mort': 'death', 'guerre': 'war', 'paix': 'peace',
                'roi': 'king', 'reine': 'queen', 'fils': 'son', 'fille': 'daughter',
                'père': 'father', 'mère': 'mother', 'frère': 'brother', 'soeur': 'sister',
                'ami': 'friend', 'ennemi': 'enemy', 'livre': 'book', 'mot': 'word',
                'ville': 'city', 'pays': 'country', 'chemin': 'path', 'porte': 'door',
                'grand': 'big', 'petit': 'small', 'bon': 'good', 'mauvais': 'bad',
                'nouveau': 'new', 'vieux': 'old', 'jeune': 'young', 'beau': 'beautiful',
                'fort': 'strong', 'faible': 'weak', 'riche': 'rich', 'pauvre': 'poor',
                'heureux': 'happy', 'triste': 'sad', 'vrai': 'true', 'faux': 'false',
                'être': 'be', 'avoir': 'have', 'faire': 'do', 'dire': 'say',
                'parler': 'speak', 'voir': 'see', 'entendre': 'hear', 'sentir': 'feel',
                'penser': 'think', 'savoir': 'know', 'vouloir': 'want', 'pouvoir': 'can',
                'devoir': 'must', 'donner': 'give', 'prendre': 'take',
                'aller': 'go', 'venir': 'come', 'vivre': 'live', 'mourir': 'die',
                'aimer': 'love', 'toujours': 'always', 'jamais': 'never',
            }
        }
        return dicts.get(self.source_lang, {})

    def is_valid_word(self, word: str) -> bool:
        """Verifica se é uma palavra válida para tradução."""
        if len(word) < 3:
            return False
        if word.lower() in self.stopwords:
            return False
        if not word.isalpha():
            return False
        return True

    def get_top_words(self, text: str) -> List[Tuple[str, int]]:
        """Extrai as N palavras mais frequentes."""
        words = re.findall(r'\b[a-záàâãäéèêëíìîïóòôõöúùûüçñ]+\b', text.lower())
        valid_words = [w for w in words if self.is_valid_word(w)]
        counter = Counter(valid_words)
        return counter.most_common(self.num_words)

    def translate_word(self, word: str) -> Optional[str]:
        """Traduz uma palavra para inglês."""
        word_lower = word.lower()

        # 1. Cache
        cached = self.cache.get(word_lower, self.source_lang)
        if cached:
            return cached

        # 2. Dicionário local
        if word_lower in self.dictionary:
            trans = self.dictionary[word_lower]
            self.cache.set(word_lower, self.source_lang, trans)
            return trans

        # 3. API (se habilitada)
        if self.use_api and self.api_key:
            trans = self._translate_with_api(word_lower)
            if trans:
                self.cache.set(word_lower, self.source_lang, trans)
                return trans

        return None

    def _translate_with_api(self, word: str) -> Optional[str]:
        """Traduz usando Gemini API."""
        try:
            import urllib.request
            import json as json_module

            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={self.api_key}"
            lang_names = {'pt': 'Portuguese', 'es': 'Spanish', 'fr': 'French'}
            lang_name = lang_names.get(self.source_lang, self.source_lang)

            data = {
                "contents": [{"parts": [{"text": f"Translate the {lang_name} word '{word}' to English. Reply with ONLY the English word, nothing else."}]}],
                "generationConfig": {"temperature": 0, "maxOutputTokens": 20}
            }

            req = urllib.request.Request(
                url,
                data=json_module.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'},
                method='POST'
            )

            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json_module.loads(resp.read().decode('utf-8'))
                return result["candidates"][0]["content"]["parts"][0]["text"].strip().lower()

        except Exception as e:
            print(f"[API ERRO] {word}: {e}")
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

    def create_enriched_docx(
        self,
        text: str,
        translations: Dict[str, str],
        output_path: Path,
        title: str,
        author: str = ""
    ) -> bool:
        """Cria DOCX com notas de rodapé e glossário."""
        try:
            # Preparar conteúdo
            paragraphs = text.split('\n\n')
            footnote_id = 1
            word_to_footnote = {}  # palavra -> id da nota

            # Atribuir IDs de nota para cada palavra traduzida
            for word in translations.keys():
                word_to_footnote[word.lower()] = footnote_id
                footnote_id += 1

            # === CONSTRUIR DOCUMENT.XML ===
            doc_parts = []
            doc_parts.append('''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<w:body>''')

            # Página de título
            lang_names = {'pt': 'Português', 'es': 'Español', 'fr': 'Français'}
            lang_name = lang_names.get(self.source_lang, self.source_lang)

            doc_parts.append(f'''
<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr>
<w:r><w:t>{self.escape_xml(title)}</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>
<w:r><w:t>{lang_name} + English Vocabulary</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Subtitle"/></w:pPr>
<w:r><w:rPr><w:sz w:val="20"/></w:rPr>
<w:t>{len(translations)} words with footnotes for active learning</w:t></w:r></w:p>
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
''')

            # Processar parágrafos
            used_footnotes = set()

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Detectar capítulos
                is_chapter = (
                    para.upper().startswith('CHAPTER') or
                    para.upper().startswith('CAPÍTULO') or
                    para.upper().startswith('CHAPITRE') or
                    re.match(r'^[IVXLC]+[\.\s]', para.upper())
                )

                if is_chapter:
                    doc_parts.append(f'''<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
<w:r><w:t>{self.escape_xml(para)}</w:t></w:r></w:p>''')
                    continue

                # Processar parágrafo com notas de rodapé
                doc_parts.append('<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>')

                # Dividir em palavras mantendo pontuação
                tokens = re.split(r'(\s+)', para)

                for token in tokens:
                    if not token:
                        continue

                    # Extrair palavra e pontuação
                    match = re.match(r'^([a-záàâãäéèêëíìîïóòôõöúùûüçñA-ZÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ]+)(.*)$', token, re.IGNORECASE)

                    if match:
                        word = match.group(1)
                        punct = match.group(2)
                        word_lower = word.lower()

                        # Verificar se tem tradução e ainda não usou a nota
                        if word_lower in word_to_footnote and word_lower not in used_footnotes:
                            fn_id = word_to_footnote[word_lower]
                            used_footnotes.add(word_lower)

                            # Palavra em negrito + referência de nota
                            doc_parts.append(f'''<w:r><w:rPr><w:b/></w:rPr><w:t>{self.escape_xml(word)}</w:t></w:r>''')
                            doc_parts.append(f'''<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>
<w:footnoteReference w:id="{fn_id}"/></w:r>''')
                            if punct:
                                doc_parts.append(f'''<w:r><w:t>{self.escape_xml(punct)}</w:t></w:r>''')
                        else:
                            doc_parts.append(f'''<w:r><w:t>{self.escape_xml(token)}</w:t></w:r>''')
                    else:
                        # Espaço ou pontuação
                        doc_parts.append(f'''<w:r><w:t xml:space="preserve">{self.escape_xml(token)}</w:t></w:r>''')

                doc_parts.append('</w:p>')

            # === GLOSSÁRIO ===
            doc_parts.append('''<w:p><w:r><w:br w:type="page"/></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
<w:r><w:t>GLOSSARY / GLOSSÁRIO</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="Normal"/></w:pPr>
<w:r><w:rPr><w:i/></w:rPr><w:t>Alphabetical list of translated words</w:t></w:r></w:p>
<w:p/>''')

            for word, trans in sorted(translations.items()):
                doc_parts.append(f'''<w:p><w:pPr><w:pStyle w:val="Glossary"/></w:pPr>
<w:r><w:rPr><w:b/></w:rPr><w:t>{self.escape_xml(word)}</w:t></w:r>
<w:r><w:t xml:space="preserve"> → </w:t></w:r>
<w:r><w:rPr><w:i/><w:color w:val="0066CC"/></w:rPr><w:t>{self.escape_xml(trans)}</w:t></w:r>
</w:p>''')

            # Fechar documento
            doc_parts.append('''
<w:sectPr>
<w:pgSz w:w="8640" w:h="12960"/>
<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="720" w:footer="720"/>
</w:sectPr>
</w:body></w:document>''')

            document_xml = ''.join(doc_parts)

            # === CONSTRUIR FOOTNOTES.XML ===
            fn_parts = [DocxTemplate.FOOTNOTES_HEADER]

            for word, trans in translations.items():
                fn_id = word_to_footnote[word.lower()]
                fn_parts.append(f'''<w:footnote w:id="{fn_id}">
<w:p><w:pPr><w:pStyle w:val="FootnoteText"/></w:pPr>
<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>
<w:footnoteRef/></w:r>
<w:r><w:t xml:space="preserve"> </w:t></w:r>
<w:r><w:rPr><w:b/></w:rPr><w:t>{self.escape_xml(word)}</w:t></w:r>
<w:r><w:t xml:space="preserve"> = </w:t></w:r>
<w:r><w:rPr><w:i/><w:color w:val="0066CC"/></w:rPr><w:t>{self.escape_xml(trans)}</w:t></w:r>
</w:p></w:footnote>
''')

            fn_parts.append(DocxTemplate.FOOTNOTES_FOOTER)
            footnotes_xml = ''.join(fn_parts)

            # === CRIAR DOCX ===
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', DocxTemplate.CONTENT_TYPES)
                zf.writestr('_rels/.rels', DocxTemplate.RELS)
                zf.writestr('word/_rels/document.xml.rels', DocxTemplate.DOCUMENT_RELS)
                zf.writestr('word/styles.xml', DocxTemplate.STYLES)
                zf.writestr('word/settings.xml', DocxTemplate.SETTINGS)
                zf.writestr('word/document.xml', document_xml)
                zf.writestr('word/footnotes.xml', footnotes_xml)

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

            # Ler conteúdo
            content = filepath.read_text(encoding='utf-8', errors='ignore')

            # Extrair título
            lines = content.split('\n')
            title = next((l.strip() for l in lines if l.strip() and len(l.strip()) > 3), filepath.stem)
            if len(title) > 100:
                title = title[:100] + "..."

            # Obter palavras mais frequentes
            top_words = self.get_top_words(content)

            # Traduzir
            translations = {}
            for word, count in top_words:
                trans = self.translate_word(word)
                if trans and trans.lower() != word.lower():
                    translations[word] = trans

            if not translations:
                print(f"[SKIP] {filepath.name} - Sem traduções")
                return None

            # Criar DOCX
            output_name = filepath.stem + "_enriched.docx"
            output_path = self.output_dir / output_name

            if self.create_enriched_docx(content, translations, output_path, title):
                print(f"[OK] {filepath.name} → {output_name} ({len(translations)} palavras)")
                return {
                    "source": str(filepath),
                    "output": str(output_path),
                    "title": title,
                    "words": len(translations),
                    "translations": translations
                }

            return None

        except Exception as e:
            print(f"[ERRO] {filepath.name}: {e}")
            return None

    def run(self, limit: int = 0) -> List[Dict]:
        """Executa enriquecimento."""
        print(f"\n{'='*60}")
        print(f"ENRICHER - Vocabulário com Notas de Rodapé")
        print(f"{'='*60}")
        print(f"Idioma: {self.source_lang.upper()} → EN")
        print(f"Palavras: {self.num_words}")
        print(f"Entrada: {self.input_dir}")
        print(f"Saída: {self.output_dir}")
        print(f"API: {'Habilitada' if self.use_api and self.api_key else 'Offline'}")
        print(f"{'='*60}\n")

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Listar arquivos
        files = list(self.input_dir.glob("**/*.txt"))
        if limit > 0:
            files = files[:limit]

        print(f"Arquivos: {len(files)}\n")

        # Processar
        results = []
        for filepath in files:
            result = self.process_file(filepath)
            if result:
                results.append(result)
                self.enriched += 1
            else:
                self.failed += 1

        # Estatísticas
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
    parser = argparse.ArgumentParser(description="Enriquecer livros com vocabulário inglês (notas de rodapé)")
    parser.add_argument("--input", default="books/txt/pt", help="Pasta de entrada")
    parser.add_argument("--output", default="books/docx/pt/enriched", help="Pasta de saída")
    parser.add_argument("--lang", default="pt", choices=['pt', 'es', 'fr'], help="Idioma de origem")
    parser.add_argument("--words", type=int, default=100, help="Número de palavras")
    parser.add_argument("--limit", type=int, default=0, help="Limite de arquivos (0=todos)")
    parser.add_argument("--use-api", action="store_true", help="Usar Gemini API para palavras extras")
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
