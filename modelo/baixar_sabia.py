#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BAIXAR_SABIA.PY - Baixa e configura o modelo Sabiá-7B no Ollama
===============================================================
O Sabiá-7B é um modelo brasileiro da Maritaca AI treinado para português.

Este script:
1. Baixa o modelo GGUF do HuggingFace (TheBloke/sabia-7B-GGUF)
2. Cria um Modelfile para Ollama
3. Importa o modelo no Ollama

Uso: python baixar_sabia.py
"""

import os
import sys
import subprocess
import urllib.request
from pathlib import Path
from tqdm import tqdm

# Configurações
MODELS_DIR = Path(__file__).parent / "models"
SABIA_GGUF_URL = "https://huggingface.co/TheBloke/sabia-7B-GGUF/resolve/main/sabia-7b.Q4_K_M.gguf"
SABIA_GGUF_FILE = "sabia-7b.Q4_K_M.gguf"
MODEL_NAME = "sabia:7b"

class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)


def download_file(url: str, output_path: Path):
    """Baixa arquivo com barra de progresso."""
    print(f"\nBaixando: {url}")
    print(f"Destino: {output_path}")
    print(f"Tamanho aproximado: ~4GB\n")

    with DownloadProgressBar(unit='B', unit_scale=True, miniters=1, desc=output_path.name) as t:
        urllib.request.urlretrieve(url, output_path, reporthook=t.update_to)

    print(f"\n✓ Download concluído: {output_path}")


def create_modelfile(gguf_path: Path, modelfile_path: Path):
    """Cria Modelfile para Ollama."""
    content = f'''# Sabiá-7B - Modelo brasileiro para português
# Maritaca AI - https://www.maritaca.ai/

FROM {gguf_path.absolute()}

PARAMETER temperature 0.3
PARAMETER num_ctx 4096
PARAMETER stop "<|endoftext|>"

TEMPLATE """{{{{ if .System }}}}{{{{ .System }}}}

{{{{ end }}}}{{{{ .Prompt }}}}"""

SYSTEM """Você é um assistente inteligente e prestativo que responde em português brasileiro.
Seja claro, preciso e útil em suas respostas."""
'''

    with open(modelfile_path, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✓ Modelfile criado: {modelfile_path}")


def import_to_ollama(modelfile_path: Path, model_name: str):
    """Importa modelo no Ollama."""
    print(f"\nImportando para Ollama como '{model_name}'...")

    try:
        result = subprocess.run(
            ["ollama", "create", model_name, "-f", str(modelfile_path)],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            print(f"✓ Modelo '{model_name}' criado com sucesso!")
            return True
        else:
            print(f"✗ Erro ao criar modelo:")
            print(result.stderr)
            return False

    except FileNotFoundError:
        print("✗ Ollama não encontrado. Instale primeiro: https://ollama.com")
        return False


def test_model(model_name: str):
    """Testa o modelo com um prompt simples."""
    print(f"\nTestando modelo '{model_name}'...")

    try:
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": "Corrija: 'O menino foi na escola ontem de manhan.'",
                "stream": False
            },
            timeout=120
        )

        if response.status_code == 200:
            result = response.json().get('response', '')
            print(f"\n✓ Resposta do modelo:\n{result[:500]}")
            return True
        else:
            print(f"✗ Erro na API: {response.status_code}")
            return False

    except Exception as e:
        print(f"✗ Erro no teste: {e}")
        return False


def main():
    print("="*60)
    print(" BAIXAR SABIÁ-7B - Modelo Brasileiro para Português")
    print("="*60)

    # Cria diretório
    MODELS_DIR.mkdir(exist_ok=True)

    gguf_path = MODELS_DIR / SABIA_GGUF_FILE
    modelfile_path = MODELS_DIR / "Modelfile.sabia"

    # 1. Verifica se já existe
    if gguf_path.exists():
        print(f"\n✓ Modelo GGUF já existe: {gguf_path}")
        file_size = gguf_path.stat().st_size / (1024**3)
        print(f"  Tamanho: {file_size:.2f} GB")
    else:
        # Baixa o modelo
        try:
            download_file(SABIA_GGUF_URL, gguf_path)
        except Exception as e:
            print(f"\n✗ Erro no download: {e}")
            print("\nBaixe manualmente:")
            print(f"  URL: {SABIA_GGUF_URL}")
            print(f"  Salvar em: {gguf_path}")
            return 1

    # 2. Cria Modelfile
    create_modelfile(gguf_path, modelfile_path)

    # 3. Importa no Ollama
    if not import_to_ollama(modelfile_path, MODEL_NAME):
        return 1

    # 4. Lista modelos
    print("\nModelos disponíveis no Ollama:")
    subprocess.run(["ollama", "list"])

    # 5. Testa
    test_model(MODEL_NAME)

    print("\n" + "="*60)
    print(" SABIÁ-7B INSTALADO COM SUCESSO!")
    print("="*60)
    print(f"\nPara usar:")
    print(f"  ollama run {MODEL_NAME}")
    print(f"\nNo tradutor.py:")
    print(f"  python tradutor.py --model {MODEL_NAME}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
