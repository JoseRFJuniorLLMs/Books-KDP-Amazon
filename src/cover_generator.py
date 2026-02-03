# -*- coding: utf-8 -*-
"""
COVER_GENERATOR.PY - Gerador de Capas de Livros com IA
=======================================================
Gera capas de livros usando múltiplas APIs de IA:
- OpenAI DALL-E 3
- Google Gemini Imagen
- Outras APIs de geração de imagem

Processo:
1. Lê autor e título do livro
2. Analisa o tema do livro usando IA local (Ollama)
3. Gera prompts otimizados para cada API
4. Cria capas com cada API
5. Salva imagens no mesmo diretório do DOCX
"""

import os
import sys
import time
import logging
import hashlib
import requests
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

# Configurações
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import (
    LOG_DIR, OLLAMA_BASE_URL, OLLAMA_MODEL,
    OPENAI_API_KEY, GEMINI_API_KEY
)

# ============================================================================
# LOGGING
# ============================================================================

LOG_DIR.mkdir(exist_ok=True)
log_file = LOG_DIR / f"cover_generator_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# BOOK ANALYZER
# ============================================================================

class BookAnalyzer:
    """Analisa livro e extrai tema/gênero usando IA local."""

    def __init__(self, ollama_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.ollama_url = ollama_url
        self.model = model
        self._validate_ollama()

    def _validate_ollama(self):
        """Valida conexão com Ollama."""
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if r.status_code == 200:
                logger.info("✅ Ollama conectado")
            else:
                raise ConnectionError()
        except Exception as e:
            logger.error(f"❌ Ollama não disponível em {self.ollama_url}")
            logger.info("Instale: https://ollama.com")
            raise

    def analyze_book(self, author: str, title: str, text_sample: str = "") -> Dict:
        """
        Analisa livro e retorna informações sobre tema, gênero, etc.

        Returns:
            {
                'genre': 'ficção científica',
                'themes': ['tecnologia', 'futuro', 'distopia'],
                'style': 'futurista, sombrio',
                'summary': 'breve resumo do tema'
            }
        """
        logger.info(f"📖 Analisando: {author} - {title}")

        # Cria amostra do texto se disponível
        sample_text = text_sample[:2000] if text_sample else ""

        prompt = f"""Analise este livro e retorne APENAS um JSON válido (sem markdown):

Autor: {author}
Título: {title}
{f'Trecho: {sample_text[:500]}...' if sample_text else ''}

Retorne no formato JSON:
{{
  "genre": "gênero literário (ex: ficção, romance, técnico)",
  "themes": ["tema1", "tema2", "tema3"],
  "style": "estilo visual sugerido para capa (ex: minimalista, épico, sombrio)",
  "mood": "atmosfera (ex: contemplativo, energético, misterioso)",
  "summary": "resumo de 1 linha do tema principal"
}}

JSON:"""

        try:
            r = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 500
                    }
                },
                timeout=60
            )
            r.raise_for_status()

            response_text = r.json().get("response", "").strip()

            # Tenta extrair JSON
            import json

            # Remove markdown se houver
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            analysis = json.loads(response_text)
            logger.info(f"✅ Análise: gênero={analysis.get('genre')}, temas={analysis.get('themes')}")
            return analysis

        except Exception as e:
            logger.warning(f"⚠️ Erro na análise: {e}")
            # Fallback para análise básica
            return {
                'genre': 'literatura',
                'themes': [title.lower()],
                'style': 'clássico',
                'mood': 'contemplativo',
                'summary': f'Obra de {author}'
            }

# ============================================================================
# COVER GENERATORS
# ============================================================================

class CoverGenerator:
    """Classe base para geradores de capa."""

    def __init__(self, api_name: str):
        self.api_name = api_name

    def create_prompt(self, author: str, title: str, analysis: Dict) -> str:
        """Cria prompt otimizado seguindo padrões KDP para geração de capa."""
        genre = analysis.get('genre', 'livro')
        style = analysis.get('style', 'clássico')
        mood = analysis.get('mood', 'contemplativo')
        themes = ', '.join(analysis.get('themes', []))

        prompt = f"""Professional book cover design for Amazon KDP/Kindle Direct Publishing.

BOOK DETAILS:
- Title: "{title}"
- Author: {author}
- Genre: {genre}
- Themes: {themes}
- Mood: {mood}, {style}

TECHNICAL SPECIFICATIONS (KDP Standards):
- Aspect ratio: 1.6:1 (height to width) - CRITICAL for KDP
- Orientation: Portrait/vertical
- Resolution: High-quality, print-ready (300 DPI equivalent)
- Format considerations: Suitable for both ebook thumbnail and print cover
- Color space: RGB for digital, but with CMYK-safe colors

DESIGN REQUIREMENTS:

1. COMPOSITION:
   - Central focal point that captures the book's essence
   - Clear visual hierarchy with strong focal area
   - Safe margins: Keep important imagery 0.125" from edges
   - Rule of thirds composition for balanced layout
   - Leave ample space at top (for title) and bottom (for author name)

2. VISUAL STYLE:
   - Genre-appropriate imagery ({genre} style)
   - Professional, publishable quality
   - Commercial book cover aesthetics
   - Evocative and thematic: {themes}
   - Mood: {mood}

3. COLOR & CONTRAST:
   - High contrast for thumbnail visibility
   - Bold, eye-catching color palette
   - Colors that stand out in search results
   - Readable at small sizes (important for Amazon thumbnails)

4. IMAGE CONTENT:
   - NO text, letters, or words in the image
   - NO typography or font elements
   - Clear, recognizable imagery even at thumbnail size
   - Symbolism related to: {themes}
   - Professional photography/illustration quality

5. MARKETABILITY:
   - Should attract target audience for {genre}
   - Competitive with bestsellers in category
   - Thumbnail-friendly (legible at 200x300 pixels)
   - Print-ready quality for paperback

6. LAYOUT ZONES:
   - Top 20%: Reserved for title placement (keep imagery subtle here)
   - Middle 60%: Main visual focus, strongest imagery
   - Bottom 20%: Reserved for author name (keep clear)

STYLE DIRECTION: {style}, {mood}, professional, bestseller-quality, commercial, print-ready

Create a stunning, professional book cover background that will make this book stand out on Amazon and in bookstores. The cover should be immediately eye-catching and genre-appropriate."""

        return prompt

    def generate(self, author: str, title: str, analysis: Dict, output_path: Path) -> bool:
        """Gera capa e salva em output_path. Implementar em subclasses."""
        raise NotImplementedError()


class DallE3Generator(CoverGenerator):
    """Gerador usando OpenAI DALL-E 3."""

    def __init__(self, api_key: str):
        super().__init__("DALL-E-3")
        self.api_key = api_key

        if not api_key:
            raise ValueError("OPENAI_API_KEY não configurada")

    def generate(self, author: str, title: str, analysis: Dict, output_path: Path) -> bool:
        """Gera capa com DALL-E 3."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=self.api_key)

            prompt = self.create_prompt(author, title, analysis)
            logger.info(f"🎨 Gerando capa com DALL-E 3...")

            response = client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                size="1024x1792",  # Vertical (1.75:1) - mais próximo do KDP 1.6:1
                quality="hd",
                n=1
            )

            image_url = response.data[0].url

            # Download da imagem
            img_response = requests.get(image_url, timeout=60)
            img_response.raise_for_status()

            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(img_response.content)

            logger.info(f"✅ Capa DALL-E 3 salva: {output_path}")
            return True

        except Exception as e:
            logger.error(f"❌ Erro DALL-E 3: {e}")
            return False


class GeminiImagenGenerator(CoverGenerator):
    """Gerador usando Google Gemini Imagen."""

    def __init__(self, api_key: str):
        super().__init__("Gemini-Imagen")
        self.api_key = api_key

        if not api_key:
            raise ValueError("GOOGLE_API_KEY não configurada")

    def generate(self, author: str, title: str, analysis: Dict, output_path: Path) -> bool:
        """Gera capa com Gemini Imagen."""
        try:
            prompt = self.create_prompt(author, title, analysis)
            logger.info(f"🎨 Gerando capa com Gemini Imagen...")

            # Usa a API Imagen do Google AI Studio
            response = requests.post(
                "https://generativelanguage.googleapis.com/v1beta/models/imagen-3.0-generate-001:predict",
                headers={
                    "Content-Type": "application/json",
                    "x-goog-api-key": self.api_key
                },
                json={
                    "instances": [
                        {
                            "prompt": prompt
                        }
                    ],
                    "parameters": {
                        "sampleCount": 1,
                        "aspectRatio": "5:8",  # 1.6:1 - padrão KDP exato
                        "safetySettings": [
                            {
                                "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                                "threshold": "BLOCK_ONLY_HIGH"
                            }
                        ]
                    }
                },
                timeout=120
            )

            if response.status_code != 200:
                logger.error(f"Gemini API erro {response.status_code}: {response.text}")
                return False

            data = response.json()

            # Extrai imagem (base64)
            if "predictions" in data and len(data["predictions"]) > 0:
                import base64
                image_b64 = data["predictions"][0]["bytesBase64Encoded"]
                image_data = base64.b64decode(image_b64)

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(image_data)

                logger.info(f"✅ Capa Gemini salva: {output_path}")
                return True
            else:
                logger.error("❌ Gemini não retornou imagem")
                return False

        except Exception as e:
            logger.error(f"❌ Erro Gemini Imagen: {e}")
            return False


class GrokGenerator(CoverGenerator):
    """Gerador usando xAI Grok."""

    def __init__(self, api_key: str):
        super().__init__("Grok-xAI")
        self.api_key = api_key

        if not api_key:
            raise ValueError("XAI_API_KEY não configurada")

    def generate(self, author: str, title: str, analysis: Dict, output_path: Path) -> bool:
        """Gera capa com Grok."""
        try:
            prompt = self.create_prompt(author, title, analysis)
            logger.info(f"🎨 Gerando capa com Grok (xAI)...")

            # xAI Grok usa API compatível com OpenAI
            response = requests.post(
                "https://api.x.ai/v1/images/generations",
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                json={
                    "model": "grok-vision-beta",
                    "prompt": prompt,
                    "n": 1,
                    "size": "1024x1792",  # Vertical (1.75:1) - mais próximo do KDP 1.6:1
                    "quality": "hd",  # Alta qualidade para impressão
                    "response_format": "url"
                },
                timeout=120
            )

            if response.status_code != 200:
                logger.error(f"Grok API erro {response.status_code}: {response.text}")
                return False

            data = response.json()

            if "data" in data and len(data["data"]) > 0:
                image_url = data["data"][0]["url"]

                # Download da imagem
                img_response = requests.get(image_url, timeout=60)
                img_response.raise_for_status()

                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(img_response.content)

                logger.info(f"✅ Capa Grok salva: {output_path}")
                return True
            else:
                logger.error("❌ Grok não retornou imagem")
                return False

        except Exception as e:
            logger.error(f"❌ Erro Grok: {e}")
            return False

# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class BookCoverOrchestrator:
    """Orquestra geração de capas de múltiplas fontes."""

    def __init__(self):
        self.analyzer = BookAnalyzer()
        self.generators = []

        # Inicializa geradores disponíveis
        if OPENAI_API_KEY:
            try:
                self.generators.append(DallE3Generator(OPENAI_API_KEY))
                logger.info("✅ DALL-E 3 habilitado")
            except Exception as e:
                logger.warning(f"⚠️ DALL-E 3 desabilitado: {e}")

        if GEMINI_API_KEY:
            try:
                self.generators.append(GeminiImagenGenerator(GEMINI_API_KEY))
                logger.info("✅ Gemini Imagen habilitado")
            except Exception as e:
                logger.warning(f"⚠️ Gemini Imagen desabilitado: {e}")

        # xAI Grok (requer chave separada)
        xai_key = os.getenv("XAI_API_KEY", "")
        if xai_key:
            try:
                self.generators.append(GrokGenerator(xai_key))
                logger.info("✅ Grok (xAI) habilitado")
            except Exception as e:
                logger.warning(f"⚠️ Grok desabilitado: {e}")

        if not self.generators:
            logger.warning("⚠️ Nenhum gerador de imagem disponível!")
            logger.info("Configure pelo menos uma API key:")
            logger.info("  - OPENAI_API_KEY para DALL-E 3")
            logger.info("  - GOOGLE_API_KEY para Gemini Imagen")
            logger.info("  - XAI_API_KEY para Grok (xAI)")

    def generate_covers(self, book_txt_path: Path, docx_path: Path = None) -> Dict[str, Path]:
        """
        Gera capas para um livro.

        Args:
            book_txt_path: Caminho do TXT traduzido
            docx_path: Caminho do DOCX (opcional, usado para extrair pasta)

        Returns:
            Dict com paths das capas geradas: {'dalle3': Path(...), 'gemini': Path(...)}
        """
        logger.info("="*70)
        logger.info(f"📚 Gerando capas para: {book_txt_path.name}")
        logger.info("="*70)

        # Extrai autor e título do path
        author = book_txt_path.parent.name
        title = book_txt_path.stem.replace('_pt', '').replace('_', ' ')

        logger.info(f"Autor: {author}")
        logger.info(f"Título: {title}")

        # Lê amostra do texto
        try:
            with open(book_txt_path, 'r', encoding='utf-8') as f:
                text_sample = f.read(5000)  # Primeiros 5000 chars
        except:
            text_sample = ""

        # Analisa o livro
        analysis = self.analyzer.analyze_book(author, title, text_sample)

        # Define diretório de saída (mesma pasta do DOCX ou pasta do TXT)
        if docx_path and docx_path.parent.exists():
            output_dir = docx_path.parent
        else:
            output_dir = book_txt_path.parent

        # Gera capas com cada API
        results = {}
        book_slug = hashlib.md5(f"{author}_{title}".encode()).hexdigest()[:8]

        for generator in self.generators:
            api_name = generator.api_name.lower().replace(' ', '_').replace('-', '_')
            output_path = output_dir / f"cover_{book_slug}_{api_name}.png"

            logger.info(f"\n{'='*50}")
            logger.info(f"Tentando {generator.api_name}...")

            success = generator.generate(author, title, analysis, output_path)

            if success and output_path.exists():
                results[api_name] = output_path
                logger.info(f"✅ {generator.api_name}: {output_path}")
            else:
                logger.warning(f"❌ {generator.api_name}: falhou")

            # Delay entre APIs para evitar rate limiting
            time.sleep(2)

        logger.info("\n" + "="*70)
        logger.info(f"✅ Capas geradas: {len(results)}/{len(self.generators)}")
        logger.info("="*70)

        return results

# ============================================================================
# CLI
# ============================================================================

def main():
    """Ponto de entrada CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="Gerador de Capas de Livros com IA")
    parser.add_argument('--input', '-i', type=Path, required=True,
                       help='Arquivo TXT do livro traduzido')
    parser.add_argument('--docx', '-d', type=Path,
                       help='Caminho do DOCX (opcional, para definir pasta de saída)')
    parser.add_argument('--batch', action='store_true',
                       help='Processa todos os livros em translated/')

    args = parser.parse_args()

    orchestrator = BookCoverOrchestrator()

    if not orchestrator.generators:
        logger.error("❌ Nenhum gerador disponível. Configure API keys.")
        return 1

    if args.batch:
        logger.info("🔄 Modo batch: gerando capas para todos os livros traduzidos")

        base_dir = Path(__file__).parent.parent
        translated_dir = base_dir / "translated"

        if not translated_dir.exists():
            logger.error(f"❌ Diretório não encontrado: {translated_dir}")
            return 1

        # Encontra todos os livros traduzidos
        txt_files = list(translated_dir.rglob("*_pt.txt"))
        logger.info(f"Encontrados {len(txt_files)} livros traduzidos")

        success_count = 0
        for txt_file in txt_files:
            try:
                results = orchestrator.generate_covers(txt_file)
                if results:
                    success_count += 1
            except Exception as e:
                logger.error(f"Erro processando {txt_file}: {e}")

        logger.info(f"\n{'='*70}")
        logger.info(f"Concluído: {success_count}/{len(txt_files)} livros com capas")
        logger.info("="*70)

        return 0 if success_count > 0 else 1

    else:
        # Modo arquivo único
        if not args.input.exists():
            logger.error(f"❌ Arquivo não encontrado: {args.input}")
            return 1

        results = orchestrator.generate_covers(args.input, args.docx)

        return 0 if results else 1


if __name__ == "__main__":
    sys.exit(main())
