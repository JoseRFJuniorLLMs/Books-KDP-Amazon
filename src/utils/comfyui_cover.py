#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
COMFYUI COVER GENERATOR - Gerador de Capas com SDXL Local
==========================================================
Gera capas de livros usando ComfyUI + Stable Diffusion XL.

Requisitos:
    1. ComfyUI rodando: python main.py --listen
    2. Modelo SDXL em models/checkpoints/

Uso:
    python -m src.utils.comfyui_cover --title "A Republica" --author "Platao" --output capa.png
"""

import sys
import json
import time
import uuid
import requests
import websocket
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import urljoin

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from config.settings import (
    COMFYUI_URL, SDXL_MODEL, SDXL_WIDTH, SDXL_HEIGHT,
    SDXL_STEPS, SDXL_CFG, IMAGE_BACKEND
)


# Workflow base para geracao de capas
BOOK_COVER_WORKFLOW = {
    "3": {
        "class_type": "KSampler",
        "inputs": {
            "seed": 0,
            "steps": SDXL_STEPS,
            "cfg": SDXL_CFG,
            "sampler_name": "euler",
            "scheduler": "normal",
            "denoise": 1,
            "model": ["4", 0],
            "positive": ["6", 0],
            "negative": ["7", 0],
            "latent_image": ["5", 0]
        }
    },
    "4": {
        "class_type": "CheckpointLoaderSimple",
        "inputs": {
            "ckpt_name": SDXL_MODEL
        }
    },
    "5": {
        "class_type": "EmptyLatentImage",
        "inputs": {
            "width": SDXL_WIDTH,
            "height": SDXL_HEIGHT,
            "batch_size": 1
        }
    },
    "6": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "",  # Preenchido dinamicamente
            "clip": ["4", 1]
        }
    },
    "7": {
        "class_type": "CLIPTextEncode",
        "inputs": {
            "text": "text, words, letters, watermark, signature, blurry, low quality, deformed",
            "clip": ["4", 1]
        }
    },
    "8": {
        "class_type": "VAEDecode",
        "inputs": {
            "samples": ["3", 0],
            "vae": ["4", 2]
        }
    },
    "9": {
        "class_type": "SaveImage",
        "inputs": {
            "filename_prefix": "BookCover",
            "images": ["8", 0]
        }
    }
}


class ComfyUICoverGenerator:
    """Gerador de capas usando ComfyUI + SDXL."""

    def __init__(self, url: str = COMFYUI_URL):
        self.url = url.rstrip('/')
        self.client_id = str(uuid.uuid4())

    def is_available(self) -> bool:
        """Verifica se ComfyUI esta rodando."""
        try:
            r = requests.get(f"{self.url}/system_stats", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def build_prompt(
        self,
        title: str,
        author: str,
        style: str = "artistic",
        theme: str = ""
    ) -> str:
        """Constroi prompt otimizado para capa de livro."""

        # Estilos predefinidos
        styles = {
            "artistic": "oil painting style, classical art, dramatic lighting, rich colors, museum quality",
            "modern": "minimalist design, clean lines, contemporary art, elegant, sophisticated",
            "vintage": "vintage book cover, retro illustration, aged paper texture, classic design",
            "fantasy": "fantasy art, magical atmosphere, ethereal lighting, detailed illustration",
            "dark": "dark academia aesthetic, moody lighting, mysterious atmosphere, gothic elements"
        }

        style_desc = styles.get(style, styles["artistic"])

        # Prompt base
        prompt = f"book cover artwork, {style_desc}"

        # Adiciona tema se fornecido
        if theme:
            prompt += f", {theme}"

        # Adiciona elementos baseados no titulo
        title_lower = title.lower()

        # Detecta genero/tema pelo titulo
        if any(w in title_lower for w in ["republic", "politica", "estado", "government"]):
            prompt += ", ancient greek architecture, columns, philosophical atmosphere"
        elif any(w in title_lower for w in ["war", "guerra", "battle"]):
            prompt += ", epic battle scene, dramatic sky, warriors"
        elif any(w in title_lower for w in ["love", "amor", "heart"]):
            prompt += ", romantic atmosphere, soft lighting, emotional"
        elif any(w in title_lower for w in ["death", "morte", "dark"]):
            prompt += ", somber mood, twilight, melancholic"
        elif any(w in title_lower for w in ["nature", "natureza", "forest"]):
            prompt += ", natural landscape, forests, mountains"
        elif any(w in title_lower for w in ["sea", "mar", "ocean"]):
            prompt += ", ocean waves, maritime scene, nautical"
        elif any(w in title_lower for w in ["god", "deus", "divine", "heaven"]):
            prompt += ", celestial imagery, divine light, spiritual"

        # Qualidade
        prompt += ", masterpiece, best quality, highly detailed, 8k resolution"

        return prompt

    def queue_prompt(self, workflow: Dict) -> str:
        """Envia workflow para fila do ComfyUI."""
        payload = {
            "prompt": workflow,
            "client_id": self.client_id
        }

        r = requests.post(
            f"{self.url}/prompt",
            json=payload
        )

        if r.status_code != 200:
            raise Exception(f"Erro ao enviar prompt: {r.text}")

        return r.json()["prompt_id"]

    def wait_for_completion(self, prompt_id: str, timeout: int = 300) -> Dict:
        """Aguarda conclusao da geracao."""
        ws_url = self.url.replace("http", "ws") + f"/ws?clientId={self.client_id}"

        ws = websocket.create_connection(ws_url)

        start_time = time.time()
        try:
            while time.time() - start_time < timeout:
                msg = ws.recv()
                if isinstance(msg, str):
                    data = json.loads(msg)
                    if data.get("type") == "executing":
                        if data["data"].get("node") is None:
                            # Geracao concluida
                            break
        finally:
            ws.close()

        # Busca resultado
        r = requests.get(f"{self.url}/history/{prompt_id}")
        return r.json()

    def get_image(self, filename: str, subfolder: str = "") -> bytes:
        """Baixa imagem gerada."""
        params = {"filename": filename}
        if subfolder:
            params["subfolder"] = subfolder

        r = requests.get(f"{self.url}/view", params=params)
        return r.content

    def generate(
        self,
        title: str,
        author: str,
        output_path: Path,
        style: str = "artistic",
        theme: str = "",
        seed: int = -1
    ) -> bool:
        """
        Gera capa de livro.

        Args:
            title: Titulo do livro
            author: Autor do livro
            output_path: Caminho para salvar a imagem
            style: Estilo (artistic, modern, vintage, fantasy, dark)
            theme: Tema adicional para o prompt
            seed: Seed para reproducibilidade (-1 = aleatorio)

        Returns:
            True se sucesso, False se falha
        """
        if not self.is_available():
            print(f"[ERRO] ComfyUI nao disponivel em {self.url}")
            print("       Inicie com: python main.py --listen")
            return False

        # Constroi prompt
        prompt_text = self.build_prompt(title, author, style, theme)
        print(f"[ComfyUI] Prompt: {prompt_text[:100]}...")

        # Prepara workflow
        workflow = json.loads(json.dumps(BOOK_COVER_WORKFLOW))
        workflow["6"]["inputs"]["text"] = prompt_text

        # Seed
        if seed == -1:
            import random
            seed = random.randint(0, 2**32 - 1)
        workflow["3"]["inputs"]["seed"] = seed

        # Envia para fila
        print(f"[ComfyUI] Gerando capa ({SDXL_WIDTH}x{SDXL_HEIGHT}, {SDXL_STEPS} steps)...")
        prompt_id = self.queue_prompt(workflow)

        # Aguarda
        result = self.wait_for_completion(prompt_id)

        # Extrai imagem
        try:
            outputs = result[prompt_id]["outputs"]
            images = outputs["9"]["images"]
            image_data = images[0]

            # Baixa imagem
            img_bytes = self.get_image(
                image_data["filename"],
                image_data.get("subfolder", "")
            )

            # Salva
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(img_bytes)

            print(f"[ComfyUI] Capa salva: {output_path}")
            return True

        except Exception as e:
            print(f"[ERRO] Falha ao processar resultado: {e}")
            return False


def generate_book_cover(
    title: str,
    author: str,
    output_path: Path,
    style: str = "artistic",
    theme: str = ""
) -> bool:
    """
    Funcao utilitaria para gerar capa.

    Verifica IMAGE_BACKEND e usa o gerador apropriado.
    """
    if IMAGE_BACKEND == "comfyui":
        generator = ComfyUICoverGenerator()
        return generator.generate(title, author, output_path, style, theme)
    elif IMAGE_BACKEND == "none":
        print("[INFO] Geracao de imagens desabilitada (IMAGE_BACKEND=none)")
        return False
    else:
        print(f"[AVISO] Backend de imagem '{IMAGE_BACKEND}' nao suportado localmente")
        return False


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Gera capa de livro com ComfyUI")
    parser.add_argument("--title", "-t", required=True, help="Titulo do livro")
    parser.add_argument("--author", "-a", default="Desconhecido", help="Autor")
    parser.add_argument("--output", "-o", required=True, help="Arquivo de saida")
    parser.add_argument("--style", "-s", default="artistic",
                        choices=["artistic", "modern", "vintage", "fantasy", "dark"],
                        help="Estilo da capa")
    parser.add_argument("--theme", default="", help="Tema adicional")
    parser.add_argument("--seed", type=int, default=-1, help="Seed (-1 = aleatorio)")

    args = parser.parse_args()

    generator = ComfyUICoverGenerator()

    if not generator.is_available():
        print(f"\n[ERRO] ComfyUI nao esta rodando em {COMFYUI_URL}")
        print("\nPara iniciar ComfyUI:")
        print("  cd ComfyUI")
        print("  python main.py --listen")
        sys.exit(1)

    success = generator.generate(
        title=args.title,
        author=args.author,
        output_path=Path(args.output),
        style=args.style,
        theme=args.theme,
        seed=args.seed
    )

    sys.exit(0 if success else 1)
