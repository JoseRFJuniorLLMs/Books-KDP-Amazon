#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
RUN_HUNTER_RUSSIAN.PY - Caçador de Livros Russos
=================================================
Baixa livros russos de múltiplas fontes:
- Project Gutenberg
- Archive.org
- Lib.ru
- Az.lib.ru

Uso:
    python run_hunter_russian.py --limit 500 --workers 20
    python run_hunter_russian.py --loop  # Loop infinito
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from hunter_russian import main

if __name__ == "__main__":
    sys.exit(main())
