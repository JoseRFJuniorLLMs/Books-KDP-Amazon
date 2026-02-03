# -*- coding: utf-8 -*-
"""
GERADOR DE CAPAS - FLUX.1 dev
=============================
Gera capas de livros automaticamente usando FLUX.1 dev local.

Requisitos:
    pip install diffusers torch accelerate transformers sentencepiece

Uso:
    python gerar_capas.py --titulo "O Quarto Caminho" --autor "P.D. Ouspensky"
    python gerar_capas.py --batch --input lista_livros.txt
"""

import os
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

# Diretórios
BASE_DIR = Path(__file__).parent
CAPAS_DIR = BASE_DIR / "capas"
CAPAS_DIR.mkdir(exist_ok=True)

# Dimensões KDP
DIMENSOES = {
    'ebook': (1600, 2560),      # Kindle ebook
    'print_6x9': (1800, 2700),  # 6x9" at 300dpi
    'print_5x8': (1500, 2400),  # 5x8" at 300dpi
}

# Estilos de capa
ESTILOS = {
    'minimalista': "minimalist book cover, clean design, elegant typography, solid color background, professional",
    'ilustrado': "illustrated book cover, artistic, hand-drawn style, vintage feel, warm colors",
    'fotografico': "photographic book cover, cinematic, dramatic lighting, professional photography",
    'mistico': "mystical book cover, ethereal, cosmic, spiritual symbols, dark background with golden accents",
    'classico': "classic literature book cover, ornate border, vintage typography, aged paper texture",
    'moderno': "modern book cover, bold geometric shapes, contemporary design, striking contrast",
}

# Gêneros e suas características visuais
GENEROS = {
    'filosofia': "philosophical, contemplative, abstract concepts, wisdom symbols",
    'espiritualidade': "spiritual, mystical, sacred geometry, cosmic energy, meditation",
    'ficcao': "narrative, storytelling, dramatic scene, emotional",
    'autoajuda': "inspiring, uplifting, growth, transformation, light",
    'historia': "historical, period-accurate, sepia tones, documentary feel",
    'ciencia': "scientific, futuristic, technology, innovation, precision",
    'poesia': "poetic, artistic, emotional, flowing, nature elements",
    'biografia': "portrait style, dignified, personal, memorable",
}


def criar_prompt_capa(titulo: str, autor: str, genero: str = 'filosofia',
                       estilo: str = 'minimalista', idioma: str = 'pt') -> str:
    """Cria prompt otimizado para FLUX.1 gerar capa de livro."""

    estilo_desc = ESTILOS.get(estilo, ESTILOS['minimalista'])
    genero_desc = GENEROS.get(genero, GENEROS['filosofia'])

    # FLUX.1 é bom com texto, mas melhor não incluir no prompt
    # O texto será adicionado depois via Pillow/ImageMagick

    prompt = f"""Professional book cover design, {estilo_desc}, {genero_desc}.

Theme inspired by the book "{titulo}" by {autor}.
High quality, print-ready, 300 DPI quality.
Clean space at top for title and bottom for author name.
Vertical orientation, portrait format.
No text, no letters, no words on the image."""

    return prompt


def gerar_capa_flux(prompt: str, output_path: Path,
                    width: int = 1600, height: int = 2560,
                    steps: int = 28, guidance: float = 3.5) -> bool:
    """Gera capa usando FLUX.1 dev local."""

    try:
        import torch
        from diffusers import FluxPipeline

        print("Carregando FLUX.1 dev...")

        # Detecta dispositivo
        if torch.cuda.is_available():
            device = "cuda"
            dtype = torch.bfloat16
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            device = "mps"
            dtype = torch.float16
        else:
            device = "cpu"
            dtype = torch.float32
            print("AVISO: Rodando em CPU será muito lento!")

        print(f"Dispositivo: {device}")

        # Carrega modelo
        pipe = FluxPipeline.from_pretrained(
            "black-forest-labs/FLUX.1-dev",
            torch_dtype=dtype
        )
        pipe = pipe.to(device)

        # Otimizações de memória
        if device == "cuda":
            pipe.enable_model_cpu_offload()

        print(f"Gerando imagem ({width}x{height})...")
        print(f"Prompt: {prompt[:100]}...")

        # Gera imagem
        image = pipe(
            prompt=prompt,
            width=width,
            height=height,
            num_inference_steps=steps,
            guidance_scale=guidance,
            generator=torch.Generator(device).manual_seed(42)
        ).images[0]

        # Salva
        image.save(output_path, quality=95)
        print(f"Capa salva: {output_path}")

        return True

    except ImportError:
        print("ERRO: Instale as dependências:")
        print("  pip install diffusers torch accelerate transformers sentencepiece")
        return False
    except Exception as e:
        print(f"ERRO: {e}")
        return False


def gerar_capa_api(prompt: str, output_path: Path,
                   width: int = 1600, height: int = 2560,
                   api: str = 'replicate') -> bool:
    """Gera capa usando API externa (fallback)."""

    if api == 'replicate':
        try:
            import replicate

            print("Gerando via Replicate API...")

            output = replicate.run(
                "black-forest-labs/flux-dev",
                input={
                    "prompt": prompt,
                    "width": width,
                    "height": height,
                    "num_inference_steps": 28,
                    "guidance_scale": 3.5,
                }
            )

            # Download da imagem
            import urllib.request
            urllib.request.urlretrieve(output[0], output_path)
            print(f"Capa salva: {output_path}")
            return True

        except ImportError:
            print("ERRO: pip install replicate")
            return False
        except Exception as e:
            print(f"ERRO API: {e}")
            return False

    return False


def adicionar_texto_capa(imagem_path: Path, titulo: str, autor: str,
                          output_path: Optional[Path] = None) -> bool:
    """Adiciona título e autor na capa."""

    try:
        from PIL import Image, ImageDraw, ImageFont

        img = Image.open(imagem_path)
        draw = ImageDraw.Draw(img)

        width, height = img.size

        # Tenta carregar fonte (fallback para default)
        try:
            # Fontes comuns no Windows
            font_titulo = ImageFont.truetype("arial.ttf", int(height * 0.06))
            font_autor = ImageFont.truetype("arial.ttf", int(height * 0.03))
        except:
            font_titulo = ImageFont.load_default()
            font_autor = ImageFont.load_default()

        # Título (parte superior)
        titulo_upper = titulo.upper()
        bbox = draw.textbbox((0, 0), titulo_upper, font=font_titulo)
        titulo_width = bbox[2] - bbox[0]
        titulo_x = (width - titulo_width) // 2
        titulo_y = int(height * 0.08)

        # Sombra do título
        draw.text((titulo_x + 2, titulo_y + 2), titulo_upper, font=font_titulo, fill='black')
        draw.text((titulo_x, titulo_y), titulo_upper, font=font_titulo, fill='white')

        # Autor (parte inferior)
        bbox = draw.textbbox((0, 0), autor, font=font_autor)
        autor_width = bbox[2] - bbox[0]
        autor_x = (width - autor_width) // 2
        autor_y = int(height * 0.88)

        draw.text((autor_x + 1, autor_y + 1), autor, font=font_autor, fill='black')
        draw.text((autor_x, autor_y), autor, font=font_autor, fill='white')

        # Salva
        out = output_path or imagem_path.with_stem(imagem_path.stem + "_final")
        img.save(out, quality=95)
        print(f"Capa com texto: {out}")

        return True

    except ImportError:
        print("ERRO: pip install Pillow")
        return False
    except Exception as e:
        print(f"ERRO: {e}")
        return False


def processar_livro(titulo: str, autor: str, genero: str = 'filosofia',
                    estilo: str = 'minimalista', formato: str = 'ebook',
                    usar_api: bool = False) -> Optional[Path]:
    """Processa um livro e gera sua capa."""

    print(f"\n{'='*50}")
    print(f"Gerando capa: {titulo}")
    print(f"Autor: {autor}")
    print(f"Gênero: {genero} | Estilo: {estilo}")
    print('='*50)

    # Dimensões
    width, height = DIMENSOES.get(formato, DIMENSOES['ebook'])

    # Cria prompt
    prompt = criar_prompt_capa(titulo, autor, genero, estilo)

    # Nome do arquivo
    nome_safe = "".join(c if c.isalnum() or c in ' -_' else '' for c in titulo)
    nome_safe = nome_safe.replace(' ', '_')[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    output_base = CAPAS_DIR / f"{nome_safe}_{timestamp}.png"
    output_final = CAPAS_DIR / f"{nome_safe}_{timestamp}_final.png"

    # Gera imagem
    if usar_api:
        success = gerar_capa_api(prompt, output_base, width, height)
    else:
        success = gerar_capa_flux(prompt, output_base, width, height)

    if not success:
        return None

    # Adiciona texto
    adicionar_texto_capa(output_base, titulo, autor, output_final)

    return output_final


def processar_batch(arquivo_lista: Path, **kwargs) -> List[Path]:
    """Processa lista de livros em batch."""

    resultados = []

    with open(arquivo_lista, 'r', encoding='utf-8') as f:
        for linha in f:
            linha = linha.strip()
            if not linha or linha.startswith('#'):
                continue

            # Formato: titulo|autor|genero|estilo
            partes = linha.split('|')
            if len(partes) < 2:
                continue

            titulo = partes[0].strip()
            autor = partes[1].strip()
            genero = partes[2].strip() if len(partes) > 2 else 'filosofia'
            estilo = partes[3].strip() if len(partes) > 3 else 'minimalista'

            resultado = processar_livro(titulo, autor, genero, estilo, **kwargs)
            if resultado:
                resultados.append(resultado)

    return resultados


def main():
    parser = argparse.ArgumentParser(description="Gera capas de livros com FLUX.1")

    # Modo individual
    parser.add_argument('--titulo', '-t', help='Título do livro')
    parser.add_argument('--autor', '-a', help='Nome do autor')
    parser.add_argument('--genero', '-g', default='filosofia',
                        choices=list(GENEROS.keys()), help='Gênero do livro')
    parser.add_argument('--estilo', '-e', default='minimalista',
                        choices=list(ESTILOS.keys()), help='Estilo visual')
    parser.add_argument('--formato', '-f', default='ebook',
                        choices=list(DIMENSOES.keys()), help='Formato/dimensões')

    # Modo batch
    parser.add_argument('--batch', '-b', type=Path, help='Arquivo com lista de livros')

    # Opções
    parser.add_argument('--api', action='store_true', help='Usar API ao invés de local')
    parser.add_argument('--listar-estilos', action='store_true', help='Lista estilos disponíveis')
    parser.add_argument('--listar-generos', action='store_true', help='Lista gêneros disponíveis')

    args = parser.parse_args()

    if args.listar_estilos:
        print("\nEstilos disponíveis:")
        for nome, desc in ESTILOS.items():
            print(f"  {nome}: {desc[:60]}...")
        return

    if args.listar_generos:
        print("\nGêneros disponíveis:")
        for nome, desc in GENEROS.items():
            print(f"  {nome}: {desc[:60]}...")
        return

    if args.batch:
        resultados = processar_batch(args.batch, formato=args.formato, usar_api=args.api)
        print(f"\n{len(resultados)} capas geradas em: {CAPAS_DIR}")

    elif args.titulo and args.autor:
        resultado = processar_livro(
            args.titulo, args.autor, args.genero, args.estilo,
            args.formato, args.api
        )
        if resultado:
            print(f"\nCapa final: {resultado}")

    else:
        parser.print_help()
        print("\nExemplo:")
        print('  python gerar_capas.py --titulo "O Quarto Caminho" --autor "P.D. Ouspensky" --genero espiritualidade')


if __name__ == "__main__":
    main()
