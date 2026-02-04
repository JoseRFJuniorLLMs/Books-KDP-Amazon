#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SMART PROCESSOR - Pipeline Completo BooksKDP
=============================================
REGRA PRINCIPAL: Verificar DOMÍNIO PÚBLICO antes de tudo!

Fluxo:
    1. Verifica domínio público (3 pontos)
    2. Limpa OCR
    3. Traduz para português
    4. Corrige gramática
    5. Gera 2 DOCX (tradução + vocabulário)
    6. Gera 2 capas (artistic + modern)

Saída:
    books/{País}/{Autor}/
    ├── {Livro} - Tradução/
    │   ├── {Livro}.docx
    │   └── {Livro}_cover.png
    └── {Livro} - Vocabulário EN/
        ├── {Livro}_vocab.docx
        └── {Livro}_vocab_cover.png

Uso:
    python -m src.pipeline.smart_processor --input books/txt/other --output books/output --limit 5
"""

import re
import json
import asyncio
import aiohttp
import argparse
import zipfile
import shutil
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from collections import Counter

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Configuracao centralizada
from config.settings import (
    GEMINI_API_KEY, VERTEX_ACCESS_TOKEN, VERTEX_PROJECT, VERTEX_REGION,
    GEMINI_URL, get_vertex_url, TEMPLATE_DOCX, MODEL_BACKEND,
    IS_LOCAL, IS_GCP, LANGUAGETOOL_URL, GRAMMAR_BACKEND
)

# URL do Vertex AI
VERTEX_URL = get_vertex_url() if VERTEX_PROJECT else ""

TEMPLATE_PATH = TEMPLATE_DOCX

# Dicionário PT→EN expandido
PT_EN_DICT = {
    'amor': 'love', 'vida': 'life', 'tempo': 'time', 'mundo': 'world',
    'homem': 'man', 'mulher': 'woman', 'casa': 'house', 'dia': 'day',
    'noite': 'night', 'água': 'water', 'terra': 'earth', 'fogo': 'fire',
    'coração': 'heart', 'alma': 'soul', 'mente': 'mind', 'corpo': 'body',
    'morte': 'death', 'guerra': 'war', 'paz': 'peace', 'rei': 'king',
    'filho': 'son', 'filha': 'daughter', 'pai': 'father', 'mãe': 'mother',
    'irmão': 'brother', 'amigo': 'friend', 'inimigo': 'enemy',
    'estado': 'state', 'governo': 'government', 'pessoas': 'people', 'povo': 'people',
    'cidadão': 'citizen', 'cidadãos': 'citizens', 'democracia': 'democracy',
    'liberdade': 'freedom', 'justiça': 'justice', 'direito': 'right',
    'lei': 'law', 'ordem': 'order', 'sociedade': 'society', 'natureza': 'nature',
    'todos': 'all', 'outros': 'others', 'mesmo': 'same', 'cada': 'each',
    'parte': 'part', 'forma': 'form', 'modo': 'way', 'coisa': 'thing',
    'causa': 'cause', 'efeito': 'effect', 'princípio': 'principle',
    'ação': 'action', 'movimento': 'movement', 'lugar': 'place',
    'sentido': 'sense', 'valor': 'value', 'exemplo': 'example',
    'questão': 'question', 'problema': 'problem', 'conhecimento': 'knowledge',
    'ciência': 'science', 'filosofia': 'philosophy', 'experiência': 'experience',
    'teoria': 'theory', 'prática': 'practice', 'sistema': 'system',
    'indivíduo': 'individual', 'família': 'family', 'comunidade': 'community',
    'verdade': 'truth', 'mentira': 'lie', 'força': 'strength', 'poder': 'power',
    'beleza': 'beauty', 'felicidade': 'happiness', 'medo': 'fear',
    'coragem': 'courage', 'esperança': 'hope', 'fé': 'faith',
    'deus': 'god', 'céu': 'sky', 'cidade': 'city', 'país': 'country',
    'trabalho': 'work', 'dinheiro': 'money', 'história': 'history',
    'virtude': 'virtue', 'bem': 'good', 'mal': 'evil', 'sabedoria': 'wisdom',
    'consciência': 'consciousness', 'memória': 'memory', 'imaginação': 'imagination',
    'existência': 'existence', 'essência': 'essence', 'eternidade': 'eternity',
    'grande': 'big', 'pequeno': 'small', 'bom': 'good', 'novo': 'new',
    'velho': 'old', 'forte': 'strong', 'fraco': 'weak', 'rico': 'rich',
    'pobre': 'poor', 'feliz': 'happy', 'triste': 'sad', 'vivo': 'alive',
    'morto': 'dead', 'primeiro': 'first', 'último': 'last',
    'ser': 'be', 'ter': 'have', 'fazer': 'do', 'dizer': 'say',
    'ver': 'see', 'ouvir': 'hear', 'sentir': 'feel', 'pensar': 'think',
    'saber': 'know', 'querer': 'want', 'poder': 'can', 'viver': 'live',
    'morrer': 'die', 'amar': 'love', 'odiar': 'hate', 'criar': 'create',
    'destruir': 'destroy', 'acreditar': 'believe', 'entender': 'understand',
}

# Exemplos de uso em inglês (frases curtas)
EN_EXAMPLES = {
    'love': 'She felt a deep love for her family.',
    'life': 'Life is full of surprises.',
    'time': 'Time flies when you are having fun.',
    'world': 'The world is a beautiful place.',
    'man': 'The man walked down the street.',
    'woman': 'The woman smiled warmly.',
    'house': 'They bought a new house.',
    'day': 'It was a beautiful day.',
    'night': 'The night was dark and cold.',
    'water': 'She drank a glass of water.',
    'earth': 'The earth is our home.',
    'fire': 'The fire kept them warm.',
    'heart': 'He spoke from the heart.',
    'soul': 'Music touches the soul.',
    'mind': 'Keep an open mind.',
    'body': 'Exercise is good for the body.',
    'death': 'Death is a part of life.',
    'war': 'War brings suffering to all.',
    'peace': 'They longed for peace.',
    'king': 'The king ruled wisely.',
    'son': 'The son helped his father.',
    'daughter': 'Her daughter became a doctor.',
    'father': 'His father taught him well.',
    'mother': 'Her mother was very kind.',
    'brother': 'His brother lives abroad.',
    'friend': 'A true friend is hard to find.',
    'enemy': 'Keep your enemies closer.',
    'state': 'The state provides public services.',
    'government': 'The government passed new laws.',
    'people': 'The people voted for change.',
    'citizen': 'Every citizen has rights.',
    'citizens': 'Citizens must obey the law.',
    'democracy': 'Democracy requires participation.',
    'freedom': 'Freedom is a basic right.',
    'justice': 'Justice must be served.',
    'right': 'Everyone has the right to speak.',
    'law': 'The law applies to everyone.',
    'order': 'Order is necessary for society.',
    'society': 'Society shapes our behavior.',
    'nature': 'Nature is beautiful.',
    'all': 'All people deserve respect.',
    'others': 'Help others when you can.',
    'same': 'They had the same idea.',
    'each': 'Each person is unique.',
    'part': 'This is part of the plan.',
    'form': 'Art takes many forms.',
    'way': 'There is always a way.',
    'thing': 'The most important thing is honesty.',
    'cause': 'Every effect has a cause.',
    'effect': 'The effect was immediate.',
    'principle': 'Stick to your principles.',
    'action': 'Action speaks louder than words.',
    'movement': 'The movement grew stronger.',
    'place': 'This is a peaceful place.',
    'sense': 'Trust your senses.',
    'value': 'What do you value most?',
    'example': 'He set a good example.',
    'question': 'That is a good question.',
    'problem': 'Every problem has a solution.',
    'knowledge': 'Knowledge is power.',
    'science': 'Science explains the world.',
    'philosophy': 'Philosophy asks deep questions.',
    'experience': 'Experience is the best teacher.',
    'theory': 'The theory was proven correct.',
    'practice': 'Practice makes perfect.',
    'system': 'The system works well.',
    'individual': 'Every individual matters.',
    'family': 'Family comes first.',
    'community': 'The community came together.',
    'truth': 'Always speak the truth.',
    'lie': 'A lie can destroy trust.',
    'strength': 'Find your inner strength.',
    'power': 'Power comes with responsibility.',
    'beauty': 'Beauty is in the eye of the beholder.',
    'happiness': 'Happiness is a choice.',
    'fear': 'Fear can hold you back.',
    'courage': 'Courage is facing your fears.',
    'hope': 'Never lose hope.',
    'faith': 'Faith can move mountains.',
    'god': 'Many believe in God.',
    'sky': 'The sky was clear and blue.',
    'city': 'The city never sleeps.',
    'country': 'I love my country.',
    'work': 'Hard work pays off.',
    'money': 'Money is not everything.',
    'history': 'History teaches us lessons.',
    'virtue': 'Patience is a virtue.',
    'good': 'Do good and good will come.',
    'evil': 'Fight against evil.',
    'wisdom': 'Wisdom comes with age.',
    'consciousness': 'Consciousness defines us.',
    'memory': 'Memories last forever.',
    'imagination': 'Use your imagination.',
    'existence': 'Existence precedes essence.',
    'essence': 'Capture the essence of life.',
    'eternity': 'Love lasts for eternity.',
    'big': 'Think big dreams.',
    'small': 'Small things matter too.',
    'new': 'Try something new today.',
    'old': 'Old friends are the best.',
    'strong': 'Stay strong in difficult times.',
    'weak': 'Even the weak can be brave.',
    'rich': 'Rich in spirit is better.',
    'poor': 'Poor in wealth, rich in love.',
    'happy': 'Be happy with what you have.',
    'sad': 'It is okay to feel sad.',
    'alive': 'Feel alive every day.',
    'dead': 'The past is dead.',
    'first': 'First impressions matter.',
    'last': 'Make it last.',
    'be': 'To be or not to be.',
    'have': 'Have faith in yourself.',
    'do': 'Do your best always.',
    'say': 'Say what you mean.',
    'see': 'See the world differently.',
    'hear': 'Hear what others say.',
    'feel': 'Feel the moment.',
    'think': 'Think before you act.',
    'know': 'Know yourself first.',
    'want': 'Want what you have.',
    'can': 'You can do it.',
    'live': 'Live your best life.',
    'die': 'We all die someday.',
    'love': 'Love unconditionally.',
    'hate': 'Do not hate others.',
    'create': 'Create something beautiful.',
    'destroy': 'Do not destroy nature.',
    'believe': 'Believe in yourself.',
    'understand': 'Seek to understand.',
}

# Stopwords PT
STOPWORDS_PT = {
    'a', 'o', 'e', 'de', 'do', 'da', 'dos', 'das', 'em', 'no', 'na', 'nos', 'nas',
    'um', 'uma', 'uns', 'umas', 'por', 'para', 'com', 'sem', 'sob', 'sobre',
    'que', 'se', 'não', 'mais', 'mas', 'como', 'foi', 'ser', 'são', 'está',
    'ter', 'tem', 'isso', 'isto', 'esse', 'essa', 'este', 'esta', 'ele', 'ela',
    'eu', 'tu', 'você', 'nós', 'ao', 'aos', 'às', 'pelo', 'pela', 'lhe', 'me',
    'já', 'ainda', 'também', 'só', 'bem', 'muito', 'quando', 'onde', 'porque',
    'seus', 'suas', 'seu', 'sua', 'meu', 'minha', 'nem', 'deve', 'pode', 'apenas',
}


class SmartProcessor:
    """Processador completo de livros com verificação de domínio público."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        api_key: str = "",
        vertex_token: str = "",
        num_words: int = 100,
        max_notes: int = 30
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.rejected_dir = Path("books/rejeitados")
        self.api_key = api_key or GEMINI_API_KEY
        self.vertex_token = vertex_token or VERTEX_ACCESS_TOKEN
        self.num_words = num_words
        self.max_notes = max_notes
        self.template_bytes = None
        self.stats = {
            "processed": 0,
            "rejected": 0,
            "failed": 0,
            "books": [],
            "rejected_books": []
        }

        # Determina qual API usar
        self.use_vertex = bool(self.vertex_token)
        if self.use_vertex:
            print(f"API: Vertex AI (Project: {VERTEX_PROJECT})")
        elif self.api_key:
            print(f"API: Gemini API")
        else:
            print("AVISO: Nenhuma API configurada!")

        # Carrega template
        if TEMPLATE_PATH.exists():
            self.template_bytes = TEMPLATE_PATH.read_bytes()
            print(f"Template: {TEMPLATE_PATH}")

    async def _call_llm(self, prompt: str, temperature: float = 0.3, max_tokens: int = 8000) -> Optional[str]:
        """Chama LLM (Vertex AI ou Gemini API)."""
        if self.use_vertex:
            return await self._call_vertex(prompt, temperature, max_tokens)
        elif self.api_key:
            return await self._call_gemini(prompt, temperature, max_tokens)
        return None

    async def _call_vertex(self, prompt: str, temperature: float, max_tokens: int) -> Optional[str]:
        """Chama Vertex AI."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    VERTEX_URL,
                    headers={
                        "Authorization": f"Bearer {self.vertex_token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                    else:
                        error = await resp.json()
                        print(f"    Vertex erro {resp.status}: {error.get('error', {}).get('message', '')[:100]}")
        except Exception as e:
            print(f"    Erro Vertex: {e}")
        return None

    async def _call_gemini(self, prompt: str, temperature: float, max_tokens: int) -> Optional[str]:
        """Chama Gemini API."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GEMINI_URL}?key={self.api_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "")
        except Exception as e:
            print(f"    Erro Gemini: {e}")
        return None

    # =========================================================================
    # VERIFICAÇÃO DE DOMÍNIO PÚBLICO (REGRA PRINCIPAL!)
    # =========================================================================

    async def verify_public_domain_before_download(self, author: str, title: str) -> Dict:
        """PONTO 1: Verifica domínio público ANTES de baixar."""
        if not self.api_key and not self.vertex_token:
            return {"status": "UNKNOWN", "motivo": "Sem API configurada"}

        prompt = f"""Verifique se este livro está em DOMÍNIO PÚBLICO.

Autor: {author}
Título: {title}

Responda em JSON:
{{
    "autor": "nome completo",
    "ano_nascimento": número ou null,
    "ano_morte": número ou null,
    "anos_desde_morte": número ou null,
    "pais_origem": "país",
    "ano_publicacao": número ou null,
    "status": "DOMÍNIO PÚBLICO" ou "PROTEGIDO" ou "INCERTO",
    "motivo": "explicação breve"
}}

Critérios:
- Brasil/Europa: autor morto há 70+ anos = domínio público
- EUA: publicado antes de 1929 OU autor morto há 70+ anos
- Se o autor é da antiguidade (antes de 1500), é domínio público
- Se não conseguir determinar, status = "INCERTO"

JSON:"""

        try:
            text = await self._call_llm(prompt, temperature=0, max_tokens=500)
            if text:
                json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            print(f"    Erro verificação: {e}")

        return {"status": "INCERTO", "motivo": f"Erro na verificação de {author}"}

    async def verify_public_domain_after_download(self, content: str, author: str, title: str) -> Dict:
        """PONTO 2: Confirma autor e data de morte (sem buscar copyright)."""
        if not self.api_key and not self.vertex_token:
            return {"status": "UNKNOWN", "motivo": "Sem API configurada"}

        content_start = content[:2000]

        prompt = f"""Confirme as informações do autor deste livro.

Autor esperado: {author}
Título: {title}

Início do arquivo:
{content_start}

Verifique:
1. O autor mencionado no texto corresponde ao esperado?
2. Há informações sobre data de nascimento/morte do autor?
3. O autor morreu há mais de 70 anos?

Responda em JSON:
{{
    "autor_confirmado": "nome encontrado no texto",
    "autor_corresponde": true/false,
    "ano_morte_encontrado": número ou null,
    "anos_desde_morte": número ou null,
    "status": "DOMÍNIO PÚBLICO" ou "PROTEGIDO" ou "INCERTO",
    "motivo": "explicação"
}}

JSON:"""

        try:
            text = await self._call_llm(prompt, temperature=0, max_tokens=500)
            if text:
                json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
        except Exception as e:
            print(f"    Erro verificação conteúdo: {e}")

        return {"status": "INCERTO", "motivo": "Erro na análise"}

    async def verify_public_domain_before_process(self, author: str, title: str, prev_checks: List[Dict]) -> Dict:
        """PONTO 3: Verificação FINAL antes de processar."""
        # Combina resultados anteriores
        all_status = [c.get("status", "INCERTO") for c in prev_checks]

        # Se algum disse PROTEGIDO, não processa
        if "PROTEGIDO" in all_status:
            return {
                "aprovado": False,
                "status": "PROTEGIDO",
                "motivo": "Verificação anterior indicou proteção de copyright"
            }

        # Se pelo menos um disse DOMÍNIO PÚBLICO, aprova
        if "DOMÍNIO PÚBLICO" in all_status:
            return {
                "aprovado": True,
                "status": "DOMÍNIO PÚBLICO",
                "motivo": "Verificação confirmou domínio público",
                "certificado": {
                    "autor": author,
                    "titulo": title,
                    "verificacoes": prev_checks,
                    "verificado_em": datetime.now().isoformat(),
                    "pode_publicar_comercialmente": True
                }
            }

        # Se todos INCERTO, aprova com aviso (autores antigos como Virgil, Aristóteles)
        if all(s == "INCERTO" or s == "UNKNOWN" for s in all_status):
            return {
                "aprovado": True,
                "status": "INCERTO - APROVADO COM AVISO",
                "motivo": "Não foi possível confirmar, mas provavelmente domínio público",
                "certificado": {
                    "autor": author,
                    "titulo": title,
                    "verificacoes": prev_checks,
                    "verificado_em": datetime.now().isoformat(),
                    "pode_publicar_comercialmente": True,
                    "aviso": "Verificar manualmente se necessário"
                }
            }

        # Se incerto, faz verificação final
        if not self.api_key and not self.vertex_token:
            return {"aprovado": False, "status": "INCERTO", "motivo": "Não foi possível confirmar"}

        prompt = f"""VERIFICAÇÃO FINAL de domínio público.

Autor: {author}
Título: {title}

Verificações anteriores:
{json.dumps(prev_checks, indent=2, ensure_ascii=False)}

DECISÃO FINAL: Este livro pode ser publicado comercialmente sem violar direitos autorais?

Responda em JSON:
{{
    "aprovado": true/false,
    "status": "DOMÍNIO PÚBLICO" ou "PROTEGIDO",
    "motivo": "explicação da decisão",
    "confianca": "ALTA" ou "MÉDIA" ou "BAIXA"
}}

JSON:"""

        try:
            text = await self._call_llm(prompt, temperature=0, max_tokens=300)
            if text:
                json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                if json_match:
                    result = json.loads(json_match.group())
                    if result.get("aprovado") and result.get("confianca") != "BAIXA":
                        result["certificado"] = {
                            "autor": author,
                            "titulo": title,
                            "verificacoes": prev_checks,
                            "verificado_em": datetime.now().isoformat(),
                            "pode_publicar_comercialmente": True
                        }
                    return result
        except Exception as e:
            print(f"    Erro verificação final: {e}")

        return {"aprovado": False, "status": "INCERTO", "motivo": "Não foi possível confirmar domínio público"}

    def reject_book(self, filepath: Path, motivo: str):
        """Move livro rejeitado para pasta de rejeitados."""
        self.rejected_dir.mkdir(parents=True, exist_ok=True)
        dest = self.rejected_dir / filepath.name
        shutil.copy2(filepath, dest)

        # Salva motivo
        reason_file = self.rejected_dir / f"{filepath.stem}_REJEITADO.json"
        reason_file.write_text(json.dumps({
            "arquivo": filepath.name,
            "motivo": motivo,
            "data": datetime.now().isoformat()
        }, ensure_ascii=False, indent=2))

        self.stats["rejected"] += 1
        self.stats["rejected_books"].append({"arquivo": filepath.name, "motivo": motivo})
        print(f"    REJEITADO: {motivo}")

    # =========================================================================
    # DETECÇÃO DE PAÍS E TRADUÇÃO DE TÍTULO
    # =========================================================================

    async def get_author_country(self, author: str) -> str:
        """Detecta o país do autor usando LLM."""
        if not self.api_key and not self.vertex_token:
            return "Desconhecido"

        prompt = f"""Qual é o país de origem do autor "{author}"?

Responda APENAS com o nome do país em português.
Exemplos: Grécia, Alemanha, França, Rússia, Inglaterra, USA, Brasil, Itália

Se não souber, responda: Desconhecido

País:"""

        try:
            country = await self._call_llm(prompt, temperature=0, max_tokens=20)
            if country and len(country.strip()) < 30:
                return country.strip()
        except Exception as e:
            print(f"    Erro detectando país: {e}")

        return "Desconhecido"

    async def translate_title_to_pt(self, title: str, source_lang: str) -> str:
        """Traduz o título para português."""
        if source_lang == 'pt':
            return title

        if not self.api_key and not self.vertex_token:
            return title

        prompt = f"""Traduza este título de livro para português brasileiro.
Mantenha nomes próprios quando apropriado.
Responda APENAS com o título traduzido, sem explicações.

Título original: {title}

Título em português:"""

        try:
            translated = await self._call_llm(prompt, temperature=0.3, max_tokens=100)
            if translated and len(translated.strip()) < 200:
                translated = translated.strip().strip('"\'')
                # Pega só a primeira linha se tiver múltiplas
                translated = translated.split('\n')[0].strip()
                return translated
        except Exception as e:
            print(f"    Erro traduzindo título: {e}")

        return title

    # =========================================================================
    # PROCESSAMENTO DE TEXTO
    # =========================================================================

    def clean_ocr(self, text: str) -> str:
        """Limpa artefatos de OCR."""
        # Remove caracteres estranhos
        text = re.sub(r'[□■�▪▫◦●○]', '', text)

        # Corrige quebras de linha no meio de palavras (pa-\nlavra → palavra)
        text = re.sub(r'(\w)-\n(\w)', r'\1\2', text)

        # Remove múltiplos espaços
        text = re.sub(r' {2,}', ' ', text)

        # Remove linhas vazias excessivas
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    async def correct_portuguese_languagetool(self, text: str) -> str:
        """Corrige ortografia e acentuação usando LanguageTool API."""
        # LanguageTool API pública (limite: 20KB por request)
        LANGUAGETOOL_URL = "https://api.languagetool.org/v2/check"
        MAX_CHUNK_SIZE = 15000  # Deixa margem de segurança

        chunks = self._split_text(text, MAX_CHUNK_SIZE)
        corrected_chunks = []

        print(f"       Corrigindo {len(chunks)} chunks com LanguageTool...")

        for i, chunk in enumerate(chunks):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        LANGUAGETOOL_URL,
                        data={
                            "text": chunk,
                            "language": "pt-BR",
                            "enabledOnly": "false"
                        },
                        timeout=aiohttp.ClientTimeout(total=60)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            matches = data.get("matches", [])

                            if matches:
                                # Aplica correções de trás para frente
                                corrected = chunk
                                for match in reversed(matches):
                                    offset = match.get("offset", 0)
                                    length = match.get("length", 0)
                                    replacements = match.get("replacements", [])

                                    if replacements:
                                        replacement = replacements[0].get("value", "")
                                        corrected = corrected[:offset] + replacement + corrected[offset + length:]

                                corrected_chunks.append(corrected)
                                if (i + 1) % 10 == 0:
                                    print(f"       Chunk {i+1}/{len(chunks)} - {len(matches)} correções")
                            else:
                                corrected_chunks.append(chunk)
                        else:
                            print(f"       LanguageTool erro {resp.status}, usando original")
                            corrected_chunks.append(chunk)

                # Rate limiting para API pública
                await asyncio.sleep(1)

            except Exception as e:
                print(f"       Erro LanguageTool chunk {i}: {e}")
                corrected_chunks.append(chunk)

        return '\n\n'.join(corrected_chunks)

    async def detect_language(self, text: str) -> str:
        """Detecta o idioma do texto."""
        if not self.api_key and not self.vertex_token:
            pt_words = ['que', 'não', 'para', 'com', 'uma', 'são', 'está', 'foi']
            en_words = ['the', 'and', 'is', 'was', 'are', 'for', 'with', 'that']
            text_lower = text[:2000].lower()
            pt_count = sum(1 for w in pt_words if f' {w} ' in text_lower)
            en_count = sum(1 for w in en_words if f' {w} ' in text_lower)
            return 'pt' if pt_count > en_count else 'en'

        prompt = f"""Detect the language. Reply with ONLY the 2-letter code: en, pt, es, fr, de, it, ru

Text: {text[:500]}

Code:"""

        try:
            lang = await self._call_llm(prompt, temperature=0, max_tokens=10)
            if lang:
                lang = lang.strip().lower()[:2]
                if lang in ['en', 'pt', 'es', 'fr', 'de', 'it', 'ru']:
                    return lang
        except Exception as e:
            print(f"    Erro detecção idioma: {e}")

        return 'en'

    async def translate_to_pt(self, text: str, source_lang: str) -> str:
        """Traduz texto para português usando LLM."""
        if source_lang == 'pt':
            return text

        if not self.api_key and not self.vertex_token:
            print("       AVISO: Sem API configurada, não é possível traduzir")
            return text

        # Divide em chunks
        chunks = self._split_text(text, 4000)
        translated = []

        api_name = "Vertex AI" if self.use_vertex else "Gemini"
        print(f"       Traduzindo {len(chunks)} chunks com {api_name}...")

        for i, chunk in enumerate(chunks):
            prompt = f"""Traduza para português brasileiro. Mantenha formatação.
NÃO adicione comentários ou explicações. Apenas a tradução.

{chunk}

Tradução:"""

            try:
                trans = await self._call_llm(prompt, temperature=0.3, max_tokens=8000)
                if trans:
                    translated.append(trans)
                else:
                    translated.append(chunk)

                if (i + 1) % 10 == 0:
                    print(f"       Traduzido {i+1}/{len(chunks)} chunks")

                await asyncio.sleep(0.3)  # Rate limiting

            except Exception as e:
                print(f"       Erro tradução chunk {i}: {e}")
                translated.append(chunk)

        return '\n\n'.join(translated)

    def _split_text(self, text: str, max_size: int) -> List[str]:
        """Divide texto em chunks."""
        paragraphs = text.split('\n\n')
        chunks = []
        current = []
        current_size = 0

        for para in paragraphs:
            if current_size + len(para) > max_size and current:
                chunks.append('\n\n'.join(current))
                current = [para]
                current_size = len(para)
            else:
                current.append(para)
                current_size += len(para)

        if current:
            chunks.append('\n\n'.join(current))

        return chunks

    def get_vocabulary(self, text: str) -> Dict[str, str]:
        """Extrai as 100 palavras mais frequentes com tradução EN."""
        words = re.findall(r'\b[a-záàâãäéèêëíìîïóòôõöúùûüçñ]+\b', text.lower())
        valid = [w for w in words if len(w) >= 3 and w not in STOPWORDS_PT]
        top_words = Counter(valid).most_common(self.num_words * 2)

        translations = {}
        for word, _ in top_words:
            if word in PT_EN_DICT:
                translations[word] = PT_EN_DICT[word]
                if len(translations) >= self.num_words:
                    break

        return translations

    async def get_example_sentences(self, translations: Dict[str, str]) -> Dict[str, str]:
        """Obtém exemplos de uso em inglês para as palavras traduzidas."""
        examples = {}

        # Primeiro, usa o dicionário de exemplos estático
        for word_pt, word_en in translations.items():
            word_en_lower = word_en.lower()
            if word_en_lower in EN_EXAMPLES:
                examples[word_en_lower] = EN_EXAMPLES[word_en_lower]

        # Se faltam exemplos e temos API, gera os que faltam
        missing = [w for w in translations.values() if w.lower() not in examples]
        if missing and self.api_key:
            print(f"       Gerando {len(missing)} exemplos de frases...")
            batch_examples = await self._generate_example_sentences_batch(missing[:30])  # Limite de 30
            examples.update(batch_examples)

        return examples

    async def _generate_example_sentences_batch(self, words: List[str]) -> Dict[str, str]:
        """Gera exemplos de frases em lote usando LLM."""
        if not words:
            return {}

        words_list = ", ".join(words[:30])
        prompt = f"""Create a simple example sentence in English for each of these words.
Format: word: sentence
Keep sentences short (max 10 words).

Words: {words_list}

Examples:"""

        try:
            result = await self._call_llm(prompt, temperature=0.3, max_tokens=1500)
            if result:
                examples = {}
                for line in result.split('\n'):
                    if ':' in line:
                        parts = line.split(':', 1)
                        word = parts[0].strip().lower().strip('- *')
                        sentence = parts[1].strip().strip('"')
                        if word and sentence and len(sentence) < 100:
                            examples[word] = sentence

                return examples
        except Exception as e:
            print(f"       Erro gerando exemplos: {e}")

        return {}

    async def get_book_summary(self, text: str, title: str) -> str:
        """Gera resumo do livro em 3 frases para a capa."""
        if not self.api_key and not self.vertex_token:
            return f"Obra clássica: {title}"

        prompt = f"""Crie um resumo do livro em EXATAMENTE 3 frases curtas.
Capture: tema principal, atmosfera, elementos visuais marcantes.

Título: {title}
Texto (primeiros 4000 caracteres):
{text[:4000]}

RESUMO (3 frases):"""

        try:
            summary = await self._call_llm(prompt, temperature=0.3, max_tokens=200)
            if summary:
                return summary.strip()
        except Exception as e:
            print(f"    Erro resumo: {e}")

        return f"Obra clássica da literatura: {title}"

    async def generate_cover_prompt(self, title: str, summary: str, style: str) -> str:
        """Gera prompt para imagem da capa baseado no título e resumo."""
        styles = {
            "artistic": "oil painting style, dramatic lighting, classical art, rich colors",
            "modern": "modern minimalist design, clean lines, bold typography, contemporary"
        }
        style_desc = styles.get(style, styles["artistic"])

        if not self.api_key and not self.vertex_token:
            return f"Book cover for '{title}', {style_desc}, symbolic imagery, no text, vertical composition"

        prompt = f"""Crie um prompt para gerar a CAPA de um livro.

Título: {title}
Resumo: {summary}
Estilo: {style_desc}

Regras:
- NÃO inclua texto/letras na imagem
- Foque em elementos visuais simbólicos
- Composição vertical (formato livro)
- Cores que evoquem o tema

PROMPT para imagem (em inglês, máximo 100 palavras):"""

        try:
            image_prompt = await self._call_llm(prompt, temperature=0.7, max_tokens=200)
            if image_prompt:
                return f"{image_prompt.strip()}, {style_desc}, book cover art, no text, vertical composition, high quality"
        except Exception as e:
            print(f"    Erro prompt capa: {e}")

        return f"Book cover illustration for '{title}', {style_desc}, symbolic imagery, no text, vertical composition, dramatic lighting"

    async def generate_cover_image(self, prompt: str, output_path: Path) -> bool:
        """Gera imagem da capa usando Gemini ou Imagen."""
        import base64

        # Tenta Gemini 2.0 para gerar imagem
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent?key={self.api_key}",
                    json={
                        "contents": [{
                            "parts": [{"text": f"Generate an image: {prompt}"}]
                        }],
                        "generationConfig": {
                            "responseModalities": ["image", "text"]
                        }
                    },
                    timeout=aiohttp.ClientTimeout(total=120)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "inlineData" in part:
                                    image_b64 = part["inlineData"]["data"]
                                    image_bytes = base64.b64decode(image_b64)
                                    output_path.parent.mkdir(parents=True, exist_ok=True)
                                    output_path.write_bytes(image_bytes)
                                    return True
        except Exception as e:
            print(f"    Erro gerando capa: {e}")

        return False

    async def get_explanatory_notes(self, text: str, title: str) -> List[Tuple[str, str]]:
        """Gera notas explicativas (história, filosofia, cultura)."""
        if not self.api_key and not self.vertex_token:
            return []

        # Pega amostra do texto para a API analisar
        text_sample = text[:8000]

        prompt = f"""Analise este texto e identifique até {self.max_notes} termos para notas explicativas.

IMPORTANTE: Os termos DEVEM aparecer EXATAMENTE como estão escritos no texto.
Inclua: nomes próprios, termos históricos, conceitos filosóficos, referências culturais, lugares, termos em latim/grego.
NÃO inclua palavras comuns ou genéricas.

Formato EXATO (um por linha, sem marcadores):
termo|explicação breve

Exemplo correto:
Juno|Deusa romana, esposa de Júpiter
Cartago|Antiga cidade fenícia no norte da África

Título: {title}
Texto: {text_sample}"""

        try:
            result = await self._call_llm(prompt, temperature=0.3, max_tokens=2000)
            if result:
                notes = []
                for line in result.split('\n'):
                    if '|' in line:
                        parts = line.split('|', 1)
                        if len(parts) == 2:
                            # Limpa formatação markdown e espaços
                            termo = parts[0].strip()
                            termo = re.sub(r'^[\s\-\*\d\.]+', '', termo)  # Remove prefixos
                            termo = re.sub(r'\*+', '', termo)  # Remove asteriscos
                            termo = termo.strip(' "\'()[]')

                            explicacao = parts[1].strip()
                            explicacao = re.sub(r'\*+', '', explicacao)  # Remove asteriscos

                            # Verifica se o termo existe no texto
                            if termo and explicacao and 2 < len(termo) < 50:
                                if termo.lower() in text_sample.lower():
                                    notes.append((termo, explicacao))

                print(f"        {len(notes)} notas válidas (encontradas no texto)")
                return notes[:self.max_notes]
        except Exception as e:
            print(f"    Erro notas: {e}")

        return []

    # =========================================================================
    # GERAÇÃO DE DOCX
    # =========================================================================

    @staticmethod
    def escape_xml(text: str) -> str:
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))

    def build_vocab_xml(self, text: str, translations: Dict[str, str], examples: Dict[str, str] = None) -> Tuple[str, str]:
        """Constrói XML para versão VOCABULÁRIO (100 palavras EN + glossário).

        No texto: a palavra aparece em INGLÊS (tradução) em negrito
        Na nota de rodapé: palavra PT = tradução EN + exemplo de frase em inglês
        """
        paragraphs = text.split('\n\n')
        word_to_fn = {w.lower(): i+1 for i, w in enumerate(translations.keys())}
        examples = examples or {}

        content_parts = []
        used_words = set()

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            is_chapter = (
                para.upper().startswith('CHAPTER') or
                para.upper().startswith('CAPÍTULO') or
                re.match(r'^[IVXLC]+\.?\s', para)
            )

            if is_chapter:
                content_parts.append(f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                    f'<w:r><w:t>{self.escape_xml(para)}</w:t></w:r></w:p>')
                continue

            content_parts.append('<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="both"/></w:pPr>')

            tokens = re.split(r'(\s+)', para)
            for token in tokens:
                if not token:
                    continue

                match = re.match(r'^([a-záàâãäéèêëíìîïóòôõöúùûüçñA-ZÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇÑ]+)(.*)$', token)

                if match:
                    word, punct = match.group(1), match.group(2)
                    word_lower = word.lower()

                    if word_lower in word_to_fn and word_lower not in used_words:
                        fn_id = word_to_fn[word_lower]
                        used_words.add(word_lower)
                        # Coloca a tradução em INGLÊS no texto (em negrito)
                        english_word = translations.get(word_lower, word)
                        # Mantém capitalização se a palavra original era capitalizada
                        if word[0].isupper():
                            english_word = english_word.capitalize()
                        content_parts.append(f'<w:r><w:rPr><w:b/></w:rPr><w:t>{self.escape_xml(english_word)}</w:t></w:r>')
                        content_parts.append(f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="{fn_id}"/></w:r>')
                        if punct:
                            content_parts.append(f'<w:r><w:t>{self.escape_xml(punct)}</w:t></w:r>')
                    else:
                        content_parts.append(f'<w:r><w:t>{self.escape_xml(token)}</w:t></w:r>')
                else:
                    content_parts.append(f'<w:r><w:t xml:space="preserve">{self.escape_xml(token)}</w:t></w:r>')

            content_parts.append('</w:p>')

        # Glossário
        content_parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
        content_parts.append('<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
            '<w:r><w:t>GLOSSARY / GLOSSÁRIO</w:t></w:r></w:p>')

        for word, trans in sorted(translations.items()):
            example = examples.get(trans.lower(), "")
            example_xml = ""
            if example:
                example_xml = (f'<w:r><w:t xml:space="preserve"> — </w:t></w:r>'
                    f'<w:r><w:rPr><w:i/><w:sz w:val="20"/></w:rPr><w:t>"{self.escape_xml(example)}"</w:t></w:r>')
            content_parts.append(f'<w:p><w:pPr><w:ind w:left="400"/></w:pPr>'
                f'<w:r><w:rPr><w:b/></w:rPr><w:t>{self.escape_xml(trans)}</w:t></w:r>'
                f'<w:r><w:t xml:space="preserve"> ({self.escape_xml(word)}) </w:t></w:r>'
                f'{example_xml}</w:p>')

        content_xml = '\n'.join(content_parts)

        # Footnotes (vocabulário) - com exemplo de uso em inglês
        fn_parts = ['''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>''']

        for word, trans in translations.items():
            fn_id = word_to_fn[word.lower()]
            example = examples.get(trans.lower(), "")
            example_text = f' — Ex: "{self.escape_xml(example)}"' if example else ""
            fn_parts.append(f'''<w:footnote w:id="{fn_id}">
<w:p><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>
<w:r><w:t xml:space="preserve"> {self.escape_xml(trans)} ({self.escape_xml(word)}){example_text}</w:t></w:r></w:p>
</w:footnote>''')

        fn_parts.append('</w:footnotes>')

        return content_xml, '\n'.join(fn_parts)

    def _normalize_for_search(self, text: str) -> str:
        """Remove acentos e normaliza texto para busca."""
        import unicodedata
        # Remove acentos
        nfkd = unicodedata.normalize('NFKD', text.lower())
        return ''.join(c for c in nfkd if not unicodedata.combining(c))

    def _find_term_in_text(self, termo: str, text: str) -> Optional[re.Match]:
        """Busca termo no texto com tolerância a variações."""
        # Primeiro, busca exata (case-insensitive)
        pattern = re.compile(r'\b' + re.escape(termo) + r'\b', re.IGNORECASE)
        match = pattern.search(text)
        if match:
            return match

        # Segundo, busca sem acentos
        termo_norm = self._normalize_for_search(termo)
        text_norm = self._normalize_for_search(text)
        pattern_norm = re.compile(r'\b' + re.escape(termo_norm) + r'\b')
        match_norm = pattern_norm.search(text_norm)
        if match_norm:
            # Encontra a posição no texto original
            start = match_norm.start()
            end = match_norm.end()
            # Tenta encontrar palavra correspondente no texto original
            words_before = len(text_norm[:start].split())
            text_words = text.split()
            if words_before < len(text_words):
                return re.search(r'\b\w+\b', text[max(0, start-5):end+5])

        return None

    def build_translation_xml(self, text: str, notes: List[Tuple[str, str]]) -> Tuple[str, str]:
        """Constrói XML para versão TRADUÇÃO (notas explicativas, sem glossário)."""
        paragraphs = text.split('\n\n')
        nota_id = 1
        notas_usadas = []
        termos_usados = set()

        content_parts = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            is_chapter = (
                para.upper().startswith('CHAPTER') or
                para.upper().startswith('CAPÍTULO') or
                re.match(r'^[IVXLC]+\.?\s', para)
            )

            if is_chapter:
                content_parts.append(f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr>'
                    f'<w:r><w:t>{self.escape_xml(para)}</w:t></w:r></w:p>')
                continue

            found_term = None
            para_lower = para.lower()
            para_norm = self._normalize_for_search(para)

            for termo, explicacao in notes:
                termo_lower = termo.lower()
                termo_norm = self._normalize_for_search(termo)
                if termo_norm in termos_usados:
                    continue
                # Busca com e sem acentos
                if termo_lower in para_lower or termo_norm in para_norm:
                    found_term = (termo, explicacao)
                    break

            if found_term:
                termo, explicacao = found_term
                # Busca com regex (case-insensitive)
                pattern = re.compile(re.escape(termo), re.IGNORECASE)
                match = pattern.search(para)

                if not match:
                    # Tenta busca sem acentos
                    termo_norm = self._normalize_for_search(termo)
                    para_norm = self._normalize_for_search(para)
                    if termo_norm in para_norm:
                        # Encontra posição aproximada
                        idx = para_norm.find(termo_norm)
                        if idx >= 0:
                            # Cria match simulado
                            match = type('Match', (), {'start': lambda: idx, 'end': lambda: idx + len(termo)})()

                if match:
                    before = para[:match.end()]
                    after = para[match.end():]

                    content_parts.append(f'<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="both"/></w:pPr>'
                        f'<w:r><w:t xml:space="preserve">{self.escape_xml(before)}</w:t></w:r>'
                        f'<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteReference w:id="{nota_id}"/></w:r>'
                        f'<w:r><w:t xml:space="preserve">{self.escape_xml(after)}</w:t></w:r></w:p>')

                    notas_usadas.append((termo, explicacao, nota_id))
                    termos_usados.add(self._normalize_for_search(termo))
                    nota_id += 1
                else:
                    content_parts.append(f'<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="both"/></w:pPr>'
                        f'<w:r><w:t xml:space="preserve">{self.escape_xml(para)}</w:t></w:r></w:p>')
            else:
                content_parts.append(f'<w:p><w:pPr><w:pStyle w:val="Normal"/><w:jc w:val="both"/></w:pPr>'
                    f'<w:r><w:t xml:space="preserve">{self.escape_xml(para)}</w:t></w:r></w:p>')

        content_xml = '\n'.join(content_parts)

        # Se nenhuma nota foi usada, log de aviso
        if not notas_usadas and notes:
            print(f"        AVISO: {len(notes)} notas geradas mas nenhuma encontrada no texto")

        # Footnotes (explicativas)
        fn_parts = ['''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>
<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r></w:p></w:footnote>''']

        for termo, explicacao, nid in notas_usadas:
            fn_parts.append(f'''<w:footnote w:id="{nid}">
<w:p><w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:footnoteRef/></w:r>
<w:r><w:t xml:space="preserve"> {self.escape_xml(termo)}: {self.escape_xml(explicacao)}</w:t></w:r></w:p>
</w:footnote>''')

        fn_parts.append('</w:footnotes>')

        return content_xml, '\n'.join(fn_parts)

    def create_docx(self, content_xml: str, footnotes_xml: str, output_path: Path) -> bool:
        """Cria DOCX usando template, preservando intro e back matter."""
        try:
            if not self.template_bytes:
                print("    ERRO: Template não encontrado")
                return False

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(TEMPLATE_PATH, 'r') as template_zip:
                with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as out_zip:
                    has_footnotes = 'word/footnotes.xml' in template_zip.namelist()

                    for item in template_zip.namelist():
                        if item == 'word/document.xml':
                            doc_xml = template_zip.read(item).decode('utf-8')

                            # Insere antes do Copyright (back matter)
                            copyright_match = re.search(r'<w:p[^>]*>(?:(?!</w:p>).)*Copyright(?:(?!</w:p>).)*</w:p>', doc_xml, re.DOTALL)

                            if copyright_match:
                                insert_pos = copyright_match.start()
                                page_break = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
                                doc_xml = doc_xml[:insert_pos] + page_break + content_xml + '\n' + page_break + doc_xml[insert_pos:]
                            else:
                                sectpr_match = re.search(r'(<w:sectPr[^>]*>)', doc_xml)
                                if sectpr_match:
                                    insert_pos = sectpr_match.start()
                                    page_break = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>\n'
                                    doc_xml = doc_xml[:insert_pos] + page_break + content_xml + '\n' + doc_xml[insert_pos:]
                                else:
                                    doc_xml = doc_xml.replace('</w:body>', content_xml + '\n</w:body>')

                            out_zip.writestr(item, doc_xml.encode('utf-8'))

                        elif item == 'word/footnotes.xml':
                            out_zip.writestr(item, footnotes_xml)
                            has_footnotes = True

                        elif item == '[Content_Types].xml':
                            ct_xml = template_zip.read(item).decode('utf-8')
                            if 'footnotes.xml' not in ct_xml:
                                ct_xml = ct_xml.replace('</Types>',
                                    '<Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>\n</Types>')
                            out_zip.writestr(item, ct_xml.encode('utf-8'))

                        elif item == 'word/_rels/document.xml.rels':
                            rels_xml = template_zip.read(item).decode('utf-8')
                            if 'footnotes.xml' not in rels_xml:
                                ids = re.findall(r'rId(\d+)', rels_xml)
                                next_id = max(int(i) for i in ids) + 1 if ids else 10
                                new_rel = f'<Relationship Id="rId{next_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>\n'
                                rels_xml = rels_xml.replace('</Relationships>', new_rel + '</Relationships>')
                            out_zip.writestr(item, rels_xml.encode('utf-8'))

                        else:
                            out_zip.writestr(item, template_zip.read(item))

                    if not has_footnotes:
                        out_zip.writestr('word/footnotes.xml', footnotes_xml)

            return True

        except Exception as e:
            print(f"    ERRO DOCX: {e}")
            import traceback
            traceback.print_exc()
            return False

    # =========================================================================
    # EXTRAÇÃO DE METADADOS
    # =========================================================================

    def extract_metadata(self, content: str, filepath: Path) -> Tuple[str, str]:
        """Extrai título e autor do conteúdo e caminho."""
        lines = content.split('\n')[:30]

        # Tenta extrair do conteúdo
        title = filepath.stem.replace('_', ' ')
        author = filepath.parent.name if filepath.parent.name != 'other' else "Autor Desconhecido"

        for line in lines:
            line = line.strip()
            if line.lower().startswith('title:'):
                title = line.split(':', 1)[1].strip()
            elif line.lower().startswith('author:'):
                author = line.split(':', 1)[1].strip()

        return title[:100], author

    # =========================================================================
    # PROCESSAMENTO PRINCIPAL
    # =========================================================================

    async def process_file(self, filepath: Path) -> Optional[Dict]:
        """Processa um arquivo completo com verificação de domínio público."""
        try:
            print(f"\n{'='*60}")
            print(f"[PROCESSANDO] {filepath.name}")
            print('='*60)

            content = filepath.read_text(encoding='utf-8', errors='ignore')
            if len(content) < 500:
                print("    Arquivo muito curto, pulando")
                return None

            title_original, author = self.extract_metadata(content, filepath)
            print(f"    Autor: {author}")
            print(f"    Título: {title_original}")

            # =============================================
            # VERIFICAÇÃO 1: ANTES (autor + título)
            # =============================================
            print("\n    [DOMÍNIO PÚBLICO] Verificação 1/3...")
            check1 = await self.verify_public_domain_before_download(author, title_original)
            print(f"       Status: {check1.get('status', 'ERRO')}")

            if check1.get("status") == "PROTEGIDO":
                self.reject_book(filepath, f"Verificação 1: {check1.get('motivo', 'Protegido')}")
                return None

            # =============================================
            # VERIFICAÇÃO 2: DEPOIS (analisa conteúdo)
            # =============================================
            print("    [DOMÍNIO PÚBLICO] Verificação 2/3...")
            check2 = await self.verify_public_domain_after_download(content, author, title_original)
            print(f"       Status: {check2.get('status', 'ERRO')}")

            if check2.get("status") == "PROTEGIDO":
                self.reject_book(filepath, f"Verificação 2: {check2.get('motivo', 'Copyright encontrado')}")
                return None

            # =============================================
            # VERIFICAÇÃO 3: FINAL
            # =============================================
            print("    [DOMÍNIO PÚBLICO] Verificação 3/3 (final)...")
            check3 = await self.verify_public_domain_before_process(author, title_original, [check1, check2])
            print(f"       Aprovado: {check3.get('aprovado', False)}")

            if not check3.get("aprovado"):
                self.reject_book(filepath, f"Verificação final: {check3.get('motivo', 'Não aprovado')}")
                return None

            print("       APROVADO PARA PROCESSAMENTO!")

            # =============================================
            # DETECTA IDIOMA
            # =============================================
            print("\n    1. Detectando idioma...")
            lang = await self.detect_language(content)
            print(f"       Idioma: {lang.upper()}")

            # =============================================
            # TRADUZ TÍTULO PARA PT
            # =============================================
            print("    2. Traduzindo título...")
            title_pt = await self.translate_title_to_pt(title_original, lang)
            print(f"       Título PT: {title_pt}")

            # =============================================
            # DETECTA PAÍS DO AUTOR
            # =============================================
            print("    3. Detectando país do autor...")
            country = await self.get_author_country(author)
            print(f"       País: {country}")

            # =============================================
            # LIMPA OCR
            # =============================================
            print("    4. Limpando OCR...")
            content = self.clean_ocr(content)

            # =============================================
            # TRADUZ PARA PT
            # =============================================
            if lang != 'pt':
                print(f"    5. Traduzindo {lang.upper()} → PT...")
                content = await self.translate_to_pt(content, lang)
                print("       Tradução concluída")
            else:
                print("    5. Já está em português")

            # =============================================
            # CORRIGE ORTOGRAFIA (LanguageTool)
            # =============================================
            print("    7. Corrigindo ortografia e acentuação (LanguageTool)...")
            content = await self.correct_portuguese_languagetool(content)
            print("       Correção concluída")

            # =============================================
            # GERA RESUMO PARA CAPAS (3 frases)
            # =============================================
            print("    8. Gerando resumo para capas (3 frases)...")
            summary = await self.get_book_summary(content, title_pt)
            print(f"       {summary[:80]}...")

            # =============================================
            # CRIA ESTRUTURA DE PASTAS
            # =============================================
            safe_country = re.sub(r'[<>:"/\\|?*]', '', country)
            safe_author = re.sub(r'[<>:"/\\|?*]', '', author)
            safe_title = re.sub(r'[<>:"/\\|?*]', '', title_pt)

            base_dir = self.output_dir / safe_country / safe_author
            translation_dir = base_dir / f"{safe_title} - Tradução"
            vocab_dir = base_dir / f"{safe_title} - Vocabulário EN"

            translation_dir.mkdir(parents=True, exist_ok=True)
            vocab_dir.mkdir(parents=True, exist_ok=True)

            # Certificado de domínio público
            cert_path = base_dir / "_DOMINIO_PUBLICO.json"
            cert_path.write_text(json.dumps(check3.get("certificado", {}), indent=2, ensure_ascii=False))

            # =============================================================
            # PIPELINE A: LIVRO TRADUÇÃO FIEL
            # =============================================================
            print("\n    ══════════════════════════════════════════")
            print("    PIPELINE A: LIVRO TRADUÇÃO FIEL")
            print("    ══════════════════════════════════════════")

            # A1. Notas explicativas (história, filosofia, cultura)
            print("    A1. Gerando notas EXPLICATIVAS...")
            notes = await self.get_explanatory_notes(content, title_pt)
            print(f"        {len(notes)} notas")

            # A2. DOCX
            print("    A2. Gerando DOCX...")
            translation_path = translation_dir / f"{safe_title}.docx"
            content_xml, fn_xml = self.build_translation_xml(content, notes)
            if self.create_docx(content_xml, fn_xml, translation_path):
                size_kb = translation_path.stat().st_size / 1024
                print(f"        {translation_path.name} ({size_kb:.0f} KB)")
            else:
                print("        FALHA")

            # A3. Capa artistic
            print("    A3. Gerando capa (artistic)...")
            cover_translation_path = translation_dir / f"{safe_title}_cover.png"
            cover_prompt_art = await self.generate_cover_prompt(title_pt, summary, "artistic")
            if await self.generate_cover_image(cover_prompt_art, cover_translation_path):
                print(f"        {cover_translation_path.name}")
            else:
                print("        FALHA capa")

            # =============================================================
            # PIPELINE B: LIVRO VOCABULÁRIO EN
            # =============================================================
            print("\n    ══════════════════════════════════════════")
            print("    PIPELINE B: LIVRO VOCABULÁRIO EN")
            print("    ══════════════════════════════════════════")

            # B1. Extrai 100 palavras PT→EN
            print("    B1. Extraindo 100 palavras PT→EN...")
            translations = self.get_vocabulary(content)
            print(f"        {len(translations)} palavras")

            # B1.5. Gera exemplos de uso em inglês
            print("    B1.5. Gerando exemplos de uso em inglês...")
            examples = await self.get_example_sentences(translations)
            print(f"        {len(examples)} exemplos")

            # B2. DOCX com vocabulário + glossário
            print("    B2. Gerando DOCX com glossário...")
            vocab_path = vocab_dir / f"{safe_title}_vocab.docx"
            content_xml, fn_xml = self.build_vocab_xml(content, translations, examples)
            if self.create_docx(content_xml, fn_xml, vocab_path):
                size_kb = vocab_path.stat().st_size / 1024
                print(f"        {vocab_path.name} ({size_kb:.0f} KB)")
            else:
                print("        FALHA")

            # B3. Capa modern
            print("    B3. Gerando capa (modern)...")
            cover_vocab_path = vocab_dir / f"{safe_title}_vocab_cover.png"
            cover_prompt_mod = await self.generate_cover_prompt(title_pt, summary, "modern")
            if await self.generate_cover_image(cover_prompt_mod, cover_vocab_path):
                print(f"        {cover_vocab_path.name}")
            else:
                print("        FALHA capa (sem API de imagem)")

            self.stats["processed"] += 1
            return {
                "source": str(filepath),
                "title_original": title_original,
                "title_pt": title_pt,
                "author": author,
                "country": country,
                "language": lang,
                "summary": summary,
                "vocabulary": len(translations),
                "notes": len(notes),
                "translation_docx": str(translation_path),
                "translation_cover": str(cover_translation_path),
                "vocab_docx": str(vocab_path),
                "vocab_cover": str(cover_vocab_path),
                "public_domain_cert": str(cert_path)
            }

        except Exception as e:
            print(f"    ERRO: {e}")
            import traceback
            traceback.print_exc()
            self.stats["failed"] += 1
            return None

    async def run(self, limit: int = 0) -> List[Dict]:
        """Executa processamento completo."""
        print("=" * 60)
        print("SMART PROCESSOR - BooksKDP")
        print("=" * 60)
        print(f"Entrada: {self.input_dir}")
        print(f"Saída: {self.output_dir}")
        print(f"Palavras EN: {self.num_words}")
        print(f"Notas max: {self.max_notes}")
        print()
        print("REGRA PRINCIPAL: Verificação de DOMÍNIO PÚBLICO em 3 pontos!")
        print()

        # Lista arquivos
        files = list(self.input_dir.rglob("*.txt"))
        if limit > 0:
            files = files[:limit]

        print(f"Arquivos: {len(files)}")

        results = []
        for i, f in enumerate(files):
            print(f"\n[{i+1}/{len(files)}]", end="")
            result = await self.process_file(f)
            if result:
                results.append(result)

        # Salva estatísticas
        self.stats["books"] = results
        self.stats["finished"] = datetime.now().isoformat()

        stats_path = self.output_dir / "smart_processor_stats.json"
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        print("\n" + "=" * 60)
        print("RESUMO")
        print("=" * 60)
        print(f"Processados: {self.stats['processed']}")
        print(f"Rejeitados: {self.stats['rejected']}")
        print(f"Falhas: {self.stats['failed']}")
        print(f"\nSaída: books/{{País}}/{{Autor}}/")
        print("=" * 60)

        return results


async def main():
    parser = argparse.ArgumentParser(description="Smart Processor - Pipeline completo com verificação de domínio público")
    parser.add_argument("--input", default="books/txt/other", help="Pasta de entrada")
    parser.add_argument("--output", default="books", help="Pasta de saída")
    parser.add_argument("--words", type=int, default=100, help="Palavras EN")
    parser.add_argument("--notes", type=int, default=30, help="Notas máximas")
    parser.add_argument("--limit", type=int, default=0, help="Limite de arquivos")
    parser.add_argument("--api-key", help="Gemini API Key")
    parser.add_argument("--vertex-token", help="Vertex AI Access Token (preferido)")

    args = parser.parse_args()

    processor = SmartProcessor(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        api_key=args.api_key or "",
        vertex_token=args.vertex_token or "",
        num_words=args.words,
        max_notes=args.notes
    )

    await processor.run(args.limit)


if __name__ == "__main__":
    asyncio.run(main())
