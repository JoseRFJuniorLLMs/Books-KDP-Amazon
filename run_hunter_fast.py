#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN_HUNTER_FAST.PY - Download Massivo Paralelo
===============================================
Baixa livros em massa (10 threads) sem verificação prévia.
Remove duplicados depois.

Uso:
    python run_hunter_fast.py --languages en es --limit 500 --workers 10
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from hunter_fast import main

if __name__ == "__main__":
    sys.exit(main())
