#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
SETUP LOCAL - Configura ambiente local para BooksKDP
====================================================
Verifica e instala dependencias para modo 100% local:
- Ollama + modelo qwen2.5:14b
- LanguageTool Docker
- ComfyUI + SDXL (instrucoes)

Uso:
    python scripts/setup_local.py
    python scripts/setup_local.py --check   # Apenas verifica
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

# Cores para terminal
class Colors:
    OK = '\033[92m'
    WARN = '\033[93m'
    FAIL = '\033[91m'
    BOLD = '\033[1m'
    END = '\033[0m'

def check_command(cmd: str) -> bool:
    """Verifica se comando existe."""
    return shutil.which(cmd) is not None

def check_url(url: str, timeout: int = 5) -> bool:
    """Verifica se URL responde."""
    try:
        import requests
        r = requests.get(url, timeout=timeout)
        return r.status_code == 200
    except:
        return False

def run_command(cmd: str, capture: bool = True) -> tuple:
    """Executa comando e retorna (sucesso, output)."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=capture, text=True
        )
        return result.returncode == 0, result.stdout
    except:
        return False, ""

def print_status(name: str, ok: bool, msg: str = ""):
    """Imprime status com cor."""
    status = f"{Colors.OK}OK{Colors.END}" if ok else f"{Colors.FAIL}FALTA{Colors.END}"
    print(f"  [{status}] {name}")
    if msg and not ok:
        print(f"        {Colors.WARN}{msg}{Colors.END}")

def main():
    print(f"\n{Colors.BOLD}BooksKDP - Setup Local{Colors.END}")
    print("=" * 50)

    all_ok = True

    # 1. Python dependencies
    print(f"\n{Colors.BOLD}1. Dependencias Python{Colors.END}")
    try:
        import dotenv
        print_status("python-dotenv", True)
    except ImportError:
        print_status("python-dotenv", False, "pip install python-dotenv")
        all_ok = False

    try:
        import requests
        print_status("requests", True)
    except ImportError:
        print_status("requests", False, "pip install requests")
        all_ok = False

    try:
        import websocket
        print_status("websocket-client", True)
    except ImportError:
        print_status("websocket-client", False, "pip install websocket-client")
        all_ok = False

    try:
        import docx
        print_status("python-docx", True)
    except ImportError:
        print_status("python-docx", False, "pip install python-docx")
        all_ok = False

    # 2. Ollama
    print(f"\n{Colors.BOLD}2. Ollama (LLM Local){Colors.END}")
    ollama_ok = check_command("ollama")
    print_status("ollama instalado", ollama_ok, "https://ollama.ai")

    if ollama_ok:
        ollama_running = check_url("http://localhost:11434/api/tags")
        print_status("ollama rodando", ollama_running, "ollama serve")

        if ollama_running:
            # Verifica modelo
            ok, output = run_command("ollama list")
            has_model = "qwen2.5:14b" in output or "qwen2.5" in output
            print_status("modelo qwen2.5:14b", has_model, "ollama pull qwen2.5:14b")
            if not has_model:
                all_ok = False
        else:
            all_ok = False
    else:
        all_ok = False

    # 3. Docker / LanguageTool
    print(f"\n{Colors.BOLD}3. LanguageTool (Gramatica){Colors.END}")
    docker_ok = check_command("docker")
    print_status("docker instalado", docker_ok, "https://docker.com")

    if docker_ok:
        lt_running = check_url("http://localhost:8010/v2/check")
        print_status("languagetool rodando", lt_running,
                    "docker run -d -p 8010:8010 erikvl87/languagetool")
        if not lt_running:
            all_ok = False
    else:
        # Fallback para API publica
        lt_public = check_url("https://api.languagetool.org/v2/check")
        print_status("languagetool API publica", lt_public, "Usar como fallback")

    # 4. ComfyUI
    print(f"\n{Colors.BOLD}4. ComfyUI (Geracao de Capas){Colors.END}")
    comfy_running = check_url("http://localhost:8188/system_stats")
    print_status("comfyui rodando", comfy_running, "Ver instrucoes abaixo")

    if not comfy_running:
        print(f"\n  {Colors.WARN}Para instalar ComfyUI:{Colors.END}")
        print("    git clone https://github.com/comfyanonymous/ComfyUI")
        print("    cd ComfyUI")
        print("    pip install -r requirements.txt")
        print("    python main.py --listen")
        print(f"\n  {Colors.WARN}Baixar modelo SDXL:{Colors.END}")
        print("    Coloque em ComfyUI/models/checkpoints/")
        print("    Recomendado: sdxl_base_1.0.safetensors")
        print("    Download: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0")

    # 5. Arquivos de configuracao
    print(f"\n{Colors.BOLD}5. Configuracao{Colors.END}")
    base_dir = Path(__file__).parent.parent
    env_file = base_dir / ".env"
    env_local = base_dir / ".env-local"

    print_status(".env-local existe", env_local.exists())
    print_status(".env configurado", env_file.exists(),
                f"copy .env-local .env" if env_local.exists() else "")

    # Resumo
    print(f"\n{'=' * 50}")
    if all_ok:
        print(f"{Colors.OK}{Colors.BOLD}Tudo pronto para modo local!{Colors.END}")
    else:
        print(f"{Colors.WARN}{Colors.BOLD}Algumas dependencias faltando.{Colors.END}")
        print("\nComandos para instalar:")
        print("  pip install -r requirements.txt")
        print("  ollama pull qwen2.5:14b")
        print("  docker run -d -p 8010:8010 erikvl87/languagetool")

    print()
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
