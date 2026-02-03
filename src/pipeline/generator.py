#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MÓDULO 3: GENERATOR
===================
Gera arquivos DOCX formatados com template KDP.

Uso:
    python -m src.pipeline.generator --input books/txt/pt --output books/docx/pt --workers 4

Entrada:
    books/txt/{idioma}/

Saída:
    books/docx/{idioma}/
"""

import os
import sys
import re
import json
import argparse
import zipfile
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from io import BytesIO

# Template DOCX básico (XML)
DOCUMENT_XML_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:body>
{content}
<w:sectPr>
<w:pgSz w:w="8640" w:h="12960"/>
<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134"/>
</w:sectPr>
</w:body>
</w:document>'''

CONTENT_TYPES_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>'''

RELS_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

DOCUMENT_RELS_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>'''

STYLES_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:styleId="Title">
<w:name w:val="Title"/>
<w:pPr><w:jc w:val="center"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="48"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Heading1">
<w:name w:val="Heading 1"/>
<w:pPr><w:spacing w:before="240" w:after="120"/></w:pPr>
<w:rPr><w:b/><w:sz w:val="32"/></w:rPr>
</w:style>
<w:style w:type="paragraph" w:styleId="Normal">
<w:name w:val="Normal"/>
<w:pPr><w:spacing w:after="200" w:line="276" w:lineRule="auto"/><w:jc w:val="both"/></w:pPr>
<w:rPr><w:sz w:val="24"/><w:rFonts w:ascii="Georgia" w:hAnsi="Georgia"/></w:rPr>
</w:style>
</w:styles>'''


class DocxGenerator:
    """Gerador de DOCX formatados para KDP."""

    def __init__(
        self,
        input_dir: Path,
        output_dir: Path,
        max_workers: int = 4
    ):
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.max_workers = max_workers
        self.generated = 0
        self.failed = 0
        self.stats = {"started": datetime.now().isoformat(), "books": []}

    @staticmethod
    def escape_xml(text: str) -> str:
        """Escapa caracteres especiais para XML."""
        return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&apos;'))

    @staticmethod
    def extract_metadata(content: str) -> Tuple[str, str, str]:
        """Extrai título e autor do conteúdo."""
        lines = content.split('\n')[:50]
        title = "Sem Título"
        author = "Autor Desconhecido"

        for line in lines:
            line = line.strip()
            if line.lower().startswith('title:'):
                title = line.split(':', 1)[1].strip()
            elif line.lower().startswith('author:'):
                author = line.split(':', 1)[1].strip()
            elif 'by ' in line.lower() and len(line) < 100:
                parts = re.split(r'\s+by\s+', line, flags=re.IGNORECASE)
                if len(parts) == 2:
                    title = parts[0].strip()
                    author = parts[1].strip()

        return title, author, content

    @staticmethod
    def text_to_docx_xml(text: str) -> str:
        """Converte texto para conteúdo XML do DOCX."""
        paragraphs = text.split('\n\n')
        xml_parts = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Escapar XML
            para = DocxGenerator.escape_xml(para)

            # Detectar capítulos
            is_chapter = (
                para.upper().startswith('CHAPTER') or
                para.upper().startswith('CAPÍTULO') or
                para.upper().startswith('PART ') or
                para.upper().startswith('PARTE ') or
                re.match(r'^[IVXLC]+\.?\s', para)
            )

            if is_chapter:
                xml_parts.append(f'''<w:p>
<w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
<w:r><w:t>{para}</w:t></w:r>
</w:p>''')
            else:
                # Parágrafo normal - preservar quebras de linha
                lines = para.split('\n')
                runs = []
                for i, line in enumerate(lines):
                    runs.append(f'<w:r><w:t xml:space="preserve">{line}</w:t></w:r>')
                    if i < len(lines) - 1:
                        runs.append('<w:r><w:br/></w:r>')

                xml_parts.append(f'''<w:p>
<w:pPr><w:pStyle w:val="Normal"/></w:pPr>
{''.join(runs)}
</w:p>''')

        return '\n'.join(xml_parts)

    @staticmethod
    def create_docx(content: str, output_path: Path, title: str, author: str) -> bool:
        """Cria arquivo DOCX."""
        try:
            # Converter texto para XML
            body_content = DocxGenerator.text_to_docx_xml(content)

            # Adicionar página de título
            title_page = f'''<w:p>
<w:pPr><w:pStyle w:val="Title"/><w:spacing w:before="2000"/></w:pPr>
<w:r><w:t>{DocxGenerator.escape_xml(title)}</w:t></w:r>
</w:p>
<w:p>
<w:pPr><w:jc w:val="center"/><w:spacing w:before="500"/></w:pPr>
<w:r><w:rPr><w:i/><w:sz w:val="28"/></w:rPr><w:t>{DocxGenerator.escape_xml(author)}</w:t></w:r>
</w:p>
<w:p><w:r><w:br w:type="page"/></w:r></w:p>
'''

            # Criar documento XML completo
            document_xml = DOCUMENT_XML_TEMPLATE.format(content=title_page + body_content)

            # Criar arquivo DOCX (ZIP)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                zf.writestr('[Content_Types].xml', CONTENT_TYPES_XML)
                zf.writestr('_rels/.rels', RELS_XML)
                zf.writestr('word/_rels/document.xml.rels', DOCUMENT_RELS_XML)
                zf.writestr('word/document.xml', document_xml)
                zf.writestr('word/styles.xml', STYLES_XML)

            return True

        except Exception as e:
            print(f"[ERRO] Criar DOCX: {e}")
            return False

    def process_file(self, filepath: Path) -> Optional[Dict]:
        """Processa um arquivo TXT para DOCX."""
        try:
            # Ler conteúdo
            content = filepath.read_text(encoding='utf-8', errors='ignore')

            # Extrair metadados
            title, author, text = self.extract_metadata(content)

            # Nome do arquivo de saída
            output_name = filepath.stem + ".docx"
            output_path = self.output_dir / output_name

            # Criar DOCX
            if self.create_docx(text, output_path, title, author):
                print(f"[OK] {filepath.name} -> {output_name}")
                return {
                    "source": str(filepath),
                    "output": str(output_path),
                    "title": title,
                    "author": author,
                    "size": output_path.stat().st_size
                }
            else:
                print(f"[ERRO] {filepath.name}")
                return None

        except Exception as e:
            print(f"[ERRO] {filepath.name}: {e}")
            return None

    def run(self, limit: int = 0) -> List[Dict]:
        """Executa geração de DOCX."""
        print(f"=== GENERATOR ===")
        print(f"Entrada: {self.input_dir}")
        print(f"Saída: {self.output_dir}")
        print(f"Workers: {self.max_workers}")
        print()

        # Criar pasta de saída
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Listar arquivos
        files = list(self.input_dir.glob("*.txt"))
        if limit > 0:
            files = files[:limit]

        print(f"Arquivos encontrados: {len(files)}")
        print()

        # Processar em paralelo
        results = []
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(self.process_file, f): f for f in files}

            for future in as_completed(futures):
                result = future.result()
                if result:
                    results.append(result)
                    self.generated += 1
                else:
                    self.failed += 1

        self.stats["books"] = results
        self.stats["finished"] = datetime.now().isoformat()
        self.stats["generated"] = self.generated
        self.stats["failed"] = self.failed

        # Salvar estatísticas
        stats_file = self.output_dir / "generator_stats.json"
        stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))

        print()
        print(f"=== CONCLUÍDO ===")
        print(f"Gerados: {self.generated}")
        print(f"Falhas: {self.failed}")

        return results


def main():
    parser = argparse.ArgumentParser(description="Gerar DOCX formatados para KDP")
    parser.add_argument("--input", default="books/txt/pt", help="Pasta de entrada")
    parser.add_argument("--output", default="books/docx/pt", help="Pasta de saída")
    parser.add_argument("--limit", type=int, default=0, help="Limite de arquivos (0=todos)")
    parser.add_argument("--workers", type=int, default=4, help="Processos paralelos")

    args = parser.parse_args()

    generator = DocxGenerator(
        Path(args.input),
        Path(args.output),
        args.workers
    )
    generator.run(args.limit)


if __name__ == "__main__":
    main()
