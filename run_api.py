#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RUN_API.PY - Inicia o servidor web do BooksKDP
================================================
Uso: python run_api.py [--port 5000] [--debug]
"""

import sys
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from api import main

if __name__ == "__main__":
    main()
