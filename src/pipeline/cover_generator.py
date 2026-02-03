#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
GERADOR DE CAPAS - BooksKDP
===========================
Gera capas de livros usando Imagen (Vertex AI).

Fluxo:
    1. Cria resumo do livro (Gemini)
    2. Gera prompt para capa
    3. Gera imagem com Imagen
    4. Salva junto com o DOCX

Uso:
    python -m src.pipeline.cover_generator --input books/txt/pt --output books/covers
"""

import os
import json
import base64
import asyncio
import aiohttp
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Configuração
PROJECT_ID = os.getenv("PROJECT_ID", "aurorav2-484411")
REGION = "us-central1"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# APIs
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3-pro-preview:generateContent"
# Imagen 3 (nano) - modelo mais novo e rápido
IMAGEN_URL = f"https://{REGION}-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/{REGION}/publishers/google/models/imagen-3.0-generate-001:predict"


class CoverGenerator:
    """Gera capas de livros usando IA."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        api_key: str = "",
        style: str = "artistic"
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.api_key = api_key or GEMINI_API_KEY
        self.style = style
        self.stats = {"generated": 0, "failed": 0, "skipped": 0}

        # Estilos de capa disponíveis
        self.styles = {
            "artistic": "oil painting style, dramatic lighting, classical art",
            "modern": "modern minimalist design, clean lines, bold typography",
            "vintage": "vintage book cover, aged paper texture, ornate borders",
            "fantasy": "fantasy art style, magical atmosphere, epic scene",
            "literary": "elegant literary design, subtle colors, sophisticated",
        }

    async def create_summary(self, text: str, title: str) -> str:
        """Cria resumo do livro usando Gemini."""
        prompt = f"""Analise este livro e crie um resumo de 2-3 frases que capture:
- O tema principal
- O tom/atmosfera
- Elementos visuais marcantes

Título: {title}

Texto (primeiros 5000 caracteres):
{text[:5000]}

RESUMO (máximo 100 palavras):"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GEMINI_URL}?key={self.api_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": 200}
                    },
                    timeout=30
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"  Erro no resumo: {e}")

        return f"Livro clássico: {title}"

    async def generate_cover_prompt(self, title: str, author: str, summary: str) -> str:
        """Gera prompt otimizado para a capa."""
        style_desc = self.styles.get(self.style, self.styles["artistic"])

        prompt = f"""Crie um prompt para gerar uma capa de livro.

Título: {title}
Autor: {author}
Resumo: {summary}
Estilo: {style_desc}

Regras:
- NÃO inclua texto/letras na imagem
- Foque em elementos visuais simbólicos
- Composição vertical (formato livro)
- Cores que evoquem o tema

PROMPT PARA IMAGEM (em inglês, máximo 150 palavras):"""

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{GEMINI_URL}?key={self.api_key}",
                    json={
                        "contents": [{"parts": [{"text": prompt}]}],
                        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 200}
                    },
                    timeout=30
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        image_prompt = data["candidates"][0]["content"]["parts"][0]["text"]
                        # Adiciona instruções de estilo
                        return f"{image_prompt}, {style_desc}, book cover art, no text, vertical composition, high quality"
        except Exception as e:
            print(f"  Erro no prompt: {e}")

        # Prompt padrão se falhar
        return f"Book cover illustration for '{title}', {style_desc}, symbolic imagery, no text, vertical composition, dramatic lighting"

    async def generate_image_imagen(self, prompt: str, output_path: Path) -> bool:
        """Gera imagem usando Imagen (Vertex AI)."""
        try:
            # Obtém token OAuth
            import subprocess
            result = subprocess.run(
                ['gcloud', 'auth', 'print-access-token'],
                capture_output=True, text=True, timeout=30
            )
            token = result.stdout.strip()

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    IMAGEN_URL,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "instances": [{"prompt": prompt}],
                        "parameters": {
                            "sampleCount": 1,
                            "aspectRatio": "9:16",  # Vertical para capa
                            "negativePrompt": "text, letters, words, watermark, signature, blurry, low quality"
                        }
                    },
                    timeout=120
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        predictions = data.get("predictions", [])
                        if predictions:
                            image_b64 = predictions[0].get("bytesBase64Encoded")
                            if image_b64:
                                image_bytes = base64.b64decode(image_b64)
                                output_path.write_bytes(image_bytes)
                                return True
                    else:
                        error = await resp.text()
                        print(f"  Imagen erro {resp.status}: {error[:200]}")

        except Exception as e:
            print(f"  Erro Imagen: {e}")

        return False

    async def generate_image_gemini(self, prompt: str, output_path: Path) -> bool:
        """Gera imagem usando Gemini (fallback)."""
        # Gemini 2.0 pode gerar imagens via API
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
                    timeout=120
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
                                    output_path.write_bytes(image_bytes)
                                    return True

        except Exception as e:
            print(f"  Erro Gemini image: {e}")

        return False

    async def generate_cover(self, txt_path: Path) -> Optional[Dict]:
        """Gera capa para um livro."""
        try:
            # Lê texto
            text = txt_path.read_text(encoding='utf-8', errors='ignore')
            if len(text) < 1000:
                self.stats["skipped"] += 1
                return None

            # Extrai título e autor do nome do arquivo
            name = txt_path.stem
            if "_" in name:
                parts = name.split("_", 1)
                author = parts[0]
                title = parts[1] if len(parts) > 1 else name
            else:
                author = "Autor Desconhecido"
                title = name

            print(f"\n[CAPA] {title[:50]}")

            # 1. Cria resumo
            print("  1. Criando resumo...")
            summary = await self.create_summary(text, title)
            print(f"     {summary[:100]}...")

            # 2. Gera prompt para imagem
            print("  2. Gerando prompt...")
            image_prompt = await self.generate_cover_prompt(title, author, summary)
            print(f"     {image_prompt[:100]}...")

            # 3. Gera imagem
            print("  3. Gerando imagem...")
            self.output_dir.mkdir(parents=True, exist_ok=True)
            cover_path = self.output_dir / f"{txt_path.stem}_cover.png"

            # Tenta Imagen primeiro, depois Gemini
            success = await self.generate_image_imagen(image_prompt, cover_path)
            if not success:
                print("     Imagen falhou, tentando Gemini...")
                success = await self.generate_image_gemini(image_prompt, cover_path)

            if success:
                self.stats["generated"] += 1
                print(f"  ✓ Capa salva: {cover_path.name}")

                # Salva metadados
                meta_path = self.output_dir / f"{txt_path.stem}_meta.json"
                meta_path.write_text(json.dumps({
                    "title": title,
                    "author": author,
                    "summary": summary,
                    "prompt": image_prompt,
                    "style": self.style,
                    "generated_at": datetime.now().isoformat()
                }, ensure_ascii=False, indent=2))

                return {
                    "title": title,
                    "author": author,
                    "cover": str(cover_path),
                    "summary": summary
                }
            else:
                self.stats["failed"] += 1
                print("  ✗ Falha na geração")

        except Exception as e:
            self.stats["failed"] += 1
            print(f"  ERRO: {e}")

        return None

    async def run(self, limit: int = 0) -> List[Dict]:
        """Gera capas para todos os livros."""
        print("=" * 60)
        print("GERADOR DE CAPAS - BooksKDP")
        print("=" * 60)
        print(f"Entrada: {self.input_dir}")
        print(f"Saída: {self.output_dir}")
        print(f"Estilo: {self.style}")
        print()

        # Lista arquivos
        txt_files = list(self.input_dir.rglob("*.txt"))
        if limit > 0:
            txt_files = txt_files[:limit]

        print(f"Livros encontrados: {len(txt_files)}")
        print()

        results = []
        for i, txt_path in enumerate(txt_files):
            print(f"[{i+1}/{len(txt_files)}]", end="")

            # Verifica se já existe
            cover_path = self.output_dir / f"{txt_path.stem}_cover.png"
            if cover_path.exists():
                print(f" {txt_path.stem[:40]} - já existe, pulando")
                self.stats["skipped"] += 1
                continue

            result = await self.generate_cover(txt_path)
            if result:
                results.append(result)

            # Rate limiting
            await asyncio.sleep(2)

        # Relatório
        print()
        print("=" * 60)
        print("RESUMO")
        print("=" * 60)
        print(f"Geradas: {self.stats['generated']}")
        print(f"Falhas:  {self.stats['failed']}")
        print(f"Puladas: {self.stats['skipped']}")

        return results


async def main():
    parser = argparse.ArgumentParser(description="Gerar capas de livros")
    parser.add_argument("--input", default="books/txt/pt", help="Pasta de entrada")
    parser.add_argument("--output", default="books/covers", help="Pasta de saída")
    parser.add_argument("--style", default="artistic",
                       choices=["artistic", "modern", "vintage", "fantasy", "literary"],
                       help="Estilo da capa")
    parser.add_argument("--limit", type=int, default=0, help="Limite de livros")
    parser.add_argument("--api-key", help="Gemini API Key")

    args = parser.parse_args()

    generator = CoverGenerator(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        api_key=args.api_key or "",
        style=args.style
    )

    await generator.run(args.limit)


if __name__ == "__main__":
    asyncio.run(main())
