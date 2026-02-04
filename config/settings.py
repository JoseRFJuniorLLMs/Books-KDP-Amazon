"""
BooksKDP - Configuracoes centralizadas

Carrega variaveis de ambiente do arquivo .env
Para alternar entre local e GCP:
    copy .env-local .env   (modo local)
    copy .env-gcp .env     (modo GCP)
"""

import os
import re
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env da raiz do projeto
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = BASE_DIR / ".env"

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    # Tenta carregar .env-local como fallback
    local_env = BASE_DIR / ".env-local"
    if local_env.exists():
        load_dotenv(local_env)
        print(f"[Config] Usando .env-local (copie para .env para silenciar)")

# ============================================================================
# MODO DE EXECUCAO
# ============================================================================
EXECUTION_MODE = os.getenv("EXECUTION_MODE", "local")
IS_LOCAL = EXECUTION_MODE == "local"
IS_GCP = EXECUTION_MODE == "gcp"

# ============================================================================
# DIRETORIOS
# ============================================================================
DATA_DIR = BASE_DIR / "books"
LOG_DIR = BASE_DIR / "logs"
TEMPLATE_DIR = BASE_DIR / "templates"

# Diretorios de entrada/saida
INPUT_TXT_DIR = DATA_DIR / "txt" / "other"
TRANSLATED_DIR = DATA_DIR / "txt" / "pt"
OUTPUT_DOCX_DIR = DATA_DIR / "docx"

# Arquivos de dados
DATABASE_PATH = BASE_DIR / "data" / "books.db"
CACHE_PATH = BASE_DIR / "data" / "cache.db"
TEMPLATE_DOCX = TEMPLATE_DIR / "template.docx"

# Garante que diretorios existem
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
TEMPLATE_DIR.mkdir(exist_ok=True)
(BASE_DIR / "data").mkdir(exist_ok=True)

# ============================================================================
# LLM - MODELO DE LINGUAGEM
# ============================================================================
MODEL_BACKEND = os.getenv("MODEL_BACKEND", "ollama")

# Ollama (local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:14b")

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Vertex AI
VERTEX_PROJECT = os.getenv("VERTEX_PROJECT", "")
VERTEX_REGION = os.getenv("VERTEX_REGION", "us-central1")
VERTEX_ACCESS_TOKEN = os.getenv("VERTEX_ACCESS_TOKEN", "")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ============================================================================
# PARAMETROS DE PROCESSAMENTO LLM
# ============================================================================
MAX_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_TOKENS", "4000"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "8000"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BASE_WAIT = float(os.getenv("RETRY_BASE_WAIT", "2.0"))
PARALLEL_CHUNKS = int(os.getenv("PARALLEL_CHUNKS", "3"))

# ============================================================================
# TRADUCAO
# ============================================================================
TRANSLATION_BACKEND = os.getenv("TRANSLATION_BACKEND", "local")
PROJECT_ID = os.getenv("PROJECT_ID", VERTEX_PROJECT)

# ============================================================================
# GERACAO DE IMAGENS
# ============================================================================
IMAGE_BACKEND = os.getenv("IMAGE_BACKEND", "none")
XAI_API_KEY = os.getenv("XAI_API_KEY", "")

# ComfyUI (local)
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://localhost:8188")
COMFYUI_WORKFLOW = os.getenv("COMFYUI_WORKFLOW", "book_cover_sdxl")

# SDXL Config
SDXL_MODEL = os.getenv("SDXL_MODEL", "sdxl_base_1.0.safetensors")
SDXL_WIDTH = int(os.getenv("SDXL_WIDTH", "832"))
SDXL_HEIGHT = int(os.getenv("SDXL_HEIGHT", "1216"))
SDXL_STEPS = int(os.getenv("SDXL_STEPS", "25"))
SDXL_CFG = float(os.getenv("SDXL_CFG", "7.0"))

# ============================================================================
# CLOUD STORAGE
# ============================================================================
GCS_ENABLED = os.getenv("GCS_ENABLED", "false").lower() == "true"
BUCKET_NAME = os.getenv("BUCKET_NAME", "")

# ============================================================================
# CORRECAO ORTOGRAFICA
# ============================================================================
GRAMMAR_BACKEND = os.getenv("GRAMMAR_BACKEND", "none")
LANGUAGETOOL_URL = os.getenv("LANGUAGETOOL_URL", "https://api.languagetool.org/v2/check")

# ============================================================================
# MARCADORES E PADROES
# ============================================================================
PAGE_BREAK_MARKER = "<<<PAGE_BREAK>>>"
AI_FAILURE_MARKER = "[ERRO_IA]"

# Padroes para detectar capitulos
CHAPTER_PATTERNS = [
    r'^(CHAPTER|CAPÍTULO|CAPITULO)\s+[IVXLCDM\d]+',
    r'^(Chapter|Capítulo|Capitulo)\s+[IVXLCDM\d]+',
    r'^\d+\.\s+[A-Z]',
    r'^PARTE\s+[IVXLCDM\d]+',
    r'^LIVRO\s+[IVXLCDM\d]+',
    r'^BOOK\s+[IVXLCDM\d]+',
]

# ============================================================================
# URLs das APIs
# ============================================================================
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

def get_vertex_url(model: str = "gemini-2.0-flash") -> str:
    """Retorna URL do Vertex AI para o modelo especificado."""
    return f"https://{VERTEX_REGION}-aiplatform.googleapis.com/v1/projects/{VERTEX_PROJECT}/locations/{VERTEX_REGION}/publishers/google/models/{model}:generateContent"

VERTEX_URL = get_vertex_url() if VERTEX_PROJECT else ""

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================
def get_llm_config() -> dict:
    """Retorna configuracao do LLM baseado no backend escolhido."""
    if MODEL_BACKEND == "ollama":
        return {
            "backend": "ollama",
            "url": OLLAMA_BASE_URL,
            "model": OLLAMA_MODEL,
        }
    elif MODEL_BACKEND == "gemini":
        return {
            "backend": "gemini",
            "url": GEMINI_URL,
            "api_key": GEMINI_API_KEY,
        }
    elif MODEL_BACKEND == "vertex":
        return {
            "backend": "vertex",
            "url": get_vertex_url(),
            "project": VERTEX_PROJECT,
            "region": VERTEX_REGION,
            "token": VERTEX_ACCESS_TOKEN,
        }
    elif MODEL_BACKEND == "openai":
        return {
            "backend": "openai",
            "api_key": OPENAI_API_KEY,
        }
    else:
        raise ValueError(f"Backend desconhecido: {MODEL_BACKEND}")


def is_chapter_heading(text: str) -> bool:
    """Verifica se o texto e um cabecalho de capitulo."""
    text = text.strip()
    for pattern in CHAPTER_PATTERNS:
        if re.match(pattern, text, re.IGNORECASE):
            return True
    return False


def print_config():
    """Imprime configuracao atual para debug."""
    print("=" * 60)
    print("BooksKDP - Configuracao Atual")
    print("=" * 60)
    print(f"Modo:            {EXECUTION_MODE}")
    print(f"LLM Backend:     {MODEL_BACKEND}")

    if MODEL_BACKEND == "ollama":
        print(f"  Ollama URL:    {OLLAMA_BASE_URL}")
        print(f"  Ollama Model:  {OLLAMA_MODEL}")
    elif MODEL_BACKEND == "gemini":
        print(f"  Gemini Key:    {'***' + GEMINI_API_KEY[-4:] if GEMINI_API_KEY else 'NAO CONFIGURADA'}")
    elif MODEL_BACKEND == "vertex":
        print(f"  Project:       {VERTEX_PROJECT}")
        print(f"  Region:        {VERTEX_REGION}")

    print(f"Traducao:        {TRANSLATION_BACKEND}")
    print(f"Imagens:         {IMAGE_BACKEND}")
    print(f"GCS:             {'Habilitado' if GCS_ENABLED else 'Desabilitado'}")
    print(f"Gramatica:       {GRAMMAR_BACKEND}")
    print("=" * 60)


if __name__ == "__main__":
    print_config()
