#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RUN_PROCESSOR.PY - Executa o processador de livros
===================================================
Uso:
  python run_processor.py --input arquivo.txt --author "Nome Autor"
  python run_processor.py --batch  # processa todos em txt/
"""

import sys
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from processor import main

if __name__ == "__main__":
    sys.exit(main())
