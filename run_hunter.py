#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN_HUNTER.PY - Script para executar o Hunter
==============================================
Baixa livros do Project Gutenberg (execução sequencial).

Uso:
    python run_hunter.py --languages pt en es --limit 100
    python run_hunter.py --author "Machado de Assis" --limit 20
"""

import sys
from pathlib import Path

# Adiciona src/ ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hunter import main

if __name__ == "__main__":
    sys.exit(main())
