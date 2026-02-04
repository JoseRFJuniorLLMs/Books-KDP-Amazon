#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
ORCHESTRATOR
============
Coordena a execução paralela de todos os módulos do pipeline.

Fluxo:
    1. DOWNLOADER  -> books/raw/{lang}/
    2. TRANSLATOR  -> books/txt/pt/
    3. GENERATOR   -> books/docx/pt/
    4. ENRICHER    -> books/docx/{pt,es,fr}/enriched/ (vocabulário EN)
    5. CLEANER     -> Organiza e valida

Uso:
    python -m src.pipeline.orchestrator --full
    python -m src.pipeline.orchestrator --step download
    python -m src.pipeline.orchestrator --step translate
    python -m src.pipeline.orchestrator --step generate
    python -m src.pipeline.orchestrator --step enrich
    python -m src.pipeline.orchestrator --step clean
"""

import sys
import json
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# Adiciona raiz do projeto ao path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

# Configuracao centralizada
from config.settings import GEMINI_API_KEY

# Importar módulos do pipeline
from .downloader import BookDownloader
from .translator import BookTranslator
from .generator import DocxGenerator
from .enricher import VocabularyEnricher
from .cleaner import BookCleaner


class PipelineOrchestrator:
    """Orquestra a execução do pipeline completo."""

    def __init__(
        self,
        base_dir: Path = Path("books"),
        gemini_api_key: str = "",
        download_workers: int = 10,
        translate_workers: int = 3,
        generate_workers: int = 4
    ):
        self.base_dir = base_dir
        self.gemini_api_key = gemini_api_key or GEMINI_API_KEY
        self.download_workers = download_workers
        self.translate_workers = translate_workers
        self.generate_workers = generate_workers

        self.stats = {
            "started": datetime.now().isoformat(),
            "steps": {}
        }

    async def step_download(self, start_id: int = 1, limit: int = 100) -> Dict:
        """Passo 1: Download de livros."""
        print("\n" + "="*60)
        print("PASSO 1: DOWNLOAD")
        print("="*60 + "\n")

        output_dir = self.base_dir / "raw"

        async with BookDownloader(output_dir, self.download_workers) as downloader:
            results = await downloader.run(start_id, limit)

        self.stats["steps"]["download"] = {
            "completed": datetime.now().isoformat(),
            "downloaded": len(results)
        }

        return {"downloaded": len(results), "results": results}

    async def step_translate(self, source_lang: str = "en", limit: int = 0) -> Dict:
        """Passo 2: Tradução de livros."""
        print("\n" + "="*60)
        print("PASSO 2: TRADUÇÃO")
        print("="*60 + "\n")

        input_dir = self.base_dir / "raw"
        output_dir = self.base_dir / "txt" / "pt"

        async with BookTranslator(
            input_dir,
            output_dir,
            self.gemini_api_key,
            self.translate_workers
        ) as translator:
            results = await translator.run(source_lang, limit)

        self.stats["steps"]["translate"] = {
            "completed": datetime.now().isoformat(),
            "translated": len(results)
        }

        return {"translated": len(results), "results": results}

    def step_generate(self, input_lang: str = "pt", limit: int = 0) -> Dict:
        """Passo 3: Geração de DOCX."""
        print("\n" + "="*60)
        print("PASSO 3: GERAÇÃO DOCX")
        print("="*60 + "\n")

        input_dir = self.base_dir / "txt" / input_lang
        output_dir = self.base_dir / "docx" / input_lang

        generator = DocxGenerator(input_dir, output_dir, self.generate_workers)
        results = generator.run(limit)

        self.stats["steps"]["generate"] = {
            "completed": datetime.now().isoformat(),
            "generated": len(results)
        }

        return {"generated": len(results), "results": results}

    def step_enrich(self, source_lang: str = "pt", num_words: int = 100, limit: int = 0) -> Dict:
        """Passo 4: Enriquecimento com vocabulário em inglês."""
        print("\n" + "="*60)
        print(f"PASSO 4: ENRIQUECIMENTO ({source_lang.upper()} + EN)")
        print("="*60 + "\n")

        input_dir = self.base_dir / "txt" / source_lang
        output_dir = self.base_dir / "docx" / source_lang / "enriched"

        enricher = VocabularyEnricher(
            input_dir=input_dir,
            output_dir=output_dir,
            source_lang=source_lang,
            num_words=num_words,
            use_api=bool(self.gemini_api_key),
            api_key=self.gemini_api_key
        )
        results = enricher.run(limit)

        self.stats["steps"]["enrich"] = {
            "completed": datetime.now().isoformat(),
            "enriched": len(results),
            "language": source_lang,
            "words_per_book": num_words
        }

        return {"enriched": len(results), "results": results}

    def step_clean(self, mode: str = "all") -> Dict:
        """Passo 5: Limpeza e organização."""
        print("\n" + "="*60)
        print("PASSO 5: LIMPEZA")
        print("="*60 + "\n")

        cleaner = BookCleaner(self.base_dir)
        results = cleaner.run(mode)

        self.stats["steps"]["clean"] = {
            "completed": datetime.now().isoformat(),
            "results": results
        }

        return results

    async def run_full_pipeline(
        self,
        download_start: int = 1,
        download_limit: int = 100,
        translate_limit: int = 0,
        generate_limit: int = 0
    ) -> Dict:
        """Executa o pipeline completo."""
        print("\n" + "#"*60)
        print("# PIPELINE COMPLETO - BooksKDP")
        print("#"*60)
        print(f"\nInício: {self.stats['started']}")
        print(f"Diretório: {self.base_dir}")
        print(f"API Key: {'Configurada' if self.gemini_api_key else 'NÃO CONFIGURADA'}")

        results = {}

        # Passo 1: Download
        results["download"] = await self.step_download(download_start, download_limit)

        # Passo 2: Tradução (se tiver API key)
        if self.gemini_api_key:
            results["translate"] = await self.step_translate("en", translate_limit)
        else:
            print("\n[AVISO] Pulando tradução - GEMINI_API_KEY não configurada")
            results["translate"] = {"skipped": True}

        # Passo 3: Geração DOCX
        results["generate"] = self.step_generate("pt", generate_limit)

        # Passo 4: Enriquecimento (PT, ES, FR com vocabulário EN)
        for lang in ['pt', 'es', 'fr']:
            lang_dir = self.base_dir / "txt" / lang
            if lang_dir.exists() and any(lang_dir.glob("**/*.txt")):
                results[f"enrich_{lang}"] = self.step_enrich(lang, 100, 0)

        # Passo 5: Limpeza
        results["clean"] = self.step_clean("all")

        # Finalizar
        self.stats["finished"] = datetime.now().isoformat()
        self.stats["results"] = results

        # Relatório final
        self.print_summary(results)

        # Salvar estatísticas
        stats_file = self.base_dir / "pipeline_stats.json"
        stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        return results

    def print_summary(self, results: Dict):
        """Imprime resumo do pipeline."""
        print("\n" + "="*60)
        print("RESUMO DO PIPELINE")
        print("="*60)

        # Contar enriquecimentos
        enrich_pt = results.get('enrich_pt', {}).get('enriched', 0)
        enrich_es = results.get('enrich_es', {}).get('enriched', 0)
        enrich_fr = results.get('enrich_fr', {}).get('enriched', 0)

        print(f"""
Download:     {results.get('download', {}).get('downloaded', 0)} livros
Tradução:     {results.get('translate', {}).get('translated', 'pulado')} livros
Geração:      {results.get('generate', {}).get('generated', 0)} DOCX
Enriquecido:  PT={enrich_pt} | ES={enrich_es} | FR={enrich_fr}
Limpeza:      Concluída

Tempo total: {self.stats.get('started')} -> {self.stats.get('finished', 'em andamento')}
        """)


async def main():
    parser = argparse.ArgumentParser(description="Orquestrador do Pipeline BooksKDP")

    parser.add_argument("--full", action="store_true", help="Executar pipeline completo")
    parser.add_argument("--step", choices=["download", "translate", "generate", "enrich", "clean"],
                       help="Executar apenas um passo")

    # Configurações de download
    parser.add_argument("--start-id", type=int, default=1, help="ID inicial para download")
    parser.add_argument("--download-limit", type=int, default=100, help="Limite de downloads")

    # Configurações de tradução
    parser.add_argument("--translate-limit", type=int, default=0, help="Limite de traduções")
    parser.add_argument("--source-lang", default="en", help="Idioma de origem")

    # Configurações de geração
    parser.add_argument("--generate-limit", type=int, default=0, help="Limite de geração")
    parser.add_argument("--target-lang", default="pt", help="Idioma alvo")

    # Configurações de enriquecimento
    parser.add_argument("--enrich-lang", default="pt", choices=['pt', 'es', 'fr'], help="Idioma para enriquecer")
    parser.add_argument("--enrich-words", type=int, default=100, help="Palavras por livro")
    parser.add_argument("--enrich-limit", type=int, default=0, help="Limite de livros para enriquecer")

    # Workers
    parser.add_argument("--download-workers", type=int, default=10, help="Workers de download")
    parser.add_argument("--translate-workers", type=int, default=3, help="Workers de tradução")
    parser.add_argument("--generate-workers", type=int, default=4, help="Workers de geração")

    # Outros
    parser.add_argument("--api-key", help="Gemini API Key")
    parser.add_argument("--dir", default="books", help="Diretório base")

    args = parser.parse_args()

    orchestrator = PipelineOrchestrator(
        base_dir=Path(args.dir),
        gemini_api_key=args.api_key or "",
        download_workers=args.download_workers,
        translate_workers=args.translate_workers,
        generate_workers=args.generate_workers
    )

    if args.full:
        await orchestrator.run_full_pipeline(
            args.start_id,
            args.download_limit,
            args.translate_limit,
            args.generate_limit
        )

    elif args.step == "download":
        await orchestrator.step_download(args.start_id, args.download_limit)

    elif args.step == "translate":
        await orchestrator.step_translate(args.source_lang, args.translate_limit)

    elif args.step == "generate":
        orchestrator.step_generate(args.target_lang, args.generate_limit)

    elif args.step == "enrich":
        orchestrator.step_enrich(args.enrich_lang, args.enrich_words, args.enrich_limit)

    elif args.step == "clean":
        orchestrator.step_clean()

    else:
        parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
