# -*- coding: utf-8 -*-
"""
SETTINGS.PY - Configurações Centralizadas do BooksKDP
======================================================
Todas as configurações do projeto em um só lugar.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega .env
load_dotenv()

# ============================================================================
# PATHS
# ============================================================================

BASE_DIR = Path(__file__).parent.parent
SRC_DIR = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = BASE_DIR / "config"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"
LOG_DIR = BASE_DIR / "logs"
CALIBRE_DIR = BASE_DIR.parent / "CALIBRE"

# Arquivos de dados
DATABASE_PATH = DATA_DIR / "books.db"
CACHE_PATH = DATA_DIR / "cache.db"
TEMPLATE_DOCX = BASE_DIR / "Estrutura.docx"

# Input/Output
INPUT_TXT_DIR = BASE_DIR / "txt"
TRANSLATED_DIR = BASE_DIR / "translated"
OUTPUT_DOCX_DIR = BASE_DIR / "docx"

# Criar diretórios se não existem
for d in [DATA_DIR, LOG_DIR, INPUT_TXT_DIR, OUTPUT_DOCX_DIR, TEMPLATES_DIR, STATIC_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================================================
# MODELOS DE IA
# ============================================================================

# Backend: "ollama", "gemini", "openai"
MODEL_BACKEND = os.getenv("MODEL_BACKEND", "ollama")

# Ollama
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")  # Modelo rápido recomendado

# Gemini (fallback)
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY", "")

# OpenAI (fallback)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ============================================================================
# PROCESSAMENTO
# ============================================================================

MAX_CHUNK_TOKENS = int(os.getenv("MAX_CHUNK_TOKENS", "1500"))
MAX_OUTPUT_TOKENS = int(os.getenv("MAX_OUTPUT_TOKENS", "4096"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.3"))
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "5"))
RETRY_BASE_WAIT = int(os.getenv("RETRY_BASE_WAIT", "5"))
PARALLEL_CHUNKS = int(os.getenv("PARALLEL_CHUNKS", "2"))

# Mínimo de texto para processar
MIN_TEXT_LENGTH = 500

# ============================================================================
# PADRÕES DE CAPÍTULOS
# ============================================================================

CHAPTER_PATTERNS = [
    r'^\s*Capítulo\s+[\dIVXLCDMivxlcdm]+',
    r'^\s*CAPÍTULO\s+[\dIVXLCDMivxlcdm]+',
    r'^\s*Chapter\s+[\dIVXLCDMivxlcdm]+',
    r'^\s*PARTE\s+[\dIVXLCDMivxlcdm]+',
    r'^\s*LIVRO\s+[\dIVXLCDMivxlcdm]+',
    r'^\s*[\dIVXLCDM]+\.\s+',
]

# Marcadores
PAGE_BREAK_MARKER = "===QUEBRA_DE_PAGINA==="
AI_FAILURE_MARKER = "*** FALHA NA IA ***"

# ============================================================================
# API WEB
# ============================================================================

API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "5000"))
API_DEBUG = os.getenv("API_DEBUG", "True").lower() == "true"

# ============================================================================
# EMAIL (Opcional)
# ============================================================================

EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "False").lower() == "true"
EMAIL_SENDER = os.getenv("EMAIL_SENDER_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_SENDER_APP_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT_ADDRESS", "")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER", "smtp.gmail.com")
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))

# ============================================================================
# GUTENBERG
# ============================================================================

GUTENBERG_CSV_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv.gz"
