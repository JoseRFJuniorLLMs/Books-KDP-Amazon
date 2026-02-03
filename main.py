#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
BooksKDP - Sistema de processamento automatizado de livros para KDP
===================================================================

Uso:
    python main.py [comando] [opcoes]

Comandos:
    hunt        - Buscar livros no Project Gutenberg
    process     - Processar livros (traduzir, formatar)
    pipeline    - Executar pipeline completo
    api         - Iniciar API web
    daemon      - Iniciar daemon de monitoramento
    organize    - Organizar estrutura de pastas
    validate    - Validar dominio publico
    cover       - Gerar capas

Exemplos:
    python main.py hunt --limit 100
    python main.py process --input txt/ --output docx/
    python main.py pipeline --mode gemini
    python main.py api --port 8000
"""

import sys
import argparse
from pathlib import Path

# Adiciona src ao path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def main():
    parser = argparse.ArgumentParser(
        description="BooksKDP - Sistema de processamento de livros para KDP",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponíveis")

    # Hunt
    hunt_parser = subparsers.add_parser("hunt", help="Buscar livros no Gutenberg")
    hunt_parser.add_argument("--limit", type=int, default=100, help="Limite de livros")
    hunt_parser.add_argument("--fast", action="store_true", help="Modo rápido")
    hunt_parser.add_argument("--russian", action="store_true", help="Buscar livros russos")

    # Process
    proc_parser = subparsers.add_parser("process", help="Processar livros")
    proc_parser.add_argument("--input", default="txt/", help="Pasta de entrada")
    proc_parser.add_argument("--output", default="docx/", help="Pasta de saída")

    # Pipeline
    pipe_parser = subparsers.add_parser("pipeline", help="Executar pipeline")
    pipe_parser.add_argument("--mode", choices=["batch", "gemini", "kdp", "turbo", "completo"],
                            default="kdp", help="Modo do pipeline")

    # API
    api_parser = subparsers.add_parser("api", help="Iniciar API web")
    api_parser.add_argument("--port", type=int, default=8000, help="Porta")
    api_parser.add_argument("--host", default="0.0.0.0", help="Host")

    # Daemon
    daemon_parser = subparsers.add_parser("daemon", help="Iniciar daemon")
    daemon_parser.add_argument("--mode", choices=["git", "watchdog", "full"],
                              default="full", help="Modo do daemon")

    # Organize
    org_parser = subparsers.add_parser("organize", help="Organizar pastas")

    # Validate
    val_parser = subparsers.add_parser("validate", help="Validar domínio público")

    # Cover
    cover_parser = subparsers.add_parser("cover", help="Gerar capas")
    cover_parser.add_argument("--book", help="Livro específico")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Executar comando
    if args.command == "hunt":
        if args.fast:
            from hunters.hunter_fast import main as hunt_main
        elif args.russian:
            from hunters.hunter_russian import main as hunt_main
        else:
            from hunters.hunter import main as hunt_main
        hunt_main()

    elif args.command == "process":
        from core.processor import main as proc_main
        proc_main()

    elif args.command == "pipeline":
        if args.mode == "batch":
            from pipelines.batch import main as pipe_main
        elif args.mode == "gemini":
            from pipelines.gemini import main as pipe_main
        elif args.mode == "turbo":
            from pipelines.turbo import main as pipe_main
        elif args.mode == "completo":
            from pipelines.completo import main as pipe_main
        else:
            from pipelines.kdp import main as pipe_main
        pipe_main()

    elif args.command == "api":
        from web.api import main as api_main
        api_main()

    elif args.command == "daemon":
        from daemons.daemon import main as daemon_main
        daemon_main()

    elif args.command == "organize":
        from utils.organizer import main as org_main
        org_main()

    elif args.command == "validate":
        from utils.validator import main as val_main
        val_main()

    elif args.command == "cover":
        from utils.cover_generator import main as cover_main
        cover_main()


if __name__ == "__main__":
    main()
