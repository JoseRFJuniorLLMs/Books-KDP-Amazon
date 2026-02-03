#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN_HUNTER2.PY - Script para executar o Hunter2
================================================
Baixa livros do Archive.org (Internet Archive).

Uso:
    python run_hunter2.py --languages en es --limit 100
    python run_hunter2.py --languages pt --limit 50
"""

import sys
from pathlib import Path

# Adiciona src/ ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from hunter2 import main

if __name__ == "__main__":
    sys.exit(main())
