#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SETUP_MODELO.PY - Configuração do ambiente para FAZ.PY
======================================================
Este script:
1. Verifica/instala dependências Python
2. Instala Ollama (se não existir)
3. Baixa o modelo recomendado
4. Testa a conexão

Uso: python setup_modelo.py [--model MODELO]
"""

import subprocess
import sys
import os
import platform
import shutil
from pathlib import Path

# Cores para terminal
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}\n")

def print_success(text):
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_warning(text):
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_error(text):
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_info(text):
    print(f"{Colors.BLUE}ℹ {text}{Colors.END}")

# ============================================================================
# DEPENDÊNCIAS PYTHON
# ============================================================================

REQUIRED_PACKAGES = [
    "python-docx",
    "python-dotenv",
    "requests",
    "tqdm",
    "lxml",
    "tiktoken",  # Para contagem precisa de tokens
]

OPTIONAL_PACKAGES = [
    "google-generativeai",  # Para Gemini API
    "openai",               # Para OpenAI API
]

def check_python_version():
    """Verifica versão do Python."""
    print_header("Verificando Python")

    version = sys.version_info
    print_info(f"Python {version.major}.{version.minor}.{version.micro}")

    if version.major < 3 or (version.major == 3 and version.minor < 9):
        print_error("Python 3.9+ é necessário!")
        return False

    print_success("Versão do Python OK")
    return True

def install_packages():
    """Instala pacotes Python necessários."""
    print_header("Instalando Dependências Python")

    for package in REQUIRED_PACKAGES:
        print_info(f"Instalando {package}...")
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print_success(f"{package} instalado")
        except subprocess.CalledProcessError:
            print_error(f"Falha ao instalar {package}")
            return False

    print_info("\nPacotes opcionais (APIs externas):")
    for package in OPTIONAL_PACKAGES:
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "-q", package],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print_success(f"{package} instalado")
        except:
            print_warning(f"{package} não instalado (opcional)")

    return True

# ============================================================================
# OLLAMA
# ============================================================================

def check_ollama_installed():
    """Verifica se Ollama está instalado."""
    return shutil.which("ollama") is not None

def install_ollama():
    """Instala Ollama."""
    print_header("Instalando Ollama")

    system = platform.system().lower()

    if system == "windows":
        print_info("Windows detectado")
        print_info("Baixando instalador do Ollama...")

        # Baixa e executa o instalador
        installer_url = "https://ollama.com/download/OllamaSetup.exe"
        installer_path = Path.home() / "Downloads" / "OllamaSetup.exe"

        try:
            import urllib.request
            urllib.request.urlretrieve(installer_url, installer_path)
            print_success(f"Instalador baixado: {installer_path}")
            print_warning("Por favor, execute o instalador manualmente:")
            print_info(f"  {installer_path}")
            print_info("\nApós instalar, execute este script novamente.")
            return False
        except Exception as e:
            print_error(f"Falha ao baixar: {e}")
            print_info("Baixe manualmente: https://ollama.com/download")
            return False

    elif system == "linux":
        print_info("Linux detectado")
        try:
            subprocess.run(
                "curl -fsSL https://ollama.com/install.sh | sh",
                shell=True,
                check=True
            )
            print_success("Ollama instalado")
            return True
        except subprocess.CalledProcessError:
            print_error("Falha na instalação")
            return False

    elif system == "darwin":  # macOS
        print_info("macOS detectado")
        if shutil.which("brew"):
            try:
                subprocess.run(["brew", "install", "ollama"], check=True)
                print_success("Ollama instalado via Homebrew")
                return True
            except:
                pass

        print_info("Baixe em: https://ollama.com/download")
        return False

    else:
        print_error(f"Sistema não suportado: {system}")
        return False

def start_ollama_service():
    """Inicia o serviço Ollama."""
    print_info("Iniciando serviço Ollama...")

    system = platform.system().lower()

    if system == "windows":
        # No Windows, Ollama geralmente inicia como serviço
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
        except:
            pass
    else:
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except:
            pass

    # Aguarda o serviço iniciar
    import time
    for i in range(10):
        try:
            import requests
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                print_success("Serviço Ollama iniciado")
                return True
        except:
            time.sleep(1)

    print_warning("Serviço pode não ter iniciado. Verifique manualmente.")
    return False

def pull_model(model_name: str = "qwen2.5:7b"):
    """Baixa um modelo do Ollama."""
    print_header(f"Baixando Modelo: {model_name}")

    print_info("Isso pode levar vários minutos dependendo da conexão...")
    print_info(f"Tamanho aproximado: ~4-8GB\n")

    try:
        # Usa subprocess para mostrar progresso
        process = subprocess.Popen(
            ["ollama", "pull", model_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        for line in process.stdout:
            print(line, end='')

        process.wait()

        if process.returncode == 0:
            print_success(f"\nModelo {model_name} baixado com sucesso!")
            return True
        else:
            print_error(f"\nFalha ao baixar modelo")
            return False

    except FileNotFoundError:
        print_error("Comando 'ollama' não encontrado. Instale o Ollama primeiro.")
        return False
    except Exception as e:
        print_error(f"Erro: {e}")
        return False

def list_available_models():
    """Lista modelos disponíveis."""
    try:
        import requests
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return [m['name'] for m in models]
    except:
        pass
    return []

def test_model(model_name: str):
    """Testa o modelo com uma pergunta simples."""
    print_header("Testando Modelo")

    print_info(f"Modelo: {model_name}")
    print_info("Enviando prompt de teste...\n")

    try:
        import requests
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model_name,
                "prompt": "Corrija esta frase: 'O menino foi na escola ontem de manhan.'",
                "stream": False
            },
            timeout=120
        )

        if response.status_code == 200:
            result = response.json().get('response', '')
            print_success("Resposta do modelo:\n")
            print(f"  {result[:500]}")
            if len(result) > 500:
                print("  [...]")
            return True
        else:
            print_error(f"Erro na API: {response.status_code}")
            return False

    except Exception as e:
        print_error(f"Falha no teste: {e}")
        return False

# ============================================================================
# SABIÁ-2 NOTA
# ============================================================================

def show_sabia_info():
    """Mostra informação sobre o Sabiá-2."""
    print_header("Sobre o Sabiá-2")

    print(f"""
{Colors.YELLOW}IMPORTANTE: O Sabiá-2 da Maritaca AI NÃO está disponível para download local.{Colors.END}

O Sabiá-2 é acessível apenas via API paga da Maritaca AI:
  https://www.maritaca.ai/

{Colors.GREEN}ALTERNATIVAS GRATUITAS para rodar localmente:{Colors.END}

┌─────────────────┬──────────┬────────────┬───────────────────────┐
│ Modelo          │ VRAM     │ Qualidade  │ Observações           │
├─────────────────┼──────────┼────────────┼───────────────────────┤
│ qwen2.5:7b      │ 6GB      │ ★★★★★      │ RECOMENDADO - PT-BR   │
│ qwen2.5:14b     │ 10GB     │ ★★★★★+     │ Melhor, mais lento    │
│ llama3.1:8b     │ 8GB      │ ★★★★☆      │ Bom em português      │
│ gemma2:9b       │ 10GB     │ ★★★★☆      │ Google, bom geral     │
│ mistral:7b      │ 6GB      │ ★★★☆☆      │ Razoável em PT        │
└─────────────────┴──────────┴────────────┴───────────────────────┘

{Colors.BLUE}O Qwen2.5 é atualmente o melhor modelo open-source para português.{Colors.END}
Desenvolvido pela Alibaba, tem excelente suporte multilíngue.
""")

# ============================================================================
# MAIN
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Setup do ambiente para FAZ.PY")
    parser.add_argument(
        '--model', '-m',
        default='qwen2.5:7b',
        help='Modelo para baixar (padrão: qwen2.5:7b)'
    )
    parser.add_argument(
        '--skip-ollama',
        action='store_true',
        help='Pula instalação do Ollama'
    )
    parser.add_argument(
        '--list-models',
        action='store_true',
        help='Lista modelos instalados'
    )
    parser.add_argument(
        '--sabia-info',
        action='store_true',
        help='Mostra informações sobre Sabiá-2'
    )

    args = parser.parse_args()

    print_header("SETUP - FAZ.PY")

    # Informação sobre Sabiá-2
    if args.sabia_info:
        show_sabia_info()
        return 0

    # Lista modelos
    if args.list_models:
        models = list_available_models()
        if models:
            print_info("Modelos instalados:")
            for m in models:
                print(f"  - {m}")
        else:
            print_warning("Nenhum modelo encontrado ou Ollama não está rodando")
        return 0

    # Mostra info do Sabiá-2 sempre
    show_sabia_info()

    # 1. Verifica Python
    if not check_python_version():
        return 1

    # 2. Instala dependências Python
    if not install_packages():
        return 1

    # 3. Verifica/Instala Ollama
    if not args.skip_ollama:
        print_header("Verificando Ollama")

        if check_ollama_installed():
            print_success("Ollama já está instalado")
        else:
            print_warning("Ollama não encontrado")
            if not install_ollama():
                print_error("Instale o Ollama manualmente: https://ollama.com")
                return 1

        # Inicia serviço
        start_ollama_service()

        # Baixa modelo
        if not pull_model(args.model):
            return 1

        # Testa
        test_model(args.model)

    # 4. Configura .env
    print_header("Configuração")

    env_example = Path(__file__).parent / ".env.exemplo"
    env_file = Path(__file__).parent.parent / ".env"

    if not env_file.exists() and env_example.exists():
        import shutil
        shutil.copy(env_example, env_file)
        print_success(f"Arquivo .env criado: {env_file}")
        print_info("Edite o arquivo .env conforme necessário")
    elif env_file.exists():
        print_info(f"Arquivo .env já existe: {env_file}")

    print_header("Setup Concluído!")
    print_info(f"Modelo configurado: {args.model}")
    print_info("Para usar outro modelo:")
    print(f"  python setup_modelo.py --model llama3.1:8b")
    print_info("\nPara executar o processador:")
    print(f"  python faz.py --input arquivo.txt")
    print(f"  python faz.py  # processa todos em txt/")

    return 0

if __name__ == "__main__":
    sys.exit(main())
